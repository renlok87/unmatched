import { PrismaClient } from '@prisma/client';
import * as fs from 'fs';
import * as path from 'path';

const prisma = new PrismaClient();

const SCRAPED_DATA_PATH = path.join(__dirname, '../../scraped-data/api');

function resolveValue(data: any[], index: number | null | undefined): any {
  if (index === null || index === undefined || index < 0) return null;
  return data[index];
}

interface ParsedSet {
  name: string;
  key: string;
  description: string;
  imageUrl: string;
}

interface ParsedMap {
  name: string;
  key: string;
  width: number;
  height: number;
  minPlayers: number;
  maxPlayers: number;
  description: string;
  imageUrl: string;
  setKey: string;
}

interface ParsedVillain {
  name: string;
  key: string;
  hp: number;
  color: string;
  description: string;
  avatar: string;
  cardBackImage: string;
  miniatureImage: string;
  setKey: string;
}

interface ParsedMinion {
  name: string;
  key: string;
  hp: number;
  color: string;
  description: string;
  avatar: string;
  setKey: string;
}

function parseSetsData(rawData: any): ParsedSet[] {
  const sets: ParsedSet[] = [];

  try {
    const nodes = rawData.nodes;
    if (!nodes || nodes.length < 3 || !nodes[2] || !nodes[2].data) return sets;

    const data = nodes[2].data as any[];
    const setIndices = data[1] as number[];

    if (!Array.isArray(setIndices)) return sets;

    const setSchema = data[2];
    if (!setSchema) return sets;

    for (const setIndex of setIndices) {
      const setData = data[setIndex];
      if (!setData || typeof setData !== 'object') continue;

      const set: ParsedSet = {
        name: resolveValue(data, setData.name) || 'Unknown',
        key: resolveValue(data, setData.key) || '',
        description: resolveValue(data, setData.description) || '',
        imageUrl: resolveValue(data, setData.imageUrl) || '',
      };

      sets.push(set);
    }
  } catch (error) {
    console.error('Error parsing sets data:', error);
  }

  return sets;
}

function parseMapsData(rawData: any): ParsedMap[] {
  const maps: ParsedMap[] = [];

  try {
    const nodes = rawData.nodes;
    if (!nodes || nodes.length < 3 || !nodes[2] || !nodes[2].data) return maps;

    const data = nodes[2].data as any[];
    const mapIndices = data[1] as number[];

    if (!Array.isArray(mapIndices)) return maps;

    const mapSchema = data[2];
    if (!mapSchema) return maps;

    for (const mapIndex of mapIndices) {
      const mapData = data[mapIndex];
      if (!mapData || typeof mapData !== 'object') continue;

      // mapData.set — числовой индекс на объект {key, title, ...} (тоже индексы)
      const setObj = resolveValue(data, mapData.set);
      const setKey = resolveValue(data, setObj?.key) || '';

      const map: ParsedMap = {
        name: resolveValue(data, mapData.name) || 'Unknown',
        key: resolveValue(data, mapData.key) || '',
        width: resolveValue(data, mapData.width) || 5,
        height: resolveValue(data, mapData.height) || 6,
        minPlayers: resolveValue(data, mapData.minPlayers) || 2,
        maxPlayers: resolveValue(data, mapData.maxPlayers) || 4,
        description: resolveValue(data, mapData.description) || '',
        imageUrl: resolveValue(data, mapData.image) || '',
        setKey: setKey,
      };

      maps.push(map);
    }
  } catch (error) {
    console.error('Error parsing maps data:', error);
  }

  return maps;
}

function parseVillainsData(rawData: any): ParsedVillain[] {
  const villains: ParsedVillain[] = [];

  try {
    const nodes = rawData.nodes;
    if (!nodes || nodes.length < 3 || !nodes[2] || !nodes[2].data) return villains;

    const data = nodes[2].data as any[];
    const villainIndices = data[1] as number[];

    if (!Array.isArray(villainIndices)) return villains;

    const villainSchema = data[2];
    if (!villainSchema) return villains;

    for (const villainIndex of villainIndices) {
      const villainData = data[villainIndex];
      if (!villainData || typeof villainData !== 'object') continue;

      // villainData.set — числовой индекс на объект {key, title} (тоже индексы)
      const setObj = resolveValue(data, villainData.set);
      const setKey = resolveValue(data, setObj?.key) || '';

      const villain: ParsedVillain = {
        name: resolveValue(data, villainData.name) || 'Unknown',
        key: resolveValue(data, villainData.key) || '',
        hp: resolveValue(data, villainData.hp) || 20,
        color: resolveValue(data, villainData.color) || '#000000',
        description: resolveValue(data, villainData.description) || '',
        avatar: resolveValue(data, villainData.avatar) || '',
        cardBackImage: resolveValue(data, villainData.cardBackImage) || '',
        miniatureImage: resolveValue(data, villainData.miniatureImage) || '',
        setKey: setKey,
      };

      villains.push(villain);
    }
  } catch (error) {
    console.error('Error parsing villains data:', error);
  }

  return villains;
}

