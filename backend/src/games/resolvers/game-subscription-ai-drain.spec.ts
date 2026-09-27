/** GD-039: подписка/реконнект gameStateUpdated возобновляет прерванный ход
 *  бота VS_AI. Если дрейн бота оборвался (рестарт процесса/очереди), человек
 *  в чужой фазе не имеет легальных мутаций — повторный вход в подписку
 *  обязан снова запустить maybeRunAiTurns (fire-and-forget, no-op вне VS_AI). */
import 'reflect-metadata';
import { Test } from '@nestjs/testing';
import { GameSubscriptionResolver } from './game-subscription.resolver';
import { GameSubscriptionService, GamePubSubEvent } from '../game-subscription.service';
import { GameStateService } from '../game-state.service';
import { AiTurnService } from '../services/ai-turn.service';

/* eslint-disable @typescript-eslint/no-explicit-any */

class FakeUpstream implements AsyncIterableIterator<GamePubSubEvent> {
  next(): Promise<IteratorResult<GamePubSubEvent>> {
    return new Promise(() => {}); // никогда не резолвится — как реальный PubSub
  }
  async return(): Promise<IteratorResult<GamePubSubEvent>> {
    return { done: true, value: undefined };
  }
  [Symbol.asyncIterator](): AsyncIterableIterator<GamePubSubEvent> {
    return this;
  }
}

const stateAt = (sequenceNumber: number) =>
  ({
    sequenceNumber,
    phase: 'ACTION_MANEUVER',
    turnCount: 1,
    currentTurnPlayerId: 'ai',
    players: [],
    fighters: [],
    handZones: {},
    discardPiles: {},
    boardState: {},
    metadata: {},
  }) as any;

async function buildResolver(aiTurn: { maybeRunAiTurns: jest.Mock }) {
  const module = await Test.createTestingModule({
    providers: [
      GameSubscriptionResolver,
      {
        provide: GameSubscriptionService,
        useValue: { asyncIteratorForGame: () => new FakeUpstream() },
      },
      {
        provide: GameStateService,
        useValue: {
          loadState: async () => stateAt(5),
          isParticipant: async () => true,
          filterPrivateData: (payload: any) => payload,
        },
      },
      { provide: AiTurnService, useValue: aiTurn },
    ],
  }).compile();
  return module.get(GameSubscriptionResolver);
}

describe('gameStateUpdated возобновляет дрейн бота (GD-039)', () => {
  it('успешная подписка участника → maybeRunAiTurns(gameId) вызван', async () => {
    const aiTurn = { maybeRunAiTurns: jest.fn().mockResolvedValue(undefined) };
    const resolver = await buildResolver(aiTurn);

    await resolver.gameStateUpdated('g1', 0, undefined, { req: { user: { id: 'u1' } } } as any);

    expect(aiTurn.maybeRunAiTurns).toHaveBeenCalledWith('g1');
  });

  it('не-участник не дергает дрейн (403 раньше триггера)', async () => {
    const aiTurn = { maybeRunAiTurns: jest.fn().mockResolvedValue(undefined) };
    const module = await Test.createTestingModule({
      providers: [
        GameSubscriptionResolver,
        { provide: GameSubscriptionService, useValue: { asyncIteratorForGame: () => new FakeUpstream() } },
        {
          provide: GameStateService,
          useValue: {
            loadState: async () => stateAt(5),
            isParticipant: async () => false,
            filterPrivateData: (payload: any) => payload,
          },
        },
        { provide: AiTurnService, useValue: aiTurn },
      ],
    }).compile();
    const resolver = module.get(GameSubscriptionResolver);

    await expect(
      resolver.gameStateUpdated('g1', 0, undefined, { req: { user: { id: 'zzz' } } } as any),
    ).rejects.toThrow();

    expect(aiTurn.maybeRunAiTurns).not.toHaveBeenCalled();
  });
});
