/**
 * Hero data normalizer for processing raw API data
 */

import type { HeroData, CardInfo, ImageCategory } from './types.js';

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

  // Find model URL
  const model = urls.find(u => u.includes('/models/') || u.includes('.glb'));

  // Try to find name
  const name = findByPattern(/^[A-Z][A-Za-z\s\-'']+\p{L}/u) || slug;

  return {
    slug,
    name,
    urls: {
      avatar,
      mini,
      cardCover,
      model,
    },
    cards,
    images: urls,
  };
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
