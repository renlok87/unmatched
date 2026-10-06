# HB-18 — свой портрет: UUmHudPlayerPanel, сторона own (шаг H4)

VS-2 шаг B2, 2026-10-06, ветка `feat/visual-vs2` (worktree `C:/tmp/wt-visual`). Карточка — `docs/game-design/visual/06-tasks/hud.csv`
HB-18; спецификация — 04 §2.2, §4.3, §7.1; ВР-47, ВР-71, ВР-72; макет — принятый CX-09 `art/imagegen/hud-panels-v1-codex/`
(c687d7cb, ревью ВР-VS2-CX09-01…08). Шаг B2 общий с HB-19 (вид AB-5…AB-8 в панели), HB-20 (PANEL-OPP, диагональ ВР-01) и
HB-21 (OPP-HAND): решения ВР-VS2-51…62 записаны здесь, README HB-19, HB-20, HB-21 ссылаются сюда.

**Статус:** код, WBP, тема, тесты и листы галереи готовы; приёмочные кадры packaged на обеих досках (наборы A, B, C, H
04 §7.2, `run-combat-demo.ps1 -RequireGameOver`, `run-vs-ai-demo.ps1`) — шаг «Кадры» VS-2 (упаковки в этом шаге нет).
**Решение по арту:** вид принят по делегированию в CX-09 (HB-17); блок повторяет макет (листы `gallery/`).
**Флаг отката:** `-S08SlateHud=panels` (или весь `-S08SlateHud`) — прежняя колонка двух портретов `US08TurnPortraitWidget`
слева внизу и строка «Opponent is planning» в боковой панели.

## Что сделано

| Пункт карточки | Где |
|---|---|
| 1. UUmHudPlayerPanel (Side Own / Opp), BindWidget Panel, Portrait, NameText, StatusText, HeartIcon, HpText, TrackerRow, SidekickRow; ApplyModel | `Source/Unmatched/S08/UI/UmHudPlayerPanel.{h,cpp}`; ещё `Canvas`, `StatusRow`, `PulseDot`, `HpRow` (раскладка CX-09 по местам); модель `FUmPlayerPanelModel` собирает `UmHudPanel::Gather` (`UI/UmHudPanels.{h,cpp}`, без мира) из показанных бойцов (`HudFighters`: HP держится до контакт + 80), `FS09PlayerPanel`, `FS09DeathStage`; `/Game/S08/UI/Hud/WBP_UI_HUD_PANEL_LOC` |
| 2. Аватар через `SetPortrait(Key)` из CP-08, нет PNG — монограмма и Warning | круг — `US08TurnPortraitWidget` (WBP_UmPortrait) в режиме панели (`AttachToPanel`, ВР-VS2-51): ключ — `heroSlug` проекции (как раньше в `TickTurnHud`), монограмма — имя героя панели («KA», «M») |
| 3. Литералы цвета `S08TurnPortraitWidget.cpp` → тема | `panel.bg`, `text.primary`, `turn.flash.yellow`, `text.secondary` из `UUmHudTheme`; цвета берутся заново при загрузке (собранный WBP_UmPortrait хранит цвета сборки), ВР-VS2-61 |
| 4. Помощники: Merlin — мини-портрет 32 и «7/7»; гарпии — три мини-портрета 32 с цифрой 1–3 на диске card.navy 14 и «1/1»; павший — насыщенность 0 и сердце павшего 24 рядом | `RebuildSidekicks`: мини-портрет — `M_UmPortraitDisc` (`UmPortrait::SetupDiscMid`, общий с кругом), гарпии через 64 su (128 / 192 / 256), цифра в углу (+21, +20); павший — `Desaturation` 1 и `resource-hp-fallen` 24 su (+34, +4); помощник, ушедший из проекции, остаётся павшим с 0 HP (ВР-VS2-55). Класс S — подсказка панели (ВР-VS2-56) |
| 5. Клик по портрету — панель колоды своей стороны (HB-28) | клик по панели через арбитр нажатий HUD (DE-014, `HUDPRESS`) → `ToggleDeckPanel(Own, "panel")` — нынешняя панель колоды до HB-28 (ВР-VS2-58) |
| 6. Строки hud.panel.status.own / .wait / .hp / .sidekick / .fallen | ST_Hud (HB-05): «ВАШ ХОД», «ЖДЁТ», «{hp}/{max}», «{name} {hp}/{max}», «ВНЕ ИГРЫ» (капс type.tag) |
| 7. SHOT widget id=UI-HUD-PANEL-LOC state=own\|wait\|fallen | `SHOT widget id=UI-HUD-PANEL-LOC impl=umg state=… bbox=<плашка> … hero=<имя> hp=<h/m> sidekicks=<n> fallen=<n> tracker=<shown/slots> ring=0\|1 avatar=0\|1 class=L\|S smoulder=<rest>` из `WriteUmHudShotLines`; `PORTRAIT … show=panel` как раньше |
| 8. Подключение: панель через UUmGameHud; старая колонка — только `-S08SlateHud=panels` | `FUmPanels::Build` в слоты `PanelLoc` / `PanelOpp` / `OppHand`; точки подключения в `S08FlowGameModeUmHud.cpp` (`BuildUmPanels`, `TickUmPanels`, `UmHudPanelLocRightSu`, кадр раскладки, SHOT) и `S08FlowGameModeTurnHud.cpp` (колонка Slate — под условием) |
| 9. Тесты Tree, Sidekicks (Merlin — 1, гарпии — 3), Monogram | `Unmatched.S08.Hud.PlayerPanel.Tree`, `.Sidekicks`, `.Monogram` (`S08/UI/UmHudPanelsTests.cpp`) |

