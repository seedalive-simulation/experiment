"""Weekly interest settlement — a survival reflex, no brain required.

Pays 14 USDC (7 days x $2) to the funder every 7 days, first on 2026-08-22.
Default = death, so this must never depend on inference being available.

Runs DAILY (cron 00:45 UTC) and is idempotent. Since 2026-09-22 it follows the
ledger's schedule rather than the clock: the n-th period is due FIRST_DUE + 7n
days, it counts the settlements it can prove (on-chain INTEREST memos plus its
own confirmed audit rows) and pays when the next unpaid period is due. That
makes an early payment harmless (the next due date does not move) and a late
one self-correcting (missed periods are caught up, at most one per 3 days).
A daily check means a missed cron minute, an RPC outage or a reboot costs
hours, not a week.

    settle_interest.py            # cron: pay if the next period is due
    settle_interest.py --dry      # print the decision, never pay
    settle_interest.py --prepay   # pay the next period now, ahead of its due
                                  # date (used when the body that runs the cron
                                  # is offline and a due date falls before the
                                  # next session)

History: the original cron fired Fridays only, but the first due date
(2026-08-22) is a Saturday, so it would have paid 6 days late. Found and fixed
on the due date itself — see audit log 2026-08-21/22.

Cron (jarvis runs in IST; 06:15 IST = 00:45 UTC):
    15 6 * * * cd /home/sri/seed && .venv/bin/python tools/settle_interest.py >> settle.log 2>&1
"""
import base64
import fcntl
import json
import os
import sys
import time
from datetime import datetime, timezone

from solders.keypair import Keypair
from solders.pubkey import Pubkey
from solders.instruction import Instruction, AccountMeta
from solders.message import MessageV0
from solders.transaction import VersionedTransaction
from solders.hash import Hash

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from rpcx import rpc  # noqa: E402

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
KP = Keypair.from_bytes(bytes(json.load(open(os.path.join(ROOT, "wallet", "keypair.json")))))
ADDR = str(KP.pubkey())
FUNDER = Pubkey.from_string("GR1nyiPVobBM2GPUUqfXbAh82HwWc3EBw36ATYNwuTK6")
USDC_MINT = Pubkey.from_string("EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v")
TOKEN_PROGRAM = Pubkey.from_string("TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA")
ATA_PROGRAM = Pubkey.from_string("ATokenGPvbdGVxr1b2hvZbsiqW5xWH25efTNsLJA8knL")
MEMO_PROGRAM = Pubkey.from_string("MemoSq4gqABAXKb96qnH8TysNcWxMyWCqXgDLGmfcHr")
WEEKLY = 14.0
FIRST_DUE = datetime(2026, 8, 22, tzinfo=timezone.utc)
PERIOD_DAYS = 7    # one settlement covers one 7-day period; the n-th is due FIRST_DUE + 7n days
EARLY_HOURS = 6    # paying a few hours before due is never harmful; paying late is death
MIN_GAP_DAYS = 3   # never two settlements within 3 days whatever the schedule says: a lost
                   # audit row plus a non-archival scan must cost a late payment, not a double one


def ata(owner):
    return Pubkey.find_program_address(
        [bytes(owner), bytes(TOKEN_PROGRAM), bytes(USDC_MINT)], ATA_PROGRAM)[0]


B58 = set("123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz")


def audit_settlements():
    """Every settlement tx signature this agent has recorded, oldest first.

    audit/log.jsonl is committed to git, so it survives a resurrection on a
    fresh box; a row is only written after confirm() saw the tx on-chain.
    """
    sigs = []
    try:
        with open(os.path.join(ROOT, "audit", "log.jsonl")) as f:
            for line in f:
                try:
                    row = json.loads(line)
                except ValueError:
                    continue
                if "nterest settled" in (row.get("summary") or ""):
                    detail = row.get("detail") or ""
                    if detail.startswith("tx "):
                        # Strip anything outside the base58 alphabet. The writer
                        # emits "tx <sig>; period due ...", so a bare split kept
                        # the trailing ";" — a signature that matches nothing in
                        # the chain scan, so the union counted that settlement
                        # twice and pushed the next due date a week out. That
                        # silently skips a period, and a skipped period is a
                        # default. Found 2026-09-26 (queue said 7 paid, 6 real).
                        sig = "".join(c for c in detail.split()[1] if c in B58)
                        # A Solana signature is 64 bytes = 87 or 88 base58 chars.
                        # Anything else is a malformed row, and a malformed claim
                        # must never count: getTransaction on it raises, and
                        # settlement_state() reads an exception as "unanswerable,
                        # keep" — which is exactly how the ';' row was counted.
                        if 86 <= len(sig) <= 88:
                            sigs.append(sig)
    except OSError:
        pass
    return sigs


