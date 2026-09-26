(function () {
  "use strict";

  const STORAGE_KEYS = {
    apiBase: "nutriflow.apiBase",
    planId: "nutriflow.planId",
    patientName: "nutriflow.patientName",
    mealsFound: "nutriflow.mealsFound",
    selectedMeals: "nutriflow.selectedMeals",
    days: "nutriflow.days",
  };

  const CATEGORY_ORDER = [
    "proteínas", "carboidratos", "frutas",
    "verduras e legumes", "laticínios", "gorduras", "outros",
  ];
  const CATEGORY_COLOR_VAR = {
    "proteínas": "--cat-proteinas",
    "carboidratos": "--cat-carboidratos",
    "frutas": "--cat-frutas",
    "verduras e legumes": "--cat-verduras",
    "laticínios": "--cat-laticinios",
    "gorduras": "--cat-gorduras",
    "outros": "--cat-outros",
  };

  const el = (id) => document.getElementById(id);

  const settingsToggle = el("settingsToggle");
  const settingsPanel = el("settingsPanel");
  const apiBaseInput = el("apiBaseInput");

  const uploadSection = el("uploadSection");
  const pickFileBtn = el("pickFileBtn");
  const fileInput = el("fileInput");
  const uploadError = el("uploadError");

  const planSection = el("planSection");
  const patientNameEl = el("patientName");
  const planMetaEl = el("planMeta");
  const changePlanBtn = el("changePlanBtn");
  const mealOptions = el("mealOptions");
  const mealSelectionSummary = el("mealSelectionSummary");
  const selectAllMealsBtn = el("selectAllMealsBtn");
  const applyMealsBtn = el("applyMealsBtn");
  const mealSelectionError = el("mealSelectionError");

  const daysInput = el("daysInput");
  const daysMinus = el("daysMinus");
  const daysPlus = el("daysPlus");
  const refreshBtn = el("refreshBtn");

  const progressText = el("progressText");
  const progressFill = el("progressFill");

  const listContainer = el("listContainer");
  const listError = el("listError");

  const copyTextBtn = el("copyTextBtn");
  const downloadJsonBtn = el("downloadJsonBtn");

  const toastEl = el("toast");

  let currentCategories = null; // último resultado carregado da API
  let availableMeals = [];
  let selectedMeals = [];

  // ---------- utilidades ----------

  function apiBase() {
    return (apiBaseInput.value || "http://127.0.0.1:8000").replace(/\/+$/, "");
  }

  function showToast(message, isError) {
    toastEl.textContent = message;
    toastEl.classList.toggle("error", !!isError);
    toastEl.classList.add("show");
    clearTimeout(showToast._t);
    showToast._t = setTimeout(() => toastEl.classList.remove("show"), 3200);
  }

  function showError(node, message) {
    if (!message) { node.classList.remove("show"); node.textContent = ""; return; }
    node.textContent = message;
    node.classList.add("show");
  }

  async function apiFetch(path, options) {
    let response;
    try {
      response = await fetch(apiBase() + path, options);
    } catch (err) {
      throw new ApiError(
        0,
        "Não foi possível conectar à API em " + apiBase() +
        ". Verifique se o servidor está rodando e se o endereço está correto."
      );
    }
    return response;
  }

  class ApiError extends Error {
    constructor(status, message) { super(message); this.status = status; }
  }

  function friendlyUploadError(status, detail) {
    if (status === 422) return "Não foi possível ler esse arquivo. Confira se é um JSON de plano alimentar válido.";
    if (status === 415) return "Formato de arquivo não suportado. Envie um arquivo .json.";
    if (status === 501) return "Upload de PDF ainda não é suportado nesta versão. Envie o plano em formato JSON.";
    return detail || "Não foi possível importar o plano. Tente novamente.";
  }

  // ---------- estado / persistência ----------

  function loadStoredApiBase() {
    const saved = localStorage.getItem(STORAGE_KEYS.apiBase);
    if (saved) apiBaseInput.value = saved;
  }
  apiBaseInput.addEventListener("change", () => {
    localStorage.setItem(STORAGE_KEYS.apiBase, apiBaseInput.value.trim());
  });

  function savePlan(planId, patientName, mealsFound) {
    localStorage.setItem(STORAGE_KEYS.planId, planId);
    localStorage.setItem(STORAGE_KEYS.patientName, patientName || "");
    localStorage.setItem(STORAGE_KEYS.mealsFound, String(mealsFound));
  }

  function clearPlan() {
    localStorage.removeItem(STORAGE_KEYS.planId);
    localStorage.removeItem(STORAGE_KEYS.patientName);
    localStorage.removeItem(STORAGE_KEYS.mealsFound);
    localStorage.removeItem(STORAGE_KEYS.selectedMeals);
    availableMeals = [];
    selectedMeals = [];
  }

  function getStoredPlanId() {
    return localStorage.getItem(STORAGE_KEYS.planId);
  }

  // ---------- telas ----------

  function showUploadScreen() {
    uploadSection.style.display = "block";
    planSection.style.display = "none";
    showError(uploadError, null);
  }

  function showPlanScreen(planId, patientName, mealsFound) {
    uploadSection.style.display = "none";
    planSection.style.display = "block";
    patientNameEl.textContent = patientName || "Plano importado";
    planMetaEl.textContent = mealsFound + " refeição(ões) encontradas";
    planSection.dataset.planId = planId;
  }

  // ---------- upload ----------

  pickFileBtn.addEventListener("click", () => fileInput.click());

  ["dragover", "dragleave", "drop"].forEach((evt) => {
    uploadSection.addEventListener(evt, (e) => {
      e.preventDefault();
      uploadSection.classList.toggle("drag", evt === "dragover");
    });
  });
  uploadSection.addEventListener("drop", (e) => {
    const file = e.dataTransfer.files && e.dataTransfer.files[0];
    if (file) handleUpload(file);
  });

  fileInput.addEventListener("change", () => {
    const file = fileInput.files[0];
    if (file) handleUpload(file);
    fileInput.value = "";
  });

  async function handleUpload(file) {
    showError(uploadError, null);
    pickFileBtn.disabled = true;
    pickFileBtn.textContent = "Enviando...";

    const formData = new FormData();
    formData.append("file", file, file.name || "plano.json");

    try {
      const response = await apiFetch("/api/v1/upload", { method: "POST", body: formData });
      const body = await response.json().catch(() => ({}));

      if (!response.ok) {
        throw new ApiError(response.status, friendlyUploadError(response.status, body.detail));
      }

      localStorage.removeItem(STORAGE_KEYS.selectedMeals);
      savePlan(body.plan_id, body.patient_name, body.meals_found);
      showPlanScreen(body.plan_id, body.patient_name, body.meals_found);
      showToast(body.message || "Plano importado com sucesso");
      await loadPlanMeals(body.plan_id);
    } catch (err) {
      showError(uploadError, err.message);
    } finally {
      pickFileBtn.disabled = false;
      pickFileBtn.textContent = "Selecionar arquivo JSON";
    }
  }

  changePlanBtn.addEventListener("click", () => {
    clearPlan();
    currentCategories = null;
    showUploadScreen();
  });

  // ---------- dias / lista ----------

  function clampDays(value) {
    let n = parseInt(value, 10);
    if (isNaN(n)) n = 7;
    return Math.min(30, Math.max(1, n));
  }

  daysMinus.addEventListener("click", () => {
    daysInput.value = clampDays(Number(daysInput.value) - 1);
  });
  daysPlus.addEventListener("click", () => {
    daysInput.value = clampDays(Number(daysInput.value) + 1);
  });
  daysInput.addEventListener("blur", () => {
    daysInput.value = clampDays(daysInput.value);
  });

  refreshBtn.addEventListener("click", loadShoppingList);
  applyMealsBtn.addEventListener("click", loadShoppingList);

  mealOptions.addEventListener("change", () => {
    selectedMeals = Array.from(
      mealOptions.querySelectorAll('input[type="checkbox"]:checked')
    ).map((checkbox) => checkbox.value);
    localStorage.setItem(STORAGE_KEYS.selectedMeals, JSON.stringify(selectedMeals));
    updateMealSelectionControls();
  });

  selectAllMealsBtn.addEventListener("click", () => {
    const selectAll = selectedMeals.length !== availableMeals.length;
    selectedMeals = selectAll ? [...availableMeals] : [];
    localStorage.setItem(STORAGE_KEYS.selectedMeals, JSON.stringify(selectedMeals));
    renderMealOptions();
  });

  async function loadPlanMeals(planId) {
    showError(listError, null);
    mealSelectionSummary.textContent = "Carregando refeições...";
    try {
      const response = await apiFetch(`/api/v1/plans/${planId}/meals`);
      if (!response.ok) {
        const body = await response.json().catch(() => ({}));
        throw new ApiError(response.status, body.detail || "Não foi possível carregar as refeições.");
      }

      const body = await response.json();
      availableMeals = body.meals || [];
      const storedSelection = JSON.parse(localStorage.getItem(STORAGE_KEYS.selectedMeals) || "null");
      selectedMeals = Array.isArray(storedSelection)
        ? availableMeals.filter((meal) => storedSelection.includes(meal))
        : [...availableMeals];
      localStorage.setItem(STORAGE_KEYS.selectedMeals, JSON.stringify(selectedMeals));
      renderMealOptions();
      await loadShoppingList();
    } catch (err) {
      showError(listError, err.message);
      mealSelectionSummary.textContent = "Não foi possível carregar as refeições.";
    }
  }

  function renderMealOptions() {
    mealOptions.replaceChildren();
    availableMeals.forEach((meal) => {
      const label = document.createElement("label");
      label.className = "meal-option";
      const checkbox = document.createElement("input");
      checkbox.type = "checkbox";
      checkbox.value = meal;
      checkbox.checked = selectedMeals.includes(meal);
      const name = document.createElement("span");
      name.textContent = meal;
      label.append(checkbox, name);
      mealOptions.appendChild(label);
    });
    updateMealSelectionControls();
  }

  function updateMealSelectionControls() {
    const selectedCount = selectedMeals.length;
    mealSelectionSummary.textContent = `${selectedCount} de ${availableMeals.length} refeições selecionadas`;
    selectAllMealsBtn.textContent = selectedCount === availableMeals.length
      ? "Desmarcar todas"
      : "Selecionar todas";
    selectAllMealsBtn.disabled = availableMeals.length === 0;
    applyMealsBtn.disabled = selectedCount === 0 || availableMeals.length === 0;
    showError(mealSelectionError, selectedCount === 0 ? "Selecione ao menos uma refeição." : null);
  }

  async function loadShoppingList() {
    const planId = getStoredPlanId();
    if (!planId) return;

    const days = clampDays(daysInput.value);
    if (selectedMeals.length === 0) {
      showError(mealSelectionError, "Selecione ao menos uma refeição.");
      return;
    }
    daysInput.value = days;
    localStorage.setItem(STORAGE_KEYS.days, String(days));

    showError(listError, null);
    refreshBtn.disabled = true;
    refreshBtn.textContent = "Calculando...";

    try {
      const params = createListParams(days);
      const response = await apiFetch(`/api/v1/shopping/${planId}?${params}`);
      if (response.status === 404) {
        clearPlan();
        showUploadScreen();
        showToast("Este plano não foi encontrado. Envie o arquivo novamente.", true);
        return;
      }
      if (!response.ok) {
        const body = await response.json().catch(() => ({}));
        throw new ApiError(response.status, body.detail || "Não foi possível calcular a lista.");
      }

      const body = await response.json();
      currentCategories = body.categories;
      renderList(body.categories, body.total_items);
    } catch (err) {
      showError(listError, err.message);
    } finally {
      refreshBtn.disabled = false;
      refreshBtn.textContent = "Atualizar lista";
    }
  }

  function createListParams(days, format) {
    const params = new URLSearchParams({ days: String(days) });
    if (format) params.set("fmt", format);
    if (selectedMeals.length !== availableMeals.length) {
      selectedMeals.forEach((meal) => params.append("meal_names", meal));
    }
    return params;
  }

  function renderList(categories, totalItems) {
    listContainer.innerHTML = "";
    listContainer.classList.remove("revealed");

    const names = Object.keys(categories || {});
    if (names.length === 0) {
      listContainer.innerHTML = '<div class="empty-list">Nenhum item encontrado neste plano para o período selecionado.</div>';
    } else {
      names
        .sort((a, b) => {
          const ia = CATEGORY_ORDER.indexOf(a), ib = CATEGORY_ORDER.indexOf(b);
          return (ia === -1 ? 99 : ia) - (ib === -1 ? 99 : ib);
        })
        .forEach((category) => {
          listContainer.appendChild(renderCategory(category, categories[category]));
        });
    }

    updateProgress();
    // uma única revelação orquestrada da lista inteira
    requestAnimationFrame(() => listContainer.classList.add("revealed"));
  }

  function renderCategory(category, items) {
    const section = document.createElement("div");
    section.className = "category";
    const colorVar = CATEGORY_COLOR_VAR[category] || "--cat-outros";
    section.style.setProperty("--cat-color", `var(${colorVar})`);

    const header = document.createElement("div");
    header.className = "category-header";
    header.innerHTML = `<h3>${escapeHtml(category)}</h3><span>${items.length} ${items.length === 1 ? "item" : "itens"}</span>`;
    section.appendChild(header);

    items.forEach((item) => section.appendChild(renderItemRow(item)));
    return section;
  }

  function renderItemRow(item) {
    const row = document.createElement("label");
    row.className = "item-row" + (item.checked ? " checked" : "");

    const checkbox = document.createElement("input");
    checkbox.type = "checkbox";
    checkbox.checked = !!item.checked;
    checkbox.addEventListener("change", () => toggleChecked(item.name, checkbox.checked, row));

    const name = document.createElement("span");
    name.className = "item-name";
    name.textContent = item.name;

    const suggestion = document.createElement("span");
    suggestion.className = "item-suggestion";
    suggestion.textContent = item.purchase_suggestion || "";

    row.appendChild(checkbox);
    row.appendChild(name);
    row.appendChild(suggestion);
    return row;
  }

  function updateProgress() {
    if (!currentCategories) { progressText.textContent = "0 de 0 itens marcados"; progressFill.style.width = "0%"; return; }
    const all = Object.values(currentCategories).flat();
    const checked = all.filter((i) => i.checked).length;
    progressText.textContent = `${checked} de ${all.length} itens marcados`;
    progressFill.style.width = all.length ? `${(checked / all.length) * 100}%` : "0%";
  }

  async function toggleChecked(itemName, checked, rowEl) {
    const planId = getStoredPlanId();
    rowEl.classList.toggle("checked", checked);

    // atualiza estado local otimisticamente
    if (currentCategories) {
      Object.values(currentCategories).flat().forEach((i) => {
        if (i.name === itemName) i.checked = checked;
      });
      updateProgress();
    }

    try {
      const response = await apiFetch(`/api/v1/checklist/${planId}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ item_name: itemName, checked }),
      });
      if (!response.ok) throw new ApiError(response.status, "Não foi possível salvar essa marcação.");
    } catch (err) {
      // reverte em caso de falha
      rowEl.classList.toggle("checked", !checked);
      rowEl.querySelector('input[type="checkbox"]').checked = !checked;
      if (currentCategories) {
        Object.values(currentCategories).flat().forEach((i) => {
          if (i.name === itemName) i.checked = !checked;
        });
        updateProgress();
      }
      showToast(err.message, true);
    }
  }

  // ---------- exportação ----------

  copyTextBtn.addEventListener("click", async () => {
    const planId = getStoredPlanId();
    const days = clampDays(daysInput.value);
    if (selectedMeals.length === 0) { showToast("Selecione ao menos uma refeição.", true); return; }
    try {
      const params = createListParams(days, "text");
      const response = await apiFetch(`/api/v1/shopping/${planId}/export?${params}`);
      if (!response.ok) throw new ApiError(response.status, "Não foi possível gerar a lista em texto.");
      const text = await response.text();
      await navigator.clipboard.writeText(text);
      showToast("Lista copiada para a área de transferência");
    } catch (err) {
      showToast(err.message || "Não foi possível copiar a lista.", true);
    }
  });

  downloadJsonBtn.addEventListener("click", async () => {
    const planId = getStoredPlanId();
    const days = clampDays(daysInput.value);
    if (selectedMeals.length === 0) { showToast("Selecione ao menos uma refeição.", true); return; }
    try {
      const params = createListParams(days, "json");
      const response = await apiFetch(`/api/v1/shopping/${planId}/export?${params}`);
      if (!response.ok) throw new ApiError(response.status, "Não foi possível gerar o JSON.");
      const blob = await response.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `lista-de-compras-${days}dias.json`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
    } catch (err) {
      showToast(err.message || "Não foi possível baixar o JSON.", true);
    }
  });

  // ---------- helpers ----------

  function escapeHtml(str) {
    const div = document.createElement("div");
    div.textContent = str;
    return div.innerHTML;
  }

  settingsToggle.addEventListener("click", () => settingsPanel.classList.toggle("open"));

  // ---------- inicialização ----------

  loadStoredApiBase();

  const storedDays = localStorage.getItem(STORAGE_KEYS.days);
  if (storedDays) daysInput.value = clampDays(storedDays);

  const storedPlanId = getStoredPlanId();
  if (storedPlanId) {
    showPlanScreen(
      storedPlanId,
      localStorage.getItem(STORAGE_KEYS.patientName),
      localStorage.getItem(STORAGE_KEYS.mealsFound)
    );
    loadPlanMeals(storedPlanId);
  } else {
    showUploadScreen();
  }
})();
