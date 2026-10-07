# IC-55 — лист приёмки `ui-log` (глиф кнопки «Журнал»)

Лист собран 2026-10-06 (VS-2 шаг A3): `draw_icons.py --sheet accept ui-log` (мастер и рабочие размеры ×4 nearest, цвет / серый Rec.709 / дейтеранопия на card.navy, card.cream, #808080), `tools/art/visual/sheet.py` (24 / 32 / 48 px) и `art/imagegen/hud-icons-v3/_tools/vr44_checks.py --a3` (пункты acceptance карточки). Финал нарисован движком `draw_icons.py`; форма — числа принятого вектора A пакета Codex IC-36 (ImageGen и Codex финал не рисовали).

**Решение:** художественно принято, по делегированию (листы; ВР-42, ВР-60). Id в `ACCEPTED_VR44` и в контракте `accepted_vr44` — вид по умолчанию.
**Дата решения:** 2026-10-06
**Ревью:** Claude, один проход, арт и рамки задачи вместе (02 §13.3); VS-2 шаг A3.
**Флаг отката:** `-S08SlateHud=top` (носитель — UUmHudTop LogButton, класс S, HB-14…HB-16)
**Решения по делегированию:** ВР-IC10, ВР-VS2-01; ВР-VS2-23, ВР-VS2-24 (art/imagegen/hud-icons-v3/README.md, раздел VR44 A3).

## Что сделано

- Форма — вектор A пакета Codex IC-36 после доработки fix1 (ВР-VS2-01): диск-пипс как у конца хода (keyline r 14–15 u, крем r 12,75–14 u, navy), белая печать без своего keyline — три строки 11 × 2,25 u с квадратными маркерами 2,75 u, зазор 1,5 u, шаг 4,5 u, целочисленный шаг рядов; при detail 0 (16, 18 px) — две строки. Числа один в один.
- Альфа побайтно равна `vector/<px>/log.png` пакета на всех восьми размерах (pytest `test_vr44_forms_match_codex_proposal`).
- Полноцветный диск, не белая маска (ВР-VS2-24): UMG его не красит; строка карточки «на главной — глиф красится card.navy» не применяется — LogButton всегда обычная кнопка.
- Контракт `ui-log` — статичный (appear 180 / leave 120 только для импорта и галереи), состояния даёт UUmButton.
- UE: T_IV3_ui_log_{18,24,32,36,48,64} — в `ue-import-report.json`.

## Состав листа (02 §13.2)

| № | Пункт | Файлы | Есть |
|---|---|---|---|
| 1 | Мастер и рабочие размеры ×4 nearest | `accept-ui-log.png`, `sheet-sizes.png` | да |
| 2 | Цвет, серый Rec.709, дейтеранопия | `accept-ui-log.png`, `sheet-01-ui-log-24.png`, `sheet-02-ui-log-32.png`, `sheet-03-ui-log-48.png` | да |
| 3 | Кадр K1 обеих настоящих досок, 1080p / 720p, 100 % / 150 % | лист галереи TOP класса S (`-S08IconGalleryActions`, HB-43: 1080p 150 % и 720p 150 %, состояния own-2 и opp) — вне git (кадр доски, ВР-VS4-01): `scraped-data/derived/visual-evidence/IC-55/` (k1-gallery-top-s-*.png), [`visual-evidence-index.json`](visual-evidence-index.json) | галерея: да (VS-4 V3); packaged `-Bench`: шаг «Кадры» |
| 4 | Контекст: panel.bg, card.cream, поле, соседи | `check-neighbours.png`, `check-discs.png` | да |
| 5 | Движение | контракт `docs/unreal/contracts/hud/icon-motion.json` (эталон `icon-motion-golden.json`) | G-ICON — IC-70 |
| 6 | Трассы | лист ACTIONS не пишет строку TOP; `SHOT widget id=UI-HUD-TOP` — шаг «Кадры» | нет |
| 7 | README | этот файл, `checks.json`, `accept.json`, `sheet-manifest.json` | да |

## Входы sheet.py

| файл | размер | sha256 |
|---|---|---|
| `art/imagegen/hud-icons-v3/sizes/ui-log-24.png` | 24×24 | 2219aaba60385d27725e4f70b6287c4a45133e0a8f208d190e91afbf09a4e049 |
| `art/imagegen/hud-icons-v3/sizes/ui-log-32.png` | 32×32 | 9717b8ed822d032b37625b1ae8e70e06b16d06f06f089767949f41b84afc14af |
| `art/imagegen/hud-icons-v3/sizes/ui-log-48.png` | 48×48 | 88bebf19c5e5670ab572c669b328a2826462f5c5b8afbdae0addcdba12ab036d |

## Проверка глазами и замеры

- Каждый PNG этой папки открыт (Read): `accept-ui-log.png`, `check-discs.png`, `check-neighbours.png`, `sheet-01-ui-log-24.png`, `sheet-02-ui-log-32.png`, `sheet-03-ui-log-48.png`, `sheet-sizes.png`.
- `check-neighbours.png`: при 18 и 24 px в сером рядом с ui-menu (три голые планки) и resource-card (скошенная стопка) — три разных значка: у журнала диск с кольцом и квадратные маркеры.
- `check-discs.png`: на общем диске рядом с action-end-turn и state-boost отличается печатью (строки против «→|» и «+2»).
- Строк при 16 / 18 / 21 / 24 / 32 / 48 px: 2 / 2 / 3 / 3 / 3 / 3 (`checks.json`); на 24 px маркер 2 px, зазоры 1 px.
- audit мастера: margin_px [32, 32, 32, 32], seam_px 0 (набор v3 — до 21).
- sha1 принятых файлов набора (27 id, 3 варианта, маска, кандидат и 17 строк VR44 шага A2) в `manifest.json` не изменились: 1290 из 1290 те же, добавлено 99 (пять id шага A3).
- VS-4 V3 (2026-10-07): лист галереи HB-43 открыт (Read: `k1-gallery-top-s-colour.png`): диск «Журнал» справа в TOP класса S (1080p 150 %, 720p 150 %) на обеих досках, три строки с маркерами читаются; в ход соперника — тот же вид. Доска — Marmoreal с нарисованным задником / Sarpedon lit3d.

## Что не прошло или отложено

- G-ICON |Δ| ≤ 0,45 — IC-70 (галерея UE в упаковке шага «Кадры»). Текстуры ue_target есть в `art/imagegen/hud-icons-v3/ue-import-report.json`.
- Кадр K1 packaged `-Bench` на Marmoreal original и Sarpedon original (шесть фигур v2), 1080p и 720p, 100 % и 150 % — после подключения носителя (блок TOP, класс S (UUmHudTop LogButton)); шаг «Кадры» VS-2. Строка реестра 03 и статус карточки правятся в основной копии после интеграции (ВР-PL09).
