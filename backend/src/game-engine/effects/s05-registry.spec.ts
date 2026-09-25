/** GD-019: executable S05 card registry (27 records / 60 copies).
 * Reads the frozen S01 catalog captures (content-medusa.json,
 * content-king-arthur.json), runs each record through the PRODUCTION ingest
 * path (normalizeCardEffects + SCHEME textEn fullText fallback — same code as
 * GameInitializationService.resolveCardEffects / backfill), classifies actual
 * support status, and diffs against the frozen expectation table below and
 * docs/game-design/_validation/deck-counts-reference.json. */
import * as fs from 'fs';
import * as path from 'path';
import { normalizeCardEffects } from '../models';
import { parseCardEffectTexts, PARSER_VERSION } from './effect-text-parser';
import { CardEffect, EffectType } from '../models';

interface CaptureCard {
  id: string;
  name: string;
  cardType: string;
  count: number;
  textEn: string;
  effects: unknown[];
  effectImmediately: string | null;
  effectDuring: string | null;
  effectAfter: string | null;
  effectBoost: string | null;
  effectOngoing: string | null;
}

type SupportStatus = 'SUPPORTED' | 'PARTIAL' | 'UNSUPPORTED' | 'BLANK';

interface RegistryEntry {
  hero: string;
  name: string;
  count: number;
  status: SupportStatus;
  notes: string;
}

const EVIDENCE = path.resolve(__dirname, '../../../..', 'docs/game-design/evidence/S01');
const medusa = JSON.parse(fs.readFileSync(path.join(EVIDENCE, 'content-medusa.json'), 'utf8')) as {
  name: string; cards: CaptureCard[];
};
const arthur = JSON.parse(fs.readFileSync(path.join(EVIDENCE, 'content-king-arthur.json'), 'utf8')) as {
  name: string; cards: CaptureCard[];
};
const countsRef = JSON.parse(
  fs.readFileSync(
    path.resolve(__dirname, '../../../..', 'docs/game-design/_validation/deck-counts-reference.json'),
    'utf8',
  ),
) as { decks: Record<'medusa' | 'king-arthur', { cards: Array<{ title: string; copies: number }> }> };

/** Production ingest (mirrors GameInitializationService.resolveCardEffects). */
function ingestEffects(card: CaptureCard): CardEffect[] {
  const effects = normalizeCardEffects(card.effects, card.id);
  if (effects.length > 0) return effects;
  if (card.cardType !== 'SCHEME' || !card.textEn.trim()) return [];
  return parseCardEffectTexts({ fullText: card.textEn }, card.id).effects;
}

/** Honest support classification of parsed effects. */
function classify(card: CaptureCard, effects: CardEffect[]): { status: SupportStatus; notes: string } {
  const types = effects.map((e) => e.type);
  const unsupported = types.filter((t) => t === EffectType.UNSUPPORTED).length;
  if (effects.length === 0 && !card.textEn.trim()) return { status: 'BLANK', notes: 'нет печатного текста и эффектов' };
  if (unsupported > 0) {
    return { status: 'UNSUPPORTED', notes: `${unsupported} из ${effects.length} эффектов UNSUPPORTED — не реализовано` };
  }
  // Известные ловушки: parsed-эффект, который не может сработать в рантайме.
  // Command the Storms: «Move each fighter (including opposing)» парсится как
  // NAMED_FIGHTER 'fighter' — не матчит ни одного бойца (двигать врагов не
  // реализовано) => честный UNSUPPORTED, а не SUPPORTED.
  if (effects.some((e) => e.type === EffectType.MOVE && e.fighterName === 'fighter')) {
    return { status: 'UNSUPPORTED', notes: "parsed MOVE NAMED_FIGHTER 'fighter' не матчит бойцов (each fighter incl. opposing не реализован)" };
  }
  // Skirmish: «choose one of the fighters in the combat» парсится как SELF —
  // выбор бойца боя не моделируется (двигается только свой).
  if (effects.some((e) => e.when?.kind === 'WON_COMBAT' && e.type === EffectType.MOVE)) {
    return { status: 'PARTIAL', notes: 'MOVE only-SELF: выбор бойца боя («choose one of the fighters») не моделируется' };
  }
  return { status: 'SUPPORTED', notes: `${effects.length} эффект(ов) исполняются движком` };
}

