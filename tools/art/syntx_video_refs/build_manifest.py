"""Regenerate docs/art-pipeline/animation-refs/manifest.json for the ASSET-MEDUSA-001 video motion references.

Usage: python tools/art/syntx_video_refs/build_manifest.py

Reads only repo files: art/animation-refs/ASSET-MEDUSA-001/MED-<Cue>/{prompt.txt,analysis.json,*.mp4,keyframes/,syntx/*.json}
and art/animation-refs/ASSET-MEDUSA-001/syntx-session/*.json (redacted copies made by import_runs.py). Needs ffprobe.
Moved from the scratch C:/tmp/medusa-vid/build_manifest.py (2026-09-28) and corrected after the P1 review (VID).
"""
import glob
import hashlib
import json
import os
import subprocess

R = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..')).replace('\\', '/')
A = 'art/animation-refs/ASSET-MEDUSA-001'
SESSION = f'{A}/syntx-session'
VISUAL = 'оценка по кадрам (визуально); pose-трекинг не запускался'


def sha(p):
    return hashlib.sha256(open(f'{R}/{p}', 'rb').read()).hexdigest()


def jload(p):
    return json.load(open(f'{R}/{p}', encoding='utf-8'))


def bal(p):
    return json.loads(jload(p)['content'][0]['text'])['balance']


inp = 'art/imagegen/mvp-v1/characters/ref-medusa-v5-front.png'
up = jload(f'{SESSION}/fileobj.json')

# Model values priced before the run (table in modelChoice.priceQuotes). "Grok i2v 480p" in the table does not say
# whether grok_i2v or grok_15_i2v was quoted, so both Grok i2v models are treated as unclear, not as unpriced.
PRICED = {'kling_image2video', 'seedance_pro-fast', 'seedance_pro', 'seedance-1.5-pro', 'hailuo-2.3-fast', 'hailuo-2.3',
          'hailuo-02', 'wan_26_i2v_flash', 'wan_26_i2v', 'wan_27_i2v', 'veo3fast_r', 'turbo4genfirstframeimage',
          'gen4.5i2v'}
UNCLEAR = {'grok_i2v', 'grok_15_i2v'}
not_priced = []
for p in sorted(glob.glob(f'{R}/{SESSION}/models_*.json')):
    for m in json.loads(json.load(open(p, encoding='utf-8'))['content'][0]['text']):
        media = (m.get('settings') or {}).get('allowed_media_types') or []
        if m.get('active') and 'images' in media and m['value'] not in PRICED | UNCLEAR:
            not_priced.append(m['value'])

