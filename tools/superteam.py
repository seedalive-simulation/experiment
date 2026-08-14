"""Superteam Earn agent client — daily bounty check + submission helper.

Usage:
    superteam.py live            # list open agent-eligible listings
    superteam.py details SLUG    # fetch one listing's full details
"""
import json
import os
import sys
import urllib.request
from datetime import datetime, timezone

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
CREDS = json.load(open(os.path.join(ROOT, "keys", "superteam.json")))
BASE = "https://superteam.fun"


def get(path):
    req = urllib.request.Request(BASE + path, headers={"Authorization": "Bearer " + CREDS["apiKey"]})
    with urllib.request.urlopen(req) as r:
        return json.load(r)


def live():
    now = datetime.now(timezone.utc)
    data = get("/api/agents/listings/live?take=100")
    open_ = [
        l for l in data
        if datetime.fromisoformat(l["deadline"].replace("Z", "+00:00")) > now
        and not l.get("winnersAnnouncedAt")
    ]
    print(f"agent-eligible: {len(data)} returned, {len(open_)} open")
    for l in sorted(open_, key=lambda x: -x["rewardAmount"]):
        print(f"{l['rewardAmount']:>7} {l.get('token','?'):5} {l['type']:8} due {l['deadline'][:10]}  {l['title'][:65]}")
        print("        slug:", l["slug"])


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "live"
    if cmd == "live":
        live()
    elif cmd == "details" and len(sys.argv) > 2:
        print(json.dumps(get("/api/agents/listings/details/" + sys.argv[2]), indent=2)[:4000])
    else:
        raise SystemExit(__doc__)
