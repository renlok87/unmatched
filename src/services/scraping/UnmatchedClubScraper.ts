/**
 * Main scraper service for the-unmatched.club
 *
 * Orchestrates the scraping of heroes, sets, villains, minions, maps,
 * downloading images and 3D models.
 */

import path from 'path';
import type {
  ScraperConfig,
  ScraperStats,
  ScrapeResult,
  Logger,
  HttpClient,
  FileStorage,
} from './types.js';
import { HeroDataNormalizer } from './HeroDataNormalizer.js';
import { buildUrl, buildHeroUrl } from './config.js';

export class UnmatchedClubScraper {
  private readonly config: ScraperConfig;
  private readonly http: HttpClient;
  private readonly storage: FileStorage;
  private readonly logger: Logger;
  private readonly stats: ScraperStats;

  constructor(
    config: ScraperConfig,
    http: HttpClient,
    storage: FileStorage,
    logger: Logger
  ) {
    this.config = config;
    this.http = http;
    this.storage = storage;
    this.logger = logger;
    this.stats = {
      heroes: 0,
      imagesDownloaded: 0,
      modelsDownloaded: 0,
      errors: 0,
      startTime: 0,
    };
  }

  /**
   * Run the full scraping process
   */
  async scrape(): Promise<ScrapeResult> {
    this.stats.startTime = Date.now();
    const errors: string[] = [];

    try {
      // Ensure all directories exist
      await this.prepareDirectories();

      // Scrape general data in parallel
      await this.scrapeGeneralData().catch(err => {
        errors.push(`General data: ${err}`);
      });

      // Get hero list
      const slugs = await this.getHeroSlugs();
      this.logger.info(`\n✨ Found ${slugs.length} heroes`);

      if (slugs.length === 0) {
        this.logger.warn('\n⚠️  No heroes found. Exiting.');
        return this.createResult(slugs, errors);
      }

      // Show first few heroes
      const preview = slugs.slice(0, 5).join(', ');
      const more = slugs.length > 5 ? '...' : '';
      this.logger.info(`   First: ${preview}${more}`);

      // Scrape each hero
      this.logger.info('\n🔄 Scraping Heroes...');
      for (let i = 0; i < slugs.length; i++) {
        const error = await this.scrapeHero(slugs[i], i + 1, slugs.length);
        if (error) {
          errors.push(error);
        }
        await this.delay(this.config.delays.betweenHeroes);
      }

      // Generate index and summary
      await this.generateIndex(slugs);
      await this.generateSummary(slugs);

      this.stats.endTime = Date.now();

      // Print summary
      this.printSummary();

      return this.createResult(slugs, errors);

    } catch (error) {
      this.logger.error('Fatal error during scraping', error);
      errors.push(`Fatal: ${error}`);
      return this.createResult([], errors);
    }
  }

  /**
   * Prepare directories for storing data
   */
  private async prepareDirectories(): Promise<void> {
    const paths = [
      this.config.paths.api,
      this.config.paths.heroes,
      this.config.paths.normalized,
      this.config.paths.heroesImages.avatars,
      this.config.paths.heroesImages.minis,
      this.config.paths.heroesImages.cardCovers,
      this.config.paths.heroesImages.models,
      this.config.paths.decksImages,
      this.config.paths.setsImages,
    ];

    await this.storage.mkdirAll(paths);
  }

  /**
   * Scrape general data (sets, villains, minions, maps)
   */
  private async scrapeGeneralData(): Promise<void> {
    this.logger.info('\n📦 Scraping Sets, Villains, Minions, Maps...');

    const tasks = [
      this.scrapeSets(),
      this.scrapeVillains(),
      this.scrapeMinions(),
      this.scrapeMaps(),
    ];

    await Promise.all(tasks);
  }

  /**
   * Download and save sets data
   */
  private async scrapeSets(): Promise<void> {
    try {
      const url = buildUrl(this.config.apiBase, this.config.endpoints.sets);
      const data = await this.http.getJson(url);
      const filePath = path.join(this.config.paths.api, 'sets.json');
      await this.storage.writeFile(filePath, JSON.stringify(data, null, 2));
      this.logger.debug('Sets data saved');
    } catch (error) {
      this.logger.error('Error scraping sets', error);
      throw error;
    }
  }

