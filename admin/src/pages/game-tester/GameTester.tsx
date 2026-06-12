/**
 * Game Tester — текстовая консоль для тестирования игровой логики через реальное API.
 *
 * P1 — текущий админ (токен из localStorage), P2 — тестовый пользователь,
 * который логинится/регистрируется прямо отсюда. Все действия выполняются
 * настоящими GraphQL-мутациями, результат пишется в читаемый лог.
 */
import { useEffect, useRef, useState } from 'react';
import { Button, Input, Select, Space, Tag, Typography, message } from 'antd';
import {
  ABORT_GAME,
  ATTACK,
  BOARD_OPTIONS,
  CREATE_GAME,
  END_TURN,
  GAME_STATE,
  GqlError,
  HERO_OPTIONS,
  JOIN_GAME,
  LOGIN,
  MANEUVER,
  MOVE_FIGHTER,
  PASS,
  PLAY_DEFENSE,
  PLAY_SCHEME, RESOLVE_PENDING_EFFECT,
  REGISTER,
  RESOLVE_COMBAT,
  SELECT_HERO,
  START_GAME,
  TOGGLE_DOOR,
  TOGGLE_READY,
  decodeJwtUserId,
  gqlRequest,
} from './api';

const { Title, Text } = Typography;

type PlayerKey = 'P1' | 'P2';

interface PlayerSlot {
  key: PlayerKey;
  token: string;
  userId: string;
  username: string;
}

interface LogEntry {
  id: number;
  ts: string;
  src: PlayerKey | 'SYS';
  kind: 'info' | 'ok' | 'error' | 'action' | 'block';
  text: string;
}

interface GameRef {
  id: string;
  code: string | null;
  status: string;
}

const LOG_COLORS: Record<string, string> = {
  SYS: '#9e9e9e',
  P1: '#4fc3f7',
  P2: '#ffb74d',
};

const KIND_COLORS: Record<string, string> = {
  error: '#ef5350',
  ok: '#81c784',
};

const HELP_TEXT = `Команды (2 действия за ход; после 2-го — авто-завершение хода):
  state            — краткое состояние игры
  state raw        — полный JSON состояния
  hand [p1|p2]     — рука игрока (карты с индексами c0, c1, ...)
  move <f> <x> <y>           — переместить бойца (f0/f1... или id, тратит 1 действие)
  maneuver <f> [<c>|-] <x>,<y> [...]     — манёвр: добор + движение; карта = BOOST к ходам (опц.)
  attack <f1> <f2> <c> [<boost>]         — атака картой (+BOOST-карта, тратит 1 действие)
  scheme <c>       — разыграть scheme-карту (тратит 1 действие)
  pending          — список отложенных эффектов (выбор игрока)
  peffect <id> <f> <x>,<y> — резолв отложенного MOVE/PLACE
  defense <c> [<boost>] — карта защиты (+BOOST-карта, за защищающегося)
  resolve          — разрешить бой
  end              — закончить ход досрочно
  pass             — пас (тратит 1 действие)
  door <x> <y>     — открыть/закрыть дверь
  abort            — прервать игру
  help             — эта справка
Актор: auto — мутация уходит от имени игрока, чей сейчас ход
(defense — от имени защищающегося). Можно зафиксировать P1/P2.`;

let logId = 0;

