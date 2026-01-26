import { Field, InputType, ObjectType, Int, registerEnumType } from '@nestjs/graphql';
import { IsOptional, IsString, IsEnum, IsInt, Min, Max } from 'class-validator';

export enum TimeFrame {
  ALL = 'all',
  WEEK = 'week',
  MONTH = 'month',
}

// Регистрируем enum для GraphQL
registerEnumType(TimeFrame, {
  name: 'TimeFrame',
  description: 'Временной период для статистики',
});

@InputType()
export class LeaderboardOptionsDto {
  @Field({ nullable: true })
  @IsOptional()
  @IsString()
  heroId?: string;

  @Field(() => TimeFrame, { nullable: true })
  @IsOptional()
  @IsEnum(TimeFrame)
  timeFrame?: TimeFrame;

  @Field(() => Int, { nullable: true })
  @IsOptional()
  @IsInt()
  @Min(1)
  @Max(100)
  limit?: number;
}

@ObjectType()
export class LeaderboardEntryResponse {
  @Field(() => Int)
  rank: number;

  @Field()
  user: {
    id: string;
    username: string;
    avatar: string | null;
  };

  @Field(() => Int)
  elo: number;

  @Field(() => Int)
  gamesWon: number;

  @Field(() => Int)
  gamesPlayed: number;
}

@ObjectType()
export class UserStatsResponse {
  @Field()
  userId: string;

  @Field(() => Int)
  gamesPlayed: number;

  @Field(() => Int)
  gamesWon: number;

  @Field(() => Int)
  gamesLost: number;

  @Field()
  winRate: number;

  @Field(() => Int)
  currentElo: number;

  @Field(() => Int)
  peakElo: number;

  @Field({ nullable: true })
  lastPlayedAt: Date | null;

  @Field(() => Int)
  totalPlayTime: number;

  @Field({ nullable: true })
  favoriteHero: {
    id: string;
    name: string;
    nameEn: string;
    nameRu: string;
  } | null;
}
