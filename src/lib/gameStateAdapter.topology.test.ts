/**
 * ENV-MAPS B2 guard: the web client plays and renders boards on a GRID. A board
 * with the topology of an original map (cells carry `links`) must never be
 * rendered here as a grid - the adapter refuses it with an explicit error,
 * grid boards (Cobble City, no links) are adapted exactly as before.
 */
import { describe, expect, it } from 'vitest';
import {
  adaptToLocal,
  isTopologyWireBoard,
  UnsupportedBoardTopologyError,
  type AdapterRefs,
  type WireGameState,
} from './gameStateAdapter';

const refs: AdapterRefs = { usernames: {}, heroAssets: {}, board: null, stanceOptions: {} };

function wire(cells: WireGameState['boardState']['cells']): WireGameState {
  return {
    gameId: 'g', sequenceNumber: 1, phase: 'ACTION_MANEUVER', turnCount: 1, currentTurnPlayerId: 'a',
    players: [{ userId: 'a', heroId: 'a', health: 10, maxHealth: 10, fighterIds: [], isAlive: true }],
    fighters: [], handZones: { a: { cards: [], maxSize: 7 } }, metadata: { actionsRemaining: 2 },
    boardState: { width: 3, height: 1, cells },
  };
}

const grid = [[{ type: 'normal', zone: 'red' }, { type: 'normal', zone: 'red' }, { type: 'obstacle' }]];
const topology = [[
  { type: 'normal', zone: 'red', links: [{ x: 2, y: 0 }] },
  { type: 'obstacle' },
  { type: 'normal', zone: 'blue', links: [{ x: 0, y: 0 }] },
]];

describe('ENV-MAPS: topology boards are not rendered by the web client', () => {
  it('detects topology only when a cell carries a links array', () => {
    expect(isTopologyWireBoard(wire(topology).boardState)).toBe(true);
    expect(isTopologyWireBoard(wire([[{ type: 'normal', links: [] }]]).boardState)).toBe(true);
    expect(isTopologyWireBoard(wire(grid).boardState)).toBe(false);
    expect(isTopologyWireBoard(wire(undefined).boardState)).toBe(false);
    expect(isTopologyWireBoard(undefined)).toBe(false);
  });

  it('refuses a topology board with an explicit error instead of a grid rendering', () => {
    expect(() => adaptToLocal(wire(topology), refs, 'a')).toThrow(UnsupportedBoardTopologyError);
    // even when the content catalog handed over a same-size grid definition
    const sameSize = { id: 'x', name: 'x', width: 3, height: 1, recommendedPlayers: 2, spaces: [] };
    expect(() => adaptToLocal(wire(topology), { ...refs, board: sameSize as never }, 'a')).toThrow(
      /UE/,
    );
  });

  it('grid boards are adapted as before', () => {
    const local = adaptToLocal(wire(grid), refs, 'a');
    expect(local.board.definition.spaces).toEqual([
      { position: { x: 0, y: 0 }, zones: ['red'], isObstacle: false },
      { position: { x: 1, y: 0 }, zones: ['red'], isObstacle: false },
      { position: { x: 2, y: 0 }, zones: [], isObstacle: true },
    ]);
  });
});
