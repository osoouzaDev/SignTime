const adminState = {
  currentUser: null,
  users: [],
  editingId: null,
  deletingId: null,
};

const adminElements = {
  sessionUser: document.querySelector("#session-user"),
  sessionAvatar: document.querySelector("#session-avatar"),
  logoutButton: document.querySelector("#logout-button"),
  newUserButton: document.querySelector("#new-user-button"),
  statTotal: document.querySelector("#stat-total"),
  statActive: document.querySelector("#stat-active"),
  statAdmins: document.querySelector("#stat-admins"),
  statInactive: document.querySelector("#stat-inactive"),
  search: document.querySelector("#user-search"),
  roleFilter: document.querySelector("#role-filter"),
  statusFilter: document.querySelector("#status-filter"),
  loading: document.querySelector("#users-loading"),
  tableWrap: document.querySelector("#users-table-wrap"),
  tableBody: document.querySelector("#users-table-body"),
  empty: document.querySelector("#users-empty"),
  userDialog: document.querySelector("#user-dialog"),
  userForm: document.querySelector("#user-form"),
  dialogKicker: document.querySelector("#dialog-kicker"),
  dialogTitle: document.querySelector("#dialog-title"),
  dialogClose: document.querySelector("#dialog-close"),
  dialogCancel: document.querySelector("#dialog-cancel"),
  dialogSave: document.querySelector("#dialog-save"),
  dialogError: document.querySelector("#dialog-error"),
  fullName: document.querySelector("#user-full-name"),
  username: document.querySelector("#user-username"),
  email: document.querySelector("#user-email"),
  role: document.querySelector("#user-role"),
  password: document.querySelector("#user-password"),
  passwordLabel: document.querySelector("#password-label"),
  passwordHelp: document.querySelector("#password-help"),
  deleteDialog: document.querySelector("#delete-dialog"),
  deleteMessage: document.querySelector("#delete-message"),
  deleteCancel: document.querySelector("#delete-cancel"),
  deleteConfirm: document.querySelector("#delete-confirm"),
  toast: document.querySelector("#admin-toast"),
  toastMessage: document.querySelector("#admin-toast-message"),
  toastClose: document.querySelector("#admin-toast-close"),
};

function cookieValue(name) {
  const prefix = `${name}=`;
  const item = document.cookie.split("; ").find((value) => value.startsWith(prefix));
  return item ? decodeURIComponent(item.slice(prefix.length)) : "";
}

async function adminFetch(url, options = {}) {
  const method = String(options.method || "GET").toUpperCase();
  const headers = new Headers(options.headers || {});
  if (!["GET", "HEAD", "OPTIONS"].includes(method)) {
    const csrfToken = cookieValue("signtime_csrf");
    if (csrfToken) headers.set("X-CSRF-Token", csrfToken);
  }
  const response = await fetch(url, {
    ...options,
    method,
    headers,
    credentials: "same-origin",
    cache: "no-store",
  });
  if (response.status === 401) {
    window.location.replace("/login");
    throw new Error("Sua sessão expirou. Entre novamente.");
  }
  return response;
}

async function responseJson(response) {
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(payload.error || "Não foi possível concluir a operação.");
  return payload;
}

function initials(fullName) {
  const parts = String(fullName || "ST").trim().split(/\s+/).filter(Boolean);
  return `${parts[0]?.[0] || "S"}${parts.length > 1 ? parts[parts.length - 1][0] : ""}`.toUpperCase();
}

function showToast(message) {
  adminElements.toastMessage.textContent = message;
  adminElements.toast.hidden = false;
  window.clearTimeout(showToast.timeout);
  showToast.timeout = window.setTimeout(() => {
    adminElements.toast.hidden = true;
  }, 5500);
}

function formatDate(value) {
  if (!value) return "Nunca acessou";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "—";
  return new Intl.DateTimeFormat("pt-BR", {
    dateStyle: "short",
    timeStyle: "short",
  }).format(date);
}

function appendText(parent, tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  node.textContent = text;
  parent.append(node);
  return node;
}

function actionButton(label, className, onClick, disabled = false, title = "") {
  const button = document.createElement("button");
  button.type = "button";
  button.className = `user-action ${className || ""}`.trim();
  button.textContent = label;
  button.disabled = disabled;
  if (title) button.title = title;
  button.addEventListener("click", onClick);
  return button;
}

function renderStats() {
  const active = adminState.users.filter((user) => user.is_active).length;
  const admins = adminState.users.filter((user) => user.role === "admin" && user.is_active).length;
  adminElements.statTotal.textContent = String(adminState.users.length);
  adminElements.statActive.textContent = String(active);
  adminElements.statAdmins.textContent = String(admins);
  adminElements.statInactive.textContent = String(adminState.users.length - active);
}

