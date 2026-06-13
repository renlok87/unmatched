/**
 * GameView — основная игровая страница (/game/:gameId) на РЕАЛЬНОМ API.
 *
 * Истина — сервер: remoteGameStore грузит wire-состояние, подписка
 * gameStateUpdated доставляет полные снапшоты, действия — GraphQL-мутации.
 * Никакой локальной игровой логики; UI лишь подсказывает доступность
 * (фаза/чей ход/остаток действий), сервер валидирует всё сам.
 *
 * Управление кликами:
 * - свой боец → выбрать (для движения/атаки)
 * - клетка при выбранном бойце → moveFighter
 * - своя карта: SCHEME в свой ход → playScheme; ATTACK/VERSATILE → выбрать
 *   (затем клик по врагу = attack); DEFENSE/VERSATILE в COMBAT у защитника
 *   → playDefense
 * - кнопки: End Turn / Pass / Resolve (в COMBAT_RESOLVE у атакующего)
 */

import { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useGameSync } from '@/hooks/useGameSync';
import { useRemoteGameStore } from '@/store/remoteGameStore';
import { PhaserGame } from '@/phaser/PhaserGame';
import type { PhaserGameEvent } from '@/phaser/types';
import { GameErrorBoundary } from './GameErrorBoundary';
import { Modal } from '@/design-system/components/Modal';
import { Button } from '@/design-system/components/Button';
import './GameView.css';

