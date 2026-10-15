import { Field, Int, ObjectType, Query, Resolver } from '@nestjs/graphql';
import { Public } from '../common/decorators';
import { SERVER_PROTOCOL } from './protocol';

@ObjectType('ServerInfo')
export class ServerInfoDto {
  @Field(() => Int, { description: 'Client <-> server protocol number (GD-053)' })
  protocol!: number;
}

/** GD-053: what the Unreal client checks before the lobby - a public query, no session needed. */
@Resolver(() => ServerInfoDto)
export class ServerInfoResolver {
  @Query(() => ServerInfoDto, { name: 'serverInfo' })
  @Public()
  serverInfo(): ServerInfoDto {
    return { protocol: SERVER_PROTOCOL };
  }
}
