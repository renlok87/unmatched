/**
 * Backfill Board.cells: доски каталога (импорт настоящих карт) пришли с cells=[],
 * а без клеток игра на доске не стартует (НД-2). Скрипт генерирует играбельные сетки:
 *   - размер: пиксели картинки (Board.width/height) масштабируются в сетку
 *     12 клеток по большей стороне;
 *   - зоны: 2-4 реальных zone-ключа из scraped-data/api/maps.json (матч по
 *     Board.name, fallback — features.mapKey), полосы вдоль большей стороны;
 *     доска без карты в maps.json пропускается (не настоящая карта —
 *     docs/game-design/decisions/2026-10-04-real-boards-only.md);
 *   - препятствия: цель 5-15% клеток, симметричные пары (180°), запрет рядом
 *     с углами и стартовыми позициями, после каждой пары — проверка 4-связности
 *     (та же метрика, что adjacency.service); при провале финальной проверки —
 *     доска без препятствий.
 *
 * Формат cells — ровно тот, что ест buildBoardState
 * (game-initialization.service.ts): плоский массив {x, y, isObstacle?: true,
 * zones: [key]} в grid-координатах. Board.width/height НЕ трогаем (пиксели
 * нужны фронту для картинки; buildBoardState выводит размер сетки сам).
 *
 * Генерация детерминированная (seed = хэш имени доски) — повторный прогон
 * с --force даёт ту же сетку.
 *
 * Идемпотентность: перезаписываются ТОЛЬКО доски с пустыми/отсутствующими
 * cells; --force перезаписывает все, кроме досок с топологией оригинальной
 * карты (ENV-MAPS: cells с links / features.topology) — они не трогаются никогда.
 *
 * Запуск: cd backend && npx ts-node --transpile-only prisma/backfill-board-cells.ts [--force]
 */
import { PrismaClient } from '@prisma/client';
import * as fs from 'fs';
import * as path from 'path';

const prisma = new PrismaClient();

const MAPS_PATH = path.join(__dirname, '../../scraped-data/api/maps.json');

/** Сетка: большая сторона 12 клеток (коридор buildBoardState 2..50 соблюдён) */
const TARGET_LONG_SIDE = 12;
/** Добивка зон, если у карты в maps.json меньше двух zone-ключей */
const DEFAULT_ZONE_KEYS = ['blue', 'red'];

// ---------- Парс maps.json (по образцу update-scraped-data.ts) ----------

function resolveValue(data: any[], index: number | null | undefined): any {
  if (index === null || index === undefined || index < 0) return null;
  return data[index];
}

function loadDataArray(filePath: string): any[] | null {
  if (!fs.existsSync(filePath)) return null;
  try {
    const parsed = JSON.parse(fs.readFileSync(filePath, 'utf-8'));
    const nodes = parsed.nodes;
    if (!nodes || nodes.length < 3 || !nodes[2] || !nodes[2].data) return null;
    return nodes[2].data as any[];
  } catch {
    return null;
  }
}

interface MapInfo {
  name: string;
  key: string;
  zonesCount: number | null;
  zoneKeys: string[];
}

function loadMaps(): MapInfo[] {
  const data = loadDataArray(MAPS_PATH);
  if (!data) return [];

  const mapIndices = data[1];
  if (!Array.isArray(mapIndices)) return [];

  const maps: MapInfo[] = [];
  for (const mapIndex of mapIndices) {
    const mapData = data[mapIndex];
    if (!mapData || typeof mapData !== 'object') continue;

    const name = resolveValue(data, mapData.name);
    if (!name || typeof name !== 'string') continue;
    const key = resolveValue(data, mapData.key);

    const zoneKeys: string[] = [];
    const zonesArr = resolveValue(data, mapData.zones);
    if (Array.isArray(zonesArr)) {
      for (const zi of zonesArr) {
        const zone = resolveValue(data, zi);
        const zoneKey = resolveValue(data, zone?.key);
        if (zoneKey && typeof zoneKey === 'string') zoneKeys.push(zoneKey);
      }
    }

    const zonesCountRaw = resolveValue(data, mapData.zonesCount);
    maps.push({
      name,
      key: typeof key === 'string' ? key : '',
      zonesCount: Number.isInteger(zonesCountRaw) ? zonesCountRaw : null,
      zoneKeys,
    });
  }
  return maps;
}

// ---------- Толерантный парс существующих cells (как parseBoardCells) ----------

function tryParse(value: string): unknown {
  try {
    return JSON.parse(value);
  } catch {
    return value;
  }
}

function parseCellsTolerant(raw: unknown): unknown[] {
  if (!raw) return [];
  let value: unknown = raw;
  if (typeof value === 'string') value = tryParse(value);
  // Двойная сериализация import-content: после первого parse снова строка
  if (typeof value === 'string') value = tryParse(value);
  return Array.isArray(value) ? value : [];
}

/**
 * ENV-MAPS: доска с топологией оригинальной карты (граф клеток со связями —
 * хоть одна клетка несёт массив `links`, или features.topology === true от
 * seed-env-map-boards.ts). Сгенерированная сетка стёрла бы граф, поэтому такие
 * доски не перезаписываются никогда, даже с --force.
 */
