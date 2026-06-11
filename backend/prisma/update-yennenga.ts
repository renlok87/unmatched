import { PrismaClient } from '@prisma/client';
import * as fs from 'fs';
import * as path from 'path';

const prisma = new PrismaClient();

const SCRAPED_DATA_PATH = path.join(__dirname, '../../scraped-data/api/heroes');

interface ParsedCard {
  id: number;
  title: string;
  type: string;
  value: number | null;
  boostValue: number | null;
  copies: number;
  effect: string | null;
  image?: string;
  imageRu?: string;
  bannerName?: string | null;
  effectAfter?: string | null;
  effectDuring?: string | null;
  effectBoost?: string | null;
  effectImmediately?: string | null;
  effectOngoing?: string | null;
}

interface ParsedHero {
  name: string;
  attack: string;
  startHealth: number;
  move: number | null;
  specialAbility: string;
  key: string;
  description: string;
  avatar: string;
  miniatureImage: string;
  cardBackImage: string;
  color: string;
  hasSidekicks: boolean;
  hasTokens: boolean;
  sidekicks?: any[];
  set: {
    key: string;
    title: string;
  };
  deck: ParsedCard[];
  characterCardImage?: string | null;
  miniatureModel?: string | null;
  additionalMiniImages?: string[];
  additionalMiniModels?: string[];
}

function resolveValue(data: any[], index: number | null | undefined): any {
  if (index === null || index === undefined || index < 0) return null;
  return data[index];
}

function parseHeroData(rawData: any): ParsedHero | null {
  try {
    const nodes = rawData.nodes;
    if (!nodes || nodes.length < 3 || !nodes[2] || !nodes[2].data) return null;

    const data = nodes[2].data as any[];
    const heroSchema = data[1];

    if (!heroSchema || typeof heroSchema !== 'object') return null;

    const hero: ParsedHero = {
      name: resolveValue(data, heroSchema.name) || 'Unknown',
      attack: resolveValue(data, heroSchema.attack) || 'melee',
      startHealth: resolveValue(data, heroSchema.startHealth) || 18,
      move: resolveValue(data, heroSchema.move) || 2,
      specialAbility: resolveValue(data, heroSchema.specialAbility) || '',
      key: resolveValue(data, heroSchema.key) || '',
      description: resolveValue(data, heroSchema.description) || '',
      avatar: resolveValue(data, heroSchema.avatar) || '',
      miniatureImage: resolveValue(data, heroSchema.miniatureImage) || '',
      cardBackImage: resolveValue(data, heroSchema.cardBackImage) || '',
      color: resolveValue(data, heroSchema.color) || '#000000',
      hasSidekicks: resolveValue(data, heroSchema.hasSidekicks) || false,
      hasTokens: resolveValue(data, heroSchema.hasTokens) || false,
      sidekicks: parseSidekicks(data, resolveValue(data, heroSchema.sidekicks) || []),
      set: {
        key: resolveValue(data, heroSchema.set?.key) || '',
        title: resolveValue(data, heroSchema.set?.title) || '',
      },
      deck: parseDeckData(data, heroSchema),
      characterCardImage: resolveValue(data, heroSchema.characterCardImage) || null,
      miniatureModel: resolveValue(data, heroSchema.miniatureModel) || null,
      additionalMiniImages: resolveValue(data, heroSchema.additionalMiniImages) || [],
      additionalMiniModels: resolveValue(data, heroSchema.additionalMiniModels) || [],
    };

    return hero;
  } catch (error) {
    console.error('Error parsing hero data:', error);
    return null;
  }
}

function parseDeckData(data: any[], heroSchema: any): ParsedCard[] {
  const cards: ParsedCard[] = [];

  try {
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

      const heroName = resolveValue(data, heroSchema.name) || 'Unknown';

      const card: ParsedCard = {
        id: cardSchema.id || i,
        title: title,
        type: resolveValue(data, cardSchema.type) || 'versatile',
        value: resolveValue(data, cardSchema.value) || null,
        boostValue: resolveValue(data, cardSchema.boostValue) || null,
        copies: resolveValue(data, item.copies) || item.copies || 1,
        effect: resolveValue(data, cardSchema.effect) || null,
        image: resolveValue(data, cardSchema.image) || null,
        bannerName: resolveValue(data, item.bannerName) || heroName,
        effectAfter: resolveValue(data, cardSchema.effectAfter) || null,
        effectDuring: resolveValue(data, cardSchema.effectDuring) || null,
        effectBoost: resolveValue(data, cardSchema.effectBoost) || null,
        effectImmediately: resolveValue(data, cardSchema.effectImmediately) || null,
        effectOngoing: resolveValue(data, cardSchema.effectOngoing) || null,
      };

      const i18nData = resolveValue(data, cardSchema.i18n);
      if (i18nData && typeof i18nData === 'object' && i18nData.ru !== undefined) {
        const ruIndex = i18nData.ru;
        if (typeof ruIndex === 'number') {
          const ruData = resolveValue(data, ruIndex);
          if (ruData && typeof ruData === 'object' && ruData.image !== undefined) {
            const ruImageIndex = ruData.image;
            if (typeof ruImageIndex === 'number') {
              card.imageRu = resolveValue(data, ruImageIndex) || null;
            }
          }
        }
      }

      cards.push(card);
    }
  } catch (error) {
    console.error('Error parsing deck data:', error);
  }

  return cards;
}

