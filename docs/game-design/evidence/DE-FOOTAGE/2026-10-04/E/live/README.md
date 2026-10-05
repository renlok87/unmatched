# Прогон E (S11e — HUD хода, рука, лист A/B): живая приёмка G-LIVE (2026-10-05)

**Итог: пройдено с одним исправлением и двумя открытыми дефектами вёрстки.**
- DE-025 принят полностью.
- DE-026 принят после исправления `d786188f`.
- DE-023 и DE-024 приняты частично: поведение и трассы верны, но открыты два дефекта вёрстки, см. «Дефекты» ниже. Им нужен один проход исправлений.
- DE-028 вживую не проверяется: это лист A/B на packaged `-Bench`, он ждёт ответа пользователя.

Как проверяли:
- упакованная сборка, два клиента, 30 FPS на клиент, оба offscreen, 1920×1080, High;
- две партии до GAME_OVER (`run-combat-demo`) на Marmoreal original и Sarpedon original;
- два прогона с манёвром хоста через черновик (`run-phase2-demo -HostManeuver`) на тех же картах;
- одна партия на Sarpedon с `-S08AnimSpeed=fast`, только ради трасс DE-025;
- `check-trace` прошёл на всех трассах;
- все кадры просмотрены глазами до отчёта.

Ссылки:
- полномочия — [IMPL-2026-10-04.md](../../../../../de-footage/task/runs/IMPL-2026-10-04.md);
- журнал — [E-2026-10-04.md](../../../../../de-footage/task/runs/E-2026-10-04.md), раздел «Живая приёмка G-LIVE»;
- гейт — [07-sprint-plan.md](../../../../../de-footage/task/07-sprint-plan.md) §8, G-LIVE.

## Коммиты агента приёмки

| Коммит | Что |
|---|---|
| `986d194b` | **Кадры прогона E.** Автоклиент S09 снимает по одному кадру тех моментов S11e, которые бывают только в живой партии: `s09-turn-banner.png` — первый баннер своего хода (DE-023), `s09-hand-limit-hint.png` — первый тост лимита руки (DE-024), `s09-card-slot-opp.png` и `s09-card-slot-own.png` — первая карта в слоте у каждого владельца (DE-026). `run-combat-demo.ps1` публикует их и кадр сброса, если клиент их записал. Новый ключ `-HostScheme` добавляет хосту в план `scheme`, чтобы джойнер увидел схему соперника. Гейты не менялись |
| `d786188f` | **Исправление DE-026.** В phase2 на Marmoreal хост усилил манёвр картой *A Momentary Glance* (это карта SCHEME), и его собственный слот показал её как `SCHEME owner=own`. Причина: наблюдатель карт знал только след буста соперника. Теперь буст с любой стороны исключает свою карту из правила «сыграна схема»: исключается самая новая карта с этим именем в сбросе бустящего. Мой буст, как и раньше, в слот не идёт (решение 9 DE-026). В тест `SCHEME.Slot played-card watch` добавлен случай своего буста картой SCHEME |

Гейты:

| Гейт | Результат |
|---|---|
| Сборка редактора и игровой цели после `986d194b` и после `d786188f` | `Result: Succeeded`, ошибок нет |
| UE `Unmatched.S09+Unmatched.S08.MoveAnim` после `986d194b` | 97/97 Success |
| UE `Unmatched.S09.SCHEME` и `Unmatched.S08+Unmatched.S09+Unmatched.S10` после `d786188f` | 12/12 и 346/346 Success |
| `cue_contract.py check-trace` на всех трассах итогового пакета | `CUE_TRACE PASS`, параметры ниже |

## Сборка и упаковка

- Упаковка `f620b15e` (её сделал DE-028) взята не была: живым кадрам нужны были новые точки съёмки `986d194b`.
- **Упаковка 1** — `package-client.ps1 -SkipBuild`, штамп `986d194b`, `UAT_EXIT=0`, ошибок и предупреждений cook нет. На ней найден дефект DE-026.
- **Упаковка 2**, вынужденная, после исправления `d786188f`: `UAT_EXIT=0`, ошибок и предупреждений cook нет. Штамп в [BuildStamp.json](BuildStamp.json): commit `d786188f`, sourceHash `825c71f6…`, 185 файлов.
- Новых `Config/**.json` в прогоне E нет, поэтому makefile не регенерировался.

