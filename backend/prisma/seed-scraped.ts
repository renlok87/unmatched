import { PrismaClient } from '@prisma/client';
import * as fs from 'fs';
import * as path from 'path';
import { planAttackTypePatch } from './backfill-attack-type';

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
  // Новые поля
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
  // Новые поля
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

    // heroSchema.set — числовой индекс на объект {key, title} (тоже индексы)
    const setObj = resolveValue(data, heroSchema.set);

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
        key: resolveValue(data, setObj?.key) || '',
        title: resolveValue(data, setObj?.title) || '',
      },
      deck: parseDeckData(data, heroSchema),
      // Новые поля
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

      // type/value/boostValue/image/bannerName/i18n лежат на уровне элемента
      // КОЛОДЫ (deck item), а не cardSchema — у cardSchema этих ключей нет
      const card: ParsedCard = {
        id: cardSchema.id || i,
        title: title,
        type: resolveValue(data, item.type) || 'versatile',
        value: resolveValue(data, item.value) ?? null,
        boostValue: resolveValue(data, item.boostValue) ?? null,
        copies: resolveValue(data, item.copies) || item.copies || 1,
        effect: resolveValue(data, cardSchema.effect) || null,
        image: resolveValue(data, item.image) || null,
        // Новые поля
        bannerName: resolveValue(data, item.bannerName) || heroName,
        effectAfter: resolveValue(data, cardSchema.effectAfter) || null,
        effectDuring: resolveValue(data, cardSchema.effectDuring) || null,
        effectBoost: resolveValue(data, cardSchema.effectBoost) || null,
        effectImmediately: resolveValue(data, cardSchema.effectImmediately) || null,
        effectOngoing: resolveValue(data, cardSchema.effectOngoing) || null,
      };

      // Извлекаем русское изображение из i18n (тоже на уровне deck item)
      const i18nData = resolveValue(data, item.i18n);
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

function normalizeCardType(type: string): string {
  const typeMap: Record<string, string> = {
    'attack': 'ATTACK',
    'defense': 'DEFENSE',
    'scheme': 'SCHEME',
    'versatile': 'VERSATILE',
    'maneuver': 'MANEUVER',
  };
  return typeMap[type.toLowerCase()] || type.toUpperCase();
}

function normalizeFighterType(attack: string): string {
  const typeMap: Record<string, string> = {
    'melee': 'HERO',
    'range': 'HERO',
    'melee_range': 'HERO',
  };
  return typeMap[attack.toLowerCase()] || 'HERO';
}

function parseCardEffect(card: ParsedCard): string {
  return card.effect || '';
}

/**
 * Парсинг sidekicks (помощников) из данных
 * Sidekicks хранятся как массив индексов, каждый указывает на объект с данными
 */
