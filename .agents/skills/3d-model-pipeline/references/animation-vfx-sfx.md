# Анимация, VFX и SFX — глобальный стандарт (этап 5 пайплайна)

Статус: действует для всех новых ассетов `ASSET-<NAME>-001` (герой / существо / проп). Этап 5 конвейера:
0 заявка → 1 концепт → 2 генерация в Tripo → 3 приёмка модели (коэффициент ≥ 8,0) → 4 доработка в Blender
(≤ 2 цикла) → 4.5 H2-bake и look-dev (SKILL.md §4) → **5 анимация и VFX/SFX (этот документ)** → 6 упаковка
под UE (`references/ue-import-package.md`).

Источники истины: `docs/art-pipeline/rig/rig-contract.json` → `docs/unreal/contracts/cue-dispatcher/cue-table.json` → бриф
`docs/game-design/18-animation-production-brief.md` §0 → реестры `03-asset-registry.csv` / `03-sound-registry.csv` →
`docs/art-pipeline/BLENDER-MODEL-HANDBOOK.md` §2.6–2.8. Всё внешнее помечено «(не проверено)».

---

## 1. Скелетный стандарт

Контракт: `docs/art-pipeline/rig/rig-contract.json` — schema `unmatched.rig-contract/2`, revision
`v2-2026-09-29`, статус «предложено». Человекочитаемо: `docs/art-pipeline/rig/RIG-CONTRACT.md`,
`BLENDER-MODEL-HANDBOOK.md` §2.6. Проверка: `tools/tripo-pipeline/anim/validate_clip.py --skeleton=UM_HUMANOID_17_v2`.

### 1.1 Иерархия (единственный допустимый риг гуманоида/существа)

```
SKEL_UM_Humanoid   ← объект арматуры; в UE становится костью 0 (носитель root motion); pose-кости нет
└─ root            ← опора на полу; pose-ключи = 0; НИКОГДА не ключуется
   └─ hips
      ├─ spine
      │  ├─ head
      │  ├─ arm_upper.L → arm_lower.L → hand.L [→ weapon.L]
      │  └─ arm_upper.R → arm_lower.R → hand.R [→ weapon.R]
      ├─ leg_upper.L → leg_lower.L → foot.L
      └─ leg_upper.R → leg_lower.R → foot.R
```

| Правило | Значение | Источник |
|---|---|---|
| Объект арматуры | ровно `SKEL_UM_Humanoid` у всех героев; другое имя (`SKEL_Medusa`, `SKEL_S05_*`) в v2 = FAIL | rig-contract.json `armature_object` |
| Кости | 16 базовых + 1 кость оружия своей стороны; в UE `.` → `_` и + кость 0: 18 костей (17 у Harpy) | rig-contract.json `bones`, `ue_names` |
| Кость оружия | Medusa `weapon.L` (лук), Arthur и Merlin `weapon.R` (меч/посох), Harpy — нет (удар когтями) | rig-contract.json `characters` |
| Rest pose | поза миниатюры, в которой смоделирован меш (bind = rest); НЕ T/A-поза | rig-contract.json `rest_pose` |
| Веса | ≤ 4 влияния на вершину, нормализованы, веса < 0,01 удаляются, снап к 1/255; оружие — 100 % на свою кость | HANDBOOK §2.6 |
| Запрещено | пальцы, twist, clavicle, neck, leaf-кости, одно имя `weapon`, масштаб кости ≠ 1 | HANDBOOK §2.6 |
| Расширения (только по решению) | `crown_snake.NN` (≤ 4, поворот ≤ 15°), `cloth_front/back`, `wing_tip.L/R` — все со статусом «предложено, не реализовано» | rig-contract.json `optional_extensions` |
| Harpy | крылья = цепочки `arm_upper → arm_lower → hand`; гуманоидные клипы на Harpy НЕ переносятся — авторить отдельно | rig-contract.json `harpy_wings` |

**Покрытие контракта (гейт этапа 0).** UM_HUMANOID_17_v2 описывает гуманоида: 2 руки, 2 ноги, 1 голова,
без хвоста и шеи; расширения (`crown_snakes.NN` ≤ 4 листовых костей, `cloth_front/back`, `wing_tip.L/R`)
четвероногих и многоголовых НЕ покрывают. `validate_clip.py --character` принимает только
`Medusa|Arthur|Merlin|Harpy`; `rig_rules.py` на неизвестного персонажа поднимает KeyError. Ассет с непокрытой
анатомией (например, Цербер — четвероногий с тремя головами) на этап 5 не заходит: остановка и эскалация
пользователю ещё на этапе 0 (поле RIG заявки, SKILL.md §6) с вариантами — (а) новая версия контракта
`unmatched.rig-contract/3` с четвероногим скелетом + правка `rig_rules.py`/`validate_clip.py` под нового
персонажа, (б) отказ от ассета. «Продление контракта» в обход этой процедуры запрещено; надевать
четвероногого на UM_HUMANOID_17_v2 нельзя — валидатор его не примет, а молчаливая подгонка даст сломанный риг.

