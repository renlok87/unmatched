import { Injectable, Logger } from '@nestjs/common';
import { promisify } from 'util';
import { gzip, gunzip } from 'zlib';

const gzipAsync = promisify(gzip);
const gunzipAsync = promisify(gunzip);

@Injectable()
export class ReplayCompressorService {
  private readonly logger = new Logger(ReplayCompressorService.name);

  async compress(data: string): Promise<Buffer> {
    try {
      const compressed = await gzipAsync(data);
      this.logger.debug(
        `Compressed data: ${data.length} bytes -> ${compressed.length} bytes (${Math.round((compressed.length / data.length) * 100)}%)`,
      );
      return compressed;
    } catch (error) {
      this.logger.error(`Failed to compress data: ${error.message}`);
      throw error;
    }
  }

  async decompress(data: Buffer): Promise<string> {
    try {
      const decompressed = await gunzipAsync(data);
      return decompressed.toString('utf-8');
    } catch (error) {
      this.logger.error(`Failed to decompress data: ${error.message}`);
      throw error;
    }
  }
}
