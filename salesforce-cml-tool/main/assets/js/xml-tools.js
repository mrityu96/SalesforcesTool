(function () {
  "use strict";

  const $ = (id) => document.getElementById(id);
  const { apiGet, postJSON } = window.CmlApi;
  const shell = window.CmlShell;

  function esc(value) {
    return (value == null ? "" : String(value))
      .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
  }
  function setStatus(el, kind, msg) { shell.setStatus(kind, msg, el); }
  function clearStatus(el) { el.className = "status"; el.textContent = ""; }
  function showReport(box, body, text) {
    body.textContent = text || "";
    box.classList.toggle("show", Boolean(text));
  }
  function busy(btn, label) {
    btn.dataset.originalHtml = btn.innerHTML;
    btn.innerHTML = '<span class="spinner"></span>' + esc(label);
    btn.disabled = true;
  }
  function idle(btn) {
    if (btn.dataset.originalHtml) btn.innerHTML = btn.dataset.originalHtml;
    btn.disabled = false;
  }
  async function callApi(request) {
    try {
      return await request();
    } catch (error) {
      if (error && error.conn) return { ok: false, log: "Lost connection to the local CML Tool. Is its window still open?" };
      return { ok: false, log: String((error && error.message) || error || "Request failed.") };
    }
  }
  const post = (url, payload) => callApi(() => postJSON(url, payload));

  // ── XML editors (CodeMirror renders only the visible lines) ─────
  const xmlEditors = {};
  const lineRefresh = {};
  function initXmlEditor(id) {
    const host = $(id);
    if (!host) return;
    const placeholder = host.dataset.placeholder || "";
    const editor = window.CmlEditors.create(host, {
      language: "xml",
      readOnly: host.hasAttribute("data-readonly"),
      placeholder,
    });
    editor.view.contentDOM.setAttribute("aria-label", placeholder.split("\n")[0]);
    xmlEditors[id] = editor;
    const footer = document.createElement("div");
    footer.className = "editor-status";
    footer.innerHTML = '<span class="format">XML</span><span data-lines></span><span class="waiting" data-validity>Awaiting XML</span>';
    host.closest(".xpane").appendChild(footer);
    let validityTimer = null, validityVersion = 0;
    function refreshValidity(version) {
      if (version !== validityVersion) return;
      const validity = footer.querySelector("[data-validity]");
      const text = editor.getValue();
      if (!text.trim()) {
        validity.className = "waiting";
        validity.textContent = "Awaiting XML";
        return;
      }
      const invalid = new DOMParser().parseFromString(text, "application/xml").querySelector("parsererror");
      validity.className = invalid ? "invalid" : "valid";
      validity.textContent = invalid ? "Invalid XML" : "Valid XML";
    }
    function refresh() {
      const doc = editor.view.state.doc;
      footer.querySelector("[data-lines]").textContent = `${doc.lines.toLocaleString()} lines`;
      clearTimeout(validityTimer);
      const version = ++validityVersion;
      validityTimer = setTimeout(() => refreshValidity(version), doc.length > 200000 ? 900 : 300);
    }
    host.addEventListener("input", refresh);
    refresh();
    lineRefresh[id] = refresh;
  }
  ["cmpA", "cmpB", "mrgA", "mrgB", "mrgOut", "dedIn", "dedOut", "cdfBase", "cdfMod", "cdfOut"].forEach(initXmlEditor);

  function setText(id, value) {
    if (xmlEditors[id]) xmlEditors[id].setValue(value || "", false);
    else $(id).value = value || "";
    if (lineRefresh[id]) lineRefresh[id]();
  }

  async function copyFrom(textarea, btn) {
    if (!textarea.value) return;
    try {
      await navigator.clipboard.writeText(textarea.value);
    } catch (_) {
      const readonly = textarea.hasAttribute("readonly");
      if (readonly) textarea.removeAttribute("readonly");
      textarea.select();
      document.execCommand("copy");
      if (readonly) textarea.setAttribute("readonly", "");
    }
    const label = btn.textContent;
    btn.textContent = "Copied!";
    setTimeout(() => { btn.textContent = label; }, 1200);
  }
  function download(textarea, name) {
    if (textarea.value) shell.downloadTextFile(name, textarea.value, "text/xml;charset=utf-8");
  }
  async function pasteInto(id) {
    try {
      setText(id, await navigator.clipboard.readText());
      $(id).dispatchEvent(new Event("input", { bubbles: true }));
    } catch (_) {
      $(id).focus();
      window.alert("Clipboard access was blocked. Click inside the editor and use Cmd/Ctrl+V to paste.");
    }
  }
  document.querySelectorAll(".xml-scope [data-paste]").forEach(btn => {
    btn.addEventListener("click", () => pasteInto(btn.dataset.paste));
  });
  document.querySelectorAll(".xml-scope [data-copy]").forEach(btn => {
    btn.addEventListener("click", () => copyFrom($(btn.dataset.copy), btn));
  });
  document.querySelectorAll(".xml-scope [data-clear]").forEach(btn => {
    btn.addEventListener("click", () => {
      setText(btn.dataset.clear, "");
      $(btn.dataset.clear).dispatchEvent(new Event("input", { bubbles: true }));
    });
  });

  // ── XML Tools secondary navigation ──────────────────────────────
  const subTabs = Array.from(document.querySelectorAll("[data-xml-tab]"));
  function switchXmlTab(tab) {
    if (!document.querySelector(`[data-xml-panel="${tab}"]`)) tab = "compare";
    subTabs.forEach(button => {
      const active = button.dataset.xmlTab === tab;
      button.classList.toggle("active", active);
      button.setAttribute("aria-selected", String(active));
      button.tabIndex = active ? 0 : -1;
    });
    document.querySelectorAll("[data-xml-panel]").forEach(panel => {
      panel.classList.toggle("active", panel.dataset.xmlPanel === tab);
    });
    try { localStorage.setItem("cml-xml-subtab", tab); } catch (_) {}
  }
  subTabs.forEach((button, index) => {
    button.addEventListener("click", () => switchXmlTab(button.dataset.xmlTab));
    button.addEventListener("keydown", event => {
      let next = null;
      if (event.key === "ArrowRight") next = (index + 1) % subTabs.length;
      if (event.key === "ArrowLeft") next = (index - 1 + subTabs.length) % subTabs.length;
      if (next === null) return;
      event.preventDefault();
      subTabs[next].focus();
      switchXmlTab(subTabs[next].dataset.xmlTab);
    });
  });
  let savedTab = "compare";
  try { savedTab = localStorage.getItem("cml-xml-subtab") || "compare"; } catch (_) {}
  switchXmlTab(savedTab);

  // ════════════════════════ XML COMPARE ═══════════════════════════
  const cmpA = $("cmpA"), cmpB = $("cmpB"), cmpTag = $("cmpTag"), xcmpBtn = $("xcmpBtn");
  const cmpStatus = $("cmpStatus"), cmpReport = $("cmpReport"), cmpReportBody = $("cmpReportBody");
  const xDiff = $("xDiff"), xDiffSummary = $("xDiffSummary"), xOnlyDiffs = $("xOnlyDiffs");
  const xDiffPanes = $("xDiffPanes"), xSrcTable = $("xSrcTable"), xTgtTable = $("xTgtTable");
  const xSrcScroll = $("xSrcScroll"), xTgtScroll = $("xTgtScroll");

  function paneRow(rowType, num, codeHtml, marker) {
    if (rowType === "filler") return '<tr class="row-filler"><td class="gutter">&nbsp;</td><td class="code">&nbsp;</td></tr>';
    const cls = rowType === "eq" ? "eqrow" : "row-" + rowType;
    return `<tr class="${cls}"><td class="gutter">${num}</td><td class="code"><span class="mk">${marker}</span>${codeHtml}</td></tr>`;
  }
  function diffOps(a, b) {
    const n = a.length, m = b.length;
    const dp = Array.from({ length: n + 1 }, () => new Int32Array(m + 1));
    for (let i = n - 1; i >= 0; i--)
      for (let j = m - 1; j >= 0; j--)
        dp[i][j] = a[i] === b[j] ? dp[i + 1][j + 1] + 1 : Math.max(dp[i + 1][j], dp[i][j + 1]);
    const ops = [];
    let i = 0, j = 0;
    while (i < n && j < m) {
      if (a[i] === b[j]) { ops.push({ t: "eq", a: i++, b: j++ }); }
      else if (dp[i + 1][j] >= dp[i][j + 1]) ops.push({ t: "del", a: i++ });
      else ops.push({ t: "ins", b: j++ });
    }
    while (i < n) ops.push({ t: "del", a: i++ });
    while (j < m) ops.push({ t: "ins", b: j++ });
    return ops;
  }
  function pairStructuralItems(leftItems, rightItems) {
    const pairs = [];
    const unusedRight = new Set(rightItems.map((_, index) => index));
    for (const left of leftItems) {
      const match = rightItems.findIndex((right, index) => unusedRight.has(index) && right.tag === left.tag
        && (left.identity ? right.identity === left.identity : !right.identity));
      if (match >= 0) {
        unusedRight.delete(match);
        pairs.push([left, rightItems[match]]);
      } else {
        pairs.push([left, null]);
      }
    }
    for (const index of unusedRight) pairs.push([null, rightItems[index]]);
    return pairs;
  }
  function structuralItemLines(item) {
    if (!item) return [];
    const identity = item.identity ? ` — ${item.identity}` : "";
    const occurrences = item.count > 1 ? ` (x${item.count})` : "";
    return [`<${item.tag}>${identity}${occurrences}`, ...String(item.snippet || "").split("\n")];
  }
  function renderStructuralDiff(data) {
    const pairs = pairStructuralItems(data.uniqueLeft || [], data.uniqueRight || []);
    let left = "", right = "";
    if (!pairs.length) {
      const message = esc("No unique structural differences — matching XML content may appear on different lines.");
      left = paneRow("eq", "✓", message, " ");
      right = left;
    }
    pairs.forEach(([leftItem, rightItem], pairIndex) => {
      const leftLines = structuralItemLines(leftItem), rightLines = structuralItemLines(rightItem);
      const rowType = leftItem && rightItem ? "chg" : leftItem ? "del" : "ins";
      for (let index = 0; index < Math.max(leftLines.length, rightLines.length); index++) {
        const label = index === 0 ? `Δ${pairIndex + 1}` : "";
        left += index < leftLines.length ? paneRow(rowType, label, esc(leftLines[index]), rowType === "chg" ? "~" : "−") : paneRow("filler");
        right += index < rightLines.length ? paneRow(rowType, label, esc(rightLines[index]), rowType === "chg" ? "~" : "+") : paneRow("filler");
      }
    });
    xSrcTable.innerHTML = "<tbody>" + left + "</tbody>";
    xTgtTable.innerHTML = "<tbody>" + right + "</tbody>";
    xOnlyDiffs.checked = false;
    xOnlyDiffs.closest(".diff-opts").hidden = true;
    xDiffPanes.classList.remove("hide-eq");
    xDiffSummary.textContent = data.onlyLeft + data.onlyRight === 0
      ? "Structurally identical — line position and element order ignored."
      : `${data.onlyLeft} unique occurrence${data.onlyLeft === 1 ? "" : "s"} only in left · ` +
        `${data.onlyRight} unique occurrence${data.onlyRight === 1 ? "" : "s"} only in right`;
    xDiff.classList.add("show");
  }
  function renderLineDiff(aText, bText) {
    xOnlyDiffs.closest(".diff-opts").hidden = false;
    const a = aText.replace(/\r\n/g, "\n").split("\n"), b = bText.replace(/\r\n/g, "\n").split("\n");
    const rows = [];
    let pendingDel = [], pendingIns = [];
    const flush = () => {
      for (let x = 0; x < Math.max(pendingDel.length, pendingIns.length); x++) {
        const d = pendingDel[x], ins = pendingIns[x];
        if (d != null && ins != null) rows.push({ type: "chg", a: d, b: ins });
        else if (d != null) rows.push({ type: "del", a: d });
        else rows.push({ type: "ins", b: ins });
      }
      pendingDel = []; pendingIns = [];
    };
    for (const op of diffOps(a, b)) {
      if (op.t === "eq") { flush(); rows.push({ type: "eq", a: op.a, b: op.b }); }
      else if (op.t === "del") pendingDel.push(op.a);
      else pendingIns.push(op.b);
    }
    flush();
    let chg = 0, del = 0, ins = 0, left = "", right = "";
    for (const r of rows) {
      if (r.type === "eq") { left += paneRow("eq", r.a + 1, esc(a[r.a]), " "); right += paneRow("eq", r.b + 1, esc(b[r.b]), " "); }
      else if (r.type === "chg") { chg++; left += paneRow("chg", r.a + 1, esc(a[r.a]), "~"); right += paneRow("chg", r.b + 1, esc(b[r.b]), "~"); }
      else if (r.type === "del") { del++; left += paneRow("del", r.a + 1, esc(a[r.a]), "−"); right += paneRow("filler"); }
      else { ins++; left += paneRow("filler"); right += paneRow("ins", r.b + 1, esc(b[r.b]), "+"); }
    }
    xSrcTable.innerHTML = "<tbody>" + left + "</tbody>";
    xTgtTable.innerHTML = "<tbody>" + right + "</tbody>";
    xDiffPanes.classList.toggle("hide-eq", xOnlyDiffs.checked);
    xDiffSummary.textContent = chg + del + ins === 0
      ? `Identical — ${a.length} lines match exactly.`
      : `${chg} changed · ${del} only in left · ${ins} only in right (left ${a.length} lines, right ${b.length} lines)`;
    xDiff.classList.add("show");
  }
  let syncingScroll = false;
  function syncScroll(from, to) {
    from.addEventListener("scroll", () => {
      if (syncingScroll) { syncingScroll = false; return; }
      syncingScroll = true;
      to.scrollTop = from.scrollTop;
    });
  }
  syncScroll(xSrcScroll, xTgtScroll);
  syncScroll(xTgtScroll, xSrcScroll);
  xOnlyDiffs.addEventListener("change", () => xDiffPanes.classList.toggle("hide-eq", xOnlyDiffs.checked));

  xcmpBtn.addEventListener("click", async () => {
    if (!cmpA.value.trim() || !cmpB.value.trim()) { setStatus(cmpStatus, "err", "Paste XML in both panes first."); return; }
    busy(xcmpBtn, "Comparing…");
    xDiff.classList.remove("show");
    cmpReport.classList.remove("show");
    const data = await post("/api/xml/compare", { a: cmpA.value, b: cmpB.value, tag: cmpTag.value });
    idle(xcmpBtn);
    if (!data.ok) { setStatus(cmpStatus, "err", data.log || "Compare failed."); return; }
    if (data.xml === false) renderLineDiff(cmpA.value, cmpB.value);
    else renderStructuralDiff(data);
    showReport(cmpReport, cmpReportBody, data.report);
    if (data.xml === false) setStatus(cmpStatus, "info", "Not valid XML — showing a line-by-line diff only.");
    else setStatus(cmpStatus, "ok", `Compared by XML content, ignoring line position. ${data.matched} matched · ${data.onlyLeft} only in left · ${data.onlyRight} only in right.`);
  });

  // ═════════════════════════ XML MERGE ════════════════════════════
  const mergeBtn = $("mergeBtn"), mrgA = $("mrgA"), mrgB = $("mrgB"), mrgOut = $("mrgOut");
  const baseSelect = $("baseSelect"), badge1 = $("badge1"), badge2 = $("badge2");
  const mrgStatus = $("mrgStatus"), mrgReport = $("mrgReport"), mrgReportBody = $("mrgReportBody");
  const mrgDupWarn = $("mrgDupWarn"), mrgDupBody = $("mrgDupBody"), mrgDupList = $("mrgDupList"), mrgDupToggle = $("mrgDupToggle");

  function updateBadges() {
    const leftIsBase = baseSelect.value === "left";
    badge1.hidden = !leftIsBase;
    badge2.hidden = leftIsBase;
  }
  baseSelect.addEventListener("change", updateBadges);
  updateBadges();
  $("swapBtn").addEventListener("click", () => {
    const left = mrgA.value;
    setText("mrgA", mrgB.value);
    setText("mrgB", left);
  });
  mrgDupToggle.addEventListener("click", () => {
    mrgDupBody.hidden = !mrgDupBody.hidden;
    mrgDupToggle.textContent = mrgDupBody.hidden ? "Show details" : "Hide details";
  });
  mergeBtn.addEventListener("click", async () => {
    if (!mrgA.value.trim() || !mrgB.value.trim()) { setStatus(mrgStatus, "err", "Paste XML in both panes first."); return; }
    const leftIsBase = baseSelect.value === "left";
    busy(mergeBtn, "Merging…");
    mrgReport.classList.remove("show");
    mrgDupWarn.hidden = true;
    const data = await post("/api/xml/merge", {
      base: leftIsBase ? mrgA.value : mrgB.value,
      override: leftIsBase ? mrgB.value : mrgA.value,
    });
    idle(mergeBtn);
    if (!data.ok) {
      setText("mrgOut", "");
      setStatus(mrgStatus, "err", data.log || "Merge failed.");
      return;
    }
    setText("mrgOut", data.merged);
    showReport(mrgReport, mrgReportBody, data.report);
    const duplicates = data.duplicates || [];
    if (duplicates.length) {
      mrgDupList.innerHTML = duplicates.map(line => {
        const badge = line.includes("[Base]") ? '<span class="xbadge base">Base</span>' : '<span class="xbadge modified">Modified</span>';
        return `<li>${badge}${esc(line.replace(/\s*\[(Base|Modified)\]\s*/, "").trim())}</li>`;
      }).join("");
      mrgDupBody.hidden = true;
      mrgDupToggle.textContent = "Show details";
      mrgDupWarn.hidden = false;
    }
    if (data.warnings && data.warnings.length)
      setStatus(mrgStatus, "info", `Merged <${data.rootType}> with ${data.warnings.length} validation warning(s) — see the report below.`);
    else if (duplicates.length)
      setStatus(mrgStatus, "ok", `Merged <${data.rootType}>. ${duplicates.length} duplicate entr${duplicates.length === 1 ? "y" : "ies"} in the inputs were collapsed.`);
    else
      setStatus(mrgStatus, "ok", `Merged <${data.rootType}> successfully. Use Copy or Download to grab the result.`);
  });
  $("mergeCopyBtn").addEventListener("click", event => copyFrom(mrgOut, event.currentTarget));
  $("mergeDownloadBtn").addEventListener("click", () => download(mrgOut, "merged.xml"));

  // ═════════════════════════ XML DEDUP ════════════════════════════
  const dedupBtn = $("dedupBtn"), dedIn = $("dedIn"), dedOut = $("dedOut");
  const dedStatus = $("dedStatus"), dedReport = $("dedReport"), dedReportBody = $("dedReportBody");
  dedupBtn.addEventListener("click", async () => {
    if (!dedIn.value.trim()) { setStatus(dedStatus, "err", "Paste a Permission Set or Profile XML first."); return; }
    busy(dedupBtn, "Cleaning…");
    dedReport.classList.remove("show");
    const data = await post("/api/xml/dedup", { content: dedIn.value });
    idle(dedupBtn);
    if (!data.ok) {
      setText("dedOut", "");
      setStatus(dedStatus, "err", data.log || "Deduplication failed.");
      return;
    }
    setText("dedOut", data.result);
    showReport(dedReport, dedReportBody, data.report);
    const warnings = data.warnings || [];
    setStatus(dedStatus, warnings.length ? "info" : "ok",
      `Done — ${data.removed} duplicate entr${data.removed === 1 ? "y" : "ies"} removed.` +
      (data.singletonDuplicates ? ` ${data.singletonDuplicates} came from singleton metadata such as description.` : "") +
      (warnings.length ? ` ${warnings.length} conflicting value warning${warnings.length === 1 ? "" : "s"} — see the report.` : ""));
  });
  $("dedupCopyBtn").addEventListener("click", event => copyFrom(dedOut, event.currentTarget));
  $("dedupDownloadBtn").addEventListener("click", () => download(dedOut, "deduplicated.xml"));

  // ════════════════ CONTEXT DEFINITION FIX: RETRIEVE ══════════════
  const cdfBase = $("cdfBase"), cdfMod = $("cdfMod"), cdfOut = $("cdfOut");
  const cdfRetrieveStatus = $("cdfRetrieveStatus");
  const NAME_KEY = "cml-cdfix-name";

  const sides = {
    base: { select: $("targetOrg"), textareaId: "cdfBase", role: "target" },
    modified: { select: $("org"), textareaId: "cdfMod", role: "source" },
  };
  Object.entries(sides).forEach(([key, side]) => {
    const root = document.querySelector(`[data-cdf-side="${key}"]`);
    Object.assign(side, {
      key,
      root,
      orgName: root.querySelector(".cdf-org-name"),
      nameSelect: root.querySelector(".cdf-name-select"),
      refreshBtn: root.querySelector(".cdf-refresh"),
      retrieveBtn: root.querySelector(".cdf-retrieve-btn"),
      sourceBadge: root.querySelector(".cdf-source"),
      loadedOrg: null,
      loadSequence: 0,
      retrieved: null,
    });
  });

  function preferredName() {
    try { return localStorage.getItem(NAME_KEY) || ""; } catch (_) { return ""; }
  }
  function orgDisplay(select) {
    const option = select.selectedOptions && select.selectedOptions[0];
    return select.value ? (option && option.textContent.trim()) || select.value : "";
  }
  function setSourceBadge(side, kind, text) {
    side.sourceBadge.className = "cdf-source " + kind;
    side.sourceBadge.textContent = text;
  }
  function updateSourceFromInput(side) {
    const textarea = $(side.textareaId);
    if (!textarea.value.trim()) { side.retrieved = null; setSourceBadge(side, "", "Empty"); return; }
    if (side.retrieved) {
      if (textarea.value !== side.retrieved.content) setSourceBadge(side, "edited", `Edited · retrieved from ${side.retrieved.org}`);
      return;
    }
    setSourceBadge(side, "pasted", "Pasted");
  }
  function updateRetrieveControls(side) {
    const hasOrg = Boolean(side.select.value);
    side.refreshBtn.disabled = !hasOrg;
    side.nameSelect.disabled = !hasOrg || !side.nameSelect.options.length || !side.nameSelect.value;
    side.retrieveBtn.disabled = !hasOrg || !side.nameSelect.value;
  }
  function renderNameOptions(side, definitions, message) {
    if (!definitions.length) {
      side.nameSelect.innerHTML = `<option value="">${esc(message || "No Context Definitions found")}</option>`;
      updateRetrieveControls(side);
      return;
    }
    const other = side.key === "base" ? sides.modified : sides.base;
    const wanted = [side.nameSelect.value, other.nameSelect.value, preferredName()].filter(Boolean);
    const names = definitions.map(item => item.name);
    const chosen = wanted.find(name => names.includes(name)) || names[0];
    side.nameSelect.innerHTML = definitions.map(item => {
      const modified = item.lastModifiedDate ? ` · modified ${item.lastModifiedDate.slice(0, 10)}` : "";
      return `<option value="${esc(item.name)}"${item.name === chosen ? " selected" : ""}>${esc(item.name + modified)}</option>`;
    }).join("");
    updateRetrieveControls(side);
  }
  async function loadDefinitionList(side, force) {
    const org = side.select.value;
    side.orgName.textContent = orgDisplay(side.select) || "—";
    if (!org) {
      side.loadedOrg = null;
      side.nameSelect.innerHTML = `<option value="">Select a ${side.role} org above…</option>`;
      updateRetrieveControls(side);
      return;
    }
    if (!force && side.loadedOrg === org) { updateRetrieveControls(side); return; }
    const sequence = ++side.loadSequence;
    side.loadedOrg = org;
    side.nameSelect.innerHTML = '<option value="">Loading Context Definitions…</option>';
    updateRetrieveControls(side);
    side.refreshBtn.disabled = true;
    const data = await callApi(() => apiGet("/api/context-definitions?org=" + encodeURIComponent(org)));
    if (sequence !== side.loadSequence) return;
    if (!data.ok) {
      side.loadedOrg = null;
      renderNameOptions(side, [], "Could not load the list");
      setStatus(cdfRetrieveStatus, "err", data.log || `Could not list Context Definitions in ${org}.`);
      return;
    }
    renderNameOptions(side, data.definitions || [], `No Context Definitions in ${org}`);
  }
  function syncSides(force) {
    if (shell.currentView() !== "cdfix") return;
    Object.values(sides).forEach(side => loadDefinitionList(side, force));
  }
  Object.values(sides).forEach(side => {
    side.select.addEventListener("change", () => {
      side.orgName.textContent = orgDisplay(side.select) || "—";
      side.loadedOrg = null;
      syncSides(false);
      updateRetrieveControls(side);
    });
    side.nameSelect.addEventListener("change", () => updateRetrieveControls(side));
    side.refreshBtn.addEventListener("click", () => loadDefinitionList(side, true));
    $(side.textareaId).addEventListener("input", () => updateSourceFromInput(side));
    side.retrieveBtn.addEventListener("click", async () => {
      const org = side.select.value, name = side.nameSelect.value;
      if (!org || !name) return;
      const textarea = $(side.textareaId);
      const hasUserContent = textarea.value.trim()
        && (!side.retrieved || textarea.value !== side.retrieved.content);
      if (hasUserContent && !window.confirm(`Replace the current ${side.key === "base" ? "Base" : "Modified"} XML with "${name}" from ${org}?`)) return;
      busy(side.retrieveBtn, "Retrieving…");
      setStatus(cdfRetrieveStatus, "info", `Retrieving Context Definition "${name}" from ${org} (read-only)…`);
      const data = await post("/api/context-definitions/retrieve", { org, name });
      idle(side.retrieveBtn);
      updateRetrieveControls(side);
      if (!data.ok) { setStatus(cdfRetrieveStatus, "err", data.log || "Retrieve failed."); return; }
      setText(side.textareaId, data.content);
      side.retrieved = { org, name, content: data.content, orgId: data.orgId || "", retrievedAt: data.retrievedAt || "" };
      const time = new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
      setSourceBadge(side, "retrieved", `Retrieved from ${orgDisplay(side.select) || org} · ${time}`);
      try { localStorage.setItem(NAME_KEY, name); } catch (_) {}
      const warnings = data.warnings || [];
      setStatus(cdfRetrieveStatus, warnings.length ? "info" : "ok",
        data.log + (warnings.length ? `\nWarnings: ${warnings.join("; ")}` : ""));
    });
    updateRetrieveControls(side);
    side.orgName.textContent = orgDisplay(side.select) || "—";
  });
  document.addEventListener("cml:viewchange", event => {
    if (event.detail.view === "cdfix") syncSides(false);
  });

  // ═════════════ CONTEXT DEFINITION FIX: ANALYZE + BUILD ══════════
  const cdfAnalyzeBtn = $("cdfAnalyzeBtn"), cdfBuildBtn = $("cdfBuildBtn");
  const cdfAnalyzeStatus = $("cdfAnalyzeStatus"), cdfBuildStatus = $("cdfBuildStatus");
  const cdfSelectPanel = $("cdfSelectPanel"), cdfBuildStep = $("cdfBuildStep");
  const cdfFieldList = $("cdfFieldList"), cdfSelCount = $("cdfSelCount");
  const cdfReport = $("cdfReport"), cdfReportBody = $("cdfReportBody");
  const cdfDetail = $("cdfDetail"), cdfSearch = $("cdfSearch");
  const cdfTimeline = $("cdfTimeline"), cdfTimelineToggle = $("cdfTimelineToggle");
  const cdfDiffCount = $("cdfDiffCount"), cdfDiffIndicator = $("cdfDiffIndicator");
  const railAdded = $("cdfRailAdded"), railUpdated = $("cdfRailUpdated"), railBaseOnly = $("cdfRailBaseOnly");
  let cdfDiagnostics = $("cdfDiagnostics");
  const cdfDiagList = $("cdfDiagList");
  // Older page shells still have a plain section here. Turn that into the
  // collapsed disclosure, and give the review actions their wider labels.
  (function upgradeReviewChrome() {
    if (cdfDiagnostics && cdfDiagnostics.tagName !== "DETAILS") {
      const details = document.createElement("details");
      details.id = cdfDiagnostics.id;
      details.className = cdfDiagnostics.className;
      const summary = document.createElement("summary");
      const version = $("cdfDiagVersions");
      if (version) summary.appendChild(version);
      summary.appendChild(document.createTextNode(" Why are the line counts different? "));
      const note = document.createElement("small");
      note.textContent = "Separates Salesforce serializer omissions from actual metadata additions, removals, and changes.";
      summary.appendChild(note);
      const body = document.createElement("div");
      body.className = "diag-body";
      const head = cdfDiagnostics.querySelector(".diag-head");
      if (head) head.remove();
      while (cdfDiagnostics.firstChild) body.appendChild(cdfDiagnostics.firstChild);
      details.append(summary, body);
      cdfDiagnostics.replaceWith(details);
      cdfDiagnostics = details;
    }
    const ACTION_ICONS = {
      cdfSelAll: '<rect x="3" y="3" width="18" height="18" rx="4"/><path d="m8 12 3 3 5-6"/>',
      cdfSelNone: '<rect x="3" y="3" width="18" height="18" rx="4"/><path d="M8 12h8"/>',
      cdfExpandAll: '<path d="m7 9 5 5 5-5M7 15l5 5 5-5" transform="translate(0 -4)"/>',
      cdfCollapseAll: '<path d="m7 15 5-5 5 5M7 9l5-5 5 5" transform="translate(0 4)"/>',
    };
    document.querySelectorAll("#cdfSelActions > .ghost").forEach(btn => {
      if (btn.querySelector("svg")) return;
      const label = (btn.dataset.label || btn.textContent || "").trim();
      btn.dataset.label = label;
      btn.innerHTML = '<svg viewBox="0 0 24 24" aria-hidden="true">' + (ACTION_ICONS[btn.id] || "") + "</svg>" +
        "<span>" + esc(label) + "</span>";
    });
  })();
  const MAPPING_TYPES = ["mapping", "mappingBlock", "nodeMappingBlock", "mappingSettings"];
  const NODE_TYPES = ["nodeAttr", "contextNodeBlock", "nodeTag"];
  const RELEASE_HELP = "This is a standard element from the newer Salesforce release that Modified is on. " +
    "Base gets it when its org is upgraded; copying it earlier can fail if the fields it reads do not exist there yet.";
  const typeLabelFor = (it, isParentBlock, isMapping) => isParentBlock ? "Required Parent Block"
    : it.type === "mappingSettings" ? "Mapping Settings"
      : it.type === "nodeTag" ? "Node Tag"
        : isMapping ? "Context Mapping" : "Context Attribute";

  let items = [], itemsById = new Map(), filter = "all";
  let itemCheckboxes = [], cards = [], activeCard = null, activeItem = null;
  let timelineEntries = [], timelineExpanded = false, diagnostics = null;

  function resetRail(text) {
    cdfDiffCount.textContent = text;
    [railAdded, railUpdated, railBaseOnly].forEach(el => { el.textContent = text; });
    cdfDiffIndicator.classList.remove("has-diffs");
  }
  function sideOrigin(side) {
    const retrieved = side.retrieved;
    if (!retrieved) return {};
    return {
      org: retrieved.org, orgId: retrieved.orgId, name: retrieved.name, retrievedAt: retrieved.retrievedAt,
      edited: $(side.textareaId).value !== retrieved.content,
    };
  }
  const NOT_APPLIED_LABELS = { schema: "Schema change", deletion: "Only in Base", tag: "Tag conflict" };
  function renderNotApplied(rows) {
    const box = $("cdfNotApplied");
    rows = rows || [];
    box.hidden = !rows.length;
    $("cdfNotAppliedCount").textContent = rows.length.toLocaleString();
    $("cdfNotAppliedList").innerHTML = rows.map(row =>
      `<div class="cdf-notapplied-row"><span class="cdf-notapplied-kind ${esc(row.kind)}">${esc(NOT_APPLIED_LABELS[row.kind] || row.kind)}</span>` +
      `<code>${esc(row.path)}</code><span>${esc(row.detail)}</span></div>`).join("");
  }
  function resetAnalysis() {
    items = []; itemsById = new Map(); itemCheckboxes = []; cards = []; activeCard = null; activeItem = null;
    cdfFieldList.innerHTML = "";
    cdfSelectPanel.classList.remove("show");
    cdfBuildStep.hidden = true;
    resetDeployStep();
    renderNotApplied([]);
    cdfReport.classList.remove("show");
    cdfDiagnostics.classList.remove("show");
    cdfDiagnostics.open = false;
    diagnostics = null;
    [cdfAnalyzeStatus, cdfBuildStatus].forEach(clearStatus);
    resetRail("—");
  }
  $("cdfClearAll").addEventListener("click", () => {
    ["cdfBase", "cdfMod", "cdfOut"].forEach(id => setText(id, ""));
    Object.values(sides).forEach(side => updateSourceFromInput(side));
    clearStatus(cdfRetrieveStatus);
    resetAnalysis();
  });

  function renderDiagnosticList(view) {
    document.querySelectorAll("[data-diag-view]").forEach(btn => btn.classList.toggle("active", btn.dataset.diagView === view));
    if (!diagnostics) { cdfDiagList.innerHTML = ""; return; }
    if (view === "counts") {
      cdfDiagList.innerHTML = '<div class="diag-count-row head"><span>Element</span><span>Base</span><span>Modified</span><span>Δ</span></div>' +
        (diagnostics.counts || []).map(row => {
          const cls = row.delta > 0 ? "diag-positive" : row.delta < 0 ? "diag-negative" : "";
          return `<div class="diag-count-row"><code>${esc(row.tag)}</code><span>${Number(row.base).toLocaleString()}</span>` +
            `<span>${Number(row.modified).toLocaleString()}</span><strong class="${cls}">${row.delta > 0 ? "+" + row.delta : row.delta}</strong></div>`;
        }).join("");
      return;
    }
    const rows = diagnostics[view] || [];
    if (!rows.length) {
      const label = view === "removed" ? "Base-only metadata" : view === "added" ? "Modified-only metadata" : "material changes";
      cdfDiagList.innerHTML = `<div class="diag-empty">No ${label} found.</div>`;
      return;
    }
    cdfDiagList.innerHTML = rows.map(row => {
      const serializer = String(row.type || "").startsWith("Serializer/");
      return `<div class="diag-row"><span class="diag-kind${serializer ? " serializer" : ""}">${esc(row.type)}</span>` +
        `<span class="diag-name">${esc(row.name)}</span><span><span class="diag-path">${esc(row.path)}</span>` +
        (row.detail ? `<br><span class="diag-detail">${esc(row.detail)}</span>` : "") +
        `</span><span class="diag-count">${Number(row.count || 1).toLocaleString()}</span></div>`;
    }).join("");
  }
  function renderDiagnostics(data) {
    diagnostics = data || null;
    if (!diagnostics) { cdfDiagnostics.classList.remove("show"); return; }
    const number = value => Number(value || 0).toLocaleString();
    $("cdfDiagBaseLines").textContent = number(diagnostics.baseLines);
    $("cdfDiagModifiedLines").textContent = number(diagnostics.modifiedLines);
    const delta = Number(diagnostics.lineDelta || 0);
    const deltaEl = $("cdfDiagLineDelta");
    deltaEl.textContent = delta > 0 ? "+" + delta.toLocaleString() : delta.toLocaleString();
    deltaEl.className = delta > 0 ? "diag-positive" : delta < 0 ? "diag-negative" : "";
    $("cdfDiagBusinessRemoved").textContent = number(diagnostics.businessRemovedCount);
    $("cdfDiagVersions").textContent = `Version ${diagnostics.baseVersion || "?"} → ${diagnostics.modifiedVersion || "?"}`;
    $("cdfDiagExplanation").textContent = diagnostics.summary || "";
    $("cdfDiagRemovedCount").textContent = number(diagnostics.removedCount);
    $("cdfDiagAddedCount").textContent = number(diagnostics.addedCount);
    $("cdfDiagChangedCount").textContent = number(diagnostics.changedCount);
    railAdded.textContent = number(diagnostics.addedCount);
    railUpdated.textContent = number(diagnostics.changedCount);
    railBaseOnly.textContent = number(diagnostics.removedCount);
    cdfDiagnostics.open = false;
    cdfDiagnostics.classList.add("show");
    renderDiagnosticList("removed");
  }
  document.querySelectorAll("[data-diag-view]").forEach(btn => {
    btn.addEventListener("click", () => renderDiagnosticList(btn.dataset.diagView));
  });

  function updateSelectionCount() {
    const checked = itemCheckboxes.filter(cb => cb.checked).length;
    cdfSelCount.textContent = `Total: ${items.length.toLocaleString()} · Selected: ${checked.toLocaleString()}`;
    if (filter === "selected") applyFilters();
  }
  function updateGroupHeader(group) {
    const header = group.querySelector(".cdfix-group-check");
    const boxes = [...group.querySelectorAll("input[data-item]")];
    if (!header || !boxes.length) return;
    const all = boxes.every(b => b.checked), none = boxes.every(b => !b.checked);
    header.indeterminate = !all && !none;
    header.checked = all;
  }
  function setGroupExpanded(group, expanded) {
    group.querySelector(".cdfix-group-body").hidden = !expanded;
    group.querySelector(".cdfix-toggle-arrow").classList.toggle("open", expanded);
  }

  function showDetail(id) {
    const it = itemsById.get(id);
    if (!it) return;
    activeItem = it;
    if (activeCard) activeCard.classList.remove("is-active");
    activeCard = cards.find(card => card.dataset.cardId === id) || null;
    if (activeCard) activeCard.classList.add("is-active");
    const isParentBlock = Boolean(it.parentPatch);
    const isUpdate = it.changeKind === "update";
    const isMapping = MAPPING_TYPES.includes(it.type);
    const name = it.attrName || it.attrTitle || it.mappingTitle || it.nodeName || "";
    const location = it.type === "mappingBlock" || it.type === "mappingSettings" ? `contextMappings › ${it.mappingTitle}`
      : it.type === "nodeMappingBlock" || it.type === "mapping" ? `${it.mappingTitle} › ${it.contextNode} › ${it.object}`
        : `contextNodes › ${it.nodeName}`;
    const preview = it.type === "mappingBlock"
      ? `<contextMappings>\n    <!-- complete mapping and all children -->\n    <title>${it.mappingTitle}</title>\n</contextMappings>`
      : it.type === "nodeMappingBlock"
        ? `<contextNodeMappings>\n    <!-- complete block and all children -->\n    <contextNode>${it.contextNode}</contextNode>\n    <object>${it.object}</object>\n</contextNodeMappings>`
        : it.type === "contextNodeBlock"
          ? `<contextNodes>\n    <!-- complete node and all children -->\n    <title>${it.nodeName}</title>\n</contextNodes>`
          : it.type === "mappingSettings"
            ? `<contextMappings>\n    <!-- ${it.afterField || ""} -->\n    <title>${it.mappingTitle}</title>\n</contextMappings>`
          : it.type === "nodeTag"
            ? `<contextNodes>\n    <contextTags>\n        <title>${it.attrTitle}</title>\n    </contextTags>\n    <title>${it.nodeName}</title>\n</contextNodes>`
          : isMapping
            ? `<contextAttributeMappings>\n    <contextAttribute>${name}</contextAttribute>\n    ${it.fieldInfo ? `<!-- ${it.fieldInfo} -->\n    ` : ""}...\n</contextAttributeMappings>`
            : `<contextAttributes>\n    <title>${name}</title>\n    ...\n</contextAttributes>`;
    const badgeLabel = typeLabelFor(it, isParentBlock, isMapping);
    cdfDetail.innerHTML =
      `<div class="cdfix-detail-head"><span class="cdfix-tbadge ${isMapping ? "cdfix-tbadge-m" : "cdfix-tbadge-n"}">${badgeLabel}</span>` +
      `<h4>${esc(name)}</h4><p>${isParentBlock ? "Ready — Step 3 copies the complete required block" : isUpdate ? "Ready — Step 3 replaces the selected Base definition" : "Ready to apply"}</p></div>` +
      `<div class="cdfix-detail-body"><div class="detail-row"><span>Location</span><code>${esc(location)}</code></div>` +
      (it.fieldInfo ? `<div class="detail-row"><span>Source</span><code>${esc(it.fieldInfo)}</code></div>` : "") +
      (isUpdate ? `<div class="detail-row"><span>Current Base value</span><code>${esc(it.beforeField || "Existing XML definition")}</code></div>` +
        `<div class="detail-row"><span>Modified value</span><code>${esc(it.afterField || "Modified XML definition")}</code></div>` : "") +
      `<div class="detail-row"><span>XML preview</span><pre class="detail-preview">${esc(preview)}</pre></div>` +
      (it.releaseContent ? `<div class="cdfix-parent-help"><strong>Salesforce release:</strong> ${esc(RELEASE_HELP)}</div>` : "") +
      (isParentBlock ? `<div class="cdfix-parent-help"><strong>Full-block patch:</strong> ${esc(it.parentPatchMessage || "")}</div>` : "") +
      (isUpdate && (it.preservedBaseFields || []).length
        ? `<div class="cdfix-parent-help"><strong>Base protected:</strong> Modified omits ${esc(it.preservedBaseFields.join(", "))}; Step 3 preserves it from Base.</div>` : "") +
      "</div>";
    cdfDetail.scrollTop = 0;
    highlightTimeline(it);
  }

  function applyFilters() {
    const query = (cdfSearch.value || "").trim().toLowerCase();
    cards.forEach(card => {
      const cb = card.querySelector("input[data-item]");
      const it = itemsById.get(cb.dataset.item);
      const haystack = [it.attrName, it.attrTitle, it.mappingTitle, it.contextNode, it.object, it.nodeName,
        it.fieldInfo, it.beforeField, it.afterField, it.group].filter(Boolean).join(" ").toLowerCase();
      const matches = filter === "all"
        || (filter === "ready" && !it.parentPatch)
        || (filter === "errors" && it.parentPatch)
        || (filter === "updates" && it.changeKind === "update")
        || (filter === "mapping" && MAPPING_TYPES.includes(it.type))
        || (filter === "nodeAttr" && NODE_TYPES.includes(it.type))
        || (filter === "selected" && cb.checked);
      card.hidden = !matches || Boolean(query && !haystack.includes(query));
    });
    cdfFieldList.querySelectorAll(".cdfix-group").forEach(group => {
      group.classList.toggle("is-filtered-empty", ![...group.querySelectorAll(".cdfix-card")].some(card => !card.hidden));
    });
  }

  function renderItems(list) {
    items = list;
    itemsById = new Map(list.map(it => [it.id, it]));
    const mappingCount = list.filter(it => MAPPING_TYPES.includes(it.type)).length;
    const nodeCount = list.filter(it => NODE_TYPES.includes(it.type)).length;
    $("cdfMetricAll").textContent = list.length;
    $("cdfMetricMappings").textContent = mappingCount;
    $("cdfMetricNodes").textContent = nodeCount;
    $("cdfMetricErrors").textContent = list.filter(it => it.parentPatch).length;
    const groups = new Map();
    list.forEach(it => {
      if (!groups.has(it.group)) groups.set(it.group, []);
      groups.get(it.group).push(it);
    });
    let html = "";
    for (const [groupName, groupItems] of groups) {
      const m = groupItems.filter(i => MAPPING_TYPES.includes(i.type)).length;
      const n = groupItems.filter(i => NODE_TYPES.includes(i.type)).length;
      const meta = [m && `${m} Context Mapping${m > 1 ? "s" : ""}`, n && `${n} Context Attribute${n > 1 ? "s" : ""}`].filter(Boolean).join(" · ");
      html += '<div class="cdfix-group"><div class="cdfix-group-head">' +
        `<input type="checkbox" class="cdfix-group-check" aria-label="Select all in ${esc(groupName)}"${groupItems.some(i => i.releaseContent) ? "" : " checked"} />` +
        `<span class="cdfix-group-name" title="${esc(groupName)}">${esc(groupName)}</span>` +
        `<span class="cdfix-group-meta">${esc(meta)} <span class="cdfix-group-badge">${groupItems.length}</span></span>` +
        '<span class="cdfix-toggle-arrow" aria-hidden="true">▼</span></div><div class="cdfix-group-body" hidden>';
      for (const it of groupItems) {
        const isParentBlock = Boolean(it.parentPatch), isUpdate = it.changeKind === "update";
        const isM = MAPPING_TYPES.includes(it.type);
        const name = esc(it.attrName || it.attrTitle || it.mappingTitle || it.nodeName || "");
        const typeLabel = typeLabelFor(it, isParentBlock, isM);
        const tag = isParentBlock ? '<span class="cdfix-parenttag">Full block patch</span>'
          : isUpdate ? '<span class="cdfix-updatetag">Value change</span>' : '<span class="cdfix-readytag">Ready</span>';
        const releaseTag = it.releaseContent ? '<span class="cdfix-releasetag">Salesforce release</span>' : "";
        const segments = isM ? [it.mappingTitle, it.contextNode, it.object].filter(Boolean) : ["contextNodes", it.nodeName];
        const breadcrumb = segments.map(s => `<span class="cdfix-seg">${esc(s)}</span>`).join('<span class="cdfix-sep">›</span>');
        let detail = "";
        if (isUpdate) {
          detail = `<div class="cdfix-r3"><span class="cdfix-rlabel">Change</span><span class="cdfix-fval cdfix-fval-before">${esc(it.beforeField || "Existing XML")}</span>` +
            `<span class="cdfix-sep">→</span><span class="cdfix-fval cdfix-fval-sf">${esc(it.afterField || "Modified XML")}</span></div>`;
        } else if (isM && it.fieldInfo) {
          const hydration = it.fieldInfo.startsWith("hydration ref:");
          detail = `<div class="cdfix-r3"><span class="cdfix-rlabel">${hydration ? "Hydration" : "SF Field"}</span>` +
            `<span class="cdfix-fval ${hydration ? "cdfix-fval-hyd" : "cdfix-fval-sf"}">${esc(hydration ? it.fieldInfo.replace("hydration ref:", "").trim() : it.fieldInfo)}</span></div>`;
        } else if (!isM && !isParentBlock) {
          detail = `<div class="cdfix-r3"><span class="cdfix-fval-role">${it.type === "nodeTag" ? "Adds this tag to the node" : "Declares this context attribute on the node"}</span></div>`;
        }
        const help = (it.releaseContent ? `<div class="cdfix-parent-help"><strong>Salesforce release:</strong> ${esc(RELEASE_HELP)}</div>` : "") + (isParentBlock
          ? `<div class="cdfix-parent-help"><strong>Applied in Step 3:</strong> ${esc(it.parentPatchMessage || "The complete required block is copied from Modified into Base.")}</div>`
          : isUpdate && (it.preservedBaseFields || []).length
            ? `<div class="cdfix-parent-help"><strong>Base protected:</strong> Preserving ${esc(it.preservedBaseFields.join(", "))} because Modified omits it.</div>` : "");
        html += `<label class="cdfix-card${isM ? " is-mapping" : " is-node"}" data-card-id="${esc(it.id)}">` +
          `<input type="checkbox" data-item="${esc(it.id)}"${it.releaseContent ? "" : " checked"} />` +
          `<div class="cdfix-ci"><div class="cdfix-r1"><span class="cdfix-tbadge ${isM ? "cdfix-tbadge-m" : "cdfix-tbadge-n"}">${typeLabel}</span>` +
          `<span class="cdfix-cname">${name}</span>${tag}${releaseTag}<span class="cdfix-modtag">${isUpdate ? "Modified value" : "Modified only"}</span></div>` +
          `<div class="cdfix-r2"><span class="cdfix-rlabel">Location</span>${breadcrumb}</div>${detail}${help}</div></label>`;
      }
      html += "</div></div>";
    }
    cdfFieldList.innerHTML = html;
    cards = [...cdfFieldList.querySelectorAll(".cdfix-card")];
    itemCheckboxes = [...cdfFieldList.querySelectorAll("input[data-item]")];
    activeCard = null;
    applyFilters();
    updateSelectionCount();
    if (list.length) showDetail(list[0].id);
  }

  cdfFieldList.addEventListener("click", event => {
    const head = event.target.closest(".cdfix-group-head");
    if (head && !event.target.closest(".cdfix-group-check")) {
      const group = head.closest(".cdfix-group");
      setGroupExpanded(group, group.querySelector(".cdfix-group-body").hidden);
      return;
    }
    const card = event.target.closest(".cdfix-card");
    if (card) showDetail(card.dataset.cardId);
  });
  cdfFieldList.addEventListener("change", event => {
    const group = event.target.closest(".cdfix-group");
    if (!group) return;
    if (event.target.classList.contains("cdfix-group-check")) {
      group.querySelectorAll("input[data-item]").forEach(cb => { cb.checked = event.target.checked; });
    } else {
      updateGroupHeader(group);
    }
    updateSelectionCount();
  });
  function setAllSelected(checked) {
    itemCheckboxes.forEach(cb => { cb.checked = checked; });
    cdfFieldList.querySelectorAll(".cdfix-group-check").forEach(cb => { cb.checked = checked; cb.indeterminate = false; });
    updateSelectionCount();
  }
  $("cdfSelAll").addEventListener("click", () => setAllSelected(true));
  $("cdfSelNone").addEventListener("click", () => setAllSelected(false));
  $("cdfExpandAll").addEventListener("click", () => cdfFieldList.querySelectorAll(".cdfix-group").forEach(g => setGroupExpanded(g, true)));
  $("cdfCollapseAll").addEventListener("click", () => cdfFieldList.querySelectorAll(".cdfix-group").forEach(g => setGroupExpanded(g, false)));
  let searchFrame = 0;
  cdfSearch.addEventListener("input", () => {
    cancelAnimationFrame(searchFrame);
    searchFrame = requestAnimationFrame(applyFilters);
  });
  document.querySelectorAll("[data-cdf-filter]").forEach(btn => {
    btn.addEventListener("click", () => {
      filter = btn.dataset.cdfFilter;
      document.querySelectorAll("[data-cdf-filter]").forEach(b => b.classList.toggle("active", b === btn));
      applyFilters();
    });
  });

  function highlightTimeline(item) {
    const rows = [...cdfTimeline.querySelectorAll(".timeline-item")];
    rows.forEach(row => row.classList.remove("is-context-match"));
    if (!item || !rows.length) return;
    const tokens = [item.attrName, item.attrTitle, item.mappingTitle, item.nodeName, item.contextNode, item.object,
      item.beforeField, item.afterField].filter(v => String(v || "").trim().length > 2).map(v => String(v).toLowerCase());
    let match = null, best = 0;
    rows.forEach(row => {
      const text = row.textContent.toLowerCase();
      const score = tokens.reduce((total, token) => total + (text.includes(token) ? 1 : 0), 0);
      if (score > best) { best = score; match = row; }
    });
    if (match) match.classList.add("is-context-match");
  }
  function paintTimeline() {
    const visible = timelineExpanded ? timelineEntries : timelineEntries.slice(0, 6);
    cdfTimeline.innerHTML = visible.map(line => {
      const kind = line.startsWith("✗") ? "error" : line.startsWith("+") ? "add" : line.startsWith("~") ? "update" : "skip";
      const icon = { error: "!", add: "+", update: "~", skip: "✓" }[kind];
      const clean = line.replace(/^[+~✓✗]\s*/, "");
      const splitAt = clean.indexOf(":");
      const label = splitAt >= 0 ? clean.slice(0, splitAt) : { add: "Added", update: "Updated", error: "Error", skip: "Skipped" }[kind];
      const detail = splitAt >= 0 ? clean.slice(splitAt + 1).trim() : clean;
      return `<div class="timeline-item ${kind}"><span class="timeline-icon">${icon}</span>` +
        `<div class="timeline-copy"><strong>${esc(label)}</strong><span>${esc(detail)}</span></div></div>`;
    }).join("");
    highlightTimeline(activeItem);
    cdfTimelineToggle.hidden = timelineEntries.length <= 6;
    cdfTimelineToggle.textContent = timelineExpanded ? "Show quick view" : `Show all ${timelineEntries.length} details`;
  }
  function renderTimeline(report, data) {
    $("cdfReportAdded").textContent = (data.added || 0).toLocaleString();
    $("cdfReportUpdated").textContent = (data.updated || 0).toLocaleString();
    $("cdfReportSkipped").textContent = (data.skipped || 0).toLocaleString();
    $("cdfReportErrors").textContent = (data.errors || 0).toLocaleString();
    timelineEntries = (report || "").split("\n").map(line => line.trim())
      .filter(line => /^[+~✓✗]/.test(line));
    timelineExpanded = false;
    if (!timelineEntries.length) {
      cdfTimeline.innerHTML = '<div class="cdfix-detail-empty"><p>No item-level changes were reported.</p></div>';
      cdfTimelineToggle.hidden = true;
      return;
    }
    paintTimeline();
  }
  cdfTimelineToggle.addEventListener("click", () => { timelineExpanded = !timelineExpanded; paintTimeline(); });

  cdfAnalyzeBtn.addEventListener("click", async () => {
    if (!cdfBase.value.trim() || !cdfMod.value.trim()) {
      setStatus(cdfRetrieveStatus, "err", "Retrieve or paste both the Base and Modified Context Definitions first.");
      return;
    }
    resetAnalysis();
    resetRail("…");
    busy(cdfAnalyzeBtn, "Analyzing…");
    const data = await post("/api/cdfix/analyze", { base: cdfBase.value, modified: cdfMod.value });
    idle(cdfAnalyzeBtn);
    cdfAnalyzeStatus.scrollIntoView({ behavior: "smooth", block: "start" });
    if (!data.ok) {
      resetRail("—");
      setStatus(cdfAnalyzeStatus, "err", data.log || "Analysis failed.");
      return;
    }
    renderDiagnostics(data.diagnostics);
    renderNotApplied(data.notApplied);
    if (!data.items || !data.items.length) {
      cdfDiffCount.textContent = "0";
      setStatus(cdfAnalyzeStatus, "ok", data.summary || "No differences found.");
      return;
    }
    cdfDiffCount.textContent = data.items.length.toLocaleString();
    cdfDiffIndicator.classList.add("has-diffs");
    setStatus(cdfAnalyzeStatus, "ok", data.summary);
    $("cdfSelHeadText").textContent = "Review Context Definition additions, value changes, and Required Parent Blocks";
    renderItems(data.items);
    cdfSelectPanel.classList.add("show");
    cdfBuildStep.hidden = false;
    setText("cdfOut", "");
  });

  cdfBuildBtn.addEventListener("click", async () => {
    const selectedIds = itemCheckboxes.filter(cb => cb.checked).map(cb => cb.dataset.item);
    if (!selectedIds.length) { setStatus(cdfBuildStatus, "err", "Select at least one change to include."); return; }
    busy(cdfBuildBtn, "Building…");
    cdfReport.classList.remove("show");
    resetDeployStep();
    const provenance = { base: sideOrigin(sides.base), modified: sideOrigin(sides.modified) };
    const data = await post("/api/cdfix/build", { base: cdfBase.value, modified: cdfMod.value, selectedIds, provenance });
    idle(cdfBuildBtn);
    if (!data.ok) { setStatus(cdfBuildStatus, "err", data.log || "Build failed."); return; }
    setText("cdfOut", data.result);
    showDeployStep(data);
    showReport(cdfReport, cdfReportBody, data.report);
    renderTimeline(data.report, data);
    const errors = data.errors || 0;
    const parentBlocks = data.parentBlocks || 0;
    const normalized = (data.normalizedDefaults || 0) + (data.normalizedRootFields || []).length;
    const release = (data.releaseContentIds || []).length;
    setStatus(cdfBuildStatus, errors || release ? "info" : "ok", errors
      ? `Built with ${data.applied} change(s) applied · ${errors} error(s) — see the report.`
      : `Done — ${data.added || 0} added and ${data.updated || 0} updated` +
        (parentBlocks ? `, including ${parentBlocks} complete parent block${parentBlocks === 1 ? "" : "s"}` : "") +
        `, ${data.skipped} already present` +
        (normalized ? `; normalized ${normalized} API-incompatible serializer field${normalized === 1 ? "" : "s"}` : "") +
        (release ? `; ${release} item${release === 1 ? " is" : "s are"} Salesforce release content — see the report warnings` : "") +
        ". Nothing was deployed — copy or download the result.");
  });
  // ═════════════ CONTEXT DEFINITION FIX: CHECK + DEPLOY COMMANDS ══
  const cdfDeployStep = $("cdfDeployStep"), cdfDeployOrg = $("cdfDeployOrg");
  const cdfPreflightBtn = $("cdfPreflightBtn"), cdfPreflightStatus = $("cdfPreflightStatus");
  const cdfPreflightList = $("cdfPreflightList"), cdfDeployWarnings = $("cdfDeployWarnings");
  let lastBuild = null, deployPlan = null, planSequence = 0;

  function resetDeployStep() {
    lastBuild = null; deployPlan = null;
    cdfDeployStep.hidden = true;
    cdfPreflightList.innerHTML = "";
    cdfDeployWarnings.innerHTML = "";
    clearStatus(cdfPreflightStatus);
  }
  function describeOrigin(label, origin) {
    if (!origin || !origin.org) return `<div><strong>${label}:</strong> pasted XML (org unknown)</div>`;
    return `<div><strong>${label}:</strong> ${esc(origin.name || "?")} from <code>${esc(origin.org)}</code>` +
      (origin.orgId ? ` · org ${esc(origin.orgId)}` : "") +
      (origin.edited ? " · edited after retrieve" : "") + "</div>";
  }
  function showDeployStep(data) {
    const provenance = data.provenance || {};
    lastBuild = {
      name: data.developerName || "",
      baseOrg: (provenance.base && provenance.base.org) || "",
      baseEdited: Boolean(provenance.base && provenance.base.edited),
      releaseCount: (data.releaseContentIds || []).length,
    };
    const orgs = [...sides.base.select.options].filter(option => option.value);
    const wanted = [lastBuild.baseOrg, sides.base.select.value].find(org => orgs.some(option => option.value === org));
    cdfDeployOrg.innerHTML = (wanted ? "" : '<option value="">Choose an org…</option>') + orgs.map(option =>
      `<option value="${esc(option.value)}"${option.value === wanted ? " selected" : ""}>${esc(option.textContent.trim())}</option>`).join("");
    $("cdfProvenance").innerHTML = describeOrigin("Base", provenance.base) + describeOrigin("Modified", provenance.modified);
    cdfDeployStep.hidden = false;
    refreshDeployPlan();
  }
  async function refreshDeployPlan() {
    if (!lastBuild) return;
    cdfPreflightList.innerHTML = "";
    clearStatus(cdfPreflightStatus);
    cdfPreflightBtn.disabled = !cdfDeployOrg.value;
    const sequence = ++planSequence;
    const plan = await post("/api/cdfix/deploy-plan", {
      name: lastBuild.name, targetOrg: cdfDeployOrg.value, baseOrg: lastBuild.baseOrg,
      releaseCount: lastBuild.releaseCount, baseEdited: lastBuild.baseEdited,
    });
    if (sequence !== planSequence) return;
    deployPlan = plan.ok ? plan : null;
    cdfDeployWarnings.innerHTML = plan.ok
      ? (plan.warnings || []).map(text => `<div class="cdf-deploy-warning">⚠ ${esc(text)}</div>`).join("")
      : `<div class="cdf-deploy-warning">${esc(plan.log || "Could not prepare the deploy commands.")}</div>`;
    $("cdfDeployFilePath").textContent = plan.ok ? plan.filePath : "—";
    $("cdfDeployManifestPath").textContent = plan.ok ? plan.manifestPath : "—";
    $("cdfCmdCheck").textContent = plan.ok ? plan.commands.checkOnly : "";
    $("cdfCmdDeploy").textContent = plan.ok ? plan.commands.deploy : "";
    $("cdfPackageXml").textContent = plan.ok ? plan.packageXml : "";
    $("cdfDownloadDeployBtn").disabled = !plan.ok;
    $("cdfDownloadPackageBtn").disabled = !plan.ok;
  }
  cdfDeployOrg.addEventListener("change", refreshDeployPlan);
  const PREFLIGHT_LABELS = { "missing-object": "Missing object", "missing-field": "Missing field", "type-mismatch": "Type mismatch" };
  cdfPreflightBtn.addEventListener("click", async () => {
    const org = cdfDeployOrg.value;
    if (!org || !cdfOut.value.trim()) return;
    busy(cdfPreflightBtn, "Checking…");
    cdfPreflightList.innerHTML = "";
    setStatus(cdfPreflightStatus, "info", `Reading field definitions from ${org} (read-only)…`);
    const data = await post("/api/cdfix/preflight", { org, content: cdfOut.value, base: cdfBase.value });
    idle(cdfPreflightBtn);
    if (!data.ok) { setStatus(cdfPreflightStatus, "err", data.log || "Field check failed."); return; }
    const problems = data.problems || [];
    setStatus(cdfPreflightStatus, problems.length ? "err" : "ok", data.log);
    cdfPreflightList.innerHTML = problems.map(problem =>
      `<div class="cdf-preflight-row"><span class="cdf-notapplied-kind ${esc(problem.kind)}">${esc(PREFLIGHT_LABELS[problem.kind] || problem.kind)}</span>` +
      `<div><code>${esc(problem.contextNode)} › ${esc(problem.attribute)}</code> <small>${esc(problem.mapping)} · ${problem.inBase ? "already in Base" : "added by this build"}</small>` +
      `<br><span>${esc(problem.detail)}</span> <span class="cdf-preflight-path">${esc(problem.path)}</span></div></div>`).join("");
  });
  document.querySelectorAll("[data-copy-text]").forEach(btn => {
    btn.addEventListener("click", async () => {
      const text = $(btn.dataset.copyText).textContent;
      if (!text) return;
      try { await navigator.clipboard.writeText(text); } catch (_) { return; }
      const label = btn.textContent;
      btn.textContent = "Copied!";
      setTimeout(() => { btn.textContent = label; }, 1200);
    });
  });
  $("cdfDownloadDeployBtn").addEventListener("click", () => {
    if (deployPlan) download(cdfOut, `${deployPlan.name}.contextDefinition-meta.xml`);
  });
  $("cdfDownloadPackageBtn").addEventListener("click", () => {
    if (deployPlan) shell.downloadTextFile("contextDefinition-package.xml", deployPlan.packageXml, "text/xml;charset=utf-8");
  });

  $("cdfCopyBtn").addEventListener("click", event => copyFrom(cdfOut, event.currentTarget));
  $("cdfDownloadBtn").addEventListener("click", () => {
    const name = (sides.base.retrieved && sides.base.retrieved.name) || "context-definition";
    download(cdfOut, `${name}-patched.contextDefinition-meta.xml`);
  });
})();
