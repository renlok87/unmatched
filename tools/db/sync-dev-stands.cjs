#!/usr/bin/env node
/**
 * One identical data set on every dev stand (user decision 2026-10-03,
 * docs/backend-api/db-divergence-2026-10-03.md section 9).
 *
 * The canonical DB is the main dev DB (unmatched-postgres, localhost:5433/unmatched, backend :3000).
 * Every stand DB (S08 :55433, S09 :55434, S10 :55435/unmatched_s10_live) is a byte-for-byte clone of it
 * (pg_dump -Fc | pg_restore), so ids, boards, effects and accounts are the same everywhere; the stand Redis
 * is flushed (it only holds runtime state of games that no longer exist after a clone).
 * Spec-owned test DBs (s04_test, unmatched_s10_tests) are never touched.
 *
 * Commands (run from the repo root):
 *   node tools/db/sync-dev-stands.cjs init-env            write .env.stands (stand passwords, from the running
 *                                                          containers; values are never printed)
 *   node tools/db/sync-dev-stands.cjs status              fingerprint main + every stand, report IDENTICAL/DIFF
 *   node tools/db/sync-dev-stands.cjs sync                dry run: what would be cloned
 *   node tools/db/sync-dev-stands.cjs sync --apply [--only s09[,s10]]
 * Stopped stand containers are started for the operation and stopped again afterwards.
 */
'use strict';

const { execFileSync } = require('child_process');
const fs = require('fs');
const os = require('os');
const path = require('path');

const ROOT = path.resolve(__dirname, '..', '..');
const MAIN = { id: 'main', pg: 'unmatched-postgres', db: 'unmatched', user: 'unmatched', redis: null };
const STANDS = [
  { id: 's08', pg: 'codex-s08-postgres', db: 'unmatched', user: 'unmatched', redis: 'codex-s08-redis', env: 'S08_PG_PASSWORD' },
  { id: 's09', pg: 'codex-s09-postgres', db: 'unmatched', user: 'unmatched', redis: 'codex-s09-redis', env: 'S09_PG_PASSWORD' },
  { id: 's10', pg: 'codex-s10-postgres', db: 'unmatched_s10_live', user: 'unmatched', redis: 'codex-s10-redis', env: 'S10_PG_PASSWORD' },
];
const FINGERPRINT_TABLES = ['Hero', 'Card', 'Board', 'User', 'UserSettings', 'UserStats', 'Game', 'GamePlayer', 'GameState'];

function docker(args, opts = {}) {
  return execFileSync('docker', args, { encoding: 'utf8', stdio: ['pipe', 'pipe', 'pipe'], ...opts }).trim();
}

function running(name) {
  try {
    return docker(['inspect', '-f', '{{.State.Running}}', name]) === 'true';
  } catch {
    return null; // container does not exist
  }
}

function waitReady(c) {
  for (let i = 0; i < 60; i++) {
    try {
      docker(['exec', c.pg, 'pg_isready', '-U', c.user, '-q']);
      return;
    } catch {
      execFileSync(process.execPath, ['-e', 'setTimeout(()=>{},1000)']);
    }
  }
  throw new Error(`${c.pg}: postgres not ready`);
}

function psql(c, sql, db = c.db) {
  return docker(['exec', c.pg, 'psql', '-U', c.user, '-d', db, '-At', '-v', 'ON_ERROR_STOP=1', '-c', sql]);
}

function fingerprint(c) {
  const exists = psql(c, `select count(*) from pg_database where datname = '${c.db}'`, 'postgres');
  if (exists !== '1') return { missing: true };
  const fp = {};
  for (const t of FINGERPRINT_TABLES) {
    fp[t] = psql(c, `select count(*) || ':' || coalesce(md5(string_agg(t::text, '|' order by t::text)), '-') from "${t}" t`);
  }
  fp.effectsV = psql(c, `select coalesce(string_agg(distinct e->>'parserVersion', ','), '-') from "Card" c, jsonb_array_elements(c.effects::jsonb) e`);
  fp.graphBoards = psql(c, `select count(*) from "Board" where features::jsonb ? 'topology'`);
  return fp;
}

/** Runs fn with the given containers started; containers that were stopped are stopped again. */
function withStarted(names, fn) {
  const started = [];
  for (const n of names.filter(Boolean)) {
    const r = running(n);
    if (r === null) throw new Error(`container ${n} does not exist - create it: docker compose -f docker-compose.stands.yml --env-file .env.stands --profile all up -d --no-start`);
    if (!r) {
      docker(['start', n]);
      started.push(n);
    }
  }
  try {
    return fn();
  } finally {
    for (const n of started) docker(['stop', n]);
  }
}

