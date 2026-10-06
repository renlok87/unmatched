# IC-53 — лист приёмки `ui-menu` (глиф кнопки меню «≡»)

Лист собран 2026-10-06: `draw_icons.py --sheet accept ui-menu` (мастер и рабочие размеры ×4 nearest, цвет / серый Rec.709 / дейтеранопия на card.navy, card.cream, #808080), `tools/art/visual/sheet.py` (24 / 32 / 48 px) и `art/imagegen/hud-icons-v3/_tools/vr44_checks.py` (пункты acceptance карточки). Финал нарисован движком `draw_icons.py` по числам карточки (ImageGen и Codex не участвовали).

**Решение:** художественно принято, по делегированию (листы; ВР-42, ВР-60). Id в `ACCEPTED_VR44` и в контракте `accepted_vr44` — вид по умолчанию.
**Дата решения:** 2026-10-06
**Ревью:** Claude, один проход, арт и рамки задачи вместе (02 §13.3); VS-2 шаг A2.
**Флаг отката:** `-S08SlateHud=top` (носитель — UUmHudTop MenuButton)
**Решения по делегированию:** ВР-VS2-22 (art/imagegen/hud-icons-v3/README.md, раздел VR44).

## Что сделано

- Три прямые планки 16 × 2,25 u, зазоры 3,5 u, плоские концы, keyline 1 u вокруг каждой; detail 0 (16, 18 px) — планки и зазоры 2 px. Белая маска (UMG красит card.glyph / card.navy). ue_sizes 18…64; appear 180 / leave 120 только для импорта и галереи.

## Состав листа (02 §13.2)

| № | Пункт | Файлы | Есть |
|---|---|---|---|
| 1 | Мастер и рабочие размеры ×4 nearest | `accept-ui-menu.png`, `sheet-sizes.png` | да |
| 2 | Цвет, серый Rec.709, дейтеранопия | `accept-ui-menu.png`, `sheet-01-ui-menu-24.png`, `sheet-02-ui-menu-32.png`, `sheet-03-ui-menu-48.png` | да |
| 3 | Кадр K1 обеих настоящих досок, 1080p / 720p, 100 % / 150 % | — | нет: после носителя (блок TOP (WBP_UI_HUD_TOP), шапки LOBBY / ROOM) |
| 4 | Контекст: panel.bg, card.cream, поле, соседи | `check-neighbours.png`, `check-tint.png` | да |
| 5 | Движение | контракт `docs/unreal/contracts/hud/icon-motion.json` (эталон `icon-motion-golden.json`) | G-ICON — IC-70 |
| 6 | Трассы | — | после носителя |
| 7 | README | этот файл, `checks.json`, `accept.json`, `sheet-manifest.json` | да |

## Входы sheet.py

| файл | размер | sha256 |
|---|---|---|
| `art/imagegen/hud-icons-v3/sizes/ui-menu-24.png` | 24×24 | c67714507f4851297dd4c49a9911b72f55f0fc9a4e078233248e9470be2c236f |
| `art/imagegen/hud-icons-v3/sizes/ui-menu-32.png` | 32×32 | f6d3f32489beaa2bc87ec18d4c0855a5588c2d26b461996b7b86d2342663456d |
| `art/imagegen/hud-icons-v3/sizes/ui-menu-48.png` | 48×48 | ca97a4d3d71f31886174564be9446e49f1781214d66baacd33ec69b00e4adac6 |

## Проверка глазами и замеры

- Каждый PNG этой папки открыт (Read): `accept-ui-menu.png`, `check-neighbours.png`, `check-tint.png`, `sheet-01-ui-menu-24.png`, `sheet-02-ui-menu-32.png`, `sheet-03-ui-menu-48.png`, `sheet-sizes.png`.
- Рядом с resource-card при 18 и 24 px в сером — разные значки: прямые планки с зазорами против скошенных плашек (`check-neighbours.png`).
- Маска × card.navy на кремовой главной кнопке читается (`check-tint.png`).
- audit: margin_px [224, 260, 224, 260], seam_px 0.
- sha1 принятых файлов набора (27 id, 3 варианта, маска, кандидат) в `manifest.json` не изменились: 968 из 968 те же, добавлено 322.
- Доска / задник / шесть фигур v2: кадров ещё нет — значок без носителя в UE.

## Что не прошло или отложено

- Кадр K1 packaged `-Bench` на Marmoreal original и Sarpedon original (шесть фигур v2), 1080p и 720p, 100 % и 150 % — после подключения носителя (блок TOP (WBP_UI_HUD_TOP), шапки LOBBY / ROOM); шаг «Кадры» VS-2. Строка реестра 03 и статус карточки правятся в основной копии после интеграции (ВР-PL09).
- G-ICON |Δ| ≤ 0,45 — IC-70 (галерея UE в упаковке шага «Кадры»). Текстуры ue_target есть в `art/imagegen/hud-icons-v3/ue-import-report.json`.
