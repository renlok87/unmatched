import type { BoardDefinition } from '../../interfaces';
import { Zone } from '../../interfaces';

/**
 * Cobble City Board
 * A simple 6x4 board with colored zones for 2 players
 *
 * Zone layout:
 * Row 0: blue, blue, green, green, yellow, yellow
 * Row 1: blue, blue, green, green, yellow, yellow
 * Row 2: purple, purple, red, red, red, red
 * Row 3: purple, purple, red, red, red, red
 */
export const cobbleCity: BoardDefinition = {
  id: 'cobble-city',
  name: 'Cobble City',
  width: 6,
  height: 4,
  recommendedPlayers: 2,
  spaces: [
    // Row 0
    { position: { x: 0, y: 0 }, zones: [Zone.BLUE] },
    { position: { x: 1, y: 0 }, zones: [Zone.BLUE] },
    { position: { x: 2, y: 0 }, zones: [Zone.GREEN] },
    { position: { x: 3, y: 0 }, zones: [Zone.GREEN] },
    { position: { x: 4, y: 0 }, zones: [Zone.YELLOW] },
    { position: { x: 5, y: 0 }, zones: [Zone.YELLOW] },

    // Row 1
    { position: { x: 0, y: 1 }, zones: [Zone.BLUE] },
    { position: { x: 1, y: 1 }, zones: [Zone.BLUE, Zone.GREEN] },
    { position: { x: 2, y: 1 }, zones: [Zone.GREEN] },
    { position: { x: 3, y: 1 }, zones: [Zone.GREEN, Zone.YELLOW] },
    { position: { x: 4, y: 1 }, zones: [Zone.YELLOW] },
    { position: { x: 5, y: 1 }, zones: [Zone.YELLOW] },

    // Row 2
    { position: { x: 0, y: 2 }, zones: [Zone.PURPLE] },
    { position: { x: 1, y: 2 }, zones: [Zone.PURPLE, Zone.RED] },
    { position: { x: 2, y: 2 }, zones: [Zone.RED] },
    { position: { x: 3, y: 2 }, zones: [Zone.RED] },
    { position: { x: 4, y: 2 }, zones: [Zone.RED] },
    { position: { x: 5, y: 2 }, zones: [Zone.RED] },

    // Row 3
    { position: { x: 0, y: 3 }, zones: [Zone.PURPLE] },
    { position: { x: 1, y: 3 }, zones: [Zone.PURPLE] },
    { position: { x: 2, y: 3 }, zones: [Zone.RED] },
    { position: { x: 3, y: 3 }, zones: [Zone.RED] },
    { position: { x: 4, y: 3 }, zones: [Zone.RED] },
    { position: { x: 5, y: 3 }, zones: [Zone.RED] },
  ],
};
