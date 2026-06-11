/**
 * Hero data normalizer for processing raw API data
 */

import type { HeroData, CardInfo, ImageCategory, SidekickInfo } from './types.js';

/**
 * Extract all strings from object recursively
 */
function extractStrings(obj: unknown): string[] {
  const allStrings: string[] = [];

  function recurse(item: unknown): void {
    if (typeof item === 'string') {
      allStrings.push(item);
    } else if (Array.isArray(item)) {
      for (const element of item) recurse(element);
    } else if (item && typeof item === 'object') {
      for (const value of Object.values(item)) recurse(value);
    }
  }

  recurse(obj);
  return allStrings;
}

/**
 * Extract filename from URL
 */
function extractFilename(url: string): string {
  if (url.includes('supabase.co/storage/')) {
    const parts = url.split('/');
    const filename = parts[parts.length - 1];
    return filename.includes('.') ? filename : `${filename}.webp`;
  }

  const urlParts = url.split('/');
  return urlParts[urlParts.length - 1] || 'file.webp';
}

/**
 * Categorize image URL by type
 */
function categorizeImageUrl(url: string): ImageCategory {
  const filename = extractFilename(url);

  if (url.includes('/heroes/models/') || url.includes('.glb') || url.includes('.gltf')) {
    return { category: 'models', filename, isModel: true };
  }
  if (url.includes('/heroes/avatars/')) {
    return { category: 'avatars', filename, isModel: false };
  }
  if (url.includes('/heroes/minis/')) {
    return { category: 'minis', filename, isModel: false };
  }
  if (url.includes('/heroes/card-covers/')) {
    return { category: 'card-covers', filename, isModel: false };
  }
  if (url.includes('/decks/')) {
    return { category: 'decks', filename, isModel: false };
  }
  if (url.includes('/sets/')) {
    return { category: 'sets', filename, isModel: false };
  }

  return { category: null, filename, isModel: false };
}

/**
 * Find all hero slugs from the API data
 */
export function findAllHeroSlugs(data: unknown): string[] {
  const strings = extractStrings(data);

  // Find all potential hero keys
  const potentialKeys = [...new Set(strings.filter(s =>
    /^[a-z][a-z0-9-]+$/.test(s) &&
    s.length > 2 &&
    s.length < 35 &&
    !s.startsWith('http') &&
    !s.includes('.') &&
    !s.includes('cow') &&
    !s.includes('chicken') &&
    !s.includes('pig') &&
    !s.includes('sheep') &&
    !s.includes('fish') &&
    !s.includes('bird') &&
    !s.includes('dragon-')
  ))];

  // Filter out obvious set patterns
  const strictSetPatterns = [
    '-vs-',
    'adventures-',
    'jurassic-park-',
  ];

  const heroKeys = potentialKeys.filter(key => {
    for (const pattern of strictSetPatterns) {
      if (key.includes(pattern)) return false;
    }
    if (key.length > 30) return false;
    return true;
  });

  return heroKeys.sort();
}

/**
 * Normalize hero data from SvelteKit format to clean JSON
 */
export function normalizeHeroData(slug: string, rawData: unknown): HeroData {
  const strings = extractStrings(rawData);

  // Helper to find value by pattern
  const findByPattern = (pattern: RegExp): string | undefined => {
    return strings.find(s => pattern.test(s));
  };

  // Extract URLs
  const urls = strings.filter(s => s.startsWith('http'));

  // Extract card images
  const cardImages = urls.filter(u => u.includes('/decks/'));
  const cards: CardInfo[] = cardImages.map((url, i) => ({
    id: i,
    url,
    filename: extractFilename(url),
  }));

  // Find avatar URL
  const avatar = urls.find(u => u.includes('/avatars/'));

  // Find mini URL
  const mini = urls.find(u => u.includes('/minis/'));

  // Find card cover URL
  const cardCover = urls.find(u => u.includes('/card-covers/'));

  // Find model URL (3D)
  const model = urls.find(u => u.includes('/models/') || u.includes('.glb') || u.includes('.gltf'));

  // Find character card URL
  const characterCard = urls.find(u => u.includes('/character-cards/'));

  // Try to find name
  const name = findByPattern(/^[A-Z][A-Za-z\s\-'']+\p{L}/u) || slug;

  // Extract additional data from the raw SvelteKit structure
  const additionalData = extractAdditionalHeroData(rawData);

  return {
    slug,
    name,
    urls: {
      avatar,
      mini,
      cardCover,
      model,
      characterCard,
    },
    cards,
    images: urls,
    ...additionalData,
  };
}

/**
 * Extract additional hero data from the complex SvelteKit structure
 */
