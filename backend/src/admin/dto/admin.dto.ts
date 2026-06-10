import { Field, InputType, Int, ObjectType } from '@nestjs/graphql';
import { IsEmail, IsInt, IsOptional, IsString, MinLength } from 'class-validator';
import { UserRole } from '@prisma/client';

// ============================================
// ADMIN ENTITY DTOs (для детального просмотра)
// ============================================

@ObjectType('AdminCard')
export class AdminCardDto {
  @Field()
  id!: string;

  @Field()
  name!: string;

  @Field()
  nameEn!: string;

  @Field()
  nameRu!: string;

  @Field()
  cardType!: string;

  @Field(() => String, { nullable: true })
  subType?: string;

  @Field(() => Int, { nullable: true })
  attackValue?: number;

  @Field(() => Int, { nullable: true })
  defenseValue?: number;

  @Field(() => Int, { nullable: true })
  boostValue?: number;

  @Field(() => String, { nullable: true })
  bannerName?: string;

  @Field(() => String, { nullable: true })
  effects?: string;

  @Field(() => String, { nullable: true })
  text?: string;

  @Field(() => String, { nullable: true })
  textEn?: string;

  @Field(() => String, { nullable: true })
  textRu?: string;

  @Field(() => String, { nullable: true })
  effectAfter?: string;

  @Field(() => String, { nullable: true })
  effectDuring?: string;

  @Field(() => String, { nullable: true })
  effectBoost?: string;

  @Field(() => String, { nullable: true })
  effectImmediately?: string;

  @Field(() => String, { nullable: true })
  effectOngoing?: string;

  @Field()
  heroId!: string;

  @Field()
  count!: number;

  @Field(() => String, { nullable: true })
  imageUrl?: string;

  @Field(() => String, { nullable: true })
  imageUrlRu?: string;

  @Field()
  createdAt!: Date;

  @Field()
  updatedAt!: Date;
}

@ObjectType('AdminHero')
export class AdminHeroDto {
  @Field()
  id!: string;

  @Field()
  name!: string;

  @Field()
  nameEn!: string;

  @Field()
  nameRu!: string;

  @Field()
  set!: string;

  @Field()
  health!: number;

  @Field()
  fighterType!: string;

  @Field(() => Int, { nullable: true })
  movement?: number;

  @Field(() => String, { nullable: true })
  color?: string;

  @Field(() => String, { nullable: true })
  ability?: string;

  @Field(() => String, { nullable: true })
  deckCards?: string;

  @Field(() => String, { nullable: true })
  properties?: string;

  @Field(() => Boolean, { nullable: true })
  hasTokens?: boolean;

  @Field(() => String, { nullable: true })
  sidekicks?: string;

  @Field(() => String, { nullable: true })
  additionalMinis?: string;

  @Field(() => String, { nullable: true })
  imageUrl?: string;

  @Field(() => String, { nullable: true })
  avatarUrl?: string;

  @Field(() => String, { nullable: true })
  characterCardUrl?: string;

  @Field(() => String, { nullable: true })
  miniModelUrl?: string;

  @Field(() => [AdminCardDto], { nullable: true })
  cards?: AdminCardDto[];

  @Field()
  createdAt!: Date;

  @Field()
  updatedAt!: Date;
}

@ObjectType('AdminBoard')
export class AdminBoardDto {
  @Field()
  id!: string;

  @Field()
  name!: string;

  @Field()
  nameEn!: string;

  @Field()
  nameRu!: string;

  @Field()
  set!: string;

  @Field()
  width!: number;

  @Field()
  height!: number;

  @Field(() => String, { nullable: true })
  cells?: string;

  @Field(() => String, { nullable: true })
  features?: string;

  @Field(() => String, { nullable: true })
  imageUrl?: string;

  @Field(() => String, { nullable: true })
  imageUrlDark?: string;

  @Field()
  createdAt!: Date;

  @Field()
  updatedAt!: Date;
}

// ============================================
// HERO DTOs
// ============================================

@InputType()
export class CreateHeroInput {
  @Field()
  @IsString()
  name: string;

  @Field()
  @IsString()
  nameEn: string;

  @Field()
  @IsString()
  nameRu: string;

  @Field()
  @IsString()
  set: string;

  @Field(() => Int)
  @IsOptional()
  @IsInt()
  health: number;

  @Field()
  @IsString()
  fighterType: string;