export const GameView = () => {
  const { gameId } = useParams<{ gameId: string }>();
  const navigate = useNavigate();
  const { isConnecting, hasError, error, connectionStatus } = useGameSync(gameId || '');

  const {
    wireState,
    adaptedState,
    localUserId,
    actionError,
    selectedFighterId,
    selectedCardId,
    selectFighter,
    selectCard,
    isMyTurn,
    actionsRemaining,
    amIDefender,
    myPendingEffects,
    moveFighter,
    attack,
    playDefense,
    playScheme,
    resolveCombat,
    resolvePendingEffect,
    endTurn,
    pass,
    leaveGame,
    clearErrors,
  } = useRemoteGameStore();

  const [showLeaveModal, setShowLeaveModal] = useState(false);
  const [busy, setBusy] = useState(false);
  // C2: боец, выбранный для резолва отложенного эффекта (MOVE/PLACE)
  const [pendingFighterId, setPendingFighterId] = useState<string | null>(null);

  // активный отложенный эффект ЛОКАЛЬНОГО игрока (первый в очереди)
  const pendingEffects = myPendingEffects();
  const activePending = pendingEffects[0] ?? null;

  // Автоскрытие ошибки действия через 5 сек
  useEffect(() => {
    if (!actionError) return;
    const t = setTimeout(clearErrors, 5000);
    return () => clearTimeout(t);
  }, [actionError, clearErrors]);

  const run = async (fn: () => Promise<void>) => {
    if (busy) return;
    setBusy(true);
    try {
      await fn();
    } catch {
      // actionError уже выставлен стором
    } finally {
      setBusy(false);
    }
  };

  // Боец подходит под отложенный эффект (грубая UI-подсказка; финал — на бэке)
  const fighterFitsPending = (fighterOwnerId: string, fighterName: string): boolean => {
    if (!activePending) return false;
    const ownerOk = activePending.targetsOpponent
      ? fighterOwnerId !== localUserId
      : fighterOwnerId === localUserId;
    if (!ownerOk) return false;
    if (activePending.fighterName) {
      const base = fighterName.replace(/\s+\d+$/, '').toLowerCase().replace(/ies$/, 'y');
      const want = activePending.fighterName.toLowerCase().replace(/ies$/, 'y');
      return base.includes(want) || fighterName.toLowerCase().includes(activePending.fighterName.toLowerCase());
    }
    return true;
  };

  const handlePhaserEvent = (event: PhaserGameEvent) => {
    if (!wireState || !localUserId) return;
    const phase = wireState.phase;

    // C2: режим резолва отложенного эффекта имеет приоритет — клик по
    // подходящему бойцу выбирает его, клик по клетке завершает эффект
    if (activePending) {
      if (event.type === 'FIGHTER_CLICKED') {
        const fighter = wireState.fighters.find((f) => f.id === event.fighterId);
        if (fighter && fighterFitsPending(fighter.ownerId, fighter.name)) {
          setPendingFighterId(pendingFighterId === fighter.id ? null : fighter.id);
        }
        return;
      }
      if (event.type === 'SPACE_CLICKED' && pendingFighterId) {
        const fid = pendingFighterId;
        void run(async () => {
          await resolvePendingEffect(activePending.id, fid, event.position.x, event.position.y);
          setPendingFighterId(null);
        });
        return;
      }
      // CARD_CLICKED и прочее в режиме pending игнорируем
      return;
    }

    switch (event.type) {
      case 'FIGHTER_CLICKED': {
        const fighter = wireState.fighters.find((f) => f.id === event.fighterId);
        if (!fighter) return;

        if (fighter.ownerId === localUserId) {
          // свой боец: выбрать/снять выбор
          selectFighter(selectedFighterId === fighter.id ? null : fighter.id);
          return;
        }

        // чужой боец: при выбранной атакующей карте и своём бойце — атака
        const card = selectedCardId
          ? wireState.handZones[localUserId]?.cards.find((c) => c.id === selectedCardId)
          : undefined;
        const myAttacker =
          selectedFighterId ??
          wireState.fighters.find((f) => f.ownerId === localUserId && f.type === 'HERO')?.id;
        if (
          card &&
          myAttacker &&
          isMyTurn() &&
          actionsRemaining() > 0 &&
          (card.cardType === 'ATTACK' || card.cardType === 'VERSATILE')
        ) {
          void run(() => attack(myAttacker, fighter.id, card.id));
        }
        return;
      }

      case 'SPACE_CLICKED': {
        if (!selectedFighterId || !isMyTurn() || actionsRemaining() <= 0) return;
        if (phase !== 'ACTION_MANEUVER' && phase !== 'ACTION_ATTACK') return;
        void run(() => moveFighter(selectedFighterId, event.position.x, event.position.y));
        return;
      }

      case 'CARD_CLICKED': {
        const card = wireState.handZones[localUserId]?.cards.find(
          (c) => c.id === event.cardId,
        );
        if (!card) return;

        // защита: в COMBAT защитник играет DEFENSE/VERSATILE сразу
        if (phase === 'COMBAT' && amIDefender()) {
          if (card.cardType === 'DEFENSE' || card.cardType === 'VERSATILE') {
            void run(() => playDefense(card.id));
          }
          return;
        }

        if (!isMyTurn() || actionsRemaining() <= 0) return;

        if (card.cardType === 'SCHEME') {
          void run(() => playScheme(card.id));
          return;
        }

        // ATTACK/VERSATILE: выделить карту, цель выбирается кликом по врагу
        selectCard(selectedCardId === card.id ? null : card.id);
        return;
      }

      default:
        return;
    }
  };

  const confirmLeave = async () => {
    setShowLeaveModal(false);
    try {
      await leaveGame();
    } finally {
      navigate('/lobby');
    }
  };

  if (isConnecting || !adaptedState) {
    return (
      <div className="game-view game-view--loading">
        <div className="game-view__loading-spinner" />
        <p>Подключение к игре...</p>
      </div>
    );
  }

  if (hasError) {
    return (
      <div className="game-view game-view--error">
        <div className="game-view__error-content">
          <div className="game-view__error-icon">⚠️</div>
          <h2>Ошибка подключения</h2>
          <p>{error}</p>
          <Button variant="primary" onClick={() => window.location.reload()}>
            Перезагрузить страницу
          </Button>
          <Button variant="ghost" onClick={() => navigate('/lobby')}>
            Вернуться в лобби
          </Button>
        </div>
      </div>
    );
  }

  const phase = wireState?.phase ?? '';
  const myTurn = isMyTurn();
  const actions = actionsRemaining();
  const combat = wireState?.metadata.combatInfo;
  const isAttacker = Boolean(
    combat && wireState?.fighters.find((f) => f.id === combat.attackerId)?.ownerId === localUserId,
  );
  const gameOver = phase === 'GAME_OVER';
  const winnerId = wireState?.metadata.winnerId ?? null;
  const opponent = wireState?.players.find((p) => p.userId !== localUserId);
  const turnOwnerName =
    adaptedState.players.find((p) => p.id === wireState?.currentTurnPlayerId)?.name ?? '';

  return (
    <GameErrorBoundary>
      <div className="game-view">
        {/* Статус-бар */}
        <div
          className="game-view__statusbar"
          style={{
            display: 'flex',
            gap: 16,
            alignItems: 'center',
            padding: '8px 16px',
          }}
        >
          <strong>Ход {wireState?.turnCount}</strong>
          <span>{myTurn ? `Ваш ход · действий: ${actions}` : `Ходит ${turnOwnerName}`}</span>
          <span style={{ opacity: 0.6 }}>{phase}</span>
          <span style={{ opacity: 0.6 }}>
            {connectionStatus === 'connected' ? '🟢 online' : `🟡 ${connectionStatus}`}
          </span>
          <span style={{ marginLeft: 'auto', display: 'flex', gap: 8 }}>
            <Button
              variant="ghost"
              disabled={!myTurn || busy || gameOver}
              onClick={() => void run(pass)}
            >
              Пас
            </Button>
            <Button
              variant="ghost"
              disabled={!myTurn || busy || gameOver}
              onClick={() => void run(endTurn)}
            >
              Конец хода
            </Button>
            <Button variant="danger" onClick={() => setShowLeaveModal(true)}>
              Покинуть
            </Button>
          </span>
        </div>

        {/* Ошибка действия (сервер отклонил) */}
        {actionError && (
          <div
            style={{
              background: 'rgba(220, 60, 60, 0.15)',
              border: '1px solid rgba(220, 60, 60, 0.5)',
              padding: '6px 16px',
            }}
          >
            ⚠️ {actionError}
          </div>
        )}

        {/* Панель боя */}
        {combat && !gameOver && (
          <div
            style={{
              background: 'rgba(255, 165, 0, 0.12)',
              border: '1px solid rgba(255, 165, 0, 0.4)',
              padding: '8px 16px',
              display: 'flex',
              gap: 16,
              alignItems: 'center',
            }}
          >
            <strong>⚔️ Бой</strong>
            {phase === 'COMBAT' && amIDefender() && (
              <span>Вас атакуют! Кликните карту защиты (DEFENSE/VERSATILE) или сразу Resolve.</span>
            )}
            {phase === 'COMBAT' && !amIDefender() && <span>Ждём карту защитника…</span>}
            {phase === 'COMBAT_RESOLVE' && <span>Карты сыграны — резолв боя.</span>}
            {(isAttacker || phase === 'COMBAT_RESOLVE') && (
              <Button variant="primary" disabled={busy} onClick={() => void run(resolveCombat)}>
                Resolve
              </Button>
            )}
            {phase === 'COMBAT' && amIDefender() && (
              <Button variant="ghost" disabled={busy} onClick={() => void run(resolveCombat)}>
                Без защиты
              </Button>
            )}
          </div>
        )}

        {/* Отложенный эффект карты (C2): выбор бойца/клетки */}
        {activePending && !gameOver && (
          <div
            style={{
              background: 'rgba(120, 90, 220, 0.16)',
              border: '1px solid rgba(120, 90, 220, 0.5)',
              padding: '8px 16px',
              display: 'flex',
              gap: 16,
              alignItems: 'center',
            }}
          >
            <strong>✨ Эффект карты</strong>
            <span>{activePending.text ?? `${activePending.type} ${activePending.value ?? ''}`}</span>
            <span style={{ opacity: 0.8 }}>
              {pendingFighterId
                ? `Боец выбран — кликните клетку (${activePending.type === 'MOVE' ? `до ${activePending.value} шагов` : 'любая свободная'})`
                : `Кликните ${activePending.targetsOpponent ? 'бойца противника' : 'своего бойца'}${activePending.fighterName ? ` (${activePending.fighterName})` : ''}`}
            </span>
            {pendingEffects.length > 1 && (
              <span style={{ opacity: 0.6 }}>ещё в очереди: {pendingEffects.length - 1}</span>
            )}
          </div>
        )}

        {/* Доска (Phaser) — формат adaptedState, players[0] = локальный игрок */}
        <div className="game-view__middle" style={{ flex: 1, minHeight: 0 }}>
          <PhaserGame
            gameId={adaptedState.id}
            gameState={adaptedState}
            // в режиме pending подсвечиваем выбранного для эффекта бойца
            selectedFighterId={activePending ? pendingFighterId : selectedFighterId}
            selectedCardId={activePending ? null : selectedCardId}
            highlightedSpaces={[]}
            onGameEvent={handlePhaserEvent}
            width={1000}
            height={640}
          />
        </div>

        <Modal
          isOpen={showLeaveModal}
          onClose={() => setShowLeaveModal(false)}
          title="Покинуть игру"
        >
          <div className="game-view__modal-content">
            <p>Вы уверены, что хотите покинуть игру?</p>
            <div className="game-view__modal-actions">
              <Button variant="ghost" onClick={() => setShowLeaveModal(false)}>
                Отмена
              </Button>
              <Button variant="danger" onClick={() => void confirmLeave()}>
                Покинуть
              </Button>
            </div>
          </div>
        </Modal>

        {/* Конец игры */}
        <Modal isOpen={gameOver} onClose={() => navigate('/lobby')} title="Игра окончена">
          <div className="game-view__modal-content" style={{ textAlign: 'center' }}>
            <h2 style={{ fontSize: 40, margin: '8px 0' }}>
              {winnerId === localUserId ? '🏆 Победа!' : '💀 Поражение'}
            </h2>
            <p>
              {winnerId === localUserId
                ? 'Все бойцы противника повержены.'
                : `Победил ${opponent && winnerId === opponent.userId ? turnOwnerName || 'противник' : 'противник'}.`}
            </p>
            <Button variant="primary" onClick={() => navigate('/lobby')}>
              В лобби
            </Button>
          </div>
        </Modal>
      </div>
    </GameErrorBoundary>
  );
};

export default GameView;
