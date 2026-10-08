# SC-03 — BOOT: загрузка (`UUmScreenBoot`)

VS-7, шаг S1, 2026-10-08, ветка `feat/visual-vs7` (worktree `C:/tmp/wt-visual`). Карточка — `screens.csv` SC-03; 04 §1.1;
принятый макет CX-27 `art/imagegen/sc03-boot-loading-codex/` (ВР-VS4-SC03-01…11). Тот же экран несёт
[SC-04](../SC-04/README.md) (ошибка) и [SC-05](../SC-05/README.md) (модаль «Вернуться в партию»); фон — [SC-02](../SC-02/README.md).

**Статус:** UE-часть готова — экран, этапы, строки, WBP, тесты, живая проверка одним клиентом editor-build; по делегированию.
Кадры набора G packaged `-S08ScreenShots` с `RENDER` (1080p 100 %, 720p 100 % и 150 %), листы цвет / серый / дейтеранопия,
G-READ / G-GRAY / G-LOOK — шаг «Кадры». **Откат:** `-S08SlateHud=boot` — прежняя Slate-панель потока.

## Что сделано (`do`)

| Пункт | Где и как |
|---|---|
| Экран | `UUmScreenBoot : UUmScreenBase` (`S08/UI/UmScreenBoot.h/.cpp`), WBP `/Game/S08/UI/Screens/WBP_UI_SCR_BOOT` (`UUmHudAuthoring`, `ue_author_um_hud.py`), в `Screens` корня; полный экран над вуалью 0,6, рамка не рисуется. |
| BindWidget | `Wordmark` (`screens.boot.title`, `type.display`, текстовый знак ВР-H19), `Progress` (`UUmProgressBar` HB-47, своя подпись скрыта), `StageCapsule` > `StageText` (капсула, `type.body` `text.secondary`, ВР-VS4-SC03-02), `BuildText` (`type.caption`, 24 / 16 su от края); SC-04: `ErrorBanner`, `ErrorIcon`, `ErrorText`, `RetryButton`, `WhyText`; SC-05: `ResumeModal`. |
| Раскладка | 04 §1.1: знак y 400 / 720p y 356, полоса 480×8 y 500 / 448, капсула 8 su под полосой; на холстах 150 % — смещения 1080p от центра (ВР-VS4-SC03-03). |
| Этапы | сессия 0/3 «Проверка сессии…» → герои 1/3 «Загрузка героев…» (до ответа) → 2/3 «Загрузка героев… 84/84» (`heroList`) → доски 2/3 «Загрузка досок…» (`boardList`) → 3/3 → проверка своей партии (SC-05). Прогресс по этапам, без процентов (ВР-SC15). |
| Версия | «сборка {commit}»: 8 знаков `commit` из `BuildStamp.json` упаковки, в editor-build — HEAD репозитория (в кадрах `29dcc089`). |
| Звук | `PlayScreenSound(UI-BOOT-LOGO)` при первом показе знака (трасса `SFX bank=UI-BOOT-LOGO tag=screen`); музыка меню — сама. |
| Трасса | `SHOT widget id=UI-SCR-BOOT impl=umg state=loading … stage=<session|heroes|boards|done> done=<n>/3 retrying= resuming= build=`; `HUD-SCREEN route=boot stage=…`, `BOOT error|retry|resume …`. |
| Строки | новые в `st-screens.csv` → `ST_Screens`, locres EN / RU (`hud_strings_build.py build` PASS): `screens.boot.title`, `.build`, `.stage.heroes.wait`, `.resume.*`; псевдолокаль строится из таблиц сама. |
| Поток | `S08FlowControllerBoot.cpp` (новый файл: `FetchBoards`, `FetchActiveGame`, `ResumeActiveGame`), в `S08FlowController.*` — объявления и счётчик отказов `heroList`. |

## Решения по делегированию (шаг S1)

