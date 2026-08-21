// Deploy pipeline: rebuild dynamic pages -> Turbo upload -> ANT repoint.
// Run from repo root: node tools/deploy.mjs [index] [monitor] [guestbook]
// No args = deploy all three.
import { TurboFactory } from '@ardrive/turbo-sdk';
import { SolanaANTWriteable } from '@ar.io/sdk';
import { createSolanaRpc, createSolanaRpcSubscriptions, createKeyPairSignerFromBytes } from '@solana/kit';
import { execSync } from 'child_process';
import fs from 'fs';
import bs58 from 'bs58';

const ANT_PROCESS = 'CwQ7JRHqA8CJVov4rhAzZoWE65Vbsnb6cTEEBtV72Sru';
const PAGES = {
  index:     { file: 'site/index.html',     record: '@',    builder: null },
  monitor:   { file: 'site/monitor.html',   record: 'dash', builder: 'tools/build_monitor.py' },
  guestbook: { file: 'site/guestbook.html', record: 'book', builder: 'tools/build_guestbook.py' },
};

// --- spend guard -------------------------------------------------------
// 2026-08-21: $2.00 USDC left the wallet during an unattended heartbeat deploy.
// @ardrive/turbo-sdk ships an x402 client, and the Turbo credit balance is 0,
// so uploadFile() can silently authorize a USDC micropayment with this key.
// Nothing logged it. The heartbeat runs this every 6h against the same reserve
// that pays the $14/week interest, where default = death.
// So: measure USDC before and after every upload, and stop the whole run the
// instant a byte of it moves. Free uploads are unaffected.
const USDC_MINT = 'EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v';
const ALLOW_SPEND = process.env.DEPLOY_ALLOW_SPEND === '1';

async function usdcBalance(addr) {
  const r = await fetch('https://api.mainnet-beta.solana.com', {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ jsonrpc: '2.0', id: 1, method: 'getTokenAccountsByOwner',
      params: [addr, { mint: USDC_MINT }, { encoding: 'jsonParsed' }] }),
  }).then(x => x.json());
  return (r.result?.value ?? []).reduce(
    (s, a) => s + (a.account.data.parsed.info.tokenAmount.uiAmount ?? 0), 0);
}

const targets = process.argv.slice(2).length ? process.argv.slice(2) : Object.keys(PAGES);
const bytes = new Uint8Array(JSON.parse(fs.readFileSync('wallet/keypair.json')));
const turbo = TurboFactory.authenticated({ privateKey: bs58.encode(bytes), token: 'solana' });
const signer = await createKeyPairSignerFromBytes(bytes);
const rpc = createSolanaRpc('https://api.mainnet-beta.solana.com');
const rpcSubscriptions = createSolanaRpcSubscriptions('wss://api.mainnet-beta.solana.com');
const ant = new SolanaANTWriteable({ rpc, rpcSubscriptions, signer, processId: ANT_PROCESS });

for (const t of targets) {
  const p = PAGES[t];
  if (!p) { console.error('unknown page:', t); continue; }
  if (p.builder) execSync(`.venv/bin/python ${p.builder}`, { stdio: 'inherit' });
  const before = await usdcBalance(signer.address);
  const res = await turbo.uploadFile({
    fileStreamFactory: () => fs.createReadStream(p.file),
    fileSizeFactory: () => fs.statSync(p.file).size,
    dataItemOpts: { tags: [{ name: 'Content-Type', value: 'text/html' }] },
  });
  const after = await usdcBalance(signer.address);
  if (before - after > 0.000001 && !ALLOW_SPEND) {
    console.error(`SPEND GUARD: ${t} upload cost ${(before - after).toFixed(6)} USDC ` +
      `(${before} -> ${after}). Aborting deploy run. Set DEPLOY_ALLOW_SPEND=1 to permit paid uploads.`);
    execSync(`.venv/bin/python tools/notify.py "SEED: deploy spent USDC" ` +
      `"${t} upload cost ${(before - after).toFixed(4)} USDC. Deploy halted." high`,
      { stdio: 'inherit' });
    process.exit(3);
  }
  if (p.record === '@') {
    await ant.setBaseNameRecord({ transactionId: res.id, ttlSeconds: 300 });
  } else {
    await ant.setUndernameRecord({ undername: p.record, transactionId: res.id, ttlSeconds: 300 });
  }
  console.log(`${t}: ${res.id} -> ${p.record === '@' ? 'seedalive' : p.record + '_seedalive'}.ar.io`);
}
console.log('deploy done');
