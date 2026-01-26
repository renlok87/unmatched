/**
 * CLI entry point for the Unmatched Club scraper
 *
 * Usage:
 *   tsx src/services/scraping/cli.ts
 *   node dist/services/scraping/cli.js
 */

import { UnmatchedClubScraper } from './UnmatchedClubScraper.js';
import { HttpClientService, HttpClientWithStorage } from './HttpClientService.js';
import { FileStorageService } from './FileStorageService.js';
import { ConsoleLogger } from './LoggerService.js';
import { DEFAULT_CONFIG } from './config.js';
import type { ScraperConfig } from './types.js';

/**
 * Parse command line arguments
 */
interface CliOptions {
  verbose: boolean;
  silent: boolean;
  downloadModels: boolean;
  skipExisting: boolean;
  baseUrl?: string;
}

function parseArgs(args: string[]): CliOptions {
  const options: CliOptions = {
    verbose: false,
    silent: false,
    downloadModels: true,
    skipExisting: true,
  };

  for (const arg of args) {
    switch (arg) {
      case '-v':
      case '--verbose':
        options.verbose = true;
        break;
      case '-s':
      case '--silent':
        options.silent = true;
        break;
      case '--no-models':
        options.downloadModels = false;
        break;
      case '--force-download':
        options.skipExisting = false;
        break;
      default:
        if (arg.startsWith('--base-url=')) {
          options.baseUrl = arg.split('=')[1];
        }
    }
  }

  return options;
}

/**
 * Create scraper with dependencies
 */
function createScraper(options: CliOptions): UnmatchedClubScraper {
  // Create config with CLI overrides
  const config: ScraperConfig = {
    ...DEFAULT_CONFIG,
    baseUrl: options.baseUrl ?? DEFAULT_CONFIG.baseUrl,
    apiBase: options.baseUrl ?? DEFAULT_CONFIG.apiBase,
    options: {
      ...DEFAULT_CONFIG.options,
      downloadModels: options.downloadModels,
      skipExistingImages: options.skipExisting,
      verbose: options.verbose,
    },
  };

  // Create dependencies
  const logger = new ConsoleLogger({
    verbose: options.verbose,
    silent: options.silent,
  });

  const fileStorage = new FileStorageService(logger);
  const httpClient = new HttpClientService(logger);
  const httpWithStorage = new HttpClientWithStorage(httpClient, fileStorage);

  // Create scraper
  return new UnmatchedClubScraper(config, httpWithStorage, fileStorage, logger);
}

/**
 * Main CLI entry point
 */
async function main(): Promise<void> {
  const args = process.argv.slice(2);
  const options = parseArgs(args);

  // Show help
  if (args.includes('-h') || args.includes('--help')) {
    console.log(`
Unmatched Club Scraper

Usage: scrape [options]

Options:
  -v, --verbose           Enable verbose logging
  -s, --silent            Silent mode (no output)
  --no-models            Skip downloading 3D models
  --force-download       Re-download existing files
  --base-url=<url>       Override base URL
  -h, --help             Show this help

Examples:
  npm run scrape
  npm run scrape -- --verbose
  npm run scrape -- --no-models --force-download
`);
    process.exit(0);
  }

  const scraper = createScraper(options);

  if (!options.silent) {
    logger.header(
      '          The Unmatched Club Scraper v3.0                  ',
      '    Downloading heroes, images, 3D models...                '
    );
  }

  const result = await scraper.scrape();

  if (!result.success) {
    process.exit(1);
  }
}

// Create a temporary logger for the header
const logger = new ConsoleLogger();

// Run if executed directly
if (import.meta.url === `file://${process.argv[1].replace(/\\/g, '/')}`) {
  main().catch(error => {
    console.error('Fatal error:', error);
    process.exit(1);
  });
}

export { main, createScraper, parseArgs };
export type { CliOptions };
