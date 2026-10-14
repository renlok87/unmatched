# ASSET-BEOWULF-001 — лист приёмки

Лист собран `tools/art/visual/sheet.py` 2026-10-14 по 02-visual-design.md §13.2. Поля ниже заполняет Claude после
ревью (один проход, 07 §5).

**Решение:** художественно принято, по делегированию (ВР-17; делегирование пользователя 2026-10-06 «Все решения принимай»)
**Дата решения:** 2026-10-14
**Ревью:** Claude, один проход, арт и рамки задачи вместе (02 §13.3)
**Флаг отката:** `-S08HeroesLegacy` (серый Body: блок-аута ART-003 у нового персонажа нет; трасса `ARTLOOK … heroes=v2`)

## Состав листа (02 §13.2)

| № | Пункт | Файлы | Есть |
|---|---|---|---|
| 1 | Мастер и рабочие размеры (значки 1024 и 24/32/48 ×4 nearest; скины ×1, ×2; карты — показы §6.2) | — | — |
| 2 | Цвет, серый Rec.709, дейтеранопия — для каждого размера | `sheet-01-bench-K1-1920x1080.jpg`, `sheet-02-bench-K2x1p6-1920x1080.jpg`, `sheet-03-bench-K2x2p5-1920x1080.jpg`, `sheet-04-bench-K1-1920x1080.jpg`, `sheet-05-bench-K2x1p6-1920x1080.jpg`, `sheet-06-bench-K2x2p5-1920x1080.jpg` (JPEG 1200 q92; PNG — `C:/tmp/ASSET-BEOWULF-001-stage7/game-sheet/`, ДС-8) | да |
| 3 | Кадр на обеих настоящих досках: Marmoreal original и Sarpedon original, K1 и K2, packaged `-Bench` с отпечатком `RENDER`; для HUD ещё 1280×720 и 150 % | `../bench-marmoreal/`, `../bench-sarpedon/` (K1, K2×1,6, K2×2,5; RENDER код 0 × 6) | да |
| 4 | Контекст: на `panel.bg`, на `card.cream`, на поле | — | — (входы непрозрачные) |
| 5 | Движение: лист кадров по времени, обычный / reduced | лист клипов AN-18 (`docs/game-design/evidence/VISUAL/AN-145…AN-148/`) | да (обычный) |
| 6 | Трассы: `ARTLOOK`, `SHOT widget` (HUD), `CUE fx` (VFX), `concept-paste` (окружение) | `../bench-*/bench.trace.txt` (`ARTLOOK heroes=v2`, `backdrop=paste/lit3d(default)`, `clips=4/4`) | да |
| 7 | README: что проверено, замеры, что не прошло, флаг отката | этот файл + `../README.md` | да |

## Входы

| файл | размер | sha256 |
|---|---|---|
| `C:/tmp/ASSET-BEOWULF-001-stage7/bench-marmoreal/bench-K1-1920x1080.png` | 1920×1080 | 478acb8fbd2cb8db8d0f6a360aae751d094ebd64ede0062966adde66a8c03d2c |
| `C:/tmp/ASSET-BEOWULF-001-stage7/bench-marmoreal/bench-K2x1p6-1920x1080.png` | 1920×1080 | a2414ae2546ea5d7a1d8c60185855fa90455fc8d119fdc229cae6b53e4b2cf24 |
| `C:/tmp/ASSET-BEOWULF-001-stage7/bench-marmoreal/bench-K2x2p5-1920x1080.png` | 1920×1080 | c694977d277be609f72bbdb61116151ac776d1fb9961df604702a1420ab59378 |
| `C:/tmp/ASSET-BEOWULF-001-stage7/bench-sarpedon/bench-K1-1920x1080.png` | 1920×1080 | e7ae9b71ed885886ab0910b9af125d20a3572caef0be7d1b13e3405d46ad25b5 |
| `C:/tmp/ASSET-BEOWULF-001-stage7/bench-sarpedon/bench-K2x1p6-1920x1080.png` | 1920×1080 | dc502b865d2e5768d995ded689d66cd75c18cf63452a9cf1dc750a5c52e0cfd1 |
| `C:/tmp/ASSET-BEOWULF-001-stage7/bench-sarpedon/bench-K2x2p5-1920x1080.png` | 1920×1080 | a6c1639738e1a44330a5a88d563017346079d4bd779171e6674ac0dcb78a46ce |

## Замеры

- Контраст (текст ≥ 4,5 : 1, значки и кромки ≥ 3 : 1): —
- ΔE76 к токенам 02 §2: —
- ΔGPU (02 §9.4, `render_bench.py`): один замер без базы для разности — K1 GPU 2,16 мс, K2×5 на Беовульфе 2,23 мс (`../bench/beowulf-stage7/r1/`), в пороге ACC-022

## Проверка глазами (G-LOOK, AGENTS.md «Look before you report»)

- Каждый PNG листа и кадра открыт (Read): да, 6 кадров и листы K1 / K2×2,5 обеих досок
- Доска — Marmoreal original или Sarpedon original: да, обе (вариант фикстуры Р7-11)
- Задник верный для карты (Marmoreal — нарисованный, Sarpedon — lit3d): да
- Все шесть фигур — v2: да (`heroesV2 summary fighters=6 mapped=6 v2=6`); Беовульф на K2 в центре: бурая меховая мантия, железный шлем, деревянный щит с умбоном, меч; кольцо команды P2 по боковине нижнего яруса подставки
- Различимо в сером и при дейтеранопии (G-GRAY): да — силуэт фигуры читается против клетки, кольцо подставки в сером — тёмная кромка

## Что не прошло

Ничего из листа K1/K2 (Idle). Провал ворота мантии в DeathSettle к.16–21 — лист AN-148 и `../README.md`.
