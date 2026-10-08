# SC-31 — RECONNECT: автопереподключение (`UUmReconnectOverlay`)

VS-7, шаг S5, 2026-10-08, ветка `feat/visual-vs7` (worktree `C:/tmp/wt-visual`). Карточка — `screens.csv` SC-31; 04 §1.9
(H14); принятый макет CX-33 `art/imagegen/sc31-reconnect-auto-codex/` (ВР-VS5-SC31-01…06). Состояния того же оверлея —
[SC-32](../SC-32/README.md) (manual, expired) и [SC-33](../SC-33/README.md) (restoring, выход); здесь — общее для трёх карточек.

**Статус:** UE-часть готова, живая проверка одним клиентом editor-build на основном бэкенде `:3000`, по делегированию. Набор F
packaged с `RENDER`, листы цвет / серый / дейтеранопия, G-READ / G-GRAY / G-LOOK, бюджет и статус в реестре 03 — шаг «Кадры».
**Откат:** `-S08SlateHud=reconnect` — оверлея нет, связь показывает только чип CONN (HB-14), как до шага.

## Что сделано (`do`)

| Пункт | Где и как |
|---|---|
| Оверлей | `UUmReconnectOverlay : UUmModalBase` (`S08/UI/UmReconnectOverlay.h/.cpp`), WBP `/Game/S08/UI/Screens/WBP_UI_SCR_RECONNECT`, в слоте `Reconnect` корня — над всеми модалями, вместе со своим `UUmConfirmDialog`. BindWidget `Icon`, `Title`, `Attempt`, `Missed`, `Running`, `Retry`, `Leave` (+ `ToLogin`, `Spinner`). |
| Карточка | ВР-VS5-SC31-02: 520 su по центру, скин `modal`, отступ 24, одна колонка; высота по содержимому (auto 330, manual 302, expired 218, restoring 146 su); Running переносится только между предложениями; вуаль `card.navy` 0,8. |
| auto | «Соединение потеряно», «Переподключение… попытка {n} из 5» (n = 1 + время потери / 10 с), «Пропущено событий: {n}», Running, «ВЫЙТИ В ЛОББИ» — обычная, главной нет (ВР-VS5-SC31-04); значок `resource-connection-reconnecting` 48 su с анимацией `cycle` (reduced — статично). |
| Вход | край `FS08NetWatch::bLost` — тот же, что у чипа CONN (HB-14) и десатурации CUE-017 (VS-6); насыщенность −30 %, звук `UI-NET-LOST` и чип — их, оверлей их не вызывает. |
| Ввод | вуаль и карточка берут клики, Esc глотается (`UmEndOwnsInput` рядом с PAUSE / INSPECT): ни клик, ни клавиша не доходят до поля. |
| Выход в лобби | «Выйти в лобби» → `UUmConfirmDialog` «Выйти в лобби» / «Партия останется на сервере.» → `DetachToLobby` (без `leaveGame`, ВР-VS7-56). |
| Трасса | `SHOT widget id=UI-SCR-RECONNECT impl=umg state=<auto|manual|restoring|expired> … attempt= missed= primary=<retry|login|none> card=<su>` (раз на смену состояния и чисел), `RECONNECT state=… attempt=… missed=… lost=<ms>`, `RECONNECT exit ms=200 …`, `RECONNECT leave asked|confirmed|cancelled`, `RECONNECT retry (manual)`. |
| Строки | `screens.reconnect.leave.confirm` (новый, ВР-VS7-56); остальные `screens.reconnect.*` уже были (ST_Screens, locres EN / RU, псевдолокаль — `UmText`). |
| Инструменты | `-S08EndDrive=<план>` (manual, retry, live, aborted, lobby, inlobby, result, board, results, again, newmatch, wait<мс>, shot-<имя>, exit); `tools/s10/delay-graphql-query-proxy.cjs` + `S10_WS_DOWN_MS` — после сброса `S10_WS_DROP_AT_MS` WS отвергается заданное время (связь лежит дольше 50 с). |

## Решения по делегированию (шаг S5)

