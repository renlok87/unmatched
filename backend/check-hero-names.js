const { PrismaClient } = require('@prisma/client');
const prisma = new PrismaClient();

async function main() {
  const heroes = await prisma.hero.findMany({
    select: { name: true },
    orderBy: { name: 'asc' }
  });
  console.log('Heroes in DB:');
  heroes.forEach(h => console.log(`  - ${h.name}`));
  console.log(`\nTotal: ${heroes.length}`);
}

main()
  .catch(console.error)
  .finally(() => prisma.$disconnect());
