/**
 * Backfill: attackType героев (Hero.properties.attackType) и их помощников (Hero.sidekicks[].attackType)
 * из scraped-data.
 *
 * Идемпотентный скрипт (F3, ranged-атаки): для каждого героя из scraped-data/api/heroes/*.json берёт поле
 * attack ('melee'|'range'|'melee_range') у героя и у помощников, находит Hero по имени и мержит
 * properties = { ...existing, attackType: attack }; помощникам с тем же именем ставит attackType. Ничего не
 * удаляет; повторный запуск — no-op. Not-found имена логируются.
 *
 * Движок нормализует значение через normalizeAttackType ('range' → 'ranged', мусор/'melee_range' → 'melee') —
 * здесь храним сырое значение скрейпа. Без поля движок даёт 'melee': так Medusa (scraped attack=range) играла
 * ближним бойцом на стенде S09 (GD-058 interim 2026-09-30 §8 п. 9) — seed-scraped.ts пропускал уже созданных
 * героев, а этот backfill не входил в цепочку tools/s09/bootstrap-s09-stack.cjs.
 *
 * Запуск (с хоста, из backend/, как остальные сиды):
 *   node -r ts-node/register/transpile-only prisma/backfill-attack-type.ts            # применить
 *   node -r ts-node/register/transpile-only prisma/backfill-attack-type.ts --dry-run  # только план, без записи
 *   node -r ts-node/register/transpile-only prisma/backfill-attack-type.ts --check    # план; exit 3, если что-то
 *                                                                                     # расходится со скрейпом
 * Чистые функции (разбор скрейпа, план правки) экспортируются для jest (src/games/services/
 * attack-type-backfill.spec.ts) и для seed-scraped.ts.
 */

import { PrismaClient } from '@prisma/client';
import * as fs from 'fs';
import * as path from 'path';

export const SCRAPED_DATA_PATH = path.join(__dirname, '../../scraped-data/api/heroes');

// Тот же список ключей, что в seed-scraped.ts (там же лежат не-геройские
// файлы — сеты/доски, поэтому по явному списку, а не readdir)
export const HERO_KEYS = [
  'achilles', 'alice', 'ancient-leshen', 'angel', 'annie-christmas',
  'beowulf', 'bigfoot', 'black-panther', 'black-widow', 'blackbeard',
  'bloody-mary', 'bruce-lee', 'buffy', 'bullseye', 'chupacabra', 'ciri',
  'cloak-dagger', 'cobble-fog', 'daredevil', 'data', 'deadpool',
  'doctor-strange', 'donatello', 'dr-jill-trent', 'dr-sattler', 'dracula',
  'elektra', 'eredin', 'geralt-of-rivia', 'ghost-rider', 'golden-bat',
  'hamlet', 'harry-houdini', 'hells-kitchen', 'invisible-man', 'jekyll-hyde',
  'king-arthur', 'krang', 'leonardo', 'little-red', 'loki', 'luke-cage',
  'medusa', 'melee', 'michelangelo', 'moon-knight', 'ms-marvel',
  'muhammad-ali', 'nikola-tesla', 'oda-nobunaga', 'pandora', 'philippa',
  'range', 'raphael', 'raptors', 'redemption-row', 'refresh',
  'robert-muldoon', 'robin-hood', 'shakespeare', 'she-hulk', 'sherlock-holmes',
  'shredder', 'sinbad', 'slings-and-arrows', 'spiderman', 'spike',
  'squirrel-girl', 'sun-wukong', 'suns-origin', 't-rex', 'teen-spirit',
  'the-genie', 'the-wayward-sisters', 'the-witcher-realms-fall',
  'the-witcher-steel-silver', 'titania', 'tomoe-gozen', 'willow',
  'winter-soldier', 'yennefer-triss', 'yennenga',
];

/** Тип атаки героя и его помощников, как в скрейпе (сырые значения). */
export interface ScrapedAttack {
  key: string;
  name: string;
  attack: string;
  sidekicks: { name: string; attack: string }[];
}

/** Строка Hero, которую читает backfill (остальные поля не трогаются). */
export interface HeroAttackRow {
  id: string;
  name: string;
  properties: unknown;
  sidekicks: unknown;
}

/** Правка одной строки Hero: только изменённые поля; changes — человекочитаемый список. */
export interface AttackTypePatch {
  properties?: Record<string, unknown>;
  sidekicks?: unknown;
  changes: string[];
}

// --- Devalue-парсер scraped-формата (тот же механизм, что в seed-scraped.ts) ---

function resolveValue(data: any[], index: number | null | undefined): any {
  if (index === null || index === undefined || index < 0) return null;
  return data[index];
}

