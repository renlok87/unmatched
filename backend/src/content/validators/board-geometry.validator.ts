/**
 * Board Geometry Validator
 *
 * Чистая (pure) функция валидации геометрии доски. Никаких NestJS-зависимостей,
 * никакого доступа к БД — только проверка структуры входного JSON, который админ
 * вводит в admin/src/pages/boards/create.tsx:
 *
 *   cells:    [{ x, y, type, zone?, zones?, connections?: ['right','down',...] }]
 *   features: { secretPassages?, doors?, highGround? }
 *
 * Connections — это строки-направления ('up' | 'down' | 'left' | 'right'),
 * указывающие на соседнюю клетку. Реципрокность: если A связана 'right' с B,
 * то B обязана быть связана 'left' с A.
 *
 * ENV-MAPS (контракт unmatched.board-topology/1): клетка оригинальной карты
 * несёт links — позиции решётки связанных пространств ({x, y}, связь может
 * перекрывать несколько шагов решётки). Если links есть хотя бы у одной
 * клетки, соседи клетки в движке — РОВНО её links, поэтому они проверяются
 * жёстко: целые координаты, существующая проходимая клетка-цель, без петель
 * и повторов, симметричность, у непроходимой клетки связей нет.
 *
 * Возвращает список человекочитаемых строк ошибок. Предупреждения (мягкие
 * замечания, не делающие доску невалидной) имеют префикс "warn:".
 */

/** Каноничные зоны доски (Zone enum из content/interfaces + src/core). */
const ALLOWED_ZONES: ReadonlySet<string> = new Set([
  'blue',
  'green',
  'yellow',
  'red',
  'purple',
  // ENV-MAPS: violet — своя зона (Marmoreal: violet ≠ purple), не синоним
  'violet',
  'brown',
  'gray',
  'orange',
  'pink',
  'white',
  'gold',
  'beige',
]);

/** Допустимые направления связи и их обратные (для проверки реципрокности). */
const OPPOSITE_DIRECTION: Readonly<Record<string, string>> = {
  up: 'down',
  down: 'up',
  left: 'right',
  right: 'left',
};

/** Смещение (dx, dy) для каждого направления. y растёт вниз (down). */
const DIRECTION_DELTA: Readonly<Record<string, { dx: number; dy: number }>> = {
  up: { dx: 0, dy: -1 },
  down: { dx: 0, dy: 1 },
  left: { dx: -1, dy: 0 },
  right: { dx: 1, dy: 0 },
};

export interface BoardGeometryCellInput {
  x: number;
  y: number;
  type?: string;
  zone?: string;
  zones?: string[];
  connections?: string[];
  isObstacle?: boolean;
  /** ENV-MAPS: позиции решётки связанных клеток (топология оригинальной карты) */
  links?: BoardGeometryPositionRef[];
  [key: string]: unknown;
}

export interface BoardGeometryPositionRef {
  x: number;
  y: number;
}

export interface BoardGeometryLinkRef {
  from?: BoardGeometryPositionRef;
  to?: BoardGeometryPositionRef;
  [key: string]: unknown;
}

export interface BoardGeometryFeaturesInput {
  secretPassages?: BoardGeometryLinkRef[];
  doors?: BoardGeometryLinkRef[];
  highGround?: BoardGeometryPositionRef[];
  [key: string]: unknown;
}

export interface BoardGeometryInput {
  width: number;
  height: number;
  cells: BoardGeometryCellInput[];
  features?: BoardGeometryFeaturesInput;
}

export interface BoardGeometryValidationResult {
  valid: boolean;
  errors: string[];
}

function key(x: number, y: number): string {
  return `${x},${y}`;
}

function isInteger(n: unknown): n is number {
  return typeof n === 'number' && Number.isInteger(n);
}

function cellZones(cell: BoardGeometryCellInput): string[] {
  if (Array.isArray(cell.zones) && cell.zones.length > 0) return cell.zones;
  if (cell.zone != null) return [cell.zone];
  return [];
}

