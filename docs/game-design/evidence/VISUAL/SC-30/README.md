# SC-30 — Настройки: качество графики (вкладка «Графика»)

VS-7, шаг S4, 2026-10-08, коммит `28ec24d2`. Карточка — `screens.csv` SC-30; 04 §1.8, ВР-H10, AGENTS.md «Unreal GPU load»,
`docs/art-pipeline/render-reference.json`; макет CX-32 `art/imagegen/sc30-settings-graphics-codex/` (ВР-VS5-SC30-01). Общее —
[SC-24](../SC-24/README.md).

**Статус:** UE-часть готова, живая проверка editor-build, по делегированию. Набор G packaged и листы — шаг «Кадры».
**Откат:** `-S08SlateHud=pause` (`-S08RenderPreset` по-прежнему задаёт пресет на запуск).

| Пункт | Где и как |
|---|---|
| Строка | «Качество графики» — чипы «ВЫСОКОЕ» (по умолчанию, `sg.*` 2, эталон приёмки) / «СРЕДНЕЕ» (1) / «НИЗКОЕ» (0) и подпись `settings.graphics.note` «Масштаб экрана 100 % и лимит 60 кадров/с не меняются» (новый ключ, `type.caption`). Выбранный чип — по текущим `sg.*` (разные группы — ни один). |
| Применение | `UGameUserSettings::SetOverallScalabilityLevel(2|1|0)`, `ResolutionQuality` = 100, `Scalability::SetQualityLevels`, `SaveSettings` (ВР-VS7-50: без `ApplySettings`, который заново выставляет лимит кадров и разрешение); `r.ScreenPercentage` 100, `FrameRateLimit` 60 и dynamic resolution не трогаются. |
| Трасса | `SETTINGS set graphics=<n> source=pause` и строка `RENDER tag=SETTINGS …`. |

Проверка: тест `Pause.Model` — значения 2 / 1 / 0, «Высокое» выбрано, подпись; `Pause.Tree` — щелчок «Низкое» фиксирует `graphics=0`.
Вживую `s4b` / `s4f` (Marmoreal original, GAME): «Низкое» → `RENDER tag=SETTINGS … sg.view=0 … screenPct=100.0 … reference=0`,
«Высокое» → `sg.view=2 … preset=High screenPct=100.0 … reference=1`. Сохранение worktree после прогонов — «Высокое». Открыты:
game-graphics, -gfx0 (`s4f`), game-graphics-ui150 (`s4g`), lobby-graphics-en (`s4e`).

Кадры: полные — `scraped-data/derived/visual-evidence/SC-30/`; в git `graphics-high-1080p-100.jpg`, `graphics-low-1080p-100.jpg`.
Не сделано: набор G packaged, листы, реестр 03 — шаг «Кадры»; кадры приёмки других задач по-прежнему только «Высокое» с `RENDER`.