## Окружение

- **Бэкенд.** Основной стек `:3000` (postgres, redis, backend) был поднят до агента и оставлен как есть. `/health` отвечает: database up, redis up. Серверных правок в прогоне E нет: `git diff bf382d32..HEAD -- backend` пуст.
- **Аккаунты.** Демо-аккаунты `S08_DEMO_*` из `C:/tmp/wt-envmaps/backend/.env` передавались только в окружение процесса и нигде не печатались. Обёртки лежат вне репозитория, в `C:/tmp/e-live/`: `run-combat.ps1`, `run-phase2.ps1`, `env-s08.cjs`.
- **GPU.** Демо шли под замком `C:/tmp/unmatched-gpu.lock`, владелец `E-LIVE`. После прогона замок снят.

## Живые прогоны (итоговый пакет `d786188f`)

### Партии до GAME_OVER — `run-combat-demo`

```
node env-s08.cjs powershell -File C:/tmp/e-live/run-combat.ps1 -Board <board> -Out <dir> -JoinerAttack -HostScheme [-Extra '-ConceptPaste+-S08MovePlates']
  → run-combat-demo.ps1 -Api http://localhost:3000/graphql -ArtPreview -FullHd -ArtPreviewBoardId <board> -ArtPreviewHeroesV2
    -ArtPreviewDiorama -ClientFps 30 -ClientRenderPreset High -RequireRenderReference -RequireShotCaptured -ClientPerf
    -RequireGameOver -RunSeconds 480 -JoinerAttack -HostScheme [-ClientExtraArgs '-ConceptPaste+-S08MovePlates']
python tools/s08/cue_contract/cue_contract.py check-trace <trace> --min-ms-cue 1 --min-combat 1 --min-death 1
```

Задник Marmoreal снят с `-ConceptPaste` (IMPL п. 3, ENV-U16 открыт). Sarpedon снят в виде по умолчанию.

| Проверка | Marmoreal — [combat-20261005-135610](demo/marmoreal/combat-20261005-135610/) | Sarpedon — [combat-20261005-135712](demo/sarpedon/combat-20261005-135712/) |
|---|---|---|
| Доска, вид | `marmoreal-original` 7×6. `ARTLOOK art=1 source=default heroes=v2`. `heroesV2 summary … v2=6`. `concept-paste status=ok` — нарисованный задник | `sarpedon-original` 9×6. `ARTLOOK … heroes=v2`, `v2=6`. `concept-scene status=ok mode=lit3d` (путь 1) |
| Партия | seq 39, FINISHED, победила Medusa (хост) | seq 64, FINISHED, победил King Arthur (джойнер) |
| `check-trace` | PASS на обоих: stale 0, `combat_sets`, `death_sets 1` | PASS на обоих |
| Строки конфигурации (оба клиента) | `HUD-TURN config portraits=1 ring=none heartGlow=0 ringIcon=0 banner=600`, `HUD-HINT config ruleHints=1 saved=1 limitDefault=7`, `HUD-SLOT config fly=200 oppHold=1500 own=500 min=1000 …`, `SETTINGS saved … combatSpeed=1.00 audioApplied=0`, `MS-ANIM settings … hop=0.000 lean=10.0 …` | то же |
| FPS (`PERF window`) | кап 30, `fps=30.00`. Провалы до 22 — только в окнах, где снимались кадры доказательств (около 250 мс на кадр) | то же, провалы до 21 |

### Манёвр хоста через черновик — `run-phase2-demo`

```
run-phase2-demo.ps1 -Api http://localhost:3000/graphql -ArtPreviewBoardId <board> -EvidenceDir <dir> -ClientFps 30
  -ClientRenderPreset High -RequireRenderReference -RequireShotCaptured -ClientPerf -HostManeuver
  -ClientExtraArgs '[-ConceptPaste+]-S08MovePlates+-S08ManeuverPlan=boost3+-S08ManeuverDraftHold=2.5+-S08ManeuverDraftShot=<png>'
```

