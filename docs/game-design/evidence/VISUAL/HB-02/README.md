# HB-02 — лист приёмки: отладка гейтов ушла из вида игрока

Карточка [HB-02](../../../visual/06-tasks/hud.csv): по умолчанию нет отладочного слоя гейтов, с `-S09Markers` он
возвращается. Код — HB-01 `b1a3ea6a`, HB-02 `88dc56f6`. Лист собран 2026-10-06, шаг «кадры и упаковка» VS-1
(05-production-plan.md §1.5 п. 7, §1.6, §1.7 п. 1).

**Решение:** вид игрока — **художественно принято, по делегированию (2026-10-06)**. На всех кадрах ниже нет неоновых
полос, строк `you:` / `opponent:` / `seq=` / `phase=` / `deck=…~` боковой панели, эха команд и полосы результата.
Каждый кадр и лист открыт глазами. Условие карточки «гейты HB-01 с `-S09Markers` — PASS» выполнено на 5 гейтах из 7.
Два гейта падают по причинам вне HB-01 и HB-02, подробности в [VS-1/README.md](../VS-1/README.md#гейты).
**Дата решения:** 2026-10-06.
**Ревью:** Claude, один проход, арт и рамки задачи вместе (02 §13.3).
**Флаг отката:** `-S09Markers` возвращает весь отладочный слой. Флаг записан в `S08ArtLook.h` (`MarkersFlagName`),
трасса пишет `ARTLOOK … markers=0|1`.

## Упаковка

Одна упаковка Development из `C:/tmp/wt-visual`, ветка `feat/visual-vs1`:
- UAT: `BUILD SUCCESSFUL`, `UAT_EXIT=0`. Кук: 2109 пакетов, `0 error(s), 0 warning(s)`.
- `BuildStamp.json`: `commit ae8950dc`, `sourceHash c3c4e930…`, `skipBuild false`.
- sha256 внутреннего exe (`Unmatched/Binaries/Win64/Unmatched.exe`): `f69b8e8f…a621bf`.
- Перед упаковкой в ветку влит `fix/admin-panel` (`8807d3d4`, слияние `9052701d`). Поэтому `sourceHash` совпадёт с
  основной копией после `safe-integrate.sh`. Коммиты после `ae8950dc` трогают только `tools/` и `docs/`, то есть хеш не
  меняют.

## Как сняты кадры

- **«До», 1080p** — кадры прогона I, упаковка `6627333e` (ВР-PL11). Слой гейтов тогда рисовался всегда. Файлы
  `frames/before-I-*.jpg` — это побайтовые копии JPG прогона I.
- **«До», 720p** — у прогона I кадров 720p нет. Взята эта же упаковка с `-S09Markers`: гейт `run-combat-demo` при
  1280×720, файлы `frames/markers-*-720-*.jpg`. Флаг возвращает ровно прежний вид.
- **«После»** — та же упаковка без `-S09Markers`. Живая партия двух клиентов `run-combat-demo -PlayerView`, файлы
  `frames/after-*`. Флаг `-PlayerView` добавлен этим шагом в `tools/s09/run-combat-demo.ps1`. Он убирает `-S09Markers`
  и вместо гейтов маркеров ставит обратный гейт: `ARTLOOK markers=0` у обоих клиентов и ни одного оттенка маркеров
  боя на кадрах состояний. Остальные гейты прежние: доска, фигуры v2, отпечаток `RENDER`, `GAME_OVER`.
- `-Bench` из карточки не подошёл: бенч не строит живой HUD. В коде `-BenchTurnHud` сказано: «the live HUD is not
  built here». Поэтому строк `seq=` и эха на бенч-кадре не было бы и раньше. Решение ВР-VS1-F01 записано в VS-1/README.
- Условия: Api `http://localhost:3000/graphql`, по 30 FPS на клиент (`t.MaxFPS 30`), пресет High, все кадры на
  эталоне `RENDER` (0 вне эталона). Партии Medusa против King Arthur, флаги прогона I: `-ArtPreviewHeroesV2
  -ArtPreviewDiorama -RequireGameOver -JoinerAttack -HostScheme -S08MovePlates -S09SchemeQuiet=3.5`.
- Marmoreal снят с `-ConceptPaste` (нарисованный задник). Флаг нужен до EN-13 (04 §7.4). Трасса:
  `concept-paste mode=on … reason=flag-on`. Sarpedon — по умолчанию: `concept-scene status=ok mode=lit3d`.

| Прогон | Доска, размер | Итог | Трассы |
|---|---|---|---|
| `pv-marm-1080` combat-20261006-105024 | Marmoreal original, 1920×1080 | PASS, FINISHED, seq 110 | `markers=0` ×2, `v2=6` ×2 |
| `pv-sarp-1080` combat-20261006-105247 | Sarpedon original, 1920×1080 | PASS, FINISHED, seq 72 | то же |
| `pv-marm-720` combat-20261006-105359 | Marmoreal original, 1280×720 | PASS, FINISHED, seq 65 | то же |
| `pv-sarp-720` combat-20261006-105508 | Sarpedon original, 1280×720 | PASS, FINISHED, seq 62 | то же |
| `pv-marm-720-dpilegacy` combat-20261006-111146 | Marmoreal, 720p, `-S08DpiLegacy` | PASS, FINISHED, seq 63 | `dpi=legacy` |
| `pv-sarp-1080-ui150` combat-20261006-111246 | Sarpedon, 1080p, `-S08UiScale=150` | PASS, FINISHED, seq 30 | — |

Манифесты прогонов с sha256 каждого PNG лежат в [runs-manifests.json](runs-manifests.json). Строки трасс `ARTLOOK`,
`concept-paste` / `concept-scene`, `TOAST`, `RESULT` — в [trace-excerpts.txt](trace-excerpts.txt), у каждой трассы
указан sha256. Полные трассы и PNG остались вне git: `C:/tmp/visual/VS1-frames/runs/`.

## Состав листа (02 §13.2)

| № | Пункт | Файлы | Есть |
|---|---|---|---|
| 1 | Мастер и рабочие размеры | кадры 1920×1080 и 1280×720 | да (для HUD мастера нет) |
| 2 | Цвет, серый Rec.709, дейтеранопия | `sheet-01…08-after-*.png` | да |
| 3 | Кадр на обеих настоящих досках, 1080p и 720p, UI 150 % | `frames/`, пары `pair-*.jpg` | да, но не `-Bench` (ВР-VS1-F01) |
| 4 | Контекст: `panel.bg`, `card.cream`, поле | — | — (кадры непрозрачные, контекст — сама сцена) |
| 5 | Движение | — | — (HB-02 движения не добавляет) |
| 6 | Трассы `ARTLOOK`, `concept-paste` | `trace-excerpts.txt` | да |
| 7 | README | этот файл | да |

- Пары «до | после»: [pair-marmoreal-1080-turn.jpg](pair-marmoreal-1080-turn.jpg), `…-combat`, `…-result`; то же
  для `sarpedon` и для `720`. На 1080p слева прогон I, на 720p слева эта упаковка с `-S09Markers`.
- [frames-index.json](frames-index.json): у каждого JPG указаны источник, его sha256 и размер.

## Замеры

- **Маркеры гейтов, все кадры игрока.** [marker_check.py](marker_check.py) ищет сплошной блок цвета маркера: не меньше
  5 строк, в каждой подряд не меньше 48 px в пределах ±16. Цвета маркеров — 17 констант `GS09*` / `GS10*` / `GResult*`.
  Цвет `#7CFC00` пропущен: им же рисуется текст раскрытых значений.
  - 150 PNG шести прогонов `-PlayerView` — блоков 0 ([marker-check-player-view.json](marker-check-player-view.json)).
  - Контроль: 12 кадров со слоем (прогон I и `markers-*`) — блок найден на каждом
    ([marker-check-control.json](marker-check-control.json)): `#FF00FF`, `#FF4040`, `#4080FF`, 4 цвета полосы результата.
- **Эхо команд.** Тосты, отфильтрованные HB-02, хранятся как прежде: 323 строки `TOAST text="… sent …"` в трассах
  `-PlayerView`. На кадрах их нет.
- **Обратный гейт `-PlayerView`.** У всех шести прогонов: `ARTLOOK … markers=0` у обоих клиентов, оттенки боя на
  кадрах защиты, разрешения и результата — 0, приватность до раскрытия соблюдена.
- Контраст, ΔE, ΔGPU не мерились. HB-02 только убирает виджеты, бюджет карточки — «ΔGT ≤ 0 мс».

## Проверка глазами (G-LOOK)

- **Открыты целиком:** 8 кадров выхода (свой ход и бой × 2 доски × 1080p и 720p). Кроме них — результат Marmoreal
  1080p, панель колоды, кадры `-S08DpiLegacy` и UI 150 %, 12 пар и 8 листов.
- **Доска.** Marmoreal original 7×6 и Sarpedon original 9×6 (`BOARD … boardId=` сверен со строкой игры сервера).
- **Задник.** Marmoreal — нарисованный (вклейка, `-ConceptPaste`), Sarpedon — остров `lit3d` с кораблём, пушками и
  огнями.
- **Фигуры.** Шесть фигур v2: King Arthur, Merlin, Medusa, три гарпии. На кадрах они в цвете команд, трасса
  `SHOT figure … art=1 blockout=0` у всех шести. Павшие фигуры к концу партии растворяются — так задумано.
- **Отладочного слоя нет.** Нет полосы `#FF00FF` над черновиком, нет строк `you:` / `opponent:` / `seq=` справа
  сверху (там теперь «Opponent is attacking»). Нет тоста «begin maneuver sent» / «choice sent» / «defense sent»,
  нет полосы из 4 цветов над «VICTORY / DEFEAT».
- **В сером и при дейтеранопии** HUD читается так же. Зоны карт различаются хуже: на Sarpedon красные и зелёные клетки
  в сером близки, на Marmoreal зелёные и синие при дейтеранопии. Это рисунок самих карт, не HB-02; см. «Открыто».

## Что не прошло или открыто

1. **Служебные слова в командной панели остались.** Это «COMBAT OVER (seq N)», «actions left: 2 phase:
   ACTION_MANEUVER» и «next: TARGET_FIGHTER – opens when the combat ends». Карточка их не перечисляет и запрещает менять
   тексты игрока. Формально критерий выполнен: нет `seq=` и `phase=`. Это кандидат в блок командной панели (VS-4) или
   в отдельную карточку.
2. **720p: ряд карт руки уходит за нижний край.** Нижняя панель растёт вниз и в части состояний выталкивает ряд карт:
   `after-*-720-turn`, `markers-sarpedon-720-turn`. С `-S08DpiLegacy` то же самое (`dpilegacy-marmoreal-720-turn`),
   значит причина не только в HB-09. При UI 150 % на 1080p ряд карт обрезан, левая панель карты закрывает гарпий и их
   полоски HP, субтитр ложится на плашку фигуры. Это задача корня HUD (VS-2).
3. **Субтитры озвучки на русском, HUD — на английском.** Причина — культура `ru` по умолчанию с HB-05, а Slate HUD ещё
   не переведён на `UmText`.
4. **Бледное поле Marmoreal в начале партии.** На 720p у джойнера при `-ConceptPaste` поле в окнах защиты и разрешения
   светлее (молочное): `after-marmoreal-720-combat`, seq 4. На более поздних кадрах и в других прогонах поле
   нормальное. Причину не искал, относится к EN-13 / ENV-U16.
