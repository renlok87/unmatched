/**
 * Guard (ENV-MAPS B1): манхэттенская смежность/дистанция живёт ТОЛЬКО в
 * engine/board-topology.ts. На топологических досках (оригинальные карты)
 * соседи — связи линиями, связь может перекрывать несколько шагов решётки,
 * а соседняя по решётке клетка без связи соседом не является, поэтому любое
 * «Math.abs(dx) + Math.abs(dy)» или «manhattan(...) === 1» в правилах —
 * ошибка. Новые правила обязаны звать board-topology (isAdjacent /
 * neighbours / boardDistance / graphDistance / distanceField).
 *
 * Сканируются все НЕ-spec .ts под backend/src (спеки держат копии прежних
 * реализаций как оракулы регрессии). Комментарии вырезаются перед поиском.
 *
 * ALLOW-LIST — каждое исключение с причиной и максимальным числом вхождений:
 */

import { readdirSync, readFileSync } from 'node:fs';
import { join, relative, resolve } from 'node:path';

const SRC = resolve(__dirname, '../..');

interface Rule {
  readonly id: string;
  readonly description: string;
  readonly pattern: RegExp;
  /** Ограничить правило префиксами путей (относительно backend/src) */
  readonly scope?: readonly string[];
}

/** Сумма двух Math.abs(...) — манхэттен «на месте» */
const MANHATTAN_SUM: Rule = {
  id: 'MANHATTAN_SUM',
  description: 'Math.abs(..) + Math.abs(..) (inline manhattan distance)',
  pattern: /Math\.abs\((?:[^()]|\([^()]*\))*\)\s*\+\s*Math\.abs\(/g,
};

/** Манхэттен-хелпер, сравниваемый с 1 — смежность по решётке */
const MANHATTAN_ADJACENCY: Rule = {
  id: 'MANHATTAN_ADJACENCY',
  description: 'manhattan/positionDistance/manhattanDistance(..) compared with 1 (grid adjacency)',
  pattern:
    /\b(?:manhattan|manhattanDistance|positionDistance)\s*\((?:[^()]|\([^()]*\))*\)\s*(?:===|!==|==|!=|<=|<|>=|>)\s*1\b/g,
};

/**
 * Таблица ортогональных смещений — «4 соседа сетки» — в РАНТАЙМ-правилах
 * (движок и игровые сервисы). Валидаторы контента (content/validators)
 * проверяют авторские направления connections up/down/left/right сеточных
 * досок — это не правило смежности движка, поэтому вне scope.
 */
const GRID_OFFSET_TABLE: Rule = {
  id: 'GRID_OFFSET_TABLE',
  description: '{ dx: 0|±1, dy: 0|±1 } neighbour offset literal (hard-coded grid neighbours)',
  pattern: /\{\s*dx:\s*-?[01]\s*,\s*dy:\s*-?[01]\b/g,
  scope: ['game-engine/', 'games/', 'game/'],
};

/** Литерал соседней позиции решётки: { x: p.x + 1, y: p.y } / { x, y: y - 1 } */
const GRID_NEIGHBOUR_LITERAL: Rule = {
  id: 'GRID_NEIGHBOUR_LITERAL',
  description: '{ x: <v> ± 1, y } / { x, y: <v> ± 1 } hard-coded grid neighbour position',
  pattern:
    /\{\s*x:\s*[\w.]+\s*[+-]\s*1\s*,\s*y\b|\{\s*x(?::\s*[\w.]+)?\s*,\s*y:\s*[\w.]+\s*[+-]\s*1\s*\}/g,
  scope: ['game-engine/', 'games/', 'game/'],
};

const RULES: readonly Rule[] = [
  MANHATTAN_SUM,
  MANHATTAN_ADJACENCY,
  GRID_OFFSET_TABLE,
  GRID_NEIGHBOUR_LITERAL,
];

/**
 * Исключения. Ключ — путь относительно backend/src (прямые слэши).
 * Значение — максимальное число вхождений по правилу и причина.
 */
const ALLOW: Record<
  string,
  { readonly max: Partial<Record<string, number>>; readonly reason: string }
> = {
  'game-engine/engine/board-topology.ts': {
    max: { MANHATTAN_SUM: 1, MANHATTAN_ADJACENCY: 1, GRID_OFFSET_TABLE: 12 },
    reason:
      'сам модуль топологии: определение манхэттена сетки, isAdjacent-фолбэк сетки ' +
      '(manhattan === 1) и таблицы ортогональных порядков NESW/NSEW/WENS',
  },
  'game-engine/engine/adjacency.service.ts': {
    max: { GRID_OFFSET_TABLE: 8 },
    reason:
      'легаси-таблица смещений С НАПРАВЛЕНИЯМИ (включая диагонали) для сеточной ветки ' +
      'getAdjacentCells; топологическая ветка идёт через board-topology.neighbours',
  },
  'game-engine/abilities/generic-hero-ability.handler.ts': {
    max: { MANHATTAN_ADJACENCY: 1 },
    reason:
      'areAdjacent: на сеточной доске сохраняет контракт deps.zone.manhattanDistance === 1 ' +
      '(стабы deps в тестах); топологическая доска проверяется раньше через board-topology',
  },
  'game/validators/game-rules.validator.ts': {
    max: { MANHATTAN_SUM: 2 },
    reason:
      'МЁРТВЫЙ код (проверено 2026-09-30): src/game/validators и src/game/index нигде не ' +
      'импортируются — модуль Nest подключает только src/game/jobs; боевой валидатор — ' +
      'game-engine/validators/game-rules.validator.ts',
  },
};

function listSources(dir: string): string[] {
  const out: string[] = [];
  for (const entry of readdirSync(dir, { withFileTypes: true })) {
    const full = join(dir, entry.name);
    if (entry.isDirectory()) {
      if (entry.name === 'node_modules') continue;
      out.push(...listSources(full));
    } else if (entry.isFile() && entry.name.endsWith('.ts') && !entry.name.endsWith('.spec.ts')) {
      out.push(full);
    }
  }
  return out;
}

/** Грубое вырезание комментариев (блоки и строчные, кроме «://» в URL) */
function stripComments(src: string): string {
  return src.replace(/\/\*[\s\S]*?\*\//g, '').replace(/(^|[^:\\])\/\/.*$/gm, '$1');
}

function countMatches(code: string, rule: Rule): number {
  return (code.match(new RegExp(rule.pattern.source, rule.pattern.flags)) ?? []).length;
}

describe('board-topology guard: no grid/manhattan adjacency outside the topology module', () => {
  const files = listSources(SRC).map((full) => ({
    rel: relative(SRC, full).split('\\').join('/'),
    code: stripComments(readFileSync(full, 'utf8')),
  }));

  it('scans the backend sources', () => {
    expect(files.length).toBeGreaterThan(50);
    expect(files.some((f) => f.rel === 'game-engine/engine/board-topology.ts')).toBe(true);
  });

  it('the rules detect what they are meant to detect', () => {
    expect(countMatches('Math.abs(a.x - b.x) + Math.abs(a.y - b.y)', MANHATTAN_SUM)).toBe(1);
    expect(countMatches('Math.abs(\n  p.x - q.x,\n) +\n  Math.abs(p.y - q.y)', MANHATTAN_SUM)).toBe(
      1,
    );
    expect(countMatches('this.manhattan(a.position, b.position) === 1', MANHATTAN_ADJACENCY)).toBe(
      1,
    );
    expect(countMatches('positionDistance(a, b) <= 1', MANHATTAN_ADJACENCY)).toBe(1);
    expect(countMatches('manhattanDistance(a, b) > 3', MANHATTAN_ADJACENCY)).toBe(0);
    expect(countMatches('[{ dx: 0, dy: -1 }, { dx: 1, dy: 0 }]', GRID_OFFSET_TABLE)).toBe(2);
    expect(countMatches('Math.abs(a.rating - b.rating)', MANHATTAN_SUM)).toBe(0);
    expect(
      countMatches('[{ x: pos.x + 1, y: pos.y }, { x, y: y - 1 }]', GRID_NEIGHBOUR_LITERAL),
    ).toBe(2);
    expect(countMatches('{ x: lastPosition.x, y: lastPosition.y }', GRID_NEIGHBOUR_LITERAL)).toBe(
      0,
    );
  });

  it.each(RULES.map((r) => [r.id, r] as const))('%s only in allow-listed files', (_id, rule) => {
    const violations: string[] = [];
    for (const { rel, code } of files) {
      if (rule.scope && !rule.scope.some((prefix) => rel.startsWith(prefix))) continue;
      const n = countMatches(code, rule);
      if (n === 0) continue;
      const allowed = ALLOW[rel]?.max[rule.id] ?? 0;
      if (n > allowed) {
        violations.push(`${rel}: ${n} × ${rule.description} (allowed ${allowed})`);
      }
    }
    expect(violations).toEqual([]);
  });

  it('every allow-list entry documents a reason', () => {
    for (const [file, entry] of Object.entries(ALLOW)) {
      expect(`${file}: ${entry.reason}`.length).toBeGreaterThan(file.length + 20);
    }
  });
});
