// Repeatable S09 test bootstrap for the isolated stack (codex-s09-postgres
// :55434 / codex-s09-redis :6381). Idempotent seed chain ending in the board
// cells backfill, so every board carries playable zone-bearing cells
// (without it a zone-constrained mandatory choice - CHOOSE_SPACE stage 1 -
// has no legal pick and the game strands).
//
// Safety: refuses to run unless backend/.env (this worktree's own copy - the
// original checkout is never read) targets the S09 stack endpoints, so the
// original checkout's DB (55433/3100 stack) can never be written from here.
//
// Hero attack types (GD-058 interim 2026-09-30 §8 item 9, wave 7): seed-scraped
// used to skip heroes that already exist, and the engine reads a missing
// Hero.properties.attackType as 'melee' - Medusa (scraped attack=range) played
// as a melee fighter on this stack. The chain therefore runs
// prisma/backfill-attack-type.ts (idempotent) and gates on its --check.
//
// Usage (from the worktree root): node tools/s09/bootstrap-s09-stack.cjs [--dry-run] [--env-file <path>]
//   --dry-run        guards + the step plan; runs only the read-only
//                    `backfill-attack-type.ts --dry-run` (no seed writes).
//   --env-file PATH  read the S09 endpoints from another backend/.env (read
//                    only, e.g. the art worktree's); the same guards apply.
const { spawnSync } = require('child_process');
const fs = require('fs');
const path = require('path');

const argv = process.argv.slice(2);
const dryRun = argv.includes('--dry-run');
const envFileIdx = argv.indexOf('--env-file');
if (envFileIdx >= 0 && !argv[envFileIdx + 1]) {
  console.error('--env-file needs a path');
  process.exit(2);
}

const root = path.resolve(__dirname, '..', '..');
const envPath = envFileIdx >= 0 ? path.resolve(argv[envFileIdx + 1]) : path.join(root, 'backend', '.env');

const env = { ...process.env };
for (const line of fs.readFileSync(envPath, 'utf8').split(/\r?\n/)) {
  const m = line.match(/^([A-Za-z][A-Za-z0-9_]*)=(.*)$/);
  if (m && !(m[1] in env)) env[m[1]] = m[2];
}

// Endpoint guards. DATABASE_URL is parsed as a URL (never substring-matched:
// `localhost:55434` hiding in credentials/path/query must not pass) and only
// protocol/host/port are echoed, so credentials can never reach the logs.
function isLocalHost(hostname) {
  return String(hostname).toLowerCase() === '127.0.0.1' || String(hostname).toLowerCase() === 'localhost';
}

let dbUrl = null;
try {
  dbUrl = new URL(String(env.DATABASE_URL ?? ''));
} catch {
  dbUrl = null;
}
if (
  !dbUrl ||
  (dbUrl.protocol !== 'postgresql:' && dbUrl.protocol !== 'postgres:') ||
  !isLocalHost(dbUrl.hostname) ||
  dbUrl.port !== '55434'
) {
  console.error(
    'REFUSED: DATABASE_URL does not target the S09 isolated postgres.\n' +
      `  parsed endpoint: ${dbUrl ? `${dbUrl.protocol}//${dbUrl.hostname}:${dbUrl.port || '<no port>'}` : '<unparseable>'}\n` +
      '  required: postgresql: or postgres: on 127.0.0.1/localhost, port 55434.\n' +
      'Bootstrap only ever writes the isolated S09 stack - fix backend/.env first.',
  );
  process.exit(2);
}

const redisHost = String(env.REDIS_HOST ?? '127.0.0.1');
const redisPort = String(env.REDIS_PORT ?? '');
if (!isLocalHost(redisHost) || redisPort !== '6381') {
  console.error(
    'REFUSED: redis endpoint does not target the S09 isolated redis.\n' +
      `  parsed endpoint: ${redisHost}:${redisPort || '<no port>'}\n` +
      '  required: 127.0.0.1/localhost, port 6381.\n' +
      'Bootstrap only ever writes the isolated S09 stack - fix backend/.env first.',
  );
  process.exit(2);
}

