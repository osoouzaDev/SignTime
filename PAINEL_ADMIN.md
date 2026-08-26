# Painel administrativo do SignTime

O painel fica disponível em `/admin` e aparece como **Gerenciar usuários** no
cabeçalho quando a pessoa autenticada possui o perfil `admin`.

## Funcionalidades

- Cadastrar usuários comuns ou administradores.
- Visualizar e pesquisar todos os usuários.
- Filtrar por perfil e situação.
- Editar nome, usuário, e-mail e perfil.
- Redefinir a senha; deixar o campo vazio mantém a senha atual.
- Ativar ou desativar contas.
- Excluir usuários definitivamente.

## Regras de segurança

- Somente administradores podem abrir o painel ou chamar as APIs administrativas.
- O administrador não pode desativar ou excluir a própria conta.
- O administrador não pode remover o próprio perfil administrativo.
- O sistema preserva pelo menos um administrador ativo.
- Desativar um usuário encerra todas as sessões dele.
- Redefinir uma senha também encerra as sessões existentes.
- Excluir um usuário apaga automaticamente as sessões associadas.
- Cadastros e novas senhas exigem pelo menos 12 caracteres.

## Endpoints internos

- `GET /api/admin/users`
- `POST /api/admin/users`
- `PATCH /api/admin/users/{id}`
- `PATCH /api/admin/users/{id}/status`
- `DELETE /api/admin/users/{id}`

Todas as alterações exigem uma sessão administrativa e o token CSRF emitido no
login.
