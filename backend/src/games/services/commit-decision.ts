import type { Logger } from '@nestjs/common';
import { GamePhase, DEFENSE_TIMEOUT_SECONDS, RESOLVE_TIMEOUT_SECONDS } from '../../game-engine/models';
import type { GameState } from '../../game-engine/models';
import type { GameStateService } from '../game-state.service';
import type { GameSubscriptionService } from '../game-subscription.service';
import type { CombatTimeoutService } from './combat-timeout.service';

/** Сервисы, через которые проходит коммит решения (у вызывающего уже внедрены). */
export interface DecisionCommitDeps {
  readonly stateService: Pick<GameStateService, 'saveState'>;
  readonly subscription?: Pick<GameSubscriptionService, 'publishGameUpdate'>;
  readonly combatTimeout?: Pick<CombatTimeoutService, 'scheduleAutoResolve' | 'cancelAutoResolve'>;
  readonly logger: Pick<Logger, 'warn'>;
}

export interface DecisionCommit {
  readonly gameId: string;
  readonly state: GameState;
  /** Named-CUE подписки и тип записи журнала (ATTACK_INITIATED, CARD_PLAYED, …). */
  readonly eventType: string;
  /**
   * Журнал GameAction для eventsSince: вызывается после коммита для самого
   * действия и, если партия закончилась, ещё раз с 'GAME_ENDED'. Форма записи
   * остаётся за вызывающим (человек и бот пишут разные metadata).
   */
  readonly journal?: (eventType: string) => Promise<void>;
}

/**
 * SEL-07: одна точка «сохранить → дедлайн боя → журнал → разослать» для
 * ответа человека (game-actions.resolver) и бота (ai-turn).
 *
 * Отказ saveState — настоящий отказ команды, он пробрасывается. Всё после
 * коммита — best-effort: закоммиченный seq — источник истины, подписчики
 * догонят его барьерным снапшотом или eventsSince, а дедлайн боя персистен в
 * combatInfo.timeoutAt и его подхватит periodic recovery sweep. Раньше отказ
 * Redis publish или очереди дедлайнов после коммита возвращал человеку
 * errors[]: UE считает это окончательным отказом, сбрасывает черновик и даёт
 * повторить уже применённый ответ. Терминальный GAME_ENDED — отдельная
 * попытка: отказ публикации самого действия не глотает конец партии.
 */
export async function commitDecision(deps: DecisionCommitDeps, commit: DecisionCommit): Promise<void> {
  const { gameId, state, eventType } = commit;
  await deps.stateService.saveState(gameId, state);
  await scheduleCombatDeadline(deps, gameId, eventType, state);
  await bestEffort(deps, `journal «${eventType}»`, gameId, state, () => commit.journal?.(eventType));
  await bestEffort(deps, `publish «${eventType}»`, gameId, state, () =>
    deps.subscription?.publishGameUpdate(gameId, eventType, state),
  );
  if (state.phase === GamePhase.GAME_OVER) {
    await bestEffort(deps, 'journal «GAME_ENDED»', gameId, state, () => commit.journal?.('GAME_ENDED'));
    await bestEffort(deps, 'publish «GAME_ENDED»', gameId, state, () =>
      deps.subscription?.publishGameUpdate(gameId, 'GAME_ENDED', state),
    );
  }
}

/**
 * GD-026 / GD-039 Sol6: боевые дедлайны — одинаковы для человека и бота.
 * Атака → окно защиты к combatInfo.timeoutAt (джоба дёргается ровно к нему,
 * не process-local таймер); защита → окно ручного резолва (оба клиента могут
 * отключиться — сервер всё равно завершит бой); резолв → отмена расписаний.
 */
async function scheduleCombatDeadline(
  deps: DecisionCommitDeps,
  gameId: string,
  eventType: string,
  state: GameState,
): Promise<void> {
  const timeout = deps.combatTimeout;
  if (!timeout) return;
  await bestEffort(deps, `combat deadline (${eventType})`, gameId, state, async () => {
    if (eventType === 'ATTACK_INITIATED') {
      const ci = state.metadata.combatInfo;
      const delayMs = ci?.timeoutAt
        ? Math.max(0, new Date(ci.timeoutAt).getTime() - Date.now())
        : DEFENSE_TIMEOUT_SECONDS * 1000;
      await timeout.scheduleAutoResolve(
        gameId,
        Math.max(1, Math.ceil(delayMs / 1000)),
        state.sequenceNumber,
        'DEFENSE',
      );
    } else if (eventType === 'DEFENSE_PLAYED') {
      await timeout.scheduleAutoResolve(gameId, RESOLVE_TIMEOUT_SECONDS, state.sequenceNumber, 'RESOLVE');
    } else if (eventType === 'COMBAT_RESOLVED') {
      await timeout.cancelAutoResolve(gameId);
    }
  });
}

async function bestEffort(
  deps: DecisionCommitDeps,
  what: string,
  gameId: string,
  state: GameState,
  step: () => Promise<unknown> | undefined,
): Promise<void> {
  try {
    await step();
  } catch (e) {
    deps.logger.warn(
      `${what} для ${gameId} не выполнен (состояние закоммичено, seq=${state.sequenceNumber}): ${e}`,
    );
  }
}
