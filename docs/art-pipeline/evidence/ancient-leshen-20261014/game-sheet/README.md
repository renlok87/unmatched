# ASSET-ANCIENT-LESHEN-001 — лист приёмки

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
| 2 | Цвет, серый Rec.709, дейтеранопия — для каждого размера | `sheet-01-bench-K1-1920x1080.png`, `sheet-02-bench-K2x1p6-1920x1080.png`, `sheet-03-bench-K2x2p5-1920x1080.png`, `sheet-04-bench-K1-1920x1080.png`, `sheet-05-bench-K2x1p6-1920x1080.png`, `sheet-06-bench-K2x2p5-1920x1080.png` | да |
| 3 | Кадр на обеих настоящих досках: Marmoreal original и Sarpedon original, K1 и K2, packaged `-Bench` с отпечатком `RENDER`; для HUD ещё 1280×720 и 150 % | `../bench-marmoreal/`, `../bench-sarpedon/` (K1, K2×1,6, K2×2,5; RENDER код 0 × 6) | да |
| 4 | Контекст: на `panel.bg`, на `card.cream`, на поле | — | — (входы непрозрачные) |
| 5 | Движение: лист кадров по времени, обычный / reduced | лист клипов AN-18 (`docs/game-design/evidence/VISUAL/AN-…/`) | да (обычный) |
| 6 | Трассы: `ARTLOOK`, `SHOT widget` (HUD), `CUE fx` (VFX), `concept-paste` (окружение) | `../bench-*/bench.trace.txt` (`ARTLOOK heroes=v2`, `backdrop=paste/lit3d(default)`, `clips=4/4`) | да |
| 7 | README: что проверено, замеры, что не прошло, флаг отката | этот файл + `../README.md` | да |

## Входы

| файл | размер | sha256 |
|---|---|---|
| `C:/tmp/ASSET-ANCIENT-LESHEN-001-stage7/bench-marmoreal/bench-K1-1920x1080.png` | 1920×1080 | b2a22fac53cc931b178605b39e20660f3041b07d465d610fb2ef368ece9a28a4 |
| `C:/tmp/ASSET-ANCIENT-LESHEN-001-stage7/bench-marmoreal/bench-K2x1p6-1920x1080.png` | 1920×1080 | b3199b5344b6598f097c1f5fe9f548476c7dcfb26a1349d1811130ac994b75c1 |
| `C:/tmp/ASSET-ANCIENT-LESHEN-001-stage7/bench-marmoreal/bench-K2x2p5-1920x1080.png` | 1920×1080 | 62c97989c824813883eff229daa74bd43fb6d6a07b9b957a33ce690061fd1eee |
| `C:/tmp/ASSET-ANCIENT-LESHEN-001-stage7/bench-sarpedon/bench-K1-1920x1080.png` | 1920×1080 | 49b672dca7b3c27b5ff7cdfeac4c22a8716d27bae53e8c883c4f03e1c43a7d85 |
| `C:/tmp/ASSET-ANCIENT-LESHEN-001-stage7/bench-sarpedon/bench-K2x1p6-1920x1080.png` | 1920×1080 | c2fcdc653c8e8eb3b63c1ef7e56fe7d377c73d06cfaaffec547de73951abe0ec |
| `C:/tmp/ASSET-ANCIENT-LESHEN-001-stage7/bench-sarpedon/bench-K2x2p5-1920x1080.png` | 1920×1080 | bad7ef3874eba608e1181268dbbfcdcfd3284576b77340878c7d2d4daa4a22ef |

## Замеры

- Контраст (текст ≥ 4,5 : 1, значки и кромки ≥ 3 : 1): —
- ΔE76 к токенам 02 §2: —
- ΔGPU (02 §9.4, `render_bench.py`): —

## Проверка глазами (G-LOOK, AGENTS.md «Look before you report»)

- Каждый PNG листа и кадра открыт (Read): да, 6 кадров и листы K2×2,5 обеих досок
- Доска — Marmoreal original или Sarpedon original: да, обе (вариант фикстуры Р7-11)
- Задник верный для карты (Marmoreal — нарисованный, Sarpedon — lit3d): да
- Все шесть фигур — v2: да (`heroesV2 summary fighters=6 mapped=6 v2=6`); Ancient Leshen на K2 в центре: светлые череп и рога, тёмный ствол с воронами
- Различимо в сером и при дейтеранопии (G-GRAY): да — силуэт фигуры читается против клетки, кольцо команды P2 видно в сером

## Что не прошло

Ничего из листа. Открытые пункты героя — `../README.md`.
