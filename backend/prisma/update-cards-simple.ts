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

function parseScrapedHero(heroKey: string): { name: string; cards: ScrapedCard[] } | null {
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

async function main() {
  console.log('🔄 Updating card images...\n');

  const heroKey = 'winter-soldier';
  const scraped = parseScrapedHero(heroKey);

  if (!scraped) {
    console.log('Failed to parse scraped data');
    return;
  }

  console.log(`Hero: ${scraped.name}`);
  console.log(`Found ${scraped.cards.length} cards in scraped data\n`);

  // Find hero in DB
  const hero = await prisma.hero.findFirst({
    where: {
      name: { contains: 'Winter', mode: 'insensitive' },
    },
  });

  if (!hero) {
    console.log('Hero not found in DB');
    return;
  }

  console.log(`DB Hero ID: ${hero.id}, Name: ${hero.name}\n`);

  // Get all cards for this hero
  const dbCards = await prisma.card.findMany({
    where: { heroId: hero.id },
  });

  console.log(`Found ${dbCards.length} cards in DB\n`);

  let updated = 0;

  for (const dbCard of dbCards) {
    // Find matching scraped card
    const scrapedCard = scraped.cards.find(
      sc => sc.title === dbCard.name || sc.title === dbCard.nameEn
    );

    if (scrapedCard) {
      console.log(`\nCard: ${dbCard.name}`);
      console.log(`  Scraped image: ${scrapedCard?.image || 'none'}`);
      console.log(`  Scraped imageRu: ${scrapedCard?.imageRu || 'none'}`);
      console.log(`  DB imageUrl: ${dbCard.imageUrl || 'none'}`);
      console.log(`  DB imageUrlRu: ${dbCard.imageUrlRu || 'none'}`);

      if ((scrapedCard.image || scrapedCard.imageRu) && !dbCard.imageUrl && !dbCard.imageUrlRu) {
        await prisma.card.update({
          where: { id: dbCard.id },
          data: {
            imageUrl: scrapedCard.image,
            imageUrlRu: scrapedCard.imageRu,
          },
        });
        console.log(`  ✅ Updated!`);
        updated++;
      } else {
        console.log(`  ⏭️ Skipped (already has images)`);
      }
    }
  }

  console.log(`\n✅ Updated ${updated} cards`);

  await prisma.$disconnect();
}

main().catch(console.error);
