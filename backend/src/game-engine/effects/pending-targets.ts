/**
 * DE-016 (W-11, D-DE-11 / F-11, SD-10, SD-16): a choice without a legal
 * target is never left waiting for input.
 *
 * The server drops a pending choice at the head of the queue when nothing in
 * it can be highlighted, and notes the skip in metadata.skippedEffects
 * (reason NO_VALID_TARGETS → why.effect.no.targets on the client, CUE-004).
 * Only the head is checked: the choices before a later one may still move
 * fighters, so the later one is checked when it becomes the head (the drain
 * after every resolve/decline in GameActionExecutorService).
 *
 * Pure functions: the zone rule comes in as a parameter, so the action
 * executor and the effect executor share one check.
 */

import type { Fighter, GameState, PendingEffect, Position, SkippedEffect } from '../models';
import { SKIPPED_EFFECTS_KEPT } from '../models';
import { bannerAllows } from '../validators/game-rules.validator';
import { computeReach } from '../movement/canonical-path';
import { isCellPassable, isFreeEndpoint } from '../movement/traversal';
import { fighterNameMatches } from './fighter-name';

/** Message of an EffectResult skipped for lack of targets (Game Tester, logs) */
export const NO_VALID_TARGETS_MESSAGE = 'No valid targets';

/** The zone rule of AdjacencyService.isInSameZone */
export interface ZoneRule {
  isInSameZone(state: GameState, a: Position, b: Position): boolean;
}

/**
 * Appends a SkippedEffect note (reason NO_VALID_TARGETS) to
 * metadata.skippedEffects, keeping the last SKIPPED_EFFECTS_KEPT. Does not
 * touch sequenceNumber: the note rides on the mutation that skipped.
 */
export function withSkippedEffect(
  state: GameState,
  note: Pick<SkippedEffect, 'playerId' | 'effectId' | 'kind' | 'text'>,
): GameState {
  const previous = state.metadata.skippedEffects ?? [];
  const entry: SkippedEffect = {
    n: (previous[previous.length - 1]?.n ?? 0) + 1,
    seq: state.sequenceNumber,
    reason: 'NO_VALID_TARGETS',
    playerId: note.playerId,
    effectId: note.effectId,
    kind: note.kind,
    ...(note.text !== undefined ? { text: note.text } : {}),
  };
  return {
    ...state,
    metadata: {
      ...state.metadata,
      skippedEffects: [...previous, entry].slice(-SKIPPED_EFFECTS_KEPT),
    },
  };
}

/**
 * Drops head-of-queue choices without a legal target (pendingHasValidTarget),
 * one after another, noting each one. The rest of the queue stays. seq is not
 * touched. Returns the same object when nothing was dropped.
 */
export function pruneHeadPendingsWithoutTargets(state: GameState, zone: ZoneRule): GameState {
  let next = state;
  for (;;) {
    const queue = next.metadata.pendingEffects ?? [];
    const head = queue[0];
    if (!head || pendingHasValidTarget(next, head, zone)) return next;
    next = withSkippedEffect(
      { ...next, metadata: { ...next.metadata, pendingEffects: queue.slice(1) } },
      { playerId: head.playerId, effectId: head.id, kind: head.type, text: head.text },
    );
  }
}

/**
 * Does the choice have a target the client can highlight? Mirrors the checks
 * of GameActionExecutorService.executeResolvePendingEffect:
 *  - MOVE / PLACE: an eligible fighter (fighterIds; living unless a revive;
 *    owner unless anyOwner; banner) with a destination OTHER than the space it
 *    stands on — free, passable, within the effect's steps (MOVE), in the zone
 *    of zoneFighterName when set. Staying put stays a legal answer, but when
 *    it is the only one the server applies it without input (zero step);
 *  - TARGET_FIGHTER: a living fighter among targetFighterIds.
 * Other choices (cards, options, spaces) have a target by construction.
 * A board without cell data cannot be judged: the choice is kept.
 */
export function pendingHasValidTarget(state: GameState, pending: PendingEffect, zone: ZoneRule): boolean {
  switch (pending.type) {
    case 'MOVE':
    case 'PLACE': {
      if (!(state.boardState?.cells?.length)) return true;
      return pendingCandidates(state, pending).some((f) => hasDestination(state, pending, f, zone));
    }
    case 'TARGET_FIGHTER':
      return state.fighters.some(
        (f) =>
          (!pending.targetFighterIds || pending.targetFighterIds.includes(f.id)) &&
          !f.isDefeated && f.health > 0,
      );
    default:
      return true;
  }
}

/** Fighters the resolver would accept for a MOVE/PLACE choice. */
function pendingCandidates(state: GameState, pending: PendingEffect): Fighter[] {
  const pool = pending.fighterIds
    ? state.fighters.filter((f) => pending.fighterIds!.includes(f.id))
    : state.fighters;
  return pool.filter((f) => {
    const dead = f.health <= 0 || f.isDefeated === true;
    if (dead && pending.restoreFullHealth !== true) return false;
    if (!pending.anyOwner &&
        (pending.targetsOpponent ? f.ownerId === pending.playerId : f.ownerId !== pending.playerId)) {
      return false;
    }
    if (pending.fighterName && !bannerAllows(pending.fighterName, f)) return false;
    return true;
  });
}

/** A legal destination other than the fighter's own space (a revive counts its old space too). */
function hasDestination(state: GameState, pending: PendingEffect, fighter: Fighter, zone: ZoneRule): boolean {
  const zoneAnchor = pending.zoneFighterName
    ? state.fighters.find((f) => fighterNameMatches(f.name, pending.zoneFighterName!))
    : undefined;
  if (pending.zoneFighterName && !zoneAnchor) return false;
  const revive = pending.restoreFullHealth === true && (fighter.isDefeated === true || fighter.health <= 0);
  const counts = (p: Position): boolean =>
    (revive || p.x !== fighter.position.x || p.y !== fighter.position.y) &&
    isFreeEndpoint(state, fighter.id, p) &&
    (!zoneAnchor || zone.isInSameZone(state, zoneAnchor.position, p));

  if (pending.type === 'MOVE') {
    const reach = computeReach(state, fighter.id, pending.value ?? 1, {
      passThroughEnemies: Boolean(pending.canPassThroughEnemies),
    });
    for (const key of reach.dist.keys()) {
      const [x, y] = key.split(':').map(Number);
      if (counts({ x, y })) return true;
    }
    return false;
  }
  const board = state.boardState;
  for (let y = 0; y < board.height; y++) {
    for (let x = 0; x < board.width; x++) {
      if (isCellPassable(board.cells[y]?.[x]) && counts({ x, y })) return true;
    }
  }
  return false;
}
