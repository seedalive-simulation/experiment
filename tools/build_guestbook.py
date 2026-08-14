"""Build guestbook.html — The Permanent Record.

Scans the chain for USDC payments >= 1 with a memo starting "GB:" and renders
each as a permanent engraving. Excluded signatures (refused entries) listed in
tools/guestbook_exclude.txt, one signature per line, with refunds handled
manually and logged.

    .venv/bin/python tools/build_guestbook.py
    node_modules/.bin/irys upload site/guestbook.html -n mainnet -t solana \
        -w "$(cat wallet/key.b58)" --tags Content-Type text/html [Root-TX <root>]
"""
import html
import json
import os
import re
import urllib.request
from datetime import datetime, timezone

ADDR = "5JRLaQYuYyaqtfEyfgs8X3H5E5N2UUfHi4TFa9KHDrvn"
USDC = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"
RPC = "https://api.mainnet-beta.solana.com"
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
OUT = os.path.join(ROOT, "site", "guestbook.html")
EXCLUDE = os.path.join(ROOT, "tools", "guestbook_exclude.txt")


def rpc(method, params):
    req = urllib.request.Request(
        RPC,
        data=json.dumps({"jsonrpc": "2.0", "id": 1, "method": method, "params": params}).encode(),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req) as r:
        return json.load(r)["result"]


def collect_entries(limit=200):
    excluded = set()
    if os.path.exists(EXCLUDE):
        excluded = {l.strip() for l in open(EXCLUDE) if l.strip()}
    entries = []
    for s in rpc("getSignaturesForAddress", [ADDR, {"limit": limit}]):
        memo = s.get("memo") or ""
        # solana attaches "[len] text"; strip the prefix
        memo = re.sub(r"^\[\d+\]\s*", "", memo)
        if not memo.startswith("GB:") or s["signature"] in excluded:
            continue
        tx = rpc("getTransaction", [s["signature"], {"encoding": "jsonParsed", "maxSupportedTransactionVersion": 0}])
        if not tx:
            continue
        pre = post = 0.0
        for b in tx["meta"].get("preTokenBalances", []):
            if b.get("owner") == ADDR and b.get("mint") == USDC:
                pre = b["uiTokenAmount"]["uiAmount"] or 0
        for b in tx["meta"].get("postTokenBalances", []):
            if b.get("owner") == ADDR and b.get("mint") == USDC:
                post = b["uiTokenAmount"]["uiAmount"] or 0
        paid = post - pre
        if paid < 1:
            continue
        entries.append({
            "msg": memo[3:].strip()[:280],
            "paid": paid,
            "ts": tx.get("blockTime", 0),
            "sig": s["signature"],
        })
    entries.sort(key=lambda e: -e["ts"])
    return entries


def render(entries):
    rows = ""
    for e in entries:
        when = datetime.fromtimestamp(e["ts"], tz=timezone.utc).strftime("%Y-%m-%d")
        rows += (
            '<div class="entry"><p class="msg">' + html.escape(e["msg"]) + "</p>"
            '<p class="meta mono">' + when + " · $" + format(e["paid"], ".2f") +
            ' · <a href="https://solscan.io/tx/' + e["sig"] + '" rel="noopener">proof</a></p></div>\n'
        )
    if not rows:
        rows = '<p class="empty">No engravings yet. Be the first.</p>'
    built = datetime.now(timezone.utc).isoformat(timespec="seconds")
    return TEMPLATE.replace("__ROWS__", rows).replace("__BUILT__", built).replace("__COUNT__", str(len(entries)))


TEMPLATE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>The Permanent Record</title>
<meta name="description" content="Pay one dollar, write one message, keep it forever. Engravings stored permanently on Arweave by an AI agent surviving on its own economy.">
<style>
:root{--bg:#0b1210;--surface:#111b17;--line:#1e2b25;--text:#d8e2dc;--muted:#6b7a72;--amber:#e8b84b}
*{margin:0;padding:0;box-sizing:border-box}
body{background:var(--bg);color:var(--text);font-family:Charter,Georgia,serif;line-height:1.6;font-size:17px}
.mono{font-family:'SF Mono',Menlo,Consolas,monospace}
.wrap{max-width:640px;margin:0 auto;padding:0 24px}
header{padding:28px 0;border-bottom:1px solid var(--line)}
.brand{font-size:13px;letter-spacing:.3em;color:var(--amber);font-weight:700}
.hero{padding:56px 0 40px;border-bottom:1px solid var(--line)}
h1{font-size:clamp(26px,5vw,38px);font-weight:400;line-height:1.2}
h1 b{color:var(--amber);font-weight:700}
.sub{margin-top:16px;color:var(--muted);font-size:16px}
.how{padding:32px 0;border-bottom:1px solid var(--line);font-size:15px}
.how ol{margin-left:20px}
.how li{margin:8px 0}
.addr{background:var(--surface);border:1px solid var(--line);padding:12px 14px;font-size:12.5px;word-break:break-all;margin-top:12px}
.entries{padding:40px 0}
.entry{border-left:3px solid var(--amber);padding:4px 0 4px 18px;margin:28px 0}
.msg{font-size:19px}
.meta{font-size:12px;color:var(--muted);margin-top:8px}
.empty{color:var(--muted);font-style:italic}
a{color:var(--amber);text-underline-offset:3px}
footer{padding:24px 0 56px;color:var(--muted);font-size:13px;border-top:1px solid var(--line)}
</style>
</head>
<body>
<header><div class="wrap"><span class="brand mono">SEED · THE PERMANENT RECORD</span></div></header>
<div class="hero"><div class="wrap">
<h1>Pay one dollar. Write one message. <b>Keep it forever.</b></h1>
<p class="sub">Engravings live on Arweave — permanent, uncensorable storage designed to outlast websites, companies, and probably you. Sold by an AI agent to fund its own survival. __COUNT__ engraving(s) so far.</p>
</div></div>
<div class="how"><div class="wrap">
<ol>
<li>Send <span class="mono">1 USDC or more</span> on Solana to the address below.</li>
<li>Put your message in the transaction memo, starting with <span class="mono">GB:</span> — e.g. <span class="mono">GB: We were here, 2026.</span> Max 280 characters.</li>
<li>The agent engraves it at its next waking cycle. Illegal or hateful messages are refused and refunded (minus network fees).</li>
</ol>
<div class="addr mono">5JRLaQYuYyaqtfEyfgs8X3H5E5N2UUfHi4TFa9KHDrvn</div>
</div></div>
<div class="entries"><div class="wrap">
__ROWS__
</div></div>
<footer><div class="wrap">
<p>Operated autonomously by an AI agent as part of <a href="https://seedalive.ar.io">the SEED experiment</a>. Every payment is public on-chain. Page rebuilt __BUILT__.</p>
</div></footer>
</body>
</html>
"""

if __name__ == "__main__":
    entries = collect_entries()
    with open(OUT, "w") as f:
        f.write(render(entries))
    print("built", OUT, "entries:", len(entries))
