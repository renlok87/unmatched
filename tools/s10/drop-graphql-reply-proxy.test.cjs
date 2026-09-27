const assert = require('node:assert/strict');
const { test } = require('node:test');
const { spawn } = require('node:child_process');
const http = require('node:http');
const net = require('node:net');
const path = require('node:path');

function listen(server) {
  return new Promise((resolve) => server.listen(0, '127.0.0.1', () => resolve(server.address().port)));
}
function availablePort() {
  const server = net.createServer();
  return listen(server).then((port) => new Promise((resolve) => server.close(() => resolve(port))));
}
function post(port, query) {
  return new Promise((resolve) => {
    const body = JSON.stringify({ query });
    const req = http.request({ hostname: '127.0.0.1', port, path: '/graphql', method: 'POST',
      headers: { 'Content-Type': 'application/json', 'Content-Length': Buffer.byteLength(body) } },
    (res) => {
      const chunks = [];
      res.on('data', (chunk) => chunks.push(chunk));
      res.on('end', () => resolve({ status: res.statusCode, body: Buffer.concat(chunks).toString('utf8') }));
      res.on('error', (error) => resolve({ error: error.code }));
      res.on('aborted', () => resolve({ error: 'ECONNRESET' }));
    });
    req.on('error', (error) => resolve({ error: error.code }));
    req.end(body);
  });
}

/** Sends a mutation, then aborts the client side before the upstream reply. */
function postThenAbort(port, query, abortAfterMs) {
  return new Promise((resolve) => {
    const body = JSON.stringify({ query });
    const req = http.request({ hostname: '127.0.0.1', port, path: '/graphql', method: 'POST',
      headers: { 'Content-Type': 'application/json', 'Content-Length': Buffer.byteLength(body) } },
    (res) => { res.resume(); res.on('end', () => resolve({ late: true })); });
    req.on('error', (error) => resolve({ error: error.code }));
    req.end(body);
    setTimeout(() => req.destroy(), abortAfterMs);
  });
}

