import { Module } from '@nestjs/common';
import { RedisModule } from '../redis';
import { PrismaModule } from '../database';
import { ContentService } from './content.service';
import { ContentDbService } from './content-db.service';
import {
  ContentResolver,
  HeroResolver,
  CardResolver,
  BoardResolver,
  BoardSpaceResolver,
} from './content.resolver';
import { ContentMapper } from './mappers/content.mapper';

@Module({
  imports: [RedisModule, PrismaModule],
  providers: [
    ContentService,
    ContentDbService,
    ContentMapper,
    ContentResolver,
    HeroResolver,
    CardResolver,
    BoardResolver,
    BoardSpaceResolver,
  ],
  exports: [ContentService, ContentDbService, ContentMapper],
})
export class ContentModule {}
