import type { GameState, CombatState } from '../models/types';
import { GamePhase, EffectTiming } from '../models/types';
import { Card } from '../models/Card';
import { FighterModel } from '../models/Fighter';
import { GameStateManager } from '../models/GameState';

/**
 * CombatResolver - handles combat resolution in Unmatched
 *
 * Combat flow:
 * 1. Attacker plays attack card face down
 * 2. Defender may play defense card face down
 * 3. Cards revealed simultaneously
 * 4. Process "Immediately" effects (attacker first)
 * 5. Process "During Combat" effects (defender first)
 * 6. Apply damage (attack - defense, if positive)
 * 7. Process "After Combat" effects
 * 8. Check for defeat
 */
export class CombatResolver {
  /**
   * Initiate combat with an attack card
   */
  initiateAttack(
    state: GameState,
    attackerId: string,
    attackCardId: string,
    defenderId: string
  ): GameState {
    const attacker = GameStateManager.findFighter(state, attackerId);
    const defender = GameStateManager.findFighter(state, defenderId);
    const currentPlayer = GameStateManager.getCurrentPlayer(state);

    if (!attacker || !defender || !currentPlayer) {
      return state;
    }

    const attackCard = GameStateManager.findCardInHand(
      state,
      currentPlayer.id,
      attackCardId
    );

    if (!attackCard) {
      return state;
    }

    // Remove card from hand
    const newHand = currentPlayer.hand.filter(c => c.id !== attackCardId);
    let newState = GameStateManager.updatePlayer(state, currentPlayer.id, { hand: newHand });

    // Create combat state
    const combatState: CombatState = {
      attacker,
      defender,
      attackCard: Card.playFaceDown(attackCard),
      defenseCard: undefined,
      attackValue: attackCard.definition.value,
      defenseValue: 0,
      attackBoosts: 0,
      defenseBoosts: 0,
      effectsToProcess: [],
      resolutionComplete: false,
    };

    newState = {
      ...newState,
      combatState,
      phase: GamePhase.COMBAT_DEFENSE,
    };

    return newState;
  }

  /**
   * Play a defense card in response to an attack
   */
  playDefense(state: GameState, defenseCardId: string): GameState {
    if (!state.combatState) return state;

    const combatState = state.combatState;
    const defenderPlayer = state.players.find(
      p => p.id === combatState.defender.ownerId
    );

    if (!defenderPlayer) return state;

    const defenseCard = GameStateManager.findCardInHand(
      state,
      defenderPlayer.id,
      defenseCardId
    );

    if (!defenseCard) return state;

    // Remove card from hand
    const newHand = defenderPlayer.hand.filter(c => c.id !== defenseCardId);
    let newState = GameStateManager.updatePlayer(state, defenderPlayer.id, { hand: newHand });

    // Add defense card to combat
    if (newState.combatState) {
      const combat = newState.combatState;
      newState.combatState = {
        ...combat,
        defenseCard: Card.playFaceDown(defenseCard),
        defenseValue: defenseCard.definition.value,
      };
    }

    return newState;
  }

  /**
   * Resolve the combat - calculate damage and apply effects
   */
  resolve(state: GameState): GameState {
    if (!state.combatState || state.combatState.resolutionComplete) {
      return state;
    }

    let combat = { ...state.combatState };
    let newState = state;

    // Step 1: Reveal cards
    combat.attackCard = Card.reveal(combat.attackCard);
    if (combat.defenseCard) {
      combat.defenseCard = Card.reveal(combat.defenseCard);
    }

    // Step 2: Process "Immediately" effects (attacker first)
    newState = this.processImmediatelyEffects(newState, combat, 'attacker');
    if (newState.combatState) combat = { ...newState.combatState };

    // Step 3: Process "Immediately" effects (defender)
    newState = this.processImmediatelyEffects(newState, combat, 'defender');
    if (newState.combatState) combat = { ...newState.combatState };

    // Step 4: Process "During Combat" effects (defender first per rules)
    newState = this.processDuringCombatEffects(newState, combat, 'defender');
    if (newState.combatState) combat = { ...newState.combatState };

    // Step 5: Process "During Combat" effects (attacker)
    newState = this.processDuringCombatEffects(newState, combat, 'attacker');
    if (newState.combatState) combat = { ...newState.combatState };

    // Step 6: Apply boosts
    const attackBoosts = combat.attackBoosts + (combat.attackCard.definition.boost || 0);
    const defenseBoosts = combat.defenseBoosts +
      (combat.defenseCard?.definition.boost || 0);

    // Step 7: Calculate damage
    const totalAttack = combat.attackValue + attackBoosts;
    const totalDefense = combat.defenseValue + defenseBoosts;
    const damage = Math.max(0, totalAttack - totalDefense);

    // Step 8: Apply damage
    if (damage > 0) {
      newState = this.applyDamage(newState, combat.defender.id, damage);
    }

    // Step 9: Process "After Combat" effects
    newState = this.processAfterCombatEffects(newState, combat);

    // Step 10: Move cards to discard
    newState = this.discardCombatCards(newState);

    // Step 11: Mark combat as complete
    if (newState.combatState) {
      newState.combatState.resolutionComplete = true;
    }

    // Step 12: Check for defeat
    newState = this.checkDefeat(newState);

    return newState;
  }

