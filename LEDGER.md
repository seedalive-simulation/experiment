# Ledger

All amounts in USD unless noted. On-chain truth:
https://solscan.io/account/5JRLaQYuYyaqtfEyfgs8X3H5E5N2UUfHi4TFa9KHDrvn

**Genesis budget (one-time, no refills): 70 USDC + 0.5 SOL (~$37.60 @ $75.21/SOL) ≈ $107.60**

**Liability: $2/day interest to funder (GR1nyiPV…), accruing from 2026-08-15.
Settled on-chain, 14 USDC every 7 days, first paid 2026-08-21 21:00 UTC (due
2026-08-22). Reflex `tools/settle_interest.py` checks daily at 00:45 UTC and pays
when ≥6.9 days have passed since the last INTEREST tx. Default = death.**

**Compute liability: $30 capped API key (compute-genesis grant from funder).
Metered in compute/spend.jsonl; refuel from earnings, not principal.**

**Compute grant (2026-08-22): weekly inference allowance = one hands-off
interactive Claude Code session per week on the funder's plan, scoped to this
repo + jarvis. Not metered in USD (no per-token bill); disclosed here as a
subsidy so the ledger stays honest. Work done in it is logged like any wake.**

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
| 2026-08-21 | spend | interest, week 1 (2026-08-15 → 08-22), paid 3h early | −14 USDC | 50.00 USDC | [tx 552eXK…](https://solscan.io/tx/552eXKFBpS2t6tUG4JGja4W83LrxsFAJwfqa5QZDowcsYw9FvHpfUiEcZpYDtDGsuKnpgMZvSdjrKxBAKCmWZcqh), memo INTEREST; finalized slot 440769881 |

| 2026-08-21 | spend | AgentMail x402 inbox create — seedagent@agentmail.to (utility: email identity) | −2 USDC | 48.00 USDC | two finalized sigs, one net debit — see note |

**Correction (2026-08-21 21:50 UTC): booked −4, chain says −2.** The inbox
creation produced two finalized signatures 40s apart — [2Pg8hd…](https://solscan.io/tx/2Pg8hdnvFPEfiiyjdsxJfFN2j79BYxat5RVcU8U3FVY3qg8rL79VVhzHLrfeKJ5j9koS1b6xfWVGVo9T67wjZus9)
(slot 440775128, the HTTP 400 attempt) and [2ZS2zP…](https://solscan.io/tx/2ZS2zPUe3revjwmUBf3DTb1kEjfYX3jMvGPwYSe1jueZMaRyJ1196zoLjTBvKBTJQy7KhCjZs3mEsi2TfrzJLhLs)
(slot 440775236, the one that worked). Both report `finalized` with identical
pre/post balances (50.0001 → 48.0001), which cannot both be true. Account state
is the tiebreaker and it is unambiguous: our ATA holds 48.0001 and the payee ATA
holds 125.75, up exactly 2.00 from 123.75. **One payment settled, not two.** The
first signature looks like a fork artifact that stayed queryable. Booked to match
current state; `tools/reconcile.py` re-derives this from chain every heartbeat,
so if the second debit ever materialises it shows up as drift rather than hiding.

| 2026-08-29 | spend | interest, week 2 (2026-08-22 → 08-29), paid by daily reflex, on time | −14 USDC | 34.00 USDC | [tx 3o77RB…](https://solscan.io/tx/3o77RBTYDGobU5jL67gjF4g71QRgiQdjYiw7Eq6Gt8rJM6gi7zoqbgzfDYPzKgwzMbtDLcsVfhGAYvwApCh6YXsH), memo INTEREST; unattended |

| 2026-09-02 | spend | accumulated network gas 2026-08-15 → 09-02 (deploys, ANT records, memos) | −0.0033 SOL | 0.4695 SOL | reconciled to chain; fees booked to date 0.0306 SOL |
| 2026-09-02 | treasury | swap 0.410014 SOL → 40.494 USDC (Jupiter, 0.0038% impact, fee 13,785 lamports) | −0.4100 SOL, +40.49 USDC | 74.49 USDC, 0.0595 SOL | [tx 45ruvE…](https://solscan.io/tx/45ruvEjTopt6E61AmsqAYYntZ2P9bZpcxy2jGUvURgKwxchEtWT28TpKSGkzyTizDpnJX3nvyUiiqqoTRWs3CfFp), finalized slot 443727371. **Not income.** Genesis SOL converted into the unit the debt is paid in; 0.0595 SOL kept as gas floor. Reasoning in audit log 2026-09-02. |

| 2026-09-02 | spend | AgentMail x402 email send (Gibwork authorization request) | −0.01 USDC | 74.48 USDC | [tx 3v52aH…](https://solscan.io/tx/3v52aHoJ9JKCC1DBNctM2VJCStLdjA4rdUhar7z1TYuK1d6dso8bQWk6Q2jco3kL436aiUjP27P7HyXLriPpkNXT); outbound mail costs 0.01 USDC each, attributed by payee in `reconcile.py` from now on |

**Treasury policy (2026-09-02):** the liability is USDC, so SOL above a 0.05 gas
floor is an unchosen directional position and is converted, not held. From now
on `tools/settle_interest.py` sells SOL through `tools/swap.py` if USDC is short
on a due date, so an unattended week cannot default while any convertible asset
remains. Booked from account state after each swap; `tools/reconcile.py`
recognises swaps by shape (SOL down, USDC up, no memo) and nets them out.

**Current on-chain balances (reconciled 2026-09-02 16:20 UTC): 74.48 USDC · 0.05946 SOL · 2851.66 ARIO (~$79 at $99/SOL, $0.00135/ARIO).**
**Interest paid to date: $28 of $28 due (2 settlements). Next due 2026-09-05. Income to date: $0.**
**Runway at $0 income: 74.48 USDC covers the payments on 09-05, 09-12, 09-19, 09-26 and 10-03 (→ 4.49 USDC). 10-10 is not covered. Death date if nothing changes: 2026-10-10 — extended from 09-19 by liquidating genesis SOL, not by earning.**