| Проверка | Marmoreal — [run-20261005-135124](phase2/marmoreal/run-20261005-135124/) | Sarpedon — [run-20261005-135345](phase2/sarpedon/run-20261005-135345/) |
|---|---|---|
| Итог скрипта | `pass: true` (оба клиента), `DEMO_EXIT=0` | то же |
| Буст соперника (DE-026, SD-54) | У джойнера `HUD-SLOT show seq=3 ribbon=boosted owner=opp card="Gaze of Stone" … min=1000`. В той же пачке строк — `MS-ANIM play seq=3 … end=1606`, без задержки | `ribbon=boosted owner=opp card="Second Shot"`, `MS-ANIM play seq=3 … end=1746` в той же пачке |
| Свой буст хоста | Строки `HUD-SLOT show` у хоста нет — верно | то же |
| Трекер (DE-023) | `HUD-TRACK chosen=maneuver seq=1` в момент отправки | то же |
| `check-trace --min-ms-cue 1` | PASS на обоих | PASS на обоих |

### Скорость боя «Быстро» — DE-025 (только трассы)

- Партия на Sarpedon, `-ClientExtraArgs '-S08AnimSpeed=fast'`, `-JoinerAttack`.
- Партия дошла до FINISHED, но скрипт её **не опубликовал**: пиксельный гейт кадра результата хоста нашёл 1 пиксель маркера защиты (`rst=2408 res=0 def=1`). Это шум пиксельного гейта S09, к коду прогона E он не относится.
- Трассы взяты из временной папки, код комнаты в них заменён на `<redacted>`: [fast-speed-unpublished/](fast-speed-unpublished/).
- `check-trace` PASS на обоих клиентах.
- В трассах:
  - `SETTINGS saved … combatSpeed=0.50`;
  - `stage=start … speed=0.50 flip=310 contact=167`;
  - `stage=lunge … rate=2.00`;
  - `clip=LungeAttack … rate=2.00`;
  - `stage=hit … tint=450`;
  - `stage=minus … life=450`.

### Дополнительно: пакет 1 (`986d194b`)

Кадры пакета 1 остались в доказательствах, потому что в итоговом пакете эти моменты не выпали. Пакеты отличаются только наблюдателем карт слота (`d786188f`). Виджеты, тост, баннер и портреты в них одни и те же.
- [pkg1-986d194b/marmoreal/…/host/s09-card-slot-own.jpg](pkg1-986d194b/marmoreal/combat-20261005-133944/host/s09-card-slot-own.jpg) — своя схема *Winged Frenzy* в слоте, рука опущена (`HUD-HAND lower=1 pick=cell`), ниже открыт MOVE.
- [pkg1-986d194b/marmoreal/…/joiner/s09-card-slot-opp.jpg](pkg1-986d194b/marmoreal/combat-20261005-133944/joiner/s09-card-slot-opp.jpg) — схема соперника *A Momentary Glance* с подсказкой «click, Space or Enter – play the effect».
- [pkg1-986d194b/sarpedon/…/joiner/s09-hand-limit-hint.jpg](pkg1-986d194b/sarpedon/combat-20261005-134200/joiner/s09-hand-limit-hint.jpg) — единственный кадр с видимым тостом лимита руки.
- [pkg1-986d194b/phase2-marmoreal/…](pkg1-986d194b/phase2-marmoreal/) — трассы дефекта DE-026 до исправления. У хоста: `HUD-SLOT show seq=3 ribbon=scheme owner=own card="A Momentary Glance"` при `MANEUVER done seq=3 … boost=card`.

## Кадры (просмотрены глазами до отчёта)

- Все кадры сняты в 1920×1080 и сохранены в JPG шириной 1600 (q88).
- sha256 исходных PNG есть в `manifest.json` и в строках `SHOT captured` трасс.
- Файлы `*.trace.log` переименованы в `*.trace.txt`, байты не менялись.

**На всех кадрах:**
- настоящая карта;
- Marmoreal — нарисованный задник: дворец, колонны, фонари, сакура;
- Sarpedon — `lit3d`: остров, корабль, пушки, фонари;
- шесть фигур v2.

**DE-023 — портреты, статус, трекер, сердце, баннер.**
- Два портрета слева внизу, соперник над своим: монограмма на диске цвета команды, имя, статус `YOUR TURN` / `THEIR TURN` / `waiting`, сердце «hp/max», ромбы трекера.
- На экране результата портретов нет — верно.
- Баннер «YOUR TURN» сверху по центру, под слотом метки боя:
  - [Marmoreal, хост](demo/marmoreal/combat-20261005-135610/host/s09-turn-banner.jpg) и [джойнер](demo/marmoreal/combat-20261005-135610/joiner/s09-turn-banner.jpg);
  - [Sarpedon, хост](demo/sarpedon/combat-20261005-135712/host/s09-turn-banner.jpg) и [джойнер](demo/sarpedon/combat-20261005-135712/joiner/s09-turn-banner.jpg).
