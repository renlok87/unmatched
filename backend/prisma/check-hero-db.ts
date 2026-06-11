import { PrismaClient } from '@prisma/client';

const prisma = new PrismaClient();

async function main() {
  const hero = await prisma.hero.findFirst({
    where: { name: 'Achilles' },
  });

  if (hero) {
    console.log('Achilles в БД:');
    console.log('  name:', hero.name);
    console.log('  nameEn:', hero.nameEn);
    console.log('  nameRu:', hero.nameRu);
    console.log('  set:', hero.set);
    console.log('  imageUrl:', hero.imageUrl);
    console.log('  avatarUrl:', hero.avatarUrl);
  }

  // Проверим несколько героев
  const heroes = await prisma.hero.findMany({
    take: 5,
    select: { name: true, imageUrl: true, avatarUrl: true }
  });

  console.log('\nПервые 5 героев:');
  heroes.forEach(h => {
    console.log(`  ${h.name}: imageUrl=${h.imageUrl}, avatarUrl=${h.avatarUrl}`);
  });
}

main()
  .catch(console.error)
  .finally(async () => {
    await prisma.$disconnect();
  });
