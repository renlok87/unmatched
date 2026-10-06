# IC-46 — лист приёмки `action-end-turn` (диск «Конец хода»)

Лист собран 2026-10-06 (VS-2 шаг A3): `draw_icons.py --sheet accept action-end-turn` (мастер и рабочие размеры ×4 nearest, цвет / серый Rec.709 / дейтеранопия на card.navy, card.cream, #808080), `tools/art/visual/sheet.py` (24 / 32 / 48 px) и `art/imagegen/hud-icons-v3/_tools/vr44_checks.py --a3` (пункты acceptance карточки). Финал нарисован движком `draw_icons.py`; форма — числа принятого вектора A пакета Codex IC-36 (ImageGen и Codex финал не рисовали).

**Решение:** художественно принято, по делегированию (листы; ВР-42, ВР-60). Id в `ACCEPTED_VR44` и в контракте `accepted_vr44` — вид по умолчанию.
**Дата решения:** 2026-10-06
**Ревью:** Claude, один проход, арт и рамки задачи вместе (02 §13.3); VS-2 шаг A3.
**Флаг отката:** `-S08SlateHud=actions` (носитель — UUmHudActions → UUmButton «диск», HB-43)
**Решения по делегированию:** ВР-IC09; ВР-VS2-23, ВР-VS2-25 (art/imagegen/hud-icons-v3/README.md, раздел VR44 A3).

## Что сделано

- Форма — вектор A пакета Codex IC-36 (`art/imagegen/hud-icons-vr44-codex/`, принят по делегированию в ревью VS-1), числа один в один: семейство shape.action_disc (keyline r 14–15 u, крем card.cream r 12,75–14 u, тело card.navy), «→|» card.glyph — древко 2,25 u от x −8 до −1,25 и наконечник 7 × 4,5 u одним полигоном, стоп-черта 2,25 × 12 u, зазор острие–черта 1,5 u до снэпа.
- Альфа экспорта побайтно равна `vector/<px>/end-turn.png` пакета на 1024 / 16 / 21 / 24 / 32 / 48 / 64 / 96, цвет — после назначения ближайшего токена (pytest `test_vr44_forms_match_codex_proposal`; ВР-VS2-23).
- Слои `_body` (диск) и `_glyph` (печать) для UUmButton и движения; контракт `action-end-turn` — события action-attack без spend / restore (hover 1,06, press 0,96, release, select — импульс глифа 1,12, tap); «пас» не делается (SD-44).
- UE: T_IV3_action_end_turn_{18,24,32,36,48,64}, _body_*, _glyph_* — в `art/imagegen/hud-icons-v3/ue-import-report.json`.

## Состав листа (02 §13.2)

| № | Пункт | Файлы | Есть |
|---|---|---|---|
| 1 | Мастер и рабочие размеры ×4 nearest | `accept-action-end-turn.png`, `sheet-sizes.png` | да |
| 2 | Цвет, серый Rec.709, дейтеранопия | `accept-action-end-turn.png`, `sheet-01-action-end-turn-24.png`, `sheet-02-action-end-turn-32.png`, `sheet-03-action-end-turn-48.png` | да |
| 3 | Кадр K1 обеих настоящих досок, 1080p / 720p, 100 % / 150 % | — | нет: после носителя (блок ACTIONS (UUmHudActions, WBP_UI_HUD_ACTIONS, HB-43)) |
| 4 | Контекст: panel.bg, card.cream, поле, соседи | `check-button.png`, `check-states.png`, `check-neighbours.png` | да |
| 5 | Движение | контракт `docs/unreal/contracts/hud/icon-motion.json` (эталон `icon-motion-golden.json`) | G-ICON — IC-70 |
| 6 | Трассы | — | после носителя |
| 7 | README | этот файл, `checks.json`, `accept.json`, `sheet-manifest.json` | да |

## Входы sheet.py

| файл | размер | sha256 |
|---|---|---|
| `art/imagegen/hud-icons-v3/sizes/action-end-turn-24.png` | 24×24 | 32abcc49750123041e6744982d8f6d70dc9ddad0a985362c8ef314122ea8f5e3 |
| `art/imagegen/hud-icons-v3/sizes/action-end-turn-32.png` | 32×32 | fd9b42b34446085d02936150abb70257d33216ab08a2188006f7e0c50b6ac0a1 |
| `art/imagegen/hud-icons-v3/sizes/action-end-turn-48.png` | 48×48 | f6d902954dd8bec2683920f84c60d951eb476872d863a8382b6b78b056818caf |

## Проверка глазами и замеры

- Каждый PNG этой папки открыт (Read): `accept-action-end-turn.png`, `check-button.png`, `check-neighbours.png`, `check-states.png`, `sheet-01-action-end-turn-24.png`, `sheet-02-action-end-turn-32.png`, `sheet-03-action-end-turn-48.png`, `sheet-sizes.png`.
- `check-button.png`: диск читается на теле главной кнопки turn.flash.yellow (navy к жёлтому 10,91 : 1, keyline 11,08 : 1) и на panel.bg (кремовое кольцо 15,64 : 1); глиф к navy 17,24 : 1; стрелка с чертой читается при 24 px.
- `check-states.png`: строка состояний 02 §4.3 — normal, hover 1,06, pressed 0,96, disabled 0,4, selected (пик импульса глифа 1,12), focus (кольцо card.glyph 2 su) на жёлтом и на panel.bg, в цвете и в сером. Масштаб на листе — билинейный ресэмпл (предпросмотр RenderTransform), не экспорт.
- `check-neighbours.png`: в сером тёмный диск (тело 45,7) с кремовым кольцом и «→|» отличается от state-boost (тело 68,2, без крема, цифра) и от пипсов action-* (тела 93,6 / 110,0 / 97,3 / 178,8).
- audit мастера: margin_px [32, 32, 32, 32], seam_px 1 (набор v3 — до 21).
- sha1 принятых файлов набора (27 id, 3 варианта, маска, кандидат и 17 строк VR44 шага A2) в `manifest.json` не изменились: 1290 из 1290 те же, добавлено 99 (пять id шага A3).
- Доска / задник / шесть фигур v2: кадров ещё нет — значок без носителя в UE.

## Что не прошло или отложено

- G-ICON |Δ| ≤ 0,45 — IC-70 (галерея UE в упаковке шага «Кадры»). Текстуры ue_target есть в `art/imagegen/hud-icons-v3/ue-import-report.json`.
- Кадр K1 packaged `-Bench` на Marmoreal original и Sarpedon original (шесть фигур v2), 1080p и 720p, 100 % и 150 % — после подключения носителя (блок ACTIONS (UUmHudActions, WBP_UI_HUD_ACTIONS, HB-43)); шаг «Кадры» VS-2. Строка реестра 03 и статус карточки правятся в основной копии после интеграции (ВР-PL09).
