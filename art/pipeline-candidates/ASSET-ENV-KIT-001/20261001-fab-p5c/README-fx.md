# ENV-MAPS P5c, трек V: VFX и варианты раскладки

Статус: **предложено** (CREATE-этап). Ничего не собрано и не импортировано в UE, кадров нет. Статусы «измерено» и
«технически импортировано» появятся после Integrate/Tune. «Художественно принято» решает только пользователь.

## Что сделано

### C++ (`unreal/Unmatched/Source/Unmatched/S08/`)

- **`S08EnvLayout.h/.cpp`: новая необязательная секция `"fx"`.** Это Niagara-системы, производные копии в `/Game/EnvKit/FX/`.
  - Путь вне `/Game/EnvKit/` — ошибка разбора. Так пак-папка никогда не попадёт в раскладку напрямую.
  - Поля: `id`, `system`, `anchor` (id пропа), `loc`, `yawDeg`, `scale`, `seed`, `warmupS`, `enabled`, `user` (user-параметры Niagara).
  - **Якорь.** Если задан `anchor`, `loc` — это смещение от пивота пропа. Смещение поворачивается вместе с yaw пропа и не масштабируется. Fx появляется только тогда, когда проп реально заспавнился.
  - **Где спавнится.** Только на досках `map-image`, в `Update` после пропов и земли. Grid-доски (Cobble) не меняются: секция там не читается.
  - **Пропускаются с записью в трассу:**
    - `enabled:false`;
    - якорь не заспавнился;
    - пивот на нарисованной карте (кружки и подписи остаются читаемыми);
    - система отсутствует;
    - у системы есть включённый Light- или Component-рендерер (бюджет света: VFX не добавляет динамических источников).
  - **Детерминизм.**
    - Фиксированный `seed`; по умолчанию это CRC от id.
    - Прогрев: `warmupS` секунд фиксированными тиками по 1/30 с (`AdvanceSimulation`).
    - В `-Bench` система ставится на паузу после прогрева: кадры воспроизводимы. `-EnvFxLive` оставляет симуляцию живой, `-EnvFxFreeze` замораживает и вне бенча.
    - `-ArtPreviewNoFx` выключает fx (A/B).
  - **Трасса:** `ARTPREVIEW envlayout fx id=… system=… particles=… deterministic=… nearBand=… user=…` для каждого fx и сводка `ARTPREVIEW envlayout fx map=… fx=N … particles=… mode=frozen|live|off`.
- **Варианты раскладки:** `-EnvLayoutVariant=<name>` накладывает `EnvLayouts/<map>.<name>.layout.json` поверх базовой раскладки.
  - Схема `unmatched.env-layout-overlay/1`. Поля `props` и `fx` принимают `{remove, replace, add}`. `replace` меняет поля по id пропа, например `mesh` и `scale`.
  - Когда удаляется проп, вместе с ним удаляются и fx, привязанные к нему якорем.
  - Свет, земля, `tray` и `apron` не меняются.
  - Результат слияния проверяется как обычная раскладка.
  - Без флага оверлей не применяется.
  - Отсутствующий или невалидный оверлей — чистый откат на базу. В трассе: `ARTPREVIEW envlayout variant=<n> … status=absent|invalid fallback=base`.
  - Файлы оверлеев никогда не считаются базовой раскладкой (`Resolve`/`Arm`).
- **`S08EnvFxAuthoring.h/.cpp`** (только редактор). Функции `DescribeNiagaraSystem` и `TuneNiagaraSystem` нужны потому, что данные эмиттеров (SimTarget, детерминизм, рендереры), константы модулей (RapidIterationParameters) и user-параметры недоступны из Python (вывод SCOUT). `TuneNiagaraSystem` отказывает для любого пути вне `/Game/EnvKit/`.
- **`Unmatched.Build.cs`:** добавлен `PrivateDependencyModuleNames.Add("Niagara")`.
- **`S08EnvLayoutTests.cpp`:** новые тесты `FxParse`, `Variant`, `FxSpawn`, `FxAssets`.
  - **Разбор и ошибки:** 24 случая отказа для fx и 16 для оверлеев.
  - **Спавн** через транзиентную систему без активации.
  - **Варианты:** слияние оверлея и откат при отсутствующем оверлее.
  - **Очистка:** смена доски и grid-регрессия.
  - **Shipped** теперь принимает Fab-дубликаты `/Game/EnvKit/Fab/<Map>/` (трек F) и проверяет fx и оверлеи.

### Python

- `tools/art/env_kit/ue_import_fab_fx.py`:
  - `FX_SPECS` с четырьмя системами:

    | Производная система | Источник |
    |---|---|
    | `NS_Env_Campfire` | `NS_Stylish_Fire_2`, пространственный множитель 0.3 |
    | `NS_Env_LanternFlame` | `NS_Stylish_Fire_3`, множитель 0.08 |
    | `NS_Env_CherryPetals` | SoftTofu `NS_leaf` |
    | `NS_Env_Fireflies` | SoftTofu `NS_Sparkling_Animate_2` |

  - **Каждая система:** CPU-симуляция, `bDeterminism` с фиксированным seed, Light- и Component-рендереры выключены, ночная палитра.
  - **`--check` без UE** проверяет:
    - AI-разрешённые паки (NoAI отклоняются);
    - цели в `/Game/EnvKit/FX/`;
    - правила констант;
    - оценку частиц (не больше 300 на экземпляр).
  - **В UE** скрипт идемпотентен: метатег `EnvFxSpecSha256`. Пересборка всегда идёт заново из нетронутой пак-системы, поэтому `mul` применяется один раз.
