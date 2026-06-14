/* eslint-disable */
import { TypedDocumentNode as DocumentNode } from '@graphql-typed-document-node/core';
export type Maybe<T> = T | null;
export type InputMaybe<T> = T | null | undefined;
export type Exact<T extends { [key: string]: unknown }> = { [K in keyof T]: T[K] };
export type MakeOptional<T, K extends keyof T> = Omit<T, K> & { [SubKey in K]?: Maybe<T[SubKey]> };
export type MakeMaybe<T, K extends keyof T> = Omit<T, K> & { [SubKey in K]: Maybe<T[SubKey]> };
export type MakeEmpty<T extends { [key: string]: unknown }, K extends keyof T> = { [_ in K]?: never };
export type Incremental<T> = T | { [P in keyof T]?: P extends ' $fragmentName' | '__typename' ? T[P] : never };
/** All built-in and custom scalars, mapped to their actual values */
export type Scalars = {
  ID: { input: string; output: string; }
  String: { input: string; output: string; }
  Boolean: { input: boolean; output: boolean; }
  Int: { input: number; output: number; }
  Float: { input: number; output: number; }
  /** Date custom scalar type */
  DateTime: { input: any; output: any; }
  /** JSON custom scalar type */
  JSON: { input: any; output: any; }
};

/** Trigger condition for a hero ability */
export enum AbilityTrigger {
  DuringCombat = 'DURING_COMBAT',
  EndOfTurn = 'END_OF_TURN',
  Passive = 'PASSIVE',
  StartOfTurn = 'START_OF_TURN',
  WhenAttacked = 'WHEN_ATTACKED',
  WhenDefending = 'WHEN_DEFENDING'
}

export type AdminBoard = {
  __typename?: 'AdminBoard';
  cells?: Maybe<Scalars['String']['output']>;
  createdAt: Scalars['DateTime']['output'];
  features?: Maybe<Scalars['String']['output']>;
  height: Scalars['Float']['output'];
  id: Scalars['String']['output'];
  imageUrl?: Maybe<Scalars['String']['output']>;
  imageUrlDark?: Maybe<Scalars['String']['output']>;
  name: Scalars['String']['output'];
  nameEn: Scalars['String']['output'];
  nameRu: Scalars['String']['output'];
  set: Scalars['String']['output'];
  updatedAt: Scalars['DateTime']['output'];
  width: Scalars['Float']['output'];
};

export type AdminCard = {
  __typename?: 'AdminCard';
  attackValue?: Maybe<Scalars['Int']['output']>;
  bannerName?: Maybe<Scalars['String']['output']>;
  boostValue?: Maybe<Scalars['Int']['output']>;
  cardType: Scalars['String']['output'];
  count: Scalars['Float']['output'];
  createdAt: Scalars['DateTime']['output'];
  defenseValue?: Maybe<Scalars['Int']['output']>;
  effectAfter?: Maybe<Scalars['String']['output']>;
  effectBoost?: Maybe<Scalars['String']['output']>;
  effectDuring?: Maybe<Scalars['String']['output']>;
  effectImmediately?: Maybe<Scalars['String']['output']>;
  effectOngoing?: Maybe<Scalars['String']['output']>;
  effects?: Maybe<Scalars['String']['output']>;
  heroId: Scalars['String']['output'];
  id: Scalars['String']['output'];
  imageUrl?: Maybe<Scalars['String']['output']>;
  imageUrlRu?: Maybe<Scalars['String']['output']>;
  name: Scalars['String']['output'];
  nameEn: Scalars['String']['output'];
  nameRu: Scalars['String']['output'];
  subType?: Maybe<Scalars['String']['output']>;
  text?: Maybe<Scalars['String']['output']>;
  textEn?: Maybe<Scalars['String']['output']>;
  textRu?: Maybe<Scalars['String']['output']>;
  updatedAt: Scalars['DateTime']['output'];
};

export type AdminGameDto = {
  __typename?: 'AdminGameDto';
  boardId: Scalars['String']['output'];
  boardName?: Maybe<Scalars['String']['output']>;
  code?: Maybe<Scalars['String']['output']>;
  createdAt: Scalars['DateTime']['output'];
  finishedAt?: Maybe<Scalars['DateTime']['output']>;
  gamePlayers: Array<GamePlayerInfoDto>;
  id: Scalars['String']['output'];
  mode: Scalars['String']['output'];
  startedAt?: Maybe<Scalars['DateTime']['output']>;
  status: Scalars['String']['output'];
};

export type AdminHero = {
  __typename?: 'AdminHero';
  ability?: Maybe<Scalars['String']['output']>;
  additionalMinis?: Maybe<Scalars['String']['output']>;
  avatarUrl?: Maybe<Scalars['String']['output']>;
  cards?: Maybe<Array<AdminCard>>;
  characterCardUrl?: Maybe<Scalars['String']['output']>;
  color?: Maybe<Scalars['String']['output']>;
  createdAt: Scalars['DateTime']['output'];
  deckCards?: Maybe<Scalars['String']['output']>;
  fighterType: Scalars['String']['output'];
  hasTokens?: Maybe<Scalars['Boolean']['output']>;
  health: Scalars['Float']['output'];
  id: Scalars['String']['output'];
  imageUrl?: Maybe<Scalars['String']['output']>;
  miniModelUrl?: Maybe<Scalars['String']['output']>;
  movement?: Maybe<Scalars['Int']['output']>;
  name: Scalars['String']['output'];
  nameEn: Scalars['String']['output'];
  nameRu: Scalars['String']['output'];
  properties?: Maybe<Scalars['String']['output']>;
  set: Scalars['String']['output'];
  sidekicks?: Maybe<Scalars['String']['output']>;
  updatedAt: Scalars['DateTime']['output'];
};

export type AdminStatsDto = {
  __typename?: 'AdminStatsDto';
  totalBoards: Scalars['Float']['output'];
  totalCards: Scalars['Float']['output'];
  totalGames: Scalars['Float']['output'];
  totalHeroes: Scalars['Float']['output'];
  totalUsers: Scalars['Float']['output'];
};

export type AttackDto = {
  attackerId: Scalars['String']['input'];
  boostCardId?: InputMaybe<Scalars['String']['input']>;
  cardId: Scalars['String']['input'];
  gameId: Scalars['String']['input'];
  targetId: Scalars['String']['input'];
};

export type AuditLogDto = {
  __typename?: 'AuditLogDto';
  action: Scalars['String']['output'];
  errorMessage?: Maybe<Scalars['String']['output']>;
  id: Scalars['String']['output'];
  ipAddress?: Maybe<Scalars['String']['output']>;
  metadata?: Maybe<Scalars['String']['output']>;
  success: Scalars['Boolean']['output'];
  timestamp: Scalars['DateTime']['output'];
  userAgent?: Maybe<Scalars['String']['output']>;
  userId?: Maybe<Scalars['String']['output']>;
};

export type AuditLogsPaginatedDto = {
  __typename?: 'AuditLogsPaginatedDto';
  items: Array<AuditLogDto>;
  total: Scalars['Float']['output'];
};

export type AuthResponseDto = {
  __typename?: 'AuthResponseDto';
  accessToken: Scalars['String']['output'];
  refreshToken: Scalars['String']['output'];
  user: AuthUserResponse;
};

export type AuthUserResponse = {
  __typename?: 'AuthUserResponse';
  avatar?: Maybe<Scalars['String']['output']>;
  createdAt: Scalars['DateTime']['output'];
  email: Scalars['String']['output'];
  emailVerified?: Maybe<Scalars['DateTime']['output']>;
  id: Scalars['String']['output'];
  role: UserRole;
  username: Scalars['String']['output'];
};

export type Board = {
  __typename?: 'Board';
  height: Scalars['Int']['output'];
  id: Scalars['String']['output'];
  imageUrl?: Maybe<Scalars['String']['output']>;
  name: Scalars['String']['output'];
  recommendedPlayers: Scalars['Int']['output'];
  spaces: Array<BoardSpace>;
  width: Scalars['Int']['output'];
};

export type BoardListItemDto = {
  __typename?: 'BoardListItemDto';
  createdAt: Scalars['DateTime']['output'];
  height: Scalars['Float']['output'];
  id: Scalars['String']['output'];
  imageUrl?: Maybe<Scalars['String']['output']>;
  imageUrlDark?: Maybe<Scalars['String']['output']>;
  name: Scalars['String']['output'];
  nameEn: Scalars['String']['output'];
  nameRu: Scalars['String']['output'];
  set: Scalars['String']['output'];
  width: Scalars['Float']['output'];
};

export type BoardSpace = {
  __typename?: 'BoardSpace';
  isObstacle?: Maybe<Scalars['Boolean']['output']>;
  position: Position;
  startingPositionsJson?: Maybe<Scalars['String']['output']>;
  zones: Array<Zone>;
};

export type BoardsPaginatedDto = {
  __typename?: 'BoardsPaginatedDto';
  items: Array<BoardListItemDto>;
  limit: Scalars['Float']['output'];
  page: Scalars['Float']['output'];
  total: Scalars['Float']['output'];
  totalPages: Scalars['Float']['output'];
};

export type Card = {
  __typename?: 'Card';
  boost: Scalars['Int']['output'];
  characterName: Scalars['String']['output'];
  effects: Array<CardEffect>;
  id: Scalars['String']['output'];
  imageUrl?: Maybe<Scalars['String']['output']>;
  imageUrlRu?: Maybe<Scalars['String']['output']>;
  quantity: Scalars['Int']['output'];
  title: Scalars['String']['output'];
  type: CardType;
  value: Scalars['Int']['output'];
};

export type CardEffect = {
  __typename?: 'CardEffect';
  id: Scalars['String']['output'];
  text: Scalars['String']['output'];
  timing: EffectTiming;
};

export type CardListItemDto = {
  __typename?: 'CardListItemDto';
  attackValue?: Maybe<Scalars['Int']['output']>;
  bannerName?: Maybe<Scalars['String']['output']>;
  boostValue?: Maybe<Scalars['Int']['output']>;
  cardType: Scalars['String']['output'];
  count: Scalars['Float']['output'];
  createdAt?: Maybe<Scalars['DateTime']['output']>;
  defenseValue?: Maybe<Scalars['Int']['output']>;
  heroId: Scalars['String']['output'];
  id: Scalars['String']['output'];
  imageUrl?: Maybe<Scalars['String']['output']>;
  imageUrlRu?: Maybe<Scalars['String']['output']>;
  name: Scalars['String']['output'];
  nameEn: Scalars['String']['output'];
  nameRu: Scalars['String']['output'];
  subType?: Maybe<Scalars['String']['output']>;
};

/** Type of a card in the game */
export enum CardType {
  Attack = 'ATTACK',
  Defense = 'DEFENSE',
  Scheme = 'SCHEME',
  Versatile = 'VERSATILE'
}

export type CardsPaginatedDto = {
  __typename?: 'CardsPaginatedDto';
  items: Array<CardListItemDto>;
  limit: Scalars['Float']['output'];
  page: Scalars['Float']['output'];
  total: Scalars['Float']['output'];
  totalPages: Scalars['Float']['output'];
};

export type ChangePasswordDto = {
  currentPassword: Scalars['String']['input'];
  newPassword: Scalars['String']['input'];
};

export type CleanupGamesInput = {
  abortStuckInProgress?: InputMaybe<Scalars['Boolean']['input']>;
  finishedOlderThanDays?: InputMaybe<Scalars['Int']['input']>;
  stuckMinutes?: InputMaybe<Scalars['Int']['input']>;
};

export type CleanupGamesResultDto = {
  __typename?: 'CleanupGamesResultDto';
  aborted: Scalars['Int']['output'];
  deleted: Scalars['Int']['output'];
};

export type ContentSummary = {
  __typename?: 'ContentSummary';
  boardsCount: Scalars['Int']['output'];
  heroesCount: Scalars['Int']['output'];
  sets: Array<Scalars['String']['output']>;
  setsCount: Scalars['Int']['output'];
  version: Scalars['String']['output'];
};

export type CreateBoardInput = {
  cells: Scalars['String']['input'];
  features?: InputMaybe<Scalars['String']['input']>;
  height: Scalars['Int']['input'];
  imageUrl?: InputMaybe<Scalars['String']['input']>;
  imageUrlDark?: InputMaybe<Scalars['String']['input']>;
  name: Scalars['String']['input'];
  nameEn: Scalars['String']['input'];
  nameRu: Scalars['String']['input'];
  set: Scalars['String']['input'];
  width: Scalars['Int']['input'];
};

export type CreateCardInput = {
  attackValue?: InputMaybe<Scalars['Int']['input']>;
  bannerName?: InputMaybe<Scalars['String']['input']>;
  boostValue?: InputMaybe<Scalars['Int']['input']>;
  cardType: Scalars['String']['input'];
  count?: InputMaybe<Scalars['Int']['input']>;
  defenseValue?: InputMaybe<Scalars['Int']['input']>;
  effectAfter?: InputMaybe<Scalars['String']['input']>;
  effectBoost?: InputMaybe<Scalars['String']['input']>;
  effectDuring?: InputMaybe<Scalars['String']['input']>;
  effectImmediately?: InputMaybe<Scalars['String']['input']>;
  effectOngoing?: InputMaybe<Scalars['String']['input']>;
  effects?: InputMaybe<Scalars['String']['input']>;
  heroId: Scalars['String']['input'];
  imageUrl?: InputMaybe<Scalars['String']['input']>;
  imageUrlRu?: InputMaybe<Scalars['String']['input']>;
  name: Scalars['String']['input'];
  nameEn: Scalars['String']['input'];
  nameRu: Scalars['String']['input'];
  subType?: InputMaybe<Scalars['String']['input']>;
  text?: InputMaybe<Scalars['String']['input']>;
  textEn?: InputMaybe<Scalars['String']['input']>;
  textRu?: InputMaybe<Scalars['String']['input']>;
};

export type CreateGameDto = {
  boardId?: InputMaybe<Scalars['String']['input']>;
  mode?: InputMaybe<GameMode>;
};

export type CreateHeroInput = {
  ability?: InputMaybe<Scalars['String']['input']>;
  additionalMinis?: InputMaybe<Scalars['String']['input']>;
  avatarUrl?: InputMaybe<Scalars['String']['input']>;
  characterCardUrl?: InputMaybe<Scalars['String']['input']>;
  color?: InputMaybe<Scalars['String']['input']>;
  deckCards?: InputMaybe<Scalars['String']['input']>;
  fighterType: Scalars['String']['input'];
  hasTokens?: InputMaybe<Scalars['Boolean']['input']>;
  health: Scalars['Int']['input'];
  imageUrl?: InputMaybe<Scalars['String']['input']>;
  miniModelUrl?: InputMaybe<Scalars['String']['input']>;
  movement?: InputMaybe<Scalars['Int']['input']>;
  name: Scalars['String']['input'];
  nameEn: Scalars['String']['input'];
  nameRu: Scalars['String']['input'];
  properties?: InputMaybe<Scalars['String']['input']>;
  set: Scalars['String']['input'];
  sidekicks?: InputMaybe<Scalars['String']['input']>;
};

/** Timing when a card effect activates */
export enum EffectTiming {
  AfterCombat = 'AFTER_COMBAT',
  DuringCombat = 'DURING_COMBAT',
  EndOfTurn = 'END_OF_TURN',
  Immediately = 'IMMEDIATELY',
  StartOfTurn = 'START_OF_TURN',
  WhenAttacked = 'WHEN_ATTACKED',
  WhenDefending = 'WHEN_DEFENDING',
  WhenPlayed = 'WHEN_PLAYED'
}

export type EndTurnDto = {
  gameId: Scalars['String']['input'];
};

export type EventsSinceResponse = {
  __typename?: 'EventsSinceResponse';
  events: Array<GameEvent>;
  gameId: Scalars['String']['output'];
  hasMore: Scalars['Boolean']['output'];
  lastSequence: Scalars['Int']['output'];
};

export type FavoriteHero = {
  __typename?: 'FavoriteHero';
  id: Scalars['String']['output'];
  name: Scalars['String']['output'];
  nameEn: Scalars['String']['output'];
  nameRu: Scalars['String']['output'];
};

/** Type of a fighter in the game */
export enum FighterType {
  Hero = 'HERO',
  Sidekick = 'SIDEKICK'
}

export type GameEdge = {
  __typename?: 'GameEdge';
  cursor: Scalars['String']['output'];
  node?: Maybe<GameResponse>;
};

export type GameEvent = {
  __typename?: 'GameEvent';
  gameId: Scalars['String']['output'];
  payload?: Maybe<Scalars['String']['output']>;
  sequenceNumber: Scalars['Int']['output'];
  timestamp: Scalars['DateTime']['output'];
  type: GameEventType;
};

/** Типы игровых событий */
export enum GameEventType {
  AttackInitiated = 'ATTACK_INITIATED',
  CardDiscarded = 'CARD_DISCARDED',
  CardPlayed = 'CARD_PLAYED',
  CombatResolved = 'COMBAT_RESOLVED',
  DefensePlayed = 'DEFENSE_PLAYED',
  DoorToggled = 'DOOR_TOGGLED',
  EffectApplied = 'EFFECT_APPLIED',
  FighterMoved = 'FIGHTER_MOVED',
  GameAborted = 'GAME_ABORTED',
  GameCreated = 'GAME_CREATED',
  GameEnded = 'GAME_ENDED',
  GameJoined = 'GAME_JOINED',
  GameStarted = 'GAME_STARTED',
  Maneuver = 'MANEUVER',
  Passed = 'PASSED',
  Placed = 'PLACED',
  PlayerJoined = 'PLAYER_JOINED',
  PlayerLeft = 'PLAYER_LEFT',
  SpecialAbility = 'SPECIAL_ABILITY',
  TurnChanged = 'TURN_CHANGED',
  TurnEnded = 'TURN_ENDED',
  TurnStarted = 'TURN_STARTED'
}

export type GameFiltersDto = {
  limit?: InputMaybe<Scalars['Float']['input']>;
  mode?: InputMaybe<GameMode>;
  offset?: InputMaybe<Scalars['Float']['input']>;
  status?: InputMaybe<GameStatus>;
};

export type GameListItemDto = {
  __typename?: 'GameListItemDto';
  boardId?: Maybe<Scalars['String']['output']>;
  boardName?: Maybe<Scalars['String']['output']>;
  code?: Maybe<Scalars['String']['output']>;
  createdAt: Scalars['DateTime']['output'];
  gamePlayers: Array<GamePlayerInfoDto>;
  id: Scalars['String']['output'];
  mode: Scalars['String']['output'];
  status: Scalars['String']['output'];
};

/** Game mode options */
export enum GameMode {
  FreeForAll = 'FREE_FOR_ALL',
  OneVOne = 'ONE_V_ONE',
  TwoVTwo = 'TWO_V_TWO',
  VsAi = 'VS_AI'
}

export type GameMutationResult = {
  __typename?: 'GameMutationResult';
  currentTurnPlayerId?: Maybe<Scalars['String']['output']>;
  phase: GamePhase;
  sequenceNumber: Scalars['Int']['output'];
  state?: Maybe<Scalars['String']['output']>;
  timestamp: Scalars['DateTime']['output'];
  turnCount: Scalars['Int']['output'];
};

/** Game phase options */
export enum GamePhase {
  ActionAttack = 'ACTION_ATTACK',
  ActionManeuver = 'ACTION_MANEUVER',
  Combat = 'COMBAT',
  CombatResolve = 'COMBAT_RESOLVE',
  GameOver = 'GAME_OVER',
  Setup = 'SETUP',
  TurnEnd = 'TURN_END',
  TurnStart = 'TURN_START'
}

export type GamePlayerInfoDto = {
  __typename?: 'GamePlayerInfoDto';
  avatar?: Maybe<Scalars['String']['output']>;
  heroId?: Maybe<Scalars['String']['output']>;
  id: Scalars['String']['output'];
  playerId: Scalars['String']['output'];
  status: Scalars['String']['output'];
  username?: Maybe<Scalars['String']['output']>;
};

export type GamePlayerResponse = {
  __typename?: 'GamePlayerResponse';
  avatar?: Maybe<Scalars['String']['output']>;
  hasPassed: Scalars['Boolean']['output'];
  heroId?: Maybe<Scalars['String']['output']>;
  id: Scalars['String']['output'];
  isReady: Scalars['Boolean']['output'];
  seatOrder: Scalars['Float']['output'];
  userId: Scalars['String']['output'];
  username: Scalars['String']['output'];
};

export type GameResponse = {
  __typename?: 'GameResponse';
  boardId: Scalars['String']['output'];
  boardState?: Maybe<Scalars['String']['output']>;
  code?: Maybe<Scalars['String']['output']>;
  createdAt: Scalars['DateTime']['output'];
  currentTurn?: Maybe<Scalars['Int']['output']>;
  endedAt?: Maybe<Scalars['DateTime']['output']>;
  host: GamePlayerResponse;
  hostId: Scalars['String']['output'];
  id: Scalars['String']['output'];
  mode: GameMode;
  opponent?: Maybe<GamePlayerResponse>;
  opponentId?: Maybe<Scalars['String']['output']>;
  phase?: Maybe<GamePhase>;
  players: Array<GamePlayerResponse>;
  startedAt?: Maybe<Scalars['DateTime']['output']>;
  status: GameStatus;
  updatedAt: Scalars['DateTime']['output'];
  version: Scalars['Float']['output'];
  winnerId?: Maybe<Scalars['String']['output']>;
};

