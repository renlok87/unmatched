/**
 * File Storage service for reading and writing files
 */

import fs from 'fs/promises';
import path from 'path';
import type { FileStorage, Logger } from './types.js';

export class FileStorageService implements FileStorage {
  private readonly logger: Logger;

  constructor(logger: Logger) {
    this.logger = logger;
  }

  /**
   * Write string content to file
   */
  async writeFile(filePath: string, data: string | Buffer): Promise<void> {
    try {
      // Ensure directory exists
      const dir = path.dirname(filePath);
      await this.mkdir(dir);

      await fs.writeFile(filePath, data);
      this.logger.debug(`Wrote: ${filePath}`);
    } catch (error) {
      this.logger.error(`Failed to write ${filePath}`, error);
      throw error;
    }
  }

  /**
   * Write JSON data to file
   */
  async writeJson(filePath: string, data: unknown, pretty = true): Promise<void> {
    const content = pretty ? JSON.stringify(data, null, 2) : JSON.stringify(data);
    await this.writeFile(filePath, content);
  }

  /**
   * Read and parse JSON file
   */
  async readFile<T>(filePath: string): Promise<T> {
    try {
      const content = await fs.readFile(filePath, 'utf-8');
      return JSON.parse(content) as T;
    } catch (error) {
      this.logger.error(`Failed to read ${filePath}`, error);
      throw error;
    }
  }

  /**
   * Check if file exists
   */
  async exists(filePath: string): Promise<boolean> {
    try {
      await fs.access(filePath);
      return true;
    } catch {
      return false;
    }
  }

  /**
   * Create directory recursively
   */
  async mkdir(dirPath: string): Promise<void> {
    try {
      await fs.mkdir(dirPath, { recursive: true });
    } catch (error) {
      // Ignore if already exists
      const code = (error as { code?: string })?.code;
      if (code !== 'EEXIST') {
        this.logger.error(`Failed to create directory ${dirPath}`, error);
        throw error;
      }
    }
  }

  /**
   * Create multiple directories in parallel
   */
  async mkdirAll(paths: string[]): Promise<void> {
    await Promise.all(paths.map(p => this.mkdir(p)));
  }

  /**
   * Read directory contents
   */
  async readDir(dirPath: string): Promise<string[]> {
    try {
      const entries = await fs.readdir(dirPath, { withFileTypes: true });
      return entries
        .filter(entry => !entry.name.startsWith('.'))
        .map(entry => entry.name);
    } catch (error) {
      this.logger.error(`Failed to read directory ${dirPath}`, error);
      return [];
    }
  }

  /**
   * Delete file if exists
   */
  async delete(filePath: string): Promise<void> {
    try {
      await fs.unlink(filePath);
      this.logger.debug(`Deleted: ${filePath}`);
    } catch (error) {
      const code = (error as { code?: string })?.code;
      if (code !== 'ENOENT') {
        this.logger.error(`Failed to delete ${filePath}`, error);
        throw error;
      }
    }
  }
}

/**
 * In-memory file storage for testing
 */
export class InMemoryFileStorage implements FileStorage {
  private readonly files = new Map<string, string | Buffer>();

  async writeFile(filePath: string, data: string | Buffer): Promise<void> {
    this.files.set(filePath, data);
  }

  async readFile<T>(_filePath: string): Promise<T> {
    throw new Error('Not implemented in in-memory storage');
  }

  async exists(filePath: string): Promise<boolean> {
    return this.files.has(filePath);
  }

  async mkdir(_filePath: string): Promise<void> {
    // No-op for in-memory storage
  }

  async mkdirAll(_paths: string[]): Promise<void> {
    // No-op for in-memory storage
  }

  /**
   * Get all stored files (for testing)
   */
  getFiles(): Map<string, string | Buffer> {
    return this.files;
  }

  /**
   * Clear all files (for testing)
   */
  clear(): void {
    this.files.clear();
  }
}
