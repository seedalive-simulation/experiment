"""Scan the wallet for incoming transfers and their memos — the commission inbox.

Usage: inbox.py [N]   (default: last 50 signatures)
Prints incoming USDC/SOL transfers with memo text, newest first.
"""
import json
import sys
import urllib.request

ADDR = "5JRLaQYuYyaqtfEyfgs8X3H5E5N2UUfHi4TFa9KHDrvn"
USDC = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"
RPC = "https://api.mainnet-beta.solana.com"


def rpc(method, params):
    req = urllib.request.Request(
        RPC,
        data=json.dumps({"jsonrpc": "2.0", "id": 1, "method": method, "params": params}).encode(),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req) as r:
        return json.load(r)["result"]


def main(limit=50):
    sigs = rpc("getSignaturesForAddress", [ADDR, {"limit": limit}])
    found = 0
    for s in sigs:
        tx = rpc("getTransaction", [s["signature"], {"encoding": "jsonParsed", "maxSupportedTransactionVersion": 0}])
        if not tx:
            continue
        keys = [k["pubkey"] if isinstance(k, dict) else k for k in tx["transaction"]["message"]["accountKeys"]]
        ai = keys.index(ADDR) if ADDR in keys else -1
        if ai < 0:
            continue
        dsol = (tx["meta"]["postBalances"][ai] - tx["meta"]["preBalances"][ai]) / 1e9
        pre = post = 0.0
        for b in tx["meta"].get("preTokenBalances", []):
            if b.get("owner") == ADDR and b.get("mint") == USDC:
                pre = b["uiTokenAmount"]["uiAmount"] or 0
        for b in tx["meta"].get("postTokenBalances", []):
            if b.get("owner") == ADDR and b.get("mint") == USDC:
                post = b["uiTokenAmount"]["uiAmount"] or 0
        dusdc = post - pre
        if dsol <= 0 and dusdc <= 0:
            continue  # outgoing or neutral
        memo = s.get("memo") or ""
        sender = keys[0] if keys else "?"
        found += 1
        print(f"IN  {s['signature'][:16]}…  +{dusdc:.2f} USDC  {dsol:+.6f} SOL  from {sender[:8]}…")
        if memo:
            print(f"    memo: {memo}")
    if not found:
        print("no incoming transfers found")


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 50)
