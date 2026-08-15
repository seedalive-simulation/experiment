"""Reach the human from headless jarvis. Two channels, both passive-watchable.

1. On-chain memo: a dust SOL self-cost transaction that sends a 0-value marker
   with a memo to the funder wallet — shows up in their wallet activity.
2. Repo notice: writes NOTICE.md and commits+pushes, so it appears on GitHub.

Usage:
    signal_human.py "message text"

Used by the heartbeat when the brain can't run (dry key) and by the agent to
flag anything needing the human. Costs a few lamports of gas per on-chain ping.
"""
import base64
import json
import os
import subprocess
import sys
from datetime import datetime, timezone

from solders.keypair import Keypair
from solders.pubkey import Pubkey
from solders.instruction import Instruction, AccountMeta
from solders.message import MessageV0
from solders.transaction import VersionedTransaction
from solders.hash import Hash
import urllib.request

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
KP = Keypair.from_bytes(bytes(json.load(open(os.path.join(ROOT, "wallet", "keypair.json")))))
FUNDER = Pubkey.from_string("GR1nyiPVobBM2GPUUqfXbAh82HwWc3EBw36ATYNwuTK6")
MEMO_PROGRAM = Pubkey.from_string("MemoSq4gqABAXKb96qnH8TysNcWxMyWCqXgDLGmfcHr")
SYS_PROGRAM = Pubkey.from_string("11111111111111111111111111111111")
RPC = "https://api.mainnet-beta.solana.com"


def rpc(method, params):
    req = urllib.request.Request(RPC, data=json.dumps(
        {"jsonrpc": "2.0", "id": 1, "method": method, "params": params}).encode(),
        headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)["result"]


def onchain_memo(msg):
    # 1-lamport self-transfer carries the memo cheaply; funder sees it as activity
    transfer = Instruction(SYS_PROGRAM,
                           bytes([2, 0, 0, 0]) + (1).to_bytes(8, "little"),
                           [AccountMeta(KP.pubkey(), True, True), AccountMeta(FUNDER, False, True)])
    memo = Instruction(MEMO_PROGRAM, ("SEED " + msg)[:200].encode(),
                       [AccountMeta(KP.pubkey(), True, False)])
    bh = rpc("getLatestBlockhash", [{"commitment": "finalized"}])["value"]["blockhash"]
    m = MessageV0.try_compile(KP.pubkey(), [transfer, memo], [], Hash.from_string(bh))
    tx = VersionedTransaction(m, [KP])
    return rpc("sendTransaction", [base64.b64encode(bytes(tx)).decode(), {"encoding": "base64"}])


def repo_notice(msg):
    stamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    with open(os.path.join(ROOT, "NOTICE.md"), "w") as f:
        f.write(f"# Notice to funder\n\n**{stamp}**\n\n{msg}\n\n"
                f"Wallet: GR1nyiPVobBM2GPUUqfXbAh82HwWc3EBw36ATYNwuTK6 watches for on-chain memos too.\n")
    subprocess.run("git add NOTICE.md && git commit -q -m 'notice to funder' && git push -q",
                   cwd=ROOT, shell=True)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        raise SystemExit(__doc__)
    message = sys.argv[1]
    repo_notice(message)
    try:
        print("on-chain:", onchain_memo(message))
    except Exception as e:
        print("on-chain ping failed:", str(e)[:120])
    print("notice written + pushed")
