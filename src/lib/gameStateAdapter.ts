/**
 * Game State Adapter
 *
 * Серверный wire-формат GameState → локальный формат (src/core/models/types.ts),
 * который потребляет Phaser GameScene. Сервер — единственный источник истины;
 * адаптер ничего не вычисляет по правилам игры, только переформатирует.
 *
 * Два wire-представления (оба per-user отфильтрованы бэком):
 * 1. Query gameState / gameplay-мутации → state: string — ОДНА JSON-строка
 *    полного состояния { gameId, sequenceNumber, phase, turnCount,
 *    currentTurnPlayerId, players[], fighters[], decks{}, discardPiles{},
 *    handZones{}, boardState{}, metadata{} }.
 * 2. Подписка gameStateUpdated → те же данные, но players/fighters/handZones/
 *    boardState/metadata — ПЯТЬ отдельных JSON-строк, и БЕЗ decks/discardPiles
 *    (мержатся из предыдущего снапшота в remoteGameStore).
 *
 * Контракт для GameScene: ЛОКАЛЬНЫЙ игрок всегда players[0] (сцена рисует
 * index 0 нижней панелью и его руку).
 */

import {
  CardType,
  FighterType,
  GamePhase,
  type BoardDefinition,
  type CardInstance,
  type Fighter,
  type GameState as LocalGameState,
  type Player,
} from '@/core/models/types';

// ---------------------------------------------------------------------------
// Wire-типы (подмножество, которое реально читаем)
// ---------------------------------------------------------------------------

export interface WirePosition {
  x: number;
  y: number;
}

export interface WireFighter {
  id: string;
  ownerId: string;
  heroId: string;
  heroSlug?: string;
  name: string;
  type: 'HERO' | 'MINION' | 'HUGE';
  health: number;
  maxHealth: number;
  position: WirePosition;
  effects: Array<{ type: string; duration?: string }>;
  movement?: number;
  attackType?: 'melee' | 'ranged';
  isDefeated?: boolean;
}

export interface WireCard {
  id: string;
  cardId: string;
  name: string;
  nameEn?: string;
  nameRu?: string;
  cardType: 'ATTACK' | 'DEFENSE' | 'SCHEME' | 'VERSATILE' | 'MANEUVER' | 'UNIVERSAL';
  attackValue?: number;
  defenseValue?: number;
  boostValue?: number;
  text?: string;
  bannerName?: string;
  isVisible?: boolean;
}

export interface WirePlayer {
  userId: string;
  heroId: string;
  health: number;
  maxHealth: number;
  fighterIds: string[];
  isAlive: boolean;
}

export interface WireCombatInfo {
  attackerId: string; // fighter id!
  defenderId: string; // userId защитника!
  targetFighterId?: string;
  attackerCardId: string;
  defenderCardId?: string;
  attackValue: number;
  defenseValue: number;
}

export interface WireGameState {
  gameId: string;
  sequenceNumber: number;
  phase: string;
  turnCount: number;
  currentTurnPlayerId: string;
  players: WirePlayer[];
  fighters: WireFighter[];
  decks?: Record<string, { cards?: WireCard[]; drawPile?: WireCard[] }>;
  discardPiles?: Record<string, WireCard[]>;
  handZones: Record<string, { cards: WireCard[]; maxSize: number }>;
  boardState: {
    width: number;
    height: number;
    cells?: Array<Array<{ type?: string; zone?: string }>>;
    doors?: Record<string, boolean>;
  };
  metadata: {
    actionsRemaining?: number;
    combatInfo?: WireCombatInfo;
    winnerId?: string;
    passCount?: number;
    pendingEffects?: WirePendingEffect[];
    /** STANCE: текущая стойка героя по userId (id из AbilityConfig.stances) */
    heroStances?: Record<string, string>;
  };
}

/**
 * Отложенный эффект карты:
 * - MOVE/PLACE (C2): выбор бойца/клетки;
 * - CHOOSE_ONE (v3): выбор одного из вариантов (options) по индексу.
 */
export interface WirePendingEffect {
  id: string;
  type: 'MOVE' | 'PLACE' | 'CHOOSE_ONE';
  playerId: string;
  value?: number;
  fighterName?: string;
  targetsOpponent?: boolean;
  text?: string;
  /** CHOOSE_ONE: варианты выбора (индекс + текст) */
  options?: Array<{ index: number; label: string }>;
  /** CHOOSE_ONE: сколько опций выбрать (default 1) */
  chooseCount?: number;
}

