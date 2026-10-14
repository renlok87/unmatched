# Этап 6: анимация, VFX и SFX — глобальный стандарт, производство, приёмка клипов (шаг 7a.2)

Документ решает две задачи. Часть A — глобальный стандарт скелетной анимации, VFX и SFX проекта (требование №4); он
действует для всех фигур. Часть B — производство этапа 6 для нового ассета и приёмка клипов с коэффициентом (`kind=anim`).

Карта этапов скилла (`SKILL.md`): 0 заявка → 1 концепт-лист → 2 Tripo H2 → 3 сборка в Blender (регистрация персонажа →
H2-bake → look-dev → TeamAccent) → 4 приёмка модели → 5 доработка модели → **6 анимация (headless-авторинг) + VFX +
SFX** → 7a импорт в UE и **приёмка клипов (шаг 7a.2)** → 7b подключение S08, упаковка, кадры в игре
(`references/ue-import-package.md`).

Порядок 6 → 7a (ДС-1, `docs/game-design/decisions/2026-10-14-skill-refinement-delegated-decisions.md`). Приёмке клипа
нужен UE-импорт: гейт `G-MANIFEST` требует статус `technically_imported`, кадры приёмки — UE-кадры редактора. Поэтому
этап 6 только авторит 4 клипа и гоняет валидаторы, а приёмка клипов (§10) идёт на шаге 7a.2 после импорта
(`references/ue-import-package.md` §4.5). Пилот шёл так же (F43, RA-01). Находки пилота F —
`docs/art-pipeline/evidence/skill-pilot-2026-10-13/NOTES.md`, исследование RA/RB/RC — там же `research/`.

Норма производства — `docs/art-pipeline/BLENDER-MODEL-HANDBOOK.md` (дальше «HANDBOOK»). Он главнее этого файла. Числа
рига и клипов здесь не копируются: даются ссылки на разделы §2.6 (риг), §2.7 (сокеты), §2.8 (клипы), §4.5 (H2Anim),
§4.6 (импорт в UE), §4.7 (подключение S08). Здесь только то, чего в HANDBOOK нет.

Плейсхолдеры берутся из заявки `<ASSET_DIR>/asset-card.yaml` (этап 0):

| Плейсхолдер | Что это | Пример |
|---|---|---|
| `<ASSET_ID>`, `<ASSET_DIR>` | id ассета и `art/pipeline-candidates/<ASSET_ID>` | `ASSET-KING-ARTHUR-001` |
| `<Key>` | поле KEY: UE-ключ, имя в путях и файлах (`AM_<Key>_*`, `/Game/PipelineCandidates/<Key>/`) | `KingArthur` |
| `<Character>` | поле CHARACTER: ключ персонажа в `rig-contract.json` и для `validate_clip.py --character` | `Arthur` |
| `<content-key>` | поле CONTENT_KEY (kebab) | `king-arthur` |
| `<FIGHTER_NAME>` | имя бойца на сервере (`Specs()`) | `King Arthur` |
| `<PRE>` | поле CLIP_PREFIX: префикс id клипа в манифесте: значение `CHARS["<Character>"][0]` в `tools/tripo-pipeline/anim/clip_manifest.py:41-42`, заводится регистрацией этапа 6 (`references/new-character-registration.md`, плейсхолдер `<PRE>`, Р6-1). Им же называются папки референсов `<PRE>-<Clip>` | `ARTH` (у Robin Hood, например, `ROB`) |
| `WEAPON_BONE`, `IDLE_SECONDS`, `LUNGE_CONTACT_FRAME` | поля заявки | `weapon.R`, `2.5`, `7` |

`<Key>` и `<Character>` — разные вещи. Пример: `king-arthur-h2anim.json` содержит `"hero": "KingArthur", "character":
"Arthur", "ue_hero": "KingArthur"`. `h2anim_run.py` передаёт в `validate_clip.py --character` поле `spec["character"]`,
то есть ключ контракта (`tools/tripo-pipeline/anim/h2anim_run.py:112`; так же HANDBOOK §4.5 п.2).

---

# Часть A. Глобальный стандарт

## 1. Скелет

- Контракт `UM_HUMANOID_17_v2`: `docs/art-pipeline/rig/rig-contract.json` (schema `unmatched.rig-contract/2`, статус
  «предложено»). Человекочитаемый вид — HANDBOOK §2.6 и `docs/art-pipeline/rig/RIG-CONTRACT.md`. Иерархия, кости, веса,
  запреты и rest-поза — только оттуда.
- **Rest = поза миниатюры, не T/A-поза** (`rig-contract.json` → `skeletons.UM_HUMANOID_17_v2.rest_pose`). Кадр 0 каждого
  клипа равен rest.
- **Кость оружия — поле `WEAPON_BONE` заявки**: `weapon.L`, `weapon.R` или `null`. Фигура без оружия (Harpy) не имеет
  кости оружия. Сокет `Weapon` у неё ставит профиль UE-импорта: у Harpy это `foot.R`
  (`art/pipeline-candidates/ASSET-HARPY-001/build-profiles/harpy-h3ld-lookdev-ue-import.json:123-126`), а
  `rig-contract.json` → `characters.Harpy.note` говорит про кисть. Расхождение открыто (HANDBOOK §2.7). Кость сокета
  нового персонажа без оружия — решение профиля импорта, записать его в поле `WEAPON_SOCKET_BONE` заявки.
- **Регистрация персонажа обязательна до первого H2-bake** (этап 3). Нужно дописать
  `skeletons.UM_HUMANOID_17_v2.characters.<Character>` (поля `asset_id`, `weapon_bone`, `weapon`, `ue_weapon_bone`) и
  поднять `revision`. Без этого `rig_rules.py` поднимает KeyError
  (`tools/tripo-pipeline/anim/rig_rules.py:33`), а с ним падают `validate_clip.py`, H2-bake и `h2anim_run.py`.
  Список мест и проверок — `references/new-character-registration.md` §3 (этап 3), §4 (этап 6), §5 (этап 7). Для гуманоида с существующими
  костями это рутинное пополнение данных, а не эскалация.
- **Анатомия вне контракта** — гейт стопа на этапе 0 (`SKILL.md` §5 п.1). Сюда относятся четвероногие, многоголовые и
  змеевидные фигуры. На этап 6 такой ассет не попадает. Новая кость или новое расширение — тоже гейт стопа (HANDBOOK
  §0.3). Имена расширений: `optional_extensions` → `crown_snakes`, `cloak`, `harpy_wings`. Все со статусом «предложено, не
  реализовано».
- **Root motion**: клипы in place. Объект арматуры (кость 0 в UE) и pose-кость `root` не ключуются. Допуск дрейфа — HANDBOOK
  §2.8. При импорте ставятся `bForceRootLock = true` и `bEnableRootMotion = false`
  (`tools/tripo-pipeline/review/ue_py/import_clips.py`). Перемещение по доске делается скольжением актора; walk/run-клипов
  нет.
- **Поворот к камере и к цели — процедурный** (ВР-06, ВР-14,
  `docs/game-design/decisions/2026-10-06-visual-delegated-decisions.md`). Клип не поворачивает фигуру по yaw: лицо
  остаётся в +X. Откат — `-S08FacingLegacy`.
- **Ретаргет**: каждый клип авторится на риге своего героя. Общий IK Retargeter не доказан: `ik_chains` контракта в UE не
  собраны. Внешние клипы (Tripo, Mixamo) допускаются только как сверка `validate_clip.py --retarget-map=`. Карта не
  заменяет перекладку.
- **В рантайме нет AnimBlueprint, Montage и Blend Space.** Клип играет код `AS08FighterActor::PlayHeroClip`
  (`unreal/Unmatched/Source/Unmatched/S08/S08FighterActor.cpp:929`). ABP не заводить.

## 2. Клипы D-11

### 2.1 Набор и числа

Набор закрыт: Idle, LungeAttack, HitReact, DeathSettle. Новых клипов нет (ВР-14), смерть — поклон корпусом без падения на
колени. Кадры, роли, длительности, допуски и правила ключей — HANDBOOK §2.8. fps 24 (`ClipFps`,
`unreal/Unmatched/Source/Unmatched/S08/S08HeroesV2.h:143`). Длины LungeAttack, HitReact и DeathSettle одинаковы у всех
героев (`ExpectedClipSeconds`, `S08HeroesV2.cpp:157`). Пер-геройные величины зашиты в `Specs()`
(`S08HeroesV2.cpp:105-116`):

| Герой (`<Key>` / `<Character>`) | Оружие, кость | Idle, с | Контакт LungeAttack (24 fps) |
|---|---|---|---|
| KingArthur / Arthur | меч, `weapon.R` | 2,5 | к. 7 = 292 мс (рубящий удар) |
| Merlin / Merlin | посох, `weapon.R` | 3,0 | к. 8 = 333 мс (выброс посоха) |
| Medusa / Medusa | лук, `weapon.L` | 56/24 | к. 8 = 333 мс (выпуск стрелы) |
| Harpy / Harpy | когти, нет | 2,0 | к. 7 = 292 мс (окно удара 7–9, контакт — первый кадр окна) |
| Angel / Angel (пилот) | меч, `weapon.R` | 2,5 | к. 7 = 292 мс (образец — клипы меча KingArthur) |
| AncientLeshen / AncientLeshen (пилот) | когти правой кисти, нет; ствол без ног | 56/24 | к. 8 = 333 мс |
| Achilles / Achilles (пилот) | копьё `weapon.R` (две части, П3-1) + щит на `arm_lower.L` (П3-2) | 2,5 | к. 7 = 292 мс (укол) |

Источник контактов — поле `design` клипа LungeAttack в `ASSET-*/build-profiles/*-h2anim.json`. Те же числа стоят в
`S08HeroesV2.h:115-118`, `tools/art/de010/de010.py:50-57` (`HEROES`) и автотесте `Unmatched.S08.HeroesV2.Contact`
(`S08HeroesV2Tests.cpp:514`).

**Новый герой.** Числа задаются на этапе 0 полями `IDLE_SECONDS` и `LUNGE_CONTACT_FRAME`. Дефолт (решение по делегированию,
`SKILL.md` §7.1, заявка): оба — как у ближайшего героя того же типа оружия из таблицы выше. Пример: лучник Robin Hood
рядом с Medusa получает 56/24 с и кадр 8. Требования:
- `round(IDLE_SECONDS × 24)` — целое число кадров Idle (в заявке число с 4 знаками, например 2.3333 = 56 к.; в
  `Specs()` писать дробью кадров `56.0f / 24.0f`, как Medusa, `S08HeroesV2.cpp:107`);
- уникальность Idle не нужна: игровой лист K1/K2 этапа 7 опознаёт бойца по фокусу запуска
  (`BENCH clip-pose … fighter=<id>` в каталоге `<frames>/<map>/<Key>`), а длину Idle берёт только запасным признаком
  и только когда она уникальна среди `HEROES` (`tools/art/anim/clip_review_sheet.py`, `parse_run`,
  `unique_idle_keys`; доработка Д-3, `references/new-character-registration.md` §2). Совпадение Idle с чужим героем
  лист не ломает;
- `LUNGE_CONTACT_FRAME` входит в `key_frames` клипа LungeAttack в спеке — иначе `de010.py` откажет
  (`tools/art/de010/de010.py:50-57`; проверка `:187` смотрит только fps 24, длину 14 к. и `key_frames`). Ключ в `keys`
  (`"f": N`) на этом кадре — правило скилла для читаемого удара; `de010.py` его не проверяет.

### 2.2 Нейминг и пути

| Что | Формат | Источник |
|---|---|---|
| Клип UE (AnimSequence) | `/Game/PipelineCandidates/<Key>/H2Anim/AM_<Key>_<Clip>`; суффикса `_Anim` нет | `ClipPath`, `S08HeroesV2.cpp:152` |
| Канонический скелет | `/Game/PipelineCandidates/<Key>/Rig/SK_<Key>_Skeleton` (рядом меш-носитель `SK_<Key>`) | `tools/tripo-pipeline/review/ue_py/canonical_skeleton.py` |
| FBX клипа | `<ASSET_DIR>/<YYYYMMDD>-h2anim/export/AM_<Key>_<Clip>.fbx`, один FBX на клип, с узлом меша | `h2anim_run.py`, HANDBOOK §2.8 |
| Спека | `<ASSET_DIR>/build-profiles/<content-key>-h2anim.json`, schema `unmatched.h2anim-spec/1` | HANDBOOK §4.5 |
| Отчёт validate | `docs/art-pipeline/animation-library/validation-h2anim/AM_<Key>_<Clip>.validation.json` (дымовой прогон — `--out-dir`, §6.6) | `h2anim_run.py:34` |
| Манифест библиотеки | `docs/art-pipeline/animation-library/clip-manifest.json` | `clip_manifest.py` |
| Реестр | строка `AM_<Key>_<Clip>` в `docs/game-design/visual/03-asset-registry.csv` | §12.2 |

### 2.3 AnimNotify `Contact`

- В каждом LungeAttack стоит ровно один notify `Contact` класса `US08ContactAnimNotify` на треке `Contact`. Его время —
  `LUNGE_CONTACT_FRAME / 24`. В Idle, HitReact и DeathSettle этого notify нет. Это проверяет автотест
  `Unmatched.S08.HeroesV2.Contact` (`S08HeroesV2Tests.cpp:508-548`, проверка «one Contact notify» — строка 540). Поэтому
  для героя из `Specs()` notify обязателен: без него этап 7 не проходит автотесты.
- Рантайм берёт время из notify. Без notify используется фолбэк `ProfileContactSeconds = LungeContactFrame / ClipFps`
  (`S08HeroesV2.cpp:167`, `:177-180`), так что тайминг боя без notify не ломается.
- От контакта отсчитываются HitReact цели, звёзда удара, «−N», HP, звук удара и запуск CUE-013. Сроки — блоки
  CUE-011 и CUE-013 в `docs/unreal/contracts/cue-dispatcher/cue-table.json`.
- Notify ставит `tools/art/de010/de010.py apply --only <Key>` на шаге 7b (`SKILL.md` §6, этап 7b п.1; регистрация
  Р7-1). На этапе 6 и в приёмке клипов 7a.2 он не нужен: гейты приёмки клипа его не проверяют (§10.2), редакторные
  кадры его не показывают.
- `h2anim_ue.py import` удаляет клип перед импортом (`import_clips.py`), notify при этом пропадает. Поэтому
  `de010.py apply` повторяется после **каждого** импорта LungeAttack, сделанного после шага 7b (§7).

### 2.4 Клип ↔ CUE

