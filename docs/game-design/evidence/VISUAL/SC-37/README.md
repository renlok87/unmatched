# SC-37 — GAMEOVER: «Сыграть ещё» против ИИ

VS-7, шаг S5, 2026-10-08, ветка `feat/visual-vs7`. Карточка — `screens.csv` SC-37; 04 §1.10; F-06, DE-027; макет CX-34
`art/imagegen/sc37-gameover-again-codex/` (ВР-VS5-SC37-01…06). Экран, сборки, тесты, гейты — [SC-34](../SC-34/README.md).

**Статус:** UE-часть готова, живая проверка editor-build: две партии VS_AI сыграны до конца и перезапущены кнопкой (`s5a`
Marmoreal 1080p, `s5h` Sarpedon 720p). Packaged-кадры — шаг «Кадры». **Откат:** `-S08SlateHud=gameover`.

## Что сделано (`do`)

- `AgainButton` «СЫГРАТЬ ЕЩЁ» (обычная) — только при `Room.Mode == VS_AI` (в 1×1 кнопки нет, DE-039); «В ЛОББИ» остаётся
  единственной главной; в классе S модаль VS_AI 760×560 (ВР-VS5-SC37-06).
- Цепочка (`UmGameOver::NextAgainStep`, игровой режим `S08FlowGameModeUmEnd.cpp`): `leaveGame` → в LOBBY `createGame(VS_AI, тот
  же boardId)` → в новой комнате `selectHero(тот же герой)` → `toggleReady` → `startGame` → новая партия; шаг ждёт не дольше 10 с;
  ошибка потока или таймаут — тост `why.command.rejected`, экран остаётся (повторное «Сыграть ещё» продолжает с лобби тем же
  героем и доской, «В лобби» закрывает экран). Пока цепочка идёт, маршрут не показывает LOBBY / ROOM (`UmEndHoldsRoute`), затем —
  LOADING (SC-19) новой партии.
- again.busy: обычное тело, спиннер `loader-spinner` + «СОЗДАЁМ ПАРТИЮ…» (`screens.result.again.busy`, новый ключ); ширина —
  по большей из двух подписей; остальные кнопки как были, их нажатия ждут.
- Звук «Сыграть ещё» — `UI-CONFIRM`. Трасса: `RESULT again mode=VS_AI step=<leave|create|select|ready|start|done|failed> …`,
  `SHOT widget id=UI-SCR-GAMEOVER state=again … mode=vs_ai`.

## Решения по делегированию

| № | Решение | Почему |
|---|---|---|
| ВР-VS7-64 | Ожидание «Сыграть ещё» — не общий busy-скин кнопки («Отправлено…»), а своя подпись со спиннером; остальные кнопки не гаснут | ВР-VS5-SC37-04: «остальные кнопки не меняются»; в `s5a` вышло «Отправлено…» и серая «В лобби» |

## Проверка

- `GameOver.Tree`: VS_AI — «Сыграть ещё» видна, одна главная, нажатие; busy — `state=again`, подпись «Создаём партию…», второе
  нажатие не проходит; 1×1 — кнопки нет. `.GameOver.Model`: leave → create → select → ready → start → done; ошибка или
  таймаут → failed.
- `s5a`: `RESULT again mode=VS_AI step=leave board=c121b47f8d6eb28daccb76d05 hero=1 sent=1` → … → `step=done game=cmuzon4x…`,
  `HUD-SCREEN route=loading` (ROOM не показывался), затем бой новой партии; строка новой партии по API: `mode VS_AI`,
  `boardId c121b47f8d6eb28daccb76d05` (тот же Marmoreal). `s5h` (Sarpedon): `board=c7fa64a26c29a0835f2383e63` → `done`.
- Открыты (Read): again (`s5a`, до правки подписи), again-busy (`s5h`): «СОЗДАЁМ ПАРТИЮ…» со спиннером, «В ЛОББИ» главная.

## Кадры

Полные кадры — `scraped-data/derived/visual-evidence/SC-37/` (портреты); в git — ряд кнопок
`gameover-again-busy-buttons-720p-100.jpg`.

## Не сделано в этом шаге

- again.error (тост) вживую не снимался — настоящей ошибки нет; проверен моделью.
- На стенде S10 (`tools/s10/run-vs-ai-demo.ps1`) кнопку не жали — прогон шёл на основном бэкенде; packaged — шаг «Кадры».
