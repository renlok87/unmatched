# 05 — План производства визуала (фаза 3)

Дата: 2026-10-06. Фаза 3 визуального чата ([00-VISUAL-BRIEF.md](00-VISUAL-BRIEF.md) §1 п. 3, §5, §7 строка 05).
Срез — HEAD `c5e7a971` (номера строк кода в карточках верны на нём; позже звук AU-S5 сдвинул `S08FlowGameMode.cpp`,
ищите по имени функции). Что делать — [02-visual-design.md](02-visual-design.md) и [04-hud-spec.md](04-hud-spec.md).
Карточки — [06-tasks/](06-tasks/): 7 таблиц, 282 строки. Шаблоны промптов и схема журнала трат —
[07-prompt-templates.md](07-prompt-templates.md). Журнал трат — [credits-ledger.json](credits-ledger.json).
Решения: [ВР-01…ВР-60](../decisions/2026-10-06-visual-delegated-decisions.md), ВР-61…ВР-79 (02 §0.2), ВР-PR01…ВР-PR11
(07 §6) и решения этого документа ВР-PL01…ВР-PL14 (§8). Образец формы — план звука
[../audio/05-production-plan.md](../audio/05-production-plan.md).

**Статус — «предложено».** Все решения приняты по делегированию: пользователь 2026-10-06 — «Не знаю. Делай сам, меня
это не касается. Все решения принимай». План ничего не генерирует. Генерация — только по готовой карточке
(START-PROMPT: «Генерируй только по готовой карточке задачи»).

**Что учтено после описи** (`git log 8aa356ff..HEAD`):
- прогон I ([I-2026-10-05.md](../de-footage/task/runs/I-2026-10-05.md)): глифы DE-012 в наборе v3 (`30ade784`), AB-5…AB-8
  по умолчанию с флагами отката (`99ce5a1b`). В карточках это IC-28…IC-31 и FX-33 со статусом «сделано»;
- звук влит (`d73d504c`), голос Arthur переозвучен (`c5e7a971`). Визуальных правил это не меняет;
- баланс SYNTX упал с 478 (2026-10-05) до 173,771 (2026-10-06 05:40, последняя строка
  [старого журнала](../../art-pipeline/evidence/s3-baseline-2026-09-28/credits-ledger.json), траты звука).

## 0. Коротко

- **Объём.** 282 карточки: 53 сделано (IC-01…IC-32, FX-33, AN-01…AN-16, AN-19, AN-20, AN-27, AN-28), 5 после MVP
  (SC-39…SC-43, статус «ждёт ВР-SC16», ВР-79). В работу — **224**.
- **Очередь (ВР-03):** P0 отладка из вида игрока → P1 HUD партии на UMG → P2 карта в руке, рубашка, инспектор →
  P3 ENV-U16 Marmoreal → P4 VFX боя → P5 экраны → P6 поворот фигур и правки героев → P7 хвосты Sarpedon.
- **Две линии работы** (ВР-PL02):
  - линия UE идёт строго по P0…P7: один worktree, одна упаковка на шаг, кадр на обеих досках;
  - линия генерации (пакеты Codex, вызовы SYNTX) идёт на шаг впереди: пакет запускается, как только готовы его входы.
- **Зависимость сильнее приоритета** (ВР-PL03): карточки ниже P1, без которых не собрать P1, идут в спринт P1: рамка и
  виджет карты (P2) для руки и боя, контракт CUE FX-01 (P4) для CUE-005/006/010.
- **Траты.** SYNTX — ожидаемо 24 токена (EN-03), потолок визуала 54 (ВР-PL10). Tripo — 0 (ВР-18). Codex — 61 пакет
  в 34 чатах, не больше 49 генераций image_gen. Покупок нет (ВР-04).
- **Приёмка** — по делегированию (ВР-17, ВР-42, ВР-60): листы в `docs/game-design/evidence/VISUAL/`, строка реестра 03.
- **От пользователя не нужно ничего**, кроме блокеров: оплата, пароль, капча.

| Спринт | P | Цель | Карточек | Codex: пакетов (чатов) | SYNTX | Дней, оценка | Выход: кадры на обеих досках |
|---|---|---|---|---|---|---|---|
| VS-1 | P0, P1 | чистый вид, токены, строки, основа значков и медиа карт | 21 | 7 (7) | 0 | 3 | лист HB-02 «до / после»: нет неона, `seq=`, `deck=…~`, эха команд; 1080p и 720p |
| VS-2 | P1 | корень HUD, кнопки, значки VR44, курсоры, портреты, верхняя полоса | 55 | 13 (13) | 24 (≤ 54) | 5 | наборы A (покой) и B (ход соперника) 04 §7.2, реальные аватары |
| VS-3 | P1, P2 | рука со сканами, колода, бой у краёв | 22 | 2 (2) | 0 | 5 | наборы A (наведение, выбрана атака), C (окно защиты, раскрытие, штамп, «−N»), E (панель колоды) |
| VS-4 | P1, P2 | выбор, слот, лента, тосты, кнопки, мировой слой, инспектор, приёмка HUD | 27 | 6 (4) | 0 | 5 | лист HB-49: наборы A–E, H, I; HUD на UMG по умолчанию |
| VS-5 | P3 | ENV-U16: нарисованный задник Marmoreal по умолчанию | 14 | 16 (4), макеты SC | 0 | 4 | Marmoreal K1, K2×1,6, K2×2,5 с вклейкой; откат `-NoConceptPaste`; пересъёмка A и C на Marmoreal |
| VS-6 | P4 | VFX боя по CUE, постпроцесс исхода и связи | 32 | 17 (4), макеты SC | 0 | 5 | бой K1 и K2: удар, лечение, смерть «пепел», вихрь Medusa, дуга Arthur; бенч ΔGPU ≤ 1 мс |
| VS-7 | P5 | экраны BOOT…ABORTED на UMG | 35 | — | 0 | 5 | наборы F и G 04 §7.2, набор I (псевдолокаль, EN) |
| VS-8 | P6 | поворот фигур, ease шага, цифры гарпий, правки материалов | 11 | — | 0 | 3 | листы клипов K1/K2 в цвете и сером (ВР-17), фигуры никогда спиной к камере |
| VS-9 | P7 | хвосты Sarpedon P10 | 7 | — | 0 | 2 | Sarpedon K1/K2 свежий `-Bench`, Marmoreal — контрольный кадр |
| Закрытие | — | полный раунд GD-058, сверка реестра | — | — | 0 | 1 | эталон GD-058 обеих досок (ВР-59) |

Сумма — 224 карточки, около 38 дней работы агента. Это оценка, не замер (ВР-PL14). Макеты экранов SC-03…SC-38
делаются в VS-5 и VS-6 (линия генерации), UE-часть этих карточек — в VS-7.

## 1. Цикл одной единицы

Цикл брифа §5: задание → генерация → ревью и коммит → импорт в UE → кадр → приёмка и интеграция. Единица — карточка
`06-tasks/*.csv`. Шаг интеграции — блок 04 §5.2 (H0…H16) или группа карточек одного ассета.

### 1.0 Где что живёт

| Что | Где | В git |
|---|---|---|
| задание (заполненный шаблон) | `docs/game-design/visual/06-tasks/prompts/<id>.codex.md`, `<id>.syntx.txt` (ВР-PR09) | да, до запуска |
| пакет Codex | `art/imagegen/<set>-codex/` | да, после ревью |
| картинки со сканами, аватарами, иллюстрацией доски, концептом окружения | `scraped-data/derived/<set>-codex/` (ВР-PR01) | нет |
| сырые ответы SYNTX | `C:/tmp/visual-syntx/<id>/raw/` | нет |
| листы «наш ассет рядом с кадром DE» | `C:/tmp/visual-review/<set>/` (ВР-60) | нет |
| рабочие кадры, логи, трассы | `C:/tmp/visual/<id>/` | нет |
| журнал трат | [credits-ledger.json](credits-ledger.json) | да |
| UE-работа | worktree `C:/tmp/wt-visual`, ветка `feat/visual-vs<N>` (ВР-PL01) | через `safe-integrate.sh` |
| лист приёмки | `docs/game-design/evidence/VISUAL/<id>/`, итог спринта — `.../VISUAL/VS-<N>/README.md` | да |

