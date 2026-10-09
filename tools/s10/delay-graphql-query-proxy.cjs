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
// VS-7 S1 (SC-04 / SC-07 evidence, opt-in): S10_DELAY_FIELD may name the BOOT query heroList or the mutation login;
// with S10_DELAY_COUNT set a query is held only for its first N replies too (the retry then passes). Two fields: chain
// two proxies (S10_TARGET_PORT of the first = S10_LISTEN_PORT of the second).
// VS-7 S2 (SC-08 skeleton / SC-13 error evidence, opt-in): S10_DELAY_FIELD=availableGames holds the LOBBY list query
// (12 s > the client's 10 s timeout = the error state; the next poll or «Повторить» passes with S10_DELAY_COUNT=1);
// S10_DELAY_FIELD=createGame holds the first create answer (the busy «Создаём…» with its spinner, SC-09).
// VS-7 S3 (SC-20 loading error evidence, opt-in): S10_DELAY_FIELD=gameState holds the first match state read (> the
// client's 10 s = «Не удаётся подключиться»); with S10_WS_REFUSE=1 the graphql-transport-ws upgrades are refused until a
// further gameState request arrives (the client's «Повторить») - the stream cannot bring the snapshot around the hold.
// VS-7 S5 (SC-31...SC-33 evidence, opt-in): S10_WS_DOWN_MS=<ms> keeps refusing every graphql-transport-ws upgrade that
// long after the S10_WS_DROP_AT_MS drop (the link stays down: RECONNECT auto -> manual after 5 x 10 s), then passes them.
// VC Frames (SC-32 expired evidence, opt-in): S10_EXPIRE_AFTER_DROP=1 - once the S10_WS_DROP_AT_MS drop happened, every
// GraphQL request is answered locally with an UNAUTHENTICATED error (the token refresh too) and the WS upgrades are refused:
// the client's session expires in the match (RECONNECT expired, GD-038). The backend itself is never told anything.
// VC Frames (SC-24 syncing evidence, opt-in): S10_HOLD_WS_WITH_DELAY=1 - while a delayed reply is held, the server->client
// frames of every open graphql-transport-ws connection are held too (then flushed in order): the stream cannot settle the
// command before its HTTP answer (MS-NET «gate released by snapshot»), so the command stays in flight (PAUSE syncing).
// Local-only; no request bodies, tokens, room codes or card data are logged (only field names and counts).
const http = require('node:http');
const net = require('node:net');

const listenPort = Number(process.env.S10_LISTEN_PORT || 3123);
const targetPort = Number(process.env.S10_TARGET_PORT || 3000);
const delayField = process.env.S10_DELAY_FIELD || 'gameDeckLists';
const delayMs = Number(process.env.S10_DELAY_MS || 12000);
const permitted = new Set(['gameDeckLists', 'heroList', 'availableGames', 'gameState']);
const permittedMutations = new Set(['beginManeuver', 'maneuver', 'endTurn', 'login', 'createGame']);
const delayCount = Number(process.env.S10_DELAY_COUNT || 1);
const countSet = Object.prototype.hasOwnProperty.call(process.env, 'S10_DELAY_COUNT');
const wsDropAtMs = Number(process.env.S10_WS_DROP_AT_MS || 0);
const wsRefuse = process.env.S10_WS_REFUSE === '1';
const wsDownMs = Number(process.env.S10_WS_DOWN_MS || 0);
const expireAfterDrop = process.env.S10_EXPIRE_AFTER_DROP === '1';
const holdWsWithDelay = process.env.S10_HOLD_WS_WITH_DELAY === '1';
let wsHoldUntil = 0;
const wsHeld = [];
let wsHoldTimer = null;
let wsHeldFrames = 0;
function flushWsHeld() {
  wsHoldTimer = null;
  while (wsHeld.length) {
    const { downstream, chunk } = wsHeld.shift();
    if (!downstream.destroyed) downstream.write(chunk);
  }
}
let expiredAnswers = 0;
let wsDroppedAt = 0;
let wsDownRefused = 0;
let fieldSeen = 0;
let wsRefused = 0;
if (!Number.isInteger(listenPort) || listenPort < 1024 || listenPort > 65535 ||
    !Number.isInteger(targetPort) || targetPort < 1024 || targetPort > 65535 ||
    !(permitted.has(delayField) || permittedMutations.has(delayField)) || listenPort === targetPort ||
    !(delayMs >= 0 && delayMs <= 120000) || !(Number.isInteger(delayCount) && delayCount >= 1) ||
    !(wsDropAtMs >= 0 && wsDropAtMs <= 3600000) || !(wsDownMs >= 0 && wsDownMs <= 600000)) {
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
    if (field === delayField) fieldSeen++;
    // the stream frames of the command go out while its HTTP answer is still upstream: hold them from the request on
    if (holdWsWithDelay && field === delayField && ((!delayMutation && !countSet) || delayed < delayCount)) {
      wsHoldUntil = Math.max(wsHoldUntil, Date.now() + delayMs + 250);
      process.stdout.write(JSON.stringify({ event: 'ws_hold', field, ms: delayMs + 250 }) + '\n');
    }
    if (expireAfterDrop && wsDroppedAt > 0) {
      expiredAnswers++;
      if (expiredAnswers === 1 || expiredAnswers % 10 === 0) {
        process.stdout.write(JSON.stringify({ event: 'expired_answer', n: expiredAnswers, field: field || mutationField(text) }) + '\n');
      }
      const reply = Buffer.from(JSON.stringify({ data: null, errors: [{ message: 'session expired (S10 proxy)',
                                                                         extensions: { code: 'UNAUTHENTICATED' } }] }));
      downstreamRes.writeHead(200, { 'content-type': 'application/json', 'content-length': reply.length });
      downstreamRes.end(reply);
      return;
    }
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
        if (field === delayField && ((!delayMutation && !countSet) || delayed < delayCount)) {
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
  if ((expireAfterDrop && wsDroppedAt > 0) || (wsDownMs > 0 && wsDroppedAt > 0 && Date.now() - wsDroppedAt < wsDownMs)) {
    wsDownRefused++;
    if (wsDownRefused === 1 || wsDownRefused % 10 === 0) {
      process.stdout.write(JSON.stringify({ event: 'ws_down_refused', n: wsDownRefused, sinceDropMs: Date.now() - wsDroppedAt }) + '\n');
    }
    downstream.destroy();
    return;
  }
  if (wsRefuse && fieldSeen <= delayCount) {
    wsRefused++;
    process.stdout.write(JSON.stringify({ event: 'ws_refused', n: wsRefused, fieldSeen }) + '\n');
    downstream.destroy();
    return;
  }
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
      wsDroppedAt = Date.now();
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
    if (!holdWsWithDelay) {
      upstream.pipe(downstream);
    } else {
      upstream.on('data', (chunk) => {
        const wait = wsHoldUntil - Date.now();
        if (wait > 0 || wsHeld.length) {
          wsHeld.push({ downstream, chunk });
          wsHeldFrames++;
          if (!wsHoldTimer) wsHoldTimer = setTimeout(flushWsHeld, Math.max(wait, 0));
        } else if (!downstream.destroyed) {
          downstream.write(chunk);
        }
      });
      upstream.on('end', () => downstream.end());
    }
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
  process.stdout.write(JSON.stringify({ event: 'summary', delayed, wsConnections, wsDropped, expiredAnswers, wsHeldFrames }) + '\n');
  server.close(() => process.exit(0));
}
process.on('SIGINT', finish);
process.on('SIGTERM', finish);
