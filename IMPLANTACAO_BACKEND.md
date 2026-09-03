# Publicação segura do SignTime

O SignTime usa duas partes:

- `SignTime.exe`: abre a interface e gera os contratos no computador do usuário.
- `backend/api.py`: fica hospedado na internet e é o único componente que conhece a senha do PostgreSQL.

O executável recebe apenas a URL HTTPS pública do backend. A senha do banco não é incluída no arquivo compartilhado.

## 1. Preparar a conexão do Supabase

No painel do Supabase, abra o projeto do SignTime e clique em **Connect**. Para uma hospedagem que utilize somente IPv4, copie a conexão **Session pooler**, na porta `5432`.

Substitua o campo reservado para a senha pela senha atual do banco. Não coloque essa conexão no GitHub.

## 2. Publicar no Render

1. Envie os novos arquivos deste projeto para o GitHub.
2. Entre em `https://dashboard.render.com`.
3. Escolha **New** e depois **Blueprint**.
4. Conecte o repositório `osoouzaDev/SignTime`.
5. O Render localizará o arquivo `render.yaml` e solicitará o valor de `DATABASE_URL`.
6. Cole a conexão **Session pooler** preparada no passo anterior.
7. Confirme a criação e aguarde o estado **Live**.
8. Abra `https://SEU-SERVICO.onrender.com/v1/health`. O resultado deve conter `"status":"ok"`.

O plano gratuito é adequado para validação, mas pode desligar o serviço após alguns minutos sem uso e demorar para responder no primeiro acesso. Para uso diário, selecione um plano sempre ativo.

## 3. Gerar o executável portátil

Depois de copiar a URL exibida pelo Render, execute no PowerShell, dentro do projeto:

```powershell
.\.venv\Scripts\python.exe .\scripts\build_portable.py --api-url "https://SEU-SERVICO.onrender.com"
```

O arquivo final será criado em `dist\SignTime.exe`. Ele poderá ser copiado sozinho para outro computador Windows.

## 4. Conferência

Antes de distribuir:

1. Copie somente o novo `SignTime.exe` para outra pasta.
2. Abra o arquivo e entre com uma conta ativa.
3. Confirme que o painel administrativo aparece para administradores.
4. Gere um contrato de teste e baixe o ZIP.

Cada computador precisa ter acesso à internet. A geração em Word funciona dentro do executável; a conversão para PDF requer Microsoft Word instalado na máquina.
