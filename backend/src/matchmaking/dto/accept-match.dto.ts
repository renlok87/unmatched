import { Field, ArgsType } from '@nestjs/graphql';
import { IsString } from 'class-validator';

@ArgsType()
export class AcceptMatchDto {
  @Field(() => String)
  @IsString()
  gameId: string;
}
