const state = {
  templateFile: null,
  spreadsheetFile: null,
  analysis: null,
  mapping: {},
  downloadUrl: null,
  config: { clicksign_configured: false },
  generating: false,
  user: null,
};

const elements = {
  templateInput: document.querySelector("#template-input"),
  spreadsheetInput: document.querySelector("#spreadsheet-input"),
  templateZone: document.querySelector("#template-zone"),
  spreadsheetZone: document.querySelector("#spreadsheet-zone"),
  analysisLoading: document.querySelector("#analysis-loading"),
  reviewSection: document.querySelector("#review-section"),
  resultSection: document.querySelector("#result-section"),
  resetButton: document.querySelector("#reset-button"),
  newBatchButton: document.querySelector("#new-batch-button"),
  rowCount: document.querySelector("#row-count"),
  variableCount: document.querySelector("#variable-count"),
  mappingCount: document.querySelector("#mapping-count"),
  mappingList: document.querySelector("#mapping-list"),
  sheetField: document.querySelector("#sheet-field"),
  sheetSelect: document.querySelector("#sheet-select"),
  filenameVariable: document.querySelector("#filename-variable"),
  generateButton: document.querySelector("#generate-button"),
  buttonLabel: document.querySelector(".button-label"),
  buttonProgress: document.querySelector(".button-progress"),
  clicksignEnabled: document.querySelector("#clicksign-enabled"),
  clicksignOptions: document.querySelector("#clicksign-options"),
  clicksignEnvironment: document.querySelector("#clicksign-environment"),
  clicksignConfirmed: document.querySelector("#clicksign-confirmed"),
  clicksignStatus: document.querySelector("#clicksign-status"),
  clicksignToken: document.querySelector("#clicksign-token"),
  clicksignTokenField: document.querySelector("#clicksign-token-field"),
  resultMessage: document.querySelector("#result-message"),
  downloadAgain: document.querySelector("#download-again"),
  toast: document.querySelector("#toast"),
  toastMessage: document.querySelector("#toast-message"),
  toastClose: document.querySelector("#toast-close"),
  sessionUser: document.querySelector("#session-user"),
  sessionRole: document.querySelector("#session-role"),
  sessionAvatar: document.querySelector("#session-avatar"),
  logoutButton: document.querySelector("#logout-button"),
  adminPanelLink: document.querySelector("#admin-panel-link"),
};

function cookieValue(name) {
  const prefix = `${name}=`;
  const item = document.cookie.split("; ").find((value) => value.startsWith(prefix));
  return item ? decodeURIComponent(item.slice(prefix.length)) : "";
}

async function authFetch(url, options = {}) {
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
  });
  if (response.status === 401) {
    window.location.replace("/login");
    throw new Error("Sua sessão expirou. Entre novamente.");
  }
  return response;
}

function userInitials(fullName) {
  const parts = String(fullName || "ST").trim().split(/\s+/).filter(Boolean);
  return `${parts[0]?.[0] || "S"}${parts.length > 1 ? parts[parts.length - 1][0] : ""}`.toUpperCase();
}

async function loadSession() {
  try {
    const response = await fetch("/api/auth/session", {
      credentials: "same-origin",
      cache: "no-store",
    });
    if (!response.ok) {
      window.location.replace("/login");
      return false;
    }
    const result = await response.json();
    state.user = result.user;
    elements.sessionUser.textContent = result.user.full_name;
    elements.sessionRole.textContent = result.user.role === "admin" ? "Administrador" : "Usuário";
    elements.sessionAvatar.textContent = userInitials(result.user.full_name);
    elements.adminPanelLink.hidden = result.user.role !== "admin";
    return true;
  } catch {
    window.location.replace("/login");
    return false;
  }
}

async function logout() {
  elements.logoutButton.disabled = true;
  try {
    await authFetch("/api/auth/logout", { method: "POST" });
    window.location.replace("/login");
  } catch (error) {
    elements.logoutButton.disabled = false;
    showToast(error.message || "Não foi possível encerrar a sessão.");
  }
}

function formatBytes(bytes) {
  if (bytes < 1024 * 1024) return `${Math.max(1, Math.round(bytes / 1024))} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1).replace(".", ",")} MB`;
}

function fileToDataUrl(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(reader.result);
    reader.onerror = () => reject(new Error(`Não foi possível ler ${file.name}.`));
    reader.readAsDataURL(file);
  });
}

function showToast(message) {
  elements.toastMessage.textContent = message;
  elements.toast.hidden = false;
  window.clearTimeout(showToast.timeout);
  showToast.timeout = window.setTimeout(() => {
    elements.toast.hidden = true;
  }, 7000);
}

function setJourney(step) {
  document.querySelectorAll(".journey-item").forEach((item) => {
    const number = Number(item.dataset.journey);
    item.classList.toggle("is-active", number === step);
    item.classList.toggle("is-complete", number < step);
  });
}

