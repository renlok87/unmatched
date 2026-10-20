/**
 * Точечный фикс дыр в данных карт (идемпотентный):
 *
 * 1. Семь карт, у которых на сайте-источнике value = null, — значения прочитаны
 *    с напечатанных карт (картинки в supabase storage):
 *    - Control The Demon (Ghost Rider, versatile)        → 0 (растёт от Hellfire)
 *    - I Think We're Back In Business (Dr. Sattler)      → 0 (= карт в руке)
 *    - Stones in the Belly 🌹 (Little Red, versatile)    → 2
 *    - Time out time out time out! (Deadpool, versatile) → 0
 *    - Lady Justice (She Hulk, defense)                  → 0
 *    - Life Model Decoy (Black Widow, defense)           → 0
 *    - Skin Like Titanium (Luke Cage, defense)           → 0
 *
 * 2. Ms. Marvel и Daredevil были созданы базовым seed.ts с выдуманными колодами
 *    (Punch, Flight, Acrobatics и т.п.) и неверными характеристиками, из-за чего
 *    seed-scraped.ts пропустил их по имени. Скрипт обновляет героев и заменяет
 *    колоды реальными данными из scraped-data/api/heroes/{ms-marvel,daredevil}.json.
 *
 * 3. Разбор DE 2026-10-20 (docs/research/de-reverse-2026-10-20, DATA-01):
 *    - What Big Eyes You Have 🐺 (Little Red, versatile) → 3 (в источнике 2);
 *    - опечатки банеров BANNER_FIXES (prisma/card-banner-fixes.ts): Allice,
 *      The Potter, Djkstra. После правки скрипт проверяет банеры всех карт
 *      (findBannerMismatches) и печатает остаток.
 *
 * Запуск: npx ts-node --transpile-only -e "require('./prisma/fix-card-gaps.ts')"
 * Только отчёт, без записи: FIX_DRY_RUN=1 в окружении или
 *   npx ts-node --transpile-only prisma/fix-card-gaps.ts --dry-run
 */

import { PrismaClient } from '@prisma/client';
import * as fs from 'fs';
import * as path from 'path';
import { applyBannerFix, BANNER_FIXES, findBannerMismatches } from './card-banner-fixes';

const prisma = new PrismaClient();

const DRY_RUN = process.argv.includes('--dry-run') || process.env.FIX_DRY_RUN === '1';

const SCRAPED_DATA_PATH = path.join(__dirname, '../../scraped-data/api/heroes');

// ============================================
// 1. Значения карт, отсутствующие в источнике
// ============================================

interface ValueFix {
  name: string;
  heroName: string;
  cardType: string;
  value: number;
}

const VALUE_FIXES: ValueFix[] = [
  { name: 'Control The Demon', heroName: 'Ghost Rider', cardType: 'VERSATILE', value: 0 },
  { name: "I Think We're Back In Business", heroName: 'Dr. Sattler', cardType: 'VERSATILE', value: 0 },
  { name: 'Stones in the Belly 🌹', heroName: 'Little Red', cardType: 'VERSATILE', value: 2 },
  { name: 'Time out time out time out!', heroName: 'Deadpool', cardType: 'VERSATILE', value: 0 },
  { name: 'Lady Justice', heroName: 'She Hulk', cardType: 'DEFENSE', value: 0 },
  { name: 'Life Model Decoy', heroName: 'Black Widow', cardType: 'DEFENSE', value: 0 },
  { name: 'Skin Like Titanium', heroName: 'Luke Cage', cardType: 'DEFENSE', value: 0 },
  // DATA-01: в источнике 2, на карте и в DE — 3
  { name: 'What Big Eyes You Have 🐺', heroName: 'Little Red', cardType: 'VERSATILE', value: 3 },
];

