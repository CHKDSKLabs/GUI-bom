const state = {
  currentPath: "",
  parentPath: null,
  currentFormat: "json",
  renderedOutput: "",
  selectedPath: "",
  documents: [],
  summary: null,
};

const elements = {
  scanPath: document.querySelector("#scan-path"),
  scanButton: document.querySelector("#scan-button"),
  hashToggle: document.querySelector("#hash-toggle"),
  message: document.querySelector("#message"),
  rootSelect: document.querySelector("#root-select"),
  upButton: document.querySelector("#up-button"),
  refreshButton: document.querySelector("#refresh-button"),
  useCurrentFolder: document.querySelector("#use-current-folder"),
  copyPath: document.querySelector("#copy-path"),
  browserPath: document.querySelector("#browser-path"),
  browserList: document.querySelector("#browser-list"),
  summaryGrid: document.querySelector("#summary-grid"),
  documentGrid: document.querySelector("#document-grid"),
  warningList: document.querySelector("#warning-list"),
  warningCount: document.querySelector("#warning-count"),
  emptyState: document.querySelector("#empty-state"),
  resultsPanel: document.querySelector("#results-panel"),
  rawOutput: document.querySelector("#raw-output"),
  copyOutput: document.querySelector("#copy-output"),
  downloadOutput: document.querySelector("#download-output"),
  formatButtons: Array.from(document.querySelectorAll("[data-format]")),
  tabButtons: Array.from(document.querySelectorAll("[data-tab]")),
  overviewTab: document.querySelector("#overview-tab"),
  rawTab: document.querySelector("#raw-tab"),
  hfOptions: document.querySelector("#hf-options"),
  hfTitle: document.querySelector("#hf-title"),
  hfShortDescription: document.querySelector("#hf-short-description"),
  hfSdk: document.querySelector("#hf-sdk"),
  hfAppFile: document.querySelector("#hf-app-file"),
  hfAppPort: document.querySelector("#hf-app-port"),
};

boot().catch((error) => {
  showMessage(error.message, "error");
});

