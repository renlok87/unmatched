import { readFileSync } from 'node:fs';
import { createHash } from 'node:crypto';
import { resolve } from 'node:path';
import { GameInitializationService } from './game-initialization.service';
import { AdjacencyService } from '../../game-engine/engine/adjacency.service';
import { getCellZones } from '../../game-engine/models';

const root = resolve(__dirname, '../../../..');
const load = (path: string) => JSON.parse(readFileSync(resolve(root, path), 'utf8'));
const contract = load('docs/game-design/evidence/S04/board-contract.json');
const source = load(contract.source.path).adminBoard;
const captured = load('docs/game-design/evidence/S01/duel-start-p1.json');
const key = (p: { x: number; y: number }) => `${p.x}:${p.y}`;

async function initialize(order: string[]) {
  const heroes = {
    medusa: { id: 'medusa', name: 'Medusa', health: 16, movement: 3,
      properties: { attackType: 'ranged' },
      sidekicks: [{ name: 'Harpy', count: 3, health: 1 }] },
    arthur: { id: 'arthur', name: 'King Arthur', health: 18, movement: 2,
      sidekicks: [{ name: 'Merlin', health: 7, attackType: 'ranged' }] },
  };
  // Only persistence and catalog IO are substituted. Board construction,
  // seat ordering, collision avoidance and fighter creation are production code.
  const prisma = {
    game: { findUnique: async () => ({ boardId: source.id }) },
    board: { findUnique: async () => source },
    gamePlayer: { findMany: async () => order.map((heroId, seatOrder) =>
      ({ heroId, seatOrder, userId: `seat-${seatOrder}` })) },
    hero: { findUnique: async ({ where }: any) => ({ ...heroes[where.id], cards: [
      { id: `${where.id}-fixture`, name: 'Fixture', cardType: 'VERSATILE', count: 30, effects: [] },
    ] }) },
  };
  const saveState = jest.fn(async () => undefined);
  const service = new GameInitializationService(prisma as any, { saveState } as any);
  const state = await service.initializeGameState('s04-board');
  expect(saveState).toHaveBeenCalledWith('s04-board', state);
  return state;
}

describe('GD-014: versioned Cobble City runtime contract', () => {
  it('pins the source capture by hash, dimensions and all cells', () => {
    const canonical = JSON.stringify(load(contract.source.path));
    expect(createHash('sha256').update(canonical).digest('hex')).toBe(contract.source.sha256);
    expect([source.width, source.height]).toEqual([5, 6]);
    expect(contract.cells).toHaveLength(30);
    expect(new Set(contract.cells.map(key)).size).toBe(30);
    expect(contract.cells.map(({ x, y, zones }: any) => ({ x, y, zones }))).toEqual(source.cells);
  });

  it.each(contract.starts)('reproduces distinct start slots for $id', async (scenario: any) => {
    const state = await initialize(scenario.heroOrder);
    expect(state.boardState).toEqual(captured.boardState);
    expect(state.currentTurnPlayerId).toBe('seat-0');
    expect(state.fighters.map(f => ({ id: f.id, position: f.position }))).toEqual(scenario.fighters);
    expect(new Set(state.fighters.map(f => key(f.position))).size).toBe(6);
    for (const fighter of state.fighters) {
      expect(contract.cells.some((c: any) => key(c) === key(fighter.position))).toBe(true);
    }
  });

  it('enumerates every production adjacency and zone, not just the bounding box', async () => {
    const { boardState } = await initialize(['medusa', 'arthur']);
    const adjacency = new AdjacencyService();
    const directedEdges: string[] = [];
    for (const expected of contract.cells) {
      const actual = boardState.cells[expected.y][expected.x];
      expect(getCellZones(actual)).toEqual(expected.zones);
      const neighbors = adjacency.getAdjacentCells(boardState, expected)
        .filter(c => !c.isBlocked).map(c => key(c.position)).sort();
      expect(neighbors).toEqual([...expected.neighbors].sort());
      for (const neighbor of neighbors) {
        directedEdges.push(`${key(expected)}>${neighbor}`);
        expect(contract.cells.find((c: any) => key(c) === neighbor).neighbors).toContain(key(expected));
      }
    }
    expect(directedEdges).toHaveLength(98); // 49 undirected orthogonal edges.
    expect(contract.cells.filter((c: any) => c.zones.length > 1)).toEqual([]);
  });

  it('defines explicit forward/inverse world coordinate controls for the future UE consumer', () => {
    const { width, height, cellSizeUu } = contract;
    // INT-019 oracle, not a claim that the UE scene or its hit test is implemented.
    const world = (x: number, y: number) =>
      [(x - (width - 1) / 2) * cellSizeUu, (y - (height - 1) / 2) * cellSizeUu, 0];
    const cell = (x: number, y: number) =>
      [Math.floor(x / cellSizeUu + width / 2), Math.floor(y / cellSizeUu + height / 2)];
    for (const control of contract.worldControls) {
      expect(world(...control.cell as [number, number])).toEqual(control.world);
      expect(cell(control.world[0], control.world[1])).toEqual(control.cell);
    }
    for (const c of contract.cells) {
      const [x, y] = world(c.x, c.y);
      expect(cell(x, y)).toEqual([c.x, c.y]);
    }
  });
});