async function fixMissingValues(): Promise<void> {
  console.log('🔧 Фикс значений карт (value=null в источнике и неверные значения)...');

  for (const fix of VALUE_FIXES) {
    const hero = await prisma.hero.findUnique({ where: { name: fix.heroName } });
    if (!hero) {
      console.log(`   ⚠️  Герой не найден: ${fix.heroName}`);
      continue;
    }

    const data: { attackValue?: number; defenseValue?: number } = {};
    if (fix.cardType === 'VERSATILE') {
      data.attackValue = fix.value;
      data.defenseValue = fix.value;
    } else if (fix.cardType === 'DEFENSE') {
      data.defenseValue = fix.value;
    } else {
      data.attackValue = fix.value;
    }

    const cards = await prisma.card.findMany({
      where: { name: fix.name, heroId: hero.id },
      select: { attackValue: true, defenseValue: true },
    });
    if (cards.length === 0) {
      console.log(`   ⚠️  Карта не найдена: ${fix.name} (${fix.heroName})`);
      continue;
    }
    const stale = cards.filter(
      (c) =>
        (data.attackValue !== undefined && c.attackValue !== data.attackValue) ||
        (data.defenseValue !== undefined && c.defenseValue !== data.defenseValue),
    );
    if (stale.length === 0) {
      console.log(`   ⏭️  ${fix.name} (${fix.heroName}): уже value=${fix.value}`);
      continue;
    }
    if (DRY_RUN) {
      console.log(`   📝 [dry-run] ${fix.name} (${fix.heroName}): value → ${fix.value} (${stale.length} стр.)`);
      continue;
    }

    await prisma.card.updateMany({ where: { name: fix.name, heroId: hero.id }, data });
    console.log(`   ✅ ${fix.name} (${fix.heroName}): value=${fix.value}`);
  }
}

// ============================================
// 3. Банеры карт (DATA-01 / DATA-02)
// ============================================

async function fixBanners(): Promise<void> {
  console.log('🔧 Опечатки банеров (BANNER_FIXES)...');

  for (const fix of BANNER_FIXES) {
    const hero = await prisma.hero.findUnique({ where: { name: fix.heroName } });
    if (!hero) {
      console.log(`   ⚠️  Герой не найден: ${fix.heroName}`);
      continue;
    }
    const cards = await prisma.card.findMany({
      where: { heroId: hero.id, bannerName: fix.from },
      select: { name: true },
    });
    if (cards.length === 0) {
      console.log(`   ⏭️  ${fix.heroName}: банера «${fix.from}» нет`);
      continue;
    }
    const names = cards.map((c) => c.name).join(', ');
    if (DRY_RUN) {
      console.log(`   📝 [dry-run] ${fix.heroName}: «${fix.from}» → «${fix.to}» (${cards.length}): ${names}`);
      continue;
    }
    const result = await prisma.card.updateMany({
      where: { heroId: hero.id, bannerName: fix.from },
      data: { bannerName: fix.to },
    });
    console.log(`   ✅ ${fix.heroName}: «${fix.from}» → «${fix.to}» (${result.count}): ${names}`);
  }
}

/** Банеры всех карт против героя и его помощников (в dry-run — с учётом будущих правок). */
async function reportBannerMismatches(): Promise<number> {
  const heroes = await prisma.hero.findMany({
    select: { name: true, sidekicks: true, cards: { select: { name: true, bannerName: true } } },
  });
  const mismatches = heroes.flatMap((hero) =>
    findBannerMismatches(
      {
        name: hero.name,
        sidekicks: Array.isArray(hero.sidekicks)
          ? (hero.sidekicks as Array<{ name?: string | null } | null>).map((s) => ({ name: s?.name ?? '' }))
          : [],
      },
      hero.cards.map((c) => ({
        name: c.name,
        bannerName: DRY_RUN ? applyBannerFix(hero.name, c.bannerName) : c.bannerName,
      })),
    ),
  );
  for (const m of mismatches) {
    console.log(`   ❌ ${m.heroName} — ${m.cardName}: «${m.bannerName}»`);
  }
  return mismatches.length;
}

// ============================================
// 2. Замена фейковых данных Ms. Marvel / Daredevil
//    (парсер devalue-формата — как в seed-scraped.ts)
// ============================================

interface ParsedCard {
  title: string;
  type: string;
  value: number | null;
  boostValue: number | null;
  copies: number;
  effect: string | null;
  image?: string | null;
  imageRu?: string | null;
  bannerName?: string | null;
  effectAfter?: string | null;
  effectDuring?: string | null;
  effectBoost?: string | null;
  effectImmediately?: string | null;
  effectOngoing?: string | null;
}

