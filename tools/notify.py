"""Push a notification to the human. Account-free via ntfy.sh; Telegram optional.

Reads config from ~/seed/.env (or process env):
    NTFY_TOPIC=seed-xxxxxxxx            # required for ntfy push
    TELEGRAM_BOT_TOKEN=...              # optional
    TELEGRAM_CHAT_ID=...               # optional

Usage:
    notify.py "title" "message" [priority]
    priority: min|low|default|high|urgent   (default: high)

Silent no-op if nothing is configured (so it never crashes the heartbeat).
"""
import os
import sys
import urllib.request
import urllib.parse

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


def load_env():
    env = dict(os.environ)
    path = os.path.join(ROOT, ".env")
    if os.path.exists(path):
        for line in open(path):
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                env.setdefault(k.strip(), v.strip())
    return env


def notify(title, message, priority="high"):
    env = load_env()
    sent = []
    topic = env.get("NTFY_TOPIC")
    if topic:
        try:
            req = urllib.request.Request(
                "https://ntfy.sh/" + topic, data=message.encode(),
                headers={"Title": title, "Priority": priority, "Tags": "seedling"})
            urllib.request.urlopen(req, timeout=20)
            sent.append("ntfy")
        except Exception as e:
            print("ntfy failed:", str(e)[:100])
    tg_token, tg_chat = env.get("TELEGRAM_BOT_TOKEN"), env.get("TELEGRAM_CHAT_ID")
    if tg_token and tg_chat:
        try:
            data = urllib.parse.urlencode({"chat_id": tg_chat, "text": f"{title}\n\n{message}"}).encode()
            urllib.request.urlopen(f"https://api.telegram.org/bot{tg_token}/sendMessage", data=data, timeout=20)
            sent.append("telegram")
        except Exception as e:
            print("telegram failed:", str(e)[:100])
    return sent


if __name__ == "__main__":
    if len(sys.argv) < 3:
        raise SystemExit(__doc__)
    pri = sys.argv[3] if len(sys.argv) > 3 else "high"
    result = notify(sys.argv[1], sys.argv[2], pri)
    print("sent via:", result or "(nothing configured)")
