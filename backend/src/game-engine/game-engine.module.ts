import { Module } from '@nestjs/common';
import { CombatResolverService } from './engine/combat-resolver.service';
import { MovementService } from './engine/movement.service';
import { AdjacencyService } from './engine/adjacency.service';
import { GameRulesValidator } from './validators/game-rules.validator';
import { ValueModifierService } from './engine/value-modifier.service';
import { HeroAbilityRegistry } from './abilities/hero-ability-registry';
import { AStarService } from './movement/astar.service';
import { PathfindingCacheService } from './movement/path-cache.service';
import { CardEffectExecutorService } from './effects/card-effect-executor.service';
import { GameActionExecutorService } from './services/game-action-executor.service';
import { AiDecisionService } from './services/ai-decision.service';
import { TurnManagementService } from './services/turn-management.service';
import { DeckManagementService } from './services/deck-management.service';
import { GameJobsModule } from '../game/jobs';
import { ContentModule } from '../content/content.module';
import { MetricsModule } from '../metrics/metrics.module';
import { CardValueCacheService } from './cache/card-value-cache.service';
import { registerHeroAbilities } from './abilities/register-hero-abilities';

/**
 * Game Engine Module
 *
 * Содержит основную игровую логику Unmatched:
 * - Разрешение боёв
 * - Перемещение бойцов
 * - Валидация правил
 * - Модификаторы значений
 * - Управление ходами
 * - Выполнение эффектов карт
 * - Особенности доски (двери, туман, высота)
 * - Единый исполнитель игровых действий
 * - Способности героев
 *
 * Мигрирован из game/ для ясности ответственности.
 */

@Module({
  imports: [GameJobsModule, ContentModule, MetricsModule],
  providers: [
    // Engine services
    CombatResolverService,
    MovementService,
    AdjacencyService,
    ValueModifierService,
    GameRulesValidator,
    // Turn & Deck management
    TurnManagementService,
    DeckManagementService,
    // Actions
    GameActionExecutorService,
    // AI (VS_AI решения)
    AiDecisionService,
    // Effects
    CardEffectExecutorService,
    // Abilities
    HeroAbilityRegistry,
    // Movement services
    AStarService,
    PathfindingCacheService,
    // Cache services
    CardValueCacheService,
  ],
  exports: [
    CombatResolverService,
    MovementService,
    AdjacencyService,
    ValueModifierService,
    GameRulesValidator,
    TurnManagementService,
    DeckManagementService,
    GameActionExecutorService,
    AiDecisionService,
    CardEffectExecutorService,
    HeroAbilityRegistry,
    AStarService,
    PathfindingCacheService,
    CardValueCacheService,
  ],
})
export class GameEngineModule {
  constructor(
    private readonly registry: HeroAbilityRegistry,
    private readonly deckManagement: DeckManagementService,
    private readonly adjacency: AdjacencyService,
  ) {}

  onModuleInit() {
    // Способности героев: ручные handler'ы (Daredevil, Ms. Marvel, Arthur),
    // затем data-driven ABILITY_CONFIGS. Та же функция собирает реестр
    // headless-харнессов (s03Engine, self-play), чтобы они играли те же герои.
    registerHeroAbilities(this.registry, {
      deck: this.deckManagement,
      zone: this.adjacency,
    });
  }
}
