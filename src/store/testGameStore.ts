import { create } from 'zustand';
import { apolloClient } from '@/lib/apolloClient';
import {
  HeroesDocument,
  HeroDocument,
  BoardsDocument,
  type HeroQuery,
  type HeroesQuery,
  type BoardsQuery,
} from '@/gql/graphql';
import type {
  GameState,
  Player,
  Fighter,
  CardInstance,
  CardDefinition,
  BoardState,
  BoardDefinition,
  Position,
  GamePhase,
} from '@/core/models/types';

// ============================================================
// TYPES FROM API
// ============================================================

interface ApiHero {
  id: string;
  name: string;
  health: number;
  movement: number;
  set: string;
  fighterType?: string;
  sidekickCount?: number;
  sidekickHealth?: number;
  urls?: {
    avatar?: string;
    mini?: string;
    cardCover?: string;
  };
  imageUrl?: string;
  avatarUrl?: string;
}

interface ApiHeroWithCards extends ApiHero {
  abilities?: ApiHeroAbility[];
  cards?: ApiCard[];
}

interface ApiHeroAbility {
  id: string;
  name: string;
  text: string;
  trigger: string;
}

interface ApiCard {
  id: string;
  title: string;
  type: string;
  value: number;
  boost: number;
  quantity: number;
  imageUrl?: string;
  imageUrlRu?: string;
}

// ============================================================
// MAPPERS: GraphQL -> Internal Types
// ============================================================

function mapCardType(cardType: string): import('@/core/models/types').CardType {
  const type = cardType.toLowerCase();
  if (type === 'attack') return 'attack' as const;
  if (type === 'defense') return 'defense' as const;
  if (type === 'versatile') return 'versatile' as const;
  if (type === 'scheme') return 'scheme' as const;
  return 'attack' as const;
}

function createCardDefinition(card: ApiCard, characterName: string): CardDefinition {
  return {
    id: card.id,
    title: card.title,
    type: mapCardType(card.type),
    value: card.value,
    boost: card.boost,
    quantity: card.quantity,
    effects: [],
    characterName,
    imageUrl: card.imageUrl || card.imageUrlRu || undefined,
  };
}

function createCardInstance(
  definition: CardDefinition,
  ownerId: string,
  instanceIndex: number
): CardInstance {
  return {
    id: `${definition.id}-${instanceIndex}`,
    definition,
    ownerId,
    instanceIndex,
  };
}

function createDeck(heroData: HeroQuery['hero'], ownerId: string): {
  deck: CardInstance[];
  definitions: CardDefinition[];
} {
  if (!heroData.cards || heroData.cards.length === 0) {
    return { deck: [], definitions: [] };
  }

  const definitions: CardDefinition[] = heroData.cards.map((card) =>
    createCardDefinition(card, heroData.name || '')
  );

  const deck: CardInstance[] = [];
  definitions.forEach((def) => {
    for (let i = 0; i < def.quantity; i++) {
      deck.push(createCardInstance(def, ownerId, i));
    }
  });

  // Shuffle deck
  for (let i = deck.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [deck[i], deck[j]] = [deck[j], deck[i]];
  }

  return { deck, definitions };
}

function createFighter(
  heroData: HeroQuery['hero'],
  ownerId: string,
  position: Position,
  sidekickNumber = 0
): Fighter {
  const isSidekick = sidekickNumber > 0;
  return {
    id: isSidekick ? `${ownerId}-sidekick-${sidekickNumber}` : `${ownerId}-hero`,
    definitionId: heroData.id || '',
    type: isSidekick ? 'sidekick' : 'hero',
    health: isSidekick
      ? (heroData.sidekickHealth || 5)
      : (heroData.health || 14),
    maxHealth: isSidekick
      ? (heroData.sidekickHealth || 5)
      : (heroData.health || 14),
    position,
    ownerId,
    isDefeated: false,
    avatarUrl: heroData.urls?.avatar || heroData.avatarUrl || undefined,
  };
}