function parseMinionsData(rawData: any): ParsedMinion[] {
  const minions: ParsedMinion[] = [];

  try {
    const nodes = rawData.nodes;
    if (!nodes || nodes.length < 3 || !nodes[2] || !nodes[2].data) return minions;

    const data = nodes[2].data as any[];
    const minionIndices = data[1] as number[];

    if (!Array.isArray(minionIndices)) return minions;

    const minionSchema = data[2];
    if (!minionSchema) return minions;

    for (const minionIndex of minionIndices) {
      const minionData = data[minionIndex];
      if (!minionData || typeof minionData !== 'object') continue;

      // minionData.set — числовой индекс на объект {key, title} (тоже индексы)
      const setObj = resolveValue(data, minionData.set);
      const setKey = resolveValue(data, setObj?.key) || '';

      const minion: ParsedMinion = {
        name: resolveValue(data, minionData.name) || 'Unknown',
        key: resolveValue(data, minionData.key) || '',
        hp: resolveValue(data, minionData.hp) || 5,
        color: resolveValue(data, minionData.color) || '#000000',
        description: resolveValue(data, minionData.description) || '',
        avatar: resolveValue(data, minionData.avatar) || '',
        setKey: setKey,
      };

      minions.push(minion);
    }
  } catch (error) {
    console.error('Error parsing minions data:', error);
  }

  return minions;
}

async function importSets() {
  console.log('\n📦 Импорт сетов...');

  const filePath = path.join(SCRAPED_DATA_PATH, 'sets.json');
  if (!fs.existsSync(filePath)) {
    console.log('⏭️  Файл sets.json не найден');
    return;
  }

  try {
    const rawData = fs.readFileSync(filePath, 'utf-8');
    const parsed = JSON.parse(rawData);
    const sets = parseSetsData(parsed);

    let imported = 0;
    let skipped = 0;

    for (const setData of sets) {
      const existingSet = await prisma.board.findFirst({
        where: { name: setData.name },
      });

      if (existingSet) {
        skipped++;
        continue;
      }

      await prisma.board.create({
        data: {
          name: setData.name,
          nameEn: setData.name,
          nameRu: setData.name,
          set: setData.name,
          width: 5,
          height: 6,
          cells: [],
          features: {
            type: 'custom',
            description: setData.description,
            setKey: setData.key,
          },
          imageUrl: setData.imageUrl,
          imageUrlDark: setData.imageUrl,
        },
      });

      imported++;
      console.log(`   ✅ Импортирован сет: ${setData.name}`);
    }

    console.log(`📊 Сеты: ${imported} импортировано, ${skipped} пропущено`);
  } catch (error) {
    console.error('❌ Ошибка при импорте сетов:', error);
  }
}

async function importMaps() {
  console.log('\n🗺️  Импорт карт (досок)...');

  const filePath = path.join(SCRAPED_DATA_PATH, 'maps.json');
  if (!fs.existsSync(filePath)) {
    console.log('⏭️  Файл maps.json не найден');
    return;
  }

  try {
    const rawData = fs.readFileSync(filePath, 'utf-8');
    const parsed = JSON.parse(rawData);
    const maps = parseMapsData(parsed);

    let imported = 0;
    let skipped = 0;

    for (const mapData of maps) {
      const existingMap = await prisma.board.findFirst({
        where: { name: mapData.name },
      });

      if (existingMap) {
        skipped++;
        continue;
      }

      await prisma.board.create({
        data: {
          name: mapData.name,
          nameEn: mapData.name,
          nameRu: mapData.name,
          set: mapData.setKey,
          width: mapData.width,
          height: mapData.height,
          cells: [],
          features: {
            type: 'custom',
            description: mapData.description,
            mapKey: mapData.key,
            minPlayers: mapData.minPlayers,
            maxPlayers: mapData.maxPlayers,
          },
          imageUrl: mapData.imageUrl,
          imageUrlDark: mapData.imageUrl,
        },
      });

      imported++;
      console.log(`   ✅ Импортирована карта: ${mapData.name} (${mapData.width}x${mapData.height})`);
    }

    console.log(`🗺️  Карты: ${imported} импортировано, ${skipped} пропущено`);
  } catch (error) {
    console.error('❌ Ошибка при импорте карт:', error);
  }
}

