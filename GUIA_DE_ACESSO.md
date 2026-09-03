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

No desenvolvimento, mantenha o arquivo `.env` na raiz do projeto. Ele pode
conter a conexão direta com o banco para executar os testes locais.

O executável distribuído não recebe `DATABASE_URL`. Ele usa somente o endereço
HTTPS público do backend, incorporado pelo comando `scripts/build_portable.py`.
A senha do PostgreSQL permanece exclusivamente nas variáveis secretas da
hospedagem.

Use `.env.example` como referência no desenvolvimento. Para publicar e gerar o
arquivo portátil, siga `IMPLANTACAO_BACKEND.md`.

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

O `SignTime.exe` portátil conhece apenas a URL HTTPS da API. Login, sessões e
administração de usuários são processados no backend hospedado, que é o único
componente autorizado a receber `DATABASE_URL`.
