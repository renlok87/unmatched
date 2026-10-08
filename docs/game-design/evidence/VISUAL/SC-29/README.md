# SC-29 — Настройки: подсказки правил и клавиш (вкладка «Интерфейс»)

VS-7, шаг S4, 2026-10-08, коммит `28ec24d2`. Карточка — `screens.csv` SC-29; 04 §2.11, §2.14, ВР-39, ВР-H09, ВР-HB07; макет CX-32
`art/imagegen/sc29-settings-hints-codex/` (ВР-VS5-SC29-01, -02). Общее — [SC-24](../SC-24/README.md).

**Статус:** UE-часть готова, живая проверка editor-build, по делегированию. Набор G packaged и листы — шаг «Кадры».
**Откат:** `-S08SlateHud=pause` (консоль `s08.Settings ruleHints= keyHints=`, флаги `-S08RuleHints` / `-S08KeyHints`).

| Пункт | Где и как |
|---|---|
| Строки | «Подсказки правил» — флажок `bRuleHints`; «Подсказки клавиш» — чипы «АВТО» / «ВКЛ» / «ВЫКЛ» (`KeyHintsMode` auto / on / off; поле и счётчик `CompletedMatches` — HB-43) и подпись `settings.interface.key_hints.note` «Авто — только в первой партии» (новый ключ). |
| Образец | справа ячейка «КОНЕЦ ХОДА» как в HUD (HB-42 / HB-43, `UUmButton` Disc: значок `action-end-turn` 48 su, подпись `type.tag`, чип «E» 20×20 в правом верхнем углу; класс S — ячейка 48×48, диск 40, без подписи) на `panel.inset`; не кнопка модали и не главная; чип виден, пока подсказки клавиш показываются (`KeyHintsShown`). Клавиша — только чипом, не в тексте статуса. |
| Применение | `ApplySetting keyHints|ruleHints` + `Save`; HUD читает режим каждый кадр (`UmKeyHintsNow`): «Выкл» убирает чипы с кнопок HUD в следующем кадре, «Авто» на профиле с `CompletedMatches` > 0 — чипов нет (правило HB-43, тест `Hud.Actions.KeyHints`). |

Проверка: тесты `Pause.Model` / `Pause.Tree` — «Авто» выбрано, подпись, образец с чипом; `Hud.Actions.KeyHints` (HB-43) — в широком
наборе 240 из 240. Вживую `s4b` / `s4f`: `SETTINGS set keyHints=off` → в том же кадре `HUD-KEYHINTS mode=off shown=0`; обратно «Авто» →
`mode=auto shown=1` (HUD показал чипы после закрытия паузы, через 3 с). Открыты: game-interface (`s4f`), game-interface-ui150 (`s4g`).

Кадры: полные — `scraped-data/derived/visual-evidence/SC-29/`; в git `interface-ru-1080p-100.jpg`.
Не сделано: профиль с завершённой партией вживую не снимался; псевдолокаль оборачивает букву на чипе клавиши (см. SC-26); набор G
packaged, листы, реестр 03 — шаг «Кадры».
