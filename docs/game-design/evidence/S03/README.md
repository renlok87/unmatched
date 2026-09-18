# S03 — ход и ресурсы

Дата: 2026-09-18. База: интегрированный S02 `94312c6`. Реализация и этот протокол входят в один коммит S03; точная ревизия доступна через `git log -1 -- docs/game-design/evidence/S03/README.md`.

## Реализованный контракт

| Задача | Результат | Доказательство |
|---|---|---|
| GD-010 / ACC-003 | Два обязательных действия; нет добора при передаче хода, свободного pass, раннего endTurn и отдельного движения в обход манёвра. Явные END_TURN и GAIN_ACTION сохраняются. | `s03-turn.spec.ts`; прежние ability/turn suites |
| GD-011 / ACC-004 | Общий draw допускает >7 карт; каждый недостающий добор наносит отдельные 2 урона всем живым своим бойцам, проверяет смерть героя и останавливает цепочку. Сброс не рециклируется. | `s03-draw.spec.ts`; S02 terminal; card-effect и generic-ability tests |
| GD-012 / ACC-005 | Лимит 7 проверяется после завершения действий и turn-end hooks. Владелец выбирает ровно лишние instance IDs, pending сохраняется, чужие/дублированные/неверные/повторные выборы отклоняются. Turn-end hooks не повторяются. | `s03-turn.spec.ts`; state DB/cache roundtrips; HTTP/WS discard scenario |
| GD-013 / ACC-006 | begin тратит одно действие и добирает одну карту; complete выбирает BOOST и ноль/одного/нескольких бойцов. Новая карта доступна до выбора. Последнее действие не передаёт ход до complete. | engine fixtures; API schema; реальный localhost HTTP/WS harness; AI tests |

### API

1. `beginManeuver({ gameId, expectedSequenceNumber })`: устаревший sequence отклоняется. Ответ содержит `metadata.pendingManeuver { id, playerId }` и добранную карту в собственной руке.
2. `maneuver({ gameId, maneuverId, moves, boostCardId? })`: точная identity из pending; `moves: []` допустим. BOOST использует instance ID. Добор и действие не повторяются; неверный выбор оставляет уже выполненный begin сохранённым.
3. При необходимости `metadata.pendingHandDiscard { id, playerId, count }` удерживает `TURN_END` у заканчивающего игрока. `discardToLimit({ gameId, pendingId, cardIds })` завершает этот выбор и передаёт ход один раз.

Каждая принятая мутация увеличивает sequence ровно на 1. Повтор запроса отклоняется; клиент восстанавливается из snapshot. Это защита стадий S03, не общая idempotency/recovery всех действий из следующих спринтов.

Чужая рука отдаёт только маски и количество; фактические instance/catalog IDs, тип, текст и boost скрыты. Обе колоды скрывают порядок и верхнюю карту. Полный privacy-аудит API/event history остаётся S07.

## Проверки

- До изменений: 838 backend tests, 835 прошли, 3 существующих падения в `auth/auth.service.spec.ts`.
- После backend реализации: 892 tests, 889 прошли, те же 3 auth failures; 44 suites прошли, 1 auth suite failed. Ошибки: два refresh-token сценария и ожидание ответа validateUser без поля role.
- `npm run build` в backend: exit 0.
- Новые regression tests сначала воспроизводили ошибки (pass/endTurn, hand cap/exhaustion, DTO/persistence/privacy), затем стали проходить.
- Независимое read-only ревью backend: блокирующих замечаний нет. Дополнительно проверен сброс атакующего после завершения второго боя защитником.
- [HTTP/WS](TRANSPORT.md): 3 сценария, 20 HTTP-ответов, 14 WS-обновлений; [сырые fixture-ответы](transport-results.json).

Воспроизведение backend:

```powershell
cd backend
npm test -- --runInBand
npm run build
cd ..
./tools/s03/run_transport.ps1
```

## Границы

Engine и transport используют синтетические детерминированные карты и production gameplay services. Внешние JWT/Postgres/Redis/очереди в transport заменены описанными isolated adapters; compact DB serialization выполняет production код. Deployed сервер и UE gameplay этим протоколом не проверены.

S04 (GD-014…016, GD-018), полные колоды/способности, сетевые timeout/recovery и UE остаются последующими задачами. Начальные S01/S02 данные и посторонние изменения основного checkout сохраняются; remote push не входит в работу.
