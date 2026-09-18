import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import {clearCaptureArtifacts} from './cleanup.mjs';

const directory = fs.mkdtempSync(path.join(os.tmpdir(), 's01-cleanup-'));
const files = ['combat-defense.json', 'combat-p1-ws.json', 'timeout-after.json',
  'catalog-medusa-error.json', 'content-board.json', 'duplicate-error.json',
  'duel-start-p1.json', 'live-error.json', 'cleanup-error.json', 'accounts.json',
  'observations.json', 'tasks.json', 'combat-notes.md'];
const nested = path.join(directory, 'combat-nested.json');
try {
  for (const name of files) fs.writeFileSync(path.join(directory, name), 'fixture');
  fs.mkdirSync(nested);
  fs.writeFileSync(path.join(nested, 'combat-defense.json'), 'preserve');
  assert.deepEqual(clearCaptureArtifacts(directory, 'combat').sort(),
    ['combat-defense.json', 'combat-p1-ws.json', 'timeout-after.json']);
  assert.deepEqual(clearCaptureArtifacts(directory, 'combat'), []);
  assert(fs.existsSync(path.join(directory, 'catalog-medusa-error.json')));
  assert.deepEqual(clearCaptureArtifacts(directory, 'live').sort(),
    ['catalog-medusa-error.json', 'cleanup-error.json', 'content-board.json',
      'duel-start-p1.json', 'duplicate-error.json', 'live-error.json']);
  assert.deepEqual(clearCaptureArtifacts(directory, 'accounts'), ['accounts.json']);
  assert.throws(() => clearCaptureArtifacts(directory, '../outside'), /Unknown capture/);
  for (const name of ['observations.json', 'tasks.json', 'combat-notes.md'])
    assert.equal(fs.readFileSync(path.join(directory, name), 'utf8'), 'fixture');
  assert.equal(fs.readFileSync(path.join(nested, 'combat-defense.json'), 'utf8'), 'preserve');
  console.log('PASS: capture-owned JSON cleanup; optional artifacts removed; unrelated files and nested directory preserved; no live calls.');
} finally {
  fs.unlinkSync(path.join(nested, 'combat-defense.json'));
  fs.rmdirSync(nested);
  for (const name of files) {
    const file = path.join(directory, name);
    if (fs.existsSync(file)) fs.unlinkSync(file);
  }
  fs.rmdirSync(directory);
}