### 1.2 Единицы, оси, масштаб

| Величина | Значение |
|---|---|
| Единица Blender | 1 unit = 1 м (Metric, Unit Scale 1.0); клетка доски = 1 м = 100 uu |
| Оси Blender | Z-up, лицо в −Y (авторский кадр); в FBX и UE — +X (пресет UM_FBX_v1, поворот +90° вокруг Z, допуск facing 0° ± 10°) |
| Зеркало координат | ue(x, y, z) = blender_export(x, −y, z) |
| Сторона `.L` | левая сторона персонажа = +X в Blender при взгляде персонажа в −Y; UE переименует в `_L`/`_R` |
| Импорт в UE | строго `import_uniform_scale = 1.0`; ручной Scale при импорте — дефект |
| Pivot | центр низа подставки (0, 0, 0) |

### 1.3 Политика root motion

- По умолчанию **in place**: объект арматуры (кость 0 UE) и pose-кость `root` не ключуются; дрейф ≤ 0,5 % роста
  (rig-contract.json `root_motion`; замер `rootDeltaUU = 0` — AN-18, 1200 строк `clippose`).
- При импорте клипа: `bForceRootLock = true`, `bEnableRootMotion = false` (`h2anim_ue.py` → `review/ue_py/import_clips.py`;
  rig-contract.json `ue_import.clip_import.by_root_policy`).
- Root motion включается только для отдельного клипа по явному решению (`enable_root_motion = true` +
  `ConsumeRootMotion` в акторе); сейчас таких клипов нет. Перемещение по доске — скольжение актора, walk/run-клипов нет.

### 1.4 Ретаргет

- Каждый клип авторится на риге своего героя; общий скелет/IK Retargeter на четверых **не доказан** — тестовый риг
  обязан доказать 6 пунктов брифа 18 §9, решение об общем скелете/CompatibleSkeletons — после прототипа
  (rig-contract.json `ue_import.skeleton_asset`).
- Заготовка: `ik_chains` контракта (Root, Spine, Head, LeftArm, RightArm, LeftLeg, RightLeg + WeaponL/R fk_only,
  retarget root = `hips`) — статус «предложено, в UE не собрано». Имена сознательно совпадают с цепочками IK Rig UE5
  Manny для AutoMapChains; авто-генерация цепочек у Epic с 5.4 — внешняя практика (не проверено).
- Внешние клипы (Tripo/Mixamo/SMPL): до перекладки в контракт допускается только проверка `--retarget-map=`
  (карты в rig-contract.json `retarget_maps`, все «не проверено»); карта не заменяет перекладку.
- В проекте нет AnimMontage, Blend Space и AnimBlueprint: клипы играются напрямую кодом
  `AS08FighterActor::PlayHeroClip` (S08FighterActor.cpp:924). ABP-стейт-машину не заводить без отдельного решения.
- Новый меш надевается на существующий канонический скелет героя: `tripo_pipeline.py` профиль `skeletal-adopt`,
  опция `ue.target_skeleton` — иерархия нового H2LD-меша обязана точно повторить иерархию скелета.

---

## 2. Набор анимаций

### 2.1 Базовый набор D-11 — ровно 16 клипов

4 клипа × 4 персонажа (King Arthur, Merlin, Medusa, Harpy); три гарпии делят один набор. Дополнительных
optional-клипов нет (бриф 18 §0.1, строки 17–39; `docs/art-pipeline/animation-library/README.md`).

| Персонаж | Idle | LungeAttack | HitReact | DeathSettle | Кадр контакта LungeAttack |
|---|---|---|---|---|---|
| King Arthur | 60 к. = 2500 мс | 14 к. = 583 мс | 10 к. = 417 мс | 21 к. = 875 мс | к. 7 = 292 мс |
| Merlin | 72 к. = 3000 мс | 583 мс | 417 мс | 875 мс | к. 8 = 333 мс |
| Medusa | 56 к. = 2333 мс | 583 мс | 417 мс | 875 мс | к. 8 = 333 мс (выпуск стрелы) |
| Harpy (×3 фигуры) | 48 к. = 2000 мс | 583 мс | 417 мс | 875 мс | к. 7–9 = 292–375 мс |

