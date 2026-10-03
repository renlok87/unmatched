// HISTORICAL VALIDATOR (2026-10-04): it checks the S08 phase-2 evidence recorded on the old backend-default
// 20x20 grey grid (the 'BOARD 20x20' trace gate and the grid verdicts of the retired check-board-shot.ps1).
// New runs are NOT gated by it: since 2026-10-04 (real boards only, docs/game-design/decisions/
// 2026-10-04-real-boards-only.md, ND-4/ND-6) tools/s08/run-phase2-demo.ps1 runs on an original map
// (default Marmoreal) and gates its own map-board trace lines and art-check shots; a 20x20 run no longer
// counts as evidence. Kept so the historical S08 runs stay verifiable.
//
// Strict validator for the latest published S08 phase-2 evidence run.
// Usage:
//   node validate-evidence.cjs <evidenceRoot>   validate <root>/latest.json target
//   node validate-evidence.cjs --selftest      negative + positive fixture checks
//
// The published run must contain EXACTLY the six expected artifacts (names
// pinned below, safe basenames only), whose bytes match the manifest sizes +
// SHA-256, the two PNGs must carry real PNG signatures at 1920x1080, both
// grid verdicts must parse with pass=true and grooves/team colors above the
// checker thresholds (12 vertical / 10 horizontal / 150+150 team px / 35%
// non-black), and both traces must show the expected host/joiner-specific
// markers with seq convergence on the maneuver (max applied seq equal and
// >= 3 on both clients).
const fs = require('fs');
const path = require('path');
const crypto = require('crypto');
const os = require('os');

const EXPECTED_FILES = [
  'phase2-client-host.trace.log',
  'phase2-client-joiner.trace.log',
  'phase2-board-host-1920x1080.png',
  'phase2-board-host-1920x1080-grid.json',
  'phase2-board-joiner-1920x1080.png',
  'phase2-board-joiner-1920x1080-grid.json',
];
const GRID_MIN = {
  verticalGrooves: 12,
  horizontalGrooves: 10,
  bluePx: 150,
  redPx: 150,
  nonBlackPct: 35.0,
};
const PNG_SIG = [0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a];
const RUN_DIR_PATTERN = /^run-\d{8}-\d{6}$/;

function isSafeBasename(name) {
  return (
    typeof name === 'string' &&
    name.length > 0 &&
    path.basename(name) === name &&
    !name.includes('..') &&
    !name.includes('/') &&
    !name.includes('\\') &&
    !/[a-zA-Z]:/.test(name)
  );
}

function hasUtf8Bom(buf) {
  return buf.length >= 3 && buf[0] === 0xef && buf[1] === 0xbb && buf[2] === 0xbf;
}

