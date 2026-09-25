/**
 * Прямые GraphQL-запросы к реальному API для текстового тестера игры.
 * Используется raw fetch вместо urql, чтобы выполнять запросы
 * под разными JWT-токенами (P1 = админ, P2 = тестовый юзер).
 */

const BACKEND_URL = import.meta.env.VITE_BACKEND_URL || 'http://localhost:3000';

export class GqlError extends Error {
  constructor(message: string, public readonly errors: any[]) {
    super(message);
  }
}

export async function gqlRequest<T = any>(
  query: string,
  variables: Record<string, unknown>,
  token?: string,
): Promise<T> {
  const res = await fetch(`${BACKEND_URL}/graphql`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: JSON.stringify({ query, variables }),
  });
  const json = await res.json();
  if (json.errors?.length) {
    throw new GqlError(json.errors.map((e: any) => e.message).join('; '), json.errors);
  }
  return json.data as T;
}

/** Достаёт userId из JWT payload (sub / userId / id). */
export function decodeJwtUserId(token: string): string | null {
  try {
    const part = token.split('.')[1];
    if (!part) return null;
    const payload = JSON.parse(atob(part.replace(/-/g, '+').replace(/_/g, '/')));
    return payload.sub || payload.userId || payload.id || null;
  } catch {
    return null;
  }
}

// ============================================
// Auth
// ============================================

export const LOGIN = `
  mutation Login($email: String!, $password: String!) {
    login(input: { email: $email, password: $password }) {
      accessToken
      user { id username email }
    }
  }
`;

export const REGISTER = `
  mutation Register($email: String!, $username: String!, $password: String!) {
    register(input: { email: $email, username: $username, password: $password }) {
      accessToken
      user { id username email }
    }
  }
`;

// ============================================
// Справочники (admin-токен)
// ============================================

export const HERO_OPTIONS = `
  query HeroOptions {
    heroList(page: 1, limit: 300, sortBy: "name", sortOrder: "asc") {
      items { id name health fighterType }
    }
  }
`;

export const BOARD_OPTIONS = `
  query BoardOptions {
    boardList(page: 1, limit: 100, sortBy: "name", sortOrder: "asc") {
      items { id name width height }
    }
  }
`;

// ============================================
// Лайфсайкл игры
// ============================================

const GAME_FIELDS = `
  id
  code
  status
  mode
  hostId
  boardId
  phase
  currentTurn
  players { id userId username heroId isReady seatOrder }
`;

export const CREATE_GAME = `
  mutation CreateGame($mode: GameMode, $boardId: String) {
    createGame(input: { mode: $mode, boardId: $boardId }) { ${GAME_FIELDS} }
  }
`;

export const JOIN_GAME = `
  mutation JoinGame($gameId: String!) {
    joinGame(input: { gameId: $gameId }) { ${GAME_FIELDS} }
  }
`;

export const SELECT_HERO = `
  mutation SelectHero($gameId: String!, $heroId: String!) {
    selectHero(gameId: $gameId, heroId: $heroId) { ${GAME_FIELDS} }
  }
`;

export const TOGGLE_READY = `
  mutation ToggleReady($gameId: String!) {
    toggleReady(gameId: $gameId) { ${GAME_FIELDS} }
  }
`;

export const START_GAME = `
  mutation StartGame($gameId: String!) {
    startGame(gameId: $gameId) { ${GAME_FIELDS} }
  }
`;

export const ABORT_GAME = `
  mutation AbortGame($gameId: String!) {
    abortGame(gameId: $gameId) { id status }
  }
`;

export const GAME_STATE = `
  query GameState($gameId: String!) {
    gameState(gameId: $gameId) {
      state
      sequenceNumber
      currentTurnPlayerId
      phase
      turnCount
    }
  }
`;

// ============================================
// Игровые действия
// ============================================

const MUTATION_RESULT = `
  state
  sequenceNumber
  timestamp
  phase
  currentTurnPlayerId
  turnCount
`;

export const MOVE_FIGHTER = `
  mutation MoveFighter($input: MoveFighterDto!) {
    moveFighter(input: $input) { ${MUTATION_RESULT} }
  }
`;

export const MANEUVER = `
  mutation Maneuver($input: ManeuverDto!) {
    maneuver(input: $input) { ${MUTATION_RESULT} }
  }
`;

export const BEGIN_MANEUVER = `
  mutation BeginManeuver($input: BeginManeuverDto!) {
    beginManeuver(input: $input) { ${MUTATION_RESULT} }
  }
`;

export const DISCARD_TO_LIMIT = `
  mutation DiscardToLimit($input: DiscardToLimitDto!) {
    discardToLimit(input: $input) { ${MUTATION_RESULT} }
  }
`;

export const ATTACK = `
  mutation Attack($input: AttackDto!) {
    attack(input: $input) { ${MUTATION_RESULT} }
  }
`;

export const PLAY_DEFENSE = `
  mutation PlayDefense($input: PlayDefenseDto!) {
    playDefense(input: $input) { ${MUTATION_RESULT} }
  }
`;

export const RESOLVE_COMBAT = `
  mutation ResolveCombat($input: ResolveCombatDto!) {
    resolveCombat(input: $input) { ${MUTATION_RESULT} }
  }
`;

export const END_TURN = `
  mutation EndTurn($input: EndTurnDto!) {
    endTurn(input: $input) { ${MUTATION_RESULT} }
  }
`;

export const PASS = `
  mutation Pass($input: PassDto!) {
    pass(input: $input) { ${MUTATION_RESULT} }
  }
`;

export const PLAY_SCHEME = `
  mutation PlayScheme($input: PlaySchemeDto!) {
    playScheme(input: $input) { ${MUTATION_RESULT} }
  }
`;

export const RESOLVE_PENDING_EFFECT = `
  mutation ResolvePendingEffect($input: ResolvePendingEffectDto!) {
    resolvePendingEffect(input: $input) { ${MUTATION_RESULT} }
  }
`;

export const DECLINE_PENDING_EFFECT = `
  mutation DeclinePendingEffect($input: DeclinePendingEffectDto!) {
    declinePendingEffect(input: $input) { ${MUTATION_RESULT} }
  }
`;

export const TOGGLE_DOOR = `
  mutation ToggleDoor($input: ToggleDoorDto!) {
    toggleDoor(input: $input) { ${MUTATION_RESULT} }
  }
`;
