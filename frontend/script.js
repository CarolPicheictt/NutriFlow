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
    mealPrepMeals: "nutriflow.mealPrepMeals",
    mealPrepDays: "nutriflow.mealPrepDays",
    considerCookingFactor: "nutriflow.considerCookingFactor",
    planData: "nutriflow.planData",   // cópia local do JSON de cada plano
    checklist: "nutriflow.checklist", // itens marcados por plano
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
  const cookingFactorToggle = el("cookingFactorToggle");

  const progressText = el("progressText");
  const progressFill = el("progressFill");

  const listContainer = el("listContainer");
  const shoppingHeading = el("shoppingHeading");
  const leftoverColumnHeader = el("leftoverColumnHeader");
  const substitutionPanel = el("substitutionPanel");
  const substitutionOptions = el("substitutionOptions");
  const listError = el("listError");

  const copyTextBtn = el("copyTextBtn");

  const toastEl = el("toast");

  const mealPrepSection = el("mealPrepSection");
  const openMealPrepBtn = el("openMealPrepBtn");
  const mealPrepBackBtn = el("mealPrepBackBtn");
  const mealPrepMealOptions = el("mealPrepMealOptions");
  const mealPrepMealSummary = el("mealPrepMealSummary");
  const mealPrepMealError = el("mealPrepMealError");
  const mealPrepDaysInput = el("mealPrepDaysInput");
  const mealPrepDaysMinus = el("mealPrepDaysMinus");
  const mealPrepDaysPlus = el("mealPrepDaysPlus");
  const mealPrepRefreshBtn = el("mealPrepRefreshBtn");
  const mealPrepError = el("mealPrepError");
  const mealPrepResult = el("mealPrepResult");
  const mealPrepHeading = el("mealPrepHeading");
  const mealPrepCookList = el("mealPrepCookList");
  const mealPrepAssemblyList = el("mealPrepAssemblyList");
  const mealPrepNotes = el("mealPrepNotes");
  const mealPrepCopyBtn = el("mealPrepCopyBtn");

  let currentCategories = null; // último resultado carregado da API
  let plans = [];
  let availableMeals = [];
  let selectedMeals = [];
  let currentSubstitutionGroups = [];
  let substitutionChoices = {};
  let leftoversGrams = {};
  let uploadMode = "pdf";
  let isUpdatingList = false;
  cookingFactorToggle.checked = localStorage.getItem(STORAGE_KEYS.considerCookingFactor) === "true";

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

  // ---------- cópia local dos planos (localStorage) ----------
  // O servidor pode "esquecer" os planos (reinício, plano gratuito que dorme).
  // A cópia que vale fica aqui no navegador e é reenviada quando necessário.

  const UUID_RE = /[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/gi;

  function readStoredJson(key, fallback) {
    try {
      const value = JSON.parse(localStorage.getItem(key) || "null");
      return value === null || value === undefined ? fallback : value;
    } catch (_) {
      return fallback;
    }
  }

  function writeStoredJson(key, value) {
    try {
      localStorage.setItem(key, JSON.stringify(value));
      return true;
    } catch (_) {
      return false; // cota cheia ou armazenamento bloqueado: o app segue sem a cópia
    }
  }

  async function cachePlanFromServer(planId) {
    try {
      const response = await fetch(apiBase() + "/api/v1/plans/" + planId);
      if (!response.ok) return;
      const cache = readStoredJson(STORAGE_KEYS.planData, {});
      cache[planId] = await response.json();
      writeStoredJson(STORAGE_KEYS.planData, cache);
    } catch (_) {}
  }

  function saveChecklistState(planId, itemName, checked) {
    const all = readStoredJson(STORAGE_KEYS.checklist, {});
    const items = new Set(all[planId] || []);
    if (checked) items.add(itemName); else items.delete(itemName);
    all[planId] = [...items];
    writeStoredJson(STORAGE_KEYS.checklist, all);
  }

  // Reenvia ao servidor os planos (e itens marcados) citados na URL que
  // existem na cópia local. Retorna true se ao menos um plano foi restaurado.
  async function restorePlansFromCache(path) {
    const ids = [...new Set((path.match(UUID_RE) || []).map((id) => id.toLowerCase()))];
    const cache = readStoredJson(STORAGE_KEYS.planData, {});
    const checklist = readStoredJson(STORAGE_KEYS.checklist, {});
    const jsonHeaders = { "Content-Type": "application/json" };
    let restored = false;

    for (const id of ids) {
      if (!cache[id]) continue;
      try {
        const response = await fetch(apiBase() + "/api/v1/plans/" + id, {
          method: "PUT",
          headers: jsonHeaders,
          body: JSON.stringify(cache[id]),
        });
        if (!response.ok) continue;
        restored = true;
        await Promise.all((checklist[id] || []).map((itemName) =>
          fetch(apiBase() + "/api/v1/checklist/" + id, {
            method: "PATCH",
            headers: jsonHeaders,
            body: JSON.stringify({ item_name: itemName, checked: true }),
          }).catch(() => null)
        ));
      } catch (_) {}
    }
    return restored;
  }

  async function apiFetch(path, options) {
    let response;
    try {
      response = await fetch(apiBase() + path, options);
      if (response.status === 404 && await restorePlansFromCache(path)) {
        response = await fetch(apiBase() + path, options); // tenta de novo, uma vez
      }
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
    if (saved) {
      apiBaseInput.value = saved;
    } else if (/^https?:$/.test(location.protocol)) {
      // Hospedado (ex.: Render): a API é servida na mesma origem do site.
      // Em desenvolvimento local com servidor estático (outra porta), mantém o padrão.
      const isLocalDev = ["localhost", "127.0.0.1"].includes(location.hostname) && location.port !== "8000";
      if (!isLocalDev) apiBaseInput.value = location.origin;
    }
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
    localStorage.removeItem(STORAGE_KEYS.mealPrepMeals);
    localStorage.removeItem(STORAGE_KEYS.substitutionChoices);
    localStorage.removeItem(STORAGE_KEYS.leftoversGrams);
    localStorage.removeItem(STORAGE_KEYS.planData);
    localStorage.removeItem(STORAGE_KEYS.checklist);
    plans = [];
    availableMeals = [];
    selectedMeals = [];
    currentSubstitutionGroups = [];
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
    mealPrepSection.style.display = "none";
    showError(uploadError, null);
  }

  function showPlanScreen() {
    uploadSection.style.display = "none";
    planSection.style.display = "block";
    mealPrepSection.style.display = "none";
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
          await cachePlanFromServer(body.plan_id);
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
  cookingFactorToggle.addEventListener("change", () => {
    localStorage.setItem(STORAGE_KEYS.considerCookingFactor, String(cookingFactorToggle.checked));
    loadShoppingList();
  });
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
    renderSubstitutionGroups(currentSubstitutionGroups);
  });

  selectAllMealsBtn.addEventListener("click", () => {
    const selectAll = selectedMeals.length !== availableMeals.length;
    selectedMeals = selectAll ? [...availableMeals] : [];
    localStorage.setItem(STORAGE_KEYS.selectedMeals, JSON.stringify(selectedMeals));
    renderMealOptions();
    renderSubstitutionGroups(currentSubstitutionGroups);
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
    const groups = new Map();
    availableMeals.forEach((meal) => {
      const { personName, label: mealName } = splitPersonLabel(meal);
      if (!groups.has(personName)) groups.set(personName, []);
      groups.get(personName).push({ value: meal, label: mealName });
    });

    groups.forEach((meals, personName) => {
      const group = document.createElement("section");
      group.className = "meal-person-group";

      if (personName) {
        const heading = document.createElement("h3");
        heading.className = "meal-person-title";
        heading.textContent = personName;
        group.appendChild(heading);
      }

      const options = document.createElement("div");
      options.className = "meal-person-options";
      meals.forEach((meal) => {
        const label = document.createElement("label");
        label.className = "meal-option";
        const checkbox = document.createElement("input");
        checkbox.type = "checkbox";
        checkbox.value = meal.value;
        checkbox.checked = selectedMeals.includes(meal.value);
        const name = document.createElement("span");
        name.textContent = meal.label;
        label.append(checkbox, name);
        options.appendChild(label);
      });
      group.appendChild(options);
      mealOptions.appendChild(group);
    });
    updateMealSelectionControls();
  }

  function splitPersonLabel(value) {
    const separator = value.indexOf(" \u00b7 ");
    return separator < 0
      ? { personName: "", label: value }
      : { personName: value.slice(0, separator), label: value.slice(separator + 3) };
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
    if (cookingFactorToggle.checked) params.set("consider_cooking_factor", "true");
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
    currentSubstitutionGroups = substitutionGroups;
    renderSubstitutionGroups(currentSubstitutionGroups);
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
    const visibleGroups = groups.filter((group) => selectedMeals.includes(group.meal_name));
    substitutionPanel.hidden = !visibleGroups.length;

    const groupKeys = new Set(groups.map((group) => group.key));
    const validChoices = Object.fromEntries(
      Object.entries(substitutionChoices).filter(([key]) => groupKeys.has(key))
    );
    const groupsByPerson = new Map();
    visibleGroups.forEach((group) => {
      const { personName, label: mealName } = splitPersonLabel(group.meal_name);
      if (!groupsByPerson.has(personName)) groupsByPerson.set(personName, []);
      groupsByPerson.get(personName).push({ group, mealName });
    });

    groupsByPerson.forEach((personGroups, personName) => {
      const personGroup = document.createElement("section");
      personGroup.className = "meal-person-group";
      if (personName) {
        const heading = document.createElement("h3");
        heading.className = "meal-person-title";
        heading.textContent = personName;
        personGroup.appendChild(heading);
      }

      const personOptions = document.createElement("div");
      personOptions.className = "substitution-person-options";
      personGroups.forEach(({ group, mealName }) => {
        const row = document.createElement("div");
        row.className = "substitution-option";

        const label = document.createElement("label");
        const selectId = `substitution-${group.key}`;
        label.htmlFor = selectId;
        const mealLabel = document.createElement("strong");
        mealLabel.textContent = mealName;
        label.append(mealLabel, document.createTextNode(`: ${group.original_name}`));

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

        const savedChoice = validChoices[group.key];
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
        personOptions.appendChild(row);
      });
      personGroup.appendChild(personOptions);
      substitutionOptions.appendChild(personGroup);
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
    if (item.cooking_factors && item.cooking_factors.length) {
      const prescribed = formatGrams(item.prescribed_quantity);
      const calculated = formatGrams(item.calculated_quantity);
      const transition = document.createElement("span");
      transition.className = "item-cooking-info";
      transition.textContent = `${prescribed} ${item.weight_state === "prepared" ? "preparado" : "cru"} → ${calculated} cru`;
      details.appendChild(transition);
    } else if (cookingFactorToggle.checked && item.unit_type === "weight_g") {
      const unavailable = document.createElement("span");
      unavailable.className = "item-cooking-note";
      unavailable.textContent = "Quantidade prescrita mantida: sem conversão aplicável";
      details.appendChild(unavailable);
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

  function formatGrams(quantity) {
    return `${new Intl.NumberFormat("pt-BR", { maximumFractionDigits: 1 }).format(quantity || 0)}g`;
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
      saveChecklistState(planId, itemName, checked);
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

  // ---------- Meal Prep ----------

  const MEAL_PREP_DEFAULT_DAYS = 5;
  let mealPrepMeals = [];
  let mealPrepPlan = null;
  let isLoadingMealPrep = false;

  function clampMealPrepDays(value) {
    const n = parseInt(value, 10);
    return isNaN(n) ? MEAL_PREP_DEFAULT_DAYS : Math.min(31, Math.max(1, n));
  }

  function showMealPrepScreen() {
    uploadSection.style.display = "none";
    planSection.style.display = "none";
    mealPrepSection.style.display = "block";
    const stored = readStoredJson(STORAGE_KEYS.mealPrepMeals, null);
    const base = Array.isArray(stored) ? stored : selectedMeals;
    mealPrepMeals = availableMeals.filter((meal) => base.includes(meal));
    mealPrepDaysInput.value = clampMealPrepDays(localStorage.getItem(STORAGE_KEYS.mealPrepDays));
    renderMealPrepMeals();
    if (mealPrepMeals.length) loadMealPrep();
  }

  function renderMealPrepMeals() {
    mealPrepMealOptions.replaceChildren();
    const groups = new Map();
    availableMeals.forEach((meal) => {
      const { personName, label } = splitPersonLabel(meal);
      if (!groups.has(personName)) groups.set(personName, []);
      groups.get(personName).push({ value: meal, label });
    });
    groups.forEach((meals, personName) => {
      const group = document.createElement("section");
      group.className = "meal-person-group";
      if (personName) {
        const heading = document.createElement("h3");
        heading.className = "meal-person-title";
        heading.textContent = personName;
        group.appendChild(heading);
      }
      const options = document.createElement("div");
      options.className = "meal-person-options";
      meals.forEach((meal) => {
        const label = document.createElement("label");
        label.className = "meal-option";
        const checkbox = document.createElement("input");
        checkbox.type = "checkbox";
        checkbox.value = meal.value;
        checkbox.checked = mealPrepMeals.includes(meal.value);
        checkbox.addEventListener("change", () => {
          mealPrepMeals = availableMeals.filter((name) => {
            const input = [...mealPrepMealOptions.querySelectorAll("input")].find((i) => i.value === name);
            return input && input.checked;
          });
          writeStoredJson(STORAGE_KEYS.mealPrepMeals, mealPrepMeals);
          updateMealPrepControls();
        });
        const name = document.createElement("span");
        name.textContent = meal.label;
        label.append(checkbox, name);
        options.appendChild(label);
      });
      group.appendChild(options);
      mealPrepMealOptions.appendChild(group);
    });
    updateMealPrepControls();
  }

  function updateMealPrepControls() {
    const count = mealPrepMeals.length;
    mealPrepMealSummary.textContent = availableMeals.length
      ? `${count} de ${availableMeals.length} refeições selecionadas`
      : "Nenhuma refeição disponível.";
    showError(mealPrepMealError, count === 0 && availableMeals.length ? "Selecione ao menos uma refeição." : null);
    mealPrepRefreshBtn.disabled = isLoadingMealPrep || count === 0;
  }

  async function loadMealPrep() {
    if (isLoadingMealPrep) return;
    const planId = getStoredPlanId();
    if (!planId) return;
    if (mealPrepMeals.length === 0) {
      showError(mealPrepMealError, "Selecione ao menos uma refeição.");
      return;
    }

    const days = clampMealPrepDays(mealPrepDaysInput.value);
    mealPrepDaysInput.value = days;
    localStorage.setItem(STORAGE_KEYS.mealPrepDays, String(days));

    const params = new URLSearchParams({ days: String(days) });
    appendAdditionalPlanIds(params);
    const choices = Object.fromEntries(
      Object.entries(substitutionChoices).filter(([, choice]) => choice !== "default")
    );
    if (Object.keys(choices).length) params.set("substitution_choices", JSON.stringify(choices));
    const leftovers = Object.fromEntries(
      Object.entries(leftoversGrams).filter(([, quantity]) => quantity > 0)
    );
    if (Object.keys(leftovers).length) params.set("leftovers_grams", JSON.stringify(leftovers));
    if (mealPrepMeals.length !== availableMeals.length) {
      mealPrepMeals.forEach((meal) => params.append("meal_names", meal));
    }

    showError(mealPrepError, null);
    isLoadingMealPrep = true;
    updateMealPrepControls();
    mealPrepRefreshBtn.textContent = "Gerando...";
    try {
      const response = await apiFetch(`/api/v1/meal-prep/${planId}?${params}`);
      if (response.status === 404) {
        clearPlan();
        showUploadScreen();
        showToast("Este plano não foi encontrado. Envie o arquivo novamente.", true);
        return;
      }
      if (!response.ok) {
        const body = await response.json().catch(() => ({}));
        throw new ApiError(response.status, body.detail || "Não foi possível gerar o plano de preparo.");
      }
      mealPrepPlan = await response.json();
      renderMealPrep(mealPrepPlan);
    } catch (err) {
      showError(mealPrepError, err.message);
    } finally {
      isLoadingMealPrep = false;
      updateMealPrepControls();
      mealPrepRefreshBtn.textContent = "Gerar plano de preparo";
    }
  }

  function node(tag, className, text) {
    const element = document.createElement(tag);
    if (className) element.className = className;
    if (text !== undefined) element.textContent = text;
    return element;
  }

  function quantityBox(label, value, primary) {
    const box = node("div", "prep-quantity" + (primary ? " primary" : ""));
    box.append(node("small", "", label), node("strong", "", value));
    return box;
  }

  function linksBlock(links, title) {
    const safe = (links || []).filter((link) => /^https:\/\//i.test(link.url));
    if (!safe.length) return null;
    const block = node("div", "prep-links", title);
    const list = node("ul");
    safe.forEach((link) => {
      const item = node("li");
      const anchor = node("a", "", link.title + (link.source ? ` · ${link.source}` : ""));
      anchor.href = link.url;
      anchor.target = "_blank";
      anchor.rel = "noopener noreferrer";
      item.appendChild(anchor);
      list.appendChild(item);
    });
    block.appendChild(list);
    return block;
  }

  function renderMealPrep(plan) {
    mealPrepHeading.textContent = `Meal Prep para ${plan.days} ${plan.days === 1 ? "dia" : "dias"}`;

    mealPrepCookList.replaceChildren();
    if (!plan.cook_items.length) {
      mealPrepCookList.appendChild(node("p", "prep-empty", "Nenhum item das refeições escolhidas precisa ir ao fogo."));
    }
    plan.cook_items.forEach((item) => mealPrepCookList.appendChild(buildCookCard(item, plan.days)));

    mealPrepAssemblyList.replaceChildren();
    if (!plan.assembly.length) {
      mealPrepAssemblyList.appendChild(node("p", "prep-empty", "Nenhuma montagem necessária."));
    }
    plan.assembly.forEach((meal) => mealPrepAssemblyList.appendChild(buildAssemblyCard(meal)));

    mealPrepNotes.replaceChildren(...plan.notes.map((note) => node("li", "", note)));
    mealPrepResult.hidden = false;
  }

  function buildCookCard(item, days) {
    const card = node("article", "prep-card");

    const head = node("div", "prep-card-head");
    const name = node("div", "prep-card-name");
    const dot = node("span", "prep-dot");
    dot.style.background = `var(${CATEGORY_COLOR_VAR[item.category] || "--cat-outros"})`;
    name.append(dot, node("span", "", item.name));
    head.appendChild(name);
    if (item.method_label) head.appendChild(node("span", "prep-method", item.method_label));
    card.appendChild(head);

    const quantities = node("div", "prep-quantities");
    if (item.cooked_text) {
      quantities.append(
        quantityBox("Cru para cozinhar", item.total_text, true),
        quantityBox("Rende (cozido)", item.cooked_text),
        quantityBox("Por marmita", item.per_portion_text)
      );
    } else {
      quantities.appendChild(quantityBox(`Total para ${days} ${days === 1 ? "dia" : "dias"}`, item.total_text, true));
      if (item.per_portion_text && item.unit_type !== "free") {
        quantities.appendChild(quantityBox("Por porção", item.per_portion_text));
      }
    }
    card.appendChild(quantities);

    if (item.instruction) card.appendChild(node("p", "prep-instruction", item.instruction));
    item.warnings.forEach((warning) => card.appendChild(node("div", "prep-warning", warning)));

    if (item.breakdown.length) {
      const details = node("details", "prep-breakdown");
      details.appendChild(node("summary", "", "Quanto cada refeição leva"));
      const list = node("ul");
      item.breakdown.forEach((part) => {
        const portion = part.per_portion_text ? ` · ${part.per_portion_text} por porção` : "";
        list.appendChild(node("li", "", `${part.meal_name}: ${part.total_text}${portion}`));
      });
      details.appendChild(list);
      card.appendChild(details);
    }

    const links = linksBlock(item.links, "Outras sugestões de receitas:");
    if (links) card.appendChild(links);
    return card;
  }

  function buildAssemblyCard(meal) {
    const card = node("article", "prep-card");
    const head = node("div", "prep-card-head");
    head.appendChild(node("div", "prep-card-name", meal.meal_name));
    card.appendChild(head);
    card.appendChild(node("p", "prep-instruction", meal.instruction));

    const list = node("ul", "prep-assembly-items");
    meal.items.forEach((item) => {
      const portion = item.per_portion_text && item.unit_type !== "free" ? ` (${item.per_portion_text} por porção)` : "";
      list.appendChild(node("li", "", `${item.name}: ${item.total_text}${portion}`));
    });
    card.appendChild(list);

    const links = linksBlock(meal.links, "Ideias de receitas:");
    if (links) card.appendChild(links);
    return card;
  }

  function mealPrepToText(plan) {
    const lines = [`MEAL PREP — ${plan.days} ${plan.days === 1 ? "dia" : "dias"}`, `Refeições: ${plan.meals.join(", ")}`, ""];
    if (plan.cook_items.length) {
      lines.push("O QUE COZINHAR");
      plan.cook_items.forEach((item) => {
        lines.push(`- ${item.instruction}`);
        const details = [];
        if (item.cooked_text) details.push(`rende ~${item.cooked_text} cozido`);
        if (item.per_portion_text && item.unit_type !== "free") details.push(`${item.per_portion_text} por porção`);
        if (details.length) lines.push(`  (${details.join(" · ")})`);
        item.warnings.forEach((warning) => lines.push(`  ! ${warning}`));
      });
      lines.push("");
    }
    if (plan.assembly.length) {
      lines.push("MONTAGEM E LANCHES");
      plan.assembly.forEach((meal) => {
        lines.push(`${meal.meal_name}: ${meal.instruction}`);
        meal.items.forEach((item) => lines.push(`  - ${item.name}: ${item.total_text}`));
      });
    }
    return lines.join("\n").trim();
  }

  openMealPrepBtn.addEventListener("click", showMealPrepScreen);
  mealPrepBackBtn.addEventListener("click", showPlanScreen);
  mealPrepRefreshBtn.addEventListener("click", loadMealPrep);
  mealPrepDaysMinus.addEventListener("click", () => {
    mealPrepDaysInput.value = clampMealPrepDays(Number(mealPrepDaysInput.value) - 1);
  });
  mealPrepDaysPlus.addEventListener("click", () => {
    mealPrepDaysInput.value = clampMealPrepDays(Number(mealPrepDaysInput.value) + 1);
  });
  mealPrepDaysInput.addEventListener("blur", () => {
    mealPrepDaysInput.value = clampMealPrepDays(mealPrepDaysInput.value);
  });
  mealPrepCopyBtn.addEventListener("click", async () => {
    if (!mealPrepPlan) return;
    try {
      await navigator.clipboard.writeText(mealPrepToText(mealPrepPlan));
      showToast("Plano de preparo copiado para a área de transferência");
    } catch (_) {
      showToast("Não foi possível copiar o plano de preparo.", true);
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
