import fs from 'node:fs';
import http from 'node:http';
import type { AddressInfo } from 'node:net';
import os from 'node:os';
import path from 'node:path';
import { afterAll, beforeAll, describe, expect, it } from 'vitest';
import { isAllowedRelPath, mimeFor, normalizeRelPath, parseRange, resolveSafePath } from '../path-guard';
import zlib from 'node:zlib';
import { PLACEHOLDER_PNG, createArtHubMiddleware, textureCandidates } from '../vite-plugin';
import { HERO, makeFixtureRepo, type FixtureRepo } from './fixture-repo';

describe('normalizeRelPath / isAllowedRelPath', () => {
  it.each([
    ['', null],
    ['../package.json', null],
    ['art/../docs/secret.txt', null],
    ['art\\..\\docs\\secret.txt', null],
    ['/etc/passwd', null],
    ['C:/Windows/win.ini', null],
    ['c:\\Windows\\win.ini', null],
    ['//server/share/x', null],
    ['\\\\server\\share\\x', null],
    ['art/x.png:stream', null],
    ['art/.hidden.txt', null],
    ['art/a\0b', null],
    ['art//x/./y.png', 'art/x/y.png'],
    ['art\\x\\y.png', 'art/x/y.png'],
  ])('normalizes %j → %j', (input, expected) => {
    expect(normalizeRelPath(input)).toBe(expected);
  });

  it.each([
    ['art/animation-refs/A/B/x.mp4', true],
    ['docs/art-pipeline/asset-registry.json', true],
    ['docs/game-design/evidence/ART-004/a.md', true],
    ['blender/ASSET-MEDUSA-001/preview/a.png', true],
    ['blender/ASSET-MEDUSA-001/export/SK.fbx', true],
    ['blender/ASSET-MEDUSA-001/tripo-source/x/a.glb', true],
    ['blender/ASSET-MEDUSA-001/medusa.blend', false],
    ['blender/ASSET-MEDUSA-001/export', false],
    ['docs/game-design/06-asset-manifest.csv', false],
    ['docs/game-design/decisions/2026-09-29-lookdev-v2-decisions.md', true],
    ['docs/game-design/decisions/2026-09-29-lookdev-v2-decisions.MD', true],
    ['docs/game-design/decisions/notes.json', false],
    ['docs/game-design/decisions/sub/x.png', false],
    ['docs/game-design/decisions', false],
    ['docs/game-design/decisions/', false],
    ['docs/game-design/decisionsX/a.md', false],
    ['docs/game-design/13-sprint-plan.md', false],
    ['docs/game-design/14-sprint-backlog.csv', false],
    ['art/imagegen/hero-quality-v1/medusa/medusa-front.png', true],
    ['docs/art-pipeline/material-library/sources.json', true],
    ['docs/art-pipeline/plan-status.json', true],
    ['unreal/Unmatched/Content/PipelineCandidates/Merlin/H2LD/SK_Merlin_H2LD.uasset', false],
    ['unreal/Unmatched/Config/DefaultEngine.ini', false],
    ['docs/secret.txt', false],
    ['unreal/Unmatched/Content/x.uasset', false],
    ['backend/.env', false],
    ['art', false],
    ['art/', false],
  ])('whitelist %j → %s', (p, ok) => {
    expect(isAllowedRelPath(p)).toBe(ok);
  });
});

describe('texture placeholder and candidates', () => {
  it('placeholder is a valid PNG (chunk CRCs match, IDAT inflates)', () => {
    const b = PLACEHOLDER_PNG;
    expect([...b.subarray(0, 8)]).toEqual([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a]);
    const types: string[] = [];
    let i = 8;
    while (i < b.length) {
      const len = b.readUInt32BE(i);
      const type = b.subarray(i + 4, i + 8);
      const data = b.subarray(i + 8, i + 8 + len);
      expect(zlib.crc32(Buffer.concat([type, data]))).toBe(b.readUInt32BE(i + 8 + len));
      if (type.toString() === 'IDAT') expect(() => zlib.inflateSync(data)).not.toThrow();
      types.push(type.toString());
      i += 12 + len;
    }
    expect(types).toEqual(['IHDR', 'IDAT', 'IEND']);
  });

  it('searches textures/ of ancestors down to the asset folder only', () => {
    const c = textureCandidates('blender/ASSET-B/variants/v4/export/SM.fbx', 'C:\\x\\T_A.png');
    expect(c).toContain('blender/ASSET-B/variants/v4/export/SM.fbm/T_A.png');
    expect(c).toContain('blender/ASSET-B/textures/T_A.png');
    expect(c).not.toContain('blender/textures/T_A.png');
    const r = textureCandidates('art/pipeline-candidates/ASSET-X/run1/export/SM.fbx', 'T.png');
    expect(r).toContain('art/pipeline-candidates/ASSET-X/run1/source/textures/T.png');
    expect(r).not.toContain('art/pipeline-candidates/textures/T.png');
  });
});