### 1.1 Инструменты

| Инструмент | Что делает | Есть |
|---|---|---|
| `tools/art/visual/prompt_build.py <id>` | строка карточки → файл задания: блоки `[[B-STYLE]]`, `[[B-PALETTE-CORE]]`, `[[B-FORBID]]`, `[[B-PACKAGE]]` из 07 §0.3 и §1.1 дословно, `{{set}}` из `deliverable`, sha256 входов из `references` | нет, VS-1 шаг 0 (ВР-PL13) |
| `tools/art/visual/ledger.py add / check` | строка журнала по 07 §4.2: замок, временный файл, `os.replace`, отступ 2, `ensure_ascii False`; `check` сверяет суммы и лимиты | нет, VS-1 шаг 0 |
| `tools/art/visual/sheet.py <id>` | лист приёмки 02 §13.2: цвет, серый Rec.709, дейтеранопия; 1080p и 720p; мастер и рабочие размеры; README-шаблон | нет, VS-1 шаг 0 |
| `tools/art/render/live_tune.py` | итерации параметров в одном клиенте, `bench` — свежий `-Bench` ([LIVE-TUNE.md](../../../tools/art/render/LIVE-TUNE.md)) | да |
| `tools/art/render/render_bench.py`, `hero_light_metrics.py`, `tools/art/render_fingerprint.py` | цена рендера, метрики света, отпечаток `RENDER` | да |
| `tools/art/render/env_gates.py` | гейты окружения G4–G7 | нет, карточка EN-05 |
| `tools/s08/hud_contract/hud_contract.py validate / check-trace` | G-TOKENS, G-WIDGET | да; генератор токенов — HB-03 |
| `tools/s08/cue_contract/cue_contract.py` | G-CUE | да |
| `art/imagegen/hud-icons-v3/_tools/compare_ue_gallery.py` | G-ICON | да |
| `tools/s08/build-editor.cjs`, `run-ue-tests.cjs`, `package-client.ps1`, `sync-staged-build.ps1` | сборка, тесты UE, упаковка, перенос упаковки | да |
| `tools/git/safe-integrate.sh` | интеграция ветки в `fix/admin-panel` | да |

### 1.2 Шаг 1. Задание

1. Claude берёт строку карточки. Пустое поле не выдумывается: карточка возвращается на доработку (07 §0.2).
2. `python tools/art/visual/prompt_build.py HB-07` пишет `docs/game-design/visual/06-tasks/prompts/HB-07.codex.md`:
   шапка (id, дата, шаблон, `set`), текст колонки `prompt` с раскрытыми блоками, список входов с sha256.
3. Claude читает файл целиком: нет названий «Unmatched», «Digital Edition», художников (ВР-PR07); hex только из 02 §2;
   входы — только наши файлы (ВР-PR08).
4. Коммит в основной копии, только этот путь:
   `git add -- docs/game-design/visual/06-tasks/prompts/HB-07.codex.md`, затем
   `git commit --no-verify -m "docs(visual): HB-07 Codex task" -- docs/game-design/visual/06-tasks/prompts/HB-07.codex.md`.
5. В папку пакета Codex Claude ничего не пишет: дословные промпты туда копирует сам Codex (`prompts/`).

### 1.3 Шаг 2. Генерация

**Codex** (ВР-PL05, ВР-PL06):
- один чат — один пакет; экраны одного семейства — серией в одном чате, у каждой карточки своя папка;
- приложение ChatGPT (пакет OpenAI.Codex) — для пакетов с image_gen (IC-36, IC-37, EN-01, EN-02, FX-20, FX-29,
  FX-31): `open_application ChatGPT` → Ctrl+N в проекте `unmached` → сообщение «Прочитай
  docs/game-design/visual/06-tasks/prompts/HB-07.codex.md и выполни задачу. Пиши только в своей папке, git не трогай.»
  → Enter. TextInputHost может забрать фокус: `open_application` прямо перед нажатием;
- `codex.exe exec` — для пакетов без генерации (макеты, 9-slice, рамка, листы поз, маски EN-04) и когда приложение
  недоступно. npm-версия `codex` не работает:

  ```text
  "C:/Program Files/WindowsApps/OpenAI.Codex_<версия>/app/resources/codex.exe" exec
    -C C:/Users/ren/WebstormProjects/unmached/unmached "Прочитай <файл задания> и выполни задачу"
  ```
- после пакета — строка журнала: `service Codex`, `units` «пакет, N генераций image_gen», `cost` и балансы `null`.

**SYNTX** (07 §2.4): `create-chat` → `upload-files` (только входы карточки) → `get-model-info` (цена; выше потолка
07 §2.3 — отмена) → `get-balance` → `generate-image` с `n 1` → `wait-for-response` → скачать в
`C:/tmp/visual-syntx/<id>/raw/` → скопировать в путь результата → `get-balance` → `ledger.py add`.
- До первой траты модели — строка `providerTerms`: сервис, модель, ссылка на условия, дата (ВР-05).
- Стоп, если баланс перед запуском меньше 20. Сначала 1 вариант, не больше 2 повторов.

### 1.4 Шаг 3. Ревью и коммит

Один проход по 07 §5, арт и рамки задачи вместе. До коммита:
1. `git status --porcelain`: изменены только `art/imagegen/<set>-codex/**`; индекс пуст; `git log` не вырос; в `unreal/`
   изменений нет. Чужие незакоммиченные файлы (§4.1) не тронуты.
2. `verification.json`: `source_unchanged: true`, `outside_folder: []`, все строки `acceptance` с `passed`.
3. Каждый финал открыт (Read PNG): значки 24 / 32 / 48 px ×4 nearest, скины ×1 и ×2, карты — показы 02 §6.2,
   макеты HUD 1080p и 720p при 100 % и 150 %; цвет и серый. Метрик мало.
4. Реальные данные: каждое имя, число, карта и аватар прослеживаются до `manifest`; «уточнить» вместо выдумки допустимо.
5. Нет ImageGen на макетах, сканах и аватарах; нет кадров DE во входах; траты записаны.
6. Строка ревью в README пакета (дата, что принято, что нет).
7. Коммит перечислением путей; `git diff --cached --name-only` перед коммитом показывает только папку пакета.
   Картинки из `scraped-data/` в коммит не попадают:

   ```text
   git add -- art/imagegen/hud-composition-v1-codex
   git commit --no-verify -m "art(visual): HB-07 composition mockups" -- art/imagegen/hud-composition-v1-codex
   ```

8. Пакет вышел за рамки (правка вне папки, ImageGen в макете, выдуманные данные) — пакет отклоняется, задание
   уточняется, новый чат.

### 1.5 Шаг 4. Импорт в UE (worktree)

Первый раз (VS-1 шаг 0):
1. `git worktree add -b feat/visual-vs1 C:/tmp/wt-visual fix/admin-panel`. Путь короткий: `core.longpaths` выключен.
2. `node_modules` — junction на основную копию; `npm install` и `prisma generate` не запускать.
3. Gitignored `unreal/Unmatched/Content/**` скопировать из основной копии в worktree: robocopy без `/MIR`, только в
   сторону worktree. Список папок — `docs/art-pipeline/DIRECTORY-MAP.md` и то, что грузит `S08Arena`.

Каждый шаг:
1. Свежие пакеты Codex — в ветку: `git merge fix/admin-panel` в worktree.
2. Импорт скриптом `tools/art/<x>_import.py` по образцу `icons_v3_import.py` (`hud_skins_import.py`,
   `cards/ue_import_card_media.py`, `concept_paste/cp_bake.py` — из карточек). Ассет рождается из файлов в git.
3. Код — в новых файлах `S08/UI/*`; в `S08FlowGameMode*.cpp` только точки подключения, до ~40 строк на файл (04 §5.1).
4. Сборка. `Build.bat` может вернуть 0 при ошибке компиляции: читать хвост лога.

   ```text
   node tools/s08/build-editor.cjs UnmatchedEditor Win64 Development
     -Project=C:/tmp/wt-visual/unreal/Unmatched/Unmatched.uproject -WaitMutex -NoXGE -MaxParallelActions=4
   ```
