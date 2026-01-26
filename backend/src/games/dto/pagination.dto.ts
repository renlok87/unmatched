import { Field, InputType, ObjectType, Int, registerEnumType } from '@nestjs/graphql';
import { IsOptional, IsString, IsInt, Min } from 'class-validator';
import { GameResponse } from '../models/game.model';

export enum PaginationOrder {
  ASC = 'asc',
  DESC = 'desc',
}

registerEnumType(PaginationOrder, {
  name: 'PaginationOrder',
});

@ObjectType()
export class PageInfo {
  @Field(() => Boolean)
  hasNextPage: boolean;

  @Field(() => Boolean)
  hasPreviousPage: boolean;

  @Field(() => String, { nullable: true })
  startCursor?: string;

  @Field(() => String, { nullable: true })
  endCursor?: string;

  @Field()
  totalCount: number;
}

@ObjectType()
export class GameEdge {
  @Field()
  cursor: string;

  @Field(() => GameResponse, { nullable: true })
  node?: GameResponse;
}

@ObjectType()
export class GameConnection {
  @Field(() => [GameEdge])
  edges: GameEdge[];

  @Field(() => PageInfo)
  pageInfo: PageInfo;
}

@InputType()
export class PaginationDto {
  @Field({ nullable: true })
  @IsOptional()
  @IsString()
  after?: string;

  @Field({ nullable: true })
  @IsOptional()
  @IsString()
  before?: string;

  @Field(() => Int, { nullable: true })
  @IsOptional()
  @IsInt()
  @Min(1)
  first?: number;

  @Field(() => Int, { nullable: true })
  @IsOptional()
  @IsInt()
  @Min(1)
  last?: number;
}