/** Validate one published run directory (latest.json target). Returns string[] of problems. */
function validateRunDir(runDir) {
  const problems = [];
  const ok = (cond, msg) => {
    if (!cond) problems.push(msg);
  };

  const manPath = path.join(runDir, 'manifest.json');
  ok(fs.existsSync(manPath), 'manifest.json missing');
  if (!fs.existsSync(manPath)) return problems;
  const manBytes = fs.readFileSync(manPath);
  ok(!hasUtf8Bom(manBytes), 'manifest.json has UTF-8 BOM');
  let manifest;
  try {
    manifest = JSON.parse(manBytes.toString('utf8'));
  } catch (e) {
    return [`manifest.json is not valid JSON: ${e.message}`];
  }
  ok(manifest.verdict && manifest.verdict.includes('SIX FIGHTERS'),
     'manifest verdict missing six fighters');

  // Exactly the six expected artifacts, safe basenames, no extras/duplicates.
  ok(Array.isArray(manifest.files), 'manifest.files must be an array');
  const files = Array.isArray(manifest.files) ? manifest.files : [];
  ok(files.length === EXPECTED_FILES.length,
     `manifest.files must list exactly ${EXPECTED_FILES.length} entries, got ${files.length}`);
  const names = files.map((f) => (f && f.name) || '');
  for (const expected of EXPECTED_FILES) {
    ok(names.filter((n) => n === expected).length === 1, `manifest must list ${expected} exactly once`);
  }
  for (const name of names) {
    ok(isSafeBasename(name), `unsafe artifact name in manifest: ${JSON.stringify(name)}`);
  }

  const byName = new Map(files.filter((f) => f && isSafeBasename(f.name)).map((f) => [f.name, f]));

  for (const f of files) {
    if (!f || !isSafeBasename(f.name)) continue;
    const p = path.join(runDir, f.name);
    if (!fs.existsSync(p)) {
      problems.push(`file missing: ${f.name}`);
      continue;
    }
    const buf = fs.readFileSync(p);
    ok(Number.isInteger(f.bytes) && f.bytes > 0, `${f.name}: manifest bytes must be a positive integer`);
    ok(buf.length === f.bytes, `${f.name} size ${buf.length} != manifest ${f.bytes}`);
    ok(typeof f.sha256 === 'string' && /^[0-9a-f]{64}$/.test(f.sha256),
       `${f.name}: manifest sha256 must be 64 lowercase hex chars`);
    if (typeof f.sha256 === 'string' && /^[0-9a-f]{64}$/.test(f.sha256)) {
      const sha = crypto.createHash('sha256').update(buf).digest('hex');
      ok(sha === f.sha256, `${f.name} sha256 mismatch`);
    }
  }

  // --- PNG artifacts: real signature, IHDR dimensions 1920x1080, plausible size.
  for (const name of EXPECTED_FILES.filter((n) => n.endsWith('.png'))) {
    const f = byName.get(name);
    if (!f) continue; // already reported via the manifest checks above
    const p = path.join(runDir, name);
    if (!fs.existsSync(p)) continue;
    const buf = fs.readFileSync(p);
    ok(PNG_SIG.every((v, i) => buf[i] === v), `${name}: not a PNG (bad signature)`);
    ok(buf.length >= 10 * 1024, `${name}: implausibly small PNG (${buf.length} bytes)`);
    if (buf.length >= 24 && PNG_SIG.every((v, i) => buf[i] === v)) {
      ok(buf.readUInt32BE(12) === 0x49484452, `${name}: first chunk is not IHDR`);
      const w = buf.readUInt32BE(16);
      const h = buf.readUInt32BE(20);
      ok(w === 1920 && h === 1080, `${name}: IHDR ${w}x${h} != 1920x1080`);
    }
  }

  // --- Grid verdicts: parsed JSON, pass=true, grooves/colors above thresholds.
  for (const name of EXPECTED_FILES.filter((n) => n.endsWith('-grid.json'))) {
    const f = byName.get(name);
    if (!f) continue;
    const p = path.join(runDir, name);
    if (!fs.existsSync(p)) continue;
    const buf = fs.readFileSync(p);
    ok(!hasUtf8Bom(buf), `${name}: UTF-8 BOM`);
    let grid;
    try {
      grid = JSON.parse(buf.toString('utf8'));
    } catch (e) {
      problems.push(`${name}: not valid JSON (${e.message})`);
      continue;
    }
    ok(grid.pass === true, `${name}: pass is ${JSON.stringify(grid.pass)}, not true`);
    for (const key of ['verticalGrooves', 'horizontalGrooves', 'bluePx', 'redPx']) {
      ok(Number.isFinite(grid[key]), `${name}: ${key} missing/not numeric`);
      if (Number.isFinite(grid[key])) {
        ok(grid[key] >= GRID_MIN[key], `${name}: ${key}=${grid[key]} < ${GRID_MIN[key]}`);
      }
    }
    ok(Number.isFinite(grid.nonBlackPct) && grid.nonBlackPct >= GRID_MIN.nonBlackPct,
       `${name}: nonBlackPct=${grid.nonBlackPct} < ${GRID_MIN.nonBlackPct}`);
    ok(Number.isFinite(grid.vThreshold) && grid.vThreshold > 0, `${name}: vThreshold not positive`);
    ok(Number.isFinite(grid.hThreshold) && grid.hThreshold > 0, `${name}: hThreshold not positive`);
  }

  // --- Traces: shared markers + client-specific markers + seq convergence.
  const traceText = {};
  for (const [name, who] of [
    ['phase2-client-host.trace.log', 'host'],
    ['phase2-client-joiner.trace.log', 'joiner'],
  ]) {
    const f = byName.get(name);
    if (!f) continue;
    const p = path.join(runDir, name);
    if (!fs.existsSync(p)) continue;
    const buf = fs.readFileSync(p);
    ok(!hasUtf8Bom(buf), `${name}: UTF-8 BOM`);
    ok(buf.indexOf(0x00) === -1, `${name}: contains NUL bytes (not UTF-8 text)`);
    const text = buf.toString('utf8');
    traceText[who] = text;
    for (const marker of ['SNAPSHOT applied', 'BOARD 20x20', 'FIGHTERS synced n=6']) {
      ok(text.includes(marker), `${name}: no ${marker}`);
    }
    const projected = (text.match(/SHOT fighter .* projected=1 alive=1/g) || []).length;
    ok(projected === 6, `${name}: projected fighters ${projected} != 6`);
    ok(!/[?&]code=[A-Z0-9-]{4,12}\b/.test(text) &&
       !/\bcode=[A-Z0-9-]{4,12}\b/.test(text.replace(/code=<redacted>/g, '')),
       `${name}: un-redacted room code present`);
  }
  if (traceText.host) {
    for (const marker of ['createGame -> room=', 'MANEUVER begin seq=', 'MANEUVER done', 'CUE move']) {
      ok(traceText.host.includes(marker), `host trace missing ${marker}`);
    }
    ok(!traceText.host.includes('joinGame -> room='), 'host trace contains joinGame (role mix-up)');
  }
  if (traceText.joiner) {
    for (const marker of [
      'CODE resolved', 'joinGame -> room=', 'SUBSCRIBED gameStateUpdated',
      'WS DROPPED', 'WS closed', 'WS reconnect attempt', 'WS reconnected', 'CUE move',
    ]) {
      ok(traceText.joiner.includes(marker), `joiner trace missing ${marker}`);
    }
    ok(!traceText.joiner.includes('createGame -> room='), 'joiner trace contains createGame (role mix-up)');
  }
  if (traceText.host && traceText.joiner) {
    const maxSeq = (text) => {
      const seqs = [...text.matchAll(/SNAPSHOT applied seq=(\d+)/g)].map((m) => Number(m[1]));
      return seqs.length ? Math.max(...seqs) : null;
    };
    const hostSeq = maxSeq(traceText.host);
    const joinerSeq = maxSeq(traceText.joiner);
    ok(hostSeq !== null && hostSeq >= 3, `host trace max applied seq ${hostSeq} < 3 (maneuver not visible)`);
    ok(joinerSeq !== null && joinerSeq >= 3, `joiner trace max applied seq ${joinerSeq} < 3 (maneuver not visible)`);
    ok(hostSeq === joinerSeq, `seq divergence: host ${hostSeq} != joiner ${joinerSeq}`);
  }
  return problems;
}

