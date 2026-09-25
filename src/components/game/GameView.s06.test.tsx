/**
 * S06 (GD-021..022) UI-контракт новых pending-типов:
 * - CHOOSE_SPACE (Restless Spirits): клик по клетке → resolvePendingEffect
 *   с координатами (без выбора бойца); подсказки стадий 1/2;
 * - DECK_TOP_PICK (Prophecy): revealed-карты рендерятся кнопками баннера
 *   (PICK — «взять N», ORDER — порядок возврата), клики по доске мимо
 *   баннера эффект не резолвят.
 */
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { renderToStaticMarkup } from 'react-dom/server';
import { adaptToLocal, type WireGameState, type WirePendingEffect } from '@/lib/gameStateAdapter';

const view = vi.hoisted(() => ({ state: {} as Record<string, unknown> }));
const phaser = vi.hoisted(() => ({ onEvent: null as ((event: unknown) => void) | null }));
vi.mock('@/store/remoteGameStore', () => ({ useRemoteGameStore: () => view.state }));
vi.mock('@/hooks/useGameSync', () => ({ useGameSync: () => ({ isConnecting: false, hasError: false, connectionStatus: 'connected' }) }));
vi.mock('react-router-dom', () => ({ useParams: () => ({ gameId: 'g' }), useNavigate: () => vi.fn() }));
// Phaser-заглушка отдаёт нам обработчик событий сцены — дергаем вручную
vi.mock('@/phaser/PhaserGame', () => ({
  PhaserGame: (props: { onGameEvent: (event: unknown) => void }) => {
    phaser.onEvent = props.onGameEvent;
    return null;
  },
}));
import { GameView } from './GameView';

const resolvePendingEffect = vi.fn(async () => undefined);

function setState(pending: WirePendingEffect) {
  const wire: WireGameState = {
    gameId: 'g', sequenceNumber: 12, phase: 'ACTION_MANEUVER', turnCount: 2, currentTurnPlayerId: 'a',
    players: [{ userId: 'a', heroId: 'a', health: 10, maxHealth: 10, fighterIds: [], isAlive: true }],
    fighters: [], boardState: { width: 3, height: 3 },
    handZones: { a: { maxSize: 7, cards: [] } },
    metadata: { actionsRemaining: 2, pendingEffects: [pending] },
  };
  view.state = {
    wireState: wire,
    adaptedState: adaptToLocal(wire, { usernames: {}, heroAssets: {}, board: null, stanceOptions: {} }, 'a'),
    localUserId: 'a', selectedFighterId: null, selectedCardId: null,
    isMyTurn: () => true, actionsRemaining: () => 2,
    amIDefender: () => false,
    myPendingEffects: () => (pending.playerId === 'a' ? [pending] : []),
    myStance: () => null, myStanceOptions: () => [],
    resolvePendingEffect,
    declinePendingEffect: vi.fn(async () => undefined),
  };
}

const spaceStage1: WirePendingEffect = {
  id: 'pe-space', type: 'CHOOSE_SPACE', playerId: 'a', stage: 1,
  zoneFighterName: 'Merlin', damage: 2, drawIfDefeated: true,
  text: "Choose any space in Merlin's zone",
};

describe('S06 GameView pending controls', () => {
  beforeEach(() => resolvePendingEffect.mockClear());

  it('CHOOSE_SPACE stage 1: подсказка про зону named-бойца, клик по клетке резолвит координатами', () => {
    setState(spaceStage1);
    const html = renderToStaticMarkup(<GameView />);
    expect(html).toContain('Кликните любую клетку в зоне «Merlin»');
    phaser.onEvent!({ type: 'SPACE_CLICKED', position: { x: 2, y: 1 } });
    expect(resolvePendingEffect).toHaveBeenCalledWith('pe-space', undefined, 2, 1);
  });

  it('CHOOSE_SPACE stage 2: подсказка про смежность с anchor + добор за поверженных', () => {
    setState({ ...spaceStage1, id: 'pe-space2', stage: 2, anchor: { x: 3, y: 1 } });
    const html = renderToStaticMarkup(<GameView />);
    expect(html).toContain('Кликните клетку, смежную с (3, 1)');
    expect(html).toContain('добор за поверженных');
    phaser.onEvent!({ type: 'SPACE_CLICKED', position: { x: 4, y: 1 } });
    expect(resolvePendingEffect).toHaveBeenCalledWith('pe-space2', undefined, 4, 1);
  });

  it('CHOOSE_SPACE: клик по бойцу НЕ резолвит (нужна клетка)', () => {
    setState(spaceStage1);
    renderToStaticMarkup(<GameView />);
    phaser.onEvent!({ type: 'FIGHTER_CLICKED', fighterId: 'f1' });
    expect(resolvePendingEffect).not.toHaveBeenCalled();
  });

  it('DECK_TOP_PICK (PICK): revealed-карты кнопками, подтверждение до выбора скрыто', () => {
    setState({
      id: 'pe-prophecy', type: 'DECK_TOP_PICK', playerId: 'a', mode: 'PICK', value: 2,
      revealedCards: [
        { id: 'p1', cardId: 'c1', cardType: 'SCHEME', name: 'Prophecy A' },
        { id: 'p2', cardId: 'c2', cardType: 'SCHEME', name: 'Prophecy B' },
        { id: 'p3', cardId: 'c3', cardType: 'SCHEME', name: 'Prophecy C' },
        { id: 'p4', cardId: 'c4', cardType: 'SCHEME', name: 'Prophecy D' },
      ],
    });
    const html = renderToStaticMarkup(<GameView />);
    expect(html).toContain('Возьмите 2 карты в руку');
    expect(html).toContain('Prophecy A');
    expect(html).toContain('Prophecy D');
    // выбор ещё не сделан — кнопки подтверждения нет
    expect(html).not.toContain('Взять 2');
    // клики по сцене/картам руки мимо баннера ничего не резолвят
    phaser.onEvent!({ type: 'CARD_CLICKED', cardId: 'p1' });
    phaser.onEvent!({ type: 'SPACE_CLICKED', position: { x: 0, y: 0 } });
    expect(resolvePendingEffect).not.toHaveBeenCalled();
  });

  it('DECK_TOP_PICK (ORDER): подпись порядка возврата, карты видимы', () => {
    setState({
      id: 'pe-order', type: 'DECK_TOP_PICK', playerId: 'a', mode: 'ORDER', value: 2,
      revealedCards: [
        { id: 'p4', cardId: 'c4', cardType: 'SCHEME', name: 'Prophecy D' },
        { id: 'p2', cardId: 'c2', cardType: 'SCHEME', name: 'Prophecy B' },
      ],
    });
    const html = renderToStaticMarkup(<GameView />);
    expect(html).toContain('Порядок возврата наверх колоды (клик по порядку)');
    expect(html).toContain('Prophecy D');
    expect(html).not.toContain('Вернуть в колоду');
  });

  it('чужой pending (Prophecy соперника) не рендерит мой баннер выбора', () => {
    setState({
      id: 'pe-foreign', type: 'DECK_TOP_PICK', playerId: 'b', mode: 'PICK', value: 2,
      revealedCount: 4,
    });
    const html = renderToStaticMarkup(<GameView />);
    expect(html).not.toContain('Возьмите 2 карты в руку');
    expect(html).not.toContain('Кликните любую клетку');
  });
});