export type GameState = {
  __typename?: 'GameState';
  boardState?: Maybe<Scalars['String']['output']>;
  currentTurnPlayerId: Scalars['String']['output'];
  fighters?: Maybe<Scalars['String']['output']>;
  gameId: Scalars['String']['output'];
  handZones?: Maybe<Scalars['String']['output']>;
  metadata?: Maybe<Scalars['String']['output']>;
  phase: GamePhase;
  players?: Maybe<Scalars['String']['output']>;
  sequenceNumber: Scalars['Int']['output'];
  turnCount: Scalars['Int']['output'];
};

export type GameStateResponse = {
  __typename?: 'GameStateResponse';
  currentTurnPlayerId?: Maybe<Scalars['String']['output']>;
  gameId: Scalars['String']['output'];
  id: Scalars['String']['output'];
  phase: Scalars['String']['output'];
  sequenceNumber: Scalars['Float']['output'];
  state: Scalars['String']['output'];
  turnCount: Scalars['Float']['output'];
  updatedAt: Scalars['DateTime']['output'];
};

/** Game status options */
export enum GameStatus {
  Aborted = 'ABORTED',
  Finished = 'FINISHED',
  InProgress = 'IN_PROGRESS',
  Lobby = 'LOBBY',
  Paused = 'PAUSED',
  Pending = 'PENDING'
}

export type GamesPaginatedDto = {
  __typename?: 'GamesPaginatedDto';
  items: Array<GameListItemDto>;
  limit: Scalars['Float']['output'];
  page: Scalars['Float']['output'];
  total: Scalars['Float']['output'];
  totalPages: Scalars['Float']['output'];
};

export type HeartbeatInput = {
  currentGameId?: InputMaybe<Scalars['String']['input']>;
  status?: InputMaybe<PresenceStatus>;
};

export type HeartbeatResponse = {
  __typename?: 'HeartbeatResponse';
  presence: Presence;
  ttl: Scalars['Float']['output'];
};

export type Hero = {
  __typename?: 'Hero';
  abilities: Array<HeroAbility>;
  avatarUrl?: Maybe<Scalars['String']['output']>;
  cards: Array<Card>;
  createdAt?: Maybe<Scalars['DateTime']['output']>;
  fighterType: FighterType;
  health: Scalars['Int']['output'];
  id: Scalars['String']['output'];
  imageUrl?: Maybe<Scalars['String']['output']>;
  movement: Scalars['Int']['output'];
  name: Scalars['String']['output'];
  nameEn?: Maybe<Scalars['String']['output']>;
  nameRu?: Maybe<Scalars['String']['output']>;
  set: Scalars['String']['output'];
  sidekickCount?: Maybe<Scalars['Int']['output']>;
  sidekickHealth?: Maybe<Scalars['Int']['output']>;
  updatedAt?: Maybe<Scalars['DateTime']['output']>;
  urls?: Maybe<HeroUrls>;
};

export type HeroAbility = {
  __typename?: 'HeroAbility';
  id: Scalars['String']['output'];
  name: Scalars['String']['output'];
  text: Scalars['String']['output'];
  trigger: AbilityTrigger;
};

export type HeroListItemDto = {
  __typename?: 'HeroListItemDto';
  ability?: Maybe<Scalars['String']['output']>;
  avatarUrl?: Maybe<Scalars['String']['output']>;
  createdAt: Scalars['DateTime']['output'];
  fighterType: Scalars['String']['output'];
  health: Scalars['Float']['output'];
  id: Scalars['String']['output'];
  imageUrl?: Maybe<Scalars['String']['output']>;
  name: Scalars['String']['output'];
  nameEn: Scalars['String']['output'];
  nameRu: Scalars['String']['output'];
  set: Scalars['String']['output'];
};

export type HeroUrls = {
  __typename?: 'HeroUrls';
  avatar: Scalars['String']['output'];
  cardCover: Scalars['String']['output'];
  mini: Scalars['String']['output'];
};

export type HeroesPaginatedDto = {
  __typename?: 'HeroesPaginatedDto';
  items: Array<HeroListItemDto>;
  limit: Scalars['Float']['output'];
  page: Scalars['Float']['output'];
  total: Scalars['Float']['output'];
  totalPages: Scalars['Float']['output'];
};

export type JoinGameDto = {
  asOpponent?: InputMaybe<Scalars['Boolean']['input']>;
  gameId: Scalars['String']['input'];
  heroId?: InputMaybe<Scalars['String']['input']>;
};

export type JoinQueueDto = {
  heroPref?: InputMaybe<Scalars['String']['input']>;
  mode: GameMode;
};

export type LeaderboardRankResponse = {
  __typename?: 'LeaderboardRankResponse';
  elo: Scalars['Int']['output'];
  heroId?: Maybe<Scalars['String']['output']>;
  rank: Scalars['Int']['output'];
  timeFrame: Scalars['String']['output'];
  userId: Scalars['String']['output'];
};

export type LeaderboardUser = {
  __typename?: 'LeaderboardUser';
  avatar?: Maybe<Scalars['String']['output']>;
  id: Scalars['String']['output'];
  username: Scalars['String']['output'];
};

export type LoginDto = {
  email: Scalars['String']['input'];
  password: Scalars['String']['input'];
};

export type ManeuverDto = {
  boostCardId?: InputMaybe<Scalars['String']['input']>;
  cardId?: InputMaybe<Scalars['String']['input']>;
  fighterId?: InputMaybe<Scalars['String']['input']>;
  gameId: Scalars['String']['input'];
  moves?: InputMaybe<Array<ManeuverMoveInput>>;
  path?: InputMaybe<Array<PositionInput>>;
};

export type ManeuverMoveInput = {
  fighterId: Scalars['String']['input'];
  path: Array<PositionInput>;
};

export type MatchFoundResponse = {
  __typename?: 'MatchFoundResponse';
  expiresAt: Scalars['DateTime']['output'];
  gameId: Scalars['String']['output'];
  mode: Scalars['String']['output'];
  opponentId: Scalars['String']['output'];
  opponentRating: Scalars['Int']['output'];
  opponentUsername: Scalars['String']['output'];
};

export type MatchmakingQueueDto = {
  __typename?: 'MatchmakingQueueDto';
  activeQueues: Scalars['Float']['output'];
  items: Array<QueuePlayerDto>;
  total: Scalars['Float']['output'];
};

export type MoveFighterDto = {
  fighterId: Scalars['String']['input'];
  gameId: Scalars['String']['input'];
  x: Scalars['Int']['input'];
  y: Scalars['Int']['input'];
};

export type Mutation = {
  __typename?: 'Mutation';
  abortGame: GameResponse;
  acceptMatch: Scalars['Boolean']['output'];
  /** Объявить атаку на соседнего бойца (тратит 1 действие) */
  attack: GameMutationResult;
  banUser: Scalars['Boolean']['output'];
  changePassword: Scalars['Boolean']['output'];
  cleanupGames: CleanupGamesResultDto;
  createBoard: AdminBoard;
  createCard: AdminCard;
  createGame: GameResponse;
  createHero: AdminHero;
  declineMatch: Scalars['Boolean']['output'];
  deleteAccount: Scalars['Boolean']['output'];
  deleteBoard: Scalars['Boolean']['output'];
  deleteCard: Scalars['Boolean']['output'];
  deleteHero: Scalars['Boolean']['output'];
  /** Завершить текущий ход */
  endTurn: GameMutationResult;
  heartbeat: HeartbeatResponse;
  joinGame: GameResponse;
  joinQueue: QueueStatusResponse;
  leaveAllQueues: Scalars['Boolean']['output'];
  leaveGame: Scalars['Boolean']['output'];
  leaveQueue: Scalars['Boolean']['output'];
  login: AuthResponseDto;
  logout: Scalars['Boolean']['output'];
  /** Переместить бойца и сыграть карту эффектов (тратит 1 действие) */
  maneuver: GameMutationResult;
  /** Переместить бойца на указанную клетку (тратит 1 действие) */
  moveFighter: GameMutationResult;
  /** Сбросить карту и получить дополнительное действие */
  pass: GameMutationResult;
  /** Сыграть карту защиты в ответ на атаку */
  playDefense: GameMutationResult;
  /** Разыграть scheme-карту из руки (тратит 1 действие) */
  playScheme: GameMutationResult;
  refreshTokens: AuthResponseDto;
  register: AuthResponseDto;
  removeAvatar: Scalars['Boolean']['output'];
  resetPassword: Scalars['Boolean']['output'];
  /** Разрешить бой и нанести урон */
  resolveCombat: GameMutationResult;
  /** Выбор бойца/клетки для отложенного эффекта карты (MOVE/PLACE) */
  resolvePendingEffect: GameMutationResult;
  selectHero: GameResponse;
  /** Сменить стойку героя (STANCE: Alice big/small, Muhammad Ali float/sting) */
  setStance: GameMutationResult;
  startGame: GameResponse;
  /** Открыть или закрыть дверь */
  toggleDoor: GameMutationResult;
  toggleReady: GameResponse;
  unbanUser: Scalars['Boolean']['output'];
  updateBoard: AdminBoard;
  updateCard: AdminCard;
  updateHero: AdminHero;
  updateProfile: UserResponse;
  updateSettings: UserSettingsGraphql;
  updateUser: UserDto;
  uploadAvatar: Scalars['String']['output'];
  verifyEmail: Scalars['Boolean']['output'];
};


export type MutationAbortGameArgs = {
  gameId: Scalars['String']['input'];
};


export type MutationAcceptMatchArgs = {
  gameId: Scalars['String']['input'];
};


export type MutationAttackArgs = {
  input: AttackDto;
};


export type MutationBanUserArgs = {
  id: Scalars['String']['input'];
};


export type MutationChangePasswordArgs = {
  input: ChangePasswordDto;
};


export type MutationCleanupGamesArgs = {
  input?: InputMaybe<CleanupGamesInput>;
};


export type MutationCreateBoardArgs = {
  input: CreateBoardInput;
};


export type MutationCreateCardArgs = {
  input: CreateCardInput;
};


export type MutationCreateGameArgs = {
  idempotencyKey?: InputMaybe<Scalars['String']['input']>;
  input: CreateGameDto;
};


export type MutationCreateHeroArgs = {
  input: CreateHeroInput;
};


export type MutationDeclineMatchArgs = {
  gameId: Scalars['String']['input'];
};


export type MutationDeleteBoardArgs = {
  id: Scalars['String']['input'];
};


export type MutationDeleteCardArgs = {
  id: Scalars['String']['input'];
};


export type MutationDeleteHeroArgs = {
  id: Scalars['String']['input'];
};


export type MutationEndTurnArgs = {
  input: EndTurnDto;
};


export type MutationHeartbeatArgs = {
  input: HeartbeatInput;
};


export type MutationJoinGameArgs = {
  input: JoinGameDto;
};


export type MutationJoinQueueArgs = {
  input: JoinQueueDto;
};


export type MutationLeaveGameArgs = {
  gameId: Scalars['String']['input'];
};


export type MutationLeaveQueueArgs = {
  mode: Scalars['String']['input'];
};


export type MutationLoginArgs = {
  input: LoginDto;
};


export type MutationManeuverArgs = {
  input: ManeuverDto;
};


export type MutationMoveFighterArgs = {
  input: MoveFighterDto;
};


export type MutationPassArgs = {
  input: PassDto;
};


export type MutationPlayDefenseArgs = {
  input: PlayDefenseDto;
};


export type MutationPlaySchemeArgs = {
  input: PlaySchemeDto;
};


export type MutationRefreshTokensArgs = {
  refreshToken: Scalars['String']['input'];
};


export type MutationRegisterArgs = {
  input: RegisterDto;
};


export type MutationResetPasswordArgs = {
  newPassword: Scalars['String']['input'];
  token: Scalars['String']['input'];
};


export type MutationResolveCombatArgs = {
  input: ResolveCombatDto;
};


export type MutationResolvePendingEffectArgs = {
  input: ResolvePendingEffectDto;
};


export type MutationSelectHeroArgs = {
  gameId: Scalars['String']['input'];
  heroId: Scalars['String']['input'];
};


export type MutationSetStanceArgs = {
  input: SetStanceDto;
};


export type MutationStartGameArgs = {
  gameId: Scalars['String']['input'];
};


export type MutationToggleDoorArgs = {
  input: ToggleDoorDto;
};


export type MutationToggleReadyArgs = {
  gameId: Scalars['String']['input'];
};


export type MutationUnbanUserArgs = {
  id: Scalars['String']['input'];
};


export type MutationUpdateBoardArgs = {
  id: Scalars['String']['input'];
  input: UpdateBoardInput;
};


export type MutationUpdateCardArgs = {
  id: Scalars['String']['input'];
  input: UpdateCardInput;
};


export type MutationUpdateHeroArgs = {
  id: Scalars['String']['input'];
  input: UpdateHeroInput;
};


export type MutationUpdateProfileArgs = {
  input: UpdateProfileDto;
};


export type MutationUpdateSettingsArgs = {
  input: SettingsDto;
};


export type MutationUpdateUserArgs = {
  id: Scalars['String']['input'];
  input: UpdateUserInput;
};


export type MutationUploadAvatarArgs = {
  fileUrl: Scalars['String']['input'];
};


export type MutationVerifyEmailArgs = {
  token: Scalars['String']['input'];
};

export type OnlineUsersResponse = {
  __typename?: 'OnlineUsersResponse';
  count: Scalars['Float']['output'];
  userIds: Array<Scalars['String']['output']>;
};

export type PageInfo = {
  __typename?: 'PageInfo';
  endCursor?: Maybe<Scalars['String']['output']>;
  hasNextPage: Scalars['Boolean']['output'];
  hasPreviousPage: Scalars['Boolean']['output'];
  startCursor?: Maybe<Scalars['String']['output']>;
  totalCount: Scalars['Float']['output'];
};

export type PaginatedBoards = {
  __typename?: 'PaginatedBoards';
  items: Array<Board>;
  pagination: PaginationInfo;
};

export type PaginatedHeroes = {
  __typename?: 'PaginatedHeroes';
  items: Array<Hero>;
  pagination: PaginationInfo;
};

export type PaginatedUsersDto = {
  __typename?: 'PaginatedUsersDto';
  limit: Scalars['Float']['output'];
  page: Scalars['Float']['output'];
  total: Scalars['Float']['output'];
  totalPages: Scalars['Float']['output'];
  users: Array<UserListItemDto>;
};

export type PaginationInfo = {
  __typename?: 'PaginationInfo';
  hasNextPage: Scalars['Boolean']['output'];
  hasPreviousPage: Scalars['Boolean']['output'];
  limit: Scalars['Int']['output'];
  page: Scalars['Int']['output'];
  total: Scalars['Int']['output'];
  totalPages: Scalars['Int']['output'];
};

export type PassDto = {
  gameId: Scalars['String']['input'];
};

export type PenaltyInfoDto = {
  __typename?: 'PenaltyInfoDto';
  canJoinQueue: Scalars['Boolean']['output'];
  declineCount: Scalars['Int']['output'];
  penaltyElo?: Maybe<Scalars['Int']['output']>;
  reason?: Maybe<Scalars['String']['output']>;
  tempBanUntil?: Maybe<Scalars['DateTime']['output']>;
};

export type PlayDefenseDto = {
  boostCardId?: InputMaybe<Scalars['String']['input']>;
  cardId: Scalars['String']['input'];
  gameId: Scalars['String']['input'];
};

export type PlaySchemeDto = {
  cardId: Scalars['String']['input'];
  gameId: Scalars['String']['input'];
};

export type Position = {
  __typename?: 'Position';
  x: Scalars['Int']['output'];
  y: Scalars['Int']['output'];
};

export type PositionInput = {
  x: Scalars['Int']['input'];
  y: Scalars['Int']['input'];
};

export type Presence = {
  __typename?: 'Presence';
  currentGameId?: Maybe<Scalars['String']['output']>;
  lastSeenAt: Scalars['Float']['output'];
  status: PresenceStatus;
  userId: Scalars['String']['output'];
};

/** Status of user presence */
export enum PresenceStatus {
  Ingame = 'INGAME',
  Inqueue = 'INQUEUE',
  Offline = 'OFFLINE',
  Online = 'ONLINE'
}

export type PublicUserResponse = {
  __typename?: 'PublicUserResponse';
  avatar?: Maybe<Scalars['String']['output']>;
  createdAt: Scalars['DateTime']['output'];
  id: Scalars['String']['output'];
  username: Scalars['String']['output'];
};

export type Query = {
  __typename?: 'Query';
  adminBoard: AdminBoard;
  adminCard: AdminCard;
  adminGame: AdminGameDto;
  adminHero: AdminHero;
  adminStats: AdminStatsDto;
  adminUser: UserDto;
  allQueueStatus: Scalars['String']['output'];
  auditLogs: AuditLogsPaginatedDto;
  availableGames: Array<GameResponse>;
  board?: Maybe<Board>;
  boardList: BoardsPaginatedDto;
  boards: Array<Board>;
  boardsList: BoardsPaginatedDto;
  boardsPaginated: PaginatedBoards;
  card?: Maybe<Card>;
  cardList: CardsPaginatedDto;
  cards: Array<Card>;
  cardsList: CardsPaginatedDto;
  clearContentCache: Scalars['Boolean']['output'];
  contentSummary: ContentSummary;
  contentVersion: Scalars['String']['output'];
  eventsSince?: Maybe<EventsSinceResponse>;
  game?: Maybe<GameResponse>;
  gameList: GamesPaginatedDto;
  gameSequence?: Maybe<Scalars['Float']['output']>;
  gameState?: Maybe<GameStateResponse>;
  gamesList: GamesPaginatedDto;
  getOnlineCount: Scalars['Float']['output'];
  getOnlineUsers: OnlineUsersResponse;
  getPlayerRank: LeaderboardRankResponse;
  getPresence?: Maybe<Presence>;
  hero?: Maybe<Hero>;
  heroList: HeroesPaginatedDto;
  heroStances: Array<StanceOptionDto>;
  heroes: Array<Hero>;
  heroesBySet: Array<Hero>;
  heroesList: HeroesPaginatedDto;
  heroesPaginated: PaginatedHeroes;
  leaderboard: Scalars['String']['output'];
  matchmakingQueue: MatchmakingQueueDto;
  me?: Maybe<UserWithSettingsResponse>;
  metrics: Scalars['String']['output'];
  myGames: Array<GameResponse>;
  mySettings: UserSettingsGraphql;
  myStats: UserStatsResponse;
  penaltyInfo: PenaltyInfoDto;
  queueStatus: QueueStatusResponse;
  sets: Array<Scalars['String']['output']>;
  stats?: Maybe<UserStatsResponse>;
  topPlayers: Scalars['String']['output'];
  user?: Maybe<PublicUserResponse>;
  userByUsername?: Maybe<PublicUserResponse>;
  userList: PaginatedUsersDto;
  usersList: PaginatedUsersDto;
};


export type QueryAdminBoardArgs = {
  id: Scalars['String']['input'];
};


export type QueryAdminCardArgs = {
  id: Scalars['String']['input'];
};


export type QueryAdminGameArgs = {
  id: Scalars['String']['input'];
};


export type QueryAdminHeroArgs = {
  id: Scalars['String']['input'];
};


export type QueryAdminUserArgs = {
  id: Scalars['String']['input'];
};


export type QueryAuditLogsArgs = {
  limit?: InputMaybe<Scalars['Int']['input']>;
  page?: InputMaybe<Scalars['Int']['input']>;
  userId?: InputMaybe<Scalars['String']['input']>;
};


export type QueryAvailableGamesArgs = {
  limit?: InputMaybe<Scalars['Float']['input']>;
  mode?: InputMaybe<Scalars['String']['input']>;
};


export type QueryBoardArgs = {
  id: Scalars['String']['input'];
};


export type QueryBoardListArgs = {
  limit?: InputMaybe<Scalars['Int']['input']>;
  page?: InputMaybe<Scalars['Int']['input']>;
  search?: InputMaybe<Scalars['String']['input']>;
  sortBy?: InputMaybe<Scalars['String']['input']>;
  sortOrder?: InputMaybe<Scalars['String']['input']>;
};


export type QueryBoardsListArgs = {
  limit?: InputMaybe<Scalars['Int']['input']>;
  page?: InputMaybe<Scalars['Int']['input']>;
  search?: InputMaybe<Scalars['String']['input']>;
  sortBy?: InputMaybe<Scalars['String']['input']>;
  sortOrder?: InputMaybe<Scalars['String']['input']>;
};


export type QueryBoardsPaginatedArgs = {
  limit?: InputMaybe<Scalars['Int']['input']>;
  page?: InputMaybe<Scalars['Int']['input']>;
};


export type QueryCardArgs = {
  id: Scalars['String']['input'];
};


