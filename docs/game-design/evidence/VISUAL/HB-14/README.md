# HB-14 — TOP и связь: UUmHudTop, UUmConnectionBadge (шаг H6, часть)

VS-2 шаг B1, 2026-10-06, ветка `feat/visual-vs2` (worktree `C:/tmp/wt-visual`). Карточка — `docs/game-design/visual/06-tasks/hud.csv`
HB-14; спецификация — 04 §2.1, §4.3, §7.1, ВР-H17; макет — принятый CX-08 `art/imagegen/hud-topstrip-v1-codex/` (25a0c8d5).
Шаг B1 общий с HB-15 (STATUS) и HB-16 (BANNER): решения ВР-VS2-41…50 записаны здесь, README HB-15 и HB-16 ссылаются сюда.

**Статус:** код, WBP, тесты и лист галереи готовы; приёмочные кадры packaged на обеих досках и прогон связи через
`tools/s10/drop-graphql-reply-proxy.cjs` — шаг «Кадры» VS-2 (упаковки в этом шаге нет).
**Решение по арту:** вид принят по делегированию в CX-08 (HB-13); блок повторяет макет (лист `gallery/`).
**Флаг отката:** `-S08SlateHud=top` (или весь `-S08SlateHud`) — TOP не строится: до шага TOP не было вовсе.

## Что сделано

| Пункт карточки | Где |
|---|---|
| 1. UUmHudTop: MenuButton, Conn, TurnText, LogButton (только S); ApplyModel | `Source/Unmatched/S08/UI/UmHudTop.{h,cpp}` — плашка `T_Skin_Panel` во весь слот TOP (L 252×44, S 236×40), квадраты 44 / 40 su, «Ход {n}» `type.button` без капса; `/Game/S08/UI/Hud/WBP_UI_HUD_TOP` |
| 2. UUmConnectionBadge: online / syncing / lost по входу | `S08/UI/UmConnectionBadge.{h,cpp}`, `UmConnection::Resolve` (ВР-VS2-43); значки v3 `resource-connection-online / -reconnecting / -lost`, 24 su; смена — appear значка (online → lost — контрактный `appear_from_online`), у ↻ цикл 1200 мс после appear (reduced — без цикла); подсказка `hud.conn.*` через 300 мс наведения; нет значка — текст и трасса `ICON missing=<id> block=UI-HUD-CONN` (ВР-HB08); `/Game/S08/UI/Common/WBP_UmConnectionBadge` |
| 3. MenuButton = Esc без выбора → PAUSE | нажатие идёт через арбитр HUD (`HandleHudPressOutcome`: CUE-003, трасса `HUDPRESS`), затем `HUD-TOP press=menu target=UI-SCR-PAUSE pending=1` — экрана PAUSE ещё нет (SC-24, шаг H16), ВР-VS2-44 |
| 4. Строки | `hud.top.menu`, `hud.top.turn`, `hud.conn.online/.syncing/.lost`, `hud.top.log` — уже в ST_Hud (HB-05) |
| 5. SHOT widget | `SHOT widget id=UI-HUD-TOP state=idle … turn=<n> class=L|S menu=glyph|word log=0|1` (bbox — плашка) и `SHOT widget id=UI-HUD-CONN state=online|syncing|lost … icon=<id> anim=<…>` (bbox — чип); на каждом кадре-доказательстве из `WriteUmHudShotLines`; смена связи — `HUD-CONN state=… ready=… wasReady=… slow=… recovering=… seq=…` |
| 6. Слот Top в UUmGameHud | `S08/UI/UmTopStrip.{h,cpp}` (`FUmTopStrip`: строит TOP / STATUS / BANNER в слоты, кадр раскладки, тик) + точки подключения в `S08FlowGameModeUmHud.cpp`; `UUmGameHud::SetBlock` |
| 7. Тесты | `Unmatched.S08.Hud.Top.Tree`, `Unmatched.S08.Hud.Top.Conn` (`S08/UI/UmHudTopStripTests.cpp`) |

## Решения по делегированию (ВР-VS2-41…50, шаг B1)

- **ВР-VS2-41. Кегль токена `type.*` — высота em в su.** 02 §3.3 задаёт `type.banner` 36 su = 36 px на 1080p, а Slate
  рисует `FSlateFontInfo::Size` как пункты при 96 DPI (`FontConstants::RenderDPI`): тема HB-04 отдавала 24 → 32 px, весь
  текст UMG был на треть крупнее макетов (на 720p 150 % «Вас атакуют…» не помещалась бы даже в две строки). `UUmHudTheme::Font`
  теперь отдаёт Su × 72/96 пт (`UmHudTheme::PointsFromSu`). Затрагивает и кнопки HB-11, и портрет CP-08 — их кадры
  packaged ещё не сняты (шаг «Кадры»). Проверка: высота строки `type.heading` 24 su = 28 su (тест Status.Tree).