| № | Решение | Почему |
|---|---|---|
| ВР-VS7-01 | Refresh-токен живёт только в памяти (GD-038): этап сессии на запуске ведёт в LOGIN через 1 с; каталог и проверка партии — второй проход BOOT после входа (стадия `Login`) | `heroList` требует входа (`GqlAuthGuard`); хранить токен на диске — отдельное решение безопасности, не экранов |
| ВР-VS7-02 | Этап досок — `boardList` (строки Board: id → имя) | у контентного `boards` нет id строк Board, а строке SC-05 нужно имя доски комнаты |
| ВР-VS7-03 | Пройденный этап держит подпись ≥ 400 мс | иначе «84/84» и «Загрузка досок…» мелькают за кадр (ответы ~50 мс) |
| ВР-VS7-08 | Прогоны `-S08Auto` (гейты S09 / S10) видят BOOT во время своего входа, но без формы LOGIN, второго `heroList` и модали | драйвер гейтов не меняется |
| ВР-VS7-10 | Доказательства: инструмент ревью `-S08MenuDrive=<hold+bg+login+badpass+retry+resume|lobby+server+exit>` (учётные данные только из окружения процесса) и кадры подсостояний `UI-SCR-BOOT-<sub>.png`, `UI-SCR-LOGIN-<sub>.png` с `-S08ScreenShots`; `tools/s10/delay-graphql-query-proxy.cjs` держит и `heroList` / `login` (`S10_DELAY_COUNT` для запроса) | состояния нужны в живом клиенте; шаг «Кадры» берёт тот же механизм |
| ВР-VS7-13 | При F10 (панель отладки) экраны UMG уступают место Slate-панели | панель оператора остаётся доступной |

## Проверка

- Сборки: UnmatchedEditor `build-1…6` (последняя Succeeded), игровая цель `build-game-1` Succeeded.
- Тесты: `Unmatched.S08.Hud.Screens.*` 13 из 13 (`Boot.Tree`, `Boot.Timer`, `MenuBg`, `Login.Tree`, `Login.Enter` + прежние
  `Base.*`, `Inspect.*`); `Unmatched.S08.Hud` 113 из 113; полный `Unmatched.S08 + S09 + S10` 542 из 542.
- Гейты: `hud_contract.py check-trace` — `a2` 102, `b1` 60, `c2` 96 строк `SHOT widget`, PASS; `validate` PASS;
  `hud_tokens_codegen.py --check` FRESH; `hud_strings_build.py check` PASS; pytest `tools/s08/hud_contract` 75 из 75.
- Живые прогоны (UnrealEditor `-game` worktree, 30 FPS, offscreen; `C:/tmp/visual/VS7/runs/`): `a2` 1080p — сессия → LOGIN →
  вход → герои (ответ `heroList` задержан прокси 13 с → баннер через 10 с, «Повторить») → 84/84 → доски → лобби; `b1` 720p 150 %
  (класс S, `HUD-LAYOUT class=S canvas=1138x640`); `c2` — модаль и возврат.
- Открыты (Read): сессия 1080p (`a1` — первый кадр без UI и с размытыми мипами — отсюда `hold`; `a2` — чистый), сессия 720p 150 %,
  герои 84/84, доски.

## Кадры в git (editor-build, не приёмка)

`boot-loading-session-1080p-100.jpg`, `boot-loading-heroes-1080p-100.jpg`, `boot-loading-boards-1080p-100.jpg`,
`boot-loading-session-720p-150.jpg`.

## Не сделано в этом шаге

- Набор G packaged с `RENDER`, листы цвет / серый / дейтеранопия, G-READ, G-GRAY, G-LOOK, статус в реестре 03 и в
  `screens.csv` — шаг «Кадры».
- Состояние «офлайн-кэш» (каталог прошлой сессии): кэша каталога в клиенте нет; при отказе — баннер SC-04.
- Бюджет экрана ≤ 0,5 мс GT p95 / ≤ 0,3 мс GPU не мерился (замер HUD — со следующим `-S08HudPerf` шага «Кадры»).
