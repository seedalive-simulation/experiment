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
import urllib.request

ADDR = "5JRLaQYuYyaqtfEyfgs8X3H5E5N2UUfHi4TFa9KHDrvn"
USDC = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"
ARIO = "DcNnMuFxwhgV4WY1HVSaSEgr92bv2b1vUvEKiNxWqHdF"
GENESIS_SOL = 0.5
GENESIS_USDC = 70.0


import os as _os, sys as _sys
_sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
from rpcx import rpc  # noqa: E402

def token_balance(mint):
    res = rpc("getTokenAccountsByOwner", [ADDR, {"mint": mint}, {"encoding": "jsonParsed"}])
    return sum(a["account"]["data"]["parsed"]["info"]["tokenAmount"]["uiAmount"] or 0 for a in res["value"])


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
    print("Booked in LEDGER.md (intentional moves):")
    print("  USDC: -6.00 (ARIO swap)                    -> matches" if abs(usdc_spent - 6.0) < 0.01
          else f"  USDC: expected -6.00, actual -{usdc_spent:.2f}  -> DRIFT ${abs(usdc_spent-6.0):.2f}")
    print(f"  SOL:  ledger lumped ~0.0272; actual {sol_spent:.6f}")
    drift = sol_spent - 0.0272
    if abs(drift) > 0.0001:
        print(f"  -> SOL fee drift since last booking: {drift:+.6f} SOL "
              f"(~${drift*240:.4f} at ARIO... use live SOL price). Book as 'accumulated network fees'.")
    else:
        print("  -> SOL matches booked figure.")


if __name__ == "__main__":
    main()