async function importVillains() {
  console.log('\n🦹 Импорт злодеев...');

  const filePath = path.join(SCRAPED_DATA_PATH, 'villains.json');
  if (!fs.existsSync(filePath)) {
    console.log('⏭️  Файл villains.json не найден');
    return;
  }

  try {
    const rawData = fs.readFileSync(filePath, 'utf-8');
    const parsed = JSON.parse(rawData);
    const villains = parseVillainsData(parsed);

    let imported = 0;
    let skipped = 0;

    for (const villainData of villains) {
      const existingHero = await prisma.hero.findFirst({
        where: { name: villainData.name },
      });

      if (existingHero) {
        skipped++;
        continue;
      }

      await prisma.hero.create({
        data: {
          name: villainData.name,
          nameEn: villainData.name,
          nameRu: villainData.name,
          set: villainData.setKey,
          health: villainData.hp,
          fighterType: 'VILLAIN',
          ability: {
            type: 'VILLAIN',
            timing: 'PASSIVE',
            effect: villainData.description,
            description: villainData.description,
          },
          deckCards: [],
          properties: {
            color: villainData.color,
          },
          imageUrl: villainData.cardBackImage,
          avatarUrl: villainData.avatar,
        },
      });

      imported++;
      console.log(`   ✅ Импортирован злодей: ${villainData.name} (${villainData.hp} HP)`);
    }

    console.log(`🦹 Злодеи: ${imported} импортировано, ${skipped} пропущено`);
  } catch (error) {
    console.error('❌ Ошибка при импорте злодеев:', error);
  }
}

async function importMinions() {
  console.log('\n👹 Импорт миньонов...');

  const filePath = path.join(SCRAPED_DATA_PATH, 'minions.json');
  if (!fs.existsSync(filePath)) {
    console.log('⏭️  Файл minions.json не найден');
    return;
  }

  try {
    const rawData = fs.readFileSync(filePath, 'utf-8');
    const parsed = JSON.parse(rawData);
    const minions = parseMinionsData(parsed);

    let imported = 0;
    let skipped = 0;

    for (const minionData of minions) {
      const existingHero = await prisma.hero.findFirst({
        where: { name: minionData.name },
      });

      if (existingHero) {
        skipped++;
        continue;
      }

      await prisma.hero.create({
        data: {
          name: minionData.name,
          nameEn: minionData.name,
          nameRu: minionData.name,
          set: minionData.setKey,
          health: minionData.hp,
          fighterType: 'MINION',
          ability: {
            type: 'MINION',
            timing: 'PASSIVE',
            effect: minionData.description,
            description: minionData.description,
          },
          deckCards: [],
          properties: {
            color: minionData.color,
          },
          imageUrl: minionData.avatar,
          avatarUrl: minionData.avatar,
        },
      });

      imported++;
      console.log(`   ✅ Импортирован миньон: ${minionData.name} (${minionData.hp} HP)`);
    }

    console.log(`👹 Миньоны: ${imported} импортировано, ${skipped} пропущено`);
  } catch (error) {
    console.error('❌ Ошибка при импорте миньонов:', error);
  }
}

async function main() {
  console.log('🌱 Seed: Импорт всех скрапленных данных...\n');

  await importSets();
  await importMaps();
  await importVillains();
  await importMinions();

  const heroCount = await prisma.hero.count();
  const cardCount = await prisma.card.count();
  const boardCount = await prisma.board.count();

  console.log('\n📊 Итоговая статистика БД:');
  console.log(`   🦸 Героев (включая злодеев и миньонов): ${heroCount}`);
  console.log(`   🃏 Карт: ${cardCount}`);
  console.log(`   🗺️  Досок: ${boardCount}`);
  console.log('\n✅ Импорт завершен!');
}

main()
  .catch((e) => {
    console.error('❌ Seed error:', e);
    process.exit(1);
  })
  .finally(async () => {
    await prisma.$disconnect();
  });