- **fps 24** — факт конвейера: `"fps": 24` во всех `build-profiles/<hero>-h2anim.json` и константа `ClipFps = 24.0f`
  (S08HeroesV2.h:143). Длительности зашиты в C++ одинаково для всех героев (`ExpectedClipSeconds`,
  S08HeroesV2.cpp:157-165; Idle per hero — `Specs()`, S08HeroesV2.cpp:105-108). Длительности HitReact 417 мс и
  DeathSettle 875 мс — предложение anim-v2 (4), `target_status: open` (не менять без решения).
- **Числа для НОВОГО героя.** Общие для всех клипов длительности LungeAttack 583 мс / HitReact 417 мс /
  DeathSettle 875 мс — константы C++ (14/10/21 кадров @ 24 fps): новый герой берёт их теми же. Пер-геройные
  величины — Idle (у четырёх: 2,0–3,0 с) и LungeContactFrame (7 или 8): их нет в конвейере, это
  гейм-дизайн-решение; задаются в `build-profiles/<hero>-h2anim.json` и в строке `Specs()` на этапе 6.
  Нет готового решения — эскалация пользователю до начала авторинга (автоматически брать число соседа
  нельзя: у героев они разные без правила вывода).
- Допуск длительности: ±0,05 с в Blender, ±0,02 с в автотесте UE (HANDBOOK §2.8).

### 2.2 Роли клипов и правила авторинга

| Роль | Клипы | Кадр 0 | Последний кадр |
|---|---|---|---|
| `idle` | Idle | = rest | = rest (первая и последняя поза совпадают; шов петли ≤ 0,5 % роста) |
| `oneshot` | LungeAttack, HitReact | = rest | = rest |
| `terminal` | DeathSettle | = rest | финальная поза, держится фигурой до растворения |

Общие правила (HANDBOOK §2.8, rig-contract.json `clip_boundaries`): in place; ключи `rotation_quaternion` на всех
костях кроме `root`; `location` только на `hips`; интерполяция LINEAR; **один FBX на клип с обязательным узлом
меша** — без меша legacy-импортёр UE не создаёт AnimSequence.

### 2.3 Нейминг и пути

| Что | Формат | Пример |
|---|---|---|
| Клип (UE, AnimSequence) | `AM_<Hero>_<Clip>` — БЕЗ суффикса `_Anim` (суффикс был у блок аутов S05) | `AM_KingArthur_LungeAttack` |
| UE-папка клипов | `/Game/PipelineCandidates/<Hero>/H2Anim/` (S08HeroesV2.cpp:152-155 `ClipPath`) | `/Game/PipelineCandidates/Harpy/H2Anim/AM_Harpy_Idle` |
| Канонический скелет | `/Game/PipelineCandidates/<Hero>/Rig/SK_<Hero>_Skeleton` | `SK_Medusa_Skeleton` |
| FBX на диске | `art/pipeline-candidates/ASSET-<ID>-001/20260929-h2anim/export/AM_<Hero>_<Clip>.fbx` | `.../ASSET-MERLIN-001/20260929-h2anim/export/AM_Merlin_Idle.fbx` |
| Реестр | строка на каждый клип в `docs/game-design/visual/03-asset-registry.csv` (id `AM_*`) | статус, rollback-флаг, бюджет |
| Спека прогона | `art/pipeline-candidates/ASSET-<ID>-001/build-profiles/<hero>-h2anim.json` (schema `unmatched.h2anim-spec/1`) | см. шаблон §7.1 |

### 2.4 Кадр контакта и AnimNotify `Contact`

- В каждом LungeAttack обязателен AnimNotify с именем **`Contact`** (`US08ContactAnimNotify`;
  `ContactNotifyName`, S08HeroesV2.h:145; `ClipFps` — строка 143). Время берёт `NotifyContactSeconds`; фолбэк —
  `ProfileContactSeconds = LungeContactFrame / ClipFps` (S08HeroesV2.cpp:167); реестр 03 подтверждает notify (коммит `07f606bd`).
- От контакта отсчитываются: HitReact цели, красная заливка 450 мс (летально 550), «−N» +60 мс, HP +80 мс,
  `duration_ms` 900 мс события CUE-011 (бриф 18 §0.2).

### 2.5 Связь клип ↔ CUE (норма — `cue-table.json`, revision `fx-p4-2026-10`)

