/**
 * Фиксы по результатам полного аудита БД против scraped-данных (июнь 2026).
 * Идемпотентный — безопасно запускать повторно.
 *
 * 1. Buffy: герой полностью отсутствовал (slug 'buffy' не был в heroKeys
 *    seed-scraped.ts) — создаётся с колодой из scraped-data.
 * 2. Krang и Shredder: строки в Hero содержали NPC-злодеев из villains.json
 *    (lore-описание вместо способности, hp злодея, 0 карт). Конвертируются
 *    в играбельных героев из heroes/{krang,shredder}.json с колодами
 *    (10 и 13 уникальных карт). NPC-версии (Adventures: TMNT) при этом
 *    не сохраняются — Hero.name уникален.
 * 3. NPC-злодеи/миньоны: set хранил слаг сета вместо названия, color лежал
 *    только в properties (колонка NULL), hasTokens не переносился,
 *    у миньонов imageUrl дублировал avatar вместо cardBackImage.
 * 4. Board 'Unknown': артефакт бага parseSetsData (читал setData.name,
 *    реальное поле — title) — удаляется.
 * 5. Board.set: слаг сета → название (по sets.json).
 * 6. Shakespeare, карта Horror (5 строк по 1 копии): все строки получили
 *    один и тот же арт — раздаются 5 разных EN/RU артов из источника.
 *
 * Запуск: npx ts-node --transpile-only -e "require('./prisma/fix-audit-findings.ts')"
 */

import { PrismaClient } from '@prisma/client';
import * as fs from 'fs';
import * as path from 'path';

const prisma = new PrismaClient();

const SCRAPED_ROOT = path.join(__dirname, '../../scraped-data/api');

// ============================================
// Парсинг devalue-формата
// ============================================

function loadData(relPath: string): any[] | null {
  const filePath = path.join(SCRAPED_ROOT, relPath);
  if (!fs.existsSync(filePath)) return null;
  const raw = JSON.parse(fs.readFileSync(filePath, 'utf-8'));
  const node = raw.nodes?.[2];
  if (!node?.data || !Array.isArray(node.data)) return null;
  return node.data as any[];
}

function makeResolver(data: any[]) {
  return (ref: any): any =>
    typeof ref === 'number' && ref >= 0 && ref < data.length ? data[ref] : ref;
}

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

