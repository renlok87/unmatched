# IC-51 — лист приёмки `marker-slot-boost` (лента слота BOOST)

Лист собран 2026-10-06: `draw_icons.py --sheet accept marker-slot-boost` (мастер и рабочие размеры ×4 nearest, цвет / серый Rec.709 / дейтеранопия на card.navy, card.cream, #808080), `tools/art/visual/sheet.py` (24 / 32 / 48 px) и `art/imagegen/hud-icons-v3/_tools/vr44_checks.py` (пункты acceptance карточки). Финал нарисован движком `draw_icons.py` по числам карточки (ImageGen и Codex не участвовали).

**Решение:** художественно принято, по делегированию (листы; ВР-42, ВР-60). Id в `ACCEPTED_VR44` и в контракте `accepted_vr44` — вид по умолчанию.
**Дата решения:** 2026-10-06
**Ревью:** Claude, один проход, арт и рамки задачи вместе (02 §13.3); VS-2 шаг A2.
**Флаг отката:** `-S08SlateHud=slot`
**Решения по делегированию:** ВР-VS2-22 (art/imagegen/hud-icons-v3/README.md, раздел VR44).

## Что сделано

- Та же лента, тело card.navy, глиф — белое кольцо card.glyph r 3,5…5,25 u (кольцо снэпнуто: 1 px при 18–24, 2 px при 32, 3 px при 48), язык диска BOOST. Одна текстура; ue_sizes 18…64; appear 220, leave 120 (держится ≥ 1000 мс по SD-54 — забота носителя).

## Состав листа (02 §13.2)

| № | Пункт | Файлы | Есть |
|---|---|---|---|
| 1 | Мастер и рабочие размеры ×4 nearest | `accept-marker-slot-boost.png`, `sheet-sizes.png` | да |
| 2 | Цвет, серый Rec.709, дейтеранопия | `accept-marker-slot-boost.png`, `sheet-01-marker-slot-boost-24.png`, `sheet-02-marker-slot-boost-32.png`, `sheet-03-marker-slot-boost-48.png` | да |
| 3 | Кадр K1 обеих настоящих досок, 1080p / 720p, 100 % / 150 % | — | нет: после носителя (блок SLOT) |
| 4 | Контекст: panel.bg, card.cream, поле, соседи | `check-neighbours.png` | да |
| 5 | Движение | контракт `docs/unreal/contracts/hud/icon-motion.json` (эталон `icon-motion-golden.json`) | G-ICON — IC-70 |
| 6 | Трассы | — | после носителя |
| 7 | README | этот файл, `checks.json`, `accept.json`, `sheet-manifest.json` | да |

## Входы sheet.py

| файл | размер | sha256 |
|---|---|---|
| `art/imagegen/hud-icons-v3/sizes/marker-slot-boost-24.png` | 24×24 | 7694949948565e2349f996c4a62511a3a6dcec05429b6bcc3ed21c4eaa102201 |
| `art/imagegen/hud-icons-v3/sizes/marker-slot-boost-32.png` | 32×32 | 0fe5bd6f869e8e66fb8312e719af12723b017508437a8b99458b869f7bfd72bd |
| `art/imagegen/hud-icons-v3/sizes/marker-slot-boost-48.png` | 48×48 | 29d611466b1efa7fa382da69de3dfc9e49c0aeabc94e70b5538ec8fab99b44f4 |

## Проверка глазами и замеры

- Каждый PNG этой папки открыт (Read): `accept-marker-slot-boost.png`, `check-neighbours.png`, `sheet-01-marker-slot-boost-24.png`, `sheet-02-marker-slot-boost-32.png`, `sheet-03-marker-slot-boost-48.png`, `sheet-sizes.png`.
- Кольцо/navy 17,2 : 1; две ленты слота различимы в сером по тону тела и глифу (`check-neighbours.png`).
- audit: margin_px [182, 32, 182, 41], seam_px 2.
- sha1 принятых файлов набора (27 id, 3 варианта, маска, кандидат) в `manifest.json` не изменились: 968 из 968 те же, добавлено 322.
- Доска / задник / шесть фигур v2: кадров ещё нет — значок без носителя в UE.

## Что не прошло или отложено

- Как IC-50: IC-52 и кадр на рамке карты — позже.
- Кадр K1 packaged `-Bench` на Marmoreal original и Sarpedon original (шесть фигур v2), 1080p и 720p, 100 % и 150 % — после подключения носителя (блок SLOT); шаг «Кадры» VS-2. Строка реестра 03 и статус карточки правятся в основной копии после интеграции (ВР-PL09).
- G-ICON |Δ| ≤ 0,45 — IC-70 (галерея UE в упаковке шага «Кадры»). Текстуры ue_target есть в `art/imagegen/hud-icons-v3/ue-import-report.json`.