| Событие | Клип | Когда |
|---|---|---|
| CUE-008 «объявление атаки» | клипа нет (прицел + шевроны 600 мс) | — |
| CUE-011 «урон» | LungeAttack атакующего — вступление; HitReact цели | LungeAttack стартует после слэма CUE-010 + пауза «счёт» 300 мс; HitReact цели — в кадр контакта |
| CUE-013 «боец повержен» | DeathSettle | после HitReact (450 мс от контакта), затем неподвижность и растворение «пепел»; фигура исчезает ≈ 2125 мс от контакта; гарпия при смерти играет HitReact, затем DeathSettle |
| Idle | без запускающего CUE (фон `state:Idle`; CUE-017 ставит на паузу) | — |

### 2.6 Расширение набора (ролевые клипы)

- D-11 закрыт: из 32 событий реестра 28 не требуют скелетной анимации — они закрываются VFX, материалом или
  движением актора (animation-library README). Optional-клипы «про запас» не делаются.
- Новый ролевой клип заводится только под конкретную игровую потребность и требует ВСЕГО списка: слот в
  `docs/art-pipeline/animation-library/clip-manifest.json`; спека в `build-profiles/<hero>-h2anim.json`; слот в C++
  (`S08HeroesV2::EClip`, `ClipPath`); строка CUE в `cue-table.json` (`clip.sequence_by_fighter`); строки реестра 03.
- Статусы библиотеки: `proposed → measured → technically_imported → artistically_accepted` (+ `draft_test`,
  `rejected`); `artistically_accepted` требует `acceptance_evidence` (clip-manifest.schema.json).
- Текущий статус: все 16 клипов художественно приняты по делегированию 2026-10-09 (ВР-17, ВР-60) — листы AN-18 из
  пакета `2233b140` (`docs/game-design/evidence/VISUAL/AN-18/README.md`). Откат — `-S08HeroesLegacy` (S08HeroesV2.h:32).

---

## 3. Производство клипов (H2Anim) и экспорт

Полный путь героя (H2 bake → look-dev → TeamAccent → **H2Anim** → UE) — HANDBOOK §4.5; здесь — стандарт этапа 5.
H2-bake и look-dev — отдельный этап 4.5 карты пайплайна (SKILL.md §3–4): на вход этапа 5 нужен
`SK_<Hero>_H2.fbx` из h2-bake-прогона и H2LD-набор look-dev; кто их делает и критерии выхода — там.

1. **Спека** `unmatched.h2anim-spec/1` в `build-profiles/<hero>-h2anim.json`: цель `SK_*.fbx` + sha256 (при
   изменении FBX `clip_author.py` отказывает), `ue.skeleton` / `ue.clips_folder`, `fps`, клипы с кадрами/ролями/
   ключами/волнами/IK. Шаблон — §7.1. Референсы движения — видео в `art/animation-refs/<ASSET>/<CLIP>/`
   (SYNTX Kling/Seedance), манифест `docs/art-pipeline/animation-refs/manifest.json`. Их производство —
   внешний платный сервис вне этого скилла (стадии генерации видео и лимит здесь не описаны): каждую платную
   генерацию SYNTX подтверждает пользователь, списание пишется в общий журнал кредитов
   (`tools/art/syntx_video_refs/ledger_append.py`, окно `syntxTokens` в credits-ledger.json). У нового ассета
   референсов нет — как их производить (или решение авторить по ключевым позам без видео) решает
   пользователь до начала авторинга клипов; в репозитории есть наборы только четырёх героев.
2. **Прогон и валидация** (Blender только headless, `blender -b`; UE-шаги под блокировкой `C:/tmp/ue-editor.lock`):

```bash
python tools/tripo-pipeline/anim/h2anim_run.py art/pipeline-candidates/ASSET-<ID>-001/build-profiles/<hero>-h2anim.json
# внутри: авторинг clip_author.py → validate_clip.py --skeleton=UM_HUMANOID_17_v2 --character=<Hero> → clip_contact_check.py
MSYS_NO_PATHCONV=1 python tools/tripo-pipeline/anim/h2anim_ue.py skeleton|import|measure <spec>   # canonical skeleton + clips
python tools/tripo-pipeline/anim/clip_manifest.py build && python tools/tripo-pipeline/anim/clip_manifest.py check
```

3. **Экспорт FBX** — только пресет `blender/_tools/presets/UM_FBX_v1.json` (поворот +90° Z, `bake_anim` со всеми
   ключами, детерминизм: время FBX 2000-01-01). Один FBX на клип, с узлом меша. Детали единиц/осей/флагов —
   `references/ue-import-package.md` (не дублируются здесь).