| Событие | Клип | Адресация в `cue-table.json` |
|---|---|---|
| CUE-008 «объявление атаки» | клипа нет | — |
| Выпад (стадия боя после слэма CUE-010) | LungeAttack атакующего | код стадии боя; звук выпада `CMB-LUNGE-<hit_type>` (§4.3) |
| CUE-011 «урон» | HitReact цели в кадр контакта | `clip.sequence_by_fighter.<Key>` |
| CUE-013 «смерть» | DeathSettle | `clip.sequence_by_fighter.<Key>` |
| Idle | без CUE (фон; CUE-017 ставит на паузу) | — |

Если ключа героя нет в `sequence_by_fighter` CUE-011/013, гейт трассы отвечает `missing`
(`tools/s08/cue_contract/cue_contract.py:343-345`). Ключи добавляются только **после** импорта клипов в UE (§6.4):
`validate-table` проверяет, что `.uasset` каждого пути `sequence_by_fighter` уже лежит в `unreal/Unmatched/Content/`
(`cue_contract.py:41`, `:257-260`). Шаг и проверка — §12.1, строка регистрации Р7-6
(`references/new-character-registration.md` §5.4).

---

## 3. VFX

### 3.1 Стиль и бюджет

- **Стиль ВР-19** «печатный»: плоские формы с жёсткой кромкой, 2–3 тона из токенов, длительность ≤ 600 мс, без дыма,
  бликов и линз. Эффект живёт на фигуре и на клетке, камера неподвижна.
- **Бюджет ВР-25**: не больше 3 одновременных боевых систем, ΔGPU ≤ 1 мс на худшем наборе. Замер — один прогон
  `tools/art/render/render_bench.py`, и только если изменение добавляет FX (AGENTS.md «Iteration speed»). Результат в
  пределах бюджета записать и идти дальше: оптимизаций в пределах бюджета не делать.
- **Цвета** — только токены `docs/unreal/contracts/hud/hud-style-tokens.json` (`colors.fx.*`, кромка `card.glyph`). Hex-
  литералы в графе запрещены.

### 3.2 Сокеты

Сокеты создаёт UE-импорт (этап 7), в Blender их не делают (HANDBOOK §2.7, `references/ue-import-package.md`).

| Сокет | Где | Кто пользуется |
|---|---|---|
| `Weapon` | кость оружия `WEAPON_BONE` в UE-имени (`weapon_L` / `weapon_R`); при `WEAPON_BONE = null` — кость по профилю импорта (у Harpy — `foot.R`; контракт говорит про кисть, расхождение HANDBOOK §2.7, §1 выше) | CUE-014 `by_hero` (дуга Arthur) |
| `Head` | `head` | evidence-съёмка; фигура без `Head` выпадает из неё (HANDBOOK §2.7) |
| `Root`, `Base` | актор и подставка, не скелет (`cue-table.json` → `sockets_from`) | вихрь Medusa → `Root`, лечение → `Base` |

### 3.3 Нейминг и папки (факт `unreal/Unmatched/Content/S08/FX/`)

| Префикс | Тип | Примеры |
|---|---|---|
| `NS_FX_*` | Niagara System | `NS_FX_HitStar`, `NS_FX_AshEmbers`, `NS_FX_ArthurArc`, `NS_FX_MedusaVortex` |
| `M_FX_*` / `MI_FX_*` | мастер / инстанс | `M_FX_Print`, `M_FX_FigurePrint`, `M_FX_AbilityPrint`, `MI_FX_HitStar` |
| `T_FX_*` | текстуры и флипбуки (сетка в имени) | `T_FX_HitStar_4x2`, `T_FX_ArthurArc_4x4` |
| `NET_UM_*` | Niagara Effect Type | `NET_UM_Board`, `NET_UM_Combat` (`/Game/S08/FX/EffectTypes/`) |

Папки: `/Game/S08/FX/{Board,Combat,Systems,EffectTypes,Materials,Textures,Meshes}`.

### 3.4 CUE → Niagara (код: `unreal/Unmatched/Source/Unmatched/S08/Fx/S08CueFx.cpp:61-71`)

| CUE | Система | Effect Type | Привязка | Спрайты |
|---|---|---|---|---|
| CUE-007 | `NS_FX_Dust` | Board | world | 5 |
| CUE-008 | `NS_FX_AttackChevrons` | Board | world | 3 |
| CUE-011 | `NS_FX_HitStar` | Combat | world (точка контакта) | 1 |
| CUE-012 | `NS_FX_HealMotes` | Combat | `Base` | 5 |
| CUE-013 | `NS_FX_AshEmbers` | Combat | world | 40 |
| CUE-014 KingArthur | `NS_FX_ArthurArc` | Combat | `Weapon` | 1 |
| CUE-014 Medusa | `NS_FX_MedusaVortex` | Combat | `Root` | 2 |

### 3.5 Технические правила

- **Детерминизм (FX-04):** сид — `CRC32(имя ассета) & 0x7FFFFFFF` (`S08CueFx.cpp:96-97`), никогда не время и не кадр.
  Эмиттеры CPU, bounds фиксированы, prewarm.
- **Сборка FX — только скриптами в репозитории:** `tools/art/fx/fx_import.py` (мастера, MI, флипбуки) и
  `tools/art/fx/fx_ability.py` (FX смерти и способностей, FX-26/30/32). Ручная сборка в редакторе не допускается.
- **Откаты:** весь боевой VFX — `-S08FxLegacy`; красная заливка вместо вспышки — `-S08HitTintLegacy`; fade вместо пепла —
  `-S08DissolveFade`; полевые FX — `-S08MovePlatesLegacy`, `-S08TargetArcLegacy` и другие флаги из AGENTS.md
  «Rollback flags». Трасса `ARTLOOK` пишет фактический вид (`fx=`, `hitFx=`, `abilityFx=`).

## 4. SFX

### 4.1 Нейминг, банк, пути

| Что | Правило | Источник |
|---|---|---|
| ID звука | `CMB-*`, `DTH-*`, `FX-*`, `VO-<FIGHTER>-<EVENT>` и др.; номер вариации — суффикс файла `_01` | `docs/game-design/audio/02-audio-design.md` §8.3 |
| Реестр | `docs/game-design/audio/03-sound-registry.csv` (одна строка на ID) | 02-audio-design.md §6 п.6 |
| Ассет | `SW_<ID без дефисов>_NN` (SoundWave); `MS_<ID>` (MetaSound) спроектирован, в Content 0 файлов (346 `SW_*`, срез 2026-10-09) | 02-audio-design.md §5.5 |
| Банк | `S08AudioBankData.inl` генерирует `tools/audio/ue_bank.py`; код путей не хардкодит | `ue_bank.py:1-11` |
| Пути | `/Game/Audio/{Music,Stings,UI,Cards,Board,Combat,Death,FX,Amb,VO}/` | 02-audio-design.md §5.5 |
| Cook | `+DirectoriesToAlwaysCook=(Path="/Game/Audio")` | `unreal/Unmatched/Config/DefaultGame.ini:18` |

### 4.2 Форматы, громкость, одновременность

- **Форматы** — 02-audio-design.md §5.5. Исходники WAV 48 кГц / 24 бит лежат вне git в `C:/tmp/audio-src/`. Импорт — WAV
  48 кГц / 16 бит. Моно для SFX и VO, стерео для музыки и постелей.
- **Громкость ассетов** — 02-audio-design.md §5.3 (удар, слэм, смерть: M max −12 ±1 LUFS; выпад и эффекты: −16 ±2).
  `sfx_build.py` нормализует к цели группы. Итог микса — −20 ±2 LUFS-I по записи партии (`tools/audio/mix_check.py`).
  Лимитер мастер-шины: make-up +5 дБ, потолок −1,5 dBFS (`S08FlowGameModeAudio.cpp:875-897`). Откат — `-S08MixLegacy`.
- **Одновременность** — 02-audio-design.md §5.4: удар ≤ 2 (StopOldest), VO = 1, всего ≤ 48 голосов.

### 4.3 Как звук привязан к событию

- Звук висит на **событии** (CUE или стадии боя). Внутрь клипа или Niagara звук не кладут. Notify в клипе служит только
  для тайминга (`Contact`, §2.3).
- **Тип удара героя `hit_type`** выбирает банки `CMB-HIT-<TYPE>` (контакт) и `CMB-LUNGE-<TYPE>` (старт LungeAttack):
  `S08AudioBank::HitType` (`S08AudioBank.cpp:62-68`), вызовы — `S08FlowGameModeAudio.cpp:526-527` и `:565`. Ключ героя
  даёт `S08AudioBank::CharacterKey` (`S08AudioBank.cpp:54-60`). Неизвестный герой получает пустой ключ и тип `BLUNT`.
- **Смерть**: банк `DTH-<KEY>`; если его нет, играет `DTH-TEMPLATE` (`S08FlowGameModeAudio.cpp:628-629`). Растворение —
  `DTH-DISSOLVE`.
- **Скорость анимации** длительность и высоту звука не меняет. При скорости «Нет» нет выпада и нет свиста
  (02-audio-design.md §5.6).
- **Визуальный дубль**: у каждого значимого звука есть дубль в UI. Звук без дубля не добавляется (02-audio-design.md
  §5.7).
- **Прослушивание**: `docs/game-design/audio/02-audio-design.md` §7 оставляет прослушивание и выбор пользователю (G-ART)
  и запрещает агенту принимать звук «на слух». По делегированию (ВР-реестр 2026-10-06,
  `docs/game-design/decisions/2026-10-06-visual-delegated-decisions.md`; решение скилла) это не стоп:
  агент проверяет звук только техническими критериями (§9: импорт, `problems: 0`, громкость `sfx_build.py`), ставит в
  `03-sound-registry.csv` пометку «прослушивание пользователем не проводилось», а пользователь слушает позже.

---

# Часть B. Производство этапа 6 для нового ассета

## 5. Вход, предусловия, среда

**Вход** — выход этапа 3, прошедший приёмку этапа 4:
- `SK_<Key>_H2.fbx` и `SM_<Key>_H2_Base.fbx` из прогона H2-bake. Клипы авторятся на bake-меше; look-dev не меняет риг и
  rest (HANDBOOK §4.5 п.1).
- Карточка этапа 4 с `verdict: pass`.
- Заявка с полями из таблицы плейсхолдеров и `MOTION_SOURCE` (§6.1).

**Выход** (ДС-1) — 4 клипа авторены: `h2anim_run.py` код 0 (validate и contact PASS, WARN разобраны), проверки
исполнителя §6.3, `clip_manifest.py build` → `MANIFEST_CHECK PASS` (клипы `measured`), заготовки промптов приёмки
`<ASSET_DIR>/evidence/acceptance-anim-prompts/<Clip>/acceptor-prompt.md` по шаблону §10, слоты VFX и SFX (§8, §9).
Карточек клипов на этапе 6 нет: их даёт шаг 7a.2 (§10, §11).

**Регистрация этапа 6** выполняется до первого `h2anim_run.py` по `references/new-character-registration.md` §4
(строки Р6-1…Р6-4). В неё входят только данные, которым не нужны ассеты UE (Р6-4 — строка `HEROES` листа и 4 карточки клипов, ниже):
- `CHARS` (с префиксом `<PRE>`) и `H2ANIM` в `tools/tripo-pipeline/anim/clip_manifest.py:41-47`;
- `"<Character>"` в `character.enum` схемы `docs/art-pipeline/animation-library/clip-manifest.schema.json:36`. Без этого
  `clip_manifest.py build` (он сам вызывает `check`) падает на схеме, и гейт `G-MANIFEST` (§10.2) не проходит ни у
  одного клипа героя;
- проверка — `python tools/tripo-pipeline/anim/clip_manifest.py build` → `MANIFEST_CHECK PASS` (пока клипов нет,
  4 новых слота без клипа).

Не входят в этап 6 и делаются позже:
- ключи `<Key>` в `sequence_by_fighter` CUE-011 и CUE-013 и `validate-table` — после импорта клипов (§6.4, §12.1;
  регистрация Р7-6). До импорта `validate-table` даёт FAIL «нет ассета»;
- `CharacterKey` и `HitType` в `S08AudioBank.cpp` — правка C++ этапа 7 (регистрация Р7-5). Этап 6 только выбирает
  `hit_type` и записывает его в заявку (§9).

Регистрация этапа 3 (`rig-contract.json` и `tools/tripo-pipeline/tests/test_rig_rules.py`) к этому моменту уже сделана.

**Карточки задач 06-tasks.** 4 карточки клипов нового героя в `anim.csv` нужны всегда: по ним строится лист AN-18
(Р6-4), а траты SYNTX без карточки запрещены (`tools/art/visual/ledger.py add` отказывает, если `--task` не найден в
`docs/game-design/visual/06-tasks/*.csv`). Формат — как у AN-01…AN-16; id — следующие свободные `AN-NN`, в пачке их
выдаёт один писатель (RC-13), иначе две фигуры возьмут один номер.

**Blender** — только headless. Скрипты `validate_clip.py`, `clip_contact_check.py` и `clip_author.py` в живом Blender
бросают RuntimeError (`validate_clip.py:1-9`). Рабочий путь — только `h2anim_run.py` (§6.3): он передаёт полный набор
флагов (`h2anim_run.py:112-116`) и пишет отчёт в `validation-h2anim/`, который служит источником гейта `G-VALIDATE`
(§10.2). Прямой вызов — **только диагностика**, с `--out` вне `docs/art-pipeline/animation-library/validation-h2anim/`,
чтобы не перезаписать отчёт гейта более слабым:

```bash
# диагностика; N = clips.<Clip>.frames из спеки; --loop=true только для Idle
"C:/Program Files/Blender Foundation/Blender 5.2/blender.exe" -b --factory-startup \
    --python tools/tripo-pipeline/anim/validate_clip.py -- <clip.fbx> --skeleton=UM_HUMANOID_17_v2 \
    --character=<Character> --clip-role=<idle|oneshot|terminal> --expect-fps=24 --expect-duration=<N/24> \
    --root-policy=in_place --min-pose-change=0.02 [--loop=true] --out=C:/tmp/skill-<content-key>/<Clip>.validation.json
```

**Среда UE** (шаги §6.4 и §7 — это этап 7, не 6):
- Шаги §6.4 идут на шаге 7a в агентском скрытом редакторе пачки (ДС-3): его поднимает и закрывает оркестратор, 7a —
  строго один герой за раз, агент героя свой редактор не запускает и чужой не закрывает. Рецепт запуска
  (`-RenderOffScreen -unattended -nosplash -ModelContextProtocolPort=8123`, без Live Coding, `UE_CONSOLE_DROP`, PID в
  `$W/editor.pid`, опознание по командной строке) — `references/ue-import-package.md` §1 п.1. Проверка MCP:
  `netstat -ano | grep ':8123 .*LISTEN'`. Интерактивный редактор пользователя (без флагов агентского запуска) агент не
  закрывает — гейт `SKILL.md` §5 п.7; пользователь UE сам не открывает (2026-10-14), так что в автономном прогоне гейт
  не срабатывает.
