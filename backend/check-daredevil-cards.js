const fs = require('fs');
const path = require('path');

const SCRAPED_DATA_PATH = path.join(__dirname, '../scraped-data/api/heroes');

function resolveValue(data, index) {
  if (index === null || index === undefined || index < 0) return null;
  return data[index];
}

const filePath = path.join(SCRAPED_DATA_PATH, 'daredevil.json');
const rawData = fs.readFileSync(filePath, 'utf-8');
const parsed = JSON.parse(rawData);

const nodes = parsed.nodes;
const data = nodes[2].data;

console.log('Daredevil cards from scraped data:\n');

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

  const type = resolveValue(data, cardSchema.type) || 'versatile';
  const value = resolveValue(data, cardSchema.value);
  const boostValue = resolveValue(data, cardSchema.boostValue);
  const bannerName = resolveValue(data, item.bannerName);

  console.log(`  ${title} - type: ${type}, value: ${value}, boost: ${boostValue}, banner: ${bannerName}`);
}
