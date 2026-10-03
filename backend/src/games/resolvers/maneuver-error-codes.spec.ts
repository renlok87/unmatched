/**
 * MS-AT-04 (move-selection 06 §1, MS-R-46): every rejection code of 02 §1.1
 * for beginManeuver, maneuver and resolvePendingEffect (MOVE/PLACE):
 *  1. executor - ActionResult.code carries the code, the message text is the
 *     same as before MS-T-06;
 *  2. real localhost HTTP GraphQL (production resolver, the production
 *     formatGraphqlError, synthetic auth, in-memory DB/cache/lock) - the code
 *     arrives as errors[0].extensions.ruleCode with the unchanged message, in
 *     NODE_ENV=development AND production;
 *  3. codes the network guards answer first (ActionPhaseGuard: NOT_YOUR_TURN,
 *     INVALID_PHASE) - the resolver path with a stubbed executor, then the
 *     formatter in both modes; a guard rejection itself has no ruleCode
 *     (02 §1.1: the client answers why.command.rejected).
 * HAND_NOT_FOUND and the validator's CARD_NOT_IN_HAND cannot reach the client
 * through the executor (it checks the hand instance first and answers
 * CARD_NOT_IN_HAND itself) - they are checked on the validator.
 */
import 'reflect-metadata';
import { INestApplication, ValidationPipe, BadRequestException } from '@nestjs/common';
import { Test } from '@nestjs/testing';
import { GraphQLModule } from '@nestjs/graphql';
import { ApolloDriver, ApolloDriverConfig } from '@nestjs/apollo';
import { GraphQLError } from 'graphql';
import { GameActionsResolver } from './game-actions.resolver';
import { GameResolver } from '../game.resolver';
import { GameStateService } from '../game-state.service';
import { GameSubscriptionService } from '../game-subscription.service';
import { GameService } from '../game.service';
import { PrismaService } from '../../database/prisma.service';
import { RedisService } from '../../redis/redis.service';
import { DistributedLockService } from '../../common/services/distributed-lock.service';
import { CombatTimeoutService } from '../services/combat-timeout.service';
import { GameActionService } from '../services/game-action.service';
import { AiTurnService } from '../services/ai-turn.service';
import { GqlAuthGuard } from '../../auth/guards/gql-auth.guard';
import { GqlThrottlerGuard } from '../guards/gql-throttler.guard';
import { formatGraphqlError } from '../../graphql/graphql.module';
import {
  ActionContext,
  ActionResult,
  GameActionExecutorService,
} from '../../game-engine/services/game-action-executor.service';
import { GameRulesValidator } from '../../game-engine/validators/game-rules.validator';
import { AdjacencyService } from '../../game-engine/engine/adjacency.service';
import { GamePhase, GameState, PendingEffect } from '../../game-engine/models';
import { s03Engine, s03Fixture } from '../../test/fixtures/s03-engine.fixture';
import {
  buildMoveFixtureState,
  fixtureActor,
  loadMoveFixtures,
} from '../../test/fixtures/move-fixture-state';

type Op = 'beginManeuver' | 'maneuver' | 'resolvePendingEffect';

interface CodeCase {
  /** unique label (the code, with a suffix when one code has several sources) */
  name: string;
  code: string;
  op: Op;
  /** the exact message text (unchanged by MS-T-06) */
  text: string | RegExp;
  state: () => GameState;
  actor: string;
  input: (state: GameState) => Record<string, unknown>;
  /** false: a network guard answers first (resolver path tested separately) */
  transport: boolean;
}

const MANEUVER_ID = 'maneuver:1:10';
const json = <T>(value: T): T => JSON.parse(JSON.stringify(value));

function base(hand = 1, actions = 2): GameState {
  return json(s03Fixture(hand, actions)) as GameState;
}
function edit(state: GameState, change: (s: any) => void): GameState {
  const copy: any = json(state);
  change(copy);
  return copy as GameState;
}
function withManeuver(state: GameState = base()): GameState {
  return edit(state, (s) => {
    s.metadata.pendingManeuver = { id: MANEUVER_ID, playerId: 'a' };
  });
}
const pendingMove = (extra: Partial<PendingEffect> = {}): PendingEffect =>
  ({ id: 'pe-1', type: 'MOVE', playerId: 'a', value: 1, text: 'fixture move', ...extra }) as PendingEffect;