- Трассы на четырёх клиентах:
  - `HUD-TRACK own=…` — 25–47 строк;
  - ни одной строки `oppVisible=1` в свой ход;
  - локальная отметка ставится раньше серверной: `own=1/2 server=0 local=1` → `server=1 local=0`;
  - `HUD-TRACK chosen=` — 6–12 строк на клиент;
  - `HUD-HEART … anim=damage|deplete|heal glow=0`; строк с `glow=1` нет.

**DE-024 — тост лимита руки.**
- [Кадр тоста](pkg1-986d194b/sarpedon/combat-20261005-134200/joiner/s09-hand-limit-hint.jpg) (пакет 1): «Hand limit: 7 cards. At the end of your turn, discard down to 7» над полосой руки.
- В трёх партиях, где рука дошла до 7, ровно одна строка `HUD-HINT rule=hand-limit show … blocking=0`, затем `close=turn`. Второго `show` нет.
- `TURN-INPUT open … gate=none` идут как обычно.
- В итоговом пакете тост жил меньше 0,4 с: автоклиент сразу завершал ход. Поэтому кадры [Marmoreal, хост](demo/marmoreal/combat-20261005-135610/host/s09-hand-limit-hint.jpg) и [Sarpedon, джойнер](demo/sarpedon/combat-20261005-135712/joiner/s09-hand-limit-hint.jpg) сняты уже после закрытия: рука 7/7, тоста нет. Это верно, правило закрывает тост концом хода.
- Сброс до лимита вживую не выпал: к концу своего хода рука ни разу не превышала 7. Внутри хода она доходила до 8/7 (Marmoreal, хост, seq 10–11; виден на [кадре баннера](demo/marmoreal/combat-20261005-135610/host/s09-turn-banner.jpg)), но лишняя карта ушла в бой того же хода (правка ревьюера).

**DE-026 — слот карты-источника.**
- [Sarpedon, хост — своя схема](demo/sarpedon/combat-20261005-135712/host/s09-card-slot-own.jpg) и [джойнер — схема соперника](demo/sarpedon/combat-20261005-135712/joiner/s09-card-slot-opp.jpg). Карта слева сверху под командной панелью, лента SCHEME читается, текст карты не обрезан, у соперника есть строка пропуска.
- [Буст соперника, Marmoreal](phase2/marmoreal/run-20261005-135124/phase2-board-joiner-1920x1080.jpg) и [Sarpedon](phase2/sarpedon/run-20261005-135345/phase2-board-joiner-1920x1080.jpg): лента BOOSTED, «BOOST +4» / «+3».

## Приёмка задач прогона

| Задача | Что проверено вживую | Статус |
|---|---|---|
| DE-023 | Портреты на обеих картах. Статус активного игрока. Трекер соперника только в его ход. Отметка в момент выбора. Сердце `damage` / `deplete` / `heal` с `glow=0`. Баннер 600 мс только в свой ход, при входе не показывается (`initial=1 banner=0`). Кольца нет (`ring=none`) — верно до арт-приёмки | **принято частично**: открыт дефект 2 (портреты закрывают панель руки) |
| DE-024 | Тост один раз за партию, `blocking=0`, закрытие концом хода, ввод не задержан | **принято частично**: открыт дефект 3 (обрезана строка тоста). Вживую не выпали сброс до лимита и закрытие кликом — они остаются на тестах `HandLimit.*` |
| DE-025 | `SETTINGS saved … combatSpeed=1.00 audioApplied=0`, `rate=1.00` у выпада и у клипа, check-trace C4/C5 PASS. Партия «Быстро»: 0,50 / rate 2,00 / «−N» 450 / tint 450 | **принято** |
| DE-026 | Слот: своя схема (`own`, hold 0, min 700), схема соперника (`opp`, hold 1500, строка пропуска), буст соперника (`boosted`, min 1000), анимация хода без задержки. Рука опускается при выборе клетки или цели (`HUD-HAND lower=1 pick=cell|target` → `lower=0`) | **принято** после исправления `d786188f` (дефект 1). Вживую не выпали: `release=time` / `click` (схему соперника всякий раз отпускал новый seq через 1,0–1,1 с — темп автоклиента), `HUD-SLOT cues held`, лента DISCARDED |
| DE-028 | Не проверяется вживую: лист A/B снят на packaged `-Bench` (`f620b15e`). Код листа после него не менялся | без изменений, ждёт ответа пользователя (G-ART) |