/** Справочники для артов/имён (контентные запросы, кэш в remoteGameStore) */
export interface AdapterRefs {
  /** username по userId (из GetGame.players) */
  usernames: Record<string, string>;
  /** контентный герой по ИМЕНИ (hero(id=name)): карты с артами */
  heroAssets: Record<
    string,
    {
      avatarUrl?: string;
      cards: Array<{ id: string; title: string; imageUrl?: string; imageUrlRu?: string }>;
    }
  >;
  /** определение доски из контентного Boards (зоны/арт) */
  board: BoardDefinition | null;
  /**
   * STANCE: опции стоек по heroSlug (id+label+isDefault), из query heroStances.
   * Пусто/нет ключа — у героя нет стоек (HUD ничего не рендерит).
   */
  stanceOptions: Record<string, StanceOption[]>;
}

/** STANCE: одна опция стойки для HUD (из query heroStances) */
export interface StanceOption {
  id: string;
  label: string;
  isDefault: boolean;
}

// ---------------------------------------------------------------------------
// Парсинг wire
// ---------------------------------------------------------------------------

/** Ответ query gameState / gameplay-мутаций: state — одна JSON-строка */
export function parseWireState(stateJson: string): WireGameState {
  return JSON.parse(stateJson) as WireGameState;
}

/** Событие подписки gameStateUpdated: 5 отдельных JSON-полей */
export function parseSubscriptionState(payload: {
  gameId: string;
  sequenceNumber: number;
  phase: string;
  turnCount: number;
  currentTurnPlayerId: string;
  players: string;
  fighters: string;
  handZones: string;
  boardState: string;
  metadata: string;
}): WireGameState {
  return {
    gameId: payload.gameId,
    sequenceNumber: payload.sequenceNumber,
    phase: payload.phase,
    turnCount: payload.turnCount,
    currentTurnPlayerId: payload.currentTurnPlayerId,
    players: JSON.parse(payload.players),
    fighters: JSON.parse(payload.fighters),
    handZones: JSON.parse(payload.handZones),
    boardState: JSON.parse(payload.boardState),
    metadata: JSON.parse(payload.metadata),
    // decks/discardPiles в подписке отсутствуют — merge в remoteGameStore
  };
}

// ---------------------------------------------------------------------------
// Адаптация wire → локальный формат
// ---------------------------------------------------------------------------

const PHASE_MAP: Record<string, GamePhase> = {
  SETUP: GamePhase.SETUP,
  TURN_START: GamePhase.START_OF_TURN,
  ACTION_MANEUVER: GamePhase.ACTION_SELECTION,
  ACTION_ATTACK: GamePhase.ACTION_SELECTION,
  COMBAT: GamePhase.COMBAT_DEFENSE,
  COMBAT_RESOLVE: GamePhase.RESOLUTION,
  TURN_END: GamePhase.END_OF_TURN,
  GAME_OVER: GamePhase.GAME_OVER,
};

const CARD_TYPE_MAP: Record<string, CardType> = {
  ATTACK: CardType.ATTACK,
  DEFENSE: CardType.DEFENSE,
  SCHEME: CardType.SCHEME,
  VERSATILE: CardType.VERSATILE,
  // MANEUVER — карта движения; локальный enum без него, ближайшее — scheme
  MANEUVER: CardType.SCHEME,
  UNIVERSAL: CardType.VERSATILE,
};

