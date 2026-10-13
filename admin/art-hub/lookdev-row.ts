/**
 * Row facts of a look-dev figure, shared by the art-hub table, the /__art-hub/hero(es) endpoints
 * and the admin hero page. Pure (no node imports): bundled into the admin client too.
 */
import type { FileRef, LookdevHeroView } from './types';

const isFront = (f: FileRef) => /front/i.test(f.path.split('/').pop() ?? '');

/** Preview: the selected design front, then package candidates, then hero-quality concepts (front views first). */
export function lookdevThumb(hero: LookdevHeroView): FileRef | undefined {
  const pkg = hero.conceptPackage;
  const concepts = [...hero.concepts].sort((a, b) => Number(isFront(b)) - Number(isFront(a)));
  return [pkg?.designFront, ...(pkg?.candidates.map((c) => c.file) ?? []), ...concepts].find((f) => f?.servable);
}

export function lookdevStage(hero: LookdevHeroView): string {
  return hero.conceptPackage ? hero.conceptPackage.stage : hero.ueSheets.length ? 'look-dev UE' : 'look-dev';
}

/** Stable-pass band 8.0–8.4 of the skill: a second acceptor of the other profile is required. */
export function needsSecondAcceptor(hero: LookdevHeroView): boolean {
  const last = hero.acceptance[0];
  return last?.verdict === 'pass' && last.score !== undefined && last.score < 8.5;
}
