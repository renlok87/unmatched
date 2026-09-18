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
 * - после обязательного добора манёвра: выбрать BOOST и пути бойцов, подтвердить
 * - своя карта: SCHEME в свой ход → playScheme; ATTACK/VERSATILE → выбрать
 *   (затем клик по врагу = attack); DEFENSE/VERSATILE в COMBAT у защитника
 *   → playDefense
 * - лишние карты в конце хода выбираются по экземплярам до передачи хода
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
import { appendManeuverStep, resourceControls, toggleDiscardInstance, type ManeuverMove } from './turnResourceChoices';
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
    myStance,
    myStanceOptions,
    setStance,
    beginManeuver,
    completeManeuver,
    discardToLimit,
    attack,
    playDefense,
    playScheme,
    resolveCombat,
    resolvePendingEffect,
    resolveChooseOption,
    endTurn,
    leaveGame,
    clearErrors,
  } = useRemoteGameStore();

  const [showLeaveModal, setShowLeaveModal] = useState(false);
  const [busy, setBusy] = useState(false);
  // C2: боец, выбранный для резолва отложенного эффекта (MOVE/PLACE)
  const [pendingFighterId, setPendingFighterId] = useState<string | null>(null);
  const [maneuverMoves, setManeuverMoves] = useState<ManeuverMove[]>([]);
  const [maneuverBoost, setManeuverBoost] = useState('');
  const [discardIds, setDiscardIds] = useState<string[]>([]);
  const controls = resourceControls(wireState, localUserId);
  const hand = localUserId ? wireState?.handZones[localUserId]?.cards ?? [] : [];
  const ownFighters = wireState?.fighters.filter(f => f.ownerId === localUserId && f.health > 0 && !f.isDefeated) ?? [];

  // The server persists the choice itself. Local plans may be reselected after reload.
  useEffect(() => {
    setManeuverMoves([]);
    setManeuverBoost('');
    setDiscardIds([]);
  }, [controls.maneuver?.id, controls.discard?.id]);

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
    if (!wireState || !localUserId || busy || wireState.phase === 'GAME_OVER') return;
    const phase = wireState.phase;

    if (controls.discard) {
      if (event.type === 'CARD_CLICKED' && hand.some(card => card.id === event.cardId)) {
        setDiscardIds(ids => toggleDiscardInstance(ids, event.cardId, controls.discard!.count));
      }
      return;
    }

    if (controls.maneuver) {
      if (event.type === 'FIGHTER_CLICKED') {
        const fighter = ownFighters.find(f => f.id === event.fighterId);
        if (fighter) selectFighter(fighter.id);
      } else if (event.type === 'CARD_CLICKED' && hand.some(card => card.id === event.cardId)) {
        setManeuverBoost(id => id === event.cardId ? '' : event.cardId);
      } else if (event.type === 'SPACE_CLICKED' && selectedFighterId) {
        setManeuverMoves(moves => appendManeuverStep(moves, selectedFighterId, event.position));
      }
      return;
    }

    if (wireState.metadata.pendingManeuver || wireState.metadata.pendingHandDiscard) return;

    // CHOOSE_ONE (v3): выбор — кнопками в баннере, клики по доске игнорируем
    if (activePending && activePending.type === 'CHOOSE_ONE') {
      return;
    }

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
          controls.canAct &&
          (card.cardType === 'ATTACK' || card.cardType === 'VERSATILE')
        ) {
          void run(() => attack(myAttacker, fighter.id, card.id));
        }
        return;
      }

      case 'SPACE_CLICKED': {
        // Movement is planned only after beginManeuver has delivered its draw.
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

        if (!controls.canAct) return;

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

  // STANCE: виджет стоек МОЕГО героя (только если у героя есть стойки)
  const stanceOptions = myStanceOptions();
  const currentStanceId = myStance();

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
            {controls.canBegin && (
              <Button variant="primary" disabled={busy} onClick={() => void run(beginManeuver)}>
                Начать манёвр
              </Button>
            )}
            {controls.canEnd && (
              <Button variant="ghost" disabled={busy} onClick={() => void run(endTurn)}>
                Конец хода
              </Button>
            )}
            <Button variant="danger" onClick={() => setShowLeaveModal(true)}>
              Покинуть
            </Button>
          </span>
        </div>

        {controls.maneuver && (
          <section className="game-view__resource-panel" aria-label="Выбор манёвра">
            <div className="game-view__resource-heading">
              <strong>Манёвр · добор выполнен</strong>
              <span>Выберите усиление и пути бойцов. Можно остаться на месте.</span>
            </div>
            <label className="game-view__resource-field">
              Усиление манёвра
              <select aria-label="Усиление манёвра" value={maneuverBoost} disabled={busy}
                onChange={event => setManeuverBoost(event.target.value)}>
                <option value="">Без усиления</option>
                {hand.map((card, index) => (
                  <option key={card.id} value={card.id}>
                    {index + 1}. {card.nameRu || card.name} · BOOST +{card.boostValue ?? 0}
                  </option>
                ))}
              </select>
            </label>
            <label className="game-view__resource-field">
              Боец для движения
              <select aria-label="Боец для движения" value={selectedFighterId ?? ''} disabled={busy}
                onChange={event => selectFighter(event.target.value || null)}>
                <option value="">Выберите бойца</option>
                {ownFighters.map(fighter => (
                  <option key={fighter.id} value={fighter.id}>
                    {fighter.name} · ({fighter.position.x}, {fighter.position.y}) · движение {fighter.movement ?? 2}
                  </option>
                ))}
              </select>
            </label>
            <p>Кликните клетки пути по порядку, затем выберите следующего бойца. Движение применяется в указанном порядке.</p>
            {maneuverMoves.length > 0 && (
              <ol className="game-view__maneuver-routes">
                {maneuverMoves.map(move => (
                  <li key={move.fighterId}>
                    <span><strong>{ownFighters.find(f => f.id === move.fighterId)?.name}</strong>: {move.path.map(p => `(${p.x}, ${p.y})`).join(' → ')}</span>
                    <Button variant="ghost" disabled={busy} onClick={() => setManeuverMoves(moves =>
                      moves.flatMap(m => m.fighterId !== move.fighterId ? [m] : m.path.length > 1 ? [{ ...m, path: m.path.slice(0, -1) }] : []))}>
                      Убрать шаг
                    </Button>
                    <Button variant="ghost" disabled={busy} onClick={() => setManeuverMoves(moves => moves.filter(m => m.fighterId !== move.fighterId))}>
                      Очистить путь
                    </Button>
                  </li>
                ))}
              </ol>
            )}
            <Button variant="primary" disabled={busy} onClick={() => void run(() =>
              completeManeuver(controls.maneuver!.id, maneuverMoves, maneuverBoost || undefined))}>
              {maneuverMoves.length ? 'Подтвердить манёвр' : 'Завершить без движения'}
            </Button>
          </section>
        )}

        {controls.discard && (
          <section className="game-view__resource-panel" aria-label="Сброс в конце хода">
            <div className="game-view__resource-heading">
              <strong>Сбросьте лишние карты</strong>
              <span>Выбрано {discardIds.length} из {controls.discard.count}. После сброса ход перейдёт сопернику.</span>
            </div>
            <div className="game-view__discard-cards">
              {hand.map((card, index) => (
                <label key={card.id} className="game-view__discard-card">
                  <input type="checkbox" value={card.id} checked={discardIds.includes(card.id)}
                    disabled={busy || (!discardIds.includes(card.id) && discardIds.length >= controls.discard!.count)}
                    onChange={() => setDiscardIds(ids => toggleDiscardInstance(ids, card.id, controls.discard!.count))} />
                  <span>{index + 1}. {card.nameRu || card.name}<small>BOOST {card.boostValue ?? 0}</small></span>
                </label>
              ))}
            </div>
            <Button variant="primary" disabled={busy || discardIds.length !== controls.discard.count}
              onClick={() => void run(() => discardToLimit(controls.discard!.id, discardIds))}>
              Сбросить выбранные карты
            </Button>
          </section>
        )}

        {!gameOver && !controls.maneuver && !controls.discard &&
          (wireState?.metadata.pendingManeuver || wireState?.metadata.pendingHandDiscard) && (
            <div className="game-view__resource-panel" role="status">Соперник завершает выбор.</div>
          )}

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
            {activePending.type === 'CHOOSE_ONE' ? (
              <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', alignItems: 'center' }}>
                {(activePending.options ?? []).map((opt) => (
                  <button
                    key={opt.index}
                    disabled={busy}
                    onClick={() => void run(() => resolveChooseOption(activePending.id, opt.index))}
                    style={{
                      background: 'rgba(120, 90, 220, 0.35)',
                      border: '1px solid rgba(120, 90, 220, 0.7)',
                      color: '#fff',
                      padding: '4px 10px',
                      borderRadius: 6,
                      cursor: busy ? 'default' : 'pointer',
                    }}
                  >
                    {opt.label}
                  </button>
                ))}
                {(activePending.chooseCount ?? 1) > 1 && (
                  <span style={{ opacity: 0.7 }}>выберите {activePending.chooseCount}</span>
                )}
              </div>
            ) : (
              <span style={{ opacity: 0.8 }}>
                {pendingFighterId
                  ? `Боец выбран — кликните клетку (${activePending.type === 'MOVE' ? `до ${activePending.value} шагов` : 'любая свободная'})`
                  : `Кликните ${activePending.targetsOpponent ? 'бойца противника' : 'своего бойца'}${activePending.fighterName ? ` (${activePending.fighterName})` : ''}`}
              </span>
            )}
            {pendingEffects.length > 1 && (
              <span style={{ opacity: 0.6 }}>ещё в очереди: {pendingEffects.length - 1}</span>
            )}
          </div>
        )}

        {/* STANCE: стойка МОЕГО героя (показывается только если стойки есть) */}
        {stanceOptions.length > 0 && !gameOver && (
          <div
            style={{
              background: 'rgba(60, 140, 200, 0.14)',
              border: '1px solid rgba(60, 140, 200, 0.45)',
              padding: '8px 16px',
              display: 'flex',
              gap: 12,
              alignItems: 'center',
              flexWrap: 'wrap',
            }}
          >
            <strong>🥋 Стойка</strong>
            <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', alignItems: 'center' }}>
              {stanceOptions.map((opt) => {
                const active = opt.id === currentStanceId;
                return (
                  <button
                    key={opt.id}
                    disabled={busy || active || Boolean(wireState?.metadata.pendingManeuver || wireState?.metadata.pendingHandDiscard)}
                    onClick={() => void run(() => setStance(opt.id))}
                    style={{
                      background: active
                        ? 'rgba(60, 140, 200, 0.65)'
                        : 'rgba(60, 140, 200, 0.25)',
                      border: active
                        ? '1px solid rgba(60, 140, 200, 1)'
                        : '1px solid rgba(60, 140, 200, 0.6)',
                      color: '#fff',
                      padding: '4px 12px',
                      borderRadius: 6,
                      fontWeight: active ? 700 : 400,
                      cursor: busy || active ? 'default' : 'pointer',
                      opacity: busy && !active ? 0.6 : 1,
                    }}
                  >
                    {active ? `✓ ${opt.label}` : opt.label}
                  </button>
                );
              })}
            </div>
          </div>
        )}

        {/* Доска (Phaser) — формат adaptedState, players[0] = локальный игрок */}
        <div className="game-view__middle" style={{ flex: 1, minHeight: 0 }}>
          <PhaserGame
            gameId={adaptedState.id}
            gameState={adaptedState}
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
                ? 'Герой противника повержен.'
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
