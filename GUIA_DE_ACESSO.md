# Acesso e autenticação do SignTime

## O que foi implementado

- Login com usuário e senha cadastrados no PostgreSQL.
- Senhas protegidas com Argon2id; a senha original não é salva.
- Sessões persistidas no banco, com expiração automática.
- Bloqueio temporário após tentativas incorretas consecutivas.
- Proteção CSRF nas ações que alteram dados.
- Cookies `HttpOnly`, `SameSite=Strict` e opção `Secure` para produção HTTPS.
- Rotas, arquivos do sistema e APIs protegidos por autenticação.
- Logout que revoga a sessão no banco.

## Configuração

No desenvolvimento, mantenha o arquivo `.env` na raiz do projeto. Para o
executável local, mantenha o `.env` ao lado de `SignTime.exe`.

Use `.env.example` como referência:

```text
DATABASE_URL=postgresql+psycopg://usuario:senha@host:5432/postgres
DATABASE_SSLMODE=require
COOKIE_SECURE=false
SESSION_DURATION_HOURS=8
```

Em um servidor online com HTTPS, configure `COOKIE_SECURE=true` nas variáveis
do ambiente de hospedagem. Não publique nem envie o arquivo `.env` junto com o
código.

## Criar o primeiro usuário

Com o ambiente virtual preparado, execute:

```powershell
.\.venv\Scripts\python.exe .\scripts\create_user.py --role admin
```

O comando solicita usuário, nome, e-mail opcional e senha sem exibir a senha na
tela. A senha precisa ter pelo menos 12 caracteres.

Para criar um usuário comum:

```powershell
.\.venv\Scripts\python.exe .\scripts\create_user.py --role user
```

## Banco de dados

As migrations ficam em `supabase/migrations`:

- `20260826010000_create_users.sql`
- `20260826020000_create_user_sessions.sql`

As tabelas ficam no schema privado `private`, sem acesso direto para as funções
`anon` e `authenticated` do Supabase.

## Observação sobre distribuição

Não distribua para usuários finais um executável acompanhado das credenciais de
administrador do PostgreSQL. Para uso por várias pessoas ou máquinas, hospede o
SignTime como aplicação web e mantenha `DATABASE_URL` somente no servidor.