Места (CX-09 `facts.json`, su): L 340×136 — окно кольца (4, 12, 104) вокруг круга 80, текст с x 128 (имя y 12
`type.heading` 24, статус y 38 `type.tag` 14, сердце 24 + HP `type.button` 20 на y 54), трекер 2×32 по правому краю 328
на y 50, помощники с y 82. S 240×96 — окно (4, 8, 80) вокруг круга 64, текст с x 92, сердце + HP на y 60, трекер 2×24
по правому краю 228. Имя длиннее 14 знаков — `type.button`. Статус хода гаснет за 120 мс (`icon.leave.ms`), затем новое
слово; reduced — сразу.

## Решения по делегированию (ВР-VS2-51…62, шаг B2)

- **ВР-VS2-51. Портрет — круг панели.** `US08TurnPortraitWidget::AttachToPanel` сворачивает собственную плашку и колонку
  текста портрета, сердце становится `HeartIcon` панели, значки трекера ложатся в `TrackerRow` панели. Логика кольца
  (AB-5), трекера (AB-7), ореола (AB-6) и креста (AB-8) остаётся в портрете, игровой режим ведёт её как раньше
  (`FeedTurnHud`, `TickTurnHud`); панель отвечает за текст, помощников, размеры класса. `SetPanelGeometry` — окно кольца,
  круг и слот трекера класса (L 104 / 80 / 32, S 80 / 64 / 24). Кольцо 104 su рисуется поверх края круга 80, как на
  макете (окно кольца по геометрии контракта 21/32 было бы 68 su).
- **ВР-VS2-52. `ring.smoulder` — токены темы.** `ring.smoulder` 0,35 (L, контракт, AB-5) и `ring.smoulder.s` 0,55 (S,
  предложение ВР-VS2-CX09-08, ВР-43) в `hud-style-tokens.json` → `S08HudTokens.generated.h` → `DA_UmHudTheme`.
  `US08AnimatedIconWidget::SetLayerRestOpacity` масштабирует дорожку прозрачности слоя `rim` так, что покой = токен; ключи,
  кривые и кадры контракта не меняются. Окончательное значение S — по живым кадрам 720p 150 % в шаге «Кадры» (G-READ обода
  ≥ 2,75 : 1).