const allSteps = [
  ['seed admin', ['prisma/seed-admin.ts']],
  ['seed maps/villains/minions', ['prisma/seed-all-scraped.ts']],
  ['seed heroes/cards', ['prisma/seed-scraped.ts']],
  ['backfill hero attackType (scraped)', ['prisma/backfill-attack-type.ts']],
  ['verify hero attackType (Medusa ranged, Merlin ranged, King Arthur melee, Harpies melee)',
    ['prisma/backfill-attack-type.ts', '--check']],
  ['backfill board cells (zones)', ['prisma/backfill-board-cells.ts']],
  ['demo users', [path.join('..', 'tools', 's09', 'ensure-demo-users.cjs')], true],
];
const steps = dryRun
  ? [['dry-run: hero attackType plan (read-only)', ['prisma/backfill-attack-type.ts', '--dry-run']]]
  : allSteps;
console.log(`endpoints OK: ${dbUrl.hostname}:${dbUrl.port} / redis ${redisHost}:${redisPort} (env ${envPath})`);
if (dryRun) {
  console.log('DRY RUN - planned steps (not executed):');
  for (const [label, args] of allSteps) console.log(`  - ${label}: ${args.join(' ')}`);
}

let failed = false;
for (const [label, args, isNodeScript] of steps) {
  console.log(`\n=== ${label} ===`);
  const command = isNodeScript ? ['node', ...args] : ['node', '-r', 'ts-node/register/transpile-only', ...args];
  const r = spawnSync(command[0], command.slice(1), {
    cwd: path.join(root, 'backend'),
    env,
    stdio: 'inherit',
    windowsHide: true,
  });
  if (r.status !== 0) {
    console.error(`step FAILED: ${label} (exit ${r.status})`);
    failed = true;
    break;
  }
}

if (!failed && dryRun) {
  console.log('\nDry run OK: nothing was written.');
} else if (!failed) {
  // Count boards whose cells is not a nonempty JSON array, or that lack any
  // cell with a nonempty zones array. Every jsonb_array_* call sits in its own
  // nested CASE arm (never in an OR that a planner could reorder), so the
  // query itself cannot error on non-array shapes.
  const zoneCheckSql = [
    'SELECT count(*) FROM "Board" b WHERE CASE',
    'WHEN b.cells IS NULL THEN true',
    "WHEN jsonb_typeof(b.cells::jsonb) IS DISTINCT FROM 'array' THEN true",
    'WHEN jsonb_array_length(b.cells::jsonb) = 0 THEN true',
    'ELSE NOT EXISTS (',
    'SELECT 1 FROM jsonb_array_elements(b.cells::jsonb) AS cell',
    "WHERE CASE WHEN jsonb_typeof(cell->'zones') = 'array' THEN jsonb_array_length(cell->'zones') > 0 ELSE false END",
    ') END;',
  ].join(' ');
  const check = spawnSync(
    'docker',
    ['exec', 'codex-s09-postgres', 'psql', '-U', 'unmatched', '-d', 'unmatched', '-t', '-c', zoneCheckSql],
    { stdio: ['ignore', 'pipe', 'inherit'], windowsHide: true, encoding: 'utf8' },
  );
  const bad = parseInt((check.stdout || '').trim(), 10);
  if (check.status !== 0 || Number.isNaN(bad) || bad > 0) {
    console.error(
      `VERIFY FAILED: ${Number.isNaN(bad) ? 'psql unreadable' : `${bad} board(s) are not zone-bearing (empty/non-array cells, or no cell with a nonempty zones array)`}`,
    );
    process.exit(3);
  }
  console.log('\nBootstrap OK: every board carries zone-bearing cells.');
}
process.exit(failed ? 1 : 0);