function updateDropzone(zone, file, defaultTitle, defaultHelp) {
  const title = zone.querySelector(".upload-copy strong");
  const help = zone.querySelector(".upload-copy small");
  const action = zone.querySelector(".upload-action");
  zone.classList.toggle("has-file", Boolean(file));
  if (file) {
    title.textContent = file.name;
    title.title = file.name;
    help.textContent = `${formatBytes(file.size)} • arquivo selecionado`;
    action.textContent = "Trocar arquivo";
  } else {
    title.textContent = defaultTitle;
    title.removeAttribute("title");
    help.textContent = defaultHelp;
    action.textContent = "Selecionar";
  }
}

function validateFile(file, extensions) {
  const extension = `.${file.name.split(".").pop().toLowerCase()}`;
  if (!extensions.includes(extension)) {
    showToast(`O arquivo ${file.name} não está no formato esperado.`);
    return false;
  }
  if (file.size > 25 * 1024 * 1024) {
    showToast(`${file.name} excede o limite de 25 MB.`);
    return false;
  }
  return true;
}

async function setFile(kind, file) {
  if (!file || state.generating) return;
  const isTemplate = kind === "template";
  const extensions = isTemplate ? [".docx"] : [".xlsx", ".csv"];
  if (!validateFile(file, extensions)) return;

  if (isTemplate) {
    state.templateFile = file;
    updateDropzone(
      elements.templateZone,
      file,
      "Modelo do contrato",
      "Arquivo Word .docx • até 25 MB",
    );
  } else {
    state.spreadsheetFile = file;
    updateDropzone(
      elements.spreadsheetZone,
      file,
      "Planilha com os dados",
      "Excel .xlsx ou .csv • até 25 MB",
    );
  }

  state.analysis = null;
  elements.reviewSection.hidden = true;
  elements.resultSection.hidden = true;
  if (state.templateFile && state.spreadsheetFile) await analyzeFiles();
}

function uploadPayload(dataUrl, file) {
  return { name: file.name, data: dataUrl };
}

async function analyzeFiles(sheetName = null) {
  elements.analysisLoading.hidden = false;
  elements.reviewSection.hidden = true;
  elements.resultSection.hidden = true;
  setJourney(1);
  try {
    const [templateData, spreadsheetData] = await Promise.all([
      fileToDataUrl(state.templateFile),
      fileToDataUrl(state.spreadsheetFile),
    ]);
    const response = await authFetch("/api/analyze", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        template: uploadPayload(templateData, state.templateFile),
        spreadsheet: uploadPayload(spreadsheetData, state.spreadsheetFile),
        sheet_name: sheetName,
      }),
    });
    const result = await response.json();
    if (!response.ok) throw new Error(result.error || "Não foi possível analisar os arquivos.");

    state.analysis = result;
    state.mapping = result.mapping;
    renderAnalysis();
    elements.reviewSection.hidden = false;
    elements.resetButton.hidden = false;
    setJourney(2);
    window.setTimeout(() => {
      elements.reviewSection.scrollIntoView({ behavior: "smooth", block: "start" });
    }, 80);
  } catch (error) {
    showToast(error.message || "Não foi possível analisar os arquivos.");
  } finally {
    elements.analysisLoading.hidden = true;
  }
}

function mappingKey(rule) {
  return JSON.stringify({ kind: rule?.kind || "empty", value: rule?.value || "" });
}

function mappingRule(value) {
  try {
    return JSON.parse(value);
  } catch {
    return { kind: "empty", value: "" };
  }
}

function makeOption(select, label, rule, selectedRule) {
  const option = document.createElement("option");
  option.textContent = label;
  option.value = mappingKey(rule);
  option.selected = option.value === mappingKey(selectedRule);
  select.append(option);
}

function isAddressVariable(variable) {
  const normalized = variable.toLowerCase().replace(/[^a-z0-9]+/g, "_");
  return normalized.includes("texto_endereco") || normalized.includes("endereco_formatado");
}

