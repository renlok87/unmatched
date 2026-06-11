import { PrismaClient } from '@prisma/client';
import * as fs from 'fs';
import * as path from 'path';

const prisma = new PrismaClient();

const SCRAPED_DATA_PATH = path.join(__dirname, '../../scraped-data/api/heroes');

interface ParsedHero {
  name: string;
  key: string;
  avatar: string;
  miniatureImage: string;
  cardBackImage: string;
  characterCardImage: string;
  set: {
    key: string;
    title: string;
  };
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

    // set - это индекс на объект с полями key и title
    const setIndex = heroSchema.set;
    const setObj = resolveValue(data, setIndex);
    const setKey = setObj?.key ? resolveValue(data, setObj.key) : '';
    const setTitle = setObj?.title ? resolveValue(data, setObj.title) : '';

    const hero: ParsedHero = {
      name: resolveValue(data, heroSchema.name) || 'Unknown',
      key: resolveValue(data, heroSchema.key) || '',
      avatar: resolveValue(data, heroSchema.avatar) || '',
      miniatureImage: resolveValue(data, heroSchema.miniatureImage) || '',
      cardBackImage: resolveValue(data, heroSchema.cardBackImage) || '',
      characterCardImage: resolveValue(data, heroSchema.characterCardImage) || resolveValue(data, heroSchema.cardBackImage) || '',
      set: {
        key: setKey || '',
        title: setTitle || '',
      },
    };

    return hero;
  } catch (error) {
    console.error('Error parsing hero data:', error);
    return null;
  }
}

async function updateHero(heroKey: string) {
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

    // Находим героя по имени
    const existingHero = await prisma.hero.findFirst({
      where: { name: { equals: hero.name, mode: 'insensitive' } },
    });

    if (!existingHero) {
      console.log(`⏭️  Пропуск: ${hero.name} (не найден в БД)`);
      return;
    }

    // Обновляем героя
    const updated = await prisma.hero.update({
      where: { id: existingHero.id },
      data: {
        nameEn: hero.name,
        nameRu: hero.name,
        set: hero.set.title,
        imageUrl: hero.characterCardImage || hero.cardBackImage,
        avatarUrl: hero.avatar,
      },
    });

    console.log(`✅ Обновлён: ${hero.name} | set: ${hero.set.title}`);
  } catch (error) {
    console.error(`❌ Ошибка при обновлении ${heroKey}:`, error);
  }
}

async function main() {
  console.log('🔄 Обновление данных героев из scraped-data...\n');

  const heroKeys = [
    'achilles', 'alice', 'ancient-leshen', 'angel', 'annie-christmas',
    'beowulf', 'bigfoot', 'black-panther', 'black-widow', 'blackbeard',
    'bloody-mary', 'bruce-lee', 'bullseye', 'chupacabra', 'ciri',
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

      await updateHero(heroKey);
      successCount++;
    } catch (error) {
      console.error(`❌ Ошибка при обработке ${heroKey}:`, error);
      errorCount++;
    }
  }

  console.log('\n📊 Статистика обновления:');
  console.log(`   ✅ Обновлено: ${successCount} героев`);
  console.log(`   ⏭️  Пропущено: ${skipCount} файлов`);
  console.log(`   ❌ Ошибок: ${errorCount}`);
}

main()
  .catch((e) => {
    console.error('❌ Error:', e);
    process.exit(1);
  })
  .finally(async () => {
    await prisma.$disconnect();
  });
