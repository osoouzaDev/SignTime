import {
  Injectable,
  OnApplicationShutdown,
  OnModuleInit,
} from '@nestjs/common';
import { ConfigService } from '@nestjs/config';
import { Pool, PoolClient, QueryResult, QueryResultRow } from 'pg';

@Injectable()
export class DatabaseService
  implements OnModuleInit, OnApplicationShutdown
{
  private readonly pool: Pool;

  constructor(private readonly configService: ConfigService) {
    const connectionString =
      this.configService.getOrThrow<string>('DATABASE_URL');

    this.pool = new Pool({
      connectionString,
      ssl: {
        rejectUnauthorized: false,
      },
      max: 10,
      idleTimeoutMillis: 30_000,
      connectionTimeoutMillis: 10_000,
    });
  }

  async onModuleInit(): Promise<void> {
    await this.pool.query('SELECT 1');
    console.log('Conectado ao Neon PostgreSQL.');
  }

  async query<T extends QueryResultRow>(
    text: string,
    values: unknown[] = [],
  ): Promise<QueryResult<T>> {
    return this.pool.query<T>(text, values);
  }

  async getClient(): Promise<PoolClient> {
    return this.pool.connect();
  }

  async onApplicationShutdown(): Promise<void> {
    await this.pool.end();
  }
}