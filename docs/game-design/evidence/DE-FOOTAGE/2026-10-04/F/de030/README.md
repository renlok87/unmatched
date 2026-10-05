# DE-030 — панель «Колода»: кадры редактора (2026-10-05)

Это не живая приёмка. Живые кадры панели в партии на Marmoreal original и Sarpedon original (G-LIVE) снимает DE-031
и агент приёмки прогона F. Здесь — проверка вида боковой панели до упаковки.

## Данные

Данные взяты из одной настоящей партии. Её создал скрипт ревью на локальном бэкенде `:3000` с новым запросом:
- партия ONE_V_ONE на Marmoreal original (Board `c121b47f8d6eb28daccb76d05`), Medusa (хозяин, зритель) против
  King Arthur, сразу после `startGame`;
- аккаунты — сидовые `pro@` и `veteran@` (`backend/prisma/seed.ts`);
- после съёмки обе стороны вышли, партия `ABORTED`.

| Файл | Что это |
|---|---|
| `de030-bench-marmoreal.json` | `gameState` хозяина в форме бенч-фикстуры (`benchViewerId`, `benchBoardId`) |
| `de030-decklists-marmoreal.json` | ответ `gameDeckLists` той же партии: Medusa — 30 карт, 11 видов; King Arthur — 30 карт, 16 видов |

Проверки скрипта на живом сервере:
- в проекции соперника нет ни одного instance-id руки хозяина, все `drawPile` — плейсхолдеры, `topCard` нет;
- в ответе `gameDeckLists` нет instance-id;
- запрос без токена отклонён («Неавторизованный доступ»).

## Кадры

Кадры уменьшены до 1280×720 (JPEG 85). Исходник — 1920×1080, редактор `-game`, offscreen, 30 FPS, High,
`-ConceptPaste=paste` (IMPL п. 3):

```
UnrealEditor.exe unreal\Unmatched\Unmatched.uproject /Game/S08/S08Arena?game=/Script/Unmatched.S08FlowGameMode -game
  -windowed -resx=1920 -resy=1080 -ForceRes -RenderOffScreen -ArtPreview -Bench -BenchOut=<dir> -BenchViews=K1
  -BenchWarmup=20 -BenchSettle=3 -BenchMeasure=1 -BenchFps=30 -BenchNoProfileGPU -S08RenderPreset=High
  -ConceptPaste=paste -BenchFixture=<de030-bench-marmoreal.json> -BenchDeckPanel=own|opp
  -BenchDeckLists=<de030-decklists-marmoreal.json>
```

`-BenchDeckPanel` — инструмент ревью DE-030. Он строит модель HUD из фикстуры тем же `FS09HudModel::Build`, что и
живой клиент, берёт списки из файла вместо запроса и открывает панель в покое (полностью открытой).

| Кадр | Опции | Что видно |
|---|---|---|
| `de030-deck-own-marmoreal.jpg` | `-BenchDeckPanel=own` | Справа панель «YOUR DECK · Medusa» с вкладками и кнопкой закрытия. Сводка «IN DECK 25 · DISCARD 0 · HAND 5». 11 строк, копии рядом: «x3 Feint … IN HAND 2 · LEFT 1», «x3 Clutching Claws … IN HAND 1 · LEFT 2». Сумма LEFT = 25 = число карт в колоде с сервера. Слева видно поле Marmoreal, шесть v2-фигур, рука и портреты |
| `de030-deck-opp-marmoreal.jpg` | `-BenchDeckPanel=opp` | «OPPONENT DECK · King Arthur», «IN DECK 25 · DISCARD 0», «HAND 5» и пять рубашек. 16 строк без меток руки и без LEFT: его рука и колода неотличимы |

Трассы бенча:
- `DECK model side=own list=1 kinds=11 copies=30 deck=25 discard=0 inHand=5 inDiscard=0 left=25 out=0`;
- `DECK model side=opp list=1 kinds=16 copies=30 deck=25 discard=0 backs=5 inDiscard=0`.

Кадры просмотрены. Поле — реальная карта Marmoreal, фигуры — v2. Метки «DISCARD» на этих кадрах не видны: партия
свежая, сброс пуст. Метки сброса и автозакрытие проверяет живая партия DE-031. Вид задника Marmoreal — тема ENV-U16,
к DE-030 она не относится.
