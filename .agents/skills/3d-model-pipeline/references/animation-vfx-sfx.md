# Этап 6: анимация, VFX и SFX — глобальный стандарт, производство, приёмка клипов

Документ решает две задачи. Часть A — глобальный стандарт скелетной анимации, VFX и SFX проекта (требование №4); он
действует для всех фигур. Часть B — производство этапа 6 для нового ассета и приёмка клипов с коэффициентом (`kind=anim`).

Карта этапов скилла (`SKILL.md`): 0 заявка → 1 концепт-лист → 2 Tripo H2 → 3 сборка в Blender (регистрация персонажа →
H2-bake → look-dev → TeamAccent) → 4 приёмка модели → 5 доработка модели → **6 анимация + VFX + SFX** → 7 упаковка,
импорт в UE, подключение S08, кадры в игре (`references/ue-import-package.md`).

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
то есть ключ контракта (`tools/tripo-pipeline/anim/h2anim_run.py:89`; так же HANDBOOK §4.5 п.2).

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
(`S08HeroesV2.cpp:105-108`):

| Герой (`<Key>` / `<Character>`) | Оружие, кость | Idle, с | Контакт LungeAttack (24 fps) |
|---|---|---|---|
| KingArthur / Arthur | меч, `weapon.R` | 2,5 | к. 7 = 292 мс (рубящий удар) |
| Merlin / Merlin | посох, `weapon.R` | 3,0 | к. 8 = 333 мс (выброс посоха) |
| Medusa / Medusa | лук, `weapon.L` | 56/24 | к. 8 = 333 мс (выпуск стрелы) |
| Harpy / Harpy | когти, нет | 2,0 | к. 7 = 292 мс (окно удара 7–9, контакт — первый кадр окна) |

Источник контактов — поле `design` клипа LungeAttack в `ASSET-*/build-profiles/*-h2anim.json`. Те же числа стоят в
`S08HeroesV2.h:115-118`, `tools/art/de010/de010.py:12-15` и автотесте `Unmatched.S08.HeroesV2.Contact`
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
  (`tools/art/de010/de010.py:12-13`; проверка `:71` смотрит только fps 24, длину 14 к. и `key_frames`). Ключ в `keys`
  (`"f": N`) на этом кадре — правило скилла для читаемого удара; `de010.py` его не проверяет.

### 2.2 Нейминг и пути

| Что | Формат | Источник |
|---|---|---|
| Клип UE (AnimSequence) | `/Game/PipelineCandidates/<Key>/H2Anim/AM_<Key>_<Clip>`; суффикса `_Anim` нет | `ClipPath`, `S08HeroesV2.cpp:152` |
| Канонический скелет | `/Game/PipelineCandidates/<Key>/Rig/SK_<Key>_Skeleton` (рядом меш-носитель `SK_<Key>`) | `tools/tripo-pipeline/review/ue_py/canonical_skeleton.py` |
| FBX клипа | `<ASSET_DIR>/<YYYYMMDD>-h2anim/export/AM_<Key>_<Clip>.fbx`, один FBX на клип, с узлом меша | `h2anim_run.py`, HANDBOOK §2.8 |
| Спека | `<ASSET_DIR>/build-profiles/<content-key>-h2anim.json`, schema `unmatched.h2anim-spec/1` | HANDBOOK §4.5 |
| Отчёт validate | `docs/art-pipeline/animation-library/validation-h2anim/AM_<Key>_<Clip>.validation.json` | `h2anim_run.py:27` |
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
- Notify ставит `tools/art/de010/de010.py apply` на шаге 7b (`SKILL.md` §6, этап 7b п.1; регистрация Р7-1). На этапе 6
  он не нужен: гейты приёмки клипа его не проверяют (§10.2), редакторные кадры его не показывают.
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
- Заявка с полями из таблицы плейсхолдеров.

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

**Карточки задач 06-tasks.** Траты SYNTX без карточки запрещены: `tools/art/visual/ledger.py add` отказывает, если
`--task` не найден в `docs/game-design/visual/06-tasks/*.csv`. Поэтому до видео-референсов в `anim.csv` заводятся 4
карточки клипов нового героя. Формат — как у AN-01…AN-16; id — следующие свободные `AN-NN`.

