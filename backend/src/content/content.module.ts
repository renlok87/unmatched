import { Module } from '@nestjs/common';
import { RedisModule } from '../redis';
import { ContentService } from './content.service';
import { ContentResolver, HeroResolver, CardResolver, BoardResolver, BoardSpaceResolver } from './content.resolver';
import { ContentMapper } from './mappers/content.mapper';

@Module({
  imports: [RedisModule],
  providers: [
    ContentService,
    ContentMapper,
    ContentResolver,
    HeroResolver,
    CardResolver,
    BoardResolver,
    BoardSpaceResolver,
  ],
  exports: [ContentService, ContentMapper],
})
export class ContentModule {}
