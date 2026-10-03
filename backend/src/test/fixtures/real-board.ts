/**
 * Real board rows for specs that start a game. A game without a usable board no longer starts on an empty
 * 20×20 grid (decision НД-2, docs/game-design/decisions/2026-10-04-real-boards-only.md), so such specs give
 * the game the default board, Marmoreal · original map.
 */
import { fixtureFiles, loadTopologyFixture, topologyBoardRow } from '../../../prisma/seed-env-map-boards';
import { DEFAULT_BOARD_ID } from '../../games/default-board';

/** The Board row of Marmoreal · original map exactly as prisma/seed-env-map-boards.ts writes it. */
export function marmorealBoardRow() {
  const file = fixtureFiles().find((f) => f.endsWith('marmoreal.topology.json'));
  if (!file) throw new Error('marmoreal.topology.json is not among the topology fixtures');
  const { fixture, sha256 } = loadTopologyFixture(file);
  const row = topologyBoardRow(fixture, sha256, file);
  if (row.id !== DEFAULT_BOARD_ID) throw new Error(`Marmoreal row ${row.id} != DEFAULT_BOARD_ID ${DEFAULT_BOARD_ID}`);
  return row;
}