function createMappingRow(variable) {
  const rule = state.mapping[variable] || { kind: "empty", value: "", confidence: "pending" };
  const row = document.createElement("div");
  row.className = "mapping-row";

  const variableLabel = document.createElement("div");
  variableLabel.className = "variable-name";
  const status = document.createElement("i");
  status.className = rule.confidence || "pending";
  const name = document.createElement("span");
  name.textContent = `{{ ${variable} }}`;
  variableLabel.append(status, name);

  const arrow = document.createElement("span");
  arrow.className = "mapping-arrow";
  arrow.textContent = "→";
  arrow.setAttribute("aria-hidden", "true");

  const select = document.createElement("select");
  select.setAttribute("aria-label", `Origem da variável ${variable}`);
  makeOption(select, "Selecione uma origem", { kind: "empty", value: "" }, rule);
  makeOption(select, "Data atual do sistema", { kind: "system", value: "today" }, rule);

  state.analysis.columns.forEach((column) => {
    makeOption(select, column, { kind: "column", value: column }, rule);
    if (isAddressVariable(variable)) {
      makeOption(
        select,
        `${column} (com texto de endereço)`,
        { kind: "address_clause", value: column },
        rule,
      );
    }
  });

  select.addEventListener("change", () => {
    const selected = mappingRule(select.value);
    state.mapping[variable] = { ...selected, confidence: selected.kind === "empty" ? "pending" : "high" };
    status.className = state.mapping[variable].confidence;
    updateMappingCount();
  });

  row.append(variableLabel, arrow, select);
  return row;
}

function updateMappingCount() {
  const mapped = Object.values(state.mapping).filter((rule) => rule.kind && rule.kind !== "empty").length;
  elements.mappingCount.textContent = String(mapped);
}

function renderAnalysis() {
  const analysis = state.analysis;
  elements.rowCount.textContent = String(analysis.rows);
  elements.variableCount.textContent = String(analysis.variables.length);
  elements.mappingList.replaceChildren(...analysis.variables.map(createMappingRow));
  updateMappingCount();

  elements.sheetField.hidden = analysis.sheets.length <= 1;
  elements.sheetSelect.replaceChildren();
  analysis.sheets.forEach((sheet) => {
    const option = document.createElement("option");
    option.value = sheet;
    option.textContent = sheet;
    option.selected = sheet === analysis.selected_sheet;
    elements.sheetSelect.append(option);
  });

  elements.filenameVariable.replaceChildren();
  analysis.variables.forEach((variable) => {
    const option = document.createElement("option");
    option.value = variable;
    option.textContent = `{{ ${variable} }}`;
    option.selected = variable === "nome_responsavel";
    elements.filenameVariable.append(option);
  });
}

function selectedFormat() {
  return document.querySelector('input[name="format"]:checked')?.value || "pdf";
}

function missingMappings() {
  return state.analysis.variables.filter((variable) => {
    const rule = state.mapping[variable];
    return !rule || !rule.kind || rule.kind === "empty";
  });
}

function setGenerating(active, progress = 0) {
  state.generating = active;
  elements.generateButton.disabled = active;
  elements.buttonLabel.textContent = active
    ? "Gerando contratos…"
    : "Gerar contratos e baixar ZIP";
  elements.buttonProgress.style.width = `${progress}%`;
}

function triggerDownload(blob) {
  if (state.downloadUrl) URL.revokeObjectURL(state.downloadUrl);
  state.downloadUrl = URL.createObjectURL(blob);
  elements.downloadAgain.href = state.downloadUrl;
  const temporaryLink = document.createElement("a");
  temporaryLink.href = state.downloadUrl;
  temporaryLink.download = "contratos_gerados.zip";
  document.body.append(temporaryLink);
  temporaryLink.click();
  temporaryLink.remove();
}

