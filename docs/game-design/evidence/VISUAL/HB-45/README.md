# HB-45 — тег бойца H12: `UUmWorldTag` (шаг H12)

VS-4, шаг V3 (H12 + FX-38), 2026-10-07, ветка `feat/visual-vs4` (worktree `C:/tmp/wt-visual`), код — `1ece7893`, значки зон — `20e9ac5b`.
Карточка — `hud.csv` HB-45; 04 §2.15 (дельта VS-4), §5.2 H12; 02 §6.5; ВР-07, ВР-61, ВР-63, ВР-72, ВР-78; принятый макет
HB-44 (`art/imagegen/hud-world-v1-codex/`). Тот же коммит — [HB-46](../HB-46/README.md), [FX-38](../FX-38/README.md).

**Статус:** тег H12 готов, тест и лист галереи — по делегированию. Кадр K1 packaged `-Bench` обеих досок (набор A) —
шаг «Кадры». **Откат:** `-S08SlateHud=tag` — прежний тег 12/11 su на `#161A28` с подписью «H1»; `-ArtHudImpl=slate` не
менялся.

## Что сделано (`do`)

| Пункт | Где и как |
|---|---|
| 1. Тема | `UUmWorldTag` (`S08/UI/UmWorldLayer.h/.cpp`) — содержимое `US08ArtTagWidget` (`SetV2`, подмена содержимого `TagBackground`): капсула `card.navy` r 8 с кромкой `panel.edge`, «{hp}/{max}» `type.tag` 14 `text.primary`, полоса 40×4 `hp.fill` / `hp.back`; цвета и кегли — только из `UUmHudTheme`. |
| 1. Чип команды | `team-chip-p1` / `-p2` 24 su (`UmTeamChip::Load`, IC-44, IC-45); откат значков `-S08IconLegacy` — как у чипа. |
| 2. Гарпии | диск 16 su `card.navy` с кремовым ободком и цифрой 1–3 `type.tag` `card.cream` слева от HP-полосы; номер — `S08HeroesV2::HarpyNumber` (порядок `sidekicks[]`, тот же, что цифра Z-1 на подставке); букв «H» нет. |
| 3. Имя | в теге имени нет (ВР-07). |
| 4. Место | без изменений — размещение W5b-R под подставкой (см. «Что не сделано»: сдвиг от шва HD-07). |
| 5. Откат | `UmWorldLayer::TagV2()` = нет ключа `tag` в `-S08SlateHud`; `SetupTag` в `BuildArtHudWidgets` (`S08FlowGameMode.cpp`, одна строка), `FillTagTexts` в `UpdateBoardLabels` (одна строка). |
| 7. SHOT | строки `SHOT widget id=tag …` — прежний формат (части `CollectParts` V2: HP, чип, цифра). |
| 8. Тест | `Unmatched.S08.ArtHudUmg.TagTokens` — нет имени, `type.tag` 14, капсула `card.navy`, чип 24, полоса 40×4, цифры 1–3 у гарпий, откат. |

## Решения по делегированию (шаг V3)

| № | Решение | Почему |
|---|---|---|
| ВР-VS4-47 | Номер гарпии — `S08HeroesV2::HarpyNumber` (порядок `sidekicks[]` снапшота), тот же, что на подставке (Z-1) | один источник цифры для подставки, тега и плашки |
| ВР-VS4-58 | Лист `-S08IconGalleryWorld` ставит панели в боксы макета HB-44 ближайшего холста макета, по центру бокса | на 1080p 150 % и 720p 100 % макета нет; центр бокса сохраняет привязку к фигуре |

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

- Вне git (кадр доски на каждом листе, ВР-VS4-01): `scraped-data/derived/visual-evidence/HB-45/` —
  [`visual-evidence-index.json`](visual-evidence-index.json) (путь, sha256, размер, что видно).
- Трассы галереи — `C:/tmp/visual/vs4-v3/gallery/w3-*` (локально): `check-trace` PASS на 8 + 4 трассах (71 / 22 / 29
  строк `SHOT widget`).

Что видно (Read: `tags-colour|grey|deut.png` — шесть тегов прогона I на 8 холстах, контакты Marmoreal 720p 100 % и
Sarpedon 1080p 100 %, откат `rollback-btp-colour.png`): капсулы navy с чипом-кругом (свои) и чипом-шестигранником
(соперник), у гарпий — диски ①②③, полоса и «14/16», «17/18», «7/7»; на 720p 100 % цифры и HP читаются (кегль 14 su =
10,5 px, диск 16 su = 12 px); в сером чипы различаются формой, полоса светлая на тёмном; дейтеранопия — то же. Откат —
прежние маленькие теги. Доска — Marmoreal с нарисованным задником / Sarpedon lit3d, шесть фигур v2 (кадр bench K1).

## Проверки

- Сборки UnmatchedEditor (build-17) и игровой цели (build-game-2, `Unmatched.Build.cs` тронут) — Succeeded.
- Тесты UE: `Unmatched.S08.ArtHudUmg.*` 12 из 12 (с TagTokens, PlateHoverOnly), полный прогон `Unmatched.S08+S09+S10`
  498 из 498 (build-18).
- pytest `tools/s08/hud_contract` 69 из 69; `hud_contract.py validate` PASS; `hud_strings_build.py check` PASS;
  `hud_tokens_codegen.py --check` FRESH; `check-trace` 12 трасс галереи PASS.

## Что не сделано в этом шаге

- Сдвиг тега от шва клеток (HD-07, `do` п. 4): размещение тега прежнее (W5b-R) — отдельная правка раскладки мирового
  слоя; на листе теги стоят в боксах макета, а не в боксах клиента.
- Бюджет ≤ 0,05 мс GT p95 на 6 тегов и кадр K1 packaged `-Bench` обеих досок (набор A, G-WIDGET) — шаг «Кадры».
- Декаль цифры на подставке (ВР-72) — не здесь (правка героев, P6).

## Кадры выхода VS-4 (HB-49, упаковка `5a74a81e`, 2026-10-07)

Живые партии приёмочной упаковки, Marmoreal original (`-ConceptPaste` до EN-13, пометка) и Sarpedon original, шесть фигур v2, слоя отладки нет; прогоны, гейты и листы — [HB-49](../HB-49/README.md) (картинки со сканами и доской — вне git, `scraped-data/derived/visual-evidence/HB-49/`, ВР-VS4-01).

Теги фигур с цифрами гарпий 1–3 и чипами команды (круг / шестигранник) на обеих досках и всех холстах; в дейтеранопии команды различимы формой. **Вердикт: художественно принято, по делегированию (2026-10-07).**