5. Тесты: `node tools/s08/run-ue-tests.cjs Unmatched.S08.Hud C:/tmp/visual/<id>/ue-tests.log`, pytest затронутых
   `tools/`, гейты карточки.
6. Режим (AGENTS.md «Iteration speed», 02 §13.4):
   - лёгкий — правка параметров (профиль доски, раскладка, свет, opacity): ≤ 3 итерации live tune в одном клиенте,
     только затронутые гейты, без отдельного ревью и бенча:

     ```text
     python tools/art/render/live_tune.py start --map marmoreal
     python tools/art/render/live_tune.py cycle --views K1+K2x1.6+K2x2.5 --out C:/tmp/visual/<id>/i1 --tag i1
     python tools/art/render/live_tune.py stop
     ```

   - полный — новая система (блок UMG, Niagara, ассет окружения, генератор): все гейты, ревью, `render_bench.py`.
7. Упаковка — одна на шаг, где меняется вид: `powershell -NoProfile -File C:/tmp/wt-visual/tools/s08/package-client.ps1`.
   Новый или переименованный `Config/**.json` попадает в pak только после `touch` `Unmatched.Build.cs` и сборки игры
   с `-MaxParallelActions=4`.
8. Новые uasset принятых ассетов — `git add -f` по путям задачи, как `Content/S08/UI/IconsV3` и `Content/Audio`
   (ВР-PL08).

### 1.6 Шаг 5. Кадр

- Только Marmoreal original (`c121b47f8d6eb28daccb76d05`) и Sarpedon original (`c7fa64a26c29a0835f2383e63`), шесть фигур
  v2. Marmoreal до EN-13 — `-ConceptPaste` с пометкой на листе (04 §7.4), после — вклейка по умолчанию.
- Приёмочные кадры — свежий packaged `-Bench` с отпечатком `RENDER` (High, SP 100), то же для `sarpedon`. Кадры live
  tune — только для итераций:

  ```text
  python tools/art/render/live_tune.py bench --packaged --map marmoreal --views K1+K2x1.6+K2x2.5
    --out C:/tmp/visual/<id>/marmoreal
  ```

- HUD — гейты `tools/s09/run-*.ps1` и `tools/s10/run-*.ps1` со съёмкой `SHOT`, 1920×1080 и 1280×720, UI 100 % и 150 %.
  Два клиента — по 30 FPS каждый (`tools/s08/run-phase2-demo.ps1 -ClientFps 30`).
- **Перед отчётом Claude открывает каждый PNG** (Read): доска настоящая, задник верный для карты, все шесть фигур v2.
  Трасс мало (AGENTS.md «Look before you report»).

### 1.7 Шаг 6. Приёмка, реестр, интеграция

1. `python tools/art/visual/sheet.py <id>` собирает лист в `docs/game-design/evidence/VISUAL/<id>/` по 02 §13.2:
   мастер и рабочие размеры, цвет / серый / дейтеранопия, кадры обеих досок, контекст, движение, трассы `ARTLOOK`,
   `SHOT widget`, `CUE fx`, `concept-paste`, README с замерами и флагом отката.
2. Решение — «художественно принято, по делегированию», дата, ссылка на лист. Принятое включается по умолчанию, прежнее
   — флагом `-S08…Legacy` или `-S08SlateHud`; флаг вписывается в `S08ArtLook.h` и трассу `ARTLOOK`.
3. Коммит листа и кода в ветке спринта (`--no-verify`, перечисление путей).
4. Интеграция (AGENTS.md «Parallel sessions»):
   - в worktree: `git merge fix/admin-panel`, пересборка, тесты шага;
   - сухой прогон `bash tools/git/safe-integrate.sh feat/visual-vs1`, затем тот же вызов с `--apply`;
   - перед `--apply` — сверка входящих uasset с игнорируемыми файлами основной копии, при совпадении путей — копия в
     `C:/tmp/visual-backup/<дата>/` (ВР-PL08).
5. В основной копии после интеграции, тронувшей `unreal/`:
   - пересобрать UnmatchedEditor (команда из вывода `safe-integrate.sh`);
   - скопировать новые gitignored папки `Content` шага, если они не в git;
   - `powershell -NoProfile -File tools/s08/sync-staged-build.ps1 -From C:/tmp/wt-visual`. Скрипт откажет, если штамп
     упаковки не совпал с HEAD; тогда не перепаковывать, а выяснить причину.
6. Статусы карточек в `06-tasks/*.csv` и строку реестра [03-asset-registry.csv](03-asset-registry.csv) Claude правит
   в основной копии отдельным коммитом (ВР-PL09).
7. Процессы, запущенные шагом, остановить, проверив командную строку, родителя и путь; по имени не убивать. Редактор
   пользователя не закрывать.

## 2. Очередь пакетов Codex и генераций SYNTX

Пакет `CX-NN` — один чат Codex, `SX-NN` — один вызов SYNTX. Папка вывода — `art/imagegen/<set>-codex/`, картинки со
сканами и доской — `scraped-data/derived/<set>-codex/`. Оценка — время агента на чат и ревью: S ≈ 1 ч, M ≈ 2–3 ч,
L ≈ полдня. Это оценка; после CX-01 она пересчитывается (ВР-PL14).

| Пакет | Карточки | Шаблон | Входы | `<set>` | Когда | Оценка | Генерации |
|---|---|---|---|---|---|---|---|
| CX-01 | HB-07 | T-CODEX-LAYOUT | bench K1 P7 Marmoreal и P10 Sarpedon; данные партии прогона I; аватары; `reused-cardart.json` | `hud-composition-v1` | VS-1 | L | 0 |
| CX-02 | HB-08 | T-CODEX-9SLICE | токены 02 §2–§4; кропы K1 обеих досок | `hud-skins-v1` | VS-1 | M | 0 |
| CX-03 | HB-44 | T-CODEX-LAYOUT | K1 обеих досок; кадры урона прогона I | `hud-world-v1` | VS-1 | M | 0 |
| CX-04 | IC-36 | T-CODEX-2D | STYLE-v3, `draw_icons.py`, листы v3 | `hud-icons-vr44` | VS-1 | M | image_gen 8 + ≤ 1 |
| CX-05 | IC-37 | T-CODEX-2D | то же; 8 ключей зон из топологии | `zone-icons` | VS-1 | M | image_gen 16 + ≤ 8 |
| CX-06 | CP-13 | T-CODEX-CARDFRAME | 27 карт `reused-cardart.json`; рубашки `Hero.imageUrl` | `card-frame-v1` | VS-1 | M | 0 |
| CX-07 | EN-01 | T-CODEX-ENVPLATE | концепт C0 `marmoreal-v1.png`; `marmoreal.paste.json` | `env-u16-marmoreal` | VS-1 | L | image edit ≤ 4 |
| CX-08…CX-15 | HB-13, HB-17, HB-22, HB-26, HB-29, HB-34, HB-38, HB-42 | T-CODEX-LAYOUT | пакет CX-01 (числа раскладки) и его входы | `hud-topstrip-v1`, `hud-panels-v1`, `hud-hand-v1`, `hud-decks-v1`, `hud-combat-v1`, `hud-pending-v1`, `hud-feed-v1`, `hud-actions-v1` | VS-2, после ревью CX-01 | M каждый | 0 |
| CX-16 | CP-07 | T-CODEX-CARDFRAME | аватары PNG из CP-01 | `portrait-crop-v1` | VS-2 | S | 0 |
| CX-17 | EN-02 | T-CODEX-ENVPLATE | плита и маски CX-07 | `env-u16-marmoreal` | VS-2 | M | image edit ≤ 6 |
| SX-01 | EN-02, запас | T-SYNTX-IMG-BANANA, `banana3` 2K | плита CX-07, поле `#808080` | — | VS-2, только если CX-17 не держит живопись | S | SYNTX ≤ 6 |
| SX-02 | EN-03 | T-SYNTX-UPSCALE, `magnific` / `precision_v2` ×2 | `marmoreal-clean-ext.png`, `marmoreal-lit-ext.png` | — | VS-2 | S | SYNTX 2 × 12 = 24 |
| CX-18 | FX-20 | T-CODEX-VFX | 02 §9; кроп нашего K1 | `fx-hitstar` | VS-2 | M | image_gen ≤ 2; запас GPT ≤ 4 |
| CX-19 | FX-29 | T-CODEX-VFX | то же | `fx-vortex` | VS-2 | M | image_gen ≤ 2; запас ≤ 4 |
| CX-20 | FX-31 | T-CODEX-VFX | то же | `fx-arc` | VS-2 | M | image_gen ≤ 2; запас ≤ 4 |
| CX-21 | EN-04 | T-CODEX-ENVPLATE, только маски | результат SX-02 | `env-u16-marmoreal` | VS-3 | M | 0 |
| CX-22 | SC-01 | T-CODEX-LAYOUT | токены; кадры P7 и P10 | `sc01-screen-base` | VS-3 | M | 0 |
| CX-23 | SC-21…SC-23 | T-CODEX-LAYOUT | библиотека CX-22; сканы | `sc21-inspect-own`, `sc22-inspect-hidden`, `sc23-inspect-deck` | VS-4 | M | 0 |
| CX-24…CX-26 | AN-22, AN-26, AN-30 | T-CODEX-ANIMSHEET | наши рендеры v2; 02 §8.3, §8.4, §9.2 | `anim-move-sheet`, `anim-facing-sheet`, `anim-death-sheet` | VS-4 | S каждый | 0 |
| CX-27 | SC-03…SC-05 BOOT | T-CODEX-LAYOUT | библиотека CX-22 | `sc03-…` … `sc05-…` | VS-5 | M | 0 |
| CX-28 | SC-06, SC-07 LOGIN | T-CODEX-LAYOUT | то же | `sc06-…`, `sc07-…` | VS-5 | S | 0 |
| CX-29 | SC-08…SC-13 LOBBY | T-CODEX-LAYOUT | то же; доски, герои | `sc08-…` … `sc13-…` | VS-5 | L | 0 |
| CX-30 | SC-14…SC-18 ROOM | T-CODEX-LAYOUT | то же; аватары CP-01 | `sc14-…` … `sc18-…` | VS-5 | L | 0 |
| CX-31 | SC-19, SC-20 загрузка | T-CODEX-LAYOUT | то же | `sc19-…`, `sc20-…` | VS-6 | S | 0 |
| CX-32 | SC-24…SC-30 PAUSE и настройки | T-CODEX-LAYOUT | то же | `sc24-…` … `sc30-…` | VS-6 | L | 0 |
| CX-33 | SC-31…SC-33 RECONNECT | T-CODEX-LAYOUT | то же | `sc31-…` … `sc33-…` | VS-6 | M | 0 |
| CX-34 | SC-34…SC-38 GAMEOVER, ABORTED | T-CODEX-LAYOUT | то же; аватары | `sc34-…` … `sc38-…` | VS-6 | L | 0 |

