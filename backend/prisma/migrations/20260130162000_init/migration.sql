-- CreateEnum
CREATE TYPE "GameStatus" AS ENUM ('PENDING', 'LOBBY', 'IN_PROGRESS', 'PAUSED', 'FINISHED', 'ABORTED');

-- CreateEnum
CREATE TYPE "GameMode" AS ENUM ('ONE_V_ONE', 'TWO_V_TWO', 'FREE_FOR_ALL', 'VS_AI');

-- CreateEnum
CREATE TYPE "GamePhase" AS ENUM ('SETUP', 'TURN_START', 'ACTION_MANEUVER', 'ACTION_ATTACK', 'COMBAT', 'COMBAT_RESOLVE', 'TURN_END');

-- CreateEnum
CREATE TYPE "GameActionType" AS ENUM ('GAME_CREATED', 'GAME_JOINED', 'GAME_STARTED', 'GAME_ENDED', 'GAME_ABORTED', 'TURN_STARTED', 'TURN_ENDED', 'PASSED', 'CARD_PLAYED', 'CARD_DISCARDED', 'FIGHTER_MOVED', 'MANEUVER', 'PLACED', 'ATTACK_INITIATED', 'DEFENSE_PLAYED', 'COMBAT_RESOLVED', 'EFFECT_APPLIED', 'SPECIAL_ABILITY', 'DOOR_TOGGLED');

