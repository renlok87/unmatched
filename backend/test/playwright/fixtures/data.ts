/**
 * Data Constants и Selectors для E2E тестов
 *
 * Содержит:
 * - URL endpoints
 * - UI селекторы (Page Object Model)
 * - GraphQL мутации/запросы
 * - Тестовые константы
 */

// ============================================================
// URL Endpoints
// ============================================================

export const URLS = {
  BASE: 'http://localhost:5174',
  GRAPHQL: 'http://localhost:3000/graphql',
  WS: 'ws://localhost:3000/graphql',

  // Pages
  HOME: '/',
  LOGIN: '/login',
  LOBBY: '/lobby',
  GAME: (gameId: string) => `/game/${gameId}`,
  PROFILE: (userId: string) => `/profile/${userId}`,
  LEADERBOARD: '/leaderboard',
} as const;

// ============================================================
// GraphQL Queries & Mutations
// ============================================================

export const MUTATIONS = {
  // Auth
  REGISTER: `mutation Register($input: RegisterDto!) {
    register(input: $input) {
      accessToken
      refreshToken
      user {
        id
        email
        username
      }
    }
  }`,

  LOGIN: `mutation Login($input: LoginDto!) {
    login(input: $input) {
      accessToken
      refreshToken
      user {
        id
        email
        username
      }
    }
  }`,

  // Game Actions
  MANEUVER: `mutation Maneuver($input: ManeuverDto!) {
    maneuver(input: $input) {
      state
      sequenceNumber
      timestamp
      phase
      currentTurnPlayerId
      turnCount
    }
  }`,

  MOVE_FIGHTER: `mutation MoveFighter($input: MoveFighterDto!) {
    moveFighter(input: $input) {
      state
      sequenceNumber
      timestamp
      phase
    }
  }`,

  ATTACK: `mutation Attack($input: AttackDto!) {
    attack(input: $input) {
      state
      sequenceNumber
      timestamp
      phase
    }
  }`,

  PLAY_DEFENSE: `mutation PlayDefense($input: PlayDefenseDto!) {
    playDefense(input: $input) {
      state
      sequenceNumber
      timestamp
      phase
    }
  }`,

  RESOLVE_COMBAT: `mutation ResolveCombat($input: ResolveCombatDto!) {
    resolveCombat(input: $input) {
      state
      sequenceNumber
      timestamp
      phase
    }
  }`,

  END_TURN: `mutation EndTurn($input: EndTurnDto!) {
    endTurn(input: $input) {
      state
      sequenceNumber
      timestamp
      phase
      currentTurnPlayerId
      turnCount
    }
  }`,

  PASS: `mutation Pass($input: PassDto!) {
    pass(input: $input) {
      state
      sequenceNumber
      timestamp
      phase
    }
  }`,

  TOGGLE_DOOR: `mutation ToggleDoor($input: ToggleDoorDto!) {
    toggleDoor(input: $input) {
      state
      sequenceNumber
      timestamp
    }
  }`,

  // Game Management
  CREATE_GAME: `mutation CreateGame($input: CreateGameDto!) {
    createGame(input: $input) {
      id
      status
      players {
        userId
        heroId
      }
    }
  }`,

  JOIN_GAME: `mutation JoinGame($input: JoinGameDto!) {
    joinGame(input: $input) {
      id
      status
      players {
        userId
        heroId
      }
    }
  }`,

  LEAVE_GAME: `mutation LeaveGame($gameId: ID!) {
    leaveGame(gameId: $gameId) {
      id
      status
    }
  }`,

  // Subscriptions
  GAME_SUBSCRIPTION: `subscription OnGameUpdate($gameId: ID!) {
    gameUpdate(gameId: $gameId) {
      state
      sequenceNumber
      timestamp
      eventType
    }
  }`,
} as const;

export const QUERIES = {
  ME: `query Me {
    me {
      id
      email
      username
      stats {
        gamesPlayed
        wins
        losses
        rating
      }
    }
  }`,

  GAME: `query Game($id: ID!) {
    game(id: $id) {
      id
      status
      phase
      currentTurnPlayerId
      turnCount
      players {
        userId
        heroId
        health
        isAlive
      }
    }
  }`,

  HEROES: `query Heroes {
    heroes {
      id
      name
      health
      abilities
    }
  }`,

  CARDS: `query Cards($heroId: ID!) {
    cards(heroId: $heroId) {
      id
      name
      cardType
      value
      effects
    }
  }`,
} as const;

// ============================================================
// UI Selectors (Page Object Model)
// ============================================================

