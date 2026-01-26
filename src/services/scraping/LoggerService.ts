/**
 * Logger service for scraping operations
 */

import type { Logger } from './types.js';

/**
 * Format seconds as MM:SS
 */
function formatTime(seconds: number): string {
  const mins = Math.floor(seconds / 60);
  const secs = Math.floor(seconds % 60);
  return `${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
}

/**
 * Draw a progress bar
 */
function drawProgress(current: number, total: number, width = 30): string {
  const percentage = Math.min(100, Math.max(0, (current / total) * 100));
  const filled = Math.round((width * percentage) / 100);
  const empty = width - filled;
  return `[${'█'.repeat(filled)}${'░'.repeat(empty)}] ${percentage.toFixed(1)}%`;
}

/**
 * Format a number with thousands separator
 */
export function formatNumber(num: number): string {
  return num.toString().replace(/\B(?=(\d{3})+(?!\d))/g, ' ');
}

export class ConsoleLogger implements Logger {
  private verbose: boolean;
  private silent: boolean;

  constructor(options: { verbose?: boolean; silent?: boolean } = {}) {
    this.verbose = options.verbose ?? false;
    this.silent = options.silent ?? false;
  }

  info(message: string): void {
    if (!this.silent) console.log(message);
  }

  warn(message: string): void {
    if (!this.silent) console.warn(`⚠️  ${message}`);
  }

  error(message: string, error?: unknown): void {
    if (!this.silent) {
      console.error(`❌ ${message}`);
      if (error && this.verbose) {
        console.error(error);
      }
    }
  }

  debug(message: string): void {
    if (this.verbose && !this.silent) {
      console.debug(`  [DEBUG] ${message}`);
    }
  }

  progress(current: number, total: number, slug: string, eta: number): void {
    if (!this.silent) {
      const bar = drawProgress(current, total);
      process.stdout.write(`\r${bar} ${current}/${total} | ${slug} | ETA: ${formatTime(eta)}       `);
    }
  }

  success(message: string): void {
    if (!this.silent) console.log(`✅ ${message}`);
  }

  /**
   * Print a header banner
   */
  header(title: string, subtitle: string): void {
    if (this.silent) return;
    const width = 60;
    const padding = Math.max(0, width - title.length - 2);
    console.log('╔' + '═'.repeat(width) + '╗');
    console.log('║' + title.padEnd(width / 2) + ' '.repeat(padding) + '║');
    console.log('║' + subtitle.padEnd(width) + '║');
    console.log('╚' + '═'.repeat(width) + '╝');
  }

  /**
   * Print a footer banner with stats
   */
  footer(stats: { heroes: number; images: number; models: number; duration: string }): void {
    if (this.silent) return;
    const width = 60;
    console.log('\n\n╔' + '═'.repeat(width) + '╗');
    console.log('║' + '✅ Done!'.padEnd(width) + '║');
    console.log(`║  Heroes:       ${stats.heroes.toString().padStart(width - 16)}║`);
    console.log(`║  Images:       ${formatNumber(stats.images).padStart(width - 16)}║`);
    console.log(`║  3D Models:    ${formatNumber(stats.models).padStart(width - 16)}║`);
    console.log(`║  Duration:     ${stats.duration.padStart(width - 16)}║`);
    console.log('╚' + '═'.repeat(width) + '╝');
  }

  /**
   * Clear the current line
   */
  clearLine(): void {
    if (!this.silent) {
      process.stdout.write('\r' + ' '.repeat(80) + '\r');
    }
  }
}

/**
 * Silent logger for testing or when no output is desired
 */
export class SilentLogger implements Logger {
  info(): void {}
  warn(): void {}
  error(): void {}
  debug(): void {}
  progress(): void {}
  success(): void {}
  header(): void {}
  footer(): void {}
}
