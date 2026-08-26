begin;

create schema if not exists private;

comment on schema private is
  'Dados internos do SignTime que não devem ser expostos pela Data API.';

revoke all on schema private from public, anon, authenticated;

create table if not exists private.users (
  id uuid primary key default gen_random_uuid(),
  username varchar(80) not null,
  email varchar(320),
  full_name varchar(160) not null,
  password_hash text not null,
  role varchar(20) not null default 'user',
  is_active boolean not null default true,
  failed_login_attempts integer not null default 0,
  locked_until timestamptz,
  last_login_at timestamptz,
  password_changed_at timestamptz not null default now(),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint users_username_not_blank check (btrim(username) <> ''),
  constraint users_email_not_blank check (
    email is null or btrim(email) <> ''
  ),
  constraint users_role_valid check (role in ('admin', 'user')),
  constraint users_failed_login_attempts_valid check (
    failed_login_attempts >= 0
  )
);

create unique index if not exists users_username_unique_ci
  on private.users (lower(username));

create unique index if not exists users_email_unique_ci
  on private.users (lower(email))
  where email is not null;

create or replace function private.set_updated_at()
returns trigger
language plpgsql
security invoker
set search_path = ''
as $$
begin
  new.updated_at = now();
  return new;
end;
$$;

drop trigger if exists users_set_updated_at on private.users;

create trigger users_set_updated_at
before update on private.users
for each row
execute function private.set_updated_at();

comment on table private.users is
  'Usuários autorizados a acessar o SignTime.';
comment on column private.users.password_hash is
  'Hash Argon2id. Senhas em texto puro nunca devem ser armazenadas.';

revoke all on table private.users from public, anon, authenticated;
revoke all on function private.set_updated_at() from public, anon, authenticated;

commit;
