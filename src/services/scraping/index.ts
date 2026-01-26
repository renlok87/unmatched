/**
 * Unmatched Club Scraping Service
 *
 * A service-oriented architecture for scraping data from the-unmatched.club
 *
 * @example
 * ```ts
 * import { createScraper } from '@/services/scraping';
 *
 * const scraper = createScraper({ verbose: true });
 * const result = await scraper.scrape();
 * ```
 */

// Main service
export { UnmatchedClubScraper } from './UnmatchedClubScraper.js';

// Dependencies
export {
  HttpClientService,
  HttpClientWithStorage,
} from './HttpClientService.js';
export {
  FileStorageService,
  InMemoryFileStorage,
} from './FileStorageService.js';
export {
  ConsoleLogger,
  SilentLogger,
  formatNumber,
} from './LoggerService.js';

// Utilities
export {
  HeroDataNormalizer,
  findAllHeroSlugs,
  normalizeHeroData,
  extractImageUrls,
  getImagePath,
  isModelUrl,
} from './HeroDataNormalizer.js';

// Configuration
export {
  DEFAULT_CONFIG,
  buildUrl,
  buildHeroUrl,
} from './config.js';

// Types
export type {
  ScraperConfig,
  ApiEndpoints,
  StoragePaths,
  HeroesImagePaths,
  DelayConfig,
  ScraperOptions,
  HeroData,
  HeroUrls,
  CardInfo,
  ImageCategory,
  ScraperStats,
  ScrapeProgress,
  ScrapeResult,
  ScrapeIndex,
  HttpClient,
  FileStorage,
  Logger,
  ImageDownloader,
} from './types.js';

// CLI
export { main as runCli, createScraper as createCliScraper, parseArgs } from './cli.js';
export type { CliOptions } from './cli.js';

// ============================================================================
// Factory Functions
// ============================================================================

import type { ScraperConfig, Logger } from './types.js';
import { DEFAULT_CONFIG } from './config.js';
import { UnmatchedClubScraper } from './UnmatchedClubScraper.js';
import { HttpClientService, HttpClientWithStorage } from './HttpClientService.js';
import { FileStorageService } from './FileStorageService.js';
import { ConsoleLogger } from './LoggerService.js';

export interface ScraperDeps {
  config?: Partial<ScraperConfig>;
  logger?: Logger;
  verbose?: boolean;
  silent?: boolean;
}

/**
 * Factory function to create a configured scraper instance
 *
 * @example
 * ```ts
 * const scraper = createScraper({ verbose: true });
 * const result = await scraper.scrape();
 * ```
 */
export function createScraper(deps: ScraperDeps = {}): UnmatchedClubScraper {
  const config: ScraperConfig = {
    ...DEFAULT_CONFIG,
    ...deps.config,
    paths: {
      ...DEFAULT_CONFIG.paths,
      ...deps.config?.paths,
    },
    options: {
      ...DEFAULT_CONFIG.options,
      ...deps.config?.options,
    },
  };

  const logger = deps.logger ?? new ConsoleLogger({
    verbose: deps.verbose ?? false,
    silent: deps.silent ?? false,
  });

  const fileStorage = new FileStorageService(logger);
  const httpClient = new HttpClientService(logger);
  const httpWithStorage = new HttpClientWithStorage(httpClient, fileStorage);

  return new UnmatchedClubScraper(config, httpWithStorage, fileStorage, logger);
}

/**
 * Create a scraper with minimal output (useful for programmatic usage)
 */
export function createSilentScraper(
  config?: Partial<ScraperConfig>
): UnmatchedClubScraper {
  return createScraper({
    config,
    silent: true,
  });
}
