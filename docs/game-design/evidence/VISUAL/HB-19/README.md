# HB-19 — кольцо хода, трекер DE, ореол сердца, сердце павшего в панелях UMG (AB-5…AB-8)

VS-2 шаг B2, 2026-10-06, ветка `feat/visual-vs2`. Карточка — `06-tasks/hud.csv` HB-19; спецификация — 04 §2.2 (таблица
состояний), §2.3; 02 §5.2 (DE-012, лично 2026-10-05); ВР-43; `de-footage/task/01-decisions.md` AB-5…AB-8. Решения шага —
ВР-VS2-51…62 в [README HB-18](../HB-18/README.md) (для этой карточки — 51, 52, 53, 60).

**Статус:** код и тест готовы, вид в листах галереи; кадры packaged (наборы A, C, H) — шаг «Кадры» VS-2.
**Вид:** AB-5…AB-8 остаётся «художественно принято, лично» (2026-10-05); перенос в UMG — по делегированию, вид не меняется.
**Флаги отката:** `-S08TurnRingLegacy`, `-S08HeartGlowLegacy`, `-S08TrackerLegacy`, `-S08CrossLegacy` (работают и в панелях),
весь блок — `-S08SlateHud=panels`.

## Что сделано

| Пункт карточки | Где |
|---|---|
| 1. В UUmHudPlayerPanel — логика US08TurnPortraitWidget: RingIcon, TrackerIcons, HeartIcon (glow); движение только US08AnimatedIconWidget по icon-motion.json | `US08TurnPortraitWidget::AttachToPanel` (ВР-VS2-51): кольцо `marker-turn-ring` в окне круга (L 104, S 80 su), значки трекера `marker-action-slot-de` в `TrackerRow` панели (L 32, S 24 su, зазор 4 su, экспорт по DPI HB-23), сердце `resource-hp-full` со слоем `glow` — `HeartIcon` панели; новых кривых нет |
| 2. Флаги отката работают в UMG | `FS08TurnHudLook::FromCommandLine` как раньше — панель строит портрет с тем же видом (тест TurnLook) |
| 3. ring.smoulder = 0,35; 720p при G-READ < 2,75 : 1 — 0,55 (ВР-43) | токены темы `ring.smoulder` 0,35 / `ring.smoulder.s` 0,55 (ВР-VS2-52): L — контракт, S — 0,55 (обод CX-09 при 0,35 — 1,78 : 1); `US08AnimatedIconWidget::SetLayerRestOpacity` масштабирует дорожку `rim`; итог S — по кадру 720p 150 % |
| 4. Трассы как в прогоне I | `HUD-TURN config portraits=1 ring=marker-turn-ring heartGlow=1 tracker=de cross=1 ringIcon=1 banner=600 panels=umg` (пишет `BuildUmPanels`), `HUD-TURN seq=…`, `HUD-TRACK …`, `HUD-HEART … anim=damage glow=1`, `HUD-HEART … anim=fallen glyph=cross played=1` — без изменений из `S08FlowGameModeTurnHud.cpp` |
| 5. Тест Unmatched.S08.Hud.PlayerPanel.TurnLook | флаги и состояния: кольцо (покой / уход), S-обод ×0,55/0,35, трекер DE в ряду панели с заливкой атакой, слот 24 su в S, слой glow, крест павшего на сердце панели; все четыре отката; колонка отката — прежние 64 su и плашка `panel.bg` |

## Проверки

- `Unmatched.S08.Hud.PlayerPanel.TurnLook` зелёный; прежние `Unmatched.S08.IconMotion.*` (портреты, откаты AB-5…AB-8) — зелёные
  (162/162 в общем прогоне).
- G-ICON перемерен после изменений (`-S08IconGallery -S08IconGallerySize=64`, 0 / 120 / 300 / 600 / 1000 / 2000 мс,
  `compare_ue_gallery.py --raster ue`): 270 пар, средняя |Δ| = 0,026 (новые id — 0,011), как в IC-70; значки и кривые не
  менялись, `SetLayerRestOpacity` действует только на слой, которому её задали (обод кольца в панели).
- Листы [HB-18/gallery](../HB-18/gallery/): вспышка кольца +300 мс (оранжевая фаза), тлеющий обод в покое (в S ярче),
  два заполненных слота (манёвры Medusa, атаки Arthur), урон +320 мс с красным ореолом, павший — сердце с крестом;
  монограмма в круге с кольцом. Красной заливки панели нет, `marker-turn-ring-team` не используется.

## Отложено (шаг «Кадры»)

- Трассы `HUD-TURN` / `HUD-HEART` на обеих досках; кадры +0 / +0,5 / +3 с от старта хода (набор A), удар с ореолом и крест
  павшего (набор C, `run-combat-demo.ps1 -RequireGameOver`), 1080p и 720p 100 / 150 %, reduced (набор H).
- G-READ обода на 720p 150 % — окончательное `ring.smoulder.s`; экспорт кольца 128 px (ВР-VS2-60).
