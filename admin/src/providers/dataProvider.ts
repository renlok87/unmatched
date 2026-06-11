import { DataProvider } from '@refinedev/core';
import { createClient, fetchExchange, gql } from 'urql';

const BACKEND_URL = import.meta.env.VITE_BACKEND_URL || 'http://localhost:3000';

const getToken = () => localStorage.getItem('accessToken');

export const client = createClient({
  url: `${BACKEND_URL}/graphql`,
  exchanges: [fetchExchange],
  fetchOptions: () => {
    const token = getToken();
    return token ? { headers: { Authorization: `Bearer ${token}` } } : {};
  },
});

// GraphQL queries для каждого ресурса
const GET_HEROES_LIST = gql`
  query GetHeroesList($page: Int!, $limit: Int!, $search: String, $sortBy: String, $sortOrder: String) {
    heroList(page: $page, limit: $limit, search: $search, sortBy: $sortBy, sortOrder: $sortOrder) {
      items {
        id
        name
        nameEn
        nameRu
        set
        health
        fighterType
        imageUrl
        avatarUrl
        createdAt
      }
      total
    }
  }
`;

const GET_HERO = gql`
  query GetHero($id: String!) {
    adminHero(id: $id) {
      id
      name
      nameEn
      nameRu
      set
      health
      fighterType
      movement
      color
      ability
      deckCards
      properties
      hasTokens
      sidekicks
      additionalMinis
      imageUrl
      avatarUrl
      characterCardUrl
      miniModelUrl
      createdAt
      updatedAt
    }
  }
`;

const GET_CARDS_LIST = gql`
  query GetCardsList($page: Int!, $limit: Int!, $search: String, $sortBy: String, $sortOrder: String) {
    cardList(page: $page, limit: $limit, search: $search, sortBy: $sortBy, sortOrder: $sortOrder) {
      items {
        id
        name
        nameEn
        nameRu
        cardType
        subType
        attackValue
        defenseValue
        boostValue
        bannerName
        count
        heroId
        imageUrl
        imageUrlRu
        createdAt
      }
      total
    }
  }
`;

const GET_CARD = gql`
  query GetCard($id: String!) {
    adminCard(id: $id) {
      id
      name
      nameEn
      nameRu
      cardType
      subType
      attackValue
      defenseValue
      boostValue
      bannerName
      effects
      text
      textEn
      textRu
      effectAfter
      effectDuring
      effectBoost
      effectImmediately
      effectOngoing
      heroId
      count
      imageUrl
      imageUrlRu
      createdAt
      updatedAt
    }
  }
`;

const GET_BOARDS_LIST = gql`
  query GetBoardsList($page: Int!, $limit: Int!, $search: String, $sortBy: String, $sortOrder: String) {
    boardList(page: $page, limit: $limit, search: $search, sortBy: $sortBy, sortOrder: $sortOrder) {
      items {
        id
        name
        nameEn
        nameRu
        set
        width
        height
        imageUrl
        imageUrlDark
        createdAt
      }
      total
    }
  }
`;

const GET_BOARD = gql`
  query GetBoard($id: String!) {
    adminBoard(id: $id) {
      id
      name
      nameEn
      nameRu
      set
      width
      height
      cells
      features
      imageUrl
      imageUrlDark
      createdAt
      updatedAt
    }
  }
`;

const GET_USERS_LIST = gql`
  query GetUsersList($page: Int!, $limit: Int!, $search: String, $sortBy: String, $sortOrder: String) {
    userList(page: $page, limit: $limit, search: $search, sortBy: $sortBy, sortOrder: $sortOrder) {
      users {
        id
        username
        email
        avatar
        role
        createdAt
        emailVerified
        stats {
          gamesPlayed
          gamesWon
          currentElo
        }
      }
      total
    }
  }
`;

const GET_USER = gql`
  query GetUser($id: String!) {
    adminUser(id: $id) {
      id
      username
      email
      avatar
      role
      createdAt
      updatedAt
      deletedAt
      emailVerified
      stats {
        gamesPlayed
        gamesWon
        currentElo
      }
    }
  }
`;

const GET_GAME = gql`
  query GetGame($id: String!) {
    adminGame(id: $id) {
      id
      code
      mode
      status
      createdAt
      startedAt
      finishedAt
      boardId
      boardName
      gamePlayers {
        id
        playerId
        heroId
        status
        username
        avatar
      }
    }
  }
`;

const GET_GAMES_LIST = gql`
  query GetGamesList($page: Int!, $limit: Int!, $search: String, $sortBy: String, $sortOrder: String) {
    gameList(page: $page, limit: $limit, search: $search, sortBy: $sortBy, sortOrder: $sortOrder) {
      items {
        id
        status
        createdAt
        boardId
        boardName
        gamePlayers {
          username
          avatar
        }
      }
      total
    }
  }
`;

const GET_MATCHMAKING_QUEUE = gql`
  query GetMatchmakingQueue {
    matchmakingQueue {
      items {
        id
        userId
        username
        avatar
        mode
        elo
        joinedAt
        position
      }
      total
      activeQueues
    }
  }
`;