**Blender** — только headless. Скрипты `validate_clip.py`, `clip_contact_check.py` и `clip_author.py` в живом Blender
бросают RuntimeError (`validate_clip.py:1-9`). Рабочий путь — только `h2anim_run.py` (§6.3): он передаёт полный набор
флагов (`h2anim_run.py:89-93`) и пишет отчёт в `validation-h2anim/`, который служит источником гейта `G-VALIDATE`
(§10.2). Прямой вызов — **только диагностика**, с `--out` вне `docs/art-pipeline/animation-library/validation-h2anim/`,
чтобы не перезаписать отчёт гейта более слабым:

```bash
# диагностика; N = clips.<Clip>.frames из спеки; --loop=true только для Idle
"C:/Program Files/Blender Foundation/Blender 5.2/blender.exe" -b --factory-startup \
    --python tools/tripo-pipeline/anim/validate_clip.py -- <clip.fbx> --skeleton=UM_HUMANOID_17_v2 \
    --character=<Character> --clip-role=<idle|oneshot|terminal> --expect-fps=24 --expect-duration=<N/24> \
    --root-policy=in_place --min-pose-change=0.02 [--loop=true] --out=C:/tmp/skill-<content-key>/<Clip>.validation.json
```

**Среда UE** (шаги §6.4 и §7):
- Работает GUI-редактор пользователя с MCP `127.0.0.1:8123`. Проверка:
  `netstat -ano | grep ':8123 .*LISTEN'`. Редактор пользователя не закрывать. Если порт не слушает — как в
  `references/ue-import-package.md` «Правила среды» п.1: агент запускает свой редактор командой HANDBOOK §0.2,
  записывает PID и в конце закрывает только его, при 0 dirty-пакетов.
- Импорт клипов идёт в `Content` того чекаута, чей редактор открыт (обычно основной чекаут пользователя). Всё, что
  проверяет `.uasset` на диске (`cue_contract.py validate-table`, §12.1), запускать в этом же чекауте.
- Каждая UE-команда выполняется под блокировкой `C:/tmp/ue-editor.lock`, по одному герою на блокировку:
  `MSYS_NO_PATHCONV=1 UE_LOCK_OWNER=<ASSET_ID>-s6 python tools/art/material_library/ue_lock.py --step "<шаг>" -- <команда>`
  (`ue_lock.py:13-14`). Сами скрипты `tools/tripo-pipeline/*` блокировку не берут.
- `h2anim_ue.py frames` отказывает, если в открытом уровне есть несохранённые изменения или если открыт сам
  `L_P17ControlScene` (`h2anim_ue.py:205-212`).
- Headless-коммандлеты (`UnrealEditor-Cmd`: `ue_import_audio.py`, `ue_verify_audio.py`, `fx_ability.py`) запускаются
  только когда на этом чекауте нет GUI-редактора (`fx_ability.py:4`: «the editor of THIS checkout must be closed»;
  HANDBOOK §0.1). Поэтому они выполняются в окне шага 7b вместе с `de010`/`de011` (`SKILL.md` §6, этап 7b), а не
  между MCP-шагами. Worktree это не обходит (`references/ue-import-package.md` §1 п.4). Открыт редактор пользователя —
  гейт стопа `SKILL.md` §5 п.7; сам агент его не закрывает.
- Свои процессы Blender и UnrealEditor-Cmd после шага проверять и завершать по PID (`SKILL.md`).

**Проп.** Этап 6 нужен пропу, только если у него есть CUE-строка или звук. Иначе этап пропускается с записью
«нет слотов» в поле `STAGE6_SLOTS` заявки.

## 6. Клипы: шаги

### 6.1 Видео-референсы движения (SYNTX)

HANDBOOK §4.5 требует строить движение по видео-референсам, а не по памяти. Траты SYNTX идут без подтверждения каждой
генерации, по карточке и в лимитах ВР-04 и ВР-PR04 (`docs/game-design/visual/00-VISUAL-BRIEF.md:21-22`, §5.3).
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
7. **Запуск** (тратит токены; без подтверждения каждой генерации, в лимитах ВР-04/ВР-PR04). Сначала один вариант на клип:
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
`ue.mesh_for_preview` (`h2anim_run.py:66,118`, `h2anim_ue.py:164,205`). Образец выбирается по оружию:

| Тип фигуры | Образец |
|---|---|
| оружие в правой руке, рубящее | `art/pipeline-candidates/ASSET-KING-ARTHUR-001/build-profiles/king-arthur-h2anim.json` |
| оружие в левой руке, стрелковое | `art/pipeline-candidates/ASSET-MEDUSA-001/build-profiles/medusa-h2anim.json` |
| древковое или посох | `art/pipeline-candidates/ASSET-MERLIN-001/build-profiles/merlin-h2anim.json` |
| без оружия, крылья или когти | `art/pipeline-candidates/ASSET-HARPY-001/build-profiles/harpy-h2anim.json` |

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
| `run_dir` | `<ASSET_DIR>/<YYYYMMDD>-h2anim` |
| `ue.skeleton` | `/Game/PipelineCandidates/<Key>/Rig/SK_<Key>_Skeleton` |
| `ue.mesh_for_preview` | `/Game/PipelineCandidates/<Key>/Rig/SK_<Key>` — меш-носитель из шага skeleton. Так сделано у Harpy; H2LD-меш появится в UE только на этапе 7 |
| `ue.clips_folder` | `/Game/PipelineCandidates/<Key>/H2Anim` |
| `clips.Idle.frames` | `IDLE_SECONDS × 24` |
| `clips.*.reference` | папка референса из §6.1 |
| `clips.*.design`, `keys`, `waves`, `key_frames`, `ik_feet`, `hand_follow`, `amplitude_scale` | авторский слой под нового героя. Кадр `LUNGE_CONTACT_FRAME` записывается в `design` LungeAttack, входит в `key_frames` и имеет ключ в `keys` (§2.1) |
| `clips.*.template` | черновики `blender/ASSET-MEDUSA-001/export/AM_Medusa_*.fbx` (в git). `mirror: true`, если сторона оружия противоположна Medusa |

Длины LungeAttack, HitReact и DeathSettle не менять: это константы C++ (§2.1). Пределы, которые не чинятся в клипе
(жёстко скиненный подол, наплечник, поворот головы, IK), описаны в HANDBOOK §4.5 п.4.

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
(`docs/art-pipeline/animation-library/VALIDATION.md`).

### 6.4 UE: скелет, импорт, notify, замер, кадры

Каждая команда — под `ue_lock.py` (§5). Подкоманды — `h2anim_ue.py:3-8`.

```bash
L="python tools/art/material_library/ue_lock.py"; S=<ASSET_DIR>/build-profiles/<content-key>-h2anim.json
export MSYS_NO_PATHCONV=1 UE_LOCK_OWNER=<ASSET_ID>-s6
$L --step "<Key> state"    -- python tools/tripo-pipeline/anim/h2anim_ue.py state
$L --step "<Key> skeleton" -- python tools/tripo-pipeline/anim/h2anim_ue.py skeleton $S   # идемпотентно
$L --step "<Key> import"   -- python tools/tripo-pipeline/anim/h2anim_ue.py import $S [--clips=LungeAttack]
# notify Contact здесь не ставится: его ставит de010.py apply на шаге 7b (§2.3, §7)
$L --step "<Key> measure"  -- python tools/tripo-pipeline/anim/h2anim_ue.py measure $S
$L --step "<Key> frames"   -- python tools/tripo-pipeline/anim/h2anim_ue.py frames $S --clips=<Clip>   # по клипу за вызов
$L --step "<Key> closeup"  -- python tools/tripo-pipeline/anim/h2anim_ue.py frames $S --clips=LungeAttack --frames=<a,b,c> --closeup
python tools/tripo-pipeline/anim/h2anim_ue.py sheet $S                                      # без редактора
```

Отчёты: `reports/ue-canonical-skeleton.json`, `ue-import-clips.json`, `ue-measure-clips.json`, `ue-frames.json`,
`ue-frames-closeup.json`. Кадры: `preview/ue/<Key>-<Clip>-fNN-{front,q34}-ue-editor.jpg` и лист
`preview/<Key>-H2Anim-ue-sheet.jpg`. Условия замера — HANDBOOK §4.6 п.5. Кадры редактора нужны для диагностики и приёмки
этапа 6. Это не K1/K2 и не evidence SHOT: отпечатка RENDER у них нет (`h2anim_ue.py:214-218`).

