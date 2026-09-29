(function () {
  "use strict";

  const STORAGE_KEYS = {
    apiBase: "nutriflow.apiBase",
    planId: "nutriflow.planId",
    patientName: "nutriflow.patientName",
    mealsFound: "nutriflow.mealsFound",
    plans: "nutriflow.plans",
    selectedMeals: "nutriflow.selectedMeals",
    substitutionChoices: "nutriflow.substitutionChoices",
    leftoversGrams: "nutriflow.leftoversGrams",
    days: "nutriflow.days",
  };

  const CATEGORY_ORDER = [
    "suplementos", "proteínas", "carboidratos", "frutas",
    "verduras e legumes", "laticínios", "gorduras", "outros",
  ];
  const CATEGORY_COLOR_VAR = {
    "suplementos": "--cat-suplementos",
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
  const jsonTab = el("jsonTab");
  const pdfTab = el("pdfTab");
  const uploadDescription = el("uploadDescription");

  const planSection = el("planSection");
  const patientNameEl = el("patientName");
  const planMetaEl = el("planMeta");
  const addPlansBtn = el("addPlansBtn");
  const changePlanBtn = el("changePlanBtn");
  const mealOptions = el("mealOptions");
  const mealSelectionSummary = el("mealSelectionSummary");
  const selectAllMealsBtn = el("selectAllMealsBtn");
  const mealSelectionError = el("mealSelectionError");

  const daysInput = el("daysInput");
  const daysMinus = el("daysMinus");
  const daysPlus = el("daysPlus");
  const refreshBtn = el("refreshBtn");
  const leftoversToggle = el("leftoversToggle");

  const progressText = el("progressText");
  const progressFill = el("progressFill");

  const listContainer = el("listContainer");
  const shoppingHeading = el("shoppingHeading");
  const leftoverColumnHeader = el("leftoverColumnHeader");
  const substitutionPanel = el("substitutionPanel");
  const substitutionOptions = el("substitutionOptions");
  const listError = el("listError");

  const copyTextBtn = el("copyTextBtn");
  const downloadJsonBtn = el("downloadJsonBtn");

  const toastEl = el("toast");

  let currentCategories = null; // último resultado carregado da API
  let plans = [];
  let availableMeals = [];
  let selectedMeals = [];
  let substitutionChoices = {};
  let leftoversGrams = {};
  let uploadMode = "json";
  let isUpdatingList = false;

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

  function friendlyUploadError(status, detail, contentType) {
    if (status === 422) return contentType === "application/pdf"
      ? "Não foi possível processar este PDF. Confira se é um plano alimentar exportado pelo WebDiet."
      : "Não foi possível ler esse arquivo. Confira se é um JSON de plano alimentar válido.";
    if (status === 415) return "Formato incompatível. Selecione um arquivo PDF ou JSON.";
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

  function getStoredPlans() {
    try {
      const stored = JSON.parse(localStorage.getItem(STORAGE_KEYS.plans) || "null");
      if (Array.isArray(stored) && stored.length) return stored;
    } catch (_) {}

    const planId = localStorage.getItem(STORAGE_KEYS.planId);
    return planId ? [{
      plan_id: planId,
      patient_name: localStorage.getItem(STORAGE_KEYS.patientName) || "",
      meals_found: Number(localStorage.getItem(STORAGE_KEYS.mealsFound) || 0),
    }] : [];
  }

  function savePlans(newPlans, append) {
    const combined = append ? [...getStoredPlans()] : [];
    newPlans.forEach((plan) => {
      if (!combined.some((existing) => existing.plan_id === plan.plan_id)) combined.push(plan);
    });
    plans = combined;
    localStorage.setItem(STORAGE_KEYS.plans, JSON.stringify(plans));
    localStorage.setItem(STORAGE_KEYS.planId, plans[0].plan_id);
    localStorage.setItem(
      STORAGE_KEYS.patientName,
      plans.map((plan) => plan.patient_name).filter(Boolean).join(" + ")
    );
    localStorage.setItem(
      STORAGE_KEYS.mealsFound,
      String(plans.reduce((total, plan) => total + plan.meals_found, 0))
    );
    return plans;
  }

  function clearPlan() {
    localStorage.removeItem(STORAGE_KEYS.planId);
    localStorage.removeItem(STORAGE_KEYS.patientName);
    localStorage.removeItem(STORAGE_KEYS.mealsFound);
    localStorage.removeItem(STORAGE_KEYS.plans);
    localStorage.removeItem(STORAGE_KEYS.selectedMeals);
    localStorage.removeItem(STORAGE_KEYS.substitutionChoices);
    localStorage.removeItem(STORAGE_KEYS.leftoversGrams);
    plans = [];
    availableMeals = [];
    selectedMeals = [];
    substitutionChoices = {};
    leftoversGrams = {};
  }

  function getStoredPlanId() {
    return getStoredPlanIds()[0] || null;
  }

  function getStoredPlanIds() {
    return plans.length ? plans.map((plan) => plan.plan_id) : getStoredPlans().map((plan) => plan.plan_id);
  }

  function appendAdditionalPlanIds(params) {
    getStoredPlanIds().slice(1).forEach((planId) => params.append("additional_plan_ids", planId));
    return params;
  }

  // ---------- telas ----------

  function showUploadScreen() {
    uploadSection.style.display = "block";
    planSection.style.display = "none";
    showError(uploadError, null);
  }

  function showPlanScreen() {
    uploadSection.style.display = "none";
    planSection.style.display = "block";
    patientNameEl.textContent = plans.map((plan) => plan.patient_name).filter(Boolean).join(" + ") || "Planos importados";
    const mealCount = plans.reduce((total, plan) => total + plan.meals_found, 0);
    const planLabel = plans.length === 1 ? "plano" : "planos";
    planMetaEl.textContent = `${plans.length} ${planLabel} · ${mealCount} refeições encontradas`;
    planSection.dataset.planId = plans[0].plan_id;
  }

  // ---------- upload ----------

  function setUploadMode(mode) {
    uploadMode = mode;
    const isPdf = mode === "pdf";
    jsonTab.classList.toggle("active", !isPdf);
    pdfTab.classList.toggle("active", isPdf);
    jsonTab.setAttribute("aria-selected", String(!isPdf));
    pdfTab.setAttribute("aria-selected", String(isPdf));
    fileInput.accept = isPdf ? "application/pdf,.pdf" : "application/json,.json";
    pickFileBtn.textContent = isPdf ? "Selecionar dietas PDF" : "Selecionar dietas JSON";
    uploadDescription.textContent = isPdf
      ? "Selecione um ou mais PDFs de planos alimentares exportados pelo WebDiet."
      : "Selecione uma ou mais dietas em JSON para somar as compras da casa.";
    showError(uploadError, null);
  }

  jsonTab.addEventListener("click", () => setUploadMode("json"));
  pdfTab.addEventListener("click", () => setUploadMode("pdf"));
  pickFileBtn.addEventListener("click", () => {
    fileInput.accept = uploadMode === "pdf" ? "application/pdf,.pdf" : "application/json,.json";
    fileInput.click();
  });
  addPlansBtn.addEventListener("click", () => {
    fileInput.accept = "application/pdf,.pdf,application/json,.json";
    fileInput.click();
  });

  ["dragover", "dragleave", "drop"].forEach((evt) => {
    uploadSection.addEventListener(evt, (e) => {
      e.preventDefault();
      uploadSection.classList.toggle("drag", evt === "dragover");
    });
  });
  uploadSection.addEventListener("drop", (e) => {
    const files = e.dataTransfer.files;
    if (files && files.length) handleUpload(files);
  });

  fileInput.addEventListener("change", () => {
    if (fileInput.files.length) handleUpload(fileInput.files);
    fileInput.value = "";
  });

  async function handleUpload(fileList) {
    const files = Array.from(fileList || []);
    if (!files.length) return;

    showError(uploadError, null);
    const invalidFile = files.find((file) => !/\.(pdf|json)$/i.test(file.name));
    if (invalidFile) {
      showError(uploadError, `${invalidFile.name}: selecione um arquivo PDF ou JSON.`);
      return;
    }

    const append = getStoredPlanIds().length > 0;
    pickFileBtn.disabled = true;
    addPlansBtn.disabled = true;
    pickFileBtn.textContent = "Enviando dietas...";
    addPlansBtn.textContent = "Enviando...";
    const importedPlans = [];
    const failedFiles = [];

    try {
      for (const file of files) {
        const formData = new FormData();
        const contentType = file.name.toLowerCase().endsWith(".pdf")
          ? "application/pdf"
          : "application/json";
        formData.append("file", new File([file], file.name, { type: contentType }));
        try {
          const response = await apiFetch("/api/v1/upload", { method: "POST", body: formData });
          const body = await response.json().catch(() => ({}));
          if (!response.ok) {
            throw new ApiError(
              response.status,
              friendlyUploadError(response.status, body.detail, contentType)
            );
          }
          importedPlans.push({
            plan_id: body.plan_id,
            patient_name: body.patient_name || file.name,
            meals_found: body.meals_found || 0,
          });
        } catch (error) {
          failedFiles.push(`${file.name}: ${error.message}`);
        }
      }

      if (!importedPlans.length) {
        const message = failedFiles.join(" ");
        showError(append ? listError : uploadError, message);
        return;
      }

      if (!append) {
        localStorage.removeItem(STORAGE_KEYS.selectedMeals);
        localStorage.removeItem(STORAGE_KEYS.substitutionChoices);
        localStorage.removeItem(STORAGE_KEYS.leftoversGrams);
        substitutionChoices = {};
        leftoversGrams = {};
      }
      const previousMeals = [...availableMeals];
      const previousSelection = [...selectedMeals];
      savePlans(importedPlans, append);
      showPlanScreen();
      await loadPlanMeals(getStoredPlanId(), {
        previousMeals: append ? previousMeals : [],
        previousSelection: append ? previousSelection : null,
      });
      const successMessage = importedPlans.length === 1
        ? "Dieta adicionada à compra da casa"
        : `${importedPlans.length} dietas adicionadas à compra da casa`;
      showToast(failedFiles.length ? `${successMessage}; ${failedFiles.length} arquivo(s) falharam.` : successMessage, failedFiles.length > 0);
      if (failedFiles.length) showError(listError, failedFiles.join(" "));
    } catch (err) {
      showError(uploadError, err.message);
    } finally {
      pickFileBtn.disabled = false;
      addPlansBtn.disabled = false;
      pickFileBtn.textContent = `Selecionar dietas ${uploadMode.toUpperCase()}`;
      addPlansBtn.textContent = "Adicionar dieta";
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
    return Math.min(31, Math.max(1, n));
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
  leftoversToggle.addEventListener("click", () => {
    const isOpen = listContainer.classList.toggle("show-leftovers");
    leftoverColumnHeader.hidden = !isOpen;
    leftoversToggle.setAttribute("aria-pressed", String(isOpen));
    leftoversToggle.textContent = isOpen ? "Ocultar sobras" : "Sobrou?";
  });

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

  async function loadPlanMeals(planId, selectionContext = {}) {
    showError(listError, null);
    mealSelectionSummary.textContent = "Carregando refeições...";
    try {
      const mealParams = appendAdditionalPlanIds(new URLSearchParams());
      const response = await apiFetch(`/api/v1/plans/${planId}/meals?${mealParams}`);
      if (!response.ok) {
        const body = await response.json().catch(() => ({}));
        throw new ApiError(response.status, body.detail || "Não foi possível carregar as refeições.");
      }

      const body = await response.json();
      availableMeals = body.meals || [];
      const storedSelection = JSON.parse(localStorage.getItem(STORAGE_KEYS.selectedMeals) || "null");
      selectedMeals = selectionContext.previousSelection
        ? availableMeals.filter((meal) => selectionContext.previousMeals.includes(meal)
          ? selectionContext.previousSelection.includes(meal)
          : true)
        : Array.isArray(storedSelection)
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
    const cannotUpdate = isUpdatingList || selectedCount === 0 || availableMeals.length === 0;
    refreshBtn.disabled = cannotUpdate;
    showError(mealSelectionError, selectedCount === 0 ? "Selecione ao menos uma refeição." : null);
  }

  async function loadShoppingList() {
    if (isUpdatingList) return;

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
    isUpdatingList = true;
    updateMealSelectionControls();
    refreshBtn.textContent = "Atualizando...";

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
      renderList(body.categories, body.total_items, body.days, body.substitution_groups || []);
    } catch (err) {
      showError(listError, err.message);
    } finally {
      isUpdatingList = false;
      updateMealSelectionControls();
      refreshBtn.textContent = "Atualizar lista";
    }
  }

  function createListParams(days, format) {
    const params = new URLSearchParams({ days: String(days) });
    if (format) params.set("fmt", format);
    appendAdditionalPlanIds(params);
    const enteredLeftovers = Object.fromEntries(
      Object.entries(leftoversGrams).filter(([, quantity]) => quantity > 0)
    );
    if (Object.keys(enteredLeftovers).length) {
      params.set("leftovers_grams", JSON.stringify(enteredLeftovers));
    }
    const selectedChoices = Object.fromEntries(
      Object.entries(substitutionChoices).filter(([, choice]) => choice !== "default")
    );
    if (Object.keys(selectedChoices).length) {
      params.set("substitution_choices", JSON.stringify(selectedChoices));
    }
    if (selectedMeals.length !== availableMeals.length) {
      selectedMeals.forEach((meal) => params.append("meal_names", meal));
    }
    return params;
  }

  function renderList(categories, totalItems, days, substitutionGroups) {
    shoppingHeading.textContent = `Lista de compras para ${days} ${days === 1 ? "dia" : "dias"}`;
    renderSubstitutionGroups(substitutionGroups);
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

  function renderSubstitutionGroups(groups) {
    substitutionOptions.replaceChildren();
    substitutionPanel.hidden = !groups.length;

    const validChoices = {};
    groups.forEach((group) => {
      const row = document.createElement("div");
      row.className = "substitution-option";

      const label = document.createElement("label");
      const selectId = `substitution-${group.key}`;
      label.htmlFor = selectId;
      label.textContent = `${group.meal_name}: ${group.original_name}`;

      const select = document.createElement("select");
      select.id = selectId;
      select.setAttribute("aria-label", `Substituição para ${group.original_name} em ${group.meal_name}`);
      group.options.forEach((option) => {
        const element = document.createElement("option");
        element.value = option.key;
        const amount = option.unit
          ? ` · ${new Intl.NumberFormat("pt-BR", { maximumFractionDigits: 1 }).format(option.quantity)} ${option.unit}`
          : "";
        element.textContent = option.key === "default"
          ? `Padrão: ${option.name}${amount}`
          : `Substituir por: ${option.name}${amount}`;
        select.appendChild(element);
      });

      const savedChoice = substitutionChoices[group.key];
      select.value = group.options.some((option) => option.key === savedChoice)
        ? savedChoice
        : "default";
      if (select.value !== "default") validChoices[group.key] = select.value;
      select.addEventListener("change", () => {
        if (select.value === "default") delete substitutionChoices[group.key];
        else substitutionChoices[group.key] = select.value;
        localStorage.setItem(STORAGE_KEYS.substitutionChoices, JSON.stringify(substitutionChoices));
        loadShoppingList();
      });

      row.append(label, select);
      substitutionOptions.appendChild(row);
    });

    substitutionChoices = validChoices;
    localStorage.setItem(STORAGE_KEYS.substitutionChoices, JSON.stringify(substitutionChoices));
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
    const row = document.createElement("div");
    row.className = "item-row" + (item.checked ? " checked" : "");

    const checkbox = document.createElement("input");
    checkbox.type = "checkbox";
    checkbox.checked = !!item.checked;
    checkbox.setAttribute("aria-label", `Marcar ${item.name} como já tenho`);
    checkbox.addEventListener("change", () => toggleChecked(item.name, checkbox.checked, row));

    const name = document.createElement("span");
    name.className = "item-name";
    name.textContent = item.name;

    const details = document.createElement("span");
    details.className = "item-details";

    const exactQuantity = formatExactQuantity(item);
    const purchaseSuggestion = item.purchase_suggestion || "";
    if (exactQuantity) {
      const quantity = document.createElement("span");
      quantity.className = "item-quantity";
      quantity.textContent = exactQuantity;
      details.appendChild(quantity);
    }
    if (purchaseSuggestion) {
      if (exactQuantity) {
        const separator = document.createElement("span");
        separator.className = "item-separator";
        separator.setAttribute("aria-hidden", "true");
        separator.textContent = "·";
        details.appendChild(separator);
      }
      const suggestion = document.createElement("span");
      suggestion.className = "item-suggestion";
      suggestion.textContent = exactQuantity
        ? `compre ${purchaseSuggestion}`
        : purchaseSuggestion;
      details.appendChild(suggestion);
    } else if (item.unit_type === "weight_g" && item.total_quantity === 0) {
      const sufficient = document.createElement("span");
      sufficient.className = "item-suggestion";
      sufficient.textContent = "suficiente em casa";
      details.appendChild(sufficient);
    }

    row.appendChild(checkbox);
    row.appendChild(name);
    row.appendChild(details);

    if (item.unit_type === "weight_g") {
      const leftoverCell = document.createElement("div");
      leftoverCell.className = "leftover-cell";

      const leftoverInput = document.createElement("input");
      leftoverInput.className = "leftover-input";
      leftoverInput.type = "number";
      leftoverInput.min = "0";
      leftoverInput.step = "any";
      leftoverInput.inputMode = "decimal";
      leftoverInput.value = leftoversGrams[item.name] || "";
      leftoverInput.setAttribute("aria-label", `Quantidade que sobrou de ${item.name}, em gramas`);
      leftoverInput.addEventListener("change", () => {
        const rawValue = leftoverInput.value.trim();
        if (!rawValue) {
          delete leftoversGrams[item.name];
        } else {
          const quantity = Number(rawValue);
          if (!Number.isFinite(quantity) || quantity < 0) {
            leftoverInput.value = leftoversGrams[item.name] || "";
            return;
          }
          if (quantity > 0) leftoversGrams[item.name] = quantity;
          else delete leftoversGrams[item.name];
        }
        localStorage.setItem(STORAGE_KEYS.leftoversGrams, JSON.stringify(leftoversGrams));
        loadShoppingList();
      });

      const unit = document.createElement("span");
      unit.className = "leftover-unit";
      unit.textContent = "g";
      leftoverCell.append(leftoverInput, unit);
      row.appendChild(leftoverCell);
    }

    return row;
  }

  function formatExactQuantity(item) {
    if (item.unit_type === "free") return "";

    if (item.unit_type === "weight_g" && item.total_quantity >= 1000) {
      const kilograms = new Intl.NumberFormat("pt-BR", {
        maximumFractionDigits: 2,
      }).format(item.total_quantity / 1000);
      const weight = `${kilograms}kg`;
      if (item.category === "suplementos" && item.name.toLowerCase().includes("whey")) {
        if (item.total_quantity === 15) return `${weight} (meio scoop)`;
        const scoops = item.total_quantity / 30;
        const scoopText = new Intl.NumberFormat("pt-BR", {
          maximumFractionDigits: 1,
        }).format(scoops);
        return `${weight} (${scoopText} ${scoops === 1 ? "scoop" : "scoops"})`;
      }
      return weight;
    }

    const quantity = new Intl.NumberFormat("pt-BR", {
      maximumFractionDigits: 1,
    }).format(item.total_quantity);
    const unit = (item.unit || "").trim();
    if (!unit) return quantity;
    const formatted = unit === "g" || unit === "ml" ? `${quantity}${unit}` : `${quantity} ${unit}`;
    if (item.unit_type === "weight_g" && item.category === "suplementos" && item.name.toLowerCase().includes("whey")) {
      if (item.total_quantity === 15) return `${formatted} (meio scoop)`;
      const scoops = item.total_quantity / 30;
      const scoopText = new Intl.NumberFormat("pt-BR", {
        maximumFractionDigits: 1,
      }).format(scoops);
      return `${formatted} (${scoopText} ${scoops === 1 ? "scoop" : "scoops"})`;
    }
    return formatted;
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
  try {
    substitutionChoices = JSON.parse(localStorage.getItem(STORAGE_KEYS.substitutionChoices) || "{}") || {};
  } catch (_) {
    substitutionChoices = {};
  }
  try {
    leftoversGrams = JSON.parse(localStorage.getItem(STORAGE_KEYS.leftoversGrams) || "{}") || {};
  } catch (_) {
    leftoversGrams = {};
  }

  plans = getStoredPlans();
  const storedPlanId = getStoredPlanId();
  if (storedPlanId) {
    showPlanScreen();
    loadPlanMeals(storedPlanId);
  } else {
    showUploadScreen();
  }
})();
