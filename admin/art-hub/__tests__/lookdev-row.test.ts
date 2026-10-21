import { describe, expect, it } from 'vitest';
import { lookdevStage } from '../lookdev-row';
import type { AcceptanceCardView, LookdevHeroView } from '../types';

const card = (kind: string, verdict: string, cycle = 'r1'): AcceptanceCardView => ({ kind, verdict, cycle }) as AcceptanceCardView;
const hero = (acceptance: AcceptanceCardView[], stage?: string, ue = 0): LookdevHeroView =>
  ({ acceptance, ueSheets: new Array(ue).fill({}), conceptPackage: stage ? { stage } : undefined }) as unknown as LookdevHeroView;

describe('lookdevStage', () => {
  it('keeps the concept stage without model/anim cards', () => {
    expect(lookdevStage(hero([card('concept', 'pass')], '1c-приёмка'))).toBe('1c-приёмка');
    expect(lookdevStage(hero([], undefined, 1))).toBe('look-dev UE');
    expect(lookdevStage(hero([]))).toBe('look-dev');
  });
  it('shows the newest model verdict as is', () => {
    expect(lookdevStage(hero([card('model', 'escalate_user', 'r3'), card('model', 'rework_blender', 'r2'), card('concept', 'pass')], '1c-приёмка'))).toBe('модель r3: эскалация пользователю');
    expect(lookdevStage(hero([card('model', 'pass', 'r3')], '1c-приёмка'))).toBe('модель r3: принята');
    expect(lookdevStage(hero([card('model', 'weird')], '1c'))).toBe('модель r1: weird');
  });
  it('anim cards (7b) win over model cards', () => {
    const a = [card('anim', 'pass'), card('anim', 'pass'), card('model', 'pass', 'r3')];
    expect(lookdevStage(hero(a, '1c-приёмка'))).toBe('анимация: принята');
    expect(lookdevStage(hero([card('anim', 'pass'), card('anim', 'rework')], '1c'))).toBe('анимация: доработка');
  });
});
