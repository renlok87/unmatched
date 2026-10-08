# SC-33 — RECONNECT: восстановление и выход из оверлея

VS-7, шаг S5, 2026-10-08, ветка `feat/visual-vs7`. Карточка — `screens.csv` SC-33; 04 §1.9 (выход), §2.12; макет CX-33
`art/imagegen/sc33-reconnect-restore-codex/` (ВР-VS5-SC33-01…04). Общее — [SC-31](../SC-31/README.md).

**Статус:** UE-часть готова, живая проверка editor-build (`s5c`); packaged-кадры, листы и G-CUE на packaged — шаг «Кадры».
**Откат:** `-S08SlateHud=reconnect`.

## Что сделано (`do`)

| Пункт | Где и как |
|---|---|
| restoring | транспорт вернулся (`IsStreamAcked`, новая строка-аксессор в `S08FlowController.h`), состояние ещё не сверено — или идёт GD-037 дольше 300 мс: в слоте значка `loader-spinner` 32 su (HB-47), заголовок «Загрузка состояния…» (`screens.reconnect.restoring`, новый ключ), кнопок нет (ВР-VS5-SC33-01). |
| Выход | связь вернулась (край `FS08NetWatch` → recovered, тот же, что CUE-018): карточка и вуаль гаснут за 200 мс (reduced — 100 мс) через `SetAlphaDirect`; насыщенность за 300 мс внутри CUE-018 (FX-36 VS-6), чип CONN → online (HB-14) и тост «Позиции обновлены (пропущено {n})» (`hud.toast.reconnected`, HB-40, n = разница seq) — их собственные, оверлей их не вызывает. |
| Трасса | `SHOT widget id=UI-SCR-RECONNECT state=restoring … card=146`, `RECONNECT exit ms=200 from=<state> missed=<n>`; рядом — `CUE sound id=CUE-018`, `FX desat off … ms=300`, `TOAST hud=hud.toast.reconnected missed=0 seqBefore=1 seq=1`. |

## Проверка

- `Unmatched.S08.Hud.Screens.Reconnect.Tree`: restoring — спиннер вместо значка, «Загрузка состояния…», кнопок нет, 146 su;
  `.Reconnect.Model`: `ExitAlpha` 1 → 0,5 → 0 за 200 мс, reduced — 100 мс; GD-037 — restoring только с 300 мс.
- Живой `s5c`: «Переподключить» → `RECONNECT state=restoring` → `CUE-018` → `RECONNECT exit ms=200` → тост `missed=0`
  (seq до и после — 1, число из трассы). Кадры restoring и через 300 мс после выхода открыты (Read): карточки нет, сцена снова
  в цвете, чип online, тост сверху по центру (цепочка 04 §2.12 HB-40).

## Кадры

Полные кадры — `scraped-data/derived/visual-evidence/SC-33/` (HUD со сканами карт); в git — `reconnect-restoring-card-720p-100.jpg`
и `reconnect-exit-toast-720p-100.jpg` (только тост).

## Не сделано в этом шаге

- G-CUE (CUE-018 800 мс) на packaged-прогоне, набор F, листы, реестр 03 — шаг «Кадры» (сбои G-CUE на прогонах со снимками —
  известный ВР-VS6-51, не трогаются).
- Кадр ровно на 200 мс выхода не снимался (снимок через 300 мс после выхода).
