# SC-19 — Загрузка партии: этапы (`UUmScreenLoading`, `UI-SCR-LOADING`)

VS-7, шаг S3, 2026-10-08, коммит `323599df`. Карточка — `screens.csv` SC-19; 04 §1.5 (новый ID `UI-SCR-LOADING`), H15; макет
CX-31 `art/imagegen/sc19-loading-codex/` (ВР-VS5-SC19-01…08). Общие сборки и гейты — [SC-14](../SC-14/README.md).

**Статус:** UE-часть готова, живая проверка editor-build на Marmoreal и Sarpedon, по делегированию. Набор G packaged, листы —
шаг «Кадры». **Откат:** `-S08SlateHud=loading` — экрана нет, партия показывается как раньше.

| Пункт | Где и как |
|---|---|
| Экран | `UUmScreenLoading : UUmScreenBase` (`S08/UI/UmScreenLoading.h/.cpp`), WBP `/Game/S08/UI/Screens/WBP_UI_SCR_LOADING`: одна панель `LoadingPanel` 624×494 su по центру (те же su на всех холстах): строка этапа (`Spinner` 48 su HB-47 + `StageText` `type.title`, ширина группы — по самой длинной подписи), `LeftCard` / `RightCard` 240×320 (`panel.inset`, портрет 160 su CP-07 `show=loading`, имя `type.heading`, ник `type.caption`; свой герой слева), «против», имя доски из `boardList`. |
| Этапы | `connect` «Подключение к партии…» — новый запрос `gameSequence(gameId)` (`FS08FlowController::FetchGameSequence`); `state` «Загрузка состояния…» — до первого применённого снапшота (`gameState` / поток); `board` «Подготовка поля…» — до доски с фигурами (`AS08BoardActor::GetFighters` 3 кадра подряд); затем GAME, `STG-MATCH-START` звучит сам. Каждый этап ≥ 600 мс (ВР-VS7-31). Показ — после отсчёта ROOM, при возврате из BOOT (SC-05) и из LOBBY. |
| Трасса | `LOADING shown game=<id> board=<id> players=<n>`, `LOADING sequence request|answered`, `LOADING stage=<state|board> t=<мс>`, `LOADING done t=<мс> fighters=<n>`, `SHOT widget id=UI-SCR-LOADING impl=umg state=<connect|state|board|error> … board= heroes= primary= veil=` (имён нет), `PORTRAIT … show=loading`. |

| № | Решение | Почему |
|---|---|---|
| ВР-VS7-31 | Этап держится ≥ 600 мс (BOOT — 400), смена на GAME — когда у доски есть фигуры три кадра | на живом бэкенде все три этапа проходят за 0,5–1,5 с: без удержания подписи не читаются, базовая очередь снимала уже следующий этап; без фигур — кадр пустой сцены |
| ВР-VS7-32 | Пока сцена под экраном — не доска комнаты (меню Marmoreal до первого снапшота партии на Sarpedon), вуаль непрозрачная `card.navy` | `s3d`: на Sarpedon под экраном (и под ошибкой) была видна Marmoreal; фон SC-02 меняется только на первом снапшоте |

Проверка: порядок `SHOT … state=connect → state → board` в `s3a`, `s3g` (Marmoreal, 1080p), `s3b2` (Sarpedon, 720p), `s3c` (класс S),
`s3d` после «Повторить»; `LOADING done` 1,5–2,2 с от показа; после смены — GAME на настоящей доске, шесть фигур v2 (открыт
`UI-SCR-GAME-own` `s3g`: Marmoreal original, нарисованный задник, Medusa + 3 гарпии, King Arthur + Merlin). На Sarpedon под экраном
— сцена Sarpedon (`s3b2` connect). Тест `Unmatched.S08.Hud.Screens.Loading.Tree`. Открыты: connect / state / board 1080p (`s3a`,
`s3g`), connect Sarpedon 720p, board класса S (`s3c`), error (`s3d`, `s3e`).

Кадры: портреты героев — PNG в `scraped-data/derived/visual-evidence/SC-19/`, в git — `stage-row-connect-1080p-100.jpg` и индекс.
Не сделано: VS_AI — бот садится сильнейшим героем с картами (T. Rex, вне ростера, монограмма без портрета; хвост бэкенда
`setupAiOpponent`); набор G, G-LOOK на кадрах packaged, листы, реестр 03 — шаг «Кадры».