Итого: 61 пакет в 34 чатах; image_gen Codex — 26–49 (подписка); SYNTX — ожидаемо 24, потолок 54 (ВР-PL10);
Tripo — 0. Макеты в `T-CODEX-LAYOUT` и `T-CODEX-CARDFRAME` генерацию изображений не используют (ВР-PR02).

Порядок внутри линии генерации:
- CX-01 первым: от него зависят 8 макетов HUD. Пока он в ревью, идут CX-02…CX-07.
- CX-07 → CX-17 → SX-02 → CX-21 — цепочка плиты. Запускается рано, потому что баланс SYNTX общий со звуком и тает
  (ВР-PL02).
- Пакеты экранов — после ревью CX-22; карточки SC сами говорят: «макет не ждёт depends_on, ждёт только пакет SC-01».

## 3. Спринты

Для каждого спринта: карточки по порядку, что только UE и скрипты, что требует генерации, гейты, кадры выхода, риски.
Шаги 04 §5.2 указаны в скобках. Итог спринта — `docs/game-design/evidence/VISUAL/VS-<N>/README.md` (ВР-PL14).

### VS-1. Чистый вид и основа (P0, начало P1)

- **Шаг 0.** Worktree `C:/tmp/wt-visual`, ветка `feat/visual-vs1`; копия `Content`; инструменты `tools/art/visual/`
  с pytest; папки `06-tasks/prompts/` и `evidence/VISUAL/`.
- **По порядку:** HB-01 → HB-02 (H0a, H0b, одна упаковка); HB-03 → HB-04 (H1); HB-05; HB-09; IC-33; FX-01 → FX-11,
  FX-12, FX-18; CP-01 → CP-02; EN-05.
- **Только UE и скрипты:** все 14 карточек выше. HB-03, HB-05, FX-01, FX-11, FX-12, FX-18 вид не меняют — без упаковки.
- **Генерация:** CX-01…CX-07 (HB-07, HB-08, HB-44, IC-36, IC-37, CP-13, EN-01).
- **Гейты:** `run-hud-demo`, `run-combat-demo`, `run-duel-demo`, `run-pending-demo`, `run-hud-probe`, `run-vs-ai-demo`,
  `run-vs-ai-abort-demo` с `-S09Markers` — PASS; G-TOKENS; `cue_contract.py validate-table` и `run-fixtures`; тесты
  `Unmatched.S08.ArtLook.*`, `Unmatched.S08.Hud.Tokens.*`, `Unmatched.S08.IconMotion.*`; pytest `tools/s08/hud_contract`,
  `tools/art`.
- **Кадры выхода:** лист HB-02 — свой ход и бой на Marmoreal и Sarpedon, 1080p и 720p. «До» — кадры прогона I
  (ВР-PL11), «после» — упаковка шага.
- **Риски:** пиксельные гейты без флага падают — поэтому HB-01 раньше HB-02; HB-02 правит `S08FlowGameMode.cpp` и
  `…Result.cpp`, горячие файлы (§4).

### VS-2. Корень HUD, значки, портреты, верх (P1)

- **По порядку:**
  1. HB-06 (H2) → HB-10, HB-11, HB-23 (H3);
  2. значки: IC-38, IC-40, IC-42…IC-45, IC-47, IC-50, IC-51, IC-53, IC-54, IC-56, IC-58, IC-61 → IC-39, IC-41, IC-60
     → после CX-04 IC-46, IC-48, IC-55, IC-59 → IC-52 → IC-34 → IC-70;
  3. HB-12;
  4. портреты: CP-08 → после CX-16 CP-09…CP-12;
  5. верх (H5, H6): HB-14, HB-15, HB-16 — после CX-08;
  6. панели (H4): HB-18 → HB-19, HB-20 → HB-21 — после CX-09.
- **Только UE и скрипты:** HB-06, HB-10, HB-11, HB-12, HB-14…HB-16, HB-18…HB-21, HB-23, CP-08…CP-12, IC-70; значки —
  движок `draw_icons.py` (финал рисует скрипт).
- **Генерация:** CX-08…CX-20, SX-02 (и SX-01 при нужде). Карточки HB-13, HB-17, HB-22, HB-26, HB-29, HB-34, HB-38,
  HB-42, CP-07, EN-02, EN-03, FX-20, FX-29, FX-31.
- **Гейты:** G-WIDGET для `UI-HUD-TOP`, `-CONN`, `-STATUS`, `-BANNER`, `-PANEL-LOC`, `-PANEL-OPP`, `-OPP-HAND`;
  трасса `HUD-LAYOUT`; G-ICON ≤ 0,45 (IC-70); G-TOKENS; тесты `Unmatched.S08.Hud.<Блок>.Tree/.Layout/.Tokens`;
  синтетические клики по `UUmButton` n ≥ 20, 0 потерь; откат `-S08SlateHud` возвращает прежний вид.
- **Кадры выхода:** наборы A (свой ход, покой) и B (ход соперника, ИИ думает) на обеих досках; 1080p 100 % и 150 %,
  720p 100 % и 150 %; портреты с реальными аватарами через +0,5 и +3 с от начала хода.
- **Риски:** колонка портретов двигает руку (`HandObstacleRightSu`); порядок слоёв UMG и мирового слоя; баланс SYNTX
  ниже 44 к моменту SX-02 — план Б (ВР-PL10).

### VS-3. Рука, колода, бой (P1, нужные P2)