function createPlayer(
  heroData: HeroQuery['hero'],
  playerId: string,
  playerName: string,
  position: Position
): Player {
  const { deck } = createDeck(heroData, playerId);

  // Create hero fighter
  const hero = createFighter(heroData, playerId, position);

  // Create sidekicks if any
  const sidekicks: Fighter[] = [];
  const sidekickCount = heroData.sidekickCount || 0;
  for (let i = 1; i <= sidekickCount; i++) {
    const sidekickPos: Position = {
      x: position.x + i,
      y: position.y,
    };
    sidekicks.push(createFighter(heroData, playerId, sidekickPos, i));
  }

  // Draw starting hand (5 cards)
  const startingHandSize = 5;
  const hand = deck.splice(0, Math.min(startingHandSize, deck.length));

  return {
    id: playerId,
    name: playerName,
    fighters: [hero, ...sidekicks],
    hand,
    discardPile: [],
    deck,
    actionsRemaining: 2,
    hasPassed: false,
    handLimit: 7,
  };
}

function mapBoardFromGraphQL(board: BoardsQuery['boards'][0]): BoardDefinition {
  return {
    id: board.id || 'unknown',
    name: board.name || 'Unknown Board',
    width: board.width || 6,
    height: board.height || 4,
    recommendedPlayers: board.recommendedPlayers || 2,
    imageUrl: board.imageUrl || undefined,
    spaces: (board.spaces || []).map((space) => ({
      position: space.position,
      zones: (space.zones || []) as Array<'blue' | 'green' | 'yellow' | 'red' | 'purple'>,
      isObstacle: space.isObstacle || false,
    })),
  };
}

function createMockGameState(
  hero1Data: HeroQuery['hero'],
  hero2Data: HeroQuery['hero'],
  boardData: BoardsQuery['boards'][0]
): GameState {
  const boardDef = mapBoardFromGraphQL(boardData);

  // Create players with opposite starting positions
  const player1 = createPlayer(
    hero1Data,
    'player-1',
    hero1Data.name || 'Player 1',
    { x: 0, y: Math.floor(boardDef.height / 2) }
  );

  const player2 = createPlayer(
    hero2Data,
    'player-2',
    hero2Data.name || 'Player 2',
    { x: boardDef.width - 1, y: Math.floor(boardDef.height / 2) }
  );

  const boardState: BoardState = {
    definition: boardDef,
    fighters: new Map(),
  };

  // Set fighter positions
  [...player1.fighters, ...player2.fighters].forEach((fighter) => {
    boardState.fighters.set(fighter.id, fighter.position);
  });

  return {
    id: 'test-game-' + Date.now(),
    players: [player1, player2],
    board: boardState,
    currentTurn: {
      currentPlayerId: player1.id,
      action1: undefined,
      action2: undefined,
      cardsDrawnThisTurn: 0,
      selectedCard: undefined,
      selectedTarget: undefined,
    },
    phase: 'action_selection' as GamePhase,
    combatState: null,
    winner: null,
    turnCount: 1,
  };
}

// ============================================================
// STORE INTERFACE
// ============================================================

interface TestGameStoreState {
  // Loading state
  isLoading: boolean;
  error: string | null;

  // Available data
  allHeroes: HeroesQuery['heroes'];
  heroDetails: Map<string, HeroQuery['hero']>;
  allBoards: BoardsQuery['boards'];

  // Game state
  gameState: GameState | null;
  selectedCardId: string | null;
  selectedFighterId: string | null;
  highlightedSpaces: Position[];

  // Actions
  loadHeroes: () => Promise<void>;
  loadHeroDetails: (heroId: string) => Promise<void>;
  loadBoards: () => Promise<void>;
  initializeGame: (hero1Id: string, hero2Id: string, boardId?: string) => Promise<void>;
  initializeRandomGame: () => Promise<void>;
  selectCard: (cardId: string | null) => void;
  selectFighter: (fighterId: string | null) => void;
  moveFighter: (fighterId: string, position: Position) => void;
  playCard: (cardId: string) => void;
  endTurn: () => void;
  resetGame: () => void;
  setError: (error: string | null) => void;

  // Getters
  getCurrentPlayer: () => Player | null;
  getOpponentPlayer: () => Player | null;
}

// ============================================================
// STORE IMPLEMENTATION
// ============================================================

