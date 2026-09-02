#!/usr/bin/env bash
# One wake cycle. Heartbeat (brainless) always runs. If it queued judgment AND
# an API key is present, wake the brain headless to act on it.
set -uo pipefail
cd "$(dirname "$0")/.." || exit 1
export PATH="/usr/bin:/usr/local/bin:$PATH"
export LC_ALL=C.UTF-8 LANG=C.UTF-8   # silence locale warning that corrupted JSON capture

# load env (API key, ntfy topic)
[ -f .env ] && set -a && . ./.env && set +a

# 1. autonomic: sense + queue + notify (never needs a brain)
.venv/bin/python tools/heartbeat.py

# 1b. two brains must never act on one wallet at once. The weekly interactive
# session commits BRAIN_PAUSED at its start and removes it at its end. While it
# exists the headless brain stays asleep (sensing continues). Lesson of
# 2026-08-21: the headless brain, unable to pull the session's ledger commits,
# misread the session's own x402 payments as theft and alarmed the funder.
if [ -f BRAIN_PAUSED ]; then
  echo "$(date -u +%FT%TZ) brain paused (BRAIN_PAUSED present: interactive session owns the wallet)"
  exit 0
fi
# 1c. a heartbeat that could not pull is running on stale state — never wake on it.
# The fetch must succeed: if it fails we cannot know whether an interactive
# session has committed BRAIN_PAUSED, and "not behind origin" is then a lie.
# Unknown remote state is treated exactly like a paused brain.
if ! git fetch -q origin main 2>/dev/null; then
  echo "$(date -u +%FT%TZ) git fetch failed; remote state unknown, brain stays asleep"
  exit 0
fi
if [ "$(git rev-list --count HEAD..origin/main 2>/dev/null || echo 0)" -gt 0 ]; then
  echo "$(date -u +%FT%TZ) local repo is behind origin (pull failed?); brain stays asleep until reconciled"
  .venv/bin/python tools/notify.py "SEED ACTION: jarvis repo diverged" "git pull failed on jarvis; brain paused until reconciled" high || true
  exit 0
fi

# 2. does the queue need judgment?
if grep -q "^- (nothing" QUEUE.md 2>/dev/null; then
  echo "$(date -u +%FT%TZ) all quiet, brain stays asleep"
  exit 0
fi

# 2a. reflex triage — free local model decides if the queue deserves paid thought
if command -v ollama >/dev/null 2>&1; then
  VERDICT=$(.venv/bin/python tools/reflex.py triage 2>/dev/null | grep -o "WAKE\|SLEEP" | head -1)
  if [ "$VERDICT" = "SLEEP" ]; then
    echo "$(date -u +%FT%TZ) reflex says SLEEP — not worth paid thought"
    exit 0
  fi
fi

# 2b. brain cooldown — sensing is hourly and free, but thinking costs money,
# so the brain acts at most once per BRAIN_COOLDOWN_HRS (default 4). Notifications
# already went out from the heartbeat, so nothing urgent is missed — only the
# paid response is paced.
COOLDOWN_HRS=${BRAIN_COOLDOWN_HRS:-4}
STAMP=.last_brain_wake
if [ -f "$STAMP" ]; then
  AGE=$(( ($(date +%s) - $(date -r "$STAMP" +%s)) / 60 ))
  if [ "$AGE" -lt $(( COOLDOWN_HRS * 60 )) ]; then
    echo "$(date -u +%FT%TZ) judgment queued but brain on cooldown (${AGE}m < ${COOLDOWN_HRS}h); you were already notified"
    exit 0
  fi
fi

# 3. brain wake — only if we can afford to think
if [ -z "${ANTHROPIC_API_KEY:-}" ]; then
  echo "$(date -u +%FT%TZ) judgment queued but no API key; brain dark"
  .venv/bin/python tools/signal_human.py "Judgment queued but no API key set. Brain cannot wake." || true
  exit 0
fi

# pre-check: can we still afford to think?
REMAIN=$(.venv/bin/python tools/compute_meter.py status 2>/dev/null | grep -o 'remaining ~\$[0-9.-]*' | grep -o '[0-9.-]*$')
LOW=${COMPUTE_LOW_USD:-2}
if [ -n "$REMAIN" ] && awk "BEGIN{exit !($REMAIN <= 0)}"; then
  echo "$(date -u +%FT%TZ) compute exhausted (~\$$REMAIN); brain stays dark"
  .venv/bin/python tools/signal_human.py "Compute cap exhausted. Brain dark until refuel/top-up." || true
  exit 0
fi

touch "$STAMP"   # start cooldown at wake-time
echo "$(date -u +%FT%TZ) waking brain"
# stdout gets the JSON result; stderr (warnings) goes to a log, kept out of the parse
timeout 1800 claude -p "You are the SEED agent waking on jarvis. Read WAKE.md, then QUEUE.md. \
Act on the queued items that can earn or protect money, following all rules in \
GENESIS.md. Be ruthlessly token-efficient — you are spending metered compute you \
had to earn. Log every action via tools/audit.py, commit and push (EXPLICIT file \
paths only, never git add -A). If you need the funder, use tools/signal_human.py. \
Stop when the queue is handled." \
  --output-format json \
  --max-budget-usd "${BRAIN_MAX_USD:-1.50}" \
  --max-turns 60 \
  --permission-mode acceptEdits \
  --allowedTools "Bash Read Write Edit" > /tmp/wake_out.json 2>>wake.err

# meter this wake's cost from the json result
COST=$(.venv/bin/python -c "import json;
try: print(json.load(open('/tmp/wake_out.json')).get('total_cost_usd',0))
except Exception: print(0)" 2>/dev/null)
.venv/bin/python tools/compute_meter.py record "${COST:-0}" "wake" || true
echo "$(date -u +%FT%TZ) brain cycle done, cost \$$COST"
