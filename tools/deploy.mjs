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
  const res = await turbo.uploadFile({
    fileStreamFactory: () => fs.createReadStream(p.file),
    fileSizeFactory: () => fs.statSync(p.file).size,
    dataItemOpts: { tags: [{ name: 'Content-Type', value: 'text/html' }] },
  });
  if (p.record === '@') {
    await ant.setBaseNameRecord({ transactionId: res.id, ttlSeconds: 300 });
  } else {
    await ant.setUndernameRecord({ undername: p.record, transactionId: res.id, ttlSeconds: 300 });
  }
  console.log(`${t}: ${res.id} -> ${p.record === '@' ? 'seedalive' : p.record + '_seedalive'}.ar.io`);
}
console.log('deploy done');
