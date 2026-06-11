/**
 * API Service
 *
 * GraphQL wrapper для backend API.
 * Адаптировано из BaseApiService паттерна alix1912/e2e.
 */

import { URLS, MUTATIONS, QUERIES } from '../../fixtures/data';

// ============================================================
// Types
// ============================================================

export interface GraphQLResponse<T = unknown> {
  data?: T;
  errors?: Array<{ message: string; code?: string }>;
}

export interface Position {
  x: number;
  y: number;
}

// Auth DTOs
export interface RegisterDto {
  email: string;
  username: string;
  password: string;
}

export interface LoginDto {
  email: string;
  password: string;
}

export interface AuthResponse {
  accessToken: string;
  refreshToken: string;
  user: {
    id: string;
    email: string;
    username: string;
  };
}

// Game DTOs
export interface CreateGameDto {
  name: string;
  gameMode: string;
  maxPlayers: number;
}

export interface JoinGameDto {
  gameId: string;
  heroId: string;
}

export interface ManeuverDto {
  gameId: string;
  fighterId: string;
  cardId: string;
  path: Position[];
}

export interface MoveFighterDto {
  gameId: string;
  fighterId: string;
  x: number;
  y: number;
}

export interface AttackDto {
  gameId: string;
  attackerId: string;
  targetId: string;
  cardId: string;
}

export interface PlayDefenseDto {
  gameId: string;
  cardId: string;
}

export interface ResolveCombatDto {
  gameId: string;
}

export interface EndTurnDto {
  gameId: string;
}

export interface PassDto {
  gameId: string;
}

export interface ToggleDoorDto {
  gameId: string;
  x: number;
  y: number;
}

export interface GameMutationResult {
  state: string;
  sequenceNumber: number;
  timestamp: Date;
  phase: string;
  currentTurnPlayerId?: string;
  turnCount?: number;
}

// ============================================================
// API Service
// ============================================================

export class ApiService {
  private readonly token: string;

  constructor(token?: string) {
    this.token = token || '';
  }

  /**
   * Базовый метод для выполнения GraphQL запросов
   */
  private async request<T>(
    query: string,
    variables?: Record<string, unknown>,
  ): Promise<T> {
    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
    };

    if (this.token) {
      headers['Authorization'] = `Bearer ${this.token}`;
    }

    const response = await fetch(URLS.GRAPHQL, {
      method: 'POST',
      headers,
      body: JSON.stringify({
        query,
        variables,
      }),
    });

    if (!response.ok) {
      throw new Error(`GraphQL request failed: ${response.status} ${response.statusText}`);
    }

    const result: GraphQLResponse<T> = await response.json();

    if (result.errors && result.errors.length > 0) {
      const error = result.errors[0];
      throw new Error(error.message || 'GraphQL error');
    }

    if (!result.data) {
      throw new Error('No data returned from GraphQL');
    }

