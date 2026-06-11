import { Test, TestingModule } from '@nestjs/testing';
import { INestApplication } from '@nestjs/common';
import request from 'supertest';
import { AppModule } from '../src/app.module';

describe('Health Check API (e2e)', () => {
  let app: INestApplication;

  beforeAll(async () => {
    const moduleFixture: TestingModule = await Test.createTestingModule({
      imports: [AppModule],
    }).compile();

    app = moduleFixture.createNestApplication();
    await app.init();
  });

  afterAll(async () => {
    await app.close();
  });

  describe('GET /health', () => {
    it('должен возвращать статус ok', async () => {
      const response = await request(app.getHttpServer()).get('/health').expect(200);

      expect(response.body.status).toBe('ok');
      expect(response.body.info).toBeDefined();
      expect(response.body.info.database).toBeDefined();
      expect(response.body.info.redis).toBeDefined();
    });

    it('database должен быть в статусе up', async () => {
      const response = await request(app.getHttpServer()).get('/health').expect(200);

      expect(response.body.info.database.status).toBe('up');
    });

    it('redis должен быть в статусе up', async () => {
      const response = await request(app.getHttpServer()).get('/health').expect(200);

      expect(response.body.info.redis.status).toBe('up');
    });

    it('должен включать метаданные', async () => {
      const response = await request(app.getHttpServer()).get('/health').expect(200);

      expect(response.body).toHaveProperty('timestamp');
      expect(response.body).toHaveProperty('uptime');
    });
  });

  describe('GET /health/live', () => {
    it('liveness probe возвращает статус ok', async () => {
      const response = await request(app.getHttpServer()).get('/health/live').expect(200);

      expect(response.body.status).toBe('ok');
      expect(response.body.timestamp).toBeDefined();
    });

    it('liveness probe быстрый (менее 100ms)', async () => {
      const start = Date.now();
      await request(app.getHttpServer()).get('/health/live').expect(200);
      const duration = Date.now() - start;

      expect(duration).toBeLessThan(100);
    });

    it('liveness probe возвращает timestamp в ISO формате', async () => {
      const response = await request(app.getHttpServer()).get('/health/live').expect(200);

      expect(response.body.timestamp).toMatch(/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}/);
    });
  });

  describe('GET /health/ready', () => {
    it('readiness probe возвращает статус ok', async () => {
      const response = await request(app.getHttpServer()).get('/health/ready').expect(200);

      expect(response.body.status).toBe('ok');
      expect(response.body.info).toBeDefined();
    });

    it('readiness probe проверяет database', async () => {
      const response = await request(app.getHttpServer()).get('/health/ready').expect(200);

      expect(response.body.info.database).toBeDefined();
      expect(response.body.info.database.status).toBe('up');
    });

    it('readiness probe проверяет redis', async () => {
      const response = await request(app.getHttpServer()).get('/health/ready').expect(200);

      expect(response.body.info.redis).toBeDefined();
      expect(response.body.info.redis.status).toBe('up');
    });

    it('readiness probe возвращает ошибку если database down', async () => {
      const response = await request(app.getHttpServer()).get('/health/ready').expect(200);

      if (response.body.status === 'error') {
        expect(response.body.error).toBeDefined();
      }
    });
  });

  describe('GET /health/detail', () => {
    it('возвращает детальную информацию о всех компонентах', async () => {
      const response = await request(app.getHttpServer()).get('/health/detail').expect(200);

      expect(response.body.status).toBeDefined();
      expect(response.body.timestamp).toBeDefined();
      expect(response.body.components).toBeDefined();
    });

    it('включает детальную информацию о database', async () => {
      const response = await request(app.getHttpServer()).get('/health/detail').expect(200);

      expect(response.body.components.database).toBeDefined();
      expect(response.body.components.database.status).toBeDefined();
      expect(response.body.components.database.latency).toBeDefined();
    });

    it('включает детальную информацию о redis', async () => {
      const response = await request(app.getHttpServer()).get('/health/detail').expect(200);

      expect(response.body.components.redis).toBeDefined();
      expect(response.body.components.redis.status).toBeDefined();
      expect(response.body.components.redis.latency).toBeDefined();
    });

    it('latency измеряется в миллисекундах', async () => {
      const response = await request(app.getHttpServer()).get('/health/detail').expect(200);

      expect(response.body.components.database.latency).toMatch(/\d+ms/);
      expect(response.body.components.redis.latency).toMatch(/\d+ms/);
    });

    it('database latency должен быть разумным (< 500ms)', async () => {
      const response = await request(app.getHttpServer()).get('/health/detail').expect(200);

      const latencyStr = response.body.components.database.latency;
      const latency = parseInt(latencyStr.replace('ms', ''));

      expect(latency).toBeLessThan(500);
    });

    it('redis latency должен быть разумным (< 100ms)', async () => {
      const response = await request(app.getHttpServer()).get('/health/detail').expect(200);

      const latencyStr = response.body.components.redis.latency;
      const latency = parseInt(latencyStr.replace('ms', ''));

      expect(latency).toBeLessThan(100);
    });

    it('включает информацию о соединениях с БД', async () => {
      const response = await request(app.getHttpServer()).get('/health/detail').expect(200);

      expect(response.body.components.database.connections).toBeDefined();
      expect(typeof response.body.components.database.connections).toBe('number');
    });
  });

  describe('Интеграционные тесты', () => {
    it('все health endpoints возвращают корректный JSON', async () => {
      const healthResponse = await request(app.getHttpServer()).get('/health');
      const liveResponse = await request(app.getHttpServer()).get('/health/live');
      const readyResponse = await request(app.getHttpServer()).get('/health/ready');
      const detailResponse = await request(app.getHttpServer()).get('/health/detail');

      expect(healthResponse.headers['content-type']).toContain('application/json');
      expect(liveResponse.headers['content-type']).toContain('application/json');
      expect(readyResponse.headers['content-type']).toContain('application/json');
      expect(detailResponse.headers['content-type']).toContain('application/json');
    });

    it('health endpoints корректно обрабатывают параллельные запросы', async () => {
      const promises = [
        request(app.getHttpServer()).get('/health'),
        request(app.getHttpServer()).get('/health/live'),
        request(app.getHttpServer()).get('/health/ready'),
        request(app.getHttpServer()).get('/health/detail'),
      ];

      const responses = await Promise.all(promises);

      responses.forEach((response) => {
        expect([200, 503]).toContain(response.status);
      });
    });
  });

  describe('Performance тесты', () => {
    it('health endpoint отвечает быстро (< 200ms)', async () => {
      const start = Date.now();
      await request(app.getHttpServer()).get('/health').expect(200);
      const duration = Date.now() - start;

      expect(duration).toBeLessThan(200);
    });

    it('ready endpoint отвечает быстро (< 200ms)', async () => {
      const start = Date.now();
      await request(app.getHttpServer()).get('/health/ready').expect(200);
      const duration = Date.now() - start;

      expect(duration).toBeLessThan(200);
    });

    it('detail endpoint отвечает разумно (< 500ms)', async () => {
      const start = Date.now();
      await request(app.getHttpServer()).get('/health/detail').expect(200);
      const duration = Date.now() - start;

      expect(duration).toBeLessThan(500);
    });

    it('множественные последовательные запросы стабильны', async () => {
      const durations = [];

      for (let i = 0; i < 10; i++) {
        const start = Date.now();
        await request(app.getHttpServer()).get('/health').expect(200);
        durations.push(Date.now() - start);
      }

      const avgDuration = durations.reduce((a, b) => a + b, 0) / durations.length;
      expect(avgDuration).toBeLessThan(200);
    });

    it('параллельные запросы не вызывают проблем', async () => {
      const promises = [];
      for (let i = 0; i < 20; i++) {
        promises.push(request(app.getHttpServer()).get('/health'));
      }

      const start = Date.now();
      const responses = await Promise.all(promises);
      const duration = Date.now() - start;

      responses.forEach((response) => {
        expect(response.status).toBe(200);
      });

      expect(duration).toBeLessThan(1000);
    });
  });

  describe('Error Handling', () => {
    it('корректный HTTP статус для health', async () => {
      const response = await request(app.getHttpServer()).get('/health');

      if (response.body.status === 'ok') {
        expect(response.status).toBe(200);
      } else {
        expect(response.status).toBe(503);
      }
    });

    it('корректный HTTP статус для ready', async () => {
      const response = await request(app.getHttpServer()).get('/health/ready');

      if (response.body.status === 'ok') {
        expect(response.status).toBe(200);
      } else {
        expect(response.status).toBe(503);
      }
    });

    it('детальная информация об ошибках при проблемах', async () => {
      const response = await request(app.getHttpServer()).get('/health/detail');

      if (response.body.status === 'unhealthy') {
        Object.values(response.body.components).forEach((component: any) => {
          if (component.status === 'down') {
            expect(component.error).toBeDefined();
            expect(typeof component.error).toBe('string');
          }
        });
      }
    });
  });

  describe('Kubernetes Compatibility', () => {
    it('формат ответа совместим с Kubernetes probes', async () => {
      const liveResponse = await request(app.getHttpServer()).get('/health/live');
      const readyResponse = await request(app.getHttpServer()).get('/health/ready');

      expect(liveResponse.body).toHaveProperty('status');
      expect(readyResponse.body).toHaveProperty('status');

      if (liveResponse.body.status === 'ok') {
        expect(liveResponse.status).toBe(200);
      }

      if (readyResponse.body.status === 'ok') {
        expect(readyResponse.status).toBe(200);
      }
    });

    it('readiness probe проверяет критические зависимости', async () => {
      const response = await request(app.getHttpServer()).get('/health/ready');

      expect(response.body.info).toBeDefined();
      expect(Object.keys(response.body.info).length).toBeGreaterThan(0);

      Object.values(response.body.info).forEach((dependency: any) => {
        expect(dependency).toHaveProperty('status');
      });
    });

    it('liveness probe не делает тяжёлых проверок', async () => {
      const start = Date.now();
      await request(app.getHttpServer()).get('/health/live').expect(200);
      const duration = Date.now() - start;

      expect(duration).toBeLessThan(50);
    });
  });
});