function withPending(state: GameState, pending: PendingEffect): GameState {
  return edit(state, (s) => {
    s.metadata.pendingEffects = [pending];
  });
}
const maneuverInput =
  (moves: Array<{ fighterId: string; path: Array<{ x: number; y: number }> }>, boostCardId?: string) =>
  (s: GameState) => ({
    gameId: s.gameId,
    maneuverId: MANEUVER_ID,
    moves,
    ...(boostCardId ? { boostCardId } : {}),
  });
const resolveInput =
  (fighterId: string | undefined, x: number, y: number, effectId = 'pe-1') => (s: GameState) => ({
    gameId: s.gameId,
    effectId,
    ...(fighterId ? { fighterId } : {}),
    x,
    y,
  });
const beginInput = (seq?: number) => (s: GameState) => ({
  gameId: s.gameId,
  expectedSequenceNumber: seq ?? s.sequenceNumber,
});

const placeOutsideZone = loadMoveFixtures().find(
  (f) => f.name === 'pending-marmoreal-place-outside-zone-manual',
);
if (!placeOutsideZone) throw new Error('golden fixture pending-marmoreal-place-outside-zone-manual is missing');

/** Every code of move-selection 02 §1.1 the three mutations can answer. */
const CASES: CodeCase[] = [
  // ---- beginManeuver (canPlayerAct + executor) ----
  { name: 'NOT_YOUR_TURN', code: 'NOT_YOUR_TURN', op: 'beginManeuver', text: 'Not your turn',
    state: () => edit(base(), (s) => { s.currentTurnPlayerId = 'b'; }), actor: 'a', input: beginInput(),
    transport: false },
  { name: 'PLAYER_NOT_IN_GAME', code: 'PLAYER_NOT_IN_GAME', op: 'beginManeuver', text: 'Player is not in game',
    state: () => edit(base(), (s) => { s.players[0].isAlive = false; }), actor: 'a', input: beginInput(),
    transport: true },
  { name: 'BEGIN_NOT_ALLOWED', code: 'BEGIN_NOT_ALLOWED', op: 'beginManeuver',
    text: 'Cannot begin maneuver in current state', state: () => base(1, 0), actor: 'a', input: beginInput(),
    transport: true },
  { name: 'STATE_CHANGED (begin)', code: 'STATE_CHANGED', op: 'beginManeuver',
    text: 'State changed; reload before beginning maneuver', state: () => base(), actor: 'a',
    input: beginInput(9), transport: true },
  // ---- maneuver: executor ----
  { name: 'PENDING_CHOICE_OPEN (maneuver)', code: 'PENDING_CHOICE_OPEN', op: 'maneuver',
    text: 'Resolve the pending choice first',
    state: () => withPending(withManeuver(), pendingMove({ playerId: 'b' })), actor: 'a',
    input: maneuverInput([]), transport: true },
  { name: 'COMBAT_IN_PROGRESS', code: 'COMBAT_IN_PROGRESS', op: 'maneuver',
    text: 'Resolve the pending combat effect first',
    state: () => edit(withManeuver(), (s) => { s.metadata.combatResolutionProgress = { stage: 'fixture' }; }),
    actor: 'a', input: maneuverInput([]), transport: true },
  { name: 'GAME_OVER (maneuver)', code: 'GAME_OVER', op: 'maneuver', text: 'Game is already over',
    state: () => edit(withManeuver(), (s) => { s.fighters[1].health = 0; }), actor: 'a',
    input: maneuverInput([]), transport: true },
  { name: 'MANEUVER_NOT_OPEN', code: 'MANEUVER_NOT_OPEN', op: 'maneuver',
    text: 'Begin maneuver first, then resolve its matching choice', state: () => base(), actor: 'a',
    input: maneuverInput([]), transport: true },
  { name: 'CARD_NOT_IN_HAND (executor)', code: 'CARD_NOT_IN_HAND', op: 'maneuver',
    text: 'Boost must be a card instance in your hand', state: () => withManeuver(), actor: 'a',
    input: maneuverInput([], 'no-such-card'), transport: true },
  { name: 'DUPLICATE_FIGHTER', code: 'DUPLICATE_FIGHTER', op: 'maneuver',
    text: 'Каждый боец двигается в манёвре не более одного раза', state: () => withManeuver(), actor: 'a',
    input: maneuverInput([
      { fighterId: 'a', path: [{ x: 1, y: 0 }] },
      { fighterId: 'a', path: [{ x: 1, y: 0 }, { x: 2, y: 0 }] },
    ]), transport: true },
  // ---- maneuver: validator codes through the executor ----
  { name: 'FIGHTER_NOT_FOUND (maneuver)', code: 'FIGHTER_NOT_FOUND', op: 'maneuver', text: 'Fighter not found',
    state: () => withManeuver(), actor: 'a', input: maneuverInput([{ fighterId: 'ghost', path: [{ x: 1, y: 0 }] }]),
    transport: true },
  { name: 'NOT_YOUR_FIGHTER', code: 'NOT_YOUR_FIGHTER', op: 'maneuver', text: 'Not your fighter',
    state: () => withManeuver(), actor: 'a', input: maneuverInput([{ fighterId: 'b', path: [{ x: 6, y: 0 }] }]),
    transport: true },
  { name: 'FIGHTER_DEFEATED (maneuver)', code: 'FIGHTER_DEFEATED', op: 'maneuver', text: 'Fighter is defeated',
    state: () => edit(withManeuver(), (s) => { s.fighters[2].health = 0; }), actor: 'a',
    input: maneuverInput([{ fighterId: 'helper', path: [{ x: 1, y: 1 }] }]), transport: true },
  { name: 'FIGHTER_IMMOBILIZED', code: 'FIGHTER_IMMOBILIZED', op: 'maneuver',
    text: 'Боец обездвижен до конца хода (эффект карты)',
    state: () => edit(withManeuver(), (s) => { s.fighters[0].effects = [{ type: 'immobilized' }]; }), actor: 'a',
    input: maneuverInput([{ fighterId: 'a', path: [{ x: 1, y: 0 }] }]), transport: true },
  { name: 'INVALID_PHASE', code: 'INVALID_PHASE', op: 'maneuver', text: 'Can only maneuver during action phase',
    state: () => edit(withManeuver(), (s) => { s.phase = GamePhase.COMBAT; }), actor: 'a',
    input: maneuverInput([{ fighterId: 'a', path: [{ x: 1, y: 0 }] }]), transport: false },
  { name: 'EMPTY_PATH', code: 'EMPTY_PATH', op: 'maneuver', text: 'Path is empty', state: () => withManeuver(),
    actor: 'a', input: maneuverInput([{ fighterId: 'a', path: [] }]), transport: true },
  { name: 'INVALID_POSITION (maneuver)', code: 'INVALID_POSITION', op: 'maneuver', text: 'Invalid position in path',
    state: () => withManeuver(), actor: 'a', input: maneuverInput([{ fighterId: 'a', path: [{ x: 0, y: 5 }] }]),
    transport: true },
  { name: 'NOT_ENOUGH_MOVEMENT (maneuver)', code: 'NOT_ENOUGH_MOVEMENT', op: 'maneuver',
    text: /^Путь длиной 3 превышает очки движения бойца \(2\)$/, state: () => withManeuver(), actor: 'a',
    input: maneuverInput([{ fighterId: 'a', path: [{ x: 1, y: 0 }, { x: 2, y: 0 }, { x: 3, y: 0 }] }]),
    transport: true },
  { name: 'INVALID_STEP', code: 'INVALID_STEP', op: 'maneuver',
    text: 'Шаг (0,0)→(2,0) не является ходом на соседнюю клетку', state: () => withManeuver(), actor: 'a',
    input: maneuverInput([{ fighterId: 'a', path: [{ x: 2, y: 0 }] }]), transport: true },
  { name: 'PATH_BLOCKED_BY_ENEMY', code: 'PATH_BLOCKED_BY_ENEMY', op: 'maneuver',
    text: 'Путь проходит через живого противника на клетке (1, 0)',
    state: () => edit(withManeuver(), (s) => { s.fighters[1].position = { x: 1, y: 0 }; }), actor: 'a',
    input: maneuverInput([{ fighterId: 'a', path: [{ x: 1, y: 0 }, { x: 2, y: 0 }] }]), transport: true },
  { name: 'POSITION_OCCUPIED (maneuver)', code: 'POSITION_OCCUPIED', op: 'maneuver',
    text: 'Target position is occupied', state: () => withManeuver(), actor: 'a',
    input: maneuverInput([{ fighterId: 'a', path: [{ x: 0, y: 1 }] }]), transport: true },
  // ---- resolvePendingEffect (MOVE / PLACE) ----
  { name: 'PENDING_CHOICE_OPEN (pending)', code: 'PENDING_CHOICE_OPEN', op: 'resolvePendingEffect',
    text: 'Resolve the pending resource choice first',
    state: () => withPending(withManeuver(), pendingMove()), actor: 'a', input: resolveInput('a', 1, 0),
    transport: true },
  { name: 'GAME_OVER (pending)', code: 'GAME_OVER', op: 'resolvePendingEffect', text: 'Game is already over',
    state: () => edit(withPending(base(), pendingMove()), (s) => { s.fighters[1].health = 0; }), actor: 'a',
    input: resolveInput('a', 1, 0), transport: true },
  { name: 'STATE_CHANGED (pending gone)', code: 'STATE_CHANGED', op: 'resolvePendingEffect',
    text: 'Отложенный эффект не найден (протух или уже резолвлен)', state: () => withPending(base(), pendingMove()),
    actor: 'a', input: resolveInput('a', 1, 0, 'pe-gone'), transport: true },
  { name: 'PENDING_WRONG_FIGHTER (owner)', code: 'PENDING_WRONG_FIGHTER', op: 'resolvePendingEffect',
    text: 'Эффект двигает не этого бойца', state: () => withPending(base(), pendingMove()), actor: 'a',
    input: resolveInput('b', 6, 0), transport: true },
  { name: 'PENDING_WRONG_FIGHTER (name)', code: 'PENDING_WRONG_FIGHTER', op: 'resolvePendingEffect',
    text: 'Эффект двигает только «Merlin» (выбран helper)',
    state: () => withPending(base(), pendingMove({ fighterName: 'Merlin' })), actor: 'a',
    input: resolveInput('helper', 1, 1), transport: true },
  { name: 'PENDING_WRONG_FIGHTER (list)', code: 'PENDING_WRONG_FIGHTER', op: 'resolvePendingEffect',
    text: 'This fighter is not a target of the pending effect',
    state: () => withPending(base(), pendingMove({ fighterIds: ['a'] })), actor: 'a',
    input: resolveInput('helper', 1, 1), transport: true },
  { name: 'FIGHTER_NOT_FOUND (pending)', code: 'FIGHTER_NOT_FOUND', op: 'resolvePendingEffect',
    text: 'Боец не найден или повержен', state: () => withPending(base(), pendingMove()), actor: 'a',
    input: resolveInput('ghost', 1, 0), transport: true },
  { name: 'FIGHTER_DEFEATED (pending)', code: 'FIGHTER_DEFEATED', op: 'resolvePendingEffect',
    text: 'Боец не найден или повержен',
    state: () => edit(withPending(base(), pendingMove()), (s) => { s.fighters[2].health = 0; }), actor: 'a',
    input: resolveInput('helper', 1, 1), transport: true },
  { name: 'INVALID_POSITION (off board)', code: 'INVALID_POSITION', op: 'resolvePendingEffect',
    text: 'Клетка вне доски', state: () => withPending(base(), pendingMove()), actor: 'a',
    input: resolveInput('a', 9, 0), transport: true },
  { name: 'INVALID_POSITION (wall)', code: 'INVALID_POSITION', op: 'resolvePendingEffect',
    text: 'Клетка непроходима',
    state: () => edit(withPending(base(), pendingMove()), (s) => { s.boardState.cells[0][1].type = 'wall'; }),
    actor: 'a', input: resolveInput('a', 1, 0), transport: true },
  { name: 'POSITION_OCCUPIED (pending)', code: 'POSITION_OCCUPIED', op: 'resolvePendingEffect',
    text: 'Клетка занята', state: () => withPending(base(), pendingMove()), actor: 'a',
    input: resolveInput('a', 0, 1), transport: true },
  { name: 'NOT_ENOUGH_MOVEMENT (pending)', code: 'NOT_ENOUGH_MOVEMENT', op: 'resolvePendingEffect',
    text: 'До клетки (2, 0) не добраться за 1 шаг(ов)', state: () => withPending(base(), pendingMove()),
    actor: 'a', input: resolveInput('a', 2, 0), transport: true },
  { name: 'PLACE_OUTSIDE_ZONE', code: 'PLACE_OUTSIDE_ZONE', op: 'resolvePendingEffect',
    text: /^Клетка должна быть в зоне «.+»$/, state: () => buildMoveFixtureState(placeOutsideZone),
    actor: fixtureActor(placeOutsideZone),
    input: (s) => resolveInput(placeOutsideZone.pending!.fighterId, placeOutsideZone.pending!.target.x,
      placeOutsideZone.pending!.target.y, `pending:${placeOutsideZone.name}`)(s),
    transport: true },
];

