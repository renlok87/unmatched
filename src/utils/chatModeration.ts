export interface ProfanityFilterConfig {
  customWords?: string[];
  replacementChar?: string;
  strictMode?: boolean;
}

export interface MessageRateLimitConfig {
  maxMessages: number;
  timeWindowMs: number;
}

export interface ReportedMessage {
  id: string;
  messageId: string;
  reportedBy: string;
  reportedUser: string;
  reason: string;
  timestamp: number;
}

const DEFAULT_PROFANE_WORDS = [
  'fuck',
  'shit',
  'ass',
  'bitch',
  'damn',
  'crap',
  'hell',
  'dick',
  'piss',
  'bastard',
];

export class ProfanityFilter {
  private profaneWords: Set<string>;
  private replacementChar: string;

  constructor(config: ProfanityFilterConfig = {}) {
    this.profaneWords = new Set([
      ...DEFAULT_PROFANE_WORDS,
      ...(config.customWords || []),
    ]);
    this.replacementChar = config.replacementChar || '*';
  }

  hasProfanity(text: string): boolean {
    const normalized = text.toLowerCase();
    return Array.from(this.profaneWords).some((word) =>
      normalized.includes(word)
    );
  }

  filterText(text: string): string {
    if (!this.hasProfanity(text)) {
      return text;
    }

    let filtered = text;
    this.profaneWords.forEach((word) => {
      const regex = new RegExp(word, 'gi');
      filtered = filtered.replace(regex, this.replacementChar.repeat(word.length));
    });

    return filtered;
  }

  addProfaneWord(word: string): void {
    this.profaneWords.add(word.toLowerCase());
  }

  removeProfaneWord(word: string): void {
    this.profaneWords.delete(word.toLowerCase());
  }

  isProfaneWord(word: string): boolean {
    return this.profaneWords.has(word.toLowerCase());
  }
}

export class MessageRateLimiter {
  private messages: Map<string, number[]> = new Map();
  private maxMessages: number;
  private timeWindowMs: number;

  constructor(config: MessageRateLimitConfig) {
    this.maxMessages = config.maxMessages;
    this.timeWindowMs = config.timeWindowMs;
  }

  canSendMessage(userId: string): boolean {
    const now = Date.now();
    const userMessages = this.messages.get(userId) || [];

    const recentMessages = userMessages.filter(
      (timestamp) => now - timestamp < this.timeWindowMs
    );

    this.messages.set(userId, recentMessages);

    return recentMessages.length < this.maxMessages;
  }

  recordMessage(userId: string): void {
    const now = Date.now();
    const userMessages = this.messages.get(userId) || [];
    userMessages.push(now);
    this.messages.set(userId, userMessages);
  }

  getRemainingMessages(userId: string): number {
    const now = Date.now();
    const userMessages = this.messages.get(userId) || [];

    const recentMessages = userMessages.filter(
      (timestamp) => now - timestamp < this.timeWindowMs
    );

    return Math.max(0, this.maxMessages - recentMessages.length);
  }

  getResetTime(userId: string): number | null {
    const userMessages = this.messages.get(userId);
    if (!userMessages || userMessages.length === 0) {
      return null;
    }

    const oldestMessage = userMessages[0];
    return oldestMessage + this.timeWindowMs;
  }

  clearUserHistory(userId: string): void {
    this.messages.delete(userId);
  }
}

export class ChatModeration {
  private profanityFilter: ProfanityFilter;
  private rateLimiter: MessageRateLimiter;
  private reportedMessages: ReportedMessage[] = [];
  private ignoredUsers: Set<string> = new Set();

  constructor(
    profanityConfig?: ProfanityFilterConfig,
    rateLimitConfig?: MessageRateLimitConfig
  ) {
    this.profanityFilter = new ProfanityFilter(profanityConfig);
    this.rateLimiter = new MessageRateLimiter(
      rateLimitConfig || {
        maxMessages: 5,
        timeWindowMs: 60000,
      }
    );
  }

  validateMessage(userId: string, content: string): {
    isValid: boolean;
    filteredContent?: string;
    reason?: string;
  } {
    const now = Date.now();

    if (!this.rateLimiter.canSendMessage(userId)) {
      const resetTime = this.rateLimiter.getResetTime(userId);
      const remainingSeconds = resetTime
        ? Math.ceil((resetTime - now) / 1000)
        : 60;

      return {
        isValid: false,
        reason: `Слишком много сообщений. Подождите ${remainingSeconds} сек.`,
      };
    }

    if (this.profanityFilter.hasProfanity(content)) {
      const filteredContent = this.profanityFilter.filterText(content);
      return {
        isValid: true,
        filteredContent,
        reason: 'Сообщение содержит нецензурную лексику',
      };
    }

    return {
      isValid: true,
      filteredContent: content,
    };
  }

  recordMessage(userId: string, content: string): {
    content: string;
    wasFiltered: boolean;
  } {
    this.rateLimiter.recordMessage(userId);

    const wasFiltered = this.profanityFilter.hasProfanity(content);
    const filteredContent = this.profanityFilter.filterText(content);

    return {
      content: filteredContent,
      wasFiltered,
    };
  }

  reportMessage(messageId: string, reporterId: string, reason: string): void {
    const report: ReportedMessage = {
      id: `report-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`,
      messageId,
      reportedBy: reporterId,
      reportedUser: '',
      reason,
      timestamp: Date.now(),
    };

    this.reportedMessages.push(report);
  }

  getReportedMessages(): ReportedMessage[] {
    return [...this.reportedMessages];
  }

  ignoreUser(userId: string): void {
    this.ignoredUsers.add(userId);
  }

  unignoreUser(userId: string): void {
    this.ignoredUsers.delete(userId);
  }

  isUserIgnored(userId: string): boolean {
    return this.ignoredUsers.has(userId);
  }

  getIgnoredUsers(): string[] {
    return Array.from(this.ignoredUsers);
  }

  getProfanityFilter(): ProfanityFilter {
    return this.profanityFilter;
  }

  getRateLimiter(): MessageRateLimiter {
    return this.rateLimiter;
  }
}

export const chatModeration = new ChatModeration();