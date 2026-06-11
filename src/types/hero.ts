export interface Hero {
  id: string;
  name: string;
  health: number;
  movement: number;
  set: string;
  thumbnailUrl: string;
  imageUrl: string;
  description?: string;
  abilities: SpecialAbility[];
  fighterTypes: FighterType[];
}

export interface SpecialAbility {
  id: string;
  name: string;
  description: string;
  timing: EffectTiming;
}

export type FighterType = 'hero' | 'sidekick';

export type EffectTiming =
  | 'IMMEDIATELY'
  | 'DURING_COMBAT'
  | 'AFTER_COMBAT'
  | 'START_OF_TURN'
  | 'END_OF_TURN';

export interface HeroStats {
  heroId: string;
  gamesPlayed: number;
  wins: number;
  winRate: number;
  avgDamageDealt: number;
}

export interface HeroFilters {
  set?: string | null;
  search?: string | null;
  fighterType?: FighterType | null;
}