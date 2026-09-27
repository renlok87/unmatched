// S10 transport fault injector. Forwards GraphQL HTTP + graphql-transport-ws
// to a local backend. After one successful named mutation has committed and
// replied upstream, closes only that downstream HTTP response. The client
// must query authoritative state, never resend the mutation blindly.
//
// S10_LISTEN_PORT=3122 S10_TARGET_PORT=3120 S10_DROP_FIELD=attack node ...
// Local-only; no request bodies, tokens, room codes, or card ids are logged.
const http = require('node:http');
const net = require('node:net');

const listenPort = Number(process.env.S10_LISTEN_PORT || 3122);
const targetPort = Number(process.env.S10_TARGET_PORT || 3120);
const dropField = process.env.S10_DROP_FIELD || '';
const permitted = new Set([
  'attack', 'playDefense', 'beginManeuver', 'maneuver',
  'resolvePendingEffect', 'declinePendingEffect',
]);
if (!Number.isInteger(listenPort) || listenPort < 1024 || listenPort > 65535 ||
    !Number.isInteger(targetPort) || targetPort < 1024 || targetPort > 65535 ||
    !permitted.has(dropField) || listenPort === targetPort) {
  throw new Error('Set distinct local S10_LISTEN_PORT/S10_TARGET_PORT and permitted S10_DROP_FIELD');
}

let dropped = false;
const forwarded = Object.create(null);
let wsConnections = 0;

function operationField(body) {
  try {
    const query = JSON.parse(body).query;
    if (typeof query !== 'string' || !/\bmutation\b/.test(query)) return '';
    // Query fields in this project are the top-level selection immediately
    // after `mutation Name(...) {`; variables can contain nested braces only
    // in the JSON body, outside this query string.
    const match = query.match(/\bmutation\b[^{}]*\{\s*([A-Za-z][A-Za-z0-9_]*)\s*\(/);
    return match ? match[1] : '';
  } catch { return ''; }
}

const server = http.createServer((downstreamReq, downstreamRes) => {
  // A drop is only real when the CLIENT could observe it: if the downstream
  // side is already gone (client abort/timeout), destroying the response
  // proves nothing about the client. The event is skipped and the one-shot
  // drop budget is preserved for a request that is still watching. Listen on
  // the per-request RESPONSE, never on the shared keep-alive socket: a
  // socket-level 'close' listener per request accumulated past Node's
  // 10-listener cap during long keep-alive duels (MaxListenersExceededWarning).
  // The response 'close' also fires after a fully-delivered reply, which is
  // harmless: downstreamGone is only consulted below BEFORE the reply is
  // written (no yield between the check and the destroy).
  let downstreamGone = false;
  downstreamRes.on('close', () => { downstreamGone = true; });
  downstreamRes.on('error', () => { downstreamGone = true; });
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
    const field = operationField(body.toString('utf8'));
    if (field) forwarded[field] = (forwarded[field] || 0) + 1;
    const upstreamReq = http.request({
      hostname: '127.0.0.1', port: targetPort,
      method: downstreamReq.method, path: downstreamReq.url,
      headers: { ...downstreamReq.headers, host: `127.0.0.1:${targetPort}` },
    }, (upstreamRes) => {
      const responseChunks = [];
      upstreamRes.on('data', (chunk) => responseChunks.push(chunk));
      upstreamRes.on('end', () => {
        const reply = Buffer.concat(responseChunks);
        let committed = false;
        if (field === dropField && upstreamRes.statusCode === 200) {
          try {
            const parsed = JSON.parse(reply.toString('utf8'));
            const result = parsed.data?.[field];
            committed = !parsed.errors?.length && typeof result?.state === 'string' &&
              Number.isInteger(result.sequenceNumber);
          } catch { /* Forward unreadable replies; never inject an unproven commit. */ }
        }
        if (!dropped && committed) {
          const socketAlive = !downstreamGone && downstreamRes.socket &&
            !downstreamRes.socket.destroyed && downstreamRes.writable;
          if (!socketAlive) {
            process.stdout.write(JSON.stringify({
              event: 'reply_drop_skipped', reason: 'downstream already closed', field,
            }) + '\n');
            return;
          }
          dropped = true;
          // The backend has finished the mutation. Close this one client reply
          // at the transport boundary; never send a fake GraphQL rejection.
          downstreamRes.destroy();
          process.stdout.write(JSON.stringify({ event: 'reply_dropped_after_commit', field,
            forwarded: forwarded[field] }) + '\n');
          return;
        }
        downstreamRes.writeHead(upstreamRes.statusCode || 502, upstreamRes.headers);
        downstreamRes.end(reply);
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
  process.stdout.write(JSON.stringify({ event: 'listening', port: listenPort,
    targetPort, dropField }) + '\n');
});

function finish() {
  process.stdout.write(JSON.stringify({ event: 'summary', dropped,
    forwarded, wsConnections }) + '\n');
  server.close(() => process.exit(0));
}
process.on('SIGINT', finish);
process.on('SIGTERM', finish);
