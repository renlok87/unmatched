# HB-46 — плашка бойца только по наведению и «ЦЕЛЬ»: `UUmWorldPlate` (шаг H12)

VS-4, шаг V3 (H12 + FX-38), 2026-10-07, ветка `feat/visual-vs4` (worktree `C:/tmp/wt-visual`), код — `1ece7893`, значки зон — `20e9ac5b`.
Карточка — `hud.csv` HB-46; 04 §2.15 (дельта VS-4); ВР-07; принятый макет HB-44 (`art/imagegen/hud-world-v1-codex/`,
ВР-VS2-HB44-03). Тот же коммит — [HB-45](../HB-45/README.md), [FX-38](../FX-38/README.md).

**Статус:** плашка H12 готова, тест и лист галереи — по делегированию. Кадры наведения и выбора цели из партии (набор A
«выбрана атака», `SHOT plate … overlapReachable=0`) — шаг «Кадры». **Откат:** `-S08SlateHud=plate` — прежняя плашка
172×54 su (имя, HP-полоса, «ВАШ / СОПЕРНИК»).

## Что сделано (`do`)

| Пункт | Где и как |
|---|---|
| 1. Показ | только наведение или выделение (как и прежде в `UpdatePlate`, плашки «по умолчанию» на настоящих досках нет); V2 — проявление 150 мс (`hover.ms`), уход 120 мс (`icon.leave.ms`), reduced motion ≤ 100 мс (`US08ArtPlateWidget::SetShownAnimated`, `S08ArtHudViews.cpp`); повторный вызов показа каждый кадр не перезапускает идущее проявление. |
| 2. Тема и данные | `UUmWorldPlate` 268×144 su: `panel.bg` r m, кромка `panel.edge`; имя `type.heading` (из `Config/Cards/S08FighterNames.json`, гарпии — «Гарпия {n}»), роль `type.tag` `text.secondary` из данных героя (`bIsHero`, `FS09CommandUi::IsRangedAttacker`), строка «HP · чип команды · ВАШ / СОПЕРНИК». |
| 3. Место | без изменений — размещение W5b-R (над фигурой, иначе снизу; `PLATE overlapReachable=0`), размер V2 берётся из стиля. |
| 4. «ЦЕЛЬ» | чип `state.pending` с текстом `card.glyph` у цели боя (`TargetId`) и у цели локального черновика атаки (`CommandUi.AttackTargetId`); флаг входит в ключ содержимого плашки. |
| 5. Строки | `hud.plate.role.hero_ranged|hero_melee|sidekick_ranged|sidekick_melee`, `hud.plate.side.own|opponent`, `hud.plate.target`, `hud.plate.harpy_name` в `st-hud.csv` (RU / EN); `ST_Hud`, `Game.locres` en / ru, `Game.po` пересобраны (`hud_strings_build.py build`). |
| 6. Тест | `Unmatched.S08.ArtHudUmg.PlateHoverOnly` — имя и роль из данных (RU), сторона, чип «ЦЕЛЬ», проявление 150 / уход 120 мс и сворачивание, reduced motion, повторный показ не перезапускает проявление, откат. |

Хуки в `S08FlowGameMode.cpp` — 4 строки (`SetupPlate`, флаг цели и ключ, `FillPlateTexts`).

## Решения по делегированию (шаг V3)

| № | Решение | Почему |
|---|---|---|
| ВР-VS4-46 | Ключи строк — предложенные макетом HB-44 (`role.hero_ranged` …, `side.own|opponent`, `target`, `harpy_name`), не `role.hero` + `.range` / `.melee` карточки | роль — одна строка «ГЕРОЙ · ДАЛЬНИЙ»: переводу нужен цельный шаблон, не склейка |
| ВР-VS4-47 | Имя на языке UI — файл данных `Config/Cards/S08FighterNames.json` (Медуза, Король Артур, Мерлин; гарпии — `hud.plate.harpy_name` с номером `sidekicks[]`); героя без записи — подпись сервера | имена — данные контента (05-content-matrix), не строки HUD; `RuntimeDependencies` в `Unmatched.Build.cs` |
| ВР-VS4-48 | «ЦЕЛЬ» — у цели боя и у цели черновика атаки | в режиме атаки цель выбирается до отправки; после — бой |

## Лист