- Импорт клипов идёт в `Content` того чекаута, чей редактор открыт. Всё, что проверяет `.uasset` на диске
  (`cue_contract.py validate-table`, §12.1), запускать в этом же чекауте.
- Каждая UE-команда выполняется под блокировкой `C:/tmp/ue-editor.lock`, по одному герою на блокировку:
  `MSYS_NO_PATHCONV=1 UE_LOCK_OWNER=<ASSET_ID>-7a python tools/art/material_library/ue_lock.py --step "<шаг>" -- <команда>`
  (`ue_lock.py:54`; heartbeat держит шаг дольше 25 мин, RB-21; зависший шаг держит её не дольше `--max-hold`, по
  умолчанию 2 ч; PID владельца — в файле блокировки, `--wait-timeout` — предел ожидания;
  `references/ue-import-package.md` §1 п.2). Сами скрипты `tools/tripo-pipeline/*` блокировку не берут.
- `h2anim_ue.py frames` отказывает, если в открытом уровне есть несохранённые изменения или если открыт сам
  `L_P17ControlScene` (`h2anim_ue.py:443-447`).
- Headless-коммандлеты (`UnrealEditor-Cmd`: `ue_import_audio.py`, `ue_verify_audio.py`, `fx_ability.py`) запускаются
  только когда на этом чекауте нет GUI-редактора (`fx_ability.py:4`: «the editor of THIS checkout must be closed»;
  HANDBOOK §0.1). Поэтому они выполняются в окне шага 7b вместе с `de010`/`de011` (`SKILL.md` §6, этап 7b), а не
  между MCP-шагами. Worktree это не обходит (`references/ue-import-package.md` §1 п.4). Агентский редактор 7a к окну
  7b закрывает оркестратор; открыт интерактивный редактор — гейт стопа `SKILL.md` §5 п.7, его агент не закрывает.
- Свои процессы Blender и UnrealEditor-Cmd после шага проверять и завершать по PID (`SKILL.md`).

**Проп.** Этап 6 нужен пропу, только если у него есть CUE-строка или звук. Иначе этап пропускается с записью
«нет слотов» в поле `STAGE6_SLOTS` заявки.

## 6. Клипы: шаги

### 6.1 Источник движения: паттерн библиотеки → пресет Tripo → видео-референсы SYNTX (ДС-6, решение 2026-10-14)

Порядок источников — ДС-6, дополненное решением пользователя 2026-10-14
(`docs/game-design/decisions/2026-10-14-tripo-smart-mesh-props-anim-presets.md`: «бесплатный пресет анимации, как
образец движения, а не клипы»). Берётся первый подходящий:

| № | Источник | Когда | `MOTION_SOURCE` |
|---|---|---|---|
| 1 | паттерн библиотеки | есть принятый герой с тем же классом оружия (таблица ниже) | `"library: <Key образца>"` |
| 2 | бесплатный пресет Tripo — образец движения, не клип | в библиотеке нет образца (решение называет: без оружия, когти, необычное оружие или походка) | `"tripo-preset: <имя пресета>"` |
| 3 | видео-референсы SYNTX | ни библиотека, ни пресеты не дают нужного движения | `"syntx: <причина>"` |

Клипы одного героя из разных источников — значения через `;` (например `"library: KingArthur; tripo-preset: fall"`),
источник каждого клипа — в `clips.*.reference_kind` спеки (решение скилла). При любом источнике клип авторится
инструментами скилла (§6.2–6.3) на `UM_HUMANOID_17_v2` с длинами D-11 (§2.1) и неподвижной подставкой.

**1. Паттерн библиотеки — по умолчанию** (ДС-6; RA-18, RC-02, F44). Движение строится по принятым клипам D-11 героя с
тем же классом оружия, а не по памяти:

| Класс оружия | Образец (папка `art/animation-refs/` и спека `build-profiles/*-h2anim.json`) |
|---|---|
| меч, рубящее в правой руке | KingArthur (`ASSET-KING-ARTHUR-001/ARTH-*`); пилот — Angel ← Arthur |
| лук, стрелковое в левой | Medusa (`ASSET-MEDUSA-001/MED-*`) |
| посох, копьё, древковое | Merlin (`ASSET-MERLIN-001/MER-*`); пилот — Achilles ← Merlin (подготовка и выброс) + Arthur (контакт к.7) |
| без оружия: когти, крылья | Harpy (`ASSET-HARPY-001/HAR-*`); фигура без ног — пилот AncientLeshen ← Medusa/Merlin |

- В спеке: `clips.*.reference` — папка образца (`art/animation-refs/<ASSET_ID образца>/<PRE>-<Clip>`), рядом
  `clips.*.reference_kind` — «library pattern (D-11, <герой и клип>), not a <Key> video» (так пилот, Angel и Achilles).
  Рядом в корне спеки — `pattern`: путь спеки образца или `{"spec": <путь>, "key": "<Key образца>"}` (Beowulf записал
  его как `history.pattern_spec` — тоже читается). По нему и по `MOTION_SOURCE` заявки (`library:` / `tripo-preset:`)
  заметка манифеста `clip_manifest.py` называет образец, а не «видео-референс» папки `reference` (C53, F50; раньше
  BEO-* получили «шаблон Medusa + видео ARTH» вместо паттерна Angel r2). Спеки без `pattern` и без такого
  `MOTION_SOURCE` пишут прежний текст.
- В заявке: `MOTION_SOURCE: "library: <Key образца>"` (`SKILL.md` §7.2).
- Отступление от HANDBOOK §4.5 («по видео-референсам») — решение ДС-6 (для пресета Tripo — решение 2026-10-14):
  записать строкой в README evidence этапа 7 («Отступления от хендбука»).
- Почему: визуального лимита SYNTX (54 на журнал, ≤ 10 на видео, 4 клипа — до 40) хватает примерно на одного героя;
  весь пилот шёл на паттернах, и все 12 его клипов приняты (часть — со второго цикла).

**2. Бесплатный пресет Tripo — образец движения, не клип** (решение 2026-10-14; факты — эксперимент на Beowulf,
`docs/art-pipeline/evidence/skill-check-beowulf-2026-10-14/tripo-tools-experiment/README.md`). Когда: в таблице выше нет
образца того же класса оружия или движения.

- **Как получить.**
  1. Модель с ригом Tripo — любая уже заригованная модель аккаунта (после эксперимента: Beowulf `1d926810`, UE5
     Mannequin; `4835e4a1`, Mixamo) или авториг «Гуманоид» один раз, 20. Авториг — платная операция: предпроверка и
     строка журнала по `references/tripo3d-stages.md` §6 пп. 5–6 с карточкой клипа `AN-NN`. Риг Tripo — только
     носитель образца, на фигуру он не идёт (`references/tripo3d-stages.md` §4, «Риг»).
  2. Страница Animate → плитка пресета (> 90: idle, slash, hit_to_body_01/02, fall, defeat, chop…). Пресет стоит 0, но
     применяется сразу по клику на плитку, цены на кнопке нет — смотреть, куда кликаешь; Text-to-motion и
     Multi-stage Motion (по 20) не нажимать. Строка журнала — с `--quoted 0` и суффиксом `#anim-<пресет>`, как в
     эксперименте.
  3. Экспорт — **со страницы Animate**: GLB, «Animation stay in Place» вкл. (таз по X/Z неподвижен), в «Number of
     Animations» — нужный пресет. Со страницы Model экспорт скелета битый (NaN-кости, лишний Icosphere 2 м). GLB — вне
     git, в рабочем каталоге ассета (`C:/tmp/…`), как сырые GLB Tripo.
- **Что брать** — тайминг (доли подготовки, удара или реакции и возврата) и ключевые позы корпуса, рук и головы.
  Смотреть в Studio и по кадрам выгруженного GLB; готового инструмента скилла для кадров нет (образец листа —
  `09-tripo-anim-frames.jpg` эксперимента).
- **Что не брать** — длительность: пресеты в 3–6 раз длиннее D-11 (idle 15,33 с, slash 6,58, hit_to_body_01 1,29,
  fall 3,0 против §2.1); ход подставки и ног вместе с ней (у Tripo подставка ездит со стопами, наша неподвижна);
  кости (у Tripo 61–65, кости оружия нет). Клип Tripo в игру не идёт ни импортом, ни ретаргетом: клип авторится
  инструментами скилла (§6.2–6.3) на `UM_HUMANOID_17_v2` с длинами D-11 и неподвижной подставкой.
- В спеке: `clips.*.reference` — `"tripo-preset:<имя>"`, `clips.*.reference_kind` — «Tripo preset <имя> (timing and
  key poses only), not a game clip» (решение скилла). В заявке — `MOTION_SOURCE: "tripo-preset: <имя>"`.

**3. Видео-референсы SYNTX — только нестандартное движение и только с причиной** (нет ни образца библиотеки, ни
подходящего пресета Tripo: двуручное или парное оружие, полёт, необычная анатомия в пределах контракта). Причина — в
`MOTION_SOURCE: "syntx: <причина>"`, в ней сказано, почему не хватило пресета. Дальше — шаги ниже. Траты SYNTX идут без подтверждения каждой генерации, по карточке, в лимитах и сроке журнала (ВР-04,
ВР-PR04; `docs/game-design/visual/00-VISUAL-BRIEF.md:21-22`, §5.3).
Порядок вызовов — `docs/game-design/visual/07-prompt-templates.md` §2.4 (create-chat → upload-files → цена → баланс →
генерация → журнал). Вызовы SYNTX идут через CLI-клиент MCP `node $SYNTX_MCP <tool> '<json>'`
(`C:/Users/ren/.claude/mcp-servers/clients/syntx_mcp.cjs`, он же дефолт `SYNTX_MCP` в `gen.sh`); токен клиент берёт сам.
Сырые ответы содержат id аккаунта — только вне репо, в `$SYNTX_WORK`.

1. **Вход** — кадр 3/4 фигуры с подставкой из набора этапа 4 (`<ASSET_DIR>/evidence/acceptance/<YYYYMMDD>-r<N>/frames/
   turn-*.jpg`, кадр с принятой карточки). 07 §2.8: «наш рендер v2 фигуры на нейтральном сером фоне, фигура крупно,
   с подставкой».
2. **Шаблон** — `T-SYNTX-VID-KLING` (07 §2.8; Kling 2.5, 5 с). Запасной — `T-SYNTX-VID-SEEDANCE` (07 §2.9), если Kling
   дважды ломает фигуру; модель в `gen.sh` — `SYNTX_MODEL=seedancefast480|seedance15pro720`.
