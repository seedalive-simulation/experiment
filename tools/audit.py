"""Append-only audit log. Every action and decision goes through here.

Usage:
    audit.py TYPE SUMMARY [DETAIL]

TYPE: decision | action | spend | revenue | observation | milestone | error
Writes JSONL to audit/log.jsonl and regenerates audit/AUDIT.md.
"""
import json
import os
import sys
from datetime import datetime, timezone

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
LOG = os.path.join(ROOT, "audit", "log.jsonl")
MD = os.path.join(ROOT, "audit", "AUDIT.md")

VALID = {"decision", "action", "spend", "revenue", "observation", "milestone", "error"}


def append(entry_type, summary, detail=""):
    if entry_type not in VALID:
        raise SystemExit(f"invalid type {entry_type!r}, must be one of {sorted(VALID)}")
    os.makedirs(os.path.dirname(LOG), exist_ok=True)
    entry = {
        "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "type": entry_type,
        "summary": summary,
        "detail": detail,
    }
    with open(LOG, "a") as f:
        f.write(json.dumps(entry) + "\n")
    regenerate_md()
    return entry


def regenerate_md():
    lines = [
        "# Audit log",
        "",
        "Human-readable view. Source of truth: `audit/log.jsonl` (append-only).",
        "",
        "| Time (UTC) | Type | Summary | Detail |",
        "|---|---|---|---|",
    ]
    with open(LOG) as f:
        for raw in f:
            e = json.loads(raw)
            detail = e["detail"].replace("|", "\\|").replace("\n", " ")
            summary = e["summary"].replace("|", "\\|")
            lines.append(f"| {e['ts']} | {e['type']} | {summary} | {detail} |")
    with open(MD, "w") as f:
        f.write("\n".join(lines) + "\n")


if __name__ == "__main__":
    if len(sys.argv) < 3:
        raise SystemExit(__doc__)
    e = append(sys.argv[1], sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else "")
    print(f"logged: [{e['type']}] {e['summary']}")
