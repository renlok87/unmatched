/**
 * Board Topology — ЕДИНСТВЕННАЯ точка правил смежности/соседства/дистанции.
 *
 * Два режима доски (контракт ENV-MAPS, 2026-09-30):
 *  - «Топологическая» доска (оригинальные карты Marmoreal/Sarpedon): хотя бы
 *    одна клетка несёт массив `links`. Тогда соседи клетки — РОВНО её links
 *    (симметрично), связь может перекрывать несколько шагов решётки, а
 *    соседняя по решётке клетка БЕЗ связи соседом НЕ является. Пересечение
 *    линий без развилки (Marmoreal M22-M29 × M25-M26) — это просто два
 *    независимых ребра графа.
 *  - Сеточная доска (Cobble City и все прежние доски, links нет ни у одной
 *    клетки): прежние ортогональные соседи в границах доски и манхэттенская
 *    метрика — поведение бит-в-бит как до топологии.
 *
 * Правила BoL Vol.1: adjacent = соединены линией; melee — только adjacent;
 * ranged — adjacent ИЛИ общая зона (зоны — engine/adjacency.service
 * isInSameZone); «в пределах N пространств» — число переходов по линиям
 * (graph distance), бойцы при подсчёте дистанции не мешают.
 *
 * Модуль чистый (без Nest DI) и импортирует из models ТОЛЬКО типы, поэтому
 * его можно звать откуда угодно (models/fighter.model.positionDistance
 * делегирует сюда) без циклов модулей в рантайме.
 *
 * Guard-тест board-topology.guard.spec.ts запрещает манхэттенскую смежность
 * (сумма двух Math.abs, «distance === 1») вне этого модуля.
 */

import type { BoardState, Cell } from '../models/board.model';
import type { Position } from '../models/fighter.model';

/** Минимальный срез доски, нужный правилам топологии */
export type TopologyBoard = Pick<BoardState, 'width' | 'height' | 'cells'>;

/** Смещение ортогонального соседа сетки */
export interface GridOffset {
  readonly dx: number;
  readonly dy: number;
}

/** N, E, S, W — порядок A* / MovementService (обход по часовой) */
export const ORTHOGONAL_NESW: readonly GridOffset[] = [
  { dx: 0, dy: -1 },
  { dx: 1, dy: 0 },
  { dx: 0, dy: 1 },
  { dx: -1, dy: 0 },
];

/** N, S, E, W — исторический порядок AdjacencyService.getAdjacentCells */
export const ORTHOGONAL_NSEW: readonly GridOffset[] = [
  { dx: 0, dy: -1 },
  { dx: 0, dy: 1 },
  { dx: 1, dy: 0 },
  { dx: -1, dy: 0 },
];

/** W, E, N, S — исторический порядок Ms. Marvel getAvailableTurnStartPositions */
export const ORTHOGONAL_WENS: readonly GridOffset[] = [
  { dx: -1, dy: 0 },
  { dx: 1, dy: 0 },
  { dx: 0, dy: -1 },
  { dx: 0, dy: 1 },
];

/** Ключ позиции `x:y` (тот же формат, что cellKey/posKey по всему движку) */
export function posKey(p: Position): string {
  return `${p.x}:${p.y}`;
}

/**
 * Манхэттенская метрика решётки. Это метрика СЕТОЧНЫХ досок; на
 * топологических досках она ничего не значит — используйте boardDistance.
 */
export function manhattanDistance(a: Position, b: Position): number {
  return Math.abs(a.x - b.x) + Math.abs(a.y - b.y);
}

/** Позиция — целочисленная клетка внутри границ доски */
export function isInBounds(board: TopologyBoard | null | undefined, p: Position): boolean {
  if (!board) return false;
  if (!Number.isInteger(p.x) || !Number.isInteger(p.y)) return false;
  return p.x >= 0 && p.x < board.width && p.y >= 0 && p.y < board.height;
}