- `scripts/p5c_layout_fx.py`: пишет **только** секции `fx`. Генератор идемпотентен, есть `--check`, `--out DIR` и `--report`. Fx строятся от **текущих** пропов по id, поэтому запускать его нужно после `p5c_layout_props.py` трека F.

  | Карта | Что ставится | Частиц |
  |---|---|---|
  | Sarpedon | огонь на `campfire-*`; пламя в стекле `lantern-*`; 3 облака светлячков (лес W ×2, пляж) | ~318 |
  | Marmoreal | пламя в 4 горящих `lamp-*`; лепестки под кронами `cherry-*` (кит или Fab-сакура); 2 облака светлячков в саду | ~322 |

  - Проверки: диск спавна не заходит на карту, ничего нет в ближней полосе, якоря существуют, NoAI нет.
- `scripts/p5c_fx_anchor_probe.py`: headless Blender (`-b --factory-startup -t 4`, BELOW_NORMAL). Скрипт находит светящиеся тексели наших собственных мешей и пишет `reports/p5c-fx-anchors.json`.

  | Меш | Центроид (uu) |
  |---|---|
  | LanternPost (стекло) | (-2.8, -17.5, 48.5) |
  | LanternPlinth | (0, 0, 49.4) |
  | Campfire (угли) | (4.0, -0.5, 9.1) |

- `tools/art/tests/test_env_fx_p5c.py`: 14 тестов, все проходят.

## Пример оверлея (для этапа UserVariant)

`Config/ArtBoards/EnvLayouts/marmoreal.user.layout.json`:

```json
{"schema": "unmatched.env-layout-overlay/1", "map": "marmoreal", "variant": "user",
 "props": {"replace": [{"id": "cherry-w", "mesh": "/Game/EnvKit/Fab/Marmoreal/SM_EnvFab_<NoAI-копия>", "scale": 0.2}]},
 "fx": {"replace": [{"id": "petals-cherry-w", "loc": [0, 0, 120]}]}}
```

Запуск: `-EnvLayoutVariant=user`. NoAI-ассеты допускаются только в оверлеях, никогда в основной раскладке и никогда в кадрах, которые смотрит агент.

## Открытые вопросы для Integrate/Tune

1. Сборка C++ ещё не выполнялась. Возможна правка по сигнатурам Niagara 5.8. Если UBT предупредит про плагин, добавить `Niagara` в `Unmatched.uproject`.
2. Перенос `SimTarget` GPU→CPU для SoftTofu: модули GPU-only (например, коллизии по глубине) могут не скомпилироваться на CPU. Это видно в отчёте `TuneNiagaraSystem` (`compiled`, `errors`).
3. Знак смещения стекла LanternPost по Y (UE Y = −Blender Y) нужно проверить на кадре K2.
4. Материалы с нодой `Time` (огонь, мерцание) анимируются и на паузе. Если хэши двух `-Bench`-кадров различаются, нужны производные MI с нулевой скоростью для бенча.
5. Туман у водопада не сделан: в AI-разрешённых паках нет подходящей Niagara-системы (по данным SCOUT).

## Настройка P5c (Tune, 2026-10-01, кадры редактора `-game -Bench`)

Статус: измерено; художественная приёмка — решение пользователя. Итог и замеры: `docs/game-design/evidence/ENV-MAPS/p5c-fab-2026-10-01/README.md`.

- `NS_Env_Campfire`: k 0,3 → **0,4**, плюс правило `*.Color.Scale Color` ×**3**. До этого на K2 пламя было бледным язычком внутри тёплого пятна собственного точечного света.
- `NS_Env_LanternFlame`: `*.Color.Scale Color` ×**2,5**, размер прежний (k 0,08).
- `NS_Env_Fireflies`: правило `*.InitializeParticle.Uniform Sprite Size*` убрано, оно ни с чем не совпадало (`unmatchedRules`). Размер спрайта задаёт только user-параметр: 3–6 → **8–14 uu**. Светлячки видны отдельными точками, эффект сдержанный.
- Проверка `--check` разрешает множитель до ×6 для правил `*.Color.*`; для размеров и сил предел прежний, ×2.
- Пересборка системы в коммандлете не работает: `delete_asset` пишет «Force Deleting», но пакет остаётся, и `duplicate_asset` падает с «asset already exists». Обход: перед импортом убрать устаревшие `Content/EnvKit/FX/NS_Env_<X>.uasset` (это наши производные ассеты, gitignored; паки не трогаются). Тогда импорт строит систему заново из пака.
- Детерминизм: строки трассы fx в двух прогонах совпадают (`mode=frozen`, `nonDeterministic=0`), частиц 317 / 316. Пиксели огня между прогонами всё же отличаются — материал огня анимируется нодой `Time` (пункт 4 выше остаётся).
