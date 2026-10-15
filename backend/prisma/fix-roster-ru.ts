/**
 * Русские названия и тексты карт ростера UE-клиента (Медуза, Король Артур) — идемпотентно.
 *
 * В БД у этих 27 карт nameRu = nameEn и textRu пуст: клиент на русском показывал
 * «A Momentary Glance / Deal 2 damage…» в баннере выбора, в журнале и в инспекторе,
 * хотя на сканах карт текст русский. Названия и тексты сняты с русских сканов
 * scraped-data/derived/ue-media-v1/cards/<hero>/<card>.ru.png
 * (prisma/data/roster-cards-ru.json, ключ <hero-slug>:<card-slug>, slug = nameEn в kebab-case).
 * Заодно nameRu героев ростера.
 *
 * Запуск (только эталонная БД, затем `node tools/db/sync-dev-stands.cjs sync --apply`):
 *   npx ts-node --transpile-only -e "require('./prisma/fix-roster-ru.ts')"
 */

import { PrismaClient } from '@prisma/client';
import * as fs from 'fs';
import * as path from 'path';

const prisma = new PrismaClient();

interface CardRu {
  key: string;
  nameRu: string;
  textRu: string;
}

const HERO_RU: Record<string, string> = { Medusa: 'Медуза', 'King Arthur': 'Король Артур' };

const slug = (s: string) =>
  s
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-|-$/g, '');

async function main() {
  const rows: CardRu[] = JSON.parse(
    fs.readFileSync(path.join(__dirname, 'data/roster-cards-ru.json'), 'utf-8'),
  );
  const byKey = new Map(rows.map((r) => [r.key, r]));
  let cards = 0;
  let heroes = 0;
  for (const [heroName, heroRu] of Object.entries(HERO_RU)) {
    const hero = await prisma.hero.findUnique({ where: { name: heroName }, include: { cards: true } });
    if (!hero) {
      console.warn(`нет героя ${heroName}`);
      continue;
    }
    if (hero.nameRu !== heroRu) {
      await prisma.hero.update({ where: { id: hero.id }, data: { nameRu: heroRu } });
      heroes++;
    }
    for (const card of hero.cards) {
      const ru = byKey.get(`${slug(heroName)}:${slug(card.nameEn || card.name)}`);
      if (!ru) {
        console.warn(`нет перевода: ${heroName} / ${card.nameEn}`);
        continue;
      }
      const textRu = ru.textRu || null;
      if (card.nameRu === ru.nameRu && card.textRu === textRu) continue;
      await prisma.card.update({ where: { id: card.id }, data: { nameRu: ru.nameRu, textRu } });
      cards++;
    }
  }
  console.log(`fix-roster-ru: героев ${heroes}, карт ${cards}`);
}

main()
  .catch((e) => {
    console.error(e);
    process.exitCode = 1;
  })
  .finally(() => prisma.$disconnect());