  /**
   * Download and save villains data
   */
  private async scrapeVillains(): Promise<void> {
    try {
      const url = buildUrl(this.config.apiBase, this.config.endpoints.villains);
      const data = await this.http.getJson(url);
      const filePath = path.join(this.config.paths.api, 'villains.json');
      await this.storage.writeFile(filePath, JSON.stringify(data, null, 2));
      this.logger.debug('Villains data saved');
    } catch (error) {
      this.logger.error('Error scraping villains', error);
      throw error;
    }
  }

  /**
   * Download and save minions data
   */
  private async scrapeMinions(): Promise<void> {
    try {
      const url = buildUrl(this.config.apiBase, this.config.endpoints.minions);
      const data = await this.http.getJson(url);
      const filePath = path.join(this.config.paths.api, 'minions.json');
      await this.storage.writeFile(filePath, JSON.stringify(data, null, 2));
      this.logger.debug('Minions data saved');
    } catch (error) {
      this.logger.error('Error scraping minions', error);
      throw error;
    }
  }

  /**
   * Download and save maps data
   */
  private async scrapeMaps(): Promise<void> {
    try {
      const url = buildUrl(this.config.apiBase, this.config.endpoints.maps);
      const data = await this.http.getJson(url);
      const filePath = path.join(this.config.paths.api, 'maps.json');
      await this.storage.writeFile(filePath, JSON.stringify(data, null, 2));
      this.logger.debug('Maps data saved');
    } catch (error) {
      this.logger.error('Error scraping maps', error);
      throw error;
    }
  }

  /**
   * Get list of all hero slugs
   */
  private async getHeroSlugs(): Promise<string[]> {
    this.logger.info('\n🦸 Getting Hero List...');

    try {
      const url = buildUrl(this.config.apiBase, this.config.endpoints.heroes);
      const data = await this.http.getJson(url);

      // Save the raw heroes data
      const filePath = path.join(this.config.paths.api, 'heroes.json');
      await this.storage.writeFile(filePath, JSON.stringify(data, null, 2));

      return HeroDataNormalizer.findAllHeroSlugs(data);
    } catch (error) {
      this.logger.error('Error getting hero list', error);
      return [];
    }
  }

  /**
   * Scrape a single hero's details, images and models
   * Returns error message if failed, null if successful
   */
  private async scrapeHero(
    slug: string,
    index: number,
    total: number
  ): Promise<string | null> {
    const elapsed = (Date.now() - this.stats.startTime) / 1000;
    const eta = elapsed > 0 ? (elapsed / index) * (total - index) : 0;

    this.logger.progress(index, total, slug, eta);

    try {
      const url = buildHeroUrl(this.config.apiBase, slug);
      const data = await this.http.getJson(url);

      // Save raw hero data
      const heroPath = path.join(this.config.paths.heroes, `${slug}.json`);
      await this.storage.writeFile(heroPath, JSON.stringify(data, null, 2));

      // Create normalized version
      const normalized = HeroDataNormalizer.normalizeHeroData(slug, data);
      const normalizedPath = path.join(this.config.paths.normalized, `${slug}.json`);
      await this.storage.writeFile(normalizedPath, JSON.stringify(normalized, null, 2));

      // Download images and models
      await this.downloadHeroAssets(normalized.images);

      this.stats.heroes++;
      return null;

    } catch (error) {
      this.stats.errors++;
      const errorMsg = `${slug}: ${error}`;
      this.logger.debug(`Error: ${errorMsg}`);
      return errorMsg;
    }
  }

  /**
   * Download all images and models for a hero
   */
  private async downloadHeroAssets(imageUrls: string[]): Promise<void> {
    for (const imageUrl of imageUrls) {
      const destPath = HeroDataNormalizer.getImagePath(imageUrl, {
        avatars: this.config.paths.heroesImages.avatars,
        minis: this.config.paths.heroesImages.minis,
        cardCovers: this.config.paths.heroesImages.cardCovers,
        models: this.config.paths.heroesImages.models,
        decks: this.config.paths.decksImages,
        sets: this.config.paths.setsImages,
      });

      if (!destPath) continue;

      // Skip if file exists and option is enabled
      if (this.config.options.skipExistingImages) {
        const exists = await this.storage.exists(destPath);
        if (exists) continue;
      }

      const isModel = HeroDataNormalizer.isModelUrl(imageUrl);

      try {
        const buffer = await this.http.downloadFile(imageUrl);
        await this.storage.writeFile(destPath, buffer);

        if (isModel) {
          this.stats.modelsDownloaded++;
        } else {
          this.stats.imagesDownloaded++;
        }
      } catch {
        this.stats.errors++;
      }

      await this.delay(this.config.delays.betweenImages);
    }
  }

