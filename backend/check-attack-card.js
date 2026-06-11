const { PrismaClient } = require('@prisma/client');
const prisma = new PrismaClient();

async function main() {
  const card = await prisma.card.findFirst({
    where: { cardType: 'ATTACK' }
  });
  console.log(JSON.stringify(card, null, 2));
}

main()
  .catch(console.error)
  .finally(() => prisma.$disconnect());
