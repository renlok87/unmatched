# IC-59 — лист приёмки `cursor-pointer` (указатель «можно нажать»)

Лист собран 2026-10-06 (VS-2 шаг A3): `draw_icons.py --sheet accept cursor-pointer` (мастер и рабочие размеры ×4 nearest, цвет / серый Rec.709 / дейтеранопия на card.navy, card.cream, #808080), `tools/art/visual/sheet.py` (24 / 32 / 48 px) и `art/imagegen/hud-icons-v3/_tools/vr44_checks.py --a3` (пункты acceptance карточки). Финал нарисован движком `draw_icons.py`; форма — числа принятого вектора A пакета Codex IC-36 (ImageGen и Codex финал не рисовали).

**Решение:** художественно принято, по делегированию (листы; ВР-42, ВР-60). Id в `ACCEPTED_VR44` — вид по умолчанию.
**Дата решения:** 2026-10-06
**Ревью:** Claude, один проход, арт и рамки задачи вместе (02 §13.3); VS-2 шаг A3.
**Флаг отката:** `-S08SlateHud=cursor` — системный курсор (HB-12)
**Решения по делегированию:** ВР-IC11, ВР-VS2-02; ВР-VS2-23, ВР-VS2-27 (art/imagegen/hud-icons-v3/README.md, раздел VR44 A3).

## Что сделано

- Форма — вектор A пакета Codex IC-36 после fix1 (ВР-VS2-02): плоская рука, указательный палец вертикально вверх слева (торец 8 u), три ступени согнутых пальцев справа, большой палец слева, плоское запястье 14 u, три скоса 3 × 3 u; keyline mark.keyline 2 u — офсет внутрь того же силуэта, тело card.glyph, радиусы 0; без кольца и тени.
- Альфа побайтно равна `vector/<px>/pointer.png` пакета на всех восьми размерах; цвет — ближайший из двух тонов курсора.
- Горячая точка — середина верхнего торца (11; 2) u: 24 px (8, 2), 32 px (11, 2), 48 px (17, 3), 64 px (22, 4) — `art/imagegen/hud-icons-v3/cursor-hotspots.json`, совпадает с verification.json пакета (pytest).
- В контракт движения и в IconsV3 курсоры не идут; T_Cursor_Pointer (32, _x2, _24, _48) импортирует HB-12 (ВР-VS2-27).

## Состав листа (02 §13.2)

| № | Пункт | Файлы | Есть |
|---|---|---|---|
| 1 | Мастер и рабочие размеры ×4 nearest | `accept-cursor-pointer.png`, `sheet-sizes.png` | да |
| 2 | Цвет, серый Rec.709, дейтеранопия | `accept-cursor-pointer.png`, `sheet-01-cursor-pointer-24.png`, `sheet-02-cursor-pointer-32.png`, `sheet-03-cursor-pointer-48.png` | да |
| 3 | Кадр K1 обеих настоящих досок, 1080p / 720p, 100 % / 150 % | лист галереи ACTIONS (`-S08IconGalleryActions`, HB-43), состояние hover — указатель над доступной ячейкой — вне git (кадр доски, ВР-VS4-01): `scraped-data/derived/visual-evidence/IC-59/` (k1-gallery-hover-*.png), [`visual-evidence-index.json`](visual-evidence-index.json) | галерея: да (VS-4 V3); packaged `-Bench`: шаг «Кадры» |
| 4 | Контекст: panel.bg, card.cream, поле, соседи | `check-cursor.png`, `check-neighbours.png` | да |
| 5 | Движение | курсоры вне контракта | — |
| 6 | Трассы | трассы галереи ACTIONS (`UI-HUD-ACTIONS … tip=`), `check-trace` PASS; строка курсора `HUD-CURSOR` — шаг «Кадры» | частично |
| 7 | README | этот файл, `checks.json`, `accept.json`, `sheet-manifest.json` | да |

## Входы sheet.py

| файл | размер | sha256 |
|---|---|---|
| `art/imagegen/hud-icons-v3/sizes/cursor-pointer-24.png` | 24×24 | cd0fa5eed05a6e5191e97ad4eb121bcb38b64d8f2073ec3222f6df3ea0129202 |
| `art/imagegen/hud-icons-v3/sizes/cursor-pointer-32.png` | 32×32 | 9f3d9ee00d775566bc06521f3cfa61b72a49bc8afe1321323e99891c6e1af6a4 |
| `art/imagegen/hud-icons-v3/sizes/cursor-pointer-48.png` | 48×48 | 29669a6e3ef286fbe2a51c8a189c0cd7f13c9cde2ac2714daec98f418701040b |

## Проверка глазами и замеры

- Каждый PNG этой папки открыт (Read): `accept-cursor-pointer.png`, `check-cursor.png`, `check-neighbours.png`, `sheet-01-cursor-pointer-24.png`, `sheet-02-cursor-pointer-32.png`, `sheet-03-cursor-pointer-48.png`, `sheet-sizes.png`.
- `check-cursor.png`: на светлом пространстве Marmoreal #DEDEE0 границу держит keyline 2 px, на красной палубе Sarpedon #A43839 — keyline и белое тело, на panel.bg — белое тело; в сером читается везде; горячая точка (пиксель #FF00FF) — на кончике пальца при 24 / 32 / 48 / 64 px.
- `check-neighbours.png`: в сером рука отличается от стрелки cursor-default и от стрелки с X cursor-unavailable при 24 / 32 / 48 px.
- audit мастера: margin_px [96, 64, 128, 64], seam_px 0 (набор v3 — до 21).
- sha1 принятых файлов набора (27 id, 3 варианта, маска, кандидат и 17 строк VR44 шага A2) в `manifest.json` не изменились: 1290 из 1290 те же, добавлено 99 (пять id шага A3).
- VS-4 V3 (2026-10-07): лист галереи HB-43 открыт (Read: `k1-gallery-hover-colour.png`): рука-указатель 1 : 1 в горячей точке над доступной ячейкой МАНЁВР на 8 холстах, палец вверх, keyline держит курсор на тёмном диске и на светлой подписи. Доска — Marmoreal с нарисованным задником / Sarpedon lit3d, шесть фигур v2.

## Что не прошло или отложено

- UE: T_Cursor_Pointer (32, _x2 64, _24, _48), трасса HUD-CURSOR state=pointer — HB-12 (тот же шаг A3).
- Кадр K1 packaged `-Bench` на Marmoreal original и Sarpedon original (шесть фигур v2), 1080p и 720p, 100 % и 150 % — после подключения носителя (курсоры HB-12 (UUmCursor, шаг H3)); шаг «Кадры» VS-2. Строка реестра 03 и статус карточки правятся в основной копии после интеграции (ВР-PL09).