- **По порядку:**
  1. карты: CP-03, CP-04, CP-05, CP-06 → CP-14 → CP-15 → CP-16, CP-17, CP-18, CP-19, CP-20;
  2. рука (H7): HB-24 → HB-25;
  3. колода (H8): HB-27, HB-47 → HB-28;
  4. бой (H9): HB-30 → HB-31, HB-32 → HB-33;
  5. SC-01 — UE-часть `UUmScreenBase` (нужна инспектору в VS-4).
- **Только UE и скрипты:** всё, кроме пакетов ниже.
- **Генерация:** CX-21 (EN-04, маски без генерации), CX-22 (SC-01, макет).
- **Гейты:** G-WIDGET для `UI-HUD-HAND`, `-DECKS`, `-DECKPANEL`, `-COMBAT`, `-COMBAT-EDGE`; приватность — строк
  раскрытия нет до `state=reveal`; `run-combat-demo`, `run-duel-demo`, `run-hud-probe` — PASS; клики по
  `UUmCardWidget` n ≥ 20, 0 потерь; бюджет HUD ≤ 0,5 мс GT p95 и ≤ 0,3 мс GPU при 1080p (HUD-RULES П8).
- **Кадры выхода:** набор A (наведение на карту, выбрана атака; рука 3 / 7 / 9 карт), набор C (окно защиты у обоих
  клиентов, раскрытие, штамп «нет защиты», «−N»), набор E (панель колоды своя и чужая) — на обеих досках.
- **Риски:** H7 и H9 — высокие (самый частый блок, приватность до раскрытия); RU-названия карт King Arthur в скрапе
  пустые — бюджет длины RU не проверен («уточнить»); сканы только для LAN-сборки (ВР-48).

### VS-4. Выбор, лента, кнопки, мировой слой, приёмка HUD (P1, P2)

- **По порядку:**
  1. выбор (H10): HB-35 → HB-37;
  2. лента (H5, H11): HB-39, HB-40, HB-41 → HB-36;
  3. кнопки (H6): HB-43;
  4. мировой слой (H12): HB-45 → HB-46;
  5. инспектор (H13): CP-21, CP-22 → SC-21, SC-22, SC-23;
  6. значки зон IC-62…IC-69 и новая карточка FX-38 «значок зоны у клетки при наведении» (ВР-PL12);
  7. HB-48 — гейты `tools/s09`, `tools/s10` на трассах `SHOT widget`;
  8. HB-49 — лист приёмки HUD.
- **Только UE и скрипты:** все, кроме пакетов ниже.
- **Генерация:** CX-23 (макеты SC-21…SC-23), CX-24…CX-26 (листы AN-22, AN-26, AN-30 — вперёд для VS-6 и VS-8).
- **Гейты:** G-TOKENS, G-WIDGET, G-ICON, G-CUE, G-READ, G-GRAY, G-LOOK; `Unmatched.S08.Hud.*`, `Unmatched.S09.*`,
  синтетические клики 0 потерь; ΔGT UMG против `-S08SlateHud` ≤ 0,3 мс (`render_bench.py` без лимита FPS).
- **Кадры выхода:** лист HB-49 — наборы A–E, H, I по 04 §7.2 на обеих досках, цвет / серый / дейтеранопия. Marmoreal —
  с `-ConceptPaste` и пометкой (до ENV-U16). Реестр — «художественно принято, по делегированию».
- **Риски:** H10 — много путей ввода; класс S при 1138×640 su плотный — запасной шаг веера 72 su (04 §7.4).

### VS-5. ENV-U16 Marmoreal (P3)

- **По порядку:** EN-06 → EN-07 → EN-08, EN-09, EN-10, EN-11, EN-12 → EN-13 → EN-14 и AN-36 одним прогоном (ВР-PL04)
  → EN-15 → EN-16 → EN-17 → EN-18. После EN-15 — пересъёмка наборов A и C на Marmoreal (04 §7.4), лёгкий режим.
- **Только UE и скрипты:** все 14 карточек. Входы плиты — из CX-07, CX-17, SX-02, CX-21.
- **Генерация:** CX-27…CX-30 — макеты BOOT, LOGIN, LOBBY, ROOM.
- **Гейты:** `env_gates.py` G4–G7; G-LOOK; G-COST — `render_bench.py` (новые свет и Niagara); тесты
  `Unmatched.S08.ConceptPaste.*`, `.EnvLayout.*`, `.LiveTune.*`; с `-S08ReducedMotion` анимация вклейки заморожена.
- **Кадры выхода:** свежий packaged `-Bench` Marmoreal K1, K2×1,6, K2×2,5 с вклейкой по умолчанию; кадр отката
  `-NoConceptPaste`; контрольный кадр Sarpedon lit3d без изменений; эталон GD-058 лёгким режимом (ВР-59).
- **Записи:** EN-13 вписывает флаг `-NoConceptPaste` в AGENTS.md (ВР-56) и обновляет там запись «Known gap».
- **Риски:** вклейка не держит читаемость на K2 (ВР-58: тогда lit3d только по слову пользователя); ловушка упаковки
  новых `Config/**.json`.

### VS-6. VFX боя (P4)

- **По порядку:**
  1. основа: FX-02, FX-03, FX-05 → FX-04;
  2. поле: FX-07, FX-08, FX-09, FX-10, FX-14, FX-15 → FX-13, FX-16; IC-35;
  3. фигура: FX-06, FX-17, FX-19 → FX-21 → FX-22 → FX-23; FX-24 → FX-25; IC-49;
  4. смерть: FX-26 → FX-27, AN-29;
  5. способности: FX-28 → FX-30, FX-32;
  6. исход и связь: FX-34 → FX-35 → FX-36;
  7. FX-37 — худший набор, бенч и лист P4.
- **Только UE и скрипты:** все 32 карточки. Флипбуки — из CX-18…CX-20, схема смерти — CX-26.
- **Генерация:** CX-31…CX-34 — макеты загрузки, PAUSE, RECONNECT, GAMEOVER.
- **Гейты:** G-CUE (`cue_contract.py check-trace`); G-COST — ΔGPU ≤ 1 мс на худшем наборе, не больше 3 боевых систем,
  `UNiagaraEffectType` у каждой (ВР-25); G-GRAY — форма несёт смысл без цвета (ВР-21); повтор MS-AT-41 — draw calls ≤ 7;
  `run-combat-demo` — PASS.
- **Кадры выхода:** бой K1 и K2 на обеих досках: удар, «−N», лечение «+N», смерть «пепел», вихрь Medusa, дуга Arthur,
  шевроны, пыль; полосы таймингов; reduced motion; кадры откатов `-S08HitTintLegacy`, `-S08DissolveFade`,
  `-S08ChoiceLegacy`.
- **Риски:** красный урона против красной зоны (02 §9.3); детерминизм сида; бюджет GPU двух клиентов.

### VS-7. Экраны (P5)

- **По порядку:** SC-02 → BOOT SC-03…SC-05 → LOGIN SC-06, SC-07 → LOBBY SC-08…SC-13 → ROOM SC-14…SC-18 → загрузка SC-19,
  SC-20 (H15); PAUSE SC-24…SC-30 (H16); RECONNECT SC-31…SC-33, GAMEOVER SC-34…SC-37, ABORTED SC-38 (H14); IC-57.
- **Только UE и скрипты:** UE-части всех 35 карточек. Макеты готовы из CX-27…CX-34.
- **Гейты:** G-WIDGET для `UI-SCR-*`; `run-vs-ai-demo`, `run-vs-ai-abort-demo` по `SHOT widget id=UI-SCR-GAMEOVER` и
  `UI-SCR-ABORTED`; экран ≤ 0,5 мс GT p95 и ≤ 0,3 мс GPU; SC-02 — GPU фона меню не выше K1 партии.
- **Кадры выхода:** набор F (победа, поражение, «посмотреть доску», ABORTED, RECONNECT) на обеих досках; набор G
  (экраны на фоне Marmoreal) 1080p 100 %, 720p 100 % и 150 %; набор I (псевдолокаль +30 % и EN).
