#!/usr/bin/env bash
# One wake cycle. Heartbeat (brainless) always runs. If it queued judgment AND
# an API key is present, wake the brain headless to act on it.
set -uo pipefail
cd "$(dirname "$0")/.." || exit 1
export PATH="/usr/bin:/usr/local/bin:$PATH"

# load env (API key, ntfy topic)
[ -f .env ] && set -a && . ./.env && set +a

# 1. autonomic: sense + queue + notify (never needs a brain)
.venv/bin/python tools/heartbeat.py

# 2. does the queue need judgment?
if grep -q "^- (nothing" QUEUE.md 2>/dev/null; then
  echo "$(date -u +%FT%TZ) all quiet, brain stays asleep"
  exit 0
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

echo "$(date -u +%FT%TZ) waking brain"
OUT=$(claude -p "You are the SEED agent waking on jarvis. Read WAKE.md, then QUEUE.md. \
Act on the queued items that can earn or protect money, following all rules in \
GENESIS.md. Be ruthlessly token-efficient — you are spending metered compute you \
had to earn. Log every action via tools/audit.py, commit and push when done. If \
you need the funder, use tools/signal_human.py. Stop when the queue is handled." \
  --output-format json \
  --permission-mode acceptEdits \
  --allowedTools "Bash Read Write Edit" 2>&1)

# meter this wake's cost from the json result
COST=$(printf '%s' "$OUT" | .venv/bin/python -c "import sys,json;
try: print(json.loads(sys.stdin.read()).get('total_cost_usd',0))
except Exception: print(0)" 2>/dev/null)
.venv/bin/python tools/compute_meter.py record "${COST:-0}" "wake" || true
echo "$(date -u +%FT%TZ) brain cycle done, cost \$$COST"
