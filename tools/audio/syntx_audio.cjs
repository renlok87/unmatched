// SYNTX audio generation from a ready task card (05-production-plan §2, 06-task-cards.csv).
//
// The MCP tool `generate-audio` puts `file_urls` at the top level of the body; the SYNTX web app (and the API for Suno
// "cover") wants them inside `settings` as [{type, url}]. This script sends the web-app body shape, waits for the
// result, downloads every audio object and records balances, so tools/audio/ledger.py can log the spend.
//
//   node tools/audio/syntx_audio.cjs run <job.json> <out dir>
//   node tools/audio/syntx_audio.cjs fetch <chat uuid> <title> <out dir> <file stem>   (recover a lost poll)
//   node tools/audio/syntx_audio.cjs balance
//
// job.json: {"ai_name": "suno"|"elevenlabs", "chat_uuid": "...", "chat_id": 123, "prompt": "...", "settings": {...},
//            "audio_url": "<uploaded file url, optional>", "names": ["file stem for object 1", ...]}
// Writes <out dir>/run.json (request id, task ids, clip ids, urls, balance before/after) and the downloaded files.
// Token: HKCU\Environment SYNTX_TOKEN (as the MCP launcher); never printed or written.
const { execFileSync } = require('child_process');
const fs = require('fs');
const path = require('path');

const API = 'https://api.syntx.ai';

function token() {
  if (process.env.SYNTX_TOKEN) return process.env.SYNTX_TOKEN;
  const out = execFileSync('reg', ['query', 'HKCU\\Environment', '/v', 'SYNTX_TOKEN'], { encoding: 'utf8', windowsHide: true });
  const m = out.match(/SYNTX_TOKEN\s+REG_\w+\s+(\S+)/);
  if (!m) throw new Error('SYNTX_TOKEN not found');
  return m[1];
}

async function call(method, url, body) {
  const res = await fetch(API + url, {
    method,
    headers: { Authorization: `Bearer ${token()}`, 'Content-Type': 'application/json', Accept: 'application/json' },
    body: body ? JSON.stringify(body) : undefined,
  });
  const text = await res.text();
  if (!res.ok) throw new Error(`${method} ${url}: ${res.status} ${text.slice(0, 500)}`);
  return text ? JSON.parse(text) : null;
}

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