export const GameTester: React.FC = () => {
  const [log, setLog] = useState<LogEntry[]>([]);
  const [busy, setBusy] = useState(false);

  const [p2Email, setP2Email] = useState('tester2@unmached.local');
  const [p2Username, setP2Username] = useState('tester2');
  const [p2Password, setP2Password] = useState('Tester123!');

  const [heroes, setHeroes] = useState<any[]>([]);
  const [boards, setBoards] = useState<any[]>([]);
  const [heroP1, setHeroP1] = useState<string>();
  const [heroP2, setHeroP2] = useState<string>();
  const [boardId, setBoardId] = useState<string>();

  const [p1, setP1] = useState<PlayerSlot | null>(null);
  const [p2, setP2] = useState<PlayerSlot | null>(null);
  const [game, setGame] = useState<GameRef | null>(null);
  const [actor, setActor] = useState<'auto' | PlayerKey>('auto');
  const [cmd, setCmd] = useState('');

  // Последнее известное состояние (распарсенный GameState JSON) и руки по игрокам
  const stateRef = useRef<any | null>(null);
  const handsRef = useRef<Record<PlayerKey, any[]>>({ P1: [], P2: [] });
  const logBoxRef = useRef<HTMLDivElement>(null);
  // id игры в ref — setGame асинхронный, а refreshState зовётся сразу после старта
  const gameIdRef = useRef<string | null>(null);
  // Слоты игроков в ref — setState не успевает примениться внутри setupGame
  const slotsRef = useRef<{ P1: PlayerSlot | null; P2: PlayerSlot | null }>({ P1: null, P2: null });

  const setGameRef = (g: GameRef | null) => {
    setGame(g);
    gameIdRef.current = g?.id ?? null;
  };

  useEffect(() => {
    logBoxRef.current?.scrollTo({ top: logBoxRef.current.scrollHeight });
  }, [log]);

  // ============ лог ============

  const push = (src: LogEntry['src'], kind: LogEntry['kind'], text: string) => {
    setLog((prev) => [
      ...prev,
      { id: ++logId, ts: new Date().toLocaleTimeString(), src, kind, text },
    ]);
  };

  const sys = (text: string) => push('SYS', 'info', text);
  const err = (src: LogEntry['src'], text: string) => push(src, 'error', `✖ ${text}`);

  // ============ игроки/токены ============

  const adminToken = () => localStorage.getItem('accessToken') || '';

  const ensureP1 = (): PlayerSlot => {
    if (slotsRef.current.P1) return slotsRef.current.P1;
    const token = adminToken();
    const userId = decodeJwtUserId(token) || '';
    const slot: PlayerSlot = { key: 'P1', token, userId, username: 'admin' };
    slotsRef.current.P1 = slot;
    setP1(slot);
    return slot;
  };

  const ensureP2 = async (): Promise<PlayerSlot> => {
    if (slotsRef.current.P2) return slotsRef.current.P2;
    try {
      const data = await gqlRequest(LOGIN, { email: p2Email, password: p2Password });
      const slot: PlayerSlot = {
        key: 'P2',
        token: data.login.accessToken,
        userId: data.login.user.id,
        username: data.login.user.username,
      };
      slotsRef.current.P2 = slot;
      setP2(slot);
      push('P2', 'ok', `✔ Логин: ${slot.username} (${p2Email})`);
      return slot;
    } catch (e: any) {
      sys(`Логин P2 не удался (${e.message}), пробую регистрацию...`);
      const data = await gqlRequest(REGISTER, {
        email: p2Email,
        username: p2Username,
        password: p2Password,
      });
      const slot: PlayerSlot = {
        key: 'P2',
        token: data.register.accessToken,
        userId: data.register.user.id,
        username: data.register.user.username,
      };
      slotsRef.current.P2 = slot;
      setP2(slot);
      push('P2', 'ok', `✔ Зарегистрирован и залогинен: ${slot.username}`);
      return slot;
    }
  };

  const slotByUserId = (userId: string): PlayerSlot | null => {
    if (slotsRef.current.P1?.userId === userId) return slotsRef.current.P1;
    if (slotsRef.current.P2?.userId === userId) return slotsRef.current.P2;
    return null;
  };

  const nameByUserId = (userId: string): string => {
    const slot = slotByUserId(userId);
    return slot ? `${slot.key}:${slot.username}` : userId.slice(0, 8);
  };

  /** Кто должен выполнять действие при actor=auto */
  const resolveActor = (action: string): PlayerSlot => {
    if (actor === 'P1') return ensureP1();
    if (actor === 'P2') {
      if (!slotsRef.current.P2) throw new Error('P2 не залогинен — нажми «Сетап игры» или «Логин P2»');
      return slotsRef.current.P2;
    }
    const state = stateRef.current;
    if (!state) return ensureP1();
    if (action === 'defense') {
      const defenderId = state.metadata?.combatInfo?.defenderId;
      const slot = defenderId ? slotByUserId(defenderId) : null;
      if (slot) return slot;
      // нет combatInfo — берём «не текущего» игрока
      const other =
        state.currentTurnPlayerId === slotsRef.current.P1?.userId
          ? slotsRef.current.P2
          : slotsRef.current.P1;
      if (other) return other;
      return ensureP1();
    }
    const slot = slotByUserId(state.currentTurnPlayerId);
    return slot || ensureP1();
  };

  // ============ состояние ============

  const fighterRefs = (): any[] => stateRef.current?.fighters || [];

  const posStr = (pos: any): string => {
    if (!pos) return '(?)';
    const p = typeof pos === 'string' ? JSON.parse(pos) : pos;
    return `(${p.x},${p.y})`;
  };

  const cardLabel = (card: any, idx?: number): string => {
    if (!card || typeof card !== 'object') return String(card);
    const vals = [
      card.attackValue != null ? `⚔${card.attackValue}` : null,
      card.defenseValue != null ? `🛡${card.defenseValue}` : null,
      card.boostValue != null ? `⬆${card.boostValue}` : null,
    ]
      .filter(Boolean)
      .join(' ');
    const prefix = idx != null ? `c${idx} ` : '';
    return `${prefix}[${card.cardType || card.type || '?'}] ${card.name || card.id} ${vals}`.trim();
  };

  const summarize = (state: any): string => {
    if (!state) return '(нет состояния)';
    const lines: string[] = [];
    lines.push(
      `─── Ход ${state.turnCount} | фаза ${state.phase} | ходит ${nameByUserId(state.currentTurnPlayerId)} | действий: ${state.metadata?.actionsRemaining ?? 2} | seq ${state.sequenceNumber}`,
    );
    for (const pl of state.players || []) {
      const slot = slotByUserId(pl.userId);
      const hand = slot ? handsRef.current[slot.key] : [];
      lines.push(
        `${nameByUserId(pl.userId)} HP ${pl.health}/${pl.maxHealth}${pl.isAlive ? '' : ' ☠ ВЫБЫЛ'} | рука: ${hand.length} карт`,
      );
    }
    const fighters = state.fighters || [];
    if (fighters.length === 0) {
      lines.push('  (бойцов на доске нет)');
    }
    fighters.forEach((f: any, i: number) => {
      lines.push(
        `  f${i} ${f.name} (${f.type}) ${f.attackType === 'ranged' ? '🏹' : '🗡'} HP ${f.health}/${f.maxHealth} @ ${posStr(f.position)} — ${nameByUserId(f.ownerId)}${(f.effects?.length ? ' fx:' + f.effects.join(',') : '')}`,
      );
    });
    const combat = state.metadata?.combatInfo;
    if (combat) {
      lines.push(
        `  ⚔ БОЙ: ${combat.attackerId} → ${combat.defenderId}, атака ${combat.attackValue ?? '?'}${combat.defenseValue != null ? `, защита ${combat.defenseValue}` : ', защита не сыграна'}`,
      );
    }
    return lines.join('\n');
  };

  const diff = (prev: any, next: any): string[] => {
    if (!prev || !next) return [];
    const out: string[] = [];
    if (prev.phase !== next.phase) out.push(`фаза ${prev.phase} → ${next.phase}`);
    if (prev.turnCount !== next.turnCount) out.push(`ход ${prev.turnCount} → ${next.turnCount}`);
    if (prev.metadata?.actionsRemaining !== next.metadata?.actionsRemaining) {
      out.push(`действия ${prev.metadata?.actionsRemaining ?? 2} → ${next.metadata?.actionsRemaining ?? 2}`);
    }
    if (prev.currentTurnPlayerId !== next.currentTurnPlayerId) {
      out.push(`ходит → ${nameByUserId(next.currentTurnPlayerId)}`);
    }
    const prevF: Record<string, any> = {};
    (prev.fighters || []).forEach((f: any) => (prevF[f.id] = f));
    (next.fighters || []).forEach((f: any) => {
      const old = prevF[f.id];
      if (!old) {
        out.push(`+ боец ${f.name} @ ${posStr(f.position)}`);
        return;
      }
      if (old.health !== f.health) out.push(`💥 ${f.name} HP ${old.health} → ${f.health}`);
      if (posStr(old.position) !== posStr(f.position)) {
        out.push(`📍 ${f.name} ${posStr(old.position)} → ${posStr(f.position)}`);
      }
    });
    (prev.players || []).forEach((pl: any) => {
      const cur = (next.players || []).find((x: any) => x.userId === pl.userId);
      if (cur && cur.health !== pl.health) {
        out.push(`❤ ${nameByUserId(pl.userId)} HP ${pl.health} → ${cur.health}`);
      }
    });
    return out;
  };

  /** Принять новое состояние (из мутации или запроса), залогировать дифф и сводку */
  const acceptState = (rawState: string | null, viewer: PlayerKey) => {
    if (!rawState) return;
    let parsed: any;
    try {
      parsed = typeof rawState === 'string' ? JSON.parse(rawState) : rawState;
    } catch {
      push('SYS', 'block', String(rawState).slice(0, 2000));
      return;
    }
    const changes = diff(stateRef.current, parsed);
    stateRef.current = parsed;
    // рука видна только владельцу — обновляем руку наблюдателя
    const slot = slotsRef.current[viewer];
    if (slot) {
      const zone = parsed.handZones?.[slot.userId];
      const cards = typeof zone?.cards === 'string' ? JSON.parse(zone.cards) : zone?.cards;
      if (Array.isArray(cards)) handsRef.current[viewer] = cards;
    }
    changes.forEach((c) => push('SYS', 'info', `  Δ ${c}`));
    push('SYS', 'block', summarize(parsed));
  };

  /** Запросить состояние под обоими токенами (руки обоих) */
  const refreshState = async (silent = false, slotsOverride?: PlayerSlot[]) => {
    const gameId = gameIdRef.current;
    if (!gameId) throw new Error('Нет активной игры');
    const slots =
      slotsOverride ??
      ([slotsRef.current.P1, slotsRef.current.P2].filter(Boolean) as PlayerSlot[]);
    let last: any = null;
    for (const slot of slots) {
      const data = await gqlRequest(GAME_STATE, { gameId }, slot.token);
      if (!data.gameState) continue;
      const parsed = JSON.parse(data.gameState.state);
      const zone = parsed.handZones?.[slot.userId];
      const cards = typeof zone?.cards === 'string' ? JSON.parse(zone.cards) : zone?.cards;
      if (Array.isArray(cards)) handsRef.current[slot.key] = cards;
      last = parsed;
    }
    if (last) {
      stateRef.current = last;
      if (!silent) push('SYS', 'block', summarize(last));
    } else if (!silent) {
      sys('gameState вернул null — состояние игры ещё не создано');
    }
  };

  // ============ ссылки на бойцов/карты ============

  const resolveFighter = (ref: string): any => {
    const fighters = fighterRefs();
    const m = ref.match(/^f(\d+)$/i);
    if (m) {
      const f = fighters[Number(m[1])];
      if (!f) throw new Error(`Нет бойца ${ref} (всего ${fighters.length})`);
      return f;
    }
    const found = fighters.find(
      (f: any) => f.id === ref || f.id?.startsWith(ref) || f.name?.toLowerCase() === ref.toLowerCase(),
    );
    if (!found) throw new Error(`Боец «${ref}» не найден. Сделай "state" и используй f0/f1/...`);
    return found;
  };

  const resolveCard = (slot: PlayerSlot, ref: string): any => {
    const hand = handsRef.current[slot.key] || [];
    const m = ref.match(/^c(\d+)$/i);
    if (m) {
      const c = hand[Number(m[1])];
      if (!c) throw new Error(`Нет карты ${ref} в руке ${slot.key} (карт: ${hand.length})`);
      return c;
    }
    const found = hand.find((c: any) => c.id === ref || c.id?.startsWith(ref));
    if (!found) throw new Error(`Карта «${ref}» не найдена в руке ${slot.key}. Сделай "hand"`);
    return found;
  };

  // ============ выполнение шага с логом ============

  const step = async <T,>(
    src: LogEntry['src'],
    title: string,
    fn: () => Promise<T>,
  ): Promise<T> => {
    push(src, 'action', `▶ ${title}`);
    try {
      const result = await fn();
      return result;
    } catch (e: any) {
      const msg = e instanceof GqlError ? e.message : e.message || String(e);
      err(src, msg);
      throw e;
    }
  };

  const runAction = async (
    slot: PlayerSlot,
    title: string,
    mutation: string,
    variables: Record<string, unknown>,
    resultKey: string,
  ) => {
    await step(slot.key, title, async () => {
      const data = await gqlRequest(mutation, variables, slot.token);
      const result = data[resultKey];
      push(slot.key, 'ok', `✔ ${title} (seq ${result.sequenceNumber}, фаза ${result.phase})`);
      acceptState(result.state, slot.key);
      return result;
    });
  };

  // ============ сетап ============

  const loadOptions = async () => {
    const token = adminToken();
    const [h, b] = await Promise.all([
      gqlRequest(HERO_OPTIONS, {}, token),
      gqlRequest(BOARD_OPTIONS, {}, token),
    ]);
    setHeroes(h.heroList.items);
    setBoards(b.boardList.items);
    if (!heroP1 && h.heroList.items[0]) setHeroP1(h.heroList.items[0].id);
    if (!heroP2 && h.heroList.items[1]) setHeroP2(h.heroList.items[1].id);
    if (!boardId && b.boardList.items[0]) setBoardId(b.boardList.items[0].id);
  };

  useEffect(() => {
    ensureP1();
    loadOptions().catch((e) => err('SYS', `Справочники не загрузились: ${e.message}`));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const setupGame = async () => {
    setBusy(true);
    try {
      const P1 = ensureP1();
      sys('=== ПОЛНЫЙ СЕТАП ИГРЫ 1v1 ===');
      const P2 = await ensureP2();

      const created = await step('P1', `createGame(ONE_V_ONE, board=${boardId || 'default'})`, () =>
        gqlRequest(CREATE_GAME, { mode: 'ONE_V_ONE', boardId }, P1.token),
      );
      const g = created.createGame;
      setGameRef({ id: g.id, code: g.code, status: g.status });
      push('P1', 'ok', `✔ Игра создана: id=${g.id} code=${g.code} status=${g.status}`);

      const joined = await step('P2', 'joinGame', () =>
        gqlRequest(JOIN_GAME, { gameId: g.id }, P2.token),
      );
      push('P2', 'ok', `✔ Подключился (status=${joined.joinGame.status})`);

      const h1 = heroes.find((h) => h.id === heroP1);
      const h2 = heroes.find((h) => h.id === heroP2);
      await step('P1', `selectHero(${h1?.name})`, () =>
        gqlRequest(SELECT_HERO, { gameId: g.id, heroId: heroP1 }, P1.token),
      );
      push('P1', 'ok', `✔ Герой: ${h1?.name}`);
      await step('P2', `selectHero(${h2?.name})`, () =>
        gqlRequest(SELECT_HERO, { gameId: g.id, heroId: heroP2 }, P2.token),
      );
      push('P2', 'ok', `✔ Герой: ${h2?.name}`);

      await step('P1', 'toggleReady', () => gqlRequest(TOGGLE_READY, { gameId: g.id }, P1.token));
      push('P1', 'ok', '✔ Готов');
      await step('P2', 'toggleReady', () => gqlRequest(TOGGLE_READY, { gameId: g.id }, P2.token));
      push('P2', 'ok', '✔ Готов');

      const started = await step('P1', 'startGame', () =>
        gqlRequest(START_GAME, { gameId: g.id }, P1.token),
      );
      const sg = started.startGame;
      setGameRef({ id: g.id, code: g.code, status: sg.status });
      push('P1', 'ok', `✔ Игра запущена: status=${sg.status} phase=${sg.phase ?? '—'}`);

      sys('Запрашиваю начальное состояние...');
      await refreshState();
      sys('Сетап завершён. Команды: help. Действия — от имени игрока, чей ход (auto).');
    } catch (e: any) {
      err('SYS', e?.message || String(e));
      sys('Сетап прерван.');
    } finally {
      setBusy(false);
    }
  };

  // ============ команды ============

  const execCommand = async (raw: string) => {
    const parts = raw.trim().split(/\s+/);
    const command = parts[0]?.toLowerCase();
    if (!command) return;
    push('SYS', 'info', `> ${raw.trim()}`);

    if (command === 'help') {
      push('SYS', 'block', HELP_TEXT);
      return;
    }

    if (!game && command !== 'help') {
      err('SYS', 'Нет активной игры — нажми «Сетап игры»');
      return;
    }

    setBusy(true);
    try {
      switch (command) {
        case 'state': {
          if (parts[1] === 'raw') {
            await refreshState(true);
            push('SYS', 'block', JSON.stringify(stateRef.current, null, 2));
          } else {
            await refreshState();
          }
          break;
        }
        case 'hand': {
          await refreshState(true);
          const keys: PlayerKey[] =
            parts[1]?.toLowerCase() === 'p1' ? ['P1'] : parts[1]?.toLowerCase() === 'p2' ? ['P2'] : ['P1', 'P2'];
          for (const k of keys) {
            const hand = handsRef.current[k] || [];
            const lines = hand.length
              ? hand.map((c: any, i: number) => '  ' + cardLabel(c, i)).join('\n')
              : '  (пусто)';
            push('SYS', 'block', `Рука ${k}:\n${lines}`);
          }
          break;
        }
        case 'move': {
          const [, fRef, x, y] = parts;
          if (!fRef || x == null || y == null) throw new Error('move <f> <x> <y>');
          const slot = resolveActor('move');
          const f = resolveFighter(fRef);
          await runAction(slot, `moveFighter(${f.name} → ${x},${y})`, MOVE_FIGHTER, {
            input: { gameId: gameIdRef.current!, fighterId: f.id, x: Number(x), y: Number(y) },
          }, 'moveFighter');
          break;
        }
        case 'maneuver': {
          // maneuver <f> [<boostCard>|-] <x>,<y> ... — boost-карта опциональна
          // ('-' или сразу путь = манёвр без карты: чистые «добор + движение»)
          const [, fRef, second, ...rest] = parts;
          if (!fRef || !second) {
            throw new Error('maneuver <f> [<boostCard>|-] <x>,<y> [<x>,<y> ...]');
          }
          const slot = resolveActor('maneuver');
          const f = resolveFighter(fRef);
          const secondIsPath = second.includes(',');
          const boostRef = secondIsPath || second === '-' ? null : second;
          const pathParts = secondIsPath ? [second, ...rest] : rest;
          if (pathParts.length === 0) {
            throw new Error('maneuver: путь пуст — укажи хотя бы одну точку <x>,<y>');
          }
          const boostCard = boostRef ? resolveCard(slot, boostRef) : null;
          const path = pathParts.map((p) => {
            const [px, py] = p.split(',').map(Number);
            if (Number.isNaN(px) || Number.isNaN(py)) throw new Error(`Плохая точка пути: ${p}`);
            return { x: px, y: py };
          });
          const label = boostCard
            ? `maneuver(${f.name}, BOOST ${boostCard.name}, путь ${pathParts.join(' ')})`
            : `maneuver(${f.name}, без карты, путь ${pathParts.join(' ')})`;
          await runAction(slot, label, MANEUVER, {
            input: {
              gameId: gameIdRef.current!,
              fighterId: f.id,
              boostCardId: boostCard?.id ?? null,
              path,
            },
          }, 'maneuver');
          break;
        }
        case 'attack': {
          const [, aRef, tRef, cRef, bRef] = parts;
          if (!aRef || !tRef || !cRef) throw new Error('attack <f-атакующий> <f-цель> <c> [<boostCard>]');
          const slot = resolveActor('attack');
          const attacker = resolveFighter(aRef);
          const target = resolveFighter(tRef);
          const card = resolveCard(slot, cRef);
          const boost = bRef ? resolveCard(slot, bRef) : null;
          const label = boost
            ? `attack(${attacker.name} → ${target.name}, ${card.name} + BOOST ${boost.name})`
            : `attack(${attacker.name} → ${target.name}, ${card.name})`;
          await runAction(slot, label, ATTACK, {
            input: { gameId: gameIdRef.current!, attackerId: attacker.id, targetId: target.id, cardId: card.id, boostCardId: boost?.id ?? null },
          }, 'attack');
          break;
        }
        case 'defense': {
          const [, cRef, bRef] = parts;
          if (!cRef) throw new Error('defense <c> [<boostCard>]');
          const slot = resolveActor('defense');
          const card = resolveCard(slot, cRef);
          const boost = bRef ? resolveCard(slot, bRef) : null;
          const label = boost
            ? `playDefense(${card.name} + BOOST ${boost.name})`
            : `playDefense(${card.name})`;
          await runAction(slot, label, PLAY_DEFENSE, {
            input: { gameId: gameIdRef.current!, cardId: card.id, boostCardId: boost?.id ?? null },
          }, 'playDefense');
          break;
        }
        case 'scheme': {
          const [, cRef] = parts;
          if (!cRef) throw new Error('scheme <c>');
          const slot = resolveActor('scheme');
          const card = resolveCard(slot, cRef);
          await runAction(slot, `playScheme(${card.name})`, PLAY_SCHEME, {
            input: { gameId: gameIdRef.current!, cardId: card.id },
          }, 'playScheme');
          break;
        }
        case 'resolve': {
          const slot = resolveActor('resolve');
          await runAction(slot, 'resolveCombat', RESOLVE_COMBAT, {
            input: { gameId: gameIdRef.current! },
          }, 'resolveCombat');
          break;
        }
        case 'pending': {
          // список отложенных эффектов (выборов игрока) из metadata
          const pend = (stateRef.current?.metadata?.pendingEffects ?? []) as any[];
          if (pend.length === 0) {
            sys('Отложенных эффектов нет');
          } else {
            pend.forEach((p: any) =>
              sys(`⏳ ${p.id} [${p.type}${p.value ? ' ' + p.value : ''}] ${p.text ?? ''}`),
            );
          }
          break;
        }
        case 'peffect': {
          // peffect <effectId> <f> <x>,<y> — резолв отложенного MOVE/PLACE
          const [, effId, fRef, posRef] = parts;
          if (!effId || !fRef || !posRef) throw new Error('peffect <effectId> <f> <x>,<y>');
          const slot = resolveActor('peffect');
          const f = resolveFighter(fRef);
          const [px, py] = posRef.split(',').map(Number);
          if (Number.isNaN(px) || Number.isNaN(py)) throw new Error(`Плохая клетка: ${posRef}`);
          await runAction(slot, `resolvePendingEffect(${effId}, ${f.name} → ${px},${py})`, RESOLVE_PENDING_EFFECT, {
            input: { gameId: gameIdRef.current!, effectId: effId, fighterId: f.id, x: px, y: py },
          }, 'resolvePendingEffect');
          break;
        }
        case 'end': {
          const slot = resolveActor('end');
          await runAction(slot, 'endTurn', END_TURN, { input: { gameId: gameIdRef.current! } }, 'endTurn');
          break;
        }
        case 'pass': {
          const slot = resolveActor('pass');
          await runAction(slot, 'pass', PASS, { input: { gameId: gameIdRef.current! } }, 'pass');
          break;
        }
        case 'door': {
          const [, x, y] = parts;
          if (x == null || y == null) throw new Error('door <x> <y>');
          const slot = resolveActor('door');
          await runAction(slot, `toggleDoor(${x},${y})`, TOGGLE_DOOR, {
            input: { gameId: gameIdRef.current!, x: Number(x), y: Number(y) },
          }, 'toggleDoor');
          break;
        }
        case 'abort': {
          const P1 = ensureP1();
          await step('P1', 'abortGame', () => gqlRequest(ABORT_GAME, { gameId: gameIdRef.current! }, P1.token));
          push('P1', 'ok', '✔ Игра прервана');
          setGameRef(null);
          stateRef.current = null;
          break;
        }
        default:
          err('SYS', `Неизвестная команда «${command}». help — список команд`);
      }
    } catch (e: any) {
      if (!(e instanceof GqlError)) {
        // GqlError уже залогирован в step/runAction
        if (!String(e?.logged) /* локальные ошибки парсинга */) err('SYS', e.message || String(e));
      }
    } finally {
      setBusy(false);
    }
  };

  const onCmdSubmit = () => {
    if (!cmd.trim() || busy) return;
    const value = cmd;
    setCmd('');
    void execCommand(value);
  };

  const copyLog = async () => {
    const text = log.map((e) => `[${e.ts}] [${e.src}] ${e.text}`).join('\n');
    await navigator.clipboard.writeText(text);
    message.success('Лог скопирован');
  };

  // ============ render ============

  const heroOptions = heroes.map((h) => ({ value: h.id, label: `${h.name} (${h.health} HP)` }));

  return (
    <div>
      <Title level={3}>Game Tester</Title>
      <Text type="secondary">
        Текстовое тестирование игровой логики через реальное API. P1 — админ, P2 — тестовый юзер.
      </Text>

      <Space direction="vertical" size="middle" style={{ width: '100%', marginTop: 16 }}>
        <Space wrap>
          <Input addonBefore="P2 email" value={p2Email} onChange={(e) => setP2Email(e.target.value)} style={{ width: 280 }} />
          <Input addonBefore="username" value={p2Username} onChange={(e) => setP2Username(e.target.value)} style={{ width: 200 }} />
          <Input.Password addonBefore="password" value={p2Password} onChange={(e) => setP2Password(e.target.value)} style={{ width: 220 }} />
          <Button onClick={() => { setBusy(true); ensureP2().catch((e) => err('P2', e.message)).finally(() => setBusy(false)); }} disabled={busy}>
            Логин P2
          </Button>
        </Space>

        <Space wrap>
          <Select placeholder="Герой P1" options={heroOptions} value={heroP1} onChange={setHeroP1} style={{ width: 240 }} showSearch optionFilterProp="label" />
          <Select placeholder="Герой P2" options={heroOptions} value={heroP2} onChange={setHeroP2} style={{ width: 240 }} showSearch optionFilterProp="label" />
          <Select
            placeholder="Доска"
            options={boards.map((b) => ({ value: b.id, label: `${b.name} (${b.width}×${b.height})` }))}
            value={boardId}
            onChange={setBoardId}
            style={{ width: 260 }}
            showSearch
            optionFilterProp="label"
          />
          <Button type="primary" onClick={setupGame} disabled={busy || !heroP1 || !heroP2}>
            ▶ Сетап игры
          </Button>
        </Space>

        <Space wrap>
          {game && (
            <>
              <Tag color="blue">game: {game.code || game.id.slice(0, 8)}</Tag>
              <Tag color={game.status === 'IN_PROGRESS' ? 'green' : 'orange'}>{game.status}</Tag>
            </>
          )}
          <Select
            value={actor}
            onChange={setActor}
            style={{ width: 160 }}
            options={[
              { value: 'auto', label: 'Актор: auto' },
              { value: 'P1', label: `Актор: P1${p1 ? ` (${p1.username})` : ''}` },
              { value: 'P2', label: `Актор: P2${p2 ? ` (${p2.username})` : ''}` },
            ]}
          />
          <Button onClick={() => void execCommand('state')} disabled={busy || !game}>Состояние</Button>
          <Button onClick={() => void execCommand('hand')} disabled={busy || !game}>Руки</Button>
          <Button onClick={() => void execCommand('end')} disabled={busy || !game}>End Turn</Button>
          <Button onClick={() => void execCommand('pass')} disabled={busy || !game}>Pass</Button>
          <Button onClick={() => void execCommand('resolve')} disabled={busy || !game}>Resolve</Button>
          <Button danger onClick={() => void execCommand('abort')} disabled={busy || !game}>Abort</Button>
          <Button onClick={() => push('SYS', 'block', HELP_TEXT)}>Help</Button>
          <Button onClick={copyLog} disabled={log.length === 0}>Копировать лог</Button>
          <Button onClick={() => setLog([])} disabled={log.length === 0}>Очистить</Button>
        </Space>

        <div
          ref={logBoxRef}
          style={{
            background: '#1e1e1e',
            color: '#ccc',
            fontFamily: 'Consolas, Menlo, monospace',
            fontSize: 12.5,
            lineHeight: 1.55,
            borderRadius: 8,
            padding: 16,
            height: 480,
            overflow: 'auto',
            whiteSpace: 'pre-wrap',
            wordBreak: 'break-word',
          }}
        >
          {log.length === 0 && (
            <span style={{ color: '#777' }}>
              Лог пуст. Выбери героев и доску, нажми «Сетап игры». Затем командуй: help
            </span>
          )}
          {log.map((e) => (
            <div key={e.id} style={{ color: KIND_COLORS[e.kind] || LOG_COLORS[e.src] || '#ccc' }}>
              {e.kind === 'block' ? (
                <div style={{ color: '#b0bec5', margin: '4px 0 8px 0', padding: '6px 10px', background: '#252526', borderLeft: '3px solid #444', borderRadius: 4 }}>
                  {e.text}
                </div>
              ) : (
                <span>
                  <span style={{ color: '#666' }}>[{e.ts}]</span>{' '}
                  <span style={{ color: LOG_COLORS[e.src], fontWeight: 600 }}>[{e.src}]</span> {e.text}
                </span>
              )}
            </div>
          ))}
        </div>

        <Space.Compact style={{ width: '100%' }}>
          <Input
            placeholder='Команда (help — справка), напр.: move f0 3 4 | attack f0 f2 c1 | end'
            value={cmd}
            onChange={(e) => setCmd(e.target.value)}
            onPressEnter={onCmdSubmit}
            disabled={busy}
            style={{ fontFamily: 'Consolas, Menlo, monospace' }}
          />
          <Button type="primary" onClick={onCmdSubmit} disabled={busy || !cmd.trim()}>
            Выполнить
          </Button>
        </Space.Compact>
      </Space>
    </div>
  );
};