- **Звук экранов** (чат звука, `3bcbfb4a`, 2026-10-06): карта «экран → звук» по каждой карточке SC —
  [08-screen-audio-hooks.md](../audio/08-screen-audio-hooks.md). Экраны вызывают три `UFUNCTION(BlueprintCallable)`
  `AS08FlowGameMode`: `PlayScreenSound(FName BankId)` (клики, открытие панелей, логотип BOOT, выход из паузы),
  `SetAudioPaused(bool)` (PAUSE, музыка −10 дБ), `PlayHeroSelectSting(FString HeroName)` (подтверждение героя в ROOM).
  Музыка меню, вход, звуки комнаты, старт партии, результат, инспектор и CUE-017/018 звучат сами — повторно не вызывать.
  Импортировать ничего не нужно: ассеты в `/Game/Audio`. Чату звука сообщено: BOOT идёт до LOGIN и LOBBY (SC-03…SC-05),
  в ROOM есть отсчёт 3-2-1 (SC-18).
- **Риски:** H15 — новые запросы и поток стадий; смены доски в ROOM на сервере нет — только вид (ВР-H11); доказательство
  прерывания S10.

### VS-8. Фигуры (P6)

- **По порядку:** AN-17 → AN-21 (лист CX-24); AN-23 → AN-24 → AN-25 (лист CX-25); AN-31; AN-32 → AN-33, AN-34; AN-35;
  AN-18 — листы 16 клипов.
- **Только UE и скрипты:** все 11 карточек. AN-32…AN-35 — лёгкий режим, live tune.
- **Гейты:** тесты `Unmatched.S08.MoveAnim.*`, `.HeroesV2.*`; `rootDeltaUU` ≤ 0,5 у всех клипов; G-LOOK.
- **Кадры выхода:** листы AN-18 — K1 и K2 обеих досок, цвет и серый (ВР-17); кадры поворота: покой вполоборота,
  разворот к цели, возврат; ни одного кадра спиной к камере (ВР-06).
- **Риски:** поворот и наклон шага складываются; лицо Medusa и перья гарпий меряются под светом AN-36.

### VS-9. Хвосты Sarpedon (P7) и закрытие фазы 3

- **По порядку:** EN-19, EN-20 → EN-23; EN-21, EN-22, EN-24 → EN-25 (одна упаковка, гейты, цена, дополнение к акту P10).
- **Только UE и скрипты:** все 7 карточек.
- **Гейты:** `env_gates.py` G4–G7, критерии P10, `render_bench.py`.
- **Кадры выхода:** Sarpedon K1, K2 свежий `-Bench`; контрольный Marmoreal.
- **Закрытие:** полный раунд GD-058 на обеих досках (ВР-59); сверка реестра 03 с карточками и ассетами UE; список флагов
  отката в AGENTS.md; итог фазы — `docs/game-design/evidence/VISUAL/CLOSEOUT-<дата>.md`.

## 4. Параллельные сессии и конфликты

### 4.1 Что трогают другие сессии

| Область | Кто | Файлы |
|---|---|---|
| поток игры и HUD-прототип | основной чат (прогоны DE, MS-T) | `S08FlowGameMode.cpp` (49 коммитов с 2026-10-03), `S08FlowGameMode.h` (41), `S08FlowGameModeTurnHud.cpp`, `…Opponent.cpp`, `…CardSlot.cpp`, `…Result.cpp`, `…DeckPanel.cpp`, `…HandLimit.cpp`, `S08FlowController.*`, `S08BoardActor.*` |
| логика HUD и выбора хода | основной чат | `S09/*`: `S09MoveSelectionTests.cpp`, `S09ManeuverUi.*`, `S09MoveInput.*`, `S09CombatStage.*`, `S09DeathStage.*`, `S09CardSlot.*`, `S09HudPressTests.cpp` |
| гейты и стенды | основной чат | `tools/s09/run-*.ps1`, `tools/s10/run-*.ps1`, `tools/s08/run-phase2-demo.ps1`, `tools/s08/cue_contract/cue_contract.py` (13 коммитов) |
| звук | аудио-чат (активен: AU-S5 `d490af39`, `c3e6f1d8`, `ada584c9` 2026-10-06) | `S08AudioBank*`, `S08AudioCues.*`, `S08MixLimiter.*`, `S08FlowGameModeAudio.cpp`, `S08FlowGameModeSound.cpp`, а также `S08FlowGameMode.cpp/.h` и `…Opponent.cpp` (AU-S5), `Content/Audio/**`, `tools/audio/**`, `docs/game-design/audio/**`, старый журнал трат |
| окружение и Art Tuner | ENV-MAPS (`C:/tmp/wt-envmaps`) | `Config/ArtBoards/S08ArtBoardProfiles.json`, `EnvLayouts/*.layout.json`, `tools/art/concept_paste/*` |
| чужое незакоммиченное | пользователь и другие сессии | `.claude/settings.local.json`, `docs/art-pipeline/CODEX-2D-PACKAGE-PROMPT.md`, `docs/game-design/evidence/S06/*.json` |

### 4.2 Правила

- Код визуала — в новых файлах `S08/UI/*`, `S08/FX/*`. В общих файлах — только точки подключения, до ~40 строк. При
  конфликте точки подключения уходят в новый `S08FlowGameModeUmHud.cpp` (04 §7.4).
- Шаги короткие: один блок 04 §5.2 или одна группа карточек — одна интеграция. Ветка спринта интегрируется после
  каждого зелёного шага, потом снова вливает свежий `fix/admin-panel`.
- Интеграция — только `tools/git/safe-integrate.sh` (сухой прогон, потом `--apply`). Скрипт сам проверяет: ветка
  содержит свежий `fix/admin-panel`, в основной копии нет git-операции и индекса, входящие файлы не пересекаются с
  чужими правками, процессы UE основной копии не запущены.