  /**
   * Generate index file with all data structure
   */
  private async generateIndex(slugs: string[]): Promise<void> {
    this.logger.info('\n\n📝 Generating Index...');

    const elapsed = (Date.now() - this.stats.startTime) / 1000;

    const index = {
      scrapedAt: new Date().toISOString(),
      source: this.config.baseUrl,
      stats: {
        heroes: slugs.length,
        imagesDownloaded: this.stats.imagesDownloaded,
        modelsDownloaded: this.stats.modelsDownloaded,
        errors: this.stats.errors,
        duration: this.formatTime(elapsed),
      },
      data: {
        heroes: slugs,
        sets: 'sets.json',
        villains: 'villains.json',
        minions: 'minions.json',
        maps: 'maps.json',
      },
    };

    const indexPath = path.join(this.config.paths.root, 'index.json');
    await this.storage.writeFile(indexPath, JSON.stringify(index, null, 2));
  }

  /**
   * Generate a summary markdown file
   */
  private async generateSummary(slugs: string[]): Promise<void> {
    const elapsed = (Date.now() - this.stats.startTime) / 1000;

    const content = `# The Unmatched Club - Scrape Summary

**Date:** ${new Date().toISOString()}
**Duration:** ${this.formatTime(elapsed)}

## Statistics

| Metric | Count |
|--------|-------|
| Heroes | ${this.stats.heroes} |
| Images Downloaded | ${this.formatNumber(this.stats.imagesDownloaded)} |
| 3D Models Downloaded | ${this.formatNumber(this.stats.modelsDownloaded)} |
| Errors | ${this.stats.errors} |

## Hero List

${slugs.map(slug => `- ${slug}`).join('\n')}

## File Structure

\`\`\`
scraped-data/
├── api/
│   ├── heroes.json           # Raw heroes API data
│   ├── heroes/               # Individual hero data
│   ├── normalized/           # Normalized hero data
│   ├── sets.json
│   ├── villains.json
│   ├── minions.json
│   └── maps.json
├── images/
│   ├── heroes/
│   │   ├── avatars/
│   │   ├── minis/
│   │   ├── card-covers/
│   │   └── models/
│   ├── decks/
│   └── sets/
├── index.json
└── summary.md
\`\`\`

## Usage

The normalized hero data structure:

\`\`\`json
{
  "slug": "muhammad-ali",
  "name": "Muhammad Ali",
  "urls": {
    "avatar": "https://...",
    "mini": "https://...",
    "cardCover": "https://...",
    "model": "https://..."
  },
  "cards": [
    { "id": 0, "url": "...", "filename": "..." }
  ]
}
\`\`\`
`;

    const summaryPath = path.join(this.config.paths.root, 'summary.md');
    await this.storage.writeFile(summaryPath, content);
  }

  /**
   * Print final summary
   */
  private printSummary(): void {
    const elapsed = this.stats.endTime
      ? (this.stats.endTime - this.stats.startTime) / 1000
      : 0;

    this.logger.footer({
      heroes: this.stats.heroes,
      images: this.stats.imagesDownloaded,
      models: this.stats.modelsDownloaded,
      duration: this.formatTime(elapsed),
    });

    this.logger.info(`\n📁 Data saved to: ${this.config.paths.root}\n`);
  }

  /**
   * Create result object
   */
  private createResult(slugs: string[], errors: string[]): ScrapeResult {
    return {
      success: errors.length === 0,
      stats: { ...this.stats },
      heroes: slugs,
      errors,
    };
  }

  /**
   * Format seconds as MM:SS
   */
  private formatTime(seconds: number): string {
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return `${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
  }

  /**
   * Format number with thousands separator
   */
  private formatNumber(num: number): string {
    return num.toString().replace(/\B(?=(\d{3})+(?!\d))/g, ' ');
  }

  /**
   * Delay execution
   */
  private delay(ms: number): Promise<void> {
    return new Promise(resolve => setTimeout(resolve, ms));
  }

  /**
   * Get current stats (for progress tracking)
   */
  getStats(): Readonly<ScraperStats> {
    return { ...this.stats };
  }
}