function parseSidekicks(data: any[], sidekickIndexes: any[]): any[] {
  const sidekicks = [];

  if (!Array.isArray(sidekickIndexes)) {
    return sidekicks;
  }

  for (const skIndex of sidekickIndexes) {
    if (typeof skIndex !== 'number') continue;

    const sidekickData = resolveValue(data, skIndex);
    if (!sidekickData || typeof sidekickData !== 'object') continue;

    let parsed: any = null;

    if (typeof sidekickData.name === 'string') {
      parsed = {
        name: sidekickData.name || 'Unknown',
        health: sidekickData.startHealth || sidekickData.health || 1,
        movement: sidekickData.move || sidekickData.movement || 1,
        attackType: sidekickData.attack || 'melee',
        avatarUrl: sidekickData.avatar || null,
      };
    } else {
      const schema = sidekickData;
      parsed = {
        name: resolveValue(data, schema.name) || 'Unknown',
        health: resolveValue(data, schema.startHealth) || resolveValue(data, schema.health) || 1,
        movement: resolveValue(data, schema.move) || resolveValue(data, schema.movement) || 1,
        attackType: resolveValue(data, schema.attack) || 'melee',
        avatarUrl: resolveValue(data, schema.avatar) || null,
      };
    }

    if (parsed) {
      sidekicks.push(parsed);
    }
  }

  return sidekicks;
}

/**
 * Get the primary effect text from card, checking all effect fields
 */
function getPrimaryEffect(card: ParsedCard): string {
  // Priority order for effect text
  return card.effectImmediately ||
         card.effectAfter ||
         card.effectDuring ||
         card.effectBoost ||
         card.effectOngoing ||
         card.effect ||
         '';
}

async function main() {
  const heroKey = 'yennenga';
  const filePath = path.join(SCRAPED_DATA_PATH, `${heroKey}.json`);

  if (!fs.existsSync(filePath)) {
    console.log(`File not found: ${filePath}`);
    return;
  }

  const rawData = fs.readFileSync(filePath, 'utf-8');
  const parsed = JSON.parse(rawData);

  const hero = parseHeroData(parsed);

  if (!hero) {
    console.log('Failed to parse hero data');
    return;
  }

  console.log(`📖 Updating hero: ${hero.name}`);

  // Get existing hero
  const existingHero = await prisma.hero.findUnique({
    where: { name: hero.name },
    include: { cards: true }
  });

  if (!existingHero) {
    console.log('Hero not found in database');
    return;
  }

  // Update hero with new fields
  const updatedHero = await prisma.hero.update({
    where: { id: existingHero.id },
    data: {
      movement: hero.move || 2,
      color: hero.color,
      hasTokens: hero.hasTokens,
      sidekicks: hero.sidekicks || [],
      additionalMinis: {
        images: hero.additionalMiniImages || [],
        models: hero.additionalMiniModels || [],
      },
      characterCardUrl: hero.characterCardImage || null,
      miniModelUrl: hero.miniatureModel || null,
    },
  });

  console.log(`✅ Updated hero: ${updatedHero.name}`);
  console.log(`   Movement: ${updatedHero.movement}`);
  console.log(`   Color: ${updatedHero.color}`);
  console.log(`   HasTokens: ${updatedHero.hasTokens}`);
  console.log(`   Sidekicks:`, JSON.stringify(updatedHero.sidekicks, null, 2));

  // Update cards
  for (const cardData of hero.deck) {
    const existingCard = existingHero.cards.find(c => c.name === cardData.title);
    if (existingCard) {
      const primaryEffect = getPrimaryEffect(cardData);
      await prisma.card.update({
        where: { id: existingCard.id },
        data: {
          bannerName: cardData.bannerName || null,
          boostValue: cardData.boostValue,
          text: primaryEffect,
          textEn: primaryEffect,
          textRu: primaryEffect,
          effectAfter: cardData.effectAfter || null,
          effectDuring: cardData.effectDuring || null,
          effectBoost: cardData.effectBoost || null,
          effectImmediately: cardData.effectImmediately || null,
          effectOngoing: cardData.effectOngoing || null,
        },
      });
      console.log(`   ✅ Updated card: ${cardData.title}`);
      if (primaryEffect) {
        console.log(`      Effect: ${primaryEffect.substring(0, 50)}...`);
      }
    }
  }

  console.log('\n🎮 Update complete!');
}

main()
  .catch((e) => {
    console.error('❌ Error:', e);
    process.exit(1);
  })
  .finally(async () => {
    await prisma.$disconnect();
  });
