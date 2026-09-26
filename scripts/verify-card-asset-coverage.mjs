import fs from 'node:fs';
import path from 'node:path';
import process from 'node:process';

const ROOT = process.cwd();
const API_DIR = path.join(ROOT, 'scraped-data', 'api', 'heroes');
const PUBLIC_DECK_DIR = path.join(ROOT, 'public', 'assets', 'decks');

const TARGET_HEROES = [
  'blackbeard',
  'chupacabra',
  'ciri',
  'deadpool',
  'donatello',
  'eredin',
  'krang',
  'leonardo',
  'loki',
  'michelangelo',
  'muhammad-ali',
  'pandora',
  'philippa',
  'raphael',
  'shredder',
  'yennefer-triss',
  'daredevil',
  'ms-marvel',
];

const IMAGE_EXTENSIONS = ['.webp', '.png', '.jpg', '.jpeg'];

function resolveValue(data, index) {
  if (index === null || index === undefined) return null;
  if (typeof index === 'number') return data[index] ?? null;
  return index;
}

function slugify(value) {
  return String(value)
    .normalize('NFKD')
    .replace(/[\u0300-\u036f]/g, '')
    .replace(/['’]/g, '')
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '');
}

function parseHeroCards(heroSlug) {
  const filePath = path.join(API_DIR, `${heroSlug}.json`);
  const parsed = JSON.parse(fs.readFileSync(filePath, 'utf8'));
  const data = parsed?.nodes?.[2]?.data;
  if (!Array.isArray(data)) throw new Error(`Unexpected scrape format for ${heroSlug}`);

  const cards = new Map();
  for (const item of data) {
    if (!item || typeof item !== 'object') continue;
    if (item.hero !== 1 && item.hero !== 2) continue;

    const cardSchema = resolveValue(data, item.card);
    if (!cardSchema || typeof cardSchema !== 'object') continue;

    const title = resolveValue(data, cardSchema.title);
    if (!title || typeof title !== 'string') continue;

    const cardSlug = slugify(title);
    if (!cardSlug || cards.has(cardSlug)) continue;

    cards.set(cardSlug, { id: cardSlug, title });
  }

  return [...cards.values()];
}

function hasCardAsset(heroSlug, cardSlug, localized) {
  const dir = localized
    ? path.join(PUBLIC_DECK_DIR, heroSlug, 'ru')
    : path.join(PUBLIC_DECK_DIR, heroSlug);
  const suffix = localized ? '-ru' : '';

  return IMAGE_EXTENSIONS.some(ext => fs.existsSync(path.join(dir, `${cardSlug}${suffix}${ext}`)));
}

function main() {
  const failures = [];
  const summary = {};

  for (const heroSlug of TARGET_HEROES) {
    const cards = parseHeroCards(heroSlug);
    let en = 0;
    let ru = 0;

    for (const card of cards) {
      if (hasCardAsset(heroSlug, card.id, false)) en += 1;
      else failures.push(`${heroSlug}/${card.id}: missing EN asset`);

      if (hasCardAsset(heroSlug, card.id, true)) ru += 1;
      else failures.push(`${heroSlug}/${card.id}: missing RU asset`);
    }

    summary[heroSlug] = { en, ru, total: cards.length };
  }

  console.log(JSON.stringify(summary, null, 2));

  if (failures.length) {
    console.error(`\nMissing assets (${failures.length}):`);
    for (const line of failures) console.error(`- ${line}`);
    process.exit(1);
  }

  console.log('\nAll target card assets have EN and RU variants.');
}

main();
