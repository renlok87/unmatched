# S03: проверка HTTP и WebSocket

Проверен реальный локальный Nest/Apollo HTTP endpoint `/graphql` и протокол
`graphql-transport-ws` на случайном loopback-порту. Запросы выполняют production
`GameActionsResolver`, `GameResolver`, `GameSubscriptionResolver`, executor,
сервис состояния с compact serialize/deserialize и приватной фильтрацией,
сервис подписок и проверки участника/фазы/статуса. Клиенты `a` и `b` подключаются
раздельно. Ответы сохранены в [transport-results.json](transport-results.json).

Внешняя инфраструктура изолирована: синтетическая авторизация по двум fixture
идентификаторам; JSON-адаптеры БД и Redis cache; локальный последовательный lock.
Postgres, Redis-сервер, JWT, очередь, AI, deployed backend и UE этим запуском
не проверяются. Принудительное удаление cache обеспечивает проверку production
DB-deserialization при восстановлении pending.

Три сценария, 20 HTTP-ответов и 14 WS-обновлений:

1. Начало манёвра отдаёт добранную карту владельцу; чужая рука содержит только
   маски, обе колоды скрывают порядок и верхнюю карту. Владелец отключает WS,
   cache удаляется, новый WS-клиент подключается с `since: 11`, оба игрока получают
   snapshot через `gameState`. Pending ID, рука, колода и sequence сохраняются.
   Завершение с `moves: []` не добирает и не тратит действие повторно; повторы
   begin/complete отклоняются.
2. Карта, полученная после begin, используется для BOOST этого же манёвра:
   движение на 5 клеток при базовых 2, один сброс, один добор, одно действие.
3. Восьмая карта доступна после begin. После завершения последнего действия
   `TURN_END` остаётся у владельца до выбора точной лишней instance-карты.
   Pending переживает cache eviction и snapshot reload. Чужой выбор,
   catalog ID и повторный выбор отклоняются. После сброса ход передаётся без
   автоматического добора следующему игроку.

Для каждой успешной мутации проверяется `sequenceNumber + 1` и ровно одно
`gameStateUpdated` каждой стороне. Приватность проверяется по сырым JSON-ответам
HTTP/WS: в чужой руке отсутствуют исходные instance/catalog IDs, тип, banner,
boost и текст добранной карты. В JSON присутствуют только синтетические данные.

Воспроизведение из корня checkout с установленными backend dependencies:

```powershell
./tools/s03/run_transport.ps1
```

Для другого пути вывода:

```powershell
./tools/s03/run_transport.ps1 -ReportPath C:/temp/s03-transport-results.json
```

Сам spec: `backend/src/games/resolvers/s03-transport.spec.ts`. Общие fixtures:
`backend/src/test/fixtures/s03-engine.fixture.ts`; импорт не запускает другие specs.
Подписка ожидает будущих событий; snapshot при reconnect запрашивается отдельно,
как в текущем контракте. Это не проверка replay пропущенных событий или полной
приватности всех игровых данных за пределами S03.
