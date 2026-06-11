/**
 * Скрипт для обновления значений карт на основе данных с unmatched.cards
 * Данные были получены через ручной парсинг сайта
 */

const { PrismaClient } = require('@prisma/client');
const prisma = new PrismaClient();

// Данные карт с unmatched.cards
// Формат: { name, count, type, value, boost }
const HEROES_CARDS = {
  'Daredevil': [
    { name: 'Through Adversity', count: 3, value: 2, boost: 0 },
    { name: 'Man Without Fear', count: 2, value: 2, boost: 3 },
    { name: 'Son Of A Boxer', count: 3, value: 3, boost: 2 },
    { name: 'Feint', count: 3, value: 2, boost: 1 },
    { name: 'Take A Knee', count: 3, value: 3, boost: 2 },
    { name: 'Grappling Hook', count: 3, value: 3, boost: 2 },
    { name: 'Breather', count: 3, value: null, boost: 2 },
    { name: 'Devil of Hell\'s Kitchen', count: 2, value: 4, boost: 3 },
  ],
};

// Карта типов по названию (пока все VERSATILE/MANEUVER)
// TODO: определить правильные типы
function guessCardType(name, value) {
  // Если есть value > 0, определяем тип по контексту
  // Но для Unmatched большинство карт - versatile (манёвры)
  return 'MANEUVER'; // По умолчанию
}

async function updateCardsForHero(heroName, cardsData) {
  console.log(`\n📖 Обработка героя: ${heroName}`);

  let updated = 0;
  let notFound = 0;

  for (const cardData of cardsData) {
    // Ищем карту по имени (экранируем специальные символы)
    const existingCard = await prisma.card.findFirst({
      where: {
        name: cardData.name,
        hero: {
          name: heroName,
        },
      },
    });

    if (!existingCard) {
      // Попробуем найти по частичному совпадению
      const similarCards = await prisma.card.findMany({
        where: {
          hero: {
            name: heroName,
          },
          name: {
            contains: cardData.name.split(' ')[0], // первое слово
          },
        },
        take: 5,
      });

      if (similarCards.length > 0) {
        console.log(`   ⚠️  Возможно совпадение для "${cardData.name}": ${similarCards.map(c => c.name).join(', ')}`);
      } else {
        console.log(`   ⚠️  Не найдена карта: ${cardData.name}`);
      }
      notFound++;
      continue;
    }

    // Определяем значения
    let attackValue = null;
    let defenseValue = null;
    let boostValue = cardData.boost;

    // Если есть value, определяем тип карты
    // Для Unmatched большинство карт versatile (MANEUVER)
    // Но нужно уточнить тип для каждой карты

    // Проверяем нужно ли обновлять
    const needsUpdate =
      existingCard.attackValue !== attackValue ||
      existingCard.defenseValue !== defenseValue ||
      existingCard.boostValue !== boostValue;

    if (needsUpdate) {
      await prisma.card.update({
        where: { id: existingCard.id },
        data: {
          attackValue,
          defenseValue,
          boostValue,
          bannerName: heroName.toUpperCase(),
        },
      });

      updated++;
      console.log(`   ✅ Обновлена карта: ${cardData.name}`);
      console.log(`      ATK: ${existingCard.attackValue} -> ${attackValue}`);
      console.log(`      DEF: ${existingCard.defenseValue} -> ${defenseValue}`);
      console.log(`      BST: ${existingCard.boostValue} -> ${boostValue}`);
    } else {
      console.log(`   ⏭️  Пропуск: ${cardData.name} (уже актуально)`);
    }
  }

  return { updated, notFound };
}

async function main() {
  console.log('🔄 Обновление значений карт из unmatched.cards...\n');

  let totalUpdated = 0;
  let totalNotFound = 0;

  for (const [heroName, cardsData] of Object.entries(HEROES_CARDS)) {
    const result = await updateCardsForHero(heroName, cardsData);
    totalUpdated += result.updated;
    totalNotFound += result.notFound;
  }

  console.log('\n📊 Результаты:');
  console.log(`   ✅ Обновлено карт: ${totalUpdated}`);
  console.log(`   ⚠️  Не найдено в БД: ${totalNotFound}`);

  // Статистика по БД
  const [cardsWithAttack, cardsWithDefense, cardsWithBoost] = await Promise.all([
    prisma.card.count({ where: { attackValue: { not: null } } }),
    prisma.card.count({ where: { defenseValue: { not: null } } }),
    prisma.card.count({ where: { boostValue: { not: null } } }),
  ]);

  console.log('\n📈 Статистика БД после обновления:');
  console.log(`   📊 С attackValue: ${cardsWithAttack}`);
  console.log(`   📊 С defenseValue: ${cardsWithDefense}`);
  console.log(`   📊 С boostValue: ${cardsWithBoost}`);

  console.log('\n⚠️  Внимание: Обновлены только карты Daredevil!');
  console.log('   Для остальных героев нужно добавить данные.');
  console.log('   Данные можно получить с https://unmatched.cards');
}

main()
  .catch((e) => {
    console.error('❌ Error:', e);
    process.exit(1);
  })
  .finally(async () => {
    await prisma.$disconnect();
  });
