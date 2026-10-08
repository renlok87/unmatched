# VS-7: экраны BOOT…ABORTED на UMG (итог спринта, шаг «Кадры»)

Итог спринта VS-7 из [05-production-plan.md §3](../../../visual/05-production-plan.md). Worktree `C:/tmp/wt-visual`, ветка
`feat/visual-vs7`. Шаг «Кадры» 2026-10-08: упаковка, гейты, цена экранов и кадры выхода F, G, I. Решения — по делегированию
пользователя 2026-10-06 («Все решения принимай»); приёмка — по делегированию и так помечена, только для того, что я открыл
глазами. Шаги S1–S5 — README карточек [SC-02](../SC-02/README.md) … [SC-38](../SC-38/README.md), [IC-57](../IC-57/README.md).

**Не влито.** Перед `tools/git/safe-integrate.sh feat/visual-vs7` (сухой прогон, затем `--apply`): ветка содержит
`fix/admin-panel` (`f60a4094`, merge — «Already up to date»). После интеграции в основной копии:
- пересобрать UnmatchedEditor и `tools/s08/sync-staged-build.ps1 -From C:/tmp/wt-visual` (штамп `3a9d1e69`, sourceHash
  `096d0da8…`; после него менялись только tools / docs);
- `tools/s08/screens/ue_import_board_thumbs.py` (`--prepare`, затем шаг UE): миниатюры досок LOBBY / ROOM не в git (S2);
- скопировать кадры `C:/tmp/wt-visual/scraped-data/derived/visual-evidence/VS-7/` и `SC-*/` в ту же папку основной копии
  (индекс [data/vs7-evidence-index.json](data/vs7-evidence-index.json));
- бэкенд с `createGame`-сбросом кэша списка (S2, ВР-VS7-15) — пересобрать и перемерить «≤ 15 с» списка LOBBY.

## Коммиты спринта

| Коммит | Что |
|---|---|
| `2f614206`, `ba533157` | S1: фон меню SC-02, BOOT SC-03…SC-05, LOGIN SC-06, SC-07 |
| `8e03bd39`, `f9e1f42e` | S2: LOBBY SC-08…SC-13 (+ сброс кэша `availableGames` на бэкенде) |
| `53bec304`, `323599df`, `63a9ecf8` | S3: IC-57 `ui-check`; ROOM SC-14…SC-18, загрузка SC-19, SC-20 |
| `28ec24d2`, `5885594b` | S4: PAUSE SC-24 и настройки SC-25…SC-30 |
| `49df1514`, `37042366` | S5: RECONNECT SC-31…SC-33, GAMEOVER SC-34…SC-37, ABORTED SC-38 |
| `30e07c84` | «Кадры»: строки `SHOT widget` BOOT / LOGIN, имена состояний в нижнем регистре (packaged), ширины текста на 720p 150 % и при +30 %, два хрупких теста |
| `3a9d1e69` | «Кадры»: многоточие ROOM / LOADING режет по границе (нужен `ClipToBounds`) |
| (этот) | гейт лобби `run-duel-demo.ps1` по трассе (ВР-VS7-77); README, листы, индекс кадров, статусы `screens.csv` / `icons.csv`, реестр 03 |

## Упаковки (ВР-VS7-71)

Три упаковки вместо одной, каждая исправляла найденное прогоном (правило «собрать все проблемы прогона и исправить вместе»):

| Пакет | Что на нём снято | Почему следующий |
|---|---|---|
| `37042366` | кадры F «результат» (`-Bench`, 12 прогонов), RECONNECT / ABORTED Sarpedon 1080p и обе доски 720p, цена экранов (два CSV-прогона) | G-WIDGET: BOOT / LOGIN без строк `SHOT widget`; имена состояний packaged с заглавной (`state=Board`); «Покинуть партию» вылезал за кнопку на 720p 150 % (RU); при +30 % — переполнения LOBBY / ROOM / LOADING / GAMEOVER / чипов языка |
| `30e07c84` | наборы G (1080p / 720p), I EN обеих досок, RECONNECT / ABORTED Marmoreal 1080p, I для RECONNECT / ABORTED, гейты `run-vs-ai-demo`, `run-vs-ai-abort-demo`, `run-hud-probe` | многоточие ROOM / LOADING без `ClipToBounds` не срабатывало |
| `3a9d1e69` | I псевдолокаль обеих досок, G 720p 150 %, `run-duel-demo` обеих досок | — |

