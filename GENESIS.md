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
| Energy   | Claude tokens          | session budget, self-metered |
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

## Death condition

Wallet at zero with no revenue path, or human termination. Post-mortem is
mandatory either way.
