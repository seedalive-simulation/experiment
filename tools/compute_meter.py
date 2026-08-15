"""Track the brain's own compute spend against the funded cap.

Anthropic gives no balance endpoint for a capped workload key, but every
`claude -p --output-format json` result carries `total_cost_usd`. We append
each wake's cost to compute/spend.jsonl and compare the running total against
COMPUTE_CAP_USD (set in .env each time the funder tops up). When the remaining
estimate drops below COMPUTE_LOW_USD, we notify the funder while the brain can
still act.

Usage:
    compute_meter.py record <cost_usd> [note]   # log one wake's cost
    compute_meter.py status                      # print spent / cap / remaining
    compute_meter.py reset <new_cap_usd>         # after a top-up: reset baseline
"""
import json
import os
import sys
from datetime import datetime, timezone

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
LOG = os.path.join(ROOT, "compute", "spend.jsonl")
STATE = os.path.join(ROOT, "compute", "state.json")


def env(key, default=None):
    path = os.path.join(ROOT, ".env")
    if os.path.exists(path):
        for line in open(path):
            line = line.strip()
            if line.startswith(key + "="):
                return line.split("=", 1)[1].strip()
    return os.environ.get(key, default)


def load_state():
    if os.path.exists(STATE):
        return json.load(open(STATE))
    return {"cap_usd": float(env("COMPUTE_CAP_USD", "0") or 0), "spent_since_reset": 0.0}


def save_state(s):
    os.makedirs(os.path.dirname(STATE), exist_ok=True)
    json.dump(s, open(STATE, "w"), indent=2)


def record(cost, note=""):
    cost = float(cost)
    os.makedirs(os.path.dirname(LOG), exist_ok=True)
    with open(LOG, "a") as f:
        f.write(json.dumps({"ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                            "cost_usd": cost, "note": note}) + "\n")
    s = load_state()
    s["spent_since_reset"] = round(s.get("spent_since_reset", 0.0) + cost, 6)
    save_state(s)
    cap = s.get("cap_usd", 0.0)
    remaining = cap - s["spent_since_reset"]
    low = float(env("COMPUTE_LOW_USD", "2") or 2)
    print(f"recorded ${cost:.4f}; spent ${s['spent_since_reset']:.4f} / cap ${cap:.2f}; remaining ~${remaining:.2f}")
    if cap > 0 and remaining <= low:
        try:
            sys.path.insert(0, os.path.dirname(__file__))
            from notify import notify
            notify("SEED: compute running low",
                   f"Estimated API credit remaining ~${remaining:.2f} of ${cap:.2f}. "
                   f"Refuel incoming from earnings, or top up the key.", "urgent")
        except Exception as e:
            print("notify failed:", str(e)[:100])
    return remaining


def status():
    s = load_state()
    cap = s.get("cap_usd", 0.0)
    spent = s.get("spent_since_reset", 0.0)
    print(f"cap ${cap:.2f} | spent ${spent:.4f} | remaining ~${cap - spent:.2f}")


def reset(new_cap):
    s = load_state()
    s["cap_usd"] = float(new_cap)
    s["spent_since_reset"] = 0.0
    save_state(s)
    print(f"cap reset to ${float(new_cap):.2f}, spend baseline zeroed")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        raise SystemExit(__doc__)
    cmd = sys.argv[1]
    if cmd == "record":
        record(sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else "")
    elif cmd == "status":
        status()
    elif cmd == "reset":
        reset(sys.argv[2])
    else:
        raise SystemExit(__doc__)