export type QueryCardListArgs = {
  heroId?: InputMaybe<Scalars['String']['input']>;
  limit?: InputMaybe<Scalars['Int']['input']>;
  page?: InputMaybe<Scalars['Int']['input']>;
  search?: InputMaybe<Scalars['String']['input']>;
  sortBy?: InputMaybe<Scalars['String']['input']>;
  sortOrder?: InputMaybe<Scalars['String']['input']>;
};


export type QueryCardsArgs = {
  heroId: Scalars['String']['input'];
};


export type QueryCardsListArgs = {
  heroId?: InputMaybe<Scalars['String']['input']>;
  limit?: InputMaybe<Scalars['Int']['input']>;
  page?: InputMaybe<Scalars['Int']['input']>;
  search?: InputMaybe<Scalars['String']['input']>;
  sortBy?: InputMaybe<Scalars['String']['input']>;
  sortOrder?: InputMaybe<Scalars['String']['input']>;
};


export type QueryEventsSinceArgs = {
  gameId: Scalars['String']['input'];
  sinceSequence: Scalars['Float']['input'];
};


export type QueryGameArgs = {
  id: Scalars['String']['input'];
};


export type QueryGameListArgs = {
  limit?: InputMaybe<Scalars['Int']['input']>;
  page?: InputMaybe<Scalars['Int']['input']>;
  search?: InputMaybe<Scalars['String']['input']>;
  sortBy?: InputMaybe<Scalars['String']['input']>;
  sortOrder?: InputMaybe<Scalars['String']['input']>;
};


export type QueryGameSequenceArgs = {
  gameId: Scalars['String']['input'];
};


export type QueryGameStateArgs = {
  gameId: Scalars['String']['input'];
};


export type QueryGamesListArgs = {
  limit?: InputMaybe<Scalars['Int']['input']>;
  page?: InputMaybe<Scalars['Int']['input']>;
  search?: InputMaybe<Scalars['String']['input']>;
  sortBy?: InputMaybe<Scalars['String']['input']>;
  sortOrder?: InputMaybe<Scalars['String']['input']>;
};


export type QueryGetPlayerRankArgs = {
  heroId?: InputMaybe<Scalars['String']['input']>;
  timeFrame?: InputMaybe<Scalars['String']['input']>;
  userId: Scalars['String']['input'];
};


export type QueryGetPresenceArgs = {
  userId: Scalars['String']['input'];
};


export type QueryHeroArgs = {
  id: Scalars['String']['input'];
};


export type QueryHeroListArgs = {
  limit?: InputMaybe<Scalars['Int']['input']>;
  page?: InputMaybe<Scalars['Int']['input']>;
  search?: InputMaybe<Scalars['String']['input']>;
  sortBy?: InputMaybe<Scalars['String']['input']>;
  sortOrder?: InputMaybe<Scalars['String']['input']>;
};


export type QueryHeroStancesArgs = {
  heroSlug: Scalars['String']['input'];
};


export type QueryHeroesBySetArgs = {
  set: Scalars['String']['input'];
};


export type QueryHeroesListArgs = {
  limit?: InputMaybe<Scalars['Int']['input']>;
  page?: InputMaybe<Scalars['Int']['input']>;
  search?: InputMaybe<Scalars['String']['input']>;
  sortBy?: InputMaybe<Scalars['String']['input']>;
  sortOrder?: InputMaybe<Scalars['String']['input']>;
};


export type QueryHeroesPaginatedArgs = {
  limit?: InputMaybe<Scalars['Int']['input']>;
  page?: InputMaybe<Scalars['Int']['input']>;
  set?: InputMaybe<Scalars['String']['input']>;
};


export type QueryLeaderboardArgs = {
  heroId?: InputMaybe<Scalars['String']['input']>;
  page?: InputMaybe<Scalars['Int']['input']>;
  pageSize?: InputMaybe<Scalars['Int']['input']>;
  timeFrame?: InputMaybe<TimeFrame>;
};


export type QueryMyGamesArgs = {
  filters?: InputMaybe<GameFiltersDto>;
};


export type QueryQueueStatusArgs = {
  mode: Scalars['String']['input'];
};


export type QueryStatsArgs = {
  userId: Scalars['String']['input'];
};


export type QueryTopPlayersArgs = {
  limit?: InputMaybe<Scalars['Int']['input']>;
  timeFrame?: InputMaybe<Scalars['String']['input']>;
};


export type QueryUserArgs = {
  id: Scalars['String']['input'];
};


export type QueryUserByUsernameArgs = {
  username: Scalars['String']['input'];
};


export type QueryUserListArgs = {
  limit?: InputMaybe<Scalars['Int']['input']>;
  page?: InputMaybe<Scalars['Int']['input']>;
  search?: InputMaybe<Scalars['String']['input']>;
  sortBy?: InputMaybe<Scalars['String']['input']>;
  sortOrder?: InputMaybe<Scalars['String']['input']>;
};


export type QueryUsersListArgs = {
  limit?: InputMaybe<Scalars['Int']['input']>;
  page?: InputMaybe<Scalars['Int']['input']>;
  search?: InputMaybe<Scalars['String']['input']>;
  sortBy?: InputMaybe<Scalars['String']['input']>;
  sortOrder?: InputMaybe<Scalars['String']['input']>;
};

export type QueuePlayerDto = {
  __typename?: 'QueuePlayerDto';
  avatar?: Maybe<Scalars['String']['output']>;
  elo: Scalars['Int']['output'];
  id: Scalars['String']['output'];
  joinedAt: Scalars['DateTime']['output'];
  mode: Scalars['String']['output'];
  position: Scalars['Int']['output'];
  userId: Scalars['String']['output'];
  username: Scalars['String']['output'];
};

export type QueueStatusResponse = {
  __typename?: 'QueueStatusResponse';
  estimatedWaitTime: Scalars['Int']['output'];
  inQueue: Scalars['Boolean']['output'];
  joinedAt?: Maybe<Scalars['DateTime']['output']>;
  mode?: Maybe<Scalars['String']['output']>;
  position?: Maybe<Scalars['Int']['output']>;
  totalPlayers: Scalars['Int']['output'];
};

export type RegisterDto = {
  email: Scalars['String']['input'];
  password: Scalars['String']['input'];
  username: Scalars['String']['input'];
};

export type ResolveCombatDto = {
  gameId: Scalars['String']['input'];
};

export type ResolvePendingEffectDto = {
  effectId: Scalars['String']['input'];
  fighterId?: InputMaybe<Scalars['String']['input']>;
  gameId: Scalars['String']['input'];
  optionIndex?: InputMaybe<Scalars['Int']['input']>;
  x?: InputMaybe<Scalars['Int']['input']>;
  y?: InputMaybe<Scalars['Int']['input']>;
};

export type SetStanceDto = {
  gameId: Scalars['String']['input'];
  stanceId: Scalars['String']['input'];
};

export type SettingsDto = {
  language?: InputMaybe<Scalars['String']['input']>;
  musicEnabled?: InputMaybe<Scalars['Boolean']['input']>;
  profileVisible?: InputMaybe<Scalars['Boolean']['input']>;
  showOnlineStatus?: InputMaybe<Scalars['Boolean']['input']>;
  soundEnabled?: InputMaybe<Scalars['Boolean']['input']>;
  theme?: InputMaybe<Scalars['String']['input']>;
};

export type StanceOptionDto = {
  __typename?: 'StanceOptionDto';
  id: Scalars['String']['output'];
  isDefault: Scalars['Boolean']['output'];
  label: Scalars['String']['output'];
};

export type Subscription = {
  __typename?: 'Subscription';
  attackInitiated: GameEvent;
  combatResolved: GameEvent;
  defensePlayed: GameEvent;
  gameEnded: GameEvent;
  gameStateUpdated: GameState;
  matchFound: MatchFoundResponse;
  playerJoined: GameEvent;
  playerLeft: GameEvent;
  presenceUpdated: Presence;
  turnChanged: TurnState;
};


export type SubscriptionAttackInitiatedArgs = {
  gameId: Scalars['String']['input'];
};


export type SubscriptionCombatResolvedArgs = {
  gameId: Scalars['String']['input'];
};


export type SubscriptionDefensePlayedArgs = {
  gameId: Scalars['String']['input'];
};


export type SubscriptionGameEndedArgs = {
  gameId: Scalars['String']['input'];
};


export type SubscriptionGameStateUpdatedArgs = {
  gameId: Scalars['String']['input'];
  since?: InputMaybe<Scalars['Float']['input']>;
  userId?: InputMaybe<Scalars['String']['input']>;
};


export type SubscriptionMatchFoundArgs = {
  userId: Scalars['String']['input'];
};


export type SubscriptionPlayerJoinedArgs = {
  gameId: Scalars['String']['input'];
};


export type SubscriptionPlayerLeftArgs = {
  gameId: Scalars['String']['input'];
};


export type SubscriptionPresenceUpdatedArgs = {
  userIds?: InputMaybe<Array<Scalars['String']['input']>>;
};


export type SubscriptionTurnChangedArgs = {
  gameId: Scalars['String']['input'];
};

/** Временной период для статистики */
export enum TimeFrame {
  All = 'ALL',
  Month = 'MONTH',
  Week = 'WEEK'
}

export type ToggleDoorDto = {
  gameId: Scalars['String']['input'];
  x: Scalars['Int']['input'];
  y: Scalars['Int']['input'];
};

export type TurnState = {
  __typename?: 'TurnState';
  phase: GamePhase;
  playerId: Scalars['String']['output'];
  turnCount: Scalars['Int']['output'];
};

export type UpdateBoardInput = {
  cells?: InputMaybe<Scalars['String']['input']>;
  features?: InputMaybe<Scalars['String']['input']>;
  height?: InputMaybe<Scalars['Int']['input']>;
  imageUrl?: InputMaybe<Scalars['String']['input']>;
  imageUrlDark?: InputMaybe<Scalars['String']['input']>;
  name?: InputMaybe<Scalars['String']['input']>;
  nameEn?: InputMaybe<Scalars['String']['input']>;
  nameRu?: InputMaybe<Scalars['String']['input']>;
  set?: InputMaybe<Scalars['String']['input']>;
  width?: InputMaybe<Scalars['Int']['input']>;
};

export type UpdateCardInput = {
  attackValue?: InputMaybe<Scalars['Int']['input']>;
  bannerName?: InputMaybe<Scalars['String']['input']>;
  boostValue?: InputMaybe<Scalars['Int']['input']>;
  cardType?: InputMaybe<Scalars['String']['input']>;
  count?: InputMaybe<Scalars['Int']['input']>;
  defenseValue?: InputMaybe<Scalars['Int']['input']>;
  effectAfter?: InputMaybe<Scalars['String']['input']>;
  effectBoost?: InputMaybe<Scalars['String']['input']>;
  effectDuring?: InputMaybe<Scalars['String']['input']>;
  effectImmediately?: InputMaybe<Scalars['String']['input']>;
  effectOngoing?: InputMaybe<Scalars['String']['input']>;
  effects?: InputMaybe<Scalars['String']['input']>;
  heroId?: InputMaybe<Scalars['String']['input']>;
  imageUrl?: InputMaybe<Scalars['String']['input']>;
  imageUrlRu?: InputMaybe<Scalars['String']['input']>;
  name?: InputMaybe<Scalars['String']['input']>;
  nameEn?: InputMaybe<Scalars['String']['input']>;
  nameRu?: InputMaybe<Scalars['String']['input']>;
  subType?: InputMaybe<Scalars['String']['input']>;
  text?: InputMaybe<Scalars['String']['input']>;
  textEn?: InputMaybe<Scalars['String']['input']>;
  textRu?: InputMaybe<Scalars['String']['input']>;
};

export type UpdateHeroInput = {
  ability?: InputMaybe<Scalars['String']['input']>;
  additionalMinis?: InputMaybe<Scalars['String']['input']>;
  avatarUrl?: InputMaybe<Scalars['String']['input']>;
  characterCardUrl?: InputMaybe<Scalars['String']['input']>;
  color?: InputMaybe<Scalars['String']['input']>;
  deckCards?: InputMaybe<Scalars['String']['input']>;
  fighterType?: InputMaybe<Scalars['String']['input']>;
  hasTokens?: InputMaybe<Scalars['Boolean']['input']>;
  health?: InputMaybe<Scalars['Int']['input']>;
  imageUrl?: InputMaybe<Scalars['String']['input']>;
  miniModelUrl?: InputMaybe<Scalars['String']['input']>;
  movement?: InputMaybe<Scalars['Int']['input']>;
  name?: InputMaybe<Scalars['String']['input']>;
  nameEn?: InputMaybe<Scalars['String']['input']>;
  nameRu?: InputMaybe<Scalars['String']['input']>;
  properties?: InputMaybe<Scalars['String']['input']>;
  set?: InputMaybe<Scalars['String']['input']>;
  sidekicks?: InputMaybe<Scalars['String']['input']>;
};

export type UpdateProfileDto = {
  avatar?: InputMaybe<Scalars['String']['input']>;
  username?: InputMaybe<Scalars['String']['input']>;
};

export type UpdateUserInput = {
  avatar?: InputMaybe<Scalars['String']['input']>;
  email?: InputMaybe<Scalars['String']['input']>;
  role?: InputMaybe<Scalars['String']['input']>;
  username?: InputMaybe<Scalars['String']['input']>;
};

export type UserDto = {
  __typename?: 'UserDto';
  avatar?: Maybe<Scalars['String']['output']>;
  createdAt: Scalars['DateTime']['output'];
  deletedAt?: Maybe<Scalars['DateTime']['output']>;
  email: Scalars['String']['output'];
  emailVerified?: Maybe<Scalars['DateTime']['output']>;
  id: Scalars['String']['output'];
  role: Scalars['String']['output'];
  stats?: Maybe<UserStatsDto>;
  updatedAt: Scalars['DateTime']['output'];
  username: Scalars['String']['output'];
};

export type UserListItemDto = {
  __typename?: 'UserListItemDto';
  avatar?: Maybe<Scalars['String']['output']>;
  createdAt: Scalars['DateTime']['output'];
  deletedAt?: Maybe<Scalars['DateTime']['output']>;
  email: Scalars['String']['output'];
  emailVerified?: Maybe<Scalars['DateTime']['output']>;
  id: Scalars['String']['output'];
  role: Scalars['String']['output'];
  stats?: Maybe<UserStatsDto>;
  updatedAt: Scalars['DateTime']['output'];
  username: Scalars['String']['output'];
};

export type UserResponse = {
  __typename?: 'UserResponse';
  avatar?: Maybe<Scalars['String']['output']>;
  createdAt: Scalars['DateTime']['output'];
  email: Scalars['String']['output'];
  emailVerified?: Maybe<Scalars['DateTime']['output']>;
  id: Scalars['String']['output'];
  role: UserRole;
  username: Scalars['String']['output'];
};

/** User role in the system */
export enum UserRole {
  Admin = 'ADMIN',
  Moderator = 'MODERATOR',
  User = 'USER'
}

export type UserSettingsGraphql = {
  __typename?: 'UserSettingsGraphql';
  id: Scalars['String']['output'];
  language: Scalars['String']['output'];
  musicEnabled: Scalars['Boolean']['output'];
  profileVisible: Scalars['Boolean']['output'];
  showOnlineStatus: Scalars['Boolean']['output'];
  soundEnabled: Scalars['Boolean']['output'];
  theme: Scalars['String']['output'];
};

export type UserSettingsResponse = {
  __typename?: 'UserSettingsResponse';
  id: Scalars['String']['output'];
  language: Scalars['String']['output'];
  musicEnabled: Scalars['Boolean']['output'];
  profileVisible: Scalars['Boolean']['output'];
  showOnlineStatus: Scalars['Boolean']['output'];
  soundEnabled: Scalars['Boolean']['output'];
  theme: Scalars['String']['output'];
};

export type UserStatsDto = {
  __typename?: 'UserStatsDto';
  currentElo?: Maybe<Scalars['Int']['output']>;
  gamesPlayed?: Maybe<Scalars['Int']['output']>;
  gamesWon?: Maybe<Scalars['Int']['output']>;
};

export type UserStatsResponse = {
  __typename?: 'UserStatsResponse';
  currentElo: Scalars['Int']['output'];
  favoriteHero?: Maybe<FavoriteHero>;
  gamesLost: Scalars['Int']['output'];
  gamesPlayed: Scalars['Int']['output'];
  gamesWon: Scalars['Int']['output'];
  lastPlayedAt?: Maybe<Scalars['DateTime']['output']>;
  peakElo: Scalars['Int']['output'];
  totalPlayTime: Scalars['Int']['output'];
  userId: Scalars['String']['output'];
  winRate: Scalars['Float']['output'];
};

export type UserWithSettingsResponse = {
  __typename?: 'UserWithSettingsResponse';
  avatar?: Maybe<Scalars['String']['output']>;
  createdAt: Scalars['DateTime']['output'];
  email: Scalars['String']['output'];
  emailVerified?: Maybe<Scalars['DateTime']['output']>;
  id: Scalars['String']['output'];
  role: UserRole;
  settings?: Maybe<UserSettingsResponse>;
  username: Scalars['String']['output'];
};

/** Color zones on the board */
export enum Zone {
  Beige = 'BEIGE',
  Blue = 'BLUE',
  Brown = 'BROWN',
  Gold = 'GOLD',
  Gray = 'GRAY',
  Green = 'GREEN',
  Orange = 'ORANGE',
  Pink = 'PINK',
  Purple = 'PURPLE',
  Red = 'RED',
  White = 'WHITE',
  Yellow = 'YELLOW'
}

export type RegisterMutationVariables = Exact<{
  input: RegisterDto;
}>;


export type RegisterMutation = { __typename?: 'Mutation', register: { __typename?: 'AuthResponseDto', accessToken: string, refreshToken: string, user: { __typename?: 'AuthUserResponse', id: string, email: string, username: string } } };

export type LoginMutationVariables = Exact<{
  input: LoginDto;
}>;


export type LoginMutation = { __typename?: 'Mutation', login: { __typename?: 'AuthResponseDto', accessToken: string, refreshToken: string, user: { __typename?: 'AuthUserResponse', id: string, email: string, username: string } } };

export type RefreshTokensMutationVariables = Exact<{
  refreshToken: Scalars['String']['input'];
}>;


export type RefreshTokensMutation = { __typename?: 'Mutation', refreshTokens: { __typename?: 'AuthResponseDto', accessToken: string, refreshToken: string } };

export type LogoutMutationVariables = Exact<{ [key: string]: never; }>;


export type LogoutMutation = { __typename?: 'Mutation', logout: boolean };

export type UpdateProfileMutationVariables = Exact<{
  input: UpdateProfileDto;
}>;


export type UpdateProfileMutation = { __typename?: 'Mutation', updateProfile: { __typename?: 'UserResponse', id: string, username: string, avatar?: string | null } };

export type UpdateSettingsMutationVariables = Exact<{
  input: SettingsDto;
}>;


export type UpdateSettingsMutation = { __typename?: 'Mutation', updateSettings: { __typename?: 'UserSettingsGraphql', theme: string, soundEnabled: boolean, musicEnabled: boolean, language: string, profileVisible: boolean } };

export type CreateGameMutationVariables = Exact<{
  input: CreateGameDto;
}>;


export type CreateGameMutation = { __typename?: 'Mutation', createGame: { __typename?: 'GameResponse', id: string, mode: GameMode, status: GameStatus, hostId: string, phase?: GamePhase | null, currentTurn?: number | null, players: Array<{ __typename?: 'GamePlayerResponse', userId: string, username: string, heroId?: string | null, isReady: boolean }> } };

export type JoinGameMutationVariables = Exact<{
  input: JoinGameDto;
}>;


export type JoinGameMutation = { __typename?: 'Mutation', joinGame: { __typename?: 'GameResponse', id: string, status: GameStatus, phase?: GamePhase | null, players: Array<{ __typename?: 'GamePlayerResponse', userId: string, username: string, heroId?: string | null, isReady: boolean }> } };

export type LeaveGameMutationVariables = Exact<{
  gameId: Scalars['String']['input'];
}>;


export type LeaveGameMutation = { __typename?: 'Mutation', leaveGame: boolean };

export type StartGameMutationVariables = Exact<{
  gameId: Scalars['String']['input'];
}>;


export type StartGameMutation = { __typename?: 'Mutation', startGame: { __typename?: 'GameResponse', id: string, status: GameStatus, phase?: GamePhase | null, players: Array<{ __typename?: 'GamePlayerResponse', userId: string, heroId?: string | null }> } };

export type AbortGameMutationVariables = Exact<{
  gameId: Scalars['String']['input'];
}>;


export type AbortGameMutation = { __typename?: 'Mutation', abortGame: { __typename?: 'GameResponse', id: string, status: GameStatus } };

export type ToggleReadyMutationVariables = Exact<{
  gameId: Scalars['String']['input'];
}>;


export type ToggleReadyMutation = { __typename?: 'Mutation', toggleReady: { __typename?: 'GameResponse', id: string, players: Array<{ __typename?: 'GamePlayerResponse', userId: string, isReady: boolean }> } };

export type SelectHeroMutationVariables = Exact<{
  gameId: Scalars['String']['input'];
  heroId: Scalars['String']['input'];
}>;