function buildRegistry(): RegistryEntry[] {
  const entries: RegistryEntry[] = [];
  for (const [hero, capture] of [['Medusa', medusa], ['King Arthur', arthur]] as const) {
    for (const card of capture.cards) {
      const effects = ingestEffects(card);
      const { status, notes } = classify(card, effects);
      entries.push({ hero, name: card.name, count: card.count, status, notes });
    }
  }
  return entries;
}

/** Frozen expectation: literal printed text → actual support (GD-019 table).
 *  Keyed by `hero/name` — shared titles (Feint, Regroup) are SEPARATE records
 *  per hero, never normalized away. */
const EXPECTED: Record<string, SupportStatus> = {
  // --- Medusa (11) — GD-020 scope ---
  'Medusa/A Momentary Glance': 'SUPPORTED', // DAMAGE ANY_FIGHTER_IN_ZONE → TARGET_FIGHTER pending (v8)
  'Medusa/Hiss and Slither': 'SUPPORTED',
  'Medusa/The Hounds of Mighty Zeus': 'SUPPORTED', // sequential per-Harpy MOVE pendings (S05)
  'Medusa/Dash': 'SUPPORTED',
  'Medusa/Winged Frenzy': 'SUPPORTED', // EACH_OWN_FIGHTER + pass-through + RETURN_DEFEATED revive (v8)
  'Medusa/Gaze of Stone': 'SUPPORTED',
  'Medusa/Regroup': 'SUPPORTED',
  'Medusa/Second Shot': 'SUPPORTED',
  'Medusa/Snipe': 'SUPPORTED',
  'Medusa/Clutching Claws': 'SUPPORTED',
  'Medusa/Feint': 'SUPPORTED',
  // --- King Arthur (16) — GD-021/022 scope остаётся вне S05, статусы честные ---
  'King Arthur/The Aid of Morgana': 'SUPPORTED',
  'King Arthur/Excalibur': 'BLANK', // подтверждённо пустая: нет text/effects/effect*-полей
  'King Arthur/Swift Strike': 'SUPPORTED',
  'King Arthur/Aid the Chosen One': 'SUPPORTED',
  'King Arthur/Feint': 'SUPPORTED',
  'King Arthur/The Holy Grail': 'UNSUPPORTED', // set-health-if-low — не реализовано
  'King Arthur/The Lady of the Lake': 'UNSUPPORTED', // search deck/discard — не реализовано
  'King Arthur/Prophecy': 'UNSUPPORTED', // look top 4 / pick 2 — не реализовано
  'King Arthur/Command the Storms': 'UNSUPPORTED', // each fighter incl. opposing — не реализовано
  'King Arthur/Noble Sacrifice': 'SUPPORTED',
  'King Arthur/Restless Spirits': 'UNSUPPORTED', // area damage по выбранной клетке — не реализовано
  'King Arthur/Bewilderment': 'SUPPORTED',
  'King Arthur/Divine Intervention': 'SUPPORTED',
  'King Arthur/Momentous Shift': 'SUPPORTED',
  'King Arthur/Skirmish': 'PARTIAL', // выбор бойца боя не моделируется (SELF only)
  'King Arthur/Regroup': 'SUPPORTED',
};