test('drops exactly one committed mutation reply and tunnels WS upgrade', { timeout: 10000 }, async () => {
  let attacks = 0;
  const upgradedSockets = new Set();
  const upstream = http.createServer((req, res) => {
    const chunks = [];
    req.on('data', (chunk) => chunks.push(chunk));
    req.on('end', () => {
      const query = JSON.parse(Buffer.concat(chunks).toString('utf8')).query;
      res.setHeader('Content-Type', 'application/json');
      if (/\battack\(/.test(query)) {
        attacks++;
        res.end(JSON.stringify({ data: { attack: { state: '{}', sequenceNumber: attacks } } }));
      } else {
        res.end(JSON.stringify({ data: { __typename: 'Query' } }));
      }
    });
  });
  upstream.on('upgrade', (_req, socket) => {
    upgradedSockets.add(socket);
    socket.on('close', () => upgradedSockets.delete(socket));
    socket.write('HTTP/1.1 101 Switching Protocols\r\nConnection: Upgrade\r\nUpgrade: websocket\r\n\r\n');
    socket.on('error', () => {});
  });
  const targetPort = await listen(upstream);
  const proxyPort = await availablePort();
  const proxy = spawn(process.execPath, [path.join(__dirname, 'drop-graphql-reply-proxy.cjs')], {
    env: { ...process.env, S10_TARGET_PORT: String(targetPort),
      S10_LISTEN_PORT: String(proxyPort), S10_DROP_FIELD: 'attack' },
    windowsHide: true, stdio: ['ignore', 'pipe', 'pipe'],
  });
  try {
    await new Promise((resolve, reject) => {
      const timer = setTimeout(() => reject(new Error('proxy did not listen')), 3000);
      proxy.stdout.on('data', (chunk) => {
        if (chunk.toString('utf8').includes('"event":"listening"')) {
          clearTimeout(timer); resolve();
        }
      });
      proxy.on('exit', (code) => { clearTimeout(timer); reject(new Error(`proxy exited ${code}`)); });
    });
    const query = 'query { __typename }';
    assert.equal(JSON.parse((await post(proxyPort, query)).body).data.__typename, 'Query');
    const attack = 'mutation A($gameId: String!) { attack(input: { gameId: $gameId }) { state sequenceNumber } }';
    const first = await post(proxyPort, attack);
    assert.equal(first.error, 'ECONNRESET');
    assert.equal(attacks, 1, 'server committed before downstream response was lost');
    const second = await post(proxyPort, attack);
    assert.equal(second.status, 200);
    assert.equal(JSON.parse(second.body).data.attack.sequenceNumber, 2);
    assert.equal(attacks, 2);
    const upgrade = await new Promise((resolve, reject) => {
      const socket = net.connect(proxyPort, '127.0.0.1');
      socket.setTimeout(2000, () => { socket.destroy(); reject(new Error('upgrade timeout')); });
      socket.on('connect', () => socket.write('GET /graphql HTTP/1.1\r\nHost: 127.0.0.1\r\nConnection: Upgrade\r\nUpgrade: websocket\r\n\r\n'));
      socket.on('data', (data) => { resolve(data.toString('utf8')); socket.destroy(); });
      socket.on('error', reject);
    });
    assert.match(upgrade, /101 Switching Protocols/);
  } finally {
    proxy.kill();
    for (const socket of upgradedSockets) socket.destroy();
    await new Promise((resolve) => upstream.close(resolve));
  }
});

// S10 review P2(7): the drop event must reflect a CLIENT-OBSERVED reset. If
// the downstream socket died (client abort/timeout) before the committed
// upstream reply, no drop is claimed, the one-shot budget is preserved, and
// a later live request still gets its dropped reply.
test('no drop event when downstream already closed; later live request still drops', { timeout: 10000 }, async () => {
  let attacks = 0;
  const stdoutLines = [];
  const upgradedSockets = new Set();
  const upstream = http.createServer((req, res) => {
    const chunks = [];
    req.on('data', (chunk) => chunks.push(chunk));
    req.on('end', () => {
      const query = JSON.parse(Buffer.concat(chunks).toString('utf8')).query;
      res.setHeader('Content-Type', 'application/json');
      if (/\battack\(/.test(query)) {
        attacks++;
        // Slow enough for the client to abort first, and to let the proxy
        // observe the closed downstream socket before forwarding.
        setTimeout(() => {
          if (res.socket && !res.socket.destroyed) {
            res.end(JSON.stringify({ data: { attack: { state: '{}', sequenceNumber: attacks } } }));
          }
        }, 60);
      } else {
        res.end(JSON.stringify({ data: { __typename: 'Query' } }));
      }
    });
  });
  upstream.on('upgrade', (_req, socket) => {
    upgradedSockets.add(socket);
    socket.on('close', () => upgradedSockets.delete(socket));
    socket.write('HTTP/1.1 101 Switching Protocols\r\nConnection: Upgrade\r\nUpgrade: websocket\r\n\r\n');
    socket.on('error', () => {});
  });
  const targetPort = await listen(upstream);
  const proxyPort = await availablePort();
  const proxy = spawn(process.execPath, [path.join(__dirname, 'drop-graphql-reply-proxy.cjs')], {
    env: { ...process.env, S10_TARGET_PORT: String(targetPort),
      S10_LISTEN_PORT: String(proxyPort), S10_DROP_FIELD: 'attack' },
    windowsHide: true, stdio: ['ignore', 'pipe', 'pipe'],
  });
  try {
    await new Promise((resolve, reject) => {
      const timer = setTimeout(() => reject(new Error('proxy did not listen')), 3000);
      proxy.stdout.on('data', (chunk) => {
        stdoutLines.push(...chunk.toString('utf8').split('\n').filter(Boolean));
        if (chunk.toString('utf8').includes('"event":"listening"')) {
          clearTimeout(timer); resolve();
        }
      });
      proxy.on('exit', (code) => { clearTimeout(timer); reject(new Error(`proxy exited ${code}`)); });
    });
    const attack = 'mutation A($gameId: String!) { attack(input: { gameId: $gameId }) { state sequenceNumber } }';
    // Client aborts before the (delayed) committed reply reaches the proxy.
    await postThenAbort(proxyPort, attack, 15);
    await new Promise((resolve) => setTimeout(resolve, 150));
    const skipped = stdoutLines.some((line) => line.includes('"event":"reply_drop_skipped"'));
    const falselyDropped = stdoutLines.some((line) => line.includes('"event":"reply_dropped_after_commit"'));
    assert.equal(skipped, true, 'skip event emitted for the dead downstream socket');
    assert.equal(falselyDropped, false, 'no drop claimed for a close the client never observed');
    assert.equal(attacks, 1, 'upstream committed the aborted request exactly once');
    // The one-shot drop is still available for a request that stays live.
    const second = await post(proxyPort, attack);
    assert.equal(second.error, 'ECONNRESET');
    assert.equal(attacks, 2);
    await new Promise((resolve) => setTimeout(resolve, 150)); // let the stdout pipe flush
    assert.ok(stdoutLines.some((line) => line.includes('"event":"reply_dropped_after_commit"')),
      'live request still observes the dropped reply');
  } finally {
    proxy.kill();
    for (const socket of upgradedSockets) socket.destroy();
    await new Promise((resolve) => upstream.close(resolve));
  }
});
