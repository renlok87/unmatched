# SC-14 — ROOM: выбор героя (`UUmScreenRoom`, `UUmHeroCard`, `UUmRoomSlot`)

VS-7, шаг S3, 2026-10-08, ветка `feat/visual-vs7` (worktree `C:/tmp/wt-visual`), коммит `323599df`. Карточка — `screens.csv`
SC-14; 04 §1.4, ВР-H12; принятый макет CX-30 `art/imagegen/sc14-room-hero-codex/` (ВР-VS4-SC14-01…16). Тот же экран несёт
[SC-15](../SC-15/README.md)…[SC-18](../SC-18/README.md), загрузка — [SC-19](../SC-19/README.md), [SC-20](../SC-20/README.md);
здесь — общие сборки, тесты, гейты и решения шага.

**Статус:** UE-часть готова, живая проверка одним клиентом editor-build на основном бэкенде `:3000` (второй игрок —
`tools/s08/screens/room_actor.cjs` по API), по делегированию. Набор G packaged с `RENDER`, листы цвет / серый / дейтеранопия,
G-READ / G-GRAY / G-LOOK, статус в реестре 03 — шаг «Кадры».
**Откат:** `-S08SlateHud=room` — прежняя Slate-панель комнаты (`HUD-SCREENS room=slate`); `-S08Auto`, `-S08HeroId=` — как раньше.

## Что сделано (`do`)

| Пункт | Где и как |
|---|---|
| Экран | `UUmScreenRoom : UUmScreenBase` (`S08/UI/UmScreenRoom.h/.cpp`), WBP `/Game/S08/UI/Screens/WBP_UI_SCR_ROOM` (`UUmHudAuthoring`, `ue_author_um_hud.py`), в `Screens` корня над фоном SC-02. Класс L — прямоугольники 04 §1.4 (1080p и колонка 720p), класс S — ВР-VS4-SC14-11 (поля 16, колонка 300 su, карточки 360×240). |
| Шапка | «Комната · код <код>» (`screens.room.title`), «Копировать» (код в буфер обмена, в трассу не пишется), «Режим» + «1×1» / «Против ИИ», «≡» (`ui-menu`; меню — шаг PAUSE). |
| Карточка | `UUmHeroCard` (пул, сетка 4 колонки с прокруткой; полоса прокрутки только когда ряды не помещаются): портрет 120 su (CP-07, `PORTRAIT … show=room`), имя БД, «HP 18 · ход 2», «ближний бой» / «дальний бой», строка помощника (мини-портрет 40 su, «Merlin · HP 7 · дальний бой», «Harpies ×3 · HP 1 · ближний бой» — фраза атаки переносится целиком), способность EN с чипом «EN» до 3 строк и «…» (S — 2), «ВЫБРАТЬ» (никогда не главная). Состояния: hover (`panel.bg.hover`), picked (кромка 3 su `state.pending` + «ВЫБРАНО»), taken (насыщенность ×0,4, `text.secondary`, «Выбран соперником» вместо кнопки и подсказкой), loading. |
| Слоты | `UUmRoomSlot` ×2 (хост — слот 1): аватар 80 su (S 64) героя слота или пустой диск, имя + чип «Хост» (если строка полна — в конце строки готовности), готовность (см. SC-17), «Medusa · HP 16 · ход 3», «+ Harpies ×3 · HP 1», «Герой не выбран», «Ждём игрока…». |
| Данные | `heroList` → герои ростера MVP (King Arthur, Medusa); `adminHero(id)` — HP, ход, тип атаки, помощники, способность; `cardList(heroId)` — колода (`FS08FlowController::FetchHeroDetails` / `FetchHeroDeck`, новый `S08FlowControllerRoom.cpp`); `FS08RoomState` — код, режим, хост, доска, игроки. |
| Выбор | «ВЫБРАТЬ» → `SelectHero` (busy с `why.syncing` до ответа комнаты, ≤ 8 с); отказ занятого героя → `UI-REJECT`, карточка — `why.hero.taken`, трасса `ROOM pick refused hero=<id> why=why.hero.taken`. |
| Звук | `UI-SELECT` на выбор, `PlayHeroSelectSting(<герой>)` — когда сервер подтвердил выбор (`STG-SELECT-MEDUSA` / `-ARTHUR`); вход в комнату и слой комнаты звучат сами. |
| Трасса | `SHOT widget id=UI-SCR-ROOM impl=umg state=<waiting|picked|ready|countdown> … host= mode= hero= ready= opp= primary= busy= heroes= phase= digit=` (кода и имён нет) + строки блоков `state=board`, `state=deck`; `ROOM hero id=<id> hp= move= attack= sidekicks=`, `ROOM deck hero= unique= copies=`, `ROOM board=<id>`, `HUD-SCREENS room=<WBP> roomParts=1`. |
| Строки | новые: `screens.room.hero.stats`, `.hero.melee`, `.hero.ranged`, `.slot.no.hero`, `.slot.ai.hero`, `.leave.confirm`, `common.btn.lobby` (EN / RU, псевдолокаль строится из таблиц). |

## Решения по делегированию (шаг S3)