function resolveValue(data: any[], index: number | null | undefined): any {
  if (index === null || index === undefined || typeof index !== 'number' || index < 0) return null;
  return data[index];
}

function parseDeck(data: any[], heroName: string): ParsedCard[] {
  const cards: ParsedCard[] = [];

  for (const item of data) {
    if (!item || typeof item !== 'object' || Array.isArray(item)) continue;
    if (!('bannerName' in item) || !('card' in item)) continue;

    const cardSchema = resolveValue(data, item.card);
    if (!cardSchema || typeof cardSchema !== 'object') continue;

    const title = resolveValue(data, cardSchema.title);
    if (!title || typeof title !== 'string') continue;

    const card: ParsedCard = {
      title,
      type: resolveValue(data, item.type) || 'versatile',
      value: resolveValue(data, item.value) ?? null,
      boostValue: resolveValue(data, item.boostValue) ?? null,
      copies: resolveValue(data, item.copies) || 1,
      effect: resolveValue(data, cardSchema.effect) || null,
      image: resolveValue(data, item.image) || null,
      bannerName: resolveValue(data, item.bannerName) || heroName,
      effectAfter: resolveValue(data, cardSchema.effectAfter) || null,
      effectDuring: resolveValue(data, cardSchema.effectDuring) || null,
      effectBoost: resolveValue(data, cardSchema.effectBoost) || null,
      effectImmediately: resolveValue(data, cardSchema.effectImmediately) || null,
      effectOngoing: resolveValue(data, cardSchema.effectOngoing) || null,
    };

    const i18nData = resolveValue(data, item.i18n);
    if (i18nData && typeof i18nData === 'object') {
      const ruData = resolveValue(data, i18nData.ru);
      if (ruData && typeof ruData === 'object') {
        card.imageRu = resolveValue(data, ruData.image) || null;
      }
    }

    cards.push(card);
  }

  return cards;
}

function normalizeCardType(type: string): string {
  const typeMap: Record<string, string> = {
    attack: 'ATTACK',
    defense: 'DEFENSE',
    scheme: 'SCHEME',
    versatile: 'VERSATILE',
    maneuver: 'MANEUVER',
  };
  return typeMap[type.toLowerCase()] || type.toUpperCase();
}

