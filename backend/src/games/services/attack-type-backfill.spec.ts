/**
 * GD-058 interim 2026-09-30 §8 п. 9 (волна 7): Medusa показывала MELEE — на стенде S09 у героя не было
 * Hero.properties.attackType (seed-scraped пропускал созданных героев, backfill не входил в bootstrap), а движок без
 * поля даёт 'melee'. Проверяем backfill-attack-type.ts (разбор скрейпа, план правки, dry-run / идемпотентность) и
 * что после него движок видит Medusa ranged, Merlin ranged, King Arthur melee, Harpies melee.
 */
import {
  applyAttackTypeBackfill,
  HeroAttackRow,
  parseHeroAttack,
  planAttackTypePatch,
  readScrapedAttacks,
  SCRAPED_DATA_PATH,
} from '../../../prisma/backfill-attack-type';
import { normalizeAttackType } from '../../game-engine/models/fighter.model';
import * as fs from 'fs';
import * as path from 'path';

function scraped(key: string) {
  const raw = JSON.parse(fs.readFileSync(path.join(SCRAPED_DATA_PATH, `${key}.json`), 'utf-8'));
  const parsed = parseHeroAttack(raw, key);
  if (!parsed) throw new Error(`scraped ${key} not parsed`);
  return parsed;
}

/** Как GameInitializationService: герой — properties.attackType, помощники — sidekicks[].attackType. */
function engineView(row: Pick<HeroAttackRow, 'properties' | 'sidekicks'>) {
  const sks = typeof row.sidekicks === 'string' ? JSON.parse(row.sidekicks) : row.sidekicks;
  return {
    hero: normalizeAttackType((row.properties as any)?.attackType),
    sidekicks: (Array.isArray(sks) ? sks : []).map((sk: any) => `${sk.name}:${normalizeAttackType(sk.attackType)}`),
  };
}