describe('parseRange / mimeFor', () => {
  it('parses single ranges', () => {
    expect(parseRange(undefined, 10)).toBeNull();
    expect(parseRange('bytes=2-5', 10)).toEqual({ start: 2, end: 5 });
    expect(parseRange('bytes=4-', 10)).toEqual({ start: 4, end: 9 });
    expect(parseRange('bytes=-3', 10)).toEqual({ start: 7, end: 9 });
    expect(parseRange('bytes=2-100', 10)).toEqual({ start: 2, end: 9 });
    expect(parseRange('bytes=10-12', 10)).toBe('unsatisfiable');
    expect(parseRange('bytes=5-2', 10)).toBe('unsatisfiable');
    expect(parseRange('bytes=0-1,4-5', 10)).toBeNull();
  });
  it('maps MIME types', () => {
    expect(mimeFor('a.mp4')).toBe('video/mp4');
    expect(mimeFor('a.GLB')).toBe('model/gltf-binary');
    expect(mimeFor('a.fbx')).toBe('application/octet-stream');
    expect(mimeFor('a.png')).toBe('image/png');
    expect(mimeFor('a.jpg')).toBe('image/jpeg');
    expect(mimeFor('a.json')).toMatch(/^application\/json/);
    expect(mimeFor('a.md')).toMatch(/^text\/markdown/);
    expect(mimeFor('a.html')).toMatch(/^text\/plain/);
    expect(mimeFor('a.wav')).toBe('audio/wav');
  });
});

