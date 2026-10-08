# SC-28 — Настройки: скорость анимации и сокращённые анимации (вкладка «Игра»)

VS-7, шаг S4, 2026-10-08, коммит `28ec24d2`. Карточка — `screens.csv` SC-28; 02 §11.2, 04 §1.8, ВР-SC06, DE-025; макет CX-32
`art/imagegen/sc28-settings-game-codex/` (ВР-VS5-SC28-01). Общее — [SC-24](../SC-24/README.md).

**Статус:** UE-часть готова, живая проверка editor-build, по делегированию. Набор H (начало хода и бой при reduced motion и
скорости «Нет», Marmoreal 1080p 100 % packaged) — шаг «Кадры».
**Откат:** `-S08SlateHud=pause` (консоль `s08.Settings speed= reduced=` и флаги `-S08AnimSpeed` / `-S08ReducedMotion`).

| Пункт | Где и как |
|---|---|
| Строки | «Скорость анимации» — чипы «НЕТ» / «БЫСТРО» / «ОБЫЧНО» / «МЕДЛЕННО» (`AnimSpeed` none / fast / normal / slow; выбранный — `btn.selected` с текстом `card.glyph`); «Сокращённые анимации» — флажок `bReducedMotion`. Строки «Тряска» нет: `bScreenShake` остаётся в сохранении (ВР-SC06). |
| Применение | `ApplySetting speed|reduced` + `Save` → `OnChanged` → `RefreshMotionSettings` (`MS-ANIM settings changed … combatSpeed=…`): следующий шаг и следующая постановка боя идут с новой скоростью, без перезапуска; удержания чтения боя множитель не сокращает (логика диспетчера не менялась). |
| Трасса | `SETTINGS set speed=<none|fast|normal|slow> source=pause`, `SETTINGS set reduced=<0|1> source=pause`. |

Проверка: тест `Pause.Model` — 2 ряда, 4 чипа, «Обычно» выбрано, сокращённые выкл, ряда `shake` нет; `Pause.Tree` — чип «Обычно» в
`btn.selected`, щелчок «Нет» фиксирует `speed=none`. Вживую вкладка открыта и снята в `s4b` / `s4f` (1080p), `s4g` (720p 150 %), `s4d`
(псевдолокаль: чипы на второй строке). Открыты: game-game (`s4f`), game-game-ui150 (`s4g`), lobby-game-pseudo-ui150 (`s4d`).

Кадры: полные — `scraped-data/derived/visual-evidence/SC-28/`; в git `game-tab-1080p-100.jpg`.
Не сделано: смена скорости / reduced motion из паузы вживую не прогонялась (путь `OnChanged` тот же, что у консоли DE-025 и теста
`S08.MoveAnim` «applied without a restart», в широком наборе PASS); набор H и набор G packaged, листы, реестр 03 — шаг «Кадры».
