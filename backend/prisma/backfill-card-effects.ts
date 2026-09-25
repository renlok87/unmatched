/**
 * Backfill: структурированные Card.effects из текстовых полей
 * (effectImmediately/effectDuring/effectAfter) через effect-text-parser.
 *
 * Идемпотентный:
 * - карты, у которых effects уже содержит хоть один эффект source:'manual',
 *   НЕ перезаписываются (ручная правка через админку — приоритет);
 * - parser-эффекты перегенерируются (parserVersion растёт — повторный запуск
 *   обновляет разбор без потери ручного).
 *
 * Флаги:
 *   --dry-run        — только отчёт, БД не трогаем
 *   --hero=<name>    — только карты героя (точное имя из БД, напр. Medusa)
 *
 * Запуск (в контейнере, DATABASE_URL уже настроен):
 *   docker exec unmatched-backend npx ts-node --transpile-only \
 *     prisma/backfill-card-effects.ts -- --dry-run
 */

import { PrismaClient } from '@prisma/client';
import {
  parseCardEffectTexts,
  PARSER_VERSION,
} from '../src/game-engine/effects/effect-text-parser';
import { CardEffect, EffectType } from '../src/game-engine/models/card.model';

const prisma = new PrismaClient();

const DRY_RUN = process.argv.includes('--dry-run');
const HERO_ARG = process.argv.find((a) => a.startsWith('--hero='))?.slice('--hero='.length);

interface HeroReport {
  total: number;
  withTexts: number;
  parsed: number;
  unsupportedCards: number;
  manualKept: number;
  unsupportedTexts: string[];
}

async function main() {
  console.log(
    `🧩 Backfill Card.effects (parser v${PARSER_VERSION})${DRY_RUN ? ' [DRY-RUN]' : ''}` +
      `${HERO_ARG ? ` [hero=${HERO_ARG}]` : ''}\n`,
  );

  const cards = await prisma.card.findMany({
    where: HERO_ARG ? { hero: { name: HERO_ARG } } : undefined,
    include: { hero: { select: { name: true } } },
    orderBy: [{ heroId: 'asc' }, { name: 'asc' }],
  });
  if (cards.length === 0) {
    console.log('Карты не найдены (проверь --hero=<точное имя из БД>)');
    return;
  }

  const byHero = new Map<string, HeroReport>();
  let updated = 0;

  for (const card of cards) {
    const heroName = card.hero?.name ?? '???';
    const report = byHero.get(heroName) ?? {
      total: 0,
      withTexts: 0,
      parsed: 0,
      unsupportedCards: 0,
      manualKept: 0,
      unsupportedTexts: [],
    };
    byHero.set(heroName, report);
    report.total++;

    const hasTexts = Boolean(
      card.effectImmediately?.trim() ||
        card.effectDuring?.trim() ||
        card.effectAfter?.trim() ||
        card.effectBoost?.trim() ||
        card.effectOngoing?.trim(),
    );
    // S05 (GD-019): SCHEME-карты, у которых эффект напечатан только общим
    // текстом (Card.text = textEn), а effect*-поля пусты — парсим fullText
    // как fallback (раньше такие карты молча получали effects [] = no-op).
    const fullTextFallback = card.cardType === 'SCHEME' && Boolean(card.text?.trim());
    if (!hasTexts && !fullTextFallback) continue;
    report.withTexts++;

    // Ручные эффекты — приоритет: сохраняем, парсер дополняет только их отсутствие
    const existing = readExistingEffects(card.effects);
    const manual = existing.filter((e) => e?.source === 'manual');
    if (manual.length > 0) {
      report.manualKept++;
      continue;
    }

    const { effects, unsupported } = parseCardEffectTexts(
      {
        immediately: card.effectImmediately,
        during: card.effectDuring,
        after: card.effectAfter,
        boost: card.effectBoost,
        ongoing: card.effectOngoing,
        fullText: fullTextFallback ? card.text : undefined,
      },
      card.id,
    );

    const hasUnsupported = effects.some((e) => e.type === EffectType.UNSUPPORTED);
    if (hasUnsupported) {
      report.unsupportedCards++;
      report.unsupportedTexts.push(
        ...unsupported.map((t) => `${card.name}: ${t.slice(0, 90)}`),
      );
    }
    if (effects.length > 0 && !hasUnsupported) report.parsed++;

    if (!DRY_RUN) {
      await prisma.card.update({
        where: { id: card.id },
        data: { effects: effects as unknown as object[] },
      });
      updated++;
    }
  }

  // --- Отчёт ---
  console.log('📊 Покрытие по героям (полностью распознанные / с текстами / всего карт):');
  const sorted = [...byHero.entries()].sort(
    (a, b) => b[1].withTexts - b[1].unsupportedCards - (a[1].withTexts - a[1].unsupportedCards),
  );
  let totals = { total: 0, withTexts: 0, parsed: 0, unsupportedCards: 0, manualKept: 0 };
  for (const [hero, r] of sorted) {
    totals.total += r.total;
    totals.withTexts += r.withTexts;
    totals.parsed += r.parsed;
    totals.unsupportedCards += r.unsupportedCards;
    totals.manualKept += r.manualKept;
    const mark = r.unsupportedCards === 0 && r.withTexts > 0 ? '✅' : r.withTexts === 0 ? '·' : '◐';
    console.log(
      `  ${mark} ${hero}: ${r.parsed}/${r.withTexts}/${r.total}` +
        (r.manualKept ? ` (manual: ${r.manualKept})` : ''),
    );
  }
  console.log(
    `\nИтого: карт ${totals.total}, с текстами ${totals.withTexts}, ` +
      `полностью распознано ${totals.parsed} (${pct(totals.parsed, totals.withTexts)}), ` +
      `с UNSUPPORTED ${totals.unsupportedCards}, manual сохранено ${totals.manualKept}`,
  );
  if (!DRY_RUN) console.log(`Записано в БД: ${updated} карт`);

  // Топ нераспознанных текстов — приоритеты для парсера v2 / ручной правки
  if (HERO_ARG) {
    const texts = sorted.flatMap(([, r]) => r.unsupportedTexts);
    if (texts.length > 0) {
      console.log('\n⚠️  Нераспознанные тексты:');
      texts.forEach((t) => console.log(`   ${t}`));
    }
  }
}

function readExistingEffects(raw: unknown): Array<Partial<CardEffect>> {
  if (!raw) return [];
  let value: unknown = raw;
  if (typeof value === 'string') {
    try {
      value = JSON.parse(value);
    } catch {
      return [];
    }
  }
  return Array.isArray(value) ? (value as Array<Partial<CardEffect>>) : [];
}

function pct(a: number, b: number): string {
  return b === 0 ? '—' : `${Math.round((a / b) * 100)}%`;
}

main()
  .catch((e) => {
    console.error('❌ Backfill error:', e);
    process.exit(1);
  })
  .finally(async () => {
    await prisma.$disconnect();
  });
