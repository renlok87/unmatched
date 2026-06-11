const { PrismaClient } = require('@prisma/client');
const prisma = new PrismaClient();

async function main() {
  const cards = await prisma.card.findMany({
    select: { name: true, cardType: true, hero: { select: { name: true } } },
    orderBy: { hero: { name: 'asc' } },
    take: 50
  });
  console.log('First 50 cards in DB:');
  cards.forEach(c => console.log(`  [${c.hero?.name || 'no hero'}] ${c.name} (${c.cardType})`));
}

main()
  .catch(console.error)
  .finally(() => prisma.$disconnect());
