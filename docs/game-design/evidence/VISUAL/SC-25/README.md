# SC-25 — Настройки: звук (вкладка «Звук» `UUmScreenPause`)

VS-7, шаг S4, 2026-10-08, коммит `28ec24d2`. Карточка — `screens.csv` SC-25; 04 §1.8 (таблица настроек); макет CX-32
`art/imagegen/sc25-settings-sound-codex/` (ВР-VS5-SC25-01, -02). Общие сборки, тесты, гейты и решения — [SC-24](../SC-24/README.md).

**Статус:** UE-часть готова, живая проверка editor-build, по делегированию. Набор G packaged и листы — шаг «Кадры».
**Откат:** `-S08SlateHud=pause` (консоль `s08.Settings` работает как раньше).

| Пункт | Где и как |
|---|---|
| Строки | `UUmSettingRow`: «Общая громкость» + «Без звука» (`master`, `masterMute`), «Музыка» (`music`), «Эффекты» (`sfx`), «Интерфейс» (`ui`), «Голоса» (`vo`), «Окружение» + «Без звука» (`ambience`, `ambienceMute`), «Субтитры» (`subtitles`), «Описывать звуки» (`describeSounds`) — порядок и шины `S08UserSettings.h`, новых шин нет. |
| Ползунок | дорожка `slider.track` 200 su, заливка `card.cream`, ручка `slider.thumb` 16 su, шаг 5 %, «{n} %» (`settings.value.percent`) справа; `UI-SLIDER-TICK` на каждые 10 % (08 hooks); значение уходит на отпускании. |
| Флажок | `check.off` / `check.on` + глиф IC-57 `ui-check` 24 su и слово «вкл» / «выкл»; `UI-TOGGLE`. |
| Применение | `ApplySetting` + `Save` → `OnChanged` → `ApplyAudioSettings` (звуковая сторона): громкость шины меняется в кадр отпускания. Сохранение — `GameUserSettings.ini` `[/Script/Unmatched.S08UserSettings]`. |
| Трасса | `SETTINGS set master=50 source=pause` → `SETTINGS changed … master=50 …` в том же кадре; следующий звук UI играет с `gain=0.40` (0,5 × 0,8) — `s4b` / `s4f`; mute → `gain=0.00`. |

Проверка: тест `Pause.Tree` — значения по умолчанию 100 / 60 / 80 / 80 / 80 / 60, mute выкл, субтитры вкл, описание выкл; перетаскивание
100 → 50 даёт одну фиксацию `master=50` и пять тиков; mute и флажок фиксируют `masterMute=1`, `subtitles=0`. Вживую (`s4b`, `s4f`)
— громкость 50 % и mute применились сразу (трасса `SFX … gain=`), значения вернулись к 100 %; файл сохранения worktree после прогонов
— значения по умолчанию. 720p 150 % (`s4g`): ряды прокручиваются, видны только целые ряды, «Без звука» в слоте 60 su на две строки
(как в макете), кнопки низа видны. Открыты: game-sound 1080p (`s4f`), game-sound(-scrolled)-ui150 (`s4g`), sound в псевдолокали (`s4d`).

Кадры: полные — `scraped-data/derived/visual-evidence/SC-25/` (индекс `visual-evidence-index.json`), в git `sound-720p-150-scroll.jpg`.
Не сделано: перезапуск клиента с изменёнными громкостями не снимался отдельным прогоном (сохранение — тот же `SaveConfig`, что у
консоли DE-025); набор G packaged, листы, реестр 03 — шаг «Кадры».
