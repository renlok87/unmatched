/**
 * Prisma Seed - Создание тестовых данных
 *
 * Запуск:
 * npx prisma db seed
 * или
 * npm run prisma:seed
 *
 * Тестовые аккаунты:
 * - test1@unmatched.com / password123
 * - test2@unmatched.com / password123
 */

import { PrismaClient } from '@prisma/client';
import * as bcrypt from 'bcrypt';
import * as crypto from 'crypto';
import { seedAiUser } from './seed-ai';

const prisma = new PrismaClient();

const TEST_USERS = [
  {
    email: 'test1@unmatched.com',
    username: 'TestPlayer1',
    password: 'password123',
  },
  {
    email: 'test2@unmatched.com',
    username: 'TestPlayer2',
    password: 'password123',
  },
  {
    email: 'pro@unmatched.com',
    username: 'ProGamer',
    password: 'password123',
  },
  {
    email: 'newbie@unmatched.com',
    username: 'NewPlayer',
    password: 'password123',
  },
  {
    email: 'veteran@unmatched.com',
    username: 'Veteran',
    password: 'password123',
  },
];

const HEROES = [
  {
    name: 'Ms. Marvel',
    nameEn: 'Ms. Marvel',
    nameRu: 'Кэрол Денверс',
    set: 'Teen Spirit',
    health: 18,
    fighterType: 'HERO',
    ability: {
      type: 'EMBIGGEN',
      timing: 'PASSIVE',
      effect: 'Can use Scheme cards as Maneuver cards',
      description: 'Can use Scheme cards as Maneuver cards',
    },
    deckCards: [],
    properties: {
      hasSidekick: true,
      sidekickCount: 2,
    },
    imageUrl: 'https://yptpnirqgfmxphjvsdjz.supabase.co/storage/v1/object/public/heroes/avatars/M61_bBineukElgyyqqSFu.webp',
    avatarUrl: 'https://yptpnirqgfmxphjvsdjz.supabase.co/storage/v1/object/public/heroes/avatars/M61_bBineukElgyyqqSFu.webp',
  },
  {
    name: 'Daredevil',
    nameEn: 'Daredevil',
    nameRu: 'Сорвиголова',
    set: 'Hell\'s Kitchen',
    health: 18,
    fighterType: 'HERO',
    ability: {
      type: 'RADAR_SENSE',
      timing: 'DEFENSE',
      effect: 'When defending, can discard 1 card to add +2 to defense value',
      description: 'When defending, can discard 1 card to add +2 to defense value',
    },
    deckCards: [],
    properties: {
      hasSidekick: false,
    },
    imageUrl: 'https://yptpnirqgfmxphjvsdjz.supabase.co/storage/v1/object/public/heroes/avatars/kZQUve8tqIcvmVUC-bGge.webp',
    avatarUrl: 'https://yptpnirqgfmxphjvsdjz.supabase.co/storage/v1/object/public/heroes/avatars/kZQUve8tqIcvmVUC-bGge.webp',
  },
];