/** Помощники героя: прямой объект или объект индексов (как parseSidekicks в seed-scraped.ts). */
function parseSidekickAttacks(data: any[], indexes: unknown): { name: string; attack: string }[] {
  if (!Array.isArray(indexes)) return [];
  const out: { name: string; attack: string }[] = [];
  for (const skIndex of indexes) {
    if (typeof skIndex !== 'number') continue;
    const sk = resolveValue(data, skIndex);
    if (!sk || typeof sk !== 'object') continue;
    const direct = typeof sk.name === 'string';
    const name = direct ? sk.name : resolveValue(data, sk.name);
    const attack = direct ? sk.attack : resolveValue(data, sk.attack);
    if (typeof name !== 'string' || !name) continue;
    out.push({ name, attack: typeof attack === 'string' && attack ? attack : 'melee' });
  }
  return out;
}

/** Достаёт {name, attack, sidekicks} героя из nodes[2].data (heroSchema = data[1]). */
export function parseHeroAttack(rawData: any, key = ''): ScrapedAttack | null {
  try {
    const nodes = rawData?.nodes;
    if (!nodes || nodes.length < 3 || !nodes[2] || !nodes[2].data) return null;

    const data = nodes[2].data as any[];
    const heroSchema = data[1];
    if (!heroSchema || typeof heroSchema !== 'object') return null;

    const name = resolveValue(data, heroSchema.name);
    const attack = resolveValue(data, heroSchema.attack);
    if (!name || typeof name !== 'string') return null;

    return {
      key,
      name,
      attack: typeof attack === 'string' && attack ? attack : 'melee',
      sidekicks: parseSidekickAttacks(data, resolveValue(data, heroSchema.sidekicks)),
    };
  } catch (error) {
    console.error('Error parsing hero data:', error);
    return null;
  }
}

/** Все герои скрейпа из списка ключей (нет файла / не разобран — в skipped). */
export function readScrapedAttacks(
  dir: string = SCRAPED_DATA_PATH,
  keys: readonly string[] = HERO_KEYS,
): { parsed: ScrapedAttack[]; skipped: string[] } {
  const parsed: ScrapedAttack[] = [];
  const skipped: string[] = [];
  for (const key of keys) {
    const filePath = path.join(dir, `${key}.json`);
    if (!fs.existsSync(filePath)) {
      skipped.push(key);
      continue;
    }
    let hero: ScrapedAttack | null = null;
    try {
      hero = parseHeroAttack(JSON.parse(fs.readFileSync(filePath, 'utf-8')), key);
    } catch (error) {
      console.error(`❌ Ошибка чтения ${key}:`, error);
    }
    if (hero) parsed.push(hero);
    else skipped.push(key);
  }
  return { parsed, skipped };
}

/** Канон движка (копия normalizeAttackType из src/game-engine/models/fighter.model.ts — сиды не тянут src). */
function canonical(v: unknown): 'melee' | 'ranged' {
  return v === 'ranged' || v === 'range' ? 'ranged' : 'melee';
}

/** Уже задано и для движка значит то же самое (например 'ranged' в БД при 'range' в скрейпе) — не трогаем. */
function sameAttack(existing: unknown, scraped: string): boolean {
  return existing === scraped || (typeof existing === 'string' && canonical(existing) === canonical(scraped));
}

function normName(v: unknown): string {
  return typeof v === 'string' ? v.trim().toLowerCase() : '';
}

/**
 * План правки одной строки Hero под скрейп. null — строка уже согласована (идемпотентность).
 * Остальные ключи properties и поля помощников сохраняются; помощник без пары по имени в скрейпе не трогается;
 * sidekicks, хранимые строкой JSON, пишутся обратно строкой.
 */
export function planAttackTypePatch(
  hero: Pick<HeroAttackRow, 'properties' | 'sidekicks'>,
  scraped: Pick<ScrapedAttack, 'attack' | 'sidekicks'>,
): AttackTypePatch | null {
  const changes: string[] = [];
  const patch: AttackTypePatch = { changes };

  const props =
    hero.properties && typeof hero.properties === 'object' && !Array.isArray(hero.properties)
      ? (hero.properties as Record<string, unknown>)
      : {};
  if (!sameAttack(props.attackType, scraped.attack)) {
    patch.properties = { ...props, attackType: scraped.attack };
    changes.push(`attackType ${String(props.attackType ?? '<none>')} -> ${scraped.attack}`);
  }

  const asString = typeof hero.sidekicks === 'string';
  let list: unknown = hero.sidekicks;
  if (asString) {
    try {
      list = JSON.parse(hero.sidekicks as string);
    } catch {
      list = null;
    }
  }
  if (Array.isArray(list) && scraped.sidekicks.length > 0) {
    const byName = new Map<string, string>();
    for (const sk of scraped.sidekicks) {
      if (!byName.has(normName(sk.name))) byName.set(normName(sk.name), sk.attack);
    }
    let touched = false;
    const next = list.map((sk: any) => {
      const want = sk && typeof sk === 'object' ? byName.get(normName(sk.name)) : undefined;
      if (want === undefined || sameAttack(sk.attackType, want)) return sk;
      touched = true;
      changes.push(`sidekick ${sk.name}: attackType ${String(sk.attackType ?? '<none>')} -> ${want}`);
      return { ...sk, attackType: want };
    });
    if (touched) patch.sidekicks = asString ? JSON.stringify(next) : next;
  }

  return changes.length > 0 ? patch : null;
}

