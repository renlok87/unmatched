/**
 * Real board rows for specs that start a game. A game without a usable board no longer starts on an empty
 * 20×20 grid (decision НД-2, docs/game-design/decisions/2026-10-04-real-boards-only.md), so such specs give
 * the game a real map: the default board, Marmoreal · original map, or Sarpedon · original map.
 */
import { fixtureFiles, loadTopologyFixture, topologyBoardRow } from '../../../prisma/seed-env-map-boards';
import { DEFAULT_BOARD_ID } from '../../games/default-board';

/** Board id of Sarpedon · original map (AGENTS.md «Board scenes and heroes») */
export const SARPEDON_BOARD_ID = 'c7fa64a26c29a0835f2383e63';

function boardRow(fileSuffix: string, expectedId: string) {
  const file = fixtureFiles().find((f) => f.endsWith(fileSuffix));
  if (!file) throw new Error(`${fileSuffix} is not among the topology fixtures`);
  const { fixture, sha256 } = loadTopologyFixture(file);
  const row = topologyBoardRow(fixture, sha256, file);
  if (row.id !== expectedId) throw new Error(`${fileSuffix} row ${row.id} != expected board id ${expectedId}`);
  return row;
}

/** The Board row of Marmoreal · original map exactly as prisma/seed-env-map-boards.ts writes it. */
export function marmorealBoardRow() {
  return boardRow('marmoreal.topology.json', DEFAULT_BOARD_ID);
}

/** The Board row of Sarpedon · original map exactly as prisma/seed-env-map-boards.ts writes it. */
export function sarpedonBoardRow() {
  return boardRow('sarpedon.topology.json', SARPEDON_BOARD_ID);
}