const CARDS = [
  {
    name: 'Punch',
    nameEn: 'Punch',
    nameRu: 'Удар',
    cardType: 'ATTACK',
    subType: null,
    attackValue: 3,
    defenseValue: null,
    boostValue: null,
    effects: [],
    text: 'Basic attack',
    textEn: 'Basic attack',
    textRu: 'Базовая атака',
    heroName: 'Ms. Marvel',
    count: 3,
  },
  {
    name: 'Dodge',
    nameEn: 'Dodge',
    nameRu: 'Уклонение',
    cardType: 'DEFENSE',
    subType: null,
    attackValue: null,
    defenseValue: 4,
    boostValue: null,
    effects: [],
    text: 'Basic defense',
    textEn: 'Basic defense',
    textRu: 'Базовая защита',
    heroName: 'Ms. Marvel',
    count: 3,
  },
  {
    name: 'Embiggen',
    nameEn: 'Embiggen',
    nameRu: 'Увеличение',
    cardType: 'SCHEME',
    subType: 'Growth',
    attackValue: null,
    defenseValue: null,
    boostValue: 2,
    effects: [],
    text: 'Boost your next attack by +2',
    textEn: 'Boost your next attack by +2',
    textRu: 'Усильте следующую атаку на +2',
    heroName: 'Ms. Marvel',
    count: 2,
  },
  {
    name: 'Photon Blast',
    nameEn: 'Photon Blast',
    nameRu: 'Фотонный взрыв',
    cardType: 'ATTACK',
    subType: 'Energy',
    attackValue: 5,
    defenseValue: null,
    boostValue: null,
    effects: [],
    text: 'Powerful energy attack',
    textEn: 'Powerful energy attack',
    textRu: 'Мощная энергетическая атака',
    heroName: 'Ms. Marvel',
    count: 2,
  },
  {
    name: 'Flight',
    nameEn: 'Flight',
    nameRu: 'Полёт',
    cardType: 'MANEUVER',
    subType: 'Movement',
    attackValue: null,
    defenseValue: null,
    boostValue: null,
    effects: [],
    text: 'Move 2 zones',
    textEn: 'Move 2 zones',
    textRu: 'Переместитесь на 2 зоны',
    heroName: 'Ms. Marvel',
    count: 2,
  },
  {
    name: 'Billy Club Strike',
    nameEn: 'Billy Club Strike',
    nameRu: 'Удар дубинкой',
    cardType: 'ATTACK',
    subType: 'Melee',
    attackValue: 4,
    defenseValue: null,
    boostValue: null,
    effects: [],
    text: 'Quick melee attack',
    textEn: 'Quick melee attack',
    textRu: 'Быстрая ближняя атака',
    heroName: 'Daredevil',
    count: 3,
  },
  {
    name: 'Radar Sense',
    nameEn: 'Radar Sense',
    nameRu: 'Радар-чувства',
    cardType: 'DEFENSE',
    subType: 'Special',
    attackValue: null,
    defenseValue: 5,
    boostValue: null,
    effects: [],
    text: 'Enhanced defense',
    textEn: 'Enhanced defense',
    textRu: 'Улучшенная защита',
    heroName: 'Daredevil',
    count: 2,
  },
  {
    name: 'Acrobatics',
    nameEn: 'Acrobatics',
    nameRu: 'Акробатика',
    cardType: 'MANEUVER',
    subType: 'Movement',
    attackValue: null,
    defenseValue: null,
    boostValue: null,
    effects: [],
    text: 'Move up to 3 zones',
    textEn: 'Move up to 3 zones',
    textRu: 'Переместитесь до 3 зон',
    heroName: 'Daredevil',
    count: 2,
  },
  {
    name: 'Devil\'s Due',
    nameEn: 'Devil\'s Due',
    nameRu: 'Долг дьявола',
    cardType: 'ATTACK',
    subType: 'Special',
    attackValue: 6,
    defenseValue: null,
    boostValue: null,
    effects: [],
    text: 'Powerful attack with drawback',
    textEn: 'Powerful attack with drawback',
    textRu: 'Мощная атака с недостатком',
    heroName: 'Daredevil',
    count: 1,
  },
  {
    name: 'Daredevil Defense',
    nameEn: 'Daredevil Defense',
    nameRu: 'Защита Сорвиголовы',
    cardType: 'DEFENSE',
    subType: 'Special',
    attackValue: null,
    defenseValue: 3,
    boostValue: null,
    effects: [],
    text: 'Basic defense',
    textEn: 'Basic defense',
    textRu: 'Базовая защита',
    heroName: 'Daredevil',
    count: 3,
  },
];

// Доски этот сид не создаёт. Синтетическая Cobble City 5×6 (cmuhgs4b2001mwik4f2b2xtf8) выведена
// (docs/game-design/decisions/2026-10-04-real-boards-only.md). Доски игры: оригинальные карты
// (prisma/seed-env-map-boards.ts, доска по умолчанию — Marmoreal · original map) и каталог
// настоящих карт для веба (prisma/seed-all-scraped.ts).

