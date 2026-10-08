# SC-05 — BOOT: модаль «Вернуться в партию» (`UUmBootResume`)

VS-7, шаг S1, 2026-10-08, ветка `feat/visual-vs7`. Карточка — `screens.csv` SC-05; 04 §1.1 (вход / выход); принятый макет CX-27
`art/imagegen/sc05-boot-resume-codex/` (ВР-VS4-SC03-06, -07). Экран, сборки, тесты и гейты — [SC-03](../SC-03/README.md).

**Статус:** UE-часть готова, живая проверка editor-build на живой партии, по делегированию. Набор G packaged и листы — шаг
«Кадры». **Откат:** `-S08SlateHud=boot`.

## Что сделано

- `UUmBootResume : UUmModalBase` (в `UmScreenBoot.h/.cpp`, дерево кодом внутри `WBP_UI_SCR_BOOT`): 640×300 su по центру, скин
  `modal`; своя вуаль прозрачная — вуаль экрана единственная (ВР-VS4-SC03-06); появление 250 мс, уход 120 мс (ВР-SC05).
  `ResumeTitle` «Партия идёт», `ResumeLine` «Ваш герой: {hero} · соперник: {opponent} · {board}» (строка 64 su от верха модали),
  `LobbyButton` «В лобби» (обычная), `ResumeButton` «Вернуться в партию» (главная); resuming — главная disabled, спиннер 32 su
  слева от подписи, `why.syncing` под кнопкой (ВР-VS4-SC03-07). Enter — вернуться, Esc — в лобби.
- Данные: `myGames(status: IN_PROGRESS)` (`FS08FlowController::FetchActiveGame`) после доски; герои — имена `heroList` по `heroId`
  игроков, доска — имя строки Board (`boardList`).
- «Вернуться»: `ResumeActiveGame` — строка партии становится комнатой, стадия `Room`, затем путь гостя IN_PROGRESS
  (`AttachGameStateStream`: снапшот + поток, стадия `Started`). «В лобби»: модаль закрывается, партия остаётся на сервере.
- Звук: `UI-PANEL-OPEN` при открытии, `UI-CONFIRM` на «Вернуться», `UI-BTN-CLICK` на «В лобби».
- Трасса: `RESUME check game=<id> mode=<m>`, `BOOT resume shown game=… players= board=…`, `BOOT resume game=<id>`,
  `RESUME room=<id> status=IN_PROGRESS`, `SHOT widget id=UI-SCR-BOOT state=resume` (ВР-SC11).

## Решения по делегированию

| № | Решение | Почему |
|---|---|---|
| ВР-VS7-06 | «Вернуться» — путь гостя IN_PROGRESS (комната из строки `myGames` + `AttachGameStateStream`), не кнопка RECOVER MY ROOM | RECOVER спрашивает `myGames(LOBBY)` и живую партию не видит |
| ВР-VS7-07 | Строка — имена героев как в БД (`name`; `nameRu` в БД = EN) и имя строки Board; у VS_AI соперник — герой бота из `players` | данные бэкенда как есть (ВР-VS4-64), без склонения (ВР-SC10) |

## Проверка

- Тест `Unmatched.S08.Hud.Screens.Boot.Tree`: строка «Ваш герой: Medusa · соперник: King Arthur · Marmoreal · original map», одна
  главная, resuming disabled + `why.syncing`, «Вернуться» и «В лобби» по одному разу — PASS.
- Живая партия VS_AI создана GraphQL-запросами аккаунтом демо-хоста (`C:/tmp/visual/VS7/tools/vsai.cjs`, Sarpedon original, Medusa;
  бот взял T. Rex), затем:
  - `c1` — клиент входит → модаль «Ваш герой: Medusa · соперник: T. Rex · Sarpedon · original map» → «В лобби»; `game(id)` после
    прогона — `IN_PROGRESS` (партия не прервана);
  - `c2` — тот же вход → «Вернуться» → `RESUME room=cmuzcneul1j65t84muz2o5zj1` — тот же gameId, стадия `Started`, доска меню
    заменена Sarpedon в кадре первого снапшота (`SCREEN-BG … state=swap`), `FIGHTERS synced n=6`.
  - после проверки партия прервана `abortGame` (`ABORTED`), `myGames(IN_PROGRESS)` пуст.
- Открыты (Read): модаль `c1` (строка налезала на заголовок — исправлено: 64 su), модаль `c2`.

## Кадры в git (editor-build, не приёмка)

`boot-resume-1080p-100.jpg`.

## Не сделано в этом шаге

- Кадр resuming: ответ снапшота приходит быстрее 300 мс задержки спиннера — состояние не держится; для кадра нужна задержка
  `gameState` прокси (шаг «Кадры»). Набор G packaged и листы — шаг «Кадры». Экран загрузки SC-19 после «Вернуться» — шаг LOADING.
