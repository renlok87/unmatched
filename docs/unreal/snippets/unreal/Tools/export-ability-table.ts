#!/usr/bin/env -S npx tsx
/**
 * unreal/Tools/export-ability-table.ts — экспорт дальностей атаки, стоек и постоянных боевых
 * модификаторов героев из бэкенда в DataTable-совместимые CSV/JSON (ADR §3.7, §4.3, §4.8
 * «Unmatched.Model.AttackRangeSync», предпосылка B12).
 *
 * Зачем: `attackRange`/стоечные модификаторы через GraphQL НЕ экспортируются (R4 §3.6, ADR §1.3 п.12) —
 * экспортируется только `heroStances(heroSlug)` (id/label/isDefault, без attackRange). Клиенту для
 * подсветки целей нужна таблица `DT_AttackRange` (FUmAttackRangeRow { HeroSlug, StanceId, Range } —
 * ADR §4.3); истина — сервер, таблица — «советчик».
 *
 * Источники (реальные пути):
 *   - `backend/src/game-engine/abilities/ability-config.ts` — `ABILITY_CONFIGS` (data-driven, файл без
 *     импортов → безопасно импортируется tsx): `attackRange?` (:413), `stances[].attackRange?` (:378),
 *     `stances[].combat?` (:380-383), правила `combat-passive` с `combat-modifier` (`whenStance`, :359).
 *     Семантика дальности — `GenericHeroAbilityHandler.canAttackAtRange`
 *     (`generic-hero-ability.handler.ts:635-645`): effectiveRange = stance.attackRange ?? config.attackRange.
 *   - `backend/src/game-engine/abilities/heroes/ms-marvel.handler.ts:22` — ручной хендлер,
 *     `const MS_MARVEL_EXTENDED_RANGE = 2` (не экспортируется, файл тянет @nestjs/common → читаем regex-ом).
 *   - `backend/src/game-engine/abilities/heroes/arthur.handler.ts:23,30` — `heroId: 'king-arthur'`,
 *     `allowsAttackBoost: true` (для FUmRules::BoostAllowed, ADR §4.3) — тоже regex-ом.
 *   - `backend/src/game-engine/models/fighter.model.ts:80-85` — `slugifyHeroName` (без импортов):
 *     проверяем, что `heroId` конфигов уже являются слагами.
 *
 * Выход (каталог `unreal/Import/`, в git не отслеживается — ADR §3.7):
 *   - `ability-table.json`   — полный снимок (для спеки AttackRangeSync и CI `npm run ability:check`);
 *   - `DT_AttackRange.csv`   — Name,HeroSlug,StanceId,Range (FUmAttackRangeRow, ADR §4.3);
 *   - `DT_HeroStances.csv`   — Name,HeroSlug,StanceId,Label,bIsDefault,AttackRange
 *                              (строка FUmHeroStanceRow — уточнение к ADR: в UmTableRows.h не перечислена,
 *                              ADR §3.7 требует файл; используется UUmContentSubsystem::GetStances как офлайн-кэш);
 *   - `DT_HeroCombatMods.csv` — Name,HeroSlug,StanceId,Condition,AppliesTo,Value,Kind
 *                              (FUmHeroCombatModRow, v1 — ADR §4.3; состав колонок — уточнение к ADR).
 *
 * Использование (из unreal/Tools, tsx из package.json):
 *   npx tsx export-ability-table.ts                       # экспорт в ../Import
 *   npx tsx export-ability-table.ts --check               # exit 1, если ability-table.json устарел
 *   npx tsx export-ability-table.ts --backend <path> --out <dir>
 *
 * Формат CSV DataTable: первая колонка — имя строки (любой заголовок), остальные — имена UPROPERTY
 * строки; булевы — `true/false`; импорт — `DataTableTools` MCP или Editor → Reimport (ADR §5.1).
 */

import fs from 'node:fs';
import path from 'node:path';
import process from 'node:process';
import crypto from 'node:crypto';
import { fileURLToPath, pathToFileURL } from 'node:url';

// Типы конфигов — только для проверки типов; в рантайме модуль импортируется динамически по пути.
import type { AbilityConfig, AbilityRule, StanceConfig } from '../../backend/src/game-engine/abilities/ability-config';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const UNREAL_ROOT = path.resolve(__dirname, '..');

interface Args {
  backend: string;
  out: string;
  check: boolean;
}

