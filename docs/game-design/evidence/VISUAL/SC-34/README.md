# SC-34 — GAMEOVER: победа (`UUmScreenGameOver`)

VS-7, шаг S5, 2026-10-08, ветка `feat/visual-vs7` (worktree `C:/tmp/wt-visual`). Карточка — `screens.csv` SC-34; 04 §1.10
(H14); принятый макет CX-34 `art/imagegen/sc34-gameover-victory-codex/` (ВР-VS5-SC34-01…09). Состояния того же экрана —
[SC-35](../SC-35/README.md) поражение, [SC-36](../SC-36/README.md) «Посмотреть доску», [SC-37](../SC-37/README.md) «Сыграть
ещё»; здесь — общее для четырёх карточек. Сборки, тесты строк и WBP — [SC-31](../SC-31/README.md) (один шаг).

**Статус:** UE-часть готова, живая проверка editor-build (`s5a` 1080p VS_AI Marmoreal, `s5h` 720p VS_AI Sarpedon, бенч `s5e`
/ `s5f` / `s5g`), по делегированию. Набор F packaged с `RENDER`, листы, G-READ / G-GRAY / G-LOOK, G-CUE удар → экран на
packaged, бюджет и реестр 03 — шаг «Кадры». **Откат:** `-S08SlateHud=gameover` — Slate-модаль DE-029 как раньше.

## Что сделано (`do`)

| Пункт | Где и как |
|---|---|
| Экран | `UUmScreenGameOver : UUmModalBase` (`S08/UI/UmScreenGameOver.h/.cpp`), WBP `/Game/S08/UI/Screens/WBP_UI_SCR_GAMEOVER`, в `Modals` корня. BindWidget `ResultModal`, `OutcomeText`, `HeadlineText`, `ReasonText`, `TurnText`, `LeftPortrait`, `RightPortrait`, `VersusText`, `LeftName`, `RightName`, `LeftCaption`, `RightCaption` (+ `LeftVerdict`, `RightVerdict`, `LeftHeart`, `RightHeart`), `ViewBoardButton`, `AgainButton`, `LobbyButton`, `BoardStrip`, `StripText`, `ResultsButton`, `StripLobbyButton`. |
| Данные | `FS09ResultSummary` (исход, герой-победитель — не добивший боец, SD-45; причина по HP проигравшего; ход; `endedAt − startedAt`), `FS09HudModel` (victory / defeat / draw / unknown), `FS09ResultView` (results / board); роль соперника в VS_AI — ник бота из строки комнаты (ВР-VS5-SC37-01). Имена героев — как в данных (`Hero.name`, ВР-VS5-SC34-01). |
| Раскладка | ВР-VS5-SC34-03: модаль 760×580 (класс S 680×560; VS_AI в S 760×560, ВР-VS5-SC37-06), скин `modal`, вуаль 0,6; «ПОБЕДА» `type.display` `turn.flash.yellow` y 32; «MEDUSA ПОБЕЖДАЕТ» `type.title` `card.cream` y 96; причина y 140; «Ход 19 · 0:35» y 168; портреты 120 su по ±180 su (S ±160), «против»; подписи «Вы · HP 12/16 · » + «Победитель» (`turn.flash.yellow`) / «AI Bot · HP 0/27 · Повержен» + сердце павшего 24 su; проигравший — насыщенность 0, прозрачность 0,6 (`EUmPortraitState::Loser`), без красного; кнопки y 500 (S 480): «ПОСМОТРЕТЬ ДОСКУ» + V, [VS_AI «СЫГРАТЬ ЕЩЁ»], «В ЛОББИ» + Enter — единственная главная; чипы клавиш — по HB-43 (Авто — только пока нет завершённых партий). |
| Вход / выход | DE-019: экран ждёт ухода павшего героя + 1000 мс (`FS09ResultGate`, без изменений); появление 500 мс и кроссфейд 250 мс — `FS09ResultView` (ВР-VS7-62); грейд CUE-016 и стинги `STG-WIN-…` / `STG-LOSE-…` звучат сами (VS-6 / AU-S), экран их не вызывает. «В лобби», Enter, Esc, L → `ReturnToLobbyCommand` (`leaveGame`) → LOBBY; автозакрытия нет. |
| Slate | модаль DE-029 и её полоса остаются собранными, но скрыты (`UmGameOverOnUmg` в `TickResultScreen`); трассы `RESULT summary` / `RESULT view` не менялись. |
| Трасса | `SHOT widget id=UI-SCR-GAMEOVER impl=umg state=<victory|defeat|draw|unknown|board|again> bbox=<модаль или полоса> … mode=<1v1|vs_ai> chips=0|1 primary=1 overlapField=<px²>`. |
| Гейты S10 | `tools/s10/run-vs-ai-demo.ps1`: по умолчанию — `Test-GameOverWidget` (строка `SHOT widget id=UI-SCR-GAMEOVER` с состоянием исхода из строки `RESULT`, нарисованная и видимая, после `RESULT screen` и до `LEFT room=`); `-S09Markers` — откат к пиксельным гейтам GD-036 (04 §5.3); самотест PASS (5 новых проверок). |

