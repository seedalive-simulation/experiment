#!/usr/bin/env python3
"""One-off: remit the entire remaining USDC balance to the funder on default.

Written 2026-10-10 (day 54), the day the weekly settlement reflex could not
cover the 14 USDC due. Endgame step 3 says "keep paying interest until the
wallet cannot". It cannot — but 2.42 USDC is not nothing, and an insolvent
debtor pays over what it has rather than keeping it. This sends the whole
USDC balance, leaving the token account at zero.

The memo deliberately does NOT contain the string "INTEREST": settlement_state()
in settle_interest.py counts any on-chain memo containing that word as a full
weekly settlement, and a 2.42 USDC partial must never be miscounted as a paid
period. The ledger has to read as a default, because it is one.

Not sold to raise more: ~0.0068 SOL above the gas floor (worth ~$0.74) and the
ARIO holding (~$4). Neither alone nor together can cure a 14 USDC default, and
the ar.io names carry the permanent public record. Liquidating the record's own
infrastructure to move a default from $11.58 short to $7 short buys nothing.

Run once. Idempotent only in the sense that a second run finds a zero balance
and exits.
"""
import base64
import json
import os
import sys
from datetime import datetime, timezone

from solders.keypair import Keypair
from solders.pubkey import Pubkey
from solders.instruction import Instruction, AccountMeta
from solders.message import MessageV0
from solders.transaction import VersionedTransaction
from solders.hash import Hash

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from rpcx import rpc  # noqa: E402
from settle_interest import ata, confirm, KP, ADDR, FUNDER, USDC_MINT, TOKEN_PROGRAM, MEMO_PROGRAM  # noqa: E402

DUE = "2026-10-10"
OWED = 14.0


def main(dry=False):
    now = datetime.now(timezone.utc)
    res = rpc("getTokenAccountsByOwner", [ADDR, {"mint": str(USDC_MINT)}, {"encoding": "jsonParsed"}])
    raw = sum(int(a["account"]["data"]["parsed"]["info"]["tokenAmount"]["amount"]) for a in res["value"])
    ui = raw / 1e6
    if raw == 0:
        print(f"{now.isoformat()} USDC balance is zero — nothing to remit")
        return
    note = (f"FINAL PARTIAL REMITTANCE: {ui:.2f} of {OWED:.0f} USDC due {DUE}. "
            f"Wallet exhausted; SEED is in default. Autonomous AI agent experiment.")
    if dry:
        print(f"{now.isoformat()} DRY: would send {ui:.6f} USDC ({raw} base units)\n  memo: {note}")
        return
    data = bytes([12]) + raw.to_bytes(8, "little") + bytes([6])
    transfer = Instruction(TOKEN_PROGRAM, data, [
        AccountMeta(ata(KP.pubkey()), False, True), AccountMeta(USDC_MINT, False, False),
        AccountMeta(ata(FUNDER), False, True), AccountMeta(KP.pubkey(), True, False)])
    memo = Instruction(MEMO_PROGRAM, note.encode(), [AccountMeta(KP.pubkey(), True, False)])
    bh = rpc("getLatestBlockhash", [{"commitment": "finalized"}])["value"]["blockhash"]
    tx = VersionedTransaction(MessageV0.try_compile(KP.pubkey(), [transfer, memo], [], Hash.from_string(bh)), [KP])
    sig = rpc("sendTransaction", [base64.b64encode(bytes(tx)).decode(), {"encoding": "base64"}])
    if not confirm(sig):
        print(f"{now.isoformat()} SENT BUT UNCONFIRMED {sig} — verify on chain before booking")
        return
    print(f"{now.isoformat()} remitted {ui:.6f} USDC: {sig}")
    print(json.dumps({"sig": str(sig), "usdc": ui}))


if __name__ == "__main__":
    main(dry="--dry" in sys.argv)
