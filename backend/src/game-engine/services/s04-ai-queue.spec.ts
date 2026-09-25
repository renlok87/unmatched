/** GD-018: AI obeys the global sequential queue — never skips a foreign head,
 * declines its own useless optional head, and a full VS_AI drain resolves the
 * chain and the deferred turn transfer exactly once. */
import { GamePhase, GameState, PendingEffect } from '../models';
import { s03Fixture, s03Engine } from '../../test/fixtures/s03-engine.fixture';
import { AiDecisionService } from './ai-decision.service';
import { AdjacencyService } from '../engine/adjacency.service';
import { AiTurnService } from '../../games/services/ai-turn.service';

const decision = new AiDecisionService(new AdjacencyService());
const { executor } = s03Engine();

function queueState(pendings: PendingEffect[], extra: Partial<GameState> = {}): GameState {
  const base = s03Fixture(0, 0);
  return { ...base, ...extra, metadata: { ...base.metadata, pendingEffects: pendings } };
}

describe('GD-018: AI queue decisions', () => {
  it('never skips a foreign head of the queue', () => {
    const state = queueState([
      { id: 'pe1', type: 'MOVE', playerId: 'a', value: 2 },
    ]);
    expect(decision.decide(state, 'b')).toBeNull();
  });

  it('resolves its own mandatory MOVE head toward the enemy', () => {
    const state = queueState([
      { id: 'pe1', type: 'MOVE', playerId: 'b', value: 1 },
    ]);
    const action = decision.decide(state, 'b');
    expect(action).toMatchObject({ kind: 'resolveMove', effectId: 'pe1', fighterId: 'b' });
    expect((action as any).x).toBeLessThan(7); // шаг к врагу на (0,0)
  });

  it('declines its own optional head when no useful decision exists', () => {
    const state = queueState([
      { id: 'pe1', type: 'CHOOSE_ONE', playerId: 'b', options: [], optional: true },
    ]);
    expect(decision.decide(state, 'b')).toEqual({ kind: 'declinePending', effectId: 'pe1' });
  });

  it('keeps waiting on an undecided mandatory head instead of fabricating', () => {
    const state = queueState([
      { id: 'pe1', type: 'CHOOSE_ONE', playerId: 'b', options: [] },
    ]);
    expect(decision.decide(state, 'b')).toBeNull();
  });

  it('drains a two-choice chain and completes the deferred transfer once', async () => {
    const base = s03Fixture(0, 0);
    const state: GameState = { ...base,
      currentTurnPlayerId: 'b',
      metadata: { ...base.metadata,
        pendingEffects: [
          { id: 'pe1', type: 'MOVE', playerId: 'b', value: 1 },
          { id: 'pe2', type: 'CHOOSE_ONE', playerId: 'b', options: [], optional: true },
        ],
        pendingTurnEnd: { playerId: 'b', endEffectsApplied: false },
      } };
    let stored = state;
    const service = new AiTurnService(
      { game: { findUnique: async () =>
        ({ mode: 'VS_AI', opponentId: 'b', status: 'IN_PROGRESS' }) } } as any,
      { withLockOptions: (_k: string, run: () => any) => run() } as any,
      { loadState: async () => stored, saveState: async (_id: string, s: GameState) => { stored = s; } } as any,
      { publishGameUpdate: async () => ({}) } as any,
      executor,
      decision,
    );
    await service.maybeRunAiTurns('s04-ai');
    expect(stored.sequenceNumber).toBe(12);
    expect(stored.metadata.pendingEffects ?? []).toHaveLength(0);
    expect(stored.metadata.pendingTurnEnd).toBeUndefined();
    expect(stored.currentTurnPlayerId).toBe('a');
    expect(stored.metadata.actionsRemaining).toBe(2);
    expect(stored.phase).toBe(GamePhase.ACTION_MANEUVER);
  });
});

/** P1-2 regressions: после смежной атаки closer-клеток нет — optional MOVE
 * бот должен отклонить, mandatory — резолвнуть нулевым шагом; полный drain
 * не strand'ит VS_AI-матч. */