function filteredUsers() {
  const query = adminElements.search.value.trim().toLocaleLowerCase("pt-BR");
  const role = adminElements.roleFilter.value;
  const status = adminElements.statusFilter.value;
  return adminState.users.filter((user) => {
    const searchable = `${user.full_name} ${user.username} ${user.email || ""}`.toLocaleLowerCase("pt-BR");
    const roleMatches = role === "all" || user.role === role;
    const statusMatches = status === "all"
      || (status === "active" && user.is_active)
      || (status === "inactive" && !user.is_active);
    return searchable.includes(query) && roleMatches && statusMatches;
  });
}

function renderUsers() {
  const users = filteredUsers();
  adminElements.tableBody.replaceChildren();
  adminElements.empty.hidden = users.length > 0;
  adminElements.tableBody.parentElement.hidden = users.length === 0;

  users.forEach((user) => {
    const isSelf = user.id === adminState.currentUser.id;
    const row = document.createElement("tr");
    row.classList.toggle("is-inactive", !user.is_active);

    const personCell = document.createElement("td");
    const person = appendText(personCell, "div", "user-person", "");
    person.textContent = "";
    appendText(person, "span", "user-list-avatar", initials(user.full_name));
    const copy = appendText(person, "span", "user-person-copy", "");
    copy.textContent = "";
    appendText(copy, "strong", "", user.full_name);
    appendText(copy, "span", "", `${user.username}${user.email ? ` • ${user.email}` : ""}`);
    if (isSelf) appendText(copy, "small", "", "Você");
    row.append(personCell);

    const roleCell = document.createElement("td");
    appendText(roleCell, "span", `role-badge ${user.role}`, user.role === "admin" ? "Administrador" : "Usuário");
    row.append(roleCell);

    const statusCell = document.createElement("td");
    appendText(statusCell, "span", `status-badge ${user.is_active ? "active" : "inactive"}`, user.is_active ? "Ativo" : "Desativado");
    row.append(statusCell);

    const accessCell = document.createElement("td");
    appendText(accessCell, "span", "last-access", formatDate(user.last_login_at));
    row.append(accessCell);

    const actionCell = document.createElement("td");
    const actions = appendText(actionCell, "div", "user-actions", "");
    actions.textContent = "";
    actions.append(actionButton("Editar", "", () => openEditDialog(user)));
    actions.append(actionButton(
      user.is_active ? "Desativar" : "Ativar",
      "",
      () => toggleUserStatus(user),
      isSelf,
      isSelf ? "Você não pode desativar a própria conta." : "",
    ));
    actions.append(actionButton(
      "Excluir",
      "danger",
      () => openDeleteDialog(user),
      isSelf,
      isSelf ? "Você não pode excluir a própria conta." : "",
    ));
    row.append(actionCell);
    adminElements.tableBody.append(row);
  });
}

async function loadSession() {
  const response = await adminFetch("/api/auth/session");
  const payload = await responseJson(response);
  if (payload.user.role !== "admin") {
    window.location.replace("/");
    return false;
  }
  adminState.currentUser = payload.user;
  adminElements.sessionUser.textContent = payload.user.full_name;
  adminElements.sessionAvatar.textContent = initials(payload.user.full_name);
  return true;
}

async function loadUsers() {
  adminElements.loading.hidden = false;
  adminElements.tableWrap.hidden = true;
  try {
    const response = await adminFetch("/api/admin/users");
    const payload = await responseJson(response);
    adminState.users = payload.users;
    renderStats();
    renderUsers();
    adminElements.tableWrap.hidden = false;
  } catch (error) {
    showToast(error.message);
  } finally {
    adminElements.loading.hidden = true;
  }
}

function showDialog(dialog) {
  if (typeof dialog.showModal === "function") dialog.showModal();
  else dialog.setAttribute("open", "");
}

function closeDialog(dialog) {
  if (typeof dialog.close === "function") dialog.close();
  else dialog.removeAttribute("open");
}

function setSaving(active) {
  adminElements.dialogSave.disabled = active;
  adminElements.dialogSave.classList.toggle("is-loading", active);
  adminElements.dialogSave.querySelector("span").textContent = active ? "Salvando…" : "Salvar usuário";
}

function openCreateDialog() {
  adminState.editingId = null;
  adminElements.userForm.reset();
  adminElements.dialogKicker.textContent = "Novo acesso";
  adminElements.dialogTitle.textContent = "Cadastrar usuário";
  adminElements.passwordLabel.textContent = "Senha";
  adminElements.passwordHelp.textContent = "Use pelo menos 12 caracteres.";
  adminElements.password.required = true;
  adminElements.dialogError.hidden = true;
  showDialog(adminElements.userDialog);
  adminElements.fullName.focus();
}