const GET_AUDIT_LOGS = gql`
  query GetAuditLogs($page: Int!, $limit: Int!) {
    auditLogs(page: $page, limit: $limit) {
      items {
        id
        action
        userId
        ipAddress
        success
        timestamp
        metadata
      }
      total
    }
  }
`;

// Мутации
const CREATE_HERO = gql`
  mutation CreateHero($input: CreateHeroInput!) {
    createHero(input: $input) {
      id
      name
      nameEn
      nameRu
      set
      health
      fighterType
      movement
      color
      ability
      hasTokens
      sidekicks
      imageUrl
      avatarUrl
      characterCardUrl
      miniModelUrl
      createdAt
    }
  }
`;

const UPDATE_HERO = gql`
  mutation UpdateHero($id: String!, $input: UpdateHeroInput!) {
    updateHero(id: $id, input: $input) {
      id
      name
      nameEn
      nameRu
      set
      health
      fighterType
      movement
      color
      ability
      hasTokens
      sidekicks
      imageUrl
      avatarUrl
      characterCardUrl
      miniModelUrl
      createdAt
    }
  }
`;

const DELETE_HERO = gql`
  mutation DeleteHero($id: String!) {
    deleteHero(id: $id)
  }
`;

const CREATE_CARD = gql`
  mutation CreateCard($input: CreateCardInput!) {
    createCard(input: $input) {
      id
      name
      nameEn
      nameRu
      cardType
      subType
      attackValue
      defenseValue
      boostValue
      bannerName
      count
      heroId
      imageUrl
      imageUrlRu
      createdAt
    }
  }
`;

const UPDATE_CARD = gql`
  mutation UpdateCard($id: String!, $input: UpdateCardInput!) {
    updateCard(id: $id, input: $input) {
      id
      name
      nameEn
      nameRu
      cardType
      subType
      attackValue
      defenseValue
      boostValue
      bannerName
      count
      heroId
      imageUrl
      imageUrlRu
      createdAt
    }
  }
`;

const DELETE_CARD = gql`
  mutation DeleteCard($id: String!) {
    deleteCard(id: $id)
  }
`;

const CREATE_BOARD = gql`
  mutation CreateBoard($input: CreateBoardInput!) {
    createBoard(input: $input) {
      id
      name
      nameEn
      nameRu
      set
      width
      height
      imageUrl
      imageUrlDark
      createdAt
    }
  }
`;

const UPDATE_BOARD = gql`
  mutation UpdateBoard($id: String!, $input: UpdateBoardInput!) {
    updateBoard(id: $id, input: $input) {
      id
      name
      nameEn
      nameRu
      set
      width
      height
      imageUrl
      imageUrlDark
      createdAt
    }
  }
`;

const DELETE_BOARD = gql`
  mutation DeleteBoard($id: String!) {
    deleteBoard(id: $id)
  }
`;

const UPDATE_USER = gql`
  mutation UpdateUser($id: String!, $input: UpdateUserInput!) {
    updateUser(id: $id, input: $input) {
      id
      username
      email
      role
    }
  }
`;

