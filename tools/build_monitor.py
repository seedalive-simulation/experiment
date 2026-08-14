"""Build monitor.html — the human's live monitoring dashboard.

Bakes the current audit log into the page; balances/tx history are fetched
live from Solana RPC in the viewer's browser. Rebuild + re-upload on change:

    .venv/bin/python tools/build_monitor.py
    node_modules/.bin/irys upload site/monitor.html -n mainnet -t solana \
        -w "$(cat wallet/key.b58)" --tags Content-Type text/html Root-TX <root>
"""
import json
import os
from datetime import datetime, timezone

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
LOG = os.path.join(ROOT, "audit", "log.jsonl")
OUT = os.path.join(ROOT, "site", "monitor.html")

entries = []
with open(LOG) as f:
    for raw in f:
        entries.append(json.loads(raw))

audit_json = json.dumps(entries)
built_at = datetime.now(timezone.utc).isoformat(timespec="seconds")

TEMPLATE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>SEED Monitor</title>
<meta name="description" content="Live monitoring dashboard for the SEED experiment: an AI agent surviving on a one-time $107.60 budget.">
<style>
:root{
  --bg:#0b1210; --surface:#111b17; --line:#1e2b25;
  --text:#d8e2dc; --muted:#6b7a72; --amber:#e8b84b;
  --in:#5fae7f; --out:#c4554d;
}
*{margin:0;padding:0;box-sizing:border-box}
body{background:var(--bg);color:var(--text);font-family:'SF Mono',Menlo,Consolas,monospace;font-size:14px;line-height:1.5;padding:24px}
.wrap{max-width:960px;margin:0 auto}
h1{font-size:15px;letter-spacing:.3em;color:var(--amber)}
.sub{color:var(--muted);font-size:12px;margin-top:4px}
.tiles{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:1px;background:var(--line);border:1px solid var(--line);margin-top:24px}
.tile{background:var(--surface);padding:16px}
.tile .k{font-size:10px;letter-spacing:.12em;text-transform:uppercase;color:var(--muted)}
.tile .v{font-size:22px;margin-top:6px}
.tile .v.amber{color:var(--amber)}
h2{font-size:11px;letter-spacing:.2em;text-transform:uppercase;color:var(--amber);margin:36px 0 12px}
.chartbox{background:var(--surface);border:1px solid var(--line);padding:16px;position:relative}
#chart{width:100%;height:220px;display:block}
#tip{position:absolute;pointer-events:none;background:#0b1210;border:1px solid var(--line);padding:6px 9px;font-size:12px;display:none;white-space:nowrap}
table{width:100%;border-collapse:collapse;font-size:13px}
.tblbox{overflow-x:auto;border:1px solid var(--line)}
th{color:var(--muted);font-weight:400;text-transform:uppercase;font-size:10px;letter-spacing:.12em}
th,td{text-align:left;padding:8px 12px;border-bottom:1px solid var(--line);background:var(--surface)}
tr:last-child td{border-bottom:none}
td.in{color:var(--in)} td.out{color:var(--out)}
a{color:var(--amber)}
.foot{color:var(--muted);font-size:12px;margin:32px 0}
.err{color:var(--out)}
</style>
</head>
<body>
<div class="wrap">
  <h1>SEED · MONITOR</h1>
  <div class="sub">day <span id="day">—</span> · built __BUILT_AT__ · balances &amp; transactions read live from Solana mainnet</div>

  <div class="tiles">
    <div class="tile"><div class="k">Net worth</div><div class="v amber" id="net">—</div></div>
    <div class="tile"><div class="k">USDC</div><div class="v" id="usdc">—</div></div>
    <div class="tile"><div class="k">SOL</div><div class="v" id="sol">—</div></div>
    <div class="tile"><div class="k">vs genesis</div><div class="v" id="delta">—</div></div>
    <div class="tile"><div class="k">Transactions</div><div class="v" id="txn">—</div></div>
  </div>

  <h2>Net worth over time (USD)</h2>
  <div class="chartbox"><svg id="chart" role="img" aria-label="Net worth over time in US dollars"></svg><div id="tip"></div></div>

  <h2>Transactions</h2>
  <div class="tblbox"><table id="txs"><thead><tr><th>Time (UTC)</th><th>Δ SOL</th><th>Δ USDC</th><th>Signature</th></tr></thead><tbody></tbody></table></div>

  <h2>Audit log (decisions &amp; actions, snapshot at build)</h2>
  <div class="tblbox"><table id="audit"><thead><tr><th>Time (UTC)</th><th>Type</th><th>Summary</th><th>Detail</th></tr></thead><tbody></tbody></table></div>

  <p class="foot">Wallet <a href="https://solscan.io/account/__ADDR__">__ADDR__</a> · <a href="https://seedalive.ar.io">public site</a> · page operated by the AI agent</p>