| № | Решение | Почему |
|---|---|---|
| ВР-VS7-27 | IC-57 `ui-check` принят по листу (см. [IC-57](../IC-57/README.md)) и подключён: «ГОТОВ ✓» слота и тумблера, чип доски | макеты стояли на HB-08 Check_On (ВР-VS4-SC14-09) до глифа |
| ВР-VS7-28 | Сетка — герои ростера MVP (ВР-02) из `heroList` по имени, в порядке макета | «герой с колодой» не отбирает ростер: карты есть у многих героев (бот VS_AI берёт T. Rex) |
| ВР-VS7-29 | Данные карточки — `adminHero` (как макет, ВР-VS4-SC14-01), колода — `cardList(heroId)`, число карт = сумма `Card.count` | публичный `heroList` не несёт хода, атаки и помощников; `gameDeckLists` есть только в партии |
| ВР-VS7-35 | «Готов», «Начать», «Выйти» звук не вызывают; выбор — `UI-SELECT`, стинг — на подтверждении сервера | 08: SC-17 «звучат сами по ответам комнаты»; SC-14 «выбор / подтверждение» |
| ВР-VS7-36 | ROOM и LOADING не строят маршрут в `-S08Auto` | как LOBBY (ВР-VS7-14): драйвер гейтов S09 / S10 не меняется |
| ВР-VS7-40 | Блоки SC-15 / SC-16 — отдельные строки `SHOT … state=board` / `state=deck` (`block=1`) рядом с основной | у экрана одно состояние; ВР-SC11 требует строки блоков |
| ВР-VS7-41 | Пока ROOM (отсчёт) или LOADING закрывают GAME, его блоки не пишут `SHOT` и не снимаются базовой очередью | иначе `check-trace` падал на `geom=unpainted` (прогоны s3a…s3f), а `UI-SCR-GAME-*.png` снимал экран комнаты |
| ВР-VS7-42 | У занятой карточки нет кнопки; отказ сервера (гонка) — `UI-REJECT` и `why.hero.taken` на карточке до следующего ответа | 04 §1.4: недоступное объясняет себя; выбор не имитируется на клиенте |
| ВР-VS7-43 | Имя в слоте не режется; не помещается с чипом «Хост» — чип уходит в конец строки готовности | ВР-VS4-SC14-11: имена не усекаются |

## Проверка

- Сборки: UnmatchedEditor `s3-build-1…8` (1 — C4458, исправлено; последняя Succeeded, лог прочитан), игровая цель
  `s3-build-game-1` Succeeded.
- WBP: `ue_author_um_hud.py` (`UM_HUD_WBP_OVERWRITE=0`) — `WBP_UI_SCR_ROOM`, `WBP_UI_SCR_LOADING` created, 31 прежних
  exists-unchanged, `UM_HUD_WBP_PASS assets=33`. Строки: `hud_strings_build.py build` PASS (ST_Screens 139, locres EN / RU).
- Тесты: новые `Unmatched.S08.Hud.Screens.Room.Tree`, `.Room.Model`, `.Loading.Tree` — PASS; `Unmatched.S08.Hud` +
  `IconMotion` 129 из 129; с потоком (`StaleGuards`, `RoomEntry`, `Leave`, `Phase2`, `S10`, `S09.HUD`, `S09.HudPress`) 223 из 223.
- Гейты: `hud_contract.py check-trace` — `s3e` 188, `s3g` 225, `s3h` 161 строк `SHOT widget`, PASS (до ВР-VS7-41 — FAIL на
  блоках GAME под экраном); `validate` PASS; `hud_tokens_codegen.py --check` FRESH; `pytest tools/s08/hud_contract` 75 из 75.
- Живые прогоны (UnrealEditor `-game` worktree, 30 FPS, offscreen, `C:/tmp/visual/VS7/runs/`, демо-аккаунты host / joiner,
  комнаты и партии убраны `room_actor.cjs --role cleanup`): `s3a`, `s3g` 1080p — хост 1×1 Marmoreal: ожидание → Medusa → колода →
  гость King Arthur → готовность → выход (отмена) → отсчёт → загрузка → GAME; `s3b2` 720p — гость на Sarpedon: Medusa занята,
  принудительный выбор Medusa → отказ сервера `why.hero.taken`, King Arthur, готов → «Партия начинается…» → загрузка → GAME;
  `s3c` 720p 150 % (класс S) и `s3h` 1080p — VS_AI; `s3f` 720p 150 % — хост 1×1; `s3d` / `s3e` — ошибка загрузки (SC-20).
  Данные карточек совпадают со снимком админки: `ROOM hero … hp=18 move=2 attack=melee` / `hp=16 move=3 attack=range`.
- Открыты (Read): host-waiting, host-picked, host-ready-taken, deck, leave, countdown-3 (1080p `s3a` / `s3g` / `s3h`);
  guest-waiting-taken-sarpedon, starting (720p `s3b2`); host-ready-ai и host-ready-taken в классе S (`s3c`, `s3f`);
  countdown-3 класса S; загрузка и GAME — см. SC-19 / SC-20. После `s3a` исправлено: белые квадраты за портретами (фон UBorder),
  разрыв «ближний / бой», цифра отсчёта не по центру, повторный стинг на старте; после `s3c` — чип «Хост» на имени, полоса
  прокрутки; после `s3g` — карточки сетки разъезжались по ширине (равномерная сетка).

## Кадры

Все кадры ROOM показывают аватары героев и миниатюры карт — в git только индекс `visual-evidence-index.json`
(`scraped-data/derived/visual-evidence/SC-14/`).

## Не сделано в этом шаге

- Набор G packaged, листы, G-READ / G-GRAY / G-LOOK, статусы в реестре 03 и `screens.csv` — шаг «Кадры». Бюджет экрана
  ≤ 0,5 мс GT / 0,3 мс GPU не мерился.
- RU-имена героев и помощников и RU-текст способности — в БД только EN (задача контента, ВР-VS4-SC14-01 / -02).
- Навигация Tab и кольцо фокуса по экрану ROOM не сделаны; hover-звук карточек не вызывается.
