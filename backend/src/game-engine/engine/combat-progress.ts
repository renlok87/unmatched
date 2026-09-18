import type { RevealResult, CombatCalculation, AfterCombatResult } from '../effects/card-effect-executor.service';

/** Saved only while a combat card awaits a player choice. No nested GameState. */
export interface CombatResolutionProgress {
  reveal?: Omit<RevealResult, 'state'> & { paused?: boolean };
  calculation?: Omit<CombatCalculation, 'state'> & { paused?: boolean };
  after?: Omit<AfterCombatResult, 'state'> & { paused?: boolean };
  damage?: {
    finalAttack: number; finalDefense: number;
    attackerDamage: number; defenderDamage: number; attackerWon: boolean;
  };
  defeatedBefore: readonly string[];
}
