# IC-54 — лист приёмки `ui-close` (глиф «×» закрыть)

Лист собран 2026-10-06: `draw_icons.py --sheet accept ui-close` (мастер и рабочие размеры ×4 nearest, цвет / серый Rec.709 / дейтеранопия на card.navy, card.cream, #808080), `tools/art/visual/sheet.py` (24 / 32 / 48 px) и `art/imagegen/hud-icons-v3/_tools/vr44_checks.py` (пункты acceptance карточки). Финал нарисован движком `draw_icons.py` по числам карточки (ImageGen и Codex не участвовали).

**Решение:** художественно принято, по делегированию (листы; ВР-42, ВР-60). Id в `ACCEPTED_VR44` и в контракте `accepted_vr44` — вид по умолчанию.
**Дата решения:** 2026-10-06
**Ревью:** Claude, один проход, арт и рамки задачи вместе (02 §13.3); VS-2 шаг A2.
**Флаг отката:** `-S08SlateHud=toast` (UUmToast CloseButton, UUmCardInspector, UUmHudDeckPanel)
**Решения по делегированию:** ВР-VS2-22 (art/imagegen/hud-icons-v3/README.md, раздел VR44).

## Что сделано

- Две планки 2,25 u крестом под 45°, полуразмах 6 u, плоские концы, keyline 1 u офсетом; белая маска, никогда не красный и без плашки. ue_sizes 18…64.

## Состав листа (02 §13.2)

| № | Пункт | Файлы | Есть |
|---|---|---|---|
| 1 | Мастер и рабочие размеры ×4 nearest | `accept-ui-close.png`, `sheet-sizes.png` | да |
| 2 | Цвет, серый Rec.709, дейтеранопия | `accept-ui-close.png`, `sheet-01-ui-close-24.png`, `sheet-02-ui-close-32.png`, `sheet-03-ui-close-48.png` | да |
| 3 | Кадр K1 обеих настоящих досок, 1080p / 720p, 100 % / 150 % | — | нет: после носителя (блоки TOASTS и INSPECT) |
| 4 | Контекст: panel.bg, card.cream, поле, соседи | `check-neighbours.png` | да |
| 5 | Движение | контракт `docs/unreal/contracts/hud/icon-motion.json` (эталон `icon-motion-golden.json`) | G-ICON — IC-70 |
| 6 | Трассы | — | после носителя |
| 7 | README | этот файл, `checks.json`, `accept.json`, `sheet-manifest.json` | да |

## Входы sheet.py

| файл | размер | sha256 |
|---|---|---|
| `art/imagegen/hud-icons-v3/sizes/ui-close-24.png` | 24×24 | 1a533c1b5c685250c3873894ed60765afea8e60ee31a620fb06ba187f0615548 |
| `art/imagegen/hud-icons-v3/sizes/ui-close-32.png` | 32×32 | 42bc98e080d25eb33de0c26e2e83be55b53e0709b2083f82bd26a7104b04707e |
| `art/imagegen/hud-icons-v3/sizes/ui-close-48.png` | 48×48 | 422077495bb98cbdc189b78300da2098c294b1e630413436522602914704b2f4 |

## Проверка глазами и замеры

- Каждый PNG этой папки открыт (Read): `accept-ui-close.png`, `check-neighbours.png`, `sheet-01-ui-close-24.png`, `sheet-02-ui-close-32.png`, `sheet-03-ui-close-48.png`, `sheet-sizes.png`.
- В сером рядом с badge-refuse и marker-x-stamp — тоньше и без плашки (`check-neighbours.png`).
- audit: margin_px 249, seam_px 8.
- sha1 принятых файлов набора (27 id, 3 варианта, маска, кандидат) в `manifest.json` не изменились: 968 из 968 те же, добавлено 322.
- Доска / задник / шесть фигур v2: кадров ещё нет — значок без носителя в UE.

## Что не прошло или отложено

- Кадр K1 packaged `-Bench` на Marmoreal original и Sarpedon original (шесть фигур v2), 1080p и 720p, 100 % и 150 % — после подключения носителя (блоки TOASTS и INSPECT); шаг «Кадры» VS-2. Строка реестра 03 и статус карточки правятся в основной копии после интеграции (ВР-PL09).
- G-ICON |Δ| ≤ 0,45 — IC-70 (галерея UE в упаковке шага «Кадры»). Текстуры ue_target есть в `art/imagegen/hud-icons-v3/ue-import-report.json`.
