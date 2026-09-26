import fs from 'node:fs';
import path from 'node:path';
import process from 'node:process';

const ROOT = process.cwd();
const HERO_API_DIR = path.join(ROOT, 'scraped-data', 'api', 'heroes');
const DECK_SOURCE_DIRS = [
  path.join(ROOT, 'scraped-data', 'images', 'decks'),
  path.join(ROOT, 'docs', 'figma', 'figma-ready', 'decks'),
];
const PUBLIC_DECK_DIR = path.join(ROOT, 'public', 'assets', 'decks');
const MANIFEST_PATH = path.join(PUBLIC_DECK_DIR, 'card-assets.generated.json');

const DEFAULT_HEROES = ['daredevil', 'ms-marvel', 'deadpool'];
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

function imageFilename(imageRef) {
  if (!imageRef || typeof imageRef !== 'string') return null;
  const withoutQuery = imageRef.split(/[?#]/)[0];
  return withoutQuery.split(/[\\/]/).filter(Boolean).pop() ?? null;
}

function findSourceImage(imageRef) {
  const fileName = imageFilename(imageRef);
  if (!fileName) return null;

  for (const sourceDir of DECK_SOURCE_DIRS) {
    const candidate = path.join(sourceDir, fileName);
    if (fs.existsSync(candidate)) return candidate;
  }

  return null;
}

function parseRuImage(data, item) {
  const i18nData = resolveValue(data, item.i18n);
  if (!i18nData || typeof i18nData !== 'object') return null;

  const ruData = resolveValue(data, i18nData.ru);
  if (!ruData || typeof ruData !== 'object') return null;

  return resolveValue(data, ruData.image);
}

function parseHeroCards(heroSlug) {
  const filePath = path.join(HERO_API_DIR, `${heroSlug}.json`);
  if (!fs.existsSync(filePath)) {
    throw new Error(`Missing hero scrape file: ${path.relative(ROOT, filePath)}`);
  }

  const parsed = JSON.parse(fs.readFileSync(filePath, 'utf8'));
  const data = parsed?.nodes?.[2]?.data;
  if (!Array.isArray(data)) {
    throw new Error(`Unexpected scrape format: ${path.relative(ROOT, filePath)}`);
  }

  const heroSchema = data[1];
  const heroName = resolveValue(data, heroSchema?.name) ?? heroSlug;
  const bySlug = new Map();

  for (const item of data) {
    if (!item || typeof item !== 'object') continue;
    if (item.hero !== 1 && item.hero !== 2) continue;

    const cardSchema = resolveValue(data, item.card);
    if (!cardSchema || typeof cardSchema !== 'object') continue;

    const title = resolveValue(data, cardSchema.title);
    if (!title || typeof title !== 'string') continue;

    const cardSlug = slugify(title);
    if (!cardSlug || bySlug.has(cardSlug)) continue;

    bySlug.set(cardSlug, {
      id: cardSlug,
      title,
      image: resolveValue(data, item.image),
      imageRu: parseRuImage(data, item),
    });
  }

  return {
    id: heroSlug,
    name: heroName,
    cards: [...bySlug.values()].sort((a, b) => a.title.localeCompare(b.title)),
  };
}

function publicPathFor(...parts) {
  return `/${path.posix.join('assets', 'decks', ...parts)}`;
}

function findExistingLocalizedAsset(heroSlug, cardSlug) {
  const localizedDir = path.join(PUBLIC_DECK_DIR, heroSlug, 'ru');

  for (const ext of IMAGE_EXTENSIONS) {
    const candidate = path.join(localizedDir, `${cardSlug}-ru${ext}`);
    if (fs.existsSync(candidate)) {
      return publicPathFor(heroSlug, 'ru', `${cardSlug}-ru${ext}`);
    }
  }

  return null;
}

function copyAsset(sourceRef, targetPath) {
  const sourcePath = findSourceImage(sourceRef);
  if (!sourcePath) return false;

  fs.mkdirSync(path.dirname(targetPath), { recursive: true });
  fs.copyFileSync(sourcePath, targetPath);
  return true;
}

function syncHero(heroSlug) {
  const parsed = parseHeroCards(heroSlug);
  const cards = [];
  const missing = [];
  let copied = 0;

  for (const card of parsed.cards) {
    const enTarget = path.join(PUBLIC_DECK_DIR, heroSlug, `${card.id}.webp`);
    const ruTarget = path.join(PUBLIC_DECK_DIR, heroSlug, 'ru', `${card.id}-ru.webp`);

    const hasEn = card.image ? copyAsset(card.image, enTarget) : false;
    if (hasEn) copied += 1;

    let ruPath = null;
    const existingRuPath = findExistingLocalizedAsset(heroSlug, card.id);

    if (card.imageRu) {
      const hasRu = copyAsset(card.imageRu, ruTarget);
      if (hasRu) {
        copied += 1;
        ruPath = publicPathFor(heroSlug, 'ru', `${card.id}-ru.webp`);
      }
    }

    if (!ruPath && existingRuPath) {
      ruPath = existingRuPath;
    }

    if (!hasEn || !ruPath) {
      missing.push({
        id: card.id,
        title: card.title,
        missingEn: !hasEn,
        missingRu: !ruPath,
        sourceImage: card.image ?? null,
      });
    }

    cards.push({
      id: card.id,
      title: card.title,
      imageUrl: hasEn ? publicPathFor(heroSlug, `${card.id}.webp`) : null,
      imageUrlRu: ruPath,
    });
  }

  return {
    id: parsed.id,
    name: parsed.name,
    copied,
    totalCards: cards.length,
    missing,
    cards,
  };
}

function main() {
  const heroSlugs = process.argv.slice(2).filter(arg => !arg.startsWith('-'));
  const selectedHeroes = heroSlugs.length > 0 ? heroSlugs : DEFAULT_HEROES;
  const manifest = {
    generatedAt: new Date().toISOString(),
    heroes: {},
  };

  fs.mkdirSync(PUBLIC_DECK_DIR, { recursive: true });

  for (const heroSlug of selectedHeroes) {
    const result = syncHero(heroSlug);
    manifest.heroes[heroSlug] = {
      id: result.id,
      name: result.name,
      cards: result.cards,
      missing: result.missing,
    };

    const missingText = result.missing.length
      ? `${result.missing.length} missing variants`
      : 'complete EN/RU coverage';
    console.log(`${heroSlug}: ${result.totalCards} cards, copied ${result.copied} assets, ${missingText}`);

    for (const card of result.missing) {
      const parts = [];
      if (card.missingEn) parts.push('EN');
      if (card.missingRu) parts.push('RU');
      console.log(`  - ${card.title}: missing ${parts.join(', ')}`);
    }
  }

  fs.writeFileSync(MANIFEST_PATH, `${JSON.stringify(manifest, null, 2)}\n`);
  console.log(`Manifest: ${path.relative(ROOT, MANIFEST_PATH)}`);
}

main();
