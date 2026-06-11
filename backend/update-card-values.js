/**
 * Скрипт для обновления значений карт на основе scraped данных
 * Обновляет attackValue, defenseValue, boostValue для существующих карт
 */

const { PrismaClient } = require('@prisma/client');
const fs = require('fs');
const path = require('path');

const prisma = new PrismaClient();
const SCRAPED_DATA_PATH = path.join(__dirname, '../scraped-data/api/heroes');

function resolveValue(data, index) {
  if (index === null || index === undefined || index < 0) return null;
  return data[index];
}

function normalizeCardType(type) {
  const typeMap = {
    'attack': 'ATTACK',
    'defense': 'DEFENSE',
    'scheme': 'SCHEME',
    'versatile': 'MANEUVER',
    'maneuver': 'MANEUVER',
  };
  return typeMap[type.toLowerCase()] || type.toUpperCase();
}

function parseHeroData(rawData) {
  try {
    const nodes = rawData.nodes;
    if (!nodes || nodes.length < 3 || !nodes[2] || !nodes[2].data) return null;

    const data = nodes[2].data;
    const heroSchema = data[1];

    if (!heroSchema || typeof heroSchema !== 'object') return null;

    const heroName = resolveValue(data, heroSchema.name) || 'Unknown';
    const heroKey = resolveValue(data, heroSchema.key) || '';

    const cards = [];

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

      const type = normalizeCardType(resolveValue(data, cardSchema.type) || 'versatile');
      const value = resolveValue(data, cardSchema.value) || null;
      const boostValue = resolveValue(data, cardSchema.boostValue) || null;
      const copies = resolveValue(data, item.copies) || item.copies || 1;

      cards.push({
        title,
        type,
        value,
        boostValue,
        copies,
        // Эффект-поля
        bannerName: resolveValue(data, item.bannerName) || heroName,
        effectAfter: resolveValue(data, cardSchema.effectAfter) || null,
        effectDuring: resolveValue(data, cardSchema.effectDuring) || null,
        effectBoost: resolveValue(data, cardSchema.effectBoost) || null,
        effectImmediately: resolveValue(data, cardSchema.effectImmediately) || null,
        effectOngoing: resolveValue(data, cardSchema.effectOngoing) || null,
      });
    }

    return { heroName, heroKey, cards };
  } catch (error) {
    console.error('Error parsing hero data:', error);
    return null;
  }
}

async function updateCardsFromScraped(heroKey) {
  const filePath = path.join(SCRAPED_DATA_PATH, `${heroKey}.json`);

  if (!fs.existsSync(filePath)) {
    return { updated: 0, notFound: 0 };
  }

  try {
    const rawData = fs.readFileSync(filePath, 'utf-8');
    const parsed = JSON.parse(rawData);

    const heroData = parseHeroData(parsed);
    if (!heroData) {
      return { updated: 0, notFound: 0 };
    }

    console.log(`\n📖 Обработка: ${heroData.heroName}`);

    let updated = 0;
    let notFound = 0;

    for (const scrapedCard of heroData.cards) {
      // Ищем карту по имени
      const existingCard = await prisma.card.findFirst({
        where: {
          name: scrapedCard.title,
          hero: {
            name: heroData.heroName,
          },
        },
      });

      if (!existingCard) {
        notFound++;
        continue;
      }

      // Определяем значения на основе типа карты
      let attackValue = null;
      let defenseValue = null;
      let boostValue = scrapedCard.boostValue;

      if (scrapedCard.type === 'ATTACK') {
        attackValue = scrapedCard.value;
      } else if (scrapedCard.type === 'DEFENSE') {
        defenseValue = scrapedCard.value;
      }

      // Проверяем, нужно ли обновлять
      const needsUpdate =
        existingCard.attackValue !== attackValue ||
        existingCard.defenseValue !== defenseValue ||
        existingCard.boostValue !== boostValue ||
        existingCard.bannerName !== scrapedCard.bannerName ||
        existingCard.effectAfter !== (scrapedCard.effectAfter || null) ||
        existingCard.effectDuring !== (scrapedCard.effectDuring || null) ||
        existingCard.effectBoost !== (scrapedCard.effectBoost || null) ||
        existingCard.effectImmediately !== (scrapedCard.effectImmediately || null) ||
        existingCard.effectOngoing !== (scrapedCard.effectOngoing || null);

      if (!needsUpdate) {
        continue;
      }

      await prisma.card.update({
        where: { id: existingCard.id },
        data: {
          attackValue,
          defenseValue,
          boostValue,
          bannerName: scrapedCard.bannerName,
          effectAfter: scrapedCard.effectAfter,
          effectDuring: scrapedCard.effectDuring,
          effectBoost: scrapedCard.effectBoost,
          effectImmediately: scrapedCard.effectImmediately,
          effectOngoing: scrapedCard.effectOngoing,
        },
      });

      updated++;
      console.log(`   ✅ Обновлена карта: ${scrapedCard.title} (${scrapedCard.type}) - ATK:${attackValue} DEF:${defenseValue} BST:${boostValue}`);
    }

    if (notFound > 0) {
      console.log(`   ⚠️  Не найдено в БД: ${notFound} карт`);
    }

    return { updated, notFound };
  } catch (error) {
    console.error(`❌ Ошибка при обработке ${heroKey}:`, error);
    return { updated: 0, notFound: 0, error: true };
  }
}

async function main() {
  console.log('🔄 Обновление значений карт на основе scraped данных...\n');

  const heroKeys = [
    'achilles', 'alice', 'ancient-leshen', 'angel', 'annie-christmas',
    'beowulf', 'bigfoot', 'black-panther', 'black-widow', 'blackbeard',
    'bloody-mary', 'bruce-lee', 'bullseye', 'chupacabra', 'ciri',
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
    'winter-soldier', 'yennefer-triss', 'yennenga'
  ];

  let totalUpdated = 0;
  let totalNotFound = 0;
  let errors = 0;

  for (const heroKey of heroKeys) {
    const result = await updateCardsFromScraped(heroKey);
    totalUpdated += result.updated;
    totalNotFound += result.notFound;
    if (result.error) errors++;
  }

  console.log('\n📊 Результаты:');
  console.log(`   ✅ Обновлено карт: ${totalUpdated}`);
  console.log(`   ⚠️  Не найдено в БД: ${totalNotFound}`);
  console.log(`   ❌ Ошибок: ${errors}`);

  // Статистика по БД
  const cardsWithAttack = await prisma.card.count({
    where: { attackValue: { not: null } }
  });
  const cardsWithDefense = await prisma.card.count({
    where: { defenseValue: { not: null } }
  });
  const cardsWithBoost = await prisma.card.count({
    where: { boostValue: { not: null } }
  });

  console.log('\n📈 Статистика БД после обновления:');
  console.log(`   🗡️  Карт с attackValue: ${cardsWithAttack}`);
  console.log(`   🛡️  Карт с defenseValue: ${cardsWithDefense}`);
  console.log(`   ⬆️  Карт с boostValue: ${cardsWithBoost}`);
}

main()
  .catch((e) => {
    console.error('❌ Error:', e);
    process.exit(1);
  })
  .finally(async () => {
    await prisma.$disconnect();
  });