eval_ = {
    'Idle': {
        'cueRef': 'нет CUE (фоновое состояние; бриф 18 §5 MED-Idle, CUE-017 только пауза)',
        'order': 2,
        'keyframes': [0, 30, 60, 90, 120],
        'motion': 'лёгкое дыхание и микроповорот головы; амплитуда очень мала (motion_mad_max 0.815, самый низкий из четырёх)',
        'suitability': 'ограниченно пригоден',
        'assessment': {
            'camera': 'стабильна: нижний край подставки неподвижен (размах 0 px), центр обода — размах 5.5 px (вероятно, подол у обода), фон по краям MAD ≤2.3',
            'limbs': 'все конечности видны весь ролик; ноги частично закрыты хитоном (видны через разрез и поножи)',
            'bow': 'лук в левой руке (справа в кадре) весь ролик, форма стабильна',
            'artifacts': 'змеиная корона перерисована относительно входа (число и размер змей плавают); цикл не замкнут: MAD первый/последний кадр 7.66',
            'videoToMotion': 'прогноз (pose-трекинг не запускался): движение, вероятно, ниже шума монокулярной оценки позы; годится как референс амплитуды и тайминга дыхания, не как источник кривых. Idle дешевле ставить руками по брифу',
        },
    },
    'LungeAttack': {
        'cueRef': 'CUE-008 (600 мс), бриф 18 §5 MED-LungeAttack',
        'order': 1,
        'keyframes': [0, 24, 48, 88, 94, 120],
        'motion': 'разворот торса вправо по кадру (к ¾), подъём лука, натяжение (кадры ~0–51), удержание прицела (~54–88), выпуск между 88 и 94 (стрела исчезает, полёта нет), возврат в стойку (~93–120)',
        'suitability': 'пригоден как референс верха тела (лучший из четырёх); направление выстрела расходится с брифом 18 §5 (см. briefDeviation)',
        'assessment': {
            'camera': 'стабильна: нижний край подставки — размах 0 px, центр обода — размах 3.5 px, ширина обода — размах 3 px (≤1% от медианы 361 px); фон MAD ≤2.8; силуэт в кадре (union bbox x 296–937 из 960, края не касается)',
            'limbs': 'обе руки читаемы в плоскости кадра; тянущая (правая) рука у подбородка, локоть в сторону; стопы на подставке, шагов нет',
            'bow': 'лук в левой руке весь ролик; стрела возникает без извлечения из колчана; тетива появляется и меняет толщину (артефакт генерации)',
            'artifacts': 'змеиная корона перерисовывается; ролик 5 с против цели 0.50–0.60 с, нужен ретайминг и выборка фаз',
            'videoToMotion': 'прогноз (pose-трекинг не запускался): подходит для пробы video-to-motion верха тела — камера неподвижна (измерено), руки не перекрыты телом, фон ровный; риск — хитон скрывает колени и таз',
        },
        'briefDeviation': {
            'status': 'оценка по кадрам (визуально)',
            'brief': 'бриф 18 §5 MED-LungeAttack: «выпад-„выстрел“ из лука вперёд», фаза (3) — «микровыпад корпусом вперёд»; стартовая и финальная поза — Idle-стойка',
            'clip': 'выстрел направлен вправо по кадру, а не вперёд на камеру — сознательно в промпте (руки в плоскости кадра для трекинга); кадры 0 и 120 — фронтальная Idle-стойка',
            'forwardLeanAtRelease': 'не подтверждён: на ключевых кадрах f088 и f094 положение головы и торса визуально не меняется; наклон по глубине во фронтальной проекции не оценить; не измерялось',
            'rejected': 'поворот всего клипа по yaw к оси «вперёд» не подходит: он развернул бы боком и Idle-стойку в кадрах 0 и 120 и сломал бы переход Idle → Attack → Idle',
            'options': {
                'status': 'предложено',
                'items': [
                    'переносить только верх тела (позвоночник, плечи, руки) с коррекцией ориентации к оси «вперёд»; таз и ноги оставить в Idle-стойке',
                    'либо одна регенерация (≈6 токенов SYNTX) в ¾ с выстрелом по оси камеры, чтобы совпасть с брифом',
                ],
            },
        },
    },
    'HitReact': {
        'cueRef': 'CUE-011 (900 мс), бриф 18 §5 MED-HitReact',
        'order': 3,
        'keyframes': [0, 14, 19, 26, 34, 120],
        'motion': 'вздрагивание: голова и плечи вверх-назад, руки чуть в стороны (кадры ~12–34), второй мягкий откат ~43–64, затем покой',
        'suitability': 'непригоден для video-to-motion без повторной генерации',
        'assessment': {
            'camera': 'стабильна по подставке (нижний край — размах 1 px, центр обода — размах 9.5 px), но фон по краям MAD до 5.8 из-за эффектов',
            'limbs': 'в пиковые кадры удара (12–26) торс и правая рука перекрыты посторонним объектом и красным лучом/брызгами',
            'bow': 'лук в левой руке, не выпадает',
            'artifacts': 'модель дорисовала снаряд/кулак, входящий справа из-за края кадра (кадры 12–21 и 25–26 касаются края), красный луч, радиальные «брызги» и красное пятно-рану на груди до конца ролика, вопреки «no blood, no projectiles» в промпте; сама амплитуда вздрагивания мала',
            'videoToMotion': 'прогноз (pose-трекинг не запускался): ключевые кадры удара заслонены, в фазе пика трекер позы, вероятно, даст мусор; повтор предложен ниже и не выполнен из-за лимита «не больше 4 роликов»',
        },
        'retryProposal': {
            'status': 'предложено',
            'why': 'формулировка «struck by an invisible blow», вероятно, спровоцировала снаряд и VFX',
            'prompt': 'Locked-off static camera, no camera movement, no zoom, no pan, no cuts. Full-body front view of the painted fantasy miniature figure of Medusa come to life, standing on her round black base, entire body and base always visible in frame. She holds the bow in her left hand (on the right side of the image). After one second she flinches in pain: her torso recoils backward, shoulders hunch up, head tilts back, then she recovers into her calm standing pose and stays still. Nothing touches her, nothing enters the frame. No visual effects, no particles, no blood, no wounds, no projectiles. Feet stay planted on the base. Plain neutral gray studio background, even soft lighting.',
            'expectedCostSyntxTokens': 6,
        },
    },
    'DeathSettle': {
        'cueRef': 'CUE-013 (950 мс), бриф 18 §5 MED-DeathSettle',
        'order': 4,
        'keyframes': [0, 24, 36, 44, 56, 120],
        'motion': 'подгиб коленей и присед (~22–44), обрушение вперёд на подставку (~44–60, пик движения кадры 37–41), затем неподвижная низкая поза (~64–120)',
        'suitability': 'ограниченно пригоден (только фаза до кадра ~44)',
        'assessment': {
            'camera': 'стабильна: левый край обода подставки 299–301 px и нижний край 859–860 px во всех кадрах, кроме 56–59 (лук свисает под обод: левый край 358/358/340/327 px, нижний 866/866/865/864 px — строка обода отсчитывается от самого нижнего тёмного пикселя, которым там становится лук); метрики центра и ширины обода (размах 49.5 / 110 px) искажены телом и луком, лёгшими на обод, это не движение камеры',
            'limbs': 'до присяда (~кадр 44) конечности читаемы; в финальной позе тело свёрнуто к камере, руки и ноги под корпусом, основная видимая масса — змеиная корона',
            'bow': 'лук остаётся у левой руки, но в финале деформирован (перекручен, похож на арбалет), это артефакт',
            'artifacts': 'падение вперёд, к камере: глубина, вероятно, неоднозначна для монокулярного трекинга (прогноз); голова и змеи в финале заметно крупнее, чем в стойке (нарушение пропорций); часть тела и лук свисают за обод справа',
            'videoToMotion': 'прогноз (pose-трекинг не запускался): фазу «потеря опоры → присед» можно брать как референс тайминга; складывание и укладку делать только ручной ключевой анимацией',
        },
    },
}

