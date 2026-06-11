# ФАЗЫ 8-13: Remaining Modules

⚠️ **Этот файл разбит на отдельные файлы по каждой фазе.** Смотри папку [`08-13-remaining-modules/`](.claude/tasks/08-13-remaining-modules/)

## Структура фаз

```
08-13-remaining-modules/
├── README.md                      # Навигация
├── 08a.md                         # QueueManagerService
├── 08b.md                         # MatchmakingSchedulerService
├── 08c.md                         # MatchConfirmationService
├── 08d.md                         # GraphQL API
├── 08e.md                         # Edge Cases
├── 08f.md                         # Testing
├── 09.md                          # Presence Module
├── 10a.md                         # Game Action Recording
├── 10b.md                         # Replay Service
├── 10c.md                         # Audit Service
├── 11a.md                         # LeaderboardService
├── 11b.md                         # StatsAggregator
├── 11c.md                         # Leaderboard API
├── 12.md                          # Frontend Integration
└── 13.md                          # Production Readiness
```

## Краткий обзор

### ФАЗА 8: Matchmaking (8A-8F)
- **8A** — Queue Manager (Redis ZSets + PostgreSQL)
- **8B** — Scheduler (BullMQ + distributed lock)
- **8C** — Match Confirmation (two-phase, penalty, ban)
- **8D** — GraphQL API
- **8E** — Edge Cases
- **8F** — Testing

### ФАЗА 9: Presence
PresenceService с Redis TTL + PubSub

### ФАЗА 10: History (10A-10C)
- **10A** — Game Action Recording (async)
- **10B** — Replay Service (gzip)
- **10C** — Audit Service

### ФАЗА 11: Leaderboard (11A-11C)
- **11A** — LeaderboardService (Redis ZSets)
- **11B** — StatsAggregator (ELO)
- **11C** — GraphQL API

### ФАЗЫ 12-13
Frontend + Production

---

## Зависимости

```
8A → 8B → 8C → 8D → 8E → 8F
9 (независимая)
10A → 10B → 10C
11A ← 11B → 11C
```

## Порядок реализации

Последовательно: 8A-8F → 9 → 10A-10C → 11A-11C → 12 → 13

Параллельно (3 команды):
- Команда A: 8A-8F
- Команда B: 9 + 10A-10C
- Команда C: 11A-11C
