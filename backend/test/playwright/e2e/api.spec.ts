/**
 * Real API E2E Tests
 *
 * Тесты с реальными API вызовами и данными.
 * Проверяют что backend работает корректно.
 */

import { test, expect } from '@playwright/test';

const API_URL = 'http://localhost:3000/graphql';

test.describe('Real API Tests', { tag: ['@api', '@real-data'] }, () => {
  test('register creates new user', async () => {
    const uniqueId = Date.now();
    const response = await fetch(API_URL, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        query: `mutation {
          register(input: {
            email: "test_${uniqueId}@example.com",
            username: "test_${uniqueId}",
            password: "Test1234"
          }) {
            accessToken
            user { id email username }
          }
        }`
      }),
    });

    const result = await response.json();
    expect(result.data?.register).toBeDefined();
    expect(result.data?.register?.user?.id).toBeDefined();
    expect(result.data?.register?.accessToken).toBeDefined();
  });

  test('login returns valid token', async () => {
    const response = await fetch(API_URL, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        query: `mutation {
          login(input: {
            email: "e2e_player1@test.com",
            password: "Test1234"
          }) {
            accessToken
            user { id email username }
          }
        }`
      }),
    });

    const result = await response.json();
    expect(result.data?.login).toBeDefined();
    expect(result.data?.login?.accessToken).toBeDefined();
    expect(result.data?.login?.user?.email).toBe('e2e_player1@test.com');
  });

  test('get heroes returns real data', async () => {
    const response = await fetch(API_URL, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        query: `query {
          heroes {
            id
            name
            health
            set
          }
        }`
      }),
    });

    const result = await response.json();
    expect(result.data?.heroes).toBeDefined();
    expect(Array.isArray(result.data?.heroes)).toBe(true);
    expect(result.data?.heroes.length).toBeGreaterThan(0);
  });

  test('get cards returns real data', async () => {
    // Сначала получаем ID героя
    const heroesResponse = await fetch(API_URL, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        query: `query { heroes { id } }`
      }),
    });

    const heroesResult = await heroesResponse.json();
    const heroId = heroesResult.data?.heroes?.[0]?.id;

    expect(heroId).toBeDefined();

    // Теперь получаем карты героя
    const cardsResponse = await fetch(API_URL, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        query: `query {
          cards(heroId: "${heroId}") {
            id
            cardId
            name
            cardType
            attackValue
            defenseValue
          }
        }`
      }),
    });

    const cardsResult = await cardsResponse.json();
    expect(cardsResult.data?.cards).toBeDefined();
    expect(Array.isArray(cardsResult.data?.cards)).toBe(true);
  });

  test('authenticated request works', async () => {
    // Сначала логинимся
    const loginResponse = await fetch(API_URL, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        query: `mutation {
          login(input: {
            email: "e2e_player1@test.com",
            password: "Test1234"
          }) {
            accessToken
          }
        }`
      }),
    });

    const loginResult = await loginResponse.json();
    const token = loginResult.data?.login?.accessToken;

    expect(token).toBeDefined();

    // Делаем аутентифицированный запрос
    const meResponse = await fetch(API_URL, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${token}`
      },
      body: JSON.stringify({
        query: `query {
          me {
            id
            email
            username
            stats {
              gamesPlayed
              wins
              losses
            }
          }
        }`
      }),
    });

    const meResult = await meResponse.json();
    expect(meResult.data?.me).toBeDefined();
    expect(meResult.data?.me?.email).toBe('e2e_player1@test.com');
    expect(meResult.data?.me?.username).toBe('e2e_player1');
  });
});

test.describe('Real Game API', { tag: ['@game', '@real-data'] }, () => {
  let authToken: string;

  test.beforeAll(async () => {
    // Логинимся перед тестами
    const response = await fetch(API_URL, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        query: `mutation {
          login(input: {
            email: "e2e_player1@test.com",
            password: "Test1234"
          }) {
            accessToken
          }
        }`
      }),
    });

    const result = await response.json();
    authToken = result.data?.login?.accessToken;
  });

  test('can create game', async () => {
    const response = await fetch(API_URL, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${authToken}`
      },
      body: JSON.stringify({
        query: `mutation {
          createGame(input: {
            name: "E2E Test Game"
            gameMode: "standard"
            maxPlayers: 2
          }) {
            id
            status
          }
        }`
      }),
    });

    const result = await response.json();
    expect(result.data?.createGame).toBeDefined();
    expect(result.data?.createGame?.id).toBeDefined();
    expect(result.data?.createGame?.status).toBeDefined();
  });

  test('get games list', async () => {
    const response = await fetch(API_URL, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${authToken}`
      },
      body: JSON.stringify({
        query: `query {
          games {
            id
            name
            status
            players {
              userId
              heroId
            }
          }
        }`
      }),
    });

    const result = await response.json();
    expect(result.data?.games).toBeDefined();
    expect(Array.isArray(result.data?.games)).toBe(true);
  });
});

test.describe('API Performance', { tag: ['@performance', '@api'] }, () => {
  test('login response is fast', async () => {
    const startTime = Date.now();

    const response = await fetch(API_URL, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        query: `mutation {
          login(input: {
            email: "e2e_player1@test.com",
            password: "Test1234"
          }) {
            accessToken
          }
        }`
      }),
    });

    await response.json();
    const responseTime = Date.now() - startTime;

    // API должен отвечать менее чем за 2 секунды
    expect(responseTime).toBeLessThan(2000);
  });

  test('heroes query is fast', async () => {
    const startTime = Date.now();

    const response = await fetch(API_URL, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        query: `query { heroes { id name health } }`
      }),
    });

    await response.json();
    const responseTime = Date.now() - startTime;

    // API должен отвечать менее чем за 1 секунду
    expect(responseTime).toBeLessThan(1000);
  });
});
