const { PrismaClient } = require('@prisma/client');
const prisma = new PrismaClient();

async function check() {
  const hero = await prisma.hero.findUnique({
    where: { name: 'Yennenga' },
    include: { cards: true }
  });

  console.log('Hero:', hero.name);
  console.log('Cards in relation:', hero.cards.length);
  console.log('deckCards field:', JSON.stringify(hero.deckCards));
  console.log('\nCard list:');
  hero.cards.forEach(c => console.log(` - ${c.name} x${c.count} (${c.cardType})`));

  await prisma.$disconnect();
}

check().catch(console.error);