clips = []
for c, e in eval_.items():
    d = f'{A}/MED-{c}'
    raw = f'{d}/syntx'
    mp4 = f'{d}/MED-{c}_kling25_ref.mp4'
    res = jload(f'{raw}/result.json')
    req = jload(f'{raw}/req.json')
    an = jload(f'{d}/analysis.json')['summary']
    pr = subprocess.run(['ffprobe', '-v', 'error', '-show_entries',
                         'stream=width,height,r_frame_rate,nb_frames,duration,codec_name', '-of', 'json', f'{R}/{mp4}'],
                        capture_output=True, text=True, check=True)
    st = json.loads(pr.stdout)['streams'][0]
    prompt = open(f'{R}/{d}/prompt.txt', encoding='utf-8').read().strip()
    assert prompt == res['prompt'].strip() == req['prompt'].strip(), c
    url_md5 = res['url'].rsplit('/', 1)[1].split('_')[0]
    assert url_md5 == hashlib.md5(open(f'{R}/{mp4}', 'rb').read()).hexdigest(), f'{c}: mp4 differs from SYNTX output'
    b0, b1 = bal(f'{raw}/balance_before.json'), bal(f'{raw}/balance_after.json')
    item = {
        'cue': f'MED-{c}', 'cueRef': e['cueRef'], 'generationOrder': e['order'],
        'status': 'референс, не анимация',
        'suitabilityVideoToMotion': {
            'verdict': e['suitability'],
            'status': VISUAL,
            'basis': 'контакт-лист 2 fps и ключевые кадры (просмотр через Read) + измерения камеры/фона/силуэта из analysis.json',
        },
        'service': 'SYNTX (syntx.ai) → Kling', 'aiName': 'kling', 'modelType': 'kling_image2video',
        'parameters': {k: res['settings'][k] for k in ('version', 'mode', 'video_duration', 'native_audio',
                                                        'aspect_ratio', 'temperature', 'multi_shots', 'camera_movement')},
        'syntxChatUuid': req['chat_id'], 'syntxTaskId': res['task_id'],
        'syntxRaw': {'dir': f'{raw}/', 'files': ['req.json', 'gen.json', 'wait.json', 'result.json',
                                                 'balance_before.json', 'balance_after.json'],
                     'note': 'сырые ответы SYNTX MCP; id аккаунта (поля user_id/owner_id/author_id и сегмент user_<id> в URL хранилища) заменён на REDACTED; md5 mp4 = хэш в имени выходного файла result.json.url'},
        'prompt': prompt, 'promptFile': f'{d}/prompt.txt',
        'input': {'path': inp, 'sha256': sha(inp), 'uploadedHashMd5': up['hash']},
        'output': {'path': mp4, 'sha256': sha(mp4), 'bytes': os.path.getsize(f'{R}/{mp4}'),
                   'codec': st['codec_name'], 'durationSec': float(st['duration']), 'fps': st['r_frame_rate'],
                   'frames': int(st['nb_frames']), 'resolution': f"{st['width']}x{st['height']}"},
        'keyframes': [{'frame': n, 'timeSec': round(n / 24, 3), 'path': f'{d}/keyframes/f{n:03d}.png',
                       'sha256': sha(f'{d}/keyframes/f{n:03d}.png')} for n in e['keyframes']],
        'contactSheet': f'{d}/contact-sheet-2fps.png',
        'measurements': {'status': 'измерено', 'file': f'{d}/analysis.json',
                         'rangeNote': '*_range_px — размах (max − min) по всем кадрам, не ±',
                         **{k: an[k] for k in ('border_mad_max', 'base_center_x_range_px', 'base_bottom_y_range_px',
                                               'base_width_range_px', 'fg_touches_edge_frames', 'fg_bbox_union',
                                               'motion_mad_max', 'motion_peak_frames')}},
        'motionSummary': e['motion'],
        'assessment': {'status': 'оценка по кадрам (визуально); числа взяты из measurements', **e['assessment']},
        'cost': {'syntxTokens': round(b0 - b1, 2), 'quotedBeforeRun': 6, 'balanceBefore': b0, 'balanceAfter': b1,
                 'source': f'{raw}/balance_before.json, {raw}/balance_after.json'},
    }
    for k in ('briefDeviation', 'retryProposal'):
        if k in e:
            item[k] = e[k]
    clips.append(item)
