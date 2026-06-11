# ФАЗЫ 8-13: Remaining Modules

## Структура фаз

- **08a-matchmaking-queue.md** - QueueManagerService (Redis ZSets + PostgreSQL)
- **08b-matchmaking-scheduler.md** - MatchmakingSchedulerService (BullMQ + distributed lock)
- **08c-matchmaking-confirmation.md** - MatchConfirmationService (two-phase, penalty, ban)
- **08d-matchmaking-api.md** - GraphQL API Integration
- **08e-matchmaking-edge-cases.md** - Edge Cases
- **08f-matchmaking-testing.md** - Testing Strategy
- **09-presence.md** - Presence Module
- **10a-history-recording.md** - Game Action Recording (async BullMQ)
- **10b-history-replay.md** - Replay Service (compressed)
- **10c-history-audit.md** - Audit Service
- **11a-leaderboard-service.md** - LeaderboardService (Redis ZSets + fallback)
- **11b-leaderboard-stats.md** - StatsAggregator (ELO calculation)
- **11c-leaderboard-api.md** - Leaderboard API
- **12-frontend.md** - Frontend Integration
- **13-production.md** - Production Readiness

## Порядок реализации

1. Фаза 8A → 8B → 8C → 8D → 8E → 8F (Matchmaking)
2. Фаза 9 (Presence — параллельно с 8)
3. Фаза 10A → 10B → 10C (History)
4. Фаза 11A → 11B → 11C (Leaderboard)
5. Фаза 12 (Frontend)
6. Фаза 13 (Production)