export const useTestGameStore = create<TestGameStoreState>((set, get) => ({
  // Initial state
  isLoading: false,
  error: null,
  allHeroes: [],
  heroDetails: new Map(),
  allBoards: [],
  gameState: null,
  selectedCardId: null,
  selectedFighterId: null,
  highlightedSpaces: [],

  // Load all heroes (basic info)
  loadHeroes: async () => {
    set({ isLoading: true, error: null });
    try {
      const { data } = await apolloClient.query({
        query: HeroesDocument,
        fetchPolicy: 'network-only',
      });

      if (data?.heroes) {
        // Filter out empty heroes
        const validHeroes = data.heroes.filter(h => h.id && h.name);
        set({ allHeroes: validHeroes, isLoading: false });
      }
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Failed to load heroes';
      set({ error: errorMessage, isLoading: false });
      console.error('Error loading heroes:', err);
    }
  },

  // Load hero details with cards
  loadHeroDetails: async (heroId: string) => {
    // Check if already loaded
    const existing = get().heroDetails.get(heroId);
    if (existing) return;

    try {
      const { data } = await apolloClient.query({
        query: HeroDocument,
        variables: { id: heroId },
        fetchPolicy: 'network-only',
      });

      if (data?.hero) {
        set((state) => {
          const newDetails = new Map(state.heroDetails);
          newDetails.set(heroId, data.hero!);
          return { heroDetails: newDetails };
        });
      }
    } catch (err) {
      console.error(`Error loading hero details for ${heroId}:`, err);
    }
  },

  // Load boards
  loadBoards: async () => {
    try {
      const { data } = await apolloClient.query({
        query: BoardsDocument,
        fetchPolicy: 'network-only',
      });

      if (data?.boards) {
        set({ allBoards: data.boards });
      }
    } catch (err) {
      console.error('Error loading boards:', err);
      // Use mock board if API fails
      set({
        allBoards: [createMockBoard()],
      });
    }
  },

  // Initialize game with specific heroes
  initializeGame: async (hero1Id: string, hero2Id: string, boardId?: string) => {
    set({ isLoading: true, error: null });

    try {
      // Load hero details for both heroes
      await Promise.all([
        get().loadHeroDetails(hero1Id),
        get().loadHeroDetails(hero2Id),
      ]);

      const hero1Data = get().heroDetails.get(hero1Id);
      const hero2Data = get().heroDetails.get(hero2Id);

      if (!hero1Data || !hero2Data) {
        throw new Error('Failed to load hero data');
      }

      // Get or create board
      let boardData = get().allBoards.find((b) => b.id === boardId);
      if (!boardData) {
        boardData = get().allBoards[0] || createMockBoard();
      }

      const gameState = createMockGameState(hero1Data, hero2Data, boardData);

      set({
        gameState,
        isLoading: false,
        selectedCardId: null,
        selectedFighterId: null,
        highlightedSpaces: [],
      });
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Failed to initialize game';
      set({ error: errorMessage, isLoading: false });
    }
  },

  // Initialize game with random heroes
  initializeRandomGame: async () => {
    const { allHeroes, allBoards } = get();

    if (allHeroes.length < 2) {
      await get().loadHeroes();
    }

    const heroes = get().allHeroes;
    if (heroes.length < 2) {
      set({ error: 'Not enough heroes available' });
      return;
    }

    // Select two random heroes
    const shuffled = [...heroes].sort(() => Math.random() - 0.5);
    const hero1Id = shuffled[0].id;
    const hero2Id = shuffled[1].id;

    // Get a random board
    const board = allBoards.length > 0
      ? allBoards[Math.floor(Math.random() * allBoards.length)]
      : undefined;

    await get().initializeGame(hero1Id, hero2Id, board?.id);
  },

  // Select a card
  selectCard: (cardId: string | null) => {
    set({ selectedCardId: cardId });

    if (cardId) {
      // Highlight valid spaces for attack/defense
      const { gameState } = get();
      if (!gameState) return;

      const selectedFighter = gameState.players
        .flatMap((p) => p.fighters)
        .find((f) => f.id === get().selectedFighterId);

      if (selectedFighter) {
        const spaces: Position[] = [];
        const { x, y } = selectedFighter.position;

        // Highlight adjacent spaces
        for (let dx = -1; dx <= 1; dx++) {
          for (let dy = -1; dy <= 1; dy++) {
            if (dx === 0 && dy === 0) continue;
            spaces.push({ x: x + dx, y: y + dy });
          }
        }

        set({ highlightedSpaces: spaces });
      }
    } else {
      set({ highlightedSpaces: [] });
    }
  },

  // Select a fighter
  selectFighter: (fighterId: string | null) => {
    set({ selectedFighterId: fighterId });
  },

  // Move fighter
  moveFighter: (fighterId: string, position: Position) => {
    const { gameState } = get();
    if (!gameState) return;

    const updatedPlayers = gameState.players.map((player) => ({
      ...player,
      fighters: player.fighters.map((fighter) =>
        fighter.id === fighterId
          ? { ...fighter, position }
          : fighter
      ),
    }));

    set({
      gameState: {
        ...gameState,
        players: updatedPlayers,
      },
    });
  },

  // Play a card
  playCard: (cardId: string) => {
    const { gameState } = get();
    if (!gameState) return;

    const currentPlayer = get().getCurrentPlayer();
    if (!currentPlayer) return;

    // Remove card from hand
    const updatedPlayer = {
      ...currentPlayer,
      hand: currentPlayer.hand.filter((c) => c.id !== cardId),
      discardPile: [
        ...currentPlayer.discardPile,
        currentPlayer.hand.find((c) => c.id === cardId)!,
      ],
    };

    const updatedPlayers = gameState.players.map((p) =>
      p.id === updatedPlayer.id ? updatedPlayer : p
    );

    set({
      gameState: {
        ...gameState,
        players: updatedPlayers,
      },
      selectedCardId: null,
      highlightedSpaces: [],
    });
  },

  // End turn
  endTurn: () => {
    const { gameState } = get();
    if (!gameState) return;

    const currentPlayerId = gameState.currentTurn.currentPlayerId;
    const nextPlayerId = gameState.players.find(
      (p) => p.id !== currentPlayerId
    )?.id;

    if (!nextPlayerId) return;

    // Draw a card for the next player
    const nextPlayer = gameState.players.find((p) => p.id === nextPlayerId)!;
    const drawnCard = nextPlayer.deck.length > 0 ? [nextPlayer.deck[0]] : [];

    const updatedPlayers = gameState.players.map((p) => {
      if (p.id === nextPlayerId) {
        return {
          ...p,
          hand: [...p.hand, ...drawnCard],
          deck: drawnCard.length > 0 ? p.deck.slice(1) : p.deck,
          actionsRemaining: 2,
          hasPassed: false,
        };
      }
      return p;
    });

    set({
      gameState: {
        ...gameState,
        players: updatedPlayers,
        currentTurn: {
          ...gameState.currentTurn,
          currentPlayerId: nextPlayerId,
          cardsDrawnThisTurn: drawnCard.length,
        },
        turnCount: gameState.turnCount + 1,
      },
      selectedCardId: null,
      selectedFighterId: null,
      highlightedSpaces: [],
    });
  },

  // Reset game
  resetGame: () => {
    set({
      gameState: null,
      selectedCardId: null,
      selectedFighterId: null,
      highlightedSpaces: [],
      error: null,
    });
  },

  // Set error
  setError: (error: string | null) => {
    set({ error });
  },

  // Get current player
  getCurrentPlayer: () => {
    const { gameState } = get();
    if (!gameState) return null;
    return gameState.players.find(
      (p) => p.id === gameState.currentTurn.currentPlayerId
    ) || null;
  },

  // Get opponent player
  getOpponentPlayer: () => {
    const { gameState } = get();
    if (!gameState) return null;
    return gameState.players.find(
      (p) => p.id !== gameState.currentTurn.currentPlayerId
    ) || null;
  },
}));

// ============================================================
// UTILITIES
// ============================================================

function createMockBoard(): BoardsQuery['boards'][0] {
  const zones: Array<'blue' | 'green' | 'yellow' | 'red' | 'purple'> = ['blue', 'green', 'yellow', 'red', 'purple'];
  const width = 6;
  const height = 4;

  const spaces = [];
  for (let y = 0; y < height; y++) {
    for (let x = 0; x < width; x++) {
      const zoneIndex = (x + y) % zones.length;
      const hasSecondZone = (x + y) % 3 === 0;

      spaces.push({
        position: { x, y },
        zones: hasSecondZone
          ? [zones[zoneIndex], zones[(zoneIndex + 1) % zones.length]]
          : [zones[zoneIndex]],
        isObstacle: false,
      });
    }
  }

  return {
    id: 'cobble-city',
    name: 'Cobble City',
    width,
    height,
    recommendedPlayers: 2,
    spaces,
  } as BoardsQuery['boards'][0];
}