/** Validate an evidence root through its latest.json pointer. */
function validateRoot(root) {
  const problems = [];
  const ok = (cond, msg) => {
    if (!cond) problems.push(msg);
  };
  ok(fs.existsSync(root), `evidence root missing: ${root}`);
  if (!fs.existsSync(root)) return problems;

  const ptrPath = path.join(root, 'latest.json');
  ok(fs.existsSync(ptrPath), 'latest.json missing');
  if (!fs.existsSync(ptrPath)) return problems;
  const ptrBytes = fs.readFileSync(ptrPath);
  ok(!hasUtf8Bom(ptrBytes), 'latest.json has UTF-8 BOM');
  let ptr;
  try {
    ptr = JSON.parse(ptrBytes.toString('utf8'));
  } catch (e) {
    return [`latest.json is not valid JSON: ${e.message}`];
  }
  ok(typeof ptr.current === 'string' && RUN_DIR_PATTERN.test(ptr.current),
     `latest.json current must match ${RUN_DIR_PATTERN}, got ${JSON.stringify(ptr.current)}`);
  if (typeof ptr.current !== 'string' || !RUN_DIR_PATTERN.test(ptr.current)) return problems;

  const runDir = path.join(root, ptr.current);
  ok(fs.existsSync(runDir), `run dir ${ptr.current} missing`);
  if (!fs.existsSync(runDir)) return problems;
  return problems.concat(validateRunDir(runDir));
}

// ---------------------------------------------------------------------------
// Selftest: deterministic synthetic fixtures prove the validator REJECTS each
// tampering class and ACCEPTS the pristine layout (no dependency on the
// currently published bytes).
// ---------------------------------------------------------------------------
function synthPng() {
  const buf = Buffer.alloc(64 * 1024, 0x5a);
  Buffer.from(PNG_SIG).copy(buf, 0); // 0..7 signature
  buf.writeUInt32BE(13, 8);          // 8..11 IHDR chunk length
  buf.write('IHDR', 12, 'ascii');    // 12..15 chunk type
  buf.writeUInt32BE(1920, 16);       // 16..19 width
  buf.writeUInt32BE(1080, 20);       // 20..23 height
  return buf;
}