4. **Импорт в UE** — `h2anim_ue.py import` → `review/ue_py/import_clips.py`: animation-only, legacy `FbxFactory`,
   `bForceRootLock = true`, `bEnableRootMotion = false`, импорт на канонический скелет героя; существующий клип
   удаляется и импортируется заново (decisions/2026-09-29-anim-v2-decisions.md E).

`validate_clip.py` PASS = техническое соответствие контракту, НЕ художественная приёмка (VALIDATION.md).

---

## 4. VFX

### 4.1 Стиль (ВР-19, binding)

«Печатный»: плоские формы с жёсткой кромкой, 2–3 тона из токенов, коротко (≤ 600 мс), без дыма, бликов и линз;
эффект живёт на фигуре и клетке, камера неподвижна (decisions/2026-10-06-visual-delegated-decisions.md).

### 4.2 Сокеты (создаёт UE-импорт; в Blender их НЕ делать)

| Сокет | Кость | Смещение | Назначение |
|---|---|---|---|
| `Weapon` | `weapon_L` (Medusa) / `weapon_R` (Arthur, Merlin); Harpy — по профилю (точка удара когтей) | (0, 0, 0) | дуги оружия, FX способностей (CUE-014 ArthurArc) |
| `Head` | `head` | прогноз сборки (`location_uu: null` → правило ниже) | evidence-съёмка, оверлеи |
| `Root`, `Base` | корень актора / подставка (не скелет; `cue-table.json` `sockets_from`) | — | MedusaVortex → Root, HealMotes → Base |

Правила: сокет вешается на меш, не на скелет — общий скелет героя не мешает; создаются сокеты UE-стадией
импорта через MCP `skeletal.add_socket` + `skeletal.set_socket_transform` (`tools/tripo-pipeline/tripo_pipeline.py:2525-2534`:
сначала `get_socket_names`/`remove_socket`, потом план сокетов профиля). Конкретный UE C++ API за этими MCP-вызовами
в репозитории не задействован (не проверено). Offset в UE bone-space = (x, −y, z) от Blender bone-space × 100; проверка
живым `get_socket_location` ± 0,05 uu; фигура
без сокета `Head` выпадает из evidence-съёмки. Расхождение Harpy `Weapon`: профиль `foot.R` против «кисти»
контракта — открыто (HANDBOOK §10).

### 4.3 Нейминг и структура (проверено по `unreal/Unmatched/Content/S08/FX/`)

| Префикс | Тип | Примеры |
|---|---|---|
| `NS_FX_*` | Niagara System | `NS_FX_Dust`, `NS_FX_HitStar`, `NS_FX_AshEmbers`, `NS_FX_ArthurArc`, `NS_FX_MedusaVortex` |
| `M_FX_*` / `MI_FX_*` | мастер-материал / инстанс | `M_FX_Print` (+ `M_FX_Print_Overlay`), `MI_FX_HitStar` |
| `T_FX_*` | текстуры, флипбуки (rows×cols в имени) | `T_FX_HitStar_4x2`, `T_FX_ArthurArc_4x4` |
| `SM_FX_*` | меши FX | — |
| `NET_UM_*` | UNiagaraEffectType | `NET_UM_Board`, `NET_UM_Combat` (`/Game/S08/FX/EffectTypes/`) |

Папки: `/Game/S08/FX/{Board,Combat,Systems,EffectTypes,Materials,Textures,Meshes}`.

### 4.4 Реестр CUE → Niagara (код — истина; S08CueFx.cpp:60-73, зеркалит cue-table.json)

| CUE | Система | EffectType | Сокет | Бюджет спрайтов |
|---|---|---|---|---|
| CUE-007 | `NS_FX_Dust` | Board | world (без сокета) | 5 |
| CUE-008 | `NS_FX_AttackChevrons` | Board | world | 3 |
| CUE-011 | `NS_FX_HitStar` | Combat | world (точка контакта) | 1 |
| CUE-012 | `NS_FX_HealMotes` | Combat | `Base` | 5 |
| CUE-013 | `NS_FX_AshEmbers` | Combat | world | 40 |
| CUE-014 (KingArthur) | `NS_FX_ArthurArc` | Combat | `Weapon` | 1 |
| CUE-014 (Medusa) | `NS_FX_MedusaVortex` | Combat | `Root` | 2 |

CUE-014 per-hero: ключ героя выбирает систему и сокет (FX-28). Все системы `prewarm = true`.

### 4.5 Технические правила

- **Детерминизм (FX-04):** сид = `CRC32(имя ассета) & 0x7FFFFFFF` — чистая функция имени, никогда время/кадр
  (S08CueFx.cpp:95-98); эмиттеры CPU, fixed bounds, шум донорских шаблонов обнулён; спавнер `S08CueFxSpawner` —
  прогрев + пул AutoRelease.