function status(stands) {
  const names = [MAIN.pg, ...stands.map((s) => s.pg)];
  return withStarted(names, () => {
    [MAIN, ...stands].forEach(waitReady);
    const ref = fingerprint(MAIN);
    const rows = [{ id: 'main', fp: ref, verdict: 'CANONICAL' }];
    for (const s of stands) {
      const fp = fingerprint(s);
      const same = !fp.missing && Object.keys(ref).every((k) => ref[k] === fp[k]);
      rows.push({ id: s.id, fp, verdict: fp.missing ? 'MISSING' : same ? 'IDENTICAL' : 'DIFF' });
    }
    for (const r of rows) {
      const short = r.fp.missing
        ? 'database missing'
        : FINGERPRINT_TABLES.map((t) => `${t}=${r.fp[t].split(':')[0]}`).join(' ') +
          ` effectsV=${r.fp.effectsV} graphBoards=${r.fp.graphBoards} md5(Hero)=${r.fp.Hero.split(':')[1].slice(0, 8)}`;
      console.log(`${r.id.padEnd(5)} ${r.verdict.padEnd(9)} ${short}`);
      if (r.verdict === 'DIFF') {
        const diff = Object.keys(ref).filter((k) => ref[k] !== r.fp[k]);
        console.log(`      differs in: ${diff.join(', ')}`);
      }
    }
    return rows.every((r) => r.verdict === 'CANONICAL' || r.verdict === 'IDENTICAL');
  });
}

function sync(stands, apply) {
  if (!apply) {
    for (const s of stands) console.log(`would clone main:${MAIN.db} -> ${s.pg}:${s.db}, flush ${s.redis}`);
    console.log('dry run - add --apply');
    return true;
  }
  const tmp = path.join(os.tmpdir(), `unmatched-canonical-${process.pid}.dump`);
  withStarted([MAIN.pg], () => {
    waitReady(MAIN);
    docker(['exec', MAIN.pg, 'pg_dump', '-U', MAIN.user, '-d', MAIN.db, '-Fc', '-f', '/tmp/canonical.dump']);
    docker(['cp', `${MAIN.pg}:/tmp/canonical.dump`, tmp]);
    docker(['exec', MAIN.pg, 'rm', '-f', '/tmp/canonical.dump']);
  });
  console.log(`canonical dump: ${fs.statSync(tmp).size} bytes`);
  for (const s of stands) {
    withStarted([s.pg, s.redis], () => {
      waitReady(s);
      psql(s, `select pg_terminate_backend(pid) from pg_stat_activity where datname = '${s.db}' and pid <> pg_backend_pid()`, 'postgres');
      psql(s, `drop database if exists "${s.db}"`, 'postgres');
      psql(s, `create database "${s.db}" owner "${s.user}"`, 'postgres');
      docker(['cp', tmp, `${s.pg}:/tmp/canonical.dump`]);
      docker(['exec', s.pg, 'pg_restore', '-U', s.user, '-d', s.db, '--no-owner', `--role=${s.user}`, '--exit-on-error', '/tmp/canonical.dump']);
      docker(['exec', s.pg, 'rm', '-f', '/tmp/canonical.dump']);
      if (s.redis) docker(['exec', s.redis, 'redis-cli', 'FLUSHALL']);
      console.log(`${s.id}: cloned into ${s.pg}:${s.db}${s.redis ? `, ${s.redis} flushed` : ''}`);
    });
  }
  fs.rmSync(tmp, { force: true });
  return status(stands);
}

function initEnv() {
  const file = path.join(ROOT, '.env.stands');
  const lines = ['# Dev stand passwords for docker-compose.stands.yml (ignored by git). Generated by tools/db/sync-dev-stands.cjs'];
  for (const s of STANDS) {
    let value = '';
    try {
      const env = JSON.parse(docker(['inspect', '-f', '{{json .Config.Env}}', s.pg]));
      value = (env.find((e) => e.startsWith('POSTGRES_PASSWORD=')) || '').slice('POSTGRES_PASSWORD='.length);
    } catch {
      /* container missing */
    }
    if (!value) throw new Error(`${s.pg}: no POSTGRES_PASSWORD found - set ${s.env} in .env.stands by hand`);
    lines.push(`${s.env}=${value}`);
  }
  fs.writeFileSync(file, lines.join('\n') + '\n', { encoding: 'utf8', mode: 0o600 });
  console.log(`wrote ${path.relative(ROOT, file)} (${STANDS.length} passwords, values not printed)`);
}

function main() {
  const [cmd = 'status', ...rest] = process.argv.slice(2);
  const onlyArg = rest.find((a) => a.startsWith('--only'));
  const only = onlyArg ? (onlyArg.includes('=') ? onlyArg.split('=')[1] : rest[rest.indexOf(onlyArg) + 1]).split(',') : null;
  const stands = only ? STANDS.filter((s) => only.includes(s.id)) : STANDS;
  let ok = true;
  if (cmd === 'init-env') initEnv();
  else if (cmd === 'status') ok = status(stands);
  else if (cmd === 'sync') ok = sync(stands, rest.includes('--apply'));
  else {
    console.error(`unknown command ${cmd}`);
    process.exit(2);
  }
  process.exit(ok ? 0 : 1);
}

main();
