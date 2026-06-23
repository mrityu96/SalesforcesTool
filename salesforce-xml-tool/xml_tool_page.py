#!/usr/bin/env python3
"""HTML/JS front-end for xml-tool.py (kept separate for readability)."""

PAGE = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<title>Salesforce Metadata XML Tool</title>
<script>(function(){try{var t=localStorage.getItem('xml-theme')||'light';document.documentElement.setAttribute('data-theme',t);}catch(e){}})();</script>
<style>
  :root {
    --bg: #f4f6f9; --panel: #ffffff; --line: #e3e7ee; --text: #1b2330;
    --muted: #616b7b; --accent: #2f6fed; --green: #1f9d57; --red: #d23b34;
    --purple:#7a4fd0; --radius: 10px; --input-bg: #ffffff;
    --ok-bg:#e7f6ec; --ok-text:#0f6b39; --err-bg:#fdeae8; --err-text:#a3241d;
    --info-bg:#e8f0fe; --info-text:#1b4fb5;
    --chg-bg:#f3e1ec; --del-bg:#fbe3d2; --ins-bg:#d6e9f7;
    --chg-line:#b3589a; --del-line:#d55e00; --ins-line:#0072b2;
    --gutter:#f1f3f7; --gutter-text:#97a1b0;
  }
  html[data-theme="dark"] {
    --bg:#0f1115; --panel:#171a21; --line:#262b35; --text:#e6e9ef; --muted:#9aa3b2;
    --accent:#4c8bf5; --green:#2ea66b; --red:#e5534b; --purple:#9d7ae0; --input-bg:#0f131a;
    --ok-bg:rgba(46,166,107,.12); --ok-text:#8be0b3; --err-bg:rgba(229,83,75,.12); --err-text:#f3a9a4;
    --info-bg:rgba(76,139,245,.10); --info-text:#b9d2ff;
    --chg-bg:rgba(204,121,167,.26); --del-bg:rgba(213,94,0,.26); --ins-bg:rgba(0,114,178,.28);
    --chg-line:#cc79a7; --del-line:#e08a3c; --ins-line:#4ea3df;
    --gutter:#10141b; --gutter-text:#6b7480;
  }
  * { box-sizing: border-box; }
  body {
    margin: 0; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    background: var(--bg); color: var(--text); line-height: 1.5;
  }
  .wrap { max-width: 1400px; margin: 0 auto; padding: 24px 20px 60px; }
  .topbar { display: flex; align-items: flex-start; justify-content: space-between; gap: 12px; }
  h1 { font-size: 20px; margin: 0 0 4px; }
  .sub { color: var(--muted); font-size: 13px; margin: 0 0 20px; }
  .panel { background: var(--panel); border: 1px solid var(--line); border-radius: var(--radius); padding: 18px; }

  /* Operation tabs */
  .tabs { display: inline-flex; gap: 4px; background: var(--gutter); border: 1px solid var(--line);
    border-radius: 10px; padding: 4px; margin-bottom: 18px; flex-wrap: wrap; }
  .tab { border: none; background: transparent; color: var(--muted); font-weight: 600; font-size: 14px;
    padding: 8px 16px; border-radius: 7px; cursor: pointer; }
  .tab.active { background: var(--panel); color: var(--text); box-shadow: 0 1px 3px rgba(0,0,0,.12); }

  label { display: block; font-size: 12px; color: var(--muted); margin-bottom: 6px;
    text-transform: uppercase; letter-spacing: .04em; }
  select, input, textarea {
    width: 100%; background: var(--input-bg); color: var(--text); border: 1px solid var(--line);
    border-radius: 8px; padding: 9px 11px; font-size: 14px; outline: none;
  }
  select:focus, input:focus, textarea:focus { border-color: var(--accent); }
  .controls { display: flex; gap: 14px; flex-wrap: wrap; align-items: flex-end; margin-bottom: 16px; }
  .controls .field { flex: 0 1 280px; }
  .controls label { margin-bottom: 6px; }
  .grow { flex: 1 1 auto; }

  button.action { border: none; border-radius: 8px; padding: 10px 20px; font-size: 14px; font-weight: 600;
    cursor: pointer; color: #fff; }
  button.action:disabled { opacity: .5; cursor: not-allowed; }
  .b-compare { background: var(--accent); }
  .b-merge { background: var(--green); }
  .b-dedup { background: var(--purple); }
  .ghost { background: transparent; border: 1px solid var(--line); color: var(--text);
    font-weight: 500; border-radius: 8px; padding: 8px 14px; font-size: 13px; cursor: pointer; }

  /* Editable code pane (paste areas) */
  .panes { display: flex; gap: 12px; align-items: stretch; flex-wrap: wrap; }
  .xpane { flex: 1 1 0; min-width: 280px; border: 1px solid var(--line); border-radius: 8px;
    overflow: hidden; display: flex; flex-direction: column; background: var(--panel); }
  .xpane-head { display: flex; align-items: center; justify-content: space-between; gap: 8px;
    padding: 8px 12px; border-bottom: 1px solid var(--line); background: var(--gutter); }
  .xpane-head .ttl { font-size: 12px; font-weight: 700; letter-spacing: .03em; text-transform: uppercase; color: var(--muted); }
  .badge { font-size: 10px; font-weight: 700; padding: 2px 8px; border-radius: 99px; color:#fff; }
  .badge.base { background: var(--green); }
  .badge.out { background: var(--accent); }
  .xpane textarea { border: none; border-radius: 0; min-height: 420px; resize: vertical;
    font-family: "SF Mono", Menlo, Consolas, monospace; font-size: 12.5px; white-space: pre;
    tab-size: 2; background: var(--input-bg); }
  .xpane textarea:focus { border: none; }
  .xpane textarea[readonly] { background: var(--gutter); }
  .mini { display: flex; gap: 6px; }
  .mini .ghost { padding: 4px 10px; font-size: 12px; }

  .status { margin-top: 16px; font-size: 13px; padding: 12px 14px; border-radius: 8px; display: none;
    white-space: pre-wrap; font-family: "SF Mono", Menlo, monospace; }
  .status.show { display: block; }
  .status.ok { background: var(--ok-bg); border: 1px solid var(--green); color: var(--ok-text); }
  .status.err { background: var(--err-bg); border: 1px solid var(--red); color: var(--err-text); }
  .status.info { background: var(--info-bg); border: 1px solid var(--accent); color: var(--info-text); }
  .report { margin-top: 16px; display: none; }
  .report.show { display: block; }
  .report pre { background: var(--gutter); border: 1px solid var(--line); border-radius: 8px;
    padding: 14px; overflow: auto; max-height: 360px; font-family: "SF Mono", Menlo, monospace;
    font-size: 12.5px; margin: 0; }
  .report h3 { font-size: 13px; margin: 0 0 8px; text-transform: uppercase; letter-spacing: .04em; color: var(--muted); }

  .spinner { display: inline-block; width: 13px; height: 13px; border: 2px solid rgba(128,128,128,.35);
    border-top-color: #fff; border-radius: 50%; animation: spin .7s linear infinite; vertical-align: -2px; margin-right: 6px; }
  @keyframes spin { to { transform: rotate(360deg); } }
  .hidden { display: none !important; }
  .hint { font-size: 12px; color: var(--muted); margin-top: 4px; }

  /* Diff view — two synced panes */
  .diff { margin-top: 22px; display: none; }
  .diff.show { display: block; }
  .diff-head { display: flex; align-items: center; justify-content: space-between; gap: 12px; flex-wrap: wrap; margin-bottom: 10px; }
  .summary { font-size: 13px; font-weight: 600; }
  .legend { font-size: 12px; color: var(--muted); display: flex; gap: 14px; flex-wrap: wrap; align-items: center; }
  .legend span { display: inline-flex; align-items: center; }
  .legend i { width: 14px; height: 14px; border-radius: 3px; margin-right: 6px; display: inline-flex; align-items: center; justify-content: center; font-size: 10px; font-weight: 700; color: #1b2330; }
  .lg-chg { background: var(--chg-bg); border: 1px solid var(--chg-line); }
  .lg-del { background: var(--del-bg); border: 1px solid var(--del-line); }
  .lg-ins { background: var(--ins-bg); border: 1px solid var(--ins-line); }
  .diff-panes { display: flex; gap: 12px; align-items: stretch; }
  .pane { flex: 1; min-width: 0; border: 1px solid var(--line); border-radius: 8px; overflow: hidden; display: flex; flex-direction: column; }
  .pane-title { padding: 8px 12px; font-size: 12px; font-weight: 600; color: var(--muted); border-bottom: 1px solid var(--line); background: var(--gutter); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  .pane-scroll { overflow: auto; max-height: 620px; }
  table.pane-table { border-collapse: collapse; width: 100%; font-family: "SF Mono", Menlo, Consolas, monospace; font-size: 12.5px; }
  .pane-table td { padding: 0 8px; vertical-align: top; white-space: pre; }
  .gutter { text-align: right; color: var(--gutter-text); background: var(--gutter); user-select: none; width: 1%; white-space: nowrap; border-right: 1px solid var(--line); position: sticky; left: 0; }
  .code { width: 100%; border-left: 3px solid transparent; }
  .mk { user-select: none; display: inline-block; width: 1ch; margin-right: 7px; color: var(--muted); font-weight: 700; }
  .row-chg .code { background: var(--chg-bg); border-left-color: var(--chg-line); }
  .row-del .code { background: var(--del-bg); border-left-color: var(--del-line); }
  .row-ins .code { background: var(--ins-bg); border-left-color: var(--ins-line); }
  .row-filler td { background: repeating-linear-gradient(45deg, transparent, transparent 6px, rgba(128,128,128,.06) 6px, rgba(128,128,128,.06) 12px); }
  .diff-panes.hide-eq tr.eqrow { display: none; }
  .diff-opts { font-size: 12px; color: var(--muted); display: inline-flex; align-items: center; gap: 6px; }
  .diff-opts input { width: auto; }
</style>
</head>
<body>
  <div class="wrap">
    <div class="topbar">
      <div>
        <h1>Salesforce Metadata XML Tool</h1>
        <p class="sub">Compare, merge, and clean up metadata XML — permission sets, context definitions, and more. Paste your XML, pick an operation, no terminal needed.</p>
      </div>
      <button class="ghost" id="themeBtn" title="Toggle day/night">Night mode</button>
    </div>

    <div class="tabs" id="tabs">
      <button class="tab active" data-mode="compare">Compare</button>
      <button class="tab" data-mode="merge">Merge</button>
      <button class="tab" data-mode="dedup">Deduplicate</button>
    </div>

    <!-- ============================ COMPARE ============================ -->
    <div class="panel" id="view-compare">
      <div class="controls">
        <div class="field">
          <label for="cmpTag">Limit to element (optional)</label>
          <input id="cmpTag" placeholder="e.g. fieldPermissions, contextMappings" autocomplete="off" spellcheck="false" />
          <div class="hint">Leave blank to compare everything. Works for permission sets, context definitions, Apex (line diff only), etc.</div>
        </div>
        <div class="grow"></div>
        <div class="field" style="flex:0 0 auto;">
          <button class="action b-compare" id="compareBtn">Compare</button>
        </div>
      </div>

      <div class="panes">
        <div class="xpane">
          <div class="xpane-head">
            <span class="ttl">Left XML</span>
            <div class="mini"><button class="ghost" data-clear="cmpA">Clear</button></div>
          </div>
          <textarea id="cmpA" placeholder="Paste the first XML here…" spellcheck="false"></textarea>
        </div>
        <div class="xpane">
          <div class="xpane-head">
            <span class="ttl">Right XML</span>
            <div class="mini"><button class="ghost" data-clear="cmpB">Clear</button></div>
          </div>
          <textarea id="cmpB" placeholder="Paste the second XML here…" spellcheck="false"></textarea>
        </div>
      </div>

      <div class="status" id="cmpStatus"></div>

      <div class="report" id="cmpReport">
        <h3>Structural summary</h3>
        <pre id="cmpReportBody"></pre>
      </div>

      <div class="diff" id="diff">
        <div class="diff-head">
          <div class="summary" id="diffSummary"></div>
          <div class="legend">
            <span><i class="lg-chg">~</i>Changed</span>
            <span><i class="lg-del">&minus;</i>Only in left</span>
            <span><i class="lg-ins">+</i>Only in right</span>
            <label class="diff-opts"><input type="checkbox" id="onlyDiffs" /> Show only differences</label>
          </div>
        </div>
        <div class="diff-panes" id="diffPanes">
          <div class="pane">
            <div class="pane-title">Left</div>
            <div class="pane-scroll" id="srcScroll"><table class="pane-table" id="srcTable"></table></div>
          </div>
          <div class="pane">
            <div class="pane-title">Right</div>
            <div class="pane-scroll" id="tgtScroll"><table class="pane-table" id="tgtTable"></table></div>
          </div>
        </div>
      </div>
    </div>

    <!-- ============================= MERGE ============================= -->
    <div class="panel hidden" id="view-merge">
      <div class="controls">
        <div class="field">
          <label for="baseSelect">Which pane is the base?</label>
          <select id="baseSelect">
            <option value="left">Pane 1 (Base XML) is the base</option>
            <option value="right">Pane 2 (Modified XML) is the base</option>
          </select>
          <div class="hint">The base is kept intact; the other side's changes are layered on top.</div>
        </div>
        <div class="grow"></div>
        <div class="field" style="flex:0 0 auto;">
          <button class="ghost" id="swapBtn">Swap panes</button>
          <button class="action b-merge" id="mergeBtn">Merge</button>
        </div>
      </div>

      <div class="panes">
        <div class="xpane">
          <div class="xpane-head">
            <span class="ttl">Pane 1 — Base XML <span class="badge base" id="badge1">BASE</span></span>
            <div class="mini"><button class="ghost" data-clear="mrgA">Clear</button></div>
          </div>
          <textarea id="mrgA" placeholder="Paste the BASE XML here (the authoritative version to build on)…" spellcheck="false"></textarea>
        </div>
        <div class="xpane">
          <div class="xpane-head">
            <span class="ttl">Pane 2 — Modified XML <span class="badge base hidden" id="badge2">BASE</span></span>
            <div class="mini"><button class="ghost" data-clear="mrgB">Clear</button></div>
          </div>
          <textarea id="mrgB" placeholder="Paste the MODIFIED XML here (the changes to layer on)…" spellcheck="false"></textarea>
        </div>
        <div class="xpane">
          <div class="xpane-head">
            <span class="ttl">Merged result <span class="badge out">OUTPUT</span></span>
            <div class="mini">
              <button class="ghost" id="mergeCopyBtn">Copy</button>
              <button class="ghost" id="mergeDownloadBtn">Download</button>
            </div>
          </div>
          <textarea id="mrgOut" placeholder="The merged XML will appear here. Use Copy to grab it in one click." spellcheck="false" readonly></textarea>
        </div>
      </div>

      <div class="status" id="mrgStatus"></div>
      <div class="report" id="mrgReport">
        <h3>Merge report</h3>
        <pre id="mrgReportBody"></pre>
      </div>
    </div>

    <!-- =========================== DEDUPLICATE ========================= -->
    <div class="panel hidden" id="view-dedup">
      <div class="controls">
        <div class="grow"></div>
        <div class="field" style="flex:0 0 auto;">
          <button class="action b-dedup" id="dedupBtn">Remove duplicates</button>
        </div>
      </div>
      <div class="panes">
        <div class="xpane">
          <div class="xpane-head">
            <span class="ttl">Permission Set XML</span>
            <div class="mini"><button class="ghost" data-clear="dedIn">Clear</button></div>
          </div>
          <textarea id="dedIn" placeholder="Paste a Permission Set (or Profile) XML here…" spellcheck="false"></textarea>
        </div>
        <div class="xpane">
          <div class="xpane-head">
            <span class="ttl">Cleaned result <span class="badge out">OUTPUT</span></span>
            <div class="mini">
              <button class="ghost" id="dedupCopyBtn">Copy</button>
              <button class="ghost" id="dedupDownloadBtn">Download</button>
            </div>
          </div>
          <textarea id="dedOut" placeholder="The deduplicated, sorted XML will appear here." spellcheck="false" readonly></textarea>
        </div>
      </div>
      <div class="status" id="dedStatus"></div>
      <div class="report" id="dedReport">
        <h3>Deduplication report</h3>
        <pre id="dedReportBody"></pre>
      </div>
    </div>
  </div>

<script>
  const $ = (id) => document.getElementById(id);

  // ---- Theme ----
  const themeBtn = $("themeBtn");
  function applyThemeLabel() {
    const t = document.documentElement.getAttribute("data-theme") || "light";
    themeBtn.textContent = t === "light" ? "Night mode" : "Day mode";
  }
  themeBtn.onclick = () => {
    const cur = document.documentElement.getAttribute("data-theme") || "light";
    const next = cur === "light" ? "dark" : "light";
    document.documentElement.setAttribute("data-theme", next);
    try { localStorage.setItem("xml-theme", next); } catch (e) {}
    applyThemeLabel();
  };
  applyThemeLabel();

  // ---- Tab switching ----
  const views = { compare: $("view-compare"), merge: $("view-merge"), dedup: $("view-dedup") };
  document.querySelectorAll(".tab").forEach(t => {
    t.onclick = () => {
      document.querySelectorAll(".tab").forEach(x => x.classList.remove("active"));
      t.classList.add("active");
      Object.values(views).forEach(v => v.classList.add("hidden"));
      views[t.dataset.mode].classList.remove("hidden");
    };
  });

  // ---- Helpers ----
  function setStatus(el, kind, msg) {
    el.className = "status show " + kind;
    el.textContent = msg;
    el.scrollIntoView({ behavior: "smooth", block: "nearest" });
  }
  function showReport(box, body, text) {
    body.textContent = text || "";
    box.classList.toggle("show", !!text);
  }
  async function postJSON(url, payload) {
    let res;
    try {
      res = await fetch(url, { method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload) });
    } catch (e) { return { ok: false, log: "Lost connection to the XML Tool. Is its window still open?" }; }
    const text = await res.text();
    try { return JSON.parse(text); }
    catch (e) { return { ok: false, log: "Unexpected server response (HTTP " + res.status + "):\n" + text.slice(0, 500) }; }
  }
  function busy(btn, label) { btn.dataset.label = btn.textContent; btn.innerHTML = '<span class="spinner"></span>' + label; btn.disabled = true; }
  function idle(btn) { btn.textContent = btn.dataset.label || btn.textContent; btn.disabled = false; }
  async function copyFrom(textarea, btn) {
    if (!textarea.value) return;
    try { await navigator.clipboard.writeText(textarea.value); }
    catch (e) { textarea.removeAttribute("readonly"); textarea.select(); document.execCommand("copy"); textarea.setAttribute("readonly",""); }
    const old = btn.textContent; btn.textContent = "Copied!"; setTimeout(() => btn.textContent = old, 1200);
  }
  function download(textarea, name) {
    if (!textarea.value) return;
    const blob = new Blob([textarea.value], { type: "text/xml" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob); a.download = name; a.click();
    setTimeout(() => URL.revokeObjectURL(a.href), 1000);
  }
  document.querySelectorAll("[data-clear]").forEach(b => b.onclick = () => { $(b.dataset.clear).value = ""; });

  // ============================ COMPARE ============================
  const compareBtn = $("compareBtn"), cmpA = $("cmpA"), cmpB = $("cmpB"), cmpTag = $("cmpTag");
  const cmpStatus = $("cmpStatus"), cmpReport = $("cmpReport"), cmpReportBody = $("cmpReportBody");
  const diffBox = $("diff"), diffSummary = $("diffSummary"), onlyDiffs = $("onlyDiffs");
  const diffPanes = $("diffPanes"), srcTable = $("srcTable"), tgtTable = $("tgtTable");
  const srcScroll = $("srcScroll"), tgtScroll = $("tgtScroll");

  compareBtn.onclick = async () => {
    if (!cmpA.value.trim() || !cmpB.value.trim()) { setStatus(cmpStatus, "err", "Paste XML in both panes first."); return; }
    busy(compareBtn, "Comparing…");
    diffBox.classList.remove("show"); cmpReport.classList.remove("show");
    const data = await postJSON("/api/compare", { a: cmpA.value, b: cmpB.value, tag: cmpTag.value });
    if (data.ok) {
      renderDiff(cmpA.value, cmpB.value);
      showReport(cmpReport, cmpReportBody, data.report);
      if (data.xml === false) setStatus(cmpStatus, "info", "Not valid XML — showing a line-by-line diff only.");
      else setStatus(cmpStatus, "ok", `Compared. ${data.matched} matched · ${data.onlyLeft} only in left · ${data.onlyRight} only in right.`);
    } else {
      setStatus(cmpStatus, "err", data.log || "Compare failed.");
    }
    idle(compareBtn);
  };

  function esc(s) { return (s == null ? "" : String(s)).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;"); }

  function diffOps(a, b) {
    const n = a.length, m = b.length;
    const dp = Array.from({ length: n + 1 }, () => new Int32Array(m + 1));
    for (let i = n - 1; i >= 0; i--)
      for (let j = m - 1; j >= 0; j--)
        dp[i][j] = a[i] === b[j] ? dp[i + 1][j + 1] + 1 : Math.max(dp[i + 1][j], dp[i][j + 1]);
    const ops = []; let i = 0, j = 0;
    while (i < n && j < m) {
      if (a[i] === b[j]) { ops.push({ t: "eq", a: i, b: j }); i++; j++; }
      else if (dp[i + 1][j] >= dp[i][j + 1]) { ops.push({ t: "del", a: i }); i++; }
      else { ops.push({ t: "ins", b: j }); j++; }
    }
    while (i < n) { ops.push({ t: "del", a: i++ }); }
    while (j < m) { ops.push({ t: "ins", b: j++ }); }
    return ops;
  }
  function paneRow(rowType, num, codeHtml, marker) {
    const cls = rowType === "eq" ? "eqrow" : rowType === "chg" ? "row-chg"
      : rowType === "del" ? "row-del" : rowType === "ins" ? "row-ins" : "row-filler";
    if (rowType === "filler") return `<tr class="row-filler"><td class="gutter">&nbsp;</td><td class="code">&nbsp;</td></tr>`;
    return `<tr class="${cls}"><td class="gutter">${num}</td><td class="code"><span class="mk">${marker}</span>${codeHtml}</td></tr>`;
  }
  function renderDiff(aText, bText) {
    const a = aText.replace(/\r\n/g, "\n").split("\n");
    const b = bText.replace(/\r\n/g, "\n").split("\n");
    const ops = diffOps(a, b);
    const rows = []; let pendDel = [], pendIns = [];
    const flush = () => {
      const k = Math.max(pendDel.length, pendIns.length);
      for (let x = 0; x < k; x++) {
        const d = pendDel[x], ins = pendIns[x];
        if (d != null && ins != null) rows.push({ type: "chg", a: d, b: ins });
        else if (d != null) rows.push({ type: "del", a: d });
        else rows.push({ type: "ins", b: ins });
      }
      pendDel = []; pendIns = [];
    };
    for (const op of ops) {
      if (op.t === "eq") { flush(); rows.push({ type: "eq", a: op.a, b: op.b }); }
      else if (op.t === "del") pendDel.push(op.a);
      else pendIns.push(op.b);
    }
    flush();
    let chg = 0, del = 0, ins = 0, left = "", right = "";
    for (const r of rows) {
      if (r.type === "eq") { left += paneRow("eq", r.a + 1, esc(a[r.a]), " "); right += paneRow("eq", r.b + 1, esc(b[r.b]), " "); }
      else if (r.type === "chg") { chg++; left += paneRow("chg", r.a + 1, esc(a[r.a]), "~"); right += paneRow("chg", r.b + 1, esc(b[r.b]), "~"); }
      else if (r.type === "del") { del++; left += paneRow("del", r.a + 1, esc(a[r.a]), "\u2212"); right += paneRow("filler"); }
      else { ins++; left += paneRow("filler"); right += paneRow("ins", r.b + 1, esc(b[r.b]), "+"); }
    }
    srcTable.innerHTML = "<tbody>" + left + "</tbody>";
    tgtTable.innerHTML = "<tbody>" + right + "</tbody>";
    diffPanes.classList.toggle("hide-eq", onlyDiffs.checked);
    diffSummary.textContent = (chg + del + ins === 0)
      ? `Identical — ${a.length} lines match exactly.`
      : `${chg} changed · ${del} only in left · ${ins} only in right   (left ${a.length} lines, right ${b.length} lines)`;
    diffBox.classList.add("show");
  }
  let syncing = false;
  function syncScroll(from, to) {
    from.addEventListener("scroll", () => {
      if (syncing) { syncing = false; return; }
      syncing = true; to.scrollTop = from.scrollTop;
    });
  }
  syncScroll(srcScroll, tgtScroll); syncScroll(tgtScroll, srcScroll);
  onlyDiffs.onchange = () => diffPanes.classList.toggle("hide-eq", onlyDiffs.checked);

  // ============================= MERGE =============================
  const mergeBtn = $("mergeBtn"), mrgA = $("mrgA"), mrgB = $("mrgB"), mrgOut = $("mrgOut");
  const baseSelect = $("baseSelect"), badge1 = $("badge1"), badge2 = $("badge2");
  const mrgStatus = $("mrgStatus"), mrgReport = $("mrgReport"), mrgReportBody = $("mrgReportBody");
  const swapBtn = $("swapBtn");

  function updateBadges() {
    const leftIsBase = baseSelect.value === "left";
    badge1.classList.toggle("hidden", !leftIsBase);
    badge2.classList.toggle("hidden", leftIsBase);
  }
  baseSelect.onchange = updateBadges;
  updateBadges();

  swapBtn.onclick = () => { const t = mrgA.value; mrgA.value = mrgB.value; mrgB.value = t; };

  mergeBtn.onclick = async () => {
    if (!mrgA.value.trim() || !mrgB.value.trim()) { setStatus(mrgStatus, "err", "Paste XML in both Base and Modified panes first."); return; }
    const leftIsBase = baseSelect.value === "left";
    const base = leftIsBase ? mrgA.value : mrgB.value;
    const override = leftIsBase ? mrgB.value : mrgA.value;
    busy(mergeBtn, "Merging…");
    mrgReport.classList.remove("show");
    const data = await postJSON("/api/merge", { base, override });
    if (data.ok) {
      mrgOut.value = data.merged;
      showReport(mrgReport, mrgReportBody, data.report);
      if (data.warnings && data.warnings.length)
        setStatus(mrgStatus, "info", `Merged <${data.rootType}> with ${data.warnings.length} warning(s) — see report below.`);
      else
        setStatus(mrgStatus, "ok", `Merged <${data.rootType}> successfully. Use Copy to grab the result.`);
    } else {
      mrgOut.value = "";
      setStatus(mrgStatus, "err", data.log || "Merge failed.");
    }
    idle(mergeBtn);
  };
  $("mergeCopyBtn").onclick = (e) => copyFrom(mrgOut, e.target);
  $("mergeDownloadBtn").onclick = () => download(mrgOut, "merged.xml");

  // =========================== DEDUPLICATE =========================
  const dedupBtn = $("dedupBtn"), dedIn = $("dedIn"), dedOut = $("dedOut");
  const dedStatus = $("dedStatus"), dedReport = $("dedReport"), dedReportBody = $("dedReportBody");
  dedupBtn.onclick = async () => {
    if (!dedIn.value.trim()) { setStatus(dedStatus, "err", "Paste a Permission Set XML first."); return; }
    busy(dedupBtn, "Cleaning…");
    dedReport.classList.remove("show");
    const data = await postJSON("/api/dedup", { content: dedIn.value });
    if (data.ok) {
      dedOut.value = data.result;
      showReport(dedReport, dedReportBody, data.report);
      setStatus(dedStatus, "ok", `Done — ${data.removed} duplicate entr${data.removed === 1 ? "y" : "ies"} removed.`);
    } else {
      dedOut.value = "";
      setStatus(dedStatus, "err", data.log || "Deduplication failed.");
    }
    idle(dedupBtn);
  };
  $("dedupCopyBtn").onclick = (e) => copyFrom(dedOut, e.target);
  $("dedupDownloadBtn").onclick = () => download(dedOut, "deduplicated.xml");
</script>
</body>
</html>"""