Галерея `-S08IconGalleryWorld=<board>` (инструмент ревью, не матч и не кадр приёмки; `S08/UI/UmWorldGallery.h`): настоящие
`US08ArtTagWidget` / `US08ArtPlateWidget` в виде H12 и `UUmZoneBadges` поверх кадра bench K1 доски как картинки
(Marmoreal original — нарисованный задник `-ConceptPaste`, Sarpedon original — lit3d; шесть фигур v2 — фон HB-44).
Панели стоят в боксах принятого макета HB-44 (`art/imagegen/hud-world-v1-codex/layout-measurements.json`): берётся
холст макета, ближайший по размеру панели к ширине окна (1920×1080 100 % или 1280×720 150 %), бокс масштабируется с
окном, панель — по центру бокса (ВР-VS4-58). Состояния по секунде: 0 tags-start, 1 tags-run-I (HP прогона I), 2–5
наведение на Медузу / Гарпию 1 / Короля Артура / Мерлина, 6 attack-medusa («ЦЕЛЬ»), 7–9 клетка с 1 / 2 / 3 зонами
(Marmoreal M02 / M01 / M04, Sarpedon S01 / S21 / S25; полигоны клеток — `art/imagegen/hud-composition-v1-codex/masks.json`).
8 холстов: обе доски × 1080p / 720p × 100 % / 150 %; откаты — 1080p 100 % обеих досок.

- Вне git (кадр доски на каждом листе, ВР-VS4-01): `scraped-data/derived/visual-evidence/HB-46/` —
  [`visual-evidence-index.json`](visual-evidence-index.json) (путь, sha256, размер, что видно).
- Трассы галереи — `C:/tmp/visual/vs4-v3/gallery/w3-*` (локально): `check-trace` PASS на 8 + 4 трассах (71 / 22 / 29
  строк `SHOT widget`).

Что видно (Read: `plates-colour|grey|deut.png` — состояния 2–6 на 8 холстах): «Медуза / ГЕРОЙ · ДАЛЬНИЙ / 14/16 ● ВАШ»,
«Гарпия 1 / ПОМОЩНИК · БЛИЖНИЙ», «Король Артур / ГЕРОЙ · БЛИЖНИЙ / 17/18 ⬢ СОПЕРНИК», «Мерлин / ПОМОЩНИК · ДАЛЬНИЙ»,
у атакуемой Медузы — чип «ЦЕЛЬ»; всё по-русски, без «уточнить» и без смешения RU/EN; на 720p 100 % роль 14 su = 10,5 px
читается; в сером и при дейтеранопии чип «ЦЕЛЬ» светлее подложки, чипы команд различаются формой. Откат
(`rollback-btp-colour.png`, вырезка в 2×) — прежняя плашка «Harpies 1 / 1/1». Доска — Marmoreal с нарисованным
задником / Sarpedon lit3d, шесть фигур v2.

## Проверки

- Как в [HB-45](../HB-45/README.md#проверки); `PlateHoverOnly` PASS.

## Что не сделано в этом шаге

- `SHOT plate … overlapReachable=0` на кадрах наведения и выбора цели из партии обеих досок — шаг «Кадры» (галерея
  ставит плашку в бокс макета, а не размещением клиента).
- Бюджет ≤ 0,02 мс GT p95 — шаг «Кадры».

## Кадры выхода VS-4 (HB-49, упаковка `5a74a81e`, 2026-10-07)

Живые партии приёмочной упаковки, Marmoreal original (`-ConceptPaste` до EN-13, пометка) и Sarpedon original, шесть фигур v2, слоя отладки нет; прогоны, гейты и листы — [HB-49](../HB-49/README.md) (картинки со сканами и доской — вне git, `scraped-data/derived/visual-evidence/HB-49/`, ВР-VS4-01).

Плашка по наведению / выбору («Король Артур · ГЕРОЙ · БЛИЖНИЙ · 18/18 · СОПЕРНИК», «Медуза · ГЕРОЙ · ДАЛЬНИЙ · ВАШ») — как в макете. **Вердикт: не принято** — на кадрах появления и скрытия плашки рисуется пустая панель без текста (`pend-marm-720-150 s09-pending-MOVE`, `pv-sarp-720-100 s09-exit-banner-combat`; 960 строк `SHOT widget id=plate* bbox=(0,0,0,0) geom=unpainted visible=1` в 59 трассах). Правка — не показывать панель, пока плашка не встала и текст не разложен.

## Ревью VS-4 (2026-10-07)

**Вердикт ревью: принято, по делегированию, после правки `55902976` (ВР-VS4-92).** Причина пустой панели —
`US08ArtPlateWidget::ApplyStyle`: его зовёт `NativePreConstruct` уже после `SetV2`, и он возвращал хост-рамке
`PlateBackground` тело `#161A28`, а затухает только сама плашка H12. Теперь с V2 рамка прозрачна (`SetV2(false)` сбрасывает
`bV2` до `ApplyStyle`); `PlateHoverOnly` проверяет рамку после построения и тело отката. Упаковка `55902976`
(`pend-marm-720-150`, `pv-sarp-720-100`): кадров с исчезающей плашкой 3, тёмной панели нет ни на одном (до правки — 3 из 3);
устойчивая плашка рисует свою панель. Замечание: плашка `placement=left` у края экрана уходит под слот-источник
(VS-4 README «Открыто» п. 5).
