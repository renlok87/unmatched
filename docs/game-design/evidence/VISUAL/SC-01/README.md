# SC-01 (UE-часть) — основа экранов и модалей: UUmScreenBase, UUmModalBase, UUmConfirmDialog, съёмка по SHOT

VS-3, шаг U4 (план VS-3 п. 5), 2026-10-07, ветка `feat/visual-vs3` (worktree `C:/tmp/wt-visual`). Карточка —
`screens.csv` SC-01 (часть «UE»); 04 §1 (общее), §3.1–§3.6, §4.1–§4.5, §5.1; ВР-H14, ВР-SC04, ВР-SC05, ВР-SC14; принятый
макет CX-22 `art/imagegen/sc01-screen-base-codex/` («SC-01 … accepted» есть в git log: `2ddb5193`, `897c7114`) —
модаль 640×360, кнопки 168×48 справа внизу, поля 16 su, вуаль 0,6 (ВР-VS3-SC01-01…10).

**Статус:** базы, диалог (WBP), ключи экранов `-S08SlateHud`, `-S08ScreenShots` и ключ `-ScreenShots` двух сценариев,
строки, тесты и лист модали-образца готовы. Код — коммит `05c3e3dd` (с H9). Экранов на этой базе ещё нет (BOOT…ABORTED,
INSPECT, PAUSE — VS-4 / VS-7); маршрут Esc в игровом режиме подключается с PAUSE (SC-24, H16). Приёмка — по делегированию.
**Откат:** ключи `-S08SlateHud=boot|login|lobby|room|loading|menubg|inspect|pause|reconnect|gameover|aborted` (ВР-SC04)
известны разбору и `ARTLOOK hudImpl=` — каждый экран держит Slate-вид, пока его шаг не построит его на этой базе.

## Что сделано (`do`, часть UE)

| Пункт | Где и как |
|---|---|
| `UUmScreenBase : UUserWidget`, `UUmModalBase : UUmScreenBase` (абстрактные, без своего WBP) | `S08/UI/UmScreenBase.{h,cpp}`. BindWidget `Veil` (UImage, `panel.veil` 0,6 — затемнение живой сцены, без размытия, HUD-RULES П2), `Frame` (UBorder, скин `modal`: `panel.bg` 1,0, `radius.l`), `Body` (UNamedSlot); поля `UiId`, `ScreenState`; `SetScreenState`, `PlayShow` / `PlayHide`, `BuildDefaultTree`, `CollectShotLines`, `SetCanvas` (класс L / S, px на su), `FrameRectSu` (по центру, не дальше безопасных полей 24 / 16 su). Вуаль ловит указатель: ввод вне модали закрыт, клик мимо рамки — `OnVeilClick`. |
| Тайминг (04 §1, ВР-SC05) | экран: проявление 250 мс, уход сразу (поверх проявляется следующий); модаль: 250 / 120 мс; reduced motion — 100 мс прозрачностью. |
| Esc (04 §1) | `UmScreens::RouteEscape(открытых модалей, есть выбор)`: верхняя модаль закрывается → снимается выбор → PAUSE. Диалог: `HandleEscape` = «Отмена». |
| `SHOT widget` (04 §4.5) | `SHOT widget id=<UI-ID> impl=umg state=<state> fighter=none bbox=(x,y,w,h) geom=painted visible=1 twin=0 source=<путь WBP> modal=0\|1 class=L\|S alpha=` — модаль — рамка, экран — весь холст. |
| `UUmConfirmDialog` (`S08/UI/UmConfirmDialog.{h,cpp}`, WBP `/Game/S08/UI/Common/WBP_UmConfirmDialog`) | BindWidget `Title`, `Message`, `Confirm`, `Cancel` (+ базовые): заголовок type.title и сообщение type.body в 16 su от левого и верхнего края рамки 640×360; «ОТМЕНА» (`common.confirm.cancel`, обычная) и «ДА» (`common.confirm.yes`, единственная главная окна) 168×48 справа внизу, 16 su между ними и от рамки (SC-01 base-modal). Ответ — один раз: «Да» → `OnConfirm`; «Отмена», Esc, клик мимо → `OnCancel`; затем уход 120 мс. Нажатия — арбитр (DE-014). Строка SHOT — UI-ID экрана-владельца с `state=confirm` (ВР-SC11: UI-SCR-PAUSE confirm). |
| Строки | `common.confirm.yes` «Да» / «Yes», `common.confirm.cancel` «Отмена» / «Cancel» в `st-screens.csv` → ST_Screens и locres (`hud_strings_build.py`). |
| `-S08UiScale=<75..150>` | уже есть (HB-09, `UmHudScale`): 1280×720 при 150 % → 1138×640 su, класс S — тест `.Scale` и строка `HUD-LAYOUT class=S canvas=1138x640`. |
| Ключи экранов `-S08SlateHud` (ВР-SC04) | `S08ArtLook::SlateHudKeys` + boot, login, lobby, room, loading, menubg, pause, reconnect, gameover, aborted (inspect был); тест `.Root.Flag` — 31 известный ключ. |
| `-S08ScreenShots` (ВР-SC14, очередь кадров I-03) | `TickUmScreenShots`: первое появление каждой пары UI-SCR-* id + состояние в прогоне ставит один кадр `<UI-ID>-<state>.png` в `-S09ShotDir` (трасса `SCREENSHOT id= state= file=`); сегодня это UI-SCR-GAME (own / opp / combat / pending / over) и любой показанный экран / модаль базы. Ключ `-ScreenShots` в `tools/s09/run-combat-demo.ps1` (оба клиента) и `tools/s10/run-vs-ai-demo.ps1`. |
| Тесты | `Unmatched.S08.Hud.Screens.Base.Tree`, `.Shot`, `.Scale` (`S08/UI/UmScreenBaseTests.cpp`). |