## Дефекты и замечания

1. **DE-026, исправлен** (`d786188f`). Свой буст картой SCHEME попадал в слот как «своя схема».
   - Вживую исправление повторно не встретилось: в итоговом пакете бусты были *Gaze of Stone* и *Second Shot*.
   - Проверено тестом. У хоста в итоговых phase2 строк `HUD-SLOT show` нет.
2. **DE-023, открыт, заметный.** Когда в руке 6–7 карт с длинными именами (колода King Arthur: «Command the Storms», «The Aid of Morgana»), панель руки шире примерно 1380 su. Тогда её левый край уходит под портреты: портреты закрывают начало ленты, строку статуса, «YOUR HAND n/7» и первую карту.
   - Видно на кадрах джойнера обеих карт, например [Sarpedon, seq 13](demo/sarpedon/combat-20261005-135712/joiner/s09-hand-limit-hint.jpg). Вырезка — [defect-portraits-over-hand.jpg](defect-portraits-over-hand.jpg).
   - Предложение: сделать колонку портретов препятствием для панели руки, то есть сдвигать или сужать панель руки, когда её левый край заходит за правый край портретов (24 + ширина портрета + отступ). Другой вариант — ограничить ширину чипов.
   - Задача — проход исправлений DE-023 или DE-031 (там же стоит «плашка не ложится на портрет»).
3. **DE-024, открыт, мелкий.** Вторая строка тоста «Click to close» обрезана: фон кнопки кончается на первой строке, а вторая строка уходит под ленту. Видно на [кадре тоста](pkg1-986d194b/sarpedon/combat-20261005-134200/joiner/s09-hand-limit-hint.jpg) и на вырезке. Задача — проход исправлений DE-024.
4. **DE-026 / DE-031, замечание.** Плашка бойца встаёт вплотную к правому краю слота: [Marmoreal, пакет 1, хост](pkg1-986d194b/marmoreal/combat-20261005-133944/host/s09-card-slot-own.jpg), плашка Medusa у края. Это известный риск: слот пока не препятствие для плашек (хвост DE-026 → DE-031).
5. **Замечание.** Ход часто переходит снапшотом, который закрывает бой соперника. Тогда баннер «YOUR TURN» появляется, пока на экране ещё карты боя и метка исхода. Баннер стоит под меткой (+132) и с ней не пересекается. Дефектом не считается.
6. **Шум доказательств.** На пакете 1 на хосте Sarpedon три кадра доказательств пришлись на три соседних кадра подряд, по 250 мс каждый. Баннер (600 мс) успел погаснуть до своего снимка. На итоговом пакете баннер снят на всех четырёх клиентах. Клиент не виноват.
7. **Шум гейта S09.** Партия «Быстро» не опубликована из-за 1 пикселя маркера защиты на кадре результата хоста.
8. **Известное из прогона D (замечание 5).** Тост действия по центру («begin maneuver sent …») держится и в ход соперника и стоит над лентой. Это MS-T-27.

## Процессы

- **Запускал агент:**
  - сборки UBT;
  - UE-тесты;
  - две упаковки RunUAT;
  - пары клиентов: 5 прогонов `run-combat-demo` (4 опубликованы, 1 — «Быстро» — нет) и 3 прогона `run-phase2-demo`.
- Все процессы завершились сами. Перед отчётом проверено, что не осталось ни одного Unmatched, UnrealEditor, UBT или UAT. Замок снят.
- Временную папку неопубликованной партии (`%TEMP%\s09-combat-20261005-140045-40692`) агент удалил после копирования трасс. Чужие временные папки не трогал.
- **Docker-стек** был поднят до агента и оставлен как есть.
- **Приватность.** Коды комнат в трассах заменены на `<redacted>`. Email и паролей в трассах нет.
