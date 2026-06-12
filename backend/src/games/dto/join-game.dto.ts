import { Field, InputType } from '@nestjs/graphql';
import { IsString, IsNotEmpty, IsOptional, IsBoolean } from 'class-validator';

@InputType()
export class JoinGameDto {
  // ID — Prisma cuid, не UUID, поэтому валидируем только наличие
  @Field()
  @IsString()
  @IsNotEmpty()
  gameId: string;

  @Field({ nullable: true })
  @IsOptional()
  @IsString()
  heroId?: string;

  @Field({ nullable: true })
  @IsOptional()
  @IsBoolean()
  asOpponent?: boolean;
}