export const SELECTORS = {
  // Auth
  LOGIN_FORM: '.login-form',
  EMAIL_INPUT: '[name="email"]',
  PASSWORD_INPUT: '[name="password"]',
  SUBMIT_BUTTON: 'button[type="submit"]',

  // Game Board
  GAME_BOARD: '.game-board',
  FIGHTER: (fighterId: string) => `[data-fighter-id="${fighterId}"]`,
  CELL: (x: number, y: number) => `[data-cell-x="${x}"][data-cell-y="${y}"]`,
  HAND_ZONE: (playerId: string) => `[data-hand-zone="${playerId}"]`,
  CARD: (cardId: string) => `[data-card-id="${cardId}"]`,

  // UI Elements
  TURN_INDICATOR: '.turn-indicator',
  PHASE_INDICATOR: '.phase-indicator',
  HEALTH_BAR: (fighterId: string) => `[data-fighter-id="${fighterId}"] .health-bar`,
  ACTION_BUTTONS: '.action-buttons',

  // Actions
  MANEUVER_BUTTON: '[data-action="maneuver"]',
  ATTACK_BUTTON: '[data-action="attack"]',
  DEFEND_BUTTON: '[data-action="defend"]',
  END_TURN_BUTTON: '[data-action="end-turn"]',
  PASS_BUTTON: '[data-action="pass"]',

  // Victory Screen
  VICTORY_SCREEN: '.victory-screen',
  VICTORY_TITLE: '.victory-screen__title',
  VICTORY_REWARDS: '.victory-screen__rewards',
  PLAY_AGAIN_BUTTON: '[data-action="play-again"]',
  RETURN_TO_LOBBY_BUTTON: '[data-action="return-to-lobby"]',

  // Replay Player
  REPLAY_PLAYER: '.replay-player',
  REPLAY_PLAY_BUTTON: '.replay-player__btn--play',
  REPLAY_TIMELINE: '.replay-player__timeline',
  REPLAY_EVENT_MARKER: '.replay-player__event-marker',

  // Lobby
  LOBBY_LIST: '.lobby-list',
  LOBBY_ITEM: (gameId: string) => `[data-game-id="${gameId}"]`,
  CREATE_GAME_BUTTON: '[data-action="create-game"]',
  JOIN_GAME_BUTTON: '[data-action="join-game"]',

  // Loading States
  LOADING_SPINNER: '.loading-spinner',
  LOADING_OVERLAY: '.loading-overlay',
} as const;

// ============================================================
// Test Data
// ============================================================

export const HEROES = {
  MS_MARVEL: 'ms-marvel',
  DAREDEVIL: 'daredevil',
  BRUCE_LEE: 'bruce-lee',
  DEADPOOL: 'deadpool',
  BLACK_PANTHER: 'black-panther',
  SPIDER_HAM: 'spider-ham',
  BIG_BARBOSA: 'big-barbosa',
} as const;

export const HERO_STATS = {
  [HEROES.MS_MARVEL]: { health: 14, maxHealth: 14 },
  [HEROES.DAREDEVIL]: { health: 17, maxHealth: 17 },
  [HEROES.BRUCE_LEE]: { health: 15, maxHealth: 15 },
  [HEROES.DEADPOOL]: { health: 20, maxHealth: 20 },
  [HEROES.BLACK_PANTHER]: { health: 14, maxHealth: 14 },
  [HEROES.SPIDER_HAM]: { health: 12, maxHealth: 12 },
  [HEROES.BIG_BARBOSA]: { health: 18, maxHealth: 18 },
} as const;

export const CARD_TYPES = {
  ATTACK: 'ATTACK',
  DEFENSE: 'DEFENSE',
  EFFECT: 'EFFECT',
  SCHEME: 'SCHEME',
} as const;

export const GAME_PHASES = {
  TURN_START: 'TURN_START',
  ACTION_MANEUVER: 'ACTION_MANEUVER',
  ACTION_ATTACK: 'ACTION_ATTACK',
  COMBAT: 'COMBAT',
  COMBAT_RESOLVE: 'COMBAT_RESOLVE',
  GAME_OVER: 'GAME_OVER',
} as const;

// ============================================================
// Test Users
// ============================================================

export const TEST_USERS = {
  PLAYER1: {
    email: 'e2e_player1@test.com',
    username: 'e2e_player1',
    password: 'Test1234',
  },
  PLAYER2: {
    email: 'e2e_player2@test.com',
    username: 'e2e_player2',
    password: 'Test1234',
  },
  PLAYER3: {
    email: 'e2e_player3@test.com',
    username: 'e2e_player3',
    password: 'Test1234',
  },
} as const;

// ============================================================
// Storage State Paths
// ============================================================

export const STORAGE_STATES = {
  PLAYER1: './storage-states/player1.json',
  PLAYER2: './storage-states/player2.json',
  PLAYER3: './storage-states/player3.json',
} as const;

// ============================================================
// Board Constants
// ============================================================

export const BOARD = {
  WIDTH: 20,
  HEIGHT: 20,
  START_POSITIONS: {
    PLAYER1: { x: 2, y: 10 },
    PLAYER2: { x: 17, y: 10 },
    PLAYER3: { x: 10, y: 2 },
    PLAYER4: { x: 10, y: 17 },
  },
} as const;

// ============================================================
// Timeout Constants
// ============================================================

export const TIMEOUTS = {
  // Navigation
  NAVIGATION: 30000,

  // Actions
  CLICK: 10000,
  FILL: 10000,
  HOVER: 5000,

  // Subscriptions
  WS_CONNECTION: 10000,
  WS_MESSAGE: 5000,

  // Game states
  TURN_CHANGE: 10000,
  PHASE_CHANGE: 5000,
  COMBAT_RESOLVE: 10000,

  // Long operations
  GAME_CREATION: 15000,
  GAME_JOIN: 10000,
} as const;
