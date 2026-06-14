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
import { daredevilHandler, msMarvelHandler, arthurAbilityHandler } from './abilities/heroes';
import { ABILITY_CONFIGS } from './abilities/ability-config';
import { GenericHeroAbilityHandler } from './abilities/generic-hero-ability.handler';

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

/**
 * Provider для автоматической регистрации Daredevil
 */
const DaredevilRegistryProvider = {
  provide: 'DAREDEVIL_REGISTRY',
  useFactory: (registry: HeroAbilityRegistry) => {
    registry.registerExtended(daredevilHandler);
    return daredevilHandler;
  },
  inject: [HeroAbilityRegistry],
};

/**
 * Provider для автоматической регистрации Ms. Marvel
 */
const MsMarvelRegistryProvider = {
  provide: 'MS_MARVEL_REGISTRY',
  useFactory: (registry: HeroAbilityRegistry) => {
    registry.registerExtended(msMarvelHandler);
    return msMarvelHandler;
  },
  inject: [HeroAbilityRegistry],
};

/**
 * Provider для автоматической регистрации Arthur
 */
const ArthurRegistryProvider = {
  provide: 'ARTHUR_REGISTRY',
  useFactory: (registry: HeroAbilityRegistry) => {
    registry.register(arthurAbilityHandler);
    return arthurAbilityHandler;
  },
  inject: [HeroAbilityRegistry],
};

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
    DaredevilRegistryProvider,
    MsMarvelRegistryProvider,
    ArthurRegistryProvider,
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
    // Регистрируем обработчики способностей героев (классические — DO NOT break)
    this.registry.register(arthurAbilityHandler);

    // Data-driven generic-способности: один GenericHeroAbilityHandler на каждый
    // декларативный AbilityConfig. registerExtended → extended-карта реестра
    // обслуживает turn-хуки И stateful combat (через getAny).
    const deps = {
      deck: this.deckManagement,
      zone: this.adjacency,
    };
    for (const config of ABILITY_CONFIGS) {
      this.registry.registerExtended(new GenericHeroAbilityHandler(config, deps));
    }
  }
}
