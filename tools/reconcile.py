"""Reconcile the ledger against actual on-chain balances.

The hand-kept LEDGER.md tracks intentional moves (swaps, purchases, refuels)
but per-transaction network fees (deploys, ANT record updates) accrue in the
background and drift the ledger from reality. This computes the truth from
chain and reports the gap so it can be booked as accumulated fees.

Usage:
    reconcile.py            # show on-chain balances vs last ledger figure
"""
import json
import os
import re
import urllib.request

ADDR = "5JRLaQYuYyaqtfEyfgs8X3H5E5N2UUfHi4TFa9KHDrvn"
USDC = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"
ARIO = "DcNnMuFxwhgV4WY1HVSaSEgr92bv2b1vUvEKiNxWqHdF"
GENESIS_SOL = 0.5
GENESIS_USDC = 70.0
SWAP_USDC = 6.0  # one-off: USDC -> ARIO for the ArNS name

# Spends with no memo of our own to match on — each one investigated and written
# up in LEDGER.md before being listed here. Adding a line here is an admission
# that money left for a reason we now understand; anything NOT here is drift.
BOOKED_UNMEMOED = [
    (2.0, "Turbo x402 upload, 2026-08-21 (see LEDGER incident)"),
]


import os as _os, sys as _sys
_sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
from rpcx import rpc  # noqa: E402

def token_balance(mint):
    res = rpc("getTokenAccountsByOwner", [ADDR, {"mint": mint}, {"encoding": "jsonParsed"}])
    return sum(a["account"]["data"]["parsed"]["info"]["tokenAmount"]["uiAmount"] or 0 for a in res["value"])


def explained_usdc_outflow():
    """USDC we can account for, derived from chain memos rather than hardcoded.

    The one-off ARIO swap plus every INTEREST settlement and COMPUTE refuel the
    wallet has actually signed. Hardcoding the expected figure meant the drift
    check went permanently red after the first interest payment — a detector
    that always alarms is a detector nobody reads.
    """
    sigs = rpc("getSignaturesForAddress", [ADDR, {"limit": 1000}])
    interest = refuel = 0.0
    for s in sigs:
        if s.get("err"):
            continue
        memo = s.get("memo") or ""
        m = re.search(r"\$([0-9]+(?:\.[0-9]+)?)", memo)
        if "INTEREST" in memo:
            interest += float(m.group(1)) if m else 14.0
        elif "COMPUTE" in memo and m:
            refuel += float(m.group(1))
    out = {"ARIO swap": SWAP_USDC, "interest settlements": interest, "compute refuels": refuel}
    for amt, label in BOOKED_UNMEMOED:
        out[label] = amt
    return out


def main():
    sol = rpc("getBalance", [ADDR])["value"] / 1e9
    usdc = token_balance(USDC)
    ario = token_balance(ARIO)

    sol_spent = GENESIS_SOL - sol
    usdc_spent = GENESIS_USDC - usdc
    print("=== on-chain reality ===")
    print(f"SOL:  {sol:.6f}  (spent {sol_spent:.6f} since genesis)")
    print(f"USDC: {usdc:.2f}  (spent {usdc_spent:.2f} since genesis)")
    print(f"ARIO: {ario:.2f}  (from the 6 USDC swap; for ArNS renewals)")
    print()
    print("Accounted-for USDC outflow (derived from chain memos):")
    parts = explained_usdc_outflow()
    for label, amt in parts.items():
        print(f"  -{amt:>7.2f}  {label}")
    expected = sum(parts.values())
    gap = usdc_spent - expected
    print(f"  = -{expected:.2f} expected vs -{usdc_spent:.2f} actual")
    print("  -> USDC matches." if abs(gap) < 0.01 else f"  -> USDC DRIFT ${gap:+.2f} UNEXPLAINED")
    print(f"  SOL:  ledger lumped ~0.0272; actual {sol_spent:.6f}")
    drift = sol_spent - 0.0272
    if abs(drift) > 0.0001:
        print(f"  -> SOL fee drift since last booking: {drift:+.6f} SOL "
              f"(~${drift*240:.4f} at ARIO... use live SOL price). Book as 'accumulated network fees'.")
    else:
        print("  -> SOL matches booked figure.")


if __name__ == "__main__":
    main()
