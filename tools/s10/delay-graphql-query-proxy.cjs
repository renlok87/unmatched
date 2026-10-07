// VS-4 V4 evidence (HB-47, VS-3 item 5 / ВР-VS3-R04): a local GraphQL proxy that holds the reply of ONE named query
// field (default gameDeckLists) for a fixed time, so a live client shows its loading state (the deck panel's skeleton
// after 300 ms, 04 §3.3). Everything else - other queries, mutations, graphql-transport-ws - is forwarded untouched.
//
// S10_LISTEN_PORT=3123 S10_TARGET_PORT=3000 S10_DELAY_FIELD=gameDeckLists S10_DELAY_MS=12000 node delay-graphql-query-proxy.cjs
//
// VS-4 HB-49 (HB-14 link states, opt-in): S10_DELAY_FIELD may also name one mutation (beginManeuver / maneuver /
// endTurn) - only its first S10_DELAY_COUNT replies (default 1) are held, so the client's command stays in flight past
// its 3 s slow mark (CONN syncing); S10_WS_DROP_AT_MS=<ms> closes every open graphql-transport-ws connection once, that
// long after the first one opened (the match stream drops: CONN lost until the client reconnects).
// Local-only; no request bodies, tokens, room codes or card data are logged (only field names and counts).
const http = require('node:http');
const net = require('node:net');

const listenPort = Number(process.env.S10_LISTEN_PORT || 3123);
const targetPort = Number(process.env.S10_TARGET_PORT || 3000);
const delayField = process.env.S10_DELAY_FIELD || 'gameDeckLists';
const delayMs = Number(process.env.S10_DELAY_MS || 12000);
const permitted = new Set(['gameDeckLists']);
const permittedMutations = new Set(['beginManeuver', 'maneuver', 'endTurn']);
const delayCount = Number(process.env.S10_DELAY_COUNT || 1);
const wsDropAtMs = Number(process.env.S10_WS_DROP_AT_MS || 0);
if (!Number.isInteger(listenPort) || listenPort < 1024 || listenPort > 65535 ||
    !Number.isInteger(targetPort) || targetPort < 1024 || targetPort > 65535 ||
    !(permitted.has(delayField) || permittedMutations.has(delayField)) || listenPort === targetPort ||
    !(delayMs >= 0 && delayMs <= 120000) || !(Number.isInteger(delayCount) && delayCount >= 1) ||
    !(wsDropAtMs >= 0 && wsDropAtMs <= 3600000)) {
  throw new Error('Set distinct local S10_LISTEN_PORT/S10_TARGET_PORT, a permitted S10_DELAY_FIELD, S10_DELAY_MS <= 120000, ' +
                  'S10_DELAY_COUNT >= 1 and S10_WS_DROP_AT_MS <= 3600000');
}
const delayMutation = permittedMutations.has(delayField);

let delayed = 0;
let wsConnections = 0;
let wsDropped = 0;
const wsPairs = new Set();
let wsDropTimer = null;

/** The top-level field of a mutation document ('' for a query or an unreadable body). */
function mutationField(body) {
  try {
    const query = JSON.parse(body).query;
    if (typeof query !== 'string' || !/^\s*mutation\b/.test(query)) return '';
    const match = query.match(/\bmutation\b[^{}]*\{\s*([A-Za-z][A-Za-z0-9_]*)\s*\(/);
    return match ? match[1] : '';
  } catch { return ''; }
}

/** The top-level field of a query document ('' for a mutation or an unreadable body). */
function queryField(body) {
  try {
    const query = JSON.parse(body).query;
    if (typeof query !== 'string' || /^\s*mutation\b/.test(query)) return '';
    const match = query.match(/\{\s*([A-Za-z][A-Za-z0-9_]*)\s*\(/);
    return match ? match[1] : '';
  } catch { return ''; }
}

const server = http.createServer((downstreamReq, downstreamRes) => {
  const chunks = [];
  let bytes = 0;
  downstreamReq.on('data', (chunk) => {
    bytes += chunk.length;
    if (bytes > 1024 * 1024) {
      downstreamReq.destroy(new Error('request too large'));
      return;
    }
    chunks.push(chunk);
  });
  downstreamReq.on('end', () => {
    const body = Buffer.concat(chunks);
    const text = body.toString('utf8');
    const field = delayMutation ? mutationField(text) : queryField(text);
    const upstreamReq = http.request({
      hostname: '127.0.0.1', port: targetPort,
      method: downstreamReq.method, path: downstreamReq.url,
      headers: { ...downstreamReq.headers, host: `127.0.0.1:${targetPort}` },
    }, (upstreamRes) => {
      const responseChunks = [];
      upstreamRes.on('data', (chunk) => responseChunks.push(chunk));
      upstreamRes.on('end', () => {
        const reply = Buffer.concat(responseChunks);
        const send = () => {
          if (downstreamRes.destroyed || !downstreamRes.writable) return;
          downstreamRes.writeHead(upstreamRes.statusCode || 502, upstreamRes.headers);
          downstreamRes.end(reply);
        };
        if (field === delayField && (!delayMutation || delayed < delayCount)) {
          delayed++;
          process.stdout.write(JSON.stringify({ event: 'reply_delayed', field, ms: delayMs, n: delayed }) + '\n');
          setTimeout(send, delayMs);
        } else {
          send();
        }
      });
    });
    upstreamReq.on('error', () => {
      if (!downstreamRes.headersSent) downstreamRes.writeHead(502);
      downstreamRes.end();
    });
    upstreamReq.end(body);
  });
});

server.on('upgrade', (request, downstream, head) => {
  wsConnections++;
  const upstream = net.connect(targetPort, '127.0.0.1');
  const pair = { upstream, downstream };
  wsPairs.add(pair);
  downstream.on('close', () => wsPairs.delete(pair));
  if (wsDropAtMs > 0 && !wsDropTimer && wsDropped === 0) {
    wsDropTimer = setTimeout(() => {
      for (const p of wsPairs) {
        wsDropped++;
        p.downstream.destroy();
        p.upstream.destroy();
      }
      wsPairs.clear();
      process.stdout.write(JSON.stringify({ event: 'ws_dropped', atMs: wsDropAtMs, n: wsDropped }) + '\n');
    }, wsDropAtMs);
  }
  upstream.on('connect', () => {
    let header = `${request.method} ${request.url} HTTP/${request.httpVersion}\r\n`;
    for (let i = 0; i < request.rawHeaders.length; i += 2) {
      const key = request.rawHeaders[i];
      const value = key.toLowerCase() === 'host' ? `127.0.0.1:${targetPort}` : request.rawHeaders[i + 1];
      header += `${key}: ${value}\r\n`;
    }
    upstream.write(header + '\r\n');
    if (head.length) upstream.write(head);
    downstream.pipe(upstream);
    upstream.pipe(downstream);
  });
  upstream.on('error', () => downstream.destroy());
  downstream.on('error', () => upstream.destroy());
  downstream.on('close', () => upstream.destroy());
});

server.listen(listenPort, '127.0.0.1', () => {
  process.stdout.write(JSON.stringify({ event: 'listening', port: listenPort, targetPort, delayField, delayMs,
                                        delayCount: delayMutation ? delayCount : null, wsDropAtMs }) + '\n');
});

function finish() {
  if (wsDropTimer) clearTimeout(wsDropTimer);
  process.stdout.write(JSON.stringify({ event: 'summary', delayed, wsConnections, wsDropped }) + '\n');
  server.close(() => process.exit(0));
}
process.on('SIGINT', finish);
process.on('SIGTERM', finish);
