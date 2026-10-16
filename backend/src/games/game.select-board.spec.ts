/** SEL (docs/game-design/select-screens/02-DESIGN.md §2): selectBoard — хост меняет поле комнаты в лобби;
 *  гость и чужие статусы отклоняются, несуществующая доска отклоняется, смена поля снимает готовность соперника. */
import { Test, TestingModule } from '@nestjs/testing';
import { BadRequestException, ForbiddenException, NotFoundException } from '@nestjs/common';
import { GameService } from './game.service';
import { GameStatus } from './dto';
import { PrismaService } from '../database/prisma.service';
import { RedisService } from '../redis/redis.service';
import { GameInitializationService } from './services/game-initialization.service';
import { GameActionService } from './services/game-action.service';
import { GameSubscriptionService } from './game-subscription.service';
import type { GameResponse } from './models';

const MARMOREAL = 'c121b47f8d6eb28daccb76d05';
const SARPEDON = 'c7fa64a26c29a0835f2383e63';

describe('GameService selectBoard (SEL)', () => {
  let service: GameService;
  let prisma: any;

  beforeEach(async () => {
    const module: TestingModule = await Test.createTestingModule({
      providers: [
        GameService,
        {
          provide: PrismaService,
          useValue: {
            game: { findUnique: jest.fn(), update: jest.fn().mockReturnValue('game.update') },
            board: { findUnique: jest.fn() },
            gamePlayer: { updateMany: jest.fn().mockReturnValue('players.unready') },
            $transaction: jest.fn().mockResolvedValue([]),
          },
        },
        { provide: RedisService, useValue: { getJson: jest.fn(), setJsonex: jest.fn(), del: jest.fn() } },
        { provide: GameInitializationService, useValue: {} },
        { provide: GameActionService, useValue: { recordAction: jest.fn() } },
        { provide: GameSubscriptionService, useValue: { publishLobbyEvent: jest.fn() } },
      ],
    }).compile();
    service = module.get(GameService);
    prisma = module.get(PrismaService);
    jest.spyOn(service, 'getGame').mockResolvedValue({ id: 'g1', boardId: SARPEDON } as GameResponse);
    jest.spyOn(service as any, 'invalidateGameCache').mockResolvedValue(undefined);
  });

  const lobby = (overrides: Record<string, unknown> = {}) => ({
    id: 'g1',
    status: GameStatus.LOBBY,
    hostId: 'host',
    boardId: MARMOREAL,
    ...overrides,
  });

  it('хост меняет поле: доска записана, готовность соперника снята, кеш сброшен', async () => {
    prisma.game.findUnique.mockResolvedValue(lobby());
    prisma.board.findUnique.mockResolvedValue({ id: SARPEDON });

    const res = await service.selectBoard('g1', 'host', SARPEDON);

    expect(res.boardId).toBe(SARPEDON);
    expect(prisma.game.update).toHaveBeenCalledWith({ where: { id: 'g1' }, data: { boardId: SARPEDON } });
    expect(prisma.gamePlayer.updateMany).toHaveBeenCalledWith({
      where: { gameId: 'g1', userId: { not: 'host' } },
      data: { isReady: false },
    });
    expect(prisma.$transaction).toHaveBeenCalledWith(['game.update', 'players.unready']);
    expect((service as any).invalidateGameCache).toHaveBeenCalledWith('g1');
  });

  it('то же поле — без записи и без снятия готовности', async () => {
    prisma.game.findUnique.mockResolvedValue(lobby());
    prisma.board.findUnique.mockResolvedValue({ id: MARMOREAL });

    await service.selectBoard('g1', 'host', MARMOREAL);

    expect(prisma.$transaction).not.toHaveBeenCalled();
  });

  it('гость не может менять поле', async () => {
    prisma.game.findUnique.mockResolvedValue(lobby());
    await expect(service.selectBoard('g1', 'guest', SARPEDON)).rejects.toBeInstanceOf(ForbiddenException);
  });

  it('после старта поле не меняется', async () => {
    prisma.game.findUnique.mockResolvedValue(lobby({ status: GameStatus.IN_PROGRESS }));
    await expect(service.selectBoard('g1', 'host', SARPEDON)).rejects.toBeInstanceOf(BadRequestException);
  });

  it('синтетическая доска (не Marmoreal/Sarpedon) отклоняется без запроса к БД', async () => {
    prisma.game.findUnique.mockResolvedValue(lobby());
    await expect(service.selectBoard('g1', 'host', 'cobble-city-5x6')).rejects.toBeInstanceOf(BadRequestException);
    expect(prisma.board.findUnique).not.toHaveBeenCalled();
  });

  it('реальная карта, которой нет в БД, отклоняется', async () => {
    prisma.game.findUnique.mockResolvedValue(lobby());
    prisma.board.findUnique.mockResolvedValue(null);
    await expect(service.selectBoard('g1', 'host', SARPEDON)).rejects.toBeInstanceOf(BadRequestException);
  });

  it('нет игры — NotFound', async () => {
    prisma.game.findUnique.mockResolvedValue(null);
    await expect(service.selectBoard('g1', 'host', SARPEDON)).rejects.toBeInstanceOf(NotFoundException);
  });
});
