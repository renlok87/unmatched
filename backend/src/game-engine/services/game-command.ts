/**
 * DET-2 (docs/research/de-reverse-2026-10-20/VERDICT.md §3 P1.2): an input
 * command of the game — what a player, the AI or the server timeout asked the
 * executor to do. A game is reproduced by its start snapshot and the list of
 * these commands, never by the engine's internal effects (DuelEngine lesson:
 * replay by inputs 120/120, by the internal action log 0/120).
 *
 * The live path (resolver, AiTurnService, CombatTimeoutService) and the replay
 * (games/replay) both run a command through executeGameCommand, so a recorded
 * command means exactly what it meant live: the same DTO as plain JSON, the
 * same clock (ActionContext.now) and the same system flag.
 */
import type { GameState } from '../models';
import type { ActionContext, ActionResult, GameActionExecutorService } from './game-action-executor.service';

/** The executor entry points a command may name (one per GraphQL game mutation). */
export type GameCommandKind =
  | 'beginManeuver'
  | 'maneuver'
  | 'discardToLimit'
  | 'moveFighter'
  | 'attack'
  | 'playDefense'
  | 'playScheme'
  | 'resolvePendingEffect'
  | 'declinePendingEffect'
  | 'resolveCombat'
  | 'endTurn'
  | 'pass'
  | 'toggleDoor'
  | 'setStance';

export const GAME_COMMAND_KINDS: readonly GameCommandKind[] = [
  'beginManeuver', 'maneuver', 'discardToLimit', 'moveFighter', 'attack', 'playDefense', 'playScheme',
  'resolvePendingEffect', 'declinePendingEffect', 'resolveCombat', 'endTurn', 'pass', 'toggleDoor', 'setStance',
];

export interface GameCommand {
  readonly kind: GameCommandKind;
  /** Who acts: the player, the AI user, or the owner of a timed-out choice */
  readonly userId: string;
  /** The DTO as plain JSON, gameId included */
  readonly input: Readonly<Record<string, unknown>>;
  /** ActionContext.now as an ISO string: the rules read this clock, not Date.now() */
  readonly now: string;
  /** ActionContext.systemInitiator (server timeout of a combat stage) */
  readonly system?: boolean;
}

/** Plain-JSON copy of a DTO: class instances and undefined fields do not reach the journal. */
export function commandInput(dto: object): Record<string, unknown> {
  return JSON.parse(JSON.stringify(dto ?? {})) as Record<string, unknown>;
}

export function makeCommand(
  kind: GameCommandKind,
  userId: string,
  dto: object,
  now: Date,
  system?: boolean,
): GameCommand {
  return { kind, userId, input: commandInput(dto), now: now.toISOString(), ...(system ? { system: true } : {}) };
}

/** Run one command on a state with the production executor. Pure apart from the executor itself. */
export async function executeGameCommand(
  executor: GameActionExecutorService,
  command: GameCommand,
  state: GameState,
): Promise<ActionResult> {
  const ctx: ActionContext = {
    userId: command.userId,
    gameId: state.gameId,
    currentState: state,
    now: new Date(command.now),
    ...(command.system ? { systemInitiator: true } : {}),
  };
  // The executor validates every field itself; a command is untyped JSON here.
  const dto = command.input as any;
  switch (command.kind) {
    case 'beginManeuver':
      return executor.executeBeginManeuver(dto, ctx);
    case 'maneuver':
      return executor.executeManeuver(dto, ctx);
    case 'discardToLimit':
      return executor.executeDiscardToLimit(dto, ctx);
    case 'moveFighter':
      return executor.executeMoveFighter(dto, ctx);
    case 'attack':
      return executor.executeAttack(dto, ctx);
    case 'playDefense':
      return executor.executePlayDefense(dto, ctx);
    case 'playScheme':
      return executor.executePlayScheme(dto, ctx);
    case 'resolvePendingEffect':
      return executor.executeResolvePendingEffect(dto, ctx);
    case 'declinePendingEffect':
      return executor.executeDeclinePendingEffect(dto, ctx);
    case 'resolveCombat':
      return executor.executeResolveCombat(dto, ctx);
    case 'endTurn':
      return executor.executeEndTurn(dto, ctx);
    case 'pass':
      return executor.executePass(dto, ctx);
    case 'toggleDoor':
      return executor.executeToggleDoor(dto, ctx);
    case 'setStance':
      return executor.executeSetStance(dto, ctx);
    default: {
      const unknown: never = command.kind;
      return { success: false, error: `Unknown command kind ${String(unknown)}` };
    }
  }
}
