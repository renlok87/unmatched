/**
 * ENV-MAPS B2: validateBoardGeometry (admin create/update) on boards with the
 * topology of an original map - cells carry `links` (lattice positions of the
 * linked spaces). On such a board the engine's neighbours are EXACTLY the
 * links, so broken links are hard errors; violet is a known zone.
 */
import { validateBoardGeometry } from './board-geometry.validator';
import { fixtureFiles, loadTopologyFixture } from '../../../prisma/seed-env-map-boards';

const space = (x: number, y: number, links: Array<{ x: number; y: number }>, extra = {}) => ({
  x,
  y,
  zones: ['violet'],
  spaceId: `S${x}${y}`,
  links,
  ...extra,
});

describe('validateBoardGeometry: original-map topology', () => {
  it.each(fixtureFiles())(
    'the committed fixture %s is a valid board (no errors, no warnings)',
    (file) => {
      const { fixture } = loadTopologyFixture(file);
      const result = validateBoardGeometry({
        width: fixture.lattice.width,
        height: fixture.lattice.height,
        cells: fixture.cells as never,
      });
      expect(result).toEqual({ valid: true, errors: [] });
    },
  );

  it('violet is a known zone (no unknown-zone warning)', () => {
    const result = validateBoardGeometry({
      width: 1,
      height: 1,
      cells: [{ x: 0, y: 0, zones: ['violet'] }],
    });
    expect(result).toEqual({ valid: true, errors: [] });
  });

  it('a long link over a hole is fine when both ends declare it', () => {
    const result = validateBoardGeometry({
      width: 3,
      height: 1,
      cells: [
        space(0, 0, [{ x: 2, y: 0 }]),
        { x: 1, y: 0, isObstacle: true },
        space(2, 0, [{ x: 0, y: 0 }]),
      ],
    });
    expect(result).toEqual({ valid: true, errors: [] });
  });

  it.each([
    ['asymmetric link', [space(0, 0, [{ x: 1, y: 0 }]), space(1, 0, [])], /Asymmetric link/],
    ['link to a missing cell', [space(0, 0, [{ x: 1, y: 0 }])], /missing cell/],
    [
      'link to an obstacle',
      [space(0, 0, [{ x: 1, y: 0 }]), { x: 1, y: 0, isObstacle: true, links: [] }],
      /obstacle cell \(1,0\)/,
    ],
    [
      'links on an obstacle',
      [space(0, 0, [{ x: 1, y: 0 }], { isObstacle: true }), space(1, 0, [{ x: 0, y: 0 }])],
      /Obstacle cell \(0,0\) must not carry links/,
    ],
    ['self link', [space(0, 0, [{ x: 0, y: 0 }])], /links to itself/],
    [
      'duplicate link',
      [
        space(0, 0, [
          { x: 1, y: 0 },
          { x: 1, y: 0 },
        ]),
        space(1, 0, [{ x: 0, y: 0 }]),
      ],
      /duplicate link/,
    ],
    ['non-integer link', [space(0, 0, [{ x: 0.5, y: 0 }])], /non-integer/],
    ['links not an array', [{ x: 0, y: 0, links: 'right' }], /must be an array/],
  ])('%s is a hard error', (_name, cells, message) => {
    const result = validateBoardGeometry({ width: 2, height: 1, cells: cells as never });
    expect(result.valid).toBe(false);
    expect(result.errors.some((e) => message.test(e))).toBe(true);
  });
});
