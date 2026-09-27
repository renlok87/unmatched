# Доска задач

Локальная канбан-доска по документам `docs/game-design/`. Pure Node (stdlib,
без npm-зависимостей), UI без сборки. Сканирует источники, мержит статусы,
даёт API + SSE и живой rescan при правке документов.

## Запуск

```bash
node tools/board/server.mjs               # http://127.0.0.1:8787
node tools/board/server.mjs --port 0      # эфемерный порт (печатает BOARD_READY <port>)
node tools/board/server.mjs --overrides path/to/overrides.json
```

При старте сервер печатает в stdout `BOARD_READY <port>` — по этой строке
готовность ловит selftest и внешние скрипты.

Файл переопределений (`tools/board/overrides.json` по умолчанию) создаётся
первым же PATCH — руками его заранее заводить не нужно.

## Selftest

```bash
node tools/board/selftest.mjs   # из корня проекта; выход 0/1, печатает SELFTEST OK
```

Поднимает сервер на эфемерном порте с overrides во временном каталоге
(реальный `tools/board/overrides.json` не затрагивается), проверяет: `GET /`
(200, `charset=utf-8`, `<title`), `GET /api/tasks` (непустой массив, у каждой
задачи `id/status/type`, есть GD-задача), `GET /api/events` (`text/event-stream`,
именованное событие `init` ≤ 5 с), `PATCH` planned-задачи в `in_progress`
(200 + статус в повторном `GET` + `event: tasks` в SSE), затем гасит сервер и
удаляет временный каталог. Общий таймаут — 30 с.

## API

| Метод | Путь             | Что делает                                                                                         |
| ----- | ---------------- | -------------------------------------------------------------------------------------------------- |
| GET   | `/api/tasks`     | JSON-массив задач; актуальный rev — в заголовке `X-Board-Rev`                                      |
| PATCH | `/api/tasks/:id` | `{status, note?}` → пишет overrides.json, поднимает rev, шлёт SSE `tasks`                          |
| GET   | `/api/events`    | SSE: `init` (полный снапшот + rev) при коннекте, `tasks` на каждое изменение, `: ping` каждые 15 с |

## Статусы и колонки

`planned` / `in_progress` / `blocked` / `done`. **Blocked — полноценная
колонка**, а не маппинг в planned: `06-asset-manifest.csv` содержит 28 записей
с `verificationStatus=blocked`.

## Правила слияния (по убыванию приоритета)

1. **`overrides.json` побеждает всегда.** Ручное решение новее машинного.
   При записи фиксируется `baseStatus` — статус скана на момент решения;
   если скан после этого изменился, задача получает флаг `diverged`
   (расхождение не прячется).
2. **CSV `14-sprint-backlog.csv` — базовый статус** GD/ART-задач
   (`sprint` → milestone, `owner` → тип: DEV→feature, ART→art).
3. **Evidence — доказательный слой, статус не перебивает.** Задача из CSV со
   статусом `done` без доказательства получает флаг `no-evidence` (статус не
   меняется). Доказательство: для S01–S07 и A01 — запись с `status: done` в
   `evidence/<S>/tasks.json` / `server-tasks.json` (три формы: плоская карта,
   объект `tasks`, массив `tasks` с `DONE`→`done`; нестандартные id вроде
   `GD-017b` и `GD-017/020-adapters` молча пропускаются); для S08–S10 —
   упоминание id в `evidence/<S>/README.md`.

Задача из `06-asset-manifest.csv` берёт статус из `verificationStatus` 1:1
(`statusSource: manifest`); `TASK`/`Q`/`RISK`/`ACC`/`QA`/`D`/`INT`/`GAP`/`CUE`
сканируются из markdown-источников (`statusSource: scan`). Статусы у
scan-источников: `Q` — `done`, если закрыта (сводная таблица в начале 11 или
маркер `[ЗАКРЫТ …]` в строке), иначе `planned`; остальные — `planned`.

### Формат overrides.json

