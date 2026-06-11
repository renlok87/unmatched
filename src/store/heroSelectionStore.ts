import { create } from 'zustand';
import { apolloClient } from '@/lib/apolloClient';
import { gql } from '@apollo/client';
import type { Hero, HeroFilters } from '@/types/hero';

interface HeroSelectionState {
  // State
  heroes: Hero[];
  selectedHero: Hero | null;
  takenHeroIds: string[];
  loading: boolean;
  error: string | null;
  filters: HeroFilters;

  // Internal
  _isMounted: boolean;
  _abortController: AbortController | null;

  // Actions
  mount: () => void;
  unmount: () => void;
  loadHeroes: () => Promise<void>;
  setFilters: (filters: Partial<HeroFilters>) => void;
  selectHero: (hero: Hero) => void;
  selectHeroOnServer: (gameId: string, heroId: string) => Promise<void>;
  setTakenHeroIds: (heroIds: string[]) => void;
  clearError: () => void;
}

/**
 * Hero Selection Store
 *
 * Управляет выбором героя перед игрой.
 * Включает загрузку героев, фильтрацию, выбор.
 */
export const useHeroSelectionStore = create<HeroSelectionState>((set, get) => ({
  // Initial state
  heroes: [],
  selectedHero: null,
  takenHeroIds: [],
  loading: false,
  error: null,
  filters: {
    set: null,
    search: null,
    fighterType: null,
  },

  // Internal
  _isMounted: false,
  _abortController: null,

  mount: () => {
    set({ _isMounted: true });
  },

  unmount: () => {
    const controller = get()._abortController;
    if (controller) {
      controller.abort();
    }
    set({ _isMounted: false, _abortController: null });
  },

  loadHeroes: async () => {
    const state = get();

    if (!state._isMounted) return;

    // Cancel previous request
    if (state._abortController) {
      state._abortController.abort();
    }

    const controller = new AbortController();
    set({ _abortController: controller, loading: true, error: null });

    try {
      const queryToUse = state.filters.set
        ? gql`
            query HeroesBySet($set: String!) {
              heroesBySet(set: $set) {
                id
                name
                health
                movement
                set
                fighterType
                sidekickCount
                sidekickHealth
                urls {
                  avatar
                  mini
                  cardCover
                }
              }
            }
          `
        : gql`
            query AllHeroes {
              heroes {
                id
                name
                health
                movement
                set
                fighterType
                sidekickCount
                sidekickHealth
                urls {
                  avatar
                  mini
                  cardCover
                }
              }
            }
          `;
      const variables = state.filters.set
        ? { set: state.filters.set }
        : {};

      const { data, errors } = await apolloClient.query({
        query: queryToUse,
        variables,
        fetchPolicy: 'network-only',
        context: {
          fetchOptions: {
            signal: controller.signal,
          },
        },
      });

      if (!get()._isMounted) return;

      if (errors?.length) {
        throw new Error(errors[0].message);
      }

      const heroesData = (data as any).heroesBySet || (data as any).heroes;

      if (!heroesData) {
        throw new Error('Failed to load heroes');
      }

      // Transform data to Hero interface
      const transformedHeroes: Hero[] = heroesData.map((h: any) => ({
        id: h.id,
        name: h.name,
        health: h.health,
        movement: h.movement,
        set: h.set,
        thumbnailUrl: h.urls?.mini || '',
        imageUrl: h.urls?.avatar || '',
        fighterTypes: [h.fighterType],
        abilities: [],
      }));

      // Apply search filter client-side
      let filteredHeroes = transformedHeroes;
      if (state.filters.search) {
        const searchLower = state.filters.search.toLowerCase();
        filteredHeroes = filteredHeroes.filter((h) =>
          h.name.toLowerCase().includes(searchLower),
        );
      }

      set({
        heroes: filteredHeroes,
        loading: false,
        _abortController: null,
      });
    } catch (error) {
      if (!get()._isMounted) return;

      if (error instanceof Error && error.name === 'AbortError') {
        return;
      }

      const message = error instanceof Error ? error.message : 'Failed to load heroes';
      set({
        error: message,
        loading: false,
        _abortController: null,
      });
    }
  },

  setFilters: (filters: Partial<HeroFilters>) => {
    set((state) => ({
      filters: { ...state.filters, ...filters },
    }));

    get().loadHeroes();
  },

  selectHero: (hero: Hero) => {
    if (!get()._isMounted) return;

    set({
      selectedHero: hero,
    });
  },

  selectHeroOnServer: async (gameId: string, heroId: string) => {
    const state = get();

    if (!state._isMounted) return;

    if (state._abortController) {
      state._abortController.abort();
    }

    const controller = new AbortController();
    const idempotencyKey = `${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;

    set({ _abortController: controller, loading: true, error: null });

    try {
      const { data, errors } = await apolloClient.mutate({
        mutation: gql`
          mutation SelectHero($gameId: String!, $heroId: String!) {
            selectHero(gameId: $gameId, heroId: $heroId) {
              id
              players {
                userId
                heroId
              }
            }
          }
        `,
        variables: {
          gameId,
          heroId,
        },
        context: {
          headers: {
            'X-Idempotency-Key': idempotencyKey,
          },
          fetchOptions: {
            signal: controller.signal,
          },
        },
      });

      if (!get()._isMounted) return;

      if (errors?.length) {
        throw new Error(errors[0].message);
      }

      const selectHeroData = (data as any).selectHero;

      if (!selectHeroData) {
        throw new Error('Failed to select hero');
      }

      const takenIds = selectHeroData.players
        .filter((p: any) => p.heroId && p.heroId !== heroId)
        .map((p: any) => p.heroId);

      set({
        takenHeroIds: takenIds,
        loading: false,
        _abortController: null,
      });
    } catch (error) {
      if (!get()._isMounted) return;

      if (error instanceof Error && error.name === 'AbortError') {
        return;
      }

      const message = error instanceof Error ? error.message : 'Failed to select hero';
      set({
        error: message,
        loading: false,
        _abortController: null,
      });
      throw error;
    }
  },

  setTakenHeroIds: (heroIds: string[]) => {
    if (!get()._isMounted) return;
    set({ takenHeroIds: heroIds });
  },

  clearError: () => {
    set({ error: null });
  },
}));