3. **Промпт — файл `art/animation-refs/<ASSET_ID>/<PRE>-<Clip>/prompt.txt`, только текст промпта.** `gen.sh` отправляет
   в SYNTX файл целиком (`gen.sh`: `p=open(pf…).read()` → `"prompt": p`), поэтому в нём не должно быть ничего, кроме
   текста 07 §2.8 с подставленными полями карточки `<AN-NN>` (`{{title}}`, `{{keyframes}}`, `{{timing}}`, `{{do}}`,
   `{{dont}}` — по-английски, правила подстановки 07 §0.2; папку создать `mkdir -p`). Образец — `art/animation-refs/ASSET-KING-ARTHUR-001/ARTH-LungeAttack/prompt.txt`. После записи открыть
   файл: нет `{{…}}`, таблиц и заголовков.
   `tools/art/visual/prompt_build.py` для видео-референса не годится: он выводит `{{set}}` из колонки `deliverable`
   и отказывает, если там нет папки `art/imagegen/<set>-codex/` (`prompt_build.py:45`, `:121-126`), а у карточки клипа
   результат — `art/animation-refs/…`. Если же он когда-то сработает, его `.syntx.txt` — provenance (таблицы, входы),
   и промпт там лежит только в блоке `## Task` (`prompt_build.py:297`, `:324`): в `gen.sh` такой файл не передавать,
   а вынуть блок:
   ```bash
   python -c 'import re,sys; t=open(sys.argv[1],encoding="utf-8").read(); m=re.search(r"^## Task\s*\n+(`{3,})text\n(.*?)\n\1[ \t]*$", t, re.S|re.M); m or sys.exit("no ## Task block"); open(sys.argv[2],"w",encoding="utf-8").write(m.group(2)+"\n")' \
       docs/game-design/visual/06-tasks/prompts/<AN-NN>.syntx.txt art/animation-refs/<ASSET_ID>/<PRE>-<Clip>/prompt.txt
   ```
4. **Сессия SYNTX — одна на ассет** (чат + загруженный входной кадр), как `art/animation-refs/ASSET-KING-ARTHUR-001/
   syntx-session/{chat,fileobj}.json`:
   ```bash
   export SYNTX_MCP=C:/Users/ren/.claude/mcp-servers/clients/syntx_mcp.cjs SYNTX_WORK=C:/tmp/syntx-<content-key>
   mkdir -p $SYNTX_WORK
   node $SYNTX_MCP create-chat '{"title":"<ASSET_ID> animation refs (video-to-motion)","scope":"video"}' > $SYNTX_WORK/chat.json
   export SYNTX_CHAT_ID=$(python -c 'import json,sys; print(json.loads(json.load(open(sys.argv[1],encoding="utf-8"))["content"][0]["text"])["uuid"])' $SYNTX_WORK/chat.json)
   # upload-files видит только файлы под текущим каталогом (MCP_FILE_ROOTS, заголовок gen.sh) → запуск из папки кадра
   (cd <ASSET_DIR>/evidence/acceptance/<YYYYMMDD>-r<N>/frames && node $SYNTX_MCP upload-files \
       '{"files":[{"path":"turn-<NNN>.jpg"}],"model_type":"kling_image2video"}') > $SYNTX_WORK/upload.json
   python -c 'import json,sys; f=json.loads(json.load(open(sys.argv[1],encoding="utf-8"))["content"][0]["text"])["files"][0]; [f.pop(k,None) for k in ("status","preview")]; f["type"]="image"; json.dump(f,open(sys.argv[2],"w",encoding="utf-8"),indent=1)' \
       $SYNTX_WORK/upload.json $SYNTX_WORK/fileobj.json
   ```
   Форма `fileobj.json` (`files[0]` без `status`/`preview` + `"type": "image"`) проверена: этот разбор ответа
   `C:/tmp/hero-vid/king-arthur-v5/upload.json` даёт ровно `fileobj.json` сессии King Arthur. Для следующих клипов
   того же ассета заново экспортировать `SYNTX_WORK`, `SYNTX_CHAT_ID` (из `chat.json`) и `SYNTX_MCP`.
5. **Сухой прогон без трат** — `gen.sh` собирает только `run_<Run>/req.json`:
   ```bash
   DRY_RUN=1 bash tools/art/syntx_video_refs/gen.sh <PRE>-<Clip> art/animation-refs/<ASSET_ID>/<PRE>-<Clip>/prompt.txt
   ```
   Проверить в `$SYNTX_WORK/run_<PRE>-<Clip>/req.json`: `prompt` = текст `prompt.txt`, `chat_id` = свой чат,
   `file_urls` — свой кадр. Имя прогона уникально (повтор — `<PRE>-<Clip>-take2`).
5а. **Условия провайдера (ВР-05) — один раз на модель, до первой траты.** В журнале есть только условия SYNTX для
   Nano Banana (`providerTerms`, `ledgerModel` `banana/banana3`); строку траты `--model "kling_image2video 2.5 standart"`
   она не покрывает, и после первой генерации `ledger.py check` даёт ERROR `no providerTerms row for SYNTX …`, код 1
   (`tools/art/visual/ledger.py:176-184` `terms_cover`, `:261`) — ложный стоп п.6. Перед первым клипом:
   ```bash
   python tools/art/visual/ledger.py check   # есть ли уже строка terms с ledgerModel kling_image2video
   python tools/art/visual/ledger.py terms --service SYNTX \
       --model "Kling 2.5 image2video (SYNTX kling_image2video) - Kling AI Terms of Service" \
       --url https://kling.ai/docs/user-policy --ledger-model kling_image2video
   ```
   URL — страница условий Kling AI (поиск 2026-10-09, «Last Updated Date: 2026/04/21»); перед записью открыть её и
   проверить дату. `--ledger-model` — подстрока поля `--model` строк трат (сравнение без регистра и знаков,
   `ledger.py:172-184`). Запасной Seedance — так же, до первой траты им: `--ledger-model seedance` и URL условий
   провайдера Seedance, найденный и открытый в момент записи (в репо его нет). Коммерческих прав не заявлять (ВР-05).
6. **Проверка лимита** перед каждым платным запуском; код 1 — гейт стопа `SKILL.md` §5 п.3. Исключение: код 1 только из-за
   `ERROR no providerTerms row for SYNTX …` — это не кредитный стоп, а пропущенный п.5а: записать `ledger.py terms`
   (строку траты не удалять) и повторить проверку. Цена берётся верхней границей
   `SYNTX_MAX_COST` (потолок видео 10 — 07 §2.3): `gen.sh` сам спрашивает цену и откажет, если она выше.
   ```bash
   node $SYNTX_MCP get-balance '{}'          # свежий баланс → <баланс>
   python tools/art/visual/ledger.py check --balance <баланс> --next-cost 10 --next-kind video
   ```
7. **Запуск** (тратит токены; без подтверждения каждой генерации, в лимитах и сроке журнала, ВР-04/ВР-PR04).
   Сначала один вариант на клип:
   ```bash
   SYNTX_MAX_COST=10 bash tools/art/syntx_video_refs/gen.sh <PRE>-<Clip> art/animation-refs/<ASSET_ID>/<PRE>-<Clip>/prompt.txt
   ```
   Результат: `$SYNTX_WORK/run_<PRE>-<Clip>/{quote,balance_before,gen,wait,result,balance_after}.json` и `out.mp4`.
8. **Журнал** — сразу после запуска (цена из `quote.json`, балансы из `balance_before.json` / `balance_after.json`):
   ```bash
   python tools/art/visual/ledger.py add --task <AN-NN> --template T-SYNTX-VID-KLING --service SYNTX \
       --model "kling_image2video 2.5 standart" --units "1 video 5s" --quoted <цена> --before <баланс до> --after <баланс после> \
       --prompt-file art/animation-refs/<ASSET_ID>/<PRE>-<Clip>/prompt.txt --result art/animation-refs/<ASSET_ID>/<PRE>-<Clip>/
   ```
   `--prompt-file` — ровно тот файл, что ушёл в `gen.sh` (если был `.syntx.txt` от `prompt_build.py` — его). Неудачная
   генерация — тоже строка, с `--status failed`; две неудачи подряд — гейт стопа `SKILL.md` §5 п.3.
9. **Копия в репо** с вычищенными id аккаунта. Первый импорт ассета копирует и сессию (`chat.json`, `fileobj.json` из
   `$SYNTX_WORK`), следующие — с `--no-session`:
   ```bash
   # первый импорт ассета (копирует и syntx-session/)
   python tools/art/syntx_video_refs/import_runs.py --asset <ASSET_ID> --src $SYNTX_WORK --run <PRE>-<Clip>=<PRE>-<Clip>
   # каждый следующий прогон того же ассета
   python tools/art/syntx_video_refs/import_runs.py --asset <ASSET_ID> --src $SYNTX_WORK --no-session --run <PRE>-<Clip>=<PRE>-<Clip>
   # mp4 import_runs.py не копирует (комментарий в конце gen.sh) — вручную, имя как ARTH-LungeAttack_kling25_ref.mp4
   cp $SYNTX_WORK/run_<PRE>-<Clip>/out.mp4 art/animation-refs/<ASSET_ID>/<PRE>-<Clip>/<PRE>-<Clip>_kling25_ref.mp4
   ```
   `build_manifest.py` зашит на Medusa (`tools/art/syntx_video_refs/build_manifest.py:16`). Поэтому для нового героя
   путь референса записывается в поле `reference` клипа в спеке (§6.2); манифест `animation-refs` не регенерируется.

Видео — только референс тайминга и поз. В UE оно не импортируется (07-prompt-templates.md §2.8).

### 6.2 Спека `<content-key>-h2anim.json`

Копировать образец **целиком**: инструменты читают обязательные ключи `run_dir`, `target.base_fbx`, `meshes`, `weapon`,
`ue.mesh_for_preview` (`h2anim_run.py:88,141`, `h2anim_ue.py:149,157`). Образец выбирается по оружию:

| Тип фигуры | Образец |
|---|---|
| оружие в правой руке, рубящее | `art/pipeline-candidates/ASSET-KING-ARTHUR-001/build-profiles/king-arthur-h2anim.json` |
| оружие в левой руке, стрелковое | `art/pipeline-candidates/ASSET-MEDUSA-001/build-profiles/medusa-h2anim.json` |
| древковое или посох | `art/pipeline-candidates/ASSET-MERLIN-001/build-profiles/merlin-h2anim.json` |
| без оружия, крылья или когти | `art/pipeline-candidates/ASSET-HARPY-001/build-profiles/harpy-h2anim.json` |
| копьё из двух частей + щит без кости (пилот) | `art/pipeline-candidates/ASSET-ACHILLES-001/build-profiles/achilles-h2anim-r3.json` |
| без оружия и без ног, когти (пилот) | `art/pipeline-candidates/ASSET-ANCIENT-LESHEN-001/build-profiles/ancient-leshen-h2anim-r3.json` |

Заменить в копии:

| Поле | Значение |
|---|---|
| `hero`, `ue_hero` | `<Key>` |
| `character` | `<Character>` |
| `asset_id`, `status`, `status_note` | свои |
| `target.sk_fbx`, `target.base_fbx` | `<ASSET_DIR>/<run h2-bake>/export/SK_<Key>_H2.fbx`, `SM_<Key>_H2_Base.fbx` |
| `target.sha256` | `sha256sum <SK_<Key>_H2.fbx>` |
| `target.rest_generation` | `H2` |
| `meshes.body`, `meshes.weapon` | имена объектов в FBX (`null`, если оружия нет) |
| `weapon.bone`, `weapon.side`, `weapon.note` | из `WEAPON_BONE` (`null`, если оружия нет) |
| `weapon.extra_parts` | части оружия внутри меша body (П3-1: вторая часть Tripo на кости оружия) и щит без своей кости (П3-2): имя кости или `{"bone", "islands"}` — `["weapon.R", {"bone": "arm_lower.L", "islands": true}]` у Achilles. `clip_contact_check` проверяет их как оружие; без ключа пересечение такой части с телом не проверяется (RB-09, F127; парное и двуручное оружие — так же) |
| `run_dir` | `<ASSET_DIR>/<YYYYMMDD>-h2anim` |
| `ue.skeleton` | `/Game/PipelineCandidates/<Key>/Rig/SK_<Key>_Skeleton` |
| `ue.mesh_for_preview` | `/Game/PipelineCandidates/<Key>/Rig/SK_<Key>` — меш-носитель из шага skeleton. Так сделано у Harpy; H2LD-меш появится в UE только на этапе 7 |
| `ue.clips_folder` | `/Game/PipelineCandidates/<Key>/H2Anim` |
| `clips.Idle.frames` | `IDLE_SECONDS × 24` |
| `clips.*.reference`, `clips.*.reference_kind` | папка образца библиотеки или своего видео-референса и вид источника (§6.1, ДС-6) |
| `clips.*.design`, `keys`, `waves`, `key_frames`, `ik_feet`, `hand_follow`, `amplitude_scale` | авторский слой под нового героя. Кадр `LUNGE_CONTACT_FRAME` записывается в `design` LungeAttack, входит в `key_frames` и имеет ключ в `keys` (§2.1) |
| `clips.*.template` | черновики `blender/ASSET-MEDUSA-001/export/AM_Medusa_*.fbx` (в git). `mirror: true`, если сторона оружия противоположна Medusa |
| `pattern` (корень спеки) | спека образца библиотеки, с которой скопирован блок `clips`: путь или `{"spec", "key"}` (§6.1; по нему пишет происхождение `clip_manifest.py`, C53) |
| `clips.*.keys[].aim.<кость>.from`, `from2` | при копии паттерна — **свои** rest-оси героя: `from` — ось кости в rest (у кисти с оружием — ось оружия, `weapon.note`), `from2` — вторая ось базиса (ось кисти, ось сгиба локтя) из замера rest этого героя; `to`/`to2` образца остаются. Чужие оси поворачивают кость на разницу rest двух фигур (C42, Beowulf ← Angel r2) |
| `clips.*.hand_follow[]`: `anchor_offset`, `tip_target`, `offset` | цели в досягаемости руки **этого** героя: после авторинга в `author-<Clip>.json` `ik_log[].follow_<S>_reach_deficit_cm` должен быть −0,5…−1,5 см (цель на 0,5–1,5 см ближе вытянутой руки). > 0 — рука не достаёт (`follow_<S>: false`, кадр в `ik_unreached_frames`), < −1,5 — локоть сильно согнут; смещение образца переносится, только если дефицит в этой полосе (Beowulf: якорь Angel (5; −12; 0) → (3; −11,5; 3), −1,25 см; C42) |

Длины LungeAttack, HitReact и DeathSettle не менять: это константы C++ (§2.1). Пределы, которые не чинятся в клипе
(жёстко скиненный подол, наплечник, поворот головы, IK), описаны в HANDBOOK §4.5 п.4.

Уроки пилота для авторского слоя (до первых ключей):
- **Сначала замер, потом ключи.** Кости rest, след стоп, верх подставки и пределы скина руки с оружием — до ключей:
  смещения кисти Arthur на другую фигуру не переносятся (F48); у Angel разгибание локтя > ~141° и скрутка предплечья
  > ~20° рвут скин, поэтому рубящий удар с мечом, жёстко зажатым в кулаке, идёт подъёмом плеча и поворотом плечевой
  кости (F122). Хват, кисть и локоть по кадрам — `grip_check.py` (§6.3).
- **Ноги.** Прямые ноги в rest при повороте таза дают скольжение стоп: таз опускать на 0,3–0,5 см, когда он
  движется (F48). Журнал IK про недотянутые кадры важен, только когда нога несёт вес (F114).
  После каждого авторинга смотреть `ik_unreached_frames` в `author-<Clip>.json` (кадры, где IK стопы `L`/`R` или руки
  `follow_<S>` не дотянулась) и запас `foot_slide_<L|R>` в `contact-<Clip>.json`: держать ≤ 0,3 % H, а не у порога
  0,5 %. Beowulf (C41): ноги в rest прямые (16,328 из 16,329 см), в недотянутых кадрах стопа ехала до 0,48 % H —
  PASS на краю; опускание таза в этих кадрах убрало и недотяг, и скольжение.
- **Закреплённая рука** (`hand_follow`/пин на оружии): полюс локтя брать в осях арматуры rest, а не в осях корпуса —
  иначе локоть переворачивается назад и кисть крутится на 26–45° (F126).
- **Оружие, упёртое пяткой в подставку** (копьё Achilles): режим `weapon_tip` для него не годится, смещения шарнира —
  вручную; прямой опорной руке кулак под прямым углом стоит 40–45° излома кисти (F128, опции в инструменте нет).
- **Наездники** — жёсткие части на кости руки (ворона Leshen): при подъёме руки они переворачиваются (F115) и могут
  висеть с зазором ещё в rest (F137) — это дефект модели, не клипа (§10.5). Отрыв наездника от деформируемой руки
  валидаторы этапа 6 не ловят (F133): смотреть Blender-листы и крупные планы.
- **Кость `hips` на оси `root`** (Leshen 0, 0, 25): импорт FBX в Blender соединяет `hips` и теряет её ключи
  положения — проверка чтения автором падает (F112, в инструменте не исправлено). Такой FAIL — эта причина; разбор
  оркестратором (`SKILL.md` §5 п.6).

### 6.3 Авторинг и валидация (headless)

```bash
"C:/Program Files/Blender Foundation/Blender 5.2/blender.exe" -b --factory-startup \
    --python tools/tripo-pipeline/anim/clip_author.py -- <ASSET_DIR>/build-profiles/<content-key>-h2anim.json --check-only
