const form = document.querySelector("#login-form");
const usernameInput = document.querySelector("#login-username");
const passwordInput = document.querySelector("#login-password");
const submitButton = document.querySelector("#login-button");
const errorBox = document.querySelector("#login-error");

function showError(message) {
  errorBox.textContent = message;
  errorBox.hidden = false;
}

function setLoading(loading) {
  submitButton.disabled = loading;
  submitButton.classList.toggle("is-loading", loading);
  submitButton.querySelector("span").textContent = loading
    ? "Verificando acesso…"
    : "Entrar com segurança";
}

async function redirectIfAuthenticated() {
  try {
    const response = await fetch("/api/auth/session", {
      credentials: "same-origin",
      cache: "no-store",
    });
    if (response.ok) window.location.replace("/");
  } catch {
    // A tela continua disponível quando o servidor ainda está iniciando.
  }
}

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  errorBox.hidden = true;
  const username = usernameInput.value.trim();
  const password = passwordInput.value;
  if (!username || !password) {
    showError("Informe seu usuário e sua senha.");
    return;
  }

  setLoading(true);
  try {
    const response = await fetch("/api/auth/login", {
      method: "POST",
      credentials: "same-origin",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username, password }),
    });
    const result = await response.json();
    if (!response.ok) {
      throw new Error(result.error || "Não foi possível entrar.");
    }
    window.location.replace("/");
  } catch (error) {
    passwordInput.value = "";
    passwordInput.focus();
    showError(error.message || "Não foi possível entrar.");
  } finally {
    setLoading(false);
  }
});

redirectIfAuthenticated();