describe('dev endpoints (/__art-hub)', () => {
  let repo: FixtureRepo;
  let server: http.Server;
  let base: string;
  let outside: string;
  let linksOk = false;

  beforeAll(async () => {
    repo = makeFixtureRepo();
    outside = fs.mkdtempSync(path.join(os.tmpdir(), 'art-hub-outside-'));
    fs.writeFileSync(path.join(outside, 'outside.txt'), 'outside secret');
    try {
      fs.symlinkSync(path.join(repo.root, 'private'), path.join(repo.root, 'art', 'escape-private'), 'junction');
      fs.symlinkSync(outside, path.join(repo.root, 'art', 'escape-outside'), 'junction');
      linksOk = true;
    } catch {
      linksOk = false;
    }
    const mw = createArtHubMiddleware({ repoRoot: repo.root });
    server = http.createServer((req, res) => {
      const url = req.url ?? '/';
      if (!url.startsWith('/__art-hub')) {
        res.statusCode = 404;
        res.end('spa');
        return;
      }
      req.url = url.slice('/__art-hub'.length) || '/';
      mw(req, res, () => {
        res.statusCode = 404;
        res.end('next');
      });
    });
    await new Promise<void>((r) => server.listen(0, '127.0.0.1', () => r()));
    base = `http://127.0.0.1:${(server.address() as AddressInfo).port}/__art-hub`;
  });

  afterAll(async () => {
    await new Promise<void>((r) => server.close(() => r()));
    repo.cleanup();
    fs.rmSync(outside, { recursive: true, force: true });
  });

  const get = (q: string, init?: RequestInit) => fetch(`${base}${q}`, init);
  const file = (p: string, init?: RequestInit) => get(`/file?path=${encodeURIComponent(p)}`, init);

  it('serves aggregated data as JSON', async () => {
    const res = await get('/data');
    expect(res.status).toBe(200);
    expect(res.headers.get('content-type')).toMatch(/application\/json/);
    expect(res.headers.get('cache-control')).toBe('no-store');
    const body = (await res.json()) as { schema: string; characters: { id: string }[] };
    expect(body.schema).toBe('unmatched.art-hub/1');
    expect(body.characters[0]?.id).toBe(HERO);
  });

  it('serves whitelisted files with MIME, ETag and Range', async () => {
    const full = await file(`art/animation-refs/${HERO}/HERO-Idle/HERO-Idle_kling25_ref.mp4`);
    expect(full.status).toBe(200);
    expect(full.headers.get('content-type')).toBe('video/mp4');
    expect(full.headers.get('accept-ranges')).toBe('bytes');
    expect(full.headers.get('x-content-type-options')).toBe('nosniff');
    expect(await full.text()).toBe('0123456789abcdefghij');
    const etag = full.headers.get('etag')!;

    const part = await file('art/range.bin', { headers: { Range: 'bytes=2-5' } });
    expect(part.status).toBe(206);
    expect(part.headers.get('content-range')).toBe('bytes 2-5/20');
    expect(part.headers.get('content-length')).toBe('4');
    expect(await part.text()).toBe('2345');

    const suffix = await file('art/range.bin', { headers: { Range: 'bytes=-3' } });
    expect(suffix.status).toBe(206);
    expect(await suffix.text()).toBe('hij');

    const bad = await file('art/range.bin', { headers: { Range: 'bytes=50-60' } });
    expect(bad.status).toBe(416);
    expect(bad.headers.get('content-range')).toBe('bytes */20');

    const cached = await file(`art/animation-refs/${HERO}/HERO-Idle/HERO-Idle_kling25_ref.mp4`, { headers: { 'If-None-Match': etag } });
    expect(cached.status).toBe(304);

    const head = await file('art/range.bin', { method: 'HEAD' });
    expect(head.status).toBe(200);
    expect(head.headers.get('content-length')).toBe('20');

    const dl = await get(`/file?path=${encodeURIComponent('art/range.bin')}&download=1`);
    expect(dl.headers.get('content-disposition')).toMatch(/^attachment/);
  });

  it.each([
    ['../package.json', 400],
    ['art/../docs/secret.txt', 400],
    ['art\\..\\docs\\secret.txt', 400],
    ['%2e%2e/docs/secret.txt', 400],
    ['/etc/passwd', 400],
    ['C:/Windows/win.ini', 400],
    ['art/.hidden.txt', 400],
    ['docs/secret.txt', 403],
    ['private/secret.txt', 403],
    [`blender/${HERO}/hero.blend`, 403],
    ['docs/game-design/07-animation-vfx-audio.csv', 403],
    ['docs/game-design/decisions/notes.json', 403],
    ['docs/game-design/decisions/../evidence/x.md', 400],
    ['unreal/Unmatched/Content/PipelineCandidates/Hero/Rig/SK_Hero_Rig.uasset', 403],
    ['art/missing.png', 404],
    ['art/animation-refs', 404],
  ])('rejects %j with %i', async (p, status) => {
    // %2e%2e is sent pre-encoded once more so the server sees a literal "%2e%2e" or ".."
    const res = p.startsWith('%') ? await get(`/file?path=${p}`) : await file(p);
    expect(res.status).toBe(status);
    const text = await res.text();
    expect(text).not.toMatch(/secret/);
  });

  it('serves decision logs (markdown only) as text', async () => {
    const res = await file('docs/game-design/decisions/2026-01-02-hero-decisions.md');
    expect(res.status).toBe(200);
    expect(res.headers.get('content-type')).toMatch(/^text\/markdown/);
    expect(await res.text()).toMatch(/Журнал решений: герой/);
  });

  it('rejects requests without a path and non-GET methods', async () => {
    expect((await get('/file')).status).toBe(400);
    expect((await get('/data', { method: 'POST' })).status).toBe(405);
  });

  it('passes unknown routes to the next middleware', async () => {
    const res = await get('/unknown');
    expect(res.status).toBe(404);
    expect(await res.text()).toBe('next');
  });

  it('blocks symlinks/junctions that escape the whitelist or the repo', async () => {
    if (!linksOk) return; // symlink creation not permitted on this machine
    const toPrivate = await file('art/escape-private/secret.txt');
    expect(toPrivate.status).toBe(403);
    const toOutside = await file('art/escape-outside/outside.txt');
    expect(toOutside.status).toBe(403);
    expect(await toOutside.text()).not.toMatch(/outside secret/);
    const guard = resolveSafePath(repo.root, 'art/escape-outside/outside.txt');
    expect(guard.ok).toBe(false);
  });

  it('resolves model textures next to the model and falls back to a placeholder', async () => {
    const model = `blender/${HERO}/export/SK_Hero.fbx`;
    expect(textureCandidates(model, 'C:\\tex\\T_Hero_BC.png')).toContain(`blender/${HERO}/textures/T_Hero_BC.png`);
    const found = await get(`/texture?model=${encodeURIComponent(model)}&name=${encodeURIComponent('C:\\tex\\T_Hero_BC.png')}`);
    expect(found.status).toBe(200);
    expect(found.headers.get('content-type')).toBe('image/png');
    expect(found.headers.get('x-art-hub-missing')).toBeNull();

    const missing = await get(`/texture?model=${encodeURIComponent(model)}&name=nope.png`);
    expect(missing.status).toBe(200);
    expect(missing.headers.get('x-art-hub-missing')).toBe('1');

    const sneaky = await get(`/texture?model=${encodeURIComponent(model)}&name=${encodeURIComponent('../../../docs/secret.txt')}`);
    expect(sneaky.headers.get('x-art-hub-missing')).toBe('1');
    expect(await sneaky.text()).not.toMatch(/secret/);

    const badModel = await get(`/texture?model=${encodeURIComponent('../x.fbx')}&name=a.png`);
    expect(badModel.status).toBe(400);
  });
});