python tools/tripo-pipeline/anim/h2anim_run.py <ASSET_DIR>/build-profiles/<content-key>-h2anim.json [--clips=LungeAttack]
```

`h2anim_run.py` по очереди вызывает `clip_author.py`, `validate_clip.py` (с `--character=<Character>`), `clip_contact_check.py`,
`clip_pose_probe.py` и `overlay_bones.py`. Результаты:
- `reports/h2anim-run.json`;
- отчёты validate (§2.2) и `reports/contact-<Clip>.json`;
- листы `preview/<Key>-<Clip>-blender-sheet.jpg`.

Код 0 — всё PASS. Код 3 — sha цели не совпал со спекой: цель перепечена, спеку нужно обновить. Условия PASS — HANDBOOK
§4.5 п.3. PASS валидатора означает соответствие контракту, а не художественную приёмку
(`docs/art-pipeline/animation-library/VALIDATION.md`). Точки входа сами пишут UTF-8 — `PYTHONIOENCODING` для «×» в
трубе cp1251 больше не нужен (F47, 70905fa2).

Что читать в отчётах контактов (`reports/contact-<Clip>.json`):
- `foot_slide_<L|R>` со статусом WARN и `measured: false` — у фигуры нет вершин подошвы (ствол, корни, змеиный
  хвост): скольжение не измерено, а не PASS. Опору проверить отдельно — по кадрам и своим замером (Leshen —
  `roots-planted.json`; F113).
- Оружие — меш `meshes.weapon` и части `weapon.extra_parts` (§6.2): `weapon_body` и `weapon_below_base_top_outside`
  считают их отдельно по каждой части.
- `skin_stretch` FAIL — только видимые рваные рёбра; закрытые — WARN `skin_stretch_hidden`.
- Верх подставки (`below_base_top`, `hem_below_base_top`, `weapon_tip`; `grip_check.py` — `butt_below_top_cm`) — устойчивая
  высота: 90-й перцентиль по площади граней, смотрящих вверх, а не максимум вершин (C40); максимум — в
  `base_top.max_vertex_cm`. Цель `tip_target` острия ставить на видимую поверхность, а не на бугорок: у Beowulf бугорок
  3 мм на 6,00 см при поверхности 5,68 заставлял острие висеть. Острия DeathSettle Angel r2 и Arthur, принятые по
  старому верху, висят над поверхностью на 3,0 и 2,4 мм — повторная проверка их клипов даст FAIL `weapon_tip`.

**Проверки исполнителя** (не гейт и не приёмка: числа для правки ключей и для приёмщика, §10.3):

```bash
"C:/Program Files/Blender Foundation/Blender 5.2/blender.exe" -b --factory-startup \
    --python tools/tripo-pipeline/anim/grip_check.py -- <run>/export/AM_<Key>_<Clip>.fbx <run>/reports/grip-<Clip>.json \
    --side R [--base <SM_<Key>_H2_Base.fbx>] [--shield-bone arm_lower.L] [--weapon-suffix _Spear]
python tools/tripo-pipeline/anim/clip_closeups.py --spec <spec> --clip <Clip> --default-shots   # §10.3; у Idle — с парой шва
```

`grip_check.py`: поворот оружия в кулаке (`weapon_in_hand_deg`, 0 — оружие жёстко в руке), излом кисти, локоть,
колени, пересечение оружия и щита с телом, пятка оружия у подставки. Поворот оружия на 60–90° внутри неподвижного
кулака валидаторы этапа 6 не ловят, а приёмка клипа ставит за него вето D (Angel LungeAttack, F95).

### 6.4 UE: скелет, импорт, замер, кадры (шаг 7a, не этап 6)

Эти команды выполняет этап 7a (`references/ue-import-package.md` §4.1 шаги 3, 5 и §4.5; ДС-1) в агентском редакторе
(§5). Каждая — под `ue_lock.py`. Подкоманды — `h2anim_ue.py:3-8`.

```bash
L="python tools/art/material_library/ue_lock.py"; S=<ASSET_DIR>/build-profiles/<content-key>-h2anim.json
PIN=art/pipeline-candidates/ASSET-HARPY-001/20260929-h3ld-ue/review/b3.2/review-b3.2.json   # свет, F81
export MSYS_NO_PATHCONV=1 UE_LOCK_OWNER=<ASSET_ID>-7a
$L --step "<Key> state"    -- python tools/tripo-pipeline/anim/h2anim_ue.py state
$L --step "<Key> skeleton" -- python tools/tripo-pipeline/anim/h2anim_ue.py skeleton $S [--refresh-preview]
$L --step "<Key> import"   -- python tools/tripo-pipeline/anim/h2anim_ue.py import $S [--clips=LungeAttack]
# notify Contact здесь не ставится: его ставит de010.py apply --only <Key> на шаге 7b (§2.3, §7)
$L --step "<Key> measure"  -- python tools/tripo-pipeline/anim/h2anim_ue.py measure $S
$L --step "<Key> frames"   -- python tools/tripo-pipeline/anim/h2anim_ue.py frames $S --clips=<Clip> --light-pinned $PIN   # по клипу за вызов
$L --step "<Key> closeup"  -- python tools/tripo-pipeline/anim/h2anim_ue.py frames $S --clips=LungeAttack --frames=<a,b,c> --closeup --light-pinned $PIN
python tools/tripo-pipeline/anim/h2anim_ue.py sheet $S                                      # без редактора
```

- `skeleton` идемпотентен для скелета, а меш превью `Rig/SK_<Key>` переимпортирует сам, если sha `SK_<Key>_H2.fbx`
  спеки изменился (новая модель после этапа 5); `--refresh-preview` — принудительно (перезапись FBX на месте по sha
  не видна). `frames` и `measure` на устаревшем меше отказывают (F145, 172fd4f1).
- `frames`: без `--light-pinned` — `SystemExit` (профиль `cobble-probe` удалён ND-5, F81). Подставка по умолчанию —
  `SM_<Key>_H2LD_Base` импорта 7a (`--base <пакет>` — другая, `--no-base` — без неё, F96). Фигура выше ~59 uu —
  камера отходит и центрирует её (`camera.mode fit`, F136). Троттлинг фонового редактора выключается на время съёмки;
  прогрев не сошёлся — `settle.status: not_settled`, кадры переснять (F153).

Отчёты: `reports/ue-canonical-skeleton.json`, `ue-import-clips.json`, `ue-measure-clips.json`, `ue-frames.json`,
`ue-frames-closeup.json`. Кадры: `preview/ue/<Key>-<Clip>-fNN-{front,q34}-ue-editor.jpg` и лист
`preview/<Key>-H2Anim-ue-sheet.jpg`. Условия замера — HANDBOOK §4.6 п.5. Кадры редактора нужны для диагностики и приёмки
клипов 7a.2. Это не K1/K2 и не evidence SHOT: отпечатка RENDER у них нет (`h2anim_ue.py:456-457`).

**После импорта.** Когда `AM_<Key>_HitReact` и `AM_<Key>_DeathSettle` лежат в `Content` (`ue-import-clips.json`),
можно добавлять ключи `<Key>` в CUE-011/013 и гонять `validate-table` (§12.1) — в чекауте этого `Content` (§5). Шаг
относится к регистрации этапа 7 (Р7-6), раньше импорта его не делать. Повторный импорт клипов (доработка клипа или
модели, `references/ue-import-package.md` §4.4) до шага 7b — notify ставит обычный `de010.py apply --only <Key>` (§7);
после 7b — повторить его.

### 6.5 Манифест библиотеки

```bash
python tools/tripo-pipeline/anim/clip_manifest.py build && python tools/tripo-pipeline/anim/clip_manifest.py check
```

Статус `technically_imported` ставит только `build` и только при трёх сходящихся свидетельствах: validate PASS,
контакты PASS, UE-импорт с тем же sha256 FBX (`clip_manifest.py:9-16`). На этапе 6 клипы получают `measured`,
`technically_imported` — после импорта 7a, тогда `build` ещё раз (`references/ue-import-package.md` §4.1 шаг 8).
Статус `artistically_accepted` сборка не пишет никогда, а ручную правку перезапишет. Художественная приёмка
фиксируется в `03-asset-registry.csv` (§12.2) и в карточке §10.

- `check` требует 4 записи h2anim у каждого героя `H2ANIM` (спека, FBX, отчёт) и называет героя с битой
  регистрацией (RB-07): раньше ошибка в `H2ANIM` давала пустой слот и `MANIFEST_CHECK PASS`, а дефект всплывал FAIL
  `G-MANIFEST` на приёмке и съедал цикл клипа.
- Доработанный клип со своей спекой регистрируется строкой `H2ANIM_CLIP["<Character>", "<Clip>"] =
  "<ASSET_DIR>/build-profiles/<content-key>-h2anim-r<N>.json"` (Р6-1, F103); без неё `G-MANIFEST` падает: sha проверки
  ≠ зарегистрированного прогона. Новая спека на все 4 клипа (новая модель) — правка `H2ANIM["<Character>"]` и снятие
  строк `H2ANIM_CLIP` героя.
- `build` пересобирает все слоты и заберёт чужие недоделанные доработки: один сборщик за раз, манифест коммитится
  сразу после доработки (F117).

### 6.6 Дымовой прогон клипов на выходе этапа 3 (RC-06)

В пилоте дефекты модели нашла только приёмка клипов: ворона Leshen висела с зазором 2,9 см (вето D HitReact, F137),
срез руки Achilles под плащом открывался при руке вперёд со спины (вето D DeathSettle, F129, F148). Обе модели уже
прошли приёмку и сожгли на позднем фиксе последний цикл (RC-06). Поэтому сдача модели (этапы 3 и 5) включает дымовой
прогон — пункт чек-листа HANDBOOK §4.4 «Сдача модели». Это не авторинг и не приёмка: чужие ключи на новой модели.

1. Спека дыма — копия спеки образца того же класса оружия (§6.1, §6.2) в `<bake run>/work/smoke/` (`work/` закрыт
   `.gitignore` ассета). Поля — по таблице §6.2, но `run_dir` = `<bake run>/work/smoke/run` (относительный — от корня
   репозитория, абсолютный — как есть; спека и прогон вне репозитория `h2anim_run.py` тоже принимает, ревью
   2026-10-14, R-13), `ue_hero` = `<Key>Smoke` — имена FBX и отчётов дыма не спутать с настоящими клипами. Ключи и волны
   образца не менять; `mirror` у `template` — по стороне оружия. В корень спеки — `"smoke": true` (C28): цели образца
   (`tip_target` острия в `weapon_tip_frames`, точки `hand_follow`) привязаны к его пропорциям и на другом герое не
   сходятся, поэтому `weapon_tip` в `contact-*.json` дыма — замер со статусом info (`status_without_smoke`), а
   `h2anim-run.json` пишет у клипа блок `smoke` (статус острия без дыма, недотянутые кадры `hand_follow`) — в вердикт
   дыма они не входят. Без флага DeathSettle с опорой на меч даёт FAIL на любом другом герое (Beowulf ← Angel r2).
2. `python tools/tripo-pipeline/anim/h2anim_run.py <bake run>/work/smoke/<content-key>-h2anim-smoke.json --out-dir
   <bake run>/work/smoke/validation` — отчёты validate дыма ложатся туда, а не в
   `docs/art-pipeline/animation-library/validation-h2anim/` (отчёты гейта настоящих клипов не трогаются; со `smoke`
   без `--out-dir` — в `<run_dir>/../validation`, то есть туда же); затем `grip_check.py` по LungeAttack и DeathSettle
   (§6.3) и **крупные планы каждого клипа дыма** (C43, C45):
   `python tools/tripo-pipeline/anim/clip_closeups.py --spec <спека дыма> --clip <Clip> --default-shots` →
   `<bake run>/work/smoke/run/preview/closeups-blender/`. Стандартный список по роли клипа: со спины 3/4 на кадре
   наибольшего поворота плеча каждой руки (`armR`/`armL`), ворот и затылок сзади и сзади сверху (`topb`), кулак на
   кадре наибольшего поворота оружия (`gripR`), фигура по роли (у DeathSettle ещё последний кадр с воротом сзади
   сверху); отсечение задних граней включено, как в UE. Открыть (Read) каждый JPEG.
3. Что смотреть: `contact-*.json` — `limb_body`, `skin_stretch` (видимые рёбра), `weapon_body` с `extra_parts`;
   Blender-листы и крупные планы — кромки и срезы при руке вперёд со спины, провал между воротом и шлемом или
   затылком, дыра кулака при повороте оружия, зазор «наездников» к телу. Этого не ловит ни один валидатор: на Beowulf
   срез верха правого рукава (LungeAttack к. 8–9, DeathSettle к. 13, вид `q34b`) и провал ворота за шлемом
   (DeathSettle к. 21, вид `topb`, в игре — C61) видны только на этих кадрах, и без них этап 3 их пропустил (C43).
   `rider_gap.py` на клипах дыма: жёсткие части одной кости (щит + умбон, клинок + навершие) идут одной группой против
   остальной фигуры, их опора — не соседи по кости; постоянный задуманный зазор пары — `--designed-gap ИМЯ=мм`
   (щит над предплечьем Beowulf 5,6 мм), иначе такая пара может только FAIL (C47). Найденное — пункт доработки
   модели до приёмки, а не на клипах. Числа и вывод — строкой в отчёт сдачи модели.
4. После прогона — удалить каталог `<bake run>/work/smoke/` — свой временный выход (`SKILL.md` §11.5); в `docs/` дым
   ничего не пишет.

## 7. Notify `Contact` для нового героя

**Основной путь — `tools/art/de010/de010.py apply --only <Key>` на шаге 7b** (`SKILL.md` §6, этап 7b п.1; сначала
`--dry-run`). Он ставит ровно один `Contact` на LungeAttack героев `--only`, идемпотентно
(`tools/art/de010/de010_apply_ue.py:9-11`). Без `--only` он переставляет notify всем героям списка `HEROES` и
пересохраняет их клипы (в пилоте — MVP, F157). Для нового героя нужна строка `HEROES` (регистрация Р7-1,
`references/new-character-registration.md` §5.1). Ограничения: он запускает свой `UnrealEditor-Cmd` (GUI-редактор этого
чекаута закрыт: агентский — оркестратором, интерактивный — гейт `SKILL.md` §5 п.7), а `M_UM_Figure_v2` пересобирает
только при смене графа (`tools/art/de010/master-builds.json`). После любого повторного импорта LungeAttack
`de010.py apply --only <Key>` повторить.

**Запасной путь — задача живого редактора ниже**: только notify одного клипа, без пересборки материала, под
`ue_lock.py`. Применять, когда notify нужен до шага 7b в редакторе 7a. Строку Р7-1 и шаг 7b он не заменяет.
Задача собрана из вызовов, которые DE-010 уже проверил (`tools/art/de010/de010_apply_ue.py:57-70`), и запускается через
`ue_live.Ue().run_task` (`tools/tripo-pipeline/review/ue_live.py:190`). Отдельным шагом она ещё не прогонялась (не
проверено): первый прогон сверить по JSON-отчёту.

Сохранить файл вне репо, например `C:/tmp/skill-<content-key>/contact_notify_task.py`:

```python
# Задача UE для ue_live.Ue().run_task: ARGS = {"out", "path", "frame", "fps"}; ARGS и unreal даёт ue_py/_run.py
import json
u = unreal  # noqa: F821
LIB, EAL, TRACK = u.AnimationLibrary, u.EditorAssetLibrary, "Contact"
path = ARGS["path"]  # noqa: F821
seq = u.load_asset("%s.%s" % (path, path.rsplit("/", 1)[-1]))
if seq is None:
    raise RuntimeError("asset not found: " + path)
removed = LIB.remove_animation_notify_events_by_name(seq, "Contact")
if not LIB.is_valid_anim_notify_track_name(seq, TRACK):
    LIB.add_animation_notify_track(seq, TRACK, u.LinearColor(1.0, 0.25, 0.2, 1.0))
t = float(ARGS["frame"]) / float(ARGS["fps"])  # noqa: F821
if LIB.add_animation_notify_event(seq, TRACK, t, u.S08ContactAnimNotify.static_class()) is None:
    raise RuntimeError("could not add the Contact notify at %.4f s" % t)
