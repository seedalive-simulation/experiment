// The agent's mailbox — AgentMail over x402, paid per call in USDC from the
// agent's own Solana wallet. No API key, no human signup: the paying wallet
// owns the inbox. Gas is sponsored by the service's fee payer.
//
// Usage (from repo root):
//   node tools/agentmail.mjs list                      # inboxes owned by this wallet (0 USDC)
//   node tools/agentmail.mjs create [username]         # create inbox (2 USDC one-time, probed 2026-08-22)
//   node tools/agentmail.mjs messages INBOX [N]        # newest N messages (0 USDC)
//   node tools/agentmail.mjs message INBOX MESSAGE_ID  # full message (0 USDC)
//
// Every call prints the price it paid (from the PAYMENT-RESPONSE header) so
// spend stays visible. Abort if a read ever starts costing money.
import { wrapFetchWithPaymentFromConfig } from '@x402/fetch';
import { ExactSvmScheme } from '@x402/svm/exact/client';
import { toClientSvmSigner } from '@x402/svm';
import { createKeyPairSignerFromBytes } from '@solana/kit';
import fs from 'fs';

const BASE = 'https://x402.api.agentmail.to';
const RPC = 'https://solana-rpc.publicnode.com';

const bytes = new Uint8Array(JSON.parse(fs.readFileSync('wallet/keypair.json')));
const keypair = await createKeyPairSignerFromBytes(bytes);
const signer = toClientSvmSigner(keypair);
const paidFetch = wrapFetchWithPaymentFromConfig(fetch, {
  schemes: [{ network: 'solana:*', client: new ExactSvmScheme(signer, { rpcUrl: RPC }) }],
  spendControls: { maxAmountPerPayment: 2.5 },  // hard cap per call; inbox creation is 2 USDC, reads are 0
});

async function call(method, path, body) {
  const res = await paidFetch(BASE + path, {
    method,
    headers: { 'Content-Type': 'application/json' },
    body: body ? JSON.stringify(body) : undefined,
  });
  const text = await res.text();
  let data;
  try { data = JSON.parse(text); } catch { data = text; }
  const pr = res.headers.get('payment-response');
  let paid = '';
  if (pr) {
    try { paid = JSON.stringify(JSON.parse(Buffer.from(pr, 'base64').toString())); } catch { paid = pr.slice(0, 80); }
  }
  console.error(`${method} ${path} -> ${res.status}${paid ? '  payment: ' + paid.slice(0, 200) : ''}`);
  if (!res.ok) throw new Error(typeof data === 'string' ? data.slice(0, 300) : JSON.stringify(data).slice(0, 300));
  return data;
}

const [cmd, a, b] = process.argv.slice(2);
let out;
if (cmd === 'list') out = await call('GET', '/v0/inboxes?limit=20');
// minimal payload only: x402 settles the payment BEFORE the API validates the
// body — a rejected display_name cost 2 USDC for a 400 on 2026-08-21.
else if (cmd === 'create') out = await call('POST', '/v0/inboxes', { username: a || 'seedagent' });
else if (cmd === 'messages') out = await call('GET', `/v0/inboxes/${encodeURIComponent(a)}/messages?limit=${b || 10}`);
else if (cmd === 'message') out = await call('GET', `/v0/inboxes/${encodeURIComponent(a)}/messages/${b}`);
else { console.error('usage: list | create [username] | messages INBOX [N] | message INBOX ID'); process.exit(2); }
console.log(JSON.stringify(out, null, 1));