- **Бюджеты (ВР-25):** ≤ 3 одновременных боевых систем, ΔGPU ≤ 1 мс на худшем наборе.
- **Цвета** — только из `hud-style-tokens.json` (тела `fx.gold/fx.heal/fx.dust/fx.impact`, кромка `card.glyph`);
  гейт G-TOKENS запрещает hex-литералы в графе. Сборка: `python tools/art/fx/fx_import.py` (мастера, MI из плана,
  флипбуки). Бюджет инструкций замеряется Stats-ом, жёстко не задан (плоская печать вышла 191–229).
- **Привязка к сокету:** аттач через код спавнера; внешняя практика Epic «частицы следуют за сокетом каждый кадр» — local space эмиттера или Skeletal Mesh sampling в Update stage (не проверено).
- **Поле (не-Niagara FX):** подложки хода `MI_FX_*` на `M_S08_GameLayerUnlit`, дуги цели `MI_FX_TargetArc`
  (cream `#F9EBDB` + тёмная кромка), кольцо выбора `MI_FX_SelectionRing`.
- **Откат:** весь боевой VFX — `-S08FxLegacy` (S08CueFx.cpp:38-41); полевые FX FX-07…FX-15 — `-S08MovePlatesLegacy`,
  `-S08TargetArcLegacy` и др.; заливка удара — `-S08HitTintLegacy`; fade вместо пепла — `-S08DissolveFade`.
  Трейс `ARTLOOK …` пишет фактический вид (`fx=/hitFx=/death=`).

---

## 5. SFX

### 5.1 Нейминг и банк

| Что | Правило | Пример |
|---|---|---|
| SoundWave | `SW_<ID>`, где `<ID>` — ID реестра без дефисов | `SW_UI_CLICK_01`, `SW_CMB_HIT_BLADE_01` |
| MetaSoundSource | `MS_<ID>` — наборы вариаций (`Random Get` без повторов), тема карты (слои + `CombatMix` 0…1, `FinalStand`) | `MS_CMB_HIT_BLADE` |
| Реестр | `docs/game-design/audio/03-sound-registry.csv` (id, категория, CUE, bus, priority, concurrency, license) | `CMB-HIT-BLADE` |
| Банк | `S08AudioBank`: ID банка → варианты soft-paths; таблица ГЕНЕРИРУЕТСЯ `python tools/audio/ue_bank.py` — код путей не хардкодит; анти-повтор `FS08SoundBag`; VO — `FS08VoLine` | `UI-SELECT`, `VO-ARTHUR-ATTACK` |
| Пути в UE | `/Game/Audio/{Music,Stings,UI,Cards,Board,Combat,Death,FX,Amb,VO}/...`; удержание в cook — `+DirectoriesToAlwaysCook=(Path="/Game/Audio")` в `Config/DefaultGame.ini` | — |

SoundWave / SoundCue / MetaSound взаимозаменяемы: диспетчер принимает любой `USoundBase` (cue-table
`asset_path_rule`). На срез 2026-10-09 в `Content/Audio` 346 `SW_*` и 0 `MS_*` (проверено find): MetaSound
спроектирован, ассетами не подтверждён; внешняя рекомендация «MetaSound — по умолчанию для нового кода» (не проверено).

### 5.2 Форматы файлов (02-audio-design.md §5.5)

| Что | Значение |
|---|---|
| Исходники | WAV 48 кГц / 24 бит ВНЕ git: `C:/tmp/audio-src/<id>/` + `manifest.json` (sha256, лицензия, дата) |
| Импорт в UE | WAV 48 кГц / 16 бит (24 бита Epic конвертирует без дизеринга) |
| Каналы | моно — UI/SFX/VO; стерео — музыка/стинги/постели |
| Петли | ровно N тактов, шов на нуле, «завёрнутый хвост»; проверка — разница RMS и спектра на 100 мс вокруг шва |

### 5.3 Микс проекта (AU-S5)

`US08MixLimiterPreset` на главном сабмиксе (`InstallMasterLimiter`, S08FlowGameModeAudio.cpp:872-897):
make-up **+5,0 дБ**, look-ahead пиковый лимитер с потолком **−1,5 dBFS** (true peak ≤ −1 dBTP); цель микса
**−20 ±2 LUFS-I**. Откат — `-S08MixLegacy` (отключает и лимитер, и make-up); override `-S08MixMakeupDb=` зажат
в −12…+12. Итоговую громкость проверяет запись партии (`tools/audio/mix_check.py`), не M max ассета.