```json
{
  "GD-040": {
    "status": "done",
    "note": "проверено вручную 2026-09-27",
    "updatedAt": "2026-09-27T12:00:00.000Z",
    "baseStatus": "planned"
  }
}
```

`status`/`note`/`updatedAt` — по плану; `baseStatus` — служебное поле для
детекции `diverged` (не обязательно при ручной правке). Задача, существующая
только в overrides, попадает на доску с пометкой «только в overrides» —
override здесь единственный канал статуса.

## Источники и паттерны

| Файл                                 | Тип                         | Паттерн                                                                                                                                                                                               |
| ------------------------------------ | --------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `14-sprint-backlog.csv`              | GD (feature), ART (art)     | CSV: `id,sprint,title,owner,…,status,…`; BOM, кавычки, CRLF                                                                                                                                           |
| `06-asset-manifest.csv`              | asset                       | id = `assetKey` целиком (ASSET-_, UI-_, M-*); `verificationStatus` → статус 1:1                                                                                                                       |
| `07-animation-vfx-audio.csv`         | cue                         | `cueId`, title = `event` (18)                                                                                                                                                                         |
| `09-vertical-slice-and-backlog.md`   | task                        | `^### TASK-\d+ / ` и `^- \*\*TASK-\d{3} / `; title после « / »; milestone = секция «Этап N»                                                                                                           |
| `10-acceptance-tests.md`             | test                        | `^#{2,3} QA-\d{3}\. ` (23)                                                                                                                                                                            |
| `11-open-questions-and-risks.md`     | question / risk             | Q: `^\*\*Q-\d+` (жирные строки; групповые `### Q-0xx` игнорируются); закрытость — сводная таблица в начале файла (`Закрыт`/`Факт установлен`) или `[ЗАКРЫТ …]` в строке. RISK: `^\| RISK-\d{3} \|`    |
| `15-rules-and-release-acceptance.md` | acceptance                  | `^## ACC-\d{3} — ` (22)                                                                                                                                                                               |
| `00-vision-and-scope.md` §8          | decision                    | строки таблицы `\| D-\d+ \|` (13)                                                                                                                                                                     |
| `08-integration-decisions.md`        | task (GAP) / decision (INT) | GAP: `^\| GAP-\d{3}` из обеих таблиц; `GAP-008/017` разворачивается в два id; дубль — «Поправки S01» перебивают §5 (первое вхождение выигрывает, 08:5). INT: `^#{2,3} … INT-\d{3}` из заголовков (19) |

CRLF-файлы: все строки обрезаются от `\r` до матчинга. `TODO.md` источником
не является.

## Живое обновление

Три watcher'а на каталогах (не файлах): `docs/game-design` (recursive),
`tools/board` (recursive) и каталог `--overrides`, если он вне первых двух —
фильтрация по базовому имени файла. События дебаунсятся 300 мс, затем rescan;
если снапшот изменился — rev растёт и всем SSE-клиентам уходит `event: tasks`.
Если recursive-режим недоступен (ENOSYS/ERR_FEATURE_UNAVAILABLE) —
нерекурсивные watcher'ы на каждом подкаталоге; последний рубеж — поллинг
mtime+size каждые 5 с.

Клиент: `fetch('/api/tasks')` при старте, `EventSource('/api/events')`;
перерисовка только при смене rev. EventSource переподключается сам;
`onerror` зажигает индикатор «офлайн», `onopen` — повторный fetch.
DnD-перенос → PATCH → SSE `tasks` → рендер: своя вкладка обновляется тем же
путём, что и остальные.

## Ограничения

- Слушается только `127.0.0.1` — доска строго локальная.
- SSE-событие `tasks` несёт полный снапшот (~300 задач, 80–120 КБ) — локально
  дёшево, для публичного хостинга так делать не стоит.
- Override для несуществующего id создаёт карточку-заглушку с типом `task`.
- `no-evidence` вычисляется по статусу источника до применения override:
  флаг означает «источник заявил done без доказательства» и сохраняется даже
  после ручного переопределения.
