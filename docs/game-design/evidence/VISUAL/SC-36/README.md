# SC-36 — GAMEOVER: «Посмотреть доску»

VS-7, шаг S5, 2026-10-08, ветка `feat/visual-vs7`. Карточка — `screens.csv` SC-36; 04 §1.10; макет CX-34
`art/imagegen/sc36-gameover-board-codex/` (ВР-VS5-SC36-01…03). Экран, сборки, тесты, гейты — [SC-34](../SC-34/README.md).

**Статус:** UE-часть готова, живая проверка editor-build (`s5a`) и бенчи (`s5f`, `s5g`); packaged-кадры — шаг «Кадры».
**Откат:** `-S08SlateHud=gameover`. Закрывает пункт 8 остатка VS-6: полоса `-BenchResult=board` теперь RU-полоса UMG.

## Что сделано (`do`)

- Состояние `board` в `UUmScreenGameOver`: модаль и вуаль уходят кроссфейдом 250 мс (`FS09ResultView`), внизу по центру
  `BoardStrip` 520×56 su (`panel` 0,92, нижний край на безопасном поле 24 / 16 su): «ХОД 19 · ПОБЕДА» (`screens.result.board.turn`
  в верхнем регистре, новый ключ), «К ИТОГАМ» + V (обычная, 40 su), «В ЛОББИ» + Enter (главная, 40 su), через 8 su; если не
  помещаются — сначала уходят чипы. V / Esc — к итогам, Enter / L — в лобби (`HandleResultKeys`, без изменений); обратный вход
  в итоги — без анимации появления. На доске экран пропускает клики к сцене, берут только кнопки полосы.
- Звук: «Посмотреть доску» / «К итогам» — `UI-PANEL-CLOSE` (08-screen-audio-hooks).
- Трасса: `SHOT widget id=UI-SCR-GAMEOVER state=board bbox=<полоса> modal=0 … overlapField=<px²>` и
  `HUD-LAYOUT class=L canvas=… field=(…) overlapField=0 block=gameover.strip rect=(…)`.

## Проверка

- `GameOver.Tree`: «ХОД 11 · ПОБЕДА», полоса видна, модаль скрыта, одна главная, полоса × FIELD (410,255)–(1440,850) = 0 px²,
  `SHOT … state=board`.
- Живой `s5a` 1080p Marmoreal: `RESULT view mode=board … fade=250`, `HUD-LAYOUT … overlapField=0 field=1`; бенч `s5f` 1080p
  Marmoreal и `s5g` 720p Sarpedon: `overlapField=0`, `check-trace` PASS (`s5g`). Кадры открыты (Read): доска, финальный HUD
  (портреты, «вне игры», сердце павшего), полоса внизу.

## Кадры

Полные кадры — `scraped-data/derived/visual-evidence/SC-36/` (HUD с портретами); в git — полосы
`gameover-board-strip-1080p-100.jpg`, `gameover-board-strip-720p-100.jpg`.

## Не сделано в этом шаге

- Набор F packaged, листы, G-READ / G-GRAY / G-LOOK, реестр 03 — шаг «Кадры».
