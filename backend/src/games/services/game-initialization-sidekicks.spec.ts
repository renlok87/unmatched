/**
 * Помощники героя на инициализации партии (parseSidekicks).
 *
 * Скрейп записал героям без помощника заглушку {name: "Unknown", health: 1}
 * (T. Rex, Deadpool, Bruce Lee…, properties.hasSidekick === false): клиент
 * показывал лишнюю фигуру «Unknown» с 1/1 HP. Заглушка не становится бойцом,
 * настоящие помощники и записи без hasSidekick — как раньше.
 */
import { GameInitializationService } from './game-initialization.service';

const svc = new GameInitializationService({} as any, {} as any);
const parse = (raw: unknown, properties?: unknown) => (svc as any).parseSidekicks(raw, properties);

describe('GameInitializationService.parseSidekicks', () => {
  it('заглушка "Unknown" при hasSidekick=false не даёт бойца (T. Rex)', () => {
    const raw = [{ name: 'Unknown', health: 1, movement: 1, attackType: 'melee' }];
    expect(parse(raw, { hasSidekick: false, sidekickCount: 1 })).toEqual([]);
  });

  it('настоящий помощник остаётся (Medusa: Harpy x3)', () => {
    const raw = [{ name: 'Harpy', health: 1, movement: 3, count: 3, attackType: 'melee' }];
    expect(parse(raw, { hasSidekick: true }).map((s: any) => s.name)).toEqual(['Harpy 1', 'Harpy 2', 'Harpy 3']);
  });

  it('без properties поведение прежнее (даже "Unknown")', () => {
    const raw = [{ name: 'Unknown', health: 1 }];
    expect(parse(raw)).toHaveLength(1);
  });
});