- **ВР-VS2-42. «Меню» и «Журнал» — глифы `ui-menu` (IC-53) и `ui-log` (IC-55)** на плоских кнопках `UUmButton`
  (`bFlat`: тела нет в покое, есть при наведении / нажатии / фокусе), слово `hud.top.menu` / `hud.top.log` — подсказка.
  ВР-VS2-HB13-07 («Меню» словом) принималось, когда глифа не было и рисовать его было нельзя; карточка HB-14 зависит
  от IC-53 / IC-55. Нет глифа — слово на кнопке и трасса `ICON missing` (ВР-HB08).
- **ВР-VS2-43. Состояние связи.** lost — поток матча уже был готов и `IsStreamReady` = false; до первого готового
  потока (вход, переподключение с нуля) — syncing, не «Связи нет»; syncing — `IsCommandSlow`, любая команда в полёте
  ≥ `CommandSlowSeconds` (3 с) или восстановление состояния (`IsAwaitingStateRecovery`, догоняем разрыв seq). Без
  порога ↻ мигал бы на каждой команде (100–300 мс).
- **ВР-VS2-44.** До PAUSE (SC-24, H16) и списка LOG класса S (H11) нажатие «≡» / «Журнал» отвечает (CUE-003, трасса
  `HUD-TOP press=menu|log … pending=1`) и ничего не открывает.
- **ВР-VS2-45 (HB-16). Баннер в классе S — y 72**, сразу под однострочным STATUS (16 + 48 + 8): на y 112 (прежний слот)
  и y 144 (карточка) плашка в S закрывает верхний ряд клеток (`FIELD` начинается с ~153 su на 720p 150 % и ~172 su на
  1080p 150 %; предложение ревью CX-08). В L — y 144 по 04. Тест Root.Layout: баннер не пересекает ни `FIELD` обеих
  досок, ни STATUS на всех четырёх холстах.
- **ВР-VS2-46 (HB-15). Раскладка STATUS.** Ширина капсулы — по реально нарисованной строке (авто-ширина, предел
  880 / 720 / 600 su): при заданной ширине по замеру шрифта чипы клавиш упирались в край (+7 su на листе галереи).
  Строки ломает клиент (явные переводы строк, NBSP в «…»), шаг строк 1,25 × кегль, отступ сверху и снизу
  (48 − 30) / 2 = 9 su: одна строка 48 su, две — 78 su (как CX-08); затем 20 и 16 su, затем «…» и полный текст в
  подсказке (капсула тогда ловит наведение). Высота слота STATUS идёт за блоком (`UmGameHudSlots::HeightFollowsBlock`),
  в S прямоугольник STATUS 600×48 (было 600×40).
- **ВР-VS2-47 (HB-15). Движение STATUS.** Новый текст проявляется 0,15 → 1 за 120 мс (reduced — 100 мс), второго
  TextBlock нет; точка хода соперника пульсирует 1 → 0,35 → 1 с частотой 1 Гц (reduced — статична).
- **ВР-VS2-48 (HB-15). Состояние SHOT строки:** sync — `why.syncing`; defend / discard / choice — режим команды
  (`CombatDefense`, `DiscardDraft`, `PendingChoice`); opp — `ms.status.opp` и ожидание соперника (`why.wait.defender`,
  `why.wait.opponent.choice`); остальное — own. Глагол соперника — RU-текст `ms.opp.phase.*` из ST_Ms, имя — данные.
  Чипы клавиш (ВР-H09) — по ключу строки (action → M A G, defend → N, …), только при UI-ACC-017; режим даёт HB-43, до
  него чипов нет.
- **ВР-VS2-49 (HB-16).** Кадр 0 мс баннера — 0,15 (правило DE-023 «кадр 0 не пустой», `FS09TurnCue`); «0 мс → 0»
  карточки — кадр до старта. 100 / 450 / 600 мс → 1 / 1 / 0 без изменений.
- **ВР-VS2-50. G-WIDGET знает 04 §7.1.** `hud_contract.py check-trace` берёт UI-ID и из `docs/game-design/visual/04-hud-spec.md`
  (UI-HUD-STATUS, -BANNER в 02-ux-ui-spec нет) и проверяет состояние по списку §7.1 (`count=<n>`, `mode=<a|b>` —
  шаблоны).
