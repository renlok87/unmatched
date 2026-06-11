/**
 * Скрипт для сбора данных карт с сайта unmatched.cards
 * Использует Playwright для навигации по страницам героёв
 */

const { PrismaClient } = require('@prisma/client');
const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');

const prisma = new PrismaClient();

// Список героёв из БД
async function getHeroesFromDB() {
  const heroes = await prisma.hero.findMany({
    select: { name: true },
    orderBy: { name: 'asc' }
  });
  return heroes.map(h => h.name);
}

// Преобразование имени героя в slug для URL
function nameToSlug(name) {
  return name
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '');
}

async function scrapeHeroCards(heroName, browser) {
  const slug = nameToSlug(heroName);
  const url = `https://unmatched.cards/umdb/decks/${slug}`;

  console.log(`  📖 Загрузка: ${url}`);

  const page = await browser.newPage();

  try {
    await page.goto(url, { waitUntil: 'networkidle', timeout: 30000 });

    // Подождём загрузку контента
    await page.waitForTimeout(3000);

    // Получим данные таблицы
    const cardsData = await page.evaluate(() => {
      const result = [];
      const rows = document.querySelectorAll('tr');

      rows.forEach(row => {
        const cells = row.querySelectorAll('td');
        if (cells.length >= 5) {
          const firstCell = cells[0].textContent.trim();

          // Пропускаем заголовки и строки без "×"
          if (!firstCell.includes('×') || firstCell.includes('Title')) {
            return;
          }

          // Парсим строку: "3×", "Card Name", "Banner", "", "Value", "Boost", "..."
          const countStr = cells[0].textContent.trim();
          const title = cells[1].textContent.trim();
          const banner = cells[2].textContent.trim();
          const value = cells[5]?.textContent.trim() || '';
          const boost = cells[6]?.textContent.trim() || '';

          if (title) {
            result.push({
              count: parseInt(countStr.replace('×', '')) || 1,
              title: title,
              banner: banner || null,
              value: value === '' ? null : parseInt(value),
              boost: boost === '' ? null : parseInt(boost),
            });
          }
        }
      });

      return result;
    });

    await page.close();
    return cardsData;
  } catch (error) {
    console.error(`    ❌ Ошибка при загрузке ${slug}: ${error.message}`);
    await page.close();
    return [];
  }
}

async function main() {
  console.log('🔄 Сбор данных карт с unmatched.cards...\n');

  const heroes = await getHeroesFromDB();
  console.log(`📊 Найдено героёв в БД: ${heroes.length}`);

  const browser = await chromium.launch({ headless: false });
  const allCardsData = {};

  // Соберём данные для всех героёв
  for (let i = 0; i < heroes.length; i++) {
    const heroName = heroes[i];
    console.log(`\n[${i + 1}/${heroes.length}] ${heroName}`);

    const cardsData = await scrapeHeroCards(heroName, browser);

    if (cardsData.length > 0) {
      allCardsData[heroName] = cardsData;
      console.log(`   ✅ Получено карт: ${cardsData.length}`);
    }

    // Небольшая задержка между запросами
    await new Promise(resolve => setTimeout(resolve, 1000));
  }

  await browser.close();

  // Сохраняем результаты в файл
  const outputPath = path.join(__dirname, 'scraped-cards-data.json');
  fs.writeFileSync(outputPath, JSON.stringify(allCardsData, null, 2));

  console.log(`\n💾 Данные сохранены в: ${outputPath}`);
  console.log(`📊 Всего героёв обработано: ${Object.keys(allCardsData).length}`);
}

main()
  .catch((e) => {
    console.error('❌ Error:', e);
    process.exit(1);
  })
  .finally(async () => {
    await prisma.$disconnect();
  });
