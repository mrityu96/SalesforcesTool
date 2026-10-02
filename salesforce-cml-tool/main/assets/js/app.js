  const $ = (id) => document.getElementById(id);

  // ── Navigation ──────────────────────────────────────────────────
  const PAGE_META = {
    fetch:   { title:"Fetch &amp; Deploy CML", sub:"Pick a source org — CMLs load automatically. Fetch, edit, and deploy to any org." },
    compare: { title:"Compare CML",         sub:"Use a VS Code-style diff to review and merge source changes into a guarded target draft." },
    data:    { title:"Constraint Data",     sub:"View, compare, and deploy ExpressionSetConstraintObj rows (Product associations)." },
    cdfix:   { title:"Context Definition Fix", sub:"Retrieve Context Definitions from the source and target orgs (read-only), then analyze and build a patched Base." },
    xml:     { title:"XML Tools",           sub:"Compare, merge, and deduplicate Salesforce metadata XML." },
    guide:   { title:"Help Me",             sub:"Step-by-step handbooks for CML and Context Definition deployments." },
  };
  const VIEWS_WITHOUT_ORGS = new Set(["guide", "xml"]);
  let currentView = "fetch";
  const navButtons = Array.from(document.querySelectorAll("#sideNav .side-nav[data-view]"));
  const navMore = $("navMore"), navMoreBtn = $("navMoreBtn"), navMoreMenu = $("navMoreMenu");
  const navMoreActive = $("navMoreActive");

  function switchView(view) {
    if (!$("view-" + view)) return;
    currentView = view;
    document.body.dataset.view = view;
    document.querySelectorAll(".view-panel").forEach(p => p.classList.remove("active"));
    $("view-" + view).classList.add("active");
    const connectionCard = $("connectionCard");
    if (connectionCard) connectionCard.hidden = VIEWS_WITHOUT_ORGS.has(view);
    navButtons.forEach(b => {
      const active = b.dataset.view === view;
      b.classList.toggle("active", active);
      b.setAttribute("aria-selected", String(active));
    });
    navMoreMenu.querySelectorAll("[data-view]").forEach(item => {
      item.classList.toggle("active", item.dataset.view === view);
    });
    const m = PAGE_META[view] || {};
    if ($("pageTitle")) $("pageTitle").innerHTML = m.title || view;
    if ($("pageSubtitle")) $("pageSubtitle").textContent = (m.sub || "").replace(/&amp;/g,"&");
    fitNav();
    document.dispatchEvent(new CustomEvent("cml:viewchange", { detail: { view } }));
  }
  navButtons.forEach(b => {
    b.addEventListener("click", () => switchView(b.dataset.view));
  });

  // ── Help Me: handbook sub-tabs and step links ───────────────────
  const helpTabs = Array.from(document.querySelectorAll("[data-help-tab]"));
  function selectHelpTab(name, focus) {
    helpTabs.forEach(tab => {
      const active = tab.dataset.helpTab === name;
      tab.classList.toggle("active", active);
      tab.setAttribute("aria-selected", String(active));
      tab.tabIndex = active ? 0 : -1;
      if (active && focus) tab.focus();
    });
    document.querySelectorAll("[data-help-panel]").forEach(panel => {
      panel.hidden = panel.dataset.helpPanel !== name;
    });
  }
  helpTabs.forEach((tab, index) => {
    tab.addEventListener("click", () => selectHelpTab(tab.dataset.helpTab));
    tab.addEventListener("keydown", event => {
      if (!["ArrowLeft", "ArrowRight", "Home", "End"].includes(event.key)) return;
      event.preventDefault();
      const next = event.key === "Home" ? 0 : event.key === "End" ? helpTabs.length - 1
        : (index + (event.key === "ArrowRight" ? 1 : -1) + helpTabs.length) % helpTabs.length;
      selectHelpTab(helpTabs[next].dataset.helpTab, true);
    });
  });
  document.querySelectorAll("[data-help-open]").forEach(link => {
    link.addEventListener("click", () => {
      switchView("guide");
      selectHelpTab(link.dataset.helpOpen, true);
      $("view-guide").scrollIntoView({ block: "start" });
    });
  });
  document.querySelectorAll("[data-help-jump]").forEach(link => {
    link.addEventListener("click", event => {
      const target = $(link.dataset.helpJump);
      if (!target) return;
      event.preventDefault();
      target.scrollIntoView({ behavior: "smooth", block: "start" });
    });
  });

  // ── Center pill: priority overflow into "More" ──────────────────
  // Items never shrink; the lowest-priority items (highest data-priority)
  // move into the More menu until the pill fits between brand and actions.
  const navLabel = button => button.querySelector(".nav-label").textContent;
  const overflowOrder = navButtons.slice().sort(
    (a, b) => Number(b.dataset.priority) - Number(a.dataset.priority));
  const pinnedCount = 2;

  function renderMoreMenu(hiddenButtons) {
    navMoreMenu.replaceChildren(...navButtons.filter(b => hiddenButtons.has(b)).map(button => {
      const item = document.createElement("button");
      item.type = "button";
      item.className = "nav-more-item" + (button.dataset.view === currentView ? " active" : "");
      item.setAttribute("role", "menuitem");
      item.dataset.view = button.dataset.view;
      item.append(button.querySelector(".nav-icon").cloneNode(true));
      const label = document.createElement("span");
      label.textContent = navLabel(button);
      item.append(label);
      return item;
    }));
  }

  function fitNav() {
    const header = document.querySelector(".app-header");
    const island = $("sideNav"), tabRow = $("tabRow");
    if (!header || !island) return;
    navButtons.forEach(b => { b.hidden = false; });
    navMore.hidden = false;
    const headerStyle = getComputedStyle(header);
    const gap = parseFloat(headerStyle.columnGap) || 0;
    const available = header.clientWidth
      - parseFloat(headerStyle.paddingLeft) - parseFloat(headerStyle.paddingRight)
      - document.querySelector(".brand-cluster").scrollWidth
      - document.querySelector(".top-actions").scrollWidth - gap * 2;
    const islandStyle = getComputedStyle(island);
    const chrome = parseFloat(islandStyle.paddingLeft) + parseFloat(islandStyle.paddingRight)
      + parseFloat(islandStyle.borderLeftWidth) + parseFloat(islandStyle.borderRightWidth);
    const itemGap = parseFloat(getComputedStyle(tabRow).columnGap) || 0;
    const widths = new Map(navButtons.map(b => [b, b.getBoundingClientRect().width]));
    const moreWidthFor = activeLabel => {
      navMoreActive.textContent = activeLabel || "";
      navMoreActive.hidden = !activeLabel;
      return navMore.getBoundingClientRect().width;
    };
    const hiddenButtons = new Set();
    const totalWidth = () => {
      const visible = navButtons.filter(b => !hiddenButtons.has(b));
      let total = chrome + visible.reduce((sum, b) => sum + widths.get(b), 0)
        + itemGap * Math.max(0, visible.length - 1);
      if (hiddenButtons.size) {
        const activeHidden = navButtons.find(b => hiddenButtons.has(b) && b.dataset.view === currentView);
        total += itemGap + moreWidthFor(activeHidden ? navLabel(activeHidden) : "");
      }
      return total;
    };
    for (const button of overflowOrder.slice(0, navButtons.length - pinnedCount)) {
      if (totalWidth() <= available) break;
      hiddenButtons.add(button);
    }
    navButtons.forEach(b => { b.hidden = hiddenButtons.has(b); });
    navMore.hidden = hiddenButtons.size === 0;
    const activeHidden = navButtons.find(b => hiddenButtons.has(b) && b.dataset.view === currentView);
    navMoreActive.textContent = activeHidden ? navLabel(activeHidden) : "";
    navMoreActive.hidden = !activeHidden;
    navMoreBtn.classList.toggle("active", Boolean(activeHidden));
    renderMoreMenu(hiddenButtons);
    if (!hiddenButtons.size) closeMoreMenu(false);
  }

  function openMoreMenu(focusFirst) {
    navMoreMenu.hidden = false;
    navMoreBtn.setAttribute("aria-expanded", "true");
    navMore.classList.add("open");
    if (focusFirst) {
      const first = navMoreMenu.querySelector(".nav-more-item.active") || navMoreMenu.querySelector(".nav-more-item");
      if (first) first.focus();
    }
  }
  function closeMoreMenu(restoreFocus) {
    if (navMoreMenu.hidden) return;
    navMoreMenu.hidden = true;
    navMoreBtn.setAttribute("aria-expanded", "false");
    navMore.classList.remove("open");
    if (restoreFocus) navMoreBtn.focus();
  }
  navMoreBtn.addEventListener("click", () => {
    if (navMoreMenu.hidden) openMoreMenu(true);
    else closeMoreMenu(false);
  });
  navMoreMenu.addEventListener("click", event => {
    const item = event.target.closest(".nav-more-item");
    if (!item) return;
    closeMoreMenu(true);
    switchView(item.dataset.view);
  });
  navMoreMenu.addEventListener("keydown", event => {
    const items = Array.from(navMoreMenu.querySelectorAll(".nav-more-item"));
    const index = items.indexOf(document.activeElement);
    let next = null;
    if (event.key === "ArrowDown") next = (index + 1) % items.length;
    if (event.key === "ArrowUp") next = (index - 1 + items.length) % items.length;
    if (event.key === "Home") next = 0;
    if (event.key === "End") next = items.length - 1;
    if (event.key === "Escape" || event.key === "Tab") closeMoreMenu(event.key === "Escape");
    if (next !== null) {
      event.preventDefault();
      items[next].focus();
    }
  });
  document.addEventListener("mousedown", event => {
    if (!navMore.contains(event.target)) closeMoreMenu(false);
  });

  // Arrow keys move across the visible pill items plus More; More itself
  // opens its menu on ArrowDown/Enter instead of switching views.
  $("tabRow").addEventListener("keydown", event => {
    if (navMoreMenu.contains(event.target)) return;
    const stops = [...navButtons.filter(b => !b.hidden), ...(navMore.hidden ? [] : [navMoreBtn])];
    const index = stops.indexOf(document.activeElement);
    if (index < 0) return;
    if (document.activeElement === navMoreBtn && event.key === "ArrowDown") {
      event.preventDefault();
      openMoreMenu(true);
      return;
    }
    let next = null;
    if (event.key === "ArrowRight") next = (index + 1) % stops.length;
    if (event.key === "ArrowLeft") next = (index - 1 + stops.length) % stops.length;
    if (event.key === "Home") next = 0;
    if (event.key === "End") next = stops.length - 1;
    if (next === null) return;
    event.preventDefault();
    closeMoreMenu(false);
    stops[next].focus();
    if (stops[next] !== navMoreBtn) switchView(stops[next].dataset.view);
  });

  if ("ResizeObserver" in window) {
    const headerObserver = new ResizeObserver(() => fitNav());
    [".app-header", ".brand-cluster", ".top-actions"].forEach(selector => {
      const el = document.querySelector(selector);
      if (el) headerObserver.observe(el);
    });
  } else {
    window.addEventListener("resize", fitNav);
  }
  if (document.fonts && document.fonts.ready) document.fonts.ready.then(fitNav);
  document.body.dataset.view = currentView;
  fitNav();

  const orgSel = $("org"), targetSel = $("targetOrg"), targetVersionSel = $("targetVersion"), model = $("model"), content = $("content"), status = $("status");
  const sourceOrgPicker = $("sourceOrgPicker"), sourceOrgTrigger = $("sourceOrgTrigger");
  const sourceOrgDisplay = $("sourceOrgDisplay"), sourceOrgMenu = $("sourceOrgMenu");
  const targetOrgPicker = $("targetOrgPicker"), targetOrgTrigger = $("targetOrgTrigger");
  const targetOrgDisplay = $("targetOrgDisplay"), targetOrgMenu = $("targetOrgMenu");
  const sourceOrgId = $("sourceOrgId"), targetOrgId = $("targetOrgId");
  const sourceOrgRelease = $("sourceOrgRelease"), targetOrgRelease = $("targetOrgRelease");
  const fetchBtn = $("fetchBtn"), deployBtn = $("deployBtn"), rollbackBtn = $("rollbackBtn"), compareBtn = $("compareBtn"), copyBtn = $("copyBtn");
  const downloadCmlBtn = $("downloadCmlBtn"), downloadBackupBtn = $("downloadBackupBtn");
  const importBackupBtn = $("importBackupBtn"), sessionDebugBtn = $("sessionDebugBtn");
  const archiveSelect = $("archiveSelect"), restoreListedArchiveBtn = $("restoreListedArchiveBtn");
  const downloadArchiveBtn = $("downloadArchiveBtn"), importArchiveBtn = $("importArchiveBtn");
  const archiveRecovery = $("archiveRecovery");
  const reportSelect = $("reportSelect"), downloadReportBtn = $("downloadReportBtn");
  const importReportBtn = $("importReportBtn"), reportRecovery = $("reportRecovery");
  const dataReportSelect = $("dataReportSelect"), downloadDataReportBtn = $("downloadDataReportBtn");
  const dataReportRecovery = $("dataReportRecovery");
  const isBrowserSession = () => Boolean(window.CmlRuntime && window.CmlRuntime.mode === "browser-session");
  if (downloadBackupBtn && isBrowserSession()) downloadBackupBtn.hidden = false;
  if (importBackupBtn && isBrowserSession()) importBackupBtn.hidden = false;
  if (sessionDebugBtn && isBrowserSession()) sessionDebugBtn.hidden = false;
  if (archiveRecovery && isBrowserSession()) archiveRecovery.hidden = false;
  if (reportRecovery && isBrowserSession()) reportRecovery.hidden = false;
  if (dataReportRecovery && isBrowserSession()) dataReportRecovery.hidden = false;

  function downloadTextFile(filename, text, mime) {
    const safe = String(filename || "download").replace(/[^\w.\-]+/g, "_").slice(0, 120);
    const blob = new Blob([text], { type: mime || "text/plain;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = safe;
    document.body.appendChild(link);
    link.click();
    link.remove();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }

  function pickJsonFile() {
    return new Promise((resolve) => {
      const input = document.createElement("input");
      input.type = "file";
      input.accept = "application/json,.json";
      input.onchange = async () => {
        const file = input.files && input.files[0];
        if (!file) { resolve(null); return; }
        try {
          resolve(JSON.parse(await file.text()));
        } catch (_) {
          resolve({ _parseError: true });
        }
      };
      input.click();
    });
  }

  function orgSessionWarning(org) {
    if (!org || org.usable !== false) return "";
    return org.warning || "Found a Lightning session but not an API session. Open the org in Classic or stay logged in, then retry.";
  }
  const lineCommentBtn = $("lineCommentBtn"), blockCommentBtn = $("blockCommentBtn");
  const cmlFilter = $("cmlFilter"), cmlCount = $("cmlCount");
  const combo = $("combo"), comboSelected = $("comboSelected"), selectedName = $("selectedName");
  const sourceVersionTrigger = $("sourceVersionTrigger"), sourceVersionMenu = $("sourceVersionMenu");
  const sourceVersionOptions = $("sourceVersionOptions");
  const targetVersionPicker = $("targetVersionPicker"), targetVersionTrigger = $("targetVersionTrigger");
  const targetVersionDisplay = $("targetVersionDisplay"), targetVersionMenu = $("targetVersionMenu");
  const targetVersionFilter = $("targetVersionFilter"), targetVersionOptions = $("targetVersionOptions");
  const deployOrgSel = $("deployOrg"), deployVersionSel = $("deployVersion");
  const backupSelect = $("backupSelect");
  const deployOrgPicker = $("deployOrgPicker"), deployOrgTrigger = $("deployOrgTrigger");
  const deployOrgDisplay = $("deployOrgDisplay"), deployOrgMenu = $("deployOrgMenu");
  const readinessBtn = $("readinessBtn"), readinessPanel = $("readinessPanel");
  const themeBtn = $("themeBtn"), conn = $("conn");
  const diffBox = $("diff"), diffSummary = $("diffSummary"), onlyDiffs = $("onlyDiffs");
  const diffPanes = $("diffPanes"), srcTable = $("srcTable"), tgtTable = $("tgtTable"), mergeTable = $("mergeTable");
  const srcTitle = $("srcTitle"), tgtTitle = $("tgtTitle"), srcScroll = $("srcScroll"), tgtScroll = $("tgtScroll"), mergeScroll = $("mergeScroll");
  const lintBtn = $("lintBtn"), lintBox = $("lint");
  const semanticChk = $("semanticDiff"), semanticInlineSummary = $("semanticInlineSummary");
  const lineLegend = $("lineLegend"), onlyDiffsWrap = $("onlyDiffsWrap");
  const mergeWorkflow = $("mergeWorkflow"), mergeWorkflowCopy = $("mergeWorkflowCopy");
  const resetMergeBtn = $("resetMergeBtn"), reviewMergeBtn = $("reviewMergeBtn");
  const copyTargetCmlBtn = $("copyTargetCmlBtn"), editTargetBtn = $("editTargetBtn");
  const saveTargetEditBtn = $("saveTargetEditBtn"), cancelTargetEditBtn = $("cancelTargetEditBtn");
  const tgtEditArea = $("tgtEditArea"), mergeAllBtn = $("mergeAllBtn");
  let lastCompare = null;
  let activeMergeHunks = [];
  let activeRevertHunks = [];
  let compareHasDiffs = false;
  let editingTarget = false;
  let semanticRefreshSequence = 0;
  let virtualDiffState = null;
  const loadDataBtn = $("loadDataBtn"), compareDataBtn = $("compareDataBtn"), stopCompareDataBtn = $("stopCompareDataBtn"), keyField = $("keyField");
  const keyFieldPicker = $("keyFieldPicker"), keyFieldMenu = $("keyFieldMenu");
  const keyFieldToggle = $("keyFieldToggle"), keyFieldHelp = $("keyFieldHelp");
  const keyName = () => (keyField.value || "").trim();
  const dataBox = $("data"), dataChips = $("dataChips"), dataTable = $("dataTable"), dataFilter = $("dataFilter");
  const deployBar = $("deployBar"), selSummary = $("selSummary"), deployDataBtn = $("deployDataBtn");
  const selAllAdds = $("selAllAdds"), selNoAdds = $("selNoAdds"), selAllDels = $("selAllDels"), selNoDels = $("selNoDels");
  const copyExcelBtn = $("copyExcelBtn");
  const dataSearch = $("dataSearch");
  const results = $("results");
  const donateBtn = $("donateBtn"), donateOptions = $("donateOptions");
  const donateUpiBtn = $("donateUpiBtn"), donateDialog = $("donateDialog");
  const donateCloseBtn = $("donateCloseBtn"), copyUpiBtn = $("copyUpiBtn");
  const confirmDialog = $("confirmDialog"), confirmForm = $("confirmForm");
  const confirmTitle = $("confirmTitle"), confirmDescription = $("confirmDescription");
  const confirmTargetText = $("confirmTargetText"), confirmExpectedAlias = $("confirmExpectedAlias");
  const confirmAlias = $("confirmAlias"), confirmMatch = $("confirmMatch");
  const confirmCancelBtn = $("confirmCancelBtn"), confirmSubmitBtn = $("confirmSubmitBtn");
  const shortcutHelpBtn = $("shortcutHelpBtn"), shortcutDialog = $("shortcutDialog");
  const shortcutCloseBtn = $("shortcutCloseBtn");
  const draftIndicator = $("draftIndicator"), draftRecovery = $("draftRecovery");
  const restoreDraftBtn = $("restoreDraftBtn"), discardDraftBtn = $("discardDraftBtn");
  let allModels = [];
  let targetModels = [];
  const modelCache = new Map();
  let modelLoadSequence = 0;
  let targetModelLoadSequence = 0;
  let allOrgs = [];
  let keyFieldCandidates = [];
  let activeKeyFieldOption = -1;
  let reconnecting = false;
  let dataRows = [];        // current rows shown in the data table
  let dataMode = "single";  // "single" (one org) or "compare"
  let currentKeyField = "";  // foreign key the shown data was matched on
  let dataCompareController = null;
  let dataCompareOperationId = null;
  let confirmationResolve = null;
  let confirmationReturnFocus = null;
  const selectedSourceVersion = () => allModels.find(m => m.versionId === model.value) || null;
  const selectedModelName = () => (selectedSourceVersion() || {}).name || "";
  const versionStatusLabel = (m) => {
    const basis = m && m.statusBasis === "runtime" ? "Runtime" : "Definition";
    return `${basis}: ${(m && m.status) || "Unknown"}`;
  };
  const selectedVersionLabel = (m) => m
    ? `${m.name} · V${m.version} · ${(m && m.status) || "Unknown"}`
    : "";
  function renderVersionTrigger(element, m, emptyText) {
    if (!m) { element.textContent = emptyText; element.title = ""; return; }
    const status = m.status || "Unknown";
    const tone = status === "Active" ? "active" : (status === "Inactive" ? "inactive" : "unknown");
    const name = document.createElement("span");
    name.className = "version-name";
    name.textContent = `${m.name} · V${m.version}`;
    element.title = `${m.name} · V${m.version} · ${status}`;
    element.replaceChildren(name, " ");
    const pill = document.createElement("span");
    pill.className = `cml-state-pill ${tone}`;
    pill.title = `Version status: ${status}`;
    pill.innerHTML = `<span aria-hidden="true">${tone === "active" ? "●" : "○"}</span> `;
    pill.append(status);
    element.append(pill);
  }

  // Size native picklists from their current option text. Containers wrap, so
  // a long exact-version label gets room instead of forcing button truncation.
  function fitPicklist(select) {
    if (!select) return;
    const texts = Array.from(select.options || []).map(option =>
      (option.textContent || "").trim());
    const selectedText = select.selectedOptions?.[0]?.textContent?.trim() || "";
    select.title = selectedText;
    // Layout sizing is handled in app.css so strict CSP remains effective.
  }
  function fitAllPicklists() {
    document.querySelectorAll("select").forEach(fitPicklist);
  }
  document.querySelectorAll("select").forEach(select => {
    new MutationObserver(() => fitPicklist(select)).observe(
      select, { childList:true, subtree:true });
    select.addEventListener("change", () => fitPicklist(select));
  });
  window.addEventListener("resize", fitAllPicklists);
  fitAllPicklists();

  // ---- Optional project support ----
  donateBtn.onclick = () => {
    const willOpen = donateOptions.hidden;
    donateOptions.hidden = !willOpen;
    donateBtn.setAttribute("aria-expanded", String(willOpen));
  };
  donateUpiBtn.onclick = () => {
    donateOptions.hidden = true;
    donateBtn.setAttribute("aria-expanded", "false");
    if (typeof donateDialog.showModal === "function") donateDialog.showModal();
    else donateDialog.setAttribute("open", "");
  };
  donateCloseBtn.onclick = () => donateDialog.close();
  donateDialog.addEventListener("click", event => {
    if (event.target === donateDialog) donateDialog.close();
  });
  document.addEventListener("click", event => {
    if (!event.target.closest(".donate-wrap")) {
      donateOptions.hidden = true;
      donateBtn.setAttribute("aria-expanded", "false");
    }
  });
  copyUpiBtn.onclick = async () => {
    const upi = copyUpiBtn.dataset.upi || "";
    try {
      await navigator.clipboard.writeText(upi);
    } catch (_) {
      const helper = document.createElement("textarea");
      helper.value = upi;
      helper.className = "clipboard-helper";
      document.body.appendChild(helper);
      helper.select();
      document.execCommand("copy");
      helper.remove();
    }
    copyUpiBtn.textContent = "UPI ID copied";
    setTimeout(() => { copyUpiBtn.textContent = "Copy UPI ID"; }, 1400);
  };

  // ---- Accessible in-app confirmation and shortcut dialogs ----
  function closeConfirmation(value) {
    if (!confirmDialog.open) return;
    confirmDialog.close(value ? "confirmed" : "cancelled");
  }
  function requestTypedConfirmation({ title, description, target, alias, submitLabel }) {
    if (confirmationResolve) return Promise.resolve(null);
    confirmationReturnFocus = document.activeElement;
    confirmTitle.textContent = title;
    confirmDescription.textContent = description;
    confirmTargetText.textContent = target;
    confirmExpectedAlias.textContent = alias;
    confirmAlias.value = "";
    confirmSubmitBtn.textContent = submitLabel || "Confirm";
    confirmSubmitBtn.disabled = true;
    confirmMatch.textContent = "Alias does not match yet.";
    confirmMatch.classList.remove("matches");
    confirmDialog.setAttribute("role", "alertdialog");
    confirmDialog.showModal();
    requestAnimationFrame(() => confirmAlias.focus());
    return new Promise(resolve => { confirmationResolve = resolve; });
  }
  confirmAlias.addEventListener("input", () => {
    const matches = confirmAlias.value === confirmExpectedAlias.textContent;
    confirmSubmitBtn.disabled = !matches;
    confirmMatch.textContent = matches ? "Exact alias match." : "Alias does not match yet.";
    confirmMatch.classList.toggle("matches", matches);
  });
  confirmForm.addEventListener("submit", event => {
    event.preventDefault();
    if (!confirmSubmitBtn.disabled) closeConfirmation(true);
  });
  confirmCancelBtn.onclick = () => closeConfirmation(false);
  confirmDialog.addEventListener("cancel", event => {
    event.preventDefault();
    closeConfirmation(false);
  });
  confirmDialog.addEventListener("close", () => {
    const resolve = confirmationResolve;
    confirmationResolve = null;
    const value = confirmDialog.returnValue === "confirmed"
      ? confirmExpectedAlias.textContent : null;
    if (resolve) resolve(value);
    if (confirmationReturnFocus && confirmationReturnFocus.isConnected) {
      confirmationReturnFocus.focus();
    }
    confirmationReturnFocus = null;
  });
  shortcutHelpBtn.onclick = () => {
    shortcutDialog.showModal();
    requestAnimationFrame(() => shortcutCloseBtn.focus());
  };
  shortcutCloseBtn.onclick = () => shortcutDialog.close();
  shortcutDialog.addEventListener("cancel", event => {
    event.preventDefault();
    shortcutDialog.close();
  });
  shortcutDialog.addEventListener("close", () => {
    requestAnimationFrame(() => shortcutHelpBtn.focus());
  });

  // ---- CodeMirror-backed CML editor compatibility layer ----
  let editorBaseline = "";
  let settingEditorContent = false;
  let draftSaveTimer = null;
  let pendingRecoveredDraft = null;
  const DRAFT_PREFIX = "cml-tool:draft:v1:";
  function draftScopeKey() {
    const source = selectedSourceVersion();
    if (!orgSel.value || !source) return "";
    return DRAFT_PREFIX + [orgSel.value, source.name, source.versionId]
      .map(encodeURIComponent).join(":");
  }
  function updateDirtyIndicator() {
    const dirty = content.value !== editorBaseline;
    draftIndicator.textContent = dirty ? "Unsaved changes" : "Not modified";
    draftIndicator.classList.toggle("dirty", dirty);
    return dirty;
  }
  function clearDraftForCurrentScope() {
    const key = draftScopeKey();
    if (key) {
      try { sessionStorage.removeItem(key); } catch (_) {}
    }
    pendingRecoveredDraft = null;
    draftRecovery.hidden = true;
  }
  function setEditorContent(value, options) {
    const text = value == null ? "" : String(value);
    settingEditorContent = true;
    window.cmlEditor.setValue(text);
    settingEditorContent = false;
    hideLintResults();
    if (!options || options.baseline !== false) editorBaseline = text;
    updateDirtyIndicator();
  }
  function resetEditorForSelection() {
    clearTimeout(draftSaveTimer);
    settingEditorContent = true;
    window.cmlEditor.setValue("");
    settingEditorContent = false;
    editorBaseline = "";
    updateDirtyIndicator();
    pendingRecoveredDraft = null;
    draftRecovery.hidden = true;
    const key = draftScopeKey();
    if (!key) return;
    try {
      const stored = JSON.parse(sessionStorage.getItem(key) || "null");
      if (stored && typeof stored.content === "string" && stored.content) {
        pendingRecoveredDraft = stored.content;
        draftRecovery.hidden = false;
      }
    } catch (_) {
      try { sessionStorage.removeItem(key); } catch (ignored) {}
    }
  }
  content.addEventListener("input", () => {
    if (settingEditorContent) return;
    hideLintResults();
    const dirty = updateDirtyIndicator();
    clearTimeout(draftSaveTimer);
    const key = draftScopeKey();
    if (!key) return;
    draftSaveTimer = setTimeout(() => {
      try {
        if (dirty) {
          sessionStorage.setItem(key, JSON.stringify({
            content: content.value, savedAt: new Date().toISOString(),
          }));
        } else {
          sessionStorage.removeItem(key);
        }
      } catch (_) {}
    }, 350);
  });
  restoreDraftBtn.onclick = () => {
    if (pendingRecoveredDraft == null) return;
    setEditorContent(pendingRecoveredDraft, { baseline:false });
    pendingRecoveredDraft = null;
    draftRecovery.hidden = true;
    setStatus("info", "Recovered the unsaved draft stored only in this browser tab/session.");
    window.cmlEditor.focus();
  };
  discardDraftBtn.onclick = () => {
    clearDraftForCurrentScope();
    setStatus("info", "Discarded the browser-session draft for this exact selection.");
    sourceVersionTrigger.focus();
  };
  window.addEventListener("beforeunload", event => {
    if (!updateDirtyIndicator()) return;
    event.preventDefault();
    event.returnValue = "";
  });
  function scrollEditorLineIntoView(line) {
    window.cmlEditor.goToLine(line);
  }
  function replaceEditorRange(start, end, replacement, selectionStart, selectionEnd) {
    window.cmlEditor.replaceRange(start, end, replacement, true);
    window.cmlEditor.setSelection(selectionStart, selectionEnd);
    window.cmlEditor.focus();
  }
  function toggleLineComment() {
    const value = content.value;
    const selectionStart = content.selectionStart;
    const selectionEnd = content.selectionEnd;
    const lineStart = value.lastIndexOf("\n", Math.max(0, selectionStart - 1)) + 1;
    const effectiveEnd = selectionEnd > selectionStart && value[selectionEnd - 1] === "\n"
      ? selectionEnd - 1 : selectionEnd;
    const nextBreak = value.indexOf("\n", effectiveEnd);
    const lineEnd = nextBreak < 0 ? value.length : nextBreak;
    const original = value.slice(lineStart, lineEnd);
    const lines = original.split("\n");
    const nonBlank = lines.filter(line => line.trim().length);
    const uncomment = nonBlank.length > 0 && nonBlank.every(line => /^\s*\/\//.test(line));
    const changed = lines.map(line => {
      if (uncomment) return line.replace(/^(\s*)\/\/ ?/, "$1");
      const indent = (line.match(/^\s*/) || [""])[0];
      return indent + "// " + line.slice(indent.length);
    }).join("\n");
    replaceEditorRange(lineStart, lineEnd, changed, lineStart, lineStart + changed.length);
  }
  function toggleBlockComment() {
    let start = content.selectionStart, end = content.selectionEnd;
    if (start === end) {
      start = content.value.lastIndexOf("\n", Math.max(0, start - 1)) + 1;
      const nextBreak = content.value.indexOf("\n", end);
      end = nextBreak < 0 ? content.value.length : nextBreak;
    }
    const selected = content.value.slice(start, end);
    const leading = selected.match(/^\s*/)?.[0] || "";
    const trailing = selected.match(/\s*$/)?.[0] || "";
    const core = selected.slice(leading.length, selected.length - trailing.length);
    const isCommented = core.startsWith("/*") && core.endsWith("*/");
    const replacement = isCommented
      ? leading + core.slice(2, -2).replace(/^ /, "").replace(/ $/, "") + trailing
      : leading + "/* " + core + " */" + trailing;
    replaceEditorRange(start, end, replacement, start, start + replacement.length);
  }
  lineCommentBtn.onclick = toggleLineComment;
  blockCommentBtn.onclick = toggleBlockComment;
  content.addEventListener("keydown", event => {
    if ((event.metaKey || event.ctrlKey) && event.key === "/") {
      event.preventDefault();
      toggleLineComment();
    }
  });

  // ---- Theme (day/night) ----
  function applyThemeLabel() {
    const dark = document.documentElement.getAttribute("data-theme") === "dark";
    themeBtn.setAttribute("aria-checked", String(dark));
    themeBtn.title = dark ? "Switch to day mode" : "Switch to night mode";
  }
  let themeTransitionTimer = null;
  themeBtn.onclick = () => {
    const root = document.documentElement;
    const next = root.getAttribute("data-theme") === "dark" ? "light" : "dark";
    root.classList.add("theme-transitioning");
    clearTimeout(themeTransitionTimer);
    themeTransitionTimer = setTimeout(() => root.classList.remove("theme-transitioning"), 450);
    root.setAttribute("data-theme", next);
    try { localStorage.setItem("cml-theme", next); } catch (e) {}
    applyThemeLabel();
  };
  applyThemeLabel();

  function setStatus(kind, msg, targetEl) {
    const el = targetEl || status;
    el.className = "status show " + kind;
    el.setAttribute("role", kind === "err" ? "alert" : "status");
    el.setAttribute("aria-live", kind === "err" ? "assertive" : "polite");
    el.textContent = msg;
    el.scrollIntoView({ behavior: "smooth", block: "nearest" });
  }

  // API transport is isolated in api-client.js.
  const { apiGet, postJSON } = window.CmlApi;

  // Shared with xml-tools.js (Context Definition Fix and XML Tools views).
  window.CmlShell = Object.freeze({
    setStatus,
    downloadTextFile,
    isBrowserSession,
    currentView: () => currentView,
  });

  function showConn() {
    conn.className = "conn show";
    conn.innerHTML = '<span class="spinner"></span>Lost connection to the CML Tool. Make sure its window is still open — reconnecting automatically…';
    if (window.CmlRuntime) {
      const overlay = document.getElementById("cmlOfflineOverlay");
      if (overlay) overlay.hidden = false;
    }
  }
  function hideConn() {
    conn.className = "conn";
    const overlay = document.getElementById("cmlOfflineOverlay");
    if (overlay) overlay.hidden = true;
  }

  function handleDisconnect() {
    if (reconnecting) return;
    reconnecting = true;
    showConn();
    const timer = setInterval(async () => {
      try {
        const ping = await apiGet("/api/ping");
        if (ping && ping.app === "cml-tool") {
          clearInterval(timer);
          reconnecting = false;
          hideConn();
          setStatus("ok", "Reconnected to the CML Tool.");
          loadOrgs();
        }
      } catch (e) { /* still down; keep trying */ }
    }, 1500);
  }
  const actionBtns = [fetchBtn, deployBtn, rollbackBtn, compareBtn, loadDataBtn, compareDataBtn, deployDataBtn];
  function busy(btn, label) {
    btn.innerHTML = '<span class="spinner"></span>' + label;
    document.querySelector(".app-main").setAttribute("aria-busy", "true");
    actionBtns.forEach(b => b.disabled = true);
  }
  function idle() {
    fetchBtn.innerHTML = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4M7 10l5 5 5-5M12 15V3"/></svg>Fetch CML';
    deployBtn.innerHTML = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 16V3M7 8l5-5 5 5"/><path d="M5 21h14a2 2 0 0 0 2-2v-4M3 15v4a2 2 0 0 0 2 2"/></svg>Deploy CML';
    rollbackBtn.innerHTML = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 12a9 9 0 1 0 3-6.7L3 8"/><path d="M3 3v5h5"/></svg>Restore Backup CML';
    compareBtn.innerHTML = '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" class="button-icon-inline"><path d="M8 3H5a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h3M16 3h3a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2h-3M10 8l-3 4 3 4M14 8l3 4-3 4"/></svg>Compare source ↔ target';
    loadDataBtn.innerHTML = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><circle cx="11" cy="11" r="7"/><path d="m20 20-4-4"/></svg>View Source Org Data';
    compareDataBtn.innerHTML = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><path d="M7 7h11l-3-3M18 17H7l3 3M18 7l-3 3M7 17l3-3"/></svg>Compare data';
    deployDataBtn.innerHTML = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><path d="m8 5 11 7-11 7z"/></svg>Deploy selected to target';
    actionBtns.forEach(b => b.disabled = false);
    document.querySelector(".app-main").removeAttribute("aria-busy");
    updateDeployBar();
  }

  function selectedOrgInfo(alias) {
    return allOrgs.find(org => org.alias === alias) || null;
  }

  const ORG_ICON = '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 21V8l8-5 8 5v13M8 21v-4h8v4M8 10h.01M12 10h.01M16 10h.01M8 13h.01M12 13h.01M16 13h.01"/></svg>';
  const REFRESH_ICON = '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M21 12a9 9 0 1 1-2.64-6.36M21 3v6h-6"/></svg>';
  let orgListLoaded = false, orgGeneration = null, orgPollTimer = null, orgRefreshWanted = false;
  const orgPickers = [
    { select:orgSel, picker:sourceOrgPicker, trigger:sourceOrgTrigger, display:sourceOrgDisplay,
      menu:sourceOrgMenu, placeholder:"Select a source org", refreshable:true },
    { select:targetSel, picker:targetOrgPicker, trigger:targetOrgTrigger, display:targetOrgDisplay,
      menu:targetOrgMenu, placeholder:"Select a target org", refreshable:true },
    { select:deployOrgSel, picker:deployOrgPicker, trigger:deployOrgTrigger, display:deployOrgDisplay,
      menu:deployOrgMenu, placeholder:"Select a deployment target" },
  ];

  function closeOrgPicker(config) {
    config.menu.hidden = true;
    config.picker.classList.remove("open");
    config.trigger.setAttribute("aria-expanded", "false");
  }

  function renderOrgPicker(config) {
    const selected = selectedOrgInfo(config.select.value);
    config.display.textContent = selected ? selected.alias
      : (orgListLoaded ? config.placeholder : "Loading orgs…");
    config.trigger.disabled = !allOrgs.length && !(config.refreshable && orgListLoaded);
    const refreshRow = config.refreshable
      ? `<button type="button" class="org-option" role="option" aria-selected="false" data-refresh="true"`
        + `${orgRefreshWanted ? ' aria-disabled="true"' : ""}>${REFRESH_ICON}`
        + `<span class="org-option-copy"><span class="org-option-name">${orgRefreshWanted ? "Refreshing org list…" : "Refresh org list"}</span>`
        + `<span class="org-option-meta">Find orgs added with sf org login</span></span></button>`
      : "";
    config.menu.innerHTML = refreshRow + allOrgs.map(org => {
      const isSelected = org.alias === config.select.value;
      return `<button type="button" class="org-option${isSelected ? " selected" : ""}" role="option"`
        + ` aria-selected="${isSelected}" data-value="${esc(org.alias)}">${ORG_ICON}`
        + `<span class="org-option-copy"><span class="org-option-name">${esc(org.alias)}</span>`
        + `<span class="org-option-meta">${esc(org.usable === false
          ? (org.warning || "No API session")
          : (org.username || "Salesforce org"))}</span></span></button>`;
    }).join("");
  }

  function openOrgPicker(config) {
    if (config.trigger.disabled) return;
    orgPickers.forEach(closeOrgPicker);
    renderOrgPicker(config);
    config.menu.hidden = false;
    config.picker.classList.add("open");
    config.trigger.setAttribute("aria-expanded", "true");
  }

  orgPickers.forEach(config => {
    config.trigger.addEventListener("click", () =>
      config.menu.hidden ? openOrgPicker(config) : closeOrgPicker(config));
    config.menu.addEventListener("click", event => {
      const option = event.target.closest(".org-option");
      if (!option) return;
      if (option.dataset.refresh) {
        refreshOrgs();
        return;
      }
      config.select.value = option.dataset.value;
      renderOrgPicker(config);
      closeOrgPicker(config);
      config.select.dispatchEvent(new Event("change", { bubbles:true }));
      config.trigger.focus();
    });
    config.select.addEventListener("change", () => renderOrgPicker(config));
  });
  document.addEventListener("mousedown", event => {
    orgPickers.forEach(config => {
      if (!config.picker.contains(event.target)) closeOrgPicker(config);
    });
  });

  function renderSelectedOrgIds() {
    const source = selectedOrgInfo(orgSel.value);
    const target = selectedOrgInfo(targetSel.value);
    [[sourceOrgId, source], [targetOrgId, target]].forEach(([button, info]) => {
      const id = (info && info.orgId) || "";
      button.querySelector(".meta-value").textContent = id || "—";
      button.dataset.orgId = id;
      button.disabled = !id;
    });
    renderOrgRelease(sourceOrgRelease, orgSel.value);
    renderOrgRelease(targetOrgRelease, targetSel.value);
  }

  const orgReleaseCache = new Map();
  function releaseText(data) {
    if (!data || !data.ok) return "unavailable";
    const parts = [data.releaseNumber, data.release].filter(Boolean);
    if (!parts.length && data.apiVersion) parts.push(`API ${data.apiVersion}`);
    return parts.join(" · ") || "unknown";
  }
  function renderOrgRelease(element, org) {
    element.dataset.org = org || "";
    if (!org) { element.textContent = "—"; return; }
    const cached = orgReleaseCache.get(org);
    if (cached && !(cached instanceof Promise)) { element.textContent = releaseText(cached); return; }
    element.textContent = "checking…";
    const request = cached || apiGet("/api/org-release?org=" + encodeURIComponent(org))
      .then(data => { orgReleaseCache.set(org, data); return data; })
      .catch(() => { orgReleaseCache.delete(org); return null; });
    orgReleaseCache.set(org, request);
    request.then(data => {
      if (element.dataset.org === org) element.textContent = releaseText(data);
    });
  }
  [sourceOrgId, targetOrgId].forEach(button => {
    button.addEventListener("click", async () => {
      const id = button.dataset.orgId;
      if (!id) return;
      try { await navigator.clipboard.writeText(id); } catch (_) { return; }
      const value = button.querySelector(".meta-value");
      value.textContent = "Copied";
      setTimeout(() => { value.textContent = button.dataset.orgId || "—"; }, 1200);
    });
  });

  function renderKeyFieldMenu(filter = "") {
    const needle = filter.trim().toLowerCase();
    const fields = keyFieldCandidates.filter(field =>
      !needle
      || field.name.toLowerCase().includes(needle)
      || (field.label || "").toLowerCase().includes(needle)
      || (field.objectTypes || []).some(type => type.toLowerCase().includes(needle))
    );
    activeKeyFieldOption = -1;
    keyFieldMenu.innerHTML = fields.length ? fields.map(field => {
      const scope = field.allReferenceTypes
        ? "Available on all supported reference objects"
        : `Available on ${(field.objectTypes || []).join(", ")}`;
      const selected = field.name === keyName();
      return `<button type="button" class="key-field-option${selected ? " selected" : ""}"`
        + ` role="option" aria-selected="${selected}" data-value="${esc(field.name)}">`
        + `<span class="key-field-option-main"><span class="key-field-option-name">${esc(field.name)}</span>`
        + `<span class="key-field-option-scope">${esc(scope)}</span></span>`
        + (selected ? '<span class="key-field-option-mark" aria-hidden="true">✓</span>' : "")
        + "</button>";
    }).join("") : `<div class="key-field-empty">${
      keyFieldCandidates.length
        ? "No detected fields match your search. You can still enter a valid API name."
        : "Select orgs to discover available fields."
    }</div>`;
  }

  function openKeyFieldMenu(filter = "") {
    renderKeyFieldMenu(filter);
    keyFieldMenu.hidden = false;
    keyFieldPicker.classList.add("open");
    keyField.setAttribute("aria-expanded", "true");
  }

  function closeKeyFieldMenu() {
    keyFieldMenu.hidden = true;
    keyFieldPicker.classList.remove("open");
    keyField.setAttribute("aria-expanded", "false");
    activeKeyFieldOption = -1;
  }

  function selectKeyField(value) {
    keyField.value = value;
    closeKeyFieldMenu();
    keyField.focus();
    keyField.dispatchEvent(new Event("change", { bubbles: true }));
  }

  function moveKeyFieldHighlight(direction) {
    const options = Array.from(keyFieldMenu.querySelectorAll(".key-field-option"));
    if (!options.length) return;
    activeKeyFieldOption = activeKeyFieldOption < 0
      ? (direction > 0 ? 0 : options.length - 1)
      : (activeKeyFieldOption + direction + options.length) % options.length;
    options.forEach((option, index) =>
      option.classList.toggle("active", index === activeKeyFieldOption));
    options[activeKeyFieldOption].scrollIntoView({ block: "nearest" });
  }

  keyField.addEventListener("focus", () => openKeyFieldMenu());
  keyField.addEventListener("input", () => {
    openKeyFieldMenu(keyName());
  });
  keyField.addEventListener("keydown", event => {
    if (event.key === "ArrowDown" || event.key === "ArrowUp") {
      event.preventDefault();
      if (keyFieldMenu.hidden) openKeyFieldMenu();
      else moveKeyFieldHighlight(event.key === "ArrowDown" ? 1 : -1);
    } else if (event.key === "Enter" && !keyFieldMenu.hidden) {
      const options = keyFieldMenu.querySelectorAll(".key-field-option");
      const selected = options[activeKeyFieldOption];
      if (selected) {
        event.preventDefault();
        selectKeyField(selected.dataset.value);
      }
    } else if (event.key === "Escape") {
      closeKeyFieldMenu();
    }
  });
  keyFieldToggle.addEventListener("click", () => {
    if (keyFieldMenu.hidden) {
      keyField.focus();
      openKeyFieldMenu();
    } else {
      closeKeyFieldMenu();
    }
  });
  keyFieldMenu.addEventListener("mousedown", event => event.preventDefault());
  keyFieldMenu.addEventListener("click", event => {
    const option = event.target.closest(".key-field-option");
    if (option) selectKeyField(option.dataset.value);
  });
  document.addEventListener("mousedown", event => {
    if (!keyFieldPicker.contains(event.target)) closeKeyFieldMenu();
  });

  let keyFieldLoadSequence = 0;
  async function loadKeyFields() {
    const source = orgSel.value;
    const target = targetSel.value;
    const sequence = ++keyFieldLoadSequence;
    if (!source) {
      keyFieldCandidates = [];
      renderKeyFieldMenu();
      keyField.value = "";
      keyField.placeholder = "Select a source org first";
      keyFieldHelp.innerHTML = "Choose a unique external ID when possible. <code>Name</code> requires matching, unique values; duplicates are blocked.";
      return;
    }
    keyField.placeholder = "Loading fields from selected orgs…";
    try {
      const query = `sourceOrg=${encodeURIComponent(source)}`
        + (target ? `&targetOrg=${encodeURIComponent(target)}` : "");
      const data = await apiGet(`/api/key-fields?${query}`);
      if (sequence !== keyFieldLoadSequence) return;
      if (!data.ok) {
        keyFieldCandidates = [];
        renderKeyFieldMenu();
        keyField.placeholder = "Type a field API name";
        keyFieldHelp.textContent = data.log || "Field discovery was unavailable; enter a field API name manually.";
        return;
      }
      const previous = keyName();
      const fields = data.fields || [];
      keyFieldCandidates = fields;
      const available = new Set(fields.map(field => field.name));
      if (previous && !available.has(previous)) keyField.value = "";
      renderKeyFieldMenu();
      keyField.placeholder = fields.length
        ? "Choose a detected field"
        : "No shared candidate fields detected";
      const compared = target ? `${source} and ${target}` : source;
      keyFieldHelp.innerHTML = fields.length
        ? `${fields.length} candidate field${fields.length === 1 ? "" : "s"} loaded from ${esc(compared)}. Prefer a unique external ID. <code>Name</code> requires matching, unique values; duplicates are blocked.`
        : `No filterable business-key candidates were shared by the supported reference objects in ${esc(compared)}.`;
    } catch (e) {
      if (sequence !== keyFieldLoadSequence) return;
      keyFieldCandidates = [];
      renderKeyFieldMenu();
      keyField.placeholder = "Type a field API name";
      keyFieldHelp.textContent = "Could not discover fields: " + e;
    }
  }

  function scheduleOrgPoll(delay) {
    clearTimeout(orgPollTimer);
    orgPollTimer = setTimeout(loadOrgs, delay);
  }

  function handleOrgLoadError(e) {
    orgRefreshWanted = false;
    if (e && e.conn) { handleDisconnect(); return; }
    if (!orgListLoaded) orgSel.innerHTML = '<option value="">(could not load orgs)</option>';
    orgPickers.forEach(renderOrgPicker);
    setStatus("err", "Could not load orgs: " + e);
  }

  async function loadOrgs() {
    try {
      applyOrgResponse(await apiGet("/api/orgs"));
    } catch (e) {
      handleOrgLoadError(e);
    }
  }

  async function refreshOrgs() {
    if (orgRefreshWanted) return;
    orgRefreshWanted = true;
    orgPickers.forEach(renderOrgPicker);
    try {
      applyOrgResponse(await postJSON("/api/orgs/refresh", {}));
    } catch (e) {
      handleOrgLoadError(e);
    }
  }

  // The local server answers from a cache and reports loading/refreshing
  // while the CLI runs in the background; the extension returns a plain array.
  function applyOrgResponse(raw) {
    const data = Array.isArray(raw)
      ? { orgs: raw, loading: false, refreshing: false, generation: null }
      : (raw || {});
    if (data.loading || data.refreshing) {
      scheduleOrgPoll(data.loading ? 400 : 1000);
    } else {
      clearTimeout(orgPollTimer);
      orgRefreshWanted = false;
    }
    const unchanged = orgListLoaded && data.generation !== null
      && data.generation === orgGeneration;
    if (data.loading || unchanged) {
      orgPickers.forEach(renderOrgPicker);
      return;
    }
    orgGeneration = data.generation;
    orgListLoaded = true;
    if (data.error) {
      allOrgs = [];
      orgSel.innerHTML = '<option value="">(could not load orgs)</option>';
      orgPickers.forEach(renderOrgPicker);
      setStatus("err", data.error);
      return;
    }
    applyOrgs(data.orgs || []);
    if (data.warning) setStatus("info", data.warning);
  }

  function applyOrgs(orgs) {
    if (!orgs.length) {
      allOrgs = [];
      orgPickers.forEach(renderOrgPicker);
      orgSel.innerHTML = '<option value="">(no orgs found)</option>';
      const browserSession = window.CmlRuntime && window.CmlRuntime.mode === "browser-session";
      setStatus("err", browserSession
        ? "No Salesforce org tabs were found in this Chrome profile.\n"
          + "Log into the org in a normal tab (Lightning or Classic), leave it open, then click Fetch again or reload this page.\n"
          + "Compare across two orgs requires both orgs to be logged in.\n"
          + "Use Session status if a tab is open but the org still does not appear."
        : "No Salesforce orgs are authorized for THIS user on THIS computer.\n"
          + "Org logins are stored per operating-system user, so each person must log in on their own account:\n\n"
          + "    sf org login web --alias <name>\n\n"
          + "Then choose Refresh org list in the Source or Target org picker. For protected local diagnostics, restart with CML_DEBUG=1.");
      return;
    }
    const firstPopulate = !allOrgs.length;
    const previous = [orgSel.value, targetSel.value, deployOrgSel.value];
    allOrgs = orgs;
    const opts = orgs.map(o => `<option value="${o.alias}">${o.alias}${o.username ? "  —  " + o.username : ""}${o.usable === false ? "  —  no API session" : ""}</option>`).join("");
    orgSel.innerHTML = '<option value="">None — select a source org</option>' + opts;
    targetSel.innerHTML = '<option value="">None — select a target org</option>' + opts;
    deployOrgSel.innerHTML = '<option value="">None — select a deployment target</option>' + opts;
    if (!firstPopulate) {
      // Background refresh: keep selections that still exist.
      const known = new Set(orgs.map(o => o.alias));
      [orgSel, targetSel, deployOrgSel].forEach((select, index) => {
        const kept = known.has(previous[index]) ? previous[index] : "";
        select.value = kept;
        if (previous[index] && !kept) select.dispatchEvent(new Event("change", { bubbles:true }));
      });
      orgPickers.forEach(renderOrgPicker);
      renderSelectedOrgIds();
      return;
    }
    orgSel.value = "";
    targetSel.value = "";
    deployOrgSel.value = "";
    targetVersionSel.innerHTML = '<option value="">None — select target org and source version</option>';
    deployVersionSel.innerHTML = '<option value="">None — select deployment target and source version</option>';
    orgPickers.forEach(renderOrgPicker);
    renderSelectedOrgIds();
    const blocked = orgs.filter(o => o.usable === false);
    if (blocked.length) {
      setStatus("info", blocked.map(o =>
        (o.alias || o.orgId) + ": " + (o.warning || "No API session")
      ).join("\n") + "\nOpen Classic or stay logged in so a my.salesforce.com cookie exists, then use Session status.");
    }
    loadKeyFields();
    loadModels();
  }

  // Floating, searchable exact-version controls. Native selects remain the
  // source of truth so existing guarded workflows keep their exact IDs.
  function openVersionPicker(picker, trigger, menu, search) {
    if (trigger.disabled) return;
    menu.hidden = false;
    picker.classList.add("open");
    trigger.setAttribute("aria-expanded", "true");
    requestAnimationFrame(() => search.focus());
  }
  function closeVersionPicker(picker, trigger, menu) {
    menu.hidden = true;
    picker.classList.remove("open");
    trigger.setAttribute("aria-expanded", "false");
  }
  function collapseModelView() {
    const selected = selectedSourceVersion();
    renderVersionTrigger(selectedName, selected, "Select exact CML version");
    closeVersionPicker(combo, sourceVersionTrigger, sourceVersionMenu);
  }
  function expandModelView() {
    openVersionPicker(combo, sourceVersionTrigger, sourceVersionMenu, cmlFilter);
  }
  model.addEventListener("change", () => {
    collapseModelView();
    renderModels();
    resetEditorForSelection();
    loadTargetVersions(targetSel, targetVersionSel, "compare");
    loadTargetVersions(deployOrgSel, deployVersionSel, "deployment");
    loadCmlBackups();
    loadAssociationArchives();
    loadDeploymentReports();
  });
  sourceVersionTrigger.onclick = () => sourceVersionMenu.hidden ? expandModelView()
    : closeVersionPicker(combo, sourceVersionTrigger, sourceVersionMenu);
  targetVersionTrigger.onclick = () => targetVersionMenu.hidden
    ? openVersionPicker(targetVersionPicker, targetVersionTrigger, targetVersionMenu, targetVersionFilter)
    : closeVersionPicker(targetVersionPicker, targetVersionTrigger, targetVersionMenu);

  function versionOptionHtml(item, selectedId) {
    const active = String(item.status || "").trim().toLowerCase() === "active";
    return `<button type="button" class="version-option${item.versionId === selectedId ? " selected" : ""}"`
      + ` role="option" aria-selected="${item.versionId === selectedId}" data-value="${esc(item.versionId)}">`
      + `<span class="version-option-copy"><span class="version-option-name">${esc(item.name)} · V${esc(item.version)}</span>`
      + `<span class="version-option-meta">${esc(versionStatusLabel(item))}</span></span>`
      + `<span class="runtime-badge ${active ? "active" : "inactive"}">${active ? "Active" : "Inactive"}</span></button>`;
  }

  function renderModels() {
    const f = cmlFilter.value.trim().toLowerCase();
    const list = allModels.filter(m =>
      !f || m.name.toLowerCase().includes(f)
      || (m.label || "").toLowerCase().includes(f)
      || String(m.version || "").includes(f)
      || (m.status || "").toLowerCase().includes(f)
      || (m.versionId || "").toLowerCase().includes(f));
    if (allModels.length) {
      const selectedValue = model.value;
      const optionHtml = m => `<option value="${m.versionId}">${m.name} · V${m.version} · ${m.status || "Unknown"}</option>`;
      const active = allModels.filter(m =>
        String(m.status || "").trim().toLowerCase() === "active");
      const inactive = allModels.filter(m =>
        String(m.status || "").trim().toLowerCase() !== "active");
      model.innerHTML = '<option value="">None — select an exact version</option>'
        + (active.length
          ? `<optgroup label="Active CML versions">${active.map(optionHtml).join("")}</optgroup>`
          : "")
        + (inactive.length
          ? `<optgroup label="Inactive / other CML versions">${inactive.map(optionHtml).join("")}</optgroup>`
          : "");
      model.value = selectedValue;
    }
    sourceVersionOptions.innerHTML = list.length
      ? list.map(item => versionOptionHtml(item, model.value)).join("")
      : `<div class="version-empty">${allModels.length ? "No CML versions match your search." : "No CML versions found in this org."}</div>`;
    cmlCount.textContent = allModels.length ? `(${list.length} of ${allModels.length})` : "";
  }

  async function getOrgModels(org, refresh = false) {
    if (refresh) modelCache.delete(org);
    if (!modelCache.has(org)) {
      const request = apiGet("/api/models?org=" + encodeURIComponent(org))
        .then(data => {
          if (data.error) modelCache.delete(org);
          return data;
        })
        .catch(error => {
          modelCache.delete(org);
          throw error;
        });
      modelCache.set(org, request);
    }
    return modelCache.get(org);
  }

  async function loadModels(refresh = false) {
    const org = orgSel.value;
    const sequence = ++modelLoadSequence;
    closeVersionPicker(combo, sourceVersionTrigger, sourceVersionMenu);
    if (!org) {
      allModels = [];
      cmlCount.textContent = "";
      cmlFilter.value = "";
      model.innerHTML = '<option value="">Choose a source org first…</option>';
      model.value = "";
      selectedName.textContent = "Select a source org first…";
      sourceVersionTrigger.disabled = true;
      sourceVersionOptions.innerHTML = "";
      targetVersionSel.innerHTML = '<option value="">None — select target org and source version</option>';
      deployVersionSel.innerHTML = '<option value="">None — select deployment target and source version</option>';
      return;
    }
    sourceVersionTrigger.disabled = true;
    selectedName.textContent = "Loading CML versions…";
    allModels = [];
    cmlCount.textContent = "";
    model.innerHTML = '<option value="">Loading CMLs…</option>';
    try {
      const data = await getOrgModels(org, refresh);
      if (sequence !== modelLoadSequence) return;
      if (data.error) {
        model.innerHTML = '<option value="">(could not load CMLs)</option>';
        model.value = "";
        selectedName.textContent = "Unable to load CML versions — reselect the source org";
        sourceVersionTrigger.disabled = false;
        setStatus("err", "Could not load CMLs from " + org + ":\n" + data.error);
        return;
      }
      allModels = data.models || [];
      model.value = "";
      cmlFilter.value = "";
      renderModels();
      sourceVersionTrigger.disabled = !allModels.length;
      selectedName.textContent = allModels.length ? "Select exact CML version" : "No CML versions found";
      if (data.runtimeStatusWarning) {
        setStatus(
          "info",
          "Runtime activity could not be loaded. Source labels are using "
          + "definition-version status.\n" + data.runtimeStatusWarning);
      }
      targetVersionSel.innerHTML = '<option value="">None — select target org and source version</option>';
      deployVersionSel.innerHTML = '<option value="">None — select deployment target and source version</option>';
      if (!allModels.length) setStatus("info", "No CMLs (Expression Set versions) were found in " + org + ".");
    } catch (e) {
      if (sequence !== modelLoadSequence) return;
      if (e && e.conn) { handleDisconnect(); return; }
      model.value = "";
      selectedName.textContent = "Unable to load CML versions — reselect the source org";
      sourceVersionTrigger.disabled = false;
      setStatus("err", "Could not load CMLs: " + e);
    }
  }

  async function loadTargetVersions(
      orgControl, versionControl, purpose, refresh = false) {
    const isCompareTarget = versionControl === targetVersionSel;
    const sequence = isCompareTarget ? ++targetModelLoadSequence : null;
    versionControl.innerHTML = `<option value="">None — select exact ${purpose} version</option>`;
    const org = orgControl.value;
    const modelName = selectedModelName();
    if (isCompareTarget) {
      targetModels = [];
      targetVersionDisplay.textContent = !org
        ? "Select a target org first…"
        : "Select a source CML version first…";
      targetVersionTrigger.disabled = true;
      closeVersionPicker(targetVersionPicker, targetVersionTrigger, targetVersionMenu);
      renderTargetVersions();
    }
    if (!org || !modelName) return;
    if (isCompareTarget) targetVersionDisplay.textContent = "Loading CML versions…";
    versionControl.innerHTML = '<option value="">Loading exact versions…</option>';
    try {
      const data = await getOrgModels(org, refresh);
      if (isCompareTarget && sequence !== targetModelLoadSequence) return;
      if (data.error) {
        versionControl.innerHTML = '<option value="">(could not load exact versions)</option>';
        if (isCompareTarget) targetVersionDisplay.textContent = "Unable to load CML versions";
        setStatus("err", `Could not load ${purpose} versions from ${org}:\n${data.error}`);
        return;
      }
      const versions = (data.models || []).filter(m => m.name === modelName);
      if (isCompareTarget) targetModels = versions;
      const targetRole = purpose === "compare" ? "Compare target" : "Deployment target";
      versionControl.innerHTML = `<option value="">None — select exact ${purpose} version</option>`
        + versions.map(m => `<option value="${m.versionId}">${m.name} · V${m.version} · ${m.status || "Unknown"}</option>`).join("");
      versionControl.value = "";
      if (isCompareTarget) {
        targetVersionFilter.value = "";
        targetVersionDisplay.textContent = versions.length ? "Select exact CML version" : "No matching CML versions found";
        targetVersionTrigger.disabled = !versions.length;
        renderTargetVersions();
      }
      if (data.runtimeStatusWarning) {
        setStatus(
          "info",
          `${targetRole} runtime activity could not be loaded. Labels are using `
          + "definition-version status.\n" + data.runtimeStatusWarning);
      }
    } catch (e) {
      if (isCompareTarget && sequence !== targetModelLoadSequence) return;
      if (e && e.conn) handleDisconnect();
      else setStatus("err", `Could not load ${purpose} versions: ${e}`);
    }
  }

  function renderTargetVersions() {
    const needle = targetVersionFilter.value.trim().toLowerCase();
    const versions = targetModels.filter(item =>
      !needle || item.name.toLowerCase().includes(needle)
      || String(item.version || "").includes(needle)
      || (item.status || "").toLowerCase().includes(needle));
    targetVersionOptions.innerHTML = versions.length
      ? versions.map(item => versionOptionHtml(item, targetVersionSel.value)).join("")
      : `<div class="version-empty">${targetModels.length ? "No CML versions match your search." : "No matching CML versions found."}</div>`;
  }

  orgSel.onchange = () => {
    const warning = orgSessionWarning(selectedOrgInfo(orgSel.value));
    if (warning) setStatus("err", warning);
    targetVersionSel.innerHTML = '<option value="">None — select target org and source version</option>';
    deployVersionSel.innerHTML = '<option value="">None — select deployment target and source version</option>';
    renderSelectedOrgIds();
    loadKeyFields();
    loadModels();
  };
  targetSel.onchange = () => {
    const warning = orgSessionWarning(selectedOrgInfo(targetSel.value));
    if (warning) setStatus("err", warning);
    renderSelectedOrgIds();
    loadKeyFields();
    loadTargetVersions(targetSel, targetVersionSel, "compare");
    loadAssociationArchives();
    loadDeploymentReports();
  };
  deployOrgSel.onchange = () => {
    const warning = orgSessionWarning(selectedOrgInfo(deployOrgSel.value));
    if (warning) setStatus("err", warning);
    loadTargetVersions(deployOrgSel, deployVersionSel, "deployment");
    readinessPanel.dataset.checked = "";
    loadCmlBackups();
    loadDeploymentReports();
  };
  deployVersionSel.addEventListener("change", loadCmlBackups);
  targetVersionSel.addEventListener("change", loadAssociationArchives);
  cmlFilter.oninput = renderModels;
  targetVersionFilter.oninput = renderTargetVersions;
  sourceVersionOptions.onclick = event => {
    const option = event.target.closest(".version-option");
    if (!option) return;
    model.value = option.dataset.value;
    model.dispatchEvent(new Event("change", { bubbles:true }));
  };
  targetVersionOptions.onclick = event => {
    const option = event.target.closest(".version-option");
    if (!option) return;
    targetVersionSel.value = option.dataset.value;
    const selected = targetModels.find(item => item.versionId === targetVersionSel.value);
    renderVersionTrigger(targetVersionDisplay, selected, "Select exact CML version");
    renderTargetVersions();
    closeVersionPicker(targetVersionPicker, targetVersionTrigger, targetVersionMenu);
    targetVersionSel.dispatchEvent(new Event("change", { bubbles:true }));
  };
  targetVersionSel.addEventListener("change", () => {
    const selected = targetModels.find(item => item.versionId === targetVersionSel.value);
    renderVersionTrigger(targetVersionDisplay, selected, "Select exact CML version");
    renderTargetVersions();
  });
  [cmlFilter, targetVersionFilter].forEach(search => {
    search.addEventListener("keydown", event => {
      if (event.key !== "Escape") return;
      const isSource = search === cmlFilter;
      closeVersionPicker(
        isSource ? combo : targetVersionPicker,
        isSource ? sourceVersionTrigger : targetVersionTrigger,
        isSource ? sourceVersionMenu : targetVersionMenu);
      (isSource ? sourceVersionTrigger : targetVersionTrigger).focus();
    });
  });
  document.addEventListener("mousedown", event => {
    if (!combo.contains(event.target)) closeVersionPicker(combo, sourceVersionTrigger, sourceVersionMenu);
    if (!targetVersionPicker.contains(event.target)) closeVersionPicker(targetVersionPicker, targetVersionTrigger, targetVersionMenu);
  });

  fetchBtn.onclick = async () => {
    if (!orgSel.value) { setStatus("err", "Please choose an org first."); return; }
    const source = selectedSourceVersion();
    if (!source) { setStatus("err", "Please select an exact CML version."); sourceVersionTrigger.focus(); return; }
    busy(fetchBtn, "Fetching…");
    setStatus("info", "Fetching " + selectedVersionLabel(source) + " from " + orgSel.value + "…");
    try {
      const data = await postJSON("/api/fetch", {
        org: orgSel.value, model: source.name, versionId: source.versionId
      });
      if (data.ok) {
        clearDraftForCurrentScope();
        setEditorContent(data.content);
        const savedNote = isBrowserSession()
          ? "Held in this tab. Use Download .cml to save a copy on disk."
          : ("Saved to: " + data.file);
        setStatus("ok", data.log + "\n\n" + savedNote);
      } else {
        setStatus("err", data.log || "Fetch failed.");
      }
    } catch (e) {
      if (e && e.conn) { handleDisconnect(); } else { setStatus("err", "Fetch error: " + e); }
    }
    idle();
    fetchBtn.focus();
  };

  function diagnosticText(diagnostic) {
    if (!diagnostic) return "";
    const lines = ["Salesforce REST diagnostic:"];
    if (diagnostic.status != null) lines.push(`HTTP status: ${diagnostic.status}`);
    if (diagnostic.requestId) lines.push(`Request ID: ${diagnostic.requestId}`);
    (diagnostic.errors || []).forEach(item => {
      let line = [item.errorCode, item.message].filter(Boolean).join(": ");
      if (item.fields && item.fields.length) line += ` · fields: ${item.fields.join(", ")}`;
      if (item.line != null || item.column != null) line += ` · line ${item.line ?? "?"}, column ${item.column ?? "?"}`;
      if (line) lines.push(line);
    });
    if (diagnostic.transportError) lines.push(`Transport: ${diagnostic.transportError}`);
    if (diagnostic.rawResponse) lines.push(`Response: ${diagnostic.rawResponse}`);
    return lines.join("\n");
  }

  function appendDiagnostic(message, diagnostic) {
    const details = diagnosticText(diagnostic);
    return details ? `${message}\n\n${details}` : message;
  }

  function renderReadiness(data) {
    const lifecycleActions = (_activateDisabled, deactivateDisabled) =>
      `<div class="lifecycle-actions" aria-label="Target CML lifecycle actions">`
      + `<button class="btn btn-danger" id="activateBtn" type="button" disabled title="Use Salesforce Constraint Builder so CML compilation and validation are enforced.">Activate in Salesforce</button>`
      + `<button class="ghost deactivate-action" id="deactivateBtn" type="button" ${deactivateDisabled ? "disabled" : ""}>Deactivate CML</button>`
      + `</div><p class="meta lifecycle-note">Select an exact target to deactivate it before fetch or deploy; the action checks its live status before confirmation. Activation must be completed in Salesforce Constraint Builder so its compiler and validation run. Direct IsActive activation is blocked by this tool.</p>`;
    if (!data.ok) {
      readinessPanel.innerHTML = `<div class="readiness-head"><strong>Target version status</strong><span class="chip warn">Unavailable</span></div><p>${esc(data.log || "Status check failed.")}</p>`
        + lifecycleActions(true, true);
      readinessPanel.dataset.checked = "";
      wireLifecycleActions();
      return;
    }
    const target = data.targetStatus || {};
    const eligible = target.status === "eligible";
    const observedStatus = String(target.versionStatus || "").toLowerCase();
    const active = observedStatus === "active";
    const inactive = observedStatus === "inactive";
    readinessPanel.innerHTML =
      `<div class="readiness-head"><strong>Target version status</strong><span class="chip ${eligible ? "ok" : "warn"}">${esc(target.status || "unverified")}</span></div>`
      + `<p><strong>${esc(target.versionStatus || "Unknown")}</strong></p>`
      + `<p class="readiness-item ${eligible ? "writable" : "blocked"}">${esc(target.message || "Target status was not verified.")}</p>`
      + lifecycleActions(!inactive, !active);
    readinessPanel.dataset.checked = "true";
    wireLifecycleActions();
  }

  async function checkReadiness() {
    const source = selectedSourceVersion();
    if (!deployOrgSel.value || !deployVersionSel.value || !source) {
      const data = { ok:false, log:"Choose a source model, deployment target org, and exact target version first." };
      renderReadiness(data);
      return data;
    }
    busy(readinessBtn, "Checking…");
    try {
      const data = await postJSON("/api/readiness", {
        org: deployOrgSel.value,
        model: source.name,
        targetVersionId: deployVersionSel.value,
      });
      renderReadiness(data);
      return data;
    } catch (error) {
      if (error && error.conn) handleDisconnect();
      const data = { ok:false, log:"Could not connect to the local readiness service." };
      renderReadiness(data);
      return data;
    } finally {
      readinessBtn.textContent = "Check target status";
      idle();
    }
  }

  readinessBtn.onclick = checkReadiness;
  deployVersionSel.onchange = () => {
    readinessPanel.dataset.checked = "";
    const activate = $("activateBtn"), deactivate = $("deactivateBtn");
    if (activate) activate.disabled = true;
    // Deactivation must be available before fetch/deploy. Its click handler
    // performs a fresh read-only status check before asking for confirmation,
    // and the server re-verifies the exact version before writing.
    if (deactivate) {
      deactivate.disabled = !(
        deployOrgSel.value && deployVersionSel.value
        && selectedSourceVersion());
    }
  };

  function wireLifecycleActions() {
    const activate = $("activateBtn"), deactivate = $("deactivateBtn");
    if (activate) activate.onclick = null;
    if (deactivate) deactivate.onclick = () => changeCmlLifecycle(false);
  }

  async function changeCmlLifecycle(active) {
    const dest = deployOrgSel.value;
    const source = selectedSourceVersion();
    const targetVersionId = deployVersionSel.value;
    if (!dest || !source || !targetVersionId) {
      setStatus("err", "Choose a source model, target org, and exact target version first.");
      return;
    }
    const readiness = await checkReadiness();
    if (!readiness.ok) {
      setStatus("err", readiness.log || "Target lifecycle status could not be verified.");
      return;
    }
    const currentlyActive = String(
      readiness.targetStatus?.versionStatus || "").toLowerCase() === "active";
    if (currentlyActive === active) {
      setStatus("info", `No change required — the exact target version is already ${active ? "Active" : "Inactive"}.`);
      return;
    }
    const action = active ? "Activate" : "Deactivate";
    const consequence = active
      ? "This compiles/enables the selected CML for runtime product configuration. Activation can fail if Salesforce validation or dependencies are incomplete."
      : "This immediately removes the selected CML version from runtime use. Reactivation is a separate validated operation and is not guaranteed to succeed.";
    const typed = await requestTypedConfirmation({
      title: `${action} CML`,
      description: consequence,
      target: `Model: ${source.name}\nTarget org: ${dest}\nExact version: ${targetVersionId}`,
      alias: dest,
      submitLabel: `${action} CML`,
    });
    if (typed !== dest) return;
    const button = active ? $("activateBtn") : $("deactivateBtn");
    if (button) {
      button.disabled = true;
      button.innerHTML = `<span class="spinner"></span>${active ? "Activating…" : "Deactivating…"}`;
    }
    document.querySelector(".app-main").setAttribute("aria-busy", "true");
    setStatus("info", `${action.slice(0, -1)}ing ${source.name} ${targetVersionId} in ${dest}…`);
    try {
      const data = await postJSON("/api/lifecycle", {
        org: dest,
        model: source.name,
        targetVersionId,
        active,
        confirmTarget: typed,
      });
      let details = data.log || `${action} operation failed.`;
      if (data.report?.file) details += `\nLifecycle report: ${data.report.file}`;
      if (data.reportError) details += `\nWARNING: ${data.reportError}`;
      setStatus(data.ok ? "ok" : "err", appendDiagnostic(details, data.diagnostic));
      await loadTargetVersions(
        deployOrgSel, deployVersionSel, "deployment", true);
      await loadDeploymentReports();
      if (Array.from(deployVersionSel.options).some(
          option => option.value === targetVersionId)) {
        deployVersionSel.value = targetVersionId;
        await checkReadiness();
      }
    } catch (error) {
      if (error && error.conn) handleDisconnect();
      else setStatus("err", `${action} error: ${error}`);
    } finally {
      document.querySelector(".app-main").removeAttribute("aria-busy");
    }
  }

  wireLifecycleActions();

  deployBtn.onclick = async () => {
    const dest = deployOrgSel.value;
    if (!dest) { setStatus("err", "Please choose an org to deploy to."); deployOrgSel.focus(); return; }
    const source = selectedSourceVersion();
    if (!source) { setStatus("err", "Please select an exact source CML version."); sourceVersionTrigger.focus(); return; }
    if (!deployVersionSel.value) { setStatus("err", "Please select an exact deployment target version."); deployVersionSel.focus(); return; }
    if (!content.value.trim()) { setStatus("err", "There is no CML content to deploy."); return; }
    const readiness = await checkReadiness();
    if (!readiness.ok || readiness.targetStatus?.status !== "eligible") {
      setStatus("err", readiness.log || readiness.targetStatus?.message || "Target version eligibility could not be established.");
      return;
    }
    const crossOrg = dest !== orgSel.value;
    const crossOrgWarning = crossOrg
      ? ` Source org is "${orgSel.value}", so this is a cross-org deployment.` : "";
    const typed = await requestTypedConfirmation({
      title: "Deploy CML",
      description: "This overwrites only the selected target version. A backup and read-after-write verification remain required." + crossOrgWarning,
      target: `Model: ${source.name}\nTarget org: ${dest}\nExact version: ${deployVersionSel.value}`,
      alias: dest,
      submitLabel: "Deploy CML",
    });
    if (typed !== dest) return;
    busy(deployBtn, "Deploying…");
    setStatus("info", "Deploying " + source.name + " to " + dest + " version " + deployVersionSel.value + "…");
    try {
      const data = await postJSON("/api/deploy", {
        org: dest, model: source.name,
        targetVersionId: deployVersionSel.value, content: content.value,
        confirmTarget: typed
      });
      let details = data.log || (data.ok ? "Deployed." : "Deploy failed.");
      if (data.backup && data.backup.file) details += `\n\nRecovery backup: ${data.backup.file}`;
      if (data.report && data.report.file) details += `\nDeployment report: ${data.report.file}`;
      if (data.reportError) details += `\nWARNING: ${data.reportError}`;
      setStatus(data.ok ? "ok" : "err", appendDiagnostic(details, data.diagnostic));
      if (data.ok) {
        clearDraftForCurrentScope();
        editorBaseline = content.value;
        updateDirtyIndicator();
      }
      await loadCmlBackups();
      await loadDeploymentReports();
    } catch (e) {
      if (e && e.conn) { handleDisconnect(); } else { setStatus("err", "Deploy error: " + e); }
    }
    idle();
    deployBtn.focus();
  };

  function setArchiveButtons() {
    const has = Boolean(archiveSelect && archiveSelect.value);
    if (restoreListedArchiveBtn) restoreListedArchiveBtn.disabled = !has;
    if (downloadArchiveBtn) downloadArchiveBtn.disabled = !has;
  }

  async function loadAssociationArchives() {
    if (!archiveSelect) return;
    archiveSelect.innerHTML = '<option value="">No archive selected</option>';
    setArchiveButtons();
    const dest = targetSel.value;
    const selectedModel = selectedModelName();
    const targetVersionId = targetVersionSel.value;
    if (!isBrowserSession() || !dest || !selectedModel || !targetVersionId) return;
    try {
      const list = await apiGet(`/api/archives?org=${encodeURIComponent(dest)}&model=${encodeURIComponent(selectedModel)}&versionId=${encodeURIComponent(targetVersionId)}`);
      if (!list.ok) return;
      for (const archive of list.archives || []) {
        const option = document.createElement("option");
        option.value = archive.id;
        option.textContent = `${archive.createdAt || "Unknown time"} · ${archive.id}`;
        archiveSelect.appendChild(option);
      }
      if ((list.archives || []).length) archiveSelect.value = list.archives[0].id;
      setArchiveButtons();
    } catch (error) {
      if (error && error.conn) handleDisconnect();
    }
  }

  async function fillReportSelect(select, org, downloadBtn) {
    if (!select) return;
    select.innerHTML = '<option value="">No report selected</option>';
    if (downloadBtn) downloadBtn.disabled = true;
    const selectedModel = selectedModelName();
    if (!isBrowserSession() || !org || !selectedModel) return;
    try {
      const list = await apiGet(`/api/reports?org=${encodeURIComponent(org)}&model=${encodeURIComponent(selectedModel)}`);
      if (!list.ok) return;
      for (const report of list.reports || []) {
        const option = document.createElement("option");
        option.value = report.id;
        const outcome = report.success === false ? "failed" : (report.success ? "ok" : "report");
        option.textContent = `${report.createdAt || "Unknown time"} · ${report.action || "report"} · ${outcome}`;
        select.appendChild(option);
      }
      if ((list.reports || []).length) select.value = list.reports[0].id;
      if (downloadBtn) downloadBtn.disabled = !select.value;
    } catch (error) {
      if (error && error.conn) handleDisconnect();
    }
  }

  async function loadDeploymentReports() {
    await fillReportSelect(reportSelect, deployOrgSel.value, downloadReportBtn);
    await fillReportSelect(dataReportSelect, targetSel.value, downloadDataReportBtn);
  }

  async function downloadStoredReport(reportId, statusEl) {
    if (!reportId) {
      setStatus("err", "Select a report to download.", statusEl);
      return;
    }
    try {
      const data = await apiGet("/api/report?id=" + encodeURIComponent(reportId));
      if (!data.ok) {
        setStatus("err", data.log || "Could not download that report.", statusEl);
        return;
      }
      const payload = Object.assign({}, data);
      delete payload.ok;
      delete payload.log;
      payload.kind = "deployment-report";
      downloadTextFile(data.id || "deployment-report.json", JSON.stringify(payload, null, 2), "application/json");
      setStatus("ok", "Downloaded report " + (data.id || "") + ".", statusEl);
    } catch (e) {
      if (e && e.conn) { handleDisconnect(); } else { setStatus("err", "Report download error: " + e, statusEl); }
    }
  }

  async function loadCmlBackups() {
    const dest = deployOrgSel.value;
    const selectedModel = selectedModelName();
    const targetVersionId = deployVersionSel.value;
    backupSelect.innerHTML = '<option value="">No backup selected</option>';
    rollbackBtn.disabled = true;
    if (downloadBackupBtn) downloadBackupBtn.disabled = true;
    if (!dest || !selectedModel || !targetVersionId) return;
    try {
      const list = await apiGet(`/api/backups?org=${encodeURIComponent(dest)}&model=${encodeURIComponent(selectedModel)}&versionId=${encodeURIComponent(targetVersionId)}`);
      if (!list.ok) return;
      for (const backup of list.backups || []) {
        const option = document.createElement("option");
        option.value = backup.id;
        option.textContent = `${backup.createdAt || "Unknown time"} · ${backup.reason || "CML backup"} · ${String(backup.sha256 || "").slice(0, 10)}`;
        backupSelect.appendChild(option);
      }
      if ((list.backups || []).length) backupSelect.value = list.backups[0].id;
      rollbackBtn.disabled = !backupSelect.value;
      if (downloadBackupBtn) downloadBackupBtn.disabled = !backupSelect.value;
    } catch (error) {
      if (error && error.conn) handleDisconnect();
    }
  }
  backupSelect.addEventListener("change", () => {
    rollbackBtn.disabled = !backupSelect.value;
    if (downloadBackupBtn) downloadBackupBtn.disabled = !backupSelect.value;
  });

  rollbackBtn.onclick = async () => {
    const dest = deployOrgSel.value;
    const source = selectedSourceVersion();
    const selectedModel = source && source.name;
    const targetVersionId = deployVersionSel.value;
    if (!dest || !selectedModel || !targetVersionId) { setStatus("err", "Choose a target org, model, and exact target version first."); return; }
    try {
      const list = await apiGet(`/api/backups?org=${encodeURIComponent(dest)}&model=${encodeURIComponent(selectedModel)}&versionId=${encodeURIComponent(targetVersionId)}`);
      const backup = (list.backups || []).find(item => item.id === backupSelect.value);
      if (!backup) { setStatus("err", "Select an available backup for this exact target version."); await loadCmlBackups(); return; }
      const typed = await requestTypedConfirmation({
        title: "Restore CML backup",
        description: "This replaces the exact target version with the selected saved backup.",
        target: `Target org: ${dest}\nExact version: ${targetVersionId}\nBackup: ${backup.createdAt || "unknown time"}\nReason: ${backup.reason || "CML backup"}`,
        alias: dest,
        submitLabel: "Restore backup",
      });
      if (typed !== dest) return;
      busy(rollbackBtn, "Restoring…");
      const data = await postJSON("/api/rollback", {
        org: dest, model: selectedModel, backupId: backup.id,
        targetVersionId,
        confirmTarget: typed
      });
      if (data.ok && typeof data.content === "string") setEditorContent(data.content);
      let details = data.log || (data.ok ? "Rollback complete." : "Rollback failed.");
      if (data.report && data.report.file) details += `\nDeployment report: ${data.report.file}`;
      setStatus(data.ok ? "ok" : "err", appendDiagnostic(details, data.diagnostic));
      await loadCmlBackups();
      await loadDeploymentReports();
    } catch (e) {
      if (e && e.conn) { handleDisconnect(); } else { setStatus("err", "Rollback error: " + e); }
    }
    idle();
    rollbackBtn.focus();
  };

  copyBtn.onclick = async () => {
    if (!content.value) return;
    try { await navigator.clipboard.writeText(content.value); copyBtn.textContent = "Copied!"; setTimeout(() => copyBtn.textContent = "Copy", 1200); }
    catch (e) { content.select(); document.execCommand("copy"); }
  };

  if (downloadCmlBtn) {
    downloadCmlBtn.onclick = () => {
      if (!content.value) {
        setStatus("err", "Nothing to download. Fetch or paste CML first.");
        return;
      }
      const source = selectedSourceVersion();
      const name = ((source && source.name) || "model") + ".cml";
      downloadTextFile(name, content.value, "text/plain;charset=utf-8");
    };
  }

  if (downloadBackupBtn) {
    downloadBackupBtn.onclick = async () => {
      if (!backupSelect.value) {
        setStatus("err", "Select a recovery backup to download.");
        return;
      }
      busy(downloadBackupBtn, "Downloading…");
      try {
        const data = await apiGet("/api/backup?id=" + encodeURIComponent(backupSelect.value));
        if (!data.ok) {
          setStatus("err", data.log || "Could not download that backup.");
          return;
        }
        const payload = JSON.stringify({
          kind: "cml-backup",
          id: data.id,
          createdAt: data.createdAt,
          reason: data.reason,
          sha256: data.sha256,
          org: data.org,
          model: data.model,
          versionId: data.versionId,
          versionNumber: data.versionNumber,
          versionStatus: data.versionStatus,
          content: data.content || "",
        }, null, 2);
        downloadTextFile(data.id || "cml-backup.json", payload, "application/json");
        setStatus("ok", "Downloaded backup " + (data.id || "") + ".");
      } catch (e) {
        if (e && e.conn) { handleDisconnect(); } else { setStatus("err", "Backup download error: " + e); }
      }
      downloadBackupBtn.textContent = "Download backup";
      idle();
    };
  }

  if (importBackupBtn) {
    importBackupBtn.onclick = async () => {
      const payload = await pickJsonFile();
      if (!payload) return;
      if (payload._parseError) {
        setStatus("err", "That file is not valid JSON.");
        return;
      }
      try {
        const imported = await postJSON("/api/backup/import", { backup: payload });
        setStatus(imported.ok ? "ok" : "err", imported.log || "Import finished.");
        if (imported.ok) await loadCmlBackups();
      } catch (e) {
        if (e && e.conn) { handleDisconnect(); } else { setStatus("err", "Backup import error: " + e); }
      }
    };
  }

  if (sessionDebugBtn) {
    sessionDebugBtn.onclick = async () => {
      try {
        const data = await apiGet("/api/debug");
        setStatus(data.ok ? "info" : "err", data.log || "Session status unavailable.");
      } catch (e) {
        if (e && e.conn) { handleDisconnect(); } else { setStatus("err", "Session status error: " + e); }
      }
    };
  }

  if (archiveSelect) {
    archiveSelect.addEventListener("change", setArchiveButtons);
  }

  if (restoreListedArchiveBtn) {
    restoreListedArchiveBtn.onclick = async () => {
      const dest = targetSel.value;
      const source = selectedSourceVersion();
      const dataStatus = $("dataStatus") || status;
      if (!dest || !source || !targetVersionSel.value || !archiveSelect.value) {
        setStatus("err", "Select a target org, exact version, and archive first.", dataStatus);
        return;
      }
      const typed = await requestTypedConfirmation({
        title: "Restore deleted associations",
        description: "This recreates associations from the selected local recovery archive.",
        target: `Target org: ${dest}\nModel: ${source.name}\nExact version: ${targetVersionSel.value}\nArchive: ${archiveSelect.value}`,
        alias: dest,
        submitLabel: "Restore associations",
      });
      if (typed !== dest) return;
      busy(restoreListedArchiveBtn, "Restoring…");
      try {
        const restored = await postJSON("/api/data/restore", {
          targetOrg: dest, model: source.name,
          targetVersionId: targetVersionSel.value,
          archiveId: archiveSelect.value, confirmTarget: typed
        });
        setStatus(restored.ok ? "ok" : "err", restored.log || "Association restore finished.", dataStatus);
        await loadAssociationArchives();
        await loadDeploymentReports();
      } catch (e) {
        if (e && e.conn) { handleDisconnect(); } else { setStatus("err", "Restore error: " + e, dataStatus); }
      }
      restoreListedArchiveBtn.textContent = "Restore archive";
      idle();
    };
  }

  if (downloadArchiveBtn) {
    downloadArchiveBtn.onclick = async () => {
      const dataStatus = $("dataStatus") || status;
      if (!archiveSelect.value) {
        setStatus("err", "Select an archive to download.", dataStatus);
        return;
      }
      try {
        const data = await apiGet("/api/archive?id=" + encodeURIComponent(archiveSelect.value));
        if (!data.ok) {
          setStatus("err", data.log || "Could not download that archive.", dataStatus);
          return;
        }
        const payload = JSON.stringify({
          kind: "association-delete-archive",
          id: data.id,
          createdAt: data.createdAt,
          org: data.org,
          targetOrg: data.targetOrg,
          model: data.model,
          versionId: data.versionId,
          expressionSetId: data.expressionSetId,
          keyField: data.keyField,
          expressionSetStatus: data.expressionSetStatus,
          prcIdentityVersion: data.prcIdentityVersion,
          rows: data.rows || [],
        }, null, 2);
        downloadTextFile(data.id || "association-archive.json", payload, "application/json");
        setStatus("ok", "Downloaded archive " + (data.id || "") + ".", dataStatus);
      } catch (e) {
        if (e && e.conn) { handleDisconnect(); } else { setStatus("err", "Archive download error: " + e, dataStatus); }
      }
    };
  }

  if (importArchiveBtn) {
    importArchiveBtn.onclick = async () => {
      const dataStatus = $("dataStatus") || status;
      const payload = await pickJsonFile();
      if (!payload) return;
      if (payload._parseError) {
        setStatus("err", "That file is not valid JSON.", dataStatus);
        return;
      }
      try {
        const imported = await postJSON("/api/archive/import", { archive: payload });
        setStatus(imported.ok ? "ok" : "err", imported.log || "Import finished.", dataStatus);
        if (imported.ok) await loadAssociationArchives();
      } catch (e) {
        if (e && e.conn) { handleDisconnect(); } else { setStatus("err", "Archive import error: " + e, dataStatus); }
      }
    };
  }

  if (reportSelect) {
    reportSelect.addEventListener("change", () => {
      if (downloadReportBtn) downloadReportBtn.disabled = !reportSelect.value;
    });
  }
  if (dataReportSelect) {
    dataReportSelect.addEventListener("change", () => {
      if (downloadDataReportBtn) downloadDataReportBtn.disabled = !dataReportSelect.value;
    });
  }
  if (downloadReportBtn) {
    downloadReportBtn.onclick = () => downloadStoredReport(reportSelect && reportSelect.value, status);
  }
  if (downloadDataReportBtn) {
    downloadDataReportBtn.onclick = () => downloadStoredReport(
      dataReportSelect && dataReportSelect.value, $("dataStatus") || status);
  }
  if (importReportBtn) {
    importReportBtn.onclick = async () => {
      const payload = await pickJsonFile();
      if (!payload) return;
      if (payload._parseError) {
        setStatus("err", "That file is not valid JSON.");
        return;
      }
      try {
        const imported = await postJSON("/api/report/import", { report: payload });
        setStatus(imported.ok ? "ok" : "err", imported.log || "Import finished.");
        if (imported.ok) await loadDeploymentReports();
      } catch (e) {
        if (e && e.conn) { handleDisconnect(); } else { setStatus("err", "Report import error: " + e); }
      }
    };
  }

  // ---- Compare (source org vs target org) ----
  const cmpStatus = $("compareStatus") || status;
  compareBtn.onclick = async () => {
    if (!orgSel.value) { setStatus("err", "Please choose a source org.", cmpStatus); return; }
    if (!targetSel.value) { setStatus("err", "Please choose a target org.", cmpStatus); return; }
    const source = selectedSourceVersion();
    if (!source) { setStatus("err", "Please select an exact source CML version.", cmpStatus); sourceVersionTrigger.focus(); return; }
    if (!targetVersionSel.value) { setStatus("err", "Please select an exact compare target version.", cmpStatus); targetVersionTrigger.focus(); return; }
    busy(compareBtn, "Comparing…");
    editingTarget = false;
    updateTargetEditUi();
    diffBox.classList.remove("show");
    setStatus("info", `Comparing "${source.name}" ${source.versionId} between ${orgSel.value} (source) and ${targetSel.value} target version ${targetVersionSel.value}…\nThis fetches the CML from both orgs and can take up to a minute — please wait.`, cmpStatus);
    try {
      const d = await postJSON("/api/compare", {
        sourceOrg: orgSel.value, targetOrg: targetSel.value,
        model: source.name, sourceVersionId: source.versionId,
        targetVersionId: targetVersionSel.value
      });
      if (d.ok) {
        lastCompare = {
          src: d.source,
          tgt: { ...d.target },
          originalTargetContent: d.target.content || "",
          mergeCount: 0,
          semantic: d.semantic || null
        };
        renderCompare();
        setStatus("ok", `Compared "${d.model}".\nSource: ${d.source.file}\nTarget: ${d.target.file}`, cmpStatus);
      } else {
        setStatus("err", d.log || "Compare failed.", cmpStatus);
      }
    } catch (e) {
      if (e && e.conn) { handleDisconnect(); } else { setStatus("err", "Compare error: " + e, cmpStatus); }
    }
    idle();
  };

  function esc(s) { return (s == null ? "" : String(s)).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;"); }

  // Myers line diff -> ordered ops (eq / del / ins). Trace memory is bounded
  // so a completely unrelated pair of very large files cannot freeze the UI.
  const MYERS_MAX_TRACE_CELLS = 4_000_000;
  const MYERS_MAX_LINES = 100_000;

  function coarseDiffOps(a, b) {
    let prefix = 0;
    while (prefix < a.length && prefix < b.length && a[prefix] === b[prefix]) prefix++;
    let suffix = 0;
    while (
      suffix < a.length - prefix
      && suffix < b.length - prefix
      && a[a.length - 1 - suffix] === b[b.length - 1 - suffix]
    ) suffix++;
    const ops = [];
    for (let i = 0; i < prefix; i++) ops.push({ t:"eq", a:i, b:i });
    for (let i = prefix; i < a.length - suffix; i++) ops.push({ t:"del", a:i });
    for (let j = prefix; j < b.length - suffix; j++) ops.push({ t:"ins", b:j });
    for (let x = suffix - 1; x >= 0; x--) {
      ops.push({ t:"eq", a:a.length - 1 - x, b:b.length - 1 - x });
    }
    return ops;
  }

  function diffOps(a, b) {
    const n = a.length, m = b.length;
    if (!n) return b.map((_, index) => ({ t:"ins", b:index }));
    if (!m) return a.map((_, index) => ({ t:"del", a:index }));
    const max = n + m;
    if (max > MYERS_MAX_LINES) return coarseDiffOps(a, b);

    const vectorSize = 2 * max + 3;
    const offset = max + 1;
    const editBudget = Math.min(
      max,
      Math.max(1, Math.floor(MYERS_MAX_TRACE_CELLS / vectorSize))
    );
    let frontier = new Int32Array(vectorSize);
    frontier.fill(-1);
    frontier[offset + 1] = 0;
    const trace = [];

    for (let distance = 0; distance <= editBudget; distance++) {
      trace.push(frontier.slice());
      for (let diagonal = -distance; diagonal <= distance; diagonal += 2) {
        const index = offset + diagonal;
        let x;
        if (
          diagonal === -distance
          || (diagonal !== distance && frontier[index - 1] < frontier[index + 1])
        ) {
          x = frontier[index + 1];
        } else {
          x = frontier[index - 1] + 1;
        }
        let y = x - diagonal;
        while (x < n && y < m && a[x] === b[y]) { x++; y++; }
        frontier[index] = x;
        if (x < n || y < m) continue;

        const reversed = [];
        let backX = n, backY = m;
        for (let d = distance; d >= 0; d--) {
          const prior = trace[d];
          const currentDiagonal = backX - backY;
          const currentIndex = offset + currentDiagonal;
          const previousDiagonal = (
            currentDiagonal === -d
            || (currentDiagonal !== d
              && prior[currentIndex - 1] < prior[currentIndex + 1])
          ) ? currentDiagonal + 1 : currentDiagonal - 1;
          const previousX = prior[offset + previousDiagonal];
          const previousY = previousX - previousDiagonal;
          while (backX > previousX && backY > previousY) {
            reversed.push({ t:"eq", a:backX - 1, b:backY - 1 });
            backX--;
            backY--;
          }
          if (d === 0) break;
          if (backX === previousX) {
            reversed.push({ t:"ins", b:backY - 1 });
            backY--;
          } else {
            reversed.push({ t:"del", a:backX - 1 });
            backX--;
          }
        }
        return reversed.reverse();
      }
    }
    return coarseDiffOps(a, b);
  }

  // A row rendered into a pane table. `marker` is a glyph cue (+ - ~) so the
  // diff is readable without relying on color (colorblind-friendly).
  function semanticLineMaps() {
    const source = new Map(), target = new Map();
    if (!semanticChk.checked || !lastCompare || !lastCompare.semantic) return { source, target };
    const priority = { AMBIGUOUS:5, MODIFIED:4, MOVED:3, REMOVED:2, ADDED:2 };
    const add = (map, range, entity) => {
      if (!range || entity.status === "UNCHANGED") return;
      for (let line = range.startLine; line <= range.endLine; line++) {
        const mark = map.get(line) || { statuses:[], badges:[] };
        if (!mark.statuses.includes(entity.status)) mark.statuses.push(entity.status);
        if (line === range.startLine) mark.badges.push(entity);
        mark.statuses.sort((a, b) => (priority[b] || 0) - (priority[a] || 0));
        map.set(line, mark);
      }
    };
    (lastCompare.semantic.entities || []).forEach(entity => {
      add(source, entity.sourceRange, entity);
      add(target, entity.targetRange, entity);
    });
    return { source, target };
  }

  function semanticTooltip(entity) {
    const changes = (entity.propertyChanges || []).map(change => change.property);
    return `${entity.identity || entity.name || entity.kind}: ${entity.status}`
      + (changes.length ? ` · changed ${changes.join(", ")}` : "")
      + (entity.reason ? ` · ${entity.reason}` : "");
  }

  function semanticDecoration(mark) {
    if (!mark) return { className:"", badges:"" };
    const status = (mark.statuses[0] || "").toLowerCase();
    const badges = mark.badges.map(entity =>
      `<span class="semantic-badge ${entity.status.toLowerCase()}" title="${esc(semanticTooltip(entity)).replace(/"/g, "&quot;")}">${esc(entity.status)}</span>`
    ).join("");
    return { className: status ? ` sem-${status}` : "", badges };
  }

  function paneRow(rowType, num, codeHtml, marker, semanticMark, draftChanged) {
    const baseClass = rowType === "eq" ? "eqrow"
      : rowType === "chg" ? "row-chg"
      : rowType === "del" ? "row-del"
      : rowType === "ins" ? "row-ins" : "row-filler";
    if (rowType === "filler") {
      return `<tr class="row-filler"><td class="gutter">&nbsp;</td><td class="code">&nbsp;</td></tr>`;
    }
    const semantic = semanticDecoration(semanticMark);
    const mk = `<span class="mk">${marker}</span>`;
    return `<tr class="${baseClass}${semantic.className}${draftChanged ? " row-draft" : ""}"><td class="gutter">${num}</td><td class="code">${mk}${semantic.badges}${codeHtml}</td></tr>`;
  }

  // Differences between the working draft and the target fetched from
  // Salesforce; each one can be reverted independently.
  function draftRevertHunks(currentLines) {
    if (!lastCompare) return [];
    const original = (lastCompare.originalTargetContent || "").replace(/\r\n/g, "\n").split("\n");
    if (original.join("\n") === currentLines.join("\n")) return [];
    const hunks = [];
    let removed = [], added = [];
    const flush = nextCurrentLine => {
      if (!removed.length && !added.length) return;
      hunks.push({
        currentStart: added.length ? added[0] : nextCurrentLine,
        currentDeleteCount: added.length,
        originalLines: removed.map(index => original[index]),
      });
      removed = []; added = [];
    };
    for (const op of diffOps(original, currentLines)) {
      if (op.t === "eq") flush(op.b);
      else if (op.t === "del") removed.push(op.a);
      else added.push(op.b);
    }
    flush(currentLines.length);
    return hunks;
  }

  function revertRailButtons(row) {
    const ids = row.b != null && virtualDiffState ? virtualDiffState.revertAnchors.get(row.b) : null;
    return (ids || []).map(index =>
      `<button type="button" class="merge-arrow revert-arrow" data-revert-hunk="${index}" title="Revert this target-draft change to the version fetched from Salesforce" aria-label="Revert target-draft change">←</button>`
    ).join("");
  }

  function railCell(buttons, count) {
    if (!buttons) return "&nbsp;";
    return `<div class="rail-actions${count > 1 ? " multi" : ""}">${buttons}</div>`;
  }

  function semanticMergeActions(sourceLines, targetLines) {
    const semantic = lastCompare && lastCompare.semantic;
    if (!semanticChk.checked || !semantic) return [];
    const candidates = (semantic.entities || []).filter(entity =>
      ["ADDED", "REMOVED", "MODIFIED", "MOVED"].includes(entity.status));
    const actions = candidates.filter(entity => !candidates.some(parent =>
      parent !== entity
      && parent.kind === "type"
      && parent.identity === `type:${entity.scope}`
      && ["ADDED", "REMOVED", "MODIFIED", "MOVED"].includes(parent.status)));

    const insertionIndex = entity => {
      const sourceRange = entity.sourceRange;
      if (!sourceRange) return targetLines.length;
      const peers = (semantic.entities || []).filter(peer =>
        peer !== entity && peer.sourceRange && peer.targetRange
        && peer.status !== "AMBIGUOUS");
      const before = peers
        .filter(peer => peer.sourceRange.endLine < sourceRange.startLine)
        .sort((left, right) => right.sourceRange.endLine - left.sourceRange.endLine)[0];
      if (before) return before.targetRange.endLine;
      const after = peers
        .filter(peer => peer.sourceRange.startLine > sourceRange.endLine)
        .sort((left, right) => left.sourceRange.startLine - right.sourceRange.startLine)[0];
      if (after) return Math.max(0, after.targetRange.startLine - 1);
      return targetLines.length;
    };

    return actions.map(entity => {
      const sourceRange = entity.sourceRange;
      const targetRange = entity.targetRange;
      const sourceBlock = sourceRange
        ? sourceLines.slice(sourceRange.startLine - 1, sourceRange.endLine)
        : [];
      const targetStart = targetRange
        ? targetRange.startLine - 1 : insertionIndex(entity);
      const targetDeleteCount = targetRange
        ? targetRange.endLine - targetRange.startLine + 1 : 0;
      const titles = {
        ADDED: "Remove this target-only entity from the target draft",
        REMOVED: "Add this complete source-only entity to the target draft",
        MODIFIED: "Replace the complete target entity with the source entity",
        MOVED: "Move the complete target entity to its source position",
      };
      return {
        semantic: true,
        status: entity.status,
        identity: entity.identity,
        sourceLead: sourceRange && sourceRange.startLine,
        targetLead: targetRange && targetRange.startLine,
        targetStart: entity.status === "MOVED"
          ? insertionIndex(entity) : targetStart,
        targetDeleteCount,
        moveFrom: entity.status === "MOVED" ? targetStart : null,
        sourceLines: entity.status === "ADDED" ? [] : sourceBlock,
        title: titles[entity.status],
      };
    });
  }

  function mergeRailRow(row, renderedSemanticActions) {
    if (semanticChk.checked) {
      const ids = [];
      activeMergeHunks.forEach((action, index) => {
        if (!action.semantic || renderedSemanticActions.has(index)) return;
        const sourceMatch = action.sourceLead && row.a + 1 === action.sourceLead;
        const targetMatch = !action.sourceLead && action.targetLead && row.b + 1 === action.targetLead;
        if (sourceMatch || targetMatch) {
          ids.push(index);
          renderedSemanticActions.add(index);
        }
      });
      const reverts = revertRailButtons(row);
      const buttons = ids.map(index => {
        const action = activeMergeHunks[index];
        return `<button type="button" class="merge-arrow semantic-merge-arrow" data-merge-hunk="${index}" title="${esc(action.title)}" aria-label="${esc(action.title)}">→</button>`;
      }).join("") + reverts;
      const count = ids.length + (reverts.match(/data-revert-hunk/g) || []).length;
      return `<tr${row.type === "eq" ? ' class="eqrow"' : ""}><td>${railCell(buttons, count)}</td></tr>`;
    }
    const reverts = revertRailButtons(row);
    const revertCount = (reverts.match(/data-revert-hunk/g) || []).length;
    if (row.type === "eq") return `<tr class="eqrow"><td>${railCell(reverts, revertCount)}</td></tr>`;
    const button = row.mergeLead
      ? `<button type="button" class="merge-arrow" data-merge-hunk="${row.mergeId}" title="Apply this source change to the target draft" aria-label="Apply source change to target draft">→</button>`
      : "";
    return `<tr><td>${railCell(button + reverts, (button ? 1 : 0) + revertCount)}</td></tr>`;
  }

  function updateMergeWorkflow() {
    const count = lastCompare ? lastCompare.mergeCount || 0 : 0;
    mergeWorkflow.hidden = count === 0;
    if (!count) return;
    mergeWorkflowCopy.textContent = `${count} change${count === 1 ? "" : "s"} applied to the target working draft by merge or direct edit. Salesforce has not been changed yet.`;
  }

  const VIRTUAL_DIFF_THRESHOLD = 1_000;
  const VIRTUAL_DIFF_OVERSCAN = 24;
  const DIFF_ROW_HEIGHT = 18.75;

  function diffSpacer(height, columns) {
    if (height <= 0) return "";
    return `<tr class="virtual-spacer" aria-hidden="true"><td colspan="${columns}"><div data-spacer-height="${height}"></div></td></tr>`;
  }

  function renderVirtualDiffWindow() {
    if (!virtualDiffState) return;
    const { a, b, semanticMaps, draftLines, revertAnchors } = virtualDiffState;
    const visibleRows = onlyDiffs.checked
      ? virtualDiffState.rows.filter(row => row.type !== "eq"
        || draftLines.has(row.b) || revertAnchors.has(row.b))
      : virtualDiffState.rows;
    const virtual = visibleRows.length > VIRTUAL_DIFF_THRESHOLD;
    const viewportRows = Math.ceil(
      (srcScroll.clientHeight || 600) / DIFF_ROW_HEIGHT);
    const start = virtual
      ? Math.max(0, Math.floor(srcScroll.scrollTop / DIFF_ROW_HEIGHT)
        - VIRTUAL_DIFF_OVERSCAN)
      : 0;
    const end = virtual
      ? Math.min(
        visibleRows.length,
        start + viewportRows + VIRTUAL_DIFF_OVERSCAN * 2)
      : visibleRows.length;
    const topHeight = virtual ? start * DIFF_ROW_HEIGHT : 0;
    const bottomHeight = virtual
      ? (visibleRows.length - end) * DIFF_ROW_HEIGHT : 0;
    let left = diffSpacer(topHeight, 2);
    let middle = diffSpacer(topHeight, 1);
    let right = diffSpacer(topHeight, 2);
    const renderedSemanticActions = new Set();
    for (let index = start; index < end; index++) {
      const row = visibleRows[index];
      middle += mergeRailRow(row, renderedSemanticActions);
      if (row.type === "eq") {
        left += paneRow("eq", row.a + 1, esc(a[row.a]), " ", semanticMaps.source.get(row.a + 1));
        right += paneRow("eq", row.b + 1, esc(b[row.b]), " ", semanticMaps.target.get(row.b + 1), draftLines.has(row.b));
      } else if (row.type === "chg") {
        left += paneRow("chg", row.a + 1, esc(a[row.a]), "~", semanticMaps.source.get(row.a + 1));
        right += paneRow("chg", row.b + 1, esc(b[row.b]), "~", semanticMaps.target.get(row.b + 1), draftLines.has(row.b));
      } else if (row.type === "del") {
        left += paneRow("del", row.a + 1, esc(a[row.a]), "−", semanticMaps.source.get(row.a + 1));
        right += paneRow("filler");
      } else {
        left += paneRow("filler");
        right += paneRow("ins", row.b + 1, esc(b[row.b]), "+", semanticMaps.target.get(row.b + 1), draftLines.has(row.b));
      }
    }
    left += diffSpacer(bottomHeight, 2);
    middle += diffSpacer(bottomHeight, 1);
    right += diffSpacer(bottomHeight, 2);
    srcTable.innerHTML = "<tbody>" + left + "</tbody>";
    mergeTable.innerHTML = "<tbody>" + middle + "</tbody>";
    tgtTable.innerHTML = "<tbody>" + right + "</tbody>";
    [srcTable, mergeTable, tgtTable].forEach(table => {
      table.querySelectorAll("[data-spacer-height]").forEach(spacer => {
        spacer.style.height = `${spacer.dataset.spacerHeight}px`;
      });
    });
    diffPanes.dataset.virtualized = virtual ? "true" : "false";
  }

  function renderDiff(src, tgt) {
    const a = (src.content || "").replace(/\r\n/g, "\n").split("\n");
    const b = (tgt.content || "").replace(/\r\n/g, "\n").split("\n");
    const ops = diffOps(a, b);
    const semanticMaps = semanticLineMaps();
    activeMergeHunks = [];
    const semanticMode = semanticChk.checked;

    // Pair runs of del/ins into aligned "changed" rows.
    const rows = []; let pendDel = [], pendIns = [];
    const flush = (nextTargetLine) => {
      if (!pendDel.length && !pendIns.length) return;
      const mergeId = semanticMode ? -1 : activeMergeHunks.length;
      if (!semanticMode) {
        activeMergeHunks.push({
          targetStart: pendIns.length ? pendIns[0] : nextTargetLine,
          targetDeleteCount: pendIns.length,
          sourceLines: pendDel.map(index => a[index])
        });
      }
      const k = Math.max(pendDel.length, pendIns.length);
      for (let x = 0; x < k; x++) {
        const d = pendDel[x], ins = pendIns[x];
        const merge = { mergeId, mergeLead: x === 0 };
        if (d != null && ins != null) rows.push({ type: "chg", a: d, b: ins, ...merge });
        else if (d != null) rows.push({ type: "del", a: d, ...merge });
        else rows.push({ type: "ins", b: ins, ...merge });
      }
      pendDel = []; pendIns = [];
    };
    for (const op of ops) {
      if (op.t === "eq") { flush(op.b); rows.push({ type: "eq", a: op.a, b: op.b }); }
      else if (op.t === "del") pendDel.push(op.a);
      else pendIns.push(op.b);
    }
    flush(b.length);
    if (semanticMode) activeMergeHunks = semanticMergeActions(a, b);

    const chg = rows.filter(row => row.type === "chg").length;
    const del = rows.filter(row => row.type === "del").length;
    const ins = rows.filter(row => row.type === "ins").length;
    compareHasDiffs = chg + del + ins > 0;
    activeRevertHunks = draftRevertHunks(b);
    const revertAnchors = new Map(), draftLines = new Set();
    activeRevertHunks.forEach((hunk, index) => {
      const anchor = Math.max(0, Math.min(hunk.currentStart, b.length - 1));
      if (!revertAnchors.has(anchor)) revertAnchors.set(anchor, []);
      revertAnchors.get(anchor).push(index);
      for (let line = hunk.currentStart; line < hunk.currentStart + hunk.currentDeleteCount; line++) {
        draftLines.add(line);
      }
    });
    virtualDiffState = { a, b, rows, semanticMaps, revertAnchors, draftLines };
    renderVirtualDiffWindow();
    srcTitle.textContent = "Source — " + src.org;
    tgtTitle.textContent = (lastCompare && lastCompare.mergeCount ? "Target draft — " : "Target — ") + tgt.org;
    diffPanes.classList.remove("hide-eq");
    updateTargetEditUi();
    updateMergeWorkflow();

    if (chg + del + ins === 0) {
      diffSummary.textContent = `Identical — "${selectedModelName()}" matches exactly (${a.length} lines).`;
    } else {
      diffSummary.textContent = `${chg} changed · ${del} only in source · ${ins} only in target   (source ${a.length} lines, target ${b.length} lines)`;
    }
    diffBox.classList.add("show");
    diffBox.scrollIntoView({ behavior: "smooth", block: "nearest" });
  }

  // Keep the two panes vertically aligned while allowing independent
  // horizontal scrolling of long lines.
  let syncing = false;
  function syncScroll(from) {
    from.addEventListener("scroll", () => {
      if (syncing) return;
      syncing = true;
      [srcScroll, mergeScroll, tgtScroll].forEach(pane => {
        if (pane !== from) pane.scrollTop = from.scrollTop;
      });
      requestAnimationFrame(() => {
        renderVirtualDiffWindow();
        syncing = false;
      });
    });
  }
  syncScroll(srcScroll);
  syncScroll(mergeScroll);
  syncScroll(tgtScroll);

  function updateTargetEditUi() {
    if (!tgtEditArea || !editTargetBtn) return;
    tgtEditArea.hidden = !editingTarget;
    tgtTable.hidden = editingTarget;
    editTargetBtn.hidden = editingTarget;
    saveTargetEditBtn.hidden = !editingTarget;
    cancelTargetEditBtn.hidden = !editingTarget;
    resetMergeBtn.disabled = editingTarget;
    reviewMergeBtn.disabled = editingTarget;
    mergeAllBtn.disabled = editingTarget || !compareHasDiffs;
    diffPanes.classList.toggle("target-editing", editingTarget);
  }

  async function refreshSemanticAgainstDraft() {
    if (!lastCompare) return;
    const compareState = lastCompare;
    const sourceContent = compareState.src.content || "";
    const targetContent = compareState.tgt.content || "";
    const sequence = ++semanticRefreshSequence;
    try {
      const data = await postJSON("/api/semantic/compare", { sourceContent, targetContent });
      if (lastCompare !== compareState || sequence !== semanticRefreshSequence
          || (lastCompare.tgt.content || "") !== targetContent) return;
      lastCompare.semantic = data;
      renderCompare();
    } catch (e) {
      if (e && e.conn) handleDisconnect();
    }
  }

  onlyDiffs.onchange = () => {
    [srcScroll, mergeScroll, tgtScroll].forEach(pane => { pane.scrollTop = 0; });
    renderVirtualDiffWindow();
  };
  function normalizedCompareText(value) {
    return (value || "").replace(/\r\n/g, "\n");
  }
  async function applyTargetDraft(content, statusMessage) {
    lastCompare.tgt.content = content;
    lastCompare.semantic = null;
    renderCompare();
    if (statusMessage) setStatus("info", statusMessage, cmpStatus);
    await refreshSemanticAgainstDraft();
  }
  mergeAllBtn.onclick = async () => {
    if (!lastCompare || editingTarget) return;
    const source = normalizedCompareText(lastCompare.src.content);
    if (source === normalizedCompareText(lastCompare.tgt.content)) return;
    const applied = Math.max(1, activeMergeHunks.length);
    lastCompare.mergeCount = (lastCompare.mergeCount || 0) + applied;
    await applyTargetDraft(source,
      `Applied all ${applied} source change${applied === 1 ? "" : "s"} to the target draft. ` +
      "Use ← on any change to revert it, or Reset target draft to undo everything. Salesforce is not changed.");
  };
  mergeTable.onclick = async event => {
    const revert = event.target.closest("[data-revert-hunk]");
    if (revert) {
      if (!lastCompare || editingTarget) return;
      const hunk = activeRevertHunks[Number(revert.dataset.revertHunk)];
      if (!hunk) return;
      const lines = normalizedCompareText(lastCompare.tgt.content).split("\n");
      lines.splice(hunk.currentStart, hunk.currentDeleteCount, ...hunk.originalLines);
      const content = lines.join("\n");
      lastCompare.mergeCount = content === normalizedCompareText(lastCompare.originalTargetContent)
        ? 0 : Math.max(1, (lastCompare.mergeCount || 0) - 1);
      await applyTargetDraft(content,
        "Reverted that change in the target draft to the version fetched from Salesforce. Salesforce is not changed.");
      return;
    }
    const button = event.target.closest("[data-merge-hunk]");
    if (!button || !lastCompare || editingTarget) return;
    const hunk = activeMergeHunks[Number(button.dataset.mergeHunk)];
    if (!hunk) return;
    const targetLines = (lastCompare.tgt.content || "").replace(/\r\n/g, "\n").split("\n");
    if (hunk.moveFrom != null) {
      targetLines.splice(hunk.moveFrom, hunk.targetDeleteCount);
      const adjustedStart = hunk.targetStart > hunk.moveFrom
        ? hunk.targetStart - hunk.targetDeleteCount : hunk.targetStart;
      targetLines.splice(adjustedStart, 0, ...hunk.sourceLines);
    } else {
      targetLines.splice(hunk.targetStart, hunk.targetDeleteCount, ...hunk.sourceLines);
    }
    lastCompare.tgt.content = targetLines.join("\n");
    lastCompare.mergeCount = (lastCompare.mergeCount || 0) + 1;
    lastCompare.semantic = null;
    renderCompare();
    await refreshSemanticAgainstDraft();
  };
  resetMergeBtn.onclick = () => {
    if (!lastCompare) return;
    editingTarget = false;
    lastCompare.tgt.content = lastCompare.originalTargetContent;
    lastCompare.mergeCount = 0;
    lastCompare.semantic = null;
    renderCompare();
    refreshSemanticAgainstDraft();
    setStatus("info", "Target draft reset to the version fetched from Salesforce. No org data was changed.", cmpStatus);
  };
  editTargetBtn.onclick = () => {
    if (!lastCompare) return;
    tgtEditArea.value = (lastCompare.tgt.content || "").replace(/\r\n/g, "\n");
    editingTarget = true;
    updateTargetEditUi();
    tgtEditArea.focus();
    setStatus("info", "Editing the local target working draft. Save edits to refresh the comparison; Salesforce is not changed.", cmpStatus);
  };
  cancelTargetEditBtn.onclick = () => {
    editingTarget = false;
    updateTargetEditUi();
    setStatus("info", "Target edit cancelled. The saved working draft is unchanged.", cmpStatus);
  };
  saveTargetEditBtn.onclick = async () => {
    if (!lastCompare) return;
    const edited = tgtEditArea.value.replace(/\r\n/g, "\n");
    const changed = edited !== (lastCompare.tgt.content || "").replace(/\r\n/g, "\n");
    editingTarget = false;
    if (!changed) {
      updateTargetEditUi();
      setStatus("info", "No target-draft changes were detected.", cmpStatus);
      return;
    }
    lastCompare.tgt.content = edited;
    lastCompare.mergeCount = (lastCompare.mergeCount || 0) + 1;
    lastCompare.semantic = null;
    renderCompare();
    setStatus("info", "Target-draft edits saved locally. Refreshing line and semantic comparison; Salesforce is not changed.", cmpStatus);
    await refreshSemanticAgainstDraft();
  };
  reviewMergeBtn.onclick = async () => {
    if (!lastCompare || !lastCompare.mergeCount) return;
    setEditorContent(lastCompare.tgt.content, { baseline:false });
    deployOrgSel.value = targetSel.value;
    renderOrgPicker(orgPickers[2]);
    await loadTargetVersions(deployOrgSel, deployVersionSel, "deployment");
    deployVersionSel.value = targetVersionSel.value;
    fitPicklist(deployOrgSel);
    fitPicklist(deployVersionSel);
    switchView("fetch");
    setStatus("info", `Merged target draft loaded for review.\nDeployment target: ${targetSel.value} · exact version ${targetVersionSel.value}.\nReview the CML, then use Deploy CML. The normal backup, confirmation, and verification safeguards still apply.`);
  };
  copyTargetCmlBtn.onclick = async () => {
    if (!lastCompare) return;
    const value = editingTarget ? tgtEditArea.value : (lastCompare.tgt.content || "");
    try {
      await navigator.clipboard.writeText(value);
    } catch (e) {
      const helper = document.createElement("textarea");
      helper.value = value;
      helper.className = "clipboard-helper";
      document.body.appendChild(helper);
      helper.select();
      document.execCommand("copy");
      helper.remove();
    }
    const label = copyTargetCmlBtn.querySelector("span");
    if (label) label.textContent = "Copied";
    setTimeout(() => { if (label) label.textContent = "Copy"; }, 1300);
  };

  // ========================================================================
  //  CML analysis — semantic diff + best-practices linter (all client-side)
  // ========================================================================

  // Replace comments with blanks but keep newlines so line numbers stay exact.
  function stripComments(text) {
    let out = "", i = 0; const n = text.length; let s = false;
    while (i < n) {
      const c = text[i], d = text[i + 1];
      if (s) { out += c; if (c === '"') s = false; i++; continue; }
      if (c === '"') { s = true; out += c; i++; continue; }
      if (c === '/' && d === '/') { while (i < n && text[i] !== "\n") { out += " "; i++; } continue; }
      if (c === '/' && d === '*') {
        out += "  "; i += 2;
        while (i < n && !(text[i] === '*' && text[i + 1] === '/')) { out += (text[i] === "\n" ? "\n" : " "); i++; }
        if (i < n) { out += "  "; i += 2; }
        continue;
      }
      out += c; i++;
    }
    return out;
  }

  // Index of the matching close bracket for the open bracket at openIdx (string-aware).
  function matchPair(text, openIdx, open, close) {
    let depth = 0, s = false;
    for (let i = openIdx; i < text.length; i++) {
      const c = text[i];
      if (s) { if (c === '"') s = false; continue; }
      if (c === '"') { s = true; continue; }
      if (c === open) depth++;
      else if (c === close) { depth--; if (depth === 0) return i; }
    }
    return -1;
  }

  const norm = (s) => (s || "").replace(/\s+/g, " ").trim();
  const lineOf = (text, idx) => text.slice(0, idx).split("\n").length;

  // ---- Tolerant top-level parser: returns blocks keyed by declared name ----
  function parseCml(rawText) {
    const text = stripComments(rawText);
    const n = text.length; let i = 0; const units = [];
    const ws = () => { while (i < n && /\s/.test(text[i])) i++; };
    const findTop = (ch, from) => {
      let s = false, d = 0;
      for (let k = from; k < n; k++) {
        const c = text[k];
        if (s) { if (c === '"') s = false; continue; }
        if (c === '"') { s = true; continue; }
        if (c === ch && d === 0) return k;
        if (c === '(' || c === '[' || c === '{') d++;
        else if (c === ')' || c === ']' || c === '}') { if (d > 0) d--; }
      }
      return -1;
    };
    while (true) {
      ws(); if (i >= n) break;
      const start = i;
      while (text[i] === '@' && text[i + 1] === '(') { const e = matchPair(text, i + 1, '(', ')'); if (e < 0) { i = n; break; } i = e + 1; ws(); }
      const rest = text.slice(i);
      let kind = "other", name = null, end;
      let km;
      if ((km = rest.match(/^property\s+([A-Za-z_]\w*)/))) {
        kind = "property"; name = km[1]; const semi = findTop(';', i); end = semi < 0 ? n : semi + 1;
      } else if ((km = rest.match(/^extern\s+[\w()\[\]]+\s+([A-Za-z_]\w*)/))) {
        kind = "extern"; name = km[1]; const semi = findTop(';', i); end = semi < 0 ? n : semi + 1;
      } else if ((km = rest.match(/^define\s+([A-Za-z_]\w*)/))) {
        kind = "define"; name = km[1];
        const br = text.indexOf('[', i); const be = br >= 0 ? matchPair(text, br, '[', ']') : -1;
        if (be >= 0) end = be + 1; else { const semi = findTop(';', i); end = semi < 0 ? n : semi + 1; }
      } else if ((km = rest.match(/^type\s+([A-Za-z_]\w*)/))) {
        kind = "type"; name = km[1];
        const brace = findTop('{', i), semi = findTop(';', i);
        if (brace >= 0 && (semi < 0 || brace < semi)) { const be = matchPair(text, brace, '{', '}'); end = be < 0 ? n : be + 1; }
        else end = semi < 0 ? n : semi + 1;
      } else {
        const semi = findTop(';', i); end = semi < 0 ? n : semi + 1;
      }
      const raw = text.slice(start, end);
      units.push({ kind, name, raw, norm: norm(raw), line: lineOf(text, start) });
      i = end > start ? end : start + 1;
    }
    return units;
  }

  // ---- Member parser for a type body (between the outer braces) ----
  function parseMembers(typeRaw) {
    const o = typeRaw.indexOf('{'); const cl = typeRaw.lastIndexOf('}');
    if (o < 0 || cl < 0 || cl < o) return [];
    const body = typeRaw.slice(o + 1, cl);
    const n = body.length; let i = 0; const out = [];
    const ws = () => { while (i < n && /\s/.test(body[i])) i++; };
    const findTop = (ch, from) => {
      let s = false, d = 0;
      for (let k = from; k < n; k++) {
        const c = body[k];
        if (s) { if (c === '"') s = false; continue; }
        if (c === '"') { s = true; continue; }
        if (c === ch && d === 0) return k;
        if (c === '(' || c === '[' || c === '{') d++;
        else if (c === ')' || c === ']' || c === '}') { if (d > 0) d--; }
      }
      return -1;
    };
    const CALLS = ["constraint", "require", "exclude", "preference", "message", "rule"];
    while (true) {
      ws(); if (i >= n) break;
      const start = i;
      while (body[i] === '@' && body[i + 1] === '(') { const e = matchPair(body, i + 1, '(', ')'); if (e < 0) { i = n; break; } i = e + 1; ws(); }
      const rest = body.slice(i);
      let sig = null, end;
      let m;
      if ((m = rest.match(/^relation\s+([A-Za-z_]\w*)/))) {
        sig = "relation:" + m[1];
        const brace = findTop('{', i), semi = findTop(';', i);
        if (brace >= 0 && (semi < 0 || brace < semi)) { const be = matchPair(body, brace, '{', '}'); end = be < 0 ? n : be + 1; }
        else end = semi < 0 ? n : semi + 1;
      } else if ((m = rest.match(new RegExp("^(" + CALLS.join("|") + ")\\s*\\(")))) {
        const p = body.indexOf('(', i); const pe = matchPair(body, p, '(', ')');
        let j = pe + 1; while (j < n && /\s/.test(body[j])) j++;
        if (body[j] === '{') { const be = matchPair(body, j, '{', '}'); end = be < 0 ? n : be + 1; }
        else { const semi = findTop(';', pe); end = semi < 0 ? (pe + 1) : semi + 1; }
        sig = m[1] + ":" + norm(body.slice(i, end));
      } else if ((m = rest.match(/^(string\[\]|string|boolean|int|double|decimal\s*\(\s*\d+\s*\))\s+([A-Za-z_]\w*)/))) {
        sig = "field:" + m[2];
        const semi = findTop(';', i); end = semi < 0 ? n : semi + 1;
      } else {
        const semi = findTop(';', i); end = semi < 0 ? n : semi + 1;
        sig = "stmt:" + norm(body.slice(i, end));
      }
      const raw = body.slice(start, end);
      out.push({ sig, raw: raw.trim(), norm: norm(raw) });
      i = end > start ? end : start + 1;
    }
    return out;
  }

  // ---- Semantic diff between two CML texts ----
  function semanticDiff(srcText, tgtText) {
    const su = parseCml(srcText), tu = parseCml(tgtText);
    const keyOf = (u) => (u.name ? u.kind + ":" + u.name : u.kind + "#" + u.norm);
    const sMap = new Map(), tMap = new Map();
    su.forEach((u, idx) => { u._i = idx; sMap.set(keyOf(u), u); });
    tu.forEach((u, idx) => { u._i = idx; tMap.set(keyOf(u), u); });

    const added = [], removed = [], changed = []; let same = 0;
    const commonEqualKeys = [];
    const header = (raw) => { const o = raw.indexOf('{'); return norm(o < 0 ? raw : raw.slice(0, o)); };
    for (const [k, u] of sMap) {
      if (!tMap.has(k)) { removed.push(u); continue; }
      const v = tMap.get(k);
      if (u.norm === v.norm) { same++; commonEqualKeys.push(k); continue; }
      if (u.kind === "type") {
        const md = memberDiff(u.raw, v.raw);
        // Members and header match -> only order/formatting differs -> not a change.
        if (!md.added.length && !md.removed.length && !md.changed.length && header(u.raw) === header(v.raw)) {
          same++; commonEqualKeys.push(k); continue;
        }
        changed.push({ kind: u.kind, name: u.name, members: md });
      } else {
        changed.push({ kind: u.kind, name: u.name || "(anon)", whole: { src: u.norm, tgt: v.norm } });
      }
    }
    for (const [k, v] of tMap) { if (!sMap.has(k)) added.push(v); }

    // "Reordered only": blocks identical in content but whose relative order differs.
    const sOrder = su.filter(u => commonEqualKeys.includes(keyOf(u))).map(keyOf);
    const tOrder = tu.filter(u => commonEqualKeys.includes(keyOf(u))).map(keyOf);
    const reordered = JSON.stringify(sOrder) !== JSON.stringify(tOrder);

    return { added, removed, changed, same, reordered, srcTotal: su.length, tgtTotal: tu.length };
  }

  function memberDiff(srcType, tgtType) {
    const sm = parseMembers(srcType), tm = parseMembers(tgtType);
    const sMap = new Map(), tMap = new Map();
    sm.forEach(x => sMap.set(x.sig, x));
    tm.forEach(x => tMap.set(x.sig, x));
    const added = [], removed = [], changed = [];
    for (const x of sm) {
      if (tMap.has(x.sig)) { const y = tMap.get(x.sig); if (x.norm !== y.norm) changed.push({ src: x.raw, tgt: y.raw }); }
      else removed.push(x.raw);
    }
    for (const y of tm) { if (!sMap.has(y.sig)) added.push(y.raw); }
    return { added, removed, changed };
  }

  function renderSemanticSummary() {
    const semantic = lastCompare && lastCompare.semantic;
    semanticInlineSummary.hidden = !semanticChk.checked;
    if (!semanticChk.checked) return;
    if (!semantic) {
      semanticInlineSummary.textContent = "Semantic: refreshing the target draft analysis…";
      return;
    }
    if (semantic.analysisStatus && semantic.analysisStatus !== "complete") {
      semanticInlineSummary.innerHTML = `<strong>Semantic:</strong> ${esc(semantic.analysisStatus)} — ${esc(semantic.analysisReason || "Raw line comparison remains available.")}`;
      return;
    }
    if (semantic.analysisError) {
      semanticInlineSummary.innerHTML = `<strong>Semantic:</strong> unavailable — ${esc(semantic.analysisError)}`;
      return;
    }
    const s = semantic.stats || {};
    const parseIssues = (semantic.sourceParseIssues || []).length
      + (semantic.targetParseIssues || []).length;
    semanticInlineSummary.innerHTML = "<strong>Semantic:</strong> "
      + `${s.ADDED || 0} added · ${s.REMOVED || 0} removed · ${s.MODIFIED || 0} modified · `
      + `${s.MOVED || 0} moved · ${s.UNCHANGED || 0} unchanged`
      + (s.AMBIGUOUS ? ` · ${s.AMBIGUOUS} ambiguous (merge blocked)` : "")
      + (parseIssues ? ` · ${parseIssues} parser warning${parseIssues === 1 ? "" : "s"}` : "");
  }

  // Semantic analysis is an overlay: it never replaces or hides the code panes.
  function renderCompare() {
    if (!lastCompare) return;
    renderDiff(lastCompare.src, lastCompare.tgt);
    renderSemanticSummary();
    diffBox.classList.add("show");
  }
  semanticChk.onchange = renderCompare;

  // Turn an implication constraint (pre -> post) into the recommended
  // "guard constraint + require() auto-add" pattern (valid CML you can paste).
  function splitImplication(blockText) {
    const t = norm(blockText);
    let label = "Rule";
    const lm = t.match(/^(?:constraint|preference)\s*\(\s*([A-Za-z_]\w*)\s*\)\s*\{/);
    if (lm) label = lm[1].replace(/_guard$/i, "");
    let region;
    const brace = t.indexOf("{");
    if (brace >= 0) { const be = t.lastIndexOf("}"); region = t.slice(brace + 1, be > brace ? be : t.length); }
    else { const p = t.indexOf("("); const pe = t.lastIndexOf(")"); region = t.slice(p + 1, pe > p ? pe : t.length); }
    const ai = region.indexOf("->");
    if (ai < 0) return null;
    // Skip biconditionals (<->) — they mean something different.
    if (region.slice(Math.max(0, ai - 2), ai).indexOf("<") >= 0) return null;
    let pre = region.slice(0, ai).trim();
    let post = region.slice(ai + 2).trim();
    post = post.replace(/,\s*"[^"]*"\s*$/, "").trim();   // drop trailing , "message"
    if (!pre || !post || pre.endsWith("<")) return null;
    const after =
      `constraint(${label}_guard) {\n  ${pre} -> ${post}\n}\n` +
      `require(${label}_auto) {\n  // When ${pre} is selected, auto-add ${post}\n}`;
    return { before: t, after };
  }

  // ---- Best-practices linter ----
  // Each finding carries: a short note, the offending snippet (before), and a
  // concrete, CML-valid correction (after) the user can copy and paste.
  function lintCml(rawText) {
    const findings = [];
    const text = stripComments(rawText);
    const lines = text.split(/\r?\n/);
    const add = (rule, sev, line, msg, note, before, after) =>
      findings.push({ rule, sev, line, msg, note, before: before || null, after: after || null });

    // Inheritance map for depth (AP-5) and stub detection (AP-3).
    const parent = {}; const typeDefs = [];
    const typeRe = /\btype\s+([A-Za-z_]\w*)\s*(?::\s*([A-Za-z_]\w*))?\s*([;{])/g;
    let mt;
    while ((mt = typeRe.exec(text))) {
      parent[mt[1]] = mt[2] || null;
      typeDefs.push({ name: mt[1], parent: mt[2] || null, line: lineOf(text, mt.index), isStub: mt[3] === ';', decl: norm(mt[0]) });
    }
    const depth = (name, seen) => {
      seen = seen || new Set();
      if (!name || seen.has(name)) return 0; seen.add(name);
      return parent[name] ? 1 + depth(parent[name], seen) : 0;
    };
    typeDefs.forEach(t => {
      const dp = depth(t.name);
      if (dp < 4) return;
      const chain = []; let cur = t.name, guard = 0;
      while (cur && guard++ < 25) { chain.push(cur); cur = parent[cur]; }
      const base = chain[chain.length - 1];
      add("AP-5", "warn", t.line,
        `Type "${t.name}" sits ${dp} levels down a chain of parent types.`,
        `This type inherits through ${dp} parents (the chain is shown below). Long chains are hard to follow and slower for the engine to resolve. Where you can, have "${t.name}" inherit directly from one shared base type and keep its own fields on it, instead of adding more in-between levels. The After sketch shows the flatter shape.`,
        chain.slice().reverse().join("  ->  "),
        `// Inherit directly from the shared base and keep this type's own fields here,\n// instead of stacking intermediate levels:\ntype ${t.name} : ${base} {\n    // attributes / relations that were spread across the chain\n}`);
    });
    const stubs = typeDefs.filter(t => t.isStub);
    if (stubs.length >= 5) {
      const ex = stubs.find(s => s.parent) || stubs[0];
      const exParent = ex.parent || "LineItem";
      add("AP-3", "info", stubs[0].line,
        `${stubs.length} types are declared with no body (e.g. "type X;").`,
        "These types are empty placeholders. That's fine if something references them, but extra unused ones add clutter. Delete the placeholders nothing points to, or give the ones you keep some real content (attributes / relations). The After example shows a stub turned into a real type.",
        stubs.slice(0, 4).map(s => s.decl).join("\n"),
        `// Either delete unused stubs, or give them meaningful content:\ntype ${ex.name} : ${exParent} {\n    @(defaultValue = "Standard")\n    string Variant = ["Standard", "Premium"];\n}`);
    }

    // Per-line rules.
    lines.forEach((ln, idx) => {
      const num = idx + 1; const t = ln.trim(); let m;
      if ((m = ln.match(/^\s*double\s+([A-Za-z_]\w*)/))) {
        add("AP-1", "warn", num,
          `"${m[1]}" uses double — not safe for money or other exact numbers.`,
          "double stores approximate values, so prices and totals can drift by a fraction of a cent. Change the type to decimal(2) — the 2 is how many digits to keep after the decimal point (use decimal(4) if you need more). The After line is the exact replacement.",
          t, t.replace(/^double\b/, "decimal(2)"));
      }
      if (/\brelation\s+\w+\s*:\s*\w+\s*\[\s*\.\.\s*\]/.test(ln)) {
        add("AP-9", "warn", num,
          "This relation is unbounded ([..]) — it allows unlimited child items.",
          "[..] lets someone add an unlimited number of these, which can slow the configurator and usually isn't intended. Put a maximum inside the brackets, like [0..50] (zero to fifty). Change 50 to the largest count you actually want to allow.",
          t, t.replace(/\[\s*\.\.\s*\]/, "[0..50]"));
      }
      if (/\brelation\s+\w+\s*:\s*\w+\s*;/.test(ln) && !/\[/.test(ln)) {
        add("AP-9", "info", num,
          "This relation doesn't say how many child items are allowed.",
          "With no range, the relation falls back to a hidden default. Make it explicit by adding a range in square brackets right after the type. Common choices: [0..1] = optional, at most one; [1..1] = required, exactly one; [0..5] = up to five. The After line uses [0..1] — change the numbers to match your rule.",
          t, t.replace(/\s*;\s*$/, "[0..1];"));
      }
      if ((m = ln.match(/\b(?:string\[\]|string|boolean|int|double|decimal\s*\(\s*\d+\s*\))\s+(x|y|z|tmp|temp|var|foo|bar|val|data)\b/))) {
        add("BP-2", "info", num,
          `The name "${m[1]}" doesn't say what it holds.`,
          "Short names like this make the model hard to read later. Rename it to a noun that describes the value — for example seatCount, monthlyTotal, or contractTerm. The After line shows where the new name goes.",
          t, t.replace(new RegExp("\\b" + m[1] + "\\b"), "descriptiveName"));
      }
    });

    // Constraint / preference scans (multi-line aware).
    const kwRe = /\b(constraint|preference)\s*\(/g; let m;
    while ((m = kwRe.exec(text))) {
      const kw = m[1]; const p = m.index + m[0].length - 1;
      const pe = matchPair(text, p, '(', ')'); if (pe < 0) continue;
      const inner = text.slice(p + 1, pe);
      let j = pe + 1; while (j < text.length && /\s/.test(text[j])) j++;
      let blockEnd = pe;
      if (text[j] === '{') { const be = matchPair(text, j, '{', '}'); if (be > 0) blockEnd = be; }
      const blockText = text.slice(m.index, blockEnd + 1);
      const oneLine = norm(blockText);
      const line = lineOf(text, m.index);
      if (/^\s*true\s*[,)]/.test(inner)) {
        add("AP-6", "warn", line,
          `This ${kw} is always true, so it never does anything.`,
          "A condition that is always true can't block or change anything — it just adds noise. If it's a leftover, delete it. If you meant to enforce something, replace true with the real condition. The After shows the shape to use.",
          oneLine,
          `// Remove this no-op, or replace true with the real condition:\n${kw}(/* your real condition */, "Message shown to the user");`);
      }
      const ops = (blockText.match(/&&|\|\|/g) || []).length;
      if (ops >= 6) {
        add("AP-8", "warn", line,
          `This ${kw} combines ${ops} conditions with && / || — too much in one rule.`,
          "Testing many things at once in a single rule is hard to read and debug. Split it into a few smaller constraints that each check one idea — they all still apply together. The After shows how to break it up.",
          oneLine,
          `// Split the combined condition into separate constraints:\n${kw}(/* first part of the condition */, "Message A");\n${kw}(/* second part of the condition */, "Message B");`);
      }
      const split = splitImplication(blockText);
      if (split) {
        add("REC", "info", line,
          `Tip: this ${kw} uses an implication (A -> B).`,
          "This works as-is. The recommended pattern is to keep A -> B as a 'guard' and add a matching require() that spells out what gets auto-added when A is chosen — so the auto-add behaviour is obvious to the next person. The After block is ready to paste; rename the _guard / _auto labels to suit.",
          split.before, split.after);
      } else if (/->/.test(blockText)) {
        add("REC", "info", line,
          `Tip: this ${kw} uses an implication (A -> B).`,
          "This works as-is. As a style improvement you can split it into a guard constraint plus a require() auto-add, which makes the auto-add behaviour explicit.",
          oneLine, null);
      }
      kwRe.lastIndex = pe + 1;
    }

    // Repeated enum literal sets (AP-4).
    const enumRe = /=\s*\[([^\]]*)\]/g; let em; const sets = {};
    while ((em = enumRe.exec(text))) {
      const items = em[1].split(",").map(s => s.trim().replace(/^"|"$/g, "")).filter(Boolean);
      if (items.length < 2) continue;
      const key = items.slice().sort().join("|");
      const rec = sets[key] || (sets[key] = { lines: [], items });
      rec.lines.push(lineOf(text, em.index));
    }
    Object.values(sets).forEach((rec) => {
      if (rec.lines.length < 3) return;
      const domain = "SharedValues";
      const listed = rec.items.map(v => `    "${v}"`).join(",\n");
      add("AP-4", "info", rec.lines[0],
        `The same list of values is typed out ${rec.lines.length} times: ["${rec.items.join('", "')}"].`,
        "Because the list is copied in many places, changing it later means editing every copy and it's easy to miss one. List the values once in a named define block (usually near the top of the file), then point to that name wherever you need the list. The After block shows the define to add — rename SharedValues to something that describes the list (e.g. ContractTerms).",
        rec.items.map(v => `"${v}"`).join(", ") + `   (used in ${rec.lines.length} places)`,
        `// 1) Declare the list once (near the top of the file):\ndefine ${domain} [\n${listed}\n]\n\n// 2) Then reference ${domain} instead of re-typing the values.`);
    });

    findings.sort((a, b) => (a.line || 0) - (b.line || 0));
    return findings;
  }

  function renderLint(rawText) {
    const findings = lintCml(rawText);
    const lineStarts = [0];
    for (let index = 0; index < rawText.length; index++) {
      if (rawText[index] === "\n") lineStarts.push(index + 1);
    }
    window.cmlEditor.setDiagnostics(findings.map(finding => {
      const lineIndex = Math.max(0, Math.min(
        lineStarts.length - 1, (Number(finding.line) || 1) - 1));
      const from = lineStarts[lineIndex];
      const lineBreak = rawText.indexOf("\n", from);
      const to = lineBreak < 0 ? rawText.length : lineBreak;
      return {
        from,
        to,
        severity: finding.sev === "warn" ? "warning" : finding.sev,
        message: finding.msg,
        source: finding.rule,
      };
    }));
    const sevRank = { error: 0, warn: 1, info: 2 };
    const errors = findings.filter(f => f.sev === "error").length;
    const warns = findings.filter(f => f.sev === "warn").length;
    const infos = findings.filter(f => f.sev === "info").length;
    // Scoring: weight by severity, but cap how much any single rule can cost so
    // one repetitive finding (e.g. many relations missing cardinality) can't sink
    // the whole score. Recommendations (REC) are optional and don't reduce it.
    const W = { error: 15, warn: 6, info: 2 };
    const NO_SCORE = new Set(["REC"]);
    const RULE_CAP = 12;
    const perRule = {};
    findings.forEach(f => { if (NO_SCORE.has(f.rule)) return; perRule[f.rule] = (perRule[f.rule] || 0) + (W[f.sev] || 0); });
    let penalty = 0; Object.values(perRule).forEach(p => penalty += Math.min(p, RULE_CAP));
    const score = Math.max(0, 100 - penalty);
    const scoreCls = score >= 85 ? "good" : score >= 60 ? "mid" : "bad";
    let html = `<div class="lint-head"><h4>Best practices</h4><div class="lint-head-actions">`
      + `<span class="lint-score ${scoreCls}">Quality score ${score}/100</span>`
      + `<button class="ghost hide-lint" type="button">Hide best practices</button></div></div>`
      + `<div class="lint-counts"><span>${errors} error${errors === 1 ? "" : "s"}</span><span>${warns} warning${warns === 1 ? "" : "s"}</span><span>${infos} suggestion${infos === 1 ? "" : "s"}</span></div>`
      + `<div class="lint-caption">The score reflects <strong>errors</strong> and <strong>warnings</strong> (each rule is capped so one repeated issue can't dominate). Blue <strong>suggestions</strong> are optional polish and don't lower the score. Every item below has a plain-English explanation and a paste-ready fix.</div>`;
    if (!findings.length) {
      html += `<div class="lint-empty">No issues found — this CML follows the built-in best-practice rules. 🎉</div>`;
    } else {
      findings.sort((a, b) => sevRank[a.sev] - sevRank[b.sev] || (a.line || 0) - (b.line || 0));
      findings.forEach((f, i) => {
        const where = f.line ? `<span class="lint-line" data-line="${f.line}">Line ${f.line}</span> · ` : "";
        let fix = "";
        if (f.before || f.after) {
          fix += `<div class="lint-fix">`;
          if (f.before) fix += `<div class="fixhead">Before (in your CML)</div><div class="lint-code before">${esc(f.before)}</div>`;
          if (f.after) fix += `<div class="fixhead">After — paste-ready CML <button class="linklike lint-copy" data-idx="${i}">Copy</button></div><div class="lint-code after">${esc(f.after)}</div>`;
          fix += `</div>`;
        }
        html += `<div class="lint-item ${f.sev}"><div class="rmeta">${where}${esc(f.rule)} · ${esc(f.sev)}</div>`
          + `<div class="msg">${esc(f.msg)}</div>`
          + (f.note ? `<div class="fix">→ ${esc(f.note)}</div>` : "")
          + fix
          + `</div>`;
      });
    }
    lintBox.innerHTML = html;
    lintBox.classList.add("show");
    lintBox.querySelectorAll(".lint-line").forEach(el => {
      el.onclick = () => {
        const ln = parseInt(el.getAttribute("data-line"), 10) || 1;
        const before = content.value.split("\n").slice(0, ln).join("\n").length;
        content.focus();
        content.setSelectionRange(Math.max(0, before - 1), before);
        scrollEditorLineIntoView(ln);
      };
    });
    lintBox.querySelectorAll(".lint-copy").forEach(el => {
      el.onclick = async (ev) => {
        ev.stopPropagation();
        const idx = parseInt(el.getAttribute("data-idx"), 10);
        const txt = (findings[idx] && findings[idx].after) || "";
        try { await navigator.clipboard.writeText(txt); el.textContent = "Copied!"; setTimeout(() => el.textContent = "Copy", 1200); }
        catch (e) { el.textContent = "Copy failed"; }
      };
    });
    const hideButton = lintBox.querySelector(".hide-lint");
    if (hideButton) hideButton.onclick = hideLintResults;
    lintBox.scrollIntoView({ behavior: "smooth", block: "nearest" });
  }

  function hideLintResults() {
    window.cmlEditor.setDiagnostics([]);
    lintBox.innerHTML = "";
    lintBox.classList.remove("show");
  }

  function doLint() {
    if (!content.value.trim()) {
      hideLintResults();
      setStatus("err", "Paste or fetch some CML first (Fetch & Deploy tab), then check best practices.");
      return;
    }
    renderLint(content.value);
  }
  lintBtn.onclick = () => { doLint(); };

  // ---- Constraint data (ExpressionSetConstraintObj) ----
  const TYPE_SHORT = {
    Product2: "Product", ProductClassification: "Classification",
    ProductComponentGroup: "Comp. Group", ProductRelatedComponent: "Related Comp."
  };
  function shortType(t) { return TYPE_SHORT[t] || t || "—"; }

  function statusBadge(s) {
    if (s === "match")      return '<span class="badge b-match"><span aria-hidden="true">✓</span> Matched</span>';
    if (s === "add")        return '<span class="badge b-add"><span aria-hidden="true">→</span> Add to target</span>';
    if (s === "ready")      return '<span class="badge b-add"><span aria-hidden="true">→</span> Add to target</span>';
    if (s === "extra")      return '<span class="badge b-extra"><span aria-hidden="true">!</span> Only in target</span>';
    if (s === "cml-difference") return '<span class="badge b-extra"><span aria-hidden="true">!</span> CML definitions differ</span>';
    if (s === "blocked")    return '<span class="badge b-blocked"><span aria-hidden="true">×</span> Blocked — catalog dependency</span>';
    if (s === "ambiguous-key") return '<span class="badge b-blocked"><span aria-hidden="true">×</span> Blocked — ambiguous key</span>';
    if (s === "dependency-unverified") return '<span class="badge b-unmappable"><span aria-hidden="true">!</span> Needs review — dependency key missing</span>';
    if (s === "exact-duplicate") return '<span class="badge b-dup"><span aria-hidden="true">!</span> Skipped — exact duplicate</span>';
    if (s === "unmappable") return '<span class="badge b-unmappable"><span aria-hidden="true">×</span> No ' + esc(currentKeyField) + '</span>';
    if (s === "stale")      return '<span class="badge b-unmappable"><span aria-hidden="true">!</span> Unused association in this org</span>';
    return "";
  }

  function statusText(r) {
    const s = r._status;
    if (s === "match")      return "Matched";
    if (s === "add" || s === "ready") return "Add to target";
    if (s === "extra")      return "Only in target";
    if (s === "cml-difference") return "CML definitions differ — valid in one org";
    if (s === "blocked")    return "Blocked — catalog dependency";
    if (s === "ambiguous-key") return "Blocked — portable key matches multiple target records";
    if (s === "dependency-unverified") return "Needs review — dependency could not be compared";
    if (s === "exact-duplicate") return "Skipped — exact duplicate";
    if (s === "unmappable") return "No " + currentKeyField;
    if (s === "stale")      return "Unused association — absent from the same org's CML";
    return s || "";
  }

  const DUP_LABEL = { exact: "Exact duplicate", tag: "Duplicate tag", ref: "Duplicate reference", name: "Ambiguous name" };
  const DUP_HELP = {
    exact: "Same complete association identity repeats within this selected parent Expression Set.",
    tag: "Same tag type and tag repeats within this selected parent Expression Set; references may still differ.",
    ref: "Same reference identity is used more than once within this selected parent Expression Set.",
    name: "Same display name maps to different portable keys within this selected parent Expression Set."
  };
  function dupBadges(r) {
    if (!r.dups || !r.dups.length) return "";
    return r.dups.map(d => `<span class="badge b-dup" title="${esc(DUP_HELP[d] || DUP_LABEL[d] || d)}">${esc(DUP_LABEL[d] || d)}</span>`).join("");
  }

  // Which rows can be acted on in a compare deploy.
  function isAdd(r) { return r._status === "add"; }     // ready to insert in target
  function isDel(r) { return r._status === "extra"; }   // exists only in target

  function referenceLabel(name, code, fallback) {
    const base = name || fallback || "(unnamed record)";
    return base + (code ? ` (${code})` : "");
  }

  function referenceRecordText(r) {
    const source = referenceLabel(r.sourceRefName, r.sourceRefCode, r.refId);
    const target = referenceLabel(r.targetRefName, r.targetRefCode, r.matchedEvidence?.target?.referenceId);
    if (r._status === "match" && (r.sourceRefName || r.targetRefName)) {
      if (source === target) return source;
      return `${r._sourceOrg || "Source"}: ${source} | ${r._targetOrg || "Target"}: ${target}`;
    }
    return referenceLabel(r.refName, r.refCode, r.refId);
  }

  function referenceRecordHtml(r) {
    const source = referenceLabel(r.sourceRefName, r.sourceRefCode, r.refId);
    const target = referenceLabel(r.targetRefName, r.targetRefCode, r.matchedEvidence?.target?.referenceId);
    if (r._status === "match" && (r.sourceRefName || r.targetRefName) && source !== target) {
      return `<span><strong>${esc(r._sourceOrg || "Source")}:</strong> ${esc(source)}</span>`
        + `<span class="block-note"><strong>${esc(r._targetOrg || "Target")}:</strong> ${esc(target)}</span>`;
    }
    return esc(referenceRecordText(r));
  }

  function reasonListHtml(reasons) {
    return `<ul class="reason-list">${reasons.map(reason => `<li>${esc(reason)}</li>`).join("")}</ul>`;
  }

  function dataRowHtml(r, withStatus) {
    const hasKeyValue = r.gkey !== null && r.gkey !== undefined && String(r.gkey).trim() !== "";
    const gk = hasKeyValue
      ? `<span class="gkey">${esc(r.gkey)}</span>`
      : `<span class="badge b-unmappable">${esc(currentKeyField)} is blank</span>`;
    const blockNote = r.blockReasons && r.blockReasons.length
      ? `<span class="block-note">${esc(r.blockTitle || "")}</span>${reasonListHtml(r.blockReasons)}`
      : (r.blockNote ? `<span class="block-note">${esc(r.blockNote)}</span>` : "");
    let sel = "";
    if (withStatus) {
      if (isAdd(r) || isDel(r)) {
        sel = `<td class="col-sel"><input type="checkbox" data-i="${r._i}" ${r._selected ? "checked" : ""} aria-label="Select ${esc(statusText(r))} association"></td>`;
      } else {
        sel = `<td class="col-sel"></td>`;
      }
    }
    return `<tr${withStatus && r._selected && (isAdd(r) || isDel(r)) ? ' class="is-selected"' : ""}>`
      + sel
      + (withStatus ? `<td class="col-status">${statusBadge(r._status)}${blockNote}</td>` : "")
      + `<td class="col-reftype"><span class="badge b-type">${esc(shortType(r.refType))}</span></td>`
      + `<td class="col-tagtype">${esc(r.tagType)}</td>`
      + `<td class="col-tag">${esc(r.tag)}</td>`
      + `<td class="col-ref">${referenceRecordHtml(r)}${dupBadges(r)}</td>`
      + `<td class="col-key">${gk}</td>`
      + "</tr>";
  }

  function rowMatchesFilter(r, f) {
    if (f === "all") return true;
    if (f === "match")   return r._status === "match";
    if (f === "add")     return r._status === "add";
    if (f === "extra")   return r._status === "extra";
    if (f === "cml-difference") return r._status === "cml-difference";
    if (f === "ambiguous-key") return r._status === "ambiguous-key";
    if (f === "blocked") return r._status === "blocked" || r._status === "ambiguous-key" || r._status === "unmappable" || r._status === "dependency-unverified";
    if (f === "stale")   return r._status === "stale";
    if (f === "dups")    return r.dups && r.dups.length;
    return true;
  }

  function rowSearchText(r) {
    if (r._search === undefined) {
      r._search = [r.tag, r.tagType, r.refType, shortType(r.refType), referenceRecordText(r), r.gkey, statusText(r)]
        .map(value => String(value ?? "")).join("\n").toLowerCase();
    }
    return r._search;
  }

  function visibleDataRows() {
    const f = dataFilter.value;
    const needle = dataSearch.value.trim().toLowerCase();
    return dataRows.filter(r => rowMatchesFilter(r, f) && (!needle || rowSearchText(r).includes(needle)));
  }

  function renderDataTable() {
    const withStatus = dataMode === "compare";
    const visible = visibleDataRows();
    const cols = (withStatus ? 7 : 5);
    const head = "<thead><tr>"
      + (withStatus ? '<th class="col-sel" scope="col" title="Select associations for the deploy action">Select</th><th class="col-status">Status</th>' : "")
      + '<th class="col-reftype">Ref type</th><th class="col-tagtype">Tag type</th><th class="col-tag">Tag</th><th class="col-ref">Reference record</th><th class="col-key">' + esc(currentKeyField) + "</th>"
      + "</tr></thead>";
    const body = visible.length
      ? visible.map(r => dataRowHtml(r, withStatus)).join("")
      : `<tr><td colspan="${cols}" class="empty-table-row">No rows for this filter${dataSearch.value.trim() ? " and search" : ""}.</td></tr>`;
    dataTable.innerHTML = head + "<tbody>" + body + "</tbody>";
    dataTable.querySelectorAll("input[type=checkbox]").forEach(cb => {
      cb.onchange = () => {
        dataRows[+cb.dataset.i]._selected = cb.checked;
        cb.closest("tr").classList.toggle("is-selected", cb.checked);
        updateDeployBar();
      };
    });
    copyExcelBtn.disabled = visible.length === 0;
    updateDeployBar();
  }
  dataFilter.onchange = renderDataTable;
  let dataSearchTimer = null;
  dataSearch.addEventListener("input", () => {
    clearTimeout(dataSearchTimer);
    dataSearchTimer = setTimeout(renderDataTable, 120);
  });


  function updateDeployBar() {
    deployBar.classList.add("show");
    if (dataMode !== "compare") {
      selSummary.textContent = "Compare source and target data to select rows for deployment.";
      [selAllAdds, selNoAdds, selAllDels, selNoDels, deployDataBtn].forEach(b => { b.disabled = true; });
      return;
    }
    const adds = dataRows.filter(r => isAdd(r) && r._selected).length;
    const dels = dataRows.filter(r => isDel(r) && r._selected).length;
    const totalAdds = dataRows.filter(isAdd).length;
    const totalDels = dataRows.filter(isDel).length;
    selAllAdds.disabled = selNoAdds.disabled = totalAdds === 0;
    selAllDels.disabled = selNoDels.disabled = totalDels === 0;
    if ((totalAdds + totalDels) === 0) {
      selSummary.textContent = "No deployable differences were found.";
    } else {
      selSummary.innerHTML =
        `Selected: <strong>${adds}</strong> to add`
        + (dels ? ` · <strong class="warn-note">${dels}</strong> <span class="warn-note">to delete</span>` : ` · <strong>0</strong> to delete`);
    }
    deployDataBtn.disabled = (adds + dels) === 0;
  }

  function setSel(pred, val) { dataRows.forEach(r => { if (pred(r)) r._selected = val; }); renderDataTable(); }
  selAllAdds.onclick = () => setSel(isAdd, true);
  selNoAdds.onclick  = () => setSel(isAdd, false);
  selAllDels.onclick = () => setSel(isDel, true);
  selNoDels.onclick  = () => setSel(isDel, false);

  copyExcelBtn.onclick = async () => {
    const withStatus = dataMode === "compare";
    const visible = visibleDataRows();
    if (!visible.length) return;
    const cols = withStatus
      ? ["Status", "Ref type", "Tag type", "Tag", "Reference record", currentKeyField]
      : ["Ref type", "Tag type", "Tag", "Reference record", currentKeyField];
    const rows = visible.map(r => {
      const base = [
        shortType(r.refType),
        r.tagType || "",
        r.tag || "",
        referenceRecordText(r),
        r.mappable ? (r.gkey || "") : "missing",
      ];
      if (withStatus) {
        const detail = r.blockNote ? " — " + r.blockNote : "";
        base.unshift(statusText(r) + detail);
      }
      return base.map(v => String(v ?? "").replace(/[\t\r\n]+/g, " ")).join("\t");
    });
    const tsv = cols.join("\t") + "\r\n" + rows.join("\r\n");
    try {
      await navigator.clipboard.writeText(tsv);
    } catch (_) {
      const ta = document.createElement("textarea");
      ta.value = tsv; ta.className = "clipboard-helper";
      document.body.appendChild(ta); ta.select();
      document.execCommand("copy");
      document.body.removeChild(ta);
    }
    const orig = copyExcelBtn.textContent;
    copyExcelBtn.textContent = `Copied ${visible.length} row${visible.length === 1 ? "" : "s"} for Excel!`;
    setTimeout(() => { copyExcelBtn.textContent = orig; }, 1600);
  };

  const dSt = () => $("dataStatus") || status;
  loadDataBtn.onclick = async () => {
    if (!orgSel.value) { setStatus("err", "Please choose a source org first.", dSt()); return; }
    if (!keyName()) { setStatus("err", "Choose a detected foreign-key field first.", dSt()); keyField.focus(); return; }
    const source = selectedSourceVersion();
    if (!source) { setStatus("err", "Please select an exact source CML version.", dSt()); sourceVersionTrigger.focus(); return; }
    busy(loadDataBtn, "Loading…");
    setStatus("info", `Loading ExpressionSet-scoped constraint data for "${source.name}" ${source.versionId} from ${orgSel.value}…`, dSt());
    try {
      const data = await postJSON("/api/data", {
        org: orgSel.value, model: source.name,
        versionId: source.versionId, keyField: keyName()
      });
      if (data.ok) {
        dataMode = "single";
        currentKeyField = data.keyField || keyName();
        dataRows = data.rows.map((r, i) => ({ ...r, _status: "", _i: i, _selected: false }));
        deployBar.classList.add("show");
        results.classList.remove("show");
        renderDataChips({
          single: true, total: data.stats.total,
          unmappable: data.stats.unmappable, dups: data.stats.duplicates,
          duplicateScope: data.duplicateScope,
          duplicateCheckError: data.duplicateCheckError,
          apiName: data.expressionSetApiName,
          definitionName: data.expressionSetDefinitionDeveloperName,
          org: orgSel.value
        });
        renderDataTable();
        dataBox.classList.add("show");
        dataBox.scrollIntoView({ behavior: "smooth", block: "nearest" });
        const warn = data.stats.unmappable ? ` (${data.stats.unmappable} without ${currentKeyField})` : "";
        const duplicateNote = data.duplicateCheckError
          ? `\nDuplicate check was unavailable because the selected CML could not be read: ${data.duplicateCheckError}`
          : "\nDuplicate flags were checked only against tags used by the exact selected CML.";
        setStatus("ok", `Loaded ${data.stats.total} constraint rows from ${orgSel.value}${warn}.`
          + `\nScope verified: ExpressionSet.ApiName ${data.expressionSetApiName}`
          + ` · Definition ${data.expressionSetDefinitionDeveloperName}.`
          + `\n${data.associationScopeNote}${duplicateNote}`, dSt());
      } else {
        setStatus("err", data.log || "Could not load data.", dSt());
      }
    } catch (e) {
      if (e && e.conn) { handleDisconnect(); } else { setStatus("err", "Data error: " + e, dSt()); }
    }
    idle();
  };

  compareDataBtn.onclick = async () => {
    if (!orgSel.value) { setStatus("err", "Please choose a source org.", dSt()); return; }
    if (!targetSel.value) { setStatus("err", "Please choose a target org.", dSt()); return; }
    if (!keyName()) { setStatus("err", "Choose a foreign-key field shared by the selected orgs.", dSt()); keyField.focus(); return; }
    const source = selectedSourceVersion();
    if (!source) { setStatus("err", "Please select an exact source CML version.", dSt()); sourceVersionTrigger.focus(); return; }
    if (!targetVersionSel.value) { setStatus("err", "Please select an exact compare target version.", dSt()); targetVersionTrigger.focus(); return; }
    dataCompareController = new AbortController();
    dataCompareOperationId = (
      globalThis.crypto && typeof globalThis.crypto.randomUUID === "function"
        ? globalThis.crypto.randomUUID()
        : `compare_${Date.now()}_${Math.random().toString(36).slice(2)}`
    );
    busy(compareDataBtn, "Comparing…");
    stopCompareDataBtn.hidden = false;
    stopCompareDataBtn.disabled = false;
    setStatus("info", `Comparing ExpressionSet-scoped constraint data for "${source.name}" between exact versions ${source.versionId} and ${targetVersionSel.value}…\nThis reads both orgs and can take up to a minute — please wait.`, dSt());
    try {
      const data = await postJSON("/api/data/compare", {
        sourceOrg: orgSel.value, targetOrg: targetSel.value,
        model: source.name, sourceVersionId: source.versionId,
        targetVersionId: targetVersionSel.value, keyField: keyName(),
        operationId: dataCompareOperationId
      }, { signal: dataCompareController.signal });
      if (data.ok) {
        dataMode = "compare";
        currentKeyField = data.keyField || keyName();
        const rows = [];
        data.matched.forEach(r => rows.push({
          ...r, _status: ["blocked", "dependency-unverified"].includes(r.deployStatus)
            ? r.deployStatus : "match"
        }));
        data.sourceOnly.forEach(r => rows.push({ ...r, _status: r.deployStatus === "ready" ? "add" : r.deployStatus }));
        data.targetOnly.forEach(r => rows.push({
          ...r, _status: r.deployStatus === "cml-difference" ? "cml-difference" : "extra"
        }));
        (data.stale || []).forEach(r => rows.push({ ...r, _status: "stale" }));
        // Adds default ON; deletes default OFF (deletion is riskier — opt in).
        rows.forEach((r, i) => {
          r._i = i;
          r._selected = (r._status === "add");
          r._sourceOrg = data.source.org;
          r._targetOrg = data.target.org;
        });
        dataRows = rows;
        results.classList.remove("show");
        renderDataChips({ single: false, s: data.stats, src: data.source, tgt: data.target, stale: data.stale });
        renderDataTable();
        dataBox.classList.add("show");
        dataBox.scrollIntoView({ behavior: "smooth", block: "nearest" });
        setStatus("ok", `Compared constraint data for "${data.model}". Counts are shown above the table.\n`
          + `${data.associationScopeNote}`
          + (data.associationsShared ? "\nBoth selected versions map to the same ExpressionSet, so these associations are shared." : ""), dSt());
      } else {
        setStatus("err", data.log || "Compare failed.", dSt());
      }
    } catch (e) {
      if (e && e.aborted) {
        setStatus("info", "Constraint data comparison stopped. No comparison results were changed.", dSt());
      } else if (e && e.conn) {
        handleDisconnect();
      } else {
        setStatus("err", "Data compare error: " + e, dSt());
      }
    }
    dataCompareController = null;
    dataCompareOperationId = null;
    stopCompareDataBtn.hidden = true;
    idle();
  };
  stopCompareDataBtn.onclick = () => {
    if (!dataCompareController) return;
    stopCompareDataBtn.disabled = true;
    if (dataCompareOperationId) {
      postJSON("/api/operation/cancel", {
        operationId: dataCompareOperationId
      }).catch(e => {
        if (e && e.conn) handleDisconnect();
      });
    }
    dataCompareController.abort();
  };

  function dupSum(d) { return d ? (d.exact + d.tag + d.ref + d.name) : 0; }

  function chipColumnHtml(side, title, chips) {
    return `<section class="chip-col ${side}" aria-label="${esc(title)}">`
      + `<span class="chip-group-label">${esc(title)}</span>`
      + `<div class="chips">${chips.filter(Boolean).join("")}</div></section>`;
  }

  const DUP_TITLE = "Checked only inside the exact selected version's resolved parent Expression Set";

  function renderDataChips(o) {
    if (o.single) {
      const dn = dupSum(o.dups);
      dataChips.innerHTML = `<div class="chip-cols">`
        + chipColumnHtml("source", `Source · ${o.org}`, [
          `<span class="chip neutral">${o.total} rows</span>`,
          o.apiName && `<span class="chip neutral" title="ExpressionSet.ApiName">${esc(o.apiName)}</span>`,
          o.unmappable && `<span class="chip amber">${o.unmappable} without ${esc(currentKeyField)}</span>`,
          dn && `<span class="chip amber" title="${DUP_TITLE}">${dn} duplicate flags</span>`,
          o.duplicateCheckError && `<span class="chip amber">Duplicate check unavailable</span>`,
        ])
        + `</div>`;
      return;
    }
    const s = o.s;
    const sd = dupSum(o.src.duplicates), td = dupSum(o.tgt.duplicates);
    const staleFrom = origin => (o.stale || []).filter(r => r.staleOrigin === origin).length;
    const staleChip = count => count
      ? `<span class="chip amber" title="Associations whose tag is not defined by the same org's CML; excluded from deploy">${count} stale</span>` : "";
    const comparison = [
      `<span class="chip ok">${s.matched} matched</span>`,
      s.blocked && `<span class="chip warn" title="${s.dependencyIssues || 0} catalog dependency finding(s) across these rows">${s.blocked} blocked by catalog dependencies</span>`,
      s.dependencyUnverified && `<span class="chip amber">${s.dependencyUnverified} need review</span>`,
      s.ambiguousKeys && `<span class="chip warn">${s.ambiguousKeys} ambiguous keys</span>`,
      s.unmappable && `<span class="chip amber">${s.unmappable} without ${esc(currentKeyField)}</span>`,
      s.cmlDifferences && `<span class="chip cml-diff" title="Valid in one org; the two CML definitions differ">${s.cmlDifferences} CML definition differences</span>`,
    ].filter(Boolean);
    dataChips.innerHTML = `<div class="chip-cols">`
      + chipColumnHtml("source", `Source · ${o.src.org}`, [
        `<span class="chip neutral">${o.src.total} rows</span>`,
        `<span class="chip info">${s.sourceOnly} only in source</span>`,
        sd && `<span class="chip amber" title="${DUP_TITLE}">${sd} duplicate flags</span>`,
        staleChip(staleFrom("source")),
        o.src.duplicateCheckError && `<span class="chip amber">Duplicate check unavailable</span>`,
      ])
      + chipColumnHtml("target", `Target · ${o.tgt.org}`, [
        `<span class="chip neutral">${o.tgt.total} rows</span>`,
        `<span class="chip info">${s.targetOnly} only in target</span>`,
        td && `<span class="chip amber" title="${DUP_TITLE}">${td} duplicate flags</span>`,
        staleChip(staleFrom("target")),
        o.tgt.duplicateCheckError && `<span class="chip amber">Duplicate check unavailable</span>`,
      ])
      + `</div>`
      + `<div class="chip-compare"><span class="chip-group-label">Comparison</span><div class="chips">${comparison.join("")}</div></div>`;
  }

  // ---- Deploy selected constraint data to the target ----
  function renderResults(data) {
    const s = data.stats;
    let html = `<h4>Deployment results — target ${esc(data.target)}</h4>`;
    if (data.outcome === "partial") {
      const partialText = data.recoveryRequired
        ? (data.log || "RECOVERY REQUIRED — associations changed but runtime validation is not established.")
        : "Partial deployment: Salesforce applied some rows and rejected others because allOrNone=false. Review every failed row before retrying.";
      html += `<div class="status show err result-alert"><strong>${esc(partialText)}</strong></div>`;
    }
    html += `<div class="chips result-chips">`
      + `<span class="chip ok">${s.insertOk} added</span>`
      + (s.insertSkipped ? `<span class="chip warn">${s.insertSkipped} duplicate add skipped</span>` : "")
      + (s.insertFail ? `<span class="chip warn">${s.insertFail} add failed</span>` : "")
      + `<span class="chip extra">${s.deleteOk} deleted</span>`
      + (s.deleteFail ? `<span class="chip warn">${s.deleteFail} delete failed</span>` : "")
      + `</div>`;
    const failureHtml = r => (r.reasons && r.reasons.length)
      ? ` — <strong>${esc(r.errorTitle || "Blocked")}</strong>${reasonListHtml(r.reasons)}`
      : " — " + esc(r.error || "failed");
    const line = (r, verb) => `<div class="result-row ${r.success ? "good" : "bad"}">`
      + `<span class="ico">${r.success ? "✓" : (r.skipped ? "○" : "✗")}</span>`
      + `<span>${r.skipped ? "Skip" : verb} ${esc(r.label)}${r.success ? "" : failureHtml(r)}`
      + (!r.success && r.diagnostic ? `<details class="diagnostic-details"><summary>Salesforce diagnostic</summary>${esc(diagnosticText(r.diagnostic))}</details>` : "")
      + `</span></div>`;
    if (data.created.length) html += `<h4>Inserts</h4>` + data.created.map(r => line(r, "Add")).join("");
    if (data.deleted.length) html += `<h4>Deletes</h4>` + data.deleted.map(r => line(r, "Delete")).join("");
    if (data.refresh) {
      html += `<h4>CML save/verification refresh</h4>`
        + `<div class="result-row ${data.refresh.ok ? "good" : "bad"}">`
        + `<span class="ico">${data.refresh.ok ? "✓" : "✗"}</span>`
        + `<span>${esc(data.refresh.ok
          ? "Target CML completed the tool-specific unchanged save/verification. This does not prove runtime behavior."
          : data.refresh.log || "Target CML save/verification refresh failed.")}</span></div>`;
    }
    if (data.archive && data.archive.id) {
      html += `<div class="result-recovery"><button class="ghost" id="restoreArchiveBtn">Restore deleted associations</button></div>`;
    }
    if (data.backup && data.backup.file) {
      html += `<div class="result-row good"><span>CML backup</span><span>${esc(data.backup.file)}</span></div>`;
    }
    if (data.report && data.report.file) {
      html += `<div class="result-row good"><span>Report</span><span>${esc(data.report.file)}</span></div>`;
    }
    if (data.reportError) {
      html += `<div class="result-row bad"><span>!</span><span>${esc(data.reportError)}</span></div>`;
    }
    if (data.auditError) {
      html += `<div class="result-row bad"><span>!</span><span>${esc(data.auditError)}</span></div>`;
    }
    results.innerHTML = html;
    results.classList.add("show");
    const restoreBtn = $("restoreArchiveBtn");
    if (restoreBtn) restoreBtn.onclick = async () => {
      const dest = data.target;
      const typed = await requestTypedConfirmation({
        title: "Restore deleted associations",
        description: "This recreates associations from the selected local recovery archive.",
        target: `Target org: ${dest}\nModel: ${data.model}\nExact version: ${data.targetVersionId}\nArchive: ${data.archive.id}`,
        alias: dest,
        submitLabel: "Restore associations",
      });
      if (typed !== dest) return;
      busy(restoreBtn, "Restoring…");
      try {
        const restored = await postJSON("/api/data/restore", {
          targetOrg: dest, model: data.model,
          targetVersionId: data.targetVersionId,
          archiveId: data.archive.id, confirmTarget: typed
        });
        setStatus(restored.ok ? "ok" : "err", appendDiagnostic(
          restored.log || "Association restore finished.",
          restored.diagnostic), dSt());
        await loadAssociationArchives();
        await loadDeploymentReports();
      } catch (e) {
        if (e && e.conn) { handleDisconnect(); } else { setStatus("err", "Restore error: " + e, dSt()); }
      }
      restoreBtn.textContent = "Restore deleted associations";
      idle();
      restoreBtn.focus();
    };
    results.scrollIntoView({ behavior: "smooth", block: "nearest" });
  }

  deployDataBtn.onclick = async () => {
    const source = selectedSourceVersion();
    if (!source || !targetVersionSel.value) {
      setStatus("err", "Select exact source and target versions before deployment.", dSt());
      return;
    }
    const adds = dataRows.filter(r => isAdd(r) && r._selected)
      .map(r => ({ sourceConstraintId: r.id, refName: r.refName }));
    const deletes = dataRows.filter(r => isDel(r) && r._selected)
      .map(r => ({ id: r.id, tag: r.tag, tagType: r.tagType, refName: r.refName }));
    if (!adds.length && !deletes.length) { setStatus("err", "Select at least one row to deploy.", dSt()); return; }
    const typed = await requestTypedConfirmation({
      title: deletes.length ? "Deploy and delete associations" : "Deploy associations",
      description: deletes.length
        ? "Selected additions will be created and selected deletions are permanent. Server-side dependency checks still run immediately before writing."
        : "Selected additions will be created after server-side dependency checks run again.",
      target: `Target org: ${targetSel.value}\nModel: ${source.name}\nExact version: ${targetVersionSel.value}\nAdd: ${adds.length}\nDelete permanently: ${deletes.length}`,
      alias: targetSel.value,
      submitLabel: deletes.length ? "Deploy and delete" : "Deploy associations",
    });
    if (typed !== targetSel.value) return;
    busy(deployDataBtn, "Deploying…");
    setStatus("info", `Deploying constraint data to ${targetSel.value}: +${adds.length} / −${deletes.length}…`, dSt());
    try {
      const data = await postJSON("/api/data/deploy", {
        sourceOrg: orgSel.value, targetOrg: targetSel.value,
        model: source.name, sourceVersionId: source.versionId,
        targetVersionId: targetVersionSel.value,
        adds, deletes, keyField: keyName(), confirmTarget: typed
      });
      if (data.stats) {
        renderResults(data);
        const s = data.stats;
        const refreshFailed = data.refresh && !data.refresh.ok;
        const nonSuccess = s.insertFail + s.deleteFail + (s.insertSkipped || 0);
        const severity = (data.outcome === "failed" || data.outcome === "partial"
          || refreshFailed) ? "err" : (nonSuccess ? "info" : "ok");
        setStatus(severity,
          (nonSuccess ? "Done with problems — see Deployment results above." : "Done — see Deployment results above.")
          + (refreshFailed ? ` RECOVERY REQUIRED — associations changed, but the tool-specific CML save/verification refresh failed; runtime validation is not established.` : "")
          + `\nReview the saved report and recovery options below, then click Compare data to refresh.`, dSt());
        await loadAssociationArchives();
        await loadDeploymentReports();
      } else {
        setStatus("err", appendDiagnostic(
          data.log || "Deploy failed.", data.diagnostic), dSt());
      }
    } catch (e) {
      if (e && e.conn) { handleDisconnect(); } else { setStatus("err", "Deploy error: " + e, dSt()); }
    }
    idle();
    deployDataBtn.focus();
  };

  document.addEventListener("keydown", event => {
    const modifier = event.metaKey || event.ctrlKey;
    if (modifier && event.key.toLowerCase() === "s" && !["cdfix", "xml"].includes(currentView)) {
      event.preventDefault();
      if (editingTarget) {
        saveTargetEditBtn.click();
        return;
      }
      if (updateDirtyIndicator()) {
        switchView("fetch");
        setStatus("info", "Draft saved in this browser tab/session. Review the exact deployment target, then use Deploy CML.");
        deployOrgTrigger.focus();
      } else {
        setStatus("info", "No unsaved CML changes to prepare.");
      }
    }
    if (event.key === "Escape" && editingTarget
        && !confirmDialog.open && !shortcutDialog.open) {
      event.preventDefault();
      cancelTargetEditBtn.click();
      editTargetBtn.focus();
    }
  });

  apiGet("/api/ping")
    .then(d => {
      const e = $("appver");
      if (e && d && !d.error) {
        e.textContent = `v${d.version || "?"} · build ${(d.build || "?").slice(0, 8)}`;
        const badge = document.querySelector(".local-badge");
        if (badge) badge.title = `Runs locally · ${e.textContent}`;
      }
    })
    .catch(error => {
      if (error && error.conn) handleDisconnect();
    });

  const buildBanner = $("buildBanner"), buildBannerText = $("buildBannerText");
  const buildBannerReload = $("buildBannerReload");
  const servedByTool = /^https?:$/.test(window.location.protocol);
  let loadedAssetsHash = null;
  async function checkBuildStatus() {
    let status;
    try {
      status = await apiGet("/api/build-status");
    } catch (error) {
      return;
    }
    if (!status || !status.ok) return;
    if (loadedAssetsHash == null) loadedAssetsHash = status.assetsHash;
    const assetsChanged = status.assetsHash !== loadedAssetsHash;
    if (status.serverStale) {
      buildBannerText.textContent = "The CML Tool's server code changed after it started, so it is still running the old version. " +
        "Restart it: press Ctrl+C in its terminal, then run python3 app/cml_tool.py again. Until then, analysis and builds use the old code.";
    } else if (assetsChanged) {
      buildBannerText.textContent = "The CML Tool's interface was updated. Reload the page to use the new version.";
    }
    buildBannerReload.hidden = !assetsChanged || status.serverStale;
    buildBanner.hidden = !status.serverStale && !assetsChanged;
  }
  if (servedByTool) {
    buildBannerReload.addEventListener("click", () => window.location.reload());
    checkBuildStatus();
    setInterval(checkBuildStatus, 60_000);
    document.addEventListener("visibilitychange", () => {
      if (document.visibilityState === "visible") checkBuildStatus();
    });
  }

  loadOrgs();
