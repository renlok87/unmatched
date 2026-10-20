/**
 * Банеры карт: опечатки источника и проверка «банер = боец своего героя».
 *
 * Банер карты — строка, а не ссылка на бойца, поэтому опечатка в скрейпе
 * (the-unmatched.club) молча снимает правило «именную карту играет только свой
 * боец»: validateBanner разрешает неизвестный банер. Разбор DE 2026-10-20
 * (docs/research/de-reverse-2026-10-20, DATA-01/DATA-02) нашёл 47 таких строк
 * у 8 героев. Расхождения написания («T-Rex» / «T. Rex», «Spider Man» /
 * «Spiderman», «Sea dog» / «Seadog», «Jill Trent» / «Dr. Jill Trent») закрывает
 * нормализация bannerAllows, формы Jekyll & Hyde — BANNER_FORM_ALIASES.
 * Здесь остаются настоящие опечатки — их правят данные.
 *
 * Чистый модуль: его используют seed-scraped.ts (правка при импорте и
 * проверка), fix-card-gaps.ts (правка живой БД) и спека.
 */

import { bannerAllows } from '../src/game-engine/validators/game-rules.validator';

export interface BannerFix {
  /** Hero.name в БД */
  readonly heroName: string;
  /** Банер в источнике */
  readonly from: string;
  /** Имя бойца, которому принадлежит карта */
  readonly to: string;
}

export const BANNER_FIXES: readonly BannerFix[] = [
  // 8 карт Alice: Jabberwock мог играть её именные карты
  { heroName: 'Alice', from: 'Allice', to: 'Alice' },
  // By Fortune and Fate — карта помощника The Porter, играл Sinbad
  { heroName: 'Sinbad', from: 'The Potter', to: 'The Porter' },
  // Spymaster's ruse — карта помощника Dijkstra
  { heroName: 'Philippa', from: 'Djkstra', to: 'Dijkstra' },
];

/** Банер карты героя после правки опечатки (без правки — как есть). */
export function applyBannerFix(heroName: string, bannerName: string | null | undefined): string | null {
  if (bannerName == null) return null;
  const fix = BANNER_FIXES.find((f) => f.heroName === heroName && f.from === bannerName);
  return fix ? fix.to : bannerName;
}

export interface BannerMismatch {
  readonly heroName: string;
  readonly cardName: string;
  readonly bannerName: string;
}

/**
 * Карты, чей банер (не 'Any') не принадлежит ни герою, ни его помощникам.
 * Имена бойцов — как их создаёт game-initialization: Hero.name и
 * Hero.sidekicks[].name (пустое имя помощника в игре не матчит банер).
 */
export function findBannerMismatches(
  hero: { readonly name: string; readonly sidekicks?: readonly { readonly name?: string | null }[] },
  cards: readonly { readonly name: string; readonly bannerName?: string | null }[],
): BannerMismatch[] {
  const fighters = [hero.name, ...(hero.sidekicks ?? []).map((s) => s.name ?? '')]
    .filter((name) => name.trim().length > 0)
    .map((name) => ({ name }));
  return cards
    .filter((card) => {
      const banner = card.bannerName?.trim();
      if (!banner || banner.toLowerCase() === 'any') return false;
      return !fighters.some((f) => bannerAllows(banner, f));
    })
    .map((card) => ({ heroName: hero.name, cardName: card.name, bannerName: card.bannerName!.trim() }));
}