function extractAdditionalHeroData(rawData: unknown): Partial<HeroData> {
  const result: Partial<HeroData> = {};

  try {
    // Navigate the SvelteKit structure
    if (rawData && typeof rawData === 'object' && 'nodes' in rawData) {
      const nodes = (rawData as any).nodes;
      if (Array.isArray(nodes) && nodes[2] && 'data' in nodes[2]) {
        const data = nodes[2].data as any[];
        if (Array.isArray(data) && data[1]) {
          const heroSchema = data[1];

          // Helper function to resolve values by index
          const resolveValue = (index: number | null | undefined): any => {
            if (index === null || index === undefined || index < 0) return null;
            return data[index];
          };

          // Extract movement
          const move = resolveValue(heroSchema.move);
          if (typeof move === 'number') {
            result.movement = move;
          }

          // Extract color
          const color = resolveValue(heroSchema.color);
          if (typeof color === 'string' && color.startsWith('#')) {
            result.color = color;
          }

          // Extract health
          const health = resolveValue(heroSchema.startHealth);
          if (typeof health === 'number') {
            result.health = health;
          }

          // Extract attack type
          const attack = resolveValue(heroSchema.attack);
          if (typeof attack === 'string') {
            result.attackType = attack;
          }

          // Extract special ability
          const ability = resolveValue(heroSchema.specialAbility);
          if (typeof ability === 'string') {
            result.specialAbility = ability;
          }

          // Extract hasTokens
          const hasTokens = resolveValue(heroSchema.hasTokens);
          if (typeof hasTokens === 'boolean') {
            result.hasTokens = hasTokens;
          }

          // Extract sidekicks
          const sidekicks = resolveValue(heroSchema.sidekicks);
          if (Array.isArray(sidekicks)) {
            result.sidekicks = extractSidekicks(data, sidekicks);
          }

          // Extract additional miniatures
          const additionalMiniImages = resolveValue(heroSchema.additionalMiniImages);
          const additionalMiniModels = resolveValue(heroSchema.additionalMiniModels);

          if (Array.isArray(additionalMiniImages) || Array.isArray(additionalMiniModels)) {
            result.additionalMinis = {
              images: additionalMiniImages || [],
              models: additionalMiniModels || [],
            };
          }
        }
      }
    }
  } catch (error) {
    // Silently fail for additional data
    console.debug('Could not extract additional hero data:', error);
  }

  return result;
}

/**
 * Extract sidekick information from the data array
 */
function extractSidekicks(data: any[], sidekickIndexes: any[]): SidekickInfo[] {
  const sidekicks: SidekickInfo[] = [];

  if (!Array.isArray(sidekickIndexes)) {
    return sidekicks;
  }

  const resolveValue = (index: number | null | undefined): any => {
    if (index === null || index === undefined || index < 0) return null;
    return data[index];
  };

  for (const skIndex of sidekickIndexes) {
    if (typeof skIndex !== 'number') continue;

    const sidekickData = resolveValue(skIndex);
    if (!sidekickData || typeof sidekickData !== 'object') continue;

    // Check if it's already a parsed object or needs index resolution
    let parsed: SidekickInfo | null = null;

    if (typeof sidekickData.name === 'string') {
      // Already parsed
      parsed = {
        name: sidekickData.name || 'Unknown',
        health: sidekickData.startHealth || sidekickData.health || 1,
        movement: sidekickData.move || sidekickData.movement || 1,
        attackType: sidekickData.attack || 'melee',
        avatarUrl: sidekickData.avatar || null,
      };
    } else {
      // Needs index resolution
      const schema = sidekickData;
      parsed = {
        name: resolveValue(schema.name) || 'Unknown',
        health: resolveValue(schema.startHealth) || resolveValue(schema.health) || 1,
        movement: resolveValue(schema.move) || resolveValue(schema.movement) || 1,
        attackType: resolveValue(schema.attack) || 'melee',
        avatarUrl: resolveValue(schema.avatar) || null,
      };
    }

    if (parsed) {
      sidekicks.push(parsed);
    }
  }

  return sidekicks;
}

/**
 * Extract all image URLs from raw data
 */
export function extractImageUrls(rawData: unknown): string[] {
  const strings = extractStrings(rawData);
  const urls: string[] = [];

  for (const s of strings) {
    if (s.startsWith('http') && s.includes('supabase.co/storage/')) {
      if (!urls.includes(s)) {
        urls.push(s);
      }
    }
  }

  return urls;
}

/**
 * Get destination path for an image based on category
 */
export function getImagePath(
  url: string,
  paths: {
    avatars: string;
    minis: string;
    cardCovers: string;
    models: string;
    decks: string;
    sets: string;
  }
): string | null {
  const { category, filename } = categorizeImageUrl(url);

  switch (category) {
    case 'avatars':
      return `${paths.avatars}/${filename}`.replace(/\\/g, '/');
    case 'minis':
      return `${paths.minis}/${filename}`.replace(/\\/g, '/');
    case 'card-covers':
      return `${paths.cardCovers}/${filename}`.replace(/\\/g, '/');
    case 'models':
      return `${paths.models}/${filename}`.replace(/\\/g, '/');
    case 'decks':
      return `${paths.decks}/${filename}`.replace(/\\/g, '/');
    case 'sets':
      return `${paths.sets}/${filename}`.replace(/\\/g, '/');
    default:
      return null;
  }
}

/**
 * Check if URL is a 3D model
 */
export function isModelUrl(url: string): boolean {
  return categorizeImageUrl(url).isModel;
}

export const HeroDataNormalizer = {
  findAllHeroSlugs,
  normalizeHeroData,
  extractImageUrls,
  getImagePath,
  isModelUrl,
};
