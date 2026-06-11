import { Module } from '@nestjs/common';
// Экспортируем из games модуля (постепенная миграция)
import { GamesModule } from '../games/games.module';

/**
 * Lobby Module
 *
 * Управляет CRUD игр и лобби:
 * - Создание игр
 * - Поиск доступных игр
 * - Присоединение к играм
 * - Управление лобби (готовность, выбор героя)
 *
 * Мигрирован из games/ для ясности ответственности.
 */
@Module({
  imports: [GamesModule],
  exports: [GamesModule],
})
export class LobbyModule {}