function synthGrid(overrides) {
  return Buffer.from(JSON.stringify(Object.assign({
    path: 'C:\\synth\\shot.png', size: '1920x1080', boardBox: 'x:391-1528 y:135-1036',
    verticalGrooves: 13, horizontalGrooves: 19, vThreshold: 10, hThreshold: 10,
    bluePx: 500, redPx: 400, nonBlackPct: 48.9, pass: true, reasons: [],
  }, overrides)));
}

function synthTrace(who) {
  const lines = [
    '2026.09.25-19.26.07 --- S08 trace open ---',
    `LOGIN ok user=${who === 'host' ? 'TestPlayer1' : 'TestPlayer2'}`,
  ];
  if (who === 'host') {
    lines.push('createGame -> room=c.synthetic0000 code=<redacted> status=LOBBY');
    lines.push('startGame -> room=c.synthetic0000 code=<redacted> status=IN_PROGRESS');
  } else {
    lines.push('CODE resolved <redacted> -> c.synthetic0000');
    lines.push('joinGame -> room=c.synthetic0000 code=<redacted> status=LOBBY');
    lines.push('SUBSCRIBED gameStateUpdated since=1');
    lines.push('WS DROPPED (test-initiated transport loss)');
    lines.push('WS closed (test drop) - reconnect in 1s');
    lines.push('WS reconnect attempt');
    lines.push('WS reconnected - refetching gameState');
  }
  lines.push('SNAPSHOT applied seq=1 phase=ACTION_MANEUVER');
  lines.push('BOARD 20x20 cells');
  lines.push('FIGHTERS synced n=6 alive=6');
  lines.push('MANEUVER begin seq=2 (apply) pending=maneuver:1:1');
  lines.push('SNAPSHOT applied seq=3 phase=ACTION_MANEUVER');
  lines.push('CUE move f-0-hero (2,2)->(3,2) seq=3');
  lines.push('MANEUVER done seq=3 (apply) fighters=6');
  for (const f of ['f-0-hero', 'f-0-sk0', 'f-0-sk1', 'f-0-sk2', 'f-1-hero', 'f-1-sk0']) {
    lines.push(`SHOT fighter ${f} pos=(1,1) world=(0,0,0) screen=(100,100) projected=1 alive=1`);
  }
  lines.push('--- S08 trace close ---');
  return Buffer.from(lines.join('\n'));
}

function sha256(buf) {
  return crypto.createHash('sha256').update(buf).digest('hex');
}

function buildSyntheticRun(root, mutate, postWrite) {
  const stamp = '20990101-000000';
  const runDir = path.join(root, `run-${stamp}`);
  fs.mkdirSync(runDir, { recursive: true });
  const artifacts = {
    'phase2-client-host.trace.log': synthTrace('host'),
    'phase2-client-joiner.trace.log': synthTrace('joiner'),
    'phase2-board-host-1920x1080.png': synthPng(),
    'phase2-board-host-1920x1080-grid.json': synthGrid(),
    'phase2-board-joiner-1920x1080.png': synthPng(),
    'phase2-board-joiner-1920x1080-grid.json': synthGrid(),
  };
  const context = { runDir, stamp, artifacts };
  if (mutate) mutate(context); // content mutations: run BEFORE manifest hashing
  const files = EXPECTED_FILES
    .filter((name) => artifacts[name])
    .map((name) => ({ name, bytes: artifacts[name].length, sha256: sha256(artifacts[name]) }));
  const manifest = {
    stamp,
    verdict: 'TRACES OK + SHOTS PRESENT + GRID VERIFIED + SIX FIGHTERS (trace: n=6, all projected in frame)',
    files,
  };
  fs.writeFileSync(path.join(runDir, 'manifest.json'), JSON.stringify(manifest, null, 2));
  for (const name of Object.keys(artifacts)) {
    fs.writeFileSync(path.join(runDir, name), artifacts[name]);
  }
  fs.writeFileSync(path.join(root, 'latest.json'), JSON.stringify({ current: `run-${stamp}`, stamp }));
  if (postWrite) postWrite(context); // disk-level mutations: run AFTER publishing
  return context;
}

