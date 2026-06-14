import { PrismaClient, UserRole } from '@prisma/client';
import * as bcrypt from 'bcrypt';

const prisma = new PrismaClient();

/** Системный e-mail ИИ-оппонента (VS_AI). Дублируется в game.service (AI_USER_EMAIL). */
export const AI_USER_EMAIL = 'ai@unmached.local';

/**
 * Сид системного юзера-бота для режима VS_AI. Бот не логинится паролем
 * (ходы исполняются сервером), пароль — случайный bcrypt-хэш заглушка.
 * Идемпотентно (upsert) — безопасно вызывать из общего сида.
 */
export async function seedAiUser() {
  console.log('🤖 Seeding AI bot user...');
  // Пароль не используется для входа — рандомная заглушка
  const hashedPassword = await bcrypt.hash(`ai-bot-${AI_USER_EMAIL}-no-login`, 10);

  const ai = await prisma.user.upsert({
    where: { email: AI_USER_EMAIL },
    update: {},
    create: {
      email: AI_USER_EMAIL,
      username: 'AI Bot',
      password: hashedPassword,
      role: UserRole.USER,
      emailVerified: new Date(),
    },
  });

  console.log('✅ AI bot user ready:', ai.email, '/', ai.username, '(id', ai.id + ')');
}

async function main() {
  try {
    await seedAiUser();
  } catch (error) {
    console.error('❌ AI seed failed:', error);
    process.exit(1);
  } finally {
    await prisma.$disconnect();
  }
}

// Самозапуск только при прямом вызове скрипта (а не при импорте из общего сида).
if (require.main === module) {
  main();
}