    return result.data;
  }

  // ============================================================
  // Auth Methods
  // ============================================================

  /**
   * Регистрация нового пользователя
   */
  async register(input: RegisterDto): Promise<AuthResponse> {
    const response = await this.request<{ register: AuthResponse }>(
      MUTATIONS.REGISTER,
      { input },
    );
    return response.register;
  }

  /**
   * Вход в систему
   */
  async login(input: LoginDto): Promise<AuthResponse> {
    const response = await this.request<{ login: AuthResponse }>(
      MUTATIONS.LOGIN,
      { input },
    );
    return response.login;
  }

  /**
   * Создаёт новый экземпляр ApiService с токеном
   */
  withToken(token: string): ApiService {
    return new ApiService(token);
  }

  // ============================================================
  // Game Methods
  // ============================================================

  /**
   * Создание игры
   */
  async createGame(input: CreateGameDto): Promise<{ id: string; status: string }> {
    const response = await this.request<{ createGame: { id: string; status: string } }>(
      MUTATIONS.CREATE_GAME,
      { input },
    );
    return response.createGame;
  }

  /**
   * Присоединение к игре
   */
  async joinGame(input: JoinGameDto): Promise<{ id: string; status: string }> {
    const response = await this.request<{ joinGame: { id: string; status: string } }>(
      MUTATIONS.JOIN_GAME,
      { input },
    );
    return response.joinGame;
  }

  /**
   * Покинуть игру
   */
  async leaveGame(gameId: string): Promise<void> {
    await this.request(MUTATIONS.LEAVE_GAME, { gameId });
  }

  // ============================================================
  // Gameplay Actions
  // ============================================================

  /**
   * Выполнить манёвр - перемещение + розыгрыш карты
   */
  async maneuver(dto: ManeuverDto): Promise<GameMutationResult> {
    const response = await this.request<{ maneuver: GameMutationResult }>(
      MUTATIONS.MANEUVER,
      { input: dto },
    );
    return response.maneuver;
  }

  /**
   * Переместить бойца
   */
  async moveFighter(dto: MoveFighterDto): Promise<GameMutationResult> {
    const response = await this.request<{ moveFighter: GameMutationResult }>(
      MUTATIONS.MOVE_FIGHTER,
      { input: dto },
    );
    return response.moveFighter;
  }

  /**
   * Объявить атаку
   */
  async attack(dto: AttackDto): Promise<GameMutationResult> {
    const response = await this.request<{ attack: GameMutationResult }>(
      MUTATIONS.ATTACK,
      { input: dto },
    );
    return response.attack;
  }

  /**
   * Сыграть защиту
   */
  async playDefense(dto: PlayDefenseDto): Promise<GameMutationResult> {
    const response = await this.request<{ playDefense: GameMutationResult }>(
      MUTATIONS.PLAY_DEFENSE,
      { input: dto },
    );
    return response.playDefense;
  }

  /**
   * Разрешить бой
   */
  async resolveCombat(dto: ResolveCombatDto): Promise<GameMutationResult> {
    const response = await this.request<{ resolveCombat: GameMutationResult }>(
      MUTATIONS.RESOLVE_COMBAT,
      { input: dto },
    );
    return response.resolveCombat;
  }

  /**
   * Завершить ход
   */
  async endTurn(dto: EndTurnDto): Promise<GameMutationResult> {
    const response = await this.request<{ endTurn: GameMutationResult }>(
      MUTATIONS.END_TURN,
      { input: dto },
    );
    return response.endTurn;
  }

  /**
   * Сбросить карту (pass)
   */
  async pass(dto: PassDto): Promise<GameMutationResult> {
    const response = await this.request<{ pass: GameMutationResult }>(
      MUTATIONS.PASS,
      { input: dto },
    );
    return response.pass;
  }

  /**
   * Открыть/закрыть дверь
   */
  async toggleDoor(dto: ToggleDoorDto): Promise<GameMutationResult> {
    const response = await this.request<{ toggleDoor: GameMutationResult }>(
      MUTATIONS.TOGGLE_DOOR,
      { input: dto },
    );
    return response.toggleDoor;
  }

  // ============================================================
  // Queries
  // ============================================================

  /**
   * Получить информацию о текущем пользователе
   */
  async getMe(): Promise<{ id: string; email: string; username: string }> {
    const response = await this.request<{ me: { id: string; email: string; username: string } }>(
      QUERIES.ME,
    );
    return response.me;
  }

  /**
   * Получить информацию об игре
   */
  async getGame(gameId: string): Promise<unknown> {
    const response = await this.request<{ game: unknown }>(
      QUERIES.GAME,
      { id: gameId },
    );
    return response.game;
  }

  /**
   * Получить список героев
   */
  async getHeroes(): Promise<unknown[]> {
    const response = await this.request<{ heroes: unknown[] }>(
      QUERIES.HEROES,
    );
    return response.heroes;
  }

  /**
   * Получить карты героя
   */
  async getCards(heroId: string): Promise<unknown[]> {
    const response = await this.request<{ cards: unknown[] }>(
      QUERIES.CARDS,
      { heroId },
    );
    return response.cards;
  }
}