describe('backfill-attack-type (GD-058 §8 п. 9)', () => {
  it('reads the S09 roster attack types from scraped-data', () => {
    const medusa = scraped('medusa');
    expect(medusa.name).toBe('Medusa');
    expect(medusa.attack).toBe('range');
    expect(medusa.sidekicks.map((s) => `${s.name}:${s.attack}`)).toEqual([
      'Harpies:melee',
      'Harpies:melee',
      'Harpies:melee',
    ]);
    const arthur = scraped('king-arthur');
    expect(arthur.name).toBe('King Arthur');
    expect(arthur.attack).toBe('melee');
    expect(arthur.sidekicks.map((s) => `${s.name}:${s.attack}`)).toEqual(['Merlin:range']);
  });

  it('readScrapedAttacks covers the hero list and reports missing files', () => {
    const { parsed, skipped } = readScrapedAttacks();
    const names = parsed.map((p) => p.name);
    expect(names).toEqual(expect.arrayContaining(['Medusa', 'King Arthur']));
    expect(parsed.length).toBeGreaterThanOrEqual(60);
    const tmp = readScrapedAttacks(SCRAPED_DATA_PATH, ['medusa', 'no-such-hero']);
    expect(tmp.parsed.map((p) => p.key)).toEqual(['medusa']);
    expect(tmp.skipped).toEqual(['no-such-hero']);
    expect(skipped).not.toContain('medusa');
  });

  it('a Medusa row without attackType (the S09 stand) is patched so the engine sees ranged, Harpies melee', () => {
    const row = {
      properties: { hasSidekick: true, sidekickCount: 3 },
      sidekicks: [
        { name: 'Harpies', health: 1, movement: 3, avatarUrl: 'a.png' },
        { name: 'Harpies', health: 1, movement: 3 },
        { name: 'Harpies', health: 1, movement: 3 },
      ],
    };
    expect(engineView(row).hero).toBe('melee'); // the defect: no field -> melee
    const patch = planAttackTypePatch(row, scraped('medusa'));
    expect(patch).not.toBeNull();
    expect(patch!.properties).toEqual({ hasSidekick: true, sidekickCount: 3, attackType: 'range' });
    const fixed = { properties: patch!.properties, sidekicks: patch!.sidekicks ?? row.sidekicks };
    expect(engineView(fixed)).toEqual({
      hero: 'ranged',
      sidekicks: ['Harpies:melee', 'Harpies:melee', 'Harpies:melee'],
    });
    expect((fixed.sidekicks as any[])[0]).toMatchObject({ name: 'Harpies', health: 1, movement: 3, avatarUrl: 'a.png' });
    expect(planAttackTypePatch(fixed, scraped('medusa'))).toBeNull(); // idempotent
  });

  it('King Arthur: hero melee kept explicit, Merlin fixed to ranged (sidekicks stored as JSON string)', () => {
    const row = {
      properties: {},
      sidekicks: JSON.stringify([{ name: 'Merlin', health: 7, movement: 2, attackType: 'melee' }]),
    };
    const patch = planAttackTypePatch(row, scraped('king-arthur'));
    expect(patch!.properties).toEqual({ attackType: 'melee' });
    expect(typeof patch!.sidekicks).toBe('string');
    const fixed = { properties: patch!.properties, sidekicks: patch!.sidekicks };
    expect(engineView(fixed)).toEqual({ hero: 'melee', sidekicks: ['Merlin:ranged'] });
    expect(planAttackTypePatch(fixed, scraped('king-arthur'))).toBeNull();
  });

  it('no-op when the stored value already means the same to the engine; unknown sidekicks untouched', () => {
    expect(
      planAttackTypePatch(
        { properties: { attackType: 'ranged' }, sidekicks: [{ name: 'Harpies', attackType: 'melee' }] },
        scraped('medusa'),
      ),
    ).toBeNull();
    const patch = planAttackTypePatch(
      { properties: { attackType: 'range' }, sidekicks: [{ name: 'Somebody', attackType: 'melee' }] },
      scraped('king-arthur'),
    );
    expect(patch!.properties).toEqual({ attackType: 'melee' });
    expect(patch!.sidekicks).toBeUndefined();
  });

  it('the seed-side copy of the canon matches normalizeAttackType', () => {
    for (const v of ['range', 'ranged', 'melee', 'melee_range', undefined, null, 3]) {
      const expected = normalizeAttackType(v);
      const viaPlan = planAttackTypePatch({ properties: { attackType: v }, sidekicks: [] }, { attack: 'range', sidekicks: [] });
      // stored value already "ranged" for the engine -> no patch; otherwise patch to 'range'
      expect(viaPlan === null).toBe(expected === 'ranged' && typeof v === 'string');
    }
  });

  describe('applyAttackTypeBackfill (mocked prisma)', () => {
    function fakePrisma(rows: HeroAttackRow[]) {
      const byName = new Map(rows.map((r) => [r.name, { ...r }]));
      const update = jest.fn(async ({ where, data }: { where: { id: string }; data: Record<string, unknown> }) => {
        for (const r of byName.values()) if (r.id === where.id) Object.assign(r, data);
      });
      const findUnique = jest.fn(async ({ where }: { where: { name: string } }) => byName.get(where.name) ?? null);
      return { prisma: { hero: { findUnique, update } }, byName, update };
    }
    const roster = () => [scraped('medusa'), scraped('king-arthur')];
    const rows = (): HeroAttackRow[] => [
      { id: 'h1', name: 'Medusa', properties: { hasSidekick: true }, sidekicks: [{ name: 'Harpies' }] },
      { id: 'h2', name: 'King Arthur', properties: { attackType: 'melee' }, sidekicks: [{ name: 'Merlin', attackType: 'range' }] },
    ];

    it('dry-run writes nothing and lists the pending change', async () => {
      const { prisma, update } = fakePrisma(rows());
      const stats = await applyAttackTypeBackfill(prisma, [...roster(), { key: 'x', name: 'Nobody', attack: 'melee', sidekicks: [] }], {
        dryRun: true,
        log: () => undefined,
      });
      expect(update).not.toHaveBeenCalled();
      expect(stats.pending.map((p) => p.name)).toEqual(['Medusa']);
      expect(stats.pending[0].changes.join(' ')).toContain('attackType <none> -> range');
      expect(stats.alreadySet).toBe(1);
      expect(stats.notFound).toEqual(['Nobody (x)']);
    });

    it('apply updates once, a second run is a no-op', async () => {
      const { prisma, byName, update } = fakePrisma(rows());
      const first = await applyAttackTypeBackfill(prisma, roster(), { log: () => undefined });
      expect(first.updated).toBe(1);
      expect(update).toHaveBeenCalledTimes(1);
      expect(engineView(byName.get('Medusa')!)).toEqual({ hero: 'ranged', sidekicks: ['Harpies:melee'] });
      expect(engineView(byName.get('King Arthur')!)).toEqual({ hero: 'melee', sidekicks: ['Merlin:ranged'] });
      const second = await applyAttackTypeBackfill(prisma, roster(), { log: () => undefined });
      expect(second.updated).toBe(0);
      expect(second.alreadySet).toBe(2);
      expect(update).toHaveBeenCalledTimes(1);
    });
  });
});
