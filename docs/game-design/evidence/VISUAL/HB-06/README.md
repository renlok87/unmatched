# HB-06: лист приёмки (корень UMG HUD и раскладка L/S)

Лист собран `tools/art/visual/sheet.py` 2026-10-07 по 02-visual-design.md §13.2. Поля ниже заполняет Claude после
ревью (один проход, 07 §5).

**Решение:** художественно принято, по делегированию (2026-10-07). Код — `f6247538` (VS-2 A1), правки слоёв по кадрам — `7751060a`, `56315f12`, `230b2b0d` (ВР-VS2-71…75, 77)
**Дата решения:** 2026-10-07
**Ревью:** Claude, один проход, арт и рамки задачи вместе (02 §13.3)
**Флаг отката:** `-S08SlateHud` (весь HUD) или `-S08SlateHud=<блоки>`; в `ARTLOOK … hudImpl=` и `HUD-ROOT impl=`

## Состав листа (02 §13.2)

| № | Пункт | Файлы | Есть |
|---|---|---|---|
| 1 | Мастер и рабочие размеры (значки 1024 и 24/32/48 ×4 nearest; скины ×1, ×2; карты — показы §6.2) | — | — |
| 2 | Цвет, серый Rec.709, дейтеранопия — для каждого размера | `sheet-01-marm-1080-100-host-own-t3.0.png`, `sheet-02-marm-1080-75-joiner-own-t3.0.png`, `sheet-03-sarp-1080-100-slate-host-own-t3.0.png`, `sheet-04-sarp-720-150-host-own-t3.0.png` | да |
| 3 | Кадр на обеих настоящих досках: Marmoreal original и Sarpedon original, K1 и K2, packaged `-Bench` с отпечатком `RENDER`; для HUD ещё 1280×720 и 150 % | живые кадры упаковки `230b2b0d` (`run-combat-demo -PlayerView`, RENDER вне эталона 0): sheet-01…04 и 112 кадров выхода [VS-2](../VS-2/README.md) | да (ВР-VS1-F01: живой HUD на `-Bench` не строится) |
| 4 | Контекст: на `panel.bg`, на `card.cream`, на поле | — | — (входы непрозрачные) |
| 5 | Движение: лист кадров по времени, обычный / reduced | — | — |
| 6 | Трассы: `ARTLOOK`, `SHOT widget` (HUD), `CUE fx` (VFX), `concept-paste` (окружение) | `HUD-ROOT`, `HUD-LAYOUT`, `SHOT widget id=UI-SCR-GAME`, `HUD-CMD`; сводка [`VS-2/data/gwidget.json`](../VS-2/data/gwidget.json) | да |
| 7 | README: что проверено, замеры, что не прошло, флаг отката | этот файл | да |

## Входы

| файл | размер | sha256 |
|---|---|---|
| `C:/tmp/visual/VS2-frames/cardin/HB-06/marm-1080-100-host-own-t3.0.png` | 1920×1080 | 90ae41a8c756bf71c4cdeed5918946b58f9eeaeb94aba5bcf0e03a6e78710dc6 |
| `C:/tmp/visual/VS2-frames/cardin/HB-06/marm-1080-75-joiner-own-t3.0.png` | 1920×1080 | 4680635c36152a0d6a64bad284caad86bde2ea3a7dbf5cd2aad6dad39a4757ee |
| `C:/tmp/visual/VS2-frames/cardin/HB-06/sarp-1080-100-slate-host-own-t3.0.png` | 1920×1080 | d0f0e7d689f3679b46ed66e1427b366257b6da1c5919296dcecd2db458709635 |
| `C:/tmp/visual/VS2-frames/cardin/HB-06/sarp-720-150-host-own-t3.0.png` | 1280×720 | d04388dc45587278158b3a00c13698e9043c56a93596c8cbc04f51a49bb9c184 |

## Замеры

- HUD-LAYOUT по прогонам: 1080p 100 % → 1920×1080 L; 1080p 150 % → 1280×720 S; 1080p 75 % → 2560×1440 L; 720p 100 % →
  1707×960 L; 720p 150 % → 1138×640 S; `overlapField = 0` во всех UMG-прогонах.
- Мин. текст на 720p 100 %: 10,5 px (подпись OPP-HAND `type.caption` и Slate «EFFECTS», замер по ширине «чернил»).
- Перекрытия по трассам: из 1004 кадров блок VS-2 закрывает тег один раз (STATUS в две строки, 720p 150 %), фигуру — ни разу.
- ΔGPU: не мерили. Блок UMG без 3D-ресурсов, лёгкий режим (AGENTS.md «Iteration speed»).

## Проверка глазами (G-LOOK, AGENTS.md «Look before you report»)

- Каждый PNG листа и кадра открыт (Read): да. Это четыре листа и все кадры выхода VS-2.
- Доска: Marmoreal original (sheet-01, 02) и Sarpedon original (sheet-03, 04).
- Задник: Marmoreal нарисован (`-ConceptPaste` до EN-13, пометка), Sarpedon — `lit3d`.
- Все шесть фигур v2: в каждой трассе `v2=6`.
- В сером и при дейтеранопии всё различимо: плашки `panel.bg` отделены от поля кромкой, текст белый и жёлтый.
- sheet-01 — 1080p 100 %, свой ход +3 с: TOP, STATUS, PANEL-LOC внизу слева, PANEL-OPP и OPP-HAND вверху справа, бой
  по краям, рука внизу.
- sheet-02 — 1080p 75 %, холст 2560×1440: всё мельче, не перекрывается.
- sheet-03 — откат `-S08SlateHud`: прежний вид — Slate «YOUR TURN», служебная строка, кнопки боковой панели, левая
  колонка портретов.
- sheet-04 — 720p 150 %, класс S: компакт-панели, баннер и STATUS, ряд руки целиком.

## Что не прошло

- STATUS в две строки один раз закрыл тег гарпии (Marmoreal 720p 150 %); STATUS закрывает шапку Slate-панели колоды на
  720p 150 % — [VS-2](../VS-2/README.md), «Открыто», п. 2–3.
- Slate-блоки (командная панель, рука, карты боя, тост «DISCARDED») ещё на английском — VS-3 / VS-4.
