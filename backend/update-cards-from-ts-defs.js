/**
 * Скрипт для обновления значений карт на основе TypeScript определений
 * Обновляет cardType, attackValue, defenseValue, boostValue, bannerName для существующих карт
 */

const { PrismaClient } = require('@prisma/client');

const prisma = new PrismaClient();

// Данные героёй из TypeScript файлов
const HEROES_DATA = {
  'Daredevil': {
    deckCards: [
      {
        id: 'billy-club',
        title: 'Billy Club',
        type: 'versatile',
        value: 3,
        boost: 2,
        characterName: 'DAREDEVIL',
      },
      {
        id: 'radar-sense',
        title: 'Radar Sense',
        type: 'attack',
        value: 4,
        boost: 1,
        characterName: 'DAREDEVIL',
      },
      {
        id: 'mania',
        title: 'Mania',
        type: 'attack',
        value: 2,
        boost: 3,
        characterName: 'DAREDEVIL',
      },
      {
        id: 'grappling-hook',
        title: 'Grappling Hook',
        type: 'versatile',
        value: 2,
        boost: 2,
        characterName: 'DAREDEVIL',
      },
      {
        id: 'daredevil',
        title: 'Daredevil',
        type: 'defense',
        value: 4,
        boost: 1,
        characterName: 'DAREDEVIL',
      },
    ],
  },
  'Ms. Marvel': {
    deckCards: [
      {
        id: 'embiggen',
        title: 'Embiggen',
        type: 'attack',
        value: 3,
        boost: 2,
        characterName: 'MS MARVEL',
      },
      {
        id: 'stretch',
        title: 'Stretch',
        type: 'defense',
        value: 3,
        boost: 2,
        characterName: 'MS MARVEL',
      },
      {
        id: 'punch',
        title: 'Punch',
        type: 'attack',
        value: 4,
        boost: 1,
        characterName: 'MS MARVEL',
      },
      {
        id: 'dodge',
        title: 'Dodge',
        type: 'defense',
        value: 4,
        boost: 1,
        characterName: 'MS MARVEL',
      },
      {
        id: 'morph',
        title: 'Morph',
        type: 'versatile',
        value: 3,
        boost: 2,
        characterName: 'MS MARVEL',
      },
    ],
  },
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

    // Проверяем нужно ли обновлять
    const needsTypeUpdate = existingCard.cardType !== cardType;
    const needsValueUpdate =
      existingCard.attackValue !== attackValue ||
      existingCard.defenseValue !== defenseValue ||
      existingCard.boostValue !== boostValue ||
      existingCard.bannerName !== cardDef.characterName;

    if (needsTypeUpdate || needsValueUpdate) {
      await prisma.card.update({
        where: { id: existingCard.id },
        data: {
          cardType,
          attackValue,
          defenseValue,
          boostValue,
          bannerName: cardDef.characterName,
        },
      });

      updated++;
      console.log(`   ✅ Обновлена карта: ${cardDef.title}`);
      console.log(`      Тип: ${existingCard.cardType} -> ${cardType}`);
      console.log(`      ATK: ${existingCard.attackValue} -> ${attackValue}`);
      console.log(`      DEF: ${existingCard.defenseValue} -> ${defenseValue}`);
      console.log(`      BST: ${existingCard.boostValue} -> ${boostValue}`);
      console.log(`      Banner: ${existingCard.bannerName} -> ${cardDef.characterName}`);
    } else {
      console.log(`   ⏭️  Пропуск: ${cardDef.title} (уже актуально)`);
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

  console.log('\n⚠️  Внимание: Обновлены только Daredevil и Ms. Marvel!');
  console.log('   Для остальных героев нужно добавить данные в TypeScript файлы или вручную.');
}

main()
  .catch((e) => {
    console.error('❌ Error:', e);
    process.exit(1);
  })
  .finally(async () => {
    await prisma.$disconnect();
  });
