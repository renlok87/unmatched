# ART-DEFAULT: принятый арт-вид стал видом клиента по умолчанию (2026-10-04)

**Повод.** 2026-10-04 пользователь посмотрел демо на Marmoreal (кадр
[run-20261004-060344](../../ART-004/t43-20261004-055419/demo/run-20261004-060344/phase2-board-host-1920x1080.png)) и написал дословно:
«Блять, а какого фига не те модели на доске? У нас же есть уже готовые модели для Артура и Мерлина и так далее.»
На том кадре King Arthur и Merlin были серыми блок-аутами ART-003, Harpy — серыми силуэтами, подноса и окружения
не было. Причина: готовые герои look-dev v2 и поднос включались только флагами (`-ArtPreviewHeroesV2`,
`-ArtPreviewDiorama`), а вся арт-доска — флагом `-ArtPreview`.

**Полномочие.** Делегирование пользователя, дословно: «делай все без меня» (2026-09-29) и «сам реши все вопросы»
(2026-10-03). Вид по умолчанию — тот, что принят по делегированию в финальном акте GD-058
([README](../../GD-058/final-2026-10-03/README.md), вариант бенча `dx12-lumen-high-v2`): герои v2, поднос и арт-доска.
Образец решения — жетон HUD v3: он стал видом по умолчанию с флагом отката `-S08IconLegacy`.

## Что теперь по умолчанию

Подробно — в заголовке [S08ArtLook.h](../../../../../unreal/Unmatched/Source/Unmatched/S08/S08ArtLook.h).

| Что | По умолчанию (клиент без флагов) | Флаг отката | Что делает откат |
|---|---|---|---|
| Арт-вид: профиль доски, карта, свет, арт-маркеры, слой HUD (плашка, теги, жетон, урон) | вкл. на доске с зарегистрированным профилем (Marmoreal, Sarpedon) | `-S08GreyBoard` | серая доска / серый вид топологии, серые манекены, без подноса и арт-слоя HUD |
| Фигуры look-dev v2 (Arthur, Merlin, Medusa H2LD; Harpy H3LD; клипы H2Anim) | вкл. | `-S08HeroesLegacy` | изолированный кандидат Medusa и блок-ауты ART-003, как было без `-ArtPreviewHeroesV2` |
| Поднос (T2b на картах) и окружение карты | вкл. | `-S08DioramaLegacy` | без подноса и окружения, как было без `-ArtPreviewDiorama`; `-ArtPreviewNoEnv` по-прежнему убирает только окружение |
| Рендер | без изменений | `-S08LegacyRender` | как и раньше: эмуляция рендера до W4 (свет, экспозиция, игровой слой) для бенча |

- `-ArtPreviewHeroesV2` и `-ArtPreviewDiorama` принимаются, но ничего не меняют: их передают скрипты.
- `-ArtPreview` теперь включает только инструменты ревью:
  - кадр-доказательство `-ArtPreviewShotAfter`;
  - зум K2 `-ArtPreviewFocusZoom`;
  - выбор своего героя `-ArtPreviewSelectOwnHero`;
  - планы ввода `-ArtPreviewInputPlan`;
  - проба значка `-ArtPreviewIconProbe`;
  - подмена доски `-ArtPreviewBoardId`;
  - обзор «шесть Medusa» `-ArtPreviewAllMedusa`, который теперь требует `-ArtPreview`; на время обзора фигуры v2 уступают кандидату.
- Каждый актор доски пишет в трассу одну строку `ARTLOOK art=… source=… heroes=… tray=… env=… review=… legacyRender=… aliases=…`.
  Остальные строки арт-пути по-прежнему начинаются с `ARTPREVIEW …`: их читают все гейты и инструменты.
- **Cook.** `DirectoriesToAlwaysCook` в `DefaultGame.ini` (строки 18–55) покрывает всё, что нужно виду по умолчанию.
  Фигуры: `PipelineCandidates/{KingArthur,Merlin,Medusa}/{H2LD,Rig,H2Anim}` и `Harpy/{H3LD,Rig,H2Anim}`. Материалы:
  `UM/Materials/v2`, MI команд лежат в папках H2LD/H3LD. Подносы: `TableBase/20260928-table-base-tripo-h31` (T1), `TableBase/T2`, `TableBase/T2b`. Карты и окружение:
  `EnvMaps`, `EnvKit`. Маркеры и общее: `ArtTests/*`, `ArtPreview/Medusa`. Правки не понадобились. В прогоне ниже нет
  ни одного недостающего ассета, предупреждений cook — 0.

## Скрипты