| № | Решение | Почему |
|---|---|---|
| ВР-VS7-56 | «Выйти в лобби» — `DetachToLobby` (партия остаётся IN_PROGRESS) через подтверждение «Партия останется на сервере.» (новый ключ `screens.reconnect.leave.confirm`) | 04 §1.9: «Партия продолжается на сервере»; `leaveGame` прервал бы партию для обоих, а без связи и вовсе не дойдёт; так же, как «В лобби» SC-20 |
| ВР-VS7-57 | Счёт попыток — часы оверлея (1 + время потери / 10 с, до 5; manual с 50 с); лестница переподключения транспорта (1-2-4-8-15 с) не меняется; «Переподключить» = новый цикл + `RetryMatchLoad` | 04 §1.9 задаёт «по 10 с» как счёт для игрока; менять GD-028 ради текста нельзя |
| ВР-VS7-58 | restoring — транспорт снова `acked`, состояние ещё не сверено, или идёт GD-037 (потерянный ответ команды) дольше 300 мс; без десатурации (CUE-017 VS-6 её не зажигает) | 04 §3.3: ожидание видно после 300 мс; не повторять CUE-017 |
| ВР-VS7-59 | «Пропущено событий» во время обрыва — seq, применённые с момента потери (что известно сейчас); число тоста после возврата — HB-40 | честный счёт; число не выдумывается |
| ВР-VS7-61 | Оверлей не показывается над GAMEOVER и ABORTED (партия кончилась — говорит её экран) | 04 §1.9 «GAMEOVER, если партия кончилась без нас»; в s5b restoring закрыл ABORTED |
| ВР-VS7-69 | Инструменты обзора: `-S08EndDrive`, `S10_WS_DOWN_MS`; при `-S08EndDrive` хвост результата `-S09Flow` ждёт | один клиент UE, без ручного ввода |
| ВР-VS7-70 | База экранов: `UUmScreenBase::SetAlphaDirect` — прозрачность ведёт владелец (кроссфейд GAMEOVER по `FS09ResultView`, выход RECONNECT 200 мс) | один источник времени с трассой `RESULT view` |

## Проверка

- Сборки: UnmatchedEditor `build-editor-1…8` (1 — C2027 / C2039 / C4458 и TObjectPtr неполного типа в тестах, исправлено;
  остальные Succeeded, логи прочитаны), игровая цель `build-game-1` Succeeded.
- WBP: `ue_author_um_hud.py` (`UM_HUD_WBP_OVERWRITE=0`) — RECONNECT / GAMEOVER / ABORTED created, 34 exists-unchanged,
  `UM_HUD_WBP_PASS assets=37`. Строки: `hud_strings_build.py build` PASS (ST_Screens 148, locres EN / RU).
- Тесты: новые `Unmatched.S08.Hud.Screens.Reconnect.Tree`, `.Reconnect.Model` (+ GameOver, Aborted) — PASS, обе передачи
  (код и WBP); `Unmatched.S08.Hud.Screens` + `S09.ResultScreen` 28 из 28; широкий набор (`S08.Hud`, `S09.ResultScreen`, `S10`,
  `S09.HudPress`, `S08.Leave*`) 193: одна ошибка `Hud.Actions.KeyHints` — от счётчика `CompletedMatches=1`, который оставил
  живой прогон s5a в `Saved` worktree; счётчик возвращён в 0, тест PASS.
- Гейты: `hud_contract.py check-trace` PASS на `s5c` (380 строк `SHOT widget`), `s5d`, `s5e`, `s5g`; `validate` PASS;
  `hud_tokens_codegen.py --check` FRESH; `pytest tools/s08/hud_contract` 75 из 75; `hud_strings_build.py check` PASS.
- Живой прогон `s5c` 720p (1×1, гость King Arthur на Sarpedon original, хост `room_actor.cjs`; прокси сбросил WS через 15 с
  и держал его 52 с): `RECONNECT state=auto attempt=1…5` каждые 10 с, `manual` на 50 с, «Переподключить» → `restoring` →
  CUE-018 и `RECONNECT exit ms=200` → тост «Позиции обновлены (пропущено 0)» → хост вышел → ABORTED. `s5b` — тот же прогон до
  правок (не было значка: `SetReducedMotion` сбрасывал позу; restoring закрывал ABORTED; не писались строки `SHOT`).
- Открыты (Read): auto, manual, restoring, exit-toast (`s5b`, `s5c`).

## Кадры

Под вуалью — HUD партии со сканами карт руки и портретами: полные кадры только в
`scraped-data/derived/visual-evidence/SC-31…SC-33/` (индексы `visual-evidence-index.json`); в git — JPEG непрозрачной
карточки `reconnect-auto-card-720p-100.jpg`.

## Не сделано в этом шаге

- Набор F packaged (`-S08ScreenShots`, Marmoreal и Sarpedon original, 1080p / 720p 100 %), листы, G-READ / G-GRAY / G-LOOK,
  G-TOKENS / G-WIDGET на packaged, бюджет ≤ 0,5 мс GT / 0,3 мс GPU, статус в реестре 03 — шаг «Кадры».
- Обрыв в ROOM: оверлей работает только в партии (`Started`); в ROOM связь показывают свои экраны (SC-19 / SC-20).
- Прогон через `tools/s10/drop-graphql-reply-proxy.cjs` (потерянный ответ мутации, GD-037) вживую не снимался; restoring для
  него проверен тестом `Reconnect.Model`.
- Десатурация CUE-017 (VS-6, `FS08NetWatch`) загорается и на ABORTED (сервер закрывает поток прерванной партии) — сцена под
  модалью ABORTED серее; это сторона VS-6, не менялась (открытый пункт).
