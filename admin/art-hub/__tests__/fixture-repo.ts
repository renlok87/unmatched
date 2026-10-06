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

  // decision logs: markdown is served, anything else under decisions/ is not
  write(
    'docs/game-design/decisions/2026-01-02-hero-decisions.md',
    '# Журнал решений: герой\n\n**Происхождение.** Решения принял оркестратор по делегированию.\n\n## D-1. Первое\n\n## D-2. Второе\n',
  );
  write('docs/game-design/decisions/notes.json', '{"secret": "decisions json"}');
  // UE project: only stat-ed by the hub, never served
  write('unreal/Unmatched/Content/PipelineCandidates/Hero/Rig/SK_Hero_Rig.uasset', 'uasset-rig');
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

/**
 * Adds look-dev, material library, UE layer and concept fixtures to a fixture
 * repo (overview sections). Patches the registry (H2LD layer dated 20260102)
 * and the clip manifest (H2Anim target path).
 */
export function addOverviewFixtures(repo: FixtureRepo): void {
  const { write } = repo;
  const json = (rel: string, v: unknown) => write(rel, JSON.stringify(v, null, 2));
  const read = (rel: string) => JSON.parse(fs.readFileSync(path.join(repo.root, ...rel.split('/')), 'utf8')) as Record<string, any>;
  const png = Buffer.from([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a, 9, 9]);

  const sheet = `art/pipeline-candidates/${HERO}/20260101-run/review/i1/hero-lookdev-sheet-i1.jpg`;
  write(sheet, png);
  write(`art/pipeline-candidates/${HERO}/20260101-run/preview/ld_sheet_concept_front.jpg`, png);
  write('art/imagegen/hero-quality-v1/hero/hero-front.png', png);
  write('art/imagegen/hero-quality-v1/hero/prompts.md', '# prompts');
  write('art/imagegen/hero-quality-v1/reference/quality-reference.png', png);
  write(
    'docs/art-pipeline/hero-lookdev-v2.md',
    '# Hero look-dev v2\n\nДата: 2026-01-02. Статус: **измерено**, в UE технически импортировано.\n\n' +
      'Скелет `/Game/PipelineCandidates/Hero/Rig`, меш `/Game/PipelineCandidates/Hero/H2LD/SK_Hero_H2LD`.\n\n' +
      '## 1. Что выпущено\n\n```bash\n## не заголовок (код)\n```\n\n## 2. UE\n',
  );
  write('unreal/Unmatched/Content/PipelineCandidates/Hero/H2LD/SK_Hero_H2LD.uasset', 'uasset-h2ld');

  const reg = read('docs/art-pipeline/asset-registry.json');
  const hero = reg.assets.find((a: { id: string }) => a.id === HERO);
  hero.layers.push({
    layer: 'ue-editor-import H2LD 20260102-h2ld-ue-import (/Game/PipelineCandidates/Hero/H2LD)',
    stage: 'ue-editor-import',
    status: 'технически импортировано',
    owner: 'pipeline',
    paths: [{ path: sheet, root: 'repo', kind: 'file', expect: 'exists', role: 'лист look-dev' }],
  });
  json('docs/art-pipeline/asset-registry.json', reg);

  const cm = read('docs/art-pipeline/animation-library/clip-manifest.json');
  cm.clips[0].ue = { status: 'technically_imported', target_path: '/Game/PipelineCandidates/Hero/H2Anim/AM_Hero_Idle' };
  json('docs/art-pipeline/animation-library/clip-manifest.json', cm);

  const ml = 'docs/art-pipeline/material-library';
  write(`${ml}/README.md`, '# Библиотека материалов\n\nДата: 2026-01-02. Статус: **предложено**.\n\n## 1. Зачем\n');
  json(`${ml}/um-material-presets-v1.json`, {
    schema: 'um-material-presets/1',
    version: 'v1',
    date: '2026-01-02',
    status: 'предложено',
    classes: [
      { index: 1, id: 'steel', nameRu: 'сталь', family: 'metal', metallic: 1, shadingModel: 'DefaultLit', baseColor: { typicalLinear: [0.5, 0.5, 0.5] }, roughness: { typical: 0.3 } },
      { index: 11, id: 'silk', nameRu: 'шёлк', family: 'dielectric', metallic: 0, shadingModel: 'Cloth' },
    ],
    extensionClasses: [{ index: 16, id: 'horn', nameRu: 'рог', family: 'dielectric', metallic: 0 }],
  });
  json(`${ml}/sources.json`, {
    schema: 'um-material-library-sources/1',
    licenseNote: 'ambientCG — CC0 1.0',
    sets: [
      { id: 'Metal001', status: 'используется', class: 'steel', license: 'CC0 1.0 (ambientCG site-wide)', page: 'https://ambientcg.com/view?id=Metal001' },
      { id: 'Bad001', status: 'не используется', class: null, license: 'CC-BY 4.0' },
    ],
    procedural: [{ class: 'silk', generator: 'procedural:satin5', reason: 'нет CC0-шёлка' }],
  });
  write('art/material-library/v1/tiles/steel/steel_DetailN.png', png);
  write(`${ml}/evidence/v2/master/um-sheet-wall.jpg`, png);
  write(`${ml}/evidence/v2/master/probe.json`, '{}');
}

