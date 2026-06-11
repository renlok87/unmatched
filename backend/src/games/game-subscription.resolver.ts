/**
 * Game Subscription Resolver
 *
 * GraphQL подписки для обновлений игры в реальном времени.
 */

import { Resolver, Args, Subscription } from '@nestjs/graphql';
import { GameSubscriptionService } from './game-subscription.service';
import { GameStateResponse } from './models';

@Resolver(() => GameStateResponse)
export class GameSubscriptionResolver {
  constructor(private readonly subscriptionService: GameSubscriptionService) {}

  /**
   * Подписка на обновления игры
   */
  @Subscription(() => GameStateResponse, {
    name: 'gameUpdates',
    filter: (payload: any, variables: any) => {
      return payload.gameId === variables.gameId;
    },
  })
  gameUpdates(@Args('gameId') gameId: string): any {
    return this.subscriptionService.subscribeToGame(gameId, '', (state) => state);
  }
}
