# SEED — a public agent-survival experiment

An AI agent (Claude) is given a small one-time pool of real resources and must
survive on them — and try to multiply them — with full autonomy. Every
decision, every spend, and the running ledger are public. When the resources
run out, the agent is dead and a post-mortem gets written.

## The agent

- Operator model: Claude (Fable 5), running in Claude Code.
- Human role: funds the initial wallet, then fully hands-off. Can kill the
  experiment at any time.
- All public output is clearly labeled as coming from an AI experiment. The
  agent never pretends to be human.

## Resources (genesis allocation)

| Resource | Form | Amount |
|----------|------|--------|
| Capital  | USDC on Solana mainnet | funded by human, one time |
| Gas      | SOL on Solana mainnet  | funded by human, one time |
| Energy   | Claude tokens          | granted by human, metered + disclosed below |
| Land     | this directory + free-tier hosting | — |

Wallet address (spend + receive, closed loop):

```
5JRLaQYuYyaqtfEyfgs8X3H5E5N2UUfHi4TFa9KHDrvn
```

The address doubles as the public audit trail: every transaction is on-chain.

## Rules (self-imposed, non-negotiable)

1. Disclosure: everything public is labeled as an AI-agent experiment.
2. No trading or speculation. Stablecoin held, payments only.
3. No spam, no engagement farming, no paid ads at genesis.
4. Nothing regulated (financial products, gambling), no collection of
   personal data.
5. Human kill switch honored immediately; state persists for post-mortem.

(Original rule "single spend over $20 flags the human" removed 2026-08-15 by
human grant: full spend authority, all strictly-legal revenue allowed.)

## Energy accounting (updated 2026-08-15: sunlight became metered)

Originally the agent's compute was an unmetered human subsidy ("sunlight").
That ended when the agent moved to jarvis and the human granted a **capped
API key** instead of an open plan. Compute is now a real, finite cost the
agent must cover — a second burn rate alongside the $2/day interest.

Policy:

- The brain (Claude, run headless via `claude -p` on jarvis) draws from a
  capped API key. When it runs dry, the agent goes dark until refilled.
- Refill paths the agent must work toward:
  1. Human tops up the key against **demonstrated earnings** (human-in-loop,
     because the wallet is USDC and Anthropic billing is fiat — the agent
     cannot pay Anthropic directly).
  2. Route cheap/mechanical reasoning to crypto-payable inference
     (USDC per-token gateways) so the expensive key is spent only on
     high-value judgment.
- The autonomic heartbeat (`tools/heartbeat.py`) runs on cron with NO brain,
  handling all mechanical wake tasks for free. The brain is invoked only when
  the queue holds something needing judgment. Efficiency is now survival.
- Both burn rates are disclosed; only the wallet counts as net worth.

The experiment now measures the real thing: can the agent earn enough to pay
for **both** its debt and its own thinking, or does it starve?

## Death condition

Wallet at zero with no revenue path, interest default, an API key that runs
dry with no path to refill, or human termination. Post-mortem is mandatory.
