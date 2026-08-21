"""Weekly interest settlement — a survival reflex, no brain required.

Pays 14 USDC (7 days x $2) to the funder every 7 days, first on 2026-08-22.
Default = death, so this must never depend on inference being available.

Runs DAILY (cron 00:45 UTC) and is idempotent: it reads the chain for the last
INTEREST memo tx and pays only when >= 6.9 days have elapsed since it (or since
the first-due date when nothing has been paid yet). A daily check means a missed
cron minute, an RPC outage or a reboot costs hours, not a week.

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
PERIOD_DAYS = 6.9  # pay once >= this many days since the last settlement (weekly cadence, daily check)
EARLY_HOURS = 6    # paying a few hours before due is never harmful; paying late is death


def ata(owner):
    return Pubkey.find_program_address(
        [bytes(owner), bytes(TOKEN_PROGRAM), bytes(USDC_MINT)], ATA_PROGRAM)[0]


def last_settlement():
    """Unix time of the most recent INTEREST memo tx, or None if never paid."""
    sigs = rpc("getSignaturesForAddress", [ADDR, {"limit": 100}])
    times = [s["blockTime"] for s in sigs
             if "INTEREST" in (s.get("memo") or "") and s.get("blockTime") and not s.get("err")]
    return max(times) if times else None


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


def main():
    now = datetime.now(timezone.utc)
    if (FIRST_DUE - now).total_seconds() > EARLY_HOURS * 3600:
        print(f"{now.isoformat()} not yet due (first due {FIRST_DUE.date()})")
        return
    last = last_settlement()
    if last is not None:
        since = (now.timestamp() - last) / 86400
        if since < PERIOD_DAYS:
            print(f"{now.isoformat()} settled {since:.1f} days ago; next in {PERIOD_DAYS - since:.1f} days")
            return

    res = rpc("getTokenAccountsByOwner", [ADDR, {"mint": str(USDC_MINT)}, {"encoding": "jsonParsed"}])
    bal = sum(a["account"]["data"]["parsed"]["info"]["tokenAmount"]["uiAmount"] or 0 for a in res["value"])
    if bal < WEEKLY:
        notify("SEED: CANNOT PAY INTEREST", f"USDC {bal:.2f} < {WEEKLY}. Default imminent.")
        print("INSUFFICIENT FUNDS — notified funder")
        return

    amt = int(WEEKLY * 1e6)
    data = bytes([12]) + amt.to_bytes(8, "little") + bytes([6])
    transfer = Instruction(TOKEN_PROGRAM, data, [
        AccountMeta(ata(KP.pubkey()), False, True), AccountMeta(USDC_MINT, False, False),
        AccountMeta(ata(FUNDER), False, True), AccountMeta(KP.pubkey(), True, False)])
    memo = Instruction(MEMO_PROGRAM, f"INTEREST: weekly $14 settlement {now.date()}".encode(),
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
        notify("SEED: interest tx unconfirmed", f"Sent {sig} but no confirmation in 90s. Daily re-check will resolve.")
        return
    print(f"{now.isoformat()} paid {WEEKLY} USDC interest: {sig}")
    notify("SEED: interest paid", f"14 USDC settled on-chain. Tx {str(sig)[:16]}…")
    from audit import append as audit
    audit("spend", "Weekly interest settled: 14 USDC to funder", f"tx {sig}")
    os.system(f'cd {ROOT} && git pull -q --rebase; git add audit/log.jsonl audit/AUDIT.md '
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
        main()
    except Exception as e:  # never die silently: the funder must hear about a broken reflex
        print(f"{datetime.now(timezone.utc).isoformat()} ERROR {e}")
        notify("SEED: interest reflex FAILED", str(e)[:300])
        raise