  @Field(() => Int, { nullable: true })
  @IsOptional()
  @IsInt()
  movement?: number;

  @Field(() => String, { nullable: true })
  @IsOptional()
  color?: string;

  @Field(() => String, { nullable: true })
  @IsOptional()
  ability?: string;

  @Field(() => String, { nullable: true })
  @IsOptional()
  deckCards?: string;

  @Field(() => String, { nullable: true })
  @IsOptional()
  properties?: string;

  @Field(() => Boolean, { nullable: true })
  @IsOptional()
  hasTokens?: boolean;

  @Field(() => String, { nullable: true })
  @IsOptional()
  sidekicks?: string;

  @Field(() => String, { nullable: true })
  @IsOptional()
  additionalMinis?: string;

  @Field(() => String, { nullable: true })
  @IsOptional()
  imageUrl?: string;

  @Field(() => String, { nullable: true })
  @IsOptional()
  avatarUrl?: string;

  @Field(() => String, { nullable: true })
  @IsOptional()
  characterCardUrl?: string;

  @Field(() => String, { nullable: true })
  @IsOptional()
  miniModelUrl?: string;
}

@InputType()
export class UpdateHeroInput {
  @Field(() => String, { nullable: true })
  @IsOptional()
  @IsString()
  name?: string;

  @Field(() => String, { nullable: true })
  @IsOptional()
  @IsString()
  nameEn?: string;

  @Field(() => String, { nullable: true })
  @IsOptional()
  @IsString()
  nameRu?: string;

  @Field(() => String, { nullable: true })
  @IsOptional()
  @IsString()
  set?: string;

  @Field(() => Int, { nullable: true })
  @IsOptional()
  health?: number;

  @Field(() => String, { nullable: true })
  @IsOptional()
  @IsString()
  fighterType?: string;

  @Field(() => Int, { nullable: true })
  @IsOptional()
  movement?: number;

  @Field(() => String, { nullable: true })
  @IsOptional()
  color?: string;

  @Field(() => String, { nullable: true })
  @IsOptional()
  ability?: string;

  @Field(() => String, { nullable: true })
  @IsOptional()
  deckCards?: string;

  @Field(() => String, { nullable: true })
  @IsOptional()
  properties?: string;

  @Field(() => Boolean, { nullable: true })
  @IsOptional()
  hasTokens?: boolean;

  @Field(() => String, { nullable: true })
  @IsOptional()
  sidekicks?: string;

  @Field(() => String, { nullable: true })
  @IsOptional()
  additionalMinis?: string;

  @Field(() => String, { nullable: true })
  @IsOptional()
  imageUrl?: string;

  @Field(() => String, { nullable: true })
  @IsOptional()
  avatarUrl?: string;

  @Field(() => String, { nullable: true })
  @IsOptional()
  characterCardUrl?: string;

  @Field(() => String, { nullable: true })
  @IsOptional()
  miniModelUrl?: string;
}

// ============================================
// CARD DTOs
// ============================================

@InputType()
export class CreateCardInput {
  @Field()
  @IsString()
  name: string;

  @Field()
  @IsString()
  nameEn: string;

  @Field()
  @IsString()
  nameRu: string;

  @Field()
  @IsString()
  heroId: string;

  @Field()
  @IsString()
  cardType: string;

  @Field(() => String, { nullable: true })
  @IsOptional()
  @IsString()
  subType?: string;

  @Field(() => Int, { nullable: true })
  @IsOptional()
  attackValue?: number;

  @Field(() => Int, { nullable: true })
  @IsOptional()
  defenseValue?: number;

  @Field(() => Int, { nullable: true })
  @IsOptional()
  boostValue?: number;

  @Field(() => String, { nullable: true })
  @IsOptional()
  bannerName?: string;

  @Field(() => String, { nullable: true })
  @IsOptional()
  effects?: string;

  @Field(() => String, { nullable: true })
  @IsOptional()
  text?: string;

  @Field(() => String, { nullable: true })
  @IsOptional()
  textEn?: string;

  @Field(() => String, { nullable: true })
  @IsOptional()
  textRu?: string;

  @Field(() => String, { nullable: true })
  @IsOptional()
  effectAfter?: string;

  @Field(() => String, { nullable: true })
  @IsOptional()
  effectDuring?: string;

  @Field(() => String, { nullable: true })
  @IsOptional()
  effectBoost?: string;

  @Field(() => String, { nullable: true })
  @IsOptional()
  effectImmediately?: string;

