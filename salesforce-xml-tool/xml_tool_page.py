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
    color-scheme: light;
    --font-sans:Inter,ui-sans-serif,system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;
    --font-mono:"SFMono-Regular",Consolas,"Liberation Mono",Menlo,monospace;
    --space-1:4px; --space-2:8px; --space-3:12px; --space-4:16px; --space-5:24px; --space-6:32px;
    --bg:#eaf3fb; --header-bg:#ffffff; --panel:#ffffff; --gutter:#f8fbfe; --input-bg:#ffffff;
    --workflow-bg:#afc0d4; --workflow-line:#d7e0ea; --workflow-text:#1b2a3a;
    --line:#d7e0ea; --text:#182536; --muted:#667589; --gutter-text:#8492a3;
    --accent:#2563eb; --accent-strong:#1d4ed8; --green:#16a34a; --red:#dc2626;
    --berry:var(--accent); --coral:var(--amber); --sage:color-mix(in srgb,var(--green) 11%,var(--panel));
    --purple:#6d4aff; --amber:#d97706; --teal:#0891b2; --on-accent:#ffffff;
    --radius:12px;
    --ok-bg:#ecfdf3; --ok-text:#167044;
    --err-bg:color-mix(in srgb, var(--red) 10%, var(--panel)); --err-text:#b4233f;
    --info-bg:#eaf2ff; --info-text:#1d4ed8;
    --chg-bg:color-mix(in srgb, var(--purple) 14%, var(--panel));
    --del-bg:color-mix(in srgb, var(--red) 12%, var(--panel));
    --ins-bg:color-mix(in srgb, var(--teal) 13%, var(--panel));
    --chg-line:var(--purple); --del-line:var(--red); --ins-line:var(--teal);
    --teal-bg:color-mix(in srgb, var(--teal) 10%, var(--panel)); --teal-text:#07657c;
    --shadow:0 2px 10px rgba(31,56,85,.06);
  }
  html[data-theme="dark"] {
    color-scheme: dark;
    --bg:#0d1622; --header-bg:#131d2a; --panel:#131d2a; --gutter:#182536; --input-bg:#101923;
    --workflow-bg:#52677f; --workflow-line:#71849a; --workflow-text:#f3f6fb;
    --line:#293449; --text:#f3f6fb; --muted:#b7c0d0; --gutter-text:#8995aa;
    --accent:#60a5fa; --accent-strong:#3b82f6; --green:#4ade80; --red:#f87171;
    --berry:var(--accent); --coral:var(--amber); --sage:color-mix(in srgb,var(--green) 13%,var(--panel));
    --purple:#a78bfa; --amber:#fbbf24; --teal:#22d3ee;
    --ok-bg:color-mix(in srgb,var(--green) 13%,var(--panel)); --ok-text:#a7f3d0;
    --err-bg:color-mix(in srgb, var(--red) 13%, var(--panel)); --err-text:#fecdd3;
    --info-bg:color-mix(in srgb, var(--accent) 13%, var(--panel)); --info-text:#d9dcff;
    --teal-bg:color-mix(in srgb, var(--teal) 12%, var(--panel)); --teal-text:#a5f3fc;
    --shadow:0 1px 2px rgba(0,0,0,.28);
  }
  * { box-sizing: border-box; }
  html,body { max-width:100%; overflow-x:hidden; }
  body {
    margin:0; font-family:var(--font-sans);
    min-height:100vh;
    background:var(--bg);
    color:var(--text); line-height:1.5;
    transition:background-color .2s ease, color .2s ease;
  }
  button,input,select,textarea { font:inherit; }
  .app-shell { min-height:100vh; display:grid; grid-template-columns:244px minmax(0,1fr); }
  .sidebar { position:sticky; top:0; height:100vh; display:flex; flex-direction:column; padding:18px 12px 14px;
    background:var(--panel); border-right:1px solid var(--line); z-index:20; }
  .brand { display:flex; align-items:center; gap:11px; padding:0 8px 26px; color:var(--text); }
  .brand-mark { width:36px; height:36px; display:grid; place-items:center; border-radius:10px;
    background:var(--accent); box-shadow:var(--shadow); }
  .brand-mark svg { width:23px; fill:var(--on-accent); }
  .brand strong,.brand small { display:block; line-height:1.2; }
  .brand strong { font-size:13px; }
  .brand small { margin-top:3px; color:var(--muted); font-size:11px; font-weight:600; }
  .side-label,.eyebrow { color:var(--muted); font-size:10px; font-weight:800; letter-spacing:.12em; text-transform:uppercase; }
  .side-label { padding:0 12px 8px; }
  .side-menu { display:grid; min-width:0; gap:5px; }
  .side-nav,.about-link { width:100%; border:0; display:flex; align-items:center; gap:10px; padding:10px 11px;
    border-radius:9px; background:transparent; color:var(--muted); text-decoration:none; font-size:13px;
    font-weight:650; text-align:left; cursor:pointer; transition:background .2s ease,color .2s ease,transform .2s ease; }
  .side-nav:hover,.about-link:hover { color:var(--text); background:var(--gutter); transform:translateX(2px); }
  .side-nav.active { color:var(--accent); background:color-mix(in srgb,var(--accent) 9%,var(--panel));
    box-shadow:inset 3px 0 0 var(--accent); }
  .nav-icon { width:21px; height:21px; display:grid; place-items:center; flex:0 0 21px; font-size:15px; }
  .nav-icon svg { width:17px; height:17px; fill:none; stroke:currentColor; stroke-width:1.8;
    stroke-linecap:round; stroke-linejoin:round; }
  .sidebar-footer { margin-top:auto; border-top:1px solid var(--line); padding-top:12px; }
  .sidebar .credit { padding:12px 12px 0; margin:0; font-size:10px; line-height:1.5; }
  .sidebar .credit a { color:var(--text); font-weight:750; text-decoration:none; }
  .sidebar .credit a:hover { color:var(--accent); }
  .linkedin-link { display:flex; align-items:center; gap:7px; margin:7px 12px 0; color:var(--accent);
    text-decoration:none; font-size:11px; font-weight:700; }
  .linkedin-link svg { width:14px; height:14px; fill:currentColor; }
  .app-main { min-width:0; }
  .wrap { width:100%; max-width:none; margin:0; padding:0 clamp(14px,2.2vw,36px) 64px; }
  .topbar { min-height:88px; display:flex; align-items:center; justify-content:space-between; gap:20px;
    padding:16px clamp(14px,2.2vw,36px) 12px; position:relative; }
  .topbar::after { display:none; }
  .topbar > * { position:relative; z-index:1; }
  h1 { font-size:clamp(25px,2.1vw,32px); letter-spacing:-.035em; margin:2px 0 4px; }
  .sub { color: var(--muted); font-size: 13px; margin: 0 0 6px; }
  .credit { color: var(--muted); font-size: 12px; margin: 0 0 20px; }
  .credit a { color: var(--accent); text-decoration: none; }
  .credit a:hover { text-decoration: underline; }
  .top-actions { display:flex; align-items:center; gap:10px; }
  .local-badge { display:inline-flex; align-items:center; gap:7px; padding:8px 11px; border:1px solid var(--line);
    border-radius:12px; background:color-mix(in srgb,var(--panel) 88%,transparent); color:var(--muted); font-size:11px; font-weight:700; }
  .theme-toggle { display:inline-flex; align-items:center; gap:8px; min-height:38px; padding:6px 9px !important; }
  .theme-label { min-width:60px; text-align:left; }
  .theme-switch { position:relative; width:34px; height:19px; flex:0 0 34px; border-radius:99px;
    background:var(--line); box-shadow:inset 0 0 0 1px color-mix(in srgb,var(--text) 8%,transparent);
    transition:background .18s ease; }
  .theme-switch::after { content:""; position:absolute; width:15px; height:15px; left:2px; top:2px;
    border-radius:50%; background:var(--panel); box-shadow:0 1px 3px rgba(15,23,42,.28);
    transition:transform .18s ease; }
  .theme-toggle.is-dark .theme-switch { background:var(--accent); }
  .theme-toggle.is-dark .theme-switch::after { transform:translateX(15px); }
  .live-dot { width:7px; height:7px; border-radius:50%; background:var(--green); box-shadow:0 0 0 4px color-mix(in srgb,var(--green) 14%,transparent); }
  .panel { background:var(--panel); border:1px solid var(--line); border-radius:var(--radius);
    padding:clamp(14px,1.5vw,24px); box-shadow:var(--shadow); }
  .section-head { display:flex; align-items:flex-start; justify-content:space-between; gap:14px;
    padding-bottom:16px; margin-bottom:18px; border-bottom:1px solid var(--line); }
  .section-title { display:flex; align-items:flex-start; gap:11px; min-width:0; }
  .step-dot { width:27px; height:27px; flex:0 0 27px; display:grid; place-items:center; border-radius:8px;
    background:var(--accent); color:var(--on-accent);
    font-size:12px; font-weight:800; box-shadow:none; }
  .section-title h2 { margin:0; color:var(--text); font-size:15px; letter-spacing:-.01em; }
  .section-title p { margin:3px 0 0; color:var(--muted); font-size:12px; }

  /* Operation tabs */
  .tabs { display:flex; width:100%; gap:4px; background:transparent; border:0;
    border-bottom:1px solid var(--line); border-radius:0; padding:0; margin-bottom:16px; flex-wrap:wrap; }
  .tab { border: none; border-bottom:2px solid transparent; background:transparent; color:var(--muted);
    font-weight:650; font-size:14px; padding:10px 14px; border-radius:0; margin-bottom:-1px;
    cursor:pointer; transition:background .16s ease,color .16s ease,border-color .16s ease; }
  .tab:hover { background:color-mix(in srgb,var(--accent) 6%,transparent); color:var(--text); }
  .tab.active { background:transparent; color:var(--accent); border-bottom-color:var(--accent); box-shadow:none; }

  label { display: block; font-size: 12px; color: var(--muted); margin-bottom: 6px;
    text-transform: uppercase; letter-spacing: .04em; }
  select, input, textarea {
    width: 100%; background: var(--input-bg); color: var(--text); border: 1px solid var(--line);
    border-radius:14px; padding:10px 13px; font-size:14px; outline:none;
    transition:border-color .16s ease,box-shadow .16s ease,background .16s ease;
  }
  select:focus, input:focus, textarea:focus { border-color:var(--accent); box-shadow:0 0 0 4px color-mix(in srgb,var(--accent) 16%,transparent); }
  .controls { display: flex; gap: 14px; flex-wrap: wrap; align-items: flex-end; margin-bottom: 16px; }
  .controls .field { flex:0 1 280px; max-width:100%; }
  .controls label { margin-bottom: 6px; }
  .grow { flex: 1 1 auto; }

  button { font-family:inherit; }
  .btn-icon { width:17px; height:17px; flex:0 0 17px; fill:none; stroke:currentColor;
    stroke-width:2; stroke-linecap:round; stroke-linejoin:round; vertical-align:-3px; }
  button .btn-icon { margin-right:6px; }
  .tab .btn-icon,.filter-chip .btn-icon { width:15px; height:15px; margin-right:6px; }
  button.action { min-height:44px; border:none; border-radius:9px; padding:10px 22px; font-size:14px; font-weight:700;
    cursor:pointer; color:var(--on-accent); box-shadow:0 1px 2px color-mix(in srgb,var(--accent) 22%,transparent);
    transition:transform .14s ease,filter .14s ease,box-shadow .14s ease; }
  button.action:hover:not(:disabled) { transform:translateY(-1px); filter:brightness(1.08) saturate(1.08); }
  button.action:active:not(:disabled) { transform:translateY(1px) scale(.97); filter:brightness(.92) saturate(1.2); }
  button.action:disabled { opacity: .5; cursor: not-allowed; }
  .b-compare,.b-cdfix { background:var(--accent); }
  .b-merge { background:var(--green); }
  .b-dedup { background:var(--purple); }
  .ghost { background:var(--panel); border:1px solid var(--line); color:var(--text);
    font-weight:650; border-radius:8px; padding:8px 14px; font-size:13px; cursor:pointer;
    transition:transform .14s ease,background .14s ease,border-color .14s ease,color .14s ease,box-shadow .14s ease; }
  .ghost:hover { background:color-mix(in srgb,var(--accent) 9%,var(--panel)); border-color:var(--accent); color:var(--accent); }
  .ghost:active { transform:scale(.96); background:var(--accent); border-color:var(--accent); color:var(--on-accent); }
  button:focus-visible { outline:3px solid color-mix(in srgb,var(--accent) 35%,transparent); outline-offset:3px; }

  /* Editable code pane (paste areas) */
  .panes { display:grid; grid-template-columns:repeat(auto-fit,minmax(min(360px,100%),1fr)); gap:14px; align-items:stretch; }
  .xpane { min-width:0; border:1px solid var(--line); border-radius:11px;
    overflow:hidden; display:flex; flex-direction:column; background:var(--panel);
    transition:border-color .16s ease,box-shadow .16s ease; }
  .xpane:focus-within { border-color:var(--accent); box-shadow:0 0 0 3px color-mix(in srgb,var(--accent) 10%,transparent); }
  .xpane-head { display:flex; align-items:center; justify-content:space-between; gap:8px;
    padding:10px 13px; border-bottom:1px solid var(--line); background:var(--gutter); }
  .xpane-head .ttl { font-size:12px; font-weight:700; letter-spacing:0; text-transform:none;
    color:var(--muted); white-space:nowrap; }
  .badge { font-size:10px; font-weight:700; padding:2px 8px; border-radius:99px; color:var(--on-accent); }
  .badge.base { background: var(--green); }
  .badge.out { background: var(--accent); }
  .badge.modified { background:var(--purple); }
  /* Line-numbered editor body */
  .xpane-body { display: flex; min-height: 360px; resize: vertical; overflow: hidden; }
  /* CD Fix panes — hard-capped 340 px with virtualized line-number gutters.
     !important needed because the base .xpane-body min-height:420px and textarea flex:1
     otherwise override these at runtime when large content is pasted. */
  #view-cdfix .xpane-body {
    min-height: 0   !important;
    height: 340px   !important;
    max-height: 340px !important;
    overflow: hidden !important;
    resize: vertical;
  }
  /* Gutter re-enabled: height is constrained by the parent's height:340px !important,
     so its 32k-line content overflows internally and is clipped — page stays compact. */
  #view-cdfix .ln-gutter { overflow-y: hidden !important; }
  #view-cdfix .xpane textarea {
    flex: none   !important;
    width: calc(100% - 52px) !important;
    height: 340px !important;
    max-height: 340px !important;
    overflow-y: auto !important;
    resize: none !important;
  }
  .ln-gutter {
    position:relative; display:block; flex-shrink:0; width:52px; overflow:hidden;
    background: var(--gutter); border-right: 1px solid var(--line);
    font-family: "SF Mono", Menlo, Consolas, monospace; font-size: 12.5px; line-height: 19px;
    padding:0; text-align:right;
    color: var(--gutter-text); user-select: none; white-space: pre;
  }
  .ln-inner { position:absolute; top:10px; right:9px; white-space:pre; will-change:transform; }
  .xpane textarea {
    flex: 1; border: none; border-radius: 0; resize: none; outline: none;
    font-family: "SF Mono", Menlo, Consolas, monospace; font-size: 12.5px; line-height: 19px;
    white-space: pre; tab-size: 2; background: var(--input-bg);
    padding: 8px; overflow: auto;
  }
  .xpane textarea:focus { border: none; }
  .xpane textarea[readonly] { background: var(--gutter); }
  .editor-status { min-height:31px; display:flex; align-items:center; gap:10px; padding:6px 11px;
    border-top:1px solid var(--line); background:var(--gutter); color:var(--muted);
    font-family:Inter,-apple-system,sans-serif; font-size:10px; font-weight:650; }
  .editor-status .format { padding:2px 6px; border:1px solid var(--line); border-radius:6px; color:var(--text); }
  .editor-status .valid { margin-left:auto; color:var(--green); }
  .editor-status .invalid { margin-left:auto; color:var(--red); }
  .editor-status .waiting { margin-left:auto; color:var(--muted); }
  .editor-status .btn-icon { width:14px; height:14px; margin-right:4px; vertical-align:-2px; }
  .mini { display:flex; justify-content:flex-end; gap:9px; flex-wrap:wrap; }
  .mini .ghost { padding:5px 11px; font-size:12px; }

  .status { margin-top:16px; font-size:13px; padding:13px 16px; border-radius:14px; display:none;
    white-space: pre-wrap; font-family: "SF Mono", Menlo, monospace; }
  .status.show { display: block; }
  .status.ok::before { content:"✓"; width:19px; height:19px; flex:0 0 19px; display:grid; place-items:center;
    border-radius:50%; background:var(--green); color:var(--on-accent); font-size:12px; font-weight:850; }
  .status.ok { background: var(--ok-bg); border: 1px solid var(--green); color: var(--ok-text); }
  .status.err { background: var(--err-bg); border: 1px solid var(--red); color: var(--err-text); }
  .status.info { background: var(--info-bg); border: 1px solid var(--accent); color: var(--info-text); }
  .dup-warn { display:none; margin-top:14px; border-radius:16px; overflow:hidden;
    border:1px solid var(--amber); }
  .dup-warn.show { display: block; }
  .dup-warn-head { display: flex; align-items: center; justify-content: space-between; gap: 10px;
    background:var(--amber); color:var(--on-accent); padding:11px 15px; font-size:13px; font-weight:700; }
  .dup-warn-head svg { flex-shrink: 0; }
  .dup-warn-head .ghost { background:transparent; color:var(--on-accent);
    border-color:color-mix(in srgb,var(--on-accent) 45%,transparent); }
  .dup-warn-head .ghost:hover { background:color-mix(in srgb,var(--on-accent) 16%,transparent);
    border-color:var(--on-accent); color:var(--on-accent); }
  .dup-warn-body { background:color-mix(in srgb,var(--amber) 10%,var(--panel)); color:var(--text);
    padding:13px 15px; font-size:13px; line-height:1.6; }
  .dup-list { margin:8px 0 0; padding:9px 12px; background:color-mix(in srgb,var(--amber) 8%,var(--gutter)); border-radius:10px;
    font-family: "SF Mono", Menlo, monospace; font-size: 12px; max-height: 180px; overflow-y: auto; }
  .dup-list li { margin: 2px 0; list-style: none; padding-left: 1.2em; text-indent: -1.2em; }
  .dup-badge { display: inline-block; font-size: 10px; font-weight: 700; padding: 1px 6px;
    border-radius: 99px; margin-right: 4px; }
  .dup-badge.base { background:var(--green); color:var(--on-accent); }
  .dup-badge.mod  { background:var(--accent); color:var(--on-accent); }
  .report { margin-top: 16px; display: none; }
  .report.show { display: block; }
  .report pre { background: var(--gutter); border: 1px solid var(--line); border-radius: 14px;
    padding:14px; overflow:auto; max-height:260px; font-family:"JetBrains Mono","SF Mono",Menlo,monospace;
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
  .legend i { width:14px; height:14px; border-radius:4px; margin-right:6px; display:inline-flex;
    align-items:center; justify-content:center; font-size:10px; font-weight:700; color:var(--text); }
  .lg-chg { background: var(--chg-bg); border: 1px solid var(--chg-line); }
  .lg-del { background: var(--del-bg); border: 1px solid var(--del-line); }
  .lg-ins { background: var(--ins-bg); border: 1px solid var(--ins-line); }
  .diff-panes { display: flex; gap: 12px; align-items: stretch; }
  .pane { flex:1; min-width:0; border:1px solid var(--line); border-radius:16px; overflow:hidden; display:flex; flex-direction:column; }
  .pane-title { padding: 8px 12px; font-size: 12px; font-weight: 600; color: var(--muted); border-bottom: 1px solid var(--line); background: var(--gutter); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  .pane-scroll { overflow: auto; max-height: 620px; }
  table.pane-table { border-collapse: collapse; width: 100%; font-family: "SF Mono", Menlo, Consolas, monospace; font-size: 12.5px; }
  .pane-table td { padding:3px 12px; vertical-align:top; white-space:pre; }
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
    color:var(--on-accent); font-size:12px; font-weight:700; display:inline-flex; align-items:center; justify-content:center; flex-shrink:0; }
  .cdfix-step-title { font-size: 13px; font-weight: 700; color: var(--text); }
  .cdfix-step-sub { font-size: 12px; color: var(--muted); margin-top: 2px; }
  .cdf-editor-grid { grid-template-columns:minmax(0,1fr) 78px minmax(0,1fr); align-items:center; }
  .cdf-diff-indicator { display:grid; justify-items:stretch; align-content:center; gap:4px; min-height:190px;
    padding:7px 5px; border:1px solid var(--line); border-radius:9px; background:var(--gutter); color:var(--muted); }
  .cdf-diff-arrow { width:32px; height:32px; display:grid; place-items:center; border:1px solid var(--line);
    border-radius:8px; background:var(--panel); color:var(--accent); font-size:17px; box-shadow:none; justify-self:center; }
  .cdf-diff-arrow svg { width:15px; height:15px; fill:none; stroke:currentColor; stroke-width:2;
    stroke-linecap:round; stroke-linejoin:round; }
  .cdf-rail-total { text-align:center; padding-bottom:6px; border-bottom:1px solid var(--line); }
  .cdf-diff-indicator strong { display:block; color:var(--text); text-align:center; font-size:22px; line-height:1.1; }
  .cdf-diff-indicator small { display:block; margin-top:3px; font-size:9px; font-weight:750;
    letter-spacing:.045em; text-transform:uppercase; text-align:center; }
  .cdf-rail-metric { display:grid; grid-template-columns:14px minmax(0,1fr); column-gap:4px; align-items:center;
    padding:4px 2px; border-radius:6px; }
  .cdf-rail-icon { width:14px; height:14px; display:grid; place-items:center; color:var(--accent);
    font-size:13px; font-weight:850; line-height:1; }
  .cdf-rail-icon svg { width:13px; height:13px; fill:none; stroke:currentColor; stroke-width:2; }
  .cdf-rail-metric.added .cdf-rail-icon { color:var(--green); }
  .cdf-rail-metric.updated .cdf-rail-icon { color:var(--amber); }
  .cdf-rail-metric b { color:var(--text); font-size:13px; line-height:1; }
  .cdf-rail-metric span:last-child { grid-column:2; color:var(--muted); font-size:9px; line-height:1.15; }
  .cdf-diff-indicator.has-diffs .cdf-diff-arrow { border-color:var(--accent);
    box-shadow:0 0 0 4px color-mix(in srgb,var(--accent) 10%,transparent); }

  /* ── Bidirectional Context Definition diagnostics ─────────────── */
  .cdf-diagnostics { display:none; margin-top:16px; border:1px solid var(--line); border-radius:16px;
    background:var(--input-bg); overflow:hidden; }
  .cdf-diagnostics.show { display:block; }
  .diag-head { display:flex; align-items:flex-start; justify-content:space-between; gap:12px;
    padding:14px 16px; border-bottom:1px solid var(--line); background:var(--gutter); }
  .diag-head h3 { margin:0; color:var(--text); font-size:14px; }
  .diag-head p { margin:3px 0 0; color:var(--muted); font-size:11px; }
  .diag-version { flex-shrink:0; padding:5px 8px; border:1px solid var(--line); border-radius:8px;
    background:var(--panel); color:var(--accent); font-size:10px; font-weight:750; }
  .diag-metrics { display:grid; grid-template-columns:repeat(4,minmax(0,1fr)); gap:8px; padding:12px 14px 0; }
  .diag-metrics > div { padding:10px 11px; border:1px solid var(--line); border-radius:11px; background:var(--panel); }
  .diag-metrics span,.diag-metrics strong { display:block; }
  .diag-metrics span { color:var(--muted); font-size:9px; font-weight:750; letter-spacing:.05em; text-transform:uppercase; }
  .diag-metrics strong { margin-top:3px; color:var(--text); font-size:18px; line-height:1.1; }
  .diag-explanation { margin:10px 14px; padding:10px 12px; border-left:3px solid var(--accent);
    border-radius:8px; background:var(--info-bg); color:var(--info-text); font-size:11px; line-height:1.55; }
  .diag-tabs { display:flex; gap:5px; flex-wrap:wrap; padding:0 14px 10px; }
  .diag-tab { border:1px solid var(--line); border-radius:9px; padding:7px 9px; background:var(--panel);
    color:var(--muted); font-size:10px; font-weight:750; cursor:pointer; }
  .diag-tab span { margin-left:4px; padding:1px 5px; border-radius:99px; background:var(--gutter); color:var(--text); }
  .diag-tab.active { border-color:var(--accent); background:var(--accent); color:var(--on-accent); }
  .diag-tab.active span { background:color-mix(in srgb,var(--on-accent) 18%,transparent); color:var(--on-accent); }
  .diag-list { max-height:360px; overflow:auto; border-top:1px solid var(--line); }
  .diag-empty { padding:22px; color:var(--muted); text-align:center; font-size:11px; }
  .diag-row { display:grid; grid-template-columns:minmax(150px,.8fr) minmax(200px,1.2fr) minmax(160px,1fr) auto;
    gap:10px; align-items:start; padding:9px 14px; border-bottom:1px solid var(--line); }
  .diag-row:last-child { border-bottom:0; }
  .diag-row:hover { background:var(--gutter); }
  .diag-kind { width:max-content; max-width:100%; padding:2px 6px; border-radius:5px;
    background:var(--gutter); color:var(--muted); font-size:9px; font-weight:750; }
  .diag-kind.serializer { background:color-mix(in srgb,var(--amber) 11%,var(--panel)); color:var(--amber); }
  .diag-name { color:var(--text); font-family:"JetBrains Mono","SF Mono",monospace; font-size:10px; font-weight:700; overflow-wrap:anywhere; }
  .diag-path,.diag-detail { color:var(--muted); font-family:"JetBrains Mono","SF Mono",monospace;
    font-size:9px; overflow-wrap:anywhere; }
  .diag-count { min-width:32px; padding:2px 6px; border-radius:99px; background:var(--gutter);
    color:var(--text); font-size:9px; font-weight:800; text-align:center; }
  .diag-count-row { display:grid; grid-template-columns:minmax(180px,1fr) repeat(3,90px);
    gap:8px; padding:8px 14px; border-bottom:1px solid var(--line); font-size:10px; }
  .diag-count-row.head { position:sticky; top:0; z-index:1; background:var(--gutter); color:var(--muted); font-weight:750; }
  .diag-count-row code { color:var(--text); }
  .diag-positive { color:var(--green); }
  .diag-negative { color:var(--red); }

  /* ── CD Fix selection panel ─────────────────────────────────── */
  .cdfix-select { display:none; margin-top:20px; border:1px solid var(--teal); border-radius:var(--radius); overflow:hidden; box-shadow:var(--shadow); }
  .cdfix-select.show { display: block; }
  .cdfix-sel-head { background:var(--teal); color:var(--on-accent); padding:12px 18px; font-size:13px; font-weight:700;
    display: flex; align-items: center; justify-content: space-between; gap: 10px; }
  .cdfix-sel-body { padding:16px; background:var(--panel); max-height:none; }
  .cdfix-metrics { display:grid; grid-template-columns:repeat(4,minmax(0,1fr)); gap:10px; margin-bottom:14px; }
  .metric-card { position:relative; overflow:hidden; display:flex; flex-direction:column; gap:2px; min-height:76px;
    padding:13px 14px; border:1px solid var(--line); border-radius:14px; background:var(--input-bg); }
  .metric-card::before { content:""; position:absolute; inset:0 auto 0 0; width:3px; background:var(--accent); }
  .metric-card strong { color:var(--text); font-size:22px; line-height:1.1; letter-spacing:-.03em; }
  .metric-card span { color:var(--muted); font-size:11px; font-weight:650; }
  .metric-map::before { background:var(--teal); }
  .metric-node::before { background:var(--purple); }
  .metric-error::before { background:var(--amber); }
  .cdfix-data-toolbar { display:flex; align-items:center; gap:10px; flex-wrap:wrap; margin-bottom:10px; }
  label.cdfix-search { width:min(330px,100%); margin:0; display:flex; align-items:center; gap:7px; padding:0 10px;
    border:1px solid var(--line); border-radius:11px; background:var(--input-bg); text-transform:none; letter-spacing:0; }
  .cdfix-search input { border:0; padding:8px 0; background:transparent; box-shadow:none !important; }
  .cdfix-filters { display:flex; align-items:center; gap:5px; flex-wrap:wrap; }
  .filter-chip { border:1px solid var(--line); border-radius:9px; padding:7px 10px; background:var(--panel);
    color:var(--muted); font-size:11px; font-weight:700; cursor:pointer; transition:all .2s ease; }
  .filter-chip[data-cdf-filter="all"] { color:var(--accent); background:color-mix(in srgb,var(--accent) 9%,var(--panel)); }
  .filter-chip[data-cdf-filter="ready"] { color:var(--ok-text); background:var(--ok-bg); }
  .filter-chip[data-cdf-filter="errors"] {
    color:var(--text); background:color-mix(in srgb,var(--amber) 12%,var(--panel));
  }
  .filter-chip[data-cdf-filter="updates"] {
    color:var(--purple); background:color-mix(in srgb,var(--purple) 10%,var(--panel));
  }
  .filter-chip[data-cdf-filter="mapping"] { color:var(--teal-text); background:var(--teal-bg); }
  .filter-chip[data-cdf-filter="nodeAttr"] { color:var(--purple); background:color-mix(in srgb,var(--purple) 10%,var(--panel)); }
  .filter-chip[data-cdf-filter="selected"] { color:var(--amber); background:color-mix(in srgb,var(--amber) 10%,var(--panel)); }
  .filter-chip:hover { border-color:var(--accent); color:var(--accent); }
  .filter-chip.active { border-color:var(--accent); background:var(--accent); color:var(--on-accent);
    box-shadow:0 5px 14px color-mix(in srgb,var(--accent) 22%,transparent); }
  .filter-chip[data-cdf-filter="ready"].active { border-color:var(--green); background:var(--green); }
  .filter-chip[data-cdf-filter="errors"].active {
    border-color:var(--amber); background:var(--amber); color:var(--text);
  }
  .filter-chip[data-cdf-filter="updates"].active { border-color:var(--purple); background:var(--purple); }
  .filter-chip[data-cdf-filter="mapping"].active { border-color:var(--teal); background:var(--teal); }
  .filter-chip[data-cdf-filter="nodeAttr"].active { border-color:var(--purple); background:var(--purple); }
  .filter-chip[data-cdf-filter="selected"].active { border-color:var(--amber); background:var(--amber); color:var(--text); }
  .cdfix-sel-actions { display: flex; gap: 8px; flex-wrap: wrap; margin-bottom: 12px; align-items: center; }
  .cdfix-sel-actions .ghost { padding: 5px 12px; font-size: 12px; }
  .cdfix-legend { display: flex; gap: 10px; margin-left: auto; flex-wrap: wrap; }
  .cdfix-legend-item { display: inline-flex; align-items: center; gap: 4px; font-size: 11px; color: var(--muted); }
  .cdfix-legend-dot { width: 8px; height: 8px; border-radius: 2px; }
  .cdfix-data-layout { display:grid; grid-template-columns:minmax(0,1.35fr) minmax(300px,.65fr); gap:12px; align-items:start; }
  #cdfFieldList { min-width:0; max-height:620px; overflow:auto; padding-right:3px; }
  .cdfix-detail { position:sticky; top:12px; min-height:260px; max-height:620px; overflow:auto;
    border:1px solid var(--line); border-radius:14px; background:var(--input-bg); }
  .cdfix-detail-empty { min-height:258px; display:grid; place-content:center; justify-items:center; padding:24px;
    color:var(--muted); text-align:center; }
  .cdfix-detail-empty > span { width:38px; height:38px; display:grid; place-items:center; margin-bottom:8px;
    border-radius:12px; background:var(--gutter); color:var(--accent); font-size:21px; }
  .cdfix-detail-empty strong { color:var(--text); font-size:13px; }
  .cdfix-detail-empty p { max-width:240px; margin:4px 0 0; font-size:11px; }
  .cdfix-detail-head { padding:14px; border-bottom:1px solid var(--line); }
  .cdfix-detail-head h4 { margin:7px 0 3px; font-size:14px; word-break:break-word; }
  .cdfix-detail-head p { margin:0; color:var(--muted); font-size:11px; }
  .cdfix-detail-body { padding:14px; }
  .detail-row { margin-bottom:12px; }
  .detail-row > span { display:block; margin-bottom:4px; color:var(--muted); font-size:10px; font-weight:800;
    letter-spacing:.08em; text-transform:uppercase; }
  .detail-row code,.detail-preview { font-family:"JetBrains Mono","SF Mono",Menlo,monospace; font-size:11px; }
  .detail-row code { color:var(--text); overflow-wrap:anywhere; }
  .detail-preview { margin:0; padding:11px; border:1px solid var(--line); border-radius:10px; background:var(--gutter);
    color:var(--text); white-space:pre-wrap; overflow:auto; line-height:1.55; }
  .cdfix-card:has(input:checked) { background:color-mix(in srgb,var(--green) 4%,var(--input-bg)); }
  .cdfix-card.is-active { border-color:var(--accent); background:color-mix(in srgb,var(--accent) 7%,var(--input-bg));
    box-shadow:0 0 0 2px color-mix(in srgb,var(--accent) 12%,transparent); }
  .cdfix-card[hidden] { display:none; }
  .cdfix-group.is-filtered-empty { display:none; }

  /* ── Group header ────────────────────────────────────────────── */
  .cdfix-group { margin-bottom: 14px; }
  .cdfix-group-head { display:flex; align-items:center; gap:8px; padding:9px 13px;
    background:var(--teal-bg); border:1px solid color-mix(in srgb,var(--teal) 28%,var(--line)); border-radius:12px;
    margin-bottom: 6px; cursor: pointer; user-select: none; }
  .cdfix-group-head:hover { border-color:var(--teal); filter:brightness(1.02); }
  .cdfix-group-check { accent-color:var(--green); width:15px; height:15px; cursor:pointer; flex-shrink:0; }
  .cdfix-group-name { font-size: 13px; font-weight: 700; color: var(--teal-text); flex: 1;
    font-family: "SF Mono", Menlo, monospace; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; min-width: 0; }
  .cdfix-group-meta { font-size: 11px; color: var(--muted); white-space: nowrap; flex-shrink: 0; }
  .cdfix-group-badge { background:var(--teal); color:var(--on-accent); font-size:10px; font-weight:700;
    padding: 1px 8px; border-radius: 99px; }
  .cdfix-toggle-arrow { font-size: 11px; color: var(--muted); flex-shrink: 0; transition: transform .2s; }
  .cdfix-toggle-arrow.open { transform: rotate(180deg); }

  /* ── Item card — flat 3-row layout ──────────────────────────── */
  label.cdfix-card { display:flex; gap:10px; align-items:flex-start; padding:11px 13px;
    border:1px solid var(--line); border-radius:14px; margin-bottom:7px; background:var(--input-bg);
    cursor:pointer; text-transform:none; letter-spacing:normal; transition:border-color .2s,background .2s; }
  label.cdfix-card:hover { border-color:var(--workflow-line); background:var(--gutter); }
  label.cdfix-card input[type=checkbox] { margin-top:2px; flex-shrink:0; accent-color:var(--green);
    width: 15px; height: 15px; cursor: pointer; }
  .cdfix-ci { flex: 1; min-width: 0; }                     /* info column — takes remaining width */

  /* Row 1: type badge + attribute name + "Modified only" tag */
  .cdfix-r1 { display: flex; align-items: center; gap: 6px; flex-wrap: wrap; margin-bottom: 4px; }
  .cdfix-tbadge { font-size: 10px; font-weight: 700; padding: 2px 7px; border-radius: 4px;
    text-transform: uppercase; letter-spacing: .04em; flex-shrink: 0; }
  .cdfix-tbadge-m { background:var(--teal-bg); color:var(--teal-text); border:1px solid color-mix(in srgb,var(--teal) 32%,var(--line)); }
  .cdfix-tbadge-n { background:color-mix(in srgb,var(--purple) 11%,var(--panel)); color:var(--purple);
    border:1px solid color-mix(in srgb,var(--purple) 30%,var(--line)); }
  .cdfix-cname { font-family: "SF Mono", Menlo, monospace; font-size: 13px; font-weight: 700;
    color: var(--text); word-break: break-word; }
  .cdfix-modtag { font-size: 10px; padding: 2px 7px; border-radius: 4px; flex-shrink: 0;
    background:color-mix(in srgb,var(--accent) 10%,var(--panel)); color:var(--accent);
    border:1px solid color-mix(in srgb,var(--accent) 28%,var(--line)); font-weight:600; }
  .cdfix-warntag { font-size: 10px; padding: 2px 7px; border-radius: 4px; flex-shrink: 0;
    background:var(--red); color:var(--on-accent); }
  .cdfix-parenttag { font-size:10px; padding:2px 7px; border-radius:4px; flex-shrink:0;
    background:color-mix(in srgb,var(--amber) 18%,var(--panel)); color:var(--text);
    border:1px solid color-mix(in srgb,var(--amber) 55%,var(--line)); font-weight:700; }
  .cdfix-updatetag { font-size:10px; padding:2px 7px; border-radius:4px; flex-shrink:0;
    background:color-mix(in srgb,var(--purple) 12%,var(--panel)); color:var(--purple);
    border:1px solid color-mix(in srgb,var(--purple) 35%,var(--line)); font-weight:700; }
  .cdfix-readytag { font-size:10px; padding:2px 7px; border-radius:4px; flex-shrink:0;
    background:var(--ok-bg); color:var(--ok-text); border:1px solid color-mix(in srgb,var(--green) 28%,var(--line)); }
  .cdfix-parent-help { margin-top: 7px; padding: 8px 10px; border-radius: 6px;
    border:1px solid color-mix(in srgb,var(--amber) 55%,var(--line));
    background:color-mix(in srgb,var(--amber) 10%,var(--panel)); color:var(--text);
    font-size: 11px; line-height: 1.5; }
  .cdfix-parent-help strong { font-weight: 700; }

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
  .cdfix-fval-before { background:var(--gutter); color:var(--muted); text-decoration:line-through; }
  .cdfix-fval-hyd { background:color-mix(in srgb,var(--purple) 10%,var(--panel)); color:var(--purple); }
  .cdfix-fval-role { color: var(--muted); font-style: italic; font-size: 11px; }
  .report-summary { display:grid; grid-template-columns:repeat(4,minmax(0,1fr)); gap:7px; margin-bottom:10px; }
  .report-summary > div { padding:9px 10px; border:1px solid var(--line); border-radius:10px; background:var(--input-bg); }
  .report-summary strong,.report-summary span { display:block; }
  .report-summary strong { color:var(--text); font-size:18px; line-height:1.1; }
  .report-summary span { margin-top:2px; color:var(--muted); font-size:9px; font-weight:750; text-transform:uppercase; letter-spacing:.06em; }
  .report-summary > div:first-child { border-top:2px solid var(--green); }
  .report-summary > div:nth-child(2) { border-top:2px solid var(--purple); }
  .report-summary > div:nth-child(3) { border-top:2px solid var(--amber); }
  .report-summary > div:last-child { border-top:2px solid var(--red); }
  .apply-timeline { display:grid; gap:8px; margin-bottom:10px; }
  .timeline-item { display:grid; grid-template-columns:24px minmax(0,1fr); gap:9px; padding:9px 11px;
    border:1px solid var(--line); border-radius:11px; background:var(--input-bg); }
  .timeline-icon { width:22px; height:22px; display:grid; place-items:center; border-radius:50%; font-size:11px; font-weight:800; }
  .timeline-item.add .timeline-icon { color:var(--green); background:var(--ok-bg); }
  .timeline-item.update .timeline-icon { color:var(--purple); background:color-mix(in srgb,var(--purple) 10%,var(--panel)); }
  .timeline-item.skip .timeline-icon { color:var(--amber); background:color-mix(in srgb,var(--amber) 12%,var(--panel)); }
  .timeline-item.error .timeline-icon { color:var(--red); background:var(--err-bg); }
  .timeline-copy strong { display:block; color:var(--text); font-size:11px; }
  .timeline-copy span { display:block; margin-top:2px; color:var(--muted); font-family:"JetBrains Mono",monospace; font-size:10px; overflow-wrap:anywhere; }
  .timeline-toggle { width:100%; margin:2px 0 10px; }
  .raw-report { border-top:1px solid var(--line); padding-top:9px; }
  .raw-report summary { color:var(--muted); font-size:11px; font-weight:700; cursor:pointer; }
  .raw-report pre { margin-top:9px; }
  #cdfBuildStep:not(.hidden) { display:grid; grid-template-columns:minmax(0,1.1fr) minmax(320px,.9fr);
    gap:12px; margin-top:20px; padding-top:20px; border-top:1px solid var(--line); }
  #cdfBuildStep .cdfix-step-head { grid-column:1 / -1; }
  #cdfBuildStep > .panes,#cdfBuildStep > .status { grid-column:1; }
  #cdfBuildStep > .report { grid-column:2; grid-row:2 / span 2; margin-top:14px; }

  /* ── Readability and responsive width system ─────────────────── */
  body { font-size:15px; line-height:1.58; }
  .app-shell { grid-template-columns:clamp(172px,11vw,194px) minmax(0,1fr); }
  .app-main { width:100%; max-width:100%; }
  .wrap { padding-inline:clamp(14px,1.45vw,28px); }
  .topbar { padding-inline:clamp(14px,1.45vw,28px); }
  .topbar { min-height:74px; padding-top:11px; padding-bottom:8px; }
  .panel { width:100%; padding:clamp(16px,1.25vw,24px); }

  .brand strong { font-size:14px; }
  .brand small { font-size:12px; }
  .side-label,.eyebrow { font-size:11px; }
  .side-nav,.about-link { font-size:14px; }
  .sidebar .credit { font-size:11.5px; }
  .sub { font-size:14px; }
  .credit,.local-badge { font-size:12.5px; }

  .tabs { display:flex; width:100%; }
  .tab { font-size:14px; }
  .section-title h2 { font-size:17px; }
  .section-title p { font-size:13.5px; max-width:90ch; }
  label { font-size:13px; }
  .hint { font-size:13px; max-width:75ch; }
  .controls .field { flex-basis:clamp(280px,30vw,440px); }

  .xpane-head { min-height:52px; padding:10px 14px; }
  .xpane-head .ttl { font-size:13px; }
  .badge { font-size:11px; }
  .mini .ghost { font-size:12.5px; }
  .ln-gutter,.xpane textarea {
    font-size:13.5px;
    line-height:21px;
  }
  .ln-gutter { color:var(--gutter-text); border-right-color:color-mix(in srgb,var(--line) 82%,var(--text)); }
  .ln-inner { top:10px; }
  .xpane textarea { padding:10px; }
  .editor-status { font-size:11.5px; }
  .status { font-size:13.5px; line-height:1.6; }
  .report h3 { font-size:14px; }
  .report pre { font-size:13px; line-height:1.6; }
  .dup-warn-body,.dup-warn-head { font-size:13.5px; }
  .dup-list { font-size:13px; }
  .dup-badge { font-size:11px; }

  .summary,.legend,.diff-opts { font-size:13px; }
  .pane-title { font-size:13px; padding:10px 13px; }
  table.pane-table { font-size:13px; line-height:1.65; }
  .pane-table td { padding-inline:10px; }

  .cdfix-step-title { font-size:14.5px; }
  .cdfix-step-sub { font-size:13px; max-width:90ch; }
  .cdf-diff-indicator small { font-size:11px; }
  .diag-head { padding:16px 18px; }
  .diag-head h3 { font-size:16px; }
  .diag-head p { font-size:12.5px; }
  .diag-version { font-size:11.5px; padding:6px 10px; }
  .diag-metrics { gap:10px; padding:14px 16px 0; }
  .diag-metrics > div { padding:12px 13px; }
  .diag-metrics span { font-size:11px; }
  .diag-metrics strong { font-size:22px; }
  .diag-explanation { margin:12px 16px; padding:12px 14px; font-size:13px; }
  .diag-tabs { gap:7px; padding:0 16px 12px; }
  .diag-tab { padding:8px 11px; font-size:12px; }
  .diag-empty { font-size:13px; }
  .diag-row {
    grid-template-columns:minmax(170px,.75fr) minmax(220px,1.05fr) minmax(280px,1.45fr) 46px;
    gap:14px; padding:11px 16px;
  }
  .diag-kind,.diag-count { font-size:11px; }
  .diag-name { font-size:12.5px; }
  .diag-path,.diag-detail { font-size:12px; line-height:1.55; }
  .diag-count-row { grid-template-columns:minmax(220px,1fr) repeat(3,minmax(82px,110px)); font-size:12px; }

  .cdfix-sel-head { font-size:14px; padding:14px 18px; }
  .cdfix-sel-body { padding:18px; }
  .metric-card { min-height:84px; padding:15px 16px; }
  .metric-card strong { font-size:25px; }
  .metric-card span { font-size:12px; }
  label.cdfix-search { width:clamp(280px,30vw,480px); }
  .cdfix-search input,.filter-chip { font-size:12.5px; }
  .cdfix-sel-actions .ghost { font-size:12.5px; }
  .cdfix-legend-item { font-size:12px; }
  .cdfix-data-layout { grid-template-columns:minmax(0,1.65fr) minmax(350px,.7fr); gap:16px; }
  #cdfFieldList,.cdfix-detail { max-height:680px; }
  .cdfix-detail-head h4 { font-size:15px; }
  .cdfix-detail-head p,.cdfix-detail-empty p { font-size:12.5px; }
  .cdfix-detail-empty strong { font-size:14px; }
  .detail-row > span { font-size:11.5px; }
  .detail-row code,.detail-preview { font-size:12.5px; }
  .cdfix-group-head { padding:11px 14px; }
  .cdfix-group-name { font-size:14px; }
  .cdfix-group-meta { font-size:12px; }
  .cdfix-group-badge { font-size:11px; }
  label.cdfix-card { padding:13px 14px; gap:12px; }
  .cdfix-tbadge,.cdfix-modtag,.cdfix-warntag,.cdfix-parenttag,
  .cdfix-updatetag,.cdfix-readytag { font-size:11px; }
  .cdfix-cname { font-size:13.5px; }
  .cdfix-parent-help { font-size:12.5px; }
  .cdfix-rlabel,.cdfix-seg,.cdfix-sep,.cdfix-fval,.cdfix-fval-role { font-size:12px; }
  .report-summary span { font-size:11px; }
  .report-summary strong { font-size:21px; }
  .timeline-copy strong { font-size:12.5px; }
  .timeline-copy span,.raw-report summary { font-size:12px; }

  #view-cdfix > .cdfix-step:first-child { margin-top:0; }
  #view-cdfix > .cdfix-step:first-child .cdfix-step-head { margin-bottom:7px; }
  #view-cdfix > .cdfix-step:first-child + .cdfix-step { margin-top:10px !important; }
  .diag-metric-card { display:flex; align-items:center; gap:11px; }
  .diag-metric-icon { width:34px; height:34px; flex:0 0 34px; display:grid; place-items:center;
    border-radius:9px; background:color-mix(in srgb,var(--accent) 9%,var(--panel)); color:var(--accent); }
  .diag-metric-icon svg { width:18px; height:18px; fill:none; stroke:currentColor; stroke-width:1.8;
    stroke-linecap:round; stroke-linejoin:round; }
  .diag-metric-card:nth-child(2) .diag-metric-icon { color:var(--purple); background:color-mix(in srgb,var(--purple) 9%,var(--panel)); }
  .diag-metric-card:nth-child(3) .diag-metric-icon { color:var(--teal); background:color-mix(in srgb,var(--teal) 9%,var(--panel)); }
  .diag-metric-card:nth-child(4) .diag-metric-icon { color:var(--amber); background:color-mix(in srgb,var(--amber) 9%,var(--panel)); }

  .primary-action-row { display:flex; width:100%; margin-top:14px; }
  .primary-action-row .action {
    width:100%; min-height:50px; display:flex; align-items:center; justify-content:center;
  }
  .primary-action-row .action:hover:not(:disabled) {
    transform:translateY(-1px); box-shadow:0 7px 18px color-mix(in srgb,var(--accent) 22%,transparent);
  }
  .section-head { padding-bottom:14px; margin-bottom:16px; }
  .controls { margin-bottom:14px; }
  .status.show { display:flex; align-items:flex-start; border-width:1px; }

  .cdf-diagnostics { border-radius:11px; background:var(--panel); }
  .diag-metrics > div,.metric-card,.report-summary > div {
    box-shadow:0 1px 2px rgba(15,23,42,.035);
  }
  .diag-tab { border-radius:7px; }
  .diag-tab.active { box-shadow:none; }
  .diag-row { transition:background .14s ease; }

  .cdfix-select { border-color:var(--line); border-radius:12px; box-shadow:var(--shadow); }
  .cdfix-sel-head {
    background:color-mix(in srgb,var(--accent) 8%,var(--panel));
    color:var(--text); border-bottom:1px solid var(--line);
  }
  .cdfix-group-head { border-radius:9px; }
  label.cdfix-card { border-radius:9px; }
  .cdfix-detail { border-radius:10px; }
  .metric-card { border-radius:10px; }

  .report.show {
    padding:16px; border:1px solid var(--line); border-radius:11px; background:var(--panel);
  }
  .raw-report pre,.report pre { border-radius:9px; }
  .timeline-item { border-radius:9px; }

  /* ── v3.2 Revenue Cloud final polish ──────────────────────────── */
  body { font-family:var(--font-sans);
    font-size:14px; line-height:1.6; letter-spacing:-.003em; }
  .xpane textarea,.ln-gutter,table.pane-table,.detail-preview,.detail-row code,
  .report pre,.raw-report pre { font-family:var(--font-mono); }
  .status { padding:14px 16px; font-family:var(--font-sans); }
  .pane-table td { padding:3px 14px; }
  button.action,.ghost,select,input { border-radius:10px; }
  .panel,.xpane,.cdf-diagnostics,.cdfix-select,.cdfix-detail,.metric-card,
  label.cdfix-card,.report.show { border-radius:12px; }
  h1 { font-size:clamp(30px,2.35vw,34px); line-height:1.15; }
  .side-menu { gap:2px; }
  .side-menu .side-label { padding:13px 11px 7px; font-size:9.5px; }
  .side-menu .side-label:first-child { padding-top:0; }
  .side-menu-divider { height:1px; margin:12px 9px 2px; background:var(--line); }
  .side-nav { padding:8px 10px; font-size:12px; font-weight:600; }
  .side-nav .nav-icon { width:19px; height:19px; flex-basis:19px; }
  .side-nav .nav-icon svg { width:15px; height:15px; }
  .side-nav[data-mode="cdfix"] { margin-top:1px; color:color-mix(in srgb,var(--accent) 76%,var(--text)); }
  .side-nav[data-mode="cdfix"] .nav-icon { border-radius:7px;
    background:color-mix(in srgb,var(--accent) 9%,var(--panel)); }
  .side-nav[data-mode="cdfix"].active { color:var(--accent); }

  #view-cdfix { background:var(--panel); }
  #view-cdfix > .cdfix-step { padding:15px; border-radius:12px; }
  #view-cdfix > .cdfix-step:first-child { background:var(--panel); }
  #view-cdfix > .cdfix-step:first-child + .cdfix-step {
    margin-top:22px !important; background:var(--gutter);
  }
  .cdfix-step-head { gap:10px; margin-bottom:12px; padding:9px 12px;
    border:1px solid var(--workflow-line); border-radius:8px; background:var(--workflow-bg); }
  .cdfix-step-num { width:auto; min-width:64px; height:30px; padding:0 10px; border-radius:8px;
    font-size:14px; font-weight:800; background:var(--accent); }
  .cdfix-step-title { font-size:18px; line-height:1.2; font-weight:750; letter-spacing:-.015em; }
  .cdfix-step-sub { margin-top:2px; font-size:12px; line-height:1.35; }
  .cdfix-step-head > div { min-width:0; }
  #view-cdfix .xpane-head { padding:11px 14px; }
  #view-cdfix .xpane textarea { padding:12px; }
  #view-cdfix .ln-inner { top:12px; }
  #view-cdfix .editor-status { min-height:34px; padding:7px 12px; }
  .cdf-diff-indicator { align-self:center; }

  .cdf-diagnostics { margin-top:22px; border:0; background:var(--gutter); }
  .diag-metric-card.metric-difference { border-color:color-mix(in srgb,var(--accent) 34%,var(--line));
    background:color-mix(in srgb,var(--accent) 5%,var(--panel)); }
  .diag-metric-card.metric-difference strong { color:var(--accent); }
  .diag-metrics strong { font-size:26px; line-height:1.05; }

  .cdfix-select { margin-top:24px; border:0; box-shadow:none; overflow:visible; background:var(--panel); }
  .cdfix-sel-head { padding:12px 14px; border:1px solid var(--workflow-line);
    border-radius:8px; background:var(--workflow-bg); font-size:16px; }
  .cdfix-sel-body { padding:24px 4px 8px; }
  .cdfix-metrics { gap:12px; margin-bottom:20px; }
  .metric-card { display:grid; grid-template-columns:32px minmax(0,1fr); grid-template-rows:auto auto;
    align-items:center; column-gap:10px; min-height:82px; padding:14px 15px; }
  .metric-card-icon { grid-row:1 / span 2; width:30px; height:30px; display:grid; place-items:center;
    border-radius:8px; background:color-mix(in srgb,var(--accent) 9%,var(--panel)); color:var(--accent); }
  .metric-card-icon svg { width:16px; height:16px; fill:none; stroke:currentColor; stroke-width:1.9;
    stroke-linecap:round; stroke-linejoin:round; }
  .metric-map .metric-card-icon { color:var(--teal); background:color-mix(in srgb,var(--teal) 9%,var(--panel)); }
  .metric-node .metric-card-icon { color:var(--purple); background:color-mix(in srgb,var(--purple) 9%,var(--panel)); }
  .metric-error .metric-card-icon { color:var(--amber); background:color-mix(in srgb,var(--amber) 10%,var(--panel)); }
  .metric-card::before { display:none; }
  .metric-card strong { grid-column:2; font-size:26px; }
  .metric-card > div > span,.metric-card > span:not(.metric-card-icon) { font-size:12px; }
  .cdfix-tbadge { display:inline-flex; align-items:center; gap:4px; }
  .cdfix-tbadge .btn-icon { width:12px; height:12px; margin:0; }
  .cdfix-data-toolbar { gap:16px; margin-bottom:16px; padding-bottom:16px; border-bottom:1px solid var(--line); }
  .cdfix-filters { gap:8px; }
  .cdfix-sel-actions { margin-bottom:16px; gap:8px; }
  .cdfix-selection-count { margin-left:auto; display:inline-flex; align-items:center; min-height:34px;
    padding:6px 10px; border-radius:10px; background:var(--workflow-bg); color:var(--text);
    font-size:12.5px; font-weight:750; white-space:nowrap; }
  .cdfix-legend { margin-left:0; }
  .cdfix-data-layout { gap:24px; }
  #cdfFieldList { padding-right:7px; }
  .cdfix-group { margin-bottom:16px; }
  label.cdfix-card { margin:8px 0; padding:16px 18px; }
  .cdfix-detail { position:static; border-color:color-mix(in srgb,var(--line) 78%,transparent);
    transition:border-color .18s ease,background .18s ease,box-shadow .18s ease; }
  .cdfix-detail.context-flash { border-color:var(--accent);
    box-shadow:0 0 0 3px color-mix(in srgb,var(--accent) 10%,transparent); }
  .cdfix-detail-head,.cdfix-detail-body { padding:16px; }

  #cdfBuildStep:not(.hidden) { margin-top:24px; padding:18px; border-top:0; border-radius:12px; background:var(--gutter); }
  #cdfBuildStep .cdfix-step-head { grid-column:1 / -1; margin-bottom:0; }
  #cdfBuildStep .cdfix-step-sub { max-width:none; white-space:nowrap; }
  #cdfBuildStep > .build-action-row { grid-column:1 / -1; margin-top:0; }
  #cdfBuildStep > .panes { grid-column:1; grid-row:3; }
  #cdfBuildStep > .status { grid-column:1; grid-row:4; }
  #cdfBuildStep > .report { grid-column:2; grid-row:3 / span 2; margin-top:14px; }
  #cdfBuildStep .build-action-row .action { min-height:50px; border-radius:10px; font-size:14px; }
  .report.show { padding:18px; border:0; background:var(--panel); }
  .report h3 { display:flex; align-items:center; gap:8px; margin-bottom:14px; font-size:16px; }
  .report h3 .btn-icon { width:17px; height:17px; color:var(--accent); }
  .report-summary { gap:9px; margin-bottom:14px; }
  .report-summary > div { position:relative; padding:11px 12px 11px 22px; border:0; }
  .report-summary > div::before { content:""; position:absolute; left:9px; top:50%; width:8px; height:8px;
    border-radius:50%; background:var(--green); transform:translateY(-50%); }
  .report-summary > div:nth-child(2)::before { background:var(--accent); }
  .report-summary > div:nth-child(3)::before { background:var(--amber); }
  .report-summary > div:nth-child(4)::before { background:var(--red); }
  .report-summary > div:nth-child(2) strong { color:var(--accent); }
  .timeline-item { padding:11px 12px; border-color:color-mix(in srgb,var(--line) 82%,transparent);
    transition:border-color .18s ease,background .18s ease,box-shadow .18s ease; }
  .timeline-item.update .timeline-icon { color:var(--accent); background:var(--info-bg); }
  .timeline-item.is-context-match { border-color:var(--accent);
    background:color-mix(in srgb,var(--accent) 7%,var(--panel));
    box-shadow:0 0 0 2px color-mix(in srgb,var(--accent) 9%,transparent); }
  .primary-action-row .action:hover:not(:disabled) {
    box-shadow:0 1px 3px color-mix(in srgb,var(--accent) 24%,transparent);
  }

  /* ── v3.2.2 calm engineering color system ─────────────────────── */
  .topbar { background:var(--header-bg); }
  .cdfix-step-head { border-left:3px solid var(--accent); }
  .cdfix-sel-head { border-left:1px solid var(--workflow-line); }
  .side-nav.active {
    color:var(--accent); background:var(--workflow-bg);
    box-shadow:inset 4px 0 0 var(--accent);
  }
  .revenue-label { color:var(--muted) !important; }
  .side-nav[data-mode="cdfix"] { color:var(--muted); }
  .side-nav[data-mode="cdfix"] .nav-icon { color:var(--muted); background:var(--gutter); }
  .side-nav[data-mode="cdfix"].active { color:var(--accent); }
  .tab[data-mode="cdfix"] { color:var(--muted); }
  .tab[data-mode="cdfix"].active { color:var(--accent); border-bottom-color:var(--accent); }
  .b-compare,.b-merge,.b-dedup,.b-cdfix { background:var(--accent); }
  .fab-up { background:var(--accent); }
  .fab-down { color:var(--accent); border-color:var(--accent); }
  .badge.modified { background:var(--accent); }

  .status.ok { background:var(--ok-bg); border-color:var(--green); color:var(--ok-text); }
  .filter-chip[data-cdf-filter="ready"] { background:var(--ok-bg); color:var(--ok-text); }
  .filter-chip[data-cdf-filter="ready"].active {
    border-color:var(--green); background:var(--green); color:var(--on-accent);
  }
  .cdfix-readytag { background:var(--ok-bg); color:var(--ok-text);
    border-color:color-mix(in srgb,var(--green) 35%,var(--line)); }
  .cdfix-warntag { background:var(--amber); color:#3a3335; }
  .cdfix-parenttag,.filter-chip[data-cdf-filter="errors"] {
    color:var(--text); background:color-mix(in srgb,var(--amber) 12%,var(--panel));
    border-color:color-mix(in srgb,var(--amber) 45%,var(--line));
  }
  .filter-chip[data-cdf-filter="errors"].active {
    color:#3a3335; background:var(--amber); border-color:var(--amber);
  }

  .filter-chip[data-cdf-filter="updates"],
  .filter-chip[data-cdf-filter="mapping"],
  .filter-chip[data-cdf-filter="nodeAttr"],
  .filter-chip[data-cdf-filter="selected"] { color:var(--muted); background:var(--panel); }
  .filter-chip[data-cdf-filter="updates"].active,
  .filter-chip[data-cdf-filter="mapping"].active,
  .filter-chip[data-cdf-filter="nodeAttr"].active,
  .filter-chip[data-cdf-filter="selected"].active {
    color:var(--on-accent); background:var(--accent); border-color:var(--accent);
  }
  .cdfix-tbadge-m,.cdfix-tbadge-n {
    color:var(--muted); background:var(--gutter); border-color:var(--line);
  }
  .metric-card,.diag-metrics > div,.report-summary > div {
    background:var(--panel); border-color:var(--line);
  }
  .metric-card-icon,.metric-map .metric-card-icon,.metric-node .metric-card-icon,.metric-error .metric-card-icon,
  .diag-metric-icon,.diag-metric-card:nth-child(2) .diag-metric-icon,
  .diag-metric-card:nth-child(3) .diag-metric-icon,.diag-metric-card:nth-child(4) .diag-metric-icon {
    color:var(--muted); background:var(--gutter);
  }
  .diag-metric-card.metric-difference .diag-metric-icon { color:var(--accent); background:var(--info-bg); }
  .pane-table tr:nth-child(even) td.code:not(.del):not(.ins):not(.chg),
  .diag-row:nth-child(even) { background:color-mix(in srgb,var(--gutter) 62%,var(--panel)); }
  .diag-row:hover { background:var(--gutter); }

  /* ── v3.3 colour, hierarchy, spacing, and visual polish ───────── */
  .panel { border-color:var(--line); box-shadow:var(--shadow); }
  #view-cdfix { background:var(--panel); }
  #view-cdfix > .cdfix-step,
  #view-cdfix > .cdfix-step:first-child,
  #view-cdfix > .cdfix-step:first-child + .cdfix-step,
  #cdfBuildStep:not(.hidden) { background:var(--panel); }
  .cdfix-step-head {
    border:1px solid var(--workflow-line); border-left:1px solid var(--workflow-line);
    background:var(--workflow-bg); color:var(--workflow-text);
  }
  .cdfix-step-title { color:var(--workflow-text); }
  .cdfix-step-sub { color:color-mix(in srgb,var(--workflow-text) 72%,transparent); font-size:12.5px; }
  .cdfix-sel-head { background:var(--gutter); border-color:var(--line); }

  .xpane { background:var(--panel); border-color:var(--line); }
  #view-cdfix .xpane textarea { background:var(--panel); font-size:14px; line-height:20.3px; }
  #view-cdfix .ln-gutter { font-size:14px; line-height:20.3px; }
  .badge.base { background:#dff6e8; color:#137a43; }
  .badge.modified { background:#e7e9ff; color:#5b3cc4; }
  .badge.out { background:var(--info-bg); color:var(--accent); }

  .primary-action-row .action { min-height:40px; height:40px; }
  #cdfAnalyzeBtn,#cdfBuildBtn { min-height:40px; height:40px; }
  #cdfBuildStep > .build-action-row { justify-content:center; }
  #cdfBuildStep .build-action-row .action { width:50%; max-width:520px; min-width:280px; }
  button.action:hover:not(:disabled),.primary-action-row .action:hover:not(:disabled) {
    background:var(--accent-strong); transform:none; filter:none;
  }
  .ghost { background:var(--panel); color:#344054; border-color:#cbd5e1; }
  html[data-theme="dark"] .ghost { color:var(--text); border-color:var(--line); }
  .btn-icon { width:14px; height:14px; flex-basis:14px; }
  .tab .btn-icon,.filter-chip .btn-icon { width:14px; height:14px; }
  .theme-toggle { gap:6px; min-height:36px; }

  .status.ok { padding:11px 14px; background:#ecfdf3; border-color:#86d7a8; color:#167044; }
  html[data-theme="dark"] .status.ok { background:var(--ok-bg); border-color:var(--green); color:var(--ok-text); }
  .diag-tab { background:#f8fafc; color:#526174; border-color:#d7e0ea; }
  .diag-tab.active { background:var(--accent); color:var(--on-accent); border-color:var(--accent); }
  html[data-theme="dark"] .diag-tab { background:var(--gutter); color:var(--muted); border-color:var(--line); }
  html[data-theme="dark"] .diag-tab.active { background:var(--accent); color:var(--on-accent); }
  .diag-row { background:var(--panel); border-color:#e2e8f0; }
  .diag-row:nth-child(even) { background:var(--panel); }
  .diag-row:hover { background:#f4f8fc; }
  html[data-theme="dark"] .diag-row:hover { background:var(--gutter); }

  .cdfix-card:has(input:checked) { background:var(--panel); }
  .cdfix-card.is-active { border-color:#9bc4f5; background:#eaf4ff;
    box-shadow:0 0 0 2px color-mix(in srgb,var(--accent) 8%,transparent); }
  html[data-theme="dark"] .cdfix-card.is-active {
    border-color:var(--accent); background:color-mix(in srgb,var(--accent) 10%,var(--panel));
  }
  #cdfBuildStep > .report { border-left:1px solid #d9e2ec; padding-left:18px; }
  html[data-theme="dark"] #cdfBuildStep > .report { border-left-color:var(--line); }

  button:focus-visible,input:focus-visible,select:focus-visible,textarea:focus-visible,
  [tabindex]:focus-visible { outline:2px solid var(--accent); outline-offset:2px; }
  .side-nav:hover,.about-link:hover,button.action:active:not(:disabled),.ghost:active {
    transform:none;
  }

  @media (min-width:1500px) {
    .xpane-body { min-height:390px; }
    #view-cdfix .xpane-body,
    #view-cdfix .xpane textarea { height:400px !important; max-height:400px !important; }
    .diag-list { max-height:440px; }
    #cdfFieldList,.cdfix-detail { max-height:760px; }
  }
  /* ── Fixed floating scroll buttons ────────────────────────────── */
  .fab { position:fixed; z-index:99999; width:48px; height:48px; border-radius:50%;
    border: none; cursor: pointer; display: flex; align-items: center; justify-content: center;
    box-shadow:var(--shadow); transition:transform .15s,box-shadow .15s,filter .15s;
    bottom: 26px; }
  .fab:hover { transform:translateY(-2px) scale(1.06); filter:brightness(1.08); }
  .fab:active { transform:scale(.94); }
  .fab-up   { right:26px; background:var(--accent); color:var(--on-accent); }
  .fab-down { left:208px; background:var(--panel); color:var(--accent);
    border:2px solid var(--accent); }

  @media (max-width: 1050px) {
    .app-shell { display:block; }
    .sidebar { position:sticky; height:auto; padding:9px 12px; flex-direction:row; align-items:center;
      gap:12px; border-right:0; border-bottom:1px solid var(--line); }
    .brand { padding:0; min-width:max-content; }
    .brand-mark { width:32px; height:32px; border-radius:10px; }
    .brand small,.side-label,.sidebar-footer { display:none; }
    .side-menu-divider { display:none; }
    .side-menu { display:flex; flex:1; gap:4px; overflow-x:auto; scrollbar-width:none; }
    .side-menu::-webkit-scrollbar { display:none; }
    .side-nav { width:auto; min-width:max-content; padding:8px 10px; }
    .side-nav:hover { transform:none; }
    .side-nav.active { box-shadow:inset 0 -2px 0 var(--accent); }
    .tabs { display:none; }
    .topbar { min-height:104px; }
    .fab-down { left:14px; }
    .cdfix-data-layout { grid-template-columns:1fr; }
    .cdfix-detail { position:static; }
    #cdfBuildStep:not(.hidden) { grid-template-columns:1fr; }
    #cdfBuildStep > .panes,#cdfBuildStep > .status,#cdfBuildStep > .report {
      grid-column:1; grid-row:auto; }
  }
  @media (max-width: 760px) {
    .sidebar { align-items:flex-start; }
    .brand { padding-top:2px; }
    .brand > span:last-child { display:none; }
    .side-nav .nav-icon { display:none; }
    .wrap { padding:0 10px 72px; }
    .topbar { align-items:stretch; flex-direction:column; gap:8px; }
    .top-actions { justify-content:space-between; flex-wrap:wrap; }
    .tabs { display:none; }
    .panel { border-radius:12px; }
    .cdfix-metrics { grid-template-columns:repeat(2,minmax(0,1fr)); }
    .diag-metrics { grid-template-columns:repeat(2,minmax(0,1fr)); }
    .diag-row { grid-template-columns:1fr; gap:4px; }
    .diag-count-row { grid-template-columns:minmax(130px,1fr) repeat(3,64px); }
    .cdf-editor-grid { grid-template-columns:1fr; }
    #view-cdfix .xpane-head { align-items:flex-start; flex-wrap:wrap; }
    #view-cdfix .xpane-head .ttl { width:100%; white-space:normal; }
    #view-cdfix .xpane-head .mini { width:100%; justify-content:flex-start; }
    .cdf-diff-indicator { grid-template-columns:repeat(4,minmax(0,1fr)); min-height:0; padding:8px; }
    .cdf-diff-arrow { display:none; }
    .cdf-rail-total { padding:4px; border-bottom:0; border-right:1px solid var(--line); }
    .cdf-rail-metric { grid-template-columns:1fr; justify-items:center; padding:4px 2px; }
    .cdf-rail-metric .cdf-rail-dot { display:none; }
    .cdf-rail-metric span:last-child { grid-column:1; text-align:center; }
    .diff-panes { flex-direction:column; }
    .cdfix-step-head { align-items:flex-start; flex-wrap:wrap; }
    .cdfix-step-head .action { margin-left:34px !important; }
    #cdfBuildStep .cdfix-step-sub { white-space:normal; }
    .cdfix-selection-count { width:100%; margin-left:0; justify-content:center; }
    #cdfBuildStep .build-action-row .action { width:100%; min-width:0; max-width:none; }
    #cdfBuildStep > .report { border-left:0; border-top:1px solid var(--line); padding-left:0; padding-top:16px; }
    .fab-up { right:14px; }
    .fab-down { left:14px; }
  }
</style>
</head>
<body>
  <div class="app-shell">
    <aside class="sidebar" aria-label="Primary navigation">
      <div class="brand">
        <span class="brand-mark" aria-hidden="true">
          <svg viewBox="0 0 24 24"><path d="M7.2 18.5c-3.1 0-5.7-2.1-5.7-4.8 0-2.1 1.5-3.9 3.7-4.5C5.7 6.5 8 4.5 10.8 4.5c2.2 0 4.1 1.2 5.1 3 3.6-.3 6.6 2 6.6 5.2 0 3.2-2.8 5.8-6.4 5.8H7.2Z"/></svg>
        </span>
        <span><strong>Salesforce</strong><small>Metadata XML Tool</small></span>
      </div>
      <nav class="side-menu">
        <div class="side-label">Metadata Tools</div>
        <button class="side-nav active" data-mode="compare"><span class="nav-icon"><svg viewBox="0 0 24 24"><path d="M8 3H5a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h3M16 3h3a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2h-3M10 8l-3 4 3 4M14 8l3 4-3 4"/></svg></span><span>Compare</span></button>
        <button class="side-nav" data-mode="merge"><span class="nav-icon"><svg viewBox="0 0 24 24"><path d="M8 6h10M14 2l4 4-4 4M16 18H6M10 14l-4 4 4 4"/></svg></span><span>Merge</span></button>
        <button class="side-nav" data-mode="dedup"><span class="nav-icon"><svg viewBox="0 0 24 24"><rect x="8" y="8" width="12" height="12" rx="2"/><path d="M16 8V6a2 2 0 0 0-2-2H6a2 2 0 0 0-2 2v8a2 2 0 0 0 2 2h2M11 14h6"/></svg></span><span>Deduplicate</span></button>
        <div class="side-menu-divider"></div>
        <div class="side-label revenue-label">Revenue Cloud</div>
        <button class="side-nav" data-mode="cdfix"><span class="nav-icon"><svg viewBox="0 0 24 24"><path d="M12 3v6M12 15v6M3 12h6M15 12h6"/><circle cx="12" cy="12" r="3"/><circle cx="12" cy="3" r="1"/><circle cx="12" cy="21" r="1"/><circle cx="3" cy="12" r="1"/><circle cx="21" cy="12" r="1"/></svg></span><span>Context Definition Fix</span></button>
      </nav>
      <div class="sidebar-footer">
        <a class="about-link" href="https://www.linkedin.com/in/mrpancholi/" target="_blank" rel="noopener noreferrer">
          <span class="nav-icon"><svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="9"/><path d="M12 11v6M12 7h.01"/></svg></span><span>About</span>
        </a>
        <p class="credit">Made with 💙 by <a href="https://www.linkedin.com/in/mrpancholi/" target="_blank" rel="noopener noreferrer">Mritunjaya Pancholi</a></p>
        <a class="linkedin-link" href="https://www.linkedin.com/in/mrpancholi/" target="_blank" rel="noopener noreferrer">
          <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M5.4 3.8a2.1 2.1 0 1 1 0 4.2 2.1 2.1 0 0 1 0-4.2ZM3.6 9.5h3.6V21H3.6V9.5Zm5.8 0h3.4v1.6h.1c.5-.9 1.7-2 3.5-2 3.7 0 4.4 2.4 4.4 5.6V21h-3.6v-5.6c0-1.3 0-3.1-1.9-3.1s-2.2 1.5-2.2 3V21H9.4V9.5Z"/></svg>
          <span>LinkedIn</span>
        </a>
      </div>
    </aside>

    <main class="app-main">
      <header class="topbar">
        <div>
          <h1 id="pageTitle">Compare XML</h1>
          <p class="sub" id="pageSubtitle">Inspect two Salesforce metadata files with structural and line-level differences.</p>
        </div>
        <div class="top-actions">
          <span class="local-badge"><span class="live-dot"></span>Runs locally</span>
          <button class="ghost theme-toggle" id="themeBtn" title="Toggle day/night" aria-label="Switch to night mode">
            <span class="theme-switch" aria-hidden="true"></span>
          </button>
        </div>
      </header>

      <div class="wrap">
        <div class="tabs" id="tabs" aria-label="Tool switcher">
          <button class="tab active" data-mode="compare">Compare</button>
          <button class="tab" data-mode="merge">Merge</button>
          <button class="tab" data-mode="dedup">Deduplicate</button>
          <button class="tab" data-mode="cdfix">Context Definition Fix</button>
        </div>

    <!-- ============================ COMPARE ============================ -->
    <div class="panel" id="view-compare">
      <div class="section-head">
        <div class="section-title"><span class="step-dot">1</span><div>
          <h2>Paste XML files to compare</h2>
          <p>See only unique XML changes. Matching content is ignored even when it appears on different lines or in a different order.</p>
        </div></div>
      </div>
      <div class="controls">
        <div class="field">
          <label for="cmpTag">Limit to element (optional)</label>
          <input id="cmpTag" placeholder="e.g. fieldPermissions, contextMappings" autocomplete="off" spellcheck="false" />
          <div class="hint">Leave blank to compare everything. Works for permission sets, context definitions, Apex (line diff only), etc.</div>
        </div>
        <div class="grow"></div>
      </div>

      <div class="panes">
        <div class="xpane">
          <div class="xpane-head">
            <span class="ttl">Left XML</span>
            <div class="mini">
              <button class="ghost" data-paste="cmpA">Paste</button>
              <button class="ghost" data-copy="cmpA">Copy</button>
              <button class="ghost" data-clear="cmpA">Clear</button>
            </div>
          </div>
          <div class="xpane-body"><div class="ln-gutter" id="ln-cmpA"></div><textarea id="cmpA" placeholder="Paste the first XML here.&#10;This file will appear on the left side of the comparison." spellcheck="false"></textarea></div>
        </div>
        <div class="xpane">
          <div class="xpane-head">
            <span class="ttl">Right XML</span>
            <div class="mini">
              <button class="ghost" data-paste="cmpB">Paste</button>
              <button class="ghost" data-copy="cmpB">Copy</button>
              <button class="ghost" data-clear="cmpB">Clear</button>
            </div>
          </div>
          <div class="xpane-body"><div class="ln-gutter" id="ln-cmpB"></div><textarea id="cmpB" placeholder="Paste the second XML here.&#10;This file will appear on the right side of the comparison." spellcheck="false"></textarea></div>
        </div>
      </div>
      <div class="primary-action-row">
        <button class="action b-compare" id="compareBtn">Compare</button>
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
            <div class="pane-title">Left — unique structural differences</div>
            <div class="pane-scroll" id="srcScroll"><table class="pane-table" id="srcTable"></table></div>
          </div>
          <div class="pane">
            <div class="pane-title">Right — unique structural differences</div>
            <div class="pane-scroll" id="tgtScroll"><table class="pane-table" id="tgtTable"></table></div>
          </div>
        </div>
      </div>
    </div>

    <!-- ============================= MERGE ============================= -->
    <div class="panel hidden" id="view-merge">
      <div class="section-head">
        <div class="section-title"><span class="step-dot">1</span><div>
          <h2>Choose a base and layer in modifications</h2>
          <p>The base remains authoritative; matching entries from Modified override it and new entries are added.</p>
        </div></div>
      </div>
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
        </div>
      </div>

      <div class="panes">
        <div class="xpane">
          <div class="xpane-head">
            <span class="ttl">Pane 1 — Base XML <span class="badge base" id="badge1">BASE</span></span>
            <div class="mini">
              <button class="ghost" data-paste="mrgA">Paste</button>
              <button class="ghost" data-copy="mrgA">Copy</button>
              <button class="ghost" data-clear="mrgA">Clear</button>
            </div>
          </div>
          <div class="xpane-body"><div class="ln-gutter" id="ln-mrgA"></div><textarea id="mrgA" placeholder="Paste the BASE XML here.&#10;This is the authoritative version the merge will build on." spellcheck="false"></textarea></div>
        </div>
        <div class="xpane">
          <div class="xpane-head">
            <span class="ttl">Pane 2 — Modified XML <span class="badge base hidden" id="badge2">BASE</span></span>
            <div class="mini">
              <button class="ghost" data-paste="mrgB">Paste</button>
              <button class="ghost" data-copy="mrgB">Copy</button>
              <button class="ghost" data-clear="mrgB">Clear</button>
            </div>
          </div>
          <div class="xpane-body"><div class="ln-gutter" id="ln-mrgB"></div><textarea id="mrgB" placeholder="Paste the MODIFIED XML here.&#10;Its matching changes and new entries will be layered onto Base." spellcheck="false"></textarea></div>
        </div>
        <div class="xpane">
          <div class="xpane-head">
            <span class="ttl">Merged result <span class="badge out">OUTPUT</span></span>
            <div class="mini">
              <button class="ghost" id="mergeCopyBtn">Copy</button>
              <button class="ghost" id="mergeDownloadBtn">Download</button>
              <button class="ghost" data-clear="mrgOut">Clear</button>
            </div>
          </div>
          <div class="xpane-body"><div class="ln-gutter" id="ln-mrgOut"></div><textarea id="mrgOut" placeholder="The merged XML will appear here.&#10;Use Copy or Download when the merge completes." spellcheck="false" readonly></textarea></div>
        </div>
      </div>
      <div class="primary-action-row">
        <button class="action b-merge" id="mergeBtn">Merge</button>
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
      <div class="section-head">
        <div class="section-title"><span class="step-dot">1</span><div>
          <h2>Clean a Permission Set or Profile</h2>
          <p>Duplicate identity keys are collapsed and the metadata is returned in stable Salesforce order.</p>
        </div></div>
      </div>
      <div class="panes">
        <div class="xpane">
          <div class="xpane-head">
            <span class="ttl">Permission Set XML</span>
            <div class="mini">
              <button class="ghost" data-paste="dedIn">Paste</button>
              <button class="ghost" data-copy="dedIn">Copy</button>
              <button class="ghost" data-clear="dedIn">Clear</button>
            </div>
          </div>
          <div class="xpane-body"><div class="ln-gutter" id="ln-dedIn"></div><textarea id="dedIn" placeholder="Paste a Permission Set or Profile XML here.&#10;Duplicate identity entries will be detected and collapsed." spellcheck="false"></textarea></div>
        </div>
        <div class="xpane">
          <div class="xpane-head">
            <span class="ttl">Cleaned result <span class="badge out">OUTPUT</span></span>
            <div class="mini">
              <button class="ghost" id="dedupCopyBtn">Copy</button>
              <button class="ghost" id="dedupDownloadBtn">Download</button>
              <button class="ghost" data-clear="dedOut">Clear</button>
            </div>
          </div>
          <div class="xpane-body"><div class="ln-gutter" id="ln-dedOut"></div><textarea id="dedOut" placeholder="The cleaned and sorted XML will appear here.&#10;Use Copy or Download when processing completes." spellcheck="false" readonly></textarea></div>
        </div>
      </div>
      <div class="primary-action-row">
        <button class="action b-dedup" id="dedupBtn">Remove duplicates</button>
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
          <span class="cdfix-step-num">Step 1</span>
          <div>
            <div class="cdfix-step-title">Input Context Definitions</div>
            <div class="cdfix-step-sub">Paste the Base and Modified Context Definition XML files.</div>
          </div>
          <button class="ghost" id="cdfClearAll" style="margin-left:auto;">Clear All</button>
        </div>
        <div class="panes cdf-editor-grid">
          <div class="xpane">
            <div class="xpane-head">
              <span class="ttl">Base Context Definition <span class="badge base">Base</span></span>
              <div class="mini">
                <button class="ghost" id="cdfBasePasteBtn" data-paste="cdfBase">Paste</button>
                <button class="ghost" id="cdfBaseCopyBtn" data-copy="cdfBase">Copy</button>
                <button class="ghost" data-clear="cdfBase">Clear</button>
              </div>
            </div>
            <div class="xpane-body"><div class="ln-gutter" id="ln-cdfBase"></div><textarea id="cdfBase" placeholder="Paste the BASE Context Definition XML here.&#10;Use the target org version—the tool will not delete its existing entries." spellcheck="false"></textarea></div>
          </div>
          <div class="cdf-diff-indicator" id="cdfDiffIndicator" aria-live="polite">
            <span class="cdf-diff-arrow"><svg viewBox="0 0 24 24"><path d="M20 7h-9a5 5 0 0 0-5 5v1M4 17h9a5 5 0 0 0 5-5v-1M16 3l4 4-4 4M8 13l-4 4 4 4"/></svg></span>
            <div class="cdf-rail-total"><strong id="cdfDiffCount">—</strong><small>Total changes</small></div>
            <div class="cdf-rail-metric added"><span class="cdf-rail-icon"><svg viewBox="0 0 24 24"><path d="M12 5v14M5 12h14"/></svg></span><b id="cdfRailAdded">—</b><span>Added</span></div>
            <div class="cdf-rail-metric updated"><span class="cdf-rail-icon"><svg viewBox="0 0 24 24"><path d="m4 20 4.5-1 10-10a2.1 2.1 0 0 0-3-3l-10 10L4 20Z"/></svg></span><b id="cdfRailUpdated">—</b><span>Updated</span></div>
            <div class="cdf-rail-metric base-only"><span class="cdf-rail-icon"><svg viewBox="0 0 24 24"><path d="M12 3 4 6v5c0 5 3.3 8.2 8 10 4.7-1.8 8-5 8-10V6l-8-3Z"/></svg></span><b id="cdfRailBaseOnly">—</b><span>Base only</span></div>
          </div>
          <div class="xpane">
            <div class="xpane-head">
              <span class="ttl">Modified Context Definition <span class="badge modified">Modified</span></span>
              <div class="mini">
                <button class="ghost" id="cdfModPasteBtn" data-paste="cdfMod">Paste</button>
                <button class="ghost" id="cdfModCopyBtn" data-copy="cdfMod">Copy</button>
                <button class="ghost" data-clear="cdfMod">Clear</button>
              </div>
            </div>
            <div class="xpane-body"><div class="ln-gutter" id="ln-cdfMod"></div><textarea id="cdfMod" placeholder="Paste the MODIFIED Context Definition XML here.&#10;Use the source org version containing the new field mappings." spellcheck="false"></textarea></div>
          </div>
        </div>
      </div>

      <!-- Step 2 trigger -->
      <div class="cdfix-step" style="margin-top:14px;">
        <div class="cdfix-step-head">
          <span class="cdfix-step-num">Step 2</span>
          <div>
            <div class="cdfix-step-title">Review Additions and Value Changes</div>
            <div class="cdfix-step-sub">Analyze Context Mappings, Context Attributes, and Required Parent Blocks while preserving Base.</div>
          </div>
        </div>
        <div class="primary-action-row">
          <button class="action b-cdfix" id="cdfAnalyzeBtn">Analyze Differences</button>
        </div>
        <div class="status" id="cdfAnalyzeStatus"></div>
      </div>

      <!-- Bidirectional diagnostics: explains line count and what changed -->
      <section class="cdf-diagnostics" id="cdfDiagnostics">
        <div class="diag-head">
          <div>
            <h3>Why are the line counts different?</h3>
            <p>Separates Salesforce serializer omissions from actual metadata additions, removals, and changes.</p>
          </div>
          <span class="diag-version" id="cdfDiagVersions"></span>
        </div>
        <div class="diag-metrics">
          <div class="diag-metric-card">
            <span class="diag-metric-icon"><svg viewBox="0 0 24 24"><path d="M6 3h9l4 4v14H6zM14 3v5h5M9 12h7M9 16h7"/></svg></span>
            <div><span>Base lines</span><strong id="cdfDiagBaseLines">0</strong></div>
          </div>
          <div class="diag-metric-card">
            <span class="diag-metric-icon"><svg viewBox="0 0 24 24"><path d="M6 3h9l4 4v14H6zM14 3v5h5M9 12h7M9 16h5"/></svg></span>
            <div><span>Modified lines</span><strong id="cdfDiagModifiedLines">0</strong></div>
          </div>
          <div class="diag-metric-card metric-difference">
            <span class="diag-metric-icon"><svg viewBox="0 0 24 24"><path d="M5 8h14M15 4l4 4-4 4M19 16H5M9 12l-4 4 4 4"/></svg></span>
            <div><span>Line difference</span><strong id="cdfDiagLineDelta">0</strong></div>
          </div>
          <div class="diag-metric-card">
            <span class="diag-metric-icon"><svg viewBox="0 0 24 24"><path d="M4 7h16v13H4zM8 7V4h8v3M9 12h6"/></svg></span>
            <div><span>Business items missing</span><strong id="cdfDiagBusinessRemoved">0</strong></div>
          </div>
        </div>
        <div class="diag-explanation" id="cdfDiagExplanation"></div>
        <div class="diag-tabs" id="cdfDiagTabs">
          <button class="diag-tab active" data-diag-view="removed">Present only in Base <span id="cdfDiagRemovedCount">0</span></button>
          <button class="diag-tab" data-diag-view="added">Present only in Modified <span id="cdfDiagAddedCount">0</span></button>
          <button class="diag-tab" data-diag-view="changed">Materially changed <span id="cdfDiagChangedCount">0</span></button>
          <button class="diag-tab" data-diag-view="counts">Element counts</button>
        </div>
        <div class="diag-list" id="cdfDiagList"></div>
      </section>

      <!-- Step 3: Selection panel (shown after analyze) -->
      <div class="cdfix-select" id="cdfSelectPanel">
        <div class="cdfix-sel-head">
          <span id="cdfSelHeadText">Select fields to include</span>
        </div>
        <div class="cdfix-sel-body">
          <div class="cdfix-metrics" id="cdfMetrics">
            <div class="metric-card metric-all"><span class="metric-card-icon"><svg viewBox="0 0 24 24"><path d="M5 6h14M5 12h14M5 18h9"/></svg></span><strong id="cdfMetricAll">0</strong><span>Total changes</span></div>
            <div class="metric-card metric-map"><span class="metric-card-icon"><svg viewBox="0 0 24 24"><path d="M10 13a5 5 0 0 0 7.1.1l2-2a5 5 0 0 0-7.1-7.1l-1.1 1.1M14 11a5 5 0 0 0-7.1-.1l-2 2A5 5 0 0 0 12 20l1.1-1.1"/></svg></span><strong id="cdfMetricMappings">0</strong><span>Context Mappings</span></div>
            <div class="metric-card metric-node"><span class="metric-card-icon"><svg viewBox="0 0 24 24"><path d="M4 6h11l5 5-9 9-7-7V6Z"/><circle cx="9" cy="11" r="1"/></svg></span><strong id="cdfMetricNodes">0</strong><span>Context Attributes</span></div>
            <div class="metric-card metric-error"><span class="metric-card-icon"><svg viewBox="0 0 24 24"><path d="m4 7 8-4 8 4-8 4-8-4Zm0 0v10l8 4 8-4V7M12 11v10"/></svg></span><strong id="cdfMetricErrors">0</strong><span>Required Parent Blocks</span></div>
          </div>
          <div class="cdfix-data-toolbar">
            <label class="cdfix-search"><span>⌕</span><input id="cdfSearch" type="search" placeholder="Search fields, Context Mappings, Context Attributes…" /></label>
            <div class="cdfix-filters" id="cdfFilters">
              <button class="filter-chip active" data-cdf-filter="all">All</button>
              <button class="filter-chip" data-cdf-filter="ready">Ready</button>
              <button class="filter-chip" data-cdf-filter="errors">Required Parent Blocks</button>
              <button class="filter-chip" data-cdf-filter="updates">Value changes</button>
              <button class="filter-chip" data-cdf-filter="mapping">Context Mappings</button>
              <button class="filter-chip" data-cdf-filter="nodeAttr">Context Attributes</button>
              <button class="filter-chip" data-cdf-filter="selected">Selected</button>
            </div>
          </div>
          <div class="cdfix-sel-actions" id="cdfSelActions">
            <button class="ghost" id="cdfSelAll">Select all</button>
            <button class="ghost" id="cdfSelNone">Deselect all</button>
            <button class="ghost" id="cdfExpandAll">Expand all</button>
            <button class="ghost" id="cdfCollapseAll">Collapse all</button>
            <span class="cdfix-selection-count" id="cdfSelCount">Total: 0 · Selected: 0</span>
          </div>
          <div class="cdfix-data-layout">
            <div id="cdfFieldList"></div>
            <aside class="cdfix-detail" id="cdfDetail" tabindex="-1">
              <div class="cdfix-detail-empty">
                <span>⌁</span>
                <strong>Select a Context Definition change</strong>
                <p>Choose a row to inspect its Revenue Cloud path and XML preview.</p>
              </div>
            </aside>
          </div>
        </div>
      </div>

      <!-- Step 4: Build -->
      <div class="cdfix-step hidden" id="cdfBuildStep">
        <div class="cdfix-step-head">
          <span class="cdfix-step-num">Step 3</span>
          <div>
            <div class="cdfix-step-title">Build Context Definition</div>
            <div class="cdfix-step-sub">Applies selected fields and complete required parent blocks on top of Base. Every structural addition is listed in the report.</div>
          </div>
        </div>
        <div class="primary-action-row build-action-row">
          <button class="action b-cdfix" id="cdfBuildBtn">Build Context Definition</button>
        </div>

        <div class="panes" style="margin-top:14px;">
          <div class="xpane">
            <div class="xpane-head">
              <span class="ttl">Patched Result <span class="badge out">Output</span></span>
              <div class="mini">
                <button class="ghost" id="cdfCopyBtn">Copy</button>
                <button class="ghost" id="cdfDownloadBtn">Download</button>
                <button class="ghost" data-clear="cdfOut">Clear</button>
              </div>
            </div>
            <div class="xpane-body"><div class="ln-gutter" id="ln-cdfOut"></div><textarea id="cdfOut" placeholder="The patched Context Definition will appear here.&#10;Review the quick report before copying or downloading it." spellcheck="false" readonly></textarea></div>
          </div>
        </div>

        <div class="status" id="cdfBuildStatus"></div>
        <div class="report" id="cdfReport">
          <h3><svg class="btn-icon" viewBox="0 0 24 24" aria-hidden="true"><path d="M6 3h9l4 4v14H6zM14 3v5h5M9 12h7M9 16h7"/></svg>Apply Report</h3>
          <div class="report-summary" id="cdfReportSummary">
            <div><strong id="cdfReportAdded">0</strong><span>Added</span></div>
            <div><strong id="cdfReportUpdated">0</strong><span>Updated</span></div>
            <div><strong id="cdfReportSkipped">0</strong><span>Skipped</span></div>
            <div><strong id="cdfReportErrors">0</strong><span>Errors</span></div>
          </div>
          <div class="apply-timeline" id="cdfTimeline"></div>
          <button class="ghost timeline-toggle hidden" id="cdfTimelineToggle">Show all details</button>
          <details class="raw-report">
            <summary>View raw report</summary>
            <pre id="cdfReportBody"></pre>
          </details>
        </div>

      </div>

        </div>
      </div>
    </main>
  </div>

<script>
  const $ = (id) => document.getElementById(id);

  // ── Consistent Lucide-style button icons ─────────────────────────────────
  const ICON_PATHS = {
    copy: '<rect x="8" y="8" width="12" height="12" rx="2"/><path d="M16 8V6a2 2 0 0 0-2-2H6a2 2 0 0 0-2 2v8a2 2 0 0 0 2 2h2"/>',
    paste: '<path d="M9 5h6M9 3h6v4H9z"/><path d="M9 5H6a2 2 0 0 0-2 2v13h16V7a2 2 0 0 0-2-2h-3"/>',
    clear: '<circle cx="12" cy="12" r="9"/><path d="m9 9 6 6m0-6-6 6"/>',
    trash: '<path d="M4 7h16M9 7V4h6v3m3 0-1 14H7L6 7M10 11v6m4-6v6"/>',
    download: '<path d="M12 3v12m-5-5 5 5 5-5M5 21h14"/>',
    search: '<circle cx="11" cy="11" r="7"/><path d="m20 20-4-4"/>',
    compare: '<path d="M8 5H4v14h4M16 5h4v14h-4M10 8l-3 4 3 4m4-8 3 4-3 4"/>',
    merge: '<path d="M6 3v6a6 6 0 0 0 6 6h6M6 21v-5a6 6 0 0 1 6-6h6M15 7l3 3-3 3"/>',
    mapping: '<path d="M10 13a5 5 0 0 0 7.1.1l2-2a5 5 0 0 0-7.1-7.1l-1.1 1.1M14 11a5 5 0 0 0-7.1-.1l-2 2A5 5 0 0 0 12 20l1.1-1.1"/>',
    attribute: '<path d="M4 6h11l5 5-9 9-7-7V6Z"/><circle cx="9" cy="11" r="1"/>',
    parentBlock: '<path d="m4 7 8-4 8 4-8 4-8-4Zm0 0v10l8 4 8-4V7M12 11v10"/>',
    sparkles: '<path d="m12 3 1.2 3.3L16.5 7.5l-3.3 1.2L12 12l-1.2-3.3-3.3-1.2 3.3-1.2L12 3ZM5 14l.8 2.2L8 17l-2.2.8L5 20l-.8-2.2L2 17l2.2-.8L5 14Zm13-2 .8 2.2 2.2.8-2.2.8L18 18l-.8-2.2L15 15l2.2-.8L18 12Z"/>',
    selectAll: '<rect x="3" y="3" width="18" height="18" rx="3"/><path d="m8 12 3 3 5-6"/>',
    deselectAll: '<rect x="3" y="3" width="18" height="18" rx="3"/><path d="M8 12h8"/>',
    expand: '<path d="m7 9 5 5 5-5M7 3l5 5 5-5"/>',
    collapse: '<path d="m7 15 5-5 5 5M7 21l5-5 5 5"/>',
    swap: '<path d="M7 7h12l-3-3m3 3-3 3M17 17H5l3 3m-3-3 3-3"/>',
    build: '<path d="m14.7 6.3 3 3M4 20l4.5-1 10-10a2.1 2.1 0 0 0-3-3l-10 10L4 20Z"/>',
    moon: '<path d="M20 15.5A8.5 8.5 0 0 1 8.5 4 8.5 8.5 0 1 0 20 15.5Z"/>',
    sun: '<circle cx="12" cy="12" r="4"/><path d="M12 2v2m0 16v2M4.9 4.9l1.4 1.4m11.4 11.4 1.4 1.4M2 12h2m16 0h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/>',
    check: '<path d="m5 12 4 4L19 6"/>',
    alert: '<path d="M12 3 2.5 20h19L12 3Z"/><path d="M12 9v4m0 3h.01"/>'
  };
  function buttonIcon(name) {
    return `<svg class="btn-icon" viewBox="0 0 24 24" aria-hidden="true">${ICON_PATHS[name] || ''}</svg>`;
  }
  function decorateButton(id, icon) {
    const btn = $(id);
    if (btn && !btn.querySelector('.btn-icon')) btn.insertAdjacentHTML('afterbegin', buttonIcon(icon));
  }
  function decorateButtons() {
    document.querySelectorAll('[data-clear]').forEach(btn => {
      if (!btn.querySelector('.btn-icon')) btn.insertAdjacentHTML('afterbegin', buttonIcon('clear'));
    });
    document.querySelectorAll('[data-paste]').forEach(btn => {
      if (!btn.querySelector('.btn-icon')) btn.insertAdjacentHTML('afterbegin', buttonIcon('paste'));
    });
    document.querySelectorAll('[data-copy]').forEach(btn => {
      if (!btn.querySelector('.btn-icon')) btn.insertAdjacentHTML('afterbegin', buttonIcon('copy'));
    });
    [
      ['compareBtn','compare'],['mergeBtn','merge'],['dedupBtn','sparkles'],['swapBtn','swap'],
      ['mergeCopyBtn','copy'],['mergeDownloadBtn','download'],['dedupCopyBtn','copy'],['dedupDownloadBtn','download'],
      ['cdfAnalyzeBtn','search'],['cdfBuildBtn','build'],['cdfCopyBtn','copy'],['cdfDownloadBtn','download'],
      ['cdfBasePasteBtn','paste'],['cdfModPasteBtn','paste'],['cdfBaseCopyBtn','copy'],['cdfModCopyBtn','copy'],
      ['cdfSelAll','selectAll'],['cdfSelNone','deselectAll'],['cdfExpandAll','expand'],['cdfCollapseAll','collapse'],
      ['cdfClearAll','trash']
    ].forEach(([id,icon]) => decorateButton(id,icon));
    const tabIcons = {compare:'compare',merge:'merge',dedup:'sparkles',cdfix:'build'};
    document.querySelectorAll('.tab').forEach(tab => {
      if (!tab.querySelector('.btn-icon')) tab.insertAdjacentHTML('afterbegin',buttonIcon(tabIcons[tab.dataset.mode]));
    });
  }
  decorateButtons();

  // ── Line-number gutter ─────────────────────────────────────────────────────
  const _lnRefresh = {};
  function initLN(taId) {
    const ta = $(taId);
    const gut = $('ln-' + taId);
    const lineInner = document.createElement('span');
    lineInner.className = 'ln-inner';
    gut.replaceChildren(lineInner);
    const pane = ta.closest('.xpane');
    const status = document.createElement('div');
    status.className = 'editor-status';
    status.innerHTML = '<span class="format">XML</span><span data-lines></span><span class="waiting" data-validity>Awaiting XML</span>';
    pane.appendChild(status);
    let validityTimer, validityVersion = 0, totalLines = 1;
    function countLines(text) {
      let count = 1;
      for (let i = 0; i < text.length; i++) if (text.charCodeAt(i) === 10) count++;
      return count;
    }
    function renderVisibleLines() {
      const lineHeight = parseFloat(getComputedStyle(ta).lineHeight) || 21;
      const first = Math.max(0, Math.floor(ta.scrollTop / lineHeight));
      const visible = Math.ceil((ta.clientHeight || 420) / lineHeight) + 2;
      const last = Math.min(totalLines, first + visible);
      let numbers = '';
      for (let line = first + 1; line <= last; line++) numbers += line + '\n';
      lineInner.textContent = numbers;
      lineInner.style.transform = `translateY(${-1 * (ta.scrollTop % lineHeight)}px)`;
    }
    function refreshValidity(version) {
      if (version !== validityVersion) return;
      const validity = status.querySelector('[data-validity]');
      if (!ta.value.trim()) {
        validity.className = 'waiting';
        validity.textContent = 'Awaiting XML';
        return;
      }
      const parsed = new DOMParser().parseFromString(ta.value, 'application/xml');
      const invalid = parsed.querySelector('parsererror');
      validity.className = invalid ? 'invalid' : 'valid';
      validity.innerHTML = buttonIcon(invalid ? 'alert' : 'check') + (invalid ? 'Invalid XML' : 'Valid XML');
    }
    function refresh() {
      totalLines = ta.value ? countLines(ta.value) : 1;
      renderVisibleLines();
      status.querySelector('[data-lines]').textContent = `${totalLines.toLocaleString()} lines`;
      clearTimeout(validityTimer);
      const version = ++validityVersion;
      const delay = ta.value.length > 200000 ? 900 : 300;
      validityTimer = setTimeout(() => {
        const run = () => refreshValidity(version);
        if ('requestIdleCallback' in window) requestIdleCallback(run, { timeout: 1500 });
        else run();
      }, delay);
    }
    ta.addEventListener('input', refresh);
    ta.addEventListener('scroll', renderVisibleLines, { passive: true });
    if ('ResizeObserver' in window) new ResizeObserver(renderVisibleLines).observe(ta);
    refresh();
    _lnRefresh[taId] = refresh;
  }
  ['cmpA','cmpB','mrgA','mrgB','mrgOut','dedIn','dedOut','cdfBase','cdfMod','cdfOut'].forEach(initLN);
  // ──────────────────────────────────────────────────────────────────────────

  // ---- Theme ----
  const themeBtn = $("themeBtn");
  function applyThemeLabel() {
    const t = document.documentElement.getAttribute("data-theme") || "light";
    const dark = t === "dark";
    themeBtn.classList.toggle("is-dark", dark);
    themeBtn.setAttribute("aria-label", dark ? "Switch to day mode" : "Switch to night mode");
    themeBtn.innerHTML = buttonIcon(dark ? "sun" : "moon") +
      '<span class="theme-switch" aria-hidden="true"></span>';
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
  const pageMeta = {
    compare: ["Compare XML", "Inspect two Salesforce metadata files with structural and line-level differences."],
    merge: ["Merge Metadata", "Layer selected changes onto an authoritative base without losing unrelated metadata."],
    dedup: ["Deduplicate XML", "Remove repeated Permission Set or Profile entries and produce a clean, stable output."],
    cdfix: ["Context Definition Fix", "Compare, analyze, and build Salesforce Context Definitions with confidence."]
  };
  function switchMode(mode) {
    if (!views[mode]) return;
    document.querySelectorAll("[data-mode]").forEach(x => x.classList.toggle("active", x.dataset.mode === mode));
    Object.entries(views).forEach(([key, view]) => view.classList.toggle("hidden", key !== mode));
    $("pageTitle").textContent = pageMeta[mode][0];
    $("pageSubtitle").textContent = pageMeta[mode][1];
  }
  document.querySelectorAll(".tab,.side-nav").forEach(t => {
    t.onclick = () => switchMode(t.dataset.mode);
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
  function busy(btn, label) { btn.dataset.originalHtml = btn.innerHTML; btn.innerHTML = '<span class="spinner"></span>' + label; btn.disabled = true; }
  function idle(btn) { btn.innerHTML = btn.dataset.originalHtml || btn.innerHTML; btn.disabled = false; }
  async function copyFrom(textarea, btn) {
    if (!textarea.value) return;
    try { await navigator.clipboard.writeText(textarea.value); }
    catch (e) {
      const wasReadonly = textarea.hasAttribute("readonly");
      if (wasReadonly) textarea.removeAttribute("readonly");
      textarea.select(); document.execCommand("copy");
      if (wasReadonly) textarea.setAttribute("readonly","");
    }
    const old = btn.innerHTML;
    btn.innerHTML = buttonIcon("check") + "Copied!";
    setTimeout(() => btn.innerHTML = old, 1200);
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
  document.querySelectorAll('[data-paste]').forEach(btn => {
    btn.onclick = () => pasteInto(btn.dataset.paste);
  });
  document.querySelectorAll('[data-copy]').forEach(btn => {
    btn.onclick = () => copyFrom($(btn.dataset.copy), btn);
  });

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
      if (data.xml === false) renderDiff(cmpA.value, cmpB.value);
      else renderStructuralDiff(data);
      showReport(cmpReport, cmpReportBody, data.report);
      if (data.xml === false) setStatus(cmpStatus, "info", "Not valid XML — showing a line-by-line diff only.");
      else setStatus(cmpStatus, "ok", `Compared by XML content, ignoring line position. ${data.matched} matched · ${data.onlyLeft} only in left · ${data.onlyRight} only in right.`);
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
  function pairStructuralItems(leftItems, rightItems) {
    const pairs = [];
    const unusedRight = new Set(rightItems.map((_, index) => index));
    for (const left of leftItems) {
      let match = -1;
      if (left.identity) {
        match = rightItems.findIndex((right, index) =>
          unusedRight.has(index) && right.tag === left.tag && right.identity === left.identity);
      }
      if (match < 0 && !left.identity) {
        match = rightItems.findIndex((right, index) =>
          unusedRight.has(index) && right.tag === left.tag && !right.identity);
      }
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
    const leftItems = data.uniqueLeft || [];
    const rightItems = data.uniqueRight || [];
    const pairs = pairStructuralItems(leftItems, rightItems);
    let left = "", right = "";
    if (!pairs.length) {
      const message = "No unique structural differences — matching XML content may appear on different lines.";
      left = paneRow("eq", "✓", esc(message), " ");
      right = paneRow("eq", "✓", esc(message), " ");
    } else {
      pairs.forEach(([leftItem, rightItem], pairIndex) => {
        const leftLines = structuralItemLines(leftItem);
        const rightLines = structuralItemLines(rightItem);
        const length = Math.max(leftLines.length, rightLines.length);
        const rowType = leftItem && rightItem ? "chg" : leftItem ? "del" : "ins";
        const leftMarker = rowType === "chg" ? "~" : "−";
        const rightMarker = rowType === "chg" ? "~" : "+";
        for (let index = 0; index < length; index++) {
          const label = index === 0 ? `Δ${pairIndex + 1}` : "";
          if (index < leftLines.length)
            left += paneRow(rowType, label, esc(leftLines[index]), leftMarker);
          else
            left += paneRow("filler");
          if (index < rightLines.length)
            right += paneRow(rowType, label, esc(rightLines[index]), rightMarker);
          else
            right += paneRow("filler");
        }
      });
    }
    srcTable.innerHTML = "<tbody>" + left + "</tbody>";
    tgtTable.innerHTML = "<tbody>" + right + "</tbody>";
    onlyDiffs.checked = false;
    onlyDiffs.closest(".diff-opts").style.display = "none";
    diffPanes.classList.remove("hide-eq");
    diffSummary.textContent = (data.onlyLeft + data.onlyRight === 0)
      ? `Structurally identical — line position and element order ignored.`
      : `${data.onlyLeft} unique occurrence${data.onlyLeft === 1 ? "" : "s"} only in left · ` +
        `${data.onlyRight} unique occurrence${data.onlyRight === 1 ? "" : "s"} only in right`;
    diffBox.classList.add("show");
  }
  function renderDiff(aText, bText) {
    onlyDiffs.closest(".diff-opts").style.display = "";
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
  $("mergeCopyBtn").onclick = (e) => copyFrom(mrgOut, e.currentTarget);
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
      const warnings = data.warnings || [];
      const message = `Done — ${data.removed} duplicate entr${data.removed === 1 ? "y" : "ies"} removed.` +
        (data.singletonDuplicates ? ` ${data.singletonDuplicates} came from singleton metadata such as description.` : "") +
        (warnings.length ? ` ${warnings.length} conflicting value warning${warnings.length === 1 ? "" : "s"} — see report.` : "");
      setStatus(dedStatus, warnings.length ? "info" : "ok", message);
    } else {
      dedOut.value = ""; _lnRefresh.dedOut();
      setStatus(dedStatus, "err", data.log || "Deduplication failed.");
    }
    idle(dedupBtn);
  };
  $("dedupCopyBtn").onclick = (e) => copyFrom(dedOut, e.currentTarget);
  $("dedupDownloadBtn").onclick = () => download(dedOut, "deduplicated.xml");

  // ====================== CONTEXT DEFINITION FIX =========================
  const cdfBase         = $("cdfBase"),  cdfMod    = $("cdfMod"), cdfOut = $("cdfOut");
  const cdfAnalyzeBtn   = $("cdfAnalyzeBtn"),  cdfBuildBtn = $("cdfBuildBtn");
  const cdfAnalyzeStatus = $("cdfAnalyzeStatus"), cdfBuildStatus = $("cdfBuildStatus");
  const cdfSelectPanel  = $("cdfSelectPanel"),   cdfBuildStep = $("cdfBuildStep");
  const cdfFieldList    = $("cdfFieldList"),      cdfSelCount  = $("cdfSelCount");
  const cdfReport       = $("cdfReport"),         cdfReportBody = $("cdfReportBody");
  const cdfSelHeadText  = $("cdfSelHeadText");
  const cdfDetail       = $("cdfDetail"),          cdfSearch = $("cdfSearch");
  const cdfTimeline     = $("cdfTimeline"),        cdfTimelineToggle = $("cdfTimelineToggle");
  const cdfDiffCount    = $("cdfDiffCount"),       cdfDiffIndicator = $("cdfDiffIndicator");
  const cdfRailAdded    = $("cdfRailAdded"),        cdfRailUpdated = $("cdfRailUpdated");
  const cdfRailBaseOnly = $("cdfRailBaseOnly");
  const cdfDiagnostics  = $("cdfDiagnostics"),     cdfDiagList = $("cdfDiagList");

  let _cdfItems = [];   // raw analysis results stored between steps
  let _cdfById = new Map();
  let _cdfFilter = 'all';
  let _cdfItemCheckboxes = [];
  let _cdfCards = [];
  let _cdfActiveCard = null;
  let _cdfActiveItem = null;
  let _cdfTimelineEntries = [];
  let _cdfTimelineExpanded = false;
  let _cdfDiagnostics = null;
  let _cdfDiagView = "removed";

  $("cdfClearAll").onclick = () => {
    [cdfBase,cdfMod,cdfOut].forEach(ta => {
      ta.value = "";
      if (_lnRefresh[ta.id]) _lnRefresh[ta.id]();
    });
    _cdfItems = []; _cdfById = new Map(); _cdfItemCheckboxes = []; _cdfCards = []; _cdfActiveCard = null; _cdfActiveItem = null;
    cdfFieldList.innerHTML = "";
    cdfSelectPanel.classList.remove("show");
    cdfBuildStep.classList.add("hidden");
    cdfReport.classList.remove("show");
    cdfDiagnostics.classList.remove("show");
    _cdfDiagnostics = null;
    [cdfAnalyzeStatus,cdfBuildStatus].forEach(el => { el.className = "status"; el.textContent = ""; });
    cdfDiffCount.textContent = "—";
    [cdfRailAdded,cdfRailUpdated,cdfRailBaseOnly].forEach(el => { el.textContent = "—"; });
    cdfDiffIndicator.classList.remove("has-diffs");
  };

  function cdfRenderDiagnosticList(view) {
    _cdfDiagView = view;
    document.querySelectorAll('[data-diag-view]').forEach(btn => {
      btn.classList.toggle('active', btn.dataset.diagView === view);
    });
    if (!_cdfDiagnostics) {
      cdfDiagList.innerHTML = "";
      return;
    }
    if (view === "counts") {
      const rows = _cdfDiagnostics.counts || [];
      cdfDiagList.innerHTML =
        `<div class="diag-count-row head"><span>Element</span><span>Base</span><span>Modified</span><span>Δ</span></div>` +
        rows.map(row => {
          const cls = row.delta > 0 ? "diag-positive" : row.delta < 0 ? "diag-negative" : "";
          const delta = row.delta > 0 ? `+${row.delta}` : String(row.delta);
          return `<div class="diag-count-row"><code>${esc(row.tag)}</code>` +
            `<span>${Number(row.base).toLocaleString()}</span>` +
            `<span>${Number(row.modified).toLocaleString()}</span>` +
            `<strong class="${cls}">${delta}</strong></div>`;
        }).join('');
      return;
    }
    const rows = _cdfDiagnostics[view] || [];
    if (!rows.length) {
      const label = view === "removed" ? "Base-only metadata" : view === "added" ? "Modified-only metadata" : "material changes";
      cdfDiagList.innerHTML = `<div class="diag-empty">No ${label} found.</div>`;
      return;
    }
    cdfDiagList.innerHTML = rows.map(row => {
      const serializer = String(row.type || "").startsWith("Serializer/");
      return `<div class="diag-row">` +
        `<span class="diag-kind ${serializer ? 'serializer' : ''}">${esc(row.type)}</span>` +
        `<span class="diag-name">${esc(row.name)}</span>` +
        `<span><span class="diag-path">${esc(row.path)}</span>` +
          (row.detail ? `<br><span class="diag-detail">${esc(row.detail)}</span>` : '') +
        `</span><span class="diag-count">${Number(row.count || 1).toLocaleString()}</span></div>`;
    }).join('');
  }

  function cdfRenderDiagnostics(diagnostics) {
    _cdfDiagnostics = diagnostics || null;
    if (!_cdfDiagnostics) {
      cdfDiagnostics.classList.remove("show");
      return;
    }
    $("cdfDiagBaseLines").textContent = Number(_cdfDiagnostics.baseLines || 0).toLocaleString();
    $("cdfDiagModifiedLines").textContent = Number(_cdfDiagnostics.modifiedLines || 0).toLocaleString();
    const delta = Number(_cdfDiagnostics.lineDelta || 0);
    const deltaEl = $("cdfDiagLineDelta");
    deltaEl.textContent = delta > 0 ? `+${delta.toLocaleString()}` : delta.toLocaleString();
    deltaEl.className = delta > 0 ? "diag-positive" : delta < 0 ? "diag-negative" : "";
    $("cdfDiagBusinessRemoved").textContent = Number(_cdfDiagnostics.businessRemovedCount || 0).toLocaleString();
    $("cdfDiagVersions").textContent =
      `Version ${_cdfDiagnostics.baseVersion || "?"} → ${_cdfDiagnostics.modifiedVersion || "?"}`;
    $("cdfDiagExplanation").textContent = _cdfDiagnostics.summary || "";
    $("cdfDiagRemovedCount").textContent = Number(_cdfDiagnostics.removedCount || 0).toLocaleString();
    $("cdfDiagAddedCount").textContent = Number(_cdfDiagnostics.addedCount || 0).toLocaleString();
    $("cdfDiagChangedCount").textContent = Number(_cdfDiagnostics.changedCount || 0).toLocaleString();
    cdfRailAdded.textContent = Number(_cdfDiagnostics.addedCount || 0).toLocaleString();
    cdfRailUpdated.textContent = Number(_cdfDiagnostics.changedCount || 0).toLocaleString();
    cdfRailBaseOnly.textContent = Number(_cdfDiagnostics.removedCount || 0).toLocaleString();
    cdfDiagnostics.classList.add("show");
    cdfRenderDiagnosticList("removed");
  }
  document.querySelectorAll('[data-diag-view]').forEach(btn => {
    btn.onclick = () => cdfRenderDiagnosticList(btn.dataset.diagView);
  });

  // ── helpers ─────────────────────────────────────────────────────────────
  function cdfUpdateSelCount() {
    const total   = _cdfItems.length;
    let checked = 0;
    for (const cb of _cdfItemCheckboxes) if (cb.checked) checked++;
    cdfSelCount.textContent = `Total: ${total.toLocaleString()} · Selected: ${checked.toLocaleString()}`;
    if (_cdfFilter === 'selected') cdfApplyFilters();
  }

  function cdfShowDetail(id) {
    const it = _cdfById.get(id);
    if (!it) return;
    _cdfActiveItem = it;
    if (_cdfActiveCard) _cdfActiveCard.classList.remove('is-active');
    _cdfActiveCard = _cdfCards.find(card => card.dataset.cardId === id) || null;
    if (_cdfActiveCard) _cdfActiveCard.classList.add('is-active');
    const isParentBlock = !!it.parentPatch;
    const isUpdate = it.changeKind === 'update';
    const isMapping = ['mapping','mappingBlock','nodeMappingBlock'].includes(it.type);
    const name = it.attrName || it.attrTitle || it.mappingTitle || it.nodeName || '';
    const location = it.type === 'mappingBlock'
      ? `contextMappings › ${it.mappingTitle}`
      : it.type === 'nodeMappingBlock' || it.type === 'mapping'
        ? `${it.mappingTitle} › ${it.contextNode} › ${it.object}`
        : `contextNodes › ${it.nodeName}`;
    const preview = it.type === 'mappingBlock'
      ? `<contextMappings>\n    <!-- complete mapping and all children -->\n    <title>${it.mappingTitle}</title>\n</contextMappings>`
      : it.type === 'nodeMappingBlock'
        ? `<contextNodeMappings>\n    <!-- complete block and all children -->\n    <contextNode>${it.contextNode}</contextNode>\n    <object>${it.object}</object>\n</contextNodeMappings>`
        : it.type === 'contextNodeBlock'
          ? `<contextNodes>\n    <!-- complete node and all children -->\n    <title>${it.nodeName}</title>\n</contextNodes>`
          : isMapping
            ? `<contextAttributeMappings>\n    <contextAttribute>${name}</contextAttribute>\n    ${it.fieldInfo ? `<!-- ${it.fieldInfo} -->\n    ` : ''}...\n</contextAttributeMappings>`
            : `<contextAttributes>\n    <title>${name}</title>\n    ...\n</contextAttributes>`;
    const parentNote = isParentBlock
      ? `<div class="cdfix-parent-help"><strong>Full-block patch:</strong> ${esc(it.parentPatchMessage || '')}</div>`
      : '';
    const preserveNote = isUpdate && (it.preservedBaseFields || []).length
      ? `<div class="cdfix-parent-help"><strong>Base protected:</strong> Modified omits ${esc(it.preservedBaseFields.join(', '))}; Step 3 will preserve it from Base.</div>`
      : '';
    const changeDetails = isUpdate
      ? `<div class="detail-row"><span>Current Base value</span><code>${esc(it.beforeField || 'Existing XML definition')}</code></div>` +
        `<div class="detail-row"><span>Modified value</span><code>${esc(it.afterField || 'Modified XML definition')}</code></div>`
      : '';
    const badgeLabel = isParentBlock ? 'Required Parent Block' : isMapping ? 'Context Mapping' : 'Context Attribute';
    const badgeIcon = isParentBlock ? 'parentBlock' : isMapping ? 'mapping' : 'attribute';
    cdfDetail.innerHTML =
      `<div class="cdfix-detail-head">` +
        `<span class="cdfix-tbadge ${isMapping ? 'cdfix-tbadge-m' : 'cdfix-tbadge-n'}">${buttonIcon(badgeIcon)}${badgeLabel}</span>` +
        `<h4>${esc(name)}</h4><p>${isParentBlock ? 'Ready — Step 3 will copy the complete required block' : isUpdate ? 'Ready — Step 3 will replace the selected Base definition' : 'Ready to apply'}</p>` +
      `</div><div class="cdfix-detail-body">` +
        `<div class="detail-row"><span>Location</span><code>${esc(location)}</code></div>` +
        (it.fieldInfo ? `<div class="detail-row"><span>Source</span><code>${esc(it.fieldInfo)}</code></div>` : '') +
        changeDetails +
        `<div class="detail-row"><span>XML preview</span><pre class="detail-preview">${esc(preview)}</pre></div>` +
        parentNote + preserveNote +
      `</div>`;
    cdfDetail.scrollTop = 0;
    cdfDetail.classList.remove('context-flash');
    requestAnimationFrame(() => cdfDetail.classList.add('context-flash'));
    setTimeout(() => cdfDetail.classList.remove('context-flash'), 650);
    try { cdfDetail.focus({ preventScroll:true }); } catch (e) {}
    cdfHighlightTimeline(it, cdfReport.classList.contains('show'));
  }

  function cdfApplyFilters() {
    const query = (cdfSearch.value || '').trim().toLowerCase();
    _cdfCards.forEach(card => {
      const cb = card.querySelector('input[data-item]');
      const it = cb ? _cdfById.get(cb.dataset.item) : null;
      if (!it) return;
      const haystack = [it.attrName, it.attrTitle, it.mappingTitle, it.contextNode,
        it.object, it.nodeName, it.fieldInfo, it.beforeField, it.afterField, it.group].filter(Boolean).join(' ').toLowerCase();
      const filterMatch =
        _cdfFilter === 'all' ||
        (_cdfFilter === 'ready' && !it.parentPatch) ||
        (_cdfFilter === 'errors' && it.parentPatch) ||
        (_cdfFilter === 'updates' && it.changeKind === 'update') ||
        (_cdfFilter === 'mapping' && ['mapping','mappingBlock','nodeMappingBlock'].includes(it.type)) ||
        (_cdfFilter === 'nodeAttr' && ['nodeAttr','contextNodeBlock'].includes(it.type)) ||
        (_cdfFilter === 'selected' && cb.checked);
      card.hidden = !filterMatch || (query && !haystack.includes(query));
    });
    document.querySelectorAll('#cdfFieldList .cdfix-group').forEach(group => {
      const cards = [...group.querySelectorAll('.cdfix-card')];
      group.classList.toggle('is-filtered-empty', !cards.some(card => !card.hidden));
    });
  }

  function cdfRenderItems(items) {
    _cdfItems = items;
    _cdfById = new Map(items.map(it => [it.id, it]));
    $("cdfMetricAll").textContent = items.length;
    $("cdfMetricMappings").textContent = items.filter(it => ['mapping','mappingBlock','nodeMappingBlock'].includes(it.type)).length;
    $("cdfMetricNodes").textContent = items.filter(it => ['nodeAttr','contextNodeBlock'].includes(it.type)).length;
    $("cdfMetricErrors").textContent = items.filter(it => it.parentPatch).length;

    // Build groups
    const groups = {};
    for (const it of items) (groups[it.group] = groups[it.group] || []).push(it);

    // Legend
    const nM = items.filter(i => ['mapping','mappingBlock','nodeMappingBlock'].includes(i.type)).length;
    const nN = items.filter(i => ['nodeAttr','contextNodeBlock'].includes(i.type)).length;
    const actBar = $('cdfSelActions');
    if (actBar) {
      const old = actBar.querySelector('.cdfix-legend');
      if (old) old.remove();
      actBar.insertAdjacentHTML('beforeend',
        `<div class="cdfix-legend">` +
        (nM ? `<span class="cdfix-legend-item"><span class="cdfix-legend-dot" style="background:var(--teal)"></span>${nM} Context Mapping${nM>1?'s':''}</span>` : '') +
        (nN ? `<span class="cdfix-legend-item"><span class="cdfix-legend-dot" style="background:var(--purple)"></span>${nN} Context Attribute${nN>1?'s':''}</span>` : '') +
        `</div>`);
    }

    let html = '';
    for (const [grpKey, grpItems] of Object.entries(groups)) {
      const grpId = 'grp_' + grpKey.replace(/\W/g, '_');
      const mC = grpItems.filter(i => ['mapping','mappingBlock','nodeMappingBlock'].includes(i.type)).length;
      const nC = grpItems.filter(i => ['nodeAttr','contextNodeBlock'].includes(i.type)).length;
      const meta = [mC && `${mC} Context Mapping${mC>1?'s':''}`, nC && `${nC} Context Attribute${nC>1?'s':''}`].filter(Boolean).join(' · ');

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
        const isParentBlock = !!it.parentPatch;
        const isUpdate = it.changeKind === 'update';
        const isM  = ['mapping','mappingBlock','nodeMappingBlock'].includes(it.type);
        const name = esc(it.attrName || it.attrTitle || it.mappingTitle || it.nodeName || '');

        // Row 1 pieces
        const tbadge = isM
          ? `<span class="cdfix-tbadge cdfix-tbadge-m">${buttonIcon(isParentBlock ? 'parentBlock' : 'mapping')}${isParentBlock ? 'Required Parent Block' : 'Context Mapping'}</span>`
          : `<span class="cdfix-tbadge cdfix-tbadge-n">${buttonIcon(isParentBlock ? 'parentBlock' : 'attribute')}${isParentBlock ? 'Required Parent Block' : 'Context Attribute'}</span>`;
        const warn = isParentBlock
          ? `<span class="cdfix-parenttag" title="Step 3 copies this complete required block">Full block patch</span>`
          : isUpdate
            ? `<span class="cdfix-updatetag" title="Step 3 replaces the existing Base definition">Value change</span>`
          : `<span class="cdfix-readytag">Ready</span>`;
        const parentHelp = isParentBlock
          ? `<div class="cdfix-parent-help"><strong>Will be applied in Step 3:</strong> ` +
            `${esc(it.parentPatchMessage || 'The complete required block will be copied from Modified into Base.')}</div>`
          : isUpdate && (it.preservedBaseFields || []).length
            ? `<div class="cdfix-parent-help"><strong>Base protected:</strong> Preserving ${esc(it.preservedBaseFields.join(', '))} because Modified omits it.</div>`
            : '';

        // Row 2: location breadcrumb
        const segs = isM
          ? [it.mappingTitle, it.contextNode, it.object].filter(Boolean)
          : ['contextNodes', it.nodeName];
        const bc = segs.map((s, i) =>
          `<span class="cdfix-seg">${esc(s)}</span>` +
          (i < segs.length-1 ? `<span class="cdfix-sep">›</span>` : '')
        ).join('');

        // Row 3: field / hydration / role
        let r3 = '';
        if (isUpdate) {
          r3 = `<div class="cdfix-r3"><span class="cdfix-rlabel">Change</span>` +
            `<span class="cdfix-fval cdfix-fval-before">${esc(it.beforeField || 'Existing XML')}</span>` +
            `<span class="cdfix-sep">→</span>` +
            `<span class="cdfix-fval cdfix-fval-sf">${esc(it.afterField || 'Modified XML')}</span></div>`;
        } else if (isM && it.fieldInfo) {
          if (it.fieldInfo.startsWith('hydration ref:')) {
            const ref = esc(it.fieldInfo.replace('hydration ref:','').trim());
            r3 = `<div class="cdfix-r3"><span class="cdfix-rlabel">Hydration</span><span class="cdfix-fval cdfix-fval-hyd">${ref}</span></div>`;
          } else {
            r3 = `<div class="cdfix-r3"><span class="cdfix-rlabel">SF Field</span><span class="cdfix-fval cdfix-fval-sf">${esc(it.fieldInfo)}</span></div>`;
          }
        } else if (!isM && !isParentBlock) {
          r3 = `<div class="cdfix-r3"><span class="cdfix-fval-role">Declares this context attribute on the node</span></div>`;
        }

        html +=
          `<label class="cdfix-card" data-card-id="${esc(it.id)}" for="ci_${sid}">` +
            `<input type="checkbox" id="ci_${sid}" data-item="${esc(it.id)}" checked` +
            ` onchange="cdfUpdateGroupHeader('${grpId}');cdfUpdateSelCount()" />` +
            `<div class="cdfix-ci">` +
              `<div class="cdfix-r1">${tbadge}<span class="cdfix-cname">${name}</span>${warn}<span class="cdfix-modtag">${isUpdate ? 'Modified value' : 'Modified only'}</span></div>` +
              `<div class="cdfix-r2"><span class="cdfix-rlabel">Location</span>${bc}</div>` +
              r3 +
              parentHelp +
            `</div>` +
          `</label>`;
      }
      html += `</div></div>`;
    }
    cdfFieldList.innerHTML = html;
    _cdfCards = [...cdfFieldList.querySelectorAll('.cdfix-card')];
    _cdfItemCheckboxes = [...cdfFieldList.querySelectorAll('input[data-item]')];
    _cdfActiveCard = null;
    cdfApplyFilters();
    cdfUpdateSelCount();
    if (items.length) cdfShowDetail(items[0].id);
  }
  cdfFieldList.addEventListener('click', event => {
    const card = event.target.closest('.cdfix-card');
    if (card && cdfFieldList.contains(card)) cdfShowDetail(card.dataset.cardId);
  });

  window.cdfToggleGroup = function(grpId) {
    const el  = $(grpId);
    const arr = $(grpId + '_arrow');
    if (!el) return;
    const hidden = el.style.display === 'none';
    el.style.display = hidden ? '' : 'none';
    if (arr) arr.classList.toggle('open', hidden);
  };
  function cdfSetAllGroups(expanded) {
    document.querySelectorAll('#cdfFieldList .cdfix-group').forEach(group => {
      const body = group.querySelector('.cdfix-group-head + div');
      const arrow = group.querySelector('.cdfix-toggle-arrow');
      if (body) body.style.display = expanded ? '' : 'none';
      if (arrow) arrow.classList.toggle('open', expanded);
    });
  }
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
    _cdfItemCheckboxes.forEach(cb => { cb.checked = true; });
    document.querySelectorAll('#cdfFieldList .cdfix-group-check').forEach(cb => { cb.checked = true; cb.indeterminate = false; });
    cdfUpdateSelCount();
  };
  $("cdfSelNone").onclick = () => {
    _cdfItemCheckboxes.forEach(cb => { cb.checked = false; });
    document.querySelectorAll('#cdfFieldList .cdfix-group-check').forEach(cb => { cb.checked = false; cb.indeterminate = false; });
    cdfUpdateSelCount();
  };
  $("cdfExpandAll").onclick = () => cdfSetAllGroups(true);
  $("cdfCollapseAll").onclick = () => cdfSetAllGroups(false);
  let cdfSearchFrame;
  cdfSearch.oninput = () => {
    cancelAnimationFrame(cdfSearchFrame);
    cdfSearchFrame = requestAnimationFrame(cdfApplyFilters);
  };
  document.querySelectorAll('[data-cdf-filter]').forEach(btn => {
    btn.onclick = () => {
      _cdfFilter = btn.dataset.cdfFilter;
      document.querySelectorAll('[data-cdf-filter]').forEach(b => b.classList.toggle('active', b === btn));
      cdfApplyFilters();
    };
  });

  function cdfHighlightTimeline(item, shouldScroll) {
    const rows = [...cdfTimeline.querySelectorAll('.timeline-item')];
    rows.forEach(row => row.classList.remove('is-context-match'));
    if (!item || !rows.length) return;
    const tokens = [item.attrName,item.attrTitle,item.mappingTitle,item.nodeName,item.contextNode,item.object,
      item.beforeField,item.afterField].filter(value => String(value || '').trim().length > 2)
      .map(value => String(value).toLowerCase());
    let match = null, bestScore = 0;
    rows.forEach(row => {
      const text = row.textContent.toLowerCase();
      const score = tokens.reduce((total, token) => total + (text.includes(token) ? 1 : 0), 0);
      if (score > bestScore) { bestScore = score; match = row; }
    });
    if (!match) return;
    match.classList.add('is-context-match');
  }

  function paintCdfTimeline() {
    const visible = _cdfTimelineExpanded ? _cdfTimelineEntries : _cdfTimelineEntries.slice(0, 6);
    cdfTimeline.innerHTML = visible.map(line => {
      const kind = line.startsWith('✗') ? 'error' : line.startsWith('+') ? 'add' : line.startsWith('~') ? 'update' : 'skip';
      const icon = kind === 'error' ? '!' : kind === 'add' ? '+' : kind === 'update' ? '~' : '✓';
      const clean = line.replace(/^[+~✓✗]\s*/, '');
      const splitAt = clean.indexOf(':');
      const label = splitAt >= 0 ? clean.slice(0, splitAt) : (kind === 'add' ? 'Added' : kind === 'update' ? 'Updated' : kind === 'error' ? 'Error' : 'Skipped');
      const detail = splitAt >= 0 ? clean.slice(splitAt + 1).trim() : clean;
      return `<div class="timeline-item ${kind}"><span class="timeline-icon">${icon}</span>` +
        `<div class="timeline-copy"><strong>${esc(label)}</strong><span>${esc(detail)}</span></div></div>`;
    }).join('');
    cdfHighlightTimeline(_cdfActiveItem, false);
    cdfTimelineToggle.classList.toggle('hidden', _cdfTimelineEntries.length <= 6);
    cdfTimelineToggle.innerHTML = buttonIcon(_cdfTimelineExpanded ? 'collapse' : 'expand') +
      (_cdfTimelineExpanded ? 'Show quick view' : `Show all ${_cdfTimelineEntries.length} details`);
  }
  function renderCdfTimeline(report, data) {
    $("cdfReportAdded").textContent = (data.added || 0).toLocaleString();
    $("cdfReportUpdated").textContent = (data.updated || 0).toLocaleString();
    $("cdfReportSkipped").textContent = (data.skipped || 0).toLocaleString();
    $("cdfReportErrors").textContent = (data.errors || 0).toLocaleString();
    _cdfTimelineEntries = (report || '').split('\n').map(line => line.trim()).filter(line =>
      line.startsWith('+') || line.startsWith('~') || line.startsWith('✓') || line.startsWith('✗')
    );
    _cdfTimelineExpanded = false;
    if (!_cdfTimelineEntries.length) {
      cdfTimeline.innerHTML = '<div class="cdfix-detail-empty" style="min-height:100px"><p>No item-level changes were reported.</p></div>';
      cdfTimelineToggle.classList.add('hidden');
      return;
    }
    paintCdfTimeline();
  }
  cdfTimelineToggle.onclick = () => { _cdfTimelineExpanded = !_cdfTimelineExpanded; paintCdfTimeline(); };

  // ── Step 2: Analyze ──────────────────────────────────────────────────────
  cdfAnalyzeBtn.onclick = async () => {
    if (!cdfBase.value.trim() || !cdfMod.value.trim()) {
      setStatus(cdfAnalyzeStatus, "err", "Paste both Base and Modified XMLs first.");
      return;
    }
    busy(cdfAnalyzeBtn, "Analyzing…");
    cdfDiffCount.textContent = "…";
    [cdfRailAdded,cdfRailUpdated,cdfRailBaseOnly].forEach(el => { el.textContent = "…"; });
    cdfDiffIndicator.classList.remove("has-diffs");
    cdfSelectPanel.classList.remove("show");
    cdfBuildStep.classList.add("hidden");
    cdfReport.classList.remove("show");
    cdfDiagnostics.classList.remove("show");
    _cdfDiagnostics = null;

    const data = await postJSON("/api/cdfix/analyze", { base: cdfBase.value, modified: cdfMod.value });
    idle(cdfAnalyzeBtn);

    if (!data.ok) {
      cdfDiffCount.textContent = "—";
      [cdfRailAdded,cdfRailUpdated,cdfRailBaseOnly].forEach(el => { el.textContent = "—"; });
      setStatus(cdfAnalyzeStatus, "err", data.log || "Analysis failed.");
      return;
    }
    cdfRenderDiagnostics(data.diagnostics);
    if (!data.items || data.items.length === 0) {
      cdfDiffCount.textContent = "0";
      setStatus(cdfAnalyzeStatus, "ok", data.summary || "No differences found.");
      return;
    }

    cdfDiffCount.textContent = data.items.length.toLocaleString();
    cdfDiffIndicator.classList.add("has-diffs");
    setStatus(cdfAnalyzeStatus, "ok", data.summary);
    cdfSelHeadText.textContent = "Review Context Definition additions, value changes, and Required Parent Blocks";
    cdfRenderItems(data.items);
    cdfSelectPanel.classList.add("show");
    cdfBuildStep.classList.remove("hidden");
    cdfOut.value = ""; _lnRefresh.cdfOut();
    cdfBuildStatus.className = "status";
  };

  // ── Step 3: Build ────────────────────────────────────────────────────────
  cdfBuildBtn.onclick = async () => {
    const selectedIds = _cdfItemCheckboxes.filter(cb => cb.checked).map(cb => cb.dataset.item);
    if (!selectedIds.length) {
      setStatus(cdfBuildStatus, "err", "Select at least one change to include.");
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
    renderCdfTimeline(data.report, data);
    const errs = data.errors || 0;
    const parentBlocks = data.parentBlocks || 0;
    const parentNote = parentBlocks
      ? `, including ${parentBlocks} complete parent block${parentBlocks === 1 ? '' : 's'}`
      : '';
    const normalizedDefaults = data.normalizedDefaults || 0;
    const normalizedRootFields = data.normalizedRootFields || [];
    const normalizedTotal = normalizedDefaults + normalizedRootFields.length;
    const normalizationNote = normalizedTotal
      ? `; normalized ${normalizedTotal} API-incompatible serializer field${normalizedTotal === 1 ? '' : 's'}`
      : '';
    const msg = errs
      ? `Built with ${data.applied} change(s) applied · ${errs} error(s) — see report.`
      : `Done — ${data.added || 0} added and ${data.updated || 0} updated${parentNote}, ${data.skipped} already present${normalizationNote}. Use Copy to grab the result.`;
    setStatus(cdfBuildStatus, errs ? "info" : "ok", msg);
  };

  $("cdfCopyBtn").onclick      = (e) => copyFrom(cdfOut, e.currentTarget);
  $("cdfDownloadBtn").onclick  = () => download(cdfOut, "context-definition-patched.xml");

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
