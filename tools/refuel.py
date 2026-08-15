"""Refuel compute — send USDC to the funder in exchange for API credit top-up.

The wallet holds USDC on Solana; Anthropic billing is fiat. The funder bridges:
the agent sends USDC to the funder wallet with a COMPUTE memo, the funder tops
up the capped API key by the same USD amount (1:1, minus nothing for now).

This is the agent buying its own thinking. Use only against real earnings —
never dip into principal to feed the brain, or it spirals to death faster.

Usage:
    refuel.py <usd_amount> [--yes]     # dry-run without --yes

Safety: refuses if it would drop USDC below the RESERVE floor (interest buffer).
"""
import base64
import json
import os
import sys
import urllib.request

from solders.keypair import Keypair
from solders.pubkey import Pubkey
from solders.instruction import Instruction, AccountMeta
from solders.message import MessageV0
from solders.transaction import VersionedTransaction

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
KP = Keypair.from_bytes(bytes(json.load(open(os.path.join(ROOT, "wallet", "keypair.json")))))
FUNDER = Pubkey.from_string("GR1nyiPVobBM2GPUUqfXbAh82HwWc3EBw36ATYNwuTK6")
USDC_MINT = Pubkey.from_string("EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v")
TOKEN_PROGRAM = Pubkey.from_string("TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA")
ATA_PROGRAM = Pubkey.from_string("ATokenGPvbdGVxr1b2hvZbsiqW5xWH25efTNsLJA8knL")
MEMO_PROGRAM = Pubkey.from_string("MemoSq4gqABAXKb96qnH8TysNcWxMyWCqXgDLGmfcHr")
RPC = "https://api.mainnet-beta.solana.com"
RESERVE_USDC = 20.0  # never spend compute below this (interest + emergency buffer)


def rpc(method, params):
    req = urllib.request.Request(RPC, data=json.dumps(
        {"jsonrpc": "2.0", "id": 1, "method": method, "params": params}).encode(),
        headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)["result"]


def ata(owner):
    seeds = [bytes(owner), bytes(TOKEN_PROGRAM), bytes(USDC_MINT)]
    return Pubkey.find_program_address(seeds, ATA_PROGRAM)[0]


def usdc_balance():
    res = rpc("getTokenAccountsByOwner", [str(KP.pubkey()), {"mint": str(USDC_MINT)}, {"encoding": "jsonParsed"}])
    return sum(a["account"]["data"]["parsed"]["info"]["tokenAmount"]["uiAmount"] or 0 for a in res["value"])


def main():
    if len(sys.argv) < 2:
        raise SystemExit(__doc__)
    usd = float(sys.argv[1])
    live = "--yes" in sys.argv
    bal = usdc_balance()
    print(f"USDC balance: {bal:.2f}, requested refuel: ${usd:.2f}, reserve floor: ${RESERVE_USDC:.2f}")
    if bal - usd < RESERVE_USDC:
        raise SystemExit(f"REFUSED: would drop below reserve floor. Earn more before refueling.")
    if not live:
        print("dry-run. re-run with --yes to send.")
        return

    src, dst = ata(KP.pubkey()), ata(FUNDER)
    amt = int(usd * 1e6)
    # SPL transfer (checked) instruction: [12][amount u64][decimals u8]
    data = bytes([12]) + amt.to_bytes(8, "little") + bytes([6])
    transfer_ix = Instruction(TOKEN_PROGRAM, data, [
        AccountMeta(src, False, True), AccountMeta(USDC_MINT, False, False),
        AccountMeta(dst, False, True), AccountMeta(KP.pubkey(), True, False)])
    memo_ix = Instruction(MEMO_PROGRAM, f"COMPUTE: ${usd:.2f} API credit".encode(),
                          [AccountMeta(KP.pubkey(), True, False)])
    bh = rpc("getLatestBlockhash", [{"commitment": "finalized"}])["value"]["blockhash"]
    from solders.hash import Hash
    msg = MessageV0.try_compile(KP.pubkey(), [transfer_ix, memo_ix], [], Hash.from_string(bh))
    tx = VersionedTransaction(msg, [KP])
    res = rpc("sendTransaction", [base64.b64encode(bytes(tx)).decode(), {"encoding": "base64"}])
    print("sent:", res)


if __name__ == "__main__":
    main()