describe('GD-019: S05 card registry (frozen captures → production ingest)', () => {
  const registry = buildRegistry();

  it('covers exactly 27 records and 60 copies (11 Medusa / 16 Arthur, 30+30)', () => {
    expect(registry).toHaveLength(27);
    expect(registry.filter((e) => e.hero === 'Medusa')).toHaveLength(11);
    expect(registry.filter((e) => e.hero === 'King Arthur')).toHaveLength(16);
    expect(registry.reduce((s, e) => s + e.count, 0)).toBe(60);
    expect(registry.filter((e) => e.hero === 'Medusa').reduce((s, e) => s + e.count, 0)).toBe(30);
    expect(registry.filter((e) => e.hero === 'King Arthur').reduce((s, e) => s + e.count, 0)).toBe(30);
  });

  it('matches per-record counts against the frozen deck-counts reference', () => {
    const ref: Record<string, number> = {};
    for (const [slug, deck] of Object.entries(countsRef.decks)) {
      for (const c of deck.cards) ref[`${slug}/${c.title}`] = c.copies;
    }
    for (const entry of registry) {
      const slug = entry.hero === 'Medusa' ? 'medusa' : 'king-arthur';
      expect(ref[`${slug}/${entry.name}`]).toBe(entry.count);
    }
  });

  it('every record matches its frozen support status (honest, not all-SUPPORTED)', () => {
    const mismatched = registry.filter((e) => EXPECTED[`${e.hero}/${e.name}`] !== e.status);
    expect(mismatched.map((e) => `${e.hero}/${e.name}: ${e.status} != ${EXPECTED[`${e.hero}/${e.name}`]}`)).toEqual([]);
  });

  it('S05 fixes unblocked the two Medusa textEn schemes; Arthur gaps stay UNSUPPORTED', () => {
    const glance = ingestEffects(medusa.cards.find((c) => c.name === 'A Momentary Glance')!);
    expect(glance).toHaveLength(1);
    expect(glance[0].type).toBe(EffectType.DAMAGE);
    expect(glance[0].target).toBe('ANY_FIGHTER_IN_ZONE');
    expect(glance[0].value).toBe(2);
    expect(glance[0].fighterName).toBe('Medusa');

    const frenzy = ingestEffects(medusa.cards.find((c) => c.name === 'Winged Frenzy')!);
    expect(frenzy.map((e) => e.type)).toEqual([EffectType.MOVE, EffectType.RETURN_DEFEATED]);
    expect(frenzy[0].target).toBe('EACH_OWN_FIGHTER');
    expect(frenzy[0].canPassThroughEnemies).toBe(true);
    expect(frenzy[1].fighterName).toBe('Harpy');
    expect(frenzy[1].zoneFighterName).toBe('Medusa');
    expect(frenzy[1].optional).toBe(true);

    // Arthur textEn schemes remain honestly UNSUPPORTED (no silent no-op claim).
    // Lady of the Lake / Prophecy / Restless Spirits → UNSUPPORTED-тип из парсера;
    // Command the Storms → parsed MOVE, но 'fighter' не матчит никого (см. classify).
    for (const name of ['The Lady of the Lake', 'Prophecy', 'Restless Spirits']) {
      const card = arthur.cards.find((c) => c.name === name)!;
      const effects = ingestEffects(card);
      expect(effects.some((e) => e.type === EffectType.UNSUPPORTED)).toBe(true);
    }
    const storms = ingestEffects(arthur.cards.find((c) => c.name === 'Command the Storms')!);
    expect(storms[0].type).toBe(EffectType.MOVE);
    expect(storms[0].fighterName).toBe('fighter');
  });

  it('Excalibur is TRULY blank: no printed text, no effect fields, no parse output', () => {
    const excalibur = arthur.cards.find((c) => c.name === 'Excalibur')!;
    expect(excalibur.textEn.trim()).toBe('');
    expect(excalibur.effectImmediately).toBeNull();
    expect(excalibur.effectDuring).toBeNull();
    expect(excalibur.effectAfter).toBeNull();
    expect(excalibur.effectBoost).toBeNull();
    expect(excalibur.effectOngoing).toBeNull();
    expect(excalibur.effects).toEqual([]);
    // Even a paranoid direct parse of every field yields nothing.
    const paranoid = parseCardEffectTexts(
      {
        immediately: excalibur.effectImmediately,
        during: excalibur.effectDuring,
        after: excalibur.effectAfter,
        boost: excalibur.effectBoost,
        ongoing: excalibur.effectOngoing,
        fullText: excalibur.textEn,
      },
      excalibur.id,
    );
    expect(paranoid.effects).toEqual([]);
    // Shared-title divergence is NOT normalized away: Medusa Feint (boost 2)
    // vs Arthur Feint (boost 1) stay separate content-keyed records.
    const medusaFeint = medusa.cards.find((c) => c.name === 'Feint')! as CaptureCard & { boostValue: number };
    const arthurFeint = arthur.cards.find((c) => c.name === 'Feint')! as CaptureCard & { boostValue: number };
    expect(medusaFeint.id).not.toBe(arthurFeint.id);
    expect(medusaFeint.boostValue).not.toBe(arthurFeint.boostValue);
    expect(registry.filter((e) => e.name === 'Feint')).toHaveLength(2);
  });

  it('parser progressed to v8 and every ingest effect carries a parser version or source', () => {
    expect(PARSER_VERSION).toBeGreaterThanOrEqual(8);
    for (const entry of registry) {
      const card = [...medusa.cards, ...arthur.cards].find((c) => c.name === entry.name
        && ((entry.hero === 'Medusa' && medusa.cards.includes(c))
          || (entry.hero === 'King Arthur' && arthur.cards.includes(c))))!;
      for (const effect of ingestEffects(card)) {
        expect(effect.source === 'parser' || effect.source === 'manual' || effect.parserVersion).toBeDefined();
      }
    }
  });

  it('prints the executable registry for evidence capture', () => {
    const line = (e: RegistryEntry) =>
      `${e.hero === 'Medusa' ? 'MED' : 'ART'} | ${e.name.padEnd(26)} | x${e.count} | ${e.status.padEnd(10)} | ${e.notes}`;
    console.log(['GD-019 registry (parser v' + PARSER_VERSION + '):', ...registry.map(line)].join('\n'));
  });

  it('writes the machine-readable registry to evidence (s05-card-registry.json)', () => {
    const outDir = path.resolve(__dirname, '../../../..', 'docs/game-design/evidence/S05');
    fs.mkdirSync(outDir, { recursive: true });
    const records = registry.map((entry) => {
      const source = entry.hero === 'Medusa' ? medusa : arthur;
      const card = source.cards.find((c) => c.name === entry.name)!;
      return {
        hero: entry.hero,
        contentKey: card.id,
        name: entry.name,
        cardType: card.cardType,
        count: entry.count,
        printedText: card.textEn.trim(),
        parsedEffects: ingestEffects(card).map((e) => ({
          type: e.type,
          value: e.value,
          target: e.target,
          fighterName: e.fighterName,
          zoneFighterName: e.zoneFighterName,
          when: e.when?.kind,
          optional: e.optional,
          canPassThroughEnemies: e.canPassThroughEnemies,
          timing: e.timing,
          source: e.source,
          parserVersion: e.parserVersion,
        })),
        status: entry.status,
        notes: entry.notes,
      };
    });
    const byStatus = (status: SupportStatus) => registry.filter((e) => e.status === status).length;
    fs.writeFileSync(
      path.join(outDir, 's05-card-registry.json'),
      JSON.stringify(
        {
          task: 'GD-019',
          parserVersion: PARSER_VERSION,
          sources: [
            'docs/game-design/evidence/S01/content-medusa.json',
            'docs/game-design/evidence/S01/content-king-arthur.json',
          ],
          totals: {
            records: registry.length,
            copies: registry.reduce((s, e) => s + e.count, 0),
            medusaRecords: registry.filter((e) => e.hero === 'Medusa').length,
            kingArthurRecords: registry.filter((e) => e.hero === 'King Arthur').length,
            byStatus: {
              SUPPORTED: byStatus('SUPPORTED'),
              PARTIAL: byStatus('PARTIAL'),
              UNSUPPORTED: byStatus('UNSUPPORTED'),
              BLANK: byStatus('BLANK'),
            },
          },
          records,
        },
        null,
        2,
      ) + '\n',
      'utf8',
    );
    expect(fs.existsSync(path.join(outDir, 's05-card-registry.json'))).toBe(true);
  });
});