/**
 * Проверяет геометрию доски. Чистая функция: один вход → детерминированный выход.
 */
export function validateBoardGeometry(
  input: BoardGeometryInput,
): BoardGeometryValidationResult {
  const errors: string[] = [];

  const width = input?.width;
  const height = input?.height;
  const cells = Array.isArray(input?.cells) ? input.cells : [];

  if (!isInteger(width) || width <= 0) {
    errors.push(`Board width must be a positive integer (got ${String(width)}).`);
  }
  if (!isInteger(height) || height <= 0) {
    errors.push(`Board height must be a positive integer (got ${String(height)}).`);
  }
  if (!Array.isArray(input?.cells)) {
    errors.push('Board cells must be an array.');
  }

  const safeWidth = isInteger(width) ? width : Number.POSITIVE_INFINITY;
  const safeHeight = isInteger(height) ? height : Number.POSITIVE_INFINITY;

  // Индекс существующих клеток + детект дубликатов + границ.
  const cellIndex = new Map<string, BoardGeometryCellInput>();
  cells.forEach((cell, i) => {
    if (!isInteger(cell?.x) || !isInteger(cell?.y)) {
      errors.push(`Cell #${i} has non-integer coordinates (x=${String(cell?.x)}, y=${String(cell?.y)}).`);
      return;
    }

    const inBounds =
      cell.x >= 0 && cell.x < safeWidth && cell.y >= 0 && cell.y < safeHeight;
    if (!inBounds) {
      errors.push(
        `Cell (${cell.x},${cell.y}) is out of bounds; must be within [0,${String(width)}) x [0,${String(height)}).`,
      );
    }

    const k = key(cell.x, cell.y);
    if (cellIndex.has(k)) {
      errors.push(`Duplicate cell at (${cell.x},${cell.y}).`);
    } else {
      cellIndex.set(k, cell);
    }

    // Зоны: неизвестные — предупреждение (warn:), пустые строки — ошибка.
    for (const z of cellZones(cell)) {
      if (typeof z !== 'string' || z.trim() === '') {
        errors.push(`Cell (${cell.x},${cell.y}) has an empty zone value.`);
      } else if (!ALLOWED_ZONES.has(z)) {
        errors.push(`warn: Cell (${cell.x},${cell.y}) uses unknown zone "${z}".`);
      }
    }
  });

  // Связи: валидность направления, существование соседа, реципрокность.
  for (const cell of cellIndex.values()) {
    const connections = Array.isArray(cell.connections) ? cell.connections : [];
    for (const dir of connections) {
      if (typeof dir !== 'string' || !(dir in DIRECTION_DELTA)) {
        errors.push(
          `Cell (${cell.x},${cell.y}) has invalid connection direction "${String(dir)}".`,
        );
        continue;
      }

      const { dx, dy } = DIRECTION_DELTA[dir];
      const nx = cell.x + dx;
      const ny = cell.y + dy;
      const neighbor = cellIndex.get(key(nx, ny));

      if (!neighbor) {
        errors.push(
          `Cell (${cell.x},${cell.y}) connection "${dir}" points to a missing neighbor cell (${nx},${ny}).`,
        );
        continue;
      }

      // Реципрокность: сосед должен иметь обратную связь.
      const back = OPPOSITE_DIRECTION[dir];
      const neighborConnections = Array.isArray(neighbor.connections)
        ? neighbor.connections
        : [];
      if (!neighborConnections.includes(back)) {
        errors.push(
          `Asymmetric connection: cell (${cell.x},${cell.y}) connects "${dir}" to (${nx},${ny}), but (${nx},${ny}) is missing the reciprocal "${back}" connection.`,
        );
      }
    }
  }

  validateTopologyLinks(cellIndex, errors);

  // Features: doors / secretPassages / highGround должны ссылаться на клетки.
  const features = input?.features;
  if (features && typeof features === 'object') {
    validateLinkRefs(features.doors, 'door', cellIndex, errors);
    validateLinkRefs(features.secretPassages, 'secretPassage', cellIndex, errors);
    validatePositionRefs(features.highGround, 'highGround', cellIndex, errors);
  }

  // Доска невалидна только при наличии "жёстких" ошибок (без префикса warn:).
  const hardErrors = errors.filter((e) => !e.startsWith('warn:'));

  return { valid: hardErrors.length === 0, errors };
}

