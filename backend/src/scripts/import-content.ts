import { PrismaClient } from '@prisma/client';
import fs from 'fs/promises';
import path from 'path';

const prisma = new PrismaClient();

/**
 * Скрипт импорта героев из scraped-data/api/normalized/
 */
async function importHeroes() {
  console.log('🔍 Importing heroes from scraped-data...');

  const normalizedDir = path.join(process.cwd(), '../scraped-data/api/normalized');

  try {
    await fs.access(normalizedDir);
  } catch {
    console.error(`❌ Directory not found: ${normalizedDir}`);
    console.log('   Make sure scraped-data is in the project root.');
    return { created: 0, updated: 0, errors: 'Directory not found' };
  }

  const files = await fs.readdir(normalizedDir);
  const jsonFiles = files.filter((f) => f.endsWith('.json') && !f.startsWith('data'));

  let created = 0;
  let updated = 0;
  const errors: string[] = [];

  for (const file of jsonFiles) {
    try {
      const filePath = path.join(normalizedDir, file);
      const content = await fs.readFile(filePath, 'utf-8');
      const data = JSON.parse(content);

      // Extract hero slug from filename
      const slug = file.replace('.json', '');
      const name = data.name || slug;

      // Parse URLs
      const avatarUrl = data.urls?.avatar || null;
      const imageUrl = data.urls?.cardCover || avatarUrl;

      // Parse deck cards - store as JSON string
      const deckCardsJson = JSON.stringify(
        (data.cards || []).map((card: any, index: number) => ({
          id: `${slug}-card-${index}`,
          name: `${name} Card ${index + 1}`,
          nameEn: `${name} Card ${index + 1}`,
          nameRu: `${name} Карта ${index + 1}`,
          cardType: 'VERSATILE',
          value: 0,
          count: 1,
          imageUrl: card.url || null,
        }))
      );

      // Create or update hero
      const hero = await prisma.hero.upsert({
        where: { name: slug },
        update: {
          nameEn: name,
          nameRu: name,
          imageUrl,
          avatarUrl,
          deckCards: deckCardsJson,
        },
        create: {
          name: slug,
          nameEn: name,
          nameRu: name,
          set: 'imported',
          health: 15,
          fighterType: 'HERO',
          ability: {},
          deckCards: deckCardsJson,
          imageUrl,
          avatarUrl,
        },
      });

      if (hero.createdAt.getTime() === hero.updatedAt.getTime()) {
        created++;
      } else {
        updated++;
      }

      console.log(`   ✓ ${slug}`);
    } catch (error) {
      errors.push(`${file}: ${error.message}`);
      console.error(`   ✗ ${file}: ${error.message}`);
    }
  }

  console.log(`\n📊 Heroes import complete:`);
  console.log(`   Created: ${created}`);
  console.log(`   Updated: ${updated}`);
  console.log(`   Errors: ${errors.length}`);

  return { created, updated, errors: errors.join('; ') };
}

/**
 * Скрипт импорта карточек из scraped-data
 */
async function importCards() {
  console.log('🔍 Importing cards from scraped-data...');

  const normalizedDir = path.join(process.cwd(), '../scraped-data/api/normalized');

  const files = await fs.readdir(normalizedDir);
  const jsonFiles = files.filter((f) => f.endsWith('.json') && !f.startsWith('data'));

  let created = 0;
  let updated = 0;
  const errors: string[] = [];

  for (const file of jsonFiles) {
    try {
      const filePath = path.join(normalizedDir, file);
      const content = await fs.readFile(filePath, 'utf-8');
      const data = JSON.parse(content);

      const heroSlug = file.replace('.json', '');
      const heroName = data.name || heroSlug;

      // Find or create hero first
      const hero = await prisma.hero.upsert({
        where: { name: heroSlug },
        update: {},
        create: {
          name: heroSlug,
          nameEn: heroName,
          nameRu: heroName,
          set: 'imported',
          health: 15,
          fighterType: 'HERO',
          ability: {},
          deckCards: '[]',
        },
      });

      // Import cards
      const cards = data.cards || [];
      for (const card of cards) {
        const cardId = `${heroSlug}-${card.id}`;

        await prisma.card.upsert({
          where: { id: cardId },
          update: {
            name: `${heroName} Card ${card.id}`,
            nameEn: `${heroName} Card ${card.id}`,
            nameRu: `${heroName} Карта ${card.id}`,
          },
          create: {
            id: cardId,
            name: `${heroName} Card ${card.id}`,
            nameEn: `${heroName} Card ${card.id}`,
            nameRu: `${heroName} Карта ${card.id}`,
            heroId: hero.id,
            cardType: 'VERSATILE',
            boostValue: 0,
            count: 1,
            effects: [],
            text: `Image URL: ${card.url || 'N/A'}`,
          },
        });

        created++;
      }
    } catch (error) {
      errors.push(`${file}: ${error.message}`);
    }
  }

  console.log(`\n📊 Cards import complete:`);
  console.log(`   Created: ${created}`);
  console.log(`   Updated: ${updated}`);
  console.log(`   Errors: ${errors.length}`);

  return { created, updated, errors: errors.join('; ') };
}

/*
 * Доски этот скрипт не импортирует. Синтетическая доска 'cobble-city' 6×6 удалена вместе с остальными
 * ненастоящими досками (docs/game-design/decisions/2026-10-04-real-boards-only.md): доски игры —
 * оригинальные карты (prisma/seed-env-map-boards.ts) и каталог настоящих карт (prisma/seed-all-scraped.ts).
 */

/**
 * Главный процесс импорта
 */
async function main() {
  console.log('🚀 Starting import from scraped-data...\n');

  try {
    const [heroesResult, cardsResult] = await Promise.all([importHeroes(), importCards()]);

    console.log('\n🎉 Import complete!');
    console.log('\n📋 Summary:');
    console.log(`   Heroes: ${heroesResult.created} created, ${heroesResult.updated} updated`);
    console.log(`   Cards: ${cardsResult.created} created, ${cardsResult.updated} updated`);

    if (heroesResult.errors || cardsResult.errors) {
      console.log('\n⚠️  Errors occurred:');
      if (heroesResult.errors) console.log(`   Heroes: ${heroesResult.errors}`);
      if (cardsResult.errors) console.log(`   Cards: ${cardsResult.errors}`);
    }
  } catch (error) {
    console.error('❌ Import failed:', error);
    process.exit(1);
  } finally {
    await prisma.$disconnect();
  }
}

main();