function parseSidekicks(data: any[], sidekickIndexes: any[]): any[] {
  const sidekicks = [];

  if (!Array.isArray(sidekickIndexes)) {
    return sidekicks;
  }

  for (const skIndex of sidekickIndexes) {
    if (typeof skIndex !== 'number') continue;

    const sidekickData = resolveValue(data, skIndex);
    if (!sidekickData || typeof sidekickData !== 'object') continue;

    // В JSON sidekick может быть либо прямым объектом с данными,
    // либо объектом с индексами (как у героя)
    let parsed: any = null;

    // Проверяем, если это уже готовые данные (примитивы)
    if (typeof sidekickData.name === 'string') {
      parsed = {
        name: sidekickData.name || 'Unknown',
        health: sidekickData.startHealth || sidekickData.health || 1,
        movement: sidekickData.move || sidekickData.movement || 1,
        attackType: sidekickData.attack || 'melee',
        avatarUrl: sidekickData.avatar || null,
      };
    } else {
      // Иначе это объект с индексами, нужно разрешить
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

async function importHero(heroKey: string) {
  const filePath = path.join(SCRAPED_DATA_PATH, `${heroKey}.json`);

  if (!fs.existsSync(filePath)) {
    return;
  }

  try {
    const rawData = fs.readFileSync(filePath, 'utf-8');
    const parsed = JSON.parse(rawData);

    const hero = parseHeroData(parsed);

    if (!hero) {
      console.log(`⚠️  Пропуск: ${heroKey} (не удалось распарсить)`);
      return;
    }

    console.log(`📖 Импорт героя: ${hero.name}`);

    const existingHero = await prisma.hero.findUnique({
      where: { name: hero.name },
    });

    if (existingHero) {
      // Колоду и прочие поля существующего героя не трогаем, но тип атаки (герой и помощники) сверяем со скрейпом:
      // без поля движок даёт 'melee' — Medusa (attack=range) играла ближним бойцом (GD-058 interim §8 п. 9).
      const patch = planAttackTypePatch(existingHero, {
        attack: hero.attack,
        sidekicks: (hero.sidekicks || []).map((sk: any) => ({ name: sk.name, attack: sk.attackType })),
      });
      if (patch) {
        const data: Record<string, any> = {};
        if (patch.properties) data.properties = patch.properties;
        if (patch.sidekicks !== undefined) data.sidekicks = patch.sidekicks;
        await prisma.hero.update({ where: { id: existingHero.id }, data });
        console.log(`🏹 ${hero.name} (уже существует): ${patch.changes.join('; ')}`);
      } else {
        console.log(`⏭️  Пропуск: ${hero.name} (уже существует)`);
      }
      return;
    }

    const createdHero = await prisma.$transaction(async (tx) => {
      const newHero = await tx.hero.create({
        data: {
          name: hero.name,
          nameEn: hero.name,
          nameRu: hero.name,
          set: hero.set.title,
          health: hero.startHealth,
          fighterType: normalizeFighterType(hero.attack),
          movement: hero.move || 2,
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
            sidekickCount: hero.sidekicks?.length || 0,
            // Тип атаки героя как в scraped ('melee'|'range'|'melee_range') —
            // движок нормализует через normalizeAttackType (range → ranged)
            attackType: hero.attack,
          },
          hasTokens: hero.hasTokens,
          sidekicks: hero.sidekicks || [],
          additionalMinis: {
            images: hero.additionalMiniImages || [],
            models: hero.additionalMiniModels || [],
          },
          imageUrl: hero.cardBackImage,
          avatarUrl: hero.avatar,
          characterCardUrl: hero.characterCardImage || null,
          miniModelUrl: hero.miniatureModel || null,
        },
      });

      console.log(`✅ Создан герой: ${newHero.name}`);

      for (const card of hero.deck) {
        if (!card.title) continue;

        const normalizedType = normalizeCardType(card.type);
        const effect = parseCardEffect(card);

        await tx.card.create({
          data: {
            name: card.title,
            nameEn: card.title,
            nameRu: card.title,
            cardType: normalizedType,
            subType: normalizedType === 'MANEUVER' ? 'Movement' : null,
            // VERSATILE играется и как атака, и как защита — значение в оба поля
            attackValue: normalizedType === 'ATTACK' || normalizedType === 'VERSATILE' ? card.value : null,
            defenseValue: normalizedType === 'DEFENSE' || normalizedType === 'VERSATILE' ? card.value : null,
            boostValue: card.boostValue,
            bannerName: card.bannerName || null,
            effects: [],
            text: effect,
            textEn: effect,
            textRu: effect,
            // Детальные эффекты по таймингам
            effectAfter: card.effectAfter || null,
            effectDuring: card.effectDuring || null,
            effectBoost: card.effectBoost || null,
            effectImmediately: card.effectImmediately || null,
            effectOngoing: card.effectOngoing || null,
            count: card.copies || 1,
            heroId: newHero.id,
            imageUrl: card.image || null,
            imageUrlRu: card.imageRu || null,
          },
        });

        console.log(`   ✅ Создана карта: ${card.title} (${card.copies || 1} шт.)`);
      }

      return newHero;
    });

  } catch (error) {
    console.error(`❌ Ошибка при импорте ${heroKey}:`, error);
  }
}

async function main() {
  console.log('🌱 Seed: Импорт данных из scraped-data...\n');

  const heroKeys = [
    'achilles', 'alice', 'ancient-leshen', 'angel', 'annie-christmas',
    'beowulf', 'bigfoot', 'black-panther', 'black-widow', 'blackbeard',
    'bloody-mary', 'bruce-lee', 'buffy', 'bullseye', 'chupacabra', 'ciri',
    'cloak-dagger', 'cobble-fog', 'daredevil', 'data', 'deadpool',
    'doctor-strange', 'donatello', 'dr-jill-trent', 'dr-sattler', 'dracula',
    'elektra', 'eredin', 'geralt-of-rivia', 'ghost-rider', 'golden-bat',
    'hamlet', 'harry-houdini', 'hells-kitchen', 'invisible-man', 'jekyll-hyde',
    'king-arthur', 'krang', 'leonardo', 'little-red', 'loki', 'luke-cage',
    'medusa', 'melee', 'michelangelo', 'moon-knight', 'ms-marvel',
    'muhammad-ali', 'nikola-tesla', 'oda-nobunaga', 'pandora', 'philippa',
    'range', 'raphael', 'raptors', 'redemption-row', 'refresh',
    'robert-muldoon', 'robin-hood', 'shakespeare', 'she-hulk', 'sherlock-holmes',
    'shredder', 'sinbad', 'slings-and-arrows', 'spiderman', 'spike',
    'squirrel-girl', 'sun-wukong', 'suns-origin', 't-rex', 'teen-spirit',
    'the-genie', 'the-wayward-sisters', 'the-witcher-realms-fall',
    'the-witcher-steel-silver', 'titania', 'tomoe-gozen', 'willow',
    'winter-soldier', 'yennefer-triss', 'yennenga'
  ];

  let successCount = 0;
  let skipCount = 0;
  let errorCount = 0;

  for (const heroKey of heroKeys) {
    try {
      const filePath = path.join(SCRAPED_DATA_PATH, `${heroKey}.json`);
      if (!fs.existsSync(filePath)) {
        skipCount++;
        continue;
      }

      await importHero(heroKey);
      successCount++;
    } catch (error) {
      console.error(`❌ Ошибка при обработке ${heroKey}:`, error);
      errorCount++;
    }
  }

  console.log('\n📊 Статистика импорта:');
  console.log(`   ✅ Успешно импортировано: ${successCount} героев`);
  console.log(`   ⏭️  Пропущено: ${skipCount} файлов`);
  console.log(`   ❌ Ошибок: ${errorCount}`);

  const heroCount = await prisma.hero.count();
  const cardCount = await prisma.card.count();

  console.log(`\n🎮 Текущее состояние БД:`);
  console.log(`   🦸 Героев: ${heroCount}`);
  console.log(`   🃏 Карт: ${cardCount}`);
}

main()
  .catch((e) => {
    console.error('❌ Seed error:', e);
    process.exit(1);
  })
  .finally(async () => {
    await prisma.$disconnect();
  });