function selftest() {
  const cases = [];
  const run = (label, mutate, expectPattern, postWrite) => {
    const root = fs.mkdtempSync(path.join(os.tmpdir(), 's08-validate-'));
    try {
      buildSyntheticRun(root, mutate, postWrite);
      const problems = validateRoot(root);
      const hit = expectPattern ? problems.some((p) => expectPattern.test(p)) : problems.length === 0;
      cases.push({ label, ok: hit, problems });
    } catch (e) {
      cases.push({ label, ok: false, problems: [`selftest threw: ${e.message}`] });
    } finally {
      fs.rmSync(root, { recursive: true, force: true });
    }
  };

  run('positive: pristine synthetic run passes', null, null);

  run('missing file: manifest lists the PNG but the file is gone',
      null,
      /file missing: phase2-board-host-1920x1080\.png/,
      (c) => { fs.rmSync(path.join(c.runDir, 'phase2-board-host-1920x1080.png'), { force: true }); });
  run('bad image: corrupted PNG signature is rejected',
      (c) => { c.artifacts['phase2-board-joiner-1920x1080.png'][0] = 0x00; },
      /not a PNG/);
  run('bad image: wrong IHDR dimensions are rejected',
      (c) => { c.artifacts['phase2-board-host-1920x1080.png'].writeUInt32BE(800, 16); },
      /IHDR 800x1080 != 1920x1080/);
  run('failing grid: pass=false with low grooves is rejected',
      (c) => {
        c.artifacts['phase2-board-host-1920x1080-grid.json'] =
          synthGrid({ pass: false, verticalGrooves: 3, horizontalGrooves: 2, bluePx: 5, redPx: 4 });
      },
      /pass is false|verticalGrooves=3|bluePx=5/);
  run('missing joiner: manifest without the joiner trace is rejected',
      (c) => { delete c.artifacts['phase2-client-joiner.trace.log']; },
      /manifest must list phase2-client-joiner\.trace\.log exactly once/);
  run('path traversal: ../evil.png entry is rejected',
      null,
      /unsafe artifact name/,
      (c) => {
        const m = JSON.parse(fs.readFileSync(path.join(c.runDir, 'manifest.json'), 'utf8'));
        m.files.push({ name: '../evil.png', bytes: 4, sha256: sha256(Buffer.from('evil')) });
        fs.writeFileSync(path.join(c.runDir, 'manifest.json'), JSON.stringify(m, null, 2));
      });
  run('empty manifest files array is rejected',
      null,
      /must list exactly 6 entries, got 0/,
      (c) => {
        const m = JSON.parse(fs.readFileSync(path.join(c.runDir, 'manifest.json'), 'utf8'));
        m.files = [];
        fs.writeFileSync(path.join(c.runDir, 'manifest.json'), JSON.stringify(m, null, 2));
      });
  run('seq divergence: joiner stuck at seq=1 is rejected',
      (c) => {
        const t = c.artifacts['phase2-client-joiner.trace.log'].toString('utf8');
        c.artifacts['phase2-client-joiner.trace.log'] =
          Buffer.from(t.replace(/seq=2/g, 'seq=1').replace(/seq=3/g, 'seq=1'));
      },
      /seq divergence|joiner trace max applied seq 1 < 3/);
  run('un-redacted room code in a trace is rejected',
      (c) => {
        const t = c.artifacts['phase2-client-host.trace.log'].toString('utf8');
        c.artifacts['phase2-client-host.trace.log'] =
          Buffer.from(t.replace('code=<redacted>', 'code=AB12CD'));
      },
      /un-redacted room code/);

  let failed = 0;
  for (const c of cases) {
    console.log(`${c.ok ? 'PASS' : 'FAIL'}  ${c.label}`);
    if (!c.ok) {
      failed++;
      console.log(`      expected-problems missing; got: ${JSON.stringify(c.problems)}`);
    }
  }
  if (failed) {
    console.log(`SELFTEST FAILED: ${failed}/${cases.length} cases`);
    process.exit(1);
  }
  console.log(`SELFTEST OK: ${cases.length}/${cases.length} cases`);
}

const arg = process.argv[2];
if (arg === '--selftest') {
  selftest();
} else if (!arg) {
  console.error('Usage: node validate-evidence.cjs <evidenceRoot> | --selftest');
  process.exit(2);
} else {
  const problems = validateRoot(arg);
  if (problems.length) {
    console.log('PROBLEMS:');
    problems.forEach((p) => console.log(' - ' + p));
    process.exit(1);
  }
  const ptr = JSON.parse(fs.readFileSync(path.join(arg, 'latest.json'), 'utf8'));
  console.log(`OK: ${ptr.current} — exactly six artifacts, hashes/sizes verified, PNG 1920x1080, ` +
    `grids pass=true above thresholds, host/joiner markers + seq convergence verified`);
}
