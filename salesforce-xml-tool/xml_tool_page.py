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
    --teal:#0d8a78; --teal-bg:#e6f6f3; --teal-text:#085048;
  }
  html[data-theme="dark"] {
    --bg:#0f1115; --panel:#171a21; --line:#262b35; --text:#e6e9ef; --muted:#9aa3b2;
    --accent:#4c8bf5; --green:#2ea66b; --red:#e5534b; --purple:#9d7ae0; --input-bg:#0f131a;
    --ok-bg:rgba(46,166,107,.12); --ok-text:#8be0b3; --err-bg:rgba(229,83,75,.12); --err-text:#f3a9a4;
    --info-bg:rgba(76,139,245,.10); --info-text:#b9d2ff;
    --chg-bg:rgba(204,121,167,.26); --del-bg:rgba(213,94,0,.26); --ins-bg:rgba(0,114,178,.28);
    --chg-line:#cc79a7; --del-line:#e08a3c; --ins-line:#4ea3df;
    --gutter:#10141b; --gutter-text:#6b7480;
    --teal:#12b09a; --teal-bg:rgba(13,138,120,.12); --teal-text:#7ee8d8;
  }
  * { box-sizing: border-box; }
  body {
    margin: 0; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    background: var(--bg); color: var(--text); line-height: 1.5;
  }
  .wrap { max-width: 1400px; margin: 0 auto; padding: 24px 20px 60px; }
  .topbar { display: flex; align-items: flex-start; justify-content: space-between; gap: 12px; }
  h1 { font-size: 20px; margin: 0 0 4px; }
  .sub { color: var(--muted); font-size: 13px; margin: 0 0 6px; }
  .credit { color: var(--muted); font-size: 12px; margin: 0 0 20px; }
  .credit a { color: var(--accent); text-decoration: none; }
  .credit a:hover { text-decoration: underline; }
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
  .b-cdfix { background: var(--teal); }
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
  /* Line-numbered editor body */
  .xpane-body { display: flex; min-height: 420px; resize: vertical; overflow: hidden; }
  /* CD Fix panes — hard-capped 300 px; gutter hidden (32k-line files make it useless).
     !important needed because the base .xpane-body min-height:420px and textarea flex:1
     otherwise override these at runtime when large content is pasted. */
  #view-cdfix .xpane-body {
    min-height: 0   !important;
    height: 300px   !important;
    max-height: 300px !important;
    overflow: hidden !important;
    resize: vertical;
  }
  /* Gutter re-enabled: height is constrained by the parent's height:300px !important,
     so its 32k-line content overflows internally and is clipped — page stays compact. */
  #view-cdfix .ln-gutter { overflow-y: hidden !important; }
  #view-cdfix .xpane textarea {
    flex: none   !important;
    width: 100%  !important;
    height: 300px !important;
    max-height: 300px !important;
    overflow-y: auto !important;
    resize: none !important;
  }
  .ln-gutter {
    flex-shrink: 0; width: 46px; overflow: hidden;
    background: var(--gutter); border-right: 1px solid var(--line);
    font-family: "SF Mono", Menlo, Consolas, monospace; font-size: 12.5px; line-height: 19px;
    padding: 8px 8px 8px 0; text-align: right;
    color: var(--gutter-text); user-select: none; white-space: pre;
  }
  .xpane textarea {
    flex: 1; border: none; border-radius: 0; resize: none; outline: none;
    font-family: "SF Mono", Menlo, Consolas, monospace; font-size: 12.5px; line-height: 19px;
    white-space: pre; tab-size: 2; background: var(--input-bg);
    padding: 8px; overflow: auto;
  }
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
  .dup-warn { display: none; margin-top: 14px; border-radius: 8px; overflow: hidden;
    border: 2px solid #b45309; }
  .dup-warn.show { display: block; }
  .dup-warn-head { display: flex; align-items: center; justify-content: space-between; gap: 10px;
    background: #b45309; color: #fff; padding: 10px 14px; font-size: 13px; font-weight: 700; }
  .dup-warn-head svg { flex-shrink: 0; }
  .dup-warn-body { background: #fffbeb; color: #78350f; padding: 12px 14px; font-size: 13px; line-height: 1.6; }
  html[data-theme="dark"] .dup-warn { border-color: #d97706; }
  html[data-theme="dark"] .dup-warn-head { background: #92400e; }
  html[data-theme="dark"] .dup-warn-body { background: rgba(217,119,6,.1); color: #fcd34d; }
  .dup-list { margin: 8px 0 0; padding: 8px 12px; background: rgba(0,0,0,.06); border-radius: 6px;
    font-family: "SF Mono", Menlo, monospace; font-size: 12px; max-height: 180px; overflow-y: auto; }
  html[data-theme="dark"] .dup-list { background: rgba(255,255,255,.05); }
  .dup-list li { margin: 2px 0; list-style: none; padding-left: 1.2em; text-indent: -1.2em; }
  .dup-badge { display: inline-block; font-size: 10px; font-weight: 700; padding: 1px 6px;
    border-radius: 99px; margin-right: 4px; }
  .dup-badge.base { background: #1f9d57; color: #fff; }
  .dup-badge.mod  { background: #2f6fed; color: #fff; }
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

  /* ── CD Fix ─────────────────────────────────────────────────────── */
  .cdfix-step { margin-top: 20px; }
  .cdfix-step-head { display: flex; align-items: center; gap: 10px; margin-bottom: 10px; }
  .cdfix-step-num { width: 24px; height: 24px; border-radius: 50%; background: var(--teal);
    color: #fff; font-size: 12px; font-weight: 700; display: inline-flex; align-items: center; justify-content: center; flex-shrink: 0; }
  .cdfix-step-title { font-size: 13px; font-weight: 700; color: var(--text); }
  .cdfix-step-sub { font-size: 12px; color: var(--muted); margin-top: 2px; }

  /* ── CD Fix selection panel ─────────────────────────────────── */
  .cdfix-select { display: none; margin-top: 20px; border: 1px solid var(--teal); border-radius: var(--radius); overflow: hidden; }
  .cdfix-select.show { display: block; }
  .cdfix-sel-head { background: var(--teal); color: #fff; padding: 10px 16px; font-size: 13px; font-weight: 700;
    display: flex; align-items: center; justify-content: space-between; gap: 10px; }
  .cdfix-sel-body { padding: 12px 14px; background: var(--panel); max-height: 520px; overflow-y: auto; }
  .cdfix-sel-actions { display: flex; gap: 8px; flex-wrap: wrap; margin-bottom: 12px; align-items: center; }
  .cdfix-sel-actions .ghost { padding: 5px 12px; font-size: 12px; }
  .cdfix-legend { display: flex; gap: 10px; margin-left: auto; flex-wrap: wrap; }
  .cdfix-legend-item { display: inline-flex; align-items: center; gap: 4px; font-size: 11px; color: var(--muted); }
  .cdfix-legend-dot { width: 8px; height: 8px; border-radius: 2px; }

  /* ── Group header ────────────────────────────────────────────── */
  .cdfix-group { margin-bottom: 14px; }
  .cdfix-group-head { display: flex; align-items: center; gap: 8px; padding: 7px 12px;
    background: var(--teal-bg); border: 1px solid rgba(13,138,120,.25); border-radius: 7px;
    margin-bottom: 6px; cursor: pointer; user-select: none; }
  .cdfix-group-head:hover { filter: brightness(.97); }
  .cdfix-group-check { accent-color: var(--teal); width: 15px; height: 15px; cursor: pointer; flex-shrink: 0; }
  .cdfix-group-name { font-size: 13px; font-weight: 700; color: var(--teal-text); flex: 1;
    font-family: "SF Mono", Menlo, monospace; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; min-width: 0; }
  .cdfix-group-meta { font-size: 11px; color: var(--muted); white-space: nowrap; flex-shrink: 0; }
  .cdfix-group-badge { background: var(--teal); color: #fff; font-size: 10px; font-weight: 700;
    padding: 1px 8px; border-radius: 99px; }
  .cdfix-toggle-arrow { font-size: 11px; color: var(--muted); flex-shrink: 0; transition: transform .2s; }
  .cdfix-toggle-arrow.open { transform: rotate(180deg); }

  /* ── Item card — flat 3-row layout ──────────────────────────── */
  label.cdfix-card { display: flex; gap: 10px; align-items: flex-start; padding: 9px 12px;
    border: 1px solid var(--line); border-radius: 7px; margin-bottom: 5px;
    cursor: pointer; transition: border-color .12s, background .12s; }
  label.cdfix-card:hover { border-color: var(--teal); background: rgba(13,138,120,.03); }
  label.cdfix-card input[type=checkbox] { margin-top: 2px; flex-shrink: 0; accent-color: var(--teal);
    width: 15px; height: 15px; cursor: pointer; }
  .cdfix-ci { flex: 1; min-width: 0; }                     /* info column — takes remaining width */

  /* Row 1: type badge + attribute name + "Modified only" tag */
  .cdfix-r1 { display: flex; align-items: center; gap: 6px; flex-wrap: wrap; margin-bottom: 4px; }
  .cdfix-tbadge { font-size: 10px; font-weight: 700; padding: 2px 7px; border-radius: 4px;
    text-transform: uppercase; letter-spacing: .04em; flex-shrink: 0; }
  .cdfix-tbadge-m { background: rgba(13,138,120,.12); color: var(--teal-text); border: 1px solid rgba(13,138,120,.3); }
  .cdfix-tbadge-n { background: rgba(124,79,208,.1);  color: var(--purple);    border: 1px solid rgba(124,79,208,.25); }
  .cdfix-cname { font-family: "SF Mono", Menlo, monospace; font-size: 13px; font-weight: 700;
    color: var(--text); word-break: break-word; }
  .cdfix-modtag { font-size: 10px; padding: 2px 7px; border-radius: 4px; flex-shrink: 0;
    background: rgba(47,111,237,.1); color: var(--accent); border: 1px solid rgba(47,111,237,.25); font-weight: 600; }
  .cdfix-warntag { font-size: 10px; padding: 2px 7px; border-radius: 4px; flex-shrink: 0;
    background: #b45309; color: #fff; }

  /* Row 2: location breadcrumb */
  .cdfix-r2 { display: flex; align-items: center; gap: 3px; flex-wrap: wrap; margin-bottom: 3px; }
  .cdfix-rlabel { font-size: 11px; color: var(--muted); flex-shrink: 0; margin-right: 2px; }
  .cdfix-seg { font-size: 11px; font-family: "SF Mono", Menlo, monospace; color: var(--text);
    background: var(--gutter); padding: 1px 6px; border-radius: 3px; }
  .cdfix-sep { font-size: 11px; color: var(--muted); opacity: .55; }

  /* Row 3: field / hydration / role */
  .cdfix-r3 { display: flex; align-items: center; gap: 5px; flex-wrap: wrap; }
  .cdfix-fval { font-size: 11px; font-family: "SF Mono", Menlo, monospace;
    padding: 1px 7px; border-radius: 4px; word-break: break-all; }
  .cdfix-fval-sf  { background: var(--teal-bg); color: var(--teal-text); }
  .cdfix-fval-hyd { background: rgba(124,79,208,.08); color: var(--purple); }
  .cdfix-fval-role { color: var(--muted); font-style: italic; font-size: 11px; }
  /* ── Fixed floating scroll buttons ────────────────────────────── */
  .fab { position: fixed; z-index: 99999; width: 46px; height: 46px; border-radius: 50%;
    border: none; cursor: pointer; display: flex; align-items: center; justify-content: center;
    box-shadow: 0 4px 14px rgba(0,0,0,.30); transition: transform .15s, box-shadow .15s;
    bottom: 26px; }
  .fab:hover { transform: scale(1.13); box-shadow: 0 6px 20px rgba(0,0,0,.40); }
  .fab-up   { right: 26px; background: var(--teal); color: #fff; }
  .fab-down { left:  26px; background: var(--panel); color: var(--teal);
    border: 2px solid var(--teal); }
</style>
</head>
<body>
  <div class="wrap">
    <div class="topbar">
      <div>
        <h1>Salesforce Metadata XML Tool</h1>
        <p class="sub">Compare, merge, and clean up metadata XML — permission sets, context definitions, and more. Paste your XML, pick an operation, no terminal needed.</p>
        <p class="credit">Made with 💙 by <strong><a href="https://www.linkedin.com/in/mrpancholi/" target="_blank" rel="noopener noreferrer">Mritunjaya Pancholi</a></strong></p>
      </div>
      <button class="ghost" id="themeBtn" title="Toggle day/night">Night mode</button>
    </div>

    <div class="tabs" id="tabs">
      <button class="tab active" data-mode="compare">Compare</button>
      <button class="tab" data-mode="merge">Merge</button>
      <button class="tab" data-mode="dedup">Deduplicate</button>
      <button class="tab" data-mode="cdfix">Context Definition Fix</button>
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
          <div class="xpane-body"><div class="ln-gutter" id="ln-cmpA"></div><textarea id="cmpA" placeholder="Paste the first XML here…" spellcheck="false"></textarea></div>
        </div>
        <div class="xpane">
          <div class="xpane-head">
            <span class="ttl">Right XML</span>
            <div class="mini"><button class="ghost" data-clear="cmpB">Clear</button></div>
          </div>
          <div class="xpane-body"><div class="ln-gutter" id="ln-cmpB"></div><textarea id="cmpB" placeholder="Paste the second XML here…" spellcheck="false"></textarea></div>
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
          <div class="xpane-body"><div class="ln-gutter" id="ln-mrgA"></div><textarea id="mrgA" placeholder="Paste the BASE XML here (the authoritative version to build on)…" spellcheck="false"></textarea></div>
        </div>
        <div class="xpane">
          <div class="xpane-head">
            <span class="ttl">Pane 2 — Modified XML <span class="badge base hidden" id="badge2">BASE</span></span>
            <div class="mini"><button class="ghost" data-clear="mrgB">Clear</button></div>
          </div>
          <div class="xpane-body"><div class="ln-gutter" id="ln-mrgB"></div><textarea id="mrgB" placeholder="Paste the MODIFIED XML here (the changes to layer on)…" spellcheck="false"></textarea></div>
        </div>
        <div class="xpane">
          <div class="xpane-head">
            <span class="ttl">Merged result <span class="badge out">OUTPUT</span></span>
            <div class="mini">
              <button class="ghost" id="mergeCopyBtn">Copy</button>
              <button class="ghost" id="mergeDownloadBtn">Download</button>
            </div>
          </div>
          <div class="xpane-body"><div class="ln-gutter" id="ln-mrgOut"></div><textarea id="mrgOut" placeholder="The merged XML will appear here. Use Copy to grab it in one click." spellcheck="false" readonly></textarea></div>
        </div>
      </div>

      <div class="status" id="mrgStatus"></div>

      <!-- Duplicate-entry warning banner — shown when input files have duplicates -->
      <div class="dup-warn" id="mrgDupWarn">
        <div class="dup-warn-head">
          <span>
            <svg width="16" height="16" viewBox="0 0 20 20" fill="currentColor" style="vertical-align:-3px;margin-right:6px"><path fill-rule="evenodd" d="M8.485 2.495c.673-1.167 2.357-1.167 3.03 0l6.28 10.875c.673 1.167-.17 2.625-1.516 2.625H3.72c-1.347 0-2.189-1.458-1.515-2.625L8.485 2.495zM10 5a.75.75 0 01.75.75v3.5a.75.75 0 01-1.5 0v-3.5A.75.75 0 0110 5zm0 9a1 1 0 100-2 1 1 0 000 2z" clip-rule="evenodd"/></svg>
            Duplicate entries detected in input files — some entries were collapsed in the merged output
          </span>
          <button class="ghost" id="mrgDupToggle" style="font-size:12px;padding:3px 10px;color:#fff;border-color:rgba(255,255,255,.4);">Show details</button>
        </div>
        <div class="dup-warn-body" id="mrgDupBody" style="display:none">
          <strong>What happened:</strong> Your input files contain elements with the same identity key
          (e.g. the same <code>field</code>, <code>object</code>, or <code>apexClass</code> listed more than once).
          The merge engine keeps only the <em>last</em> occurrence of each duplicate, so the merged output
          has fewer entries than your inputs.
          <br><br>
          <strong>How to fix:</strong> Switch to the <strong>Deduplicate</strong> tab, clean each input file,
          then re-merge the cleaned versions.
          <ul class="dup-list" id="mrgDupList"></ul>
        </div>
      </div>

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
          <div class="xpane-body"><div class="ln-gutter" id="ln-dedIn"></div><textarea id="dedIn" placeholder="Paste a Permission Set (or Profile) XML here…" spellcheck="false"></textarea></div>
        </div>
        <div class="xpane">
          <div class="xpane-head">
            <span class="ttl">Cleaned result <span class="badge out">OUTPUT</span></span>
            <div class="mini">
              <button class="ghost" id="dedupCopyBtn">Copy</button>
              <button class="ghost" id="dedupDownloadBtn">Download</button>
            </div>
          </div>
          <div class="xpane-body"><div class="ln-gutter" id="ln-dedOut"></div><textarea id="dedOut" placeholder="The deduplicated, sorted XML will appear here." spellcheck="false" readonly></textarea></div>
        </div>
      </div>
      <div class="status" id="dedStatus"></div>
      <div class="report" id="dedReport">
        <h3>Deduplication report</h3>
        <pre id="dedReportBody"></pre>
      </div>
    </div>

    <!-- ====================== CONTEXT DEFINITION FIX ================== -->
    <div class="panel hidden" id="view-cdfix">

      <!-- Step 1: Paste XMLs -->
      <div class="cdfix-step">
        <div class="cdfix-step-head">
          <span class="cdfix-step-num">1</span>
          <div>
            <div class="cdfix-step-title">Paste your Base and Modified Context Definitions</div>
            <div class="cdfix-step-sub">Base = the org you are deploying TO (e.g. QA). Modified = the org with your new fields (e.g. dev sandbox).</div>
          </div>
        </div>
        <div class="panes">
          <div class="xpane">
            <div class="xpane-head">
              <span class="ttl">Base Context Definition <span class="badge base">BASE</span></span>
              <div class="mini">
                <button class="ghost" id="cdfBasePasteBtn">Paste</button>
                <button class="ghost" id="cdfBaseCopyBtn">Copy</button>
                <button class="ghost" data-clear="cdfBase">Clear</button>
              </div>
            </div>
            <div class="xpane-body"><div class="ln-gutter" id="ln-cdfBase"></div><textarea id="cdfBase" placeholder="Paste the BASE Context Definition XML here (e.g. QA org — the authoritative version; nothing from here will be deleted)…" spellcheck="false"></textarea></div>
          </div>
          <div class="xpane">
            <div class="xpane-head">
              <span class="ttl">Modified Context Definition</span>
              <div class="mini">
                <button class="ghost" id="cdfModPasteBtn">Paste</button>
                <button class="ghost" id="cdfModCopyBtn">Copy</button>
                <button class="ghost" data-clear="cdfMod">Clear</button>
              </div>
            </div>
            <div class="xpane-body"><div class="ln-gutter" id="ln-cdfMod"></div><textarea id="cdfMod" placeholder="Paste the MODIFIED Context Definition XML here (e.g. dev sandbox — contains your new field mappings)…" spellcheck="false"></textarea></div>
          </div>
        </div>
      </div>

      <!-- Step 2 trigger -->
      <div class="cdfix-step" style="margin-top:14px;">
        <div class="cdfix-step-head">
          <span class="cdfix-step-num">2</span>
          <div>
            <div class="cdfix-step-title">Discover what Modified adds beyond Base</div>
            <div class="cdfix-step-sub">Finds every contextAttributeMapping and contextAttribute present in Modified but absent in Base.</div>
          </div>
          <button class="action b-cdfix" id="cdfAnalyzeBtn" style="margin-left:auto;">Analyze Differences</button>
        </div>
        <div class="status" id="cdfAnalyzeStatus"></div>
      </div>

      <!-- Step 3: Selection panel (shown after analyze) -->
      <div class="cdfix-select" id="cdfSelectPanel">
        <div class="cdfix-sel-head">
          <span id="cdfSelHeadText">Select fields to include</span>
          <span id="cdfSelCount" style="font-size:12px;opacity:.85;"></span>
        </div>
        <div class="cdfix-sel-body">
          <div class="cdfix-sel-actions" id="cdfSelActions">
            <button class="ghost" id="cdfSelAll">Select all</button>
            <button class="ghost" id="cdfSelNone">Deselect all</button>
          </div>
          <div id="cdfFieldList"></div>
        </div>
      </div>

      <!-- Step 4: Build -->
      <div class="cdfix-step hidden" id="cdfBuildStep">
        <div class="cdfix-step-head">
          <span class="cdfix-step-num">3</span>
          <div>
            <div class="cdfix-step-title">Build the patched Context Definition</div>
            <div class="cdfix-step-sub">Applies only the selected field additions on top of Base. Everything else stays exactly as it is in Base.</div>
          </div>
          <button class="action b-cdfix" id="cdfBuildBtn" style="margin-left:auto;">Build Context Definition</button>
        </div>

        <div class="panes" style="margin-top:14px;">
          <div class="xpane">
            <div class="xpane-head">
              <span class="ttl">Patched result <span class="badge out">OUTPUT</span></span>
              <div class="mini">
                <button class="ghost" id="cdfCopyBtn">Copy</button>
                <button class="ghost" id="cdfDownloadBtn">Download</button>
                <button class="ghost" data-clear="cdfOut">Clear</button>
              </div>
            </div>
            <div class="xpane-body"><div class="ln-gutter" id="ln-cdfOut"></div><textarea id="cdfOut" placeholder="The patched Context Definition will appear here." spellcheck="false" readonly></textarea></div>
          </div>
        </div>

        <div class="status" id="cdfBuildStatus"></div>
        <div class="report" id="cdfReport">
          <h3>Apply report</h3>
          <pre id="cdfReportBody"></pre>
        </div>

      </div>

    </div>
  </div>

<script>
  const $ = (id) => document.getElementById(id);

  // ── Line-number gutter ─────────────────────────────────────────────────────
  const _lnRefresh = {};
  function initLN(taId) {
    const ta = $(taId);
    const gut = $('ln-' + taId);
    function refresh() {
      const lines = ta.value ? ta.value.split('\n').length : 1;
      let s = '';
      for (let i = 1; i <= lines; i++) s += i + '\n';
      gut.textContent = s;
      gut.scrollTop = ta.scrollTop;
    }
    ta.addEventListener('input', refresh);
    ta.addEventListener('scroll', () => { gut.scrollTop = ta.scrollTop; });
    refresh();
    _lnRefresh[taId] = refresh;
  }
  ['cmpA','cmpB','mrgA','mrgB','mrgOut','dedIn','dedOut','cdfBase','cdfMod','cdfOut'].forEach(initLN);
  // ──────────────────────────────────────────────────────────────────────────

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
  const views = { compare: $("view-compare"), merge: $("view-merge"), dedup: $("view-dedup"), cdfix: $("view-cdfix") };
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
  document.querySelectorAll("[data-clear]").forEach(b => b.onclick = () => {
    const id = b.dataset.clear;
    $(id).value = "";    // works on both editable and readonly textareas when set via JS
    if (_lnRefresh[id]) _lnRefresh[id]();
  });

  async function pasteInto(taId) {
    const ta = $(taId);
    if (!ta) return;
    try {
      const text = await navigator.clipboard.readText();
      ta.value = text;
      if (_lnRefresh[taId]) _lnRefresh[taId]();
    } catch (e) {
      ta.focus();
      alert("Clipboard read blocked — click inside the text area and use Ctrl/Cmd+V to paste.");
    }
  }

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
  const mrgDupWarn = $("mrgDupWarn"), mrgDupBody = $("mrgDupBody");
  const mrgDupList = $("mrgDupList"), mrgDupToggle = $("mrgDupToggle");
  const swapBtn = $("swapBtn");

  // Toggle duplicate details panel
  mrgDupToggle.onclick = () => {
    const open = mrgDupBody.style.display !== 'none';
    mrgDupBody.style.display = open ? 'none' : 'block';
    mrgDupToggle.textContent = open ? 'Show details' : 'Hide details';
  };

  function updateBadges() {
    const leftIsBase = baseSelect.value === "left";
    badge1.classList.toggle("hidden", !leftIsBase);
    badge2.classList.toggle("hidden", leftIsBase);
  }
  baseSelect.onchange = updateBadges;
  updateBadges();

  swapBtn.onclick = () => {
    const t = mrgA.value; mrgA.value = mrgB.value; mrgB.value = t;
    _lnRefresh.mrgA(); _lnRefresh.mrgB();
  };

  mergeBtn.onclick = async () => {
    if (!mrgA.value.trim() || !mrgB.value.trim()) { setStatus(mrgStatus, "err", "Paste XML in both Base and Modified panes first."); return; }
    const leftIsBase = baseSelect.value === "left";
    const base = leftIsBase ? mrgA.value : mrgB.value;
    const override = leftIsBase ? mrgB.value : mrgA.value;
    busy(mergeBtn, "Merging…");
    mrgReport.classList.remove("show");
    mrgDupWarn.classList.remove("show");
    const data = await postJSON("/api/merge", { base, override });
    if (data.ok) {
      mrgOut.value = data.merged; _lnRefresh.mrgOut();
      showReport(mrgReport, mrgReportBody, data.report);

      // ── Duplicate warning banner ──
      const dups = data.duplicates || [];
      if (dups.length) {
        // Parse each warning line into labelled list items
        mrgDupList.innerHTML = dups.map(w => {
          // Format: "  [Base] <tag> 'key' appears Nx — ..."
          const badgeHtml = w.includes('[Base]')
            ? '<span class="dup-badge base">Base</span>'
            : '<span class="dup-badge mod">Modified</span>';
          const text = w.replace(/\s*\[(Base|Modified)\]\s*/, '').trim();
          return `<li>${badgeHtml}${esc(text)}</li>`;
        }).join('');
        mrgDupBody.style.display = 'none';
        mrgDupToggle.textContent = 'Show details';
        mrgDupWarn.classList.add("show");
      }

      if (data.warnings && data.warnings.length)
        setStatus(mrgStatus, "info", `Merged <${data.rootType}> with ${data.warnings.length} validation warning(s) — see report below.`);
      else if (dups.length)
        setStatus(mrgStatus, "ok", `Merged <${data.rootType}>. ⚠ ${dups.length} duplicate entry/entries in inputs were collapsed — see warning above.`);
      else
        setStatus(mrgStatus, "ok", `Merged <${data.rootType}> successfully. Use Copy to grab the result.`);
    } else {
      mrgOut.value = ""; _lnRefresh.mrgOut();
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
      dedOut.value = data.result; _lnRefresh.dedOut();
      showReport(dedReport, dedReportBody, data.report);
      setStatus(dedStatus, "ok", `Done — ${data.removed} duplicate entr${data.removed === 1 ? "y" : "ies"} removed.`);
    } else {
      dedOut.value = ""; _lnRefresh.dedOut();
      setStatus(dedStatus, "err", data.log || "Deduplication failed.");
    }
    idle(dedupBtn);
  };
  $("dedupCopyBtn").onclick = (e) => copyFrom(dedOut, e.target);
  $("dedupDownloadBtn").onclick = () => download(dedOut, "deduplicated.xml");

  // ====================== CONTEXT DEFINITION FIX =========================
  const cdfBase         = $("cdfBase"),  cdfMod    = $("cdfMod"), cdfOut = $("cdfOut");
  const cdfAnalyzeBtn   = $("cdfAnalyzeBtn"),  cdfBuildBtn = $("cdfBuildBtn");
  const cdfAnalyzeStatus = $("cdfAnalyzeStatus"), cdfBuildStatus = $("cdfBuildStatus");
  const cdfSelectPanel  = $("cdfSelectPanel"),   cdfBuildStep = $("cdfBuildStep");
  const cdfFieldList    = $("cdfFieldList"),      cdfSelCount  = $("cdfSelCount");
  const cdfReport       = $("cdfReport"),         cdfReportBody = $("cdfReportBody");
  const cdfSelHeadText  = $("cdfSelHeadText");

  let _cdfItems = [];   // raw analysis results stored between steps

  // ── helpers ─────────────────────────────────────────────────────────────
  function cdfUpdateSelCount() {
    const total   = _cdfItems.length;
    const checked = document.querySelectorAll('#cdfFieldList input[type=checkbox][data-item]:checked').length;
    cdfSelCount.textContent = `${checked} / ${total} selected`;
  }

  function cdfRenderItems(items) {
    _cdfItems = items;

    // Build groups
    const groups = {};
    for (const it of items) (groups[it.group] = groups[it.group] || []).push(it);

    // Legend
    const nM = items.filter(i => i.type === 'mapping').length;
    const nN = items.filter(i => i.type === 'nodeAttr').length;
    const actBar = $('cdfSelActions');
    if (actBar) {
      const old = actBar.querySelector('.cdfix-legend');
      if (old) old.remove();
      actBar.insertAdjacentHTML('beforeend',
        `<div class="cdfix-legend">` +
        (nM ? `<span class="cdfix-legend-item"><span class="cdfix-legend-dot" style="background:rgba(13,138,120,.55)"></span>${nM} mapping${nM>1?'s':''}</span>` : '') +
        (nN ? `<span class="cdfix-legend-item"><span class="cdfix-legend-dot" style="background:rgba(124,79,208,.55)"></span>${nN} node attr${nN>1?'s':''}</span>` : '') +
        `</div>`);
    }

    let html = '';
    for (const [grpKey, grpItems] of Object.entries(groups)) {
      const grpId = 'grp_' + grpKey.replace(/\W/g, '_');
      const mC = grpItems.filter(i => i.type==='mapping').length;
      const nC = grpItems.filter(i => i.type==='nodeAttr').length;
      const meta = [mC && `${mC} mapping${mC>1?'s':''}`, nC && `${nC} node attr${nC>1?'s':''}`].filter(Boolean).join(' · ');

      // ── Group header ────────────────────────────────────────────────────────
      html += `<div class="cdfix-group">` +
        `<div class="cdfix-group-head" onclick="cdfToggleGroup('${grpId}')">` +
          `<input type="checkbox" class="cdfix-group-check" id="${grpId}_hdr"` +
          ` onclick="event.stopPropagation();cdfGroupHeaderClick('${grpId}')" checked />` +
          `<span class="cdfix-group-name" title="${esc(grpKey)}">${esc(grpKey)}</span>` +
          `<span class="cdfix-group-meta">${esc(meta)}&nbsp;<span class="cdfix-group-badge">${grpItems.length}</span></span>` +
          `<span class="cdfix-toggle-arrow open" id="${grpId}_arrow">▼</span>` +
        `</div>` +
        `<div id="${grpId}">`;

      // ── Item cards ──────────────────────────────────────────────────────────
      for (const it of grpItems) {
        const sid  = it.id.replace(/\W/g, '_');
        const isM  = it.type === 'mapping';
        const name = esc(it.attrName || it.attrTitle || '');

        // Row 1 pieces
        const tbadge = isM
          ? `<span class="cdfix-tbadge cdfix-tbadge-m">Mapping</span>`
          : `<span class="cdfix-tbadge cdfix-tbadge-n">Node Attr</span>`;
        const warn = it.missingParent
          ? `<span class="cdfix-warntag" title="Parent location not found in Base — may fail to apply">⚠ parent missing</span>` : '';

        // Row 2: location breadcrumb
        const segs = isM
          ? [it.mappingTitle, it.contextNode, it.object]
          : ['contextNodes', it.nodeName];
        const bc = segs.map((s, i) =>
          `<span class="cdfix-seg">${esc(s)}</span>` +
          (i < segs.length-1 ? `<span class="cdfix-sep">›</span>` : '')
        ).join('');

        // Row 3: field / hydration / role
        let r3 = '';
        if (isM && it.fieldInfo) {
          if (it.fieldInfo.startsWith('hydration ref:')) {
            const ref = esc(it.fieldInfo.replace('hydration ref:','').trim());
            r3 = `<div class="cdfix-r3"><span class="cdfix-rlabel">Hydration</span><span class="cdfix-fval cdfix-fval-hyd">${ref}</span></div>`;
          } else {
            r3 = `<div class="cdfix-r3"><span class="cdfix-rlabel">SF Field</span><span class="cdfix-fval cdfix-fval-sf">${esc(it.fieldInfo)}</span></div>`;
          }
        } else if (!isM) {
          r3 = `<div class="cdfix-r3"><span class="cdfix-fval-role">Declares this context attribute on the node</span></div>`;
        }

        html +=
          `<label class="cdfix-card" for="ci_${sid}">` +
            `<input type="checkbox" id="ci_${sid}" data-item="${esc(it.id)}" checked` +
            ` onchange="cdfUpdateGroupHeader('${grpId}');cdfUpdateSelCount()" />` +
            `<div class="cdfix-ci">` +
              `<div class="cdfix-r1">${tbadge}<span class="cdfix-cname">${name}</span>${warn}<span class="cdfix-modtag">Modified only</span></div>` +
              `<div class="cdfix-r2"><span class="cdfix-rlabel">Location</span>${bc}</div>` +
              r3 +
            `</div>` +
          `</label>`;
      }
      html += `</div></div>`;
    }
    cdfFieldList.innerHTML = html;
    cdfUpdateSelCount();
  }

  window.cdfToggleGroup = function(grpId) {
    const el  = $(grpId);
    const arr = $(grpId + '_arrow');
    if (!el) return;
    const hidden = el.style.display === 'none';
    el.style.display = hidden ? '' : 'none';
    if (arr) arr.classList.toggle('open', hidden);
  };
  window.cdfGroupHeaderClick = function(grpId) {
    const hdr = $(grpId + '_hdr');
    if (!hdr) return;
    const checked = hdr.checked;
    document.querySelectorAll(`#${grpId} input[data-item]`).forEach(cb => {
      cb.checked = checked;
    });
    cdfUpdateSelCount();
  };
  window.cdfUpdateGroupHeader = function(grpId) {
    const hdr   = $(grpId + '_hdr');
    const boxes = [...document.querySelectorAll(`#${grpId} input[data-item]`)];
    if (!hdr || !boxes.length) return;
    const all  = boxes.every(b => b.checked);
    const none = boxes.every(b => !b.checked);
    hdr.indeterminate = !all && !none;
    hdr.checked = all;
  };

  $("cdfSelAll").onclick = () => {
    document.querySelectorAll('#cdfFieldList input[type=checkbox]').forEach(cb => { cb.checked = true; cb.indeterminate = false; });
    cdfUpdateSelCount();
  };
  $("cdfSelNone").onclick = () => {
    document.querySelectorAll('#cdfFieldList input[type=checkbox]').forEach(cb => { cb.checked = false; cb.indeterminate = false; });
    cdfUpdateSelCount();
  };

  // ── Step 2: Analyze ──────────────────────────────────────────────────────
  cdfAnalyzeBtn.onclick = async () => {
    if (!cdfBase.value.trim() || !cdfMod.value.trim()) {
      setStatus(cdfAnalyzeStatus, "err", "Paste both Base and Modified XMLs first.");
      return;
    }
    busy(cdfAnalyzeBtn, "Analyzing…");
    cdfSelectPanel.classList.remove("show");
    cdfBuildStep.classList.add("hidden");
    cdfReport.classList.remove("show");

    const data = await postJSON("/api/cdfix/analyze", { base: cdfBase.value, modified: cdfMod.value });
    idle(cdfAnalyzeBtn);

    if (!data.ok) {
      setStatus(cdfAnalyzeStatus, "err", data.log || "Analysis failed.");
      return;
    }
    if (!data.items || data.items.length === 0) {
      setStatus(cdfAnalyzeStatus, "ok", data.summary || "No differences found.");
      return;
    }

    setStatus(cdfAnalyzeStatus, "ok", data.summary);
    cdfSelHeadText.textContent = "Step 2 — Select which field additions to include";
    cdfRenderItems(data.items);
    cdfSelectPanel.classList.add("show");
    cdfBuildStep.classList.remove("hidden");
    cdfOut.value = ""; _lnRefresh.cdfOut();
    cdfBuildStatus.className = "status";
  };

  // ── Step 3: Build ────────────────────────────────────────────────────────
  cdfBuildBtn.onclick = async () => {
    const selectedIds = [...document.querySelectorAll('#cdfFieldList input[data-item]:checked')]
      .map(cb => cb.dataset.item);
    if (!selectedIds.length) {
      setStatus(cdfBuildStatus, "err", "Select at least one field to include.");
      return;
    }
    busy(cdfBuildBtn, "Building…");
    cdfReport.classList.remove("show");

    const data = await postJSON("/api/cdfix/build", {
      base: cdfBase.value, modified: cdfMod.value, selectedIds
    });
    idle(cdfBuildBtn);

    if (!data.ok) {
      setStatus(cdfBuildStatus, "err", data.log || "Build failed.");
      return;
    }
    cdfOut.value = data.result; _lnRefresh.cdfOut();
    showReport(cdfReport, cdfReportBody, data.report);
    const errs = data.errors || 0;
    const msg = errs
      ? `Built with ${data.applied} addition(s) applied · ${errs} error(s) — see report.`
      : `Done — ${data.applied} addition(s) applied, ${data.skipped} already present. Use Copy to grab the result.`;
    setStatus(cdfBuildStatus, errs ? "info" : "ok", msg);
  };

  $("cdfCopyBtn").onclick      = (e) => copyFrom(cdfOut, e.target);
  $("cdfDownloadBtn").onclick  = () => download(cdfOut, "context-definition-patched.xml");
  $("cdfBasePasteBtn").onclick = () => pasteInto("cdfBase");
  $("cdfModPasteBtn").onclick  = () => pasteInto("cdfMod");
  $("cdfBaseCopyBtn").onclick  = (e) => copyFrom(cdfBase, e.target);
  $("cdfModCopyBtn").onclick   = (e) => copyFrom(cdfMod,  e.target);

  // ── CD Fix pane height guard — JS fallback if CSS alone isn't enough ─────────
  // Fires on every keystroke/paste (including Ctrl+V) and resets height to 300px.
  ['cdfBase','cdfMod','cdfOut'].forEach(id => {
    const ta = $(id);
    if (!ta) return;
    const cap = () => { ta.style.height = '300px'; ta.style.overflowY = 'auto'; };
    ta.addEventListener('input', cap);
    ta.addEventListener('change', cap);
  });
</script>

<!-- Fixed scroll buttons — always visible at screen corners (inline onclick = no DOM-order dependency) -->
<button class="fab fab-up"
  onclick="window.scrollTo({top:0,behavior:'smooth'})"
  title="Back to top">
  <svg width="18" height="18" viewBox="0 0 18 18" fill="none"><path d="M9 14V4M4 9l5-5 5 5" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"/></svg>
</button>
<button class="fab fab-down"
  onclick="window.scrollTo({top:document.body.scrollHeight,behavior:'smooth'})"
  title="Scroll to bottom">
  <svg width="18" height="18" viewBox="0 0 18 18" fill="none"><path d="M9 4v10M4 9l5 5 5-5" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"/></svg>
</button>

</body>
</html>"""
