import { PrismaClient } from '@prisma/client';
import * as fs from 'fs';
import * as path from 'path';
import { planAttackTypePatch } from './backfill-attack-type';
import { ParsedCard, parseHeroData } from './scraped-hero-parser';
import { applyBannerFix, BannerMismatch, findBannerMismatches } from './card-banner-fixes';

const prisma = new PrismaClient();

const SCRAPED_DATA_PATH = path.join(__dirname, '../../scraped-data/api/heroes');

const bannerMismatches: BannerMismatch[] = [];

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

    // DATA-02: банер каждой карты обязан принадлежать герою или помощнику
    // (после правки опечаток BANNER_FIXES). Иначе правило «именную карту
    // играет только свой боец» молча снимается — валим сид в конце.
    bannerMismatches.push(
      ...findBannerMismatches(
        { name: hero.name, sidekicks: hero.sidekicks || [] },
        hero.deck.map((c) => ({ name: c.title, bannerName: applyBannerFix(hero.name, c.bannerName) })),
      ),
    );

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
            bannerName: applyBannerFix(hero.name, card.bannerName) || null,
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

  if (bannerMismatches.length > 0) {
    console.error(`\n❌ Банер не принадлежит ни герою, ни помощнику (${bannerMismatches.length}):`);
    for (const m of bannerMismatches) {
      console.error(`   ${m.heroName} — ${m.cardName}: «${m.bannerName}»`);
    }
    console.error('   Добавьте правку в prisma/card-banner-fixes.ts (BANNER_FIXES) или BANNER_FORM_ALIASES.');
    process.exitCode = 1;
  }
}

main()
  .catch((e) => {
    console.error('❌ Seed error:', e);
    process.exit(1);
  })
  .finally(async () => {
    await prisma.$disconnect();
  });