function parseArgs(argv: string[]): Args {
  const args: Args = {
    backend: path.resolve(UNREAL_ROOT, '..', 'backend'),
    out: path.join(UNREAL_ROOT, 'Import'),
    check: false,
  };
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i];
    if (a === '--backend') args.backend = path.resolve(argv[++i]);
    else if (a === '--out') args.out = path.resolve(argv[++i]);
    else if (a === '--check') args.check = true;
    else if (a === '-h' || a === '--help') {
      console.log('npx tsx export-ability-table.ts [--backend <dir>] [--out <dir>] [--check]');
      process.exit(0);
    } else {
      console.error(`Неизвестный аргумент: ${a}`);
      process.exit(2);
    }
  }
  return args;
}

// ----------------------------------------------------------------------------
// Модель снимка
// ----------------------------------------------------------------------------

interface StanceRow {
  id: string;
  label: string;
  isDefault: boolean;
  attackRange: number | null;
  combat: { appliesTo: 'attack' | 'defense' | 'both'; value: number } | null;
}

interface CombatModRow {
  stanceId: string | null; // whenStance | стойка со встроенным combat | null
  condition: string;       // 'always' | 'attacking' | … | 'handSizeEquals:N' | 'stance' (для stance.combat)
  appliesTo: 'attack' | 'defense' | 'both';
  value: number;           // для per-count — valuePer
  kind: 'combat-modifier' | 'combat-modifier-per-count' | 'aura-combat-modifier' | 'stance-combat';
  countOf?: string;
  scope?: string;
}

interface HeroRow {
  heroSlug: string;
  abilityName: string;
  attackRange: number | null;
  defaultStanceId: string | null;
  stances: StanceRow[];
  combatModifiers: CombatModRow[];
  triggers: string[];
  source: 'ability-config' | 'manual-handler';
}

interface AbilityTable {
  schemaVersion: 1;
  sources: Record<string, { path: string; sha256: string }>;
  heroes: HeroRow[];
  /** Ручные хендлеры (не в ABILITY_CONFIGS) — данные извлечены regex-ом из исходников. */
  manual: {
    msMarvelExtendedRange: number | null;
    kingArthurAllowsAttackBoost: boolean | null;
  };
  /** Итоговая таблица дальностей: heroSlug × stanceId → range (то, что уходит в DT_AttackRange). */
  attackRanges: Array<{ heroSlug: string; stanceId: string; range: number }>;
}

function conditionToString(rule: AbilityRule): string {
  const c = rule.condition ?? 'always';
  if (typeof c === 'string') return c;
  if ('handSizeEquals' in c) return `handSizeEquals:${c.handSizeEquals}`;
  return JSON.stringify(c);
}

function defaultStance(stances: readonly StanceConfig[] | undefined): StanceConfig | undefined {
  if (!stances || stances.length === 0) return undefined;
  // generic-hero-ability.handler.ts:100-111 — стойка с default:true, иначе первая (R4 §2.13).
  return stances.find((s) => s.default) ?? stances[0];
}

function buildHeroRow(cfg: AbilityConfig, slugify: (s: string) => string): HeroRow {
  if (slugify(cfg.heroId) !== cfg.heroId) {
    throw new Error(`heroId «${cfg.heroId}» не является слагом (slugifyHeroName даёт «${slugify(cfg.heroId)}»)`);
  }
  const def = defaultStance(cfg.stances);
  const stances: StanceRow[] = (cfg.stances ?? []).map((s) => ({
    id: s.id,
    label: s.label,
    isDefault: def?.id === s.id,
    attackRange: s.attackRange ?? null,
    combat: s.combat ? { appliesTo: s.combat.appliesTo, value: s.combat.value } : null,
  }));

  const combatModifiers: CombatModRow[] = [];
  for (const rule of cfg.rules) {
    if (rule.trigger !== 'combat-passive') continue;
    const e = rule.effect;
    if (e.kind === 'combat-modifier') {
      combatModifiers.push({ stanceId: rule.whenStance ?? null, condition: conditionToString(rule), appliesTo: e.appliesTo, value: e.value, kind: e.kind });
    } else if (e.kind === 'combat-modifier-per-count') {
      combatModifiers.push({ stanceId: rule.whenStance ?? null, condition: conditionToString(rule), appliesTo: e.appliesTo, value: e.valuePer, kind: e.kind, countOf: e.countOf });
    } else if (e.kind === 'aura-combat-modifier') {
      combatModifiers.push({ stanceId: rule.whenStance ?? null, condition: conditionToString(rule), appliesTo: e.appliesTo, value: e.value, kind: e.kind, scope: e.scope });
    }
  }
  for (const s of cfg.stances ?? []) {
    if (s.combat) combatModifiers.push({ stanceId: s.id, condition: 'stance', appliesTo: s.combat.appliesTo, value: s.combat.value, kind: 'stance-combat' });
  }

  return {
    heroSlug: cfg.heroId,
    abilityName: cfg.abilityName,
    attackRange: cfg.attackRange ?? null,
    defaultStanceId: def?.id ?? null,
    stances,
    combatModifiers,
    triggers: [...new Set(cfg.rules.map((r) => r.trigger))],
    source: 'ability-config',
  };
}