export type SelectHeroMutation = { __typename?: 'Mutation', selectHero: { __typename?: 'GameResponse', id: string, players: Array<{ __typename?: 'GamePlayerResponse', userId: string, heroId?: string | null }> } };

export type ManeuverMutationVariables = Exact<{
  input: ManeuverDto;
}>;


export type ManeuverMutation = { __typename?: 'Mutation', maneuver: { __typename?: 'GameMutationResult', state?: string | null, sequenceNumber: number, phase: GamePhase, currentTurnPlayerId?: string | null, turnCount: number, timestamp: any } };

export type MoveFighterMutationVariables = Exact<{
  input: MoveFighterDto;
}>;


export type MoveFighterMutation = { __typename?: 'Mutation', moveFighter: { __typename?: 'GameMutationResult', state?: string | null, sequenceNumber: number, phase: GamePhase, currentTurnPlayerId?: string | null, turnCount: number, timestamp: any } };

export type AttackMutationVariables = Exact<{
  input: AttackDto;
}>;


export type AttackMutation = { __typename?: 'Mutation', attack: { __typename?: 'GameMutationResult', state?: string | null, sequenceNumber: number, phase: GamePhase, currentTurnPlayerId?: string | null, turnCount: number, timestamp: any } };

export type PlayDefenseMutationVariables = Exact<{
  input: PlayDefenseDto;
}>;


export type PlayDefenseMutation = { __typename?: 'Mutation', playDefense: { __typename?: 'GameMutationResult', state?: string | null, sequenceNumber: number, phase: GamePhase, currentTurnPlayerId?: string | null, turnCount: number, timestamp: any } };

export type ResolveCombatMutationVariables = Exact<{
  input: ResolveCombatDto;
}>;


export type ResolveCombatMutation = { __typename?: 'Mutation', resolveCombat: { __typename?: 'GameMutationResult', state?: string | null, sequenceNumber: number, phase: GamePhase, currentTurnPlayerId?: string | null, turnCount: number, timestamp: any } };

export type EndTurnMutationVariables = Exact<{
  input: EndTurnDto;
}>;


export type EndTurnMutation = { __typename?: 'Mutation', endTurn: { __typename?: 'GameMutationResult', state?: string | null, sequenceNumber: number, phase: GamePhase, currentTurnPlayerId?: string | null, turnCount: number, timestamp: any } };

export type PassMutationVariables = Exact<{
  input: PassDto;
}>;


export type PassMutation = { __typename?: 'Mutation', pass: { __typename?: 'GameMutationResult', state?: string | null, sequenceNumber: number, phase: GamePhase, currentTurnPlayerId?: string | null, turnCount: number, timestamp: any } };

export type ToggleDoorMutationVariables = Exact<{
  input: ToggleDoorDto;
}>;


export type ToggleDoorMutation = { __typename?: 'Mutation', toggleDoor: { __typename?: 'GameMutationResult', state?: string | null, sequenceNumber: number, phase: GamePhase, currentTurnPlayerId?: string | null, turnCount: number, timestamp: any } };

export type PlaySchemeMutationVariables = Exact<{
  input: PlaySchemeDto;
}>;


export type PlaySchemeMutation = { __typename?: 'Mutation', playScheme: { __typename?: 'GameMutationResult', state?: string | null, sequenceNumber: number, phase: GamePhase, currentTurnPlayerId?: string | null, turnCount: number, timestamp: any } };

export type ResolvePendingEffectMutationVariables = Exact<{
  input: ResolvePendingEffectDto;
}>;


export type ResolvePendingEffectMutation = { __typename?: 'Mutation', resolvePendingEffect: { __typename?: 'GameMutationResult', state?: string | null, sequenceNumber: number, phase: GamePhase, currentTurnPlayerId?: string | null, turnCount: number, timestamp: any } };

export type SetStanceMutationVariables = Exact<{
  input: SetStanceDto;
}>;


export type SetStanceMutation = { __typename?: 'Mutation', setStance: { __typename?: 'GameMutationResult', state?: string | null, sequenceNumber: number, phase: GamePhase, currentTurnPlayerId?: string | null, turnCount: number, timestamp: any } };

export type PlaceFighterMutationVariables = Exact<{
  input: MoveFighterDto;
}>;


export type PlaceFighterMutation = { __typename?: 'Mutation', moveFighter: { __typename?: 'GameMutationResult', state?: string | null, sequenceNumber: number, phase: GamePhase, currentTurnPlayerId?: string | null, turnCount: number, timestamp: any } };

export type ConfirmPlacementMutationVariables = Exact<{
  gameId: Scalars['String']['input'];
}>;


export type ConfirmPlacementMutation = { __typename?: 'Mutation', pass: { __typename?: 'GameMutationResult', state?: string | null, sequenceNumber: number, phase: GamePhase, currentTurnPlayerId?: string | null, turnCount: number, timestamp: any } };

export type MeQueryVariables = Exact<{ [key: string]: never; }>;


export type MeQuery = { __typename?: 'Query', me?: { __typename?: 'UserWithSettingsResponse', id: string, email: string, username: string, avatar?: string | null, createdAt: any, settings?: { __typename?: 'UserSettingsResponse', theme: string, soundEnabled: boolean, musicEnabled: boolean, language: string, profileVisible: boolean } | null } | null };

export type MyStatsQueryVariables = Exact<{ [key: string]: never; }>;


export type MyStatsQuery = { __typename?: 'Query', myStats: { __typename?: 'UserStatsResponse', userId: string, gamesPlayed: number, gamesWon: number, gamesLost: number, winRate: number, currentElo: number, peakElo: number } };

export type MySettingsQueryVariables = Exact<{ [key: string]: never; }>;


export type MySettingsQuery = { __typename?: 'Query', mySettings: { __typename?: 'UserSettingsGraphql', theme: string, soundEnabled: boolean, musicEnabled: boolean, language: string, profileVisible: boolean } };

export type GetCardsQueryVariables = Exact<{
  page: Scalars['Int']['input'];
  limit: Scalars['Int']['input'];
}>;


export type GetCardsQuery = { __typename?: 'Query', cardList: { __typename?: 'CardsPaginatedDto', total: number, items: Array<{ __typename?: 'CardListItemDto', id: string, name: string, nameEn: string, nameRu: string, cardType: string, subType?: string | null, attackValue?: number | null, defenseValue?: number | null, boostValue?: number | null, bannerName?: string | null, count: number, heroId: string, imageUrl?: string | null, imageUrlRu?: string | null }> } };

export type GetCardQueryVariables = Exact<{
  id: Scalars['String']['input'];
}>;


export type GetCardQuery = { __typename?: 'Query', card?: { __typename?: 'Card', id: string, title: string, type: CardType, value: number, boost: number, quantity: number, characterName: string, imageUrl?: string | null, imageUrlRu?: string | null, effects: Array<{ __typename?: 'CardEffect', id: string, timing: EffectTiming, text: string }> } | null };

export type GetGameQueryVariables = Exact<{
  id: Scalars['String']['input'];
}>;


export type GetGameQuery = { __typename?: 'Query', game?: { __typename?: 'GameResponse', id: string, mode: GameMode, status: GameStatus, hostId: string, boardId: string, winnerId?: string | null, createdAt: any, updatedAt: any, startedAt?: any | null, endedAt?: any | null, phase?: GamePhase | null, currentTurn?: number | null, players: Array<{ __typename?: 'GamePlayerResponse', id: string, userId: string, username: string, avatar?: string | null, heroId?: string | null, isReady: boolean, hasPassed: boolean, seatOrder: number }> } | null };

export type MyGamesQueryVariables = Exact<{
  filters?: InputMaybe<GameFiltersDto>;
}>;


export type MyGamesQuery = { __typename?: 'Query', myGames: Array<{ __typename?: 'GameResponse', id: string, mode: GameMode, status: GameStatus, hostId: string, createdAt: any, phase?: GamePhase | null, currentTurn?: number | null, players: Array<{ __typename?: 'GamePlayerResponse', userId: string, username: string, avatar?: string | null, heroId?: string | null, isReady: boolean }> }> };

export type AvailableGamesQueryVariables = Exact<{
  mode?: InputMaybe<Scalars['String']['input']>;
  limit?: InputMaybe<Scalars['Float']['input']>;
}>;


export type AvailableGamesQuery = { __typename?: 'Query', availableGames: Array<{ __typename?: 'GameResponse', id: string, mode: GameMode, status: GameStatus, players: Array<{ __typename?: 'GamePlayerResponse', userId: string, username: string, avatar?: string | null, heroId?: string | null }> }> };

export type GetGameStateQueryVariables = Exact<{
  gameId: Scalars['String']['input'];
}>;


export type GetGameStateQuery = { __typename?: 'Query', gameState?: { __typename?: 'GameStateResponse', id: string, gameId: string, state: string, sequenceNumber: number, currentTurnPlayerId?: string | null, phase: string, turnCount: number, updatedAt: any } | null };

export type GetGameSequenceQueryVariables = Exact<{
  gameId: Scalars['String']['input'];
}>;


export type GetGameSequenceQuery = { __typename?: 'Query', gameSequence?: number | null };

export type EventsSinceQueryVariables = Exact<{
  gameId: Scalars['String']['input'];
  sinceSequence: Scalars['Float']['input'];
}>;


export type EventsSinceQuery = { __typename?: 'Query', eventsSince?: { __typename?: 'EventsSinceResponse', gameId: string, lastSequence: number, hasMore: boolean, events: Array<{ __typename?: 'GameEvent', sequenceNumber: number, type: GameEventType, gameId: string, payload?: string | null, timestamp: any }> } | null };

export type HeroesQueryVariables = Exact<{ [key: string]: never; }>;


export type HeroesQuery = { __typename?: 'Query', heroes: Array<{ __typename?: 'Hero', id: string, name: string, health: number, movement: number, set: string, fighterType: FighterType, sidekickCount?: number | null, sidekickHealth?: number | null }> };

export type HeroQueryVariables = Exact<{
  id: Scalars['String']['input'];
}>;


export type HeroQuery = { __typename?: 'Query', hero?: { __typename?: 'Hero', id: string, name: string, health: number, movement: number, set: string, fighterType: FighterType, abilities: Array<{ __typename?: 'HeroAbility', id: string, name: string, text: string, trigger: AbilityTrigger }>, cards: Array<{ __typename?: 'Card', id: string, title: string, type: CardType, value: number, boost: number, quantity: number, imageUrl?: string | null, imageUrlRu?: string | null }> } | null };

export type BoardsQueryVariables = Exact<{ [key: string]: never; }>;


export type BoardsQuery = { __typename?: 'Query', boards: Array<{ __typename?: 'Board', id: string, name: string, width: number, height: number, recommendedPlayers: number, imageUrl?: string | null, spaces: Array<{ __typename?: 'BoardSpace', zones: Array<Zone>, isObstacle?: boolean | null, position: { __typename?: 'Position', x: number, y: number } }> }> };

export type BoardQueryVariables = Exact<{
  id: Scalars['String']['input'];
}>;


export type BoardQuery = { __typename?: 'Query', board?: { __typename?: 'Board', id: string, name: string, width: number, height: number, recommendedPlayers: number, imageUrl?: string | null, spaces: Array<{ __typename?: 'BoardSpace', zones: Array<Zone>, isObstacle?: boolean | null, position: { __typename?: 'Position', x: number, y: number } }> } | null };

export type ContentSummaryQueryVariables = Exact<{ [key: string]: never; }>;


export type ContentSummaryQuery = { __typename?: 'Query', contentSummary: { __typename?: 'ContentSummary', heroesCount: number, boardsCount: number, setsCount: number, version: string, sets: Array<string> } };

export type SetsQueryVariables = Exact<{ [key: string]: never; }>;


export type SetsQuery = { __typename?: 'Query', sets: Array<string> };

export type AllHeroesQueryVariables = Exact<{ [key: string]: never; }>;


export type AllHeroesQuery = { __typename?: 'Query', heroes: Array<{ __typename?: 'Hero', id: string, name: string, health: number, movement: number, set: string, fighterType: FighterType, sidekickCount?: number | null, sidekickHealth?: number | null, urls?: { __typename?: 'HeroUrls', avatar: string, mini: string, cardCover: string } | null }> };

export type HeroDetailsQueryVariables = Exact<{
  id: Scalars['String']['input'];
}>;


export type HeroDetailsQuery = { __typename?: 'Query', hero?: { __typename?: 'Hero', id: string, name: string, health: number, movement: number, set: string, fighterType: FighterType, sidekickCount?: number | null, sidekickHealth?: number | null, urls?: { __typename?: 'HeroUrls', avatar: string, mini: string, cardCover: string } | null, abilities: Array<{ __typename?: 'HeroAbility', id: string, name: string, text: string, trigger: AbilityTrigger }>, cards: Array<{ __typename?: 'Card', id: string, title: string, type: CardType, value: number, boost: number, quantity: number, imageUrl?: string | null, imageUrlRu?: string | null }> } | null };

export type HeroesBySetQueryVariables = Exact<{
  set: Scalars['String']['input'];
}>;


export type HeroesBySetQuery = { __typename?: 'Query', heroesBySet: Array<{ __typename?: 'Hero', id: string, name: string, health: number, movement: number, set: string, fighterType: FighterType, sidekickCount?: number | null, sidekickHealth?: number | null, urls?: { __typename?: 'HeroUrls', avatar: string, mini: string, cardCover: string } | null }> };

export type HeroStanceOptionsQueryVariables = Exact<{
  heroSlug: Scalars['String']['input'];
}>;


export type HeroStanceOptionsQuery = { __typename?: 'Query', heroStances: Array<{ __typename?: 'StanceOptionDto', id: string, label: string, isDefault: boolean }> };

export type LobbyAvailableGamesQueryVariables = Exact<{
  mode?: InputMaybe<Scalars['String']['input']>;
  limit?: InputMaybe<Scalars['Float']['input']>;
}>;


export type LobbyAvailableGamesQuery = { __typename?: 'Query', availableGames: Array<{ __typename?: 'GameResponse', id: string, mode: GameMode, status: GameStatus, boardId: string, createdAt: any, updatedAt: any, host: { __typename?: 'GamePlayerResponse', id: string, username: string, avatar?: string | null }, opponent?: { __typename?: 'GamePlayerResponse', id: string, username: string, avatar?: string | null } | null }> };

export type QueueStatusQueryVariables = Exact<{
  mode: Scalars['String']['input'];
}>;


export type QueueStatusQuery = { __typename?: 'Query', queueStatus: { __typename?: 'QueueStatusResponse', inQueue: boolean, mode?: string | null, position?: number | null, totalPlayers: number, estimatedWaitTime: number, joinedAt?: any | null } };

export type PenaltyInfoQueryVariables = Exact<{ [key: string]: never; }>;


export type PenaltyInfoQuery = { __typename?: 'Query', penaltyInfo: { __typename?: 'PenaltyInfoDto', canJoinQueue: boolean, declineCount: number, tempBanUntil?: any | null, penaltyElo?: number | null, reason?: string | null } };

export type RoomInfoQueryVariables = Exact<{
  id: Scalars['String']['input'];
}>;


export type RoomInfoQuery = { __typename?: 'Query', game?: { __typename?: 'GameResponse', id: string, code?: string | null, status: GameStatus, mode: GameMode, hostId: string, boardId: string, phase?: GamePhase | null, createdAt: any, players: Array<{ __typename?: 'GamePlayerResponse', id: string, userId: string, username: string, avatar?: string | null, heroId?: string | null, isReady: boolean, seatOrder: number }> } | null };

export type ValidSpawnZonesQueryVariables = Exact<{
  gameId: Scalars['String']['input'];
  playerId: Scalars['String']['input'];
}>;


export type ValidSpawnZonesQuery = { __typename?: 'Query', gameState?: { __typename?: 'GameStateResponse', id: string, gameId: string, state: string, sequenceNumber: number, currentTurnPlayerId?: string | null, phase: string, turnCount: number, updatedAt: any } | null };

export type GameStateUpdatedSubscriptionVariables = Exact<{
  gameId: Scalars['String']['input'];
  since?: InputMaybe<Scalars['Float']['input']>;
}>;


export type GameStateUpdatedSubscription = { __typename?: 'Subscription', gameStateUpdated: { __typename?: 'GameState', gameId: string, sequenceNumber: number, phase: GamePhase, turnCount: number, currentTurnPlayerId: string, players?: string | null, fighters?: string | null, handZones?: string | null, boardState?: string | null, metadata?: string | null } };

export type AttackInitiatedSubscriptionVariables = Exact<{
  gameId: Scalars['String']['input'];
}>;


export type AttackInitiatedSubscription = { __typename?: 'Subscription', attackInitiated: { __typename?: 'GameEvent', type: GameEventType, gameId: string, sequenceNumber: number, timestamp: any, payload?: string | null } };

export type DefensePlayedSubscriptionVariables = Exact<{
  gameId: Scalars['String']['input'];
}>;


export type DefensePlayedSubscription = { __typename?: 'Subscription', defensePlayed: { __typename?: 'GameEvent', type: GameEventType, gameId: string, sequenceNumber: number, timestamp: any, payload?: string | null } };

export type CombatResolvedSubscriptionVariables = Exact<{
  gameId: Scalars['String']['input'];
}>;


export type CombatResolvedSubscription = { __typename?: 'Subscription', combatResolved: { __typename?: 'GameEvent', type: GameEventType, gameId: string, sequenceNumber: number, timestamp: any, payload?: string | null } };

export type TurnChangedSubscriptionVariables = Exact<{
  gameId: Scalars['String']['input'];
}>;


export type TurnChangedSubscription = { __typename?: 'Subscription', turnChanged: { __typename?: 'TurnState', playerId: string, turnCount: number, phase: GamePhase } };

export type PlayerJoinedSubscriptionVariables = Exact<{
  gameId: Scalars['String']['input'];
}>;


export type PlayerJoinedSubscription = { __typename?: 'Subscription', playerJoined: { __typename?: 'GameEvent', type: GameEventType, gameId: string, sequenceNumber: number, timestamp: any, payload?: string | null } };

export type PlayerLeftSubscriptionVariables = Exact<{
  gameId: Scalars['String']['input'];
}>;


export type PlayerLeftSubscription = { __typename?: 'Subscription', playerLeft: { __typename?: 'GameEvent', type: GameEventType, gameId: string, sequenceNumber: number, timestamp: any, payload?: string | null } };

export type GameEndedSubscriptionVariables = Exact<{
  gameId: Scalars['String']['input'];
}>;


export type GameEndedSubscription = { __typename?: 'Subscription', gameEnded: { __typename?: 'GameEvent', type: GameEventType, gameId: string, sequenceNumber: number, timestamp: any, payload?: string | null } };

export type MatchFoundSubscriptionVariables = Exact<{
  userId: Scalars['String']['input'];
}>;


export type MatchFoundSubscription = { __typename?: 'Subscription', matchFound: { __typename?: 'MatchFoundResponse', gameId: string, opponentId: string, opponentUsername: string, opponentRating: number, mode: string, expiresAt: any } };


