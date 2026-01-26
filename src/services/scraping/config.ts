/**
 * Default configuration for the Unmatched Club scraper
 */

import path from 'path';
import { fileURLToPath } from 'url';
import type { ScraperConfig } from './types.js';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

// Navigate from src/services/scraping to scraped-data directory
const scrapedDataRoot = path.join(__dirname, '../../../scraped-data');

export const DEFAULT_CONFIG: ScraperConfig = {
  baseUrl: 'https://www.the-unmatched.club',
  apiBase: 'https://www.the-unmatched.club',
  endpoints: {
    heroes: '/heroes/__data.json',
    sets: '/sets/__data.json',
    villains: '/villains/__data.json',
    minions: '/minions/__data.json',
    maps: '/maps/__data.json',
  },
  paths: {
    root: scrapedDataRoot,
    api: path.join(scrapedDataRoot, 'api'),
    heroes: path.join(scrapedDataRoot, 'api', 'heroes'),
    normalized: path.join(scrapedDataRoot, 'api', 'normalized'),
    images: path.join(scrapedDataRoot, 'images'),
    heroesImages: {
      avatars: path.join(scrapedDataRoot, 'images', 'heroes', 'avatars'),
      minis: path.join(scrapedDataRoot, 'images', 'heroes', 'minis'),
      cardCovers: path.join(scrapedDataRoot, 'images', 'heroes', 'card-covers'),
      models: path.join(scrapedDataRoot, 'images', 'heroes', 'models'),
    },
    decksImages: path.join(scrapedDataRoot, 'images', 'decks'),
    setsImages: path.join(scrapedDataRoot, 'images', 'sets'),
  },
  delays: {
    betweenHeroes: 200,
    betweenImages: 50,
  },
  options: {
    skipExistingImages: true,
    downloadModels: true,
    verbose: false,
  },
};

/**
 * Create a full URL from endpoint
 */
export function buildUrl(apiBase: string, endpoint: string): string {
  return `${apiBase}${endpoint}`;
}

/**
 * Build hero detail URL
 */
export function buildHeroUrl(apiBase: string, slug: string): string {
  return `${apiBase}/heroes/${slug}/__data.json`;
}
