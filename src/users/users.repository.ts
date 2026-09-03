import { Injectable } from '@nestjs/common';
import { DatabaseService } from '../database/database.service';
import { User, UserRole } from './entities/user.entity';

interface UserRow {
  id: string;
  name: string;
  email: string;
  password_hash: string;
  role: UserRole;
  active: boolean;
  created_at: Date;
  updated_at: Date;
}

@Injectable()
export class UsersRepository {
  constructor(private readonly database: DatabaseService) {}

  async findByEmail(email: string): Promise<User | null> {
    const result = await this.database.query<UserRow>(
      `
        SELECT
          id,
          name,
          email,
          password_hash,
          role,
          active,
          created_at,
          updated_at
        FROM users
        WHERE LOWER(email) = LOWER($1)
        LIMIT 1
      `,
      [email.trim()],
    );

    const row = result.rows[0];

    return row ? this.mapRow(row) : null;
  }

  async findById(id: string): Promise<User | null> {
    const result = await this.database.query<UserRow>(
      `
        SELECT
          id,
          name,
          email,
          password_hash,
          role,
          active,
          created_at,
          updated_at
        FROM users
        WHERE id = $1
        LIMIT 1
      `,
      [id],
    );

    const row = result.rows[0];

    return row ? this.mapRow(row) : null;
  }

  async create(data: {
    name: string;
    email: string;
    passwordHash: string;
  }): Promise<User> {
    const result = await this.database.query<UserRow>(
      `
        INSERT INTO users (
          name,
          email,
          password_hash
        )
        VALUES ($1, LOWER($2), $3)
        RETURNING
          id,
          name,
          email,
          password_hash,
          role,
          active,
          created_at,
          updated_at
      `,
      [
        data.name.trim(),
        data.email.trim(),
        data.passwordHash,
      ],
    );

    return this.mapRow(result.rows[0]);
  }

  private mapRow(row: UserRow): User {
    return {
      id: row.id,
      name: row.name,
      email: row.email,
      passwordHash: row.password_hash,
      role: row.role,
      active: row.active,
      createdAt: row.created_at,
      updatedAt: row.updated_at,
    };
  }
}