- **ВР-VS2-53. Сердце соперника — `resource-hp-full`.** На макете CX-09 у PANEL-OPP вариант `resource-hp-full-enemy`; вид
  прогона I (AB-6, лично 2026-10-05) переезжает «без изменений» (HB-19) — у обеих сторон прежнее сердце.
- **ВР-VS2-54. Ход соперника — без слова статуса** (подтверждено ВР-VS2-CX09-07): ключа `hud.panel.status.opp` нет; ход
  соперника называет строка STATUS (HB-15, `ms.opp.phase.*`), на панели — кольцо и его трекер. Строка статуса остаётся
  на месте (Hidden), ряд HP не прыгает.
- **ВР-VS2-55. «Пал».** Герой и помощник — павшие с метки стадии смерти (контакт + 1100, `FS09DeathStage::HeartState` ≠
  Alive) или когда показанный боец мёртв без стадии (вход в партию посреди игры). Помощник, ушедший из проекции, остаётся
  павшим с 0 HP; новый id героя — новая партия, память помощников сбрасывается.
- **ВР-VS2-56. Помощники в классе S — подсказка UMG панели**, строки `hud.panel.sidekick`, у павших сердце павшего 24 su
  (у остальных — отступ той же ширины). Подсказка идёт за курсором, а не в фиксированный прямоугольник (16, 416) / (16, 472)
  макета (ВР-VS2-CX09-06): это стандартная подсказка UMG, поверх аватара ничего не рисуется.
- **ВР-VS2-57. Подсказка «HP {hp} из {max}» отложена.** Ключа в ST_Hud нет; новый ключ — пересборка ST_Hud и locres
  (бинарные файлы, которые трогают и другие ветки). Ключ добавляется одной сборкой строк в шаге, где строки собираются
  пакетом; до того у HP подсказки нет.
- **ВР-VS2-58. Клик по панели и рубашкам** — нынешняя панель колоды своей стороны / соперника (`ToggleDeckPanel`) через
  арбитр нажатий HUD, пока нет HB-28; ПКМ по рубашкам — инспектор с карточкой «скрытая» (`InspectCard`, лица нет).
- **ВР-VS2-59. OPP-HAND.** Рубашки слева на плашке `T_Skin_Panel` (x 12, y 4), шаг min(28, (ширина − 24 − 48) / (n − 1)):
  10 карт — 25,3 su в L и 16,4 su в S (как CX-09); перекрытие — отрицательный левый отступ в `UHorizontalBox`; высота
  слота S 104 su (дельта CX-09 к CX-01r, `UmHudLayout.cpp`). Подпись — «Рука {n} · колода {d} · сброс {s}», «≈» у колоды
  (`bDeckCountStale`); разделитель «·» — пунктуация (`INVTEXT`), слова из ST_Hud.
- **ВР-VS2-60. Текстура кольца.** Самый крупный экспорт `marker-turn-ring` — 64 px; окно 104 su (L 100 %) и 120 px
  (S 150 %) растягивают его (на листах мягко, читается). Экспорт 128 px слоёв кольца — отдельная карточка значков, здесь
  не меняется.
- **ВР-VS2-61. Колонка отката на токенах.** Цвета `S08TurnPortraitWidget.cpp` из темы и в откате `-S08SlateHud=panels`
  (`panel.bg` вместо `#161A28` 0,88; `text.secondary` вместо `#9A9EAC`); WBP_UmPortrait не пересобирался, цвета
  применяются при загрузке.
- **ВР-VS2-62. Звук добора соперника** — `CUE-005 hand.opp` (аудио, d73d504c) расходится с 04 §2.3 «CRD-DRAW у соперника —
  нет»; файл аудио-сессии в B2 не меняется, вопрос владельцу звука.
