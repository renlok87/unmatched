/**
 * Матчинг имени бойца против имени из текста карты/способности.
 *  - «Harpy 2» (клон сайдкика) матчит «Harpy»;
 *  - «Harpies» (имя сайдкика в каталоге) матчит «Harpy» (единственное число
 *    из текста карты) — нормализация множественного числа: ies→y, s/es→;
 *  - регистронезависимо.
 */
export function fighterNameMatches(fighterName: string, effectName: string): boolean {
  const stem = (s: string): string => {
    const base = s.replace(/\s+\d+$/, '').trim().toLowerCase();
    if (/ies$/.test(base)) return base.replace(/ies$/, 'y');
    if (/es$/.test(base)) return base.replace(/es$/, '');
    if (/s$/.test(base)) return base.replace(/s$/, '');
    return base;
  };
  const f = fighterName.trim().toLowerCase();
  const e = effectName.trim().toLowerCase();
  const fBase = fighterName.replace(/\s+\d+$/, '').trim().toLowerCase();
  return fBase === e || f === e || stem(fighterName) === stem(effectName);
}