/** 02 §1.1 codes of these three mutations (BOOST_NO_VALUE arrives with MS-T-20). */
const TABLE_CODES = [
  'FIGHTER_NOT_FOUND', 'NOT_YOUR_FIGHTER', 'FIGHTER_DEFEATED', 'FIGHTER_IMMOBILIZED', 'INVALID_PHASE',
  'HAND_NOT_FOUND', 'CARD_NOT_IN_HAND', 'EMPTY_PATH', 'INVALID_POSITION', 'NOT_ENOUGH_MOVEMENT', 'INVALID_STEP',
  'PATH_BLOCKED_BY_ENEMY', 'POSITION_OCCUPIED', 'NOT_YOUR_TURN', 'PLAYER_NOT_IN_GAME', 'BEGIN_NOT_ALLOWED',
  'STATE_CHANGED', 'PENDING_CHOICE_OPEN', 'COMBAT_IN_PROGRESS', 'GAME_OVER', 'MANEUVER_NOT_OPEN',
  'DUPLICATE_FIGHTER', 'PENDING_WRONG_FIGHTER', 'PLACE_OUTSIDE_ZONE',
];

const engine = s03Engine();

async function runExecutor(c: CodeCase): Promise<ActionResult> {
  const state = c.state();
  const ctx: ActionContext = { userId: c.actor, gameId: state.gameId, currentState: state };
  const input: any = c.input(state);
  if (c.op === 'beginManeuver') return engine.executor.executeBeginManeuver(input, ctx);
  if (c.op === 'maneuver') return engine.executor.executeManeuver(input, ctx);
  return engine.executor.executeResolvePendingEffect(input, ctx);
}
const textMatches = (actual: string | undefined, expected: string | RegExp) =>
  typeof expected === 'string' ? actual === expected : expected.test(actual ?? '');

