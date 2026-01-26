/**
 * HTTP Client service for making API requests and downloading files
 */

import type { HttpClient, Logger } from './types.js';

export class HttpClientService implements HttpClient {
  private readonly logger: Logger;
  private readonly timeout: number;
  private readonly retryAttempts: number;
  private readonly retryDelay: number;

  constructor(
    logger: Logger,
    options: {
      timeout?: number;
      retryAttempts?: number;
      retryDelay?: number;
    } = {}
  ) {
    this.logger = logger;
    this.timeout = options.timeout ?? 30000;
    this.retryAttempts = options.retryAttempts ?? 3;
    this.retryDelay = options.retryDelay ?? 1000;
  }

  /**
   * Fetch JSON from URL with retry logic
   */
  async getJson<T>(url: string): Promise<T> {
    let lastError: Error | undefined;

    for (let attempt = 1; attempt <= this.retryAttempts; attempt++) {
      try {
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), this.timeout);

        const response = await fetch(url, {
          signal: controller.signal,
        });

        clearTimeout(timeoutId);

        if (!response.ok) {
          throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }

        return (await response.json()) as T;
      } catch (error) {
        lastError = error instanceof Error ? error : new Error(String(error));

        if (attempt < this.retryAttempts) {
          this.logger.debug(`Retry ${attempt}/${this.retryAttempts} for ${url}`);
          await this.delay(this.retryDelay * attempt);
        }
      }
    }

    throw new Error(`Failed to fetch ${url}: ${lastError?.message ?? 'Unknown error'}`);
  }

  /**
   * Download file as Buffer
   */
  async downloadFile(url: string): Promise<Buffer> {
    let lastError: Error | undefined;

    for (let attempt = 1; attempt <= this.retryAttempts; attempt++) {
      try {
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), this.timeout);

        const response = await fetch(url, {
          signal: controller.signal,
        });

        clearTimeout(timeoutId);

        if (!response.ok) {
          throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }

        const arrayBuffer = await response.arrayBuffer();
        return Buffer.from(arrayBuffer);
      } catch (error) {
        lastError = error instanceof Error ? error : new Error(String(error));

        if (attempt < this.retryAttempts) {
          await this.delay(this.retryDelay * attempt);
        }
      }
    }

    throw new Error(`Failed to download ${url}: ${lastError?.message ?? 'Unknown error'}`);
  }

  /**
   * Download file only if it doesn't exist at destination
   * Returns true if file was downloaded, false if skipped or failed
   */
  async downloadFileIfNotExists(_url: string, _destPath: string): Promise<boolean> {
    // This method requires FileStorage - handled by the scraper service
    throw new Error('downloadFileIfNotExists requires FileStorage dependency');
  }

  /**
   * Delay execution for specified milliseconds
   */
  private delay(ms: number): Promise<void> {
    return new Promise(resolve => setTimeout(resolve, ms));
  }
}

/**
 * HTTP client with integrated file storage
 */
export class HttpClientWithStorage implements HttpClient {
  private readonly http: HttpClientService;
  private readonly fileStorage: { exists: (path: string) => Promise<boolean>; writeFile: (path: string, data: Buffer) => Promise<void> };

  constructor(
    http: HttpClientService,
    fileStorage: { exists: (path: string) => Promise<boolean>; writeFile: (path: string, data: Buffer) => Promise<void> }
  ) {
    this.http = http;
    this.fileStorage = fileStorage;
  }

  async getJson<T>(url: string): Promise<T> {
    return this.http.getJson<T>(url);
  }

  async downloadFile(url: string): Promise<Buffer> {
    return this.http.downloadFile(url);
  }

  async downloadFileIfNotExists(url: string, destPath: string): Promise<boolean> {
    try {
      // Check if file already exists
      const exists = await this.fileStorage.exists(destPath);
      if (exists) {
        return false;
      }

      // Download the file
      const buffer = await this.http.downloadFile(url);
      await this.fileStorage.writeFile(destPath, buffer);
      return true;
    } catch {
      return false;
    }
  }
}
