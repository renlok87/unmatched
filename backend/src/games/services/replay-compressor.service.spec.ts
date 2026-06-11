import { Test, TestingModule } from '@nestjs/testing';
import { ReplayCompressorService } from './replay-compressor.service';

describe('ReplayCompressorService', () => {
  let service: ReplayCompressorService;

  beforeEach(async () => {
    const module: TestingModule = await Test.createTestingModule({
      providers: [ReplayCompressorService],
    }).compile();

    service = module.get<ReplayCompressorService>(ReplayCompressorService);
  });

  it('should be defined', () => {
    expect(service).toBeDefined();
  });

  describe('compress', () => {
    it('should compress data', async () => {
      const data = JSON.stringify({ test: 'data', nested: { value: 123 } });

      const compressed = await service.compress(data);

      expect(compressed).toBeInstanceOf(Buffer);
    });

    it('should handle large data', async () => {
      const largeData = JSON.stringify({
        actions: Array(1000).fill({ type: 'test', data: {} }),
      });

      const compressed = await service.compress(largeData);

      expect(compressed).toBeInstanceOf(Buffer);
      expect(compressed.length).toBeLessThan(largeData.length);
    });

    it('should throw error on compression failure', async () => {
      await expect(service.compress(null as unknown as string)).rejects.toThrow();
    });
  });

  describe('decompress', () => {
    it('should decompress data', async () => {
      const data = JSON.stringify({ test: 'data' });
      const compressed = await service.compress(data);

      const decompressed = await service.decompress(compressed);

      expect(decompressed).toBe(data);
    });

    it('should decompress to valid JSON', async () => {
      const data = JSON.stringify({ test: 'data', nested: { value: 123 } });
      const compressed = await service.compress(data);

      const decompressed = await service.decompress(compressed);
      const parsed = JSON.parse(decompressed);

      expect(parsed).toEqual({ test: 'data', nested: { value: 123 } });
    });

    it('should throw error on decompression failure', async () => {
      await expect(service.decompress(Buffer.from('invalid'))).rejects.toThrow();
    });
  });

  describe('roundtrip', () => {
    it('should compress and decompress without data loss', async () => {
      const originalData = JSON.stringify({
        version: 1,
        gameId: 'test-game',
        actions: [
          { type: 'ATTACK', playerId: 'player1', data: {} },
          { type: 'DEFENSE', playerId: 'player2', data: {} },
        ],
      });

      const compressed = await service.compress(originalData);
      const decompressed = await service.decompress(compressed);

      expect(decompressed).toBe(originalData);
    });
  });
});
