import { PrismaClient } from '@prisma/client';

const prisma = new PrismaClient();

async function main() {
  const heroCount = await prisma.hero.count();
  const cardCount = await prisma.card.count();

  console.log('🎮 Состояние БД:');
  console.log(`   🦸 Героев: ${heroCount}`);
  console.log(`   🃏 Карт: ${cardCount}`);

  if (heroCount > 0) {
    const heroes = await prisma.hero.findMany({
      take: 25,
      select: { name: true, set: true },
      orderBy: { name: 'asc' }
    });

    console.log('\n📋 Первые 25 героев:');
    heroes.forEach(h => console.log(`   - ${h.name} (${h.set})`));

    // Проверим конкретных героев из scraped-data
    const scrapedHeroes = ['Achilles', 'Beowulf', 'Dracula', 'Geralt of Rivia', 'King Arthur'];
    console.log('\n🔍 Проверка героев из scraped-data:');
    for (const name of scrapedHeroes) {
      const hero = await prisma.hero.findFirst({
        where: { name: { equals: name, mode: 'insensitive' } }
      });
      console.log(`   ${hero ? '✅' : '❌'} ${name}`);
    }
  }
}

main()
  .catch(console.error)
  .finally(async () => {
    await prisma.$disconnect();
  });
