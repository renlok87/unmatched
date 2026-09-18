import { GamePhase, type GameState } from '../models';

/** Damage boundary. Never advances sequence or reopens a completed duel. */
export function applyTerminalState(state: GameState): GameState {
  if (state.phase === GamePhase.GAME_OVER) return state;
  const fighters = state.fighters.map(f =>
    f.health <= 0 && !f.isDefeated ? { ...f, health: 0, isDefeated: true } : f,
  );
  const players = state.players.map(p => {
    const hero = fighters.find(f => f.ownerId === p.userId &&
      ['HERO', 'HUGE'].includes(String(f.type).toUpperCase()));
    // Initial lobby states may not have fighters yet.
    const isAlive = hero ? hero.health > 0 && !hero.isDefeated : p.isAlive;
    return isAlive === p.isAlive ? p : { ...p, isAlive };
  });
  const alive = players.filter(p => p.isAlive);
  const ended = players.length > 1 && alive.length <= 1;
  if (!ended && fighters.every((f, i) => f === state.fighters[i]) &&
      players.every((p, i) => p === state.players[i])) return state;
  return {
    ...state, fighters, players,
    ...(ended ? {
      phase: GamePhase.GAME_OVER,
      metadata: { ...state.metadata, winnerId: alive[0]?.userId,
        combatInfo: undefined, pendingEffects: [],
        combatResolutionProgress: undefined, combatEffectContinuation: undefined },
    } : {}),
  };
}
