# SC-09 — LOBBY: создать комнату 1×1 с выбором доски (`UUmScreenLobby`, `UUmBoardChip`)

VS-7, шаг S2, 2026-10-08, ветка `feat/visual-vs7`. Карточка — `screens.csv` SC-09; 04 §1.3, §3.1; принятый макет CX-29
`art/imagegen/sc09-lobby-create-codex/` (ВР-VS4-SC09-01…03). Сборки, тесты, гейты, общие решения — [SC-08](../SC-08/README.md).

**Статус:** UE-часть готова, живая проверка editor-build, по делегированию. Набор G packaged и листы — шаг «Кадры».
**Откат:** `-S08SlateHud=lobby`.

## Что сделано (`do`)

| Пункт | Где и как |
|---|---|
| Колонка «Создать» | `CreateTitle` «Создать игру», `ModeLabel` «Режим» + `ModeChip1v1` «1×1» (выбран) / `ModeChipAi` (32 su, выбран — `state.pending`), `BoardLabel` «Доска», `BoardChips` — 2 × `UUmBoardChip`, `CreateButton` «Создать» — главная (кроме шести знаков кода, ВР-VS4-SC11-02). |
| Плитки досок | только Marmoreal original `c121b47f8d6eb28daccb76d05` (по умолчанию) и Sarpedon original `c7fa64a26c29a0835f2383e63`; имя — из `boardList` (запасное — имя AGENTS.md), под миниатюрой, всегда видно; миниатюра — иллюстрация карты целиком, пропорции сохранены (`UUmBoardChip`, `S08/UI/UmBoardChip.h/.cpp`). Выбранная — `Btn_Selected`, имя `card.glyph`. |
| Миниатюры | `/Game/S08/UI/Boards/T_BoardThumb_marmoreal` / `_sarpedon` — `scraped-data/images/maps/*.png` (sha256 c28ce0d7… / 4c5941fa…) LANCZOS до 600 px, UI без mip, только LAN, вне git (ВР-VS7-21); `tools/s08/screens/ue_import_board_thumbs.py --prepare` + UE-прогон. Нет текстуры — только имя и строка `BOARDTHUMB missing=` в логе. |
| Создание | `FS08FlowController::CreateRoom(Mode, BoardId)` — доска выбранной плитки в `createGame(input{mode, boardId}, idempotencyKey)` (хук 5 строк в `S08FlowController.cpp`; флаги `-S08BoardId` / `-ArtPreviewBoardId` — как раньше, когда доски нет); трасса `LOBBY create mode=ONE_V_ONE board=<id>` и `CREATE boardId=<id> source=lobby`. |
| busy | «Создаём…» в отключённой главной с `why.syncing`, спиннер 32 su после 300 мс; повторное нажатие ничего не шлёт (один ключ на намерение); чипы и плитки держат вид выбора, нажатия на них ждут (ВР-VS7-22); курсор «занято». Нет ответа 12 с — busy снимается. |
| Ошибка | ответ с ошибкой → `CreateError` «Сервер недоступен» (над кнопкой в классе L, вместо заметки в классе S). |
| Звук | `UI-TOGGLE` (чипы, плитки), `UI-BTN-CLICK` («Создать»); `UI-ROOM-CREATE` звучит сам. |
| Строки | `screens.lobby.create.mode` «Режим», `screens.lobby.create.busy` «Создаём…» (новые); `create.title`, `.mode.1v1`, `.board`, `.submit` были. |

## Решения по делегированию

| № | Решение | Почему |
|---|---|---|
| ВР-VS7-21 | Миниатюра — иллюстрация карты, ужатая до 600 px, без mip, вне git | без mip исходник 1337 px мерцает в плитке 296–468 px; иллюстрация — сторонний арт (ВР-48) |
| ВР-VS7-22 | Во время busy чипы режима и плитки остаются в виде выбора (не disabled); их нажатия игнорируются до ответа | ВР-VS4-SC09-01: «chips and tiles keep their state»; disabled-скин стирал выбор (кадр `s2d`) |

## Проверка

- `Lobby.Tree`: Marmoreal по умолчанию, ровно две плитки, выбор Sarpedon, двойное нажатие «Создать» → один `OnCreate`, busy
  «Создаём…» с `why.syncing`, плитка во время busy сохраняет выбор, ошибка снимает busy. `Lobby.Poll`: пропорции миниатюры.
- Живой `s2d2` (1080p): Sarpedon + «Против ИИ» → `createGame` задержан прокси 3 с → кадр busy → ROOM; `game(id)` на сервере:
  `mode VS_AI, boardId c7fa64a26c29a0835f2383e63`. `s2g` (1080p): 1×1 на Marmoreal по умолчанию → `game(id)`: `ONE_V_ONE`,
  `c121b47f8d6eb28daccb76d05`. `s2a`: кадры create-sarpedon, create-marmoreal.
- Открыты (Read): create-ai / busy 1080p (`s2d` — дефект выбора, `s2d2` — исправлено), create-sarpedon 1080p, list 720p 150 %.

## Кадры

Только в `scraped-data/derived/visual-evidence/SC-09/` (миниатюры карт = board art): create-marmoreal, create-sarpedon,
busy 1080p — `visual-evidence-index.json`.

## Не сделано в этом шаге

- Двойной клик живьём не прогонялся (экран блокирует второе нажатие — тест).
- Набор G packaged, листы, статус в реестре 03 — шаг «Кадры».