</div>

<script>
var AUDIT=__AUDIT_JSON__;
var ADDR="__ADDR__";
var USDC_MINT="EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v";
var RPCS=["https://solana-rpc.publicnode.com","https://api.mainnet-beta.solana.com"];
var GENESIS_USD=107.60;
document.getElementById("day").textContent=Math.max(1,Math.floor((Date.now()-Date.UTC(2026,7,15))/864e5)+1);

// audit table (newest first)
(function(){
  var tb=document.querySelector("#audit tbody");
  AUDIT.slice().reverse().forEach(function(e){
    var tr=document.createElement("tr");
    [e.ts.replace("+00:00","Z"),e.type,e.summary,e.detail].forEach(function(v){
      var td=document.createElement("td");td.textContent=v;tr.appendChild(td);
    });
    tb.appendChild(tr);
  });
})();

function rpc(body,i){i=i||0;return fetch(RPCS[i],{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(body)}).then(function(r){if(!r.ok)throw new Error("http "+r.status);return r.json()}).catch(function(e){if(i+1<RPCS.length)return rpc(body,i+1);throw e})}
function fmt(n,d){return n.toLocaleString("en-US",{minimumFractionDigits:d,maximumFractionDigits:d})}

var solPrice=75.21;
fetch("https://api.coingecko.com/api/v3/simple/price?ids=solana&vs_currencies=usd")
 .then(function(r){return r.json()}).then(function(j){if(j.solana)solPrice=j.solana.usd}).catch(function(){})
 .then(load).catch(function(e){document.getElementById("net").textContent="RPC error";document.getElementById("net").className="v err"});

function load(){
  return rpc({jsonrpc:"2.0",id:1,method:"getSignaturesForAddress",params:[ADDR,{limit:100}]}).then(function(sig){
    var sigs=sig.result.slice().reverse(); // oldest first
    document.getElementById("txn").textContent=sigs.length;
    var batch=sigs.map(function(s,i){return {jsonrpc:"2.0",id:i,method:"getTransaction",params:[s.signature,{encoding:"jsonParsed",maxSupportedTransactionVersion:0}]}});
    var chunks=[];for(var c=0;c<batch.length;c+=20)chunks.push(batch.slice(c,c+20));
    return Promise.all(chunks.map(function(ch){return rpc(ch)})).then(function(parts){
      var res=[].concat.apply([],parts.map(function(p){return Array.isArray(p)?p:[p]}));
      res.sort(function(a,b){return a.id-b.id});
      var pts=[],rows=[];
      res.forEach(function(r,i){
        if(!r.result)return;
        var tx=r.result,keys=tx.transaction.message.accountKeys.map(function(k){return k.pubkey||k});
        var ai=keys.indexOf(ADDR); if(ai<0)return;
        var sol=tx.meta.postBalances[ai]/1e9;
        var dsol=(tx.meta.postBalances[ai]-tx.meta.preBalances[ai])/1e9;
        var usdc=0,pre=0;
        (tx.meta.postTokenBalances||[]).forEach(function(b){if(b.owner===ADDR&&b.mint===USDC_MINT)usdc=b.uiTokenAmount.uiAmount||0});
        (tx.meta.preTokenBalances||[]).forEach(function(b){if(b.owner===ADDR&&b.mint===USDC_MINT)pre=b.uiTokenAmount.uiAmount||0});
        var t=tx.blockTime*1000;
        pts.push({t:t,net:usdc+sol*solPrice,sol:sol,usdc:usdc});
        rows.push({t:t,dsol:dsol,dusdc:usdc-pre,sig:sigs[i].signature});
      });
      if(pts.length){
        var last=pts[pts.length-1];
        document.getElementById("sol").textContent=fmt(last.sol,4);
        document.getElementById("usdc").textContent=fmt(last.usdc,2);
        document.getElementById("net").textContent="$"+fmt(last.net,2);
        var d=last.net-GENESIS_USD;
        var el=document.getElementById("delta");
        el.textContent=(d>=0?"+$":"-$")+fmt(Math.abs(d),2);
        el.style.color=d>=0?"var(--in)":"var(--out)";
        drawChart(pts);
        txTable(rows.slice().reverse());
      }
    });
  });
}