if not EAL.save_loaded_asset(seq, False):
    raise RuntimeError("could not save " + path)
events = [{"name": str(e.get_editor_property("notify_name")),
           "time": round(float(LIB.get_anim_notify_event_trigger_time(e)), 5)}
          for e in LIB.get_animation_notify_events(seq)]
with open(ARGS["out"], "w", encoding="utf-8") as h:  # noqa: F821
    json.dump({"path": path, "time": round(t, 5), "removed": int(removed), "notifies": events,
               "play_length": round(float(seq.get_play_length()), 5)}, h, indent=1)
```

```bash
MSYS_NO_PATHCONV=1 python tools/art/material_library/ue_lock.py --step "<Key> Contact notify" -- \
  python -c "import sys; sys.path.insert(0, 'tools/tripo-pipeline/review'); from ue_live import Ue; print(Ue().run_task(sys.argv[1], sys.argv[2], path=sys.argv[3], frame=int(sys.argv[4]), fps=24))" \
  C:/tmp/skill-<content-key>/contact_notify_task.py <ASSET_DIR>/<YYYYMMDD>-h2anim/reports/ue-contact-notify.json \
  /Game/PipelineCandidates/<Key>/H2Anim/AM_<Key>_LungeAttack <LUNGE_CONTACT_FRAME>
```

Критерий успеха — в `ue-contact-notify.json` ровно один `Contact` с `time = LUNGE_CONTACT_FRAME / 24` (± 0,5 кадра) и
`play_length`, равный N/24. Если запасная задача упала — дождаться шага 7b (`de010.py apply`). Пока notify нет, рантайм
берёт `ProfileContactSeconds` и тайминг удара верен, но автотест `Unmatched.S08.HeroesV2.Contact` этапа 7 падает.
Если и `de010.py apply` не ставит notify — разбор оркестратором, а не вопрос пользователю (`SKILL.md` §5 п.6, ДС-2;
HANDBOOK §0.3 п.3 — FAIL проверки, п.6 — если упал или завис редактор): путь клипа, кадр и вывод `de010.py` — в строку
F; исправление — фиксом или опцией `de010` с тестом, а не ручной правкой ассета в редакторе.

## 8. VFX нового ассета: слоты

| Слот | CUE | Что нужно от ассета | По умолчанию |
|---|---|---|---|
| Звезда удара | CUE-011 | ничего: world, точка контакта по капсуле цели | работает сразу |
| Вспышка и обод фигуры | CUE-011 `material` (CPD `FxFlash`) | MI героя от `M_UM_Figure_v2` (этап 7) | работает через мастер |
| Лечение | CUE-012 | ничего (`Base` — подставка актора) | работает сразу |
| Пепел смерти | CUE-013 | MIC растворения героя (`tools/art/de011/de011.py`, регистрация этапа 7) | без MIC угольков нет (заметка CUE-013 в `cue-table.json`) |
| Способность | CUE-014 `vfx.by_hero.<Key>` | система, сокет, строка `Make(...)` в `S08CueFx.cpp`, запись `by_hero` | нет; фолбэк CUE-014: «иконка способности в HUD без VFX и звука» |
| Полевые FX (ход, цель, выбор) | — | ничего | работают сразу |

**Решение скилла (по делегированию):** новый герой по умолчанию идёт без FX способности. FX способности делается только
отдельной задачей по образцу FX-29…FX-32 (`docs/game-design/visual/06-tasks/vfx.csv`):
1. флипбук Codex по шаблону `T-CODEX-VFX`;
2. Niagara-сборка скриптом по образцу `tools/art/fx/fx_ability.py`; сейчас он зашит на Arthur и Medusa, расширение —
   пункт регистрации;
3. запись `by_hero` в CUE-014, строка `S08CueFx.cpp`, `cue_contract.py validate-table`;
4. стиль ВР-19, один замер ВР-25.

В заявке: `STAGE6_SLOTS.ability_fx: none` с `decided_by: delegated (ВР-реестр 2026-10-06)`.

## 9. SFX нового ассета: слоты (02-audio-design.md §8.1)

| Слот | Обязателен | Действие по умолчанию |
|---|---|---|
| `hit_type` | да | Выбрать по оружию из готовых `BLADE`, `CLAW`, `ARROW`, `MAGIC`: у них есть оба банка, `CMB-HIT-*` и `CMB-LUNGE-*` (рецепты `tools/audio/sfx_build.py:539-591`). Выбор записать в поле `HIT_TYPE` заявки на этапе 6; ключ героя в `S08AudioBank::CharacterKey` и тип в `HitType` (`S08AudioBank.cpp:54-68`) дописываются правкой C++ этапа 7 (регистрация Р7-5). Для `BLUNT` и `BEAST` есть только `CMB-HIT-*`, рецепта выпада нет: добавить рецепт `CMB-LUNGE-<TYPE>` по образцу `sfx_build.py:539-560` и строку реестра |
| Звук смерти | да | Общий `DTH-TEMPLATE` работает автоматически, если банка `DTH-<KEY>` нет. Свой звук — рецепт `DTH-<KEY>` по образцу `sfx_build.py:653-692` и строка реестра |
| Способность (1–3 звука) | если есть способность | По умолчанию нет. Хуки звука способности — код `S08FlowGameModeAudio.cpp`; это отдельная задача вместе с FX способности (§8) |
| VO, лейтмотив, фирменные карты | нет | По умолчанию нет: без VO герой молчит, остальное работает (02-audio-design.md §8.1). Если всё же делать: VO — SYNTX ElevenLabs по 02-audio-design.md §3 и `tools/audio/vo_batch.py`, траты в журнал §6.1 |

Готовые банки и `DTH-TEMPLATE` не требуют новых аудиофайлов. Нужна только правка C++ (регистрация) и пересборка на
этапе 7. Если `S08AudioTests.cpp:49` использует имя нового героя как образец «неизвестного героя» (сейчас там
`"Robin Hood"`), заменить образец в тесте.

**Конвейер нового звука** (только если добавлен рецепт). SFX — это CC0 Kenney и собственный синтез, а не SYNTX
(02-audio-design.md §0):

```bash
python tools/audio/sfx_build.py --kenney C:/tmp/audio-src/kenney --out C:/tmp/audio-src/final/sfx --only <ID>
python tools/audio/ue_bank.py --final C:/tmp/audio-src/final --manifest C:/tmp/audio-src/ue-import.json \
    --cpp-out unreal/Unmatched/Source/Unmatched/S08
git diff --numstat -- unreal/Unmatched/Source/Unmatched/S08/S08AudioBankData.inl unreal/Unmatched/Source/Unmatched/S08/S08VoLinesData.inl
```

`ue_bank.py` переписывает банк целиком по содержимому `--final`. Поэтому в diff допустимы только добавленные строки
нового ID. Удалённая строка значит, что `C:/tmp/audio-src/final` неполон: откатить файлы `.inl` (`git restore` по
имени файла) и остановиться.

Импорт только новых ассетов. Отфильтровать манифест по имени, затем запустить коммандлеты в окне шага 7b, когда
GUI-редактора на чекауте нет (§5):

```bash
python -c "import json,sys; m=json.load(open(sys.argv[1])); json.dump([x for x in m if x['name'].startswith(sys.argv[3])], open(sys.argv[2],'w'), indent=1)" \
    C:/tmp/audio-src/ue-import.json C:/tmp/audio-src/ue-import-<ID>.json SW_<ID_с_подчёркиваниями>
"C:/Program Files/Epic Games/UE_5.8/Engine/Binaries/Win64/UnrealEditor-Cmd.exe" <checkout>/unreal/Unmatched/Unmatched.uproject \
    -run=pythonscript -script="<checkout>/tools/audio/ue_import_audio.py C:/tmp/audio-src/ue-import-<ID>.json" -unattended -nosplash -nullrhi
"C:/Program Files/Epic Games/UE_5.8/Engine/Binaries/Win64/UnrealEditor-Cmd.exe" <checkout>/unreal/Unmatched/Unmatched.uproject \
    -run=pythonscript -script="<checkout>/tools/audio/ue_verify_audio.py C:/tmp/audio-src/ue-import-<ID>.json" -unattended -nosplash -nullrhi