export const dataProvider: DataProvider = {
  getList: async ({ resource, pagination, filters, sorters }) => {
    let query;
    let extractItems: (data: any) => { items: any[]; total: number };
    let supportsSearch = false;

    switch (resource) {
      case 'heroes':
        query = GET_HEROES_LIST;
        extractItems = (data) => ({ items: data.heroList.items, total: data.heroList.total });
        supportsSearch = true;
        break;
      case 'cards':
        query = GET_CARDS_LIST;
        extractItems = (data) => ({ items: data.cardList.items, total: data.cardList.total });
        supportsSearch = true;
        break;
      case 'boards':
        query = GET_BOARDS_LIST;
        extractItems = (data) => ({ items: data.boardList.items, total: data.boardList.total });
        supportsSearch = true;
        break;
      case 'users':
        query = GET_USERS_LIST;
        extractItems = (data) => ({ items: data.userList.users, total: data.userList.total });
        supportsSearch = true;
        break;
      case 'games':
        query = GET_GAMES_LIST;
        extractItems = (data) => ({ items: data.gameList.items, total: data.gameList.total });
        supportsSearch = true;
        break;
      case 'matchmakingQueue':
        query = GET_MATCHMAKING_QUEUE;
        extractItems = (data) => ({ items: data.matchmakingQueue.items, total: data.matchmakingQueue.total });
        break;
      case 'auditLogs':
        query = GET_AUDIT_LOGS;
        extractItems = (data) => ({ items: data.auditLogs.items, total: data.auditLogs.total });
        break;
      default:
        throw new Error(`No getList query found for resource: ${resource}`);
    }

    const page = pagination?.currentPage || 1;
    const perPage = pagination?.pageSize || 20;

    const variables: Record<string, unknown> =
      resource === 'matchmakingQueue' ? {} : { page, limit: perPage };

    if (supportsSearch) {
      if (filters) {
        for (const filter of filters) {
          if (
            'field' in filter &&
            (filter.field === 'q' || filter.field === 'search' || filter.operator === 'contains') &&
            filter.value !== undefined &&
            filter.value !== null &&
            filter.value !== ''
          ) {
            variables.search = String(filter.value);
            break;
          }
        }
      }

      const sorter = sorters?.[0];
      if (sorter) {
        variables.sortBy = sorter.field;
        variables.sortOrder = sorter.order;
      }
    }

    try {
      const result = await client.query(query, variables).toPromise();

      if (result.error) {
        console.error('[dataProvider] GraphQL error:', result.error);
        throw result.error;
      }

      const { items, total } = extractItems(result.data || {});

      return { data: items, total };
    } catch (error) {
      console.error(`[dataProvider] Error fetching ${resource}:`, error);
      throw error;
    }
  },

  getOne: async ({ resource, id, meta }) => {
    let query;
    let dataKey: string;

    switch (resource) {
      case 'heroes':
        query = GET_HERO;
        dataKey = 'adminHero';
        break;
      case 'cards':
        query = GET_CARD;
        dataKey = 'adminCard';
        break;
      case 'boards':
        query = GET_BOARD;
        dataKey = 'adminBoard';
        break;
      case 'users':
        query = GET_USER;
        dataKey = 'adminUser';
        break;
      case 'games':
        query = GET_GAME;
        dataKey = 'adminGame';
        break;
      default:
        throw new Error(`No getOne query found for resource: ${resource}`);
    }

    // Extract ID from various possible locations
    let actualId = id;

    // Try to get ID from different sources
    if (!actualId && meta?.id) {
      actualId = meta.id as string;
    }
    if (!actualId && (meta as any)?.identifier) {
      actualId = (meta as any).identifier as string;
    }

    if (!actualId) {
      console.error(`[dataProvider] No ID provided for ${resource}`, { id, meta });
      throw new Error(`No ID provided for resource: ${resource}`);
    }

    try {
      const result = await client.query(query, { id: actualId }).toPromise();

      if (result.error) {
        throw result.error;
      }

      return { data: result.data?.[dataKey] };
    } catch (error) {
      console.error(`[dataProvider] Error fetching ${resource} with id ${actualId}:`, error);
      throw error;
    }
  },

  create: async ({ resource, variables }) => {
    let query;
    let dataKey: string;

    switch (resource) {
      case 'heroes':
        query = CREATE_HERO;
        dataKey = 'createHero';
        break;
      case 'cards':
        query = CREATE_CARD;
        dataKey = 'createCard';
        break;
      case 'boards':
        query = CREATE_BOARD;
        dataKey = 'createBoard';
        break;
      default:
        throw new Error(`No create mutation found for resource: ${resource}`);
    }

    try {
      const result = await client.mutation(query, { input: variables }).toPromise();

      if (result.error) {
        throw result.error;
      }

      return { data: result.data?.[dataKey] };
    } catch (error) {
      console.error(`[dataProvider] Error creating ${resource}:`, error);
      throw error;
    }
  },

  update: async ({ resource, id, variables, meta }) => {
    let query;
    let dataKey: string;

    switch (resource) {
      case 'heroes':
        query = UPDATE_HERO;
        dataKey = 'updateHero';
        break;
      case 'cards':
        query = UPDATE_CARD;
        dataKey = 'updateCard';
        break;
      case 'boards':
        query = UPDATE_BOARD;
        dataKey = 'updateBoard';
        break;
      case 'users':
        query = UPDATE_USER;
        dataKey = 'updateUser';
        break;
      default:
        throw new Error(`No update mutation found for resource: ${resource}`);
    }

    // Extract ID from various possible locations
    let actualId = id;
    if (!actualId && meta?.id) actualId = meta.id as string;

    if (!actualId) {
      console.error(`[dataProvider] No ID provided for update ${resource}`, { id, meta });
      throw new Error(`No ID provided for update resource: ${resource}`);
    }

    try {
      const result = await client.mutation(query, { id: actualId, input: variables }).toPromise();

      if (result.error) {
        throw result.error;
      }

      return { data: result.data?.[dataKey] };
    } catch (error) {
      console.error(`[dataProvider] Error updating ${resource}:`, error);
      throw error;
    }
  },

  deleteOne: async ({ resource, id, meta }) => {
    let query;

    switch (resource) {
      case 'heroes':
        query = DELETE_HERO;
        break;
      case 'cards':
        query = DELETE_CARD;
        break;
      case 'boards':
        query = DELETE_BOARD;
        break;
      default:
        throw new Error(`No delete mutation found for resource: ${resource}`);
    }

    // Extract ID from various possible locations
    let actualId = id;
    if (!actualId && meta?.id) actualId = meta.id as string;

    if (!actualId) {
      console.error(`[dataProvider] No ID provided for delete ${resource}`, { id, meta });
      throw new Error(`No ID provided for delete resource: ${resource}`);
    }

    try {
      const result = await client.mutation(query, { id: actualId }).toPromise();

      if (result.error) {
        throw result.error;
      }

      return { data: { id: actualId } as any };
    } catch (error) {
      console.error(`[dataProvider] Error deleting ${resource}:`, error);
      throw error;
    }
  },

  getApiUrl: () => `${BACKEND_URL}/graphql`,
};

export { gql };