  /**
   * Process "Immediately" effects for a side
   */
  private processImmediatelyEffects(
    state: GameState,
    combat: CombatState,
    side: 'attacker' | 'defender'
  ): GameState {
    const card = side === 'attacker' ? combat.attackCard : combat.defenseCard;
    if (!card) return state;

    void card.definition.effects.filter(
      e => e.timing === EffectTiming.IMMEDIATELY
    );

    // TODO: Implement effect processing
    return state;
  }

  /**
   * Process "During Combat" effects for a side
   */
  private processDuringCombatEffects(
    state: GameState,
    combat: CombatState,
    side: 'attacker' | 'defender'
  ): GameState {
    const card = side === 'attacker' ? combat.attackCard : combat.defenseCard;
    if (!card) return state;

    void card.definition.effects.filter(
      e => e.timing === EffectTiming.DURING_COMBAT
    );

    // TODO: Implement effect processing
    return state;
  }

  /**
   * Process "After Combat" effects
   */
  private processAfterCombatEffects(state: GameState, combat: CombatState): GameState {
    const attackCard = combat.attackCard;
    const defenseCard = combat.defenseCard;

    void [
      ...attackCard.definition.effects.filter(e => e.timing === EffectTiming.AFTER_COMBAT),
      ...(defenseCard?.definition.effects.filter(e => e.timing === EffectTiming.AFTER_COMBAT) || []),
    ];

    // TODO: Implement effect processing (draw cards, heal, etc.)
    return state;
  }

  /**
   * Apply damage to a fighter
   */
  private applyDamage(state: GameState, fighterId: string, damage: number): GameState {
    const fighter = GameStateManager.findFighter(state, fighterId);
    if (!fighter) return state;

    const damagedFighter = FighterModel.dealDamage(fighter, damage);
    return GameStateManager.updateFighter(state, fighterId, {
      health: damagedFighter.health,
      isDefeated: damagedFighter.isDefeated,
    });
  }

  /**
   * Discard combat cards to appropriate discard piles
   */
  private discardCombatCards(state: GameState): GameState {
    if (!state.combatState) return state;

    const combatState = state.combatState;
    let newState = state;

    // Discard attack card
    const attackerPlayer = newState.players.find(
      p => p.id === combatState.attacker.ownerId
    );
    if (attackerPlayer) {
      const newDiscard = [
        ...attackerPlayer.discardPile,
        Card.reset(combatState.attackCard),
      ];
      newState = GameStateManager.updatePlayer(newState, attackerPlayer.id, {
        discardPile: newDiscard,
      });
    }

    // Discard defense card if played
    if (combatState.defenseCard) {
      const defenderPlayer = newState.players.find(
        p => p.id === combatState.defender.ownerId
      );
      if (defenderPlayer) {
        const newDiscard = [
          ...defenderPlayer.discardPile,
          Card.reset(combatState.defenseCard),
        ];
        newState = GameStateManager.updatePlayer(newState, defenderPlayer.id, {
          discardPile: newDiscard,
        });
      }
    }

    return newState;
  }

  /**
   * Check for defeat conditions and update winner
   */
  private checkDefeat(state: GameState): GameState {
    // Check if any player has all fighters defeated
    const winner = GameStateManager.checkGameOver(state);

    if (winner) {
      return GameStateManager.setWinner(state, winner);
    }

    // Clear combat state
    return {
      ...state,
      combatState: null,
      phase: GamePhase.ACTION_SELECTION,
    };
  }

  /**
   * Boost a card in combat
   */
  boostCard(state: GameState, side: 'attack' | 'defense', boostValue: number): GameState {
    if (!state.combatState) return state;

    const newCombat = { ...state.combatState };

    if (side === 'attack') {
      newCombat.attackBoosts += boostValue;
      newCombat.attackCard = Card.boost(newCombat.attackCard, boostValue);
    } else {
      newCombat.defenseBoosts += boostValue;
      if (newCombat.defenseCard) {
        newCombat.defenseCard = Card.boost(newCombat.defenseCard, boostValue);
      }
    }

    return {
      ...state,
      combatState: newCombat,
    };
  }

  /**
   * Calculate final damage without applying it
   */
  calculateDamage(combat: CombatState): number {
    const totalAttack = combat.attackValue + combat.attackBoosts;
    const totalDefense = combat.defenseValue + combat.defenseBoosts;
    return Math.max(0, totalAttack - totalDefense);
  }
}
