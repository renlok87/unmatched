/**
 * Backfill: attackType героев в Hero.properties из scraped-data.
 *
 * Одноразовый идемпотентный скрипт (F3, ranged-атаки): для каждого героя из
 * scraped-data/api/heroes/*.json берёт поле attack ('melee'|'range'|'melee_range'),
 * находит Hero по имени и мержит properties = { ...existing, attackType: attack }.
 * Ничего не удаляет; повторный запуск — no-op. Not-found имена логируются.
 *
 * Движок нормализует значение через normalizeAttackType ('range' → 'ranged',
 * мусор/'melee_range' → 'melee') — здесь храним сырое значение скрейпа.
 *
 * Запуск (с хоста, из backend/, как остальные сиды):
 *   npx ts-node --transpile-only -e "require('./prisma/backfill-attack-type.ts')"
 */

import { PrismaClient } from '@prisma/client';
import * as fs from 'fs';
import * as path from 'path';

const prisma = new PrismaClient();

const SCRAPED_DATA_PATH = path.join(__dirname, '../../scraped-data/api/heroes');

// Тот же список ключей, что в seed-scraped.ts (там же лежат не-геройские
// файлы — сеты/доски, поэтому по явному списку, а не readdir)
const HERO_KEYS = [
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

// --- Devalue-парсер scraped-формата (тот же механизм, что в seed-scraped.ts) ---

function resolveValue(data: any[], index: number | null | undefined): any {
  if (index === null || index === undefined || index < 0) return null;
  return data[index];
}

/** Достаёт {name, attack} героя из nodes[2].data (heroSchema = data[1]) */
function parseHeroAttack(rawData: any): { name: string; attack: string } | null {
  try {
    const nodes = rawData.nodes;
    if (!nodes || nodes.length < 3 || !nodes[2] || !nodes[2].data) return null;

    const data = nodes[2].data as any[];
    const heroSchema = data[1];
    if (!heroSchema || typeof heroSchema !== 'object') return null;

    const name = resolveValue(data, heroSchema.name);
    const attack = resolveValue(data, heroSchema.attack);
    if (!name || typeof name !== 'string') return null;

    return { name, attack: typeof attack === 'string' ? attack : 'melee' };
  } catch (error) {
    console.error('Error parsing hero data:', error);
    return null;
  }
}

async function main() {
  console.log('🏹 Backfill: attackType героев в Hero.properties...\n');

  let updated = 0;
  let alreadySet = 0;
  let notFound = 0;
  let skipped = 0;
  const notFoundNames: string[] = [];

  for (const heroKey of HERO_KEYS) {
    const filePath = path.join(SCRAPED_DATA_PATH, `${heroKey}.json`);
    if (!fs.existsSync(filePath)) {
      skipped++;
      continue;
    }

    let parsed: { name: string; attack: string } | null = null;
    try {
      parsed = parseHeroAttack(JSON.parse(fs.readFileSync(filePath, 'utf-8')));
    } catch (error) {
      console.error(`❌ Ошибка чтения ${heroKey}:`, error);
    }
    if (!parsed) {
      console.log(`⚠️  Пропуск: ${heroKey} (не удалось распарсить)`);
      skipped++;
      continue;
    }

    const hero = await prisma.hero.findUnique({ where: { name: parsed.name } });
    if (!hero) {
      notFound++;
      notFoundNames.push(`${parsed.name} (${heroKey})`);
      continue;
    }

    const existingProps =
      hero.properties && typeof hero.properties === 'object' && !Array.isArray(hero.properties)
        ? (hero.properties as Record<string, unknown>)
        : {};

    if (existingProps.attackType === parsed.attack) {
      alreadySet++;
      continue;
    }

    await prisma.hero.update({
      where: { id: hero.id },
      data: { properties: { ...existingProps, attackType: parsed.attack } },
    });
    console.log(`✅ ${hero.name}: attackType = ${parsed.attack}`);
    updated++;
  }

  console.log('\n📊 Статистика backfill:');
  console.log(`   ✅ Обновлено: ${updated}`);
  console.log(`   ⏭️  Уже заполнено: ${alreadySet}`);
  console.log(`   ⚠️  Пропущено (нет файла/парс): ${skipped}`);
  console.log(`   ❓ Не найдено в БД: ${notFound}`);
  if (notFoundNames.length > 0) {
    console.log(`      ${notFoundNames.join('\n      ')}`);
  }
}

main()
  .catch((e) => {
    console.error('❌ Backfill error:', e);
    process.exit(1);
  })
  .finally(async () => {
    await prisma.$disconnect();
  });
