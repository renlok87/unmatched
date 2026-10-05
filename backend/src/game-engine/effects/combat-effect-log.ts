/**
 * R-01 (RESEARCH-2026-10-05 findings 5–6, DE-018 tail): the public log of the
 * effects a combat fired, carried in the snapshot as metadata.lastCombat.
 *
 * The server writes an explicit log "effect → outcome" with causal links
 * (an option of a CHOOSE_ONE points at the CHOOSE_ONE) instead of letting the
 * client guess lines from the difference of two snapshots: the final state
 * loses what caused what. Hidden information is filtered per viewer on the
 * server: an entry's public part names only fighters and players, anything
 * else (a card instance id, the engine note) sits in `hidden`, which only the
 * effect's owner receives.
 *
 * Pure functions: the effect executor annotates every EffectResult with its
 * source (describeEffectSource), executeResolveCombat builds the log
 * (buildCombatEffectLog), filterPrivateData projects it (projectLastCombat).
 */

import type {
  CardEffect,
  CombatEffectLogEntry,
  CombatEffectOutcome,
  CombatEffectTiming,
  EffectContext,
  GameState,
  LastCombat,
} from '../models';
import type { EffectResult } from './card-effect-executor.service';
import { NO_VALID_TARGETS_MESSAGE } from './pending-targets';

/** Who and what fired an effect — set on EffectResult by the effect executor. */
export interface EffectSource {
  /** Owner of the effect (EffectContext.playerId) */
  readonly playerId: string;
  /** Instance id of the card that carries the effect */
  readonly cardId: string;
  /** Catalog id (Card.cardId) */
  readonly catalogId: string;
  readonly cardName: string;
  /** EffectType */
  readonly kind: string;
  /** Printed effect sentence */
  readonly text?: string;
  /** Ids of the pending choices this effect opened */
  readonly opened?: readonly string[];
  /** Id of the pending choice whose resolution fired this effect */
  readonly fromPending?: string;
}

/** Ids of the pending choices present in `after` but not in `before`. */
function openedPendings(before: GameState, after: GameState): string[] {
  const had = new Set((before.metadata.pendingEffects ?? []).map((p) => p.id));
  return (after.metadata.pendingEffects ?? []).map((p) => p.id).filter((id) => !had.has(id));
}

export function describeEffectSource(
  before: GameState,
  after: GameState,
  effect: CardEffect,
  context: EffectContext,
  fromPending?: string,
): EffectSource {
  const card = context.card;
  const opened = openedPendings(before, after);
  return {
    playerId: context.playerId,
    cardId: card?.id ?? '',
    catalogId: card?.cardId ?? '',
    cardName: card?.nameEn ?? card?.name ?? '',
    kind: effect.type,
    ...(effect.text !== undefined ? { text: effect.text } : {}),
    ...(opened.length > 0 ? { opened } : {}),
    ...(fromPending !== undefined ? { fromPending } : {}),
  };
}

function outcomeOf(result: EffectResult): CombatEffectOutcome {
  if (result.manual) return 'MANUAL';
  if (!result.success) return result.message === NO_VALID_TARGETS_MESSAGE ? 'NO_TARGETS' : 'FAILED';
  if (result.source?.opened?.length) return 'CHOICE';
  return 'APPLIED';
}

/** One combat stage's results, in the order they were applied. */
export interface CombatLogStage {
  readonly timing: CombatEffectTiming;
  readonly results: readonly EffectResult[];
}

/**
 * Builds the ordered public log of one combat. `state` gives the public ids
 * (fighters and players); a result without a source (a save from before R-01)
 * is left out: its owner is unknown, so it cannot be classified.
 */
export function buildCombatEffectLog(
  stages: readonly CombatLogStage[],
  attackerPlayerId: string,
  state: GameState,
): CombatEffectLogEntry[] {
  const publicIds = new Set<string>([
    ...state.fighters.map((f) => f.id),
    ...state.players.map((p) => p.userId),
  ]);
  const openedBy = new Map<string, number>();
  const log: CombatEffectLogEntry[] = [];
  for (const stage of stages) {
    for (const result of stage.results) {
      const source = result.source;
      if (!source) continue;
      const i = log.length;
      const targets = result.targetIds.filter((id) => publicIds.has(id));
      const refs = result.targetIds.filter((id) => !publicIds.has(id));
      const parent =
        source.fromPending !== undefined ? openedBy.get(source.fromPending) : undefined;
      const hidden = {
        ...(result.message !== undefined ? { note: result.message } : {}),
        ...(refs.length > 0 ? { refs } : {}),
      };
      log.push({
        i,
        timing: stage.timing,
        side: source.playerId === attackerPlayerId ? 'ATTACKER' : 'DEFENDER',
        playerId: source.playerId,
        source: {
          kind: 'CARD',
          cardId: source.cardId,
          catalogId: source.catalogId,
          name: source.cardName,
        },
        effectId: result.effectId,
        kind: source.kind,
        outcome: outcomeOf(result),
        ...(result.valueApplied !== undefined ? { value: result.valueApplied } : {}),
        targets,
        ...(source.text !== undefined ? { text: source.text } : {}),
        ...(parent !== undefined ? { parent } : {}),
        ...(Object.keys(hidden).length > 0 ? { hidden } : {}),
      });
      for (const id of source.opened ?? []) openedBy.set(id, i);
    }
  }
  return log;
}

/** The viewer's projection: `hidden` stays only on the viewer's own entries. */
export function projectLastCombat(lastCombat: LastCombat, viewerId: string): LastCombat {
  if (!lastCombat.appliedEffects.some((e) => e.hidden && e.playerId !== viewerId))
    return lastCombat;
  return {
    ...lastCombat,
    appliedEffects: lastCombat.appliedEffects.map((entry) => {
      if (!entry.hidden || entry.playerId === viewerId) return entry;
      const open: { -readonly [K in keyof CombatEffectLogEntry]?: CombatEffectLogEntry[K] } = {
        ...entry,
      };
      delete open.hidden;
      return open as CombatEffectLogEntry;
    }),
  };
}