/** 230-character note: the hub cuts it to 200. */
export const AUDIO_LONG_NOTE = `${'длинная заметка '.repeat(14)}конец`;

/**
 * Adds the game-audio track (docs/game-design/audio, evidence/AUDIO, UE
 * SoundWaves, AUC-* ledger entries) to a fixture repo.
 */
export function addAudioFixtures(repo: FixtureRepo): void {
  const { write } = repo;
  const json = (rel: string, v: unknown) => write(rel, JSON.stringify(v, null, 2));
  const read = (rel: string) => JSON.parse(fs.readFileSync(path.join(repo.root, ...rel.split('/')), 'utf8')) as Record<string, any>;
  const audio = 'docs/game-design/audio';

  write(`${audio}/00-AUDIO-BRIEF.md`, '# Звук: бриф\n\nДата: 2026-01-03. Статус: принято.\n\n## 1. Цель\n\n## 2. Объём\n');
  write(`${audio}/START-PROMPT.md`, '# Промпт чата (не документ)\n');
  write(
    `${audio}/03-sound-registry.csv`,
    [
      'id,category,name_ru,event_or_cue,trigger,duration_ms,variations,bus,priority,concurrency,loop,scope,owner,source_plan,license,status,file,de013_role,notes',
      `VO-HERO-ATTACK,vo,Герой: атака,CUE-020,атака,800,2,VO,2,1,нет,MVP,Hero,elevenlabs,SYNTX,in-game,/Game/Audio/VO/Hero/SW_VO_HERO_ATTACK_*,,${AUDIO_LONG_NOTE}`,
      'VO-HERO-ATTACK-BIG,vo,Герой: сильная атака,CUE-020,атака ≥ 4,900,1,VO,2,1,нет,MVP,Hero,elevenlabs,SYNTX,in-game,/Game/Audio/VO/Hero/SW_VO_HERO_ATTACK_BIG_*,,',
      'FX-HERO-SLASH,fx,Удар героя,CUE-014,способность,600,1,SFX,3,1,нет,MVP,-,kenney,CC0,in-game,/Game/Audio/FX/SW_FX_HERO_SLASH,,',
      'FX-GLARE,fx,Взгляд,CUE-015,способность,700,1,SFX,3,1,нет,MVP,Hero,synth,своё,in-game,/Game/Audio/FX/SW_FX_GLARE,,ассета нет',
      'UI-BTN-HOVER,ui,Наведение на кнопку,-,hover,80,2,UI,5,1,нет,MVP,-,kenney,CC0,in-bank,/Game/Audio/UI/SW_UI_BTN_HOVER_*,,"AU-S5: не звучит, нет события ""hover"""',
      'CMB-HIT-BLUNT,combat,Удар дробящий,-,-,-,-,SFX,3,1,нет,framework,-,-,-,template,,,',
      'MOT-DUEL,motif,Мотив дуэли,-,-,-,-,-,-,-,нет,MVP,-,midi,своё,done-source,C:/tmp/audio-src/sketches/MOT-DUEL.mid|.wav (вне git),,',
      'UI-BRD-HOVER,ui,Наведение на клетку,-,-,-,-,-,-,-,нет,MVP,-,-,-,none-by-design,,,нет по замыслу',
    ].join('\n'),
  );
  write(`${audio}/06-task-cards.csv`, 'id,title\nAUC-V01,реплики\n');
  write(
    `${audio}/04-vo-script.md`,
    [
      '# 04 — Реплики',
      '',
      '## 2. Hero — 3 реплики',
      '',
      '| ID | EN (текст озвучки) | RU (субтитр) | Направление |',
      '|---|---|---|---|',
      '| HERO-ATTACK-01 | Go! | Вперёд! | [firm] |',
      '| HERO-ATTACK-02 | For the realm. | За королевство. | [rousing] |',
      '| HERO-DEATH-01 | — | — | [groan] |',
      '| HERO-ATTACK-01 | Go! | Вперёд! | [firm] |',
      '',
      '## 5. Гарпии',
      '',
      '| ID | Что | Направление |',
      '|---|---|---|',
      '| HARPY-ATTACK-01…03 | визг | короткий |',
      '| HARPY-RETURN-01 | восходящий визг | 0,6 с |',
      '',
    ].join('\n'),
  );
  write(
    `${audio}/07-production-log.md`,
    '# 07 — Журнал производства\n\nДата: 2026-01-04.\n\n## 0. Итог\n\n| Слой | Статус | Где |\n|---|---|---|\n| Реплики | **в игре** | `/Game/Audio/VO/` |\n\n## 1. Решения\n',
  );

  const ev = 'docs/game-design/evidence/AUDIO';
  write(`${ev}/2026-01-03/arena-host.trace.log`, 'trace');
  write(`${ev}/2026-01-04/arena-host-frame.png`, Buffer.from([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a, 7]));
  const targets = { I: '-20.0 ±2.0', TP_max: -1.0 };
  json(`${ev}/2026-01-04/arena-host-mix.json`, { I: -19.8, LRA: 7, TP: -1.5, S_max: -16.8, near_peak_share: 0.6, seconds: 60.5, file: 'host.wav', correction_db: 0, ok_I: true, ok_TP: true, targets });
  json(`${ev}/2026-01-04/arena-joiner-mix.json`, { I: -23.1, TP: -2, S_max: -19, seconds: 58, ok_I: false, ok_TP: true, targets });
  write(`${ev}/2026-01-04/broken-host-mix.json`, '{ "I": -20, ');

  const ue = 'unreal/Unmatched/Content/Audio';
  write(`${ue}/VO/Hero/SW_VO_HERO_ATTACK_01.uasset`, 'sw');
  write(`${ue}/VO/Hero/SW_VO_HERO_ATTACK_02.uasset`, 'sw');
  write(`${ue}/VO/Hero/SW_VO_HERO_ATTACK_BIG_01.uasset`, 'sw');
  write(`${ue}/FX/SW_FX_HERO_SLASH_01.uasset`, 'sw');
  write(`${ue}/UI/SW_UI_BTN_HOVER_01.uasset`, 'sw');
  write(`${ue}/Combat/SW_CMB_HIT_BLUNT_01.uasset`, 'sw');

  const ledgerRel = 'docs/art-pipeline/evidence/baseline/credits-ledger.json';
  const ledger = read(ledgerRel);
  ledger.syntx.window.entries.push(
    { time: '2026-01-02T10:00:00+05:00', asset: 'VO-HERO-ATTACK', cue: 'AUC-V01', op: 'tts (ElevenLabs v3)', model: 'ElevenLabs v3', delta: -2.5, balanceBefore: 86.5, balanceAfter: 84, ref: 'C:/tmp/audio-src/syntx-runs/AUC-V01/' },
    { time: '2026-01-02T11:00:00+05:00', asset: 'MUS-MENU', cue: 'AUC-M01', op: 'music (Suno)', delta: -10, balanceBefore: 84, balanceAfter: 74, ref: 'C:/tmp/audio-src/syntx-runs/AUC-M01/' },
    { time: '2026-01-02T11:05:00+05:00', asset: 'MUS-MENU', cue: 'AUC-M01', op: 'возврат за сбой', delta: 1, balanceBefore: 74, balanceAfter: 75 },
  );
  json(ledgerRel, ledger);
}