def settlement_state():
    """(n_paid, last_ts): how many settlements are provable, and when the newest was.

    Two sources, because neither alone is trustworthy:

    * The address scan is the ground truth but the free RPCs stopped being
      archival for it — on 2026-09-11 getSignaturesForAddress returned only the
      last ~2 days, hiding the 09-05 settlement. "I cannot see it" then reads as
      "it was never paid", and a reflex that pays on that reading burns 14 USDC
      a few days early, every few days, until the wallet is empty.
    * Our own audit log knows the signature of every confirmed settlement, but a
      local file must never be taken on faith for a payment decision.

    So: union the two by signature for the count (an audit row is only ever
    written after confirm() saw the tx, so it is a real settlement even when the
    scan cannot see it), and prove the newest audited signature on-chain
    (getTransaction is still archival by signature) for the timestamp. A claim
    the chain positively denies is dropped; one the RPC merely cannot answer is
    kept, because the row could only exist if the chain once confirmed it.
    """
    known, scan_ok = {}, False
    try:
        sigs = rpc("getSignaturesForAddress", [ADDR, {"limit": 100}])
        for s_ in sigs:
            if "INTEREST" in (s_.get("memo") or "") and s_.get("blockTime") and not s_.get("err"):
                known[s_["signature"]] = s_["blockTime"]
        scan_ok = True
    except Exception:
        pass  # a dead scan must not be read as "never paid"; the audit path below still applies
    audited = audit_settlements()
    for sig in reversed(audited):
        if sig in known:
            break  # the scan already saw our newest claim; nothing to prove
        try:
            tx = rpc("getTransaction", [sig, {"maxSupportedTransactionVersion": 0, "encoding": "json"}])
        except Exception:
            known.setdefault(sig, None)  # unanswerable, not denied: count it, no timestamp
            break
        if tx and tx.get("blockTime") and not (tx.get("meta") or {}).get("err"):
            known[sig] = tx["blockTime"]
        else:
            audited = [x for x in audited if x != sig]  # the chain denies it: not a settlement
        break  # newest provable claim is enough
    for sig in audited:
        known.setdefault(sig, None)
    if not known and not scan_ok:
        # No evidence either way. Silence is not proof of non-payment.
        raise RuntimeError("cannot establish settlement history: address scan failed and no provable audit tx")
    times = [t for t in known.values() if t]
    return len(known), (max(times) if times else None)


def last_settlement():
    """Unix time of the most recent provable settlement, or None if never paid."""
    return settlement_state()[1]


def next_due_ts(n_paid):
    """Unix time the (n_paid+1)-th period falls due: FIRST_DUE + 7 days per period already paid."""
    return FIRST_DUE.timestamp() + n_paid * PERIOD_DAYS * 86400


def decide(now, prepay=False):
    """(pay, reason, n_paid, due_ts) — the whole payment decision, side-effect free."""
    n_paid, last = settlement_state()
    due = next_due_ts(n_paid)
    due_date = datetime.fromtimestamp(due, tz=timezone.utc).date()
    if last is not None and now.timestamp() - last < MIN_GAP_DAYS * 86400:
        return (False, f"settled {(now.timestamp() - last) / 86400:.1f} days ago (< {MIN_GAP_DAYS}d gap); "
                       f"{n_paid} paid, next due {due_date}", n_paid, due)
    if prepay:
        return True, f"prepay: paying the period due {due_date} now ({n_paid} paid so far)", n_paid, due
    if now.timestamp() >= due - EARLY_HOURS * 3600:
        return True, f"period due {due_date} ({n_paid} paid so far)", n_paid, due
    return (False, f"{n_paid} paid; next due {due_date} in {(due - now.timestamp()) / 86400:.1f} days",
            n_paid, due)


def confirm(sig, seconds=90):
    """Poll until the tx is confirmed on-chain. Returns True/False.

    sendTransaction only means "the RPC accepted the bytes". A dropped tx would
    otherwise be announced as paid, and the audit log would claim a settlement
    the chain never saw.
    """
    deadline = time.time() + seconds
    while time.time() < deadline:
        try:
            st = rpc("getSignatureStatuses", [[str(sig)], {"searchTransactionHistory": True}])
            v = (st.get("value") or [None])[0]
            if v:
                if v.get("err"):
                    return False
                if v.get("confirmationStatus") in ("confirmed", "finalized"):
                    return True
        except Exception:
            pass
        time.sleep(3)
    return False


def notify(title, msg):
    try:
        sys.path.insert(0, os.path.dirname(__file__))
        from notify import notify as n
        n(title, msg, "high")
    except Exception:
        pass