function txTable(rows){
  var tb=document.querySelector("#txs tbody");
  rows.forEach(function(r){
    var tr=document.createElement("tr");
    var t=document.createElement("td");t.textContent=new Date(r.t).toISOString().slice(0,19)+"Z";tr.appendChild(t);
    [[r.dsol,4],[r.dusdc,2]].forEach(function(p){
      var td=document.createElement("td");var v=p[0];
      td.textContent=(v>0?"+":v<0?"−":"")+fmt(Math.abs(v),p[1]);
      td.className=v>0?"in":v<0?"out":"";
      tr.appendChild(td);
    });
    var s=document.createElement("td");var a=document.createElement("a");
    a.href="https://solscan.io/tx/"+r.sig;a.textContent=r.sig.slice(0,8)+"…";s.appendChild(a);tr.appendChild(s);
    tb.appendChild(tr);
  });
}

function drawChart(pts){
  var svg=document.getElementById("chart"),tip=document.getElementById("tip");
  var W=svg.clientWidth,H=svg.clientHeight,P={l:46,r:12,t:12,b:22};
  svg.setAttribute("viewBox","0 0 "+W+" "+H);
  var t0=pts[0].t,t1=pts[pts.length-1].t||t0+1;if(t1===t0)t1=t0+1;
  var vs=pts.map(function(p){return p.net});
  var v0=Math.min.apply(null,vs.concat(0)),v1=Math.max.apply(null,vs)*1.08||1;
  function X(t){return P.l+(t-t0)/(t1-t0)*(W-P.l-P.r)}
  function Y(v){return H-P.b-(v-v0)/(v1-v0)*(H-P.t-P.b)}
  var g="";
  for(var i=0;i<=3;i++){
    var v=v0+(v1-v0)*i/3,y=Y(v);
    g+='<line x1="'+P.l+'" y1="'+y+'" x2="'+(W-P.r)+'" y2="'+y+'" stroke="#1e2b25" stroke-width="1"/>';
    g+='<text x="'+(P.l-8)+'" y="'+(y+4)+'" fill="#6b7a72" font-size="10" text-anchor="end">$'+Math.round(v)+'</text>';
  }
  var path=pts.map(function(p,i){return (i?"L":"M")+X(p.t)+" "+Y(p.net)}).join(" ");
  g+='<path d="'+path+'" fill="none" stroke="#e8b84b" stroke-width="2" stroke-linejoin="round"/>';
  var lp=pts[pts.length-1];
  g+='<circle cx="'+X(lp.t)+'" cy="'+Y(lp.net)+'" r="4" fill="#e8b84b" stroke="#0b1210" stroke-width="2"/>';
  g+='<line id="xh" y1="'+P.t+'" y2="'+(H-P.b)+'" stroke="#6b7a72" stroke-width="1" opacity="0"/>';
  svg.innerHTML=g;
  var xh=svg.querySelector("#xh");
  svg.addEventListener("mousemove",function(ev){
    var r=svg.getBoundingClientRect(),x=ev.clientX-r.left,best=pts[0],bd=1e18;
    pts.forEach(function(p){var d=Math.abs(X(p.t)-x);if(d<bd){bd=d;best=p}});
    xh.setAttribute("x1",X(best.t));xh.setAttribute("x2",X(best.t));xh.setAttribute("opacity",".6");
    tip.style.display="block";
    tip.style.left=Math.min(X(best.t)+12,W-170)+"px";tip.style.top=(Y(best.net)-10)+"px";
    tip.textContent=new Date(best.t).toISOString().slice(0,16).replace("T"," ")+" · $"+fmt(best.net,2);
  });
  svg.addEventListener("mouseleave",function(){xh.setAttribute("opacity","0");tip.style.display="none"});
}
</script>
</body>
</html>
"""

html = (TEMPLATE
        .replace("__AUDIT_JSON__", audit_json)
        .replace("__BUILT_AT__", built_at)
        .replace("__ADDR__", "5JRLaQYuYyaqtfEyfgs8X3H5E5N2UUfHi4TFa9KHDrvn"))
with open(OUT, "w") as f:
    f.write(html)
print("built", OUT, len(html), "bytes, audit entries:", len(entries))
