/**
 * Точечная починка данных, испорченных багами парсера seed-scraped.ts /
 * seed-all-scraped.ts (set всегда '', все карты MANEUVER без значений и картинок).
 *
 * НЕ пересоздаёт записи (id героев/карт/досок остаются прежними — на них
 * ссылаются games/gamePlayers). Обновляет ТОЛЬКО:
 *   - Hero.set (по name)
 *   - Board.set (по name, для карт из maps.json)
 *   - Card.cardType/subType/attackValue/defenseValue/boostValue/imageUrl/imageUrlRu
 *     (по heroId + name)
 *
 * Запуск: cd backend && npx ts-node --transpile-only prisma/update-scraped-data.ts
 */
import { PrismaClient } from '@prisma/client';
import * as fs from 'fs';
import * as path from 'path';

const prisma = new PrismaClient();

const HEROES_PATH = path.join(__dirname, '../../scraped-data/api/heroes');
const API_PATH = path.join(__dirname, '../../scraped-data/api');

function resolveValue(data: any[], index: number | null | undefined): any {
  if (index === null || index === undefined || index < 0) return null;
  return data[index];
}

function normalizeCardType(type: string): string {
  const typeMap: Record<string, string> = {
    'attack': 'ATTACK',
    'defense': 'DEFENSE',
    'scheme': 'SCHEME',
    'versatile': 'VERSATILE',
    'maneuver': 'MANEUVER',
  };
  return typeMap[type.toLowerCase()] || type.toUpperCase();
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

async function updateHeroesAndCards() {
  console.log('\n🦸 Обновление героев и карт из scraped-data/api/heroes...');

  let heroesUpdated = 0;
  let cardsUpdated = 0;
  let cardsNotMatched = 0;
  let filesSkipped = 0;

  const files = fs.readdirSync(HEROES_PATH).filter((f) => f.endsWith('.json'));

  for (const file of files) {
    const data = loadDataArray(path.join(HEROES_PATH, file));
    if (!data) {
      filesSkipped++;
      continue;
    }

    const heroSchema = data[1];
    if (!heroSchema || typeof heroSchema !== 'object' || Array.isArray(heroSchema)) {
      filesSkipped++;
      continue;
    }

    const heroName = resolveValue(data, heroSchema.name);
    if (!heroName || typeof heroName !== 'string') {
      filesSkipped++;
      continue;
    }

    const dbHero = await prisma.hero.findUnique({ where: { name: heroName } });
    if (!dbHero) {
      filesSkipped++;
      continue;
    }

    // --- Hero.set: heroSchema.set — индекс на объект {key, title} (тоже индексы)
    const setObj = resolveValue(data, heroSchema.set);
    const setTitle = resolveValue(data, setObj?.title) || '';
    if (setTitle && dbHero.set !== setTitle) {
      await prisma.hero.update({
        where: { id: dbHero.id },
        data: { set: setTitle },
      });
      heroesUpdated++;
      console.log(`   ✅ ${heroName}: set → "${setTitle}"`);
    }

    // --- Карты: поля type/value/boostValue/image/i18n лежат на deck item
    for (let i = 0; i < data.length; i++) {
      const item = data[i];
      if (!item || typeof item !== 'object' || Array.isArray(item)) continue;
      if (item.hero !== 2 && item.hero !== 1) continue;
      if (item.card === null || item.card === undefined) continue;

      const cardSchema = resolveValue(data, item.card);
      if (!cardSchema || typeof cardSchema !== 'object') continue;

      const title = resolveValue(data, cardSchema.title);
      if (!title || typeof title !== 'string') continue;

      const rawType = resolveValue(data, item.type) || 'versatile';
      const cardType = normalizeCardType(rawType);
      const value = resolveValue(data, item.value) ?? null;
      const boostValue = resolveValue(data, item.boostValue) ?? null;
      const image = resolveValue(data, item.image) || null;

      let imageRu: string | null = null;
      const i18nData = resolveValue(data, item.i18n);
      if (i18nData && typeof i18nData === 'object' && i18nData.ru !== undefined) {
        const ruData = resolveValue(data, i18nData.ru);
        if (ruData && typeof ruData === 'object' && ruData.image !== undefined) {
          imageRu = resolveValue(data, ruData.image) || null;
        }
      }

      const res = await prisma.card.updateMany({
        where: { heroId: dbHero.id, name: title },
        data: {
          cardType,
          subType: cardType === 'MANEUVER' ? 'Movement' : null,
          // VERSATILE играется и как атака, и как защита
          attackValue: cardType === 'ATTACK' || cardType === 'VERSATILE' ? value : null,
          defenseValue: cardType === 'DEFENSE' || cardType === 'VERSATILE' ? value : null,
          boostValue,
          imageUrl: image,
          imageUrlRu: imageRu,
        },
      });

      if (res.count > 0) {
        cardsUpdated += res.count;
      } else {
        cardsNotMatched++;
      }
    }
  }

  console.log(`\n   📊 Героев обновлено (set): ${heroesUpdated}`);
  console.log(`   📊 Карт обновлено: ${cardsUpdated}`);
  console.log(`   📊 Deck-элементов без совпадения в БД: ${cardsNotMatched}`);
  console.log(`   📊 Файлов пропущено (не герой/нет в БД): ${filesSkipped}`);
}

/** villains.json / minions.json: у item свой индекс set → {key, title} */
async function updateVillainsMinionsSet(fileName: string, label: string) {
  console.log(`\n🦹 Обновление set (${label})...`);

  const data = loadDataArray(path.join(API_PATH, fileName));
  if (!data) {
    console.log(`   ⏭️  Файл ${fileName} не найден или не распарсился`);
    return;
  }

  const indices = data[1];
  if (!Array.isArray(indices)) return;

  let updated = 0;

  for (const index of indices) {
    const itemData = data[index];
    if (!itemData || typeof itemData !== 'object') continue;

    const name = resolveValue(data, itemData.name);
    if (!name || typeof name !== 'string') continue;

    const setObj = resolveValue(data, itemData.set);
    const setKey = resolveValue(data, setObj?.key) || '';
    if (!setKey) continue;

    const res = await prisma.hero.updateMany({
      where: { name, set: '' },
      data: { set: setKey },
    });
    if (res.count > 0) {
      updated += res.count;
      console.log(`   ✅ ${name}: set → "${setKey}"`);
    }
  }

  console.log(`   📊 ${label}: обновлено ${updated}`);
}

/** maps.json → Board.set */
async function updateBoardsSet() {
  console.log('\n🗺️  Обновление set у досок (maps.json)...');

  const data = loadDataArray(path.join(API_PATH, 'maps.json'));
  if (!data) {
    console.log('   ⏭️  Файл maps.json не найден или не распарсился');
    return;
  }

  const mapIndices = data[1];
  if (!Array.isArray(mapIndices)) return;

  let updated = 0;

  for (const mapIndex of mapIndices) {
    const mapData = data[mapIndex];
    if (!mapData || typeof mapData !== 'object') continue;

    const name = resolveValue(data, mapData.name);
    if (!name || typeof name !== 'string') continue;

    const setObj = resolveValue(data, mapData.set);
    const setKey = resolveValue(data, setObj?.key) || '';
    if (!setKey) continue;

    const res = await prisma.board.updateMany({
      where: { name, set: '' },
      data: { set: setKey },
    });
    if (res.count > 0) {
      updated += res.count;
      console.log(`   ✅ ${name}: set → "${setKey}"`);
    }
  }

  console.log(`   📊 Досок обновлено: ${updated}`);
}

async function printStats(label: string) {
  const byType = await prisma.card.groupBy({ by: ['cardType'], _count: true });
  const totalCards = await prisma.card.count();
  const noValues = await prisma.card.count({
    where: { attackValue: null, defenseValue: null },
  });
  const noImage = await prisma.card.count({
    where: { OR: [{ imageUrl: null }, { imageUrl: '' }] },
  });
  const heroesEmptySet = await prisma.hero.count({ where: { set: '' } });
  const boardsEmptySet = await prisma.board.count({ where: { set: '' } });

  console.log(`\n📊 ${label}:`);
  console.log(
    `   Карты по типам: ${byType
      .map((t) => `${t.cardType}=${t._count}`)
      .join(', ')} (всего ${totalCards})`,
  );
  console.log(`   Карт без attack/defense value: ${noValues}`);
  console.log(`   Карт без imageUrl: ${noImage}`);
  console.log(`   Героев с пустым set: ${heroesEmptySet}`);
  console.log(`   Досок с пустым set: ${boardsEmptySet}`);
}

async function main() {
  console.log('🔧 Точечная починка scraped-данных в БД (без пересоздания записей)...');

  await printStats('Состояние ДО');

  await updateHeroesAndCards();
  await updateVillainsMinionsSet('villains.json', 'злодеи');
  await updateVillainsMinionsSet('minions.json', 'миньоны');
  await updateBoardsSet();

  await printStats('Состояние ПОСЛЕ');

  console.log('\n✅ Готово!');
}

main()
  .catch((e) => {
    console.error('❌ Update error:', e);
    process.exit(1);
  })
  .finally(async () => {
    await prisma.$disconnect();
  });