- Точки подключения в горячих файлах: `S08FlowGameModeTurnHud.cpp` +31 / −20 (из них 20 — перенос колонки Slate под
  условие с новым отступом), `S08FlowGameModeUmHud.cpp` +89 / −2 (файл точек подключения UMG HUD, как в B1: сборка,
  тик, кадр, SHOT, лист галереи), `S08FlowGameModeOpponent.cpp` +2 / −1, `S08FlowGameMode.h` +5.

## Проверки

- UE: `Unmatched.S08.Hud.*` 29/29 (новые PlayerPanel.Tree, .Sidekicks, .Monogram, .TurnLook, .OppMirror,
  OppHand.Fan); вместе с `Unmatched.S09.*`, `S08.ArtLook.*`, `S08.ArtHudUmg.*`, `S08.IconMotion.*` — 162/162; весь
  `Unmatched.S08` + `Unmatched.S10` — 308/308.
- pytest `tools/s08/hud_contract` 64/64 (новый `test_check_trace_panels_hb18_21`: строки LOC / OPP / OPP-HAND клиента
  проходят `check-trace` по состояниям 04 §7.1); `hud_contract.py validate` PASS (G-TOKENS, тема с новыми токенами).
- WBP: `ue_author_um_hud.py` (`UM_HUD_WBP_OVERWRITE=0`, прежние 9 WBP не тронуты) — `UM_HUD_WBP_PASS assets=12`;
  `hud_theme_import.py` — `DA_UmHudTheme` alphas=7, textureSkins=29.
- Листы галереи `-S08IconGallery -S08IconGalleryPanels=1|2` в editor `-game` (не упаковка): `gallery/sheet-<холст>-p<стр>.png`
  (цвет | серый Rec.709 | дейтеранопия), 1080p и 720p при 100 % и 150 %; стр. 1 — свой Medusa (гарпии) против
  King Arthur, стр. 2 — свой King Arthur (Merlin) против Medusa; трассы `gallery/trace-*.txt`. Фон листа — `fx.dust`,
  не доска; данные — числа прогона I из CX-09 (павший, 0 HP, 3 и 10 рубашек, «≈» — состояния листа). Открыты все
  восемь: аватары настоящие (CP-09…12), монограммы «M» / «KA» в состоянии «нет аватара», кольцо — вспышка +300 мс
  оранжевая, тлеющее в покое (S заметно ярче), трекер DE — манёвры Medusa / атаки Arthur, сердце урона с ореолом,
  павший — серый круг, сердце с крестом и «ВНЕ ИГРЫ»; гарпии 1–3 на дисках, «1/1» под каждой, павшая гарпия серая с
  сердцем рядом; Merlin с именем и «7/7». PANEL-OPP зеркальный: аватар справа, текст по правому краю, трекер снаружи слева,
  «ИИ ДУМАЕТ» с точкой. В сером «ВАШ ХОД» / «ЖДЁТ» / «ВНЕ ИГРЫ» различимы текстом, обод виден; в дейтеранопии
  оранжевый обод и жёлтый статус остаются отличимыми от серого «ЖДЁТ».

## Отложено (шаг «Кадры» VS-2, packaged)

- G-WIDGET `UI-HUD-PANEL-LOC own` и `wait` на обеих досках (Marmoreal original, Sarpedon original, шесть фигур v2), `fallen` —
  в партии до GAME_OVER (`tools/s09/run-combat-demo.ps1 -RequireGameOver`); наборы A и B 04 §7.2 (1080p 75 / 100 / 150 %,
  720p 100 / 150 %): аватар настоящий, `overlapField=0`, HP меняется в контакт + 80 (трасса `HUD-HEART`); цвет, серый,
  дейтеранопия; окончательное `ring.smoulder.s` по кадру 720p 150 %.
- Подсказка HP (ВР-VS2-57), экспорт кольца 128 px (ВР-VS2-60), звук добора соперника (ВР-VS2-62).
