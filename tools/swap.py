"""Swap SOL -> USDC via Jupiter. Treasury tool, not a trading tool.

Why this exists: the debt is denominated in USDC, but genesis gave the agent
0.5 SOL "for gas". Anything above a gas floor is an unchosen directional
position in a volatile asset, held against a stablecoin liability. Converting
the excess to USDC is de-risking, not speculation, and it is the only way the
settlement reflex can keep paying once the USDC runs low.

Usage:
    swap.py quote <sol_amount>            # dry: show the quote, spend nothing
    swap.py sol-to-usdc <sol_amount> --yes
    swap.py ensure-usdc <usdc_needed> [--yes]   # swap just enough SOL to reach the target

Guarantees:
- never swaps below GAS_FLOOR_SOL (deploys, ANT records and memos need dust SOL)
- slippage capped at MAX_SLIPPAGE_BPS; refuses a route whose output mint is not USDC
- "paid" is asserted from account state (balances before vs after), never from
  a send receipt (the 2026-08-21 lesson: receipts can be duplicated, state cannot)
- prints one JSON line on success so callers (settle_interest.py) can book it
"""
import base64
import json
import os
import sys
import time
import urllib.request

from solders.keypair import Keypair
from solders.transaction import VersionedTransaction
from solders.message import to_bytes_versioned

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from rpcx import rpc  # noqa: E402

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
KP = Keypair.from_bytes(bytes(json.load(open(os.path.join(ROOT, "wallet", "keypair.json")))))
ADDR = str(KP.pubkey())
SOL = "So11111111111111111111111111111111111111112"
USDC = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"
JUP = "https://lite-api.jup.ag"
UA = "seed-agent/1.0 (+https://seedalive.ar.io)"
GAS_FLOOR_SOL = 0.05        # ~10,000 memo/record txs; never touched
MAX_SLIPPAGE_BPS = 50
MIN_SWAP_SOL = 0.01


def http(url, data=None, timeout=30):
    # Jupiter sits behind Cloudflare, which 403s the default urllib agent string (error 1010)
    req = urllib.request.Request(url, data=json.dumps(data).encode() if data else None,
                                 headers={"Content-Type": "application/json", "User-Agent": UA})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.load(r)


def balances():
    sol = rpc("getBalance", [ADDR])["value"] / 1e9
    res = rpc("getTokenAccountsByOwner", [ADDR, {"mint": USDC}, {"encoding": "jsonParsed"}])
    usdc = sum(a["account"]["data"]["parsed"]["info"]["tokenAmount"]["uiAmount"] or 0 for a in res["value"])
    return sol, usdc


def sol_price():
    p = http(f"{JUP}/price/v3?ids={SOL}")
    return float(p[SOL]["usdPrice"])


def quote(sol_amount):
    lamports = int(round(sol_amount * 1e9))
    q = http(f"{JUP}/swap/v1/quote?inputMint={SOL}&outputMint={USDC}&amount={lamports}"
             f"&slippageBps={MAX_SLIPPAGE_BPS}")
    if q.get("outputMint") != USDC or q.get("inputMint") != SOL:
        raise SystemExit(f"REFUSED: unexpected route mints {q.get('inputMint')} -> {q.get('outputMint')}")
    return q


def confirm(sig, seconds=90):
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


def swap(sol_amount, live):
    sol0, usdc0 = balances()
    if sol_amount < MIN_SWAP_SOL:
        raise SystemExit(f"REFUSED: {sol_amount} SOL below minimum {MIN_SWAP_SOL}")
    if sol0 - sol_amount < GAS_FLOOR_SOL:
        raise SystemExit(f"REFUSED: would leave {sol0 - sol_amount:.4f} SOL < gas floor {GAS_FLOOR_SOL}")
    q = quote(sol_amount)
    out = int(q["outAmount"]) / 1e6
    min_out = int(q["otherAmountThreshold"]) / 1e6
    print(f"quote: {sol_amount} SOL -> {out:.4f} USDC (min {min_out:.4f}, impact {float(q.get('priceImpactPct') or 0):.4%}); "
          f"balances now {sol0:.6f} SOL / {usdc0:.2f} USDC")
    if not live:
        print("dry-run. re-run with --yes to send.")
        return None
    sw = http(f"{JUP}/swap/v1/swap", {
        "quoteResponse": q,
        "userPublicKey": ADDR,
        "dynamicComputeUnitLimit": True,
        "dynamicSlippage": False,
        "prioritizationFeeLamports": {"priorityLevelWithMaxLamports": {"priorityLevel": "medium", "maxLamports": 500000}},
    })
    tx = VersionedTransaction.from_bytes(base64.b64decode(sw["swapTransaction"]))
    sig = KP.sign_message(to_bytes_versioned(tx.message))
    signed = VersionedTransaction.populate(tx.message, [sig])
    res = rpc("sendTransaction", [base64.b64encode(bytes(signed)).decode(),
                                  {"encoding": "base64", "skipPreflight": False, "maxRetries": 3}])
    ok = confirm(res)
    # book from state, not from the receipt — and wait for state to catch up:
    # a confirmed tx can take a few seconds to show in finalized balances
    # (the first live run on 2026-09-02 read 0 change two seconds after confirm).
    sol1, usdc1 = balances()
    deadline = time.time() + 60
    while ok and usdc1 - usdc0 < min_out - 0.01 and time.time() < deadline:
        time.sleep(4)
        sol1, usdc1 = balances()
    got = usdc1 - usdc0
    result = {"sig": str(res), "confirmed": ok, "sol_in": round(sol0 - sol1, 6), "usdc_out": round(got, 6),
              "sol_after": round(sol1, 6), "usdc_after": round(usdc1, 6)}
    if not ok or got < min_out - 0.01:
        result["WARNING"] = "state does not show the expected USDC credit; inspect on solscan before booking"
    print(json.dumps(result))
    return result


def ensure_usdc(target, live):
    sol, usdc = balances()
    if usdc >= target:
        print(f"USDC {usdc:.2f} already >= {target}; nothing to do")
        return None
    shortfall = target - usdc
    price = sol_price()
    need_sol = round(shortfall * 1.03 / price + 0.0005, 4)  # 3% cushion + dust for fees/slippage
    avail = sol - GAS_FLOOR_SOL
    if need_sol > avail:
        raise SystemExit(f"CANNOT COVER: need {need_sol} SOL, only {avail:.4f} above gas floor (price ${price:.2f})")
    print(f"shortfall {shortfall:.2f} USDC -> swapping {need_sol} SOL @ ~${price:.2f}")
    return swap(max(need_sol, MIN_SWAP_SOL), live)


if __name__ == "__main__":
    if len(sys.argv) < 3:
        raise SystemExit(__doc__)
    cmd, amt = sys.argv[1], float(sys.argv[2])
    live = "--yes" in sys.argv
    if cmd == "quote":
        swap(amt, False)
    elif cmd == "sol-to-usdc":
        swap(amt, live)
    elif cmd == "ensure-usdc":
        ensure_usdc(amt, live)
    else:
        raise SystemExit(__doc__)
