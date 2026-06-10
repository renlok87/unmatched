import { Injectable, Logger } from '@nestjs/common';

export interface MatchmakingMetrics {
  totalJoins: number;
  totalLeaves: number;
  totalMatchesCreated: number;
  totalMatchesAccepted: number;
  totalMatchesDeclined: number;
  totalMatchesTimeout: number;
  currentQueueSizes: Record<string, number>;
  averageWaitTime: number;
  metricsResetAt: Date;
}

@Injectable()
export class MatchmakingMetricsService {
  private readonly logger = new Logger(MatchmakingMetricsService.name);

  private metrics: MatchmakingMetrics = {
    totalJoins: 0,
    totalLeaves: 0,
    totalMatchesCreated: 0,
    totalMatchesAccepted: 0,
    totalMatchesDeclined: 0,
    totalMatchesTimeout: 0,
    currentQueueSizes: {},
    averageWaitTime: 0,
    metricsResetAt: new Date(),
  };

  private waitTimes: number[] = [];

  recordJoin(mode: string): void {
    this.metrics.totalJoins++;
    this.logger.debug(`Metrics: joinQueue called (mode: ${mode})`);
  }

  recordLeave(mode: string): void {
    this.metrics.totalLeaves++;
    this.logger.debug(`Metrics: leaveQueue called (mode: ${mode})`);
  }

  recordMatchCreated(mode: string, waitTimeMs: number): void {
    this.metrics.totalMatchesCreated++;
    this.waitTimes.push(waitTimeMs);

    if (this.waitTimes.length > 1000) {
      this.waitTimes = this.waitTimes.slice(-1000);
    }

    this.metrics.averageWaitTime =
      this.waitTimes.reduce((sum, time) => sum + time, 0) / this.waitTimes.length;

    this.logger.debug(`Metrics: match created (mode: ${mode}, waitTime: ${waitTimeMs}ms)`);
  }

  recordMatchAccepted(gameId: string): void {
    this.metrics.totalMatchesAccepted++;
    this.logger.debug(`Metrics: match accepted (gameId: ${gameId})`);
  }

  recordMatchDeclined(gameId: string): void {
    this.metrics.totalMatchesDeclined++;
    this.logger.debug(`Metrics: match declined (gameId: ${gameId})`);
  }

  recordMatchTimeout(gameId: string): void {
    this.metrics.totalMatchesTimeout++;
    this.logger.debug(`Metrics: match timeout (gameId: ${gameId})`);
  }

  updateQueueSizes(queueSizes: Record<string, number>): void {
    this.metrics.currentQueueSizes = queueSizes;
  }

  getMetrics(): MatchmakingMetrics {
    return { ...this.metrics };
  }

  resetMetrics(): void {
    this.metrics = {
      totalJoins: 0,
      totalLeaves: 0,
      totalMatchesCreated: 0,
      totalMatchesAccepted: 0,
      totalMatchesDeclined: 0,
      totalMatchesTimeout: 0,
      currentQueueSizes: {},
      averageWaitTime: 0,
      metricsResetAt: new Date(),
    };
    this.waitTimes = [];
    this.logger.log('Metrics reset');
  }
}
