import { Injectable } from '@nestjs/common';
import type { GameState, Fighter, Card, PendingEffect, Position } from '../models';
import { CardType, GamePhase, getActionsRemaining, getFighterMovement } from '../models';
import { AdjacencyService } from '../engine/adjacency.service';
import { bannerAllows } from '../validators/game-rules.validator';

/**
 * Решение ИИ-оппонента (VS_AI). Чистая greedy-эвристика без сайд-эффектов:
 * по GameState + id бота возвращает следующее действие либо null («боту нечего
 * делать — ход за человеком»). Исполняет действие AiTurnService.
 *
 * Сначала завершает серверные выборы. Манёвр начинается добором; путь выбирается
 * по сохранённому состоянию после добора и содержит все соседние шаги BFS.
 * Если двигаться некуда, завершает манёвр без движения.
 */
export type AiAction =
  | { kind: 'resolveChoose'; effectId: string; optionIndex: number }
  | { kind: 'resolveMove'; effectId: string; fighterId: string; x: number; y: number }
  | { kind: 'declinePending'; effectId: string }
  | { kind: 'defense'; cardId: string }
  | { kind: 'resolveCombat' }
  | { kind: 'attack'; attackerId: string; targetId: string; cardId: string }
  | { kind: 'beginManeuver'; expectedSequenceNumber: number }
  | { kind: 'maneuver'; maneuverId: string; moves: Array<{ fighterId: string; path: Position[] }>; boostCardId?: string }
  | { kind: 'discardToLimit'; pendingId: string; cardIds: string[] }
  | { kind: 'endTurn' };

@Injectable()
export class AiDecisionService {
  constructor(private readonly adjacency: AdjacencyService) {}

  decide(state: GameState, aiUserId: string): AiAction | null {
    if (state.phase === GamePhase.GAME_OVER) return null;

    const discard = state.metadata.pendingHandDiscard;
    if (discard) {
      if (discard.playerId !== aiUserId) return null;
      return { kind: 'discardToLimit', pendingId: discard.id,
        cardIds: this.hand(state, aiUserId).slice(0, discard.count).map(card => card.id) };
    }
    const maneuver = state.metadata.pendingManeuver;
    if (maneuver) {
      if (maneuver.playerId !== aiUserId) return null;
      const hero = this.aiHero(state, aiUserId);
      const enemy = hero ? this.nearestEnemy(state, aiUserId, hero) : null;
      const path = hero && enemy && !hero.effects.some(effect => effect.type === 'immobilized')
        ? this.pathToward(state, hero, enemy, getFighterMovement(hero)) : [];
      return { kind: 'maneuver', maneuverId: maneuver.id,
        moves: hero && path.length ? [{ fighterId: hero.id, path }] : [] };
    }

    // 1. GD-018: голова ГЛОБАЛЬНОЙ очереди выборов — строго по порядку;
    // чужой выбор бот не скипает (null = ждём человека). Свой optional-выбор
    // без полезного решения бот отклоняет; mandatory должен быть резолвнут.
    const queue = state.metadata.pendingEffects ?? [];
    if (queue.length > 0) {
      const head = queue[0];
      if (head.playerId !== aiUserId) return null;
      const dec = this.decidePending(state, aiUserId, head);
      if (dec) return dec;
      if (head.optional) return { kind: 'declinePending', effectId: head.id };
      return null;
    }

    // 2. Бой
    if (state.phase === GamePhase.COMBAT || state.phase === GamePhase.COMBAT_RESOLVE) {
      const ci = state.metadata.combatInfo as any;
      if (!ci) return null;
      if (state.phase === GamePhase.COMBAT_RESOLVE) return { kind: 'resolveCombat' };
      // бот-защитник: один раз играем лучшую защиту, затем резолвим
      if (ci.defenderId === aiUserId) {
        if (ci.defenderCardId) return { kind: 'resolveCombat' };
        const def = this.bestDefenseCard(state, aiUserId);
        return def ? { kind: 'defense', cardId: def.id } : { kind: 'resolveCombat' };
      }
      // бот-атакующий: резолвим, как только человек сыграл защиту (иначе ждём)
      const attackerFighter = state.fighters.find((f) => f.id === ci.attackerId);
      if (attackerFighter?.ownerId === aiUserId && ci.defenderCardId) {
        return { kind: 'resolveCombat' };
      }
      return null;
    }

    // 3. Ход бота
    if (state.currentTurnPlayerId !== aiUserId) return null;
    if (state.phase !== GamePhase.ACTION_MANEUVER && state.phase !== GamePhase.ACTION_ATTACK) return null;
    if (getActionsRemaining(state) <= 0) return { kind: 'endTurn' };

    const heroF = this.aiHero(state, aiUserId);
    if (!heroF) return null;
    const enemy = this.nearestEnemy(state, aiUserId, heroF);
    if (!enemy) return null;

    // Атака при досягаемости: melee — смежно, ranged — смежно или одна зона
    const adjacent = this.manhattan(heroF.position, enemy.position) === 1;
    const reach = adjacent || (heroF.attackType === 'ranged' && this.shareZone(state, heroF, enemy));
    if (reach) {
      const atk = this.bestAttackCard(state, aiUserId, heroF);
      if (atk) return { kind: 'attack', attackerId: heroF.id, targetId: enemy.id, cardId: atk.id };
    }

    return { kind: 'beginManeuver', expectedSequenceNumber: state.sequenceNumber };
  }