  @Field(() => String, { nullable: true })
  @IsOptional()
  effectOngoing?: string;

  @Field(() => Int, { nullable: true })
  @IsOptional()
  count?: number;

  @Field(() => String, { nullable: true })
  @IsOptional()
  @IsString()
  imageUrl?: string;

  @Field(() => String, { nullable: true })
  @IsOptional()
  @IsString()
  imageUrlRu?: string;
}

@InputType()
export class UpdateCardInput {
  @Field(() => String, { nullable: true })
  @IsOptional()
  @IsString()
  heroId?: string;

  @Field(() => String, { nullable: true })
  @IsOptional()
  @IsString()
  name?: string;

  @Field(() => String, { nullable: true })
  @IsOptional()
  @IsString()
  nameEn?: string;

  @Field(() => String, { nullable: true })
  @IsOptional()
  @IsString()
  nameRu?: string;

  @Field(() => String, { nullable: true })
  @IsOptional()
  @IsString()
  cardType?: string;

  @Field(() => String, { nullable: true })
  @IsOptional()
  @IsString()
  subType?: string;

  @Field(() => Int, { nullable: true })
  @IsOptional()
  attackValue?: number;

  @Field(() => Int, { nullable: true })
  @IsOptional()
  defenseValue?: number;

  @Field(() => Int, { nullable: true })
  @IsOptional()
  boostValue?: number;

  @Field(() => String, { nullable: true })
  @IsOptional()
  bannerName?: string;

  @Field(() => String, { nullable: true })
  @IsOptional()
  effects?: string;

  @Field(() => String, { nullable: true })
  @IsOptional()
  text?: string;

  @Field(() => String, { nullable: true })
  @IsOptional()
  textEn?: string;

  @Field(() => String, { nullable: true })
  @IsOptional()
  textRu?: string;

  @Field(() => String, { nullable: true })
  @IsOptional()
  effectAfter?: string;

  @Field(() => String, { nullable: true })
  @IsOptional()
  effectDuring?: string;

  @Field(() => String, { nullable: true })
  @IsOptional()
  effectBoost?: string;

  @Field(() => String, { nullable: true })
  @IsOptional()
  effectImmediately?: string;

  @Field(() => String, { nullable: true })
  @IsOptional()
  effectOngoing?: string;

  @Field(() => Int, { nullable: true })
  @IsOptional()
  count?: number;

  @Field(() => String, { nullable: true })
  @IsOptional()
  @IsString()
  imageUrl?: string;

  @Field(() => String, { nullable: true })
  @IsOptional()
  @IsString()
  imageUrlRu?: string;
}

// ============================================
// BOARD DTOs
// ============================================

@InputType()
export class CreateBoardInput {
  @Field()
  @IsString()
  name: string;

  @Field()
  @IsString()
  nameEn: string;

  @Field()
  @IsString()
  nameRu: string;

  @Field()
  @IsString()
  set: string;

  @Field(() => Int)
  @IsOptional()
  @IsInt()
  width: number;

  @Field(() => Int)
  @IsOptional()
  @IsInt()
  height: number;

  @Field()
  @IsString()
  cells: string;

  @Field(() => String, { nullable: true })
  @IsOptional()
  features?: string;

  @Field(() => String, { nullable: true })
  @IsOptional()
  imageUrl?: string;

  @Field(() => String, { nullable: true })
  @IsOptional()
  imageUrlDark?: string;
}

@InputType()
export class UpdateBoardInput {
  @Field(() => String, { nullable: true })
  @IsOptional()
  @IsString()
  name?: string;

  @Field(() => String, { nullable: true })
  @IsOptional()
  @IsString()
  nameEn?: string;

  @Field(() => String, { nullable: true })
  @IsOptional()
  @IsString()
  nameRu?: string;

  @Field(() => String, { nullable: true })
  @IsOptional()
  @IsString()
  set?: string;

  @Field(() => Int, { nullable: true })
  @IsOptional()
  width?: number;

  @Field(() => Int, { nullable: true })
  @IsOptional()
  height?: number;

  @Field(() => String, { nullable: true })
  @IsOptional()
  cells?: string;

  @Field(() => String, { nullable: true })
  @IsOptional()
  features?: string;

  @Field(() => String, { nullable: true })
  @IsOptional()
  imageUrl?: string;

  @Field(() => String, { nullable: true })
  @IsOptional()
  imageUrlDark?: string;
}