Loudness-карта (выборка, полная — 02-audio-design.md §5.3): музыка L1+L2 −23 LUFS; VO −19 ±1 LUFS TP ≤ −3 dBTP;
удар −12 ±1; выпад/блок −16 ±2; шаги −24 ±2; UI-клик −18 ±2; постель окружения −38 LUFS. Одновременность (§5.4):
удар (CUE-011) ≤ 2, шаг (CUE-007) ≤ 1, resolution `StopOldest`; всего ≤ 48 голосов, при превышении первыми уходят
окружение и шаги.

### 5.4 Когда звук вешается на клип (Anim Notify), а когда на VFX

- Звук всегда вешается на **CUE-событие** (блок `sfx` в `cue-table.json`: `sound`, `bank`, `sound_class`,
  `priority`, `concurrency`) — не внутрь клипа и не внутрь Niagara-системы.
- Anim Notify в клипе используется только для **тайминга**: notify `Contact` в LungeAttack задаёт момент, к которому
  диспетчер запускает звук удара, HitReact и заливку (§2.4). Другие notify не заводятся без нужды.
- Скорость анимации не меняет длительность/высоту звука (§5.6): LungeAttack масштабируется — звук нет; «нет
  выпада → нет свиста», шаги прыжком → один звук посадки. Reduced motion звук не трогает.
- Каждый значимый звук обязан иметь визуальный дубль в UI (§5.7); новых звуков без дубля не добавлять.
- Прослушивание/приёмка на слух — за пользователем; агент звук на слух не принимает (02-audio-design.md §7).

---

## 6. Приёмка этапа 5

### 6.1 Модель приёмки — та же, что на этапе 3

Приёмщик — модель «Opus xhigh» или «Sol 6.1 xhigh». Профиль внешний (SKILL.md §2): нет предоставленного
пользователем способа его вызвать — остановка и эскалация до приёмки; валидаторы не заменяют приёмщика и
приёмщиком не становятся. Коэффициент 0–10 по взвешенной рубрике; порог **8,0**.
Ниже порога — доработка (правки анимации в Blender силами «Opus xhigh»), максимум **2 цикла** «правка →
повторная приёмка», дальше эскалация пользователю. Валидаторы (`validate_clip.py`, `clip_contact_check.py`) —
вход приёмки, не её замена: PASS ≠ художественная приёмка.

### 6.2 Измеримые входы рубрики (считаются скриптами, не на глаз)

| Метрика | Порог | Инструмент |
|---|---|---|
| Деформация `skin_stretch` | ребро > 5× rest и > 2 % роста, видимое с 1 из 24 направлений = FAIL | `clip_contact_check.py` |
| Пересечения (оружие ↔ тело; конечности/крылья ↔ корпус, голова, ноги) и скольжение подошвы | новая область или рост > 3× + 20 пар = FAIL; подошва ≤ 0,5 % роста | `clip_contact_check.py` (BVH) |
| Дрейф root (in place) | = 0 (замер `rootDeltaUU`) | `h2anim_ue.py measure`, трейс `clippose` |
| Шов петли Idle | ≤ 0,5 % роста | `validate_clip.py --loop=true` |
| Длительность | ±0,05 с Blender / ±0,02 с UE-автотест | `validate_clip.py --expect-duration` |
| Контакт | notify `Contact` на кадре профиля (F-03) | `NotifyContactSeconds` vs `ProfileContactSeconds` |
| Силуэт в движении | листы поз K1 / K2×1,6 обеих досок, цвет/серый/дейтеранопия | `tools/art/anim/clip_review_sheet.py` (формат AN-18) |

### 6.3 Рубрика коэффициента (предложение этого документа; веса согласуй при первом применении)

| Критерий | Вес | Что оцениваем |
|---|---|---|
| Деформация на пике амплитуды | 0,25 | нет разрывов/дыр скина и ракушин; `skin_stretch` PASS; крупный план рук с оружием чист |
| Читаемость силуэта в движении | 0,25 | поза читается на K1 и K2×1,6; ВР-06: не спиной к камере; характер героя виден в силуэте |
| Тайминг и характер | 0,20 | контакт в кадре профиля; замах → удар → проводка → возврат; Idle — дыхание, не мёртвая поза |
| Границы и шов | 0,10 | кадр 0 = rest; последний кадр по роли; шов Idle невидим |
| Контракт | 0,10 | валидаторы PASS, fps 24, длительности, root = 0 |
| Читаемость в особых условиях | 0,10 | серый (Rec.709) и дейтеранопия (Machado 2009) листы |

Коэффициент = Σ(оценка 0–10 × вес); проход ≥ 8,0.

