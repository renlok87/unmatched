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

## Шипнуто (7 героев)

luke-cage (+2 def always), annie-christmas (+2 atk if HP<defender), eredin (+1 both если все sidekick'и мертвы) [combat]; bloody-mary (gainAction если рука==3) [turn-start]; philippa (draw до 4), t-rex (draw 1), bigfoot (draw 1 если в зоне нет врагов) [turn-end].

## Каталог 88 (для v2)

70 реальных героев: clean=2, **partial=21**, complex=47. Реализовано 3 хардкод + 7 config = 10. Следующие цели:

- **partial-бакет** (нужен 1 доп-хук каждый):
  - after-attack хук → chupacabra/deadpool (heal)/michelangelo/robin-hood(move)/raphael(gainAction)/angel(draw on lose). Требует wiring пост-resolve hero-хука.
  - combat-условия (уже есть stateful): golden-bat (+2 если не маневрировал — нужен флаг maneuvered-this-turn), ancient-leshen (+3 если уже атаковал — нужен флаг attacked-this-turn).
  - turn-start таргетные: dracula/medusa/she-hulk (ping+draw — нужен выбор цели).
- **complex** (отдельный дизайн): токены (invisible-man fog, dr-sattler, spike, squirrel-girl summon), stances (alice/hamlet/moon-knight/muhammad-ali/jekyll-hyde), ресурсы (beowulf rage, blackbeard doubloon, ghost-rider hellfire, krang machines), под-колоды (pandora, titania), rules-override (ciri/holmes/winter-soldier uncancelable, buffy/bullseye movement/range, elektra resurrect), ауры (oda-nobunaga), масштаб-счётчики (raptors, sinbad, loki).
