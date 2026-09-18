# S01 — проверяемый baseline

18 сентября 2026. Ветка `codex/s01-baseline`, база `3feaa9beb4a8e6f5f0c50ad4a7738e7bf06947c1`. **GD-001..005 выполнены в пределах S01.** Это техническая сборка и проверка контрактов; соответствие всей игры правилам, законченная партия и ACC-001..022 целиком ещё не приняты.

## Что можно запустить

- Windows Development: [`Unmatched.exe`](../../../../unreal/Unmatched/Artifacts/S01/Windows/Unmatched.exe). Локальный пакет около 935 MB, воспроизводится скриптом и не включён в Git.
- [UE-проект](../../../../unreal/Unmatched/Unmatched.uproject), [инструкция сборки](../../../../unreal/Unmatched/README.md), [отчёт импорта/запуска](ue/README.md), [кадр из packaged](ue/packaged-smoke.png).
- [Эталон правил](rules-oracle.md), [17 контрольных ситуаций](rules-cases.json), [свежая GraphQL SDL](schema.graphql), [сводка измерений API](observations.json).

Сцена строится из живого обезличенного fixture: 30 клеток и шесть примитивов бойцов. Пробный куб экспортирован Blender и импортирован UE. Это даёт художнику работающий путь подготовки сцены независимо от исправлений backend.

## Версия и происхождение

Исходный проект: `C:\Users\ren\WebstormProjects\unmached\unmached`. Worktree первоначально был на `0641577`, затем **до проверок** переведён на аудитный HEAD `3feaa9b`. Скопированы только пакеты документации `docs/game-design`, `docs/unreal`, `docs/backend-api`. Унаследованные примеры тестовых credentials в девяти скопированных документах заменены placeholders; [список](documentation-redactions.json), оригиналы сохранены. Незакоммиченная реализация исходного проекта не переносилась. [Provenance](provenance.json) содержит SHA-256 всех 37 изменённых tracked-файлов исходного дерева и соответствующих файлов базы.

Live API запускался из `SOURCE_ROOT/backend/dist/src/main`, а не из worktree. Существенные отличия dirty-исходников от базы: исправление поиска героя по DB ID в `content-db.service.ts` и перенос URL изображений в `content.mapper.ts`; есть также seed/data/web-изменения, перечисленные в provenance. Ошибку каталожного `movement=3` и сериализации effect timing мы **наблюдали**, а не исправляли. Нельзя считать worktree HEAD полной копией deployed backend.

Первый захват 07:54–07:57 UTC повторён после внешнего перезапуска backend в 08:00:12 UTC и после исправления очистки устаревших файлов harness. Время итоговых HTTP/WS fixtures указано в `health.json` и `combat-findings.json`. [Environment](environment.json) фиксирует новый PID; [runtime fingerprint](runtime-fingerprint.json) — 212 JS-модулей на диске. Исходные dirty-файлы не изменились между preflight и повтором. Хэши файлов не являются снимком V8-памяти процесса. S01 не перезапускал общий сервер и не изменял его БД напрямую.

UE **5.8.2**, changelist **56702186**; Blender **5.2.2 LTS**, build **d13f752e3b9c**; MSVC **14.44.35228**, Windows SDK **10.0.22621.0**. Версии проверены установленными файлами/исполняемыми программами. Точная конфигурация и хэш EXE — [build-manifest.json](ue/build-manifest.json).

## GD-001 — доступная среда

HTTP: `http://localhost:3000/graphql`; WS: `ws://localhost:3000/graphql`, протокол `graphql-transport-ws`. Health: `http://localhost:3000/health`; PostgreSQL и Redis отвечают `up`. Контейнеры `unmatched-postgres` и `unmatched-redis` уже работали; использованы без reset/migrate/seed.

Два существующих локальных тестовых аккаунта вошли успешно: [accounts.json](accounts.json). Fixture-имена — `player-1` / `player-2`; в доказательствах нет логинов, паролей, JWT. Harness получает credentials из переменных `S01_P1_EMAIL`, `S01_P1_PASSWORD`, `S01_P2_EMAIL`, `S01_P2_PASSWORD`; на этой машине использован fallback чтения существующего `backend/scripts/setup-test-game.mjs`. **Сам старый скрипт не запускать:** он печатает токены и завершает другие активные партии.

Новые комнаты созданы через create/join/select/ready/start. По окончании abort вызван только для комнат, созданных конкретным запуском harness; существующие игры не затронуты. Случайная тасовка сохраняется в каждом снимке; повтор не обязан дать ту же руку.

При необходимости поднять локальные зависимости исходного проекта: `docker compose up -d postgres redis`; затем из его `backend/` запустить `npm run start:dev` при имеющемся локальном `.env`. Не делать этого поверх уже занятого порта 3000. Секреты/БД в worktree не копировались. Для воспроизведения на другом компьютере нужны собственные два разрешённых аккаунта, локальный сервер с контентом пары и npm-зависимости; S01 не включает перенос чужих credentials/БД.