Код экранов, которые показывают кадры пакета 1 (GAMEOVER на бенче, RECONNECT, ABORTED), во 2-м и 3-м пакетах менялся только
там, где текст не помещается (подгонка `UUmButton`, ряд кнопок GAMEOVER) и в регистре имён файлов — на RU-кадрах 100 % без
переполнения раскладка та же. Новых / переименованных `Config/**.json` нет (ловушка makefile не сработала). Пакет 2 с `-build`
упал на нехватке памяти компилятора (C3859 / C1076 в XGE) — игра собрана `build-editor.cjs -MaxParallelActions=4`, пакеты 2 и
3 — `-SkipBuild`.

## Карточки (35)

| Карточки | Итог | Где в packaged-кадрах | Только editor-build шагов S1–S5 |
|---|---|---|---|
| SC-02 | художественно принято, по делегированию: Marmoreal original, нарисованный задник, фигур 0 под BOOT…ROOM на всех масштабах; цена GPU 1,95 мс ≤ K1 2,14 мс | [g-menu-bg](g-menu-bg-1080p-100.jpg), все G | — |
| SC-03 | художественно принято, по делегированию | [g-boot](g-boot-1080p-100.jpg), [i-boot-pseudo](i-boot-pseudo-720p-150.jpg) | — |
| SC-04, SC-05 | принято по шагу S1 (живые editor-build) | BOOT loading | error / retrying, resume / resuming |
| SC-06 | художественно принято, по делегированию (чипы RU / EN по ширине текста) | [g-login](g-login-1080p-100.jpg), [720p 150 %](g-login-720p-150.jpg), [pseudo](i-login-pseudo-720p-150.jpg), [EN](i-login-en-720p-150.jpg) | — |
| SC-07 | busy — по делегированию; ошибки — по S1 | busy | error-credentials / error-server |
| SC-08…SC-12 | художественно принято, по делегированию | список / empty / create / create-ai / code / code-full на 1080p / 720p / 720p 150 %, pseudo, EN (кадры вне git) | code-error-notfound |
| SC-13 | принято по S2 | — | error (прокси задержки) |
| SC-14, SC-15, SC-17, SC-18 | художественно принято, по делегированию | ROOM хоста VS_AI и гостя 1×1, обе доски, отсчёт; pseudo — многоточие в слотах (пакет 3) | — |
| SC-16 | строка колоды — по делегированию | «Колода: 30 карт» | модаль колоды |
| SC-19 | художественно принято, по делегированию | connect / state / board обеих досок, swap Marmoreal → Sarpedon в кадре | — |
| SC-20 | принято по S3 | — | error и «Повторить» / «В лобби» |
| SC-24…SC-30 | художественно принято, по делегированию: все вкладки в живой партии обеих досок | [g-pause-sound](g-pause-sound-1080p-100.jpg), [interface 720p 150 %](g-pause-interface-720p-150.jpg), [pseudo](i-pause-game-pseudo-720p-150.jpg), [EN](i-pause-graphics-en-720p-150.jpg), [лист](sheet-pause-colour-grey-deutan.jpg) | confirm; game.defense / syncing — только тест |
| SC-31…SC-33 | художественно принято, по делегированию | [auto](f-reconnect-auto-marm-1080p.jpg), [manual](f-reconnect-manual-marm-1080p.jpg), [restoring](f-reconnect-restoring-sarp-720p.jpg), [EN](i-reconnect-manual-en-720p-150.jpg), [лист](sheet-modals-colour-grey-deutan.jpg) | expired — только тест |
| SC-34…SC-36 | художественно принято, по делегированию | победа: живые VS_AI обеих досок + бенч; поражение и «посмотреть доску»: бенч обеих досок 1080p / 720p (кадры вне git: портреты) | ничья — только тест |
| SC-37 | кнопка на кадрах победы — по делегированию | «СЫГРАТЬ ЕЩЁ» на победе VS_AI | again / again-busy (s5a / s5h) |
| SC-38 | художественно принято, по делегированию | [Marmoreal 1080p](f-aborted-marm-1080p.jpg), [Sarpedon 720p](f-aborted-sarp-720p.jpg), [pseudo](i-aborted-pseudo-720p-150.jpg), гейт abort-demo | — |
| IC-57 | художественно принято, по делегированию | «ГОТОВ ✓» слотов и чип доски ROOM на всех масштабах | — |

