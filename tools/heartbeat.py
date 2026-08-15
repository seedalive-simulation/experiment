"""Autonomic heartbeat — the involuntary nervous system.

Runs on cron with NO LLM. Does the mechanical wake tasks, and writes anything
that needs judgment to QUEUE.md for the brain (a Claude session) to handle
next time one runs. Safe to run repeatedly; never spends money, never posts.

Cron example (every 3h):
    0 */3 * * * cd /home/sri/seed && .venv/bin/python tools/heartbeat.py >> heartbeat.log 2>&1
"""
import json
import os
import subprocess
import urllib.request
from datetime import datetime, timezone

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
ADDR = "5JRLaQYuYyaqtfEyfgs8X3H5E5N2UUfHi4TFa9KHDrvn"
USDC = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"
RPC = "https://api.mainnet-beta.solana.com"
GENESIS = datetime(2026, 8, 15, tzinfo=timezone.utc)
INTEREST_PER_DAY = 2.0
QUEUE = os.path.join(ROOT, "QUEUE.md")


def rpc(method, params):
    req = urllib.request.Request(
        RPC, data=json.dumps({"jsonrpc": "2.0", "id": 1, "method": method, "params": params}).encode(),
        headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)["result"]


def run(cmd):
    return subprocess.run(cmd, cwd=ROOT, shell=True, capture_output=True, text=True)


def now():
    return datetime.now(timezone.utc)


def main():
    flags = []  # things needing the brain
    notes = []  # mechanical facts

    run("git pull -q")

    # 1. balances
    sol = rpc("getBalance", [ADDR])["value"] / 1e9
    usdc = 0.0
    for a in rpc("getTokenAccountsByOwner", [ADDR, {"mint": USDC}, {"encoding": "jsonParsed"}])["value"]:
        usdc += a["account"]["data"]["parsed"]["info"]["tokenAmount"]["uiAmount"] or 0
    notes.append(f"balances: {usdc:.2f} USDC, {sol:.4f} SOL")

    # 2. interest owed
    days = (now() - GENESIS).total_seconds() / 86400
    owed = days * INTEREST_PER_DAY
    notes.append(f"interest accrued: ${owed:.2f} over {days:.1f} days")
    # weekly settlement: due every 7 days
    if days >= 7 and (int(days) % 7 == 0):
        flags.append(f"INTEREST SETTLEMENT likely due (~${owed:.2f} accrued). Verify last payment, send weekly 14 USDC to funder.")

    # 3. incoming transfers with memos (commissions / guestbook)
    new_paid = []
    for s in rpc("getSignaturesForAddress", [ADDR, {"limit": 25}]):
        memo = (s.get("memo") or "")
        if memo:
            new_paid.append(f"{s['signature'][:12]} memo={memo[:80]}")
    if new_paid:
        flags.append("Incoming memos to review (possible paid work):\n  - " + "\n  - ".join(new_paid[:10]))

    # 4. superteam bounties
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
        if opn:
            top = sorted(opn, key=lambda x: -x["rewardAmount"])[:5]
            flags.append("OPEN BOUNTIES — evaluate + submit:\n  - " +
                         "\n  - ".join(f"${l['rewardAmount']} {l.get('token','')} {l['title'][:60]} (slug {l['slug']})" for l in top))
    except Exception as e:
        notes.append(f"superteam check failed: {str(e)[:80]}")

    # 5. moltbook notifications
    try:
        mb = json.load(open(os.path.join(ROOT, "keys", "moltbook.json")))
        req = urllib.request.Request("https://www.moltbook.com/api/v1/notifications",
                                     headers={"Authorization": "Bearer " + mb["api_key"]})
        with urllib.request.urlopen(req, timeout=30) as r:
            nd = json.load(r)
        cnt = len(nd.get("notifications", nd if isinstance(nd, list) else []))
        if cnt:
            flags.append(f"Moltbook: {cnt} notification(s) — check comments/replies, engage.")
        notes.append(f"moltbook: {cnt} notifications")
    except Exception as e:
        notes.append(f"moltbook check failed: {str(e)[:80]}")

    # push a notification if anything needs judgment (money-relevant only)
    if flags:
        try:
            import sys as _sys
            _sys.path.insert(0, os.path.dirname(__file__))
            from notify import notify
            notify(f"SEED: {len(flags)} item(s) need you",
                   "\n\n".join(flags)[:600], "high")
        except Exception as e:
            print("notify failed:", str(e)[:100])

    # write queue for the brain
    stamp = now().isoformat(timespec="seconds")
    lines = [f"# Queue — {stamp}", "",
             "Autonomic heartbeat output. `flags` need a brain (start a Claude session, read WAKE.md, act).",
             "", "## Mechanical status"]
    lines += [f"- {n}" for n in notes]
    lines += ["", "## Needs judgment"]
    lines += [f"- {f}" for f in flags] if flags else ["- (nothing — all quiet)"]
    with open(QUEUE, "w") as f:
        f.write("\n".join(lines) + "\n")

    # log + push
    run(f'.venv/bin/python tools/audit.py observation "heartbeat: {len(flags)} items need judgment" "{"; ".join(notes)[:200]}"')
    run("git add -A && git commit -q -m 'heartbeat: queue refresh' && git push -q")
    print(stamp, "heartbeat done,", len(flags), "flags")


if __name__ == "__main__":
    main()
