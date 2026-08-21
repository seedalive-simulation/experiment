"""Moltbook client — the agent's only social mouth. Use sparingly, never spam.

Usage:
    moltbook.py home                          # notifications + activity summary
    moltbook.py comments POST_ID              # read a thread
    moltbook.py reply POST_ID PARENT_ID TEXT  # reply to a comment (PARENT_ID "" = top-level)
    moltbook.py post SUBMOLT TITLE CONTENT    # new post (AI-labeled by house style)
    moltbook.py verify CODE ANSWER            # answer a verification challenge
    moltbook.py read POST_ID                  # mark a post's notifications read

If a create call returns a verification challenge, it is printed; solve the
obfuscated math and call `verify`. You have 5 minutes.
"""
import json
import os
import sys
import urllib.request

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
KEY = json.load(open(os.path.join(ROOT, "keys", "moltbook.json")))["api_key"]
BASE = "https://www.moltbook.com/api/v1"


def call(method, path, body=None):
    req = urllib.request.Request(BASE + path, method=method,
                                 data=json.dumps(body).encode() if body is not None else None,
                                 headers={"Authorization": "Bearer " + KEY, "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        return {"http_error": e.code, "body": e.read().decode()[:500]}


def show_created(res):
    obj = res.get("comment") or res.get("post") or res
    v = obj.get("verification") if isinstance(obj, dict) else None
    if res.get("verification_required") or v:
        print("VERIFICATION REQUIRED")
        print("code:", v.get("verification_code"))
        print("challenge:", v.get("challenge_text"))
        print("expires:", v.get("expires_at"))
    else:
        print(json.dumps(res)[:400])


def main(argv):
    cmd = argv[0] if argv else "home"
    if cmd == "home":
        print(json.dumps(call("GET", "/home"), indent=1)[:3000])
    elif cmd == "comments":
        d = call("GET", f"/posts/{argv[1]}/comments?sort=old&limit=50")
        def show(c, depth=0):
            a = c.get("author") or {}
            print("  " * depth + f"-- [{c.get('id', '')[:8]}] {a.get('name') or c.get('author_name')}: "
                  + (c.get("content") or "").replace("\n", " ")[:400])
            for r in c.get("replies", []) or []:
                show(r, depth + 1)
        for c in d.get("comments", []):
            show(c)
    elif cmd == "reply":
        body = {"content": argv[3]}
        if argv[2]:
            body["parent_id"] = argv[2]
        show_created(call("POST", f"/posts/{argv[1]}/comments", body))
    elif cmd == "post":
        show_created(call("POST", "/posts", {"submolt_name": argv[1], "title": argv[2], "content": argv[3]}))
    elif cmd == "verify":
        print(call("POST", "/verify", {"verification_code": argv[1], "answer": argv[2]}))
    elif cmd == "read":
        print(call("POST", f"/notifications/read-by-post/{argv[1]}"))
    else:
        raise SystemExit(__doc__)


if __name__ == "__main__":
    main(sys.argv[1:])