function parseDeck(data: any[], heroName: string): ParsedCard[] {
  const res = makeResolver(data);
  const cards: ParsedCard[] = [];

  for (const item of data) {
    if (!item || typeof item !== 'object' || Array.isArray(item)) continue;
    if (!('bannerName' in item) || !('card' in item)) continue;

    const cardSchema = res(item.card);
    if (!cardSchema || typeof cardSchema !== 'object') continue;

    const title = res(cardSchema.title);
    if (!title || typeof title !== 'string') continue;

    const card: ParsedCard = {
      title,
      type: res(item.type) || 'versatile',
      value: res(item.value) ?? null,
      boostValue: res(item.boostValue) ?? null,
      copies: res(item.copies) || 1,
      effect: res(cardSchema.effect) || null,
      image: res(item.image) || null,
      bannerName: res(item.bannerName) || heroName,
      effectAfter: res(cardSchema.effectAfter) || null,
      effectDuring: res(cardSchema.effectDuring) || null,
      effectBoost: res(cardSchema.effectBoost) || null,
      effectImmediately: res(cardSchema.effectImmediately) || null,
      effectOngoing: res(cardSchema.effectOngoing) || null,
    };

    const i18nData = res(item.i18n);
    if (i18nData && typeof i18nData === 'object') {
      const ruData = res(i18nData.ru);
      if (ruData && typeof ruData === 'object') {
        card.imageRu = res(ruData.image) || null;
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

function parseSidekicks(data: any[], sidekickIndexes: any[]): any[] {
  const res = makeResolver(data);
  const sidekicks: any[] = [];
  if (!Array.isArray(sidekickIndexes)) return sidekicks;

  for (const skIndex of sidekickIndexes) {
    if (typeof skIndex !== 'number') continue;
    const sk = res(skIndex);
    if (!sk || typeof sk !== 'object') continue;
    sidekicks.push({
      name: res(sk.name) || 'Unknown',
      health: res(sk.startHealth) ?? res(sk.health) ?? 1,
      movement: res(sk.move) ?? res(sk.movement) ?? 1,
      attackType: res(sk.attack) || 'melee',
      avatarUrl: res(sk.avatar) || null,
    });
  }
  return sidekicks;
}

function cardCreateData(card: ParsedCard, heroId: string) {
  const normalizedType = normalizeCardType(card.type);
  return {
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
    heroId,
    imageUrl: card.image || null,
    imageUrlRu: card.imageRu || null,
  };
}

function parseHeroFields(data: any[]) {
  const res = makeResolver(data);
  const h = data[1];
  const setObj = res(h.set);
  return {
    name: res(h.name) as string,
    set: (res(setObj?.title) as string) || '',
    health: (res(h.startHealth) as number) || 18,
    movement: (res(h.move) as number) || 2,
    color: (res(h.color) as string) || null,
    specialAbility: (res(h.specialAbility) as string) || '',
    hasTokens: Boolean(res(h.hasTokens)),
    hasSidekicks: Boolean(res(h.hasSidekicks)),
    sidekicks: parseSidekicks(data, res(h.sidekicks) || []),
    avatarUrl: (res(h.avatar) as string) || null,
    cardBackImage: (res(h.cardBackImage) as string) || null,
    characterCardImage: (res(h.characterCardImage) as string) || null,
    miniatureModel: (res(h.miniatureModel) as string) || null,
    additionalMiniImages: res(h.additionalMiniImages) || [],
    additionalMiniModels: res(h.additionalMiniModels) || [],
  };
}

// ============================================
// 1+2. Buffy (создать) и Krang/Shredder (конвертировать из NPC в героев)
// ============================================

async function importOrConvertHero(slug: string): Promise<void> {
  const data = loadData(`heroes/${slug}.json`);
  if (!data) {
    console.log(`   ⚠️  Не удалось загрузить heroes/${slug}.json`);
    return;
  }

  const hero = parseHeroFields(data);
  const deck = parseDeck(data, hero.name);

  const existing = await prisma.hero.findUnique({
    where: { name: hero.name },
    include: { cards: { select: { name: true } } },
  });

  // Идемпотентность: герой уже играбельный и колода совпадает — пропуск
  if (existing) {
    const dbNames = new Set(existing.cards.map((c) => c.name));
    const srcNames = new Set(deck.map((c) => c.title));
    const sameDeck =
      dbNames.size === srcNames.size && [...srcNames].every((n) => dbNames.has(n));
    if (existing.fighterType === 'HERO' && sameDeck) {
      console.log(`   ⏭️  ${hero.name}: уже актуален (${deck.length} карт)`);
      return;
    }
  }

  const heroData = {
    name: hero.name,
    nameEn: hero.name,
    nameRu: hero.name,
    set: hero.set,
    health: hero.health,
    fighterType: 'HERO',
    movement: hero.movement,
    color: hero.color,
    ability: {
      type: 'CUSTOM',
      timing: 'PASSIVE',
      effect: hero.specialAbility,
      description: hero.specialAbility,
    },
    deckCards: [],
    properties: {
      hasSidekick: hero.hasSidekicks,
      sidekickCount: hero.sidekicks.length,
    },
    hasTokens: hero.hasTokens,
    sidekicks: hero.sidekicks,
    additionalMinis: {
      images: hero.additionalMiniImages,
      models: hero.additionalMiniModels,
    },
    imageUrl: hero.cardBackImage || '',
    avatarUrl: hero.avatarUrl || '',
    characterCardUrl: hero.characterCardImage,
    miniModelUrl: hero.miniatureModel,
  };

  await prisma.$transaction(async (tx) => {
    let heroId: string;
    if (existing) {
      await tx.hero.update({ where: { id: existing.id }, data: heroData });
      const deleted = await tx.card.deleteMany({ where: { heroId: existing.id } });
      heroId = existing.id;
      console.log(
        `   🔄 ${hero.name}: NPC → играбельный герой (hp ${hero.health}, move ${hero.movement}); удалено ${deleted.count} старых карт`,
      );
    } else {
      const created = await tx.hero.create({ data: heroData });
      heroId = created.id;
      console.log(`   ✅ ${hero.name}: создан герой (hp ${hero.health}, move ${hero.movement})`);
    }

    for (const card of deck) {
      await tx.card.create({ data: cardCreateData(card, heroId) });
    }
    console.log(`   ✅ ${hero.name}: создано ${deck.length} карт колоды`);
  });
}

// ============================================
// 3. NPC-злодеи и миньоны: set/color/hasTokens/imageUrl
// ============================================

interface NpcInfo {
  name: string;
  setTitle: string;
  color: string | null;
  hasTokens: boolean;
  cardBackImage: string | null;
}

function parseNpcList(relPath: string): NpcInfo[] {
  const data = loadData(relPath);
  if (!data) return [];
  const res = makeResolver(data);
  const indices = data[1];
  if (!Array.isArray(indices)) return [];

  const npcs: NpcInfo[] = [];
  for (const idx of indices) {
    const item = res(idx);
    if (!item || typeof item !== 'object') continue;
    const setObj = res(item.set);
    npcs.push({
      name: res(item.name),
      setTitle: res(setObj?.title) || '',
      color: res(item.color) || null,
      hasTokens: Boolean(res(item.hasTokens)) || (res(item.tokens) || []).length > 0,
      cardBackImage: res(item.cardBackImage) || null,
    });
  }
  return npcs;
}

async function fixNpcs(): Promise<void> {
  const npcs = [...parseNpcList('villains.json'), ...parseNpcList('minions.json')];
  console.log(`   Источник: ${npcs.length} NPC (villains + minions)`);

  for (const npc of npcs) {
    const hero = await prisma.hero.findUnique({ where: { name: npc.name } });
    if (!hero) continue; // Krang/Shredder конвертированы в героев — их NPC-версии не трогаем
    if (hero.fighterType !== 'VILLAIN' && hero.fighterType !== 'MINION') continue;

    const data: Record<string, any> = {};
    if (npc.setTitle && hero.set !== npc.setTitle) data.set = npc.setTitle;
    if (npc.color && hero.color !== npc.color) data.color = npc.color;
    if (npc.hasTokens && !hero.hasTokens) data.hasTokens = true;
    if (npc.cardBackImage && hero.imageUrl !== npc.cardBackImage)
      data.imageUrl = npc.cardBackImage;

    if (Object.keys(data).length > 0) {
      await prisma.hero.update({ where: { id: hero.id }, data });
      console.log(`   ✅ ${npc.name}: ${Object.keys(data).join(', ')}`);
    }
  }
}

// ============================================
// 4+5. Доски: удалить артефакт Unknown, set слаг → название
// ============================================

async function fixBoards(): Promise<void> {
  // Артефакт parseSetsData
  const unknown = await prisma.board.findFirst({ where: { name: 'Unknown' } });
  if (unknown) {
    const games = await prisma.game.count({ where: { boardId: unknown.id } });
    if (games === 0) {
      await prisma.board.delete({ where: { id: unknown.id } });
      console.log(`   🗑️  Удалена фейковая доска 'Unknown'`);
    } else {
      console.log(`   ⚠️  Доска 'Unknown' используется в ${games} играх — не удалена`);
    }
  }

  // Маппинг key → title из sets.json
  const data = loadData('sets.json');
  if (!data) {
    console.log('   ⚠️  Не удалось загрузить sets.json');
    return;
  }
  const res = makeResolver(data);
  const indices = data[1];
  if (!Array.isArray(indices)) return;

  const keyToTitle = new Map<string, string>();
  for (const idx of indices) {
    const item = res(idx);
    if (!item || typeof item !== 'object') continue;
    const key = res(item.key);
    const title = res(item.title);
    if (key && title) keyToTitle.set(key, title);
  }

  for (const [key, title] of keyToTitle) {
    const result = await prisma.board.updateMany({
      where: { set: key },
      data: { set: title },
    });
    if (result.count > 0) console.log(`   ✅ Доски: set '${key}' → '${title}' (${result.count} шт.)`);
  }
}

// ============================================
// 6. Shakespeare Horror: 5 разных артов
// ============================================

async function fixHorrorArts(): Promise<void> {
  const data = loadData('heroes/shakespeare.json');
  if (!data) {
    console.log('   ⚠️  Не удалось загрузить shakespeare.json');
    return;
  }

  const hero = await prisma.hero.findUnique({ where: { name: 'Shakespeare' } });
  if (!hero) {
    console.log('   ⚠️  Shakespeare не найден в БД');
    return;
  }

  const deck = parseDeck(data, 'Shakespeare');
  const horrorArts = deck.filter((c) => c.title === 'Horror');
  const horrorRows = await prisma.card.findMany({
    where: { heroId: hero.id, name: 'Horror' },
    orderBy: { id: 'asc' },
  });

  if (horrorArts.length !== horrorRows.length) {
    console.log(
      `   ⚠️  Horror: в источнике ${horrorArts.length} вариантов, в БД ${horrorRows.length} строк — пропуск`,
    );
    return;
  }

  for (let i = 0; i < horrorRows.length; i++) {
    const row = horrorRows[i];
    const art = horrorArts[i];
    if (row.imageUrl !== art.image || row.imageUrlRu !== (art.imageRu || null)) {
      await prisma.card.update({
        where: { id: row.id },
        data: { imageUrl: art.image, imageUrlRu: art.imageRu || null },
      });
    }
  }
  console.log(`   ✅ Horror: розданы ${horrorRows.length} уникальных артов (EN+RU)`);
}

// ============================================
// main
// ============================================

async function main() {
  console.log('🌱 Фиксы по результатам аудита БД против scraped-данных...\n');

  console.log('🦸 Buffy / Krang / Shredder:');
  await importOrConvertHero('buffy');
  await importOrConvertHero('krang');
  await importOrConvertHero('shredder');

  console.log('\n🦹 NPC-злодеи и миньоны (set/color/hasTokens/imageUrl):');
  await fixNpcs();

  console.log('\n🗺️  Доски:');
  await fixBoards();

  console.log('\n🃏 Shakespeare Horror:');
  await fixHorrorArts();

  // Контрольные проверки
  const heroes = await prisma.hero.count();
  const cards = await prisma.card.count();
  const valueGaps = await prisma.card.count({
    where: {
      OR: [
        { cardType: 'VERSATILE', attackValue: null },
        { cardType: 'VERSATILE', defenseValue: null },
        { cardType: 'DEFENSE', defenseValue: null },
        { cardType: 'ATTACK', attackValue: null },
      ],
    },
  });
  const slugSets = await prisma.hero.count({ where: { set: { contains: '-' } } });
  console.log(
    `\n📊 Героев: ${heroes}, карт: ${cards}, карт без значений: ${valueGaps}, героев со slug-set: ${slugSets}`,
  );
}

main()
  .catch((e) => {
    console.error('❌ Ошибка:', e);
    process.exit(1);
  })
  .finally(async () => {
    await prisma.$disconnect();
  });
