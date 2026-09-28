/**
 * Builds a small fake repo in a temp dir that mimics the real art-pipeline
 * layout (registry, manifests, runs, video refs, ledger, acts). Tests create
 * it on the fly so no fake binaries are committed.
 */
import crypto from 'node:crypto';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';

export const HERO = 'ASSET-HERO-001';
export const BARREL = 'ASSET-DECOR-KIT-001.BARREL';

export function sha(text: string | Buffer): string {
  return crypto.createHash('sha256').update(text).digest('hex');
}

export interface FixtureRepo {
  root: string;
  write: (rel: string, content: string | Buffer) => void;
  cleanup: () => void;
}

export function makeFixtureRepo(): FixtureRepo {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'art-hub-fixture-'));
  const write = (rel: string, content: string | Buffer) => {
    const abs = path.join(root, ...rel.split('/'));
    fs.mkdirSync(path.dirname(abs), { recursive: true });
    fs.writeFileSync(abs, content);
  };
  const json = (rel: string, v: unknown) => write(rel, JSON.stringify(v, null, 2));

  const fbxBytes = 'Kaydara FBX Binary  \0fake-sk-hero';
  const glbBytes = 'glTF-fake-barrel';
  const videoBytes = Buffer.from('0123456789abcdefghij'); // 20 bytes, used for Range tests
  const pngBytes = Buffer.from([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a, 1, 2, 3]);

  // ---- files on disk
  write(`art/pipeline-candidates/${HERO}/20260101-run/export/SK_Hero.fbx`, fbxBytes);
  write(`art/pipeline-candidates/${HERO}/20260101-run/preview/front.png`, pngBytes);
  write(`art/pipeline-candidates/${HERO}/20260101-run/reports/verify-report.json`, '{"checks":{}}');
  write(`art/pipeline-candidates/${HERO}/20260101-run/preview/deform/probe-deform.json`, JSON.stringify({
    label: 'probe',
    source: 'x.fbx',
    tests: [
      { test: 'head_turn', bone: 'head', deg: 35, status: 'plausible' },
      { test: 'arm', bone: 'arm_upper.L', deg: -45, status: 'wrong_region' },
    ],
  }));
  write(`art/pipeline-candidates/${HERO}/20260101-run/preview/deform/probe-sheet.png`, pngBytes);
  json(`art/pipeline-candidates/${HERO}/20260101-run/manifest.json`, {
    schema: 'unmatched.tripo-pipeline.run/1',
    run_id: '20260101-run',
    created_at: '2026-01-01T00:00:00+00:00',
    tool: { name: 'tripo-pipeline', version: '0.4.0' },
    claims: { art_accepted: false },
    exports: [{ path: 'export/SK_Hero.fbx', sha256: sha(fbxBytes) }],
    stages: { build: { status: 'completed', summary: { passed: true }, outputs: {} } },
  });
  // half-written manifest of a live run → warning, no crash
  write(`art/pipeline-candidates/${HERO}/20260102-broken/manifest.json`, '{ "schema": "unmatched.tripo-pipeline.run/1", ');
  write(`art/pipeline-candidates/ASSET-DECOR-KIT-001/20260101-barrel/source/barrel.glb`, glbBytes);
  write(`art/pipeline-candidates/${HERO}/scripts/helper.py`, 'print(1)'); // helper dir, not a run
  write(`art/pipeline-candidates/${HERO}/notes-dir/readme.txt`, 'no run markers'); // not a run either
  write(`art/pipeline-candidates/ASSET-DECOR-KIT-001/20260101-barrel/preview/barrel-front.png`, pngBytes);

  write(`blender/${HERO}/preview/rig-idle.png`, pngBytes);
  write(`blender/${HERO}/export/AM_Hero_Idle.fbx`, fbxBytes);
  write(`blender/${HERO}/textures/T_Hero_BC.png`, pngBytes);
  write(`blender/${HERO}/hero.blend`, 'BLENDER-not-served');

  const cue = `art/animation-refs/${HERO}/HERO-Idle`;
  write(`${cue}/HERO-Idle_kling25_ref.mp4`, videoBytes);
  write(`${cue}/contact-sheet-2fps.png`, pngBytes);
  write(`${cue}/keyframes/f000.png`, pngBytes);
  write(`${cue}/prompt.txt`, 'Locked-off static camera, hero breathes.');
  json(`${cue}/analysis.json`, { summary: { frames: 121, width: 960, height: 960, motion_mad_max: 3.2, fg_touches_edge_frames: [] }, per_frame: [] });
  write(`${cue}/take2/HERO-Idle_seedance15pro_take2_ref.mp4`, videoBytes);
  write(`${cue}/take2/prompt.txt`, 'retake');
  write('art/animation-refs/ASSET-NEW-001/NEW-Idle/prompt.txt', 'a new character appears');
  write('art/range.bin', videoBytes);
  write('art/.hidden.txt', 'hidden');
  write('docs/secret.txt', 'top secret');
  write('private/secret.txt', 'private secret');

  write('docs/game-design/evidence/ART-100/act-2026.md', '# Акт героя\n\n**Решение:** доработать (v2).\n');
  write('docs/game-design/evidence/ART-100/frame-k2.png', pngBytes);
  write('docs/art-pipeline/hero-candidate-report.md', '# Отчёт по герою\n');

  // ---- registry
  const ref = (p: string, extra: Record<string, unknown> = {}) => ({ path: p, root: 'repo', kind: 'file', expect: 'exists', ...extra });
  json('docs/art-pipeline/asset-registry.json', {
    schemaVersion: 1,
    snapshotDate: '2026-01-01',
    vocabularies: {
      status: {
        'не начато': 'нет файлов',
        предложено: 'только бриф',
        измерено: 'есть отчёт',
        'технически импортировано': 'импорт в UE',
        'художественно принято': 'есть акт',
      },
      statusRules: ['Слой не может иметь статус «художественно принято».'],
      stage: ['planned', 'reference-images', 'tripo-source', 'blender-candidate', 'ue-editor-import'],
      pathRoots: { repo: 'repo', 'art-worktree': 'Рабочая копия C:/nonexistent/worktree' },
    },
    assets: [
      {
        id: HERO,
        name: 'Hero (герой)',
        category: 'hero',
        backlog: ['ART-100'],
        parent: null,
        instances: 1,
        status: 'измерено',
        stage: 'blender-candidate',
        sourceImages: { recommended: [] },
        source3d: [ref(`art/pipeline-candidates/${HERO}/20260101-run/export/SK_Hero.fbx`, { role: 'вход кандидата', sha256: sha(fbxBytes) })],
        layers: [
          {
            layer: 'blender-candidate',
            stage: 'blender-candidate',
            status: 'измерено',
            owner: 'pipeline',
            decision: 'доработать v2',
            paths: [
              ref(`blender/${HERO}/export/AM_Hero_Idle.fbx`, { sha256: 'deadbeef'.repeat(8) }),
              ref('/Game/Hero/SK_Hero', { kind: 'ue-asset' }),
              ref('docs/game-design/evidence/ART-100/act-2026.md', { role: 'акт' }),
            ],
          },
        ],
        nextStep: 'Сделать v2.',
        blocker: 'Нет решения по лицу.',
        doneCriteria: 'Акт приёмки.',
        acceptanceEvidence: [],
        evidence: [ref('docs/art-pipeline/missing-report.md', { role: 'нет файла' })],
      },
      {
        id: `${HERO}.WEAPON`,
        name: 'Меч героя',
        category: 'weapon',
        parent: HERO,
        backlog: ['ART-100'],
        status: 'предложено',
        stage: 'reference-images',
        layers: [],
      },
      {
        id: BARREL,
        name: 'Бочка (пропс)',
        category: 'prop',
        parent: 'ASSET-DECOR-KIT-001',
        backlog: ['ART-009'],
        status: 'измерено',
        stage: 'blender-candidate',
        source3d: [ref('art/pipeline-candidates/ASSET-DECOR-KIT-001/20260101-barrel/source/barrel.glb', { role: 'основной вход', sha256: sha(glbBytes) })],
        layers: [{ layer: 'tripo', stage: 'tripo-source', status: 'измерено', paths: [ref('docs/art-pipeline/evidence/barrel/tripo-run.json')] }],
        acceptanceEvidence: [],
      },
      {
        id: 'ASSET-DECOR-KIT-001.LANTERN',
        name: 'Фонарь',
        category: 'prop',
        parent: 'ASSET-DECOR-KIT-001',
        backlog: ['ART-009'],
        status: 'художественно принято',
        stage: 'reference-images',
        layers: [],
        acceptanceEvidence: [],
      },
    ],
  });

  // ---- clip manifest + validation
  write('docs/art-pipeline/animation-library/clip-manifest.schema.json', JSON.stringify({
    description:
      'Статусы строго: proposed (предложено) -> draft_test (черновой тестовый файл) -> measured (измерено валидатором) -> technically_imported (технически импортировано в UE) -> artistically_accepted (художественно принято, только с актом). rejected — проверено и отклонено.',
  }));
  json('docs/art-pipeline/animation-library/clip-manifest.json', {
    schema: 'unmatched.animation-clip-manifest/1',
    revision: 'r1',
    rig_contract: 'docs/art-pipeline/rig/rig-contract.json',
    notes: ['слоты не заполнены'],
    clips: [
      {
        id: 'HERO-Idle',
        character: 'Hero',
        asset_id: HERO,
        clip: 'Idle',
        role: 'production',
        required_mvp: true,
        cue: ['state:Idle', 'CUE-017'],
        source: { type: 'none' },
        license: { terms: 'нет файла', commercial_use: 'n/a' },
        fps: { target: 24, measured: null },
        duration_s: { target: '2-3', target_status: 'proposal', measured: null },
        loop: true,
        root_motion: 'in_place',
        skeleton: { contract_key: 'UM_HUMANOID_17_v1', version: 'r1' },
        ue: { target_path: '/Game/X/AM_Hero_Idle', status: 'proposed' },
        status: 'proposed',
        validation: { result: 'not_run' },
      },
      {
        id: 'HERO-Idle-draft',
        character: 'Hero',
        asset_id: HERO,
        clip: 'Idle',
        role: 'test',
        required_mvp: false,
        cue: ['state:Idle'],
        source: { type: 'blender_keyframed', files: [{ path: `blender/${HERO}/export/AM_Hero_Idle.fbx`, exists: true, format: 'fbx' }] },
        license: { terms: 'own', commercial_use: 'yes' },
        fps: { target: 24, measured: 24 },
        duration_s: { target: 2.3, measured: 2.3 },
        loop: true,
        root_motion: 'in_place',
        skeleton: { contract_key: 'UM_HUMANOID_17_v1', version: 'r1' },
        status: 'draft_test',
        validation: { result: 'pass', report: 'docs/art-pipeline/animation-library/validation/AM_Hero_Idle.validation.json', fails: [], warnings: ['visible_pose_change'] },
      },
    ],
  });
  json('docs/art-pipeline/animation-library/validation/AM_Hero_Idle.validation.json', {
    checks: [
      { check: 'import', status: 'pass' },
      { check: 'visible_pose_change', status: 'warn', note: 'порог — предложение' },
    ],
  });
  json('docs/art-pipeline/animation-library/validation/summary.json', {
    cases: [{ case: 'AM_Hero_Idle', clip: `blender/${HERO}/export/AM_Hero_Idle.fbx`, result: 'pass', expectation_met: true, fails: [], warnings: [] }],
  });
  write(
    'docs/art-pipeline/animation-library/VIDEO-TO-MOTION.md',
    [
      '# Video-to-motion',
      '',
      '## 4. Ретаргет',
      '',
      'Для Harpy video-to-motion **не применим**: крылья. Её клипы делаются вручную.',
      '',
      '## 5. Рекомендация',
      '',
      '1. **Сейчас**: ротоскоп ручных ключей.',
      '2. Если нужен mocap — Rokoko.',
      '',
      '## 6. Внешние зависимости',
      '',
      '| Зависимость | Нужна для | Статус | Кто решает |',
      '| --- | --- | --- | --- |',
      '| Аккаунт Rokoko | п.2 | не создан | пользователь |',
      '| Скрипт ретаргета | перекладка | не написано | следующий этап |',
      '',
    ].join('\n'),
  );

  // ---- video refs manifest
  json('docs/art-pipeline/animation-refs/manifest.json', {
    assetId: HERO,
    overallStatus: 'референсы, не анимация',
    budget: { spentSyntxTokens: 6 },
    nextSteps: { status: 'предложено', items: ['Проба video-to-motion'] },
    clips: [
      {
        cue: 'HERO-Idle',
        status: 'референс, не анимация',
        suitabilityVideoToMotion: { verdict: 'ограниченно пригоден', status: 'оценка по кадрам' },
        service: 'SYNTX → Kling',
        parameters: { version: '2.5', mode: 'standart' },
        output: { path: `${cue}/HERO-Idle_kling25_ref.mp4`, sha256: sha(videoBytes) },
        keyframes: [{ frame: 0, path: `${cue}/keyframes/f000.png`, sha256: sha(pngBytes) }],
        cost: { syntxTokens: 6, balanceBefore: 100, balanceAfter: 94 },
      },
    ],
  });

  // ---- rig contract
  json('docs/art-pipeline/rig/rig-contract.json', {
    revision: 'r1',
    status: 'предложено',
    skeletons: {
      UM_HUMANOID_17_v1: {
        applies_to: [HERO, 'Harpy (planned)'],
        armature_object: { name: 'SKEL_UM_Humanoid', status: 'предложено' },
        bones: [
          { name: 'root', parent: null },
          { name: 'hips', parent: 'root' },
          { name: 'hand.R', parent: 'hips' },
          { name: 'weapon', parent: 'hand.R', parent_by_character: { Hero: 'hand.R' } },
        ],
      },
    },
    ue_import: { sockets: [{ name: 'Weapon', bone: 'weapon', offset: [0, 0, 0] }] },
    optional_extensions: { cloak: { status: 'предложено', rule: 'плащ' } },
    retarget_maps: { mixamo_to_um17: { status: 'составлено' } },
  });

  // ---- credits ledger
  json('docs/art-pipeline/evidence/baseline/credits-ledger.json', {
    tripo: {
      unit: 'Studio-кредиты',
      preWindow: { entries: [{ historyTime: '2026-01-01 10:00', op: 'Пополнение', delta: 100 }] },
      window: {
        balanceStart: 1000,
        spent: 55,
        limit: 300,
        byTask: { hero: 40, barrel: 15 },
        entries: [
          { historyTime: '2026-01-01 11:00', op: 'Генерация героя', delta: -40, ref: `art/pipeline-candidates/${HERO}/20260101-run/manifest.json` },
          { historyTime: '2026-01-01 12:00', op: 'Генерация бочки', delta: -15, ref: 'docs/art-pipeline/evidence/barrel/tripo-run.json' },
          { historyTime: '2026-01-01 13:00', op: 'Неизвестная трата', delta: -5, ref: 'somewhere/else.json' },
        ],
      },
    },
    syntx: {
      unit: 'токены SYNTX',
      window: {
        balanceStart: 100,
        spent: 13.5,
        entries: [
          { cue: 'HERO-Idle', model: 'Kling 2.5 std', delta: -6, balanceAfter: 94, ref: `${cue}/` },
          { time: '2026-01-01T14:00:00+05:00', asset: HERO, cue: 'HERO-Idle', model: 'Seedance 1.5 Pro', delta: -7.5, balanceBefore: 94, balanceAfter: 86.5, ref: `${cue}/take2/` },
        ],
      },
    },
  });

  // ---- sound cues
  write(
    'docs/game-design/07-animation-vfx-audio.csv',
    'cueId,event,triggerCondition,object,animation,vfx,sound,durationMs\n' +
      'CUE-017,"Потеря, idle",state,фигурка,idle,нет,"ui: мягкий сигнал",400\n' +
      'CUE-014,Способность,Hero: удар,носитель,нет,свечение,sfx: способность,800\n' +
      'CUE-001,Наведение,курсор,клетка,нет,нет,ui: тик,150\n',
  );

  return {
    root,
    write,
    cleanup: () => fs.rmSync(root, { recursive: true, force: true }),
  };
}