// ============================================
// USER DTOs
// ============================================

@InputType()
export class UpdateUserInput {
  @Field(() => String, { nullable: true })
  @IsOptional()
  @IsString()
  username?: string;

  @Field(() => String, { nullable: true })
  @IsOptional()
  @IsString()
  avatar?: string;

  @Field(() => String, { nullable: true })
  @IsOptional()
  email?: string;

  @Field(() => String, { nullable: true })
  @IsOptional()
  role?: UserRole;
}

@ObjectType()
export class AdminStatsDto {
  @Field()
  totalUsers: number;

  @Field()
  totalHeroes: number;

  @Field()
  totalCards: number;

  @Field()
  totalBoards: number;

  @Field()
  totalGames: number;
}

// ============================================
// IMPORT DTOs
// ============================================

@ObjectType()
export class ImportResultDto {
  @Field()
  success: boolean;

  @Field()
  heroesCreated: number;

  @Field()
  heroesUpdated: number;

  @Field()
  errors: string;
}

// ============================================
// PAGINATED RESPONSE DTOs
// ============================================

@ObjectType()
export class UserStatsDto {
  @Field(() => Int, { nullable: true })
  gamesPlayed?: number;

  @Field(() => Int, { nullable: true })
  gamesWon?: number;

  @Field(() => Int, { nullable: true })
  currentElo?: number;
}

@ObjectType()
export class UserDto {
  @Field()
  id: string;

  @Field()
  username: string;

  @Field()
  email: string;

  @Field(() => String, { nullable: true })
  avatar?: string;

  @Field()
  role: string;

  @Field()
  createdAt: Date;

  @Field()
  updatedAt: Date;

  @Field(() => Date, { nullable: true })
  deletedAt?: Date | null;

  @Field(() => Date, { nullable: true })
  emailVerified?: Date | null;

  @Field(() => UserStatsDto, { nullable: true })
  stats?: UserStatsDto;
}

@ObjectType()
export class UserListItemDto {
  @Field()
  id: string;

  @Field()
  username: string;

  @Field()
  email: string;

  @Field(() => String, { nullable: true })
  avatar?: string;

  @Field()
  role: string;

  @Field()
  createdAt: Date;

  @Field()
  updatedAt: Date;

  @Field(() => Date, { nullable: true })
  deletedAt?: Date | null;

  @Field(() => Date, { nullable: true })
  emailVerified?: Date | null;

  @Field(() => UserStatsDto, { nullable: true })
  stats?: UserStatsDto;
}

@ObjectType()
export class PaginatedUsersDto {
  @Field(() => [UserListItemDto])
  users: UserListItemDto[];

  @Field()
  total: number;

  @Field()
  page: number;

  @Field()
  limit: number;

  @Field()
  totalPages: number;
}

// ============================================
// CARDS LIST DTOs
// ============================================

@ObjectType()
export class CardListItemDto {
  @Field()
  id: string;

  @Field()
  name: string;

  @Field()
  nameEn: string;

  @Field()
  nameRu: string;

  @Field()
  cardType: string;

  @Field(() => String, { nullable: true })
  subType?: string;

  @Field(() => Int, { nullable: true })
  attackValue?: number;

  @Field(() => Int, { nullable: true })
  defenseValue?: number;

  @Field(() => Int, { nullable: true })
  boostValue?: number;

  @Field()
  count: number;

  @Field()
  heroId: string;

  @Field(() => String, { nullable: true })
  imageUrl?: string;

  @Field(() => String, { nullable: true })
  imageUrlRu?: string;

  @Field({ nullable: true })
  createdAt?: Date;
}

@ObjectType()
export class CardsPaginatedDto {
  @Field(() => [CardListItemDto])
  items: CardListItemDto[];

  @Field()
  total: number;

  @Field()
  page: number;

  @Field()
  limit: number;

  @Field()
  totalPages: number;
}

// ============================================
// GAMES LIST DTOs
// ============================================

@ObjectType()
export class GamePlayerInfoDto {
  @Field()
  id: string;

  @Field()
  playerId: string;

  @Field(() => String, { nullable: true })
  heroId?: string;

  @Field()
  status: string;

  @Field(() => String, { nullable: true })
  username?: string;

  @Field(() => String, { nullable: true })
  avatar?: string;
}

@ObjectType()
export class GameListItemDto {
  @Field()
  id: string;