## GD-003 — десять сверок TASK-012

| № | Наблюдение | Доказательство и следующий владелец |
|---|---|---|
| 1 | Cobble City: **5×6, 30 уникальных клеток**, зоны blue/red по 15; мультизон нет. Явного графа соседства и стартовых областей в payload нет. Шесть бойцов размещены без наложений. | `content-board.json`, `duel-start-p1.json`, `observations.json`. Размеры зафиксированы; тактическую версию/граф/старт принимает DEV в GD-014/016. Финальная модель доски остаётся за этим gate. |
| 2 | Medusa перенесена в красную зону обычным maneuver; после передачи ей хода Arthur **18→17**, Merlin **7→7**. Оба были законными целями зоны; pending/отказа нет. | `combat-before-gaze.json`, `combat-after-gaze.json`. Generic-способность исполняется, но нарушает optional choice. DEV/GD-017. |
| 3 | Обе WS-проекции атаки доставлены. В metadata/combatInfo есть startedAt, но **нет timeoutAt**. После 32 секунд с закрытыми WS и без defense/resolve: sequence **3→4**, фаза `COMBAT_RESOLVE`, HP Arthur **18**, урон отсутствует. | `combat-p1-ws.json`, `combat-p2-ws.json`, `timeout-attack.json`, `timeout-after.json`. DEV/GD-026; UI не выводит новый 30-секундный deadline самостоятельно. |
| 4 | Первый pass: actions **2→1**, рука и колода неизменны, сброс пуст. Второй: ход передан, соперник получил лишний добор **5→6**, draw pile **25→24**. | `duel-pass-1.json`, `duel-pass-2.json`, `duel-after-pass-p2.json`. Описание mutation ошибочно обещает сброс/дополнительное действие. DEV/GD-010. |
| 5 | maxSize руки **7** у обеих сторон. В живом контенте и instance-картах используется **VERSATILE**, не UNIVERSAL; четыре каталожных типа ATTACK/DEFENSE/SCHEME/VERSATILE. | Стартовые дампы, `content-*.json`, `schema.graphql`. Это форма DTO, не доказательство корректного лимита в конце хода; GD-012. |
| 6 | В attack отправлен **HandCard.id с `::copy`**, именно он исчез из руки и появился в сбросе. Защита также отправлена по instance ID. | `combat-attack.json`, `combat-defense.json`; `analyze.py` проверяет перенос экземпляра. Legacy catalog-ID тоже допускается прочитанным кодом поиска, но live-мутация по нему не проверялась. |
| 7 | Первым ходит host/seat0 (`player-1`). Medusa (2,2), Harpies (3,2)/(2,3)/(3,3), Arthur (1,3), Merlin (2,4). | `duel-lobby.json`, оба стартовых снимка. Своп сторон и законные стартовые области — GD-016; S01 не утверждает текущую расстановку как правила. |
| 8 | Select и start **разрешили Medusa против Medusa**, состояние создано. | `duplicate-lobby.json`, `duplicate-start.json`. Исправление ограничений пары — DEV/GD-016. |
| 9 | Дальняя атака Medusa из (0,3) в Merlin (2,4) принята по общей красной зоне. Атака смежного Arthur через границу зон также принята в timeout-сценарии. **Мультизонный случай заблокирован: в реальном Cobble City нет таких клеток.** | `combat-attack.json`, `timeout-attack.json`. Не менять общую БД ради проверки. Адресный fixture после фиксации карты — DEV/GD-014; текущий код читает только legacy `zone`. |
| 10 | Arthur movement: **3** в public hero, **2** в admin content и fighter. | `catalog-king-arthur.json`, `content-king-arthur.json`, `duel-start-p1.json`. Для сцены/движения источник fighter; каталог исправить в контрактном проходе GD-019/027. |

**Колоды:** live content содержит Medusa 11/30 и Arthur 16/30. Для каждого участника объединены его стартовые 5 карт руки и 25 draw pile: 30 уникальных instance ID, тираж каждой записи совпадает с live content. Независимо проверены названия/тиражи исходного RSC scrape; небольшой hash-linked extract лежит в `_validation/deck-counts-reference.json`. Это не проверка исполнения 27 эффектов.

Дополнительные найденные факты:

- Public `hero.cards.effects.timing` падает с `Enum EffectTiming cannot represent value: a_f_t_e_r_c_o_m_b_a_t` для обеих колод. Ошибки сохранены в `catalog-*-error.json`; полный текст эффектов взят read-only из admin content. Владелец DEV/GD-019, согласование схемы — GD-027. В UE не вводить enum с этим ошибочным значением.
- Maneuver с `moves:[]` отклонён (`combat-zero-move-error.json`); исправление GD-013.
- Чужая WS-проекция содержит instance/cardId руки и объявленную атакующую карту/значение до раскрытия. Снимки намеренно показывают фактическую утечку на тестовых данных, не утверждают приватность API. GD-025/ACC-009 остаётся открыт.
- Полный snapshot включает decks/discardPiles; WS schema этих полей не имеет. Сохранены обе формы и `eventsSince`; восстановления/replay этим прогоном не доказано. GD-027/037 остаются открыты.

