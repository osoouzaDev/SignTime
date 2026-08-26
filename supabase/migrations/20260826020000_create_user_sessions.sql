begin;

create table if not exists private.user_sessions (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references private.users(id) on delete cascade,
  token_hash char(64) not null unique,
  csrf_token_hash char(64) not null,
  created_at timestamptz not null default now(),
  last_seen_at timestamptz not null default now(),
  expires_at timestamptz not null,
  revoked_at timestamptz,
  constraint user_sessions_expiration_valid check (expires_at > created_at)
);

create index if not exists user_sessions_user_id_idx
  on private.user_sessions (user_id);

create index if not exists user_sessions_expires_at_idx
  on private.user_sessions (expires_at)
  where revoked_at is null;

comment on table private.user_sessions is
  'Sessões web do SignTime. Apenas hashes dos tokens são armazenados.';

revoke all on table private.user_sessions from public, anon, authenticated;

commit;
