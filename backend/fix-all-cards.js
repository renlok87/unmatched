/**
 * Скрипт для исправления карт всех героев
 * Проблема: в оригинальном JSON значения copies, value, boostValue
 * хранятся как индексы в data-массиве, а не как прямые значения
 */

const { PrismaClient } = require('@prisma/client');
const fs = require('fs');
const path = require('path');

const prisma = new PrismaClient();
const SCRAPED_DATA_PATH = path.join(__dirname, '../scraped-data/api/heroes');

function resolveValue(data, index) {
  if (index === null || index === undefined || index < 0) return null;
  return data[index];
}

function parseDeckData(data) {
  const cards = [];

  for (let i = 0; i < data.length; i++) {
    const item = data[i];
    if (!item || typeof item !== 'object') continue;

    const heroId = item.hero;
    if (heroId !== 2 && heroId !== 1) continue;

    const cardIndex = item.card;
    if (cardIndex === null || cardIndex === undefined) continue;

    const cardSchema = resolveValue(data, cardIndex);
    if (!cardSchema || typeof cardSchema !== 'object') continue;

    const title = resolveValue(data, cardSchema.title);
    if (!title || typeof title !== 'string') continue;

    const card = {
      id: cardSchema.id || i,
      title: title,
      type: resolveValue(data, cardSchema.type) || 'versatile',
      value: resolveValue(data, cardSchema.value) || null,
      boostValue: resolveValue(data, cardSchema.boostValue) || null,
      copies: resolveValue(data, item.copies) || item.copies || 1,
      effect: resolveValue(data, cardSchema.effect) || null,
      image: resolveValue(data, cardSchema.image) || null,
    };

    cards.push(card);
  }

  return cards;
}

function parseHeroData(rawData) {
  const nodes = rawData.nodes;
  if (!nodes || nodes.length < 3 || !nodes[2] || !nodes[2].data) return null;

  const data = nodes[2].data;
  const heroSchema = data[1];

  if (!heroSchema || typeof heroSchema !== 'object') return null;

  return {
    name: resolveValue(data, heroSchema.name) || 'Unknown',
    attack: resolveValue(data, heroSchema.attack) || 'melee',
    startHealth: resolveValue(data, heroSchema.startHealth) || 18,
    specialAbility: resolveValue(data, heroSchema.specialAbility) || '',
    set: {
      key: resolveValue(data, heroSchema.set?.key) || '',
      title: resolveValue(data, heroSchema.set?.title) || '',
    },
    deck: parseDeckData(data),
  };
}

function normalizeCardType(type) {
  const typeMap = {
    'attack': 'ATTACK',
    'defense': 'DEFENSE',
    'scheme': 'SCHEME',
    'versatile': 'MANEUVER',
    'maneuver': 'MANEUVER',
  };
  return typeMap[type.toLowerCase()] || type.toUpperCase();
}

async function fixHero(heroKey) {
  const filePath = path.join(SCRAPED_DATA_PATH, `${heroKey}.json`);

  if (!fs.existsSync(filePath)) {
    return { success: false, reason: 'file_not_found' };
  }

  try {
    const rawData = fs.readFileSync(filePath, 'utf8');
    const parsed = JSON.parse(rawData);

    const hero = parseHeroData(parsed);
    if (!hero) {
      return { success: false, reason: 'parse_failed' };
    }

    // Проверяем, есть ли герой в БД
    const heroRecord = await prisma.hero.findUnique({
      where: { name: hero.name },
      include: { cards: true }
    });

    if (!heroRecord) {
      return { success: false, reason: 'hero_not_found_in_db' };
    }

    // Удаляем старые карты
    for (const card of heroRecord.cards) {
      await prisma.card.delete({ where: { id: card.id } });
    }

    // Создаём карты заново
    for (const card of hero.deck) {
      if (!card.title) continue;

      const normalizedType = normalizeCardType(card.type);

      await prisma.card.create({
        data: {
          name: card.title,
          nameEn: card.title,
          nameRu: card.title,
          cardType: normalizedType,
          subType: normalizedType === 'MANEUVER' ? 'Movement' : null,
          attackValue: normalizedType === 'ATTACK' ? card.value : null,
          defenseValue: normalizedType === 'DEFENSE' ? card.value : null,
          boostValue: card.boostValue,
          effects: [],
          text: card.effect || '',
          textEn: card.effect || '',
          textRu: card.effect || '',
          count: card.copies || 1,
          heroId: heroRecord.id,
        },
      });
    }

    return { success: true, name: hero.name, cards: hero.deck.length };
  } catch (error) {
    return { success: false, reason: 'error', error: error.message };
  }
}

async function main() {
  const heroKeys = [
    'yennenga', 'achilles', 'bloody-mary', 'sun-wukong', 'daredevil',
    'ms-marvel', 'beowulf', 'king-arthur', 'dracula', 'jekyll-hyde'
  ];

  console.log('🔧 Исправление карт героев...\n');

  let fixed = 0;
  let failed = 0;

  for (const heroKey of heroKeys) {
    const result = await fixHero(heroKey);

    if (result.success) {
      console.log(`✅ ${result.name}: ${result.cards} карт`);
      fixed++;
    } else {
      console.log(`❌ ${heroKey}: ${result.reason}`);
      failed++;
    }
  }

  console.log(`\n📊 Результат: ${fixed} исправлено, ${failed} пропущено`);
}

main()
  .catch(console.error)
  .finally(() => prisma.$disconnect());
