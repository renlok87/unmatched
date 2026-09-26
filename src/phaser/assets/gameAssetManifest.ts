export interface PhaserImageAsset {
  key: string;
  path: string;
}

export const HERO_ASSET_IDS = ['ms-marvel', 'daredevil'] as const;

export const HERO_IMAGE_ASSETS: PhaserImageAsset[] = HERO_ASSET_IDS.flatMap(heroId => [
  { key: `hero-mini-${heroId}`, path: `/assets/heroes/${heroId}/mini.webp` },
  { key: `hero-avatar-${heroId}`, path: `/assets/heroes/${heroId}/avatar.webp` },
  { key: `hero-cover-${heroId}`, path: `/assets/heroes/${heroId}/card-cover.webp` },
]);

export const HUD_IMAGE_ASSETS: PhaserImageAsset[] = [
  { key: 'hud-player-panel-local', path: '/assets/ui/hud/player-panel-local.png' },
  { key: 'hud-player-panel-opponent', path: '/assets/ui/hud/player-panel-opponent.png' },
  { key: 'hud-turn-phase-pill', path: '/assets/ui/hud/turn-phase-pill.png' },
  { key: 'hud-selected-card-panel', path: '/assets/ui/hud/selected-card-panel.png' },
  { key: 'hud-mobile-bottom-sheet', path: '/assets/ui/hud/mobile-bottom-sheet.png' },
  { key: 'hud-hand-tray', path: '/assets/ui/hud/hand-tray.png' },
  { key: 'hud-hand-tray-mobile', path: '/assets/ui/hud/hand-tray-mobile.png' },
  { key: 'hud-deck-slot', path: '/assets/ui/hud/deck-slot.png' },
  { key: 'hud-discard-slot', path: '/assets/ui/hud/discard-slot.png' },
  { key: 'hud-hidden-card-back', path: '/assets/ui/hud/hidden-card-back.png' },
  { key: 'hud-board-vignette', path: '/assets/ui/hud/board-vignette.png' },
  { key: 'hud-board-frame-6x4', path: '/assets/ui/hud/board-frame-6x4.png' },
  { key: 'hud-zone-legend-chip', path: '/assets/ui/hud/zone-legend-chip.png' },
  { key: 'hud-status-badges', path: '/assets/ui/hud/status-badges.png' },
  { key: 'hud-action-buttons', path: '/assets/ui/hud/action-buttons.png' },
];

export const EFFECT_IMAGE_ASSETS: PhaserImageAsset[] = [
  { key: 'fx-selection-ring', path: '/assets/ui/effects/selection-ring.png' },
  { key: 'fx-move-highlight', path: '/assets/ui/effects/move-highlight.png' },
  { key: 'fx-attack-highlight', path: '/assets/ui/effects/attack-highlight.png' },
  { key: 'fx-defense-shield', path: '/assets/ui/effects/defense-shield.png' },
  { key: 'fx-hit-spark-strip', path: '/assets/ui/effects/hit-spark-strip.png' },
  { key: 'fx-card-play-flash-strip', path: '/assets/ui/effects/card-play-flash-strip.png' },
];

export const BOARD_IMAGE_ASSETS: PhaserImageAsset[] = [
  { key: 'board-cobble-city', path: '/assets/boards/hells-kitchen.webp' },
];

const CARD_IMAGE_BY_HERO_AND_ID: Record<string, PhaserImageAsset> = {
  'ms-marvel:big-wind-up': {
    key: 'card-ms-marvel-big-wind-up',
    path: '/assets/decks/ms-marvel/big-wind-up.webp',
  },
  'ms-marvel:easy-peasy': {
    key: 'card-ms-marvel-easy-peasy',
    path: '/assets/decks/ms-marvel/easy-peasy.webp',
  },
  'ms-marvel:embiggen': {
    key: 'card-ms-marvel-embiggen',
    path: '/assets/decks/ms-marvel/embiggen.webp',
  },
  'ms-marvel:fangirl': {
    key: 'card-ms-marvel-fangirl',
    path: '/assets/decks/ms-marvel/fangirl.webp',
  },
  'ms-marvel:feint': {
    key: 'card-ms-marvel-feint',
    path: '/assets/decks/ms-marvel/feint.webp',
  },
  'ms-marvel:friends-and-family': {
    key: 'card-ms-marvel-friends-and-family',
    path: '/assets/decks/ms-marvel/friends-and-family.webp',
  },
  'ms-marvel:gyro-and-fries': {
    key: 'card-ms-marvel-gyro-and-fries',
    path: '/assets/decks/ms-marvel/gyro-and-fries.webp',
  },
  'ms-marvel:im-not-touching-you': {
    key: 'card-ms-marvel-im-not-touching-you',
    path: '/assets/decks/ms-marvel/im-not-touching-you.webp',
  },
  'ms-marvel:momentous-shift': {
    key: 'card-ms-marvel-momentous-shift',
    path: '/assets/decks/ms-marvel/momentous-shift.webp',
  },
  'ms-marvel:shrink-shrink-shrink': {
    key: 'card-ms-marvel-shrink-shrink-shrink',
    path: '/assets/decks/ms-marvel/shrink-shrink-shrink.webp',
  },
  'ms-marvel:slingshot': {
    key: 'card-ms-marvel-slingshot',
    path: '/assets/decks/ms-marvel/slingshot.webp',
  },
  'daredevil:breather': {
    key: 'card-daredevil-breather',
    path: '/assets/decks/daredevil/breather.webp',
  },
  'daredevil:devil-of-hells-kitchen': {
    key: 'card-daredevil-devil-of-hells-kitchen',
    path: '/assets/decks/daredevil/devil-of-hells-kitchen.webp',
  },
  'daredevil:feint': {
    key: 'card-daredevil-feint',
    path: '/assets/decks/daredevil/feint.webp',
  },
  'daredevil:grappling-hook': {
    key: 'card-daredevil-grappling-hook',
    path: '/assets/decks/daredevil/grappling-hook.webp',
  },
  'daredevil:man-without-fear': {
    key: 'card-daredevil-man-without-fear',
    path: '/assets/decks/daredevil/man-without-fear.webp',
  },
  'daredevil:son-of-a-boxer': {
    key: 'card-daredevil-son-of-a-boxer',
    path: '/assets/decks/daredevil/son-of-a-boxer.webp',
  },
  'daredevil:take-a-knee': {
    key: 'card-daredevil-take-a-knee',
    path: '/assets/decks/daredevil/take-a-knee.webp',
  },
  'daredevil:through-adversity': {
    key: 'card-daredevil-through-adversity',
    path: '/assets/decks/daredevil/through-adversity.webp',
  },
};

export const CARD_IMAGE_ASSETS: PhaserImageAsset[] = Object.values(CARD_IMAGE_BY_HERO_AND_ID);

export const GAME_IMAGE_ASSETS: PhaserImageAsset[] = [
  ...HERO_IMAGE_ASSETS,
  ...HUD_IMAGE_ASSETS,
  ...EFFECT_IMAGE_ASSETS,
  ...BOARD_IMAGE_ASSETS,
  ...CARD_IMAGE_ASSETS,
];

export function getCardArtAsset(heroId: string | undefined, cardId: string): PhaserImageAsset | undefined {
  if (!heroId) return undefined;
  return CARD_IMAGE_BY_HERO_AND_ID[`${heroId}:${cardId}`];
}

export function getBoardArtAsset(boardId: string | undefined): PhaserImageAsset | undefined {
  if (!boardId) return undefined;
  return BOARD_IMAGE_ASSETS.find(asset => asset.key === `board-${boardId}`);
}
