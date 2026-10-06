# HB-20 — портрет соперника справа вверху: диагональ, трекер соперника, «ИИ думает» (ВР-H03, ВР-01)

VS-2 шаг B2, 2026-10-06, ветка `feat/visual-vs2`. Карточка — `06-tasks/hud.csv` HB-20; спецификация — 04 §2.3, §1.6, §7.1;
ВР-H03; макет — CX-09 (принят по делегированию). Решения шага — ВР-VS2-51…62 в [README HB-18](../HB-18/README.md) (для этой
карточки — 51, 53, 54, 55, 58).

**Статус:** код, WBP, тест, листы галереи готовы; кадры packaged (набор B, `tools/s10/run-vs-ai-demo.ps1`) — шаг «Кадры».
**Флаг отката:** `-S08SlateHud=panels` — обе панели прежней колонкой слева и строка «Opponent is planning».

## Что сделано

| Пункт карточки | Где |
|---|---|
| 1. Второй UUmHudPlayerPanel, Side=Opp, WBP_UI_HUD_PANEL_OPP, якорь право-верх | `/Game/S08/UI/Hud/WBP_UI_HUD_PANEL_OPP` — зеркальное дерево (`BuildDefaultTree(…, Opp)`); слот `PanelOpp` раскладки HB-06: L (1556, 24, 340, 136), 720p (1342.7, 24), S (W − 256, 16, 240, 96). Зеркально (ВР-H03): кольцо (232, 12), текст, статус и группа HP по правому краю 212, трекер снаружи слева (12, 46), помощники по правому краю; Merlin — мини-портрет, затем имя и HP |
| 2. Трекер соперника — FS09ActionTracker: 150 мс в его ход, скрытие за 1 кадр в мой | прежняя логика `TickTurnHud` (`OpponentAlpha`, сброс F-12) на ряду трекера панели соперника |
| 3. VS_AI: точка-пульс слева от статуса при IsBotActing, «ИИ думает» | состояние `ai` при `FS08FlowController::IsBotActing` в его ход: `PulseDot` 8 su `text.secondary`, 5 su до текста, 1 Гц 1 → 0,35 → 1 (reduced — статична), `hud.opp.thinking` капсом «ИИ ДУМАЕТ»; глагол соперника — в STATUS (HB-15) |
| 4. HandObstacleRightSu / HandPanelLeft не учитывают панель соперника слева | `HandObstacleRightSu` берёт правый край PANEL-LOC (`UmHudPanelLocRightSu`); колонки двух портретов нет |
| 5. «Opponent is planning» Slate — только `-S08SlateHud=panels` | `AddOpponentPanelLines` — одно условие |
| 6. SHOT widget id=UI-HUD-PANEL-OPP state=opp\|wait\|fallen\|ai | `SHOT widget id=UI-HUD-PANEL-OPP impl=umg state=…` (тот же формат, что у LOC) |
| 7. Тест Unmatched.S08.Hud.PlayerPanel.OppMirror | позиция (диагональ к PANEL-LOC, 1080p и 720p 150 %), зеркальные места, «их ход» без слова (ВР-VS2-54), «ИИ ДУМАЕТ» и пульс 1 / 0,35 через 500 мс, reduced статичен, правила состояний `Gather` (opp / ai / wait / fallen), SHOT |

## Проверки

- `Unmatched.S08.Hud.PlayerPanel.OppMirror` и `Root.Layout` зелёные; копии соперника в левой колонке нет (колонка Slate
  строится только при откате).
- Листы [HB-18/gallery](../HB-18/gallery/): opp (кольцо, видимый трекер с одним заполненным слотом), wait («ЖДЁТ», трекер
  скрыт), ai (точка и «ИИ ДУМАЕТ»), fallen (серый круг, сердце с крестом, «ВНЕ ИГРЫ»); в S трекер слева, HP справа.

## Отложено (шаг «Кадры»)

- G-WIDGET `UI-HUD-PANEL-OPP opp` и `wait` на обеих досках, `ai` — в `tools/s10/run-vs-ai-demo.ps1`; кадры набора B (ход
  соперника, VS_AI думает, трекер соперника), 1080p 100 % и 720p 100 %; `overlapField=0`.

## Кадры VS-2 (2026-10-07, упаковка `230b2b0d`)

Кадры выхода и гейты — [VS-2](../VS-2/README.md). Прогоны `run-combat-demo -PlayerView -S08ExitShots` на Marmoreal original (`-ConceptPaste` до EN-13) и Sarpedon original, шесть фигур v2, 1080p 75 / 100 / 150 %, 720p 100 / 150 %; vs-ai `-PlayerView`. Листы цвет / серый / дейтеранопия — `sheet-0*.png` (`sheet.py`, вырезки по трассовым bbox). Все кадры и листы открыты (Read).

- **Решение:** художественно принято, по делегированию (2026-10-07).
- PANEL-OPP справа вверху, зеркально, в состояниях opp / wait / fallen. «ИИ ДУМАЕТ» с точкой — в кадрах vs-ai, где в трассе `state=ai` (ВР-VS2-78; бот отвечает быстрее 0,5 с).
- PANEL-OPP гаснет под открытой панелью колоды (ВР-VS2-71).
- У T. Rex нет аватара в реестре, поэтому монограмма «TR» и помощник «U Unknown» — ожидаемый фолбэк CP-08.
