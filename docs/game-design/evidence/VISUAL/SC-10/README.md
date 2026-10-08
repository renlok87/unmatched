# SC-10 — LOBBY: создать партию «Против ИИ» (`UUmScreenLobby`)

VS-7, шаг S2, 2026-10-08, ветка `feat/visual-vs7`. Карточка — `screens.csv` SC-10; 04 §1.3, §1.4; принятый макет CX-29
`art/imagegen/sc10-lobby-create-ai-codex/` (ВР-VS4-SC10-01). Общее — [SC-08](../SC-08/README.md), колонка — [SC-09](../SC-09/README.md).

**Статус:** UE-часть готова, живая проверка editor-build, по делегированию. **Откат:** `-S08SlateHud=lobby`.

## Что сделано (`do`)

| Пункт | Где и как |
|---|---|
| Режим | `ModeChipAi` «Против ИИ» выбран → `CreateNote` «Соперник — ИИ: AI Bot» (`screens.lobby.create.ai.note`, `{name}` = username `backend/prisma/seed-ai.ts:24`, `type.body` `text.secondary`) между строкой режима и «Доска» (в классе S доска сдвигается на 12 su); героя бота экран не показывает. |
| Создание | тот же путь `CreateRoom(VS_AI, BoardId)`; трасса `LOBBY create mode=VS_AI board=<id>`; блок «Войти по коду» остаётся доступным. |
| Строки | `screens.lobby.create.ai.note` (новая, EN «Opponent — AI: {name}»). |

## Проверка

- `Lobby.Tree`: заметки нет в 1×1, в режиме ИИ — «Соперник — ИИ: AI Bot»; один create `VS_AI` на Sarpedon.
- Живой `s2d2` (1080p): `LOBBY create mode=VS_AI board=c7fa64a26c29a0835f2383e63` → `createGame` → ROOM (`UI-ROOM-CREATE`);
  `game(id)`: `VS_AI`, Sarpedon, игрок — хост. Открыты (Read): create-ai, busy.

## Кадры

`scraped-data/derived/visual-evidence/SC-10/` (миниатюры карт): create-ai, busy-ai 1080p — `visual-evidence-index.json`.

## Не сделано в этом шаге

- `tools/s10/run-vs-ai-demo.ps1 -ScreenShots` до ROOM со слотом AI Bot: слот бота показывает ROOM (SC-17, следующий шаг);
  сервер добавляет бота на `startGame`. Прогон демо — шаг «Кадры».
- Набор G packaged, листы, статус в реестре 03 — шаг «Кадры».
