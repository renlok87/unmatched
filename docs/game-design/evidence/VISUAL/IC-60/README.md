# IC-60 — лист приёмки `cursor-unavailable` (курсор «недоступно»)

Лист собран 2026-10-06: `draw_icons.py --sheet accept cursor-unavailable` (мастер и рабочие размеры ×4 nearest, цвет / серый Rec.709 / дейтеранопия на card.navy, card.cream, #808080), `tools/art/visual/sheet.py` (24 / 32 / 48 px) и `art/imagegen/hud-icons-v3/_tools/vr44_checks.py` (пункты acceptance карточки). Финал нарисован движком `draw_icons.py` по числам карточки (ImageGen и Codex не участвовали).

**Решение:** художественно принято, по делегированию (листы; ВР-42, ВР-60). Id в `ACCEPTED_VR44` — вид по умолчанию.
**Дата решения:** 2026-10-06
**Ревью:** Claude, один проход, арт и рамки задачи вместе (02 §13.3); VS-2 шаг A2.
**Флаг отката:** `-S08SlateHud=cursor` (HB-12)
**Решения по делегированию:** ВР-VS2-20, ВР-VS2-22 (art/imagegen/hud-icons-v3/README.md, раздел VR44).

## Что сделано

- cursor-default и малый X state.error: центр (23; 23) u, полуразмах 4,25 u, штрих 2,5 u, keyline 2 u; X в нижнем правом поле, остриё свободно; горячая точка — как у cursor-default.

## Состав листа (02 §13.2)

| № | Пункт | Файлы | Есть |
|---|---|---|---|
| 1 | Мастер и рабочие размеры ×4 nearest | `accept-cursor-unavailable.png`, `sheet-sizes.png` | да |
| 2 | Цвет, серый Rec.709, дейтеранопия | `accept-cursor-unavailable.png`, `sheet-01-cursor-unavailable-24.png`, `sheet-02-cursor-unavailable-32.png`, `sheet-03-cursor-unavailable-48.png` | да |
| 3 | Кадр K1 обеих настоящих досок, 1080p / 720p, 100 % / 150 % | — | нет: после носителя (блок курсоров HB-12) |
| 4 | Контекст: panel.bg, card.cream, поле, соседи | `check-cursor.png` | да |
| 5 | Движение | контракт `docs/unreal/contracts/hud/icon-motion.json` (эталон `icon-motion-golden.json`) | курсоры вне контракта |
| 6 | Трассы | — | после носителя |
| 7 | README | этот файл, `checks.json`, `accept.json`, `sheet-manifest.json` | да |

## Входы sheet.py

| файл | размер | sha256 |
|---|---|---|
| `art/imagegen/hud-icons-v3/sizes/cursor-unavailable-24.png` | 24×24 | 6c5668ee839ae66265f44c43d22748030e257a57bc98e89e6b8cdd047b7f4cf8 |
| `art/imagegen/hud-icons-v3/sizes/cursor-unavailable-32.png` | 32×32 | df3812e2cd6f69c368804ae60b2baff67d45886fc32254d81ed8c250dca27c6f |
| `art/imagegen/hud-icons-v3/sizes/cursor-unavailable-48.png` | 48×48 | d4a850512e5681ce3ef53d6f8c06fe88b33d9859d87802f05aeea8f34e64fc64 |

## Проверка глазами и замеры

- Каждый PNG этой папки открыт (Read): `accept-cursor-unavailable.png`, `check-cursor.png`, `sheet-01-cursor-unavailable-24.png`, `sheet-02-cursor-unavailable-32.png`, `sheet-03-cursor-unavailable-48.png`, `sheet-sizes.png`.
- X не теряется при 24 px (`check-cursor.png`, `sheet-01-cursor-unavailable-24.png`); красный только у знака (И-3); на трёх фонах и в сером читается.
- audit: margin_px [32, 49, 33, 33], seam_px 10.
- sha1 принятых файлов набора (27 id, 3 варианта, маска, кандидат) в `manifest.json` не изменились: 968 из 968 те же, добавлено 322.
- Доска / задник / шесть фигур v2: кадров ещё нет — значок без носителя в UE.

## Что не прошло или отложено

- UE (T_Cursor_Denied, HUD-CURSOR state=denied) — HB-12.
- Кадр K1 packaged `-Bench` на Marmoreal original и Sarpedon original (шесть фигур v2), 1080p и 720p, 100 % и 150 % — после подключения носителя (блок курсоров HB-12); шаг «Кадры» VS-2. Строка реестра 03 и статус карточки правятся в основной копии после интеграции (ВР-PL09).
