/**
 * Скрипт для обновления значений карт на основе TypeScript определений
 * Обновляет attackValue, defenseValue, boostValue для существующих карт
 */

const { PrismaClient } = require('@prisma/client');

// Импортируем данные героев
const { daredevil } = require('./src/content/data/heroes/daredevil');
const { msMarvel } = require('./src/content/data/heroes/ms-marvel');

const prisma = new PrismaClient();

const HEROES_DATA = {
  'Daredevil': daredevil,
  'Ms. Marvel': msMarvel,
};

function normalizeCardType(type) {
  const typeMap = {
    'attack': 'ATTACK',
    'defense': 'DEFENSE',
    'scheme': 'SCHEME',
    'versatile': 'MANEUVER',
  };
  return typeMap[type.toLowerCase()] || type.toUpperCase();
}

async function updateCardsFromHero(heroName, heroData) {
  console.log(`\n📖 Обработка героя: ${heroName}`);

  let updated = 0;
  let notFound = 0;

  for (const cardDef of heroData.deckCards) {
    // Ищем карту по имени и герою
    const existingCard = await prisma.card.findFirst({
      where: {
        name: cardDef.title,
        hero: {
          name: heroName,
        },
      },
    });

    if (!existingCard) {
      console.log(`   ⚠️  Не найдена карта: ${cardDef.title}`);
      notFound++;
      continue;
    }

    // Определяем значения
    const cardType = normalizeCardType(cardDef.type);
    let attackValue = null;
    let defenseValue = null;
    let boostValue = cardDef.boost;

    if (cardType === 'ATTACK') {
      attackValue = cardDef.value;
    } else if (cardType === 'DEFENSE') {
      defenseValue = cardDef.value;
    }

    // Проверяем нужно ли обновлять cardType
    const needsTypeUpdate = existingCard.cardType !== cardType;
    const needsValueUpdate =
      existingCard.attackValue !== attackValue ||
      existingCard.defenseValue !== defenseValue ||
      existingCard.boostValue !== boostValue;

    if (needsTypeUpdate || needsValueUpdate) {
      await prisma.card.update({
        where: { id: existingCard.id },
        data: {
          cardType,
          attackValue,
          defenseValue,
          boostValue,
          bannerName: cardDef.characterName || heroName,
        },
      });

      updated++;
      console.log(`   ✅ Обновлена карта: ${cardDef.title}`);
      console.log(`      Тип: ${existingCard.cardType} -> ${cardType}`);
      console.log(`      ATK: ${existingCard.attackValue} -> ${attackValue}`);
      console.log(`      DEF: ${existingCard.defenseValue} -> ${defenseValue}`);
      console.log(`      BST: ${existingCard.boostValue} -> ${boostValue}`);
    }
  }

  return { updated, notFound };
}

async function main() {
  console.log('🔄 Обновление значений карт из TypeScript определений...\n');

  let totalUpdated = 0;
  let totalNotFound = 0;

  for (const [heroName, heroData] of Object.entries(HEROES_DATA)) {
    const result = await updateCardsFromHero(heroName, heroData);
    totalUpdated += result.updated;
    totalNotFound += result.notFound;
  }

  console.log('\n📊 Результаты:');
  console.log(`   ✅ Обновлено карт: ${totalUpdated}`);
  console.log(`   ⚠️  Не найдено в БД: ${totalNotFound}`);

  // Статистика по БД
  const [cardsWithAttack, cardsWithDefense, cardsWithBoost, attackCards, defenseCards, maneuverCards] = await Promise.all([
    prisma.card.count({ where: { attackValue: { not: null } } }),
    prisma.card.count({ where: { defenseValue: { not: null } } }),
    prisma.card.count({ where: { boostValue: { not: null } } }),
    prisma.card.count({ where: { cardType: 'ATTACK' } }),
    prisma.card.count({ where: { cardType: 'DEFENSE' } }),
    prisma.card.count({ where: { cardType: 'MANEUVER' } }),
  ]);

  console.log('\n📈 Статистика БД после обновления:');
  console.log(`   🗡️  Карт типа ATTACK: ${attackCards}`);
  console.log(`   🛡️  Карт типа DEFENSE: ${defenseCards}`);
  console.log(`   🏃 Карт типа MANEUVER: ${maneuverCards}`);
  console.log(`   📊 С attackValue: ${cardsWithAttack}`);
  console.log(`   📊 С defenseValue: ${cardsWithDefense}`);
  console.log(`   📊 С boostValue: ${cardsWithBoost}`);
}

main()
  .catch((e) => {
    console.error('❌ Error:', e);
    process.exit(1);
  })
  .finally(async () => {
    await prisma.$disconnect();
  });