- Чужую ветку руками не мержим. Никаких stash, reset, clean. Чужие незакоммиченные файлы не правим.
- Коммиты — `git commit --no-verify`, перечислением путей, без push. В конце сообщения — строка
  `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.
- Профили досок правит и ENV-MAPS: добавляем новые поля, чужие значения не откатываем, конфликт решаем по смыслу.
- `cue_contract.py` и `cue-table.json` — горячие: FX-01 — один короткий коммит, сразу интеграция.
- Документы, задания и пакеты Codex — в основной копии; код, импорт, кадры — в worktree (ВР-PL09).

### 4.3 Процессы UE и GPU

- Одна UE-сессия визуала за раз: один редактор или одна сборка из `C:/tmp/wt-visual`. Сборки — с `-WaitMutex`.
  Редактор с Live Coding в любом чекауте блокирует сборку в других: перед сборкой проверить процессы.
- Замок GPU `C:/tmp/unmatched-gpu.lock`: live tune держит его всю сессию, `bench` и чужие прогоны ждут.
- Упакованный клиент — 60 FPS; два клиента S08 — по 30 FPS (`-ClientFps 30`); `-RenderOffScreen` только прячет окна.
  Цена рендера — `render_bench.py` без лимита FPS, не `gpuMs` с лимитом.
- После каждого прогона — остановить свои процессы: проверить командную строку, родителя, путь к exe. По имени не
  убивать. Редактор пользователя и MCP-службы Codex не закрывать.

## 5. Бюджет и журнал

### 5.1 Лимиты

| Сервис | Лимит | Факт и план |
|---|---|---|
| SYNTX | ≤ 300 токенов до 2026-10-28 (ВР-04); стоп при балансе < 20; потолок одной генерации: картинка 8, видео 10, апскейл 12 (ВР-PR04) | баланс 478 (2026-10-05) → 210,131 (2026-10-06, 07 §2.2) → 173,771 (2026-10-06 05:40). Баланс общий со звуком. План визуала — 24, потолок 54 (ВР-PL10) |
| Tripo | ≤ 3000 кредитов до 2026-10-28 (ВР-04) | 0: ростер после MVP вне объёма (ВР-18) |
| Codex | подписка, учёт по пакетам | 61 пакет, 34 чата, image_gen 26–49 |
| покупки | нет (ВР-04) | — |

### 5.2 По спринтам

| Спринт | Пакеты Codex | image_gen | SYNTX ожидаемо | SYNTX потолок | Tripo |
|---|---|---|---|---|---|
| VS-1 | 7 | 26–37 (IC-36, IC-37, EN-01) | 0 | 0 | 0 |
| VS-2 | 13 | ≤ 12 (EN-02, FX-20, FX-29, FX-31) | 24 (SX-02) | 54: SX-02 24 + повтор 12, SX-01 6, запас FX 12 | 0 |
| VS-3 | 2 | 0 | 0 | 0 | 0 |
| VS-4 | 6 | 0 | 0 | 0 | 0 |
| VS-5 | 16 | 0 | 0 | 0 | 0 |
| VS-6 | 17 | 0 | 0 | 0 | 0 |
| VS-7…VS-9 | 0 | 0 | 0 | 0 | 0 |
| **Итого** | **61** | **26–49** | **24** | **54** | **0** |

Деньги вне подписок — ноль. Пополнение SYNTX для визуала не нужно.

### 5.3 Журнал

- Файл — [credits-ledger.json](credits-ledger.json), схема `unmatched.visual-credits-ledger/1` (07 §4.2). Создан пустым
  2026-10-06.
- Запись — сразу после каждой траты, до следующей:

  ```text
  python tools/art/visual/ledger.py add --task EN-03 --template T-SYNTX-UPSCALE --service SYNTX
    --model "magnific/precision_v2 2x" --quoted 12 --before <get-balance> --after <get-balance>
    --result <путь> --prompt-file docs/game-design/visual/06-tasks/prompts/EN-03.syntx.txt
  ```

- `balance_before` — всегда свежий `get-balance`. Разрыв с `balance_after` прошлой строки — чужая трата (звук), её не
  пишем (07 §4.1).
- Codex — строка на пакет: `units` «пакет, N генераций image_gen», `cost` и балансы `null`. Неудача тоже пишется
  (`status failed`).
- До первой траты модели — строка `providerTerms` (ВР-05): Magnific (EN-03), Google (banana3, запас EN-02), OpenAI
  (gpt-image-2, запас FX).
- `ledger.py check` — в конце каждого спринта: суммы `totals` равны сумме строк, лимиты не превышены.
- Старые журналы визуал не пишет: [s3-baseline](../../art-pipeline/evidence/s3-baseline-2026-09-28/credits-ledger.json)
  (общая история SYNTX и Tripo, звук `AUC-*`) и [ENV-MAPS](../../art-pipeline/evidence/ENV-MAPS/credits-ledger-env.json)
  (Tripo трека окружения).

## 6. Риски

| Риск | Что делаем |
|---|---|
| Параллельные сессии правят `S08FlowGameMode*.cpp` | новые файлы `S08/UI/*`; точки подключения ≤ 40 строк; короткие шаги; при конфликте — `S08FlowGameModeUmHud.cpp`; `safe-integrate.sh` |
| Баланс SYNTX общий и тает (478 → 173,771 за сутки) | цепочка плиты в VS-2; потолок визуала 54; при балансе < 44 перед SX-02 — план Б (ВР-PL10) |
| Codex image_gen не держит hex и толщину штриха | финал всегда рисует скрипт или движок v3; ревью проверяет `palette` (07 §7) |
| Пакет Codex выходит за рамки: правит чужое, рисует макет ImageGen, выдумывает данные | `git status` и `outside_folder` до коммита; пакет отклоняется; новый чат с уточнённым заданием |
| `Content/` в gitignore: ассеты теряются между worktree и основной копией | импорт-скрипт — источник правды; `git add -f` принятых uasset; копия совпадающих путей в `C:/tmp/visual-backup/` (ВР-PL08) |
| ENV-U16 позже приёмки HUD | кадры HB-49 на Marmoreal с `-ConceptPaste` и пометкой; пересъёмка A и C после EN-15 |
| Пиксельные гейты `tools/s09`, `tools/s10` падают без маркеров | HB-01 до HB-02; HB-48 переводит гейты на `SHOT widget` |
| `Build.bat` возвращает 0 при ошибке компиляции | читать хвост лога `build-editor.cjs`; тесты после каждой сборки |
| Ловушка упаковки: новый `Config/**.json` не попадает в pak | `touch` `Unmatched.Build.cs` и сборка игры с `-MaxParallelActions=4` |
| Live Coding блокирует сборку во всех чекаутах | проверка процессов перед сборкой; `-WaitMutex`; `package-client.ps1 -SkipBuild`, если игра уже собрана |
| Дубли карточек (AN-36 и EN-14) | один прогон, строже из двух (ВР-PL04) |
| Нет потребителя значков зон IC-62…IC-69 | новая карточка FX-38 в VS-4 (ВР-PL12); инспектор клетки в 04 не описан — открыто |
| Класс S при 720p 150 % плотный | шаг веера 72 su, название по наведению (04 §7.4) |
| RU-названия карт King Arthur пустые в скрапе | «уточнить: scraped-data/api/heroes/king-arthur.json, админка :5480»; длина RU для его колоды не проверена |
| Сканы и аватары без подтверждённой лицензии (GAP-019) | только внутренняя LAN-сборка; производные вне git (ВР-48) |
| Условия провайдеров SYNTX не проверены | строка `providerTerms` до первой траты модели (ВР-05) |
| Оценки сроков не замерены | пересчёт после CX-01 и после VS-1 (ВР-PL14) |
| Codex в приложении: фокус крадёт TextInputHost | `open_application` прямо перед нажатием; пакеты без генерации — через `codex.exe exec` |
| Узнаваемые элементы DE попадают в арт | кадры DE не входят во входы; листы «рядом с DE» только в `C:/tmp`; ревью 07 §5.5 |

## 7. Готовность к старту

### 7.1 Что есть и чего нет

- Есть: 7 таблиц карточек, 02, 04, 07, решения ВР; приложение Codex (`OpenAI.Codex_26.930.4958.0`); инструменты UE и
  гейты из §1.1; журнал [credits-ledger.json](credits-ledger.json) (пустой); разрешение на UE (2026-10-05, AGENTS.md
  «Known gap»).
- Нет: worktree `C:/tmp/wt-visual`; папки `06-tasks/prompts/` и `evidence/VISUAL/`; `tools/art/visual/*`. Всё это —
  шаг 0 VS-1.
- Проверить перед стартом: реестр [03-asset-registry.csv](03-asset-registry.csv) и документы фазы 2 в git; `git status`
  основной копии (чужое незакоммиченное — §4.1); нет процессов UE основной копии.

### 7.2 Первые три итерации

**И-1. P0: отладка под `-S09Markers` (HB-01 → HB-02).** Полный режим, одна упаковка.
1. Шаг 0 VS-1: `git worktree add -b feat/visual-vs1 C:/tmp/wt-visual fix/admin-panel`, junction `node_modules`, копия
   `Content`.
2. HB-01: функция `S08Markers()` в `S08ArtLook`, поле `markers=` в `ARTLOOK`, по умолчанию «вкл»; явный `-S09Markers`
   во всех `tools/s09/run-*.ps1` и `tools/s10/run-*.ps1`; тест `Unmatched.S08.ArtLook.MarkersFlag`.
3. HB-02: по умолчанию «выкл»; под флаг уходят 13 маркеров `AddMarker`, полоса результата, строки `seq=` и `phase=`,
   эхо команд, AUTO-тосты, заголовок «UNMATCHED S08 grey flow», F10-панель. Правки ≤ 40 строк на файл.
4. Сборка, тесты, одна упаковка; гейты HB-01 с `-S09Markers` — PASS на обеих досках.
5. Кадры: свой ход и бой на Marmoreal и Sarpedon, 1080p и 720p, каждый PNG открыть. Лист
   `docs/game-design/evidence/VISUAL/HB-02/` «до» (прогон I) и «после».
6. `merge fix/admin-panel` → сухой прогон и `--apply` `safe-integrate.sh` → пересборка редактора и
   `sync-staged-build.ps1` в основной копии → статусы HB-01, HB-02 «сделано (<коммит>)» в `hud.csv`.

**И-2. Генератор токенов (HB-03), затем тема (HB-04).** Скрипт, вид не меняется, без упаковки.
1. В `hud-style-tokens.json` — токены 02 §2.2–§2.7, шкала `type.*`, радиусы 4 / 6 / 8 su, алиасы ВР-61; у каждого
   статус «предложено» и источник «02 §N».
2. `tools/s08/hud_contract/hud_tokens_codegen.py` пишет `S08HudTokens.generated.h` (namespace `S08HudTokens`, строка
   `kTokensJsonSha256`).
3. `hud_contract.py validate` падает «header stale», если hex правлен без перегенерации; pytest; тест
   `Unmatched.S08.Hud.Tokens.Header`. Гейт G-TOKENS.
4. Сразу за ним HB-04 (`UUmHudTheme`, `DA_UmHudTheme`) и HB-05 (StringTable RU/EN) — основа для HB-06 в VS-2.

**И-3. Первый пакет Codex: CX-01, макет компоновки GAME (HB-07).** Идёт параллельно с И-1: Codex не трогает `unreal/`.
1. `prompt_build.py HB-07` → `06-tasks/prompts/HB-07.codex.md`; входы с sha256: bench K1 P7 Marmoreal и P10 Sarpedon,
   кадры и трассы прогона I (данные партии), аватары из `scraped-data/images/heroes/`, `reused-cardart.json`; коммит
   задания.
2. Запуск: `codex.exe exec` (пакет без image_gen) или приложение, если exec недоступен. Строка журнала на пакет.
3. Ревью 07 §5: перекрытие 0 px² на обеих досках и 4 холстах; минимальный текст ≥ 10,5 px на 720p; контраст текста
   ≥ 4,5 : 1; каждое число прослеживается до входа (Medusa 14/16, King Arthur 17/18, Merlin 7/7 и другие значения
   карточки HB-07 — из кадров прогона I).
4. Коммит `art/imagegen/hud-composition-v1-codex/`; лист `docs/game-design/evidence/VISUAL/HB-07/` — overlay без сканов,
   цвет и серый.
5. Замер времени чата и ревью → пересчёт оценок §2 (ВР-PL14). Сразу за ним — CX-02…CX-07.

## 8. Решения этого документа (по делегированию)

Все — по делегированию (пользователь 2026-10-06: «Все решения принимай»). Серия `ВР-PL` — локальная серия этого документа
(02 §0.3). До ревью 2026-10-06 она называлась `ВР-05.N`.

| ВР | Решение | Почему |
|---|---|---|
| ВР-PL01 | Вся UE-работа визуала — в одном worktree `C:/tmp/wt-visual`, ветка на спринт `feat/visual-vs<N>` от свежего `fix/admin-panel`; следующая ветка — `git switch -c` в том же worktree после интеграции. Другие worktree в карточках env.csv (`C:/tmp/wt-env-u16`, `C:/tmp/wt-env-p10b`) заменены этим при ревью 2026-10-06 | одна UE-сессия за раз (AGENTS.md «Agent and process lifecycle»); `Content` копируется в worktree один раз; Live Coding блокирует сборки во всех чекаутах |
| ВР-PL02 | Генерация идёт на шаг впереди UE: пакеты Codex и SYNTX запускаются, как только готовы их входы, независимо от P; UE-работа — строго P0…P7. Цепочка плиты EN-01…EN-04 — в VS-1…VS-3. Так же вперёд идут скрипты без UE (EN-05 в VS-1) | Codex не трогает `unreal/` и не мешает UE; баланс SYNTX общий со звуком и упал с 478 до 173,771 за сутки |
| ВР-PL03 | Зависимость сильнее приоритета: карточка ниже P1, нужная P1-карточке, идёт в спринт зависящей (CP-03…CP-06, CP-13…CP-20 для HB-24, HB-25, HB-30, HB-32; FX-01 (P4) для FX-11, FX-12, FX-18) | иначе P1 не собрать; порядок ВР-03 сохраняется для всего, что не блокирует |
| ВР-PL04 | AN-36 и EN-14 — один прогон света героев под нарисованным Marmoreal. Владелец — AN-36 (ВР-AN10). Из EN-14 добавляются контрольная сессия `-NoHeroLight`, замер D6 до смены цвета, H2 через `env_gates.py`. Где пределы расходятся, берётся строже: ключ 5…7 лк (AN-36: не ярче P9b, ≤ 7). Один лист `evidence/VISUAL/AN-36/`; README P9c в ENV-MAPS ссылается на него; обе карточки закрывает один коммит | две карточки на одни и те же параметры `lightProfiles.marmoreal-night.heroLight` дали бы два разных результата |
| ВР-PL05 | Один чат Codex — один пакет. Исключение — экраны одного семейства (BOOT, LOGIN, LOBBY, ROOM, загрузка, INSPECT, PAUSE, RECONNECT, GAMEOVER): серией в одном чате, у каждой карточки своя папка, README, `verification.json` и ревью | у экранов общая библиотека `screen_mockup_base.py` (ВР-SC02); 37 чатов на экраны — лишняя работа без пользы |
| ВР-PL06 | Приложение Codex (Ctrl+N) — для пакетов с image_gen; `codex.exe exec` — для пакетов без генерации и когда приложение недоступно | image_gen в приложении проверен на DE-012, в exec — нет; скриптовым пакетам не нужен computer use |
| ВР-PL07 | Задание собирает `prompt_build.py` в `06-tasks/prompts/<id>.codex.md` (ВР-PR09) и коммитит до запуска; в папку пакета Claude не пишет, `prompts/` пакета заполняет Codex | договор «Codex пишет только в свою папку»; проверка `outside_folder` иначе ломается |
| ВР-PL08 | uasset принятых визуальных ассетов коммитятся `git add -f` по путям задачи, как `Content/S08/UI/IconsV3` и `Content/Audio`; источник правды — импорт-скрипт. Перед `--apply` — сверка входящих путей с игнорируемыми файлами основной копии и копия совпавших в `C:/tmp/visual-backup/<дата>/` | `Content/` в gitignore; git считает игнорируемые файлы расходными и может перезаписать их при слиянии; AGENTS.md требует резервных копий |
| ВР-PL09 | Статусы в `06-tasks/*.csv` и реестре 03 правятся только в основной копии после интеграции шага, отдельным коммитом. Задания и пакеты Codex — тоже в основной копии. Код, импорт, кадры и листы `evidence/VISUAL/` — в ветке спринта | одна точка правки таблиц исключает конфликты слияния; Codex работает в основной копии |
| ВР-PL10 | Потолок визуала в SYNTX — 54 токена без нового решения (ожидаемо 24). Если перед SX-02 баланс < 44 (24 + стоп 20), план Б: ×2 своей плиты локально (Lanczos, без ИИ), пометка «план Б» на листе EN-03, статус «технически импортировано» | лимит ВР-04 (300) недостижим: баланс 173,771 и общий со звуком; плита — наш ассет, не скан (ВР-48 не нарушается) |
| ВР-PL11 | Кадры «до» — из прогона I (`evidence/DE-FOOTAGE/2026-10-05/I/`) и bench P7/P10 ENV-MAPS; отдельной упаковки «до» нет. Разница с HEAD — звук AU-S4 и его субтитры (`4d73ba10`); README листа это называет | кроме звука и субтитров, в клиент после прогона I вошёл только тест кадра (`6627333e`); одна упаковка на изменение |
| ВР-PL12 | В начале VS-4 пишется новая карточка FX-38 «Значок зоны и бейджи L6 у клетки при наведении» (vfx.csv, area board, P2). Инспектор клетки остаётся открытым вопросом: блока в 04 нет | у IC-62…IC-69 в таблицах нет потребителя; ВР-32 требует значок у клетки |
| ВР-PL13 | Инструменты цикла `tools/art/visual/` (`prompt_build.py`, `ledger.py`, `sheet.py`) с pytest — шаг 0 VS-1, лёгкий режим. Трат SYNTX до `ledger.py` нет | ручная сборка заданий и журнала даёт ошибки; 07 §4.3 требует запись под замком |
| ВР-PL14 | Сроки и оценки этого плана — «предложено». После CX-01 и после VS-1 они пересчитываются по факту и записываются в §2 и §0. Итог каждого спринта — `evidence/VISUAL/VS-<N>/README.md`: листы карточек, кадры обеих досок, гейты, траты | оценки без замера (память «оценки по логам»); выход спринта должен быть проверяемым |
