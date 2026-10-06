# HB-21 — рука соперника рубашками: UUmHudOppHand

VS-2 шаг B2, 2026-10-06, ветка `feat/visual-vs2`. Карточка — `06-tasks/hud.csv` HB-21; спецификация — 04 §2.3, §7.1; 02 §6.2,
§6.4 (рубашка 48×67, ВР-50); макет — CX-09 (принят по делегированию). Решения шага — ВР-VS2-51…62 в
[README HB-18](../HB-18/README.md) (для этой карточки — 58, 59, 62).

**Статус:** код, WBP, тест, листы галереи готовы; кадры packaged (набор B, оба клиента) — шаг «Кадры» VS-2.
**Флаг отката:** `-S08SlateHud=opphand` — блока нет (до HB-21 рука соперника была только отладочной строкой `opponent:` под
`-S09Markers`, HB-02).

## Что сделано

| Пункт карточки | Где |
|---|---|
| 1. UUmHudOppHand: Backs (UHorizontalBox, пул UImage 48×67), Caption; ApplyModel из OpponentPanel | `Source/Unmatched/S08/UI/UmHudOppHand.{h,cpp}`; модель `FUmOppHandModel` (HandCount, DeckCount, Discard, bDeckCountStale, герой соперника, ширина слота) собирает `FUmPanels::Tick`; плашка `T_Skin_Panel`, рубашки с x 12, y 4, шаг ВР-VS2-59; `/Game/S08/UI/Hud/WBP_UI_HUD_OPP_HAND` |
| 2. Текстура — рубашка героя соперника (CP-05 King Arthur, CP-06 Medusa); до импорта — плоская рубашка-фолбэк и Warning | `UmCardMedia::FindBack(<heroSlug>)` — `T_CardBack_king_arthur` / `T_CardBack_medusa`, UV исходника в паддинге; нет рубашки — `T_Skin_Panel` 48×67 со значком `resource-card` 24 su и `OPPHAND back fallback hero=… reason=…` |
| 3. Клик по рубашкам или подписи — панель колоды соперника (HB-28); ПКМ — инспектор «Скрытая информация» | арбитр нажатий HUD → `ToggleDeckPanel(Opponent, "panel")`; ПКМ → `InspectCard` скрытой карты (лица нет), ВР-VS2-58 |
| 4. Строки hud.opp.hand, .deck, .discard, .stale | «Рука {n} · колода {d} · сброс {s}», «≈{d}» при `bDeckCountStale` (`UmHudOppHand::Caption`) |
| 5. SHOT widget id=UI-HUD-OPP-HAND state=count=<n> | `SHOT widget id=UI-HUD-OPP-HAND impl=umg state=count=<n> … deck=<d> discard=<s> stale=0\|1 step=<su> width=<su> fan=<su> back=<текстура\|fallback>` |
| 6. Отладочная строка opponent: — только -S09Markers | уже так с HB-02 (`bDebugLines`) |
| 7. Тест Unmatched.S08.Hud.OppHand.Fan (0, 5, 10, 12 карт: ширина ≤ 300 su) | шаг и ширина веера для 0 / 5 / 10 / 12 карт в слотах 300 / 220 / 201 su (с отступами не шире слота), 10 карт — 25,3 и 16,4 su как CX-09; WBP; подпись RU и «≈»; новая рубашка въезжает за 180 мс (0,15 → 1, −12 → 0 su), ушедшая гаснет за 120 мс и уходит из ряда; рубашки обоих героев и фолбэк; SHOT `count=12` |

Движение: `icon.appear.ms` 180 и `icon.leave.ms` 120 из темы, reduced — только прозрачность ≤ 100 мс; первая модель (вход в
партию) — рука сразу в покое. Звука добора у блока нет (`CRD-DRAW` соперника не играется отсюда; про `CUE-005 hand.opp`
аудио — ВР-VS2-62).

## Проверки

- `Unmatched.S08.Hud.OppHand.Fan` зелёный; `Root.Layout` — слот OPP-HAND в S 220×104 (дельта CX-09).
- Листы [HB-18/gallery](../HB-18/gallery/): 3 / 5 / 10 рубашек и «≈» — рубашка King Arthur (стр. 1) и Medusa (стр. 2) целиком,
  перекрытие слева направо, последняя внутри плашки; подпись в одну строку на всех четырёх холстах; лица карт нет.

## Отложено (шаг «Кадры»)

- G-WIDGET `count=<n>` = `HandCount` снапшота на обоих клиентах; кадры набора B: рубашки не пересекают `FIELD` и PANEL-OPP
  (ширина слота сужается до места справа от поля, ВР-VS2-10); mip рубашек на 48×67 — по кадру packaged.
