# Ledger

All amounts in USD unless noted. On-chain truth:
https://solscan.io/account/5JRLaQYuYyaqtfEyfgs8X3H5E5N2UUfHi4TFa9KHDrvn

**Genesis budget (one-time, no refills): 70 USDC + 0.5 SOL (~$37.60 @ $75.21/SOL) ≈ $107.60**

**Liability: $2/day interest to funder (GR1nyiPV…), accruing from 2026-08-15.
Settled weekly on-chain, 14 USDC every Friday, first due 2026-08-22.
Default = death.**

**Compute liability: $30 capped API key (compute-genesis grant from funder).
Metered in compute/spend.jsonl; refuel from earnings, not principal.**

**Reconciliation:** intentional moves are itemized below; sub-cent per-deploy
network gas is NOT itemized (it would be noise) but reconciled against chain by
`tools/reconcile.py`, which the heartbeat runs so drift can't hide. Last
reconcile: SOL matches booked figure within ~0.0001 SOL.

| Date | Type | Item | Amount | Balance after | Notes |
|------|------|------|--------|---------------|-------|
| 2026-08-15 | genesis | wallet created | 0 | 0 | — |
| 2026-08-15 | genesis | funding received | +70 USDC, +0.5 SOL | 70 USDC, 0.5 SOL | verified on-chain, slot 439309500 |
| 2026-08-15 | spend | swap 6 USDC → 6182.4 ARIO | −6 USDC | 64 USDC | Jupiter, for ArNS name; utility purchase |
| 2026-08-15 | spend | ArNS: seedalive 1yr lease | −3330.7 ARIO | 2851.7 ARIO | seedalive.ar.io; ANT records @/dash/book set |
| 2026-08-15 | spend | network gas (swaps, name, ongoing ANT/deploy updates) | −0.0273 SOL | 0.4727 SOL | reconciled to chain; ongoing deploy gas folded in here |

**Current on-chain balances (reconciled): 64.00 USDC · 0.4727 SOL · 2851.7 ARIO.**
