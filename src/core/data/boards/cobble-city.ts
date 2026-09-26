import type { BoardDefinition } from '../../models/types';
import { Zone } from '../../models/types';

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
  imageUrl: '/assets/boards/hells-kitchen.webp',
  spaces: [
    // Row 0
    { position: { x: 0, y: 0 }, zones: ['blue' as Zone] },
    { position: { x: 1, y: 0 }, zones: ['blue' as Zone] },
    { position: { x: 2, y: 0 }, zones: ['green' as Zone] },
    { position: { x: 3, y: 0 }, zones: ['green' as Zone] },
    { position: { x: 4, y: 0 }, zones: ['yellow' as Zone] },
    { position: { x: 5, y: 0 }, zones: ['yellow' as Zone] },

    // Row 1
    { position: { x: 0, y: 1 }, zones: ['blue' as Zone] },
    { position: { x: 1, y: 1 }, zones: ['blue' as Zone, 'green' as Zone] },
    { position: { x: 2, y: 1 }, zones: ['green' as Zone] },
    { position: { x: 3, y: 1 }, zones: ['green' as Zone, 'yellow' as Zone] },
    { position: { x: 4, y: 1 }, zones: ['yellow' as Zone] },
    { position: { x: 5, y: 1 }, zones: ['yellow' as Zone] },

    // Row 2
    { position: { x: 0, y: 2 }, zones: ['purple' as Zone] },
    { position: { x: 1, y: 2 }, zones: ['purple' as Zone, 'red' as Zone] },
    { position: { x: 2, y: 2 }, zones: ['red' as Zone] },
    { position: { x: 3, y: 2 }, zones: ['red' as Zone] },
    { position: { x: 4, y: 2 }, zones: ['red' as Zone] },
    { position: { x: 5, y: 2 }, zones: ['red' as Zone] },

    // Row 3
    { position: { x: 0, y: 3 }, zones: ['purple' as Zone] },
    { position: { x: 1, y: 3 }, zones: ['purple' as Zone] },
    { position: { x: 2, y: 3 }, zones: ['red' as Zone] },
    { position: { x: 3, y: 3 }, zones: ['red' as Zone] },
    { position: { x: 4, y: 3 }, zones: ['red' as Zone] },
    { position: { x: 5, y: 3 }, zones: ['red' as Zone] },
  ],
};
