/**
 * Default board of a new game (decision НД-1,
 * docs/game-design/decisions/2026-10-04-real-boards-only.md): Marmoreal · original map.
 *
 * The id is the deterministic topology id of backend/prisma/fixtures/boards/marmoreal.topology.json,
 * written to the Board table by prisma/seed-env-map-boards.ts. default-board.spec.ts keeps the two equal.
 * The default used to be the oldest Board row (the synthetic Cobble City), with a literal 'default' fallback.
 */
export const DEFAULT_BOARD_ID = 'c121b47f8d6eb28daccb76d05';
export const DEFAULT_BOARD_NAME = 'Marmoreal · original map';

/**
 * The real game maps a room may switch to (selectBoard, docs/game-design/select-screens/02-DESIGN.md §2): only the
 * original maps of AGENTS.md «Board scenes and heroes» — Marmoreal and Sarpedon; synthetic boards never.
 */
export const SARPEDON_BOARD_ID = 'c7fa64a26c29a0835f2383e63';
export const REAL_BOARD_IDS: readonly string[] = [DEFAULT_BOARD_ID, SARPEDON_BOARD_ID];