-- CreateTable
CREATE TABLE "User" (
    "id" TEXT NOT NULL,
    "email" TEXT NOT NULL,
    "username" TEXT NOT NULL,
    "password" TEXT NOT NULL,
    "avatar" TEXT,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" TIMESTAMP(3) NOT NULL,
    "deletedAt" TIMESTAMP(3),
    "emailVerified" TIMESTAMP(3),
    "emailVerifiedToken" TEXT,
    "passwordResetToken" TEXT,
    "passwordResetExpires" TIMESTAMP(3),

    CONSTRAINT "User_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "UserSettings" (
    "id" TEXT NOT NULL,
    "userId" TEXT NOT NULL,
    "theme" TEXT NOT NULL DEFAULT 'dark',
    "language" TEXT NOT NULL DEFAULT 'ru',
    "soundEnabled" BOOLEAN NOT NULL DEFAULT true,
    "musicEnabled" BOOLEAN NOT NULL DEFAULT true,
    "profileVisible" BOOLEAN NOT NULL DEFAULT true,
    "showOnlineStatus" BOOLEAN NOT NULL DEFAULT true,

    CONSTRAINT "UserSettings_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "UserStats" (
    "id" TEXT NOT NULL,
    "userId" TEXT NOT NULL,
    "gamesPlayed" INTEGER NOT NULL DEFAULT 0,
    "gamesWon" INTEGER NOT NULL DEFAULT 0,
    "gamesLost" INTEGER NOT NULL DEFAULT 0,
    "winRate" DOUBLE PRECISION NOT NULL DEFAULT 0,
    "currentElo" INTEGER NOT NULL DEFAULT 1200,
    "peakElo" INTEGER NOT NULL DEFAULT 1200,
    "heroStats" JSONB NOT NULL DEFAULT '{}',
    "lastPlayedAt" TIMESTAMP(3),
    "totalPlayTime" INTEGER NOT NULL DEFAULT 0,

    CONSTRAINT "UserStats_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "RefreshToken" (
    "id" TEXT NOT NULL,
    "token" TEXT NOT NULL,
    "userId" TEXT NOT NULL,
    "expiresAt" TIMESTAMP(3) NOT NULL,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "revokedAt" TIMESTAMP(3),
    "replacedBy" TEXT,

    CONSTRAINT "RefreshToken_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "Session" (
    "id" TEXT NOT NULL,
    "userId" TEXT NOT NULL,
    "deviceId" TEXT,
    "deviceName" TEXT,
    "ipAddress" TEXT,
    "refreshToken" TEXT NOT NULL,
    "expiresAt" TIMESTAMP(3) NOT NULL,
    "lastSeenAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "Session_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "AuthAuditLog" (
    "id" TEXT NOT NULL,
    "userId" TEXT,
    "action" TEXT NOT NULL,
    "success" BOOLEAN NOT NULL,
    "ipAddress" TEXT,
    "userAgent" TEXT,
    "errorMessage" TEXT,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "AuthAuditLog_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "Game" (
    "id" TEXT NOT NULL,
    "status" "GameStatus" NOT NULL DEFAULT 'PENDING',
    "mode" "GameMode" NOT NULL DEFAULT 'ONE_V_ONE',
    "hostId" TEXT NOT NULL,
    "opponentId" TEXT,
    "boardId" TEXT NOT NULL,
    "boardState" JSONB,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" TIMESTAMP(3) NOT NULL,
    "startedAt" TIMESTAMP(3),
    "endedAt" TIMESTAMP(3),
    "deletedAt" TIMESTAMP(3),
    "winnerId" TEXT,
    "version" INTEGER NOT NULL DEFAULT 0,

    CONSTRAINT "Game_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "GamePlayer" (
    "id" TEXT NOT NULL,
    "gameId" TEXT NOT NULL,
    "userId" TEXT NOT NULL,
    "heroId" TEXT,
    "isReady" BOOLEAN NOT NULL DEFAULT false,
    "hasPassed" BOOLEAN NOT NULL DEFAULT false,
    "seatOrder" INTEGER NOT NULL DEFAULT 0,

    CONSTRAINT "GamePlayer_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "GameState" (
    "id" TEXT NOT NULL,
    "gameId" TEXT NOT NULL,
    "state" JSONB NOT NULL,
    "sequenceNumber" INTEGER NOT NULL DEFAULT 0,
    "currentTurnPlayerId" TEXT,
    "phase" TEXT NOT NULL DEFAULT 'SETUP',
    "turnCount" INTEGER NOT NULL DEFAULT 0,
    "updatedAt" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "GameState_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "GameStateHistory" (
    "id" TEXT NOT NULL,
    "gameId" TEXT NOT NULL,
    "state" JSONB NOT NULL,
    "sequenceNumber" INTEGER NOT NULL,
    "actionType" TEXT NOT NULL,
    "playerId" TEXT,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "GameStateHistory_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "GameStateSnapshot" (
    "id" TEXT NOT NULL,
    "gameId" TEXT NOT NULL,
    "sequence" INTEGER NOT NULL,
    "fullState" JSONB NOT NULL,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "GameStateSnapshot_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "GameAction" (
    "id" TEXT NOT NULL,
    "gameId" TEXT NOT NULL,
    "type" "GameActionType" NOT NULL,
    "sequenceNumber" INTEGER NOT NULL,
    "playerId" TEXT,
    "payload" JSONB NOT NULL,
    "previousStateId" TEXT,
    "newStateId" TEXT,
    "timestamp" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "GameAction_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "Hero" (
    "id" TEXT NOT NULL,
    "name" TEXT NOT NULL,
    "nameEn" TEXT NOT NULL,
    "nameRu" TEXT NOT NULL,
    "set" TEXT NOT NULL,
    "health" INTEGER NOT NULL,
    "fighterType" TEXT NOT NULL,
    "ability" JSONB NOT NULL,
    "deckCards" JSONB NOT NULL,
    "properties" JSONB,
    "imageUrl" TEXT,
    "avatarUrl" TEXT,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "Hero_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "Card" (
    "id" TEXT NOT NULL,
    "name" TEXT NOT NULL,
    "nameEn" TEXT NOT NULL,
    "nameRu" TEXT NOT NULL,
    "cardType" TEXT NOT NULL,
    "subType" TEXT,
    "attackValue" INTEGER,
    "defenseValue" INTEGER,
    "boostValue" INTEGER,
    "effects" JSONB NOT NULL,
    "text" TEXT,
    "textEn" TEXT,
    "textRu" TEXT,
    "heroId" TEXT NOT NULL,
    "count" INTEGER NOT NULL DEFAULT 1,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "Card_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "Board" (
    "id" TEXT NOT NULL,
    "name" TEXT NOT NULL,
    "nameEn" TEXT NOT NULL,
    "nameRu" TEXT NOT NULL,
    "set" TEXT NOT NULL,
    "width" INTEGER NOT NULL,
    "height" INTEGER NOT NULL,
    "cells" JSONB NOT NULL,
    "features" JSONB,
    "imageUrl" TEXT,
    "imageUrlDark" TEXT,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "Board_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "MatchmakingQueueEntry" (
    "id" TEXT NOT NULL,
    "userId" TEXT NOT NULL,
    "mode" "GameMode" NOT NULL,
    "heroPref" TEXT,
    "rating" INTEGER NOT NULL,
    "joinedAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "MatchmakingQueueEntry_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "LeaderboardEntry" (
    "id" TEXT NOT NULL,
    "userId" TEXT NOT NULL,
    "heroId" TEXT,
    "timeFrame" TEXT NOT NULL DEFAULT 'all',
    "rank" INTEGER NOT NULL,
    "elo" INTEGER NOT NULL,
    "gamesWon" INTEGER NOT NULL,
    "gamesPlayed" INTEGER NOT NULL,
    "updatedAt" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "LeaderboardEntry_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "Presence" (
    "userId" TEXT NOT NULL,
    "status" TEXT NOT NULL DEFAULT 'offline',
    "lastSeenAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "currentGameId" TEXT,

    CONSTRAINT "Presence_pkey" PRIMARY KEY ("userId")
);

-- CreateIndex
CREATE UNIQUE INDEX "User_email_key" ON "User"("email");

-- CreateIndex
CREATE UNIQUE INDEX "User_username_key" ON "User"("username");

-- CreateIndex
CREATE UNIQUE INDEX "User_emailVerifiedToken_key" ON "User"("emailVerifiedToken");

-- CreateIndex
CREATE UNIQUE INDEX "User_passwordResetToken_key" ON "User"("passwordResetToken");

-- CreateIndex
CREATE INDEX "User_email_idx" ON "User"("email");

-- CreateIndex
CREATE INDEX "User_username_idx" ON "User"("username");

-- CreateIndex
CREATE INDEX "User_deletedAt_idx" ON "User"("deletedAt");

-- CreateIndex
CREATE UNIQUE INDEX "UserSettings_userId_key" ON "UserSettings"("userId");

-- CreateIndex
CREATE UNIQUE INDEX "UserStats_userId_key" ON "UserStats"("userId");

-- CreateIndex
CREATE INDEX "UserStats_currentElo_idx" ON "UserStats"("currentElo" DESC);

-- CreateIndex
CREATE INDEX "UserStats_gamesWon_idx" ON "UserStats"("gamesWon" DESC);

-- CreateIndex
CREATE INDEX "UserStats_lastPlayedAt_idx" ON "UserStats"("lastPlayedAt");

-- CreateIndex
CREATE UNIQUE INDEX "RefreshToken_token_key" ON "RefreshToken"("token");

-- CreateIndex
CREATE INDEX "RefreshToken_userId_idx" ON "RefreshToken"("userId");

-- CreateIndex
CREATE INDEX "RefreshToken_token_idx" ON "RefreshToken"("token");

-- CreateIndex
CREATE INDEX "RefreshToken_expiresAt_idx" ON "RefreshToken"("expiresAt");

-- CreateIndex
CREATE UNIQUE INDEX "Session_refreshToken_key" ON "Session"("refreshToken");

-- CreateIndex
CREATE INDEX "Session_userId_idx" ON "Session"("userId");

-- CreateIndex
CREATE INDEX "Session_expiresAt_idx" ON "Session"("expiresAt");

-- CreateIndex
CREATE INDEX "AuthAuditLog_userId_idx" ON "AuthAuditLog"("userId");

-- CreateIndex
CREATE INDEX "AuthAuditLog_action_idx" ON "AuthAuditLog"("action");

-- CreateIndex
CREATE INDEX "AuthAuditLog_createdAt_idx" ON "AuthAuditLog"("createdAt");

-- CreateIndex
CREATE INDEX "Game_status_idx" ON "Game"("status");

-- CreateIndex
CREATE INDEX "Game_hostId_idx" ON "Game"("hostId");

-- CreateIndex
CREATE INDEX "Game_hostId_status_idx" ON "Game"("hostId", "status");

-- CreateIndex
CREATE INDEX "Game_opponentId_status_idx" ON "Game"("opponentId", "status");

-- CreateIndex
CREATE INDEX "Game_createdAt_idx" ON "Game"("createdAt");

-- CreateIndex
CREATE INDEX "Game_status_createdAt_idx" ON "Game"("status", "createdAt");

-- CreateIndex
CREATE INDEX "Game_mode_status_idx" ON "Game"("mode", "status");

-- CreateIndex
CREATE INDEX "Game_winnerId_idx" ON "Game"("winnerId");

-- CreateIndex
CREATE INDEX "Game_updatedAt_idx" ON "Game"("updatedAt");

-- CreateIndex
CREATE INDEX "Game_deletedAt_idx" ON "Game"("deletedAt");

-- CreateIndex
CREATE INDEX "Game_mode_status_createdAt_idx" ON "Game"("mode", "status", "createdAt");

-- CreateIndex
CREATE INDEX "GamePlayer_gameId_idx" ON "GamePlayer"("gameId");

-- CreateIndex
CREATE INDEX "GamePlayer_gameId_isReady_idx" ON "GamePlayer"("gameId", "isReady");

-- CreateIndex
CREATE INDEX "GamePlayer_userId_idx" ON "GamePlayer"("userId");

-- CreateIndex
CREATE UNIQUE INDEX "GamePlayer_gameId_userId_key" ON "GamePlayer"("gameId", "userId");

-- CreateIndex
CREATE UNIQUE INDEX "GameState_gameId_key" ON "GameState"("gameId");

-- CreateIndex
CREATE INDEX "GameState_gameId_idx" ON "GameState"("gameId");

-- CreateIndex
CREATE INDEX "GameState_sequenceNumber_idx" ON "GameState"("sequenceNumber");

-- CreateIndex
CREATE INDEX "GameStateHistory_gameId_sequenceNumber_idx" ON "GameStateHistory"("gameId", "sequenceNumber");

-- CreateIndex
CREATE INDEX "GameStateHistory_gameId_createdAt_idx" ON "GameStateHistory"("gameId", "createdAt");

-- CreateIndex
CREATE INDEX "GameStateSnapshot_gameId_idx" ON "GameStateSnapshot"("gameId");

-- CreateIndex
CREATE INDEX "GameStateSnapshot_gameId_createdAt_idx" ON "GameStateSnapshot"("gameId", "createdAt");

-- CreateIndex
CREATE UNIQUE INDEX "GameStateSnapshot_gameId_sequence_key" ON "GameStateSnapshot"("gameId", "sequence");

-- CreateIndex
CREATE INDEX "GameAction_gameId_sequenceNumber_idx" ON "GameAction"("gameId", "sequenceNumber");

-- CreateIndex
CREATE INDEX "GameAction_gameId_timestamp_idx" ON "GameAction"("gameId", "timestamp");

-- CreateIndex
CREATE INDEX "GameAction_gameId_type_sequenceNumber_idx" ON "GameAction"("gameId", "type", "sequenceNumber");

-- CreateIndex
CREATE INDEX "GameAction_playerId_timestamp_idx" ON "GameAction"("playerId", "timestamp");

-- CreateIndex
CREATE INDEX "GameAction_timestamp_idx" ON "GameAction"("timestamp");

-- CreateIndex
CREATE UNIQUE INDEX "Hero_name_key" ON "Hero"("name");

-- CreateIndex
CREATE INDEX "Hero_set_idx" ON "Hero"("set");

-- CreateIndex
CREATE INDEX "Card_heroId_idx" ON "Card"("heroId");

-- CreateIndex
CREATE INDEX "Card_cardType_idx" ON "Card"("cardType");

-- CreateIndex
CREATE UNIQUE INDEX "Board_name_key" ON "Board"("name");

-- CreateIndex
CREATE INDEX "Board_set_idx" ON "Board"("set");

-- CreateIndex
CREATE UNIQUE INDEX "MatchmakingQueueEntry_userId_key" ON "MatchmakingQueueEntry"("userId");

-- CreateIndex
CREATE INDEX "MatchmakingQueueEntry_mode_rating_idx" ON "MatchmakingQueueEntry"("mode", "rating");

-- CreateIndex
CREATE INDEX "MatchmakingQueueEntry_joinedAt_idx" ON "MatchmakingQueueEntry"("joinedAt");

-- CreateIndex
CREATE INDEX "LeaderboardEntry_heroId_timeFrame_elo_idx" ON "LeaderboardEntry"("heroId", "timeFrame", "elo");

-- CreateIndex
CREATE UNIQUE INDEX "LeaderboardEntry_userId_heroId_timeFrame_key" ON "LeaderboardEntry"("userId", "heroId", "timeFrame");

-- CreateIndex
CREATE INDEX "Presence_status_idx" ON "Presence"("status");

-- AddForeignKey
ALTER TABLE "UserSettings" ADD CONSTRAINT "UserSettings_userId_fkey" FOREIGN KEY ("userId") REFERENCES "User"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "UserStats" ADD CONSTRAINT "UserStats_userId_fkey" FOREIGN KEY ("userId") REFERENCES "User"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "RefreshToken" ADD CONSTRAINT "RefreshToken_userId_fkey" FOREIGN KEY ("userId") REFERENCES "User"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "Session" ADD CONSTRAINT "Session_userId_fkey" FOREIGN KEY ("userId") REFERENCES "User"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "AuthAuditLog" ADD CONSTRAINT "AuthAuditLog_userId_fkey" FOREIGN KEY ("userId") REFERENCES "User"("id") ON DELETE SET NULL ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "Game" ADD CONSTRAINT "Game_hostId_fkey" FOREIGN KEY ("hostId") REFERENCES "User"("id") ON DELETE RESTRICT ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "Game" ADD CONSTRAINT "Game_opponentId_fkey" FOREIGN KEY ("opponentId") REFERENCES "User"("id") ON DELETE SET NULL ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "GamePlayer" ADD CONSTRAINT "GamePlayer_gameId_fkey" FOREIGN KEY ("gameId") REFERENCES "Game"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "GamePlayer" ADD CONSTRAINT "GamePlayer_userId_fkey" FOREIGN KEY ("userId") REFERENCES "User"("id") ON DELETE RESTRICT ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "GameState" ADD CONSTRAINT "GameState_gameId_fkey" FOREIGN KEY ("gameId") REFERENCES "Game"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "GameStateHistory" ADD CONSTRAINT "GameStateHistory_gameId_fkey" FOREIGN KEY ("gameId") REFERENCES "Game"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "GameStateSnapshot" ADD CONSTRAINT "GameStateSnapshot_gameId_fkey" FOREIGN KEY ("gameId") REFERENCES "Game"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "GameAction" ADD CONSTRAINT "GameAction_gameId_fkey" FOREIGN KEY ("gameId") REFERENCES "Game"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "Card" ADD CONSTRAINT "Card_heroId_fkey" FOREIGN KEY ("heroId") REFERENCES "Hero"("id") ON DELETE RESTRICT ON UPDATE CASCADE;