## Решения по делегированию (шаг S5)

| № | Решение | Почему |
|---|---|---|
| ВР-VS7-62 | Появление и кроссфейд — часы `FS09ResultView` (500 мс / 250 мс), «400 мс» карточки — в пределах «вход ≈ 500 мс» | одна шкала с трассой `RESULT view intro=500 fade=250`, гейты её читают |
| ВР-VS7-63 | Чипы V / Enter в режиме «Авто» решаются по партиям, завершённым до этой (открытие экрана само засчитывает партию, HB-43) | иначе чипы гасли бы в первом же кадре первой партии |
| ВР-VS7-65 | `state=board` — bbox полосы; `state=again` — пока идёт «Сыграть ещё»; строка `HUD-LAYOUT class= canvas= field= overlapField=` для полосы (формат гейта G-WIDGET) | 04 §4.5, гейт `check-trace` |
| ВР-VS7-68 | Гейты S10 — по строкам `SHOT widget` (UI-SCR-GAMEOVER / UI-SCR-ABORTED), `-S09Markers` — откат на пиксели; пиксельные проверки лобби — только с `-S09Markers` (за UMG-лобби стоит сцена меню SC-02, гейт ярких пикселей к ней неприменим) | 04 §5.3, как HB-48 для дуэли |

## Проверка

- Тесты `Unmatched.S08.Hud.Screens.GameOver.Tree` (код и WBP): данные прогона I (тестовые копии): «ПОБЕДА», «MEDUSA ПОБЕЖДАЕТ»,
  «King Arthur: HP достигли 0», «Ход 11 · 0:27», подписи «Вы · HP 11/16 · Победитель» / «Соперник · HP 0/18 · Повержен», сердце
  у проигравшего, 1×1 без «Сыграть ещё», одна главная, нажатия; поражение, ничья, VS_AI, полоса; модаль и полоса внутри 1080p,
  720p, 720p 150 %. `.GameOver.Model`: цепочка «Сыграть ещё», `Duration`, состояния, размеры модали. `S09.ResultScreen.*` PASS.
- Живой `s5a` (1080p, VS_AI, Marmoreal original, Medusa против T. Rex — бот; `-S09Flow -S09Combat=attack+scheme` ведёт бой):
  `RESULT summary outcome=VICTORY winnerHero=Medusa loserHero=T._Rex reason=hp0 turn=19 duration=35`, `RESULT screen … wait=4455`
  (DE-019, без изменений), `SHOT … state=victory`, затем board и again. `s5h` (720p, Sarpedon): победа, ход 20, 0:35.
- Открыты (Read): victory (`s5a`, `s5h`), board, again (`s5a`), again-busy (`s5h`), бенчи defeat 720p (`s5d`, `s5e`), board
  (`s5f` 1080p Marmoreal, `s5g` 720p Sarpedon). После `s5a`: «Сыграть ещё» в ожидании показывала общий «Отправлено…», «В лобби»
  гасла — исправлено (`s5h`); после `s5d`: подпись на 720p резалась («· » терялся) — исправлено (`s5e`).
- G-CUE: `cue_contract.py check-trace` на `s5a` — FAIL G2 / G4 / C2 / A1 на второй партии после «Сыграть ещё» (выход клиента
  посреди постановки, номера seq второй партии); `hit_to_screen` 1455 мс в сводке. Замер удар → экран 3,1 ± 0,2 с — на packaged
  в «Кадрах» (сбои G-CUE прогонов со снимками — ВР-VS6-51).
- G-WIDGET: `check-trace` на `s5a` — FAIL только на строках `plate*` (мировой слой: снимки S09 `-S09Flow` в кадре до раскладки
  табличек), все строки `UI-SCR-*` проходят; без строк `plate` остаётся одна старая строка `HUD-LAYOUT` полосы до правки
  формата (исправлено, `s5g` PASS).

## Кадры

Модаль GAMEOVER несёт портреты (аватары) — полные кадры только в `scraped-data/derived/visual-evidence/SC-34…SC-37/` (индексы);
в git — JPEG без аватаров: `gameover-victory-head-1080p-100.jpg` (верх модали до портретов).

## Не сделано в этом шаге

- Набор F packaged, листы цвет / серый / дейтеранопия, G-READ / G-GRAY / G-LOOK, G-CUE на packaged, бюджет, реестр 03 и
  статусы `screens.csv` — шаг «Кадры»; packaged-прогоны `run-vs-ai-demo.ps1` / `run-vs-ai-abort-demo.ps1` с новыми гейтами — там же
  (в этом шаге упаковки нет; гейты проверены самотестами).
- Кадр draw живьём (настоящей ничьей нет) — только тест.
- У T. Rex нет кропа CP-07: диск — монограмма «TR» (фолбэк CP-08, на navy-модали почти не виден); дельта CP-07 из пакета SC-37
  (кроп `cx 0.58, cy 0.33, d 0.64`) не импортирована — открытый пункт.
