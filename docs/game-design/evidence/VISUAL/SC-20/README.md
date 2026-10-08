# SC-20 — Загрузка партии: не удаётся подключиться

VS-7, шаг S3, 2026-10-08, коммит `323599df`. Карточка — `screens.csv` SC-20; 04 §1.5 (ошибка); макет CX-31
`art/imagegen/sc20-loading-error-codex/` (ВР-VS5-SC20-01…03). Общее — [SC-19](../SC-19/README.md), [SC-14](../SC-14/README.md).

**Статус:** UE-часть готова, живая проверка editor-build, по делегированию. **Откат:** `-S08SlateHud=loading`.

| Пункт | Где и как |
|---|---|
| Состояние | `error` в `UUmScreenLoading` через 10 с от показа экрана без первого снапшота: «Не удаётся подключиться» (`screens.loading.error`), значок `resource-connection-lost` 48 su на месте спиннера (смена формы), карточки героев и доска остаются; ряд кнопок: «В лобби» (`common.btn.lobby`, обычная) и «Повторить» (`common.btn.retry`, единственная главная); панель +72 su. |
| «Повторить» | `FS08FlowController::RetryMatchLoad` — снова `gameSequence` и `gameState`, поток переподключается сразу (без ожидания отката); этап `connect`, 10 с считаются заново. |
| «В лобби» | `DetachToLobby` — комната и поток уходят только у клиента (стадия Lobby), без `leaveGame`: партия остаётся IN_PROGRESS; в LOBBY — «Вернуться в мою партию» (SC-11 / SC-05). |
| Звук | `UI-NET-LOST` на показ ошибки; кнопки — `UI-BTN-CLICK`. |
| Трасса | `LOADING error waited=<мс>`, `LOADING retry pressed`, `LOADING retry game=`, `LOADING lobby pressed`, `LOADING detach to lobby game=… (no leaveGame …)`, `SHOT widget id=UI-SCR-LOADING … state=error … primary=retry`. |

| № | Решение | Почему |
|---|---|---|
| ВР-VS7-37 | Ошибка снимается прокси `tools/s10/delay-graphql-query-proxy.cjs`: `S10_DELAY_FIELD=gameState` держит первый ответ 60 с, `S10_WS_REFUSE=1` отказывает в WS до следующего `gameState` («Повторить») | `drop-graphql-reply-proxy.cjs` рвёт только мутации; без отказа WS снапшот приходит барьером потока (как ВР-VS7-20) |
| ВР-VS7-38 | «В лобби» — локальный выход (`DetachToLobby`), сервер не трогается | карточка: «В лобби» не прерывает партию на сервере |
| ВР-VS7-44 | 10 с считаются от показа LOADING (после 3-2-1 и «Партия начинается…» ROOM) | 04 §1.5 / карточка: «ошибка через 10 с от входа на экран» |

Проверка: `s3d` (VS_AI на Sarpedon, 1080p, прокси) — `LOADING stage=error t=10001`, `UI-NET-LOST`, «Повторить» → `STATE seq=1 -> apply`
→ `board` → `LOADING done` → GAME; `s3e` — `t=10032`, «В лобби» → LOBBY, `SHOT … UI-SCR-LOBBY … recover=1` (партия осталась). Тест
`Loading.Tree`: значок вместо спиннера, одна главная «Повторить», нажатия только в ошибке. Открыты: error `s3d` (до ВР-VS7-32 — под
экраном меню Marmoreal), error `s3e` (непрозрачная вуаль), вырезки.

Кадры: портреты — PNG в `scraped-data/derived/visual-evidence/SC-20/`, в git — `stage-row-error-1080p-100.jpg`,
`buttons-error-1080p-100.jpg` и индекс. Не сделано: набор G packaged, листы, реестр 03 — шаг «Кадры».
