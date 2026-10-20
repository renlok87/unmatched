/**
 * «You may draw» (RULE-02): необязательный добор как optional CHOOSE_ONE.
 *
 * Опция 0 — отказ (пустые эффекты), опция 1 — добор. Отказ первым, потому что
 * системный фолбэк обязательного CHOOSE_ONE берёт опцию 0, а optional-выбор
 * по таймауту отклоняется (declinePendingEffect). Так ни таймаут, ни офлайн
 * не принуждают к добору с пустой колоды (истощение — 2 урона каждому своему
 * бойцу за недостающую карту).
 *
 * Общий для карт (DRAW_CARD optional) и способностей героев (TurnEffect optional).
 */

import { CardEffect, EffectTiming, EffectType } from '../models/card.model';
import type { Card } from '../models/card.model';
import type { EffectContext, PendingEffect } from '../models/game-state.model';

export const DECLINE_DRAW_LABEL = 'Do not draw';

export function optionalDrawPending(args: {
  readonly id: string;
  readonly playerId: string;
  readonly count: number;
  readonly text: string;
  readonly card?: Card;
  readonly effectContext?: EffectContext;
}): PendingEffect {
  const drawLabel = `Draw ${args.count} card${args.count === 1 ? '' : 's'}`;
  const draw: CardEffect = {
    id: `${args.id}-draw`,
    type: EffectType.DRAW_CARD,
    timing: EffectTiming.AFTER_COMBAT,
    value: args.count,
    text: drawLabel,
  };
  return {
    id: args.id,
    type: 'CHOOSE_ONE',
    playerId: args.playerId,
    chooseCount: 1,
    options: [
      { index: 0, label: DECLINE_DRAW_LABEL },
      { index: 1, label: drawLabel },
    ],
    optionEffects: [[], [draw]],
    ...(args.card ? { card: args.card } : {}),
    ...(args.effectContext ? { effectContext: args.effectContext } : {}),
    optional: true,
    text: args.text,
  };
}