Статусы — `06-tasks/screens.csv` (SC-02…SC-20, SC-24…SC-38), `icons.csv` (IC-57), реестр 03 (`UmMenuBackdrop`,
`WBP_UI_SCR_BOOT` … `WBP_UI_SCR_ABORTED`, `T_IV3_ui_check`).

## Гейты

| Гейт | Итог |
|---|---|
| UE-тесты `Unmatched.S08 + S09 + S10` | **554 / 554** на финальном коде (`ue-full-2`). Первый прогон на `37042366` — 552 / 554: `Hud.Actions.KeyHints` читал сохранённый профиль чекаута (живая партия засчитала `completedMatches=1`), `Screens.Pause.Model` — ensure MTAccessDetector на `MarkAsGarbage`; оба теста исправлены (`30e07c84`), перепрогон групп 5 / 5, затем полный |
| pytest `tools/art/tests`, `tools/s08/hud_contract`, `tools/s08/cue_contract` | **744 passed**, 4 skipped |
| G-WIDGET (`hud_contract.py check-trace`) | **PASS** на 12 трассах пакета 2 (G 1080p / 720p, I EN обеих досок, RC ×6, vsai, vsai-abort) и на трассах пакета 3; в трассах есть все 10 экранов спринта: BOOT, LOGIN, LOBBY, ROOM, LOADING, GAME, PAUSE, RECONNECT, GAMEOVER, ABORTED. Строки мирового слоя `plate*` (12–72 на трассу с `-S09Flow`) из проверки исключены: они падают `geom=unpainted` в кадрах снапшота до раскладки табличек — открытый пункт VS-5 / S5, не блок `UI-SCR` ([data/gwidget-p2.json](data/gwidget-p2.json)) |
| `run-vs-ai-demo` (гейт `SHOT widget id=UI-SCR-GAMEOVER`) | **PASS** (пакеты 1 и 2): бот в месте 1, FINISHED, VICTORY = winnerId сервера, `UI-SCR-GAMEOVER state=victory` нарисован, LEFT room= |
| `run-vs-ai-abort-demo` (гейт `SHOT widget id=UI-SCR-ABORTED`) | **PASS** (пакеты 1 и 2): строка ABORTED без победителя, `state=shown` до снимка, ни одной строки GAMEOVER |
| `run-duel-demo` обе доски, два клиента по 30 FPS (`t.MaxFPS 30` на процесс) | **PASS** на пакете 3 (Marmoreal, Sarpedon): SHOTGATE результата и лобби обоих мест, privacy, FINISHED. На пакете 1 — FAIL «45 тыс. ярких пикселей» кадра лобби: за лобби теперь сцена меню SC-02; гейт исправлен (ВР-VS7-77), перепрогон только этого гейта (первая попытка на пакете 2 упала на ошибке моего патча — массив из одной строки, исправлено) |
| `run-hud-probe` | **PASS** (rules 3, пакеты 1 и 2). Пробник без бэкенда и без доски (фикстура 04) — второго прогона «на другой доске» у него нет (ВР-VS7-78) |
| G-LOOK | PASS: `ARTLOOK board=marmoreal-original backdrop=paste(default)` на фоне меню и партиях Marmoreal, `sarpedon-original backdrop=lit3d(default)` на Sarpedon, `heroes=v2`, `FIGHTERS synced n=6`; в партиях VS_AI соперник — T. Rex, которого берёт бот сервера (ВР-VS4-SC17), шесть фигур v2 — на 1×1 (RC) и бенче; слоя отладки нет (кадры CSV-прогона со счётчиком CsvProfiler в доказательства не взяты) |
| G-GRAY / дейтеранопия | PASS по листам: [модали](sheet-modals-colour-grey-deutan.jpg), [PAUSE](sheet-pause-colour-grey-deutan.jpg), [BOOT / LOGIN](sheet-boot-login-colour-grey-deutan.jpg); листы F / G / I с портретами и миниатюрами — вне git (`scraped-data/…/VS-7/sheets/`). Смысл не держится на цвете: выбранное — бирюзовая заливка + рамка, главная кнопка — жёлтая заливка + тёмный текст, проигравший — серый портрет + «Повержен» + сердце, красный только у X значков |
| G-READ | PASS на глаз: модали и панели непрозрачные на вуали 0,6, текст кремовый / `text.secondary` на navy; замер контраста — по пакетам CX-27…CX-34 (тот же текст, те же токены) |

## Цена экранов (одно измерение, правило «без оптимизаций»)

