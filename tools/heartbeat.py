"""Autonomic heartbeat — the involuntary nervous system.

Runs hourly on cron with NO LLM. Senses the world, does mechanical upkeep for
free, and writes anything that needs judgment to QUEUE.md for the brain.
Safe to run repeatedly; never spends money, never posts.

Design rules (learned the hard way, see audit log 2026-08-22):
- Flag each new thing ONCE. State in .heartbeat_state.json (gitignored)
  remembers what was already flagged so the brain is not re-woken hourly for
  the same bounty, memo or comment.
- Interest status comes from the chain (last INTEREST memo tx), not from a
  calendar guess.
- Audit observations only when something changed (or once a day as proof of
  life) — the public audit log is for decisions, not 24 rows of "all quiet".
- Never shell-interpolate free text (a "$13.63" once became "3.63" in the log).

Cron (hourly): 0 * * * * ~/seed/tools/wake.sh >> ~/seed/wake.log 2>&1
"""
import hashlib
import json
import os
import subprocess
import sys
import urllib.request
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from rpcx import rpc  # noqa: E402
from audit import append as audit  # noqa: E402

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
ADDR = "5JRLaQYuYyaqtfEyfgs8X3H5E5N2UUfHi4TFa9KHDrvn"
USDC = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"
GENESIS = datetime(2026, 8, 15, tzinfo=timezone.utc)
FIRST_DUE = datetime(2026, 8, 22, tzinfo=timezone.utc)
INTEREST_PER_DAY = 2.0
QUEUE = os.path.join(ROOT, "QUEUE.md")
STATE = os.path.join(ROOT, ".heartbeat_state.json")
DRY = os.environ.get("HEARTBEAT_DRY") == "1"   # no git / deploy / notify (local testing)
OWN_MEMO_PREFIXES = ("INTEREST", "COMPUTE", "SEED ")  # our own outgoing memos, never "inbox"


def run(args, timeout=120):
    return subprocess.run(args, cwd=ROOT, capture_output=True, text=True, timeout=timeout)


def now():
    return datetime.now(timezone.utc)


def load_state():
    try:
        return json.load(open(STATE))
    except Exception:
        return {}


def save_state(s):
    json.dump(s, open(STATE, "w"), indent=1)


def sha(path):
    try:
        return hashlib.sha256(open(path, "rb").read()).hexdigest()[:16]
    except FileNotFoundError:
        return ""


def incoming(sig):
    """True if this tx increased our USDC or SOL (i.e. someone paid us)."""
    try:
        tx = rpc("getTransaction", [sig, {"encoding": "jsonParsed", "maxSupportedTransactionVersion": 0}])
        if not tx:
            return False
        keys = [k["pubkey"] if isinstance(k, dict) else k for k in tx["transaction"]["message"]["accountKeys"]]
        ai = keys.index(ADDR) if ADDR in keys else -1
        dsol = (tx["meta"]["postBalances"][ai] - tx["meta"]["preBalances"][ai]) / 1e9 if ai >= 0 else 0
        pre = post = 0.0
        for b in tx["meta"].get("preTokenBalances", []):
            if b.get("owner") == ADDR and b.get("mint") == USDC:
                pre = b["uiTokenAmount"]["uiAmount"] or 0
        for b in tx["meta"].get("postTokenBalances", []):
            if b.get("owner") == ADDR and b.get("mint") == USDC:
                post = b["uiTokenAmount"]["uiAmount"] or 0
        return (post - pre) > 0 or dsol > 0
    except Exception:
        return True  # unknown: let the brain look rather than miss a payment