- Шрифты WBP: `FSlateFontInfo` темы — составной шрифт без UObject, WBP его не сохраняет (текст рисовался «тофу» на
  первом листе галереи), блоки берут шрифт из темы при каждой загрузке; тест проверяет это на WBP.

## Проверки

- UE: `Unmatched.S08.Hud.*` 23/23 (новые Top.Tree, Top.Conn, Status.Tree, Status.Keys, Banner.Alpha; Root.Layout с
  баннером против `FIELD`); вместе с `Unmatched.S09.*`, `S08.ArtLook.*`, `S08.ArtHudUmg.*`, `S08.IconMotion.*` — 156/156
  (`S09.HudPress.Umg` — 0 потерь после правки `UUmButton`); весь `Unmatched.S08` + `Unmatched.S10` — 302/302.
- pytest `tools/s08/hud_contract` 63/63 (новый `test_check_trace_topstrip_hb14_16`); `hud_contract.py validate` PASS (G-TOKENS).
- WBP: `ue_author_um_hud.py` (`UM_HUD_WBP_OVERWRITE=0`, прежние 5 WBP не тронуты) — `UM_HUD_WBP_PASS assets=9`.
- Лист галереи `-S08IconGallery -S08IconGalleryTopStrip` в editor `-game` (не упаковка), 1080p и 720p при 100 % и 150 %:
  `gallery/sheet-*.png` (цвет | серый), трассы `gallery/trace-*.txt`. Открыты все четыре: TOP — глиф «≡», столбики /
  ↻ / X различимы в сером, «Ход 7», в S справа глиф журнала; ширины STATUS как в CX-08 (608 / 482 / 369 / 480 / 204 su),
  защита в S — две строки, «Без защиты» целиком; баннер «ВАШ ХОД» жёлтым на navy-плашке. Фон листа — `fx.dust`, не доска.

## Отложено (шаг «Кадры» VS-2, packaged)

- G-WIDGET на кадрах обеих досок (Marmoreal original, Sarpedon original, шесть фигур v2), 1080p 100 / 150 %, 720p 100 / 150 %:
  `UI-HUD-TOP idle`, `UI-HUD-CONN online`; `syncing` и `lost` — прогон через `tools/s10/drop-graphql-reply-proxy.cjs`;
  TOP не пересекает `FIELD`; цвет и серый.
- Звуки `UI-NET-LOST` / `UI-NET-BACK` при смене связи — не в «do» карточки, отдельно.

## Кадры VS-2 (2026-10-07, упаковка `230b2b0d`)

Кадры выхода и гейты — [VS-2](../VS-2/README.md). Прогоны `run-combat-demo -PlayerView -S08ExitShots` на Marmoreal original (`-ConceptPaste` до EN-13) и Sarpedon original, шесть фигур v2, 1080p 75 / 100 / 150 %, 720p 100 / 150 %; vs-ai `-PlayerView`. Листы цвет / серый / дейтеранопия — `sheet-0*.png` (`sheet.py`, вырезки по трассовым bbox). Все кадры и листы открыты (Read).

- **Решение:** художественно принято, по делегированию (2026-10-07) — состояния `idle` / `online` на обеих досках и всех холстах.
- TOP: плашка, связь и «Ход n», класс S с кнопкой «Журнал». В сером и при дейтеранопии читается. TOP не пересекает FIELD: `overlapField=0`. Командная Slate-панель больше не лежит под TOP (ВР-VS2-73).
- G-WIDGET: `UI-HUD-TOP idle` и `UI-HUD-CONN online` есть во всех прогонах, ошибок 0. `lost` встретилось только в трассе vs-ai-abort.
- **Не снято:** `syncing` / `lost` через `drop-graphql-reply-proxy.cjs` (VS-2, «Открыто», п. 4).

## Кадры выхода VS-4 (HB-49, упаковка `5a74a81e`, 2026-10-07)

Живые партии приёмочной упаковки, Marmoreal original (`-ConceptPaste` до EN-13, пометка) и Sarpedon original, шесть фигур v2, слоя отладки нет; прогоны, гейты и листы — [HB-49](../HB-49/README.md) (картинки со сканами и доской — вне git, `scraped-data/derived/visual-evidence/HB-49/`, ВР-VS4-01).

`lost` снят в каждой партии (переподключение потока в начале матча, ~0,5 с; рядом Slate-строка «RECONNECTING …» — H14, VS-7). **`syncing` не снят:** клиент снимает команду «в полёте» по снимку из потока раньше задержанного ответа мутации (`hb14-marm-1080-100`, прокси держал `beginManeuver` 5 с). Открыто — стенд с задержкой потока.