/** Итоговые дальности: базовая строка (StanceId "") при config.attackRange; стоечные — при stance.attackRange. */
function computeAttackRanges(heroes: HeroRow[], manual: AbilityTable['manual']): AbilityTable['attackRanges'] {
  const rows: AbilityTable['attackRanges'] = [];
  for (const h of heroes) {
    if (h.attackRange != null) rows.push({ heroSlug: h.heroSlug, stanceId: '', range: h.attackRange });
    for (const s of h.stances) {
      if (s.attackRange != null) rows.push({ heroSlug: h.heroSlug, stanceId: s.id, range: s.attackRange });
    }
  }
  if (manual.msMarvelExtendedRange != null && !rows.some((r) => r.heroSlug === 'ms-marvel')) {
    rows.push({ heroSlug: 'ms-marvel', stanceId: '', range: manual.msMarvelExtendedRange });
  }
  rows.sort((a, b) => a.heroSlug.localeCompare(b.heroSlug) || a.stanceId.localeCompare(b.stanceId));
  return rows;
}

// ----------------------------------------------------------------------------
// CSV
// ----------------------------------------------------------------------------

function csvCell(v: string | number | boolean | null): string {
  if (v === null || v === undefined) return '';
  const s = String(v);
  return /[",\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
}
function csv(header: string[], rows: Array<Array<string | number | boolean | null>>): string {
  return [header, ...rows].map((r) => r.map(csvCell).join(',')).join('\n') + '\n';
}

function sha256File(p: string): string {
  return crypto.createHash('sha256').update(fs.readFileSync(p)).digest('hex');
}

function stableStringify(v: unknown): string {
  return JSON.stringify(v, (_k, val) => {
    if (val && typeof val === 'object' && !Array.isArray(val)) {
      return Object.fromEntries(Object.entries(val as Record<string, unknown>).sort(([a], [b]) => a.localeCompare(b)));
    }
    return val;
  }, 2) + '\n';
}

// ----------------------------------------------------------------------------
// main
// ----------------------------------------------------------------------------

async function main(): Promise<void> {
  const args = parseArgs(process.argv.slice(2));
  const abilitiesDir = path.join(args.backend, 'src', 'game-engine', 'abilities');
  const configPath = path.join(abilitiesDir, 'ability-config.ts');
  const fighterModelPath = path.join(args.backend, 'src', 'game-engine', 'models', 'fighter.model.ts');
  const msMarvelPath = path.join(abilitiesDir, 'heroes', 'ms-marvel.handler.ts');
  const arthurPath = path.join(abilitiesDir, 'heroes', 'arthur.handler.ts');
  for (const p of [configPath, fighterModelPath]) {
    if (!fs.existsSync(p)) {
      console.error(`Не найден ${p}. Укажите --backend <путь к backend/>.`);
      process.exit(2);
    }
  }

  // Динамический импорт TS-модулей бэкенда (tsx транспилирует на лету; оба файла без импортов).
  const configModule = (await import(pathToFileURL(configPath).href)) as { ABILITY_CONFIGS: readonly AbilityConfig[] };
  const fighterModule = (await import(pathToFileURL(fighterModelPath).href)) as { slugifyHeroName: (s: string) => string };
  const { ABILITY_CONFIGS } = configModule;
  const { slugifyHeroName } = fighterModule;

  // Ручные хендлеры — regex по исходнику (константы не экспортируются, модули тянут NestJS).
  const manual: AbilityTable['manual'] = { msMarvelExtendedRange: null, kingArthurAllowsAttackBoost: null };
  if (fs.existsSync(msMarvelPath)) {
    const m = /const\s+MS_MARVEL_EXTENDED_RANGE\s*=\s*(\d+)/.exec(fs.readFileSync(msMarvelPath, 'utf8'));
    manual.msMarvelExtendedRange = m ? Number(m[1]) : null;
  }
  if (fs.existsSync(arthurPath)) {
    const src = fs.readFileSync(arthurPath, 'utf8');
    manual.kingArthurAllowsAttackBoost = /allowsAttackBoost\s*:\s*true/.test(src) ? true : /allowsAttackBoost/.test(src) ? false : null;
  }

  const heroes = ABILITY_CONFIGS.map((cfg) => buildHeroRow(cfg, slugifyHeroName));
  const dupes = heroes.map((h) => h.heroSlug).filter((s, i, a) => a.indexOf(s) !== i);
  if (dupes.length) throw new Error(`Дубликаты heroId в ABILITY_CONFIGS: ${dupes.join(', ')}`);
  if (manual.msMarvelExtendedRange != null) {
    heroes.push({
      heroSlug: 'ms-marvel',
      abilityName: 'Stretchy',
      attackRange: manual.msMarvelExtendedRange,
      defaultStanceId: null,
      stances: [],
      combatModifiers: [],
      triggers: ['turn-start'],
      source: 'manual-handler',
    });
  }
  heroes.sort((a, b) => a.heroSlug.localeCompare(b.heroSlug));

  const table: AbilityTable = {
    schemaVersion: 1,
    sources: {
      abilityConfig: { path: path.relative(args.backend, configPath).replace(/\\/g, '/'), sha256: sha256File(configPath) },
      ...(fs.existsSync(msMarvelPath) ? { msMarvelHandler: { path: 'src/game-engine/abilities/heroes/ms-marvel.handler.ts', sha256: sha256File(msMarvelPath) } } : {}),
      ...(fs.existsSync(arthurPath) ? { arthurHandler: { path: 'src/game-engine/abilities/heroes/arthur.handler.ts', sha256: sha256File(arthurPath) } } : {}),
    },
    heroes,
    manual,
    attackRanges: computeAttackRanges(heroes, manual),
  };

  const jsonText = stableStringify(table);
  const jsonPath = path.join(args.out, 'ability-table.json');

  if (args.check) {
    if (!fs.existsSync(jsonPath)) {
      console.error(`${jsonPath} отсутствует — запустите экспорт (npm run ability:export)`);
      process.exit(1);
    }
    const existing = fs.readFileSync(jsonPath, 'utf8');
    if (existing !== jsonText) {
      console.error(`ability-table.json устарел относительно ${table.sources.abilityConfig.path} — перезапустите npm run ability:export и обновите DT_AttackRange в проекте (спека Unmatched.Model.AttackRangeSync)`);
      process.exit(1);
    }
    console.log(`ability-table.json актуален (${heroes.length} героев, ${table.attackRanges.length} дальностей)`);
    return;
  }

  fs.mkdirSync(args.out, { recursive: true });
  fs.writeFileSync(jsonPath, jsonText, 'utf8');

  // DT_AttackRange.csv — FUmAttackRangeRow { HeroSlug, StanceId, Range } (ADR §4.3).
  fs.writeFileSync(
    path.join(args.out, 'DT_AttackRange.csv'),
    csv(['Name', 'HeroSlug', 'StanceId', 'Range'], table.attackRanges.map((r) => [r.stanceId ? `${r.heroSlug}__${r.stanceId}` : r.heroSlug, r.heroSlug, r.stanceId, r.range])),
    'utf8',
  );

  // DT_HeroStances.csv — офлайн-копия heroStances(heroSlug) + attackRange стойки.
  const stanceRows: Array<Array<string | number | boolean | null>> = [];
  for (const h of heroes) for (const s of h.stances) stanceRows.push([`${h.heroSlug}__${s.id}`, h.heroSlug, s.id, s.label, s.isDefault, s.attackRange]);
  fs.writeFileSync(path.join(args.out, 'DT_HeroStances.csv'), csv(['Name', 'HeroSlug', 'StanceId', 'Label', 'bIsDefault', 'AttackRange'], stanceRows), 'utf8');

  // DT_HeroCombatMods.csv (v1) — только combat-passive модификаторы; FUmCombatPreview — «оценка», не предикция.
  const modRows: Array<Array<string | number | boolean | null>> = [];
  for (const h of heroes) {
    h.combatModifiers.forEach((m, i) => {
      modRows.push([`${h.heroSlug}__${i}`, h.heroSlug, m.stanceId ?? '', m.condition, m.appliesTo, m.value, m.kind]);
    });
  }
  fs.writeFileSync(path.join(args.out, 'DT_HeroCombatMods.csv'), csv(['Name', 'HeroSlug', 'StanceId', 'Condition', 'AppliesTo', 'Value', 'Kind'], modRows), 'utf8');

  console.log(`Экспортировано в ${args.out}: ${heroes.length} героев, ${table.attackRanges.length} дальностей, ${stanceRows.length} стоек, ${modRows.length} модификаторов`);
  for (const r of table.attackRanges) console.log(`  attackRange ${r.heroSlug}${r.stanceId ? `/${r.stanceId}` : ''} = ${r.range}`);
}

main().catch((e: unknown) => {
  console.error(e instanceof Error ? e.stack ?? e.message : String(e));
  process.exit(1);
});
