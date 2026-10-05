# Прогон E: проход исправлений по ревью — живая проверка (2026-10-05)

Журнал и решения — [E-2026-10-04.md](../../../../../de-footage/task/runs/E-2026-10-04.md), раздел «Исправления по
ревью». Здесь только доказательства.

## Сборка

- Одна упаковка на проход: `package-client.ps1 -SkipBuild`, `UAT_EXIT=0`, ошибок и предупреждений cook нет.
- Штамп в [BuildStamp.json](BuildStamp.json): commit `2c3ed515`, sourceHash `22a11a41…`, 185 файлов.
- Перед упаковкой: сборка UnmatchedEditor и игровой цели `Result: Succeeded`; UE `S08+S09+S10` — 348/348 Success.

## Прогоны

Окружение то же, что у приёмки E: основной стек `:3000`, обёртки `C:/tmp/e-live/run-combat.ps1` и `env-s08.cjs`
(учётные данные только в окружении процесса), два клиента offscreen, 1920×1080, High, 30 FPS на клиент,
`-JoinerAttack -HostScheme`.

| Прогон | Итог | Что в нём |
|---|---|---|
| [sarpedon-chain/](sarpedon-chain/) — Sarpedon original | партия до FINISHED, но скрипт её **не опубликовал**: пиксельный гейт кадра результата джойнера нашёл 1 пиксель маркера защиты (`rst=2261 res=0 def=1`) — тот же шум гейта S09, что и в партии «Быстро» приёмки E. Трассы взяты из временной папки, код комнаты заменён на `<redacted>` | схема соперника и цепочка удержания (DE-026) |
| [marmoreal/](marmoreal/) — Marmoreal original, `-ConceptPaste` | опубликована, `GAME_OVER gate ok`, победил хост | широкая рука у колонки портретов (DE-023), плашка рядом со слотом |
| Sarpedon original, второй прогон | опубликован во временную папку (`GAME_OVER gate ok`), в доказательства не перенесён: схемы соперника и тоста в нём не выпало | `HUD-HAND layout … shifted=0`, `check-trace` PASS |

`cue_contract.py check-trace --min-ms-cue 1 --min-combat 1 --min-death 1` — `CUE_TRACE PASS` на всех шести трассах,
stale 0, duplicate 0.

На всех кадрах: настоящая карта; Marmoreal — нарисованный задник (`-ConceptPaste`, IMPL п. 3), Sarpedon — lit3d
(`concept-scene … mode=lit3d`); шесть фигур v2 (`ARTLOOK art=1 source=default heroes=v2`, `heroes v2 … figures=6`).

## DE-026 — цепочка удержания схемы соперника

Джойнер, [combat-client-joiner.trace.txt](sarpedon-chain/combat-client-joiner.trace.txt):

```
HUD-SLOT show seq=25 ribbon=scheme owner=opp card="A Momentary Glance" … hold=1500 min=1700
HUD-SLOT chain seq=25 add=26 n=2 why=choice          ← хост ответил на выбор схемы (TARGET_FIGHTER), ход перешёл
HUD-SLOT cues held seq=26 of=25 n=1 total=1          ← урон 2 от схемы ждёт
ATTACK sent …                                         ← автоклиент джойнера сразу атакует (новое действие)
HUD-SLOT effect seq=25 release=newseq afterArrive=1166 chain=2
HUD-SLOT cues play seq=26 n=1 why=newseq carry=27
HUD-SLOT cues flushed seq=27 n=1
CUE damage f-0-hero -2 seq=26                         ← урон схемы показан (число и HitReact), не потерян
HUD-SLOT off seq=25 ribbon=scheme shown=2189 reason=done   ← карта держалась дольше времени чтения 1700
```

До исправления seq 26 отпустил бы удержание без проигрывания CUE seq 25 (`release=newseq` за ~1 с, как
`afterArrive=1120` в приёмке E). Отпускание здесь сделало новое действие самого джойнера (атака в его ход) — по
правилу так и должно быть.

Кадры: [схема соперника в слоте](sarpedon-chain/joiner-s09-card-slot-opp.jpg) (лента SCHEME, строка пропуска; рука
5 карт правее портретов), [MOVE в свой ход](sarpedon-chain/joiner-s09-pending-MOVE.jpg) (панель руки начинается правее
колонки портретов).

## DE-023 / DE-024 — панель руки и колонка портретов

- Трассы: `HUD-HAND layout left=283 panel=1425 canvas=1920 columnRight=271 gutter=12 shifted=1 wrap=1601` (Marmoreal,
  джойнер, рука 6 карт King Arthur с длинными именами). Без исправления центрированная панель шириной 1425 su
  начиналась бы с 247 su — под портретами.
- [Кадр баннера, Marmoreal, джойнер](marmoreal/joiner-s09-turn-banner.jpg): лента событий, строка статуса,
  «YOUR HAND 6/7» и первая карта «Noble Sacrifice» начинаются правее портретов, ничего не закрыто.
- [Своя схема в слоте, Marmoreal, хост](marmoreal/host-s09-card-slot-own.jpg): плашка Medusa встала правее слота, с
  зазором (слот — мягкое препятствие плашки).
- Тост лимита руки (DE-024) в этих партиях не выпал: рука не доходила до 7. Тост — первая строка панели руки, поэтому
  он сдвигается вместе с ней; причина обрезки (портрет поверх второй строки) устранена.

## Процессы

Запускались: сборки UBT, UE-тесты, одна упаковка RunUAT (первая попытка остановлена на ходу ради правки
`2c3ed515`, дочерних процессов не осталось), три пары клиентов. Все завершились сами, замок GPU снят.
