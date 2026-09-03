import { Injectable } from '@nestjs/common';
import { ConfigService } from '@nestjs/config';
import * as argon2 from 'argon2';
import { createHmac } from 'node:crypto';

@Injectable()
export class PasswordService {
  private readonly pepper: string;

  constructor(private readonly configService: ConfigService) {
    this.pepper =
      this.configService.getOrThrow<string>('PASSWORD_PEPPER');
  }

  async hash(password: string): Promise<string> {
    const passwordWithPepper = this.applyPepper(password);

    return argon2.hash(passwordWithPepper, {
      type: argon2.argon2id,
      memoryCost: 19_456,
      timeCost: 2,
      parallelism: 1,
      hashLength: 32,
    });
  }

  async verify(
    passwordHash: string,
    password: string,
  ): Promise<boolean> {
    try {
      const passwordWithPepper = this.applyPepper(password);

      return await argon2.verify(
        passwordHash,
        passwordWithPepper,
      );
    } catch {
      return false;
    }
  }

  private applyPepper(password: string): Buffer {
    return createHmac('sha256', this.pepper)
      .update(password, 'utf8')
      .digest();
  }
}