**После импорта.** Когда `AM_<Key>_HitReact` и `AM_<Key>_DeathSettle` лежат в `Content` (`ue-import-clips.json`),
можно добавлять ключи `<Key>` в CUE-011/013 и гонять `validate-table` (§12.1) — в чекауте этого `Content` (§5). Шаг
относится к регистрации этапа 7 (Р7-6), раньше импорта его не делать. Если этап 7 снова импортирует клипы
(`SKILL.md`, этап 7a п.2), это происходит до шага 7b, и notify ставит обычный `de010.py apply` (§7).

### 6.5 Манифест библиотеки

```bash
python tools/tripo-pipeline/anim/clip_manifest.py build && python tools/tripo-pipeline/anim/clip_manifest.py check
```

Статус `technically_imported` ставит только `build` и только при трёх сходящихся свидетельствах: validate PASS,
контакты PASS, UE-импорт с тем же sha256 FBX (`clip_manifest.py:9-16`). Статус `artistically_accepted` сборка не пишет
никогда, а ручную правку перезапишет. Художественная приёмка фиксируется в `03-asset-registry.csv` (§12.2) и в
карточке §10.

## 7. Notify `Contact` для нового героя

**Основной путь — `tools/art/de010/de010.py apply` на шаге 7b** (`SKILL.md` §6, этап 7b п.1). Он ставит ровно один
`Contact` на LungeAttack каждого героя своего списка `HEROES`, идемпотентно (`tools/art/de010/de010_apply_ue.py:9-11`).
Для нового героя нужна строка `HEROES` (регистрация Р7-1, `references/new-character-registration.md` §5.1). Ограничения:
он запускает свой `UnrealEditor-Cmd` (GUI-редактор этого чекаута закрыт, гейт `SKILL.md` §5 п.7) и заново собирает
`M_UM_Figure_v2` текущим графом. После любого повторного импорта LungeAttack `de010.py apply` повторить.

**Запасной путь — задача живого редактора ниже**: только notify одного клипа, без пересборки материала, под
`ue_lock.py`. Применять, когда notify нужен до шага 7b в открытом редакторе. Строку Р7-1 и шаг 7b он не заменяет.
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
Если и `de010.py apply` не ставит notify — гейт стопа `SKILL.md` §5 п.6 (HANDBOOK §0.3 п.3 — FAIL проверки, п.6 —
если упал или завис редактор) с пакетом шагов пользователю: путь клипа, кадр, вывод `de010.py`. Обходной путь не
придумывать.

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

Путь движка — `UE_ROOT`, по умолчанию `C:\Program Files\Epic Games\UE_5.8` (`tools/art/de010/de010.py:34`). Критерии:
- `AUDIO-IMPORT summary … failed=0`;
- `ue-import-<ID>-verify.json` → `problems: 0`;
- строка ID в `03-sound-registry.csv` с пометкой о прослушивании (§4.3);
- автотесты `Unmatched.S08.Audio.*` на этапе 7.

## 10. Приёмка клипов (`kind=anim`)

Механика та же, что у модели (вызов приёмщика, формула, вердикт, бриф доработки): `references/acceptance-and-blender.md`.
Схема — `tools/art/acceptance/asset-acceptance-2.schema.json` (ветка `kind: anim`). Судья согласованности —
`python tools/art/acceptance/validate_card.py <card.json> --print-verdict --check-files`. Если поле в этом разделе
расходится со схемой, права схема.

Промпт приёмщика клипа — шаблон acceptance-and-blender.md §8.2 с такими заменами: заголовок «Приёмка клипа
AM_<Key>_<Clip>, цикл <rN> (этап 6)»; рубрика — этот файл §10.2–§10.5; «Вход» — кадры и материалы §10.3; «Порядок» —
гейты `G-VALIDATE`, `G-CONTACT`, `G-MANIFEST` по отчётам, баллы R, C, D, L по кадрам; константы
`schema "unmatched.anim-acceptance/1"`, `kind "anim"`, `clip "<Clip>"`. Вызов — §8.3 (или §8.4) того же файла, label
`acceptor-<ASSET_ID>-<Clip>-r<N>`.

### 10.1 Единица, циклы, путь

- Единица приёмки — **один клип**. Вердикт героя — pass, когда все 4 клипа pass.
- Циклы на клип: r1 → доработка → r2 → доработка → r3, то есть не больше 2 доработок. После r3 без pass —
  `escalate_user` (`SKILL.md` §5 п.4).
- Путь (решение скилла): `<ASSET_DIR>/evidence/acceptance-anim/<YYYYMMDD>-r<N>/<Clip>/card.json` и рядом `frames/`. Если
  в цикле r2 переделывается один клип, в каталоге r2 лежит только он.

### 10.2 Гейты (PASS/FAIL из отчётов, не баллы)

| Гейт | PASS, если | Источник |
|---|---|---|
| `G-VALIDATE` | `result: pass` | `docs/art-pipeline/animation-library/validation-h2anim/AM_<Key>_<Clip>.validation.json` |
| `G-CONTACT` | `result: pass` | `<run>/reports/contact-<Clip>.json` |
| `G-MANIFEST` | `clip_manifest.py check` прошёл и у клипа статус `technically_imported` (то есть есть UE-импорт с тем же sha256) | `clip-manifest.json` |

Notify `Contact` в приёмку клипа не входит: его ставит `de010.py apply` на шаге 7b, проверяет автотест
`Unmatched.S08.HeroesV2.Contact` (§2.3, §7). Время контакта клипа проверяют `G-CONTACT` и измерение C.

### 10.3 Кадры приёмщика

Кадры копируются в `frames/`; имена — как у источника:
- Blender-лист `<Key>-<Clip>-blender-sheet.jpg` (§6.3);
- UE-кадры `<Key>-<Clip>-fNN-front-ue-editor.jpg` и `<Key>-<Clip>-fNN-q34-ue-editor.jpg` (§6.4);
- у LungeAttack — крупный план `*-closeup-ue-editor.jpg` кадров вокруг контакта;
- лист `<Key>-H2Anim-ue-sheet.jpg`.

Кроме кадров приёмщик получает:
- `design` клипа из спеки;
- `LUNGE_CONTACT_FRAME`;
- отчёты validate, contact и `ue-measure-clips.json`;
- референс §6.1 (`contact-sheet-2fps.png`, если есть);
- лист концепта и QUALITY_REFERENCE для характера героя.

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
   команда `references/acceptance-and-blender.md` §8.4 с `windows.sandbox="unelevated"`,
   label Workflow — `acceptor2-<ASSET_ID>-<Clip>-r<N>`).
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
`acceptor.profile`: «Opus xhigh» или «Sol 6.1 xhigh». Сессия приёмщика ≠ `executor_session_id`.

### 10.6 Доработка клипа (лично «Opus xhigh», бриф ниже)

Бриф модели (`references/acceptance-and-blender.md` §10) для клипа не годится: он разрешает только `run_h2_bake.py` и
профили bake/look-dev. Клип дорабатывается по брифу ниже. Работа делится так:
- исполнитель «Opus xhigh» (агент Workflow `{model: 'opus', effort: 'xhigh'}`, как в acceptance-and-blender.md §1) —
  только правка спеки и headless `h2anim_run.py`, без Unreal;
- запускающий агент — после отчёта исполнителя: шаги §6.4 (импорт, measure, frames, sheet) под
  `ue_lock.py`, §6.5 (манифест), кадры §10.3 в каталог нового цикла и вызов **нового** приёмщика.

Правила:
- Разрешено править только блок клипа в спеке: `keys`, `waves`, `key_frames`, `ik_feet`, `hand_follow`, вес и `mirror` у
  `template`, `amplitude_scale`.
- `target`, `fps`, длины кадров (§2.1) и `LUNGE_CONTACT_FRAME` не менять. Новые кости не добавлять.

```markdown
# Доработка клипа AM_{{KEY}}_{{CLIP}}: приёмка {{CYCLE}} → r{{N_NEXT}} (этап 6 скилла 3d-model-pipeline)

Делегирование пользователя (2026-10-06, дословно): «Не знаю. Делай сам, меня это не касается. Все решения
принимай». Траты: нет — кредиты Tripo/SYNTX, Unreal и упаковка на этом шаге запрещены.

Ты — исполнитель доработки «Opus xhigh». Работаешь лично, не делегируешь, свою работу не принимаешь.
Норма — docs/art-pipeline/BLENDER-MODEL-HANDBOOK.md §2.8, §4.5; правила —
.agents/skills/3d-model-pipeline/references/animation-vfx-sfx.md §2.1, §6.2, §6.3, §10.6 (прочитать).

## Вход
- Карточка: {{E}}/{{CLIP}}/card.json (verdict rework_blender) и кадры {{E}}/{{CLIP}}/frames/.
- Спека: {{SPEC}} (править только clips.{{CLIP}}); референс: {{REF_DIR}}.
- Отчёты прошлого прогона (только чтение): {{RUN}}/reports/h2anim-run.json, contact-{{CLIP}}.json,
  docs/art-pipeline/animation-library/validation-h2anim/AM_{{KEY}}_{{CLIP}}.validation.json.

## Правки — только эти пункты rework_fix_list
{{FIX_LIST — по пункту: item · frame · fix · tool}}

## Границы
- Только ключи clips.{{CLIP}}: keys, waves, key_frames, ik_feet, hand_follow, template (вес, mirror),
  amplitude_scale. target, fps, frames, design-кадр контакта {{CONTACT_FRAME}} и другие клипы не трогать.
- Только headless: python tools/tripo-pipeline/anim/h2anim_run.py {{SPEC}} --clips={{CLIP}}.
  Живой Blender — только осмотр. Код tools/tripo-pipeline/** не менять.
- Без Unreal, без кредитов, без коммитов, без git add/stash/reset/checkout. Свои Blender-процессы — остановить по PID.
- Пункт с tool «h2_bake профиль (веса), этап 5 модели» не делать: пометить «не закрыто: веса скина, этап 5».

## Готово, если
- h2anim_run.py дал код 0; validate и contact клипа — pass; новых FAIL нет.
- Каждый пункт списка закрыт по листу preview/{{KEY}}-{{CLIP}}-blender-sheet.jpg (открыть и посмотреть) либо
  помечен «не закрыто: <причина>».

## Отчёт (последнее сообщение)
- Ключи спеки: было → стало, по пункту списка; sha256 нового FBX клипа; что не закрыто и почему.
Баллы и вердикт не ставь: повторная приёмка — новый агент-приёмщик.
```

После брифа запускающий проверяет `git status --short` (изменились только спека, `export/AM_<Key>_<Clip>.fbx`,
отчёты и листы прогона, отчёт validate), выполняет §6.4 и §6.5 для этого клипа (после шага 7b — ещё `de010.py apply`, §7), собирает кадры §10.3 в
`evidence/acceptance-anim/<YYYYMMDD>-r<N+1>/<Clip>/frames/` и вызывает нового приёмщика (§10).
- Историю правок хранит git. В карточке нового цикла `accepted_object` содержит FBX клипа и спеку с sha256, а
  `previous_card` указывает на карточку прошлого цикла.
- Дефект весов скина (рвётся одежда при допустимой амплитуде) клипом не чинится. Пункт `tool: "h2_bake профиль
  (веса), этап 5 модели"` уходит в новый bake-прогон. Новый `SK_<Key>_H2.fbx` меняет sha цели, поэтому все 4 клипа
  авторятся заново (`clip_author.py`, код 3).
- Известные пределы HANDBOOK §4.5 п.4 приёмщик учитывает как ограничение: их записывают в `rationale`, а не в
  `rework_fix_list`.

### 10.7 Калибровка (smoke-тест оркестратора)

До первого боевого прогона приёмщик оценивает 4 клипа KingArthur по существующим кадрам
`art/pipeline-candidates/ASSET-KING-ARTHUR-001/20260929-h2anim/preview/`. Это Blender-листы и `ue/*-ue-editor.jpg`;
клипы художественно приняты по делегированию 2026-10-09 (ВР-17, ВР-60). Ожидается `pass` по всем 4 клипам. Если
откалиброванная рубрика даёт не pass на принятых клипах, надо исправлять якоря §10.4, а не клипы.

## 11. Выход этапа 6 и связь с этапом 7

Этап 6 закрыт, когда выполнено всё ниже.
- 4 клипа: карточки `verdict: pass` (`validate_card.py` код 0), `clip_manifest.py check` PASS. Notify `Contact` —
  выход этапа 7 (`de010.py apply`, §7), не этапа 6.
- VFX: слоты §8 с решением по каждому (по умолчанию «работает сразу» или «нет, фолбэк», запись в заявке).
- SFX: `hit_type` записан в заявку (`HIT_TYPE`) и звук смерти выбран по §9; новый рецепт (если был) собран
  `sfx_build.py`, банк пересоздан `ue_bank.py` без удалённых строк; строки `03-sound-registry.csv` с пометкой о
  прослушивании. Импорт и проверка новых звуков в UE — в окне шага 7b (§5, §9).
- Строки `AM_<Key>_<Clip>` в `03-asset-registry.csv` (§12.2) со статусом «технически импортировано»; художественный
  статус ставится после листа K1/K2.

На этапе 7 (`references/ue-import-package.md`) после подключения S08 и упаковки делается лист K1/K2 обеих настоящих досок
через `tools/art/anim/clip_review_sheet.py run` и `sheet`. Новый герой — запись `HEROES` с явными карточками клипов
(`"<Key>": Hero("<Character>", "<PRE>", <IDLE_SECONDS>, ("AN-…", "AN-…", "AN-…", "AN-…"))`, регистрация Р6-4) и
запуск на вариантах фикстуры: `run --packaged --heroes <Key> --fixture marmoreal=S08BenchMarmoreal-<Key>.json,sarpedon=S08BenchSarpedon-<Key>.json`
(новый герой — первым ключом: K1 снимает первый ключ `--heroes`), затем `sheet --cards <4 карточки>`. Бойца лист
узнаёт по фокусу запуска (§2.1). Кадры обязаны нести `RENDER … reference=1`
(`clip_review_sheet.py:501-502`). Дефект клипа на листе означает возврат клипа в доработку §10.6 (новый цикл). Чистый лист
означает строку реестра 03 «художественно принято, по делегированию» (ВР-17, ВР-60).

## 12. Шаблоны

### 12.1 Ключи `<Key>` в `cue-table.json`

```json
"sequence_by_fighter": { "<Key>": "/Game/PipelineCandidates/<Key>/H2Anim/AM_<Key>_HitReact.AM_<Key>_HitReact" }
```

Пример дан для CUE-011. Для CUE-013 то же с `DeathSettle`. Для CUE-014 запись `vfx.by_hero.<Key>` (`system`, `socket`,
`fx_row`) добавляется только при FX способности (§8).

Когда: только после `h2anim_ue.py import` (§6.4), когда оба `.uasset` уже в `unreal/Unmatched/Content/`. Иначе
`validate-table` даёт FAIL `…sequence_by_fighter.<Key>: нет ассета …` (`cue_contract.py:257-260`), это гейт стопа
`SKILL.md` §5 п.6. Где: в чекауте, в чей `Content` импортированы клипы (редактор, §5). Строка регистрации — Р7-6
(`references/new-character-registration.md` §5.4). После правки:

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

- Notify `Contact` нового героя ставит `de010.py apply` после строки `HEROES` (Р7-1); на новом герое этот шаг ещё не
  прогонялся. Запасная задача живого редактора §7 собрана из проверенных вызовов DE-010, но отдельным шагом не
  прогонялась.
- Шаги SYNTX §6.1 (create-chat, upload-files, разбор `fileobj.json`) собраны по заголовку `gen.sh`, 07 §2.4 и
  сохранённым ответам сессии King Arthur; сквозным платным прогоном для нового героя не проверялись.
- Лист K1/K2 на новом герое (вариант фикстуры, фокус запуска, явные карточки — Д-2/Д-3) проверен тестами и
  синтетическими трассами, но живым packaged-прогоном ещё не снимался; чтение loose-варианта фикстуры
  packaged-клиентом тоже не подтверждено (при `BENCH FAILED fixture load` — путь пака, регистрация Д-2).
- `ue_h5cb1.py`, `de010.py`, `fx_ability.py` и `build_manifest.py` зашиты на существующих героев: новому нужны строки
  регистрации (`references/new-character-registration.md`).
- Контракт рига, сокеты и `ik_chains` имеют статус «предложено». Общий ретаргет в UE не доказан. Сокет Harpy
  `Weapon` (профиль `foot.R` против «кисти» контракта) — расхождение из HANDBOOK §2.7 и §10.
- `MS_*` (MetaSound) спроектированы, но в Content их нет. Прослушивание звука пользователем не проводилось
  (`docs/game-design/audio/07-production-log.md` §6).