## Решения по делегированию

| № | Решение | Почему |
|---|---|---|
| ВР-VS3-58 | Текст сообщения диалога — BindWidget `Message`; `Body` (04 §4.3) — именованный слот базы, в нём содержимое диалога | `UUmConfirmDialog` наследует `UUmScreenBase`, у которого `Body` — UNamedSlot (SC-01 do); два виджета с одним именем в дереве невозможны |
| ВР-VS3-63 | Экран уходит сразу, модаль — 120 мс; вуаль ловит указатель, клик вне рамки — `OnVeilClick` (диалог: «Отмена»); маршрут Esc — чистая функция, подключение к игровому Esc — с PAUSE | 04 §1 «экраны сменяют друг друга», ВР-SC05; ввод вне модали закрыт (SC-01 do) |
| ВР-VS3-64 | `-S08ScreenShots` снимает по одному кадру на пару id + состояние за прогон, по одному запросу на кадр; каталог — `-S09ShotDir` сценария | ВР-SC14: кадры экранов — packaged-клиент по строкам SHOT, без отдельного каталога |
| ВР-VS3-67 | ST_Screens / ST_Why и locres собраны шагами `hud_strings_build.py build` (ассеты + GatherText) без его проверки ключей 04: она падает на чужом `hud.log.turn` (будущий ключ HB-38, VS-4); все прочие проверки PASS, diff `Game.po` — ровно три новых ключа | не трогать чужой ключ 04 ради сборки; обёртка `C:/tmp/visual/VS3-U4/strings_build_nocheck.py` |

## Проверки