  // ---------- Отложенные эффекты ----------

  private decidePending(state: GameState, aiUserId: string, p: PendingEffect): AiAction | null {
    if (p.type === 'CHOOSE_ONE') {
      const opts = p.options ?? [];
      if (opts.length === 0) return null;
      // выгодная опция: HEAL > DRAW_CARD > GAIN_ACTION > первая
      const rank = (i: number): number => {
        const effs = p.optionEffects?.[i] ?? [];
        if (effs.some((e) => e.type === 'HEAL')) return 3;
        if (effs.some((e) => e.type === 'DRAW_CARD')) return 2;
        if (effs.some((e) => e.type === 'GAIN_ACTION')) return 1;
        return 0;
      };
      let best = opts[0];
      for (const o of opts) if (rank(o.index) > rank(best.index)) best = o;
      return { kind: 'resolveChoose', effectId: p.id, optionIndex: best.index };
    }

    // MOVE/PLACE: выбираем бойца и валидную клетку (шаг к врагу, иначе на месте)
    const ownHero = this.aiHero(state, aiUserId);
    const moveOpponent = p.targetsOpponent === true;
    const fighter = moveOpponent
      ? this.nearestEnemy(state, aiUserId, ownHero ?? state.fighters[0])
      : ownHero ?? this.living(state).find((f) => f.ownerId === aiUserId);
    if (!fighter) return null;

    if (moveOpponent) {
      // двигаем врага — на месте (нейтрально), лишь бы очистить pending
      return { kind: 'resolveMove', effectId: p.id, fighterId: fighter.id, x: fighter.position.x, y: fighter.position.y };
    }
    const enemy = this.nearestEnemy(state, aiUserId, fighter);
    // не дальше pending.value (если задан); иначе — полный movement бойца
    const maxCost = typeof p.value === 'number' && p.value > 0 ? p.value : getFighterMovement(fighter);
    const step = enemy ? this.stepToward(state, fighter, enemy, maxCost) : null;
    if (step) {
      return { kind: 'resolveMove', effectId: p.id, fighterId: fighter.id, x: step.x, y: step.y };
    }
    // Улучшающего шага нет (враг смежен / бот заперт). Optional-эфект отклоняем
    // (null → declinePending в decide); mandatory резолвим нулевым шагом —
    // «up to N» включает 0, очередь не strand'ится.
    if (p.optional) return null;
    return {
      kind: 'resolveMove', effectId: p.id, fighterId: fighter.id,
      x: fighter.position.x, y: fighter.position.y,
    };
  }

  // ---------- Карты ----------

  private hand(state: GameState, uid: string): readonly Card[] {
    return state.handZones[uid]?.cards ?? [];
  }

  private bannerOk(card: Card, fighter: Fighter): boolean {
    if (!card.bannerName || card.bannerName === 'Any') return true;
    return bannerAllows(card.bannerName, fighter);
  }

  private bestAttackCard(state: GameState, uid: string, fighter: Fighter): Card | null {
    const cards = this.hand(state, uid).filter(
      (c) => (c.cardType === CardType.ATTACK || c.cardType === CardType.VERSATILE) && this.bannerOk(c, fighter),
    );
    // При равном attackValue предпочитаем ATTACK над VERSATILE — не тратим
    // универсальную карту, когда есть чистая атака той же силы.
    return cards.reduce<Card | null>((best, c) => {
      if (best === null) return c;
      const cv = c.attackValue ?? 0;
      const bv = best.attackValue ?? 0;
      if (cv > bv) return c;
      if (cv === bv && c.cardType === CardType.ATTACK && best.cardType !== CardType.ATTACK) return c;
      return best;
    }, null);
  }