async function replaceFakeHero(slug: string): Promise<void> {
  const filePath = path.join(SCRAPED_DATA_PATH, `${slug}.json`);
  if (!fs.existsSync(filePath)) {
    console.log(`   ⚠️  Нет файла: ${filePath}`);
    return;
  }

  const rawData = JSON.parse(fs.readFileSync(filePath, 'utf-8'));
  const data = rawData.nodes?.[2]?.data as any[];
  const heroSchema = data?.[1];
  if (!heroSchema || typeof heroSchema !== 'object') {
    console.log(`   ⚠️  Не удалось распарсить: ${slug}`);
    return;
  }

  const heroName = resolveValue(data, heroSchema.name);
  const setObj = resolveValue(data, heroSchema.set);
  const deck = parseDeck(data, heroName);

  const existingHero = await prisma.hero.findUnique({ where: { name: heroName } });
  if (!existingHero) {
    console.log(`   ⚠️  Герой не найден в БД: ${heroName}`);
    return;
  }

  // Идемпотентность: если колода уже совпадает со scraped-данными, не трогаем
  const existingCards = await prisma.card.findMany({
    where: { heroId: existingHero.id },
    select: { name: true },
  });
  const existingNames = new Set(existingCards.map((c) => c.name));
  const scrapedNames = new Set(deck.map((c) => c.title));
  const sameDeck =
    existingNames.size === scrapedNames.size &&
    [...scrapedNames].every((n) => existingNames.has(n));

  if (sameDeck) {
    console.log(`   ⏭️  ${heroName}: колода уже актуальна (${deck.length} карт)`);
    return;
  }
  if (DRY_RUN) {
    console.log(`   📝 [dry-run] ${heroName}: колода будет заменена (${existingNames.size} → ${deck.length} карт)`);
    return;
  }

  await prisma.$transaction(async (tx) => {
    await tx.hero.update({
      where: { id: existingHero.id },
      data: {
        set: resolveValue(data, setObj?.title) || existingHero.set,
        health: resolveValue(data, heroSchema.startHealth) || existingHero.health,
        movement: resolveValue(data, heroSchema.move) || existingHero.movement,
        color: resolveValue(data, heroSchema.color) || existingHero.color,
        ability: {
          type: 'CUSTOM',
          timing: 'PASSIVE',
          effect: resolveValue(data, heroSchema.specialAbility) || '',
          description: resolveValue(data, heroSchema.specialAbility) || '',
        },
        hasTokens: resolveValue(data, heroSchema.hasTokens) || false,
        imageUrl: resolveValue(data, heroSchema.cardBackImage) || existingHero.imageUrl,
        avatarUrl: resolveValue(data, heroSchema.avatar) || existingHero.avatarUrl,
        characterCardUrl:
          resolveValue(data, heroSchema.characterCardImage) || existingHero.characterCardUrl,
        miniModelUrl:
          resolveValue(data, heroSchema.miniatureModel) || existingHero.miniModelUrl,
      },
    });

    const deleted = await tx.card.deleteMany({ where: { heroId: existingHero.id } });
    console.log(`   🗑️  ${heroName}: удалено ${deleted.count} фейковых карт`);

    for (const card of deck) {
      const normalizedType = normalizeCardType(card.type);
      await tx.card.create({
        data: {
          name: card.title,
          nameEn: card.title,
          nameRu: card.title,
          cardType: normalizedType,
          subType: normalizedType === 'MANEUVER' ? 'Movement' : null,
          // VERSATILE играется и как атака, и как защита — значение в оба поля
          attackValue:
            normalizedType === 'ATTACK' || normalizedType === 'VERSATILE' ? card.value : null,
          defenseValue:
            normalizedType === 'DEFENSE' || normalizedType === 'VERSATILE' ? card.value : null,
          boostValue: card.boostValue,
          bannerName: card.bannerName || null,
          effects: [],
          text: card.effect || '',
          textEn: card.effect || '',
          textRu: card.effect || '',
          effectAfter: card.effectAfter || null,
          effectDuring: card.effectDuring || null,
          effectBoost: card.effectBoost || null,
          effectImmediately: card.effectImmediately || null,
          effectOngoing: card.effectOngoing || null,
          count: card.copies,
          heroId: existingHero.id,
          imageUrl: card.image || null,
          imageUrlRu: card.imageRu || null,
        },
      });
      console.log(`   ✅ ${heroName}: создана карта ${card.title} (${card.copies} шт.)`);
    }
  });
}

async function main() {
  console.log('🌱 Фикс дыр в данных карт...\n');

  if (DRY_RUN) console.log('📝 DRY-RUN: БД не меняется\n');

  await fixMissingValues();

  console.log('');
  await fixBanners();

  console.log('\n🔧 Замена фейковых колод Ms. Marvel / Daredevil...');
  await replaceFakeHero('ms-marvel');
  await replaceFakeHero('daredevil');

  // Контрольная проверка
  const gaps = await prisma.card.count({
    where: {
      OR: [
        { cardType: 'VERSATILE', attackValue: null },
        { cardType: 'VERSATILE', defenseValue: null },
        { cardType: 'DEFENSE', defenseValue: null },
        { cardType: 'ATTACK', attackValue: null },
      ],
    },
  });
  console.log(`\n📊 Карт с пропущенными значениями: ${gaps}`);

  console.log('\n🔎 Банеры карт против героя и помощников...');
  const bannerMismatches = await reportBannerMismatches();
  console.log(`📊 Карт с чужим банером: ${bannerMismatches}`);
  if (bannerMismatches > 0) process.exitCode = 1;
}

main()
  .catch((e) => {
    console.error('❌ Ошибка:', e);
    process.exit(1);
  })
  .finally(async () => {
    await prisma.$disconnect();
  });
