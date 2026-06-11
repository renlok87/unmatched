const { PrismaClient } = require('@prisma/client');
const prisma = new PrismaClient();

async function main() {
  const cards = await prisma.card.findMany({
    select: {
      id: true,
      name: true,
      cardType: true,
      attackValue: true,
      defenseValue: true,
      boostValue: true,
    }
  });
  console.log('Total cards:', cards.length);
  console.log('Cards by type:');
  const byType = {};
  cards.forEach(c => {
    if (!byType[c.cardType]) byType[c.cardType] = [];
    byType[c.cardType].push({ name: c.name, attack: c.attackValue, defense: c.defenseValue, boost: c.boostValue });
  });
  console.log(JSON.stringify(byType, null, 2));
}

main()
  .catch(console.error)
  .finally(() => prisma.$disconnect());