export interface BackfillStats {
  updated: number;
  alreadySet: number;
  notFound: string[];
  pending: { name: string; changes: string[] }[];
}

type HeroDelegate = {
  findUnique(args: { where: { name: string } }): Promise<HeroAttackRow | null>;
  update(args: { where: { id: string }; data: Record<string, unknown> }): Promise<unknown>;
};

/** Прогон по героям скрейпа. dryRun — ни одной записи, всё найденное попадает в pending. */
export async function applyAttackTypeBackfill(
  prisma: { hero: HeroDelegate } | PrismaClient,
  scraped: ScrapedAttack[],
  opts: { dryRun?: boolean; log?: (line: string) => void } = {},
): Promise<BackfillStats> {
  const log = opts.log ?? ((line: string) => console.log(line));
  const heroes = (prisma as { hero: HeroDelegate }).hero;
  const stats: BackfillStats = { updated: 0, alreadySet: 0, notFound: [], pending: [] };
  for (const s of scraped) {
    const hero = await heroes.findUnique({ where: { name: s.name } });
    if (!hero) {
      stats.notFound.push(`${s.name} (${s.key})`);
      continue;
    }
    const patch = planAttackTypePatch(hero, s);
    if (!patch) {
      stats.alreadySet++;
      continue;
    }
    if (opts.dryRun) {
      stats.pending.push({ name: hero.name, changes: patch.changes });
      log(`🔎 [dry-run] ${hero.name}: ${patch.changes.join('; ')}`);
      continue;
    }
    const data: Record<string, unknown> = {};
    if (patch.properties) data.properties = patch.properties;
    if (patch.sidekicks !== undefined) data.sidekicks = patch.sidekicks;
    await heroes.update({ where: { id: hero.id }, data });
    stats.updated++;
    log(`✅ ${hero.name}: ${patch.changes.join('; ')}`);
  }
  return stats;
}

async function main() {
  const args = new Set(process.argv.slice(2));
  const check = args.has('--check');
  const dryRun = check || args.has('--dry-run');
  console.log(`🏹 Backfill: attackType героев и помощников${dryRun ? ' (без записи)' : ''}...\n`);

  const { parsed, skipped } = readScrapedAttacks();
  const prisma = new PrismaClient();
  try {
    const stats = await applyAttackTypeBackfill(prisma, parsed, { dryRun });

    console.log('\n📊 Статистика backfill:');
    console.log(`   ✅ Обновлено: ${stats.updated}`);
    console.log(`   🔎 Требует правки (не записано): ${stats.pending.length}`);
    console.log(`   ⏭️  Уже согласовано: ${stats.alreadySet}`);
    console.log(`   ⚠️  Пропущено (нет файла/парс): ${skipped.length}`);
    console.log(`   ❓ Не найдено в БД: ${stats.notFound.length}`);
    if (stats.notFound.length > 0) console.log(`      ${stats.notFound.join('\n      ')}`);

    // Состав стенда S09 (Medusa vs King Arthur): тип атаки, как его увидит движок.
    for (const name of ['Medusa', 'King Arthur']) {
      const hero = (await prisma.hero.findUnique({ where: { name } })) as HeroAttackRow | null;
      if (!hero) continue;
      const props = (hero.properties ?? {}) as Record<string, unknown>;
      let sks: unknown = hero.sidekicks;
      if (typeof sks === 'string') {
        try {
          sks = JSON.parse(sks);
        } catch {
          sks = [];
        }
      }
      const skText = Array.isArray(sks)
        ? sks.map((sk: any) => `${sk?.name}=${canonical(sk?.attackType)}(${String(sk?.attackType ?? '<none>')})`).join(', ')
        : '-';
      console.log(`   🎯 ${name}: ${canonical(props.attackType)} (${String(props.attackType ?? '<none>')}); помощники: ${skText}`);
    }

    if (check && stats.pending.length > 0) {
      console.error(`CHECK FAILED: ${stats.pending.length} герой(ев) расходятся со скрейпом по attackType`);
      process.exitCode = 3;
    }
  } finally {
    await prisma.$disconnect();
  }
}

if (require.main === module) {
  main().catch((e) => {
    console.error('❌ Backfill error:', e);
    process.exit(1);
  });
}