export const RegisterDocument = {"kind":"Document","definitions":[{"kind":"OperationDefinition","operation":"mutation","name":{"kind":"Name","value":"Register"},"variableDefinitions":[{"kind":"VariableDefinition","variable":{"kind":"Variable","name":{"kind":"Name","value":"input"}},"type":{"kind":"NonNullType","type":{"kind":"NamedType","name":{"kind":"Name","value":"RegisterDto"}}}}],"selectionSet":{"kind":"SelectionSet","selections":[{"kind":"Field","name":{"kind":"Name","value":"register"},"arguments":[{"kind":"Argument","name":{"kind":"Name","value":"input"},"value":{"kind":"Variable","name":{"kind":"Name","value":"input"}}}],"selectionSet":{"kind":"SelectionSet","selections":[{"kind":"Field","name":{"kind":"Name","value":"accessToken"}},{"kind":"Field","name":{"kind":"Name","value":"refreshToken"}},{"kind":"Field","name":{"kind":"Name","value":"user"},"selectionSet":{"kind":"SelectionSet","selections":[{"kind":"Field","name":{"kind":"Name","value":"id"}},{"kind":"Field","name":{"kind":"Name","value":"email"}},{"kind":"Field","name":{"kind":"Name","value":"username"}}]}}]}}]}}]} as unknown as DocumentNode<RegisterMutation, RegisterMutationVariables>;
export const LoginDocument = {"kind":"Document","definitions":[{"kind":"OperationDefinition","operation":"mutation","name":{"kind":"Name","value":"Login"},"variableDefinitions":[{"kind":"VariableDefinition","variable":{"kind":"Variable","name":{"kind":"Name","value":"input"}},"type":{"kind":"NonNullType","type":{"kind":"NamedType","name":{"kind":"Name","value":"LoginDto"}}}}],"selectionSet":{"kind":"SelectionSet","selections":[{"kind":"Field","name":{"kind":"Name","value":"login"},"arguments":[{"kind":"Argument","name":{"kind":"Name","value":"input"},"value":{"kind":"Variable","name":{"kind":"Name","value":"input"}}}],"selectionSet":{"kind":"SelectionSet","selections":[{"kind":"Field","name":{"kind":"Name","value":"accessToken"}},{"kind":"Field","name":{"kind":"Name","value":"refreshToken"}},{"kind":"Field","name":{"kind":"Name","value":"user"},"selectionSet":{"kind":"SelectionSet","selections":[{"kind":"Field","name":{"kind":"Name","value":"id"}},{"kind":"Field","name":{"kind":"Name","value":"email"}},{"kind":"Field","name":{"kind":"Name","value":"username"}}]}}]}}]}}]} as unknown as DocumentNode<LoginMutation, LoginMutationVariables>;
export const RefreshTokensDocument = {"kind":"Document","definitions":[{"kind":"OperationDefinition","operation":"mutation","name":{"kind":"Name","value":"RefreshTokens"},"variableDefinitions":[{"kind":"VariableDefinition","variable":{"kind":"Variable","name":{"kind":"Name","value":"refreshToken"}},"type":{"kind":"NonNullType","type":{"kind":"NamedType","name":{"kind":"Name","value":"String"}}}}],"selectionSet":{"kind":"SelectionSet","selections":[{"kind":"Field","name":{"kind":"Name","value":"refreshTokens"},"arguments":[{"kind":"Argument","name":{"kind":"Name","value":"refreshToken"},"value":{"kind":"Variable","name":{"kind":"Name","value":"refreshToken"}}}],"selectionSet":{"kind":"SelectionSet","selections":[{"kind":"Field","name":{"kind":"Name","value":"accessToken"}},{"kind":"Field","name":{"kind":"Name","value":"refreshToken"}}]}}]}}]} as unknown as DocumentNode<RefreshTokensMutation, RefreshTokensMutationVariables>;
export const LogoutDocument = {"kind":"Document","definitions":[{"kind":"OperationDefinition","operation":"mutation","name":{"kind":"Name","value":"Logout"},"selectionSet":{"kind":"SelectionSet","selections":[{"kind":"Field","name":{"kind":"Name","value":"logout"}}]}}]} as unknown as DocumentNode<LogoutMutation, LogoutMutationVariables>;
export const UpdateProfileDocument = {"kind":"Document","definitions":[{"kind":"OperationDefinition","operation":"mutation","name":{"kind":"Name","value":"UpdateProfile"},"variableDefinitions":[{"kind":"VariableDefinition","variable":{"kind":"Variable","name":{"kind":"Name","value":"input"}},"type":{"kind":"NonNullType","type":{"kind":"NamedType","name":{"kind":"Name","value":"UpdateProfileDto"}}}}],"selectionSet":{"kind":"SelectionSet","selections":[{"kind":"Field","name":{"kind":"Name","value":"updateProfile"},"arguments":[{"kind":"Argument","name":{"kind":"Name","value":"input"},"value":{"kind":"Variable","name":{"kind":"Name","value":"input"}}}],"selectionSet":{"kind":"SelectionSet","selections":[{"kind":"Field","name":{"kind":"Name","value":"id"}},{"kind":"Field","name":{"kind":"Name","value":"username"}},{"kind":"Field","name":{"kind":"Name","value":"avatar"}}]}}]}}]} as unknown as DocumentNode<UpdateProfileMutation, UpdateProfileMutationVariables>;
export const UpdateSettingsDocument = {"kind":"Document","definitions":[{"kind":"OperationDefinition","operation":"mutation","name":{"kind":"Name","value":"UpdateSettings"},"variableDefinitions":[{"kind":"VariableDefinition","variable":{"kind":"Variable","name":{"kind":"Name","value":"input"}},"type":{"kind":"NonNullType","type":{"kind":"NamedType","name":{"kind":"Name","value":"SettingsDto"}}}}],"selectionSet":{"kind":"SelectionSet","selections":[{"kind":"Field","name":{"kind":"Name","value":"updateSettings"},"arguments":[{"kind":"Argument","name":{"kind":"Name","value":"input"},"value":{"kind":"Variable","name":{"kind":"Name","value":"input"}}}],"selectionSet":{"kind":"SelectionSet","selections":[{"kind":"Field","name":{"kind":"Name","value":"theme"}},{"kind":"Field","name":{"kind":"Name","value":"soundEnabled"}},{"kind":"Field","name":{"kind":"Name","value":"musicEnabled"}},{"kind":"Field","name":{"kind":"Name","value":"language"}},{"kind":"Field","name":{"kind":"Name","value":"profileVisible"}}]}}]}}]} as unknown as DocumentNode<UpdateSettingsMutation, UpdateSettingsMutationVariables>;
export const CreateGameDocument = {"kind":"Document","definitions":[{"kind":"OperationDefinition","operation":"mutation","name":{"kind":"Name","value":"CreateGame"},"variableDefinitions":[{"kind":"VariableDefinition","variable":{"kind":"Variable","name":{"kind":"Name","value":"input"}},"type":{"kind":"NonNullType","type":{"kind":"NamedType","name":{"kind":"Name","value":"CreateGameDto"}}}}],"selectionSet":{"kind":"SelectionSet","selections":[{"kind":"Field","name":{"kind":"Name","value":"createGame"},"arguments":[{"kind":"Argument","name":{"kind":"Name","value":"input"},"value":{"kind":"Variable","name":{"kind":"Name","value":"input"}}}],"selectionSet":{"kind":"SelectionSet","selections":[{"kind":"Field","name":{"kind":"Name","value":"id"}},{"kind":"Field","name":{"kind":"Name","value":"mode"}},{"kind":"Field","name":{"kind":"Name","value":"status"}},{"kind":"Field","name":{"kind":"Name","value":"hostId"}},{"kind":"Field","name":{"kind":"Name","value":"phase"}},{"kind":"Field","name":{"kind":"Name","value":"currentTurn"}},{"kind":"Field","name":{"kind":"Name","value":"players"},"selectionSet":{"kind":"SelectionSet","selections":[{"kind":"Field","name":{"kind":"Name","value":"userId"}},{"kind":"Field","name":{"kind":"Name","value":"username"}},{"kind":"Field","name":{"kind":"Name","value":"heroId"}},{"kind":"Field","name":{"kind":"Name","value":"isReady"}}]}}]}}]}}]} as unknown as DocumentNode<CreateGameMutation, CreateGameMutationVariables>;
export const JoinGameDocument = {"kind":"Document","definitions":[{"kind":"OperationDefinition","operation":"mutation","name":{"kind":"Name","value":"JoinGame"},"variableDefinitions":[{"kind":"VariableDefinition","variable":{"kind":"Variable","name":{"kind":"Name","value":"input"}},"type":{"kind":"NonNullType","type":{"kind":"NamedType","name":{"kind":"Name","value":"JoinGameDto"}}}}],"selectionSet":{"kind":"SelectionSet","selections":[{"kind":"Field","name":{"kind":"Name","value":"joinGame"},"arguments":[{"kind":"Argument","name":{"kind":"Name","value":"input"},"value":{"kind":"Variable","name":{"kind":"Name","value":"input"}}}],"selectionSet":{"kind":"SelectionSet","selections":[{"kind":"Field","name":{"kind":"Name","value":"id"}},{"kind":"Field","name":{"kind":"Name","value":"status"}},{"kind":"Field","name":{"kind":"Name","value":"phase"}},{"kind":"Field","name":{"kind":"Name","value":"players"},"selectionSet":{"kind":"SelectionSet","selections":[{"kind":"Field","name":{"kind":"Name","value":"userId"}},{"kind":"Field","name":{"kind":"Name","value":"username"}},{"kind":"Field","name":{"kind":"Name","value":"heroId"}},{"kind":"Field","name":{"kind":"Name","value":"isReady"}}]}}]}}]}}]} as unknown as DocumentNode<JoinGameMutation, JoinGameMutationVariables>;
export const LeaveGameDocument = {"kind":"Document","definitions":[{"kind":"OperationDefinition","operation":"mutation","name":{"kind":"Name","value":"LeaveGame"},"variableDefinitions":[{"kind":"VariableDefinition","variable":{"kind":"Variable","name":{"kind":"Name","value":"gameId"}},"type":{"kind":"NonNullType","type":{"kind":"NamedType","name":{"kind":"Name","value":"String"}}}}],"selectionSet":{"kind":"SelectionSet","selections":[{"kind":"Field","name":{"kind":"Name","value":"leaveGame"},"arguments":[{"kind":"Argument","name":{"kind":"Name","value":"gameId"},"value":{"kind":"Variable","name":{"kind":"Name","value":"gameId"}}}]}]}}]} as unknown as DocumentNode<LeaveGameMutation, LeaveGameMutationVariables>;
export const StartGameDocument = {"kind":"Document","definitions":[{"kind":"OperationDefinition","operation":"mutation","name":{"kind":"Name","value":"StartGame"},"variableDefinitions":[{"kind":"VariableDefinition","variable":{"kind":"Variable","name":{"kind":"Name","value":"gameId"}},"type":{"kind":"NonNullType","type":{"kind":"NamedType","name":{"kind":"Name","value":"String"}}}}],"selectionSet":{"kind":"SelectionSet","selections":[{"kind":"Field","name":{"kind":"Name","value":"startGame"},"arguments":[{"kind":"Argument","name":{"kind":"Name","value":"gameId"},"value":{"kind":"Variable","name":{"kind":"Name","value":"gameId"}}}],"selectionSet":{"kind":"SelectionSet","selections":[{"kind":"Field","name":{"kind":"Name","value":"id"}},{"kind":"Field","name":{"kind":"Name","value":"status"}},{"kind":"Field","name":{"kind":"Name","value":"phase"}},{"kind":"Field","name":{"kind":"Name","value":"players"},"selectionSet":{"kind":"SelectionSet","selections":[{"kind":"Field","name":{"kind":"Name","value":"userId"}},{"kind":"Field","name":{"kind":"Name","value":"heroId"}}]}}]}}]}}]} as unknown as DocumentNode<StartGameMutation, StartGameMutationVariables>;
export const AbortGameDocument = {"kind":"Document","definitions":[{"kind":"OperationDefinition","operation":"mutation","name":{"kind":"Name","value":"AbortGame"},"variableDefinitions":[{"kind":"VariableDefinition","variable":{"kind":"Variable","name":{"kind":"Name","value":"gameId"}},"type":{"kind":"NonNullType","type":{"kind":"NamedType","name":{"kind":"Name","value":"String"}}}}],"selectionSet":{"kind":"SelectionSet","selections":[{"kind":"Field","name":{"kind":"Name","value":"abortGame"},"arguments":[{"kind":"Argument","name":{"kind":"Name","value":"gameId"},"value":{"kind":"Variable","name":{"kind":"Name","value":"gameId"}}}],"selectionSet":{"kind":"SelectionSet","selections":[{"kind":"Field","name":{"kind":"Name","value":"id"}},{"kind":"Field","name":{"kind":"Name","value":"status"}}]}}]}}]} as unknown as DocumentNode<AbortGameMutation, AbortGameMutationVariables>;
export const ToggleReadyDocument = {"kind":"Document","definitions":[{"kind":"OperationDefinition","operation":"mutation","name":{"kind":"Name","value":"ToggleReady"},"variableDefinitions":[{"kind":"VariableDefinition","variable":{"kind":"Variable","name":{"kind":"Name","value":"gameId"}},"type":{"kind":"NonNullType","type":{"kind":"NamedType","name":{"kind":"Name","value":"String"}}}}],"selectionSet":{"kind":"SelectionSet","selections":[{"kind":"Field","name":{"kind":"Name","value":"toggleReady"},"arguments":[{"kind":"Argument","name":{"kind":"Name","value":"gameId"},"value":{"kind":"Variable","name":{"kind":"Name","value":"gameId"}}}],"selectionSet":{"kind":"SelectionSet","selections":[{"kind":"Field","name":{"kind":"Name","value":"id"}},{"kind":"Field","name":{"kind":"Name","value":"players"},"selectionSet":{"kind":"SelectionSet","selections":[{"kind":"Field","name":{"kind":"Name","value":"userId"}},{"kind":"Field","name":{"kind":"Name","value":"isReady"}}]}}]}}]}}]} as unknown as DocumentNode<ToggleReadyMutation, ToggleReadyMutationVariables>;
export const SelectHeroDocument = {"kind":"Document","definitions":[{"kind":"OperationDefinition","operation":"mutation","name":{"kind":"Name","value":"SelectHero"},"variableDefinitions":[{"kind":"VariableDefinition","variable":{"kind":"Variable","name":{"kind":"Name","value":"gameId"}},"type":{"kind":"NonNullType","type":{"kind":"NamedType","name":{"kind":"Name","value":"String"}}}},{"kind":"VariableDefinition","variable":{"kind":"Variable","name":{"kind":"Name","value":"heroId"}},"type":{"kind":"NonNullType","type":{"kind":"NamedType","name":{"kind":"Name","value":"String"}}}}],"selectionSet":{"kind":"SelectionSet","selections":[{"kind":"Field","name":{"kind":"Name","value":"selectHero"},"arguments":[{"kind":"Argument","name":{"kind":"Name","value":"gameId"},"value":{"kind":"Variable","name":{"kind":"Name","value":"gameId"}}},{"kind":"Argument","name":{"kind":"Name","value":"heroId"},"value":{"kind":"Variable","name":{"kind":"Name","value":"heroId"}}}],"selectionSet":{"kind":"SelectionSet","selections":[{"kind":"Field","name":{"kind":"Name","value":"id"}},{"kind":"Field","name":{"kind":"Name","value":"players"},"selectionSet":{"kind":"SelectionSet","selections":[{"kind":"Field","name":{"kind":"Name","value":"userId"}},{"kind":"Field","name":{"kind":"Name","value":"heroId"}}]}}]}}]}}]} as unknown as DocumentNode<SelectHeroMutation, SelectHeroMutationVariables>;
export const ManeuverDocument = {"kind":"Document","definitions":[{"kind":"OperationDefinition","operation":"mutation","name":{"kind":"Name","value":"Maneuver"},"variableDefinitions":[{"kind":"VariableDefinition","variable":{"kind":"Variable","name":{"kind":"Name","value":"input"}},"type":{"kind":"NonNullType","type":{"kind":"NamedType","name":{"kind":"Name","value":"ManeuverDto"}}}}],"selectionSet":{"kind":"SelectionSet","selections":[{"kind":"Field","name":{"kind":"Name","value":"maneuver"},"arguments":[{"kind":"Argument","name":{"kind":"Name","value":"input"},"value":{"kind":"Variable","name":{"kind":"Name","value":"input"}}}],"selectionSet":{"kind":"SelectionSet","selections":[{"kind":"Field","name":{"kind":"Name","value":"state"}},{"kind":"Field","name":{"kind":"Name","value":"sequenceNumber"}},{"kind":"Field","name":{"kind":"Name","value":"phase"}},{"kind":"Field","name":{"kind":"Name","value":"currentTurnPlayerId"}},{"kind":"Field","name":{"kind":"Name","value":"turnCount"}},{"kind":"Field","name":{"kind":"Name","value":"timestamp"}}]}}]}}]} as unknown as DocumentNode<ManeuverMutation, ManeuverMutationVariables>;
export const MoveFighterDocument = {"kind":"Document","definitions":[{"kind":"OperationDefinition","operation":"mutation","name":{"kind":"Name","value":"MoveFighter"},"variableDefinitions":[{"kind":"VariableDefinition","variable":{"kind":"Variable","name":{"kind":"Name","value":"input"}},"type":{"kind":"NonNullType","type":{"kind":"NamedType","name":{"kind":"Name","value":"MoveFighterDto"}}}}],"selectionSet":{"kind":"SelectionSet","selections":[{"kind":"Field","name":{"kind":"Name","value":"moveFighter"},"arguments":[{"kind":"Argument","name":{"kind":"Name","value":"input"},"value":{"kind":"Variable","name":{"kind":"Name","value":"input"}}}],"selectionSet":{"kind":"SelectionSet","selections":[{"kind":"Field","name":{"kind":"Name","value":"state"}},{"kind":"Field","name":{"kind":"Name","value":"sequenceNumber"}},{"kind":"Field","name":{"kind":"Name","value":"phase"}},{"kind":"Field","name":{"kind":"Name","value":"currentTurnPlayerId"}},{"kind":"Field","name":{"kind":"Name","value":"turnCount"}},{"kind":"Field","name":{"kind":"Name","value":"timestamp"}}]}}]}}]} as unknown as DocumentNode<MoveFighterMutation, MoveFighterMutationVariables>;
export const AttackDocument = {"kind":"Document","definitions":[{"kind":"OperationDefinition","operation":"mutation","name":{"kind":"Name","value":"Attack"},"variableDefinitions":[{"kind":"VariableDefinition","variable":{"kind":"Variable","name":{"kind":"Name","value":"input"}},"type":{"kind":"NonNullType","type":{"kind":"NamedType","name":{"kind":"Name","value":"AttackDto"}}}}],"selectionSet":{"kind":"SelectionSet","selections":[{"kind":"Field","name":{"kind":"Name","value":"attack"},"arguments":[{"kind":"Argument","name":{"kind":"Name","value":"input"},"value":{"kind":"Variable","name":{"kind":"Name","value":"input"}}}],"selectionSet":{"kind":"SelectionSet","selections":[{"kind":"Field","name":{"kind":"Name","value":"state"}},{"kind":"Field","name":{"kind":"Name","value":"sequenceNumber"}},{"kind":"Field","name":{"kind":"Name","value":"phase"}},{"kind":"Field","name":{"kind":"Name","value":"currentTurnPlayerId"}},{"kind":"Field","name":{"kind":"Name","value":"turnCount"}},{"kind":"Field","name":{"kind":"Name","value":"timestamp"}}]}}]}}]} as unknown as DocumentNode<AttackMutation, AttackMutationVariables>;
export const PlayDefenseDocument = {"kind":"Document","definitions":[{"kind":"OperationDefinition","operation":"mutation","name":{"kind":"Name","value":"PlayDefense"},"variableDefinitions":[{"kind":"VariableDefinition","variable":{"kind":"Variable","name":{"kind":"Name","value":"input"}},"type":{"kind":"NonNullType","type":{"kind":"NamedType","name":{"kind":"Name","value":"PlayDefenseDto"}}}}],"selectionSet":{"kind":"SelectionSet","selections":[{"kind":"Field","name":{"kind":"Name","value":"playDefense"},"arguments":[{"kind":"Argument","name":{"kind":"Name","value":"input"},"value":{"kind":"Variable","name":{"kind":"Name","value":"input"}}}],"selectionSet":{"kind":"SelectionSet","selections":[{"kind":"Field","name":{"kind":"Name","value":"state"}},{"kind":"Field","name":{"kind":"Name","value":"sequenceNumber"}},{"kind":"Field","name":{"kind":"Name","value":"phase"}},{"kind":"Field","name":{"kind":"Name","value":"currentTurnPlayerId"}},{"kind":"Field","name":{"kind":"Name","value":"turnCount"}},{"kind":"Field","name":{"kind":"Name","value":"timestamp"}}]}}]}}]} as unknown as DocumentNode<PlayDefenseMutation, PlayDefenseMutationVariables>;
export const ResolveCombatDocument = {"kind":"Document","definitions":[{"kind":"OperationDefinition","operation":"mutation","name":{"kind":"Name","value":"ResolveCombat"},"variableDefinitions":[{"kind":"VariableDefinition","variable":{"kind":"Variable","name":{"kind":"Name","value":"input"}},"type":{"kind":"NonNullType","type":{"kind":"NamedType","name":{"kind":"Name","value":"ResolveCombatDto"}}}}],"selectionSet":{"kind":"SelectionSet","selections":[{"kind":"Field","name":{"kind":"Name","value":"resolveCombat"},"arguments":[{"kind":"Argument","name":{"kind":"Name","value":"input"},"value":{"kind":"Variable","name":{"kind":"Name","value":"input"}}}],"selectionSet":{"kind":"SelectionSet","selections":[{"kind":"Field","name":{"kind":"Name","value":"state"}},{"kind":"Field","name":{"kind":"Name","value":"sequenceNumber"}},{"kind":"Field","name":{"kind":"Name","value":"phase"}},{"kind":"Field","name":{"kind":"Name","value":"currentTurnPlayerId"}},{"kind":"Field","name":{"kind":"Name","value":"turnCount"}},{"kind":"Field","name":{"kind":"Name","value":"timestamp"}}]}}]}}]} as unknown as DocumentNode<ResolveCombatMutation, ResolveCombatMutationVariables>;
export const EndTurnDocument = {"kind":"Document","definitions":[{"kind":"OperationDefinition","operation":"mutation","name":{"kind":"Name","value":"EndTurn"},"variableDefinitions":[{"kind":"VariableDefinition","variable":{"kind":"Variable","name":{"kind":"Name","value":"input"}},"type":{"kind":"NonNullType","type":{"kind":"NamedType","name":{"kind":"Name","value":"EndTurnDto"}}}}],"selectionSet":{"kind":"SelectionSet","selections":[{"kind":"Field","name":{"kind":"Name","value":"endTurn"},"arguments":[{"kind":"Argument","name":{"kind":"Name","value":"input"},"value":{"kind":"Variable","name":{"kind":"Name","value":"input"}}}],"selectionSet":{"kind":"SelectionSet","selections":[{"kind":"Field","name":{"kind":"Name","value":"state"}},{"kind":"Field","name":{"kind":"Name","value":"sequenceNumber"}},{"kind":"Field","name":{"kind":"Name","value":"phase"}},{"kind":"Field","name":{"kind":"Name","value":"currentTurnPlayerId"}},{"kind":"Field","name":{"kind":"Name","value":"turnCount"}},{"kind":"Field","name":{"kind":"Name","value":"timestamp"}}]}}]}}]} as unknown as DocumentNode<EndTurnMutation, EndTurnMutationVariables>;
export const PassDocument = {"kind":"Document","definitions":[{"kind":"OperationDefinition","operation":"mutation","name":{"kind":"Name","value":"Pass"},"variableDefinitions":[{"kind":"VariableDefinition","variable":{"kind":"Variable","name":{"kind":"Name","value":"input"}},"type":{"kind":"NonNullType","type":{"kind":"NamedType","name":{"kind":"Name","value":"PassDto"}}}}],"selectionSet":{"kind":"SelectionSet","selections":[{"kind":"Field","name":{"kind":"Name","value":"pass"},"arguments":[{"kind":"Argument","name":{"kind":"Name","value":"input"},"value":{"kind":"Variable","name":{"kind":"Name","value":"input"}}}],"selectionSet":{"kind":"SelectionSet","selections":[{"kind":"Field","name":{"kind":"Name","value":"state"}},{"kind":"Field","name":{"kind":"Name","value":"sequenceNumber"}},{"kind":"Field","name":{"kind":"Name","value":"phase"}},{"kind":"Field","name":{"kind":"Name","value":"currentTurnPlayerId"}},{"kind":"Field","name":{"kind":"Name","value":"turnCount"}},{"kind":"Field","name":{"kind":"Name","value":"timestamp"}}]}}]}}]} as unknown as DocumentNode<PassMutation, PassMutationVariables>;
export const ToggleDoorDocument = {"kind":"Document","definitions":[{"kind":"OperationDefinition","operation":"mutation","name":{"kind":"Name","value":"ToggleDoor"},"variableDefinitions":[{"kind":"VariableDefinition","variable":{"kind":"Variable","name":{"kind":"Name","value":"input"}},"type":{"kind":"NonNullType","type":{"kind":"NamedType","name":{"kind":"Name","value":"ToggleDoorDto"}}}}],"selectionSet":{"kind":"SelectionSet","selections":[{"kind":"Field","name":{"kind":"Name","value":"toggleDoor"},"arguments":[{"kind":"Argument","name":{"kind":"Name","value":"input"},"value":{"kind":"Variable","name":{"kind":"Name","value":"input"}}}],"selectionSet":{"kind":"SelectionSet","selections":[{"kind":"Field","name":{"kind":"Name","value":"state"}},{"kind":"Field","name":{"kind":"Name","value":"sequenceNumber"}},{"kind":"Field","name":{"kind":"Name","value":"phase"}},{"kind":"Field","name":{"kind":"Name","value":"currentTurnPlayerId"}},{"kind":"Field","name":{"kind":"Name","value":"turnCount"}},{"kind":"Field","name":{"kind":"Name","value":"timestamp"}}]}}]}}]} as unknown as DocumentNode<ToggleDoorMutation, ToggleDoorMutationVariables>;
export const PlaySchemeDocument = {"kind":"Document","definitions":[{"kind":"OperationDefinition","operation":"mutation","name":{"kind":"Name","value":"PlayScheme"},"variableDefinitions":[{"kind":"VariableDefinition","variable":{"kind":"Variable","name":{"kind":"Name","value":"input"}},"type":{"kind":"NonNullType","type":{"kind":"NamedType","name":{"kind":"Name","value":"PlaySchemeDto"}}}}],"selectionSet":{"kind":"SelectionSet","selections":[{"kind":"Field","name":{"kind":"Name","value":"playScheme"},"arguments":[{"kind":"Argument","name":{"kind":"Name","value":"input"},"value":{"kind":"Variable","name":{"kind":"Name","value":"input"}}}],"selectionSet":{"kind":"SelectionSet","selections":[{"kind":"Field","name":{"kind":"Name","value":"state"}},{"kind":"Field","name":{"kind":"Name","value":"sequenceNumber"}},{"kind":"Field","name":{"kind":"Name","value":"phase"}},{"kind":"Field","name":{"kind":"Name","value":"currentTurnPlayerId"}},{"kind":"Field","name":{"kind":"Name","value":"turnCount"}},{"kind":"Field","name":{"kind":"Name","value":"timestamp"}}]}}]}}]} as unknown as DocumentNode<PlaySchemeMutation, PlaySchemeMutationVariables>;
export const ResolvePendingEffectDocument = {"kind":"Document","definitions":[{"kind":"OperationDefinition","operation":"mutation","name":{"kind":"Name","value":"ResolvePendingEffect"},"variableDefinitions":[{"kind":"VariableDefinition","variable":{"kind":"Variable","name":{"kind":"Name","value":"input"}},"type":{"kind":"NonNullType","type":{"kind":"NamedType","name":{"kind":"Name","value":"ResolvePendingEffectDto"}}}}],"selectionSet":{"kind":"SelectionSet","selections":[{"kind":"Field","name":{"kind":"Name","value":"resolvePendingEffect"},"arguments":[{"kind":"Argument","name":{"kind":"Name","value":"input"},"value":{"kind":"Variable","name":{"kind":"Name","value":"input"}}}],"selectionSet":{"kind":"SelectionSet","selections":[{"kind":"Field","name":{"kind":"Name","value":"state"}},{"kind":"Field","name":{"kind":"Name","value":"sequenceNumber"}},{"kind":"Field","name":{"kind":"Name","value":"phase"}},{"kind":"Field","name":{"kind":"Name","value":"currentTurnPlayerId"}},{"kind":"Field","name":{"kind":"Name","value":"turnCount"}},{"kind":"Field","name":{"kind":"Name","value":"timestamp"}}]}}]}}]} as unknown as DocumentNode<ResolvePendingEffectMutation, ResolvePendingEffectMutationVariables>;
export const SetStanceDocument = {"kind":"Document","definitions":[{"kind":"OperationDefinition","operation":"mutation","name":{"kind":"Name","value":"SetStance"},"variableDefinitions":[{"kind":"VariableDefinition","variable":{"kind":"Variable","name":{"kind":"Name","value":"input"}},"type":{"kind":"NonNullType","type":{"kind":"NamedType","name":{"kind":"Name","value":"SetStanceDto"}}}}],"selectionSet":{"kind":"SelectionSet","selections":[{"kind":"Field","name":{"kind":"Name","value":"setStance"},"arguments":[{"kind":"Argument","name":{"kind":"Name","value":"input"},"value":{"kind":"Variable","name":{"kind":"Name","value":"input"}}}],"selectionSet":{"kind":"SelectionSet","selections":[{"kind":"Field","name":{"kind":"Name","value":"state"}},{"kind":"Field","name":{"kind":"Name","value":"sequenceNumber"}},{"kind":"Field","name":{"kind":"Name","value":"phase"}},{"kind":"Field","name":{"kind":"Name","value":"currentTurnPlayerId"}},{"kind":"Field","name":{"kind":"Name","value":"turnCount"}},{"kind":"Field","name":{"kind":"Name","value":"timestamp"}}]}}]}}]} as unknown as DocumentNode<SetStanceMutation, SetStanceMutationVariables>;
export const PlaceFighterDocument = {"kind":"Document","definitions":[{"kind":"OperationDefinition","operation":"mutation","name":{"kind":"Name","value":"PlaceFighter"},"variableDefinitions":[{"kind":"VariableDefinition","variable":{"kind":"Variable","name":{"kind":"Name","value":"input"}},"type":{"kind":"NonNullType","type":{"kind":"NamedType","name":{"kind":"Name","value":"MoveFighterDto"}}}}],"selectionSet":{"kind":"SelectionSet","selections":[{"kind":"Field","name":{"kind":"Name","value":"moveFighter"},"arguments":[{"kind":"Argument","name":{"kind":"Name","value":"input"},"value":{"kind":"Variable","name":{"kind":"Name","value":"input"}}}],"selectionSet":{"kind":"SelectionSet","selections":[{"kind":"Field","name":{"kind":"Name","value":"state"}},{"kind":"Field","name":{"kind":"Name","value":"sequenceNumber"}},{"kind":"Field","name":{"kind":"Name","value":"phase"}},{"kind":"Field","name":{"kind":"Name","value":"currentTurnPlayerId"}},{"kind":"Field","name":{"kind":"Name","value":"turnCount"}},{"kind":"Field","name":{"kind":"Name","value":"timestamp"}}]}}]}}]} as unknown as DocumentNode<PlaceFighterMutation, PlaceFighterMutationVariables>;
export const ConfirmPlacementDocument = {"kind":"Document","definitions":[{"kind":"OperationDefinition","operation":"mutation","name":{"kind":"Name","value":"ConfirmPlacement"},"variableDefinitions":[{"kind":"VariableDefinition","variable":{"kind":"Variable","name":{"kind":"Name","value":"gameId"}},"type":{"kind":"NonNullType","type":{"kind":"NamedType","name":{"kind":"Name","value":"String"}}}}],"selectionSet":{"kind":"SelectionSet","selections":[{"kind":"Field","name":{"kind":"Name","value":"pass"},"arguments":[{"kind":"Argument","name":{"kind":"Name","value":"input"},"value":{"kind":"ObjectValue","fields":[{"kind":"ObjectField","name":{"kind":"Name","value":"gameId"},"value":{"kind":"Variable","name":{"kind":"Name","value":"gameId"}}}]}}],"selectionSet":{"kind":"SelectionSet","selections":[{"kind":"Field","name":{"kind":"Name","value":"state"}},{"kind":"Field","name":{"kind":"Name","value":"sequenceNumber"}},{"kind":"Field","name":{"kind":"Name","value":"phase"}},{"kind":"Field","name":{"kind":"Name","value":"currentTurnPlayerId"}},{"kind":"Field","name":{"kind":"Name","value":"turnCount"}},{"kind":"Field","name":{"kind":"Name","value":"timestamp"}}]}}]}}]} as unknown as DocumentNode<ConfirmPlacementMutation, ConfirmPlacementMutationVariables>;
export const MeDocument = {"kind":"Document","definitions":[{"kind":"OperationDefinition","operation":"query","name":{"kind":"Name","value":"Me"},"selectionSet":{"kind":"SelectionSet","selections":[{"kind":"Field","name":{"kind":"Name","value":"me"},"selectionSet":{"kind":"SelectionSet","selections":[{"kind":"Field","name":{"kind":"Name","value":"id"}},{"kind":"Field","name":{"kind":"Name","value":"email"}},{"kind":"Field","name":{"kind":"Name","value":"username"}},{"kind":"Field","name":{"kind":"Name","value":"avatar"}},{"kind":"Field","name":{"kind":"Name","value":"createdAt"}},{"kind":"Field","name":{"kind":"Name","value":"settings"},"selectionSet":{"kind":"SelectionSet","selections":[{"kind":"Field","name":{"kind":"Name","value":"theme"}},{"kind":"Field","name":{"kind":"Name","value":"soundEnabled"}},{"kind":"Field","name":{"kind":"Name","value":"musicEnabled"}},{"kind":"Field","name":{"kind":"Name","value":"language"}},{"kind":"Field","name":{"kind":"Name","value":"profileVisible"}}]}}]}}]}}]} as unknown as DocumentNode<MeQuery, MeQueryVariables>;
export const MyStatsDocument = {"kind":"Document","definitions":[{"kind":"OperationDefinition","operation":"query","name":{"kind":"Name","value":"MyStats"},"selectionSet":{"kind":"SelectionSet","selections":[{"kind":"Field","name":{"kind":"Name","value":"myStats"},"selectionSet":{"kind":"SelectionSet","selections":[{"kind":"Field","name":{"kind":"Name","value":"userId"}},{"kind":"Field","name":{"kind":"Name","value":"gamesPlayed"}},{"kind":"Field","name":{"kind":"Name","value":"gamesWon"}},{"kind":"Field","name":{"kind":"Name","value":"gamesLost"}},{"kind":"Field","name":{"kind":"Name","value":"winRate"}},{"kind":"Field","name":{"kind":"Name","value":"currentElo"}},{"kind":"Field","name":{"kind":"Name","value":"peakElo"}}]}}]}}]} as unknown as DocumentNode<MyStatsQuery, MyStatsQueryVariables>;
export const MySettingsDocument = {"kind":"Document","definitions":[{"kind":"OperationDefinition","operation":"query","name":{"kind":"Name","value":"MySettings"},"selectionSet":{"kind":"SelectionSet","selections":[{"kind":"Field","name":{"kind":"Name","value":"mySettings"},"selectionSet":{"kind":"SelectionSet","selections":[{"kind":"Field","name":{"kind":"Name","value":"theme"}},{"kind":"Field","name":{"kind":"Name","value":"soundEnabled"}},{"kind":"Field","name":{"kind":"Name","value":"musicEnabled"}},{"kind":"Field","name":{"kind":"Name","value":"language"}},{"kind":"Field","name":{"kind":"Name","value":"profileVisible"}}]}}]}}]} as unknown as DocumentNode<MySettingsQuery, MySettingsQueryVariables>;
export const GetCardsDocument = {"kind":"Document","definitions":[{"kind":"OperationDefinition","operation":"query","name":{"kind":"Name","value":"GetCards"},"variableDefinitions":[{"kind":"VariableDefinition","variable":{"kind":"Variable","name":{"kind":"Name","value":"page"}},"type":{"kind":"NonNullType","type":{"kind":"NamedType","name":{"kind":"Name","value":"Int"}}}},{"kind":"VariableDefinition","variable":{"kind":"Variable","name":{"kind":"Name","value":"limit"}},"type":{"kind":"NonNullType","type":{"kind":"NamedType","name":{"kind":"Name","value":"Int"}}}}],"selectionSet":{"kind":"SelectionSet","selections":[{"kind":"Field","name":{"kind":"Name","value":"cardList"},"arguments":[{"kind":"Argument","name":{"kind":"Name","value":"page"},"value":{"kind":"Variable","name":{"kind":"Name","value":"page"}}},{"kind":"Argument","name":{"kind":"Name","value":"limit"},"value":{"kind":"Variable","name":{"kind":"Name","value":"limit"}}}],"selectionSet":{"kind":"SelectionSet","selections":[{"kind":"Field","name":{"kind":"Name","value":"items"},"selectionSet":{"kind":"SelectionSet","selections":[{"kind":"Field","name":{"kind":"Name","value":"id"}},{"kind":"Field","name":{"kind":"Name","value":"name"}},{"kind":"Field","name":{"kind":"Name","value":"nameEn"}},{"kind":"Field","name":{"kind":"Name","value":"nameRu"}},{"kind":"Field","name":{"kind":"Name","value":"cardType"}},{"kind":"Field","name":{"kind":"Name","value":"subType"}},{"kind":"Field","name":{"kind":"Name","value":"attackValue"}},{"kind":"Field","name":{"kind":"Name","value":"defenseValue"}},{"kind":"Field","name":{"kind":"Name","value":"boostValue"}},{"kind":"Field","name":{"kind":"Name","value":"bannerName"}},{"kind":"Field","name":{"kind":"Name","value":"count"}},{"kind":"Field","name":{"kind":"Name","value":"heroId"}},{"kind":"Field","name":{"kind":"Name","value":"imageUrl"}},{"kind":"Field","name":{"kind":"Name","value":"imageUrlRu"}}]}},{"kind":"Field","name":{"kind":"Name","value":"total"}}]}}]}}]} as unknown as DocumentNode<GetCardsQuery, GetCardsQueryVariables>;
export const GetCardDocument = {"kind":"Document","definitions":[{"kind":"OperationDefinition","operation":"query","name":{"kind":"Name","value":"GetCard"},"variableDefinitions":[{"kind":"VariableDefinition","variable":{"kind":"Variable","name":{"kind":"Name","value":"id"}},"type":{"kind":"NonNullType","type":{"kind":"NamedType","name":{"kind":"Name","value":"String"}}}}],"selectionSet":{"kind":"SelectionSet","selections":[{"kind":"Field","name":{"kind":"Name","value":"card"},"arguments":[{"kind":"Argument","name":{"kind":"Name","value":"id"},"value":{"kind":"Variable","name":{"kind":"Name","value":"id"}}}],"selectionSet":{"kind":"SelectionSet","selections":[{"kind":"Field","name":{"kind":"Name","value":"id"}},{"kind":"Field","name":{"kind":"Name","value":"title"}},{"kind":"Field","name":{"kind":"Name","value":"type"}},{"kind":"Field","name":{"kind":"Name","value":"value"}},{"kind":"Field","name":{"kind":"Name","value":"boost"}},{"kind":"Field","name":{"kind":"Name","value":"quantity"}},{"kind":"Field","name":{"kind":"Name","value":"characterName"}},{"kind":"Field","name":{"kind":"Name","value":"imageUrl"}},{"kind":"Field","name":{"kind":"Name","value":"imageUrlRu"}},{"kind":"Field","name":{"kind":"Name","value":"effects"},"selectionSet":{"kind":"SelectionSet","selections":[{"kind":"Field","name":{"kind":"Name","value":"id"}},{"kind":"Field","name":{"kind":"Name","value":"timing"}},{"kind":"Field","name":{"kind":"Name","value":"text"}}]}}]}}]}}]} as unknown as DocumentNode<GetCardQuery, GetCardQueryVariables>;
export const GetGameDocument = {"kind":"Document","definitions":[{"kind":"OperationDefinition","operation":"query","name":{"kind":"Name","value":"GetGame"},"variableDefinitions":[{"kind":"VariableDefinition","variable":{"kind":"Variable","name":{"kind":"Name","value":"id"}},"type":{"kind":"NonNullType","type":{"kind":"NamedType","name":{"kind":"Name","value":"String"}}}}],"selectionSet":{"kind":"SelectionSet","selections":[{"kind":"Field","name":{"kind":"Name","value":"game"},"arguments":[{"kind":"Argument","name":{"kind":"Name","value":"id"},"value":{"kind":"Variable","name":{"kind":"Name","value":"id"}}}],"selectionSet":{"kind":"SelectionSet","selections":[{"kind":"Field","name":{"kind":"Name","value":"id"}},{"kind":"Field","name":{"kind":"Name","value":"mode"}},{"kind":"Field","name":{"kind":"Name","value":"status"}},{"kind":"Field","name":{"kind":"Name","value":"hostId"}},{"kind":"Field","name":{"kind":"Name","value":"boardId"}},{"kind":"Field","name":{"kind":"Name","value":"winnerId"}},{"kind":"Field","name":{"kind":"Name","value":"createdAt"}},{"kind":"Field","name":{"kind":"Name","value":"updatedAt"}},{"kind":"Field","name":{"kind":"Name","value":"startedAt"}},{"kind":"Field","name":{"kind":"Name","value":"endedAt"}},{"kind":"Field","name":{"kind":"Name","value":"phase"}},{"kind":"Field","name":{"kind":"Name","value":"currentTurn"}},{"kind":"Field","name":{"kind":"Name","value":"players"},"selectionSet":{"kind":"SelectionSet","selections":[{"kind":"Field","name":{"kind":"Name","value":"id"}},{"kind":"Field","name":{"kind":"Name","value":"userId"}},{"kind":"Field","name":{"kind":"Name","value":"username"}},{"kind":"Field","name":{"kind":"Name","value":"avatar"}},{"kind":"Field","name":{"kind":"Name","value":"heroId"}},{"kind":"Field","name":{"kind":"Name","value":"isReady"}},{"kind":"Field","name":{"kind":"Name","value":"hasPassed"}},{"kind":"Field","name":{"kind":"Name","value":"seatOrder"}}]}}]}}]}}]} as unknown as DocumentNode<GetGameQuery, GetGameQueryVariables>;
export const MyGamesDocument = {"kind":"Document","definitions":[{"kind":"OperationDefinition","operation":"query","name":{"kind":"Name","value":"MyGames"},"variableDefinitions":[{"kind":"VariableDefinition","variable":{"kind":"Variable","name":{"kind":"Name","value":"filters"}},"type":{"kind":"NamedType","name":{"kind":"Name","value":"GameFiltersDto"}}}],"selectionSet":{"kind":"SelectionSet","selections":[{"kind":"Field","name":{"kind":"Name","value":"myGames"},"arguments":[{"kind":"Argument","name":{"kind":"Name","value":"filters"},"value":{"kind":"Variable","name":{"kind":"Name","value":"filters"}}}],"selectionSet":{"kind":"SelectionSet","selections":[{"kind":"Field","name":{"kind":"Name","value":"id"}},{"kind":"Field","name":{"kind":"Name","value":"mode"}},{"kind":"Field","name":{"kind":"Name","value":"status"}},{"kind":"Field","name":{"kind":"Name","value":"hostId"}},{"kind":"Field","name":{"kind":"Name","value":"createdAt"}},{"kind":"Field","name":{"kind":"Name","value":"phase"}},{"kind":"Field","name":{"kind":"Name","value":"currentTurn"}},{"kind":"Field","name":{"kind":"Name","value":"players"},"selectionSet":{"kind":"SelectionSet","selections":[{"kind":"Field","name":{"kind":"Name","value":"userId"}},{"kind":"Field","name":{"kind":"Name","value":"username"}},{"kind":"Field","name":{"kind":"Name","value":"avatar"}},{"kind":"Field","name":{"kind":"Name","value":"heroId"}},{"kind":"Field","name":{"kind":"Name","value":"isReady"}}]}}]}}]}}]} as unknown as DocumentNode<MyGamesQuery, MyGamesQueryVariables>;
export const AvailableGamesDocument = {"kind":"Document","definitions":[{"kind":"OperationDefinition","operation":"query","name":{"kind":"Name","value":"AvailableGames"},"variableDefinitions":[{"kind":"VariableDefinition","variable":{"kind":"Variable","name":{"kind":"Name","value":"mode"}},"type":{"kind":"NamedType","name":{"kind":"Name","value":"String"}}},{"kind":"VariableDefinition","variable":{"kind":"Variable","name":{"kind":"Name","value":"limit"}},"type":{"kind":"NamedType","name":{"kind":"Name","value":"Float"}}}],"selectionSet":{"kind":"SelectionSet","selections":[{"kind":"Field","name":{"kind":"Name","value":"availableGames"},"arguments":[{"kind":"Argument","name":{"kind":"Name","value":"mode"},"value":{"kind":"Variable","name":{"kind":"Name","value":"mode"}}},{"kind":"Argument","name":{"kind":"Name","value":"limit"},"value":{"kind":"Variable","name":{"kind":"Name","value":"limit"}}}],"selectionSet":{"kind":"SelectionSet","selections":[{"kind":"Field","name":{"kind":"Name","value":"id"}},{"kind":"Field","name":{"kind":"Name","value":"mode"}},{"kind":"Field","name":{"kind":"Name","value":"status"}},{"kind":"Field","name":{"kind":"Name","value":"players"},"selectionSet":{"kind":"SelectionSet","selections":[{"kind":"Field","name":{"kind":"Name","value":"userId"}},{"kind":"Field","name":{"kind":"Name","value":"username"}},{"kind":"Field","name":{"kind":"Name","value":"avatar"}},{"kind":"Field","name":{"kind":"Name","value":"heroId"}}]}}]}}]}}]} as unknown as DocumentNode<AvailableGamesQuery, AvailableGamesQueryVariables>;
export const GetGameStateDocument = {"kind":"Document","definitions":[{"kind":"OperationDefinition","operation":"query","name":{"kind":"Name","value":"GetGameState"},"variableDefinitions":[{"kind":"VariableDefinition","variable":{"kind":"Variable","name":{"kind":"Name","value":"gameId"}},"type":{"kind":"NonNullType","type":{"kind":"NamedType","name":{"kind":"Name","value":"String"}}}}],"selectionSet":{"kind":"SelectionSet","selections":[{"kind":"Field","name":{"kind":"Name","value":"gameState"},"arguments":[{"kind":"Argument","name":{"kind":"Name","value":"gameId"},"value":{"kind":"Variable","name":{"kind":"Name","value":"gameId"}}}],"selectionSet":{"kind":"SelectionSet","selections":[{"kind":"Field","name":{"kind":"Name","value":"id"}},{"kind":"Field","name":{"kind":"Name","value":"gameId"}},{"kind":"Field","name":{"kind":"Name","value":"state"}},{"kind":"Field","name":{"kind":"Name","value":"sequenceNumber"}},{"kind":"Field","name":{"kind":"Name","value":"currentTurnPlayerId"}},{"kind":"Field","name":{"kind":"Name","value":"phase"}},{"kind":"Field","name":{"kind":"Name","value":"turnCount"}},{"kind":"Field","name":{"kind":"Name","value":"updatedAt"}}]}}]}}]} as unknown as DocumentNode<GetGameStateQuery, GetGameStateQueryVariables>;
export const GetGameSequenceDocument = {"kind":"Document","definitions":[{"kind":"OperationDefinition","operation":"query","name":{"kind":"Name","value":"GetGameSequence"},"variableDefinitions":[{"kind":"VariableDefinition","variable":{"kind":"Variable","name":{"kind":"Name","value":"gameId"}},"type":{"kind":"NonNullType","type":{"kind":"NamedType","name":{"kind":"Name","value":"String"}}}}],"selectionSet":{"kind":"SelectionSet","selections":[{"kind":"Field","name":{"kind":"Name","value":"gameSequence"},"arguments":[{"kind":"Argument","name":{"kind":"Name","value":"gameId"},"value":{"kind":"Variable","name":{"kind":"Name","value":"gameId"}}}]}]}}]} as unknown as DocumentNode<GetGameSequenceQuery, GetGameSequenceQueryVariables>;
export const EventsSinceDocument = {"kind":"Document","definitions":[{"kind":"OperationDefinition","operation":"query","name":{"kind":"Name","value":"EventsSince"},"variableDefinitions":[{"kind":"VariableDefinition","variable":{"kind":"Variable","name":{"kind":"Name","value":"gameId"}},"type":{"kind":"NonNullType","type":{"kind":"NamedType","name":{"kind":"Name","value":"String"}}}},{"kind":"VariableDefinition","variable":{"kind":"Variable","name":{"kind":"Name","value":"sinceSequence"}},"type":{"kind":"NonNullType","type":{"kind":"NamedType","name":{"kind":"Name","value":"Float"}}}}],"selectionSet":{"kind":"SelectionSet","selections":[{"kind":"Field","name":{"kind":"Name","value":"eventsSince"},"arguments":[{"kind":"Argument","name":{"kind":"Name","value":"gameId"},"value":{"kind":"Variable","name":{"kind":"Name","value":"gameId"}}},{"kind":"Argument","name":{"kind":"Name","value":"sinceSequence"},"value":{"kind":"Variable","name":{"kind":"Name","value":"sinceSequence"}}}],"selectionSet":{"kind":"SelectionSet","selections":[{"kind":"Field","name":{"kind":"Name","value":"gameId"}},{"kind":"Field","name":{"kind":"Name","value":"events"},"selectionSet":{"kind":"SelectionSet","selections":[{"kind":"Field","name":{"kind":"Name","value":"sequenceNumber"}},{"kind":"Field","name":{"kind":"Name","value":"type"}},{"kind":"Field","name":{"kind":"Name","value":"gameId"}},{"kind":"Field","name":{"kind":"Name","value":"payload"}},{"kind":"Field","name":{"kind":"Name","value":"timestamp"}}]}},{"kind":"Field","name":{"kind":"Name","value":"lastSequence"}},{"kind":"Field","name":{"kind":"Name","value":"hasMore"}}]}}]}}]} as unknown as DocumentNode<EventsSinceQuery, EventsSinceQueryVariables>;
export const HeroesDocument = {"kind":"Document","definitions":[{"kind":"OperationDefinition","operation":"query","name":{"kind":"Name","value":"Heroes"},"selectionSet":{"kind":"SelectionSet","selections":[{"kind":"Field","name":{"kind":"Name","value":"heroes"},"selectionSet":{"kind":"SelectionSet","selections":[{"kind":"Field","name":{"kind":"Name","value":"id"}},{"kind":"Field","name":{"kind":"Name","value":"name"}},{"kind":"Field","name":{"kind":"Name","value":"health"}},{"kind":"Field","name":{"kind":"Name","value":"movement"}},{"kind":"Field","name":{"kind":"Name","value":"set"}},{"kind":"Field","name":{"kind":"Name","value":"fighterType"}},{"kind":"Field","name":{"kind":"Name","value":"sidekickCount"}},{"kind":"Field","name":{"kind":"Name","value":"sidekickHealth"}}]}}]}}]} as unknown as DocumentNode<HeroesQuery, HeroesQueryVariables>;
export const HeroDocument = {"kind":"Document","definitions":[{"kind":"OperationDefinition","operation":"query","name":{"kind":"Name","value":"Hero"},"variableDefinitions":[{"kind":"VariableDefinition","variable":{"kind":"Variable","name":{"kind":"Name","value":"id"}},"type":{"kind":"NonNullType","type":{"kind":"NamedType","name":{"kind":"Name","value":"String"}}}}],"selectionSet":{"kind":"SelectionSet","selections":[{"kind":"Field","name":{"kind":"Name","value":"hero"},"arguments":[{"kind":"Argument","name":{"kind":"Name","value":"id"},"value":{"kind":"Variable","name":{"kind":"Name","value":"id"}}}],"selectionSet":{"kind":"SelectionSet","selections":[{"kind":"Field","name":{"kind":"Name","value":"id"}},{"kind":"Field","name":{"kind":"Name","value":"name"}},{"kind":"Field","name":{"kind":"Name","value":"health"}},{"kind":"Field","name":{"kind":"Name","value":"movement"}},{"kind":"Field","name":{"kind":"Name","value":"set"}},{"kind":"Field","name":{"kind":"Name","value":"fighterType"}},{"kind":"Field","name":{"kind":"Name","value":"abilities"},"selectionSet":{"kind":"SelectionSet","selections":[{"kind":"Field","name":{"kind":"Name","value":"id"}},{"kind":"Field","name":{"kind":"Name","value":"name"}},{"kind":"Field","name":{"kind":"Name","value":"text"}},{"kind":"Field","name":{"kind":"Name","value":"trigger"}}]}},{"kind":"Field","name":{"kind":"Name","value":"cards"},"selectionSet":{"kind":"SelectionSet","selections":[{"kind":"Field","name":{"kind":"Name","value":"id"}},{"kind":"Field","name":{"kind":"Name","value":"title"}},{"kind":"Field","name":{"kind":"Name","value":"type"}},{"kind":"Field","name":{"kind":"Name","value":"value"}},{"kind":"Field","name":{"kind":"Name","value":"boost"}},{"kind":"Field","name":{"kind":"Name","value":"quantity"}},{"kind":"Field","name":{"kind":"Name","value":"imageUrl"}},{"kind":"Field","name":{"kind":"Name","value":"imageUrlRu"}}]}}]}}]}}]} as unknown as DocumentNode<HeroQuery, HeroQueryVariables>;
export const BoardsDocument = {"kind":"Document","definitions":[{"kind":"OperationDefinition","operation":"query","name":{"kind":"Name","value":"Boards"},"selectionSet":{"kind":"SelectionSet","selections":[{"kind":"Field","name":{"kind":"Name","value":"boards"},"selectionSet":{"kind":"SelectionSet","selections":[{"kind":"Field","name":{"kind":"Name","value":"id"}},{"kind":"Field","name":{"kind":"Name","value":"name"}},{"kind":"Field","name":{"kind":"Name","value":"width"}},{"kind":"Field","name":{"kind":"Name","value":"height"}},{"kind":"Field","name":{"kind":"Name","value":"recommendedPlayers"}},{"kind":"Field","name":{"kind":"Name","value":"imageUrl"}},{"kind":"Field","name":{"kind":"Name","value":"spaces"},"selectionSet":{"kind":"SelectionSet","selections":[{"kind":"Field","name":{"kind":"Name","value":"position"},"selectionSet":{"kind":"SelectionSet","selections":[{"kind":"Field","name":{"kind":"Name","value":"x"}},{"kind":"Field","name":{"kind":"Name","value":"y"}}]}},{"kind":"Field","name":{"kind":"Name","value":"zones"}},{"kind":"Field","name":{"kind":"Name","value":"isObstacle"}}]}}]}}]}}]} as unknown as DocumentNode<BoardsQuery, BoardsQueryVariables>;
export const BoardDocument = {"kind":"Document","definitions":[{"kind":"OperationDefinition","operation":"query","name":{"kind":"Name","value":"Board"},"variableDefinitions":[{"kind":"VariableDefinition","variable":{"kind":"Variable","name":{"kind":"Name","value":"id"}},"type":{"kind":"NonNullType","type":{"kind":"NamedType","name":{"kind":"Name","value":"String"}}}}],"selectionSet":{"kind":"SelectionSet","selections":[{"kind":"Field","name":{"kind":"Name","value":"board"},"arguments":[{"kind":"Argument","name":{"kind":"Name","value":"id"},"value":{"kind":"Variable","name":{"kind":"Name","value":"id"}}}],"selectionSet":{"kind":"SelectionSet","selections":[{"kind":"Field","name":{"kind":"Name","value":"id"}},{"kind":"Field","name":{"kind":"Name","value":"name"}},{"kind":"Field","name":{"kind":"Name","value":"width"}},{"kind":"Field","name":{"kind":"Name","value":"height"}},{"kind":"Field","name":{"kind":"Name","value":"recommendedPlayers"}},{"kind":"Field","name":{"kind":"Name","value":"imageUrl"}},{"kind":"Field","name":{"kind":"Name","value":"spaces"},"selectionSet":{"kind":"SelectionSet","selections":[{"kind":"Field","name":{"kind":"Name","value":"position"},"selectionSet":{"kind":"SelectionSet","selections":[{"kind":"Field","name":{"kind":"Name","value":"x"}},{"kind":"Field","name":{"kind":"Name","value":"y"}}]}},{"kind":"Field","name":{"kind":"Name","value":"zones"}},{"kind":"Field","name":{"kind":"Name","value":"isObstacle"}}]}}]}}]}}]} as unknown as DocumentNode<BoardQuery, BoardQueryVariables>;
export const ContentSummaryDocument = {"kind":"Document","definitions":[{"kind":"OperationDefinition","operation":"query","name":{"kind":"Name","value":"ContentSummary"},"selectionSet":{"kind":"SelectionSet","selections":[{"kind":"Field","name":{"kind":"Name","value":"contentSummary"},"selectionSet":{"kind":"SelectionSet","selections":[{"kind":"Field","name":{"kind":"Name","value":"heroesCount"}},{"kind":"Field","name":{"kind":"Name","value":"boardsCount"}},{"kind":"Field","name":{"kind":"Name","value":"setsCount"}},{"kind":"Field","name":{"kind":"Name","value":"version"}},{"kind":"Field","name":{"kind":"Name","value":"sets"}}]}}]}}]} as unknown as DocumentNode<ContentSummaryQuery, ContentSummaryQueryVariables>;
export const SetsDocument = {"kind":"Document","definitions":[{"kind":"OperationDefinition","operation":"query","name":{"kind":"Name","value":"Sets"},"selectionSet":{"kind":"SelectionSet","selections":[{"kind":"Field","name":{"kind":"Name","value":"sets"}}]}}]} as unknown as DocumentNode<SetsQuery, SetsQueryVariables>;
export const AllHeroesDocument = {"kind":"Document","definitions":[{"kind":"OperationDefinition","operation":"query","name":{"kind":"Name","value":"AllHeroes"},"selectionSet":{"kind":"SelectionSet","selections":[{"kind":"Field","name":{"kind":"Name","value":"heroes"},"selectionSet":{"kind":"SelectionSet","selections":[{"kind":"Field","name":{"kind":"Name","value":"id"}},{"kind":"Field","name":{"kind":"Name","value":"name"}},{"kind":"Field","name":{"kind":"Name","value":"health"}},{"kind":"Field","name":{"kind":"Name","value":"movement"}},{"kind":"Field","name":{"kind":"Name","value":"set"}},{"kind":"Field","name":{"kind":"Name","value":"fighterType"}},{"kind":"Field","name":{"kind":"Name","value":"sidekickCount"}},{"kind":"Field","name":{"kind":"Name","value":"sidekickHealth"}},{"kind":"Field","name":{"kind":"Name","value":"urls"},"selectionSet":{"kind":"SelectionSet","selections":[{"kind":"Field","name":{"kind":"Name","value":"avatar"}},{"kind":"Field","name":{"kind":"Name","value":"mini"}},{"kind":"Field","name":{"kind":"Name","value":"cardCover"}}]}}]}}]}}]} as unknown as DocumentNode<AllHeroesQuery, AllHeroesQueryVariables>;
export const HeroDetailsDocument = {"kind":"Document","definitions":[{"kind":"OperationDefinition","operation":"query","name":{"kind":"Name","value":"HeroDetails"},"variableDefinitions":[{"kind":"VariableDefinition","variable":{"kind":"Variable","name":{"kind":"Name","value":"id"}},"type":{"kind":"NonNullType","type":{"kind":"NamedType","name":{"kind":"Name","value":"String"}}}}],"selectionSet":{"kind":"SelectionSet","selections":[{"kind":"Field","name":{"kind":"Name","value":"hero"},"arguments":[{"kind":"Argument","name":{"kind":"Name","value":"id"},"value":{"kind":"Variable","name":{"kind":"Name","value":"id"}}}],"selectionSet":{"kind":"SelectionSet","selections":[{"kind":"Field","name":{"kind":"Name","value":"id"}},{"kind":"Field","name":{"kind":"Name","value":"name"}},{"kind":"Field","name":{"kind":"Name","value":"health"}},{"kind":"Field","name":{"kind":"Name","value":"movement"}},{"kind":"Field","name":{"kind":"Name","value":"set"}},{"kind":"Field","name":{"kind":"Name","value":"fighterType"}},{"kind":"Field","name":{"kind":"Name","value":"sidekickCount"}},{"kind":"Field","name":{"kind":"Name","value":"sidekickHealth"}},{"kind":"Field","name":{"kind":"Name","value":"urls"},"selectionSet":{"kind":"SelectionSet","selections":[{"kind":"Field","name":{"kind":"Name","value":"avatar"}},{"kind":"Field","name":{"kind":"Name","value":"mini"}},{"kind":"Field","name":{"kind":"Name","value":"cardCover"}}]}},{"kind":"Field","name":{"kind":"Name","value":"abilities"},"selectionSet":{"kind":"SelectionSet","selections":[{"kind":"Field","name":{"kind":"Name","value":"id"}},{"kind":"Field","name":{"kind":"Name","value":"name"}},{"kind":"Field","name":{"kind":"Name","value":"text"}},{"kind":"Field","name":{"kind":"Name","value":"trigger"}}]}},{"kind":"Field","name":{"kind":"Name","value":"cards"},"selectionSet":{"kind":"SelectionSet","selections":[{"kind":"Field","name":{"kind":"Name","value":"id"}},{"kind":"Field","name":{"kind":"Name","value":"title"}},{"kind":"Field","name":{"kind":"Name","value":"type"}},{"kind":"Field","name":{"kind":"Name","value":"value"}},{"kind":"Field","name":{"kind":"Name","value":"boost"}},{"kind":"Field","name":{"kind":"Name","value":"quantity"}},{"kind":"Field","name":{"kind":"Name","value":"imageUrl"}},{"kind":"Field","name":{"kind":"Name","value":"imageUrlRu"}}]}}]}}]}}]} as unknown as DocumentNode<HeroDetailsQuery, HeroDetailsQueryVariables>;
export const HeroesBySetDocument = {"kind":"Document","definitions":[{"kind":"OperationDefinition","operation":"query","name":{"kind":"Name","value":"HeroesBySet"},"variableDefinitions":[{"kind":"VariableDefinition","variable":{"kind":"Variable","name":{"kind":"Name","value":"set"}},"type":{"kind":"NonNullType","type":{"kind":"NamedType","name":{"kind":"Name","value":"String"}}}}],"selectionSet":{"kind":"SelectionSet","selections":[{"kind":"Field","name":{"kind":"Name","value":"heroesBySet"},"arguments":[{"kind":"Argument","name":{"kind":"Name","value":"set"},"value":{"kind":"Variable","name":{"kind":"Name","value":"set"}}}],"selectionSet":{"kind":"SelectionSet","selections":[{"kind":"Field","name":{"kind":"Name","value":"id"}},{"kind":"Field","name":{"kind":"Name","value":"name"}},{"kind":"Field","name":{"kind":"Name","value":"health"}},{"kind":"Field","name":{"kind":"Name","value":"movement"}},{"kind":"Field","name":{"kind":"Name","value":"set"}},{"kind":"Field","name":{"kind":"Name","value":"fighterType"}},{"kind":"Field","name":{"kind":"Name","value":"sidekickCount"}},{"kind":"Field","name":{"kind":"Name","value":"sidekickHealth"}},{"kind":"Field","name":{"kind":"Name","value":"urls"},"selectionSet":{"kind":"SelectionSet","selections":[{"kind":"Field","name":{"kind":"Name","value":"avatar"}},{"kind":"Field","name":{"kind":"Name","value":"mini"}},{"kind":"Field","name":{"kind":"Name","value":"cardCover"}}]}}]}}]}}]} as unknown as DocumentNode<HeroesBySetQuery, HeroesBySetQueryVariables>;
export const HeroStanceOptionsDocument = {"kind":"Document","definitions":[{"kind":"OperationDefinition","operation":"query","name":{"kind":"Name","value":"HeroStanceOptions"},"variableDefinitions":[{"kind":"VariableDefinition","variable":{"kind":"Variable","name":{"kind":"Name","value":"heroSlug"}},"type":{"kind":"NonNullType","type":{"kind":"NamedType","name":{"kind":"Name","value":"String"}}}}],"selectionSet":{"kind":"SelectionSet","selections":[{"kind":"Field","name":{"kind":"Name","value":"heroStances"},"arguments":[{"kind":"Argument","name":{"kind":"Name","value":"heroSlug"},"value":{"kind":"Variable","name":{"kind":"Name","value":"heroSlug"}}}],"selectionSet":{"kind":"SelectionSet","selections":[{"kind":"Field","name":{"kind":"Name","value":"id"}},{"kind":"Field","name":{"kind":"Name","value":"label"}},{"kind":"Field","name":{"kind":"Name","value":"isDefault"}}]}}]}}]} as unknown as DocumentNode<HeroStanceOptionsQuery, HeroStanceOptionsQueryVariables>;
export const LobbyAvailableGamesDocument = {"kind":"Document","definitions":[{"kind":"OperationDefinition","operation":"query","name":{"kind":"Name","value":"LobbyAvailableGames"},"variableDefinitions":[{"kind":"VariableDefinition","variable":{"kind":"Variable","name":{"kind":"Name","value":"mode"}},"type":{"kind":"NamedType","name":{"kind":"Name","value":"String"}}},{"kind":"VariableDefinition","variable":{"kind":"Variable","name":{"kind":"Name","value":"limit"}},"type":{"kind":"NamedType","name":{"kind":"Name","value":"Float"}}}],"selectionSet":{"kind":"SelectionSet","selections":[{"kind":"Field","name":{"kind":"Name","value":"availableGames"},"arguments":[{"kind":"Argument","name":{"kind":"Name","value":"mode"},"value":{"kind":"Variable","name":{"kind":"Name","value":"mode"}}},{"kind":"Argument","name":{"kind":"Name","value":"limit"},"value":{"kind":"Variable","name":{"kind":"Name","value":"limit"}}}],"selectionSet":{"kind":"SelectionSet","selections":[{"kind":"Field","name":{"kind":"Name","value":"id"}},{"kind":"Field","name":{"kind":"Name","value":"mode"}},{"kind":"Field","name":{"kind":"Name","value":"status"}},{"kind":"Field","name":{"kind":"Name","value":"host"},"selectionSet":{"kind":"SelectionSet","selections":[{"kind":"Field","name":{"kind":"Name","value":"id"}},{"kind":"Field","name":{"kind":"Name","value":"username"}},{"kind":"Field","name":{"kind":"Name","value":"avatar"}}]}},{"kind":"Field","name":{"kind":"Name","value":"opponent"},"selectionSet":{"kind":"SelectionSet","selections":[{"kind":"Field","name":{"kind":"Name","value":"id"}},{"kind":"Field","name":{"kind":"Name","value":"username"}},{"kind":"Field","name":{"kind":"Name","value":"avatar"}}]}},{"kind":"Field","name":{"kind":"Name","value":"boardId"}},{"kind":"Field","name":{"kind":"Name","value":"createdAt"}},{"kind":"Field","name":{"kind":"Name","value":"updatedAt"}}]}}]}}]} as unknown as DocumentNode<LobbyAvailableGamesQuery, LobbyAvailableGamesQueryVariables>;
export const QueueStatusDocument = {"kind":"Document","definitions":[{"kind":"OperationDefinition","operation":"query","name":{"kind":"Name","value":"QueueStatus"},"variableDefinitions":[{"kind":"VariableDefinition","variable":{"kind":"Variable","name":{"kind":"Name","value":"mode"}},"type":{"kind":"NonNullType","type":{"kind":"NamedType","name":{"kind":"Name","value":"String"}}}}],"selectionSet":{"kind":"SelectionSet","selections":[{"kind":"Field","name":{"kind":"Name","value":"queueStatus"},"arguments":[{"kind":"Argument","name":{"kind":"Name","value":"mode"},"value":{"kind":"Variable","name":{"kind":"Name","value":"mode"}}}],"selectionSet":{"kind":"SelectionSet","selections":[{"kind":"Field","name":{"kind":"Name","value":"inQueue"}},{"kind":"Field","name":{"kind":"Name","value":"mode"}},{"kind":"Field","name":{"kind":"Name","value":"position"}},{"kind":"Field","name":{"kind":"Name","value":"totalPlayers"}},{"kind":"Field","name":{"kind":"Name","value":"estimatedWaitTime"}},{"kind":"Field","name":{"kind":"Name","value":"joinedAt"}}]}}]}}]} as unknown as DocumentNode<QueueStatusQuery, QueueStatusQueryVariables>;
export const PenaltyInfoDocument = {"kind":"Document","definitions":[{"kind":"OperationDefinition","operation":"query","name":{"kind":"Name","value":"PenaltyInfo"},"selectionSet":{"kind":"SelectionSet","selections":[{"kind":"Field","name":{"kind":"Name","value":"penaltyInfo"},"selectionSet":{"kind":"SelectionSet","selections":[{"kind":"Field","name":{"kind":"Name","value":"canJoinQueue"}},{"kind":"Field","name":{"kind":"Name","value":"declineCount"}},{"kind":"Field","name":{"kind":"Name","value":"tempBanUntil"}},{"kind":"Field","name":{"kind":"Name","value":"penaltyElo"}},{"kind":"Field","name":{"kind":"Name","value":"reason"}}]}}]}}]} as unknown as DocumentNode<PenaltyInfoQuery, PenaltyInfoQueryVariables>;
export const RoomInfoDocument = {"kind":"Document","definitions":[{"kind":"OperationDefinition","operation":"query","name":{"kind":"Name","value":"RoomInfo"},"variableDefinitions":[{"kind":"VariableDefinition","variable":{"kind":"Variable","name":{"kind":"Name","value":"id"}},"type":{"kind":"NonNullType","type":{"kind":"NamedType","name":{"kind":"Name","value":"String"}}}}],"selectionSet":{"kind":"SelectionSet","selections":[{"kind":"Field","name":{"kind":"Name","value":"game"},"arguments":[{"kind":"Argument","name":{"kind":"Name","value":"id"},"value":{"kind":"Variable","name":{"kind":"Name","value":"id"}}}],"selectionSet":{"kind":"SelectionSet","selections":[{"kind":"Field","name":{"kind":"Name","value":"id"}},{"kind":"Field","name":{"kind":"Name","value":"code"}},{"kind":"Field","name":{"kind":"Name","value":"status"}},{"kind":"Field","name":{"kind":"Name","value":"mode"}},{"kind":"Field","name":{"kind":"Name","value":"hostId"}},{"kind":"Field","name":{"kind":"Name","value":"boardId"}},{"kind":"Field","name":{"kind":"Name","value":"phase"}},{"kind":"Field","name":{"kind":"Name","value":"createdAt"}},{"kind":"Field","name":{"kind":"Name","value":"players"},"selectionSet":{"kind":"SelectionSet","selections":[{"kind":"Field","name":{"kind":"Name","value":"id"}},{"kind":"Field","name":{"kind":"Name","value":"userId"}},{"kind":"Field","name":{"kind":"Name","value":"username"}},{"kind":"Field","name":{"kind":"Name","value":"avatar"}},{"kind":"Field","name":{"kind":"Name","value":"heroId"}},{"kind":"Field","name":{"kind":"Name","value":"isReady"}},{"kind":"Field","name":{"kind":"Name","value":"seatOrder"}}]}}]}}]}}]} as unknown as DocumentNode<RoomInfoQuery, RoomInfoQueryVariables>;
export const ValidSpawnZonesDocument = {"kind":"Document","definitions":[{"kind":"OperationDefinition","operation":"query","name":{"kind":"Name","value":"ValidSpawnZones"},"variableDefinitions":[{"kind":"VariableDefinition","variable":{"kind":"Variable","name":{"kind":"Name","value":"gameId"}},"type":{"kind":"NonNullType","type":{"kind":"NamedType","name":{"kind":"Name","value":"String"}}}},{"kind":"VariableDefinition","variable":{"kind":"Variable","name":{"kind":"Name","value":"playerId"}},"type":{"kind":"NonNullType","type":{"kind":"NamedType","name":{"kind":"Name","value":"String"}}}}],"selectionSet":{"kind":"SelectionSet","selections":[{"kind":"Field","name":{"kind":"Name","value":"gameState"},"arguments":[{"kind":"Argument","name":{"kind":"Name","value":"gameId"},"value":{"kind":"Variable","name":{"kind":"Name","value":"gameId"}}}],"selectionSet":{"kind":"SelectionSet","selections":[{"kind":"Field","name":{"kind":"Name","value":"id"}},{"kind":"Field","name":{"kind":"Name","value":"gameId"}},{"kind":"Field","name":{"kind":"Name","value":"state"}},{"kind":"Field","name":{"kind":"Name","value":"sequenceNumber"}},{"kind":"Field","name":{"kind":"Name","value":"currentTurnPlayerId"}},{"kind":"Field","name":{"kind":"Name","value":"phase"}},{"kind":"Field","name":{"kind":"Name","value":"turnCount"}},{"kind":"Field","name":{"kind":"Name","value":"updatedAt"}}]}}]}}]} as unknown as DocumentNode<ValidSpawnZonesQuery, ValidSpawnZonesQueryVariables>;
export const GameStateUpdatedDocument = {"kind":"Document","definitions":[{"kind":"OperationDefinition","operation":"subscription","name":{"kind":"Name","value":"GameStateUpdated"},"variableDefinitions":[{"kind":"VariableDefinition","variable":{"kind":"Variable","name":{"kind":"Name","value":"gameId"}},"type":{"kind":"NonNullType","type":{"kind":"NamedType","name":{"kind":"Name","value":"String"}}}},{"kind":"VariableDefinition","variable":{"kind":"Variable","name":{"kind":"Name","value":"since"}},"type":{"kind":"NamedType","name":{"kind":"Name","value":"Float"}}}],"selectionSet":{"kind":"SelectionSet","selections":[{"kind":"Field","name":{"kind":"Name","value":"gameStateUpdated"},"arguments":[{"kind":"Argument","name":{"kind":"Name","value":"gameId"},"value":{"kind":"Variable","name":{"kind":"Name","value":"gameId"}}},{"kind":"Argument","name":{"kind":"Name","value":"since"},"value":{"kind":"Variable","name":{"kind":"Name","value":"since"}}}],"selectionSet":{"kind":"SelectionSet","selections":[{"kind":"Field","name":{"kind":"Name","value":"gameId"}},{"kind":"Field","name":{"kind":"Name","value":"sequenceNumber"}},{"kind":"Field","name":{"kind":"Name","value":"phase"}},{"kind":"Field","name":{"kind":"Name","value":"turnCount"}},{"kind":"Field","name":{"kind":"Name","value":"currentTurnPlayerId"}},{"kind":"Field","name":{"kind":"Name","value":"players"}},{"kind":"Field","name":{"kind":"Name","value":"fighters"}},{"kind":"Field","name":{"kind":"Name","value":"handZones"}},{"kind":"Field","name":{"kind":"Name","value":"boardState"}},{"kind":"Field","name":{"kind":"Name","value":"metadata"}}]}}]}}]} as unknown as DocumentNode<GameStateUpdatedSubscription, GameStateUpdatedSubscriptionVariables>;
export const AttackInitiatedDocument = {"kind":"Document","definitions":[{"kind":"OperationDefinition","operation":"subscription","name":{"kind":"Name","value":"AttackInitiated"},"variableDefinitions":[{"kind":"VariableDefinition","variable":{"kind":"Variable","name":{"kind":"Name","value":"gameId"}},"type":{"kind":"NonNullType","type":{"kind":"NamedType","name":{"kind":"Name","value":"String"}}}}],"selectionSet":{"kind":"SelectionSet","selections":[{"kind":"Field","name":{"kind":"Name","value":"attackInitiated"},"arguments":[{"kind":"Argument","name":{"kind":"Name","value":"gameId"},"value":{"kind":"Variable","name":{"kind":"Name","value":"gameId"}}}],"selectionSet":{"kind":"SelectionSet","selections":[{"kind":"Field","name":{"kind":"Name","value":"type"}},{"kind":"Field","name":{"kind":"Name","value":"gameId"}},{"kind":"Field","name":{"kind":"Name","value":"sequenceNumber"}},{"kind":"Field","name":{"kind":"Name","value":"timestamp"}},{"kind":"Field","name":{"kind":"Name","value":"payload"}}]}}]}}]} as unknown as DocumentNode<AttackInitiatedSubscription, AttackInitiatedSubscriptionVariables>;
export const DefensePlayedDocument = {"kind":"Document","definitions":[{"kind":"OperationDefinition","operation":"subscription","name":{"kind":"Name","value":"DefensePlayed"},"variableDefinitions":[{"kind":"VariableDefinition","variable":{"kind":"Variable","name":{"kind":"Name","value":"gameId"}},"type":{"kind":"NonNullType","type":{"kind":"NamedType","name":{"kind":"Name","value":"String"}}}}],"selectionSet":{"kind":"SelectionSet","selections":[{"kind":"Field","name":{"kind":"Name","value":"defensePlayed"},"arguments":[{"kind":"Argument","name":{"kind":"Name","value":"gameId"},"value":{"kind":"Variable","name":{"kind":"Name","value":"gameId"}}}],"selectionSet":{"kind":"SelectionSet","selections":[{"kind":"Field","name":{"kind":"Name","value":"type"}},{"kind":"Field","name":{"kind":"Name","value":"gameId"}},{"kind":"Field","name":{"kind":"Name","value":"sequenceNumber"}},{"kind":"Field","name":{"kind":"Name","value":"timestamp"}},{"kind":"Field","name":{"kind":"Name","value":"payload"}}]}}]}}]} as unknown as DocumentNode<DefensePlayedSubscription, DefensePlayedSubscriptionVariables>;
export const CombatResolvedDocument = {"kind":"Document","definitions":[{"kind":"OperationDefinition","operation":"subscription","name":{"kind":"Name","value":"CombatResolved"},"variableDefinitions":[{"kind":"VariableDefinition","variable":{"kind":"Variable","name":{"kind":"Name","value":"gameId"}},"type":{"kind":"NonNullType","type":{"kind":"NamedType","name":{"kind":"Name","value":"String"}}}}],"selectionSet":{"kind":"SelectionSet","selections":[{"kind":"Field","name":{"kind":"Name","value":"combatResolved"},"arguments":[{"kind":"Argument","name":{"kind":"Name","value":"gameId"},"value":{"kind":"Variable","name":{"kind":"Name","value":"gameId"}}}],"selectionSet":{"kind":"SelectionSet","selections":[{"kind":"Field","name":{"kind":"Name","value":"type"}},{"kind":"Field","name":{"kind":"Name","value":"gameId"}},{"kind":"Field","name":{"kind":"Name","value":"sequenceNumber"}},{"kind":"Field","name":{"kind":"Name","value":"timestamp"}},{"kind":"Field","name":{"kind":"Name","value":"payload"}}]}}]}}]} as unknown as DocumentNode<CombatResolvedSubscription, CombatResolvedSubscriptionVariables>;
export const TurnChangedDocument = {"kind":"Document","definitions":[{"kind":"OperationDefinition","operation":"subscription","name":{"kind":"Name","value":"TurnChanged"},"variableDefinitions":[{"kind":"VariableDefinition","variable":{"kind":"Variable","name":{"kind":"Name","value":"gameId"}},"type":{"kind":"NonNullType","type":{"kind":"NamedType","name":{"kind":"Name","value":"String"}}}}],"selectionSet":{"kind":"SelectionSet","selections":[{"kind":"Field","name":{"kind":"Name","value":"turnChanged"},"arguments":[{"kind":"Argument","name":{"kind":"Name","value":"gameId"},"value":{"kind":"Variable","name":{"kind":"Name","value":"gameId"}}}],"selectionSet":{"kind":"SelectionSet","selections":[{"kind":"Field","name":{"kind":"Name","value":"playerId"}},{"kind":"Field","name":{"kind":"Name","value":"turnCount"}},{"kind":"Field","name":{"kind":"Name","value":"phase"}}]}}]}}]} as unknown as DocumentNode<TurnChangedSubscription, TurnChangedSubscriptionVariables>;
export const PlayerJoinedDocument = {"kind":"Document","definitions":[{"kind":"OperationDefinition","operation":"subscription","name":{"kind":"Name","value":"PlayerJoined"},"variableDefinitions":[{"kind":"VariableDefinition","variable":{"kind":"Variable","name":{"kind":"Name","value":"gameId"}},"type":{"kind":"NonNullType","type":{"kind":"NamedType","name":{"kind":"Name","value":"String"}}}}],"selectionSet":{"kind":"SelectionSet","selections":[{"kind":"Field","name":{"kind":"Name","value":"playerJoined"},"arguments":[{"kind":"Argument","name":{"kind":"Name","value":"gameId"},"value":{"kind":"Variable","name":{"kind":"Name","value":"gameId"}}}],"selectionSet":{"kind":"SelectionSet","selections":[{"kind":"Field","name":{"kind":"Name","value":"type"}},{"kind":"Field","name":{"kind":"Name","value":"gameId"}},{"kind":"Field","name":{"kind":"Name","value":"sequenceNumber"}},{"kind":"Field","name":{"kind":"Name","value":"timestamp"}},{"kind":"Field","name":{"kind":"Name","value":"payload"}}]}}]}}]} as unknown as DocumentNode<PlayerJoinedSubscription, PlayerJoinedSubscriptionVariables>;
export const PlayerLeftDocument = {"kind":"Document","definitions":[{"kind":"OperationDefinition","operation":"subscription","name":{"kind":"Name","value":"PlayerLeft"},"variableDefinitions":[{"kind":"VariableDefinition","variable":{"kind":"Variable","name":{"kind":"Name","value":"gameId"}},"type":{"kind":"NonNullType","type":{"kind":"NamedType","name":{"kind":"Name","value":"String"}}}}],"selectionSet":{"kind":"SelectionSet","selections":[{"kind":"Field","name":{"kind":"Name","value":"playerLeft"},"arguments":[{"kind":"Argument","name":{"kind":"Name","value":"gameId"},"value":{"kind":"Variable","name":{"kind":"Name","value":"gameId"}}}],"selectionSet":{"kind":"SelectionSet","selections":[{"kind":"Field","name":{"kind":"Name","value":"type"}},{"kind":"Field","name":{"kind":"Name","value":"gameId"}},{"kind":"Field","name":{"kind":"Name","value":"sequenceNumber"}},{"kind":"Field","name":{"kind":"Name","value":"timestamp"}},{"kind":"Field","name":{"kind":"Name","value":"payload"}}]}}]}}]} as unknown as DocumentNode<PlayerLeftSubscription, PlayerLeftSubscriptionVariables>;
export const GameEndedDocument = {"kind":"Document","definitions":[{"kind":"OperationDefinition","operation":"subscription","name":{"kind":"Name","value":"GameEnded"},"variableDefinitions":[{"kind":"VariableDefinition","variable":{"kind":"Variable","name":{"kind":"Name","value":"gameId"}},"type":{"kind":"NonNullType","type":{"kind":"NamedType","name":{"kind":"Name","value":"String"}}}}],"selectionSet":{"kind":"SelectionSet","selections":[{"kind":"Field","name":{"kind":"Name","value":"gameEnded"},"arguments":[{"kind":"Argument","name":{"kind":"Name","value":"gameId"},"value":{"kind":"Variable","name":{"kind":"Name","value":"gameId"}}}],"selectionSet":{"kind":"SelectionSet","selections":[{"kind":"Field","name":{"kind":"Name","value":"type"}},{"kind":"Field","name":{"kind":"Name","value":"gameId"}},{"kind":"Field","name":{"kind":"Name","value":"sequenceNumber"}},{"kind":"Field","name":{"kind":"Name","value":"timestamp"}},{"kind":"Field","name":{"kind":"Name","value":"payload"}}]}}]}}]} as unknown as DocumentNode<GameEndedSubscription, GameEndedSubscriptionVariables>;
export const MatchFoundDocument = {"kind":"Document","definitions":[{"kind":"OperationDefinition","operation":"subscription","name":{"kind":"Name","value":"MatchFound"},"variableDefinitions":[{"kind":"VariableDefinition","variable":{"kind":"Variable","name":{"kind":"Name","value":"userId"}},"type":{"kind":"NonNullType","type":{"kind":"NamedType","name":{"kind":"Name","value":"String"}}}}],"selectionSet":{"kind":"SelectionSet","selections":[{"kind":"Field","name":{"kind":"Name","value":"matchFound"},"arguments":[{"kind":"Argument","name":{"kind":"Name","value":"userId"},"value":{"kind":"Variable","name":{"kind":"Name","value":"userId"}}}],"selectionSet":{"kind":"SelectionSet","selections":[{"kind":"Field","name":{"kind":"Name","value":"gameId"}},{"kind":"Field","name":{"kind":"Name","value":"opponentId"}},{"kind":"Field","name":{"kind":"Name","value":"opponentUsername"}},{"kind":"Field","name":{"kind":"Name","value":"opponentRating"}},{"kind":"Field","name":{"kind":"Name","value":"mode"}},{"kind":"Field","name":{"kind":"Name","value":"expiresAt"}}]}}]}}]} as unknown as DocumentNode<MatchFoundSubscription, MatchFoundSubscriptionVariables>;