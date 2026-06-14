# Hero abilities — data-driven framework (2026-06-14)

Branch `fix/admin-panel`. Реализовано через 2 workflow (design/audit → implement). 561/564 backend-юнитов (3 fail = pre-existing auth).

## Реальный wiring хуков (аудит)

Prod-геймплей идёт ТОЛЬКО через `GameActionExecutorService`. До этой работы в проде жили 2 хука, добавлены ещё 2:

| Хук | Путь | Статус |
|---|---|---|
| combat-модификаторы | КЛАССИЧЕСКИЙ `applyCombatModifier`→`ValueModifier[]` (суммируется только `ADD`), `combat-resolver.getHeroCombatModifiers` | был live |
| turn-start | extended `onTurnStart(state)` via `advanceTurn`→`triggerHeroTurnStart` | был live (14.06) |
| **stateful combat** | NEW `getStatefulCombatModifiers(state, ctx, fighter, role)` — combat-хук С доступом к GameState (условия) | **добавлен** |
| **turn-end** | NEW `triggerHeroTurnEnd` в `advanceTurn` (для завершающего игрока, до смены) → `triggerOnTurnEndExtended` | **добавлен** |

Мёртвые (НЕ wired, для v2): `getCombatModifiers`/`CombatModifier[]`, `onCombat`, `onMove`, `onDefeat`, `canAttackAtRange`. Lookup везде `fighter.heroSlug ?? heroId`.

## Generic data-driven фреймворк

- `ability-config.ts` — декларативный `AbilityConfig {heroId(slug), abilityName, description, rules[]}`; `AbilityRule {trigger, condition?, effect}`.
  - triggers: `combat-passive` | `turn-start` | `turn-end`.
  - conditions: `always` | `attacking` | `defending` | `self-health-below-defender` | `all-own-sidekicks-defeated` | `no-enemy-in-own-zone` | `{handSizeEquals:N}`.
  - effects: `{kind:'combat-modifier', appliesTo, value}` (ADD) | `{kind:'turn-effect', draw?/drawToHandSize?/heal?/gainAction?}`.
- `generic-hero-ability.handler.ts` — `GenericHeroAbilityHandler` интерпретирует config через `getStatefulCombatModifiers`/`onTurnStart`/`onTurnEnd`. Чистый no-op (===) если правило не сработало (seq не дёргается).
- Регистрация: цикл в `game-engine.module.ts onModuleInit` — добавить героя = ОДНА строка в `ABILITY_CONFIGS`, без новых файлов/провайдеров. Хардкод daredevil/ms-marvel/arthur сохранён.

## Шипнуто (14 героев = 3 хардкод + 11 config)

Хардкод: daredevil, ms-marvel, king-arthur.