## GD-004 — импорт и запуск

Editor и Win64 game targets собраны; cook/stage/package завершились успешно. Standalone Development исполняемый файл запущен с рендером вне Editor, записал `S01_SMOKE_READY` с полным URL, кадр и `S01_SMOKE_COMPLETE`, затем завершился с exit 0. [Логи и замеры](ue/README.md).

Куб: bbox min≈(−50,−50,0), max≈(50,50,100) uu, один material slot. Подтверждены масштаб, нижний pivot и получение static mesh в UE. Фиксированная камера показывает всю сцену. Arrow/оси, rig/clips, zoom, gameplay HUD, сеть, художественное принятие и performance gate **не выполнены**. Открытый Editor и Blender пользователя не закрывались.

## GD-005 — ближайшие два спринта

Оценки оставлены **S02=7 DEV дней, S03=8 DEV дней**: живые результаты подтверждают объём уже учтённых AUD; оснований сокращать его из-за быстрой генерации smoke нет. У каждого спринта сохраняются 2 дня резерва из исходных 10; S02 имеет ещё 1 неназначенный день. Это оценка труда одного разработчика с ИИ, не время работы этого чата.

| Последовательность | План после S01 | Выход |
|---|---|---|
| S02: GD-006 1.5д → GD-007 2д → GD-008 2д → GD-009 1.5д | Исправлять рабочий executor и альтернативный resolver, не обходить баг в UE. Терминальный контроль охватывает будущий draw/exhaustion. Использовать S02-cases из oracle и entry-point тесты; случайная live-рука не является oracle. | 2 против 5, ничья, prevent, Feint, смертельный удар по герою с живым помощником и смерть только помощника. Все ожидаемые HP/победитель — из GD-002. |
| S03: GD-010 1.5д → GD-011 2д → GD-012 1.5д → GD-013 3д | Удалить pass/лишний добор; общий draw; end-turn discard choice; begin/complete maneuver. В первые 0.5д GD-013 внутри его 3д определить persistent pending DTO и точку продолжения. Не переносить клиентский boost-выбор до draw. | Возобновление без двойного добора/траты действия, разрешённое 0-движение, добранная карта доступна для boost, истощение/лимит руки по oracle. |

Новая неопределённость не добавляет задачи сверх capacity молча: если GD-012/013 требуют более общей очереди, явно перенести равный объём и пересчитать зависимость GD-018. S02/S03 сами не исправляют всю приватность/таймауты и не называются публично пригодной сетевой игрой.

Арт может продолжать ART-001 (стрелка, манекен/rig) и ART-002 (варианты направления) на этой UE-сцене. GD-004 не закрывает ART-001 целиком. Финальная доска ждёт GD-014, серия моделей — GD-058 и rules-gate S06. Неизвестные карточные формулировки перечислены с владельцами в [oracle](rules-oracle.md), GD-017..023; никакой manual/no-op не принят как реализация карты.

## Воспроизведение проверок

Из корня worktree, при работающем локальном API и доступных npm-зависимостях исходного проекта:

```powershell
node tools/s01/capture.mjs
node tools/s01/live.mjs
node tools/s01/combat.mjs
python tools/s01/analyze.py
node tools/s01/verify_capture.mjs
node tools/s01/verify_cleanup.mjs
python tools/s01/verify_artifacts.py
python docs/game-design/_validation/validate_package.py
./tools/s01/ue_build.ps1
./tools/s01/ue_smoke.ps1
```

`S01_SOURCE_ROOT` меняет путь поиска локальных npm-модулей и существующей credential fixture; `S01_HTTP` меняет loopback endpoint. Harness не работает с внешним адресом. Live-команды создают временные игровые записи и перезаписывают собственные доказательства; для сохранения этого baseline сначала скопировать каталог evidence/S01. Пароли передавать только через локальное окружение, не добавлять в командные логи.

Заново выполнены существующие две Medusa Jest suites: **5 passed, 132 skipped** ([лог](medusa-existing-tests.txt)). Это тесты текущего generic-поведения на fixtures; они не закрывают ACC-016. Документальный валидатор проверяет 69 задач, 34/34 TASK, DAG, capacity и ссылки на доказательства изменённых статусов. Проверка снимков отдельно проверяет counts/instance IDs/координаты, наличие обеих WS-проекций и отсутствие credentials/JWT. Результаты — [verification.txt](verification.txt).

Открытые gates: мультизонный live-тест и тактическая геометрия; arrow/rig/zoom/арт; корректность правил, API-приватность и reconnect; полная PvP/VS_AI партия; производительность на названном среднем ПК. Среда S01 доступна. Следующий шаг — **GD-006**.