| Скрипт | Что изменено |
|---|---|
| `tools/s08/run-phase2-demo.ps1` | Гейты по умолчанию ожидают фигуры v2, поднос, окружение и строку `ARTLOOK art=1 source=default heroes=v2 tray=on`. Ключи `-HeroesLegacy` / `-DioramaLegacy` передают откаты и возвращают прежние гейты. `-ArtPreviewHeroesV2` / `-ArtPreviewDiorama` остались безвредными ключами |
| `tools/art/render/render_bench.py` | Все варианты без `-v2` (`dx12-lumen-high`, `dx11-legacy`, `dx12sm5-legacy`, `vsm`, `csmdefault`, `medium/low`, `sm5/dx11-fallback`, `sky-<k>`) явно передают `-S08HeroesLegacy -S08DioramaLegacy`, поэтому измеряют то же, что и раньше. Варианты `-v2` передают псевдонимы |
| `tools/s09/run-hud-demo.ps1` | Явно передаёт `-S08GreyBoard`: эта логическая обвязка HUD, её маркерные гейты и нагрузка двух клиентов без ограничения FPS построены на сером виде |
| `tools/s09/run-combat-demo.ps1` | Только комментарий: его ключи v2 / поднос теперь лишь добавляют гейты |
| `tools/s08/Unmatched-ArtTuner.cmd`, `tools/art/render/live_tune.py` | Без изменений: передают `-ArtPreview` и безвредные псевдонимы |

Прочие демо S09 и S10 (`run-combat`, `-duel`, `-pending`, `-hud-probe`, `run-vs-ai*`) без `-ArtPreview` теперь идут в
арт-виде. Здесь они не перезапускались. Если пиксельный гейт какого-то из них не пройдёт, ему нужен `-S08GreyBoard`
или перекалибровка.

## Прогон: демо без арт-флагов

`tools/s08/run-phase2-demo.ps1 -Api http://localhost:3000/graphql`. Арт-ключей скрипта нет. Доска Marmoreal по
умолчанию, два клиента offscreen, `-ClientFps 30` на каждом, пресет High. Пакет собран один раз, штамп `0f2bdb9a`
(`Saved/StagedBuilds/Windows/BuildStamp.json`). Клиенты получили только `-ArtPreview` от самого скрипта, ради
инструментов ревью: подмена доски, кадр и выбор своего героя. Вид пришёл по умолчанию: строка
`ARTLOOK … source=default … aliases=-`.

| Проверка | Хост | Джойнер |
|---|---|---|
| `ARTLOOK` | `art=1 source=default heroes=v2 tray=on env=on review=1 legacyRender=0 aliases=-` | то же |
| Фигуры v2 | `heroesV2 summary fighters=6 mapped=6 v2=6`: SK_Medusa_H2LD, 3 × SK_Harpy_H3LD, SK_KingArthur_H2LD, SK_Merlin_H2LD | то же |
| Idle | 6/6 | 6/6 |
| Поднос | T2b `SM_TableBase_T2b`, MI `MI_TableBase_T2b_Marmoreal` | то же |
| Окружение | `envlayout map=marmoreal props=64 lights=5 missingMeshes=0`, fx 10/10, `missingSystems=0` | то же |
| Недостающие ассеты | 0: зоны 12/12, глифы 11/11, `heroesV2 … missing=` нет, `diorama tray missing` нет | 0 |
| RENDER на кадре | `reference=1`, D3D12 SM6 Lumen, `t.MaxFPS 30` | `reference=1` |
| Гейты скрипта | все прошли (публикация только после них), WS drop/reconnect сошёлся, игра этого прогона снята (ABORTED) | — |

**Кадры (просмотрены глазом).**
- [Хост](phase2-board-host-1920x1080.png), [джойнер](phase2-board-joiner-1920x1080.png). Marmoreal с дворцом,
  фонарями и сакурами вокруг каменного подноса. На своих местах: три крылатые Harpy, Medusa в золоте со змеями,
  Merlin в синей мантии с посохом, King Arthur в красном плаще с короной. Серых блок-аутов нет.
- [Увеличение фигур хоста 2×](host-figures-crop-2x.png).

**Файлы.**
- Трассы клиентов: [хост](phase2-client-host.trace.txt) и [джойнер](phase2-client-joiner.trace.txt). Код комнаты
  скрыт. В `manifest.json` они записаны как `*.trace.log`, байты и sha256 те же.
- Статус прогона: `art-preview-status.json`, поля `heroesV2: true`, `diorama: true`, `artLookDefault: true`.
- Пиксельные проверки: `*-artcheck.json`.
- Автотесты: `automation-s08-s09-2026-10-04.txt`.

## Сборка и тесты

- Целевой `Unmatched` (`-NoXGE -MaxParallelActions=4`): `Result: Succeeded`.
- `UnmatchedEditor` (`-NoXGE -MaxParallelActions=2`): `Result: Succeeded`.
- Автотесты headless `Unmatched.S08+Unmatched.S09`: **250/250**. Это прежние 248 и два новых теста.
- Новые тесты `Unmatched.S08.ArtLook.Default` и `.Actor`
  ([S08ArtLookTests.cpp](../../../../../unreal/Unmatched/Source/Unmatched/S08/S08ArtLookTests.cpp)) дописывают флаги в
  настоящую командную строку и восстанавливают её после себя. Что они проверяют:
  - без флагов — арт-вид, v2, поднос, окружение;
  - каждый откат по отдельности;
  - псевдонимы ничего не меняют;
  - откат сильнее псевдонима;
  - `-ArtPreviewAllMedusa` без `-ArtPreview` ничего не делает;
  - на уровне акторов: поднос создаётся; King Arthur по умолчанию — фигура v2, с `-S08HeroesLegacy` — блок-аут, с
    `-S08GreyBoard` — серый манекен.

**Честная пометка.** Художественная приёмка этим прогоном не повышается: вид тот же, что принят по делегированию в
GD-058. Если пользователь решит иначе, прав он.
