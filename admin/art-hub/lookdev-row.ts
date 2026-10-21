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

const MODEL_VERDICT: Record<string, string> = {
  pass: 'принята',
  rework_blender: 'доработка в Blender',
  rework_stage_2: 'доработка этапа 2',
  return_to_stage_2: 'возврат на этап 2',
  escalate_user: 'эскалация пользователю',
};

/**
 * Stage of the figure. Concept packages give only stages 1a…1c; once acceptance cards of the model (stages 3-5) or of the
 * animation clips (7b) exist, the newest facts win: the latest model verdict, or the clip verdicts. Nothing is invented:
 * a figure without model/anim cards keeps its concept stage.
 */
export function lookdevStage(hero: LookdevHeroView): string {
  const anim = hero.acceptance.filter((c) => c.kind === 'anim');
  if (anim.length) return anim.every((c) => c.verdict === 'pass') ? 'анимация: принята' : 'анимация: доработка';
  const model = hero.acceptance.find((c) => c.kind === 'model');
  if (model) return `модель ${model.cycle ?? ''}: ${MODEL_VERDICT[model.verdict ?? ''] ?? model.verdict ?? 'без вердикта'}`.replace('модель : ', 'модель: ');
  return hero.conceptPackage ? hero.conceptPackage.stage : hero.ueSheets.length ? 'look-dev UE' : 'look-dev';
}

/** Stable-pass band 8.0–8.4 of the skill: a second acceptor of the other profile is required. */
export function needsSecondAcceptor(hero: LookdevHeroView): boolean {
  const last = hero.acceptance[0];
  return last?.verdict === 'pass' && last.score !== undefined && last.score < 8.5;
}