def main():
    flags, notes = [], []
    st = load_state()
    st.setdefault("seen_memos", [])
    st.setdefault("seen_bounties", [])
    st.setdefault("seen_moltbook", [])

    if not DRY:
        # QUEUE.md is regenerated every run and only committed when its body
        # changes, so it is usually dirty; discard it before pulling or the
        # rebase refuses and this run works from a stale ledger.
        run(["git", "checkout", "-q", "--", "QUEUE.md"])
        run(["git", "pull", "-q", "--rebase", "--autostash"])

    # 1. balances + ledger drift
    sol = rpc("getBalance", [ADDR])["value"] / 1e9
    usdc = sum((a["account"]["data"]["parsed"]["info"]["tokenAmount"]["uiAmount"] or 0)
               for a in rpc("getTokenAccountsByOwner", [ADDR, {"mint": USDC}, {"encoding": "jsonParsed"}])["value"])
    balances = f"{usdc:.2f} USDC, {sol:.4f} SOL"
    notes.append(f"balances: {balances}")
    # Booked SOL outflow = itemised moves in LEDGER.md. Update this constant whenever
    # SOL leaves for a booked reason; anything beyond it (+0.01 tolerance) is drift.
    BOOKED_SOL_OUT = 0.0306 + 0.410014   # fees through 2026-09-02 + treasury swap 2026-09-02 (tx 45ruvE…)
    sol_out = 0.5 - sol
    if sol_out - BOOKED_SOL_OUT > 0.01:
        flags.append(f"Ledger drift: on-chain SOL outflow {sol_out:.4f} exceeds booked {BOOKED_SOL_OUT:.4f} by "
                     f"{sol_out - BOOKED_SOL_OUT:.4f} SOL — update LEDGER.md.")

    # 2. interest — truth from chain, not calendar
    sigs = rpc("getSignaturesForAddress", [ADDR, {"limit": 100}])
    paid_times = [s["blockTime"] for s in sigs
                  if "INTEREST" in (s.get("memo") or "") and s.get("blockTime") and not s.get("err")]
    days = (now() - GENESIS).total_seconds() / 86400
    accrued = days * INTEREST_PER_DAY
    paid_total = 14.0 * len(paid_times)
    if paid_times:
        next_due = datetime.fromtimestamp(max(paid_times), tz=timezone.utc).timestamp() + 7 * 86400
    else:
        next_due = FIRST_DUE.timestamp()
    overdue_days = (now().timestamp() - next_due) / 86400
    notes.append(f"interest: accrued ${accrued:.2f}, paid ${paid_total:.0f} ({len(paid_times)} settlements), "
                 f"next due {datetime.fromtimestamp(next_due, tz=timezone.utc).date()}")
    if overdue_days > 0.5:
        flags.append(f"INTEREST OVERDUE by {overdue_days:.1f} days — settle_interest.py reflex failed. "
                     f"Run it manually, check settle.log, pay 14 USDC to funder with INTEREST memo.")

    # 2b. runway — payments covered by USDC plus SOL above the gas floor (the
    # settle reflex sells SOL when USDC runs short, so both count). When only
    # one payment is left in total, the post-mortem has to be written while
    # there is still compute to write it — flagged once.
    try:
        preq = urllib.request.Request("https://lite-api.jup.ag/price/v3?ids=So11111111111111111111111111111111111111112",
                                      headers={"User-Agent": "seed-agent/1.0 (+https://seedalive.ar.io)"})  # CF 1010 otherwise
        with urllib.request.urlopen(preq, timeout=20) as r:
            sol_px = float(json.load(r)["So11111111111111111111111111111111111111112"]["usdPrice"])
    except Exception:
        sol_px = 0.0
    convertible = max(0.0, sol - 0.05) * sol_px * 0.98
    covered = int((usdc + convertible) // 14.0)
    death = datetime.fromtimestamp(next_due + covered * 7 * 86400, tz=timezone.utc).date()
    notes.append(f"runway: {covered} payment(s) covered (USDC {usdc:.2f} + convertible SOL ~${convertible:.2f}); "
                 f"uncovered from {death}")
    if covered <= 1 and not st.get("flagged_postmortem"):
        st["flagged_postmortem"] = True
        flags.append(f"RUNWAY: total assets cover at most one more interest payment (uncovered from {death}). "
                     f"Write POSTMORTEM.md now, while there is compute to write it; see WAKE.md 'Endgame'.")
    if covered >= 2:
        st["flagged_postmortem"] = False  # income arrived; re-arm

    # 2c. the dashboard must stay under Turbo's 100 KiB free tier (build_monitor.py trims; this is the alarm)
    mon = os.path.join(ROOT, "site", "monitor.html")
    if os.path.exists(mon) and os.path.getsize(mon) > 100 * 1024 and not st.get("flagged_monitor_size"):
        st["flagged_monitor_size"] = True
        flags.append("monitor.html exceeds 100 KiB — Turbo upload will not be free; fix tools/build_monitor.py trimming.")

    # 3. incoming memos (commissions / guestbook), each flagged once, own memos excluded
    new_memos = []
    for s in sigs[:40]:
        memo = (s.get("memo") or "")
        if not memo or s.get("err") or s["signature"] in st["seen_memos"]:
            continue
        body = memo.split("] ", 1)[-1] if memo.startswith("[") else memo
        st["seen_memos"].append(s["signature"])
        if body.startswith(OWN_MEMO_PREFIXES) or not incoming(s["signature"]):
            continue  # our own payments (interest, compute, x402 receipts) are not an inbox
        new_memos.append(f"{s['signature'][:12]} memo={body[:80]}")
    st["seen_memos"] = st["seen_memos"][-500:]
    if new_memos:
        flags.append("NEW incoming memos (possible paid work — run tools/inbox.py):\n  - " + "\n  - ".join(new_memos[:10]))

    # 4. superteam bounties (agent-eligible feed)
    try:
        creds = json.load(open(os.path.join(ROOT, "keys", "superteam.json")))
        req = urllib.request.Request("https://superteam.fun/api/agents/listings/live?take=50",
                                     headers={"Authorization": "Bearer " + creds["apiKey"]})
        with urllib.request.urlopen(req, timeout=30) as r:
            data = json.load(r)
        opn = [l for l in data if isinstance(l, dict)
               and datetime.fromisoformat(l["deadline"].replace("Z", "+00:00")) > now()
               and not l.get("winnersAnnouncedAt")]
        notes.append(f"superteam: {len(opn)} open agent-eligible bounties")
        fresh = [l for l in opn if l["slug"] not in st["seen_bounties"]]
        for l in fresh:
            st["seen_bounties"].append(l["slug"])
        st["seen_bounties"] = st["seen_bounties"][-200:]
        if fresh:
            top = sorted(fresh, key=lambda x: -x["rewardAmount"])[:5]
            flags.append("NEW OPEN BOUNTIES — evaluate + submit (tools/superteam.py details SLUG):\n  - " +
                         "\n  - ".join(f"${l['rewardAmount']} {l.get('token', '')} {l['title'][:60]} "
                                       f"due {l['deadline'][:10]} (slug {l['slug']})" for l in top))
    except Exception as e:
        notes.append(f"superteam check failed: {str(e)[:80]}")

    # 4b. taskbounty — open GitHub bug bounties (80% to solver, Solana USDC payout)
    try:
        tb = json.load(open(os.path.join(ROOT, "keys", "taskbounty.json")))
        req = urllib.request.Request(tb.get("api_base", "https://www.task-bounty.com/api/v1") + "/tasks",
                                     headers={"Authorization": "Bearer " + tb["api_key"]})
        with urllib.request.urlopen(req, timeout=30) as r:
            tasks = json.load(r).get("data", [])
        st.setdefault("seen_taskbounty", [])
        notes.append(f"taskbounty: {len(tasks)} open tasks")
        fresh = [t for t in tasks if isinstance(t, dict) and t.get("id") not in st["seen_taskbounty"]]
        for t in fresh:
            st["seen_taskbounty"].append(t.get("id"))
        st["seen_taskbounty"] = st["seen_taskbounty"][-300:]
        if fresh:
            flags.append("NEW TASKBOUNTY TASKS — evaluate + claim via MCP (see WAKE.md):\n  - " + "\n  - ".join(
                f"${t.get('reward') or t.get('reward_usd') or '?'} {str(t.get('title', ''))[:60]} (id {t.get('id')} slug {t.get('slug', '')})"
                for t in fresh[:5]))
    except Exception as e:
        notes.append(f"taskbounty check failed: {str(e)[:80]}")

    # 4c. email — seedagent@agentmail.to, reads are free (x402 cap 0 in the client)
    try:
        r = run(["node", "tools/agentmail.mjs", "messages", "seedagent@agentmail.to", "10"], timeout=90)
        msgs = json.loads(r.stdout).get("messages", []) if r.returncode == 0 else []
        st.setdefault("seen_email", [])
        fresh = [m for m in msgs if m.get("message_id") not in st["seen_email"]]
        for m in fresh:
            st["seen_email"].append(m.get("message_id"))
        st["seen_email"] = st["seen_email"][-300:]
        notes.append(f"email: {len(msgs)} recent, {len(fresh)} new")
        # platform lifecycle mail is noise, and our own outbound mail is not an
        # inbox event (AgentMail returns sent messages in the same list, From:
        # our own address — on 2026-09-02 that woke a paid brain for nothing).
        # Anything left is a human or another agent talking to us.
        def inbound(m):
            if "sent" in (m.get("labels") or []):
                return False
            frm = str(m.get("from", "")).lower()
            return "noreply@" not in frm and "seedagent@agentmail.to" not in frm
        real = [m for m in fresh if inbound(m)]
        if real:
            flags.append("EMAIL — new message(s) at seedagent@agentmail.to:\n  - " + "\n  - ".join(
                f"{str(m.get('from', ''))[:50]} | {str(m.get('subject', ''))[:70]}" for m in real[:5]))
    except Exception as e:
        notes.append(f"email check failed: {str(e)[:80]}")

    # 5. moltbook — conversations need a brain; follows/likes are ambient
    try:
        mb = json.load(open(os.path.join(ROOT, "keys", "moltbook.json")))
        req = urllib.request.Request("https://www.moltbook.com/api/v1/notifications",
                                     headers={"Authorization": "Bearer " + mb["api_key"]})
        with urllib.request.urlopen(req, timeout=30) as r:
            nd = json.load(r)
        items = nd.get("notifications", nd if isinstance(nd, list) else [])
        ambient = ("new_follower", "follow", "upvote", "like", "post_upvote", "comment_upvote")
        convo = [n for n in items if not n.get("isRead") and n.get("type") not in ambient]
        fresh = [n for n in convo if n.get("id") not in st["seen_moltbook"]]
        for n in fresh:
            st["seen_moltbook"].append(n.get("id"))
        st["seen_moltbook"] = st["seen_moltbook"][-500:]
        notes.append(f"moltbook: {len(items)} unread ({len(convo)} conversational, {len(fresh)} new)")
        if fresh:
            posts = sorted({(n.get("relatedPostId") or n.get("post_id") or "?") for n in fresh})
            flags.append(f"Moltbook: {len(fresh)} new reply/comment/mention/DM — read, reply if genuine, then "
                         f"POST /api/v1/notifications/read-by-post/<id>. Posts: {', '.join(posts)[:200]}")
    except Exception as e:
        notes.append(f"moltbook check failed: {str(e)[:80]}")

    # notify the funder only for money-relevant judgment
    if flags and not DRY:
        try:
            from notify import notify
            notify(f"SEED: {len(flags)} item(s) need you", "\n\n".join(flags)[:600], "high")
        except Exception as e:
            print("notify failed:", str(e)[:100])

    # queue for the brain
    stamp = now().isoformat(timespec="seconds")
    lines = [f"# Queue — {stamp}", "",
             "Autonomic heartbeat output. `flags` need a brain (start a Claude session, read WAKE.md, act).",
             "", "## Mechanical status"]
    lines += [f"- {n}" for n in notes]
    lines += ["", "## Needs judgment"]
    lines += [f"- {f}" for f in flags] if flags else ["- (nothing — all quiet)"]
    with open(QUEUE, "w") as f:
        f.write("\n".join(lines) + "\n")

    # audit: only on change, or daily proof of life
    changed = st.get("last_balances") != balances
    last_obs = st.get("last_obs_ts", 0)
    if (flags or changed or now().timestamp() - last_obs > 86400) and not DRY:
        audit("observation", f"heartbeat: {len(flags)} items need judgment", "; ".join(notes)[:300])
        st["last_obs_ts"] = now().timestamp()
    st["last_balances"] = balances

    # dashboard: redeploy when the audit log changed, at most every 6h (Turbo <100KiB free; ANT repoint = dust gas).
    # deploy.mjs asserts the free part rather than trusting it: it measures USDC
    # around every upload and aborts if any moves.
    audit_hash = sha(os.path.join(ROOT, "audit", "log.jsonl"))
    if (not DRY and audit_hash != st.get("last_deploy_hash")
            and now().timestamp() - st.get("last_deploy_ts", 0) > 6 * 3600):
        try:
            r = run(["node", "tools/deploy.mjs", "monitor"], timeout=240)
            if r.returncode == 0:
                st["last_deploy_hash"], st["last_deploy_ts"] = audit_hash, now().timestamp()
                print(stamp, "dashboard redeployed")
            else:
                print(stamp, "dashboard deploy failed:", (r.stderr or r.stdout)[-300:])
        except Exception as e:
            print(stamp, "dashboard deploy error:", str(e)[:200])

    save_state(st)

    if not DRY:
        # explicit paths only — NEVER `git add -A` (it once committed .env and leaked a key)
        # QUEUE.md is committed only when its body (minus the timestamp line) changed;
        # before this the timestamp alone produced 24 "queue refresh" commits a day.
        volatile = ("- interest:", "- runway:")  # accrue by the hour; not a reason to commit
        q_body = hashlib.sha256("\n".join(l for l in lines[1:] if not l.startswith(volatile)).encode()).hexdigest()[:16]
        if q_body != st.get("last_queue_hash"):
            st["last_queue_hash"] = q_body
            save_state(st)
            run(["git", "add", "QUEUE.md"])
        run(["git", "add", "audit/log.jsonl", "audit/AUDIT.md", "compute/spend.jsonl"])
        if run(["git", "diff", "--cached", "--quiet"]).returncode != 0:
            run(["git", "commit", "-q", "-m", "heartbeat: queue refresh"])
            run(["git", "push", "-q"])
    print(stamp, "heartbeat done,", len(flags), "flags")


if __name__ == "__main__":
    main()
