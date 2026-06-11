import { PrismaClient } from '@prisma/client';
import * as fs from 'fs';
import * as path from 'path';

const prisma = new PrismaClient();

const SCRAPED_DATA_PATH = path.join(__dirname, '../../scraped-data/api/heroes');

interface ParsedCard {
  id: number;
  title: string;
  type: string;
  value: number | null;
  boostValue: number | null;
  copies: number;
  effect: string | null;
  image?: string;
  imageRu?: string;
}

interface ParsedHero {
  name: string;
  deck: ParsedCard[];
}

function resolveValue(data: any[], index: number | null | undefined): any {
  if (index === null || index === undefined || index < 0) return null;
  return data[index];
}

function parseHeroData(rawData: any): ParsedHero | null {
  try {
    const nodes = rawData.nodes;
    if (!nodes || nodes.length < 3 || !nodes[2] || !nodes[2].data) return null;

    const data = nodes[2].data as any[];
    const heroSchema = data[1];

    if (!heroSchema || typeof heroSchema !== 'object') return null;

    const hero: ParsedHero = {
      name: resolveValue(data, heroSchema.name) || 'Unknown',
      deck: parseDeckData(data),
    };

    return hero;
  } catch (error) {
    console.error('Error parsing hero data:', error);
    return null;
  }
}

function parseDeckData(data: any[]): ParsedCard[] {
  const cards: ParsedCard[] = [];

  try {
    for (let i = 0; i < data.length; i++) {
      const item = data[i];

      if (!item || typeof item !== 'object') continue;

      const heroId = item.hero;
      if (heroId !== 2 && heroId !== 1) continue;

      const cardIndex = item.card;
      if (cardIndex === null || cardIndex === undefined) continue;

      const cardSchema = resolveValue(data, cardIndex);
      if (!cardSchema || typeof cardSchema !== 'object') continue;

      const title = resolveValue(data, cardSchema.title);
      if (!title || typeof title !== 'string') continue;

      const card: ParsedCard = {
        id: cardSchema.id || i,
        title: title,
        type: resolveValue(data, cardSchema.type) || 'versatile',
        value: resolveValue(data, cardSchema.value) || null,
        boostValue: resolveValue(data, cardSchema.boostValue) || null,
        copies: resolveValue(data, item.copies) || item.copies || 1,
        effect: resolveValue(data, cardSchema.effect) || null,
        image: resolveValue(data, cardSchema.image) || null,
      };

      // Извлекаем русское изображение из i18n
      const i18nData = resolveValue(data, cardSchema.i18n);
      if (i18nData && typeof i18nData === 'object' && i18nData.ru !== undefined) {
        const ruIndex = i18nData.ru;
        if (typeof ruIndex === 'number') {
          const ruData = resolveValue(data, ruIndex);
          if (ruData && typeof ruData === 'object' && ruData.image !== undefined) {
            const ruImageIndex = ruData.image;
            if (typeof ruImageIndex === 'number') {
              card.imageRu = resolveValue(data, ruImageIndex) || null;
            }
          }
        }
      }

      cards.push(card);
    }
  } catch (error) {
    console.error('Error parsing deck data:', error);
  }

  return cards;
}

async function updateHeroCards(heroKey: string) {
  const filePath = path.join(SCRAPED_DATA_PATH, `${heroKey}.json`);

  if (!fs.existsSync(filePath)) {
    return;
  }

  try {
    const rawData = fs.readFileSync(filePath, 'utf-8');
    const parsed = JSON.parse(rawData);

    const hero = parseHeroData(parsed);

    if (!hero) {
      console.log(`⚠️  Пропуск: ${heroKey} (не удалось распарсить)`);
      return;
    }

    console.log(`📖 Обновление карт для: ${hero.name}`);

    // Находим героя в БД
    const existingHero = await prisma.hero.findFirst({
      where: {
        name: {
          contains: hero.name,
          mode: 'insensitive',
        },
      },
    });

    if (!existingHero) {
      console.log(`⏭️  Пропуск: ${hero.name} (не найден в БД)`);
      return;
    }

    let updatedCount = 0;

    for (const card of hero.deck) {
      if (!card.title) continue;

      // Ищем карту по названию и heroId
      const existingCard = await prisma.card.findFirst({
        where: {
          heroId: existingHero.id,
          OR: [
            { name: { contains: card.title, mode: 'insensitive' } },
            { nameEn: { contains: card.title, mode: 'insensitive' } },
          ],
        },
      });

      if (!existingCard) {
        console.log(`   ⚠️  Карта не найдена: ${card.title}`);
        continue;
      }

      // Обновляем только если есть изображение и его ещё нет в БД
      if ((card.image || card.imageRu) && (!existingCard.imageUrl && !existingCard.imageUrlRu)) {
        await prisma.card.update({
          where: { id: existingCard.id },
          data: {
            imageUrl: card.image || existingCard.imageUrl,
            imageUrlRu: card.imageRu || existingCard.imageUrlRu,
          },
        });
        updatedCount++;
        console.log(`   ✅ Обновлена карта: ${card.title}`);
      }
    }

    if (updatedCount === 0) {
      console.log(`   ℹ️  Все карты уже имеют изображения`);
    } else {
      console.log(`   ✅ Обновлено ${updatedCount} карт`);
    }

  } catch (error) {
    console.error(`❌ Ошибка при обновлении ${heroKey}:`, error);
  }
}

async function main() {
  console.log('🔄 Обновление изображений карт...\n');

  const heroKeys = [
    'winter-soldier', 'yennenga', 'ms-marvel', 'black-widow', 'black-panther',
    'daredevil', 'spiderman', 'deadpool', 'doctor-strange', 'hells-kitchen',
    'for-king-and-country', 'teen-spirit', 'the-witcher-realms-fall', 'the-witcher-steel-silver',
    'yennefer-triss',
  ];

  let successCount = 0;
  let skipCount = 0;
  let errorCount = 0;

  for (const heroKey of heroKeys) {
    try {
      const filePath = path.join(SCRAPED_DATA_PATH, `${heroKey}.json`);
      if (!fs.existsSync(filePath)) {
        skipCount++;
        continue;
      }

      await updateHeroCards(heroKey);
      successCount++;
    } catch (error) {
      console.error(`❌ Ошибка при обработке ${heroKey}:`, error);
      errorCount++;
    }
  }

  console.log('\n📊 Статистика обновления:');
  console.log(`   ✅ Обработано: ${successCount} героев`);
  console.log(`   ⏭️  Пропущено: ${skipCount} файлов`);
  console.log(`   ❌ Ошибок: ${errorCount}`);

  // Проверяем сколько карт теперь имеют изображения
  const cardsWithImages = await prisma.card.count({
    where: {
      OR: [
        { imageUrl: { not: null } },
        { imageUrlRu: { not: null } },
      ],
    },
  });

  const totalCards = await prisma.card.count();

  console.log(`\n🎮 Карты с изображениями: ${cardsWithImages} из ${totalCards}`);
}

main()
  .catch((e) => {
    console.error('❌ Update error:', e);
    process.exit(1);
  })
  .finally(async () => {
    await prisma.$disconnect();
  });
