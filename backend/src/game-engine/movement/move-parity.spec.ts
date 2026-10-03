/**
 * MS-AT-02: every golden move fixture through the server layer named by
 * expect.layer (dto / validator / executor / resolvePending) on a full
 * GameState (src/test/fixtures/move-fixture-state.ts); `server` is 'ok' or a
 * code of docs/game-design/move-selection/02-rules-and-edge-cases.md §1.1.
 * A fixture with `pendingRuleChange` documents a server-vs-rules deviation:
 * it asserts today's answer; the named task (MS-T-19/20) flips it.
 */
import {
  DTO_REJECTED,
  loadMoveFixtures,
  runFixtureLayer,
  serverCodeOf,
  topologyStaleness,
  type MoveFixture,
} from '../../test/fixtures/move-fixture-state';

/** Codes of 02 §1.1 (existing validator codes and the MS-T-06 / MS-T-20 ones) */
const RULE_CODES = new Set([
  'FIGHTER_NOT_FOUND',
  'NOT_YOUR_FIGHTER',
  'FIGHTER_DEFEATED',
  'FIGHTER_IMMOBILIZED',
  'INVALID_PHASE',
  'HAND_NOT_FOUND',
  'CARD_NOT_IN_HAND',
  'EMPTY_PATH',
  'INVALID_POSITION',
  'NOT_ENOUGH_MOVEMENT',
  'INVALID_STEP',
  'PATH_BLOCKED_BY_ENEMY',
  'POSITION_OCCUPIED',
  'NOT_YOUR_TURN',
  'PLAYER_NOT_IN_GAME',
  'BEGIN_NOT_ALLOWED',
  'STATE_CHANGED',
  'PENDING_CHOICE_OPEN',
  'COMBAT_IN_PROGRESS',
  'GAME_OVER',
  'MANEUVER_NOT_OPEN',
  'DUPLICATE_FIGHTER',
  'PENDING_WRONG_FIGHTER',
  'PLACE_OUTSIDE_ZONE',
  'BOOST_NO_VALUE',
]);

const FIXTURES = loadMoveFixtures();

describe('MS-AT-02 fixture contract', () => {
  it('every expected server answer is ok, DTO_REJECTED (dto layer) or a 02 §1.1 code', () => {
    for (const fx of FIXTURES) {
      const codes = [fx.expect.server, fx.expect.pendingRuleChange?.server].filter(Boolean);
      for (const code of codes) {
        const allowed =
          code === 'ok' ||
          RULE_CODES.has(code) ||
          (code === DTO_REJECTED && fx.expect.layer === 'dto');
        expect({ fixture: fx.name, code, allowed }).toEqual({
          fixture: fx.name,
          code,
          allowed: true,
        });
      }
    }
  });

  it('every layer is exercised', () => {
    const layers = new Set(FIXTURES.map((f) => f.expect.layer));
    expect([...layers].sort()).toEqual(['dto', 'executor', 'resolvePending', 'validator']);
  });

  it('serverCodeOf prefers ActionResult.code (MS-T-06) and flags unknown texts', () => {
    expect(serverCodeOf({ success: true })).toBe('ok');
    expect(serverCodeOf({ success: false, error: 'Клетка (3, 4) занята' })).toBe(
      'POSITION_OCCUPIED',
    );
    expect(serverCodeOf({ success: false, error: 'Клетка занята', code: 'X_CODE' })).toBe('X_CODE');
    expect(serverCodeOf({ success: false, error: 'something new' })).toBe(
      'UNMAPPED: something new',
    );
  });
});

describe.each(FIXTURES.map((f) => [f.name, f] as const))(
  'MS-AT-02 %s',
  (_name: string, fx: MoveFixture) => {
    it(`${fx.expect.layer} answers ${fx.expect.server}`, async () => {
      expect(topologyStaleness(fx)).toBeNull();
      const outcome = await runFixtureLayer(fx);
      expect({ server: outcome.server, error: outcome.error }).toEqual({
        server: fx.expect.server,
        error: outcome.error,
      });
      // dto layer: the rejection is for the expected constraint, not any constraint
      if (fx.expect.serverDetail !== undefined) expect(outcome.error).toBe(fx.expect.serverDetail);
      if (outcome.server !== 'ok' || !outcome.positions) return;
      // accepted: every fighter ends where its command (or the pending target) put it
      if (fx.expect.layer === 'resolvePending') {
        expect(outcome.positions[fx.pending.fighterId]).toEqual(fx.pending.target);
      } else {
        for (const mv of outcome.moves ?? []) {
          expect(outcome.positions[mv.fighterId]).toEqual(mv.path[mv.path.length - 1]);
        }
      }
    });
  },
);