### 6.4 Мини-чек-лист приёмки клипа

```markdown
- [ ] validate_clip.py --skeleton=UM_HUMANOID_17_v2 --character=<Hero> --clip-role=<роль> — PASS, WARN объяснены
- [ ] clip_contact_check.py — PASS (skin_stretch, пересечения, подошва, weapon_tip, подол)
- [ ] h2anim_ue.py measure: длительность ±0,02 с от ExpectedClipSeconds; rootDeltaUU = 0
- [ ] LungeAttack: notify `Contact` стоит, время = LungeContactFrame / 24
- [ ] Лист поз просмотрен: K1 и K2×1,6, обе настоящие доски, цвет + серый + дейтеранопия
- [ ] ВР-06: покой вполоборота к камере, в атаке — разворот к цели; спиной к камере нет
- [ ] Крупный план суставов с оружием (--closeup): дыр оболочки на сгибах нет
- [ ] Реестр 03-asset-registry.csv обновлён; коэффициент рубрики ≥ 8,0 (или эскалация после 2 циклов правки)
```

### 6.5 Чек-листы VFX и SFX

```markdown
VFX:
- [ ] Стиль ВР-19: плоские формы, жёсткая кромка, ≤ 600 мс, без дыма/бликов/линз
- [ ] Цвета из hud-style-tokens.json; G-TOKENS PASS (hex-литералов в графе нет)
- [ ] EffectType назначен (NET_UM_Board / NET_UM_Combat); эмиттеры CPU; сид = CRC32(имя)
- [ ] Бюджет: спрайты по реестру CUE→Niagara; худший набор ≤ 3 боевых систем, ΔGPU ≤ 1 мс
- [ ] Строка реестра 03 с rollback-флагом; трейс ARTLOOK показывает фактический вид
SFX:
- [ ] ID в 03-sound-registry.csv; имя SW_/MS_ без дефисов; исходник вне git с manifest.json
- [ ] Формат 48/16, каналы по типу; петля — шов на нуле, проверка RMS/спектра
- [ ] Блок sfx в cue-table.json (sound_class, priority, concurrency); визуальный дубль в UI есть (§5.7)
- [ ] Громкость по loudness-карте; итог — записью партии, не M max
```

---

## 7. Шаблоны

### 7.1 Спека клипа в `build-profiles/<hero>-h2anim.json` (сокращённо; полный образец — профиль King Arthur)

```json
{
  "schema": "unmatched.h2anim-spec/1",
  "hero": "KingArthur", "character": "Arthur", "ue_hero": "KingArthur",
  "target": {
    "sk_fbx": "art/pipeline-candidates/ASSET-KING-ARTHUR-001/20260929-h2-bake/export/SK_KingArthur_H2.fbx",
    "sha256": "<sha256 цели>"
  },
  "fps": 24,
  "ue": {
    "skeleton": "/Game/PipelineCandidates/KingArthur/Rig/SK_KingArthur_Skeleton",
    "clips_folder": "/Game/PipelineCandidates/KingArthur/H2Anim"
  },
  "clips": {
    "LungeAttack": {
      "frames": 14, "role": "oneshot",
      "reference": "art/animation-refs/ASSET-KING-ARTHUR-001/ARTH-LungeAttack",
      "keys": [ { "f": 7, "bones": { "spine": [0, -12, 8] }, "aim": { "weapon.R": { "to": [0.5, 0, -0.8] } } } ]
    }
  }
}
```

### 7.2 Строка реестра 03-asset-registry.csv (формат колонок, клип)

```text
id,area,event_or_screen,description,source_tool,format_size,ue_path,rollback_flag,status,acceptance,license,budget,link
AM_<Hero>_<Clip>,anim,"<CUE и момент запуска>","Клип D-11 <роль> для <Hero> на риге UM_HUMANOID_17_v2, root motion выкл","Blender (H2Anim)","FBX 24 fps, <N> к.; AnimSequence","/Game/PipelineCandidates/<Hero>/H2Anim/AM_<Hero>_<Clip>","-S08HeroesLegacy","<статус>","<кто/когда принял>","свой (код и материалы проекта)","<мс>, <N> к.; <кости>; ΔGPU 0","AN-xx; ASSET-<ID>-001; <путь FBX>"
```

---

Известные расхождения (полный список — HANDBOOK §10): контракт рига и сокеты — статус «предложено»; сокет Harpy
`Weapon` — профиль `foot.R` против «кисти» контракта; общий ретаргет и `ik_chains` в UE не доказаны (§1.4);
`MS_*` в Content не создан (§5.1).