function openEditDialog(user) {
  adminState.editingId = user.id;
  adminElements.userForm.reset();
  adminElements.dialogKicker.textContent = "Editar acesso";
  adminElements.dialogTitle.textContent = user.full_name;
  adminElements.fullName.value = user.full_name;
  adminElements.username.value = user.username;
  adminElements.email.value = user.email || "";
  adminElements.role.value = user.role;
  adminElements.passwordLabel.textContent = "Nova senha (opcional)";
  adminElements.passwordHelp.textContent = "Deixe em branco para manter a senha atual.";
  adminElements.password.required = false;
  adminElements.dialogError.hidden = true;
  showDialog(adminElements.userDialog);
  adminElements.fullName.focus();
}

async function saveUser(event) {
  event.preventDefault();
  if (!adminElements.userForm.reportValidity()) return;
  setSaving(true);
  adminElements.dialogError.hidden = true;
  const payload = {
    full_name: adminElements.fullName.value.trim(),
    username: adminElements.username.value.trim(),
    email: adminElements.email.value.trim() || null,
    role: adminElements.role.value,
    password: adminElements.password.value,
  };
  const editing = Boolean(adminState.editingId);
  try {
    const response = await adminFetch(
      editing ? `/api/admin/users/${adminState.editingId}` : "/api/admin/users",
      {
        method: editing ? "PATCH" : "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      },
    );
    await responseJson(response);
    closeDialog(adminElements.userDialog);
    showToast(editing ? "Usuário atualizado com sucesso." : "Usuário cadastrado com sucesso.");
    await loadUsers();
  } catch (error) {
    adminElements.dialogError.textContent = error.message;
    adminElements.dialogError.hidden = false;
  } finally {
    setSaving(false);
  }
}

async function toggleUserStatus(user) {
  if (user.is_active && !window.confirm(`Desativar o acesso de ${user.full_name}?`)) return;
  try {
    const response = await adminFetch(`/api/admin/users/${user.id}/status`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ is_active: !user.is_active }),
    });
    await responseJson(response);
    showToast(user.is_active ? "Usuário desativado e sessões encerradas." : "Usuário ativado com sucesso.");
    await loadUsers();
  } catch (error) {
    showToast(error.message);
  }
}

function openDeleteDialog(user) {
  adminState.deletingId = user.id;
  adminElements.deleteMessage.textContent = `O acesso de ${user.full_name} será removido definitivamente e todas as sessões serão encerradas.`;
  showDialog(adminElements.deleteDialog);
}

async function deleteUser() {
  if (!adminState.deletingId) return;
  adminElements.deleteConfirm.disabled = true;
  try {
    const response = await adminFetch(`/api/admin/users/${adminState.deletingId}`, { method: "DELETE" });
    await responseJson(response);
    closeDialog(adminElements.deleteDialog);
    adminState.deletingId = null;
    showToast("Usuário excluído com sucesso.");
    await loadUsers();
  } catch (error) {
    closeDialog(adminElements.deleteDialog);
    showToast(error.message);
  } finally {
    adminElements.deleteConfirm.disabled = false;
  }
}

async function logout() {
  adminElements.logoutButton.disabled = true;
  try {
    await adminFetch("/api/auth/logout", { method: "POST" });
    window.location.replace("/login");
  } catch (error) {
    adminElements.logoutButton.disabled = false;
    showToast(error.message);
  }
}

adminElements.newUserButton.addEventListener("click", openCreateDialog);
adminElements.userForm.addEventListener("submit", saveUser);
adminElements.dialogClose.addEventListener("click", () => closeDialog(adminElements.userDialog));
adminElements.dialogCancel.addEventListener("click", () => closeDialog(adminElements.userDialog));
adminElements.deleteCancel.addEventListener("click", () => closeDialog(adminElements.deleteDialog));
adminElements.deleteConfirm.addEventListener("click", deleteUser);
adminElements.logoutButton.addEventListener("click", logout);
adminElements.toastClose.addEventListener("click", () => { adminElements.toast.hidden = true; });
[adminElements.search, adminElements.roleFilter, adminElements.statusFilter].forEach((element) => {
  element.addEventListener(element === adminElements.search ? "input" : "change", renderUsers);
});

async function initializeAdmin() {
  try {
    if (await loadSession()) await loadUsers();
  } catch (error) {
    showToast(error.message || "Não foi possível abrir o painel administrativo.");
  }
}

initializeAdmin();