Config v1 (7): luke-cage (+2 def always), annie-christmas (+2 atk if HP<defender), eredin (+1 both если все sidekick'и мертвы) [combat]; bloody-mary (gainAction если рука==3) [turn-start]; philippa (draw до 4), t-rex (draw 1), bigfoot (draw 1 если в зоне нет врагов) [turn-end].

Config v2 — after-attack (4): chupacabra (draw 1), deadpool (heal 1), michelangelo (draw 1; hand-cap-3 НЕ смоделирован), angel (draw 1 if lost-combat). Хук `after-attack` + condition `won-combat`/`lost-combat` добавлены. **Хук after-combat теперь wired**: `triggerOnAfterCombat(attacker, ctx{won,damageDealt,...})` в executeResolveCombat до advanceTurn (`onAfterCombat(state, ctx)`).

Config v3 — per-turn флаги (3): golden-bat (+2 atk если не маневрировал в ход), ancient-leshen (+3 atk если уже атаковал в ход; Wolves move-3 НЕ смоделирован — sidekick-стат), raphael (gainAction при ПЕРВОМ проигрыше боя в ход).
- Добавлены флаги `metadata.maneuveredThisTurn/attackedThisTurn/lostCombatThisTurn` (set в executeManeuver/executeResolveCombat, reset в advanceTurn, персист save/load wire-ключи mt/at/lc) + `AfterCombatContext.firstLossThisTurn`.
- Новые condition: `has-not-maneuvered-this-turn`, `has-attacked-this-turn` (combat-passive), `first-lost-combat-this-turn` (after-attack).
- Инфра `after-defense` (триггер + `ctx.defenderPlayerId`, зеркало after-attack для defender-side) добавлена, но БЕЗ героя: реальный Spider-Man = info-reveal (complex), не draw — НЕ реализован.

Config v4 — pending-move (2): новый effect-kind `{kind:'pending-move', target:'attacker'|'own-hero'|'any-own', maxSpaces}` — способность порождает MOVE `PendingEffect` (C2), резолвится общим resolvePendingEffect (executor/resolver НЕ тронуты). robin-hood (after-attack, target attacker, 2 клетки), leonardo (turn-start, target any-own, 1 клетка; MVP — только свои бойцы, реальный «any fighter» incl. enemy не модель). Покрытие 17→19 (3 хардкод + 16 config).

Config v5 — turn-damage (2): effect-kind `{kind:'turn-damage', targetScope:'enemy-in-zone'|'enemy-adjacent', value, thenDraw?}` — onTurnStart/onTurnEnd авто-таргетит ПЕРВОГО подходящего вражеского бойца (MVP без выбора/opt-out), наносит урон (immutable, isDefeated + recompute player.isAlive при 0), опц. добор только при попадании. dracula (enemy-adjacent 1 + draw 1), medusa (enemy-in-zone 1). deps.zone расширен `manhattanDistance` (AdjacencyService уже передаётся, module не тронут). **Safety**: `checkAndApplyGameOver(state)` извлечён из executeResolveCombat + вызывается в advanceTurn ПОСЛЕ triggerHeroTurnStart (turn-start kill героя → корректный GAME_OVER). Покрытие 19→21 (3 хардкод + 18 config).

v10 — onMove reactive (1 герой + движок): оживлён 3-й мёртвый хук (onMove) как extended `onFighterMoved(state, movedFighter, from, to)` + `registry.triggerOnFighterMoved` (опрос ВСЕХ героев — реактор ≠ мувер). Wiring: `applyMoveReactions(before, after)` диффит позиции бойцов после move-действия → fire реакции + game-over recheck; подключён в executeManeuver / executeMoveFighter / resolvePendingEffect(MOVE). Новый trigger `enemy-hero-left-my-zone` + effect `reactive-damage{value}`. tomoe-gozen («враг-герой покидает зону Tomoe → 1 урон»). Покрытие 26→27 (3 хардкод + 24 config). Переиспользуемо: onFighterMoved (houdini/sinbad/buffy move-реакции впредь). Из 3 мёртвых combat/move-хуков остался onCombat.

v9 — aura + onDefeat (2 героя + 2 движка): **aura-combat-modifier** (oda-nobunaga «+1 боевым картам союзников в его зоне, сам не получает») — новый dispatch `registry.getAuraCombatModifiers(state, beneficiary, role)` опрашивает ВСЕХ героев (аура исходит от героя ≠ бойца боя), суммируется в executeResolveCombat. **Оживлён мёртвый onDefeat-хук** как extended `onFighterDefeated(state, defeatedFighter)` (диспетчер на героя ВЛАДЕЛЬЦА павшего бойца, до game-over/advanceTurn) + effect `discard-random{count}` (детерминированный стенд-ин «random», без выбора) + condition `won-combat-and-all-sidekicks-defeated` + trigger `sidekick-defeated`. achilles полностью: +2 атаки пока Patroclus мёртв / draw при победе в этом состоянии / discard 2 при гибели Patroclus. Покрытие 24→26 (3 хардкод + 23 config). Переиспользуемо: aura-dispatch (loki и др.), onFighterDefeated (любые on-death способности).

v8 — quick-wins (2) после параллельного триажа: bruce-lee (turn-end pending-move own-hero 1), raptors (новый effect-kind `combat-modifier-per-count`: +valuePer × кол-во своих бойцов, смежных с защитником, excl-self — использует `targetFighterId`). Покрытие 22→24 (3 хардкод + 21 config). **Триаж 48 оставшихся** (параллельный fan-out, grounded в scraped): SHIP_NOW=1 (исчерпан), NEW_KIND=6 (achilles/she-hulk/the-genie/tomoe-gozen/yennenga + raptors[done]), SYSTEM=39 (11 подсистем: resource×6/token×5/stance×5/rules-override×5/identity×4/sub-deck×4/summon×3/movement×3/aura×2/resurrect×1/info-reveal×1), SETUP=2. Вывод: чистый config-бакет закрыт; дальше нужны подсистемы (многие + фронт/выбор игрока). ⚠️ prompt-injection в scraped-данных («Disregard…») — агент проигнорировал, флагнул.

v7 — e2e-консолидация + bug-fix: `ability-configs.e2e.spec.ts` гоняет ВСЕ 19 config-героев через НАСТОЯЩИЙ `GameActionExecutorService` (real registry + real configs, mock I/O) по всем 5 хук-поверхностям (combat-passive/turn-start/turn-end/after-attack/attackRange), 30 тестов. **Нашёл и починил prod-баг**: `self-health-below-defender` (annie-christmas) не срабатывал — handler искал защитника по `combatInfo.defenderId` (= id ИГРОКА), а боец-защитник в `targetFighterId`. Фикс: registry `CombatState.targetFighterId?` + handler резолвит `targetFighterId ?? defenderId`. Live GraphQL-e2e отложен (нужен docker+seed+playable-герои с картами; зоны/позиции недетерминированы из сида — крепкие assertion'ы только на integration-уровне).

Config v6 — attackRange (2): wiring `canAttackAtRange` (был МЁРТВЫЙ хук!) в executeAttack — если обычная melee/ranged-проверка не пускает, консультируется `registry.canAttackAtRange(slug, ..., manhattanRange)`; additive-only (false→true, не наоборот). Config-поле `AbilityConfig.attackRange?:number`; `GenericHeroAbilityHandler.canAttackAtRange` = range ≤ attackRange. Герои: t-rex (range 2), bullseye (range 5; rules:[] — только range). **Бонус**: хардкод-способность Ms.Marvel (range≤2) теперь реально enforced в проде (была dead). Покрытие 21→22 (3 хардкод + 19 config).

## Каталог 88 (для v2)

70 реальных героев: clean=2, **partial=21**, complex=47. Реализовано 3 хардкод + 7 config = 10. Следующие цели:

- **partial-бакет** (нужен 1 доп-хук каждый):
  - after-attack хук → chupacabra/deadpool (heal)/michelangelo/robin-hood(move)/raphael(gainAction)/angel(draw on lose). Требует wiring пост-resolve hero-хука.
  - combat-условия (уже есть stateful): golden-bat (+2 если не маневрировал — нужен флаг maneuvered-this-turn), ancient-leshen (+3 если уже атаковал — нужен флаг attacked-this-turn).
  - turn-start таргетные: dracula/medusa/she-hulk (ping+draw — нужен выбор цели).
- **complex** (отдельный дизайн): токены (invisible-man fog, dr-sattler, spike, squirrel-girl summon), stances (alice/hamlet/moon-knight/muhammad-ali/jekyll-hyde), ресурсы (beowulf rage, blackbeard doubloon, ghost-rider hellfire, krang machines), под-колоды (pandora, titania), rules-override (ciri/holmes/winter-soldier uncancelable, buffy/bullseye movement/range, elektra resurrect), ауры (oda-nobunaga), масштаб-счётчики (raptors, sinbad, loki).