function isBlockedCell(cell: BoardGeometryCellInput): boolean {
  return cell.isObstacle === true || cell.type === 'obstacle' || cell.type === 'wall';
}

/**
 * ENV-MAPS: связи топологической доски (cells[].links). Жёсткие ошибки:
 * не массив / не целые координаты / цель не существует / петля / повтор /
 * связь у непроходимой клетки или в непроходимую клетку / асимметрия.
 */
function validateTopologyLinks(
  cellIndex: Map<string, BoardGeometryCellInput>,
  errors: string[],
): void {
  for (const cell of cellIndex.values()) {
    if (cell.links === undefined) continue;
    const at = `(${cell.x},${cell.y})`;
    if (!Array.isArray(cell.links)) {
      errors.push(`Cell ${at} links must be an array of {x, y} positions.`);
      continue;
    }
    if (cell.links.length > 0 && isBlockedCell(cell)) {
      errors.push(`Obstacle cell ${at} must not carry links.`);
    }
    const seen = new Set<string>();
    cell.links.forEach((link, i) => {
      if (!isInteger(link?.x) || !isInteger(link?.y)) {
        errors.push(`Cell ${at} link #${i} has non-integer coordinates.`);
        return;
      }
      const k = key(link.x, link.y);
      if (link.x === cell.x && link.y === cell.y) {
        errors.push(`Cell ${at} links to itself.`);
        return;
      }
      if (seen.has(k)) {
        errors.push(`Cell ${at} has a duplicate link to (${link.x},${link.y}).`);
        return;
      }
      seen.add(k);
      const target = cellIndex.get(k);
      if (!target) {
        errors.push(`Cell ${at} links to a missing cell (${link.x},${link.y}).`);
        return;
      }
      if (isBlockedCell(target)) {
        errors.push(`Cell ${at} links to an obstacle cell (${link.x},${link.y}).`);
        return;
      }
      const back = Array.isArray(target.links) ? target.links : [];
      if (!back.some((b) => b?.x === cell.x && b?.y === cell.y)) {
        errors.push(
          `Asymmetric link: cell ${at} links to (${link.x},${link.y}), but (${link.x},${link.y}) does not link back.`,
        );
      }
    });
  }
}

function validateLinkRefs(
  refs: BoardGeometryLinkRef[] | undefined,
  label: string,
  cellIndex: Map<string, BoardGeometryCellInput>,
  errors: string[],
): void {
  if (!Array.isArray(refs)) return;
  refs.forEach((ref, i) => {
    for (const side of ['from', 'to'] as const) {
      const pos = ref?.[side];
      if (pos == null) continue; // отсутствие стороны не проверяем здесь
      if (!isInteger(pos.x) || !isInteger(pos.y)) {
        errors.push(`${label} #${i} has non-integer ${side} coordinates.`);
        continue;
      }
      if (!cellIndex.has(key(pos.x, pos.y))) {
        errors.push(
          `${label} #${i} references a non-existent cell at (${pos.x},${pos.y}).`,
        );
      }
    }
  });
}

function validatePositionRefs(
  refs: BoardGeometryPositionRef[] | undefined,
  label: string,
  cellIndex: Map<string, BoardGeometryCellInput>,
  errors: string[],
): void {
  if (!Array.isArray(refs)) return;
  refs.forEach((pos, i) => {
    if (!isInteger(pos?.x) || !isInteger(pos?.y)) {
      errors.push(`${label} #${i} has non-integer coordinates.`);
      return;
    }
    if (!cellIndex.has(key(pos.x, pos.y))) {
      errors.push(
        `${label} #${i} references a non-existent cell at (${pos.x},${pos.y}).`,
      );
    }
  });
}