/** Ортогональные позиции вокруг pos в заданном порядке, БЕЗ проверки границ */
export function orthogonalPositions(
  pos: Position,
  order: readonly GridOffset[] = ORTHOGONAL_NESW,
): Position[] {
  return order.map(({ dx, dy }) => ({ x: pos.x + dx, y: pos.y + dy }));
}

// ---------------------------------------------------------------------------
// Индекс связей (кэш по ссылке на массив cells: BoardState иммутабелен)
// ---------------------------------------------------------------------------

type LinkIndex = ReadonlyMap<string, readonly Position[]>;

const linkIndexCache = new WeakMap<object, LinkIndex | null>();

/** Array.isArray без сужения до any[] (readonly-массивы из JSON-состояния) */
function isList<T>(v: readonly T[] | null | undefined): v is readonly T[] {
  return Array.isArray(v);
}

/**
 * Индекс связей доски или null для сеточной доски. Порядок соседей клетки:
 * сначала её собственные links в исходном порядке, затем (для симметрии)
 * обратные связи, объявленные только у соседа. Связи вне доски и петли
 * отбрасываются. Координаты клетки — индексы массива cells[y][x].
 */
function linkIndex(board: TopologyBoard | null | undefined): LinkIndex | null {
  const cells = board?.cells;
  if (!board || !Array.isArray(cells)) return null;
  const cached = linkIndexCache.get(cells);
  if (cached !== undefined) return cached;

  const adj = new Map<string, Position[]>();
  const add = (from: Position, to: Position): void => {
    const k = posKey(from);
    let list = adj.get(k);
    if (!list) {
      list = [];
      adj.set(k, list);
    }
    if (!list.some((p) => p.x === to.x && p.y === to.y)) list.push({ x: to.x, y: to.y });
  };
  const declared: Array<{ from: Position; to: Position }> = [];
  let hasLinks = false;

  // Данные доски приходят из JSON (БД/Redis/фикстуры) — проверяем форму в рантайме
  const rows: readonly (readonly (Cell | undefined)[] | undefined)[] = cells;
  for (let y = 0; y < rows.length; y++) {
    const row = rows[y];
    if (!isList(row)) continue;
    for (let x = 0; x < row.length; x++) {
      const links: readonly (Position | undefined)[] | undefined = row[x]?.links;
      if (!isList(links)) continue;
      hasLinks = true;
      for (const l of links) {
        if (!l || !isInBounds(board, l)) continue;
        if (l.x === x && l.y === y) continue;
        declared.push({ from: { x, y }, to: { x: l.x, y: l.y } });
      }
    }
  }

  let index: LinkIndex | null = null;
  if (hasLinks) {
    for (const { from, to } of declared) add(from, to); // собственный порядок
    for (const { from, to } of declared) add(to, from); // симметрия
    index = adj;
  }
  linkIndexCache.set(cells, index);
  return index;
}

/**
 * Доска имеет топологию ⟺ хотя бы одна клетка несёт массив links.
 * Иначе действуют прежние ортогональные правила сетки.
 */
export function hasTopology(board: TopologyBoard | null | undefined): boolean {
  return linkIndex(board) !== null;
}

/**
 * Соседи позиции.
 *  - топологическая доска: связанные клетки (links, симметрично); у клетки
 *    без связей соседей нет;
 *  - сеточная доска: ортогональные клетки в границах в порядке `order`;
 *  - доски нет: ортогональные позиции без проверки границ (легаси-вызовы,
 *    проходимость/границы проверяет вызывающий).
 * Проходимость клеток и бойцов здесь НЕ проверяется.
 */
export function neighbours(
  board: TopologyBoard | null | undefined,
  pos: Position,
  order: readonly GridOffset[] = ORTHOGONAL_NESW,
): Position[] {
  const index = linkIndex(board);
  if (index) {
    return (index.get(posKey(pos)) ?? []).map((p) => ({ x: p.x, y: p.y }));
  }
  const candidates = orthogonalPositions(pos, order);
  return board ? candidates.filter((p) => isInBounds(board, p)) : candidates;
}