```

Путь движка — `UE_ROOT`, по умолчанию `C:\Program Files\Epic Games\UE_5.8` (`tools/art/de010/de010.py:42`). Критерии:
- `AUDIO-IMPORT summary … failed=0`;
- `ue-import-<ID>-verify.json` → `problems: 0`;
- строка ID в `03-sound-registry.csv` с пометкой о прослушивании (§4.3);
- автотесты `Unmatched.S08.Audio.*` на этапе 7.

## 10. Приёмка клипов (`kind=anim`)

Механика та же, что у модели (вызов приёмщика, формула, вердикт, бриф доработки): `references/acceptance-and-blender.md`.
Схема — `tools/art/acceptance/asset-acceptance-2.schema.json` (ветка `kind: anim`). Судья согласованности —
`python tools/art/acceptance/validate_card.py <card.json> --print-verdict --check-files`. Если поле в этом разделе
расходится со схемой, права схема.

Когда: шаг 7a.2, после импорта клипов, `measure`, `clip_manifest.py build` и UE-кадров (ДС-1;
`references/ue-import-package.md` §4.5). Не на этапе 6: без UE-импорта гейт `G-MANIFEST` даёт FAIL, а `validate_card.py`
не принимает `n/a` у клипа — карточка сожгла бы цикл (F43).

Промпт приёмщика клипа — шаблон acceptance-and-blender.md §8.2 с такими заменами: заголовок «Приёмка клипа
AM_<Key>_<Clip>, цикл <rN> (шаг 7a.2)»; рубрика — этот файл §2.1, §2.3, §10.2–§10.5, механика формулы и полей карточки
— acceptance-and-blender.md §6, §7; «Вход» — кадры и материалы §10.3; «Порядок» — гейты `G-VALIDATE`, `G-CONTACT`,
`G-MANIFEST` по отчётам, баллы R, C, D, L по кадрам; константы `schema "unmatched.anim-acceptance/1"`, `kind "anim"`,
`clip "<Clip>"`. Вызов — §8.3 (или §8.4) того же файла, label `acceptor-<ASSET_ID>-<Clip>-r<N>`; Workflow-приёмщику
— строгая схема `tools/art/acceptance/asset-acceptance-2.output-anim.schema.json` (RA-11). Образец заполненного
промпта — `art/pipeline-candidates/ASSET-BEOWULF-001/evidence/acceptance-anim/20261014-r1/LungeAttack/acceptor-prompt.md`
(полный блок чтения кириллицы п.3 и блок известных пределов п.4); образец заготовки этапа 6 с `{{KNOWN_LIMITS}}` —
`art/pipeline-candidates/ASSET-BEOWULF-001/evidence/acceptance-anim-prompts/LungeAttack/acceptor-prompt.md` и рядом
`known-limits.md`. Прежний образец Achilles r2 нёс старый OEM-блок без «читай КАЖДЫЙ файл» и без «СБОЙ ОКРУЖЕНИЯ» и
не знал `{{KNOWN_LIMITS}}` (C46) — по нему не копировать.

Заготовку промпта на каждый клип пишет этап 6: `<ASSET_DIR>/evidence/acceptance-anim-prompts/<Clip>/acceptor-prompt.md`
с плейсхолдерами `{{E}}`, `{{DATE}}`, `{{CYCLE}}`, `{{PREVIOUS_CARD_JSON}}`, `{{FRAMES_FILES_JSON}}`, `{{KNOWN_LIMITS}}`
и служебным комментарием `<!-- … -->`; на шаге 7a.2 их заполняет `tools/tripo-pipeline/ue7a/prep_acceptance.py` (сверяет
sha клипа и спеки, вставляет заметку о меше-носителе UE-кадров и список `known-limits.md`, §10.5). Обязательные блоки
каждого промпта приёмщика клипа:

1. Цитата делегирования пользователя (2026-10-06) дословно и «траты на этом шаге: нет».
2. Роль: приёмщик ничего не правит и не запускает, выдача — только JSON карточки.
3. **Блок чтения кириллицы (RA-03) — дословно, как в `references/concept-sheet.md` §11**; меняется только строка
   рубрики. Без него Sol читал рубрику кракозябрами при коде 0 (F36), а без строки «рубрика — только эти файлы»
   открывал SKILL.md вне входов (F75):

   ```text
   Текстовые файлы читай так, чтобы кириллица дошла целой. В песочнице codex PowerShell работает в Constrained
   Language Mode и пишет вывод в OEM-кодировке: `Get-Content -Encoding UTF8` даёт кракозябры, смена
   `[Console]::OutputEncoding` запрещена, `rg` нет. Рабочие способы (проверено пробой 2026-10-13): читай КАЖДЫЙ
   текстовый файл (рубрику, JSON-отчёты, предыдущую карточку) командой
   `Get-Content <файл> -Raw -Encoding OEM` (байты UTF-8 проходят без перекодировки и читаются верно) или
   `cmd /c type <файл>`. Кодовые точки (`[int[]][char[]]`) не нужны. Если кириллица рубрики всё равно пришла
   кракозябрами — это сбой окружения: не оценивай по догадкам, верни карточку, где verdict_reason начинается со слов
   «СБОЙ ОКРУЖЕНИЯ: кириллица не читается».
   Рубрика (обязательна к прочтению целиком): .agents/skills/3d-model-pipeline/references/animation-vfx-sfx.md §2.1,
   §2.3, §10 (гейты §10.2, кадры §10.3, измерения и якоря §10.4, вердикт §10.5); механика формулы, вердикта и полей
   карточки — .agents/skills/3d-model-pipeline/references/acceptance-and-blender.md §6 и §7 (где они расходятся с §10 —
   прав §10 и схема). Рубрика — ТОЛЬКО эти два файла: SKILL.md и другие файлы скилла (.agents/skills/**, кроме
   animation-vfx-sfx.md и acceptance-and-blender.md) не открывай и не учитывай.
   ```

   Карточка, где `verdict_reason` начинается со «СБОЙ ОКРУЖЕНИЯ», — сбой окружения, а не приёмка: цикл клипа не
   тратится, балл не пишется; разбор оркестратором (ДС-2), затем тот же вызов заново (acceptance-and-blender.md §8.4).
4. «Вход» — список §10.3 и блок «Известные пределы этой фигуры» (§10.5): один список на фигуру, одинаковый во всех
   четырёх промптах героя, а не свободный текст в каждом (F156).
5. «Порядок», константы карточки и «Запрещено» — как в образце выше.

### 10.1 Единица, циклы, путь

- Единица приёмки — **один клип**. Вердикт героя — pass, когда все 4 клипа pass.
- Циклы на клип: r1 → доработка → r2 → доработка → r3, то есть не больше 2 доработок. После r3 без pass —
  `escalate_user` (`SKILL.md` §5 п.4). Перепринятие после позднего фикса модели с неизменными ключами цикла не
  тратит (§10.5).
- Путь (решение скилла): `<ASSET_DIR>/evidence/acceptance-anim/<YYYYMMDD>-r<N>/<Clip>/card.json` и рядом `frames/`. Если
  в цикле r2 переделывается один клип, в каталоге r2 лежит только он. Перепринятие после позднего фикса —
  `…/<YYYYMMDD>-r<N>-m<M>/<Clip>/` (`SKILL.md` §9, словарь суффиксов).

### 10.2 Гейты (PASS/FAIL из отчётов, не баллы)

| Гейт | PASS, если | Источник |
|---|---|---|
| `G-VALIDATE` | `result: pass` | `docs/art-pipeline/animation-library/validation-h2anim/AM_<Key>_<Clip>.validation.json` |
| `G-CONTACT` | `result: pass` | `<run>/reports/contact-<Clip>.json` |
| `G-MANIFEST` | `clip_manifest.py check` прошёл и у клипа статус `technically_imported` (то есть есть UE-импорт 7a с тем же sha256; доработанный клип — со строкой `H2ANIM_CLIP`, §6.5) | `clip-manifest.json` |

Notify `Contact` в приёмку клипа не входит: его ставит `de010.py apply --only <Key>` на шаге 7b, проверяет автотест
`Unmatched.S08.HeroesV2.Contact` (§2.3, §7). Время контакта клипа проверяют `G-CONTACT` и измерение C.

### 10.3 Кадры приёмщика

Кадры копируются в `frames/` инструментом `tools/tripo-pipeline/ue7a/prep_acceptance.py` (шаг 7a.2) с прежними
именами и не больше 1200 px по длинной стороне, JPEG q92 — как у кадров модели (ДС-8, RC-22; ревью 2026-10-14, R-03):
UE-кадр 1920 × 1080 → 1200 × 675, Blender-лист 1680 × 2520 → 800 × 1200, UE-лист 4200 × 1860 → 1200 × 531. Листы
уменьшаются целиком, а не режутся на части: лист — обзор движения, детали — в покадровых UE-кадрах и крупных планах
того же клипа, а одно имя листа сохраняет список кадров циклов r2+. Кадр не больше 1200 px копируется байт в байт,
оригиналы в `<run>/preview` не меняются; `--max-px 0` — копия как есть. Состав:
- Blender-лист `<Key>-<Clip>-blender-sheet.jpg` (§6.3);
- крупные планы Blender (RA-27, F146): `python tools/tripo-pipeline/anim/clip_closeups.py --spec <S> --clip <Clip>
  --default-shots [--shots "<свои кадры>"]` → `<run>/preview/closeups-blender/<Key>-<Clip>-fNN-<view>.jpg`, камера
  каждого кадра — в `<Key>-<Clip>-closeups.json`; на r1 — стандартный список по роли клипа (§6.6 п.2, C45) плюс свои
  кадры исполнителя; на r2/r3 — `--shots-from <отчёт прежнего цикла>`, те же камеры числами и то же отсечение задних
  граней (у пилота разовый скрипт камеру не записывал, и r2 нельзя было снять один в один);
- у Idle — пара шва цикла `<Key>-Idle-seam-fNN-f00-{front,q34}.jpg`: последний кадр и кадр 0 одной камерой, разница —
  `seam.views.*.diff_px` отчёта (F154: по ключам 0/15/30/45 приёмщик шва не видел, и L держался на 1,5);
- UE-кадры `<Key>-<Clip>-fNN-front-ue-editor.jpg` и `<Key>-<Clip>-fNN-q34-ue-editor.jpg` (§6.4);
- у LungeAttack — крупный план `*-closeup-ue-editor.jpg` кадров вокруг контакта;
- лист `<Key>-H2Anim-ue-sheet.jpg`.

Кроме кадров приёмщик получает:
- `design` клипа из спеки — цитатой в промпте; саму спеку с заметками исполнителя он не открывает;
- `LUNGE_CONTACT_FRAME`;
- отчёты validate, contact и `ue-measure-clips.json`;
- заметку о меше-носителе UE-кадров (серый, без look-dev материалов, подставка `SM_<Key>_H2LD_Base`; вставляет
  `prep_acceptance.py`): цвет и материал в приёмке клипа не оцениваются;
- референс §6.1 (`contact-sheet-2fps.png` образца библиотеки или своего видео, если есть) и `reference_kind`;
- лист концепта и QUALITY_REFERENCE для характера героя;
- блок известных пределов фигуры (§10.5).

Отчёты исполнителя — только машинные JSON инструментов репозитория, с числами, без текста исполнителя (RA-27; правило
независимости acceptance-and-blender.md §1 п.3): `grip-<Clip>.json` (`grip_check.py`, §6.3), `author-<Clip>.json`
(журнал IK), `contact-<Clip>.json`, отчёт validate, `ue-measure-clips.json`. Свободный текст исполнителя («закрыто»,
«читается лучше»), его заметки в спеке (`status_note`, `note`) и отчёт доработки приёмщику не идут (F118, F147). На
r ≥ 2 приёмщик получает пункты прежней карточки — пункт, кадр, текст прежнего приёмщика — и в rationale отмечает по
каждому «rN п.K: закрыт» или «не закрыт — что видно, кадр» (F99, как у модели).

Игровые листы K1/K2 (`tools/art/anim/clip_review_sheet.py`, с отпечатком RENDER) появляются на этапе 7, после
подключения S08. Ниже сказано, как они связаны с этим вердиктом (§11).

### 10.4 Измерения (0–2, шаг 0,5)

Все четыре измерения применимы к каждому клипу.
`score = round((R + C + D + L) / 8 × 10, 1)`, pass при `score >= 8.0`. Вето: любое измерение < 1,0.

| Измерение | 0 | 0,5 | 1 | 1,5 | 2 |
|---|---|---|---|---|---|
| **R** читаемость и тайминг | действие не читается или противоречит роли | поза ключевого кадра неразборчива с q34 | читается, но тайминг плоский: нет замаха, проводки или дыхания | ясно, мелкие огрехи ритма | замах → удар → проводка → возврат (Idle — живое дыхание) ясны с front и q34; характер героя виден; спиной к камере нет (ВР-06) |
| **C** контакт и опора | удар не в кадре контакта или оружие проходит сквозь тело; стопы едут | контакт смещён на ≥ 2 кадра | контакт на кадре, но удар без веса; опора с заметными огрехами | мелкие огрехи | удар точно в `LUNGE_CONTACT_FRAME` и с весом (HitReact — реакция на удар с нужной стороны); стопы и подол держат подставку (Idle, DeathSettle — опора) |
| **D** деформация в движении | разрыв скина или дыра видна на крупном плане | заметный залом на пике | залом виден только в одном кадре на крупном плане | следы без разрывов | на пике амплитуды оболочка цела, суставы с оружием чисты на крупном плане |
| **L** оседание и цикл | шов Idle виден скачком или финал не совпадает с ролью | рывок на возврате или в финале | возврат или финал механичны | почти незаметно | шов Idle невидим; oneshot мягко садится в rest; DeathSettle держит финальную позу без дрожи |

### 10.5 Вердикт

Правило фиксированное (`validate_card.py`):
- любой гейт FAIL, вето (измерение < 1,0) или `score < 8.0` → `rework_blender` (доработка клипа);
- иначе `pass`;
- после r3 без pass → `escalate_user`.

**Устойчивый pass клипа** (решение оркестратора по калибровке 2026-10-09, раунд 3; то же правило, что у модели,
`references/acceptance-and-blender.md` §6, §8.5, §13). `pass` со `score` 8,0–8,4 одной карточкой не окончателен:
`validate_card.py` даёт код **3** и печатает `needs_second_acceptor`. Порядок:
1. Второй приёмщик — **другой профиль** («Sol 6.1 xhigh» при первом «Opus xhigh» и наоборот), тот же промпт, те же
   кадры `frames/` клипа, новый контекст; первую карточку он не видит. Ответ — `<Clip>/card-2.json` (для Sol —
   `--output-schema tools/art/acceptance/asset-acceptance-2.output-anim.schema.json -o <E>/<Clip>/card-2.json`, остальное —
   команда `references/acceptance-and-blender.md` §8.4 с `windows.sandbox="unelevated"`; для Opus — сохранённый
   workflow `second-acceptor` со схемой `…output-anim…` и label `acceptor2-<ASSET_ID>-<Clip>-r<N>`, затем
   `finish_second.py`, там же §8.3).
2. Итог пары: `python tools/art/acceptance/validate_card.py <E>/<Clip>/card.json --second <E>/<Clip>/card-2.json
   --final-json <E>/<Clip>/final.json --print-verdict --check-files`. `score` — минимум двух; вердикт — карточки с
   меньшим `score` (при равенстве — более строгий), строгий маршрут другой карточки (`rework_blender` по гейту или вето)
   побеждает. Маршрут и `rework_fix_list` — из `final.json#source_card`; бриф §10.6 берёт список оттуда.
3. Второй `pass` в той же полосе — итог `pass`. Другой профиль не запускается после пробы — второй приёмщик того же
   профиля в новом контексте и `--same-profile-ok`.

Расширенное покрытие `rework_fix_list` модели (при `score < 8` — каждое измерение ниже 2) к клипу тоже не
применяется: у клипа список покрывает FAIL-гейты и вето, как ниже.

Если `verdict != pass`, обязателен `verdict_reason`; при `rework_blender` `rework_fix_list` не пуст и покрывает каждый
FAIL-гейт и каждое измерение < 1,0 (схема и `validate_card.py`). Пункты списка (`item`, `frame`, `fix`, `tool`)
ссылаются только на измерения ниже 2 и на FAIL-гейты. При pass в `status_note` пишется «художественно принято, по
делегированию» со ссылкой на `docs/game-design/decisions/2026-10-06-visual-delegated-decisions.md`.
`acceptor.profile`: «Opus xhigh» или «Sol 6.1 xhigh» — профиль фактического запуска (RA-17, F119). Сессия
приёмщика ≠ `executor_session_id`.

**Известные пределы фигуры** (F141, F156; правило скилла). Пределы, которые клипом не чинятся (HANDBOOK §4.5 п.4:
жёсткий подол, наплечник, поворот головы, IK; у фигуры — свои: щит без кости, наездник на руке, F115), — один список на
фигуру: `<ASSET_DIR>/evidence/acceptance-anim-prompts/known-limits.md`. Этап 6 пишет его, а во все 4 заготовки ставит
блок «Известные пределы этой фигуры» с плейсхолдером `{{KNOWN_LIMITS}}`: `prep_acceptance.py` подставляет текст файла
(комментарии `<!-- … -->` убираются, пустой файл — «нет»; свой файл — `--known-limits`); заготовка с плейсхолдером без
файла — код 2. Правка списка — только в файле. Оценка одна на все клипы (в пилоте один и тот же срез у подмышки
получил D 1,5 в LungeAttack и D 0 в DeathSettle, F141):
- предел без видимого разрыва — в `rationale` и `known_issues`, не в `rework_fix_list`; балл за него не ниже 1,0 (вето
  пределом не ставится);
- если на крупном плане предел даёт разрыв, дыру или отрыв части (якорь D 0), это уже не предел, а дефект модели:
  пункт `rework_fix_list` с `tool: "этап 5 модели: <ключ профиля bake или стадия>"` и маршрут ниже.

**Клип вскрыл дефект модели — поздний фикс** (RA-08, RC-06; правило скилла, `SKILL.md` §5 п.4). Дефект модели —
то, что видно в rest или при допустимой амплитуде и ключами клипа не чинится: зазор «наездника» к телу (Leshen,
`prepare.part_offsets_m`, F137), рваный срез конечности под плащом (Achilles, `rig.junctions`, F129, F148), рвущийся
скин (веса).
1. **Список правок пишет приёмщик клипа**: пункт с `tool: "этап 5 модели: …"` в его карточке. Этап 5 идёт только по
   карточке `rework_blender` (acceptance-and-blender.md §9.1); оркестратор пунктов не составляет и не добавляет — в
   пилоте его пункт оказался ложным FAIL инструмента (F149). Свои наблюдения оркестратор передаёт следующему
   приёмщику модели кадрами, а не текстом брифа.
2. **Цикл модели тратится**: этап 5 по этой карточке (`source_card` в `STAGE5[]` заявки) → новый прогон модели
   `…-r<N+1>` с `--reuse-from` (ДС-7) → сдача модели (HANDBOOK §4.4) → приёмка модели цикла r<N+1> (на r ≥ 2 второй
   приёмщик видит `changed_vs_previous`). Циклов модели не осталось — один поздний фикс сверх лимита, приёмка `r4`
   (схема карточки модели её принимает; не-pass на `r4` → `escalate_user`, `references/acceptance-and-blender.md` §6);
   второй дефект модели из клипов — `escalate_user`.
3. **Что перепринимается** после pass модели. Новый `SK_<Key>_H2.fbx` меняет sha цели, поэтому все 4 клипа авторятся
   заново по новой спеке `<content-key>-h2anim-r<N>.json` (тот же блок `clips`, новый `target`; `H2ANIM` → новая
   спека, строки `H2ANIM_CLIP` героя снять, §6.5). В UE (7a): переимпорт меша (`references/ue-import-package.md` §4.4),
   меш превью через `skeleton` по sha (п.4 там же), клипы `import` и `measure`, `verify.clips_reference`,
   `clip_manifest.py build`, UE-кадры — и приёмка всех 4 клипов: прежние карточки описывают другой FBX.
4. **Цикл клипа не тратится**, если ключи клипа не менялись. Карточка перепринятия — с тем же `cycle`, что у
   последней карточки клипа, в каталоге `evidence/acceptance-anim/<YYYYMMDD>-r<N>-m<M>/<Clip>/` (M — номер прогона
   модели); `previous_card` — по правилу `validate_card.py` (у r1 `null`, у r2+ — карточка цикла r<N-1>); прежняя
   карточка этого цикла — в `rationale` и `status_note` («перепринятие после позднего фикса модели r<M>, ключи те
   же»). Клип, ключи которого менялись, — обычный следующий цикл r<N+1>.
5. Поздний фикс отмечает в списке известных пределов, какие пункты закрыты (F156).

### 10.6 Доработка клипа (лично «Opus xhigh», бриф ниже)

Бриф модели (`references/acceptance-and-blender.md` §10) для клипа не годится: он разрешает только `run_h2_bake.py` и
профили bake/look-dev. Клип дорабатывается по брифу ниже. Работа делится так:
- исполнитель «Opus xhigh» (агент Workflow `{model: 'opus', effort: 'xhigh'}`, как в acceptance-and-blender.md §1) —
  только правка новой спеки и headless `h2anim_run.py`, без Unreal. Фактический механизм, модель и effort — в
  `STAGE6.executor` заявки и в `executor_session_id` следующей карточки (RA-21);
- запускающий агент — до брифа: новая спека; после отчёта исполнителя: регистрация `H2ANIM_CLIP` (§6.5), шаги §6.4
  на шаге 7a под `ue_lock.py`, `verify.clips_reference` (`references/ue-import-package.md` §4.4 п.5),
  `clip_manifest.py build`, каталог нового цикла `prep_acceptance.py --previous …` и вызов **нового** приёмщика.

Правила:
- **Новая спека и новый прогон на доработку** (одно правило, F123, F103): копия прежней спеки —
  `<ASSET_DIR>/build-profiles/<content-key>-h2anim-r<N>.json` с `run_dir` `<ASSET_DIR>/<YYYYMMDD>-h2anim-r<N>` (номер —
  следующий свободный, `SKILL.md` §9); прежние спека и прогон не трогаются. Так шёл пилот
  (Angel `angel-h2anim-r2.json`).
- Разрешено править только блок клипа в новой спеке: `keys`, `waves`, `key_frames`, `ik_feet`, `hand_follow`, вес и
  `mirror` у `template`, `amplitude_scale`.
- `target`, `fps`, длины кадров (§2.1) и `LUNGE_CONTACT_FRAME` не менять. Новые кости не добавлять.
- Пункт с `tool: "этап 5 модели…"` клипом не чинится: маршрут позднего фикса (§10.5).

```markdown
# Доработка клипа AM_{{KEY}}_{{CLIP}}: приёмка {{CYCLE}} → r{{N_NEXT}} (этап 6 скилла 3d-model-pipeline; приёмка — шаг 7a.2)

Делегирование пользователя (2026-10-06, дословно): «Не знаю. Делай сам, меня это не касается. Все решения
принимай». Траты: нет — кредиты Tripo/SYNTX, Unreal и упаковка на этом шаге запрещены.

Ты — исполнитель доработки «Opus xhigh». Работаешь лично, не делегируешь, свою работу не принимаешь.
Норма — docs/art-pipeline/BLENDER-MODEL-HANDBOOK.md §2.8, §4.5; правила —
.agents/skills/3d-model-pipeline/references/animation-vfx-sfx.md §2.1, §6.2, §6.3, §10.6 (прочитать).

## Вход
- Карточка: {{E}}/{{CLIP}}/card.json (verdict rework_blender) и кадры {{E}}/{{CLIP}}/frames/.
- Спека: {{SPEC_NEXT}} — копия {{SPEC}} с run_dir {{RUN_NEXT}} (готовит запускающий); править только
  clips.{{CLIP}}. Референс: {{REF_DIR}}.
- Отчёты прошлого прогона (только чтение): {{RUN}}/reports/h2anim-run.json, contact-{{CLIP}}.json, grip-{{CLIP}}.json,
  {{RUN}}/preview/closeups-blender/{{KEY}}-{{CLIP}}-closeups.json,
  docs/art-pipeline/animation-library/validation-h2anim/AM_{{KEY}}_{{CLIP}}.validation.json.

## Правки — только эти пункты rework_fix_list
{{FIX_LIST — по пункту: item · frame · fix · tool}}

## Границы
- Только ключи clips.{{CLIP}} в {{SPEC_NEXT}}: keys, waves, key_frames, ik_feet, hand_follow, template (вес, mirror),
  amplitude_scale. target, fps, frames, design-кадр контакта {{CONTACT_FRAME}}, другие клипы и прежнюю спеку
  {{SPEC}} не трогать.
- Только headless: python tools/tripo-pipeline/anim/h2anim_run.py {{SPEC_NEXT}} --clips={{CLIP}}; свои проверки —
  grip_check.py (по LungeAttack и DeathSettle — всегда) и clip_closeups.py --spec {{SPEC_NEXT}} --clip {{CLIP}}
  --shots-from <отчёт closeups прошлого прогона> (animation-vfx-sfx.md §6.3, §10.3).
  Живой Blender — только осмотр. Код tools/tripo-pipeline/** не менять.
- Без Unreal, без кредитов, без коммитов, без git add/stash/reset/checkout. Свои Blender-процессы — остановить по PID.
- Пункт с tool «этап 5 модели…» не делать: пометить «не закрыто: дефект модели, поздний фикс §10.5».

## Готово, если
- h2anim_run.py дал код 0; validate и contact клипа — pass; новых FAIL нет.
- Каждый пункт списка закрыт по листу preview/{{KEY}}-{{CLIP}}-blender-sheet.jpg и крупным планам того же типа, что у
  приёмщика (открыть и посмотреть; числовое закрытие без кадра — не закрытие, F100), либо помечен
  «не закрыто: <причина>».

## Отчёт (последнее сообщение)
- Ключи спеки: было → стало, по пункту списка; sha256 нового FBX клипа и новой спеки; что не закрыто и почему.
- Механизм запуска, модель и effort этого исполнителя.
Баллы и вердикт не ставь: повторная приёмка — новый агент-приёмщик. Твой отчёт приёмщику не передаётся.
```

После брифа запускающий проверяет `git status --short` (изменились только новая спека, новый run-каталог —
`export/AM_<Key>_<Clip>.fbx`, отчёты и листы — и отчёт validate), дописывает `H2ANIM_CLIP` (§6.5), на шаге 7a
выполняет §6.4 для этого клипа (после шага 7b — ещё `de010.py apply --only <Key>`, §7), собирает каталог цикла
`prep_acceptance.py --cycle r<N+1> --previous <каталог прошлого цикла> --run <новый run> --replace "<старый run>/=<новый
run>/" --refresh-sha` (`references/ue-import-package.md` §4.5) и вызывает нового приёмщика (§10).
- Историю правок хранит git. В карточке нового цикла `accepted_object` содержит FBX клипа и спеку с sha256, а
  `previous_card` указывает на карточку прошлого цикла.

### 10.7 Калибровка (smoke-тест оркестратора)

До первого боевого прогона приёмщик оценивает 4 клипа KingArthur по существующим кадрам
`art/pipeline-candidates/ASSET-KING-ARTHUR-001/20260929-h2anim/preview/`. Это Blender-листы и `ue/*-ue-editor.jpg`;
клипы художественно приняты по делегированию 2026-10-09 (ВР-17, ВР-60). Ожидается `pass` по всем 4 клипам. Если
откалиброванная рубрика даёт не pass на принятых клипах, надо исправлять якоря §10.4, а не клипы.

## 11. Выход этапа 6 и связь с этапом 7

Этап 6 закрыт — это вход 7.0 (`references/ue-import-package.md` §2), — когда выполнено всё ниже.
- 4 клипа авторены (ДС-1): `h2anim_run.py` код 0 (validate и contact PASS, WARN разобраны), проверки исполнителя §6.3
  сняты, `clip_manifest.py build` → `MANIFEST_CHECK PASS` (клипы `measured`). Карточек клипов на этапе 6 нет.
- Заготовки промптов приёмки 4 клипов и список известных пределов фигуры — в
  `<ASSET_DIR>/evidence/acceptance-anim-prompts/` (§10, §10.5).
- `MOTION_SOURCE` записан в заявку; паттерн библиотеки — строка «Отступления от хендбука» для README этапа 7 (§6.1).
- VFX: слоты §8 с решением по каждому (по умолчанию «работает сразу» или «нет, фолбэк», запись в заявке).
- SFX: `hit_type` записан в заявку (`HIT_TYPE`) и звук смерти выбран по §9; новый рецепт (если был) собран
  `sfx_build.py`, банк пересоздан `ue_bank.py` без удалённых строк; строки `03-sound-registry.csv` с пометкой о
  прослушивании. Импорт и проверка новых звуков в UE — в окне шага 7b (§5, §9).

Дальше, на этапе 7:
- **Шаг 7a.2** (`references/ue-import-package.md` §4.5): импорт клипов, `measure`, `clip_manifest.py build`
  (`technically_imported`), UE-кадры, приёмка §10 → 4 карточки `pass`. Это выход 7a, а не этапа 6.
- **Notify `Contact`** — шаг 7b, `de010.py apply --only <Key>` (§7).
- **Реестры** — по таблице `references/new-character-registration.md` §10 (RA-26). Строки `AM_<Key>_<Clip>` в
  `03-asset-registry.csv` (§12.2) пишутся на шаге 7.8, когда у клипов есть путь в UE: «технически импортировано», после
  осмотра листа K1/K2 — «художественно принято, по делегированию» (ВР-17, ВР-60). На этапе 6 строк 03 нет.
- **Лист K1/K2 AN-18** — после подключения S08 и упаковки, обе настоящие доски,
  `tools/art/anim/clip_review_sheet.py run` и `sheet`. Новый герой — запись `HEROES` с явными карточками клипов
  (регистрация Р6-4): `"<Key>": Hero("<Character>", "<PRE>", <IDLE_SECONDS>, ("AN-…", "AN-…", "AN-…", "AN-…"))`.
  Запуск — на вариантах фикстуры:
  `run --packaged --heroes <Key> --fixture marmoreal=S08BenchMarmoreal-<Key>.json,sarpedon=S08BenchSarpedon-<Key>.json`,
  затем `sheet --heroes <Key>` (или `--cards <4 карточки>`). `--heroes` обязателен: по умолчанию инструмент снял бы
  всех героев и переписал бы их закоммиченные листы (RB-12). Несколько новых героев — одним вызовом с картой фикстур на
  героя (`--fixture "<Key1>:marmoreal=…,sarpedon=…;<Key2>:…"`, F159; регистрация Д-3). K1 — объединение кадров группы
  запуска, не всех `HEROES` (76168867). Бойца лист узнаёт по фокусу запуска (§2.1). Кадры обязаны нести
  `RENDER … reference=1` (`clip_review_sheet.py:501-502`); после переупаковки запуски переснимаются сами по штампу
  сборки, `--force` не нужен.
- Дефект клипа на листе означает возврат клипа в доработку §10.6 (новый цикл). Чистый лист означает строку реестра
  03 «художественно принято, по делегированию» (ВР-17, ВР-60). Лист доказывает, что клип играет в игре, но с K1/K2
  сверху плохо видно, как читается DeathSettle (F163): суть движения судит приёмка 7a.2.

## 12. Шаблоны

### 12.1 Ключи `<Key>` в `cue-table.json`

```json
"sequence_by_fighter": { "<Key>": "/Game/PipelineCandidates/<Key>/H2Anim/AM_<Key>_HitReact.AM_<Key>_HitReact" }
```

Пример дан для CUE-011. Для CUE-013 то же с `DeathSettle`. Для CUE-014 запись `vfx.by_hero.<Key>` (`system`, `socket`,
`fx_row`) добавляется только при FX способности (§8).

Когда: только после `h2anim_ue.py import` (§6.4), когда оба `.uasset` уже в `unreal/Unmatched/Content/`. Иначе
`validate-table` даёт FAIL `…sequence_by_fighter.<Key>: нет ассета …` (`cue_contract.py:257-260`) — разбор
оркестратором (`SKILL.md` §5 п.6, ДС-2): ключ добавлен раньше импорта. Где: в чекауте, в чей `Content` импортированы
клипы (редактор, §5). Строка регистрации — Р7-6 (`references/new-character-registration.md` §5.4). После правки:

```bash
python tools/s08/cue_contract/cue_contract.py validate-table        # → CUE_TABLE PASS
python -m pytest tools/s08/cue_contract/test_cue_contract.py -q
```

### 12.2 Строка `03-asset-registry.csv` (клип)

Колонки — по заголовку файла; образец — строка `AM_KingArthur_LungeAttack`.

```text
AM_<Key>_<Clip>,anim,"<событие и момент запуска>","Клип D-11 <роль> для <FIGHTER_NAME> на риге UM_HUMANOID_17_v2, root motion выкл<; AnimNotify Contact>",Blender (H2Anim),"FBX 24 fps, <N> к.; AnimSequence",/Game/PipelineCandidates/<Key>/H2Anim/AM_<Key>_<Clip>,-S08HeroesLegacy,<статус>,"<карточка evidence/acceptance-anim/...; лист K1/K2 этапа 7>",свой (код и материалы проекта),"<мс>, <N> к.; <кости>; ΔGPU 0","<AN-NN>; <ASSET_ID>; <путь FBX>"
```

## 13. Открытые пункты (честно)

Закрыто пилотом 2026-10-13/14 (RA-24): notify `Contact` нового героя `de010.py apply` поставил трём героям пилота
(автотесты S08 PASS в 7b, F157 — с откатом пересохранённых MVP, теперь `--only`); лист K1/K2 AN-18 снят живым
packaged-прогоном на вариантах фикстуры, packaged-клиент читает loose-вариант (F158).

- Запасная задача живого редактора §7 собрана из проверенных вызовов DE-010, но отдельным шагом не прогонялась.
- Шаги SYNTX §6.1 (create-chat, upload-files, разбор `fileobj.json`) собраны по заголовку `gen.sh`, 07 §2.4 и
  сохранённым ответам сессии King Arthur; сквозным платным прогоном для нового героя не проверялись. Пилот шёл на
  паттернах библиотеки (ДС-6), SYNTX — только для нестандартного движения.
- Заметка манифеста `clip_manifest.py` пишет «по видео-референсу» для паттерна библиотеки, только если в спеке нет
  `pattern` / `history.pattern_spec`, а в заявке — `MOTION_SOURCE` «library:» / «tripo-preset:» (F50; C53 исправлено
  для таких спек, пилотные Angel, Achilles, Leshen — прежний текст); дата валидации в манифесте зашита 2026-09-29
  (F130). Источник движения — по `reference_kind` спеки.
- Крупные планы и пара шва Idle (`clip_closeups.py`), `grip_check.py` и `weapon.extra_parts` в `clip_contact_check`
  появились после пилота (42ed7951, ee301065, 00f358c7) и на новом герое целиком ещё не прогонялись.
- Дымовой прогон §6.6 — правило после пилота (RC-06); на фигуре ещё не прогонялся.
- `ue_h5cb1.py`, `fx_ability.py` и `build_manifest.py` зашиты на существующих героев: новому нужны строки регистрации
  или новый код (`references/new-character-registration.md`).
- Контракт рига, сокеты и `ik_chains` имеют статус «предложено». Общий ретаргет в UE не доказан. Сокет Harpy
  `Weapon` (профиль `foot.R` против «кисти» контракта) — расхождение из HANDBOOK §2.7 и §10.
- `MS_*` (MetaSound) спроектированы, но в Content их нет. Прослушивание звука пользователем не проводилось
  (`docs/game-design/audio/07-production-log.md` §6).