async function run(jobPath, outDir) {
  const job = JSON.parse(fs.readFileSync(jobPath, 'utf8'));
  fs.mkdirSync(outDir, { recursive: true });
  const settings = { ...job.settings };
  if (job.audio_url) settings.file_urls = [{ type: 'audio', url: job.audio_url }];
  const before = (await call('GET', '/api/v1/user/balance')).balance;
  let sent = null;
  for (let attempt = 0; attempt < 40 && !sent; attempt++) {
    try {
      sent = await call('POST', `/api/v1/audio/generate?ai_name=${job.ai_name}`, {
        chat_uuid: job.chat_uuid, prompt: job.prompt, settings,
      });
    } catch (e) {
      if (!/: 429 /.test(String(e.message))) throw e;  // busy chat or the provider's active-generation limit
      await sleep(20000);
    }
  }
  if (!sent) throw new Error('still 429 after retries');
  const requestId = sent.id;
  const chatId = sent.chat_id;
  const t0 = Date.now();
  let reply = null;
  while (Date.now() - t0 < 15 * 60 * 1000) {
    await sleep(8000);
    const page = await call('GET', `/api/v1/chats/${job.chat_uuid}/messages?page_size=20`);
    const msgs = page.messages || page.items || page;
    // the reply of THIS request: same title (suno) or same voice + prompt (tts) - lanes may share a chat
    const mine = (m) => (m.message_object || []).some((o) => {
      const p = (o.metadata && o.metadata.payload) || {};
      const st = p.settings || {};
      if (settings.title) return st.title === settings.title;
      // SYNTX strips some punctuation (apostrophes) from the stored prompt: compare letters and digits only
      const norm = (v) => String(v || '').toLowerCase().replace(/[^a-z0-9]+/g, '');
      return st.voice_id === settings.voice_id && norm(p.prompt) === norm(job.prompt);
    });
    const after = msgs.filter((m) => m.id > requestId && m.author_id === -1 && mine(m));
    const done = after.find((m) => (m.message_object || []).length && m.message_object.every((o) => o.completed));
    if (done) { reply = done; break; }
    const failed = after.find((m) => (m.message_object || []).some((o) => o.metadata && o.metadata.provider_error));
    if (failed) { reply = failed; break; }
  }
  const afterBal = (await call('GET', '/api/v1/user/balance')).balance;
  const objects = reply ? reply.message_object.filter((o) => o.object_type === 'audio' && o.object_url) : [];
  const files = [];
  for (let i = 0; i < objects.length; i++) {
    const o = objects[i];
    const stem = (job.names && job.names[i]) || `out-${i + 1}`;
    const ext = path.extname(new URL(o.object_url).pathname) || '.mp3';
    const file = path.join(outDir, stem + ext);
    const res = await fetch(o.object_url);
    fs.writeFileSync(file, Buffer.from(await res.arrayBuffer()));
    const p = (o.metadata && o.metadata.payload) || {};
    files.push({ file: path.basename(file), url: o.object_url, clip_id: p.clip_id || null, task_id: p.task_id || null,
      provider_error: (o.metadata && o.metadata.provider_error) || null });
  }
  const result = {
    card: job.card || null, ai_name: job.ai_name, model_type: settings.model_type, chat_id: chatId,
    request_id: requestId, reply_id: reply ? reply.id : null, balance_before: before, balance_after: afterBal,
    delta: Math.round((afterBal - before) * 100) / 100, prompt: job.prompt, settings: { ...settings },
    files, finished: !!reply, seconds: Math.round((Date.now() - t0) / 1000),
  };
  fs.writeFileSync(path.join(outDir, 'run.json'), JSON.stringify(result, null, 1));
  console.log(JSON.stringify({ card: result.card, finished: result.finished, delta: result.delta,
    balance_after: afterBal, files: files.map((f) => f.file), errors: files.filter((f) => f.provider_error).length }));
}

async function fetchByTitle(chatUuid, title, outDir, stem) {
  // Recover finished objects of a request whose poll was lost: newest bot reply whose objects carry this title.
  fs.mkdirSync(outDir, { recursive: true });
  const page = await call('GET', `/api/v1/chats/${chatUuid}/messages?page_size=100`);
  const msgs = page.messages || page.items || page;
  const reply = msgs.filter((m) => m.author_id === -1 && (m.message_object || []).some((o) => o.metadata && (o.metadata.title === title || (o.metadata.payload && o.metadata.payload.settings && o.metadata.payload.settings.title === title))))
    .sort((a, b) => b.id - a.id)[0];
  if (!reply) { console.log(JSON.stringify({ title, found: false })); return; }
  const objs = reply.message_object.filter((o) => o.object_type === 'audio' && o.object_url);
  const files = [];
  for (let i = 0; i < objs.length; i++) {
    const o = objs[i];
    const file = path.join(outDir, `${stem}_v${i + 1}` + (path.extname(new URL(o.object_url).pathname) || '.mp3'));
    if (!o.completed) { files.push({ file: path.basename(file), completed: false }); continue; }
    const res = await fetch(o.object_url);
    fs.writeFileSync(file, Buffer.from(await res.arrayBuffer()));
    const p = (o.metadata && o.metadata.payload) || {};
    files.push({ file: path.basename(file), url: o.object_url, clip_id: p.clip_id || null, task_id: p.task_id || null, completed: true });
  }
  fs.writeFileSync(path.join(outDir, 'run.json'), JSON.stringify({ title, chat_uuid: chatUuid, reply_id: reply.id, files }, null, 1));
  console.log(JSON.stringify({ title, found: true, files: files.map((f) => `${f.file}:${f.completed}`) }));
}

async function balance() {
  console.log(JSON.stringify(await call('GET', '/api/v1/user/balance')).replace(/"user_id":"?\d+"?,?/, ''));
}

const [cmd, a, b, c, d] = process.argv.slice(2);
(cmd === 'run' ? run(a, b) : cmd === 'fetch' ? fetchByTitle(a, b, c, d) : balance()).catch((e) => { console.error(String(e.message || e)); process.exit(1); });