async function generateContracts() {
  if (!state.analysis || state.generating) return;
  const missing = missingMappings();
  if (missing.length) {
    showToast(`Defina a origem de: ${missing.join(", ")}.`);
    elements.mappingList.scrollIntoView({ behavior: "smooth", block: "center" });
    return;
  }

  if (elements.clicksignEnabled.checked && !elements.clicksignConfirmed.checked) {
    showToast("Confirme os dados dos signatários antes de enviar à Clicksign.");
    document.querySelector("#clicksign-panel").open = true;
    return;
  }

  if (
    elements.clicksignEnabled.checked
    && !state.config.clicksign_configured
    && !elements.clicksignToken.value.trim()
  ) {
    showToast("Informe o token de acesso da Clicksign para realizar os envios.");
    document.querySelector("#clicksign-panel").open = true;
    return;
  }

  setGenerating(true, 8);
  let progress = 8;
  const progressTimer = window.setInterval(() => {
    progress = Math.min(88, progress + Math.max(1, Math.round((90 - progress) / 8)));
    elements.buttonProgress.style.width = `${progress}%`;
  }, 450);

  try {
    const [templateData, spreadsheetData] = await Promise.all([
      fileToDataUrl(state.templateFile),
      fileToDataUrl(state.spreadsheetFile),
    ]);
    const response = await authFetch("/api/generate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        template: uploadPayload(templateData, state.templateFile),
        spreadsheet: uploadPayload(spreadsheetData, state.spreadsheetFile),
        sheet_name: state.analysis.selected_sheet,
        mapping: state.mapping,
        output_format: selectedFormat(),
        filename_variable: elements.filenameVariable.value,
        clicksign: {
          enabled: elements.clicksignEnabled.checked,
          confirmed: elements.clicksignConfirmed.checked,
          environment: elements.clicksignEnvironment.value,
          access_token: elements.clicksignToken.value.trim(),
        },
      }),
    });
    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.error || "Não foi possível gerar os contratos.");
    }

    const blob = await response.blob();
    const generated = Number(response.headers.get("X-Generated") || 0);
    const errors = Number(response.headers.get("X-Errors") || 0);
    const fallbacks = Number(response.headers.get("X-Pdf-Fallbacks") || 0);
    const sent = Number(response.headers.get("X-Clicksign-Sent") || 0);

    elements.buttonProgress.style.width = "100%";
    triggerDownload(blob);

    const details = [`${generated} contrato${generated === 1 ? "" : "s"} gerado${generated === 1 ? "" : "s"}`];
    if (errors) details.push(`${errors} linha${errors === 1 ? "" : "s"} com erro no relatório`);
    if (fallbacks) details.push(`${fallbacks} arquivo${fallbacks === 1 ? "" : "s"} entregue${fallbacks === 1 ? "" : "s"} em Word`);
    if (sent) details.push(`${sent} enviado${sent === 1 ? "" : "s"} à Clicksign`);
    elements.resultMessage.textContent = `${details.join(" • ")}. O download do ZIP começou automaticamente.`;

    document.querySelector(".step-section").hidden = true;
    elements.reviewSection.hidden = true;
    elements.resultSection.hidden = false;
    elements.resetButton.hidden = false;
    setJourney(3);
    elements.resultSection.scrollIntoView({ behavior: "smooth", block: "center" });
  } catch (error) {
    showToast(error.message || "Não foi possível gerar os contratos.");
  } finally {
    window.clearInterval(progressTimer);
    window.setTimeout(() => setGenerating(false, 0), 450);
  }
}

function resetAll() {
  if (state.generating) return;
  state.templateFile = null;
  state.spreadsheetFile = null;
  state.analysis = null;
  state.mapping = {};
  elements.templateInput.value = "";
  elements.spreadsheetInput.value = "";
  elements.reviewSection.hidden = true;
  elements.resultSection.hidden = true;
  document.querySelector(".step-section").hidden = false;
  elements.resetButton.hidden = true;
  elements.clicksignEnabled.checked = false;
  elements.clicksignConfirmed.checked = false;
  elements.clicksignToken.value = "";
  elements.clicksignOptions.hidden = true;
  updateDropzone(elements.templateZone, null, "Modelo do contrato", "Arquivo Word .docx • até 25 MB");
  updateDropzone(elements.spreadsheetZone, null, "Planilha com os dados", "Excel .xlsx ou .csv • até 25 MB");
  setJourney(1);
  window.scrollTo({ top: 0, behavior: "smooth" });
}

function installFileEvents(input, zone, kind) {
  input.addEventListener("change", () => setFile(kind, input.files?.[0]));
  ["dragenter", "dragover"].forEach((eventName) => {
    zone.addEventListener(eventName, (event) => {
      event.preventDefault();
      zone.classList.add("is-dragging");
    });
  });
  ["dragleave", "drop"].forEach((eventName) => {
    zone.addEventListener(eventName, (event) => {
      event.preventDefault();
      zone.classList.remove("is-dragging");
    });
  });
  zone.addEventListener("drop", (event) => setFile(kind, event.dataTransfer.files?.[0]));
}

async function loadConfig() {
  try {
    const response = await authFetch("/api/config");
    state.config = await response.json();
  } catch {
    state.config = { clicksign_configured: false };
  }

  if (state.config.clicksign_configured) {
    elements.clicksignEnabled.disabled = false;
    elements.clicksignStatus.textContent = "Token configurado • use somente quando desejar enviar";
  } else {
    elements.clicksignEnabled.disabled = false;
    elements.clicksignStatus.textContent = "Configure CLICKSIGN_ACCESS_TOKEN no arquivo .env para habilitar";
  }
}

installFileEvents(elements.templateInput, elements.templateZone, "template");
installFileEvents(elements.spreadsheetInput, elements.spreadsheetZone, "spreadsheet");
elements.sheetSelect.addEventListener("change", () => analyzeFiles(elements.sheetSelect.value));
elements.generateButton.addEventListener("click", generateContracts);
elements.resetButton.addEventListener("click", resetAll);
elements.newBatchButton.addEventListener("click", resetAll);
elements.toastClose.addEventListener("click", () => { elements.toast.hidden = true; });
elements.logoutButton.addEventListener("click", logout);
elements.clicksignEnabled.addEventListener("change", () => {
  elements.clicksignOptions.hidden = !elements.clicksignEnabled.checked;
});

async function initialize() {
  if (await loadSession()) await loadConfig();
}

initialize();