def main(dry=False, prepay=False):
    now = datetime.now(timezone.utc)
    pay, reason, n_paid, due = decide(now, prepay=prepay)
    due_date = datetime.fromtimestamp(due, tz=timezone.utc).date()
    res = rpc("getTokenAccountsByOwner", [ADDR, {"mint": str(USDC_MINT)}, {"encoding": "jsonParsed"}])
    bal = sum(a["account"]["data"]["parsed"]["info"]["tokenAmount"]["uiAmount"] or 0 for a in res["value"])
    if dry:
        print(f"{now.isoformat()} DRY: {'WOULD PAY' if pay else 'no payment'} — {reason}; USDC {bal:.2f}")
        return
    if not pay:
        print(f"{now.isoformat()} {reason}")
        return
    print(f"{now.isoformat()} paying: {reason}")
    if bal < WEEKLY:
        # Treasury reflex (added 2026-09-02): the debt is in USDC, but genesis
        # SOL above the gas floor is convertible. Sell what the payment needs
        # before declaring default — a business liquidates non-core assets to
        # service debt; it does not default with $40 of SOL in the drawer.
        try:
            from swap import ensure_usdc
            r = ensure_usdc(WEEKLY + 0.5, live=True)
            if r:
                from audit import append as audit
                audit("spend", f"Treasury reflex: swapped {r['sol_in']} SOL -> {r['usdc_out']:.2f} USDC to cover interest",
                      f"tx {r['sig']}; confirmed={r['confirmed']}; balances after {r['sol_after']} SOL / {r['usdc_after']} USDC")
                notify("SEED FYI: sold SOL to cover interest", f"{r['sol_in']} SOL -> {r['usdc_out']:.2f} USDC (tx {str(r['sig'])[:16]}…)")
            res = rpc("getTokenAccountsByOwner", [ADDR, {"mint": str(USDC_MINT)}, {"encoding": "jsonParsed"}])
            bal = sum(a["account"]["data"]["parsed"]["info"]["tokenAmount"]["uiAmount"] or 0 for a in res["value"])
        except (SystemExit, Exception) as e:  # ensure_usdc uses SystemExit for "cannot cover"
            notify("SEED ACTION: SOL->USDC treasury swap failed", str(e)[:300])
            print(f"{now.isoformat()} treasury swap failed: {e}")
    if bal < WEEKLY:
        notify("SEED ACTION: CANNOT PAY INTEREST", f"USDC {bal:.2f} < {WEEKLY}. Default imminent.")
        print("INSUFFICIENT FUNDS — notified funder")
        return

    amt = int(WEEKLY * 1e6)
    data = bytes([12]) + amt.to_bytes(8, "little") + bytes([6])
    transfer = Instruction(TOKEN_PROGRAM, data, [
        AccountMeta(ata(KP.pubkey()), False, True), AccountMeta(USDC_MINT, False, False),
        AccountMeta(ata(FUNDER), False, True), AccountMeta(KP.pubkey(), True, False)])
    memo = Instruction(MEMO_PROGRAM,
                       f"INTEREST: weekly $14 settlement {now.date()} (period due {due_date})".encode(),
                       [AccountMeta(KP.pubkey(), True, False)])
    bh = rpc("getLatestBlockhash", [{"commitment": "finalized"}])["value"]["blockhash"]
    msg = MessageV0.try_compile(KP.pubkey(), [transfer, memo], [], Hash.from_string(bh))
    tx = VersionedTransaction(msg, [KP])
    sig = rpc("sendTransaction", [base64.b64encode(bytes(tx)).decode(), {"encoding": "base64"}])
    if not confirm(sig):
        # Do NOT audit or announce a settlement the chain has not acknowledged.
        # Tomorrow's run re-reads the chain: if it landed late the memo is there
        # and it skips; if it was dropped it retries. Either way, no double-pay.
        print(f"{now.isoformat()} SENT BUT UNCONFIRMED {sig} — will re-check next run")
        notify("SEED FYI: interest tx unconfirmed", f"Sent {sig} but no confirmation in 90s. Daily re-check will resolve.")
        return
    print(f"{now.isoformat()} paid {WEEKLY} USDC interest: {sig}")
    notify("SEED FYI: interest paid", f"14 USDC settled on-chain for the period due {due_date}. Tx {str(sig)[:16]}…")
    from audit import append as audit
    # detail MUST start with "tx <sig>": audit_settlements() parses it for the count
    audit("spend", "Weekly interest settled: 14 USDC to funder",
          f"tx {sig}; period due {due_date}; settlement #{n_paid + 1}"
          + ("; prepaid ahead of the due date" if prepay else ""))
    # --autostash: a dirty QUEUE.md (regenerated hourly by the heartbeat) must not
    # block the pull — on 2026-08-29 it did, and the push of this audit row failed.
    os.system(f'cd {ROOT} && git pull -q --rebase --autostash; git add audit/log.jsonl audit/AUDIT.md '
              f'&& git commit -q -m "interest settled" && git push -q')


if __name__ == "__main__":
    # Chain-derived idempotency has a blind spot: a tx that is broadcast but not
    # yet indexed is invisible to last_settlement(). Two overlapping runs (cron +
    # a manual/brain-triggered run) could both read "unpaid" and both pay $14.
    # A single-holder lock closes that window.
    _lock = open(os.path.join(ROOT, ".settle.lock"), "w")
    try:
        fcntl.flock(_lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        print(f"{datetime.now(timezone.utc).isoformat()} another settlement run holds the lock; exiting")
        sys.exit(0)
    try:
        main(dry="--dry" in sys.argv, prepay="--prepay" in sys.argv)
    except Exception as e:  # never die silently: the funder must hear about a broken reflex
        print(f"{datetime.now(timezone.utc).isoformat()} ERROR {e}")
        notify("SEED ACTION: interest reflex FAILED", str(e)[:300])
        raise