function bindEvents() {
  elements.scanButton.addEventListener("click", () => {
    void runScan();
  });

  elements.scanPath.addEventListener("keydown", (event) => {
    if (event.key === "Enter") {
      event.preventDefault();
      void runScan();
    }
  });

  elements.rootSelect.addEventListener("change", () => {
    const nextPath = elements.rootSelect.value;
    if (nextPath) {
      void loadDirectory(nextPath);
    }
  });

  elements.upButton.addEventListener("click", () => {
    if (state.parentPath) {
      void loadDirectory(state.parentPath);
    }
  });

  elements.refreshButton.addEventListener("click", () => {
    if (state.currentPath) {
      void loadDirectory(state.currentPath);
    }
  });

  elements.useCurrentFolder.addEventListener("click", async () => {
    if (!state.currentPath) {
      return;
    }

    elements.scanPath.value = state.currentPath;
    showMessage(`Ready to scan ${state.currentPath}`, "success");
  });

  elements.copyPath.addEventListener("click", async () => {
    const value = elements.scanPath.value.trim();
    if (!value) {
      showMessage("Choose or enter a path first.", "error");
      return;
    }

    if (await copyText(value)) {
      showMessage("Path copied to your clipboard.", "success");
      return;
    }

    showMessage("Clipboard access is not available in this browser session.", "error");
  });

  elements.copyOutput.addEventListener("click", async () => {
    if (!state.renderedOutput) {
      return;
    }

    if (await copyText(state.renderedOutput)) {
      showMessage("Rendered output copied to your clipboard.", "success");
      return;
    }

    showMessage("Clipboard access is not available in this browser session.", "error");
  });

  elements.downloadOutput.addEventListener("click", () => {
    if (!state.renderedOutput) {
      return;
    }

    const filename = state.currentFormat === "hf-readme"
      ? "README.md"
      : `L-BOM.${state.currentFormat === "json" ? "json" : "txt"}`;
    const blob = new Blob([state.renderedOutput], { type: "text/plain;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = filename;
    document.body.append(link);
    link.click();
    link.remove();
    URL.revokeObjectURL(url);
  });

  for (const button of elements.formatButtons) {
    button.addEventListener("click", () => {
      state.currentFormat = button.dataset.format;
      syncFormatButtons();
      elements.hfOptions.hidden = state.currentFormat !== "hf-readme";
    });
  }

  for (const button of elements.tabButtons) {
    button.addEventListener("click", () => {
      setActiveTab(button.dataset.tab);
    });
  }
}

async function boot() {
  bindEvents();
  syncFormatButtons();
  setActiveTab("overview");
  await loadRoots();
}

async function loadRoots() {
  const payload = await fetchJson("/api/fs/roots");
  const roots = Array.isArray(payload.roots) ? payload.roots : [];

  elements.rootSelect.innerHTML = "";
  for (const root of roots) {
    const option = document.createElement("option");
    option.value = root;
    option.textContent = root;
    elements.rootSelect.append(option);
  }

  if (roots.length > 0) {
    await loadDirectory(roots[0]);
  } else {
    elements.browserPath.textContent = "No filesystem roots were found.";
    elements.browserList.innerHTML = "";
  }
}

async function loadDirectory(path) {
  elements.browserPath.textContent = `Loading ${path}...`;
  const payload = await fetchJson(`/api/fs/list?path=${encodeURIComponent(path)}`);

  state.currentPath = payload.path;
  state.parentPath = payload.parent;
  elements.rootSelect.value = findClosestRoot(payload.path);
  elements.browserPath.textContent = payload.path;
  elements.upButton.disabled = !payload.parent;

  renderBrowserEntries(Array.isArray(payload.entries) ? payload.entries : []);
}

async function runScan() {
  const path = elements.scanPath.value.trim();
  if (!path) {
    showMessage("Enter a file or folder path first.", "error");
    return;
  }

  setBusy(true);

  try {
    const body = {
      path,
      format: state.currentFormat,
      compute_hash: elements.hashToggle.checked,
    };

    if (state.currentFormat === "hf-readme") {
      const hfTitle = elements.hfTitle.value.trim();
      const hfShortDescription = elements.hfShortDescription.value.trim();
      const hfSdk = elements.hfSdk.value;
      const hfAppFile = elements.hfAppFile.value.trim();
      const hfAppPortRaw = elements.hfAppPort.value.trim();

      if (hfTitle) body.hf_title = hfTitle;
      if (hfShortDescription) body.hf_short_description = hfShortDescription;
      if (hfSdk) body.hf_sdk = hfSdk;
      if (hfAppFile) body.hf_app_file = hfAppFile;
      if (hfAppPortRaw) body.hf_app_port = parseInt(hfAppPortRaw, 10);
    }

    const payload = await fetchJson("/api/scan", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(body),
    });

    state.selectedPath = payload.selected_path;
    state.renderedOutput = payload.rendered_output;
    state.documents = Array.isArray(payload.documents) ? payload.documents : [];
    state.summary = payload.summary ?? null;

    renderResults();
    showMessage(`Scan complete for ${payload.selected_path}`, "success");
  } catch (error) {
    showMessage(error.message, "error");
  } finally {
    setBusy(false);
  }
}

function renderBrowserEntries(entries) {
  elements.browserList.innerHTML = "";

  if (entries.length === 0) {
    const empty = document.createElement("div");
    empty.className = "browser-item";
    empty.innerHTML = "<strong>No folders or supported model files were found here.</strong>";
    elements.browserList.append(empty);
    return;
  }

  for (const entry of entries) {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "browser-item";
    button.dataset.kind = entry.kind;

    const icon = document.createElement("span");
    icon.className = "browser-icon";
    icon.textContent = entry.kind === "directory" ? "Folder" : "Model";

    const content = document.createElement("div");
    const title = document.createElement("strong");
    title.textContent = entry.name;
    const subtitle = document.createElement("span");
    subtitle.className = "subtle";
    subtitle.textContent = entry.path;
    content.append(title, subtitle);

    const action = document.createElement("span");
    action.textContent = entry.kind === "directory" ? "Open" : "Select";

    button.append(icon, content, action);
    button.addEventListener("click", () => {
      if (entry.kind === "directory") {
        void loadDirectory(entry.path);
        return;
      }

      elements.scanPath.value = entry.path;
      showMessage(`Ready to scan ${entry.name}`, "success");
    });

    elements.browserList.append(button);
  }
}

function renderResults() {
  elements.emptyState.hidden = true;
  elements.resultsPanel.hidden = false;
  elements.copyOutput.disabled = false;
  elements.downloadOutput.disabled = false;
  elements.rawOutput.textContent = state.renderedOutput;

  renderSummary();
  renderDocuments();
  renderWarnings();
}

function renderSummary() {
  elements.summaryGrid.innerHTML = "";

  const cards = [
    {
      label: "Models found",
      value: formatInteger(state.summary?.model_count ?? 0),
    },
    {
      label: "Total size",
      value: formatBytes(state.summary?.total_size_bytes ?? 0),
    },
    {
      label: "Formats",
      value: (state.summary?.formats ?? []).join(", ").toUpperCase() || "None",
    },
    {
      label: "Warnings",
      value: formatInteger(state.summary?.warning_count ?? 0),
    },
  ];

  for (const card of cards) {
    const node = document.createElement("section");
    node.className = "summary-card";

    const label = document.createElement("span");
    label.className = "subtle";
    label.textContent = card.label;

    const value = document.createElement("strong");
    value.textContent = card.value;

    node.append(label, value);
    elements.summaryGrid.append(node);
  }
}

function renderDocuments() {
  elements.documentGrid.innerHTML = "";

  if (state.documents.length === 0) {
    const empty = document.createElement("div");
    empty.className = "document-card";

    const title = document.createElement("h3");
    title.textContent = "No model files found";

    const body = document.createElement("p");
    body.textContent = "The selected directory did not contain any supported GGUF or safetensors files.";

    empty.append(title, body);
    elements.documentGrid.append(empty);
    return;
  }

  for (const documentData of state.documents) {
    const card = document.createElement("article");
    card.className = "document-card";

    const title = document.createElement("h3");
    title.textContent = documentData.model_filename;

    const subtitle = document.createElement("p");
    subtitle.textContent = documentData.model_path;

    const meta = document.createElement("div");
    meta.className = "document-meta";

    const facts = [
      ["Format", documentData.format?.toUpperCase() ?? "UNKNOWN"],
      ["Architecture", documentData.architecture || "Unknown"],
      ["Parameters", formatOptionalNumber(documentData.parameter_count)],
      ["Quantization", documentData.quantization || "Unknown"],
      ["Dtype", documentData.dtype || "Unknown"],
      ["Context", formatOptionalNumber(documentData.context_length)],
      ["Vocab", formatOptionalNumber(documentData.vocab_size)],
      ["Size", formatBytes(documentData.file_size_bytes)],
      ["Base model", documentData.base_model || "Unknown"],
    ];

    for (const [label, value] of facts) {
      const row = document.createElement("div");
      row.className = "meta-row";

      const left = document.createElement("span");
      left.textContent = label;

      const right = document.createElement("span");
      right.textContent = value;

      row.append(left, right);
      meta.append(row);
    }

    card.append(title, subtitle, meta);
    elements.documentGrid.append(card);
  }
}

function renderWarnings() {
  elements.warningList.innerHTML = "";

  const warnings = [];
  for (const documentData of state.documents) {
    for (const warning of documentData.warnings ?? []) {
      warnings.push(`${documentData.model_filename}: ${warning}`);
    }
  }

  elements.warningCount.textContent = formatInteger(warnings.length);

  if (warnings.length === 0) {
    const clean = document.createElement("div");
    clean.className = "warning-item";
    clean.textContent = "No warnings were reported for this scan.";
    elements.warningList.append(clean);
    return;
  }

  for (const warning of warnings) {
    const item = document.createElement("div");
    item.className = "warning-item";
    item.textContent = warning;
    elements.warningList.append(item);
  }
}

function setBusy(isBusy) {
  elements.scanButton.disabled = isBusy;
  elements.copyOutput.disabled = isBusy || !state.renderedOutput;
  elements.downloadOutput.disabled = isBusy || !state.renderedOutput;
  elements.scanButton.textContent = isBusy ? "Scanning..." : "Scan now";
}

function setActiveTab(tabName) {
  for (const button of elements.tabButtons) {
    button.classList.toggle("active", button.dataset.tab === tabName);
  }

  elements.overviewTab.classList.toggle("active", tabName === "overview");
  elements.rawTab.classList.toggle("active", tabName === "raw");
}

function syncFormatButtons() {
  for (const button of elements.formatButtons) {
    button.classList.toggle("active", button.dataset.format === state.currentFormat);
  }
}

function showMessage(message, tone = "info") {
  elements.message.hidden = false;
  elements.message.className = `message ${tone}`;
  elements.message.textContent = message;
}

async function fetchJson(url, options) {
  const response = await fetch(url, options);
  const payload = await response.json();

  if (!response.ok) {
    throw new Error(payload.error || "The request failed.");
  }

  return payload;
}

function findClosestRoot(path) {
  for (const option of Array.from(elements.rootSelect.options)) {
    if (path.toLowerCase().startsWith(option.value.toLowerCase())) {
      return option.value;
    }
  }

  return elements.rootSelect.options[0]?.value ?? "";
}

async function copyText(value) {
  if (!navigator.clipboard) {
    return false;
  }

  try {
    await navigator.clipboard.writeText(value);
  } catch {
    return false;
  }

  return true;
}

function formatInteger(value) {
  return new Intl.NumberFormat().format(value);
}

function formatOptionalNumber(value) {
  return typeof value === "number" ? formatInteger(value) : "Unknown";
}

function formatBytes(bytes) {
  if (!bytes) {
    return "0 B";
  }

  const units = ["B", "KB", "MB", "GB", "TB", "PB"];
  const exponent = Math.min(Math.floor(Math.log(bytes) / Math.log(1024)), units.length - 1);
  const amount = bytes / 1024 ** exponent;
  return `${amount.toFixed(amount >= 100 || exponent === 0 ? 0 : 1)} ${units[exponent]}`;
}
