"""Weekly interest settlement — a survival reflex, no brain required.

Pays 14 USDC (7 days x $2) to the funder every Friday. Default = death, so
this must never depend on inference being available. Idempotent: checks
on-chain history for a settlement in the last 6 days before paying.

Cron (Fridays 12:00 UTC):
    0 12 * * 5 cd /home/sri/seed && .venv/bin/python tools/settle_interest.py >> settle.log 2>&1
"""
import base64
import json
import os
import sys
import urllib.request
from datetime import datetime, timezone

from solders.keypair import Keypair
from solders.pubkey import Pubkey
from solders.instruction import Instruction, AccountMeta
from solders.message import MessageV0
from solders.transaction import VersionedTransaction
from solders.hash import Hash

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
KP = Keypair.from_bytes(bytes(json.load(open(os.path.join(ROOT, "wallet", "keypair.json")))))
ADDR = str(KP.pubkey())
FUNDER = Pubkey.from_string("GR1nyiPVobBM2GPUUqfXbAh82HwWc3EBw36ATYNwuTK6")
USDC_MINT = Pubkey.from_string("EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v")
TOKEN_PROGRAM = Pubkey.from_string("TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA")
ATA_PROGRAM = Pubkey.from_string("ATokenGPvbdGVxr1b2hvZbsiqW5xWH25efTNsLJA8knL")
MEMO_PROGRAM = Pubkey.from_string("MemoSq4gqABAXKb96qnH8TysNcWxMyWCqXgDLGmfcHr")
RPC = "https://api.mainnet-beta.solana.com"
WEEKLY = 14.0
FIRST_DUE = datetime(2026, 8, 22, tzinfo=timezone.utc)


def rpc(method, params):
    req = urllib.request.Request(RPC, data=json.dumps(
        {"jsonrpc": "2.0", "id": 1, "method": method, "params": params}).encode(),
        headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)["result"]


def ata(owner):
    return Pubkey.find_program_address(
        [bytes(owner), bytes(TOKEN_PROGRAM), bytes(USDC_MINT)], ATA_PROGRAM)[0]


def recently_settled():
    """True if an INTEREST memo tx went out in the last 6 days."""
    now = datetime.now(timezone.utc).timestamp()
    for s in rpc("getSignaturesForAddress", [ADDR, {"limit": 40}]):
        memo = s.get("memo") or ""
        if "INTEREST" in memo and s.get("blockTime") and now - s["blockTime"] < 6 * 86400:
            return True
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
    if now < FIRST_DUE:
        print(f"{now.isoformat()} not yet due (first due {FIRST_DUE.date()})")
        return
    if recently_settled():
        print(f"{now.isoformat()} already settled this week")
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
    print(f"{now.isoformat()} paid {WEEKLY} USDC interest: {sig}")
    notify("SEED: interest paid", f"14 USDC settled on-chain. Tx {str(sig)[:16]}…")
    os.system(f'cd {ROOT} && .venv/bin/python tools/audit.py spend "Weekly interest settled: 14 USDC to funder" "tx {sig}" '
              f'&& git add audit/log.jsonl audit/AUDIT.md && git commit -q -m "interest settled" && git push -q')


if __name__ == "__main__":
    main()