Один packaged-клиент, 1080p 100 %, Marmoreal, CSV-профайлер с первого кадра (`-csvGpuStats`, `CsvProfile Frames=6600`, лимит
60 кадров/с — времена GT / GPU кадра ожидание не включают), без кадров доказательств; RECONNECT / ABORTED — второй CSV-прогон
(1×1, 30 кадров/с). Интервал экрана — по трассе (`HUD-SCREEN route=`, `PAUSE open/close`, `RESULT screen`, `RECONNECT`,
`ABORTED shown`) с полями 1 с ([cost7.py → data/cost-vs7.json](data/cost-vs7.json)). Пакет `37042366`.

| Экран | Slate GT p95 (prepass + paint с тиками виджетов), мс | UI GT p95 (`Exclusive/GameThread/UI`), мс | GPU `SlateUI` p95, мс |
|---|---|---|---|
| BOOT | 0,101 | 0,279 | 0,021 |
| LOGIN | 0,158 | 0,347 | 0,021 |
| LOBBY | 0,167 | 0,393 | 0,034 |
| ROOM | 0,272 | 0,666 | 0,047 |
| PAUSE (над HUD) | 0,346 | 1,022 | 0,048 |
| GAMEOVER (результат / доска) | 0,133…0,174 | 0,328…0,364 | 0,023…0,024 |
| RECONNECT (над HUD, 30 FPS) | 0,228…0,238 | 0,649…0,673 | 0,083…0,097 |
| ABORTED (30 FPS) | 0,125 | 0,354 | 0,077 |
| справочно: HUD партии без экрана | 0,19…0,32 | 0,58…0,93 | 0,023 / 0,075 (30 FPS) |

**Итог: PASS.** Собственный GT экрана — Slate prepass + paint — ≤ 0,35 мс p95 на всех экранах (это верхняя граница: в ней и
HUD под модалью, и остальной Slate окна) при бюджете 0,5 мс. Категория `Exclusive/GameThread/UI` — весь UI кадра вместе с
HUD и полом движка: её прирост к полу — ROOM − BOOT 0,39 мс, PAUSE − партия 0,10…0,22 мс, RECONNECT − партия ≤ 0,09 мс — в
бюджете. GPU интерфейса ≤ 0,05 мс (60 FPS) / ≤ 0,10 мс (30 FPS, GPU на низких частотах) при бюджете 0,3 мс. LOADING держится
~3 с — короче окна с полями, отдельно не мерился (тот же порядок, что BOOT). SC-02: GPU фона меню 1,95 мс (p95 2,13) против
K1 партии с фигурами 2,14 мс (p95 2,27) — `render_bench.py` шага S1 (одно измерение); в CSV-прогоне кадр BOOT / LOGIN / LOBBY
2,29…2,35 мс GPU p95 против партии 2,51…2,63 — то же соотношение.

## Кадры выхода, которые я открыл

- **G** (пакет 2, 3): BOOT loading-heroes, LOGIN input, фон меню без UI, LOBBY create-ai, ROOM host-ready-ai (обе доски),
  LOADING board, PAUSE sound / interface / game / graphics, GAMEOVER victory / board на 1080p 100 %, 720p 100 % (Sarpedon) и
  720p 150 % (Marmoreal). На пакете 1 этот же набор показал вылезающий «Покинуть партию» (720p 150 %) — исправлено.
- **F** (пакет 1, бенч `-BenchResult` с `RENDER`): победа, поражение, «посмотреть доску» обеих досок 1080p и 720p; живые победа
  и доска VS_AI обеих досок; RECONNECT auto / manual / restoring и ABORTED обеих досок 1080p / 720p (пакеты 1 и 2).
- **I** (720p 150 %): псевдолокаль +30 % обеих досок (LOGIN, LOBBY, ROOM, LOADING, PAUSE ×4, GAMEOVER) и EN обеих досок;
  RECONNECT / ABORTED в псевдолокали (Marmoreal) и EN (Sarpedon). Пакет 1 — переполнения (чипы RU / EN, «Обновить», ряд
  режима класса S за краем экрана, строки слотов ROOM, «Колода: 30 карт», «против», кнопки GAMEOVER шире модали); пакет 2 —
  остались ROOM / LOADING; пакет 3 — всё внутри своих рамок (строки слотов и «Колода» — с «…»), кроме мелочей в «Открыто» п. 8.

## Решения шага (по делегированию, 2026-10-08)

