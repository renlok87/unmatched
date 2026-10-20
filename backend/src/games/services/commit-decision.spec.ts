/**
 * SEL-07 (docs/research/de-reverse-2026-10-20): после saveState команда уже
 * применена — отказ публикации или очереди дедлайнов не должен превращаться в
 * errors[] для клиента (UE сочтёт это окончательным отказом, сбросит черновик
 * и даст повторить применённый ответ). Журнал (DET-2) коммитится в той же
 * транзакции saveState, что и состояние.
 */
import { commitDecision } from './commit-decision';
import type { JournalEntry, SaveStateOptions } from '../game-state.service';
import { GameActionType } from '../models/game-action.model';
import { GameActionsResolver } from '../resolvers/game-actions.resolver';
import { GamePhase, GameState } from '../../game-engine/models';

const state = (over: Partial<GameState> = {}): GameState =>
  ({
    gameId: 'g1',
    sequenceNumber: 11,
    phase: GamePhase.ACTION_MANEUVER,
    turnCount: 1,
    currentTurnPlayerId: 'a',
    players: [],
    fighters: [],
    decks: {},
    handZones: {},
    discardPiles: {},
    boardState: { width: 1, height: 1, cells: [[{ x: 0, y: 0, type: 'normal' }]] },
    metadata: { lastActionAt: new Date(0), lastActionBy: 'a', version: 1 },
    ...over,
  }) as unknown as GameState;

describe('commitDecision (SEL-07)', () => {
  const logger = () => ({ warn: jest.fn() });

  it('отказ publish после коммита не бросает; журнал уходит в saveState, GAME_ENDED всё равно публикуется', async () => {
    const calls: string[] = [];
    const log = logger();
    const journal: JournalEntry[] = [{ type: GameActionType.CARD_PLAYED, playerId: 'a', payload: { action: 'playScheme' } }];
    let saved: SaveStateOptions | undefined;
    await expect(
      commitDecision(
        {
          stateService: { saveState: async (_g: string, _s: GameState, options?: SaveStateOptions) => {
            calls.push('save');
            saved = options;
          } },
          subscription: {
            publishGameUpdate: async (_g: string, event: string) => {
              calls.push(`publish:${event}`);
              if (event === 'CARD_PLAYED') throw new Error('redis down');
            },
          },
          logger: log,
        },
        {
          gameId: 'g1',
          state: state({ phase: GamePhase.GAME_OVER }),
          eventType: 'CARD_PLAYED',
          journal,
        },
      ),
    ).resolves.toBeUndefined();
    expect(calls).toEqual(['save', 'publish:CARD_PLAYED', 'publish:GAME_ENDED']);
    // the journal rows are committed with the state, not after it
    expect(saved).toEqual({ journal });
    expect(log.warn).toHaveBeenCalledWith(expect.stringContaining('publish «CARD_PLAYED» для g1 не выполнен'));
  });

  it('отказ очереди дедлайнов боя не бросает, публикация идёт дальше', async () => {
    const published: string[] = [];
    await commitDecision(
      {
        stateService: { saveState: async () => {} },
        subscription: { publishGameUpdate: async (_g: string, event: string) => { published.push(event); } },
        combatTimeout: {
          scheduleAutoResolve: async () => { throw new Error('bullmq down'); },
          cancelAutoResolve: async () => {},
        },
        logger: logger(),
      },
      { gameId: 'g1', state: state(), eventType: 'DEFENSE_PLAYED' },
    );
    expect(published).toEqual(['DEFENSE_PLAYED']);
  });

  it('отказ saveState — настоящий отказ команды: пробрасывается, ничего не публикуется', async () => {
    const publish = jest.fn();
    await expect(
      commitDecision(
        {
          stateService: { saveState: async () => { throw new Error('optimistic conflict'); } },
          subscription: { publishGameUpdate: publish },
          logger: logger(),
        },
        { gameId: 'g1', state: state(), eventType: 'CARD_PLAYED' },
      ),
    ).rejects.toThrow('optimistic conflict');
    expect(publish).not.toHaveBeenCalled();
  });

  it('резолвер: resolvePendingEffect при упавшем publish возвращает результат, а не ошибку', async () => {
    const before = state({ sequenceNumber: 10 });
    const after = state({ sequenceNumber: 11 });
    const saved: number[] = [];
    const resolver = new GameActionsResolver(
      {
        loadState: async () => before,
        saveState: async (_g: string, s: GameState) => { saved.push(s.sequenceNumber); },
        filterPrivateData: (s: GameState) => s,
      } as any,
      { publishGameUpdate: async () => { throw new Error('redis down'); } } as any,
      { withLockOptions: async (_k: string, run: () => Promise<unknown>) => run() } as any,
      { scheduleAutoResolve: async () => {}, cancelAutoResolve: async () => {} } as any,
      { executeResolvePendingEffect: async () => ({ success: true, gameState: after }) } as any,
      { maybeRunAiTurns: async () => {} } as any,
    );
    const result = await resolver.resolvePendingEffect(
      { gameId: 'g1', effectId: 'e1', x: 0, y: 0, expectedSequenceNumber: 10 } as any,
      { req: { user: { id: 'a' } } },
    );
    expect(saved).toEqual([11]);
    expect(result.sequenceNumber).toBe(11);
  });
});