- Тесты `Screens.Base.Tree` (дерево кода и WBP, одна главная, «Да» / «Отмена»), `.Shot` (строка 04 §4.5, рамка 1080p
  (640, 360, 640, 360), 250 / 120 / 100 мс, один ответ, Esc), `.Scale` (1138×640 класс S, поля 24 / 16, рамка внутри полей
  на 1080p 75 / 100 / 150 % и 720p 100 / 150 %) — PASS; сборка и прочие гейты — [HB-30](../HB-30/README.md#проверки).
- Лист модали-образца (`-S08IconGalleryConfirm=marmoreal|sarpedon`: «Покинуть партию» / «Партия прервётся для обоих
  игроков» над кадром K1 под вуалью 0,6) на 1080p 100 % и 720p 150 % обеих досок — `check-trace` PASS (5 строк SHOT
  каждый, `UI-SCR-PAUSE state=confirm modal=1`).

- В git: `confirm-plain-1080-100-contact-colour.png` (`5498b742…`), `-grey.png` (`c7988c2e…`) — модаль без картинки доски
  (фон `panel.bg.inset`): «Покинуть партию», «Партия прервётся для обоих игроков», «ОТМЕНА» и жёлтая «ДА» справа внизу.
- Вне git: `scraped-data/derived/visual-evidence/HB-30/confirm-{marm,sarp}-{1080-100,720-150}-contact-*.png` (кадр K1 под
  вуалью; sha256 — [`../HB-30/sheets-sha.json`](../HB-30/sheets-sha.json)). Видно: вуаль 0,6 затемняет сцену без
  размытия, рамка 640×360 по центру, текст в 16 su от краёв, кнопки 168×48 с полями 16 su; на 720p 150 % (класс S) рамка
  внутри безопасных полей.

## Что не сделано в этом шаге

- Экраны на базе (BOOT…ABORTED, INSPECT, PAUSE) и подключение Esc / модалей к игровому режиму — их шаги (VS-4 H13, VS-7).
- Кадры `-S08ScreenShots` живого клиента (UI-SCR-GAME-*.png) — шаг «Кадры» (сценарии получили `-ScreenShots`).
- Граница модали к светлым участкам заднику ниже 3 : 1 местами — свойство токенов (ВР-VS3-SC01-10); на кадре движка
  граница видна (лист), подъём кромки `T_Skin_Modal` — не понадобился.

## Кадры выхода VS-3 (2026-10-07, упаковка `c9dac400`)

Живая партия двух клиентов `run-combat-demo -PlayerView -S08ExitShots` без `-S09Markers`, по 30 FPS у клиента, на приёмочной упаковке шага (`BuildStamp` `c9dac400`, `sourceHash` `0eaad2a3…`). Доски — Marmoreal original (с `-ConceptPaste` до EN-13, пометка) и Sarpedon original (lit3d), шесть фигур v2 (`v2=6`), слоя отладки нет (`ARTLOOK markers=0`). Сводка шага, гейты и открытые пункты — [VS-3](../VS-3/README.md).

Листы `tools/art/visual/sheet.py` (цвет / серый Rec.709 / дейтеранопия): `sheet-NN-*.png` — вне git, `scraped-data/derived/visual-evidence/SC-01/exit-vs3/` в worktree `C:/tmp/wt-visual` (индекс с sha256 — `scraped-data/derived/visual-evidence/VS3-exit-index.json`): на них сканы, рубашки и аватары нашего клиента (ВР-48, ВР-CP12, 02 §12; ревью VS-3, ВР-VS3-R01). В этой папке — `sheet-manifest.json` с sha256 каждого листа; в git из кадров выхода — только контактные листы [VS-3/contact](../VS-3/contact/).

Кадры `-S08ScreenShots` живого клиента: `UI-SCR-GAME-own / -opp / -combat / -pending / -over.png` (Marmoreal и Sarpedon, 1080p 100 %); открыт кадр `combat` — экран GAME с блоками VS-2 / VS-3, модалей в партии шага нет.

**Ревью VS-3 (2026-10-07, единый проход):** основа принята, по делегированию: модаль-образец «Покинуть партию» совпадает с принятым макетом CX-22 (640×360, «ОТМЕНА» / «ДА» 168×48), откаты экранов в `ARTLOOK hudImpl`; экраны на базе — VS-4 / VS-7.
