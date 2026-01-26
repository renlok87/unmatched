/**
 * Types and interfaces for the Unmatched Club scraping service
 */

// ============================================================================
// Configuration
// ============================================================================

export interface ScraperConfig {
  baseUrl: string;
  apiBase: string;
  endpoints: ApiEndpoints;
  paths: StoragePaths;
  delays: DelayConfig;
  options: ScraperOptions;
}

export interface ApiEndpoints {
  heroes: string;
  sets: string;
  villains: string;
  minions: string;
  maps: string;
}

export interface StoragePaths {
  root: string;
  api: string;
  heroes: string;
  normalized: string;
  images: string;
  heroesImages: HeroesImagePaths;
  decksImages: string;
  setsImages: string;
}

export interface HeroesImagePaths {
  avatars: string;
  minis: string;
  cardCovers: string;
  models: string;
}

export interface DelayConfig {
  betweenHeroes: number;
  betweenImages: number;
}

export interface ScraperOptions {
  skipExistingImages: boolean;
  downloadModels: boolean;
  verbose: boolean;
}

// ============================================================================
// Domain Models
// ============================================================================

export interface HeroData {
  slug: string;
  name: string;
  urls: HeroUrls;
  cards: CardInfo[];
  images: string[];
}

export interface HeroUrls {
  avatar?: string;
  mini?: string;
  cardCover?: string;
  model?: string;
}

export interface CardInfo {
  id: number;
  url: string;
  filename: string;
}

export interface ImageCategory {
  category: string | null;
  filename: string;
  isModel: boolean;
}

// ============================================================================
// Statistics
// ============================================================================

export interface ScraperStats {
  heroes: number;
  imagesDownloaded: number;
  modelsDownloaded: number;
  errors: number;
  startTime: number;
  endTime?: number;
}

export interface ScrapeProgress {
  current: number;
  total: number;
  currentSlug: string;
  eta: number;
}

// ============================================================================
// Results
// ============================================================================

export interface ScrapeResult {
  success: boolean;
  stats: ScraperStats;
  heroes: string[];
  errors: string[];
}

export interface ScrapeIndex {
  scrapedAt: string;
  source: string;
  stats: {
    heroes: number;
    imagesDownloaded: number;
    modelsDownloaded: number;
    errors: number;
    duration: string;
  };
  data: {
    heroes: string[];
    sets: string;
    villains: string;
    minions: string;
    maps: string;
  };
}

// ============================================================================
// Service Interfaces
// ============================================================================

export interface HttpClient {
  getJson<T>(url: string): Promise<T>;
  downloadFile(url: string): Promise<Buffer>;
  downloadFileIfNotExists(url: string, destPath: string): Promise<boolean>;
}

export interface FileStorage {
  writeFile(path: string, data: string | Buffer): Promise<void>;
  readFile<T>(path: string): Promise<T>;
  exists(path: string): Promise<boolean>;
  mkdir(path: string): Promise<void>;
  mkdirAll(paths: string[]): Promise<void>;
}

export interface Logger {
  info(message: string): void;
  warn(message: string): void;
  error(message: string, error?: unknown): void;
  debug(message: string): void;
  progress(current: number, total: number, slug: string, eta: number): void;
  success(message: string): void;
  header(title: string, subtitle: string): void;
  footer(stats: { heroes: number; images: number; models: number; duration: string }): void;
}

export interface ImageDownloader {
  downloadImage(url: string, destPath: string): Promise<boolean>;
  downloadModel(url: string, destPath: string): Promise<boolean>;
}
