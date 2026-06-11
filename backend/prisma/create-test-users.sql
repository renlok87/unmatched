-- Тестовые аккаунты для Unmatched
-- Пароль: password123 (bcrypt hash)
-- Запуск: docker exec unmatched-postgres psql -U unmatched -d unmatched -f prisma/create-test-users.sql

-- Очистка существующих тестовых пользователей (опционально)
-- DELETE FROM "AuthAuditLog" WHERE "userId" IN ('user1test', 'user2test');
-- DELETE FROM "UserStats" WHERE "userId" IN ('user1test', 'user2test');
-- DELETE FROM "UserSettings" WHERE "userId" IN ('user1test', 'user2test');
-- DELETE FROM "User" WHERE id IN ('user1test', 'user2test');

-- Создание пользователей
INSERT INTO "User" (id, email, username, password, "emailVerified", "createdAt", "updatedAt")
VALUES
  ('user1test', 'test1@unmatched.com', 'TestPlayer1', '$2b$10$N9qo8uLHkQ/ZFvHVx4q2.OqQV7qE1mGHSFjKWGe4eGWxvdQN.PXS2', NOW(), NOW(), NOW()),
  ('user2test', 'test2@unmatched.com', 'TestPlayer2', '$2b$10$N9qo8uLHkQ/ZFvHVx4q2.OqQV7qE1mGHSFjKWGe4eGWxvdQN.PXS2', NOW(), NOW(), NOW())
ON CONFLICT (email) DO NOTHING;

-- Создание настроек
INSERT INTO "UserSettings" (id, "userId", theme, language, "soundEnabled", "musicEnabled", "profileVisible", "showOnlineStatus")
VALUES
  ('settings1', 'user1test', 'dark', 'ru', true, true, true, true),
  ('settings2', 'user2test', 'dark', 'ru', true, true, true, true)
ON CONFLICT ("userId") DO NOTHING;

-- Создание статистики
INSERT INTO "UserStats" (id, "userId", "gamesPlayed", "gamesWon", "gamesLost", "winRate", "currentElo", "peakElo", "heroStats", "totalPlayTime")
VALUES
  ('stats1', 'user1test', 0, 0, 0, 0, 1200, 1200, '{}', 0),
  ('stats2', 'user2test', 0, 0, 0, 0, 1200, 1200, '{}', 0)
ON CONFLICT ("userId") DO NOTHING;

-- Audit логи
INSERT INTO "AuthAuditLog" (id, "userId", action, success, "createdAt")
VALUES
  ('audit1', 'user1test', 'register', true, NOW()),
  ('audit2', 'user2test', 'register', true, NOW());

-- Вывод списка созданных пользователей
SELECT '✅ Тестовые пользователи созданы!' as status;
SELECT u.email, u.username, 'password123' as password FROM "User" u WHERE u.id IN ('user1test', 'user2test');