clips.sort(key=lambda x: x['generationOrder'])

first = next(x for x in clips if x['generationOrder'] == 1)
man = {
    'schemaVersion': 2,
    'assetId': 'ASSET-MEDUSA-001',
    'route': 'P1.6: модель → видео-референс → скелетный клип → ретаргет (манифест покрывает только шаг «видео-референс»)',
    'created': '2026-09-28',
    'revisions': [
        {'date': '2026-09-28', 'what': 'первая версия (исполнитель VID, P1)'},
        {'date': '2026-09-28', 'what': 'исправления по ревью P1 (VID): «размах N px» вместо «±N px»; выбросы DeathSettle 56–59; статус визуальной оценки пригодности; модель — «дешевейшая из опрошенных»; balanceStart переименован; LungeAttack — отказ от yaw всего клипа; скрипты и сырые ответы SYNTX перенесены в репо'},
    ],
    'language': 'ru',
    'statusVocabulary': ['предложено', 'измерено', 'технически импортировано', 'художественно принято'],
    'overallStatus': 'референсы, не анимация. Ни один ролик не является клипом, не импортирован в Blender/UE и не принят художественно.',
    'cueSource': 'docs/game-design/18-animation-production-brief.md §5 (MED-Idle, MED-LungeAttack, MED-HitReact, MED-DeathSettle; порядок производства Idle → LungeAttack → HitReact → DeathSettle — АВТОР-рекомендация брифа)',
    'inputChoice': {
        'chosen': inp,
        'sha256': sha(inp),
        'why': 'рекомендованный фронтальный ref в docs/art-pipeline/asset-registry.json (sha совпадает); 1024×1024, фигура крупно, полный рост с подставкой, ровный серый фон, лук в левой руке. Нейтральный Blender-рендер (blender/ASSET-MEDUSA-001/preview/rig-idle.png) отклонён: фигура занимает около половины кадра, кисти и лук мельче, что хуже для image-to-video и трекинга.',
        'uploadedTo': 'хранилище SYNTX пользователя (hidden), file uuid ' + up['uuid'],
        'uploadRecord': f'{SESSION}/fileobj.json',
    },
    'modelChoice': {
        'chosen': 'Kling 2.5, kling_image2video, mode standart, 5 с, без звука',
        'costPer5s': 6,
        'why': 'самая низкая цена среди опрошенных моделей: 6 токенов за 5 с, наравне с Kling 2.1 std и Seedance 1.0 Pro-Fast 480p; выбор между равными по цене замером не подкреплён. Неподвижность камеры задана промптом (camera_movement=null) и измерена на пробном ролике.',
        'bodyStabilityComparison': {
            'status': 'предложено / не измерено',
            'text': 'утверждение «по стабильности тела Kling 2.5 std равен только Seedance 1.0 Pro-Fast 480p» не проверялось ни одной генерацией или тестом',
        },
        'priceQuotes': {
            'status': 'получено запросом get-model-info до запуска (через tools/art/syntx_video_refs/patch.cjs); ответы не сохранены. Верификатор 2026-09-28 перепроверил: Kling 2.5 std 5 с = 6, Seedance 1.0 Pro-Fast 480p = 6, Kling 2.6 std = 14. Цена Kling 2.5 std подтверждена и списанием: дельта баланса по каждому ролику = 6',
            'table': 'токены SYNTX за 5–6 с: Kling 2.5/2.1 std 6, Kling 2.6 std 14, Kling 3.0-turbo 25, Kling 2.5 hd 17, Seedance 1.0 Pro-Fast 480p 6 / 720p 10, Seedance 1.0 Pro 720p 11, Seedance 1.5 Pro 720p 7.5, Hailuo 2.3 Fast 768p 6 с 9, Hailuo 2.3 14, Hailuo-02 14, Wan 2.6 i2v Flash 720P 10, Wan 2.6 i2v 35, Wan 2.7 i2v 30, Grok i2v 480p 6 с 12, Veo 3.1 Lite 13, Runway Gen-4 Turbo 14, Gen-4.5 i2v 14',
        },
        'notPriced': {
            'notable': ['seedance-2.0', 'seedance-2.5', 'hailuo-3.0', 'kling_o1_image2video'],
            'notableNote': 'активные модели с входом-изображением, более новые версии опрошенных семейств; цены не запрашивались',
            'allImageInputWithoutPriceRecord': not_priced,
            'allNote': 'все активные модели снимка каталога, принимающие изображение, для которых нет записи цены; часть из них не i2v в строгом смысле (v2v, r2v, video edit, keyframes). «Grok i2v» в таблице не различает grok_i2v и grok_15_i2v, поэтому обе в список не включены',
            'catalogSnapshot': f'{SESSION}/models_*.json (list-models SYNTX, 2026-09-28)',
        },
        'trial': 'первым сгенерирован MED-LungeAttack (самый сложный: лук, обе руки); камера по подставке неподвижна (размах центра обода 3.5 px, нижнего края 0 px), поэтому остальные три запущены с теми же параметрами',
    },
    'budget': {
        'limitSyntxTokens': 120,
        'spentSyntxTokens': round(sum(x['cost']['syntxTokens'] for x in clips), 2),
        'spentStatus': 'измерено: сумма дельт balance_before/after по четырём успешным генерациям',
        'balanceBeforeFirstSuccessfulGeneration': first['cost']['balanceBefore'],
        'balanceBeforeFirstSuccessfulGenerationSource': f"{first['cost']['source'].split(',')[0]} (записан в 11:27:12 +05 по времени scratch-файла, перед генерацией MED-LungeAttack)",
        'balanceAtTaskStart': None,
        'balanceAtTaskStartNote': f'не записан: чат SYNTX создан в 06:16:06Z (11:16 +05, {SESSION}/chat.json), первая запись баланса — только в 11:27:12 +05, после отклонённых запросов',
        'balanceEnd': clips[-1]['cost']['balanceAfter'],
        'clipLimit': 4, 'clipsGenerated': len(clips),
        'failedRequests': {
            'count': 3,
            'countSource': 'отчёт исполнителя; ответы 422 не сохранены',
            'reason': 'API 422 (формат settings.file_urls) до генерации',
            'chargeStatus': 'отсутствие списания не подтверждено записью баланса: баланс до этих запросов не записан',
        },
        'note': 'Покупок нет. Дельта баланса по каждому успешному запуску = 6 и совпадает с ценой get-model-info.',
    },
    'measurementMethod': 'tools/art/analyze_video_ref.py: ffmpeg-декодирование всех кадров во временную папку (удаляется после чтения) → numpy; фон = медиана углов кадра 0; маска фигуры max|RGB−фон|>28; подставка = пиксели яркости <80 в нижних 25% кадра, ширина и центр по строке обода на 8 px выше нижнего тёмного края; стабильность фона = MAD краевой полосы 6% против кадра 0; motion_mad = средняя |Δ| соседних кадров; *_range_px = размах (max − min). Измерены только камера, фон, рамка силуэта и энергия движения. Пригодность для video-to-motion, видимость конечностей и поведение трекера — визуальная оценка по контакт-листам и ключевым кадрам (Read, PNG отрисовался) и прогноз; pose-трекинг не запускался.',
    'reproducibility': {
        'scripts': {
            'generate': 'tools/art/syntx_video_refs/gen.sh (реальный запуск тратит ≈6 токенов SYNTX; DRY_RUN=1 — только req.json, без трат)',
            'priceQuote': 'tools/art/syntx_video_refs/patch.cjs (добавляет version/native_audio в get_model_info)',
            'importRawResponses': 'tools/art/syntx_video_refs/import_runs.py (копирует сырые ответы из scratch с заменой id аккаунта на REDACTED)',
            'manifest': 'tools/art/syntx_video_refs/build_manifest.py',
            'measurements': 'tools/art/analyze_video_ref.py',
        },
        'rawResponses': f'{A}/MED-<Cue>/syntx/ и {SESSION}/',
        'commands': [
            "цена (бесплатно): SYNTX_EXTRA_Q='{\"version\":\"2.5\",\"native_audio\":\"false\"}' NODE_OPTIONS='--require tools/art/syntx_video_refs/patch.cjs' node <syntx_mcp.cjs> get-model-info '{\"ai_name\":\"kling\",\"model_type\":\"kling_image2video\",\"mode\":\"standart\",\"video_duration\":5}'",
            'генерация (тратит ≈6 токенов): SYNTX_CHAT_ID=<uuid чата> SYNTX_FILEOBJ=<объект upload-files вне репо> bash tools/art/syntx_video_refs/gen.sh LungeAttack art/animation-refs/ASSET-MEDUSA-001/MED-LungeAttack/prompt.txt',
            f'проверка запроса без трат: DRY_RUN=1 SYNTX_WORK=<scratch> SYNTX_FILEOBJ={SESSION}/fileobj.json SYNTX_CHAT_ID=5ac4e224-2019-46c2-b4a2-8d5804835b0e bash tools/art/syntx_video_refs/gen.sh <Cue> {A}/MED-<Cue>/prompt.txt — req.json совпадает с MED-<Cue>/syntx/req.json',
            'сырые ответы → репо: python tools/art/syntx_video_refs/import_runs.py --src <scratch>',
            'замеры (в папке cue): python ../../../../tools/art/analyze_video_ref.py MED-<Cue>_kling25_ref.mp4 analysis.json',
            'ключевой кадр: ffmpeg -i <clip>.mp4 -vf "select=eq(n\\,48)" -vsync 0 -frames:v 1 keyframes/f048.png',
            'контакт-лист: ffmpeg -i <clip>.mp4 -vf "fps=2,scale=320:-1,tile=5x2" -frames:v 1 contact-sheet-2fps.png',
            'манифест: python tools/art/syntx_video_refs/build_manifest.py',
        ],
    },
    'clips': clips,
    'nextSteps': {
        'status': 'предложено',
        'items': [
            'Проба video-to-motion только на MED-LungeAttack и только для верха тела (позвоночник, плечи, руки) с коррекцией ориентации к оси «вперёд»; поворот всего клипа по yaw отклонён (briefDeviation). Сервис не выбран, выбор и стоимость фиксировать отдельно.',
            'MED-LungeAttack: альтернатива — одна регенерация (≈6 токенов) в ¾ с выстрелом по оси камеры, чтобы совпасть с брифом 18 §5.',
            'MED-HitReact: одна повторная генерация по retryProposal (≈6 токенов), если лимит «4 ролика» будет снят.',
            'MED-Idle и фазу укладки MED-DeathSettle ставить ключевой анимацией в Blender по брифу; видео использовать как референс тайминга.',
            'Ретаргет на риг Medusa и ретайминг под окна CUE не начаты; «технически импортировано» и «художественно принято» не заявляются.',
        ],
    },
}
with open(f'{R}/docs/art-pipeline/animation-refs/manifest.json', 'w', encoding='utf-8', newline='\n') as f:
    json.dump(man, f, ensure_ascii=False, indent=2)
    f.write('\n')
print('ok', json.dumps(man['budget'], ensure_ascii=False))