export function adaptToLocal(
  wire: WireGameState,
  refs: AdapterRefs,
  localUserId: string,
): LocalGameState {
  // Имя героя игрока — из его HERO-бойца (контентные арты ключуются именем)
  const heroNameOf = (userId: string): string | undefined =>
    wire.fighters.find((f) => f.ownerId === userId && f.type === 'HERO')?.name;

  const toCardInstance = (card: WireCard, ownerId: string, idx: number): CardInstance => {
    const heroName = heroNameOf(ownerId);
    const assets = heroName ? refs.heroAssets[heroName] : undefined;
    const art = assets?.cards.find(
      (c) => c.id === card.cardId || c.title === (card.nameEn ?? card.name),
    );
    const hidden = card.isVisible === false && card.name === '???';
    return {
      id: card.id,
      ownerId,
      instanceIndex: idx,
      definition: {
        id: card.cardId,
        title: hidden ? '???' : card.nameRu || card.name,
        type: CARD_TYPE_MAP[card.cardType] ?? CardType.VERSATILE,
        value: card.attackValue ?? card.defenseValue ?? 0,
        boost: card.boostValue ?? 0,
        quantity: 1,
        effects: card.text
          ? [{ id: `${card.cardId}-text`, timing: 'after_combat' as never, text: card.text }]
          : [],
        characterName: card.bannerName ?? '',
        imageUrl: hidden ? undefined : art?.imageUrl,
        imageUrlRu: hidden ? undefined : art?.imageUrlRu,
      },
    };
  };

  const toFighter = (f: WireFighter): Fighter => {
    const heroName = heroNameOf(f.ownerId);
    const assets = heroName ? refs.heroAssets[heroName] : undefined;
    return {
      id: f.id,
      definitionId: f.heroSlug ?? f.heroId,
      type: f.type === 'HERO' ? FighterType.HERO : FighterType.SIDEKICK,
      health: f.health,
      maxHealth: f.maxHealth,
      position: { x: f.position.x, y: f.position.y },
      ownerId: f.ownerId,
      isDefeated: f.isDefeated ?? f.health <= 0,
      avatarUrl: f.type === 'HERO' ? assets?.avatarUrl : undefined,
    };
  };

  const toPlayer = (wp: WirePlayer): Player => {
    const handCards = wire.handZones[wp.userId]?.cards ?? [];
    const deckCards = wire.decks?.[wp.userId]?.drawPile ?? [];
    const discardCards = wire.discardPiles?.[wp.userId] ?? [];
    const isCurrent = wire.currentTurnPlayerId === wp.userId;
    return {
      id: wp.userId,
      name: refs.usernames[wp.userId] ?? heroNameOf(wp.userId) ?? wp.userId.slice(0, 8),
      fighters: wire.fighters.filter((f) => f.ownerId === wp.userId).map(toFighter),
      hand: handCards.map((c, i) => toCardInstance(c, wp.userId, i)),
      deck: deckCards.map((c, i) => toCardInstance(c, wp.userId, i)),
      discardPile: discardCards.map((c, i) => toCardInstance(c, wp.userId, i)),
      actionsRemaining: isCurrent ? (wire.metadata.actionsRemaining ?? 0) : 0,
      hasPassed: false,
      handLimit: wire.handZones[wp.userId]?.maxSize ?? 7,
    };
  };

  // КОНТРАКТ: локальный игрок всегда players[0]
  const sortedWirePlayers = [...wire.players].sort((a, b) =>
    a.userId === localUserId ? -1 : b.userId === localUserId ? 1 : 0,
  );
  const players = sortedWirePlayers.map(toPlayer);

  // Доска: контентное определение (зоны/арт); fallback — из wire-геометрии
  const definition: BoardDefinition =
    refs.board ?? {
      id: wire.gameId,
      name: 'Board',
      width: wire.boardState.width,
      height: wire.boardState.height,
      recommendedPlayers: 2,
      spaces: (wire.boardState.cells ?? []).flatMap((row, y) =>
        row.map((cell, x) => ({
          position: { x, y },
          zones: cell?.zone ? ([cell.zone] as never) : [],
          isObstacle: cell?.type === 'obstacle',
        })),
      ),
    };

  const fightersMap = new Map<string, { x: number; y: number }>();
  wire.fighters.forEach((f) => fightersMap.set(f.id, { x: f.position.x, y: f.position.y }));

  // combatState для UI-панелей (сцене не критичен)
  const ci = wire.metadata.combatInfo;
  const attackerFighter = ci ? wire.fighters.find((f) => f.id === ci.attackerId) : undefined;
  const targetFighter = ci
    ? wire.fighters.find(
        (f) => f.id === (ci.targetFighterId ?? ''),
      ) ?? wire.fighters.find((f) => f.ownerId === ci?.defenderId)
    : undefined;

  return {
    id: wire.gameId,
    players,
    board: { definition, fighters: fightersMap },
    currentTurn: {
      currentPlayerId: wire.currentTurnPlayerId,
      cardsDrawnThisTurn: 0,
    },
    phase: PHASE_MAP[wire.phase] ?? GamePhase.ACTION_SELECTION,
    combatState:
      ci && attackerFighter && targetFighter
        ? {
            attacker: toFighter(attackerFighter),
            defender: toFighter(targetFighter),
            attackCard: null as never, // карта атаки скрыта/в сбросе — UI показывает значения
            attackValue: ci.attackValue,
            defenseValue: ci.defenseValue,
            attackBoosts: 0,
            defenseBoosts: 0,
            effectsToProcess: [],
            resolutionComplete: false,
          }
        : null,
    winner: wire.metadata.winnerId ?? null,
    turnCount: wire.turnCount,
  };
}