/**
 * Смежность двух позиций: топология — есть связь; сетка/нет доски —
 * манхэттен === 1 (прежнее поведение). Позиция не смежна сама с собой.
 */
export function isAdjacent(
  board: TopologyBoard | null | undefined,
  a: Position,
  b: Position,
): boolean {
  const index = linkIndex(board);
  if (index) {
    return (index.get(posKey(a)) ?? []).some((p) => p.x === b.x && p.y === b.y);
  }
  return manhattanDistance(a, b) === 1;
}

export interface DistanceOptions {
  /** Можно ли ВОЙТИ в позицию (старт не проверяется). По умолчанию — любая. */
  readonly passable?: (pos: Position) => boolean;
  /** Не расширять BFS дальше этой дистанции */
  readonly maxDistance?: number;
}

/**
 * BFS-дистанции от `from` по графу соседей (neighbours): Map `x:y` → число
 * шагов, старт включён с 0. Работает на обоих типах досок; без доски —
 * только старт.
 */
export function distancesFrom(
  board: TopologyBoard | null | undefined,
  from: Position,
  options: DistanceOptions = {},
): Map<string, number> {
  const { passable, maxDistance = Infinity } = options;
  const dist = new Map<string, number>([[posKey(from), 0]]);
  // Без доски граница графа неизвестна (сетка была бы бесконечной) — только старт
  if (!board) return dist;
  const queue: Position[] = [from];
  for (let i = 0; i < queue.length; i++) {
    const current = queue[i];
    const d = dist.get(posKey(current)) ?? 0;
    if (d >= maxDistance) continue;
    for (const next of neighbours(board, current)) {
      const k = posKey(next);
      if (dist.has(k)) continue;
      if (passable && !passable(next)) continue;
      dist.set(k, d + 1);
      queue.push(next);
    }
  }
  return dist;
}

/**
 * Кратчайшая дистанция по графу соседей (BFS); Infinity — недостижимо.
 * `passable` ограничивает, в какие позиции можно входить (цель тоже).
 */
export function graphDistance(
  board: TopologyBoard | null | undefined,
  a: Position,
  b: Position,
  passable?: (pos: Position) => boolean,
): number {
  if (a.x === b.x && a.y === b.y) return 0;
  // Без доски: BFS по бесконечной сетке равен манхэттену (легаси-вызовы)
  if (!board) return passable ? Infinity : manhattanDistance(a, b);
  const field = distancesFrom(board, a, { passable });
  return field.get(posKey(b)) ?? Infinity;
}

/**
 * «Сколько пространств между» — метрика дальности карт/способностей
 * («attack up to 2 spaces», «move 1 space»): топология — graph distance по
 * линиям (бойцы не мешают подсчёту); сетка/нет доски — манхэттен (как было).
 */
export function boardDistance(
  board: TopologyBoard | null | undefined,
  a: Position,
  b: Position,
): number {
  return hasTopology(board) ? graphDistance(board, a, b) : manhattanDistance(a, b);
}

/** boardDistance(a, b) <= n */
export function isWithinDistance(
  board: TopologyBoard | null | undefined,
  a: Position,
  b: Position,
  n: number,
): boolean {
  return boardDistance(board, a, b) <= n;
}

/**
 * Поле дистанций до цели для многократных запросов (AI «ближе к врагу»,
 * эвристика A*): топология — один BFS от цели по статическому графу
 * (Infinity для недостижимых); сетка/нет доски — манхэттен до цели.
 * На топологии это допустимая и согласованная эвристика A* (бойцы и
 * блокировки только удлиняют реальный путь).
 */
export function distanceField(
  board: TopologyBoard | null | undefined,
  target: Position,
): (p: Position) => number {
  if (!hasTopology(board)) {
    return (p) => manhattanDistance(p, target);
  }
  const field = distancesFrom(board, target);
  return (p) => field.get(posKey(p)) ?? Infinity;
}
