/**
 * Разбор героя из скрейпа the-unmatched.club (devalue-формат nodes[2].data).
 * Чистый модуль без побочных эффектов: его используют seed-scraped.ts и
 * спеки (проверка банеров карт). Вынесен из seed-scraped.ts без изменений.
 */

export interface ParsedCard {
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

export interface ParsedHero {
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

export function resolveValue(data: any[], index: number | null | undefined): any {
  if (index === null || index === undefined || index < 0) return null;
  return data[index];
}

export function parseHeroData(rawData: any): ParsedHero | null {
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

export function parseDeckData(data: any[], heroSchema: any): ParsedCard[] {
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

/**
 * Парсинг sidekicks (помощников) из данных
 * Sidekicks хранятся как массив индексов, каждый указывает на объект с данными
 */
export function parseSidekicks(data: any[], sidekickIndexes: any[]): any[] {
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