  private bestDefenseCard(state: GameState, uid: string): Card | null {
    const fighter = this.aiHero(state, uid);
    const cards = this.hand(state, uid).filter(
      (c) =>
        (c.cardType === CardType.DEFENSE || c.cardType === CardType.VERSATILE) &&
        (c.defenseValue ?? 0) > 0 &&
        (!fighter || this.bannerOk(c, fighter)),
    );
    // При равном defenseValue предпочитаем DEFENSE над VERSATILE — не тратим
    // универсальную карту, когда есть чистая защита той же силы.
    return cards.reduce<Card | null>((best, c) => {
      if (best === null) return c;
      const cv = c.defenseValue ?? 0;
      const bv = best.defenseValue ?? 0;
      if (cv > bv) return c;
      if (cv === bv && c.cardType === CardType.DEFENSE && best.cardType !== CardType.DEFENSE) return c;
      return best;
    }, null);
  }

  // ---------- Бойцы / геометрия ----------

  private living(state: GameState): Fighter[] {
    return state.fighters.filter((f) => f.health > 0 && !f.isDefeated);
  }

  private aiHero(state: GameState, uid: string): Fighter | null {
    const mine = this.living(state).filter((f) => f.ownerId === uid);
    return mine.find((f) => f.type === ('HERO' as Fighter['type'])) ?? mine[0] ?? null;
  }

  private nearestEnemy(state: GameState, uid: string, from: Fighter): Fighter | null {
    const enemies = this.living(state).filter((f) => f.ownerId !== uid);
    if (enemies.length === 0) return null;
    const heroes = enemies.filter((f) => f.type === ('HERO' as Fighter['type']));
    const pool = heroes.length > 0 ? heroes : enemies;
    return pool.reduce((a, b) => (this.manhattan(from.position, a.position) <= this.manhattan(from.position, b.position) ? a : b));
  }

  private manhattan(a: { x: number; y: number }, b: { x: number; y: number }): number {
    return Math.abs(a.x - b.x) + Math.abs(a.y - b.y);
  }

  private shareZone(state: GameState, a: Fighter, b: Fighter): boolean {
    return this.adjacency.isInSameZone(state, a.position, b.position);
  }

  /**
   * BFS-путь до maxCost очков, СТРОГО приближающий к врагу по манхэттену.
   * Живые враги блокируют прохождение (blockedPositions), живые союзники
   * проходимы насквозь, но путь не может ЗАКАНЧИВАТЬСЯ на занятой клетке;
   * побеждённые бойцы никого не блокируют (GD-015). Среди достижимых
   * выбираем свободную клетку с минимальным манхэттеном до врага.
   */
  private stepToward(
    state: GameState,
    mine: Fighter,
    enemy: Fighter,
    maxCost: number,
  ): { x: number; y: number } | null {
    const path = this.pathToward(state, mine, enemy, maxCost);
    return path.length ? path[path.length - 1] : null;
  }

  private pathToward(state: GameState, mine: Fighter, enemy: Fighter, maxCost: number): Position[] {
    if (maxCost < 1) return [];

    // Прохождение блокируют только живые ВРАГИ; союзники проходимы насквозь
    const blockedPositions = new Set(
      this.living(state)
        .filter((f) => f.id !== mine.id && f.ownerId !== mine.ownerId)
        .map((f) => `${f.position.x}:${f.position.y}`),
    );
    const livingPositions = new Set(
      this.living(state).map((f) => `${f.position.x}:${f.position.y}`),
    );

    const queue: Array<{ position: Position; path: Position[] }> = [{ position: mine.position, path: [] }];
    const visited = new Set([`${mine.position.x}:${mine.position.y}`]);
    let best: Position[] = [];
    let bestDist = this.manhattan(mine.position, enemy.position);
    for (let index = 0; index < queue.length; index++) {
      const current = queue[index];
      if (current.path.length >= maxCost) continue;
      for (const cell of this.adjacency.getAdjacentCells(state.boardState, current.position)) {
        const key = `${cell.position.x}:${cell.position.y}`;
        if (cell.isBlocked || blockedPositions.has(key) || visited.has(key)) continue;
        visited.add(key);
        const path = [...current.path, cell.position];
        queue.push({ position: cell.position, path });
        const distance = this.manhattan(cell.position, enemy.position);
        // Финал пути — только на свободной клетке (не на живом бойце)
        if (distance < bestDist && !livingPositions.has(key)) {
          bestDist = distance;
          best = path;
        }
      }
    }

    return best;
  }
}
