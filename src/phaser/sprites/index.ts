// ============================================================
// СПРАЙТЫ - Экспорт всех классов спрайтов
// ============================================================

// Основной спрайт бойца (из entities/)
export { FighterSprite as BaseFighterSprite, type FighterDisplayConfig, type FighterEvents } from '../entities/FighterSprite';

// Расширенный спрайт бойца с дополнительными анимациями (из sprites/)
export { FighterSprite, FighterAnimationState } from './FighterSprite';
export type { FighterSpriteConfig } from './FighterSprite';

// Другие спрайты
export { CardSprite } from './CardSprite';
