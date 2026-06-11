/**
 * Скрипт для загрузки данных карт с API unmatched.cards
 * и обновления базы данных
 */

const { PrismaClient } = require('@prisma/client');
const https = require('https');

const prisma = new PrismaClient();

// Карта типов из API в нашу систему
const TYPE_MAP = {
  'attack': 'ATTACK',
  'defense': 'DEFENSE',
  'scheme': 'SCHEME',
  'versatile': 'MANEUVER',
};

// Получение данных с API
function fetchJSON(url) {
  return new Promise((resolve, reject) => {
    https.get(url, (res) => {
      let data = '';
      res.on('data', (chunk) => data += chunk);
      res.on('end', () => {
        try {
          resolve(JSON.parse(data));
        } catch (e) {
          reject(e);
        }
      });
    }).on('error', reject);
  });
}

async function getHeroDeckFromAPI(heroSlug) {
  const url = `https://unmatched.cards/api/db/decks/${heroSlug}`;
  try {
    return await fetchJSON(url);
  } catch (e) {
    console.error(`   ❌ Ошибка при загрузке ${heroSlug}:`, e.message);
    return null;
  }
}

async function updateCardsForHero(heroName, heroSlug) {
  console.log(`\n📖 Загрузка данных: ${heroSlug}`);

  const deckData = await getHeroDeckFromAPI(heroSlug);

  if (!deckData || !deckData.cards) {
    console.log(`   ⚠️  Нет данных для ${heroSlug}`);
    return { updated: 0, notFound: 0 };
  }

  let updated = 0;
  let notFound = 0;

  for (const cardData of deckData.cards) {
    // Ищем карту по имени
    const existingCard = await prisma.card.findFirst({
      where: {
        name: cardData.title,
        hero: {
          name: heroName,
        },
      },
    });

    if (!existingCard) {
      console.log(`   ⚠️  Не найдена карта: ${cardData.title}`);
      notFound++;
      continue;
    }

    // Определяем значения
    const cardType = TYPE_MAP[cardData.type] || 'MANEUVER';
    let attackValue = null;
    let defenseValue = null;
    let boostValue = cardData.boost;

    if (cardType === 'ATTACK') {
      attackValue = cardData.value;
    } else if (cardType === 'DEFENSE') {
      defenseValue = cardData.value;
    }

    // Эффекты
    const effectImmediately = cardData.immediateText || null;
    const effectDuring = cardData.duringText || null;
    const effectAfter = cardData.afterText || null;
    const basicText = cardData.basicText || null;

    // Проверяем нужно ли обновлять
    const needsUpdate =
      existingCard.cardType !== cardType ||
      existingCard.attackValue !== attackValue ||
      existingCard.defenseValue !== defenseValue ||
      existingCard.boostValue !== boostValue ||
      existingCard.bannerName !== (cardData.characterName || null) ||
      existingCard.effectImmediately !== effectImmediately ||
      existingCard.effectDuring !== effectDuring ||
      existingCard.effectAfter !== effectAfter;

    if (needsUpdate) {
      await prisma.card.update({
        where: { id: existingCard.id },
        data: {
          cardType,
          attackValue,
          defenseValue,
          boostValue,
          bannerName: cardData.characterName || heroName.toUpperCase(),
          effectImmediately,
          effectDuring,
          effectAfter,
          text: basicText,
        },
      });

      updated++;
      console.log(`   ✅ ${cardData.title}: ${cardType} VAL:${cardData.value} BST:${cardData.boost}`);
    } else {
      console.log(`   ⏭️  ${cardData.title} (уже актуально)`);
    }
  }

  return { updated, notFound };
}

// Список героёв и их slugs
const HEROES_SLUGS = {
  'Daredevil': 'daredevil',
  'Ms. Marvel': 'ms-marvel',
  'Jekyll & Hyde': 'jekyll-hyde',
  'Achilles': 'achilles',
  'Alice': 'alice',
  'Bigfoot': 'bigfoot',
  'Black Panther': 'black-panther',
  'Black Widow': 'black-widow',
  'Dracula': 'dracula',
  'King Arthur': 'king-arthur',
  'Medusa': 'medusa',
  'Robin Hood': 'robin-hood',
  'Sherlock Holmes': 'sherlock-holmes',
  'Sinbad': 'sinbad',
  'Beowulf': 'beowulf',
  'Bruce Lee': 'bruce-lee',
  'Angel': 'angel',
  'Willow': 'willow',
  'Buffy': 'buffy',
  'Dr. Jill Trent': 'dr-ellie-sattler',
  'Doctor Strange': 'doctor_strange',
  'Bloody Mary': 'bloody-mary',
};

async function main() {
  console.log('🔄 Загрузка данных карт с unmatched.cards API...\n');

  let totalUpdated = 0;
  let totalNotFound = 0;

  for (const [heroName, heroSlug] of Object.entries(HEROES_SLUGS)) {
    const result = await updateCardsForHero(heroName, heroSlug);
    totalUpdated += result.updated;
    totalNotFound += result.notFound;
  }

  console.log('\n📊 Результаты:');
  console.log(`   ✅ Обновлено карт: ${totalUpdated}`);
  console.log(`   ⚠️  Не найдено в БД: ${totalNotFound}`);

  // Статистика по типам карт
  const [attackCards, defenseCards, schemeCards, versatileCards, cardsWithBoost] = await Promise.all([
    prisma.card.count({ where: { cardType: 'ATTACK' } }),
    prisma.card.count({ where: { cardType: 'DEFENSE' } }),
    prisma.card.count({ where: { cardType: 'SCHEME' } }),
    prisma.card.count({ where: { cardType: 'MANEUVER' } }),
    prisma.card.count({ where: { boostValue: { not: null } } }),
  ]);

  console.log('\n📈 Статистика БД:');
  console.log(`   🗡️  ATTACK: ${attackCards}`);
  console.log(`   🛡️  DEFENSE: ${defenseCards}`);
  console.log(`   📜 SCHEME: ${schemeCards}`);
  console.log(`   🏃 MANEUVER: ${versatileCards}`);
  console.log(`   ⬆️  С boostValue: ${cardsWithBoost}`);
}

main()
  .catch((e) => {
    console.error('❌ Error:', e);
    process.exit(1);
  })
  .finally(async () => {
    await prisma.$disconnect();
  });