describe('MS-AT-04 rule codes of beginManeuver / maneuver / resolvePendingEffect', () => {
  it('the case table covers every code of 02 §1.1 (except BOOST_NO_VALUE, MS-T-20)', () => {
    const covered = new Set(CASES.map((c) => c.code));
    covered.add('HAND_NOT_FOUND'); // validator-only, see below
    for (const code of TABLE_CODES) expect({ code, covered: covered.has(code) }).toEqual({ code, covered: true });
  });

  describe('executor: ActionResult.code + unchanged message', () => {
    it.each(CASES.map((c) => [c.name, c] as const))('%s', async (_name, c) => {
      const r = await runExecutor(c);
      expect(r.success).toBe(false);
      expect(r.code).toBe(c.code);
      expect({ text: r.error, matches: textMatches(r.error, c.text) }).toEqual({ text: r.error, matches: true });
    });
  });

  describe('validator-only codes (the executor answers CARD_NOT_IN_HAND first)', () => {
    const validator = new GameRulesValidator(new AdjacencyService());
    it('HAND_NOT_FOUND', () => {
      const state = edit(withManeuver(), (s) => { delete s.handZones.a; });
      expect(validator.validateManeuver(state, 'a', 'h0', [{ x: 1, y: 0 }], 'a')).toEqual({
        valid: false, error: 'Hand not found', code: 'HAND_NOT_FOUND',
      });
    });
    it('CARD_NOT_IN_HAND', () => {
      expect(validator.validateManeuver(withManeuver(), 'a', 'nope', [{ x: 1, y: 0 }], 'a')).toEqual({
        valid: false, error: 'Boost card not in hand', code: 'CARD_NOT_IN_HAND',
      });
    });
  });

  describe('formatGraphqlError keeps extensions.ruleCode in both modes', () => {
    const previous = process.env.NODE_ENV;
    afterAll(() => { process.env.NODE_ENV = previous; });
    const silence = () => jest.spyOn(console, 'error').mockImplementation(() => {});
    it.each(['development', 'production'])('%s', (mode) => {
      process.env.NODE_ENV = mode;
      const spy = silence();
      const business = formatGraphqlError({
        message: 'Not your turn', path: ['beginManeuver'],
        extensions: { code: 'BAD_USER_INPUT', ruleCode: 'NOT_YOUR_TURN', stacktrace: ['x'] },
      });
      expect(business.message).toBe('Not your turn');
      expect(business.extensions?.ruleCode).toBe('NOT_YOUR_TURN');
      expect(business.extensions?.code).toBe('BAD_USER_INPUT');
      // A guard rejection (no ruleCode) keeps its old shape: no ruleCode invented.
      const guard = formatGraphqlError({ message: 'Invalid phase', extensions: { code: 'BAD_REQUEST' } });
      expect(guard.extensions?.ruleCode).toBeUndefined();
      if (mode === 'production') {
        expect(business.extensions).toEqual({ code: 'BAD_USER_INPUT', ruleCode: 'NOT_YOUR_TURN' });
        expect(guard).toEqual({ message: 'Internal server error', code: 'INTERNAL_SERVER_ERROR' });
      }
      spy.mockRestore();
    });
  });

  describe('resolver: codes the network guards answer first', () => {
    const guarded = CASES.filter((c) => !c.transport);
    it.each(guarded.map((c) => [c.name, c] as const))('%s -> GraphQLError with ruleCode', async (_name, c) => {
      const state = c.state();
      const resolver = new GameActionsResolver(
        { loadState: async () => state } as any,
        {} as any,
        { withLockOptions: async (_k: string, run: () => Promise<unknown>) => run() } as any,
        {} as any,
        { executeBeginManeuver: () => runExecutor(c), executeManeuver: () => runExecutor(c) } as any,
        {} as any,
        { maybeRunAiTurns: async () => {} } as any,
      );
      const call = c.op === 'beginManeuver'
        ? resolver.beginManeuver(c.input(state) as any, { req: { user: { id: c.actor } } })
        : resolver.maneuver(c.input(state) as any, { req: { user: { id: c.actor } } }, null);
      const error: unknown = await call.then(() => null, (e: unknown) => e);
      expect(error).toBeInstanceOf(GraphQLError);
      const gql = error as GraphQLError;
      expect(gql.extensions).toMatchObject({ code: 'BAD_USER_INPUT', ruleCode: c.code });
      expect(textMatches(gql.message, c.text)).toBe(true);
    });

    it('a rejection without a code keeps the BadRequestException', async () => {
      const resolver = new GameActionsResolver(
        { loadState: async () => base() } as any, {} as any,
        { withLockOptions: async (_k: string, run: () => Promise<unknown>) => run() } as any, {} as any,
        { executeBeginManeuver: async () => ({ success: false, error: 'legacy text' }) } as any, {} as any,
        { maybeRunAiTurns: async () => {} } as any,
      );
      await expect(
        resolver.beginManeuver({ gameId: 's03', expectedSequenceNumber: 10 } as any, { req: { user: { id: 'a' } } }),
      ).rejects.toBeInstanceOf(BadRequestException);
    });
  });

  describe('real HTTP GraphQL: errors[0].extensions.ruleCode', () => {
    let app: INestApplication;
    let url: string;
    let states: GameStateService;
    const rows = new Map<string, any>();
    const games = new Map<string, { status: string }>();
    const members = new Map<string, Set<string>>();
    const cache = new Map<string, any>();
    const previousEnv = process.env.NODE_ENV;
    let consoleSpy: jest.SpyInstance;

    beforeAll(async () => {
      consoleSpy = jest.spyOn(console, 'error').mockImplementation(() => {});
      const redis = {
        getJson: async (key: string) => (cache.has(key) ? json(cache.get(key)) : null),
        setJsonex: async (key: string, _ttl: number, value: unknown) => { cache.set(key, json(value)); return 'OK'; },
        del: async (key: string) => { cache.delete(key); },
        subscribe: () => {}, publish: async () => 1,
      };
      const prisma = {
        gameState: {
          findUnique: async ({ where }: any) => (rows.has(where.gameId) ? json(rows.get(where.gameId)) : null),
          upsert: async ({ where, create, update }: any) => {
            const row = json(rows.has(where.gameId) ? { ...rows.get(where.gameId), ...update } : create);
            rows.set(where.gameId, row);
            return row;
          },
        },
        game: {
          findUnique: async ({ where }: any) => games.get(where.id) ?? null,
          updateMany: async () => ({ count: 1 }),
          update: async () => ({}),
        },
        gamePlayer: {
          findUnique: async ({ where }: any) =>
            members.get(where.gameId_userId.gameId)?.has(where.gameId_userId.userId) ? {} : null,
        },
        $transaction: async (run: (tx: unknown) => unknown) => run(prisma),
      };
      const module = await Test.createTestingModule({
        imports: [GraphQLModule.forRoot<ApolloDriverConfig>({
          driver: ApolloDriver, autoSchemaFile: true, csrfPrevention: false,
          context: (ctx: any) => ({ req: ctx.req }),
          includeStacktraceInErrorResponses: false,
          formatError: formatGraphqlError,
        })],
        // GameResolver: the schema needs a Query root (its queries are not called).
        providers: [GameActionsResolver, GameResolver, GameStateService,
          { provide: GameSubscriptionService, useValue: { publishGameUpdate: async () => {} } },
          { provide: GameActionExecutorService, useValue: engine.executor },
          { provide: PrismaService, useValue: prisma }, { provide: RedisService, useValue: redis },
          { provide: DistributedLockService, useValue: {
            withLockOptions: async (_key: string, run: () => Promise<unknown>) => run() } },
          { provide: CombatTimeoutService, useValue: {
            scheduleAutoResolve: async () => {}, cancelAutoResolve: async () => {} } },
          { provide: GameActionService, useValue: { recordAction: async () => {} } },
          { provide: AiTurnService, useValue: { maybeRunAiTurns: async () => {} } },
          { provide: GameService, useValue: { requireParticipation: async () => {} } },
        ],
      }).overrideGuard(GqlAuthGuard).useValue({ canActivate: (context: any) => {
        const req = context.getArgByIndex(2).req;
        const userId = req.headers['x-fixture-user'];
        if (!userId) return false;
        req.user = { id: userId };
        return true;
      } })
        .overrideGuard(GqlThrottlerGuard).useValue({ canActivate: () => true })
        .compile();
      app = module.createNestApplication();
      app.useLogger(false);
      app.useGlobalPipes(new ValidationPipe({ transform: true, whitelist: true }));
      states = app.get(GameStateService);
      await app.listen(0, '127.0.0.1');
      url = await app.getUrl();
    }, 15000);

    afterAll(async () => {
      process.env.NODE_ENV = previousEnv;
      consoleSpy?.mockRestore();
      await app?.close();
    });

    const documents: Record<Op, string> = {
      beginManeuver: 'mutation M($input: BeginManeuverDto!) { beginManeuver(input: $input) { sequenceNumber } }',
      maneuver: 'mutation M($input: ManeuverDto!) { maneuver(input: $input) { sequenceNumber } }',
      resolvePendingEffect:
        'mutation M($input: ResolvePendingEffectDto!) { resolvePendingEffect(input: $input) { sequenceNumber } }',
    };

    let seeded = 0;
    function seed(c: CodeCase): { gameId: string; state: GameState } {
      const gameId = `ms-at-04-${++seeded}`;
      const raw = c.state();
      // The JSON clones of the case table turn Dates into strings; serialize wants a Date.
      const state = {
        ...raw,
        gameId,
        metadata: { ...raw.metadata, lastActionAt: new Date(raw.metadata.lastActionAt as unknown as string) },
      } as GameState;
      rows.set(gameId, { gameId, sequenceNumber: state.sequenceNumber, state: json(states.serialize(state)) });
      games.set(gameId, { status: 'IN_PROGRESS' });
      members.set(gameId, new Set(state.players.map((p) => p.userId)));
      cache.delete(`gamestate:${gameId}`);
      return { gameId, state };
    }

    const reachable = CASES.filter((c) => c.transport);
    for (const mode of ['development', 'production']) {
      it.each(reachable.map((c) => [c.name, c] as const))(`${mode}: %s`, async (_name, c) => {
        process.env.NODE_ENV = mode;
        const { state } = seed(c);
        const response = await fetch(`${url}/graphql`, {
          method: 'POST',
          headers: { 'content-type': 'application/json', 'x-fixture-user': c.actor },
          body: JSON.stringify({ query: documents[c.op], variables: { input: c.input(state) } }),
        });
        const body: any = await response.json();
        // The UE client reads GraphQL rejections from an HTTP 200 body (S08GraphqlClient).
        expect(response.status).toBe(200);
        expect(body.errors).toHaveLength(1);
        const error = body.errors[0];
        expect(error.extensions?.ruleCode).toBe(c.code);
        expect(error.extensions?.code).toBe('BAD_USER_INPUT');
        expect({ text: error.message, matches: textMatches(error.message, c.text) }).toEqual({
          text: error.message, matches: true,
        });
      });
    }
  });
});