  @Field(() => String, { nullable: true })
  code?: string;

  @Field()
  mode: string;

  @Field()
  status: string;

  @Field()
  createdAt: Date;

  @Field(() => String, { nullable: true })
  boardId?: string;

  @Field(() => String, { nullable: true })
  boardName?: string;

  @Field(() => [GamePlayerInfoDto])
  gamePlayers: GamePlayerInfoDto[];
}

@ObjectType()
export class AdminGameDto {
  @Field()
  id: string;

  @Field(() => String, { nullable: true })
  code?: string;

  @Field()
  mode: string;

  @Field()
  status: string;

  @Field()
  createdAt: Date;

  @Field(() => Date, { nullable: true })
  startedAt?: Date | null;

  @Field(() => Date, { nullable: true })
  finishedAt?: Date | null;

  @Field()
  boardId: string;

  @Field(() => String, { nullable: true })
  boardName?: string;

  @Field(() => [GamePlayerInfoDto])
  gamePlayers: GamePlayerInfoDto[];
}

@ObjectType()
export class GamesPaginatedDto {
  @Field(() => [GameListItemDto])
  items: GameListItemDto[];

  @Field()
  total: number;

  @Field()
  page: number;

  @Field()
  limit: number;

  @Field()
  totalPages: number;
}

// ============================================
// AUDIT LOGS DTOs
// ============================================

@ObjectType()
export class AuditLogDto {
  @Field()
  id: string;

  @Field()
  action: string;

  @Field(() => String, { nullable: true })
  userId?: string;

  @Field(() => String, { nullable: true })
  ipAddress?: string;

  @Field(() => String, { nullable: true })
  userAgent?: string;

  @Field()
  success: boolean;

  @Field(() => String, { nullable: true })
  errorMessage?: string;

  @Field()
  timestamp: Date;

  @Field(() => String, { nullable: true })
  metadata?: string;
}

@ObjectType()
export class AuditLogsPaginatedDto {
  @Field(() => [AuditLogDto])
  items: AuditLogDto[];

  @Field()
  total: number;
}

// ============================================
// MATCHMAKING QUEUE DTOs
// ============================================

@ObjectType()
export class QueuePlayerDto {
  @Field()
  id: string;

  @Field()
  userId: string;

  @Field()
  username: string;

  @Field(() => String, { nullable: true })
  avatar?: string;

  @Field()
  mode: string;

  @Field(() => Int)
  elo: number;

  @Field()
  joinedAt: Date;

  @Field(() => Int)
  position: number;
}

@ObjectType()
export class MatchmakingQueueDto {
  @Field(() => [QueuePlayerDto])
  items: QueuePlayerDto[];

  @Field()
  total: number;

  @Field()
  activeQueues: number;
}

// ============================================
// HEROES LIST DTOs
// ============================================

@ObjectType()
export class HeroListItemDto {
  @Field()
  id: string;

  @Field()
  name: string;

  @Field()
  nameEn: string;

  @Field()
  nameRu: string;

  @Field()
  set: string;

  @Field()
  health: number;

  @Field()
  fighterType: string;

  @Field(() => String, { nullable: true })
  ability?: string;

  @Field(() => String, { nullable: true })
  imageUrl?: string;

  @Field(() => String, { nullable: true })
  avatarUrl?: string;

  @Field()
  createdAt: Date;
}

@ObjectType()
export class HeroesPaginatedDto {
  @Field(() => [HeroListItemDto])
  items: HeroListItemDto[];

  @Field()
  total: number;

  @Field()
  page: number;

  @Field()
  limit: number;

  @Field()
  totalPages: number;
}

// ============================================
// BOARDS LIST DTOs
// ============================================

@ObjectType()
export class BoardListItemDto {
  @Field()
  id: string;

  @Field()
  name: string;

  @Field()
  nameEn: string;

  @Field()
  nameRu: string;

  @Field()
  set: string;

  @Field()
  width: number;

  @Field()
  height: number;

  @Field(() => String, { nullable: true })
  imageUrl?: string;

  @Field(() => String, { nullable: true })
  imageUrlDark?: string;

  @Field()
  createdAt: Date;
}

@ObjectType()
export class BoardsPaginatedDto {
  @Field(() => [BoardListItemDto])
  items: BoardListItemDto[];

  @Field()
  total: number;

  @Field()
  page: number;

  @Field()
  limit: number;

  @Field()
  totalPages: number;
}
