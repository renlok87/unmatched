import type { Fighter, HeroDefinition, Position, FighterType } from './types';

/**
 * Fighter class - represents a hero or sidekick on the board
 */
export class FighterModel {
  /**
   * Create a hero fighter from a definition
   */
  static createHero(
    definition: HeroDefinition,
    ownerId: string,
    startPosition: Position
  ): Fighter {
    return {
      id: `${ownerId}_hero`,
      definitionId: definition.id,
      type: 'hero' as FighterType.HERO,
      health: definition.health,
      maxHealth: definition.health,
      position: { ...startPosition },
      ownerId,
      isDefeated: false,
    };
  }

  /**
   * Create a sidekick fighter
   */
  static createSidekick(
    definition: HeroDefinition,
    ownerId: string,
    startPosition: Position,
    index: number
  ): Fighter {
    const sidekickHealth = definition.sidekickHealth || 1;

    return {
      id: `${ownerId}_sidekick_${index}`,
      definitionId: definition.id,
      type: 'sidekick' as FighterType.SIDEKICK,
      health: sidekickHealth,
      maxHealth: sidekickHealth,
      position: { ...startPosition },
      ownerId,
      isDefeated: false,
    };
  }

  /**
   * Create all sidekicks for a hero
   */
  static createSidekicks(
    definition: HeroDefinition,
    ownerId: string,
    startPosition: Position
  ): Fighter[] {
    const sidekicks: Fighter[] = [];
    const count = definition.sidekickCount || 0;

    for (let i = 0; i < count; i++) {
      sidekicks.push(this.createSidekick(definition, ownerId, startPosition, i));
    }

    return sidekicks;
  }

  /**
   * Check if a fighter is a hero
   */
  static isHero(fighter: Fighter): boolean {
    return fighter.type === 'hero';
  }

  /**
   * Check if a fighter is a sidekick
   */
  static isSidekick(fighter: Fighter): boolean {
    return fighter.type === 'sidekick';
  }

  /**
   * Check if a fighter is alive
   */
  static isAlive(fighter: Fighter): boolean {
    return !fighter.isDefeated && fighter.health > 0;
  }

  /**
   * Get effective movement (could be modified by abilities)
   */
  static getMovement(_fighter: Fighter, baseMovement: number): number {
    // TODO: Apply modifiers
    return baseMovement;
  }

  /**
   * Deal damage to a fighter
   */
  static dealDamage(fighter: Fighter, damage: number): Fighter {
    const newHealth = Math.max(0, fighter.health - damage);
    return {
      ...fighter,
      health: newHealth,
      isDefeated: newHealth === 0,
    };
  }

  /**
   * Heal a fighter
   */
  static heal(fighter: Fighter, amount: number): Fighter {
    const newHealth = Math.min(fighter.maxHealth, fighter.health + amount);
    return {
      ...fighter,
      health: newHealth,
    };
  }

  /**
   * Move a fighter to a new position
   */
  static move(fighter: Fighter, position: Position): Fighter {
    return {
      ...fighter,
      position: { ...position },
    };
  }

  /**
   * Clone a fighter
   */
  static clone(fighter: Fighter): Fighter {
    return {
      ...fighter,
      position: { ...fighter.position },
    };
  }

  /**
   * Get all alive fighters for a player
   */
  static getAliveFighters(fighters: Fighter[]): Fighter[] {
    return fighters.filter(f => this.isAlive(f));
  }

  /**
   * Check if all fighters for a player are defeated
   */
  static isAllDefeated(fighters: Fighter[]): boolean {
    return fighters.every(f => f.isDefeated || f.health === 0);
  }

  /**
   * Get the hero from a list of fighters
   */
  static getHero(fighters: Fighter[]): Fighter | undefined {
    return fighters.find(f => this.isHero(f));
  }

  /**
   * Get all sidekicks from a list of fighters
   */
  static getSidekicks(fighters: Fighter[]): Fighter[] {
    return fighters.filter(f => this.isSidekick(f));
  }
}
