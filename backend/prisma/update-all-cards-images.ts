import { PrismaClient } from '@prisma/client';
import * as fs from 'fs';
import * as path from 'path';

const prisma = new PrismaClient();

const SCRAPED_DATA_PATH = path.join(__dirname, '../../scraped-data/api/heroes');

interface ScrapedCard {
  title: string;
  image?: string;
  imageRu?: string;
}

interface ScrapedHero {
  name: string;
  cards: ScrapedCard[];
}

function parseScrapedHero(heroKey: string): ScrapedHero | null {
  const filePath = path.join(SCRAPED_DATA_PATH, `${heroKey}.json`);
  if (!fs.existsSync(filePath)) return null;

  try {
    const rawData = fs.readFileSync(filePath, 'utf-8');
    const parsed = JSON.parse(rawData);

    const nodes = parsed.nodes;
    if (!nodes || nodes.length < 3 || !nodes[2] || !nodes[2].data) return null;

    const data = nodes[2].data as any[];
    const heroSchema = data[1];

    if (!heroSchema || typeof heroSchema !== 'object') return null;

    const heroName = data[heroSchema.name] || 'Unknown';
    const cards: ScrapedCard[] = [];

    for (let i = 0; i < data.length; i++) {
      const item = data[i];
      if (!item || typeof item !== 'object') continue;

      const heroId = item.hero;
      if (heroId !== 2 && heroId !== 1) continue;

      const cardIndex = item.card;
      if (cardIndex === null || cardIndex === undefined) continue;

      const cardSchema = data[cardIndex];
      if (!cardSchema || typeof cardSchema !== 'object') continue;

      const titleIndex = cardSchema.title;
      if (!titleIndex) continue;

      const title = data[titleIndex];
      if (!title || typeof title !== 'string') continue;

      const card: ScrapedCard = {
        title: title,
        image: data[item.image] || null,
      };

      // Извлекаем русское изображение из i18n
      const i18nIndex = item.i18n;
      if (i18nIndex) {
        const i18nData = data[i18nIndex];
        if (i18nData && typeof i18nData === 'object' && i18nData.ru !== undefined) {
          const ruIndex = i18nData.ru;
          if (typeof ruIndex === 'number') {
            const ruData = data[ruIndex];
            if (ruData && typeof ruData === 'object' && ruData.image !== undefined) {
              const ruImageIndex = ruData.image;
              if (typeof ruImageIndex === 'number') {
                card.imageRu = data[ruImageIndex] || null;
              }
            }
          }
        }
      }

      cards.push(card);
    }

    return { name: heroName, cards };
  } catch (error) {
    console.error(`Error parsing ${heroKey}:`, error);
    return null;
  }
}

async function updateHeroCards(heroKey: string) {
  const scraped = parseScrapedHero(heroKey);

  if (!scraped || scraped.cards.length === 0) {
    return;
  }

  // Find hero in DB - try exact match first, then contains
  let hero = await prisma.hero.findFirst({
    where: {
      name: { equals: scraped.name, mode: 'insensitive' },
    },
  });

  if (!hero) {
    hero = await prisma.hero.findFirst({
      where: {
        name: { contains: scraped.name.split(' ')[0], mode: 'insensitive' },
      },
    });
  }

  if (!hero) {
    console.log(`⚠️  Hero not found in DB: ${scraped.name}`);
    return;
  }

  console.log(`📖 Processing: ${scraped.name} (DB: ${hero.name})`);

  // Get all cards for this hero
  const dbCards = await prisma.card.findMany({
    where: { heroId: hero.id },
  });

  let updated = 0;
  let skipped = 0;

  for (const dbCard of dbCards) {
    // Find matching scraped card
    const scrapedCard = scraped.cards.find(
      sc => sc.title === dbCard.name || sc.title === dbCard.nameEn
    );

    if (scrapedCard && (scrapedCard.image || scrapedCard.imageRu)) {
      if (!dbCard.imageUrl && !dbCard.imageUrlRu) {
        await prisma.card.update({
          where: { id: dbCard.id },
          data: {
            imageUrl: scrapedCard.image,
            imageUrlRu: scrapedCard.imageRu,
          },
        });
        updated++;
      } else {
        skipped++;
      }
    }
  }

  if (updated > 0) {
    console.log(`   ✅ Updated ${updated} cards (skipped ${skipped} already with images)`);
  } else {
    console.log(`   ⏭️  All ${skipped} cards already have images`);
  }
}

async function main() {
  console.log('🔄 Updating all card images...\n');

  // Get all available hero JSON files
  const files = fs.readdirSync(SCRAPED_DATA_PATH)
    .filter(f => f.endsWith('.json'))
    .map(f => f.replace('.json', ''));

  console.log(`Found ${files.length} hero files\n`);

  let processed = 0;
  let totalUpdated = 0;

  for (const heroKey of files) {
    try {
      const scraped = parseScrapedHero(heroKey);

      if (!scraped || scraped.cards.length === 0) {
        continue;
      }

      // Find hero in DB
      let hero = await prisma.hero.findFirst({
        where: {
          name: { equals: scraped.name, mode: 'insensitive' },
        },
      });

      if (!hero) {
        hero = await prisma.hero.findFirst({
          where: {
            name: { contains: scraped.name.split(' ')[0], mode: 'insensitive' },
          },
        });
      }

      if (!hero) {
        continue;
      }

      // Get all cards for this hero
      const dbCards = await prisma.card.findMany({
        where: { heroId: hero.id },
      });

      let updated = 0;

      for (const dbCard of dbCards) {
        const scrapedCard = scraped.cards.find(
          sc => sc.title === dbCard.name || sc.title === dbCard.nameEn
        );

        if (scrapedCard && (scrapedCard.image || scrapedCard.imageRu)) {
          if (!dbCard.imageUrl && !dbCard.imageUrlRu) {
            await prisma.card.update({
              where: { id: dbCard.id },
              data: {
                imageUrl: scrapedCard.image,
                imageUrlRu: scrapedCard.imageRu,
              },
            });
            updated++;
          }
        }
      }

      if (updated > 0) {
        console.log(`✅ ${scraped.name}: updated ${updated} cards`);
        totalUpdated += updated;
      }

      processed++;
    } catch (error) {
      console.error(`❌ Error processing ${heroKey}:`, error);
    }
  }

  console.log(`\n📊 Processed ${processed} heroes`);
  console.log(`✅ Updated ${totalUpdated} cards total`);

  // Final count
  const cardsWithImages = await prisma.card.count({
    where: {
      OR: [
        { imageUrl: { not: null } },
        { imageUrlRu: { not: null } },
      ],
    },
  });

  const totalCards = await prisma.card.count();

  console.log(`\n🎮 Cards with images: ${cardsWithImages} out of ${totalCards}`);

  await prisma.$disconnect();
}

main().catch(console.error);
