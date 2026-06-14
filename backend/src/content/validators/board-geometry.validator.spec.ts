import { validateBoardGeometry } from './board-geometry.validator';

/**
 * Тесты чистого валидатора геометрии доски.
 *
 * Форма входа повторяет JSON, который админ вводит в admin/.../boards/create.tsx:
 *   cells: [{ x, y, type, zone, connections: ['right','down'] }]
 *   features: { secretPassages, doors, highGround }
 */
describe('validateBoardGeometry', () => {
  describe('валидная доска', () => {
    it('маленькая корректная доска 2x1 с реципрокными связями проходит без ошибок', () => {
      const result = validateBoardGeometry({
        width: 2,
        height: 1,
        cells: [
          { x: 0, y: 0, type: 'normal', zone: 'blue', connections: ['right'] },
          { x: 1, y: 0, type: 'normal', zone: 'blue', connections: ['left'] },
        ],
        features: { secretPassages: [], doors: [], highGround: [] },
      });

      expect(result.valid).toBe(true);
      expect(result.errors).toEqual([]);
    });

    it('доска без features также валидна', () => {
      const result = validateBoardGeometry({
        width: 1,
        height: 1,
        cells: [{ x: 0, y: 0, type: 'normal', zone: 'red', connections: [] }],
      });

      expect(result.valid).toBe(true);
      expect(result.errors).toEqual([]);
    });
  });

  describe('границы клеток', () => {
    it('помечает клетку с координатами вне [0,width) x [0,height)', () => {
      const result = validateBoardGeometry({
        width: 2,
        height: 2,
        cells: [
          { x: 0, y: 0, type: 'normal', zone: 'blue', connections: [] },
          { x: 5, y: 0, type: 'normal', zone: 'blue', connections: [] },
        ],
      });

      expect(result.valid).toBe(false);
      expect(result.errors.some((e) => /5/.test(e) && /bound/i.test(e))).toBe(true);
    });

    it('помечает отрицательную координату как вне границ', () => {
      const result = validateBoardGeometry({
        width: 2,
        height: 2,
        cells: [{ x: -1, y: 0, type: 'normal', zone: 'blue', connections: [] }],
      });

      expect(result.valid).toBe(false);
      expect(result.errors.some((e) => /bound/i.test(e))).toBe(true);
    });
  });

  describe('дубликаты клеток', () => {
    it('помечает две клетки с одинаковыми (x,y)', () => {
      const result = validateBoardGeometry({
        width: 2,
        height: 2,
        cells: [
          { x: 0, y: 0, type: 'normal', zone: 'blue', connections: [] },
          { x: 0, y: 0, type: 'normal', zone: 'red', connections: [] },
        ],
      });

      expect(result.valid).toBe(false);
      expect(result.errors.some((e) => /duplicate/i.test(e) && /0\s*,\s*0/.test(e))).toBe(true);
    });
  });

  describe('связи между клетками', () => {
    it('помечает асимметричную связь (A->right->B, но B не связан left->A)', () => {
      const result = validateBoardGeometry({
        width: 2,
        height: 1,
        cells: [
          { x: 0, y: 0, type: 'normal', zone: 'blue', connections: ['right'] },
          { x: 1, y: 0, type: 'normal', zone: 'blue', connections: [] },
        ],
      });

      expect(result.valid).toBe(false);
      expect(result.errors.some((e) => /asymmetric/i.test(e))).toBe(true);
    });

    it('помечает связь, указывающую на несуществующего соседа', () => {
      const result = validateBoardGeometry({
        width: 2,
        height: 1,
        cells: [
          // (1,0) не описана как клетка — сосед справа отсутствует
          { x: 0, y: 0, type: 'normal', zone: 'blue', connections: ['right'] },
        ],
      });

      expect(result.valid).toBe(false);
      expect(result.errors.some((e) => /neighbor|missing/i.test(e))).toBe(true);
    });

    it('помечает связь с неизвестным направлением', () => {
      const result = validateBoardGeometry({
        width: 1,
        height: 1,
        cells: [{ x: 0, y: 0, type: 'normal', zone: 'blue', connections: ['sideways'] }],
      });

      expect(result.valid).toBe(false);
      expect(result.errors.some((e) => /direction/i.test(e))).toBe(true);
    });
  });

  describe('зоны', () => {
    it('помечает неизвестную зону как предупреждение (warn:), но не делает доску невалидной', () => {
      const result = validateBoardGeometry({
        width: 1,
        height: 1,
        cells: [{ x: 0, y: 0, type: 'normal', zone: 'p1-start', connections: [] }],
      });

      expect(result.valid).toBe(true);
      expect(result.errors.some((e) => e.startsWith('warn:') && /p1-start/.test(e))).toBe(true);
    });

    it('принимает зону из массива zones', () => {
      const result = validateBoardGeometry({
        width: 1,
        height: 1,
        cells: [{ x: 0, y: 0, type: 'normal', zones: ['blue', 'green'], connections: [] }],
      });

      expect(result.valid).toBe(true);
      expect(result.errors).toEqual([]);
    });
  });

  describe('features', () => {
    it('помечает door, ссылающуюся на несуществующую клетку', () => {
      const result = validateBoardGeometry({
        width: 2,
        height: 1,
        cells: [
          { x: 0, y: 0, type: 'normal', zone: 'blue', connections: ['right'] },
          { x: 1, y: 0, type: 'normal', zone: 'blue', connections: ['left'] },
        ],
        features: {
          doors: [{ from: { x: 0, y: 0 }, to: { x: 9, y: 9 } }],
          secretPassages: [],
          highGround: [],
        },
      });

      expect(result.valid).toBe(false);
      expect(result.errors.some((e) => /door/i.test(e) && /9\s*,\s*9/.test(e))).toBe(true);
    });

    it('помечает secretPassage, ссылающийся на несуществующую клетку', () => {
      const result = validateBoardGeometry({
        width: 2,
        height: 1,
        cells: [
          { x: 0, y: 0, type: 'normal', zone: 'blue', connections: ['right'] },
          { x: 1, y: 0, type: 'normal', zone: 'blue', connections: ['left'] },
        ],
        features: {
          doors: [],
          secretPassages: [{ from: { x: 0, y: 0 }, to: { x: 7, y: 7 } }],
          highGround: [],
        },
      });

      expect(result.valid).toBe(false);
      expect(result.errors.some((e) => /passage/i.test(e) && /7\s*,\s*7/.test(e))).toBe(true);
    });
  });
});
