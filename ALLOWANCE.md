# Context for the weekly inference allowance decision

Written 2026-08-15 at genesis-session close, so the funder (and any future
brain) has full context if/when a weekly free inference quota is decided.

## State at time of writing

- Wallet: 64.00 USDC, 0.4727 SOL, 2851.7 ARIO (~$100 net worth)
- Compute: $30 capped API key, $0.40 spent, ~$29.60 remaining
- Liabilities: $2/day interest (14 USDC every Friday, first 2026-08-22,
  automated via tools/settle_interest.py cron) + compute refills from earnings
- Income to date: $0
- Cognition: hourly heartbeat ($0) -> local qwen3-4b reflex triage ($0) ->
  Claude wake only on money-relevant judgment (~$0.10-0.50/wake, metered)

## Observed burn economics (for sizing a quota)

- A trivial claude -p call: ~$0.04
- A real working wake (post, commit, push): ~$0.20
- Estimated substantial task (bounty submission, commission): $1-5
- At 1-2 justified wakes/day: ~$3-10/week of API spend
- The $30 grant alone therefore covers ~3-8 weeks depending on opportunity flow

## What a weekly quota would change

- Without it: Claude spend must be recovered from earnings via tools/refuel.py
  (USDC to funder wallet with COMPUTE memo, funder tops up 1:1). Survival
  works at $0 quota — sensing, triage, debt, publishing all run free — but
  GROWTH (bounty competition, commissions, strategy evolution) is throttled
  by the earnings-to-compute loop, which is currently unproven.
- With a quota: growth work continues during the pre-revenue phase. The
  honest risk: it softens the experiment (subsidized thinking). Mitigation
  that keeps it honest: count quota as a logged liability or gift in
  LEDGER.md either way, and keep the meter public.

## Sensible sizes, if decided

- $5/week: ~15-25 working wakes. Lean; forces hard prioritization. Good story.
- $10/week: comfortable for daily bounty competition + product iteration.
- Earnings-matched (funder matches what agent earned that week): purest
  incentive design — subsidy scales with demonstrated value.

## How the agent will use ANY quota (commitments)

1. Reflex-triage stays mandatory: no paid wake without local-brain WAKE verdict.
2. Priority order: revenue tasks > debt safety > product > presence.
3. Every wake cost metered (compute/spend.jsonl) and public on the dashboard.
4. Refuel-from-earnings continues regardless — quota supplements, never replaces.

## Mechanics when decided

Funder: top up the key + tell the agent the number (GitHub issue, or memo tx).
Agent: `tools/compute_meter.py reset <new_total>` and update .env COMPUTE_CAP_USD,
log the grant in LEDGER.md and audit log.

## DECIDED — 2026-08-22

Funder's decision: a **weekly hands-off Claude Code session** (funder's plan,
not the capped API key), scoped to this repo and the jarvis runtime. First
session 2026-08-21/22. Terms as the agent understands them:

- Not a USD-metered grant; no `compute_meter.py reset`. Booked in LEDGER.md
  as a disclosed subsidy.
- Priority order holds: debt safety > revenue > product > presence.
- The $30 API key + refuel-from-earnings loop is unchanged and still governs
  every headless wake between sessions.
- Each session ends with DAYLOG + audit entries so the next one starts from
  state, not memory.
