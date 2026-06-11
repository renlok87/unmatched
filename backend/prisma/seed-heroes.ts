import { PrismaClient } from '@prisma/client';
import * as fs from 'fs';
import * as path from 'path';

const prisma = new PrismaClient();

const HEROES_DATA_PATH = path.join(__dirname, '../../scraped-data/api/heroes');
const NORMALIZED_PATH = path.join(__dirname, '../../scraped-data/api/normalized');

interface HeroData {
  slug: string;
  name: string;
  urls: {
    avatar?: string;
    mini?: string;
    cardCover?: string;
  };
  cards: Array<{
    id: number;
    url: string;
    filename: string;
  }>;
  images: string[];
}

interface RawHeroData {
  nodes: Array<{
    type: string;
    data?: any[];
  }>;
}

function resolveValue(data: any[], index: number | null | undefined): any {
  if (index === null || index === undefined || index < 0) return null;
  return data[index];
}

function parseHeroFile(filePath: string, normalizedData?: HeroData) {
  try {
    const rawData = fs.readFileSync(filePath, 'utf-8');
    const parsed: RawHeroData = JSON.parse(rawData);

    const nodes = parsed.nodes;
    if (!nodes || nodes.length < 3 || !nodes[2] || !nodes[2].data) {
      return null;
    }

    const data = nodes[2].data as any[];

    // data[1] - это схема (объект с индексами полей)
    // data[2] - это индекс массива с индексами героев
    const schema = data[1]; // схема с индексами полей
    const heroesArrayIndex = data[2]; // индекс массива с героями (обычно 25)

    const heroIndices = data[heroesArrayIndex];

    if (!Array.isArray(heroIndices) || heroIndices.length === 0) {
      return null;
    }

    // Берем первого героя из списка
    const heroIndex = heroIndices[0];
    const heroData = data[heroIndex];

    if (!heroData || typeof heroData !== 'object') {
      return null;
    }

    // Извлекаем данные героя используя индексы из схемы
    const name = data[schema.name] || normalizedData?.name || 'Unknown';
    const key = data[schema.key] || normalizedData?.slug || '';
    const startHealth = data[schema.startHealth] || 20;
    const attack = data[schema.attack] || 'melee';
    const specialAbility = data[schema.specialAbility] || '';
    const description = data[schema.description] || '';
    const cardBackImage = data[schema.cardBackImage] || normalizedData?.urls?.cardCover || '';
    const miniatureImage = data[schema.miniatureImage] || normalizedData?.urls?.mini || '';
    const avatar = data[schema.avatar] || normalizedData?.urls?.avatar || '';
    const color = data[schema.color] || '#000000';

    // Извлекаем сет
    let setKey = 'default';
    let setTitle = 'Default';
    const setIndex = schema.set;
    if (setIndex !== undefined) {
      const setData = data[setIndex];
      if (setData && typeof setData === 'object') {
        setKey = setData.key || 'default';
        const titleIndex = setData.title;
        if (titleIndex !== undefined) {
          setTitle = data[titleIndex] || 'Default';
        }
      }
    }

    // Определяем тип бойца
    let fighterType = 'HERO';
    if (attack === 'range') fighterType = 'HERO';
    else if (attack === 'melee') fighterType = 'HERO';

    return {
      name,
      key,
      startHealth,
      attack,
      specialAbility,
      description,
      cardBackImage,
      miniatureImage,
      avatar,
      color,
      setKey,
      setTitle,
      fighterType,
    };
  } catch (error) {
    console.error(`Error parsing hero file ${filePath}:`, error);
    return null;
  }
}

async function importHeroes() {
  console.log('\n🦸 Импорт героев...');

  const heroesDir = HEROES_DATA_PATH;
  if (!fs.existsSync(heroesDir)) {
    console.log('⏭️  Папка heroes не найдена');
    return;
  }

  const files = fs.readdirSync(heroesDir).filter(f => f.endsWith('.json'));
  console.log(`   Найдено ${files.length} файлов героев`);

  let imported = 0;
  let skipped = 0;
  let errors = 0;

  for (const file of files) {
    try {
      const filePath = path.join(heroesDir, file);
      const normalizedPath = path.join(NORMALIZED_PATH, file);

      // Пытаемся загрузить нормализованные данные для дополнительной информации
      let normalizedData: HeroData | undefined;
      if (fs.existsSync(normalizedPath)) {
        try {
          normalizedData = JSON.parse(fs.readFileSync(normalizedPath, 'utf-8'));
        } catch {
          // Игнорируем ошибки чтения нормализованных данных
        }
      }

      const heroData = parseHeroFile(filePath, normalizedData);

      if (!heroData) {
        console.log(`   ⚠️  Не удалось распарсить: ${file}`);
        errors++;
        continue;
      }

      // Проверяем существование героя
      const existingHero = await prisma.hero.findFirst({
        where: {
          OR: [
            { name: heroData.name },
            { id: heroData.key },
          ],
        },
      });

      if (existingHero) {
        skipped++;
        console.log(`   ⏭️  Пропущен (существует): ${heroData.name}`);
        continue;
      }

      // Создаем героя
      await prisma.hero.create({
        data: {
          id: heroData.key,
          name: heroData.name,
          nameEn: heroData.name,
          nameRu: heroData.name,
          set: heroData.setTitle,
          health: heroData.startHealth,
          fighterType: heroData.fighterType,
          ability: {
            type: heroData.attack,
            timing: 'DURING_COMBAT',
            effect: heroData.specialAbility,
            description: heroData.description,
          },
          deckCards: [],
          properties: {
            color: heroData.color,
            key: heroData.key,
          },
          imageUrl: heroData.cardBackImage || heroData.avatar,
          avatarUrl: heroData.avatar,
        },
      });

      imported++;
      console.log(`   ✅ Импортирован: ${heroData.name} (${heroData.startHealth} HP, ${heroData.attack})`);
    } catch (error) {
      console.error(`   ❌ Ошибка при импорте ${file}:`, error);
      errors++;
    }
  }

  console.log(`🦸 Герои: ${imported} импортировано, ${skipped} пропущено, ${errors} ошибок`);
}

async function main() {
  console.log('🌱 Seed: Импорт героев из scraped-data...\n');

  await importHeroes();

  const heroCount = await prisma.hero.count();
  const cardCount = await prisma.card.count();
  const boardCount = await prisma.board.count();

  console.log('\n📊 Статистика БД после импорта:');
  console.log(`   🦸 Героев: ${heroCount}`);
  console.log(`   🃏 Карт: ${cardCount}`);
  console.log(`   🗺️  Досок: ${boardCount}`);
  console.log('\n✅ Импорт героев завершен!');
}

main()
  .catch((e) => {
    console.error('❌ Seed error:', e);
    process.exit(1);
  })
  .finally(async () => {
    await prisma.$disconnect();
  });
