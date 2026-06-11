import { PrismaClient, UserRole } from '@prisma/client';
import * as bcrypt from 'bcrypt';

const prisma = new PrismaClient();

async function seedAdmin() {
  console.log('🌱 Seeding admin user...');

  const hashedPassword = await bcrypt.hash('Admin123!', 10);

  const admin = await prisma.user.upsert({
    where: { email: 'admin@unmached.local' },
    update: {},
    create: {
      email: 'admin@unmached.local',
      username: 'admin',
      password: hashedPassword,
      role: UserRole.ADMIN,
      emailVerified: new Date(),
    },
  });

  console.log('✅ Admin user created:');
  console.log('   Email:', admin.email);
  console.log('   Username:', admin.username);
  console.log('   Password: Admin123!');
  console.log('   Role:', admin.role);
}

async function seedModerator() {
  console.log('🌱 Seeding moderator user...');

  const hashedPassword = await bcrypt.hash('Moderator123!', 10);

  const moderator = await prisma.user.upsert({
    where: { email: 'moderator@unmached.local' },
    update: {},
    create: {
      email: 'moderator@unmached.local',
      username: 'moderator',
      password: hashedPassword,
      role: UserRole.MODERATOR,
      emailVerified: new Date(),
    },
  });

  console.log('✅ Moderator user created:');
  console.log('   Email:', moderator.email);
  console.log('   Username:', moderator.username);
  console.log('   Password: Moderator123!');
  console.log('   Role:', moderator.role);
}

async function main() {
  try {
    await seedAdmin();
    await seedModerator();
    console.log('\n🎉 Seed completed successfully!');
  } catch (error) {
    console.error('❌ Seed failed:', error);
    process.exit(1);
  } finally {
    await prisma.$disconnect();
  }
}

main();
