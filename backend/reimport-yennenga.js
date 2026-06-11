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

  const hero = {
    name: resolveValue(data, heroSchema.name) || 'Unknown',
    attack: resolveValue(data, heroSchema.attack) || 'melee',
    startHealth: resolveValue(data, heroSchema.startHealth) || 18,
    move: resolveValue(data, heroSchema.move) || 3,
    specialAbility: resolveValue(data, heroSchema.specialAbility) || '',
    key: resolveValue(data, heroSchema.key) || '',
    description: resolveValue(data, heroSchema.description) || '',
    avatar: resolveValue(data, heroSchema.avatar) || '',
    miniatureImage: resolveValue(data, heroSchema.miniatureImage) || '',
    cardBackImage: resolveValue(data, heroSchema.cardBackImage) || '',
    color: resolveValue(data, heroSchema.color) || '#000000',
    hasSidekicks: resolveValue(data, heroSchema.hasSidekicks) || false,
    sidekicks: resolveValue(data, heroSchema.sidekicks) || [],
    set: {
      key: resolveValue(data, heroSchema.set?.key) || '',
      title: resolveValue(data, heroSchema.set?.title) || '',
    },
    deck: parseDeckData(data),
  };

  return hero;
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

async function reimportYennenga() {
  const filePath = path.join(SCRAPED_DATA_PATH, 'yennenga.json');

  console.log('📖 Чтение файла:', filePath);
  const rawData = fs.readFileSync(filePath, 'utf8');
  const parsed = JSON.parse(rawData);

  const hero = parseHeroData(parsed);
  if (!hero) {
    console.log('❌ Не удалось распарсить героя');
    return;
  }

  console.log('🦸 Герой:', hero.name);
  console.log('🃏 Карт в колоде:', hero.deck.length);

  // Удаляем существующие карты
  const existingCards = await prisma.card.findMany({
    where: { hero: { name: 'Yennenga' } }
  });

  console.log('🗑️ Удаление старых карт:', existingCards.length);

  for (const card of existingCards) {
    await prisma.card.delete({ where: { id: card.id } });
  }

  // Создаём карты заново
  for (const card of hero.deck) {
    if (!card.title) continue;

    const heroRecord = await prisma.hero.findUnique({
      where: { name: 'Yennenga' }
    });

    if (!heroRecord) {
      console.log('❌ Герой не найден в БД');
      return;
    }

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

    console.log(`   ✅ ${card.title} x${card.copies} (${normalizedType})`);
  }

  console.log('✅ Готово!');
}

reimportYennenga()
  .catch(console.error)
  .finally(() => prisma.$disconnect());
