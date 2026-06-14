# Engine gaps — parallel batch (2026-06-14)

Branch: `fix/admin-panel`. Метод: superpowers (brainstorm→plan→dispatch-parallel-agents), TDD per task, file-disjoint для безопасной параллельности.

## Контекст / коррекции к исходному списку

- `deck-management.initializeDeck` — **НЕ гэп**. Удалён в A8; реальная раздача колод через `GameInitializationService.initializeGameState()` (drawPile из `hero.cards`, стартовая рука 5).
- Board admin CRUD — **уже есть** (`admin/src/pages/boards/{list,create,edit,show}.tsx`, JSON-редактор `cells`/`features`). Реальный гэп — **валидатор геометрии** (JSON принимается без проверок).
- Tokens / per-hero abilities (50 шт) / choose-one opponent-targeting — **design-heavy, отложены** (требуют brainstorm-сессии, не слепой грайнд).

## Batch (4 параллельных TDD-агента, file-disjoint)

### A — TURN_START infra wiring (engine/turn)
Проблема: `triggerOnTurnStartExtended` существует, но фаза TURN_START исключена из prod-потока (`game-action-executor.service.ts:153`); два пути диспатча (`GameEvent[]` vs `GameState`).
Scope: при старте хода вызывать зарегистрированные `onTurnStart` хуки через единый путь; **без изменения поведения текущих героев** (ms-marvel остаётся reserved/no-op). Тест: фиктивный hero-handler с `onTurnStart` → хук срабатывает на старте хода, state мутируется.
Files: `turn-management.service.ts`, `game-action-executor.service.ts`, `hero-ability-registry.ts`, новый `.spec.ts`.

### B — Parser coverage expansion (parser)
Поднять 240/712. Бакеты: `unless`-условия, `do both:` (не choose), улучшить named-fighter adjacency. TDD: спека измеряет покрытие до/после.
Files: `effect-text-parser.ts`, `effect-text-parser.spec.ts` (ИЗОЛИРОВАН).

### C — Admin game cleanup (admin/games)
Admin-инициируемая очистка: мутация удаления FINISHED/ABORTED старше N дней + abort зависших IN_PROGRESS + кнопка в admin UI. Тест на сервис-метод.
Files: `admin.service.ts`, admin resolver, `admin/src/pages/games/list.tsx`, `.spec.ts`.

### D — Board geometry validator (standalone)
Чистая функция-валидатор cells JSON: in-bounds, уникальность (x,y), связность connections (двусторонность), валидность zone. Полная спека. Wiring в create/update — потом вручную (избегаем конфликта с C по admin.service.ts).
Files: новый `board-geometry.validator.ts` + `.spec.ts`.

## Verify
Полный `npm test` (backend) зелёный. Затем коммиты явными путями (как прошлая сессия), `--no-verify` (сломанный pre-commit hook).
