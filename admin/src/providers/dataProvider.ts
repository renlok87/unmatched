import { DataProvider } from '@refinedev/core';
import { createClient, fetchExchange, gql } from 'urql';

const BACKEND_URL = import.meta.env.VITE_BACKEND_URL || 'http://localhost:3000';

const getToken = () => localStorage.getItem('accessToken');

export const client = createClient({
  url: `${BACKEND_URL}/graphql`,
  exchanges: [fetchExchange],
  fetchOptions: () => ({
    headers: {
      Authorization: `Bearer ${getToken()}`,
    },
  }),
});

// GraphQL queries для каждого ресурса
const GET_HEROES_LIST = gql`
  query GetHeroesList($page: Int!, $limit: Int!) {
    heroList(page: $page, limit: $limit) {
      items {
        id
        name
        nameEn
        nameRu
        set
        health
        fighterType
        ability
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
      ability
      deckCards
      properties
      imageUrl
      avatarUrl
      createdAt
      updatedAt
    }
  }
`;

const GET_CARDS_LIST = gql`
  query GetCardsList($page: Int!, $limit: Int!) {
    cardList(page: $page, limit: $limit) {
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
        count
        heroId
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
      effects
      text
      textEn
      textRu
      heroId
      count
      createdAt
      updatedAt
    }
  }
`;

const GET_BOARDS_LIST = gql`
  query GetBoardsList($page: Int!, $limit: Int!) {
    boardList(page: $page, limit: $limit) {
      items {
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
  query GetUsersList($page: Int!, $limit: Int!) {
    userList(page: $page, limit: $limit) {
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
    user(id: $id) {
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
  }
`;

const GET_GAME = gql`
  query GetGame($id: String!) {
    game(id: $id) {
      id
      status
      createdAt
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
  query GetGamesList($page: Int!, $limit: Int!) {
    gameList(page: $page, limit: $limit) {
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
      ability
      imageUrl
      avatarUrl
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
      ability
      imageUrl
      avatarUrl
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
      count
      heroId
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
      count
      heroId
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

export const dataProvider: DataProvider = {
  getList: async ({ resource, pagination }) => {
    console.log(`[dataProvider] getList called for resource: ${resource}`, pagination);

    let query;
    let extractItems: (data: any) => { items: any[]; total: number };

    switch (resource) {
      case 'heroes':
        query = GET_HEROES_LIST;
        extractItems = (data) => ({ items: data.heroList.items, total: data.heroList.total });
        break;
      case 'cards':
        query = GET_CARDS_LIST;
        extractItems = (data) => ({ items: data.cardList.items, total: data.cardList.total });
        break;
      case 'boards':
        query = GET_BOARDS_LIST;
        extractItems = (data) => ({ items: data.boardList.items, total: data.boardList.total });
        break;
      case 'users':
        query = GET_USERS_LIST;
        extractItems = (data) => ({ items: data.userList.users, total: data.userList.total });
        break;
      case 'games':
        query = GET_GAMES_LIST;
        extractItems = (data) => ({ items: data.gameList.items, total: data.gameList.total });
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
        console.error(`[dataProvider] Unknown resource: ${resource}`);
        return { data: [], total: 0 };
    }

    const page = 1;
    const perPage = pagination?.pageSize || 20;

    console.log(`[dataProvider] Fetching ${resource} with page=${page}, limit=${perPage}`);

    try {
      const result = await client.query(query, { page, limit: perPage }).toPromise();

      if (result.error) {
        console.error('[dataProvider] GraphQL error:', result.error);
        throw result.error;
      }

      console.log(`[dataProvider] Raw response for ${resource}:`, result.data);

      const { items, total } = extractItems(result.data || {});

      console.log(`[dataProvider] Returning ${items.length} items, total: ${total}`);

      return { data: items, total };
    } catch (error) {
      console.error(`[dataProvider] Error fetching ${resource}:`, error);
      throw error;
    }
  },

  getOne: async ({ resource, id, meta, resourceParams }) => {
    console.log(`[dataProvider] getOne called for resource: ${resource}, id: ${id}`, { meta, resourceParams });

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
        dataKey = 'user';
        break;
      case 'games':
        query = GET_GAME;
        dataKey = 'game';
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
    if (!actualId && resourceParams?.id) {
      actualId = resourceParams.id as string;
    }
    if (!actualId && (resourceParams as any)?.identifier) {
      actualId = (resourceParams as any).identifier as string;
    }

    if (!actualId) {
      console.error(`[dataProvider] No ID provided for ${resource}`, { id, meta, resourceParams });
      throw new Error(`No ID provided for resource: ${resource}`);
    }

    console.log(`[dataProvider] Using actualId: ${actualId} for ${resource}`);

    try {
      const result = await client.query(query, { id: actualId }).toPromise();

      if (result.error) {
        throw result.error;
      }

      console.log(`[dataProvider] Successfully fetched ${resource}:`, result.data?.[dataKey]);
      return { data: result.data?.[dataKey] };
    } catch (error) {
      console.error(`[dataProvider] Error fetching ${resource} with id ${actualId}:`, error);
      throw error;
    }
  },

  create: async ({ resource, variables }) => {
    console.log(`[dataProvider] create called for resource: ${resource}`);

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

  update: async ({ resource, id, variables, meta, resourceParams }) => {
    console.log(`[dataProvider] update called for resource: ${resource}, id: ${id}`, { meta, resourceParams });

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
      default:
        throw new Error(`No update mutation found for resource: ${resource}`);
    }

    // Extract ID from various possible locations
    let actualId = id;
    if (!actualId && meta?.id) actualId = meta.id as string;
    if (!actualId && resourceParams?.id) actualId = resourceParams.id as string;

    if (!actualId) {
      console.error(`[dataProvider] No ID provided for update ${resource}`, { id, meta, resourceParams });
      throw new Error(`No ID provided for update resource: ${resource}`);
    }

    console.log(`[dataProvider] Using actualId: ${actualId} for update ${resource}`);

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

  deleteOne: async ({ resource, id, meta, resourceParams }) => {
    console.log(`[dataProvider] deleteOne called for resource: ${resource}, id: ${id}`, { meta, resourceParams });

    let query;
    let dataKey: string;

    switch (resource) {
      case 'heroes':
        query = DELETE_HERO;
        dataKey = 'deleteHero';
        break;
      case 'cards':
        query = DELETE_CARD;
        dataKey = 'deleteCard';
        break;
      case 'boards':
        query = DELETE_BOARD;
        dataKey = 'deleteBoard';
        break;
      default:
        throw new Error(`No delete mutation found for resource: ${resource}`);
    }

    // Extract ID from various possible locations
    let actualId = id;
    if (!actualId && meta?.id) actualId = meta.id as string;
    if (!actualId && resourceParams?.id) actualId = resourceParams.id as string;

    if (!actualId) {
      console.error(`[dataProvider] No ID provided for delete ${resource}`, { id, meta, resourceParams });
      throw new Error(`No ID provided for delete resource: ${resource}`);
    }

    console.log(`[dataProvider] Using actualId: ${actualId} for delete ${resource}`);

    try {
      const result = await client.mutation(query, { id: actualId }).toPromise();

      if (result.error) {
        throw result.error;
      }

      return { data: result.data?.[dataKey] };
    } catch (error) {
      console.error(`[dataProvider] Error deleting ${resource}:`, error);
      throw error;
    }
  },

  getApiUrl: () => `${BACKEND_URL}/graphql`,
};

export { gql };
