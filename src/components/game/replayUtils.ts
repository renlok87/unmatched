// ============================================================
// REPLAY UTILS - Утилиты для работы с replay
// ============================================================

/**
 * Форматирует время в миллисекундах в читаемый формат
 */
export function formatTime(ms: number): string {
  if (ms < 0) ms = 0;

  const seconds = Math.floor(ms / 1000);
  const minutes = Math.floor(seconds / 60);
  const remainingSeconds = seconds % 60;

  return `${minutes}:${remainingSeconds.toString().padStart(2, '0')}`;
}

/**
 * Парсит строку времени в миллисекунды
 */
export function parseTime(timeStr: string): number {
  const parts = timeStr.split(':');
  if (parts.length !== 2) return 0;

  const minutes = parseInt(parts[0], 10);
  const seconds = parseInt(parts[1], 10);

  return (minutes * 60 + seconds) * 1000;
}

/**
 * Вычисляет прогресс воспроизведения
 */
export function calculateProgress(currentTime: number, duration: number): number {
  if (duration <= 0) return 0;
  return Math.min(100, Math.max(0, (currentTime / duration) * 100));
}

/**
 * Форматирует тип события для отображения
 */
export function formatEventType(eventType: string): string {
  return eventType
    .split('_')
    .map(word => word.charAt(0).toUpperCase() + word.slice(1))
    .join(' ');
}

/**
 * Определяет цвет для типа события
 */
export function getEventColor(eventType: string): string {
  const colorMap: Record<string, string> = {
    'game_started': '#4ecca3',
    'game_ended': '#ffd93d',
    'maneuver': '#6c5ce7',
    'attack': '#ff6b6b',
    'play_defense': '#48dbfb',
    'resolve_combat': '#ff9500',
    'fighter_defeated': '#ff4444',
    'card_played': '#a29bfe',
    'turn_changed': '#74b9ff',
  };

  return colorMap[eventType] || '#888';
}

/**
 * Проверяет валидность replay
 */
export function validateReplay(replay: unknown): boolean {
  if (!replay || typeof replay !== 'object') return false;

  const r = replay as Record<string, unknown>;

  return (
    typeof r.id === 'string' &&
    typeof r.gameId === 'string' &&
    typeof r.startTime === 'number' &&
    Array.isArray(r.events) &&
    Array.isArray(r.players)
  );
}

/**
 * Фильтрует события по типу
 */
export function filterEventsByType<T>(
  events: T[],
  eventType: string,
  typeKey: string = 'type'
): T[] {
  return events.filter((event) => (event as Record<string, unknown>)[typeKey] === eventType);
}

/**
 * Находит событие по времени
 */
export function findEventAtTime<T>(
  events: T[],
  time: number,
  timeKey: string = 'timestamp'
): T | null {
  let left = 0;
  let right = events.length - 1;

  while (left <= right) {
    const mid = Math.floor((left + right) / 2);
    const eventTime = (events[mid] as Record<string, unknown>)[timeKey] as number;

    if (eventTime === time) {
      return events[mid];
    } else if (eventTime < time) {
      left = mid + 1;
    } else {
      right = mid - 1;
    }
  }

  return events[right] ?? null;
}

/**
 * Создаёт миниатюру для события (для timeline)
 */
export function createEventThumbnail(
  eventType: string,
  size: number = 16
): string {
  const canvas = document.createElement('canvas');
  canvas.width = size;
  canvas.height = size;
  const ctx = canvas.getContext('2d');

  if (!ctx) return '';

  const color = getEventColor(eventType);

  ctx.fillStyle = color;
  ctx.beginPath();
  ctx.arc(size / 2, size / 2, size / 2, 0, Math.PI * 2);
  ctx.fill();

  return canvas.toDataURL();
}

/**
 * Экспортирует replay в файл
 */
export function downloadReplay(replay: unknown, filename?: string): void {
  const json = JSON.stringify(replay, null, 2);
  const blob = new Blob([json], { type: 'application/json' });
  const url = URL.createObjectURL(blob);

  const a = document.createElement('a');
  a.href = url;
  a.download = filename ?? `replay_${Date.now()}.json`;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);

  URL.revokeObjectURL(url);
}

/**
 * Импортирует replay из файла
 */
export async function uploadReplay(file: File): Promise<unknown | null> {
  try {
    const text = await file.text();
    const replay = JSON.parse(text);

    if (!validateReplay(replay)) {
      throw new Error('Invalid replay format');
    }

    return replay;
  } catch (e) {
    console.error('Failed to load replay:', e);
    return null;
  }
}

/**
 * Создаёт статистику по replay
 */
export interface ReplayStats {
  totalEvents: number;
  eventTypes: Record<string, number>;
  averageActionsPerTurn: number;
  longestTurn: number;
  shortestTurn: number;
}

export function calculateReplayStats(replay: {
  events: Array<{ type: string; timestamp: number }>;
  metadata?: { turnCount?: number };
}): ReplayStats {
  const eventTypes: Record<string, number> = {};

  for (const event of replay.events) {
    eventTypes[event.type] = (eventTypes[event.type] || 0) + 1;
  }

  const turnCount = replay.metadata?.turnCount ?? 1;
  const actionEvents = replay.events.filter(e =>
    e.type === 'maneuver' ||
    e.type === 'attack' ||
    e.type === 'play_defense'
  );

  return {
    totalEvents: replay.events.length,
    eventTypes,
    averageActionsPerTurn: actionEvents.length / turnCount,
    longestTurn: 0, // TODO: calculate
    shortestTurn: 0, // TODO: calculate
  };
}
