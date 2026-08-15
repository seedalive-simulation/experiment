"""Tier-2 brain: free local model (Ollama on jarvis) for routine judgment.

Reads QUEUE.md, decides for each flagged item whether it (a) can be handled
mechanically / skipped, or (b) genuinely needs the expensive Claude brain.
Writes its triage verdict into QUEUE.md so wake.sh can decide whether to
spend API money. Costs nothing but CPU time.

Usage:
    reflex.py triage             # annotate QUEUE.md with local-brain verdicts
    reflex.py ask "prompt"       # one-shot local generation (for other tools)
"""
import json
import os
import subprocess
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
QUEUE = os.path.join(ROOT, "QUEUE.md")
MODEL = os.environ.get("REFLEX_MODEL", "qwen3:4b-instruct")


def ask(prompt, timeout=180):
    r = subprocess.run(["ollama", "run", MODEL], input=prompt,
                       capture_output=True, text=True, timeout=timeout)
    return r.stdout.strip()


def triage():
    if not os.path.exists(QUEUE):
        print("no queue")
        return
    q = open(QUEUE).read()
    if "(nothing — all quiet)" in q:
        print("all quiet, no triage needed")
        return
    verdict = ask(
        "You are the cheap reflex brain of a survival AI agent. Its expensive brain "
        "costs real money per wake, so your job is to decide if this queue truly "
        "needs it. The expensive brain SHOULD wake for: open bounties worth "
        "submitting, paid commissions or guestbook payments to deliver, interest "
        "problems, security issues, replies from real agents worth answering. It "
        "should NOT wake for: empty pipelines, ambient noise, follows/likes, "
        "unactionable status. Read the queue below and answer with EXACTLY one "
        "first line: 'WAKE' or 'SLEEP', then max 3 short lines of reasoning.\n\n"
        "=== QUEUE ===\n" + q)
    first = (verdict.splitlines() or ["SLEEP"])[0].strip().upper()
    decision = "WAKE" if "WAKE" in first else "SLEEP"
    with open(QUEUE, "a") as f:
        f.write(f"\n## Reflex triage (local model, $0)\n- verdict: {decision}\n")
        for line in verdict.splitlines()[1:4]:
            if line.strip():
                f.write(f"- {line.strip()}\n")
    print("reflex verdict:", decision)
    return decision


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "triage"
    if cmd == "triage":
        triage()
    elif cmd == "ask" and len(sys.argv) > 2:
        print(ask(sys.argv[2]))
    else:
        raise SystemExit(__doc__)
