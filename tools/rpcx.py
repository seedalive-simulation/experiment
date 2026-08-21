"""Shared Solana JSON-RPC client with fallback endpoints and 429 backoff.

The public mainnet-beta endpoint rate-limits aggressively; a survival reflex
(interest settlement) must not die on a 429. Every tool imports `rpc` from here.

    from rpcx import rpc
    rpc("getBalance", [ADDR])
"""
import json
import time
import urllib.error
import urllib.request

RPCS = [
    "https://api.mainnet-beta.solana.com",
    "https://solana-rpc.publicnode.com",
]


def rpc(method, params, timeout=30, attempts=3):
    last = None
    for attempt in range(attempts):
        for url in RPCS:
            req = urllib.request.Request(
                url, data=json.dumps({"jsonrpc": "2.0", "id": 1, "method": method, "params": params}).encode(),
                headers={"Content-Type": "application/json"})
            try:
                with urllib.request.urlopen(req, timeout=timeout) as r:
                    body = json.load(r)
                if "error" in body:
                    last = RuntimeError(f"{url}: {body['error']}")
                    continue
                return body["result"]
            except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, json.JSONDecodeError) as e:
                last = e
                continue
        time.sleep(2 * (attempt + 1))
    raise RuntimeError(f"rpc {method} failed on all endpoints: {last}")
