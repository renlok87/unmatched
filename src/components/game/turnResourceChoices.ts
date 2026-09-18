import type { WireGameState, WirePosition } from '@/lib/gameStateAdapter';

export interface ManeuverMove {
  fighterId: string;
  path: WirePosition[];
}

export function resourceControls(state: WireGameState | null, userId: string | null) {
  const active = Boolean(state && userId && state.phase !== 'GAME_OVER' && state.currentTurnPlayerId === userId);
  const meta = state?.metadata;
  const maneuver = active && meta?.pendingManeuver?.playerId === userId ? meta.pendingManeuver : null;
  const discard = active && meta?.pendingHandDiscard?.playerId === userId ? meta.pendingHandDiscard : null;
  const waiting = Boolean(meta?.pendingManeuver || meta?.pendingHandDiscard || meta?.pendingEffects?.length || meta?.combatInfo);
  const actionPhase = state?.phase === 'ACTION_MANEUVER' || state?.phase === 'ACTION_ATTACK';
  const canAct = active && actionPhase && !waiting && (meta?.actionsRemaining ?? 2) > 0;
  const canEnd = active && !waiting && (actionPhase || state?.phase === 'TURN_END') && (meta?.actionsRemaining ?? 2) === 0;
  return { canAct, canBegin: canAct, canEnd, maneuver, discard };
}

export function appendManeuverStep(moves: ManeuverMove[], fighterId: string, position: WirePosition): ManeuverMove[] {
  const existing = moves.find(move => move.fighterId === fighterId);
  return existing
    ? moves.map(move => move === existing ? { ...move, path: [...move.path, { ...position }] } : move)
    : [...moves, { fighterId, path: [{ ...position }] }];
}

export function toggleDiscardInstance(ids: string[], cardId: string, count: number): string[] {
  if (ids.includes(cardId)) return ids.filter(id => id !== cardId);
  return ids.length < count ? [...ids, cardId] : ids;
}