export function isTopologyBoard(board: { cells: unknown; features: unknown }): boolean {
  const features = (board.features ?? {}) as Record<string, unknown>;
  if (features.topology === true) return true;
  return parseCellsTolerant(board.cells).some(
    (cell) =>
      cell !== null &&
      typeof cell === 'object' &&
      Array.isArray((cell as { links?: unknown }).links),
  );
}

// ---------- Детерминированный PRNG ----------

/** FNV-1a хэш строки → 32-битный seed */
function hashString(s: string): number {
  let h = 0x811c9dc5;
  for (let i = 0; i < s.length; i++) {
    h ^= s.charCodeAt(i);
    h = Math.imul(h, 0x01000193);
  }
  return h >>> 0;
}

function mulberry32(seed: number): () => number {
  let a = seed >>> 0;
  return () => {
    a |= 0;
    a = (a + 0x6d2b79f5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

// ---------- Генерация сетки ----------

interface GeneratedCell {
  x: number;
  y: number;
  isObstacle?: true;
  zones: string[];
}

function clamp(v: number, min: number, max: number): number {
  return Math.max(min, Math.min(max, v));
}

/** Размер сетки из размеров доски (пиксели → ~12 по большей стороне) */
function computeGridSize(width: number, height: number): { gw: number; gh: number } {
  if (width >= height) {
    return { gw: TARGET_LONG_SIDE, gh: clamp(Math.round((TARGET_LONG_SIDE * height) / width), 2, 50) };
  }
  return { gw: clamp(Math.round((TARGET_LONG_SIDE * width) / height), 2, 50), gh: TARGET_LONG_SIDE };
}

/** 4-связность по непрепятствиям (метрика adjacency.service): все проходимые достижимы? */
function isConnected(obstacles: boolean[][], gw: number, gh: number): boolean {
  let passable = 0;
  let start: { x: number; y: number } | null = null;
  for (let y = 0; y < gh; y++) {
    for (let x = 0; x < gw; x++) {
      if (!obstacles[y][x]) {
        passable++;
        if (!start) start = { x, y };
      }
    }
  }
  if (!start) return false;

  const visited = new Set<string>([`${start.x}:${start.y}`]);
  const queue = [start];
  while (queue.length > 0) {
    const { x, y } = queue.shift()!;
    for (const [dx, dy] of [[1, 0], [-1, 0], [0, 1], [0, -1]] as const) {
      const nx = x + dx;
      const ny = y + dy;
      if (nx < 0 || ny < 0 || nx >= gw || ny >= gh) continue;
      if (obstacles[ny][nx] || visited.has(`${nx}:${ny}`)) continue;
      visited.add(`${nx}:${ny}`);
      queue.push({ x: nx, y: ny });
    }
  }
  return visited.size === passable;
}

/**
 * Клетки, где препятствия запрещены: manhattan < 3 от углов + стартовые
 * позиции computeStartPositions (углы с отступом 2) с окрестностью Чебышёва 1
 * (покрывает все SIDEKICK_OFFSETS).
 */
function buildProtectedSet(gw: number, gh: number): Set<string> {
  const protectedCells = new Set<string>();
  const corners = [
    { x: 0, y: 0 },
    { x: gw - 1, y: 0 },
    { x: 0, y: gh - 1 },
    { x: gw - 1, y: gh - 1 },
  ];
  for (let y = 0; y < gh; y++) {
    for (let x = 0; x < gw; x++) {
      if (corners.some((c) => Math.abs(c.x - x) + Math.abs(c.y - y) < 3)) {
        protectedCells.add(`${x}:${y}`);
      }
    }
  }
  // Стартовые позиции — та же формула, что computeStartPositions
  const starts = [
    { x: 2, y: 2 },
    { x: gw - 3, y: gh - 3 },
    { x: gw - 3, y: 2 },
    { x: 2, y: gh - 3 },
  ].map((p) => ({ x: clamp(p.x, 0, gw - 1), y: clamp(p.y, 0, gh - 1) }));
  for (const s of starts) {
    for (let dy = -1; dy <= 1; dy++) {
      for (let dx = -1; dx <= 1; dx++) {
        const x = s.x + dx;
        const y = s.y + dy;
        if (x >= 0 && y >= 0 && x < gw && y < gh) protectedCells.add(`${x}:${y}`);
      }
    }
  }
  return protectedCells;
}

function generateCells(
  boardName: string,
  width: number,
  height: number,
  zoneKeys: string[],
  zonesCount: number | null,
): { cells: GeneratedCell[]; gw: number; gh: number; obstacleCount: number } {
  const { gw, gh } = computeGridSize(width, height);
  const rng = mulberry32(hashString(boardName));

  // --- Зоны: 2-4 реальных ключа, полосы вдоль большей стороны ---
  const zoneCount = clamp(zonesCount ?? 3, 2, Math.min(4, Math.max(2, zoneKeys.length)));
  const keys = zoneKeys.slice(0, zoneCount);
  while (keys.length < zoneCount) keys.push(DEFAULT_ZONE_KEYS[keys.length % DEFAULT_ZONE_KEYS.length]);
  const zoneAt = (x: number, y: number): string => {
    const idx =
      gw >= gh
        ? Math.floor((x * keys.length) / gw)
        : Math.floor((y * keys.length) / gh);
    return keys[clamp(idx, 0, keys.length - 1)];
  };

  // --- Препятствия: симметричные пары, связность после каждой пары ---
  const obstacles: boolean[][] = Array.from({ length: gh }, () => Array(gw).fill(false));
  const protectedCells = buildProtectedSet(gw, gh);
  const total = gw * gh;
  const targetShare = 0.05 + rng() * 0.1; // 5-15%
  const target = Math.round(total * targetShare);

  let placed = 0;
  let attempts = 0;
  while (placed < target && attempts < 500) {
    attempts++;
    const x = Math.floor(rng() * gw);
    const y = Math.floor(rng() * gh);
    const mx = gw - 1 - x;
    const my = gh - 1 - y;
    if (protectedCells.has(`${x}:${y}`) || protectedCells.has(`${mx}:${my}`)) continue;
    if (obstacles[y][x] || obstacles[my][mx]) continue;

    obstacles[y][x] = true;
    obstacles[my][mx] = true;
    const pairSize = x === mx && y === my ? 1 : 2;
    if (!isConnected(obstacles, gw, gh)) {
      // Пара рвёт связность — откат
      obstacles[y][x] = false;
      obstacles[my][mx] = false;
      continue;
    }
    placed += pairSize;
  }

  // Финальный assert связности (не должен сработать — проверяем каждую пару)
  if (!isConnected(obstacles, gw, gh)) {
    console.warn(`   ⚠️  ${boardName}: финальная сетка несвязна — пишу без препятствий`);
    for (const row of obstacles) row.fill(false);
    placed = 0;
  }

  const cells: GeneratedCell[] = [];
  for (let y = 0; y < gh; y++) {
    for (let x = 0; x < gw; x++) {
      const cell: GeneratedCell = { x, y, zones: [zoneAt(x, y)] };
      if (obstacles[y][x]) cell.isObstacle = true;
      cells.push(cell);
    }
  }
  return { cells, gw, gh, obstacleCount: placed };
}

// ---------- Main ----------

async function main() {
  const force = process.argv.includes('--force');
  console.log(`🗺️  Backfill Board.cells${force ? ' (--force: перезапись всех)' : ''}...`);

  const maps = loadMaps();
  console.log(`   maps.json: ${maps.length} карт`);
  const byName = new Map(maps.map((m) => [m.name, m]));
  const byKey = new Map(maps.filter((m) => m.key).map((m) => [m.key, m]));

  const boards = await prisma.board.findMany({ orderBy: { name: 'asc' } });

  let updated = 0;
  let skippedNonEmpty = 0;
  let skippedTopology = 0;
  let noMapping = 0;

  for (const board of boards) {
    if (isTopologyBoard(board)) {
      skippedTopology++;
      console.log(
        `   ⏭️  ${board.name}: топология оригинальной карты (links) — пропуск${force ? ' даже с --force' : ''}`,
      );
      continue;
    }
    const existing = parseCellsTolerant(board.cells);
    if (existing.length > 0 && !force) {
      skippedNonEmpty++;
      continue;
    }

    // Матч с maps.json: по имени, fallback — features.mapKey
    const features = (board.features ?? {}) as Record<string, unknown>;
    const mapKey = typeof features.mapKey === 'string' ? features.mapKey : '';
    const map = byName.get(board.name) ?? (mapKey ? byKey.get(mapKey) : undefined);
    if (!map) {
      // Не карта из игры — сетку не выдумываем
      noMapping++;
      console.log(`   ⏭️  ${board.name}: нет в maps.json — пропуск`);
      continue;
    }

    const { cells, gw, gh, obstacleCount } = generateCells(
      board.name,
      board.width,
      board.height,
      map.zoneKeys?.length ? map.zoneKeys : DEFAULT_ZONE_KEYS,
      map.zonesCount ?? 3,
    );

    await prisma.board.update({
      where: { id: board.id },
      data: { cells: cells as unknown as object },
    });
    updated++;
    console.log(
      `   ✅ ${board.name}: ${gw}×${gh} (${cells.length} клеток, препятствий ${obstacleCount} = ${Math.round((obstacleCount / cells.length) * 100)}%)`,
    );
  }

  console.log(`\n📊 Итог: обновлено ${updated}, пропущено (cells непустые) ${skippedNonEmpty}, пропущено (топология) ${skippedTopology}, пропущено (нет в maps.json) ${noMapping}, всего досок ${boards.length}`);
}

// Specs import isTopologyBoard without running the backfill.
if (require.main === module) {
  main()
    .catch((e) => {
      console.error('❌ Backfill error:', e);
      process.exit(1);
    })
    .finally(async () => {
      await prisma.$disconnect();
    });
}