async function main() {
  console.log('🌱 Seed: Создание тестовых данных...\n');

  for (const userData of TEST_USERS) {
    try {
      const existingUser = await prisma.user.findFirst({
        where: {
          OR: [{ email: userData.email }, { username: userData.username }],
        },
      });

      if (existingUser) {
        console.log(`⏭️  Пропуск: ${userData.email} (уже существует)`);
        continue;
      }

      const hashedPassword = await bcrypt.hash(userData.password, 10);
      const emailVerifiedToken = crypto.randomBytes(32).toString('hex');

      const result = await prisma.$transaction(async (tx) => {
        const user = await tx.user.create({
          data: {
            email: userData.email,
            username: userData.username,
            password: hashedPassword,
            emailVerified: new Date(),
            emailVerifiedToken,
          },
        });

        await tx.userSettings.create({
          data: { userId: user.id },
        });

        await tx.userStats.create({
          data: { userId: user.id },
        });

        await tx.authAuditLog.create({
          data: {
            userId: user.id,
            action: 'register',
            success: true,
          },
        });

        return user;
      });

      console.log(`✅ Создан пользователь: ${userData.email}`);
    } catch (error) {
      console.error(`❌ Ошибка при создании ${userData.email}:`, error);
    }
  }

  // Системный AI-юзер для режима VS_AI (идемпотентный upsert).
  try {
    await seedAiUser();
  } catch (error) {
    console.error('❌ Ошибка при создании AI-юзера:', error);
  }

  console.log('\n🦸 Создание героев...');
  for (const heroData of HEROES) {
    try {
      const existingHero = await prisma.hero.findUnique({
        where: { name: heroData.name },
      });

      if (existingHero) {
        console.log(`⏭️  Пропуск героя: ${heroData.name} (уже существует)`);
        continue;
      }

      const hero = await prisma.hero.create({
        data: heroData,
      });

      console.log(`✅ Создан герой: ${hero.name}`);
    } catch (error) {
      console.error(`❌ Ошибка при создании героя ${heroData.name}:`, error);
    }
  }

  console.log('\n🃏 Создание карт...');
  for (const cardData of CARDS) {
    try {
      const hero = await prisma.hero.findUnique({
        where: { name: cardData.heroName },
      });

      if (!hero) {
        console.log(`⚠️  Пропуск карты ${cardData.name}: герой не найден`);
        continue;
      }

      const existingCard = await prisma.card.findFirst({
        where: {
          name: cardData.name,
          heroId: hero.id,
        },
      });

      if (existingCard) {
        console.log(`⏭️  Пропуск карты: ${cardData.name} (уже существует)`);
        continue;
      }

      const { heroName, ...cardInput } = cardData;
      const card = await prisma.card.create({
        data: {
          ...cardInput,
          heroId: hero.id,
        },
      });

      console.log(`✅ Создана карта: ${card.name} (${hero.name})`);
    } catch (error) {
      console.error(`❌ Ошибка при создании карты ${cardData.name}:`, error);
    }
  }

  console.log('\n📋 Тестовые аккаунты:');
  console.log('┌─────────────────────────┬────────────────┬───────────────┐');
  console.log('│ Email                   │ Username       │ Password      │');
  console.log('├─────────────────────────┼────────────────┼───────────────┤');
  TEST_USERS.forEach((u) => {
    console.log(`│ ${u.email.padEnd(23)} │ ${u.username.padEnd(14)} │ ${u.password.padEnd(13)} │`);
  });
  console.log('└─────────────────────────┴────────────────┴───────────────┘');

  console.log('\n🎮 Содержимое БД:');
  const heroCount = await prisma.hero.count();
  const cardCount = await prisma.card.count();
  const boardCount = await prisma.board.count();
  const userCount = await prisma.user.count();

  console.log(`   👥 Пользователей: ${userCount}`);
  console.log(`   🦸 Героев: ${heroCount}`);
  console.log(`   🃏 Карт: ${cardCount}`);
  console.log(`   🗺️  Досок: ${boardCount}`);
}

main()
  .catch((e) => {
    console.error('❌ Seed error:', e);
    process.exit(1);
  })
  .finally(async () => {
    await prisma.$disconnect();
  });
