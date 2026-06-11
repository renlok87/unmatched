const { PrismaClient } = require('@prisma/client');
const prisma = new PrismaClient();

async function checkYennenga() {
  const hero = await prisma.hero.findUnique({
    where: { name: 'Yennenga' },
    include: { cards: true }
  });

  console.log('Hero:', hero?.name || 'NOT FOUND');
  console.log('Cards:', hero?.cards?.length || 0);

  if (hero?.cards) {
    hero.cards.forEach(c => {
      console.log(` - ${c.name} x${c.count} (${c.cardType})`);
    });
  }

  await prisma.$disconnect();
}

checkYennenga().catch(console.error);
