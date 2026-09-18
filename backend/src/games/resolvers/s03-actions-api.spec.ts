import 'reflect-metadata';
import { validate } from 'class-validator';
import { Test } from '@nestjs/testing';
import { GraphQLSchemaBuilderModule, GraphQLSchemaFactory, Query, Resolver } from '@nestjs/graphql';
import { printSchema } from 'graphql';
import * as gameplay from '../dto/gameplay.dto';
import { GameActionsResolver } from './game-actions.resolver';
import { GamePhase } from '../dto/create-game.dto';

@Resolver()
class SchemaQuery {
  @Query(() => Boolean)
  s03Ready() { return true; }
}

describe('S03 action API contract', () => {
  it('requires the maneuver identity and a nonnegative begin sequence', async () => {
    const beginClass = (gameplay as any).BeginManeuverDto;
    expect(beginClass).toBeDefined();
    expect(await validate(Object.assign(new beginClass(), { gameId: 'g', expectedSequenceNumber: 0 }))).toEqual([]);
    for (const sequence of [undefined, -1, 1.5]) {
      expect(await validate(Object.assign(new beginClass(), { gameId: 'g', expectedSequenceNumber: sequence })))
        .toEqual(expect.arrayContaining([expect.objectContaining({ property: 'expectedSequenceNumber' })]));
    }
    expect(await validate(Object.assign(new gameplay.ManeuverDto(), { gameId: 'g', moves: [] })))
      .toEqual(expect.arrayContaining([expect.objectContaining({ property: 'maneuverId' })]));
    expect(await validate(Object.assign(new gameplay.ManeuverDto(), { gameId: 'g', maneuverId: 'm1', moves: [] }))).toEqual([]);
  });

  it('requires a nonempty unique instance-card selection for discard', async () => {
    const discardClass = (gameplay as any).DiscardToLimitDto;
    expect(discardClass).toBeDefined();
    expect(await validate(Object.assign(new discardClass(), { gameId: 'g', pendingId: 'd1', cardIds: ['copy::1'] }))).toEqual([]);
    for (const cardIds of [[], ['copy::1', 'copy::1'], [42]]) {
      expect(await validate(Object.assign(new discardClass(), { gameId: 'g', pendingId: 'd1', cardIds })))
        .toEqual(expect.arrayContaining([expect.objectContaining({ property: 'cardIds' })]));
    }
  });

  it('publishes begin, completion and discard inputs in the generated GraphQL schema', async () => {
    const module = await Test.createTestingModule({ imports: [GraphQLSchemaBuilderModule] }).compile();
    try {
      const schema = printSchema(await module.get(GraphQLSchemaFactory).create([GameActionsResolver, SchemaQuery]));
      expect(schema).toContain('beginManeuver(input: BeginManeuverDto!): GameMutationResult!');
      expect(schema).toContain('discardToLimit(input: DiscardToLimitDto!): GameMutationResult!');
      expect(schema).toMatch(/input BeginManeuverDto \{[^}]*expectedSequenceNumber: Int!/s);
      expect(schema).toMatch(/input ManeuverDto \{[^}]*maneuverId: String!/s);
      expect(schema).toMatch(/input DiscardToLimitDto \{[^}]*pendingId: String![^}]*cardIds: \[String!\]!/s);
    } finally { await module.close(); }
  });

  it.each([
    ['beginManeuver', 'executeBeginManeuver', 'MANEUVER', { gameId: 'g', expectedSequenceNumber: 4 }],
    ['discardToLimit', 'executeDiscardToLimit', 'CARD_DISCARDED', { gameId: 'g', pendingId: 'd1', cardIds: ['copy::1'] }],
  ])('%s runs inside the existing lock/save/publish pipeline', async (method, executorMethod, eventType, dto) => {
    const before = { gameId: 'g', sequenceNumber: 4, metadata: {} };
    const after = { ...before, sequenceNumber: 5, phase: GamePhase.ACTION_MANEUVER, currentTurnPlayerId: 'p1', turnCount: 2 };
    const executor = { [executorMethod as string]: jest.fn().mockResolvedValue({ success: true, gameState: after }) };
    const state = { loadState: jest.fn().mockResolvedValue(before), saveState: jest.fn().mockResolvedValue(undefined),
      filterPrivateData: jest.fn().mockReturnValue({ ...after, filtered: true }) };
    const subscriptions = { publishGameUpdate: jest.fn().mockResolvedValue(undefined) };
    const lock = { withLockOptions: jest.fn().mockImplementation(async (_id, run) => run()) };
    const actions = { recordAction: jest.fn().mockResolvedValue(undefined) };
    const ai = { maybeRunAiTurns: jest.fn().mockResolvedValue(undefined) };
    const resolver = new GameActionsResolver(state as any, subscriptions as any, lock as any, {} as any,
      executor as any, actions as any, ai as any);
    expect(typeof (resolver as any)[method as string]).toBe('function');
    const result = await (resolver as any)[method as string](dto, { req: { user: { id: 'p1' } } });
    expect(lock.withLockOptions).toHaveBeenCalledWith('game:g', expect.any(Function), expect.any(Object));
    expect(executor[executorMethod as string]).toHaveBeenCalledWith(dto, { gameId: 'g', userId: 'p1', currentState: before });
    expect(state.saveState).toHaveBeenCalledWith('g', after);
    expect(subscriptions.publishGameUpdate).toHaveBeenCalledWith('g', eventType, after);
    expect(actions.recordAction).toHaveBeenCalledWith(expect.objectContaining({ type: eventType, sequenceNumber: 5 }));
    expect(JSON.parse(result.state)).toMatchObject({ filtered: true });
  });
});