describe('GD-018 corrections: AI adjacent / no-move heads', () => {
  // 'b'(1,0) смежен с 'a'(0,0); все свободные клетки не ближе → step=null.
  const adjacentState = (pendings: PendingEffect[], extra: Partial<GameState> = {}): GameState => {
    const base = s03Fixture(0, 0);
    const fighters = base.fighters.map(f =>
      f.id === 'b' ? { ...f, position: { x: 1, y: 0 } } : f);
    return { ...base, ...extra, fighters,
      metadata: { ...base.metadata, ...extra.metadata, pendingEffects: pendings } };
  };

  it('declines an optional MOVE head when already adjacent (no improving step)', () => {
    const state = adjacentState([
      { id: 'pe1', type: 'MOVE', playerId: 'b', value: 4, optional: true },
    ]);
    expect(decision.decide(state, 'b')).toEqual({ kind: 'declinePending', effectId: 'pe1' });
  });

  it('resolves a mandatory MOVE head adjacent to the enemy with a legal zero step', () => {
    const state = adjacentState([
      { id: 'pe1', type: 'MOVE', playerId: 'b', value: 4, optional: false },
    ]);
    expect(decision.decide(state, 'b')).toMatchObject(
      { kind: 'resolveMove', effectId: 'pe1', fighterId: 'b', x: 1, y: 0 });
  });

  it('declines an optional head even with a distant enemy when no step improves', () => {
    // Полностью заблокированный боец: враг на (1,0), союзник 'a' на (0,0),
    // 'b' на (0,1) в углу 2x2 — свободных closer-клеток нет.
    const base = s03Fixture(0, 0);
    const fighters = [
      { ...base.fighters[0]!, position: { x: 0, y: 0 } },
      { ...base.fighters[2]!, position: { x: 1, y: 0 }, ownerId: 'b' },
      { ...base.fighters[1]!, position: { x: 0, y: 1 } },
    ];
    const board = { width: 2, height: 2,
      cells: Array.from({ length: 2 }, (_, y) =>
        Array.from({ length: 2 }, (_, x) => ({ x, y, type: 'normal' }))),
      doors: {}, fog: {}, tokens: {} };
    const state: GameState = { ...base, fighters, boardState: board as any,
      metadata: { ...base.metadata, pendingEffects: [
        { id: 'pe1', type: 'MOVE', playerId: 'b', value: 2, optional: true },
      ] } };
    expect(decision.decide(state, 'b')).toEqual({ kind: 'declinePending', effectId: 'pe1' });
  });

  it('full drain with adjacent fighters: zero-step mandatory + declined optional, transfer once', async () => {
    const base = s03Fixture(0, 0);
    const fighters = base.fighters.map(f =>
      f.id === 'b' ? { ...f, position: { x: 1, y: 0 } } : f);
    let stored: GameState = { ...base,
      currentTurnPlayerId: 'b',
      fighters,
      metadata: { ...base.metadata,
        pendingEffects: [
          { id: 'pe1', type: 'MOVE', playerId: 'b', value: 4, optional: false },
          { id: 'pe2', type: 'MOVE', playerId: 'b', value: 4, optional: true },
        ],
        pendingTurnEnd: { playerId: 'b', endEffectsApplied: false },
      } };
    const service = new AiTurnService(
      { game: { findUnique: async () =>
        ({ mode: 'VS_AI', opponentId: 'b', status: 'IN_PROGRESS' }) } } as any,
      { withLockOptions: (_k: string, run: () => any) => run() } as any,
      { loadState: async () => stored, saveState: async (_id: string, s: GameState) => { stored = s; } } as any,
      { publishGameUpdate: async () => ({}) } as any,
      executor,
      decision,
    );
    await service.maybeRunAiTurns('s04-ai-adjacent');
    expect(stored.metadata.pendingEffects ?? []).toHaveLength(0);
    expect(stored.metadata.pendingTurnEnd).toBeUndefined();
    expect(stored.currentTurnPlayerId).toBe('a');
    expect(stored.metadata.actionsRemaining).toBe(2);
    expect(stored.sequenceNumber).toBe(12); // resolve(11) + decline(12), одна передача
  });
});
