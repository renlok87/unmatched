# SC-04 — BOOT: сервер недоступен (состояние `error` в `UUmScreenBoot`)

VS-7, шаг S1, 2026-10-08, ветка `feat/visual-vs7`. Карточка — `screens.csv` SC-04; 04 §1.1, §3.1, §3.3; принятый макет CX-27
`art/imagegen/sc04-boot-error-codex/` (ВР-VS4-SC03-05, ВР-VS4-SC04-01…03). Экран, сборки, тесты и гейты — [SC-03](../SC-03/README.md).

**Статус:** UE-состояние готово, живая проверка editor-build, по делегированию. Набор G packaged и листы — шаг «Кадры».
**Откат:** `-S08SlateHud=boot`.

## Что сделано

- Баннер 480×104 su (скин `capsule`) 16 su под капсулой этапа: `resource-connection-lost` 48 su (`US08AnimatedIconWidget`, его X —
  единственный красный), «Сервер недоступен» (`screens.boot.error.server`, `type.body`, `text.primary`), «Повторить» 168×48 —
  единственная главная (`common.btn.retry`); retrying — та же кнопка в disabled-скине с причиной `why.syncing`, строка
  «Синхронизация…» 6 su под ней по правому краю; подпись этапа остаётся.
- Ошибка: отказ ответа этапа (`heroList` — счётчик отказов в потоке; `boardList`, `myGames` — их состояние) или 10 с без ответа
  (`UmBoot::TimedOut`). «Повторить» перезапускает текущий этап; поздний первый ответ тоже закрывает ошибку.
- Звук: `PlayScreenSound(UI-NET-LOST)` при показе ошибки, `UI-BTN-CLICK` на «Повторить».
- Трасса: `BOOT error stage=heroes waited=10001`, `BOOT retry stage=heroes`, `SHOT … state=error … retrying=0|1`.
- Ключ `screens.boot.stage.heroes.wait` «Загрузка героев…» (ВР-VS4-SC03-05) — подпись этапа героев до ответа (1/3).

## Проверка

- Тесты `Unmatched.S08.Hud.Screens.Boot.Tree` (баннер, одна главная, retrying: disabled + `why.syncing`, «Повторить» один раз и
  не во время повтора) и `.Boot.Timer` (9,999 с — ждём, 10 с — ошибка) — PASS.
- Живой прогон `a2`: прокси `delay-graphql-query-proxy.cjs` держит первый ответ `heroList` 13 с → через 10 с баннер, драйвер жмёт
  «Повторить» → retrying → второй `heroList` отвечает → «84/84» → доски → лобби.
- Открыты (Read): ожидание героев, ошибка, retrying 1080p (`a1`, `a2`).

## Кадры в git (editor-build, не приёмка)

`boot-loading-heroes-wait-1080p-100.jpg`, `boot-error-1080p-100.jpg`, `boot-retrying-1080p-100.jpg`.

## Не сделано в этом шаге

- Ошибка при остановленном бэкенде стенда (вместо задержки ответа) и кадры набора G packaged — шаг «Кадры».