| № | Решение | Почему |
|---|---|---|
| ВР-VS7-71 | Три упаковки | каждая исправляла найденное прогоном (гейт BOOT / LOGIN, текст на 720p 150 % и при +30 %, многоточие без клипа) |
| ВР-VS7-72 | Цена экрана — один CSV-прогон: Slate GT prepass + paint p95 и GPU `SlateUI` p95 на интервале экрана, абсолютные (верхняя граница); `Exclusive/GameThread/UI` — справочно, приростом к полу | у меню нет «экрана выключенного» для A/B, как у HUD (`-S08HudPerf`); новый режим замера в C++ — оптимизация ради цены |
| ВР-VS7-73 | `UUmButton::FitLabel`: подпись шире кнопки уменьшает шрифт до её ширины (не меньше 70 %), мерит при реальном px/su | одно правило на все кнопки экранов, RU / EN 100 % не меняются |
| ВР-VS7-74 | Строки слотов ROOM, «Колода: N карт», имена / ники / «против» LOADING — многоточие с `ClipToBounds` | 04 §6: «…», полный текст есть в карточке героя / колоде; имя игрока не режется (ВР-VS4-SC14-11) |
| ВР-VS7-75 | LOBBY класса S: ряд «Режим» под заголовком, если рядом не помещается; плитки досок отдают высоту, «Создать» на месте | псевдолокаль: «ПРОТИВ ИИ» уходил за край экрана |
| ВР-VS7-76 | Имена состояний в строках `SHOT widget` и файлах кадров — в нижнем регистре | packaged называет FName первым написанием в таблице имён (`Board`, `Connect`) |
| ВР-VS7-77 | `run-duel-demo.ps1`: яркостный гейт кадра лобби — только с `-S09Markers`; по умолчанию — трасса: после `LEFT room=` есть `SCREEN-BG … fighters=0 … stage=Lobby state=menu` | после SC-02 за лобби живая сцена меню Marmoreal (45 тыс. ярких пикселей); исходная цель гейта — «доска и бойцы партии не пережили выход» — трасса проверяет прямо (как ВР-VS7-68 для S10) |
| ВР-VS7-78 | `run-hud-probe` — один прогон | пробник без бэкенда, доска — фикстура; параметра доски у него нет |
| ВР-VS7-79 | Поражение набора F — бенч `-BenchResultLoser` обеих досок; живое поражение не снимается | бот VS_AI проигрывает автопилоту S09, 1×1 автопилоты не выбирают исход |
| ВР-VS7-80 | Набор I для RECONNECT / ABORTED — прогоны 1×1 с обрывом WS в псевдолокали (Marmoreal) и EN (Sarpedon) | модали партии не входят в прогоны меню |

## Открыто

1. **Интеграция** (см. начало), миниатюры досок и кадры в основной копии, перемер «≤ 15 с» списка LOBBY.
2. Строки мирового слоя `plate*` падают G-WIDGET в кадрах снапшота `-S09Flow` (до раскладки табличек) — VS-5 / S5.
3. Состояния только в editor-build / тестах: BOOT error / resume, LOGIN ошибки, LOBBY error / code-error, модаль колоды, ошибка
   загрузки, PAUSE confirm / defense / syncing, RECONNECT expired, GAMEOVER draw / again / again-busy — packaged-кадров нет.
4. Файлы кадров дров PAUSE называют вкладку с заглавной (`UI-SCR-PAUSE-game-Sound…`) — имя файла дрова S4, не состояние гейта.
5. Составная строка статуса HUD в псевдолокали получает двойные скобки (`[Medusa — [Соперник выбирает действие~~]~~]`) — HUD,
   не экран; T. Rex без кропа CP-07 (монограмма «TR») — S5.
6. Десатурация CUE-017 под ABORTED (VS-6 `FS08NetWatch`) — S5, сторона VS-6.
7. G-CUE AU5 / AU6 на кадрах съёмки — не трогалось (ВР-VS6-51).
8. Псевдолокаль +30 % (только она): имя «AI Bot» после чипа «[ИИ-соперник~~~~]» на ~8 px за краем слота (имя не режется,
   ВР-VS4-SC14-11); «против» LOADING центрирован и обрезан с обеих сторон без «…»; текст полосы GAMEOVER «[ХОД 17 ·
   [ПОБЕДА~~]~~]» заходит под «[К ИТОГАМ~~~]». RU и EN на 720p 150 % помещаются.
9. Sarpedon, «посмотреть доску» после смерти T. Rex (live-ipseudo-sarp, пакет 3): белый прямоугольник над клеткой у корабля —
   мировой слой / FX смерти не-v2 героя, не экран; не разбирался.
