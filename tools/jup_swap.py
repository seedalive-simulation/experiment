"""Swap USDC -> ARIO via Jupiter. Usage: jup_swap.py <usdc_amount>"""
import base64
import json
import os
import sys
import urllib.request

from solders.keypair import Keypair
from solders.transaction import VersionedTransaction
from solders.message import to_bytes_versioned

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
KP = Keypair.from_bytes(bytes(json.load(open(os.path.join(ROOT, "wallet", "keypair.json")))))
USDC = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"
ARIO = "DcNnMuFxwhgV4WY1HVSaSEgr92bv2b1vUvEKiNxWqHdF"
RPC = "https://api.mainnet-beta.solana.com"


def http(url, data=None):
    req = urllib.request.Request(url, data=json.dumps(data).encode() if data else None,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req) as r:
        return json.load(r)


amount = int(float(sys.argv[1]) * 1e6)
quote = http(f"https://lite-api.jup.ag/swap/v1/quote?inputMint={USDC}&outputMint={ARIO}&amount={amount}&slippageBps=100")
print("quote:", int(quote["outAmount"]) / 1e6, "ARIO for", amount / 1e6, "USDC")

swap = http("https://lite-api.jup.ag/swap/v1/swap", {
    "quoteResponse": quote,
    "userPublicKey": str(KP.pubkey()),
    "dynamicComputeUnitLimit": True,
    "prioritizationFeeLamports": {"priorityLevelWithMaxLamports": {"priorityLevel": "medium", "maxLamports": 1000000}},
})
tx = VersionedTransaction.from_bytes(base64.b64decode(swap["swapTransaction"]))
sig = KP.sign_message(to_bytes_versioned(tx.message))
signed = VersionedTransaction.populate(tx.message, [sig])

res = http(RPC, {"jsonrpc": "2.0", "id": 1, "method": "sendTransaction",
                 "params": [base64.b64encode(bytes(signed)).decode(),
                            {"encoding": "base64", "skipPreflight": False}]})
print("sent:", res.get("result", res))
