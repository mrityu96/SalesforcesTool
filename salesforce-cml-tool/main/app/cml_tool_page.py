"""Embedded browser UI for the local CML tool."""

PAGE = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<link rel="icon" type="image/png" href="/favicon/favicon-96x96.png" sizes="96x96" />
<link rel="icon" type="image/svg+xml" href="/favicon/favicon.svg" />
<link rel="shortcut icon" href="/favicon/favicon.ico" />
<link rel="apple-touch-icon" sizes="180x180" href="/favicon/apple-touch-icon.png" />
<meta name="apple-mobile-web-app-title" content="CML Tool" />
<meta name="theme-color" content="#3B82F6" />
<link rel="manifest" href="/favicon/site.webmanifest" />
<title>CML Tool — Fetch, Deploy &amp; Compare</title>
<script>(function(){try{var t=localStorage.getItem('cml-theme')||'light';document.documentElement.setAttribute('data-theme',t);}catch(e){}})();</script>
<style>
  :root {
    color-scheme: light;
    --surface-page:#f4f7fb; --surface-card:#ffffff; --surface-subtle:#f8fafc;
    --surface-hover:#f1f5f9; --surface-control:#ffffff; --surface-nav:rgba(255,255,255,.82);
    --border:#d9e2ec; --border-strong:#c7d2e0;
    --text-primary:#172033; --text-secondary:#5b6b82; --text-muted:#7b889a;
    --color-primary:#2563eb; --color-primary-hover:#1d4ed8; --color-primary-soft:#eff6ff;
    --color-primary-border:#bfdbfe; --color-accent:#06b6d4; --color-accent-soft:#ecfeff;
    --color-success:#059669; --color-success-soft:#ecfdf5;
    --color-warning:#d97706; --color-warning-soft:#fff7ed;
    --color-danger:#dc2626; --color-danger-soft:#fef2f2;
    --radius-control:10px; --radius-card:16px; --radius-pill:999px;
    --focus-ring:0 0 0 3px #dbeafe;
    --shadow-card:0 4px 18px rgba(23,32,51,.06);
    --shadow-floating:0 8px 28px rgba(23,32,51,.10);
    --bg:var(--surface-page); --panel:var(--surface-card); --gutter:var(--surface-subtle);
    --input-bg:var(--surface-control); --line:var(--border); --text:var(--text-primary);
    --muted:var(--text-secondary); --gutter-text:var(--text-muted); --comment:#8b98aa;
    --accent:var(--color-primary); --accent-strong:var(--color-accent);
    --green:var(--color-success); --red:var(--color-danger); --purple:#7c3aed;
    --amber:var(--color-warning); --teal:var(--color-accent); --on-accent:#ffffff;
    --radius:var(--radius-card);
    --ok-bg:color-mix(in srgb,var(--green) 11%,var(--panel)); --ok-text:#08734f;
    --err-bg:color-mix(in srgb,var(--red) 10%,var(--panel)); --err-text:#b4233f;
    --info-bg:var(--color-primary-soft); --info-text:#1e40af;
    --teal-bg:color-mix(in srgb,var(--teal) 10%,var(--panel)); --teal-text:#07657c;
    --chg-bg:color-mix(in srgb,var(--purple) 14%,var(--panel));
    --del-bg:color-mix(in srgb,var(--red) 12%,var(--panel));
    --ins-bg:color-mix(in srgb,var(--teal) 13%,var(--panel));
    --chg-line:var(--purple); --del-line:var(--red); --ins-line:var(--teal);
    --shadow:var(--shadow-card);
  }
  html[data-theme="dark"] {
    color-scheme: dark;
    --surface-page:#08101f; --surface-card:#101a2d; --surface-subtle:#152137;
    --surface-hover:#1b2942; --surface-control:#0c1628; --surface-nav:rgba(16,26,45,.86);
    --border:#2d3b55; --border-strong:#40506c;
    --text-primary:#f3f7ff; --text-secondary:#b5c0d3; --text-muted:#8290a8;
    --color-primary:#60a5fa; --color-primary-hover:#93c5fd; --color-primary-soft:#12294a;
    --color-primary-border:#315f91; --color-accent:#22d3ee; --color-accent-soft:#10303b;
    --color-success:#34d399; --color-success-soft:#102d27;
    --color-warning:#fbbf24; --color-warning-soft:#332712;
    --color-danger:#fb7185; --color-danger-soft:#351822;
    --focus-ring:0 0 0 3px rgba(96,165,250,.25);
    --shadow-card:0 5px 22px rgba(0,0,0,.22);
    --shadow-floating:0 12px 34px rgba(0,0,0,.38);
    --bg:var(--surface-page); --panel:var(--surface-card); --gutter:var(--surface-subtle);
    --input-bg:var(--surface-control); --line:var(--border); --text:var(--text-primary);
    --muted:var(--text-secondary); --gutter-text:var(--text-muted); --comment:#929db2;
    --accent:var(--color-primary); --accent-strong:var(--color-accent);
    --green:var(--color-success); --red:var(--color-danger);
    --purple:#a78bfa; --amber:var(--color-warning); --teal:var(--color-accent);
    --ok-bg:color-mix(in srgb,var(--green) 13%,var(--panel)); --ok-text:#a7f3d0;
    --err-bg:color-mix(in srgb,var(--red) 13%,var(--panel)); --err-text:#fecdd3;
    --info-bg:color-mix(in srgb,var(--accent) 13%,var(--panel)); --info-text:#d9dcff;
    --teal-bg:color-mix(in srgb,var(--teal) 12%,var(--panel)); --teal-text:#a5f3fc;
    --shadow:var(--shadow-card);
  }
  * { box-sizing: border-box; }
  html,body { width:100%; height:100%; max-width:100%; overflow:hidden; }
  body {
    margin:0; font-family:Inter,-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;
    min-height:100vh;
    background:
      radial-gradient(900px 500px at 84% 2%,rgba(56,189,248,.24),transparent 64%),
      radial-gradient(720px 460px at 8% 12%,rgba(96,165,250,.16),transparent 66%),
      linear-gradient(180deg,#dff2ff 0%,#eaf7ff 46%,#d8edf9 100%);
    color:var(--text); line-height:1.5;
    transition:background-color .2s ease,color .2s ease;
  }
  html[data-theme="dark"] body {
    background:
      radial-gradient(900px 500px at 84% 2%,rgba(14,165,233,.16),transparent 64%),
      radial-gradient(720px 460px at 8% 12%,rgba(37,99,235,.12),transparent 66%),
      linear-gradient(180deg,#071a33 0%,#0a203d 48%,#071426 100%);
  }
  body::before,body::after { content:""; position:fixed; left:-5%; right:-5%;
    pointer-events:none; z-index:0; }
  body::before { top:0; height:222px; filter:blur(5px); transform:scale(1.02);
    transform-origin:center top;
    background:linear-gradient(180deg,rgba(186,230,253,.32),rgba(96,165,250,.19));
    clip-path:polygon(0 100%,0 80%,7% 72%,14% 55%,21% 69%,30% 39%,39% 65%,49% 46%,58% 68%,68% 35%,77% 61%,87% 31%,94% 52%,100% 43%,100% 100%); }
  body::after {
    bottom:-3%; height:clamp(140px,20vh,200px);
    background:linear-gradient(165deg,rgba(100,116,139,.13),rgba(56,189,248,.09));
    clip-path:polygon(0 84%,8% 67%,16% 79%,25% 56%,34% 76%,43% 62%,52% 82%,62% 55%,71% 75%,80% 49%,89% 72%,100% 57%,100% 100%,0 100%); }
  html[data-theme="dark"] body::after {
    background:linear-gradient(165deg,rgba(71,85,105,.22),rgba(14,116,144,.13)); }
  html[data-theme="dark"] body::before {
    filter:blur(6px);
    background:linear-gradient(180deg,rgba(31,91,153,.62),rgba(8,42,84,.38)); }
  button,input,select,textarea { font:inherit; }
  [hidden] { display:none !important; }
  .sr-only { position:absolute !important; width:1px !important; height:1px !important; padding:0 !important;
    margin:-1px !important; overflow:hidden !important; clip:rect(0,0,0,0) !important;
    white-space:nowrap !important; border:0 !important; }

  /* ── App shell and compact header ─────────────────────────────── */
  .app-shell { position:relative; z-index:1; height:100vh; min-height:0; display:flex; flex-direction:column; overflow:hidden; }
  .app-shell::before,.app-shell::after { content:""; position:fixed; left:-1%; right:-1%; bottom:-2px;
    pointer-events:none; z-index:0; transform:translateZ(0); }
  .app-shell::before { height:clamp(90px,16vh,160px); background:rgba(14,116,144,.14);
    clip-path:polygon(0 100%,0 82%,1% 82%,2.2% 52%,3.4% 82%,5% 82%,6.6% 25%,8.2% 82%,11% 82%,12.3% 58%,13.6% 82%,17% 82%,18.8% 38%,20.6% 82%,24% 82%,25.3% 63%,26.6% 82%,31% 82%,32.7% 30%,34.4% 82%,39% 82%,40.4% 55%,41.8% 82%,47% 82%,48.8% 22%,50.6% 82%,56% 82%,57.4% 59%,58.8% 82%,64% 82%,65.8% 34%,67.6% 82%,73% 82%,74.4% 61%,75.8% 82%,81% 82%,82.8% 27%,84.6% 82%,89% 82%,90.5% 54%,92% 82%,96% 82%,97.4% 36%,98.8% 82%,100% 82%,100% 100%); }
  .app-shell::after { height:clamp(74px,13vh,132px); background:rgba(15,92,112,.18);
    clip-path:polygon(0 100%,0 88%,
      2.2% 88%,3.1% 73%,2.8% 73%,3.6% 58%,3.3% 58%,4% 34%,4.7% 58%,4.4% 58%,5.2% 73%,4.9% 73%,5.8% 88%,
      10.8% 88%,11.7% 72%,11.4% 72%,12.2% 57%,11.9% 57%,12.7% 40%,13.5% 57%,13.2% 57%,14% 72%,13.7% 72%,14.6% 88%,
      20% 88%,21% 69%,20.6% 69%,21.6% 50%,21.2% 50%,22.1% 25%,23% 50%,22.6% 50%,23.6% 69%,23.2% 69%,24.2% 88%,
      39% 88%,40% 71%,39.6% 71%,40.6% 54%,40.2% 54%,41.1% 32%,42% 54%,41.6% 54%,42.6% 71%,42.2% 71%,43.2% 88%,
      61% 88%,62% 68%,61.6% 68%,62.6% 48%,62.2% 48%,63.1% 20%,64% 48%,63.6% 48%,64.6% 68%,64.2% 68%,65.2% 88%,
      82% 88%,83% 70%,82.6% 70%,83.6% 52%,83.2% 52%,84.1% 29%,85% 52%,84.6% 52%,85.6% 70%,85.2% 70%,86.2% 88%,
      93% 88%,94% 72%,93.6% 72%,94.6% 57%,94.2% 57%,95.1% 39%,96% 57%,95.6% 57%,96.6% 72%,96.2% 72%,97.2% 88%,
      100% 88%,100% 100%); }
  html[data-theme="dark"] .app-shell::before { background:rgba(14,116,144,.20); }
  html[data-theme="dark"] .app-shell::after { background:rgba(8,70,88,.30); }
  .app-header { min-height:76px; padding:10px clamp(16px,2.5vw,40px); display:grid;
    grid-template-columns:minmax(370px,1fr) auto minmax(190px,1fr); align-items:center; gap:20px;
    border-bottom:0; background:color-mix(in srgb,#e0f2fe 46%,transparent);
    box-shadow:inset 0 -1px 0 rgba(255,255,255,.34),0 8px 30px rgba(30,64,175,.06);
    backdrop-filter:blur(22px) saturate(145%); -webkit-backdrop-filter:blur(22px) saturate(145%); z-index:40; }
  html[data-theme="dark"] .app-header { background:rgba(7,26,51,.46);
    box-shadow:inset 0 -1px 0 rgba(125,211,252,.14),0 10px 34px rgba(0,0,0,.14); }
  .brand-cluster { min-width:0; display:flex; align-items:center; gap:14px; }
  .brand { display:flex; align-items:center; gap:10px; color:var(--text); text-decoration:none; min-width:0; }
  .brand-mark { width:38px; height:38px; flex:0 0 38px; display:grid; place-items:center; border-radius:11px;
    background:linear-gradient(135deg,var(--accent),var(--accent-strong));
    box-shadow:0 7px 18px color-mix(in srgb,var(--accent) 22%,transparent); }
  .brand-mark svg { width:22px; fill:var(--on-accent); }
  .brand-copy { min-width:0; line-height:1.12; }
  .brand-copy strong,.credit { display:block; }
  .brand-copy strong { font-size:15px; font-weight:780; line-height:1.1; white-space:nowrap; }
  .credit { margin:4px 0 0; color:var(--text-muted); font-size:10.5px; line-height:1.15; white-space:nowrap; }
  .credit .heart { width:11px; height:11px; vertical-align:-1px; fill:var(--accent); stroke:var(--accent);
    stroke-width:2; stroke-linecap:round; stroke-linejoin:round; }
  .header-links { display:flex; align-items:center; gap:5px; margin-left:4px; }
  .header-link { border:0; background:transparent; color:var(--text-secondary); padding:6px 5px;
    display:inline-flex; align-items:center; gap:7px; font-size:14px; font-weight:650;
    text-decoration:none; cursor:pointer; white-space:nowrap; }
  .donate-link,.about-link,.donate-link span,.about-link span { font-size:14px; line-height:18px; }
  .header-link svg { width:18px; height:18px; fill:none; stroke:currentColor; stroke-width:1.9;
    stroke-linecap:round; stroke-linejoin:round; }
  .about-link svg { color:#0ea5e9; }
  .header-link:hover { color:var(--accent); }
  .header-link + .header-link::before { content:"·"; color:var(--text-muted); margin-right:8px; }
  .nav-island { min-width:0; min-height:50px; justify-self:center; padding:5px; border:1px solid color-mix(in srgb,var(--line) 72%,transparent);
    border-radius:16px; background:var(--surface-nav); box-shadow:var(--shadow-floating);
    backdrop-filter:blur(14px); -webkit-backdrop-filter:blur(14px); }
  .side-menu,.tabs { display:flex; align-items:center; gap:6px; min-width:0; margin:0; padding:0; }
  .side-nav,.tab { width:auto; min-height:40px; border:0; display:flex; align-items:center; gap:8px; padding:9px 14px;
    border-radius:10px; background:transparent; color:var(--text-secondary); font-size:13.5px;
    font-weight:700; white-space:nowrap; cursor:pointer; transition:background .16s,color .16s,box-shadow .16s; }
  .side-nav:hover,.tab:hover { color:var(--text); background:var(--color-primary-soft); }
  .side-nav.active,.tab.active { color:#fff; background:linear-gradient(135deg,#3b82f6,#06b6d4);
    box-shadow:0 5px 14px color-mix(in srgb,var(--accent) 25%,transparent); }
  .nav-icon { width:19px; height:19px; display:grid; place-items:center; flex:0 0 19px; }
  .nav-icon svg { width:18px; height:18px; fill:none; stroke:currentColor; stroke-width:1.9;
    stroke-linecap:round; stroke-linejoin:round; }
  .about-link { border:0; background:transparent; color:var(--text-muted); text-decoration:none;
    font-size:14px; line-height:18px; font-weight:650; cursor:pointer; }
  .about-link:hover { color:var(--accent); }
  .donate-link { color:var(--accent); }
  .donate-wrap { position:relative; }
  .donate-options { position:absolute; z-index:60; top:calc(100% + 8px); left:0; width:190px;
    display:grid; gap:5px; padding:7px; border:1px solid var(--line); border-radius:12px;
    background:var(--panel); box-shadow:var(--shadow-floating); }
  .donate-options[hidden] { display:none; }
  .donate-option { width:100%; display:flex; align-items:center; gap:9px; padding:8px 10px;
    border:1px solid transparent; border-radius:9px; background:transparent; color:var(--text);
    font-size:12px; font-weight:700; text-align:left; text-decoration:none; cursor:pointer; }
  .donate-option:hover:not(:disabled) { border-color:var(--accent); background:var(--gutter); }
  .donate-option:disabled { color:var(--muted); cursor:not-allowed; opacity:.58; }
  .payment-icon { width:27px; height:22px; flex:0 0 27px; display:grid; place-items:center;
    border:1px solid currentColor; border-radius:6px; font-size:8px; font-weight:900;
    letter-spacing:-.03em; }
  .razorpay-icon { font-size:14px; font-style:italic; }
  .donate-dialog { width:min(520px,calc(100vw - 28px)); max-width:100%; padding:0;
    border:1px solid var(--line); border-radius:18px; background:var(--panel);
    color:var(--text); }
  .donate-dialog::backdrop { background:rgba(9,14,26,.68); }
  .donate-dialog-body { padding:22px; }
  .donate-dialog-head { display:flex; align-items:flex-start; justify-content:space-between; gap:16px; }
  .donate-dialog h2 { margin:0; font-size:20px; }
  .donate-dialog p { color:var(--muted); font-size:13px; }
  .donate-dialog .disclaimer { padding:10px 12px; border-radius:10px; background:var(--gutter);
    font-size:11px; line-height:1.55; }
  .donate-qr { display:block; width:min(330px,100%); max-height:54vh; object-fit:contain;
    margin:17px auto 0; border:1px solid var(--line); border-radius:12px; background:#fff; }
  .donate-actions { display:flex; align-items:center; gap:9px; flex-wrap:wrap; margin-top:18px; }
  .upi-note { margin:10px 0 0; font-size:11px !important; }

  /* ── Main area ────────────────────────────────────────────────── */
  .app-main { position:relative; z-index:1; min-width:0; min-height:0; flex:1 1 auto; display:flex; flex-direction:column;
    overflow-y:auto; overflow-x:hidden; scrollbar-gutter:stable; }
  .app-main::before,.app-main::after { content:""; position:absolute; top:-76px; left:-4%; right:-4%;
    height:250px; pointer-events:none; z-index:0; transform:translateZ(0); }
  .app-main::before {
    background:linear-gradient(180deg,rgba(125,211,252,.22),rgba(59,130,246,.12));
    filter:blur(3px);
    clip-path:polygon(0 100%,0 88%,8% 74%,16% 81%,25% 57%,34% 77%,44% 48%,54% 78%,64% 59%,73% 80%,83% 45%,92% 70%,100% 55%,100% 100%); }
  .app-main::after {
    top:-60px; height:268px;
    background:linear-gradient(180deg,rgba(56,189,248,.15),rgba(37,99,235,.09));
    filter:blur(1.5px);
    clip-path:polygon(0 100%,0 94%,7% 80%,15% 88%,23% 66%,31% 85%,40% 58%,49% 87%,58% 69%,67% 89%,76% 62%,85% 84%,93% 64%,100% 77%,100% 100%); }
  html[data-theme="dark"] .app-main::before {
    background:linear-gradient(180deg,rgba(20,78,138,.43),rgba(7,40,78,.34)); }
  html[data-theme="dark"] .app-main::after {
    background:linear-gradient(180deg,rgba(12,66,119,.42),rgba(5,31,63,.45)); }
  .topbar,.wrap { position:relative; z-index:1; }
  .topbar { display:flex; align-items:flex-end; justify-content:space-between; gap:20px;
    padding:11px clamp(18px,1.7vw,24px) 10px; position:relative; min-height:48px; }
  .eyebrow { color:var(--muted); font-size:10px; font-weight:800; letter-spacing:.12em; text-transform:uppercase; margin-bottom:4px; }
  h1 { font-size:clamp(22px,2vw,30px); letter-spacing:-.03em; margin:0 0 3px; }
  .sub { color:var(--muted); font-size:13px; margin:0; }
  .top-actions { justify-self:end; display:flex; align-items:center; justify-content:flex-end; gap:10px; flex-shrink:0; }
  .local-badge { display:inline-flex; align-items:center; gap:7px; padding:6px 4px;
    color:var(--text-secondary); font-size:10px; font-weight:700; white-space:nowrap; }
  .live-dot { width:7px; height:7px; border-radius:50%; background:var(--green);
    box-shadow:0 0 0 4px color-mix(in srgb,var(--green) 14%,transparent); }
  .theme-toggle { min-width:0; padding:6px 8px; border-color:transparent; background:transparent; }
  .theme-toggle svg { width:17px; height:17px; fill:none; stroke:currentColor; stroke-width:1.9;
    stroke-linecap:round; stroke-linejoin:round; }
  html[data-theme="dark"] .header-link svg,
  html[data-theme="dark"] .nav-icon,
  html[data-theme="dark"] .theme-toggle svg,
  html[data-theme="dark"] .workspace-icon svg,
  html[data-theme="dark"] .label-with-icon svg,
  html[data-theme="dark"] .control-icon {
    color:#7dd3fc;
    filter:drop-shadow(0 0 5px rgba(56,189,248,.62)); }
  html[data-theme="dark"] .side-nav.active .nav-icon { color:#e0f2fe;
    filter:drop-shadow(0 0 6px rgba(125,211,252,.82)); }
  .wrap { width:100%; padding:0 clamp(18px,1.7vw,24px) 64px; }

  /* ── Panels ───────────────────────────────────────────────────── */
  .view-panel { display:none; }
  .view-panel.active { display:block; }
  .card { background:color-mix(in srgb,var(--panel) 94%,transparent); border:1px solid color-mix(in srgb,var(--line) 76%,transparent); border-radius:var(--radius);
    padding:clamp(16px,1.5vw,24px); box-shadow:var(--shadow); margin-bottom:18px; }
  .card-head { display:flex; align-items:flex-start; justify-content:space-between; gap:14px;
    padding-bottom:16px; margin-bottom:18px; border-bottom:1px solid var(--line); }
  .card-title { display:flex; align-items:flex-start; gap:11px; min-width:0; }
  .step-dot { width:30px; height:30px; flex:0 0 30px; display:grid; place-items:center; border-radius:9px;
    background:linear-gradient(135deg,var(--accent),var(--accent-strong)); color:var(--on-accent);
    font-size:12px; font-weight:800; box-shadow:0 7px 16px color-mix(in srgb,var(--accent) 22%,transparent); }
  .card-title h2 { margin:0; font-size:18px; letter-spacing:-.015em; }
  .card-title p { margin:3px 0 0; color:var(--muted); font-size:12.5px; }

  /* ── Connection strip ─────────────────────────────────────────── */
  .connection-card { position:relative; z-index:30; padding:0; border:0; background:transparent; box-shadow:none; }
  .conn-strip { display:grid; grid-template-columns:minmax(0,1fr) minmax(0,1fr);
    gap:12px; align-items:start; }
  .conn-strip > .field { max-width:100%; }
  .conn-strip > .reload-field { grid-column:1 / -1; justify-self:start; }
  .org-workspace { min-width:0; display:flex; flex-direction:column; gap:8px; padding:14px;
    border:1px solid color-mix(in srgb,var(--line) 76%,transparent); border-radius:var(--radius-card);
    background:color-mix(in srgb,var(--panel) 94%,transparent); box-shadow:var(--shadow-card);
    backdrop-filter:blur(10px); -webkit-backdrop-filter:blur(10px); }
  .org-workspace:has(.version-picker.open),.org-workspace:has(.org-picker.open) { z-index:2; }
  .workspace-head { display:flex; align-items:center; justify-content:space-between; gap:12px; }
  .workspace-title { min-width:0; display:flex; align-items:center; gap:9px; }
  .workspace-icon { width:36px; height:36px; flex:0 0 36px; display:grid; place-items:center;
    border-radius:10px; color:var(--accent); background:var(--color-primary-soft); }
  .target-workspace .workspace-icon { color:var(--purple); background:color-mix(in srgb,var(--purple) 10%,var(--panel)); }
  .workspace-icon svg { width:20px; height:20px; fill:none; stroke:currentColor; stroke-width:1.9; }
  .workspace-title strong { display:block; font-size:16px; line-height:1.25; letter-spacing:-.01em; text-transform:none; }
  .workspace-title span { display:block; color:var(--text-muted); font-size:11px; }
  .workspace-org-id { flex:none; color:var(--text-secondary); font:500 12px "JetBrains Mono",ui-monospace,monospace; }
  .field { min-width:0; max-width:100%; }
  label { display:block; font-size:11px; color:var(--text-secondary); margin-bottom:6px;
    text-transform:uppercase; letter-spacing:.055em; font-weight:750; }
  .label-with-icon { display:flex; align-items:center; gap:6px; }
  .label-with-icon svg,.control-icon { width:16px; height:16px; flex:none; fill:none;
    stroke:currentColor; stroke-width:1.9; stroke-linecap:round; stroke-linejoin:round; }
  select,input { width:100%; background:var(--input-bg); color:var(--text); border:1px solid var(--line);
    border-radius:var(--radius-control); min-height:46px; padding:10px 15px; font-size:14px; outline:none;
    transition:border-color .16s,box-shadow .16s,background .16s; }
  select:hover,input:hover { border-color:var(--border-strong); }
  select:focus,input:focus { border-color:var(--accent); box-shadow:var(--focus-ring); }
  select:disabled,input:disabled { opacity:.62; cursor:not-allowed; background:var(--surface-subtle); }
  .org-picker { position:relative; width:100%; }
  .org-trigger { width:100%; min-height:46px; padding:9px 13px; border:1px solid var(--line);
    border-radius:var(--radius-control); background:var(--input-bg); color:var(--text);
    display:flex; align-items:center; gap:9px; text-align:left; cursor:pointer; }
  .org-trigger:hover { border-color:var(--border-strong); }
  .org-trigger:focus-visible,.org-picker.open .org-trigger { border-color:var(--accent);
    box-shadow:var(--focus-ring); outline:none; }
  .org-trigger:disabled { opacity:.62; cursor:not-allowed; background:var(--surface-subtle); }
  .org-trigger svg,.org-option svg { width:17px; height:17px; flex:none; fill:none; stroke:var(--accent);
    stroke-width:1.9; stroke-linecap:round; stroke-linejoin:round; }
  .org-trigger-copy { flex:1; min-width:0; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; font-size:14px; }
  .org-menu { position:absolute; z-index:56; top:calc(100% + 7px); left:0; right:0; max-height:280px;
    overflow:auto; padding:7px; border:1px solid var(--line); border-radius:12px;
    background:var(--panel); box-shadow:0 12px 30px rgba(23,32,51,.16); }
  .org-option { width:100%; padding:9px 10px; border:0; border-radius:9px; color:var(--text);
    background:transparent; display:flex; align-items:center; gap:9px; text-align:left; cursor:pointer; }
  .org-option:hover,.org-option.selected { background:var(--color-primary-soft); }
  .org-option-copy { min-width:0; }
  .org-option-name { display:block; font-size:13px; font-weight:700; }
  .org-option-meta { display:block; color:var(--text-muted); font-size:10.5px; overflow:hidden;
    text-overflow:ellipsis; white-space:nowrap; }
  textarea { width:100%; background:var(--input-bg); color:var(--text); border:1px solid var(--line);
    border-radius:14px; padding:10px 13px; font-size:12.5px; outline:none;
    font-family:"JetBrains Mono","Fira Code",ui-monospace,"SF Mono",Menlo,Consolas,monospace;
    min-height:320px; resize:vertical; white-space:pre; tab-size:2;
    transition:border-color .16s,box-shadow .16s; }
  textarea:focus { border-color:var(--accent); box-shadow:0 0 0 4px color-mix(in srgb,var(--accent) 16%,transparent); }

  /* searchable exact-version picker */
  .combo { display:block; }
  select[size] { padding:0; height:auto; border-radius:12px; }
  select[size] option { padding:7px 12px; border-bottom:1px solid var(--line); }
  select[size] option:checked { background:var(--accent); color:#fff; }
  .version-picker { position:relative; width:100%; }
  .version-trigger { width:100%; min-height:46px; padding:9px 13px; border:1px solid var(--line);
    border-radius:var(--radius-control); background:var(--input-bg); color:var(--text);
    display:flex; align-items:center; gap:9px; text-align:left; cursor:pointer; }
  .version-trigger:hover { border-color:var(--border-strong); }
  .version-trigger:focus-visible,.version-picker.open .version-trigger { border-color:var(--accent);
    box-shadow:var(--focus-ring); outline:none; }
  .version-trigger:disabled { opacity:.62; cursor:not-allowed; background:var(--surface-subtle); }
  .version-trigger > svg { width:17px; height:17px; flex:none; fill:none; stroke:var(--accent);
    stroke-width:1.9; stroke-linecap:round; stroke-linejoin:round; }
  .version-trigger-copy { min-width:0; flex:1; overflow:hidden; text-overflow:ellipsis; white-space:nowrap;
    font-size:14px; }
  .version-chevron { color:var(--text-muted); transition:transform .16s; }
  .version-picker.open .version-chevron { transform:rotate(180deg); }
  .version-menu { position:absolute; z-index:55; top:calc(100% + 7px); left:0; right:0; padding:7px;
    border:1px solid var(--line); border-radius:12px; background:var(--panel);
    box-shadow:0 12px 30px rgba(23,32,51,.16); }
  .version-search-wrap { position:relative; margin-bottom:6px; }
  .version-search-wrap > svg { position:absolute; left:12px; top:50%; width:16px; height:16px;
    transform:translateY(-50%); fill:none; stroke:var(--text-muted); stroke-width:1.9; }
  .version-search { min-height:40px; padding-left:37px; }
  .version-options { max-height:300px; overflow:auto; display:grid; gap:3px; }
  .version-option { width:100%; padding:9px 10px; border:0; border-radius:9px; color:var(--text);
    background:transparent; display:flex; align-items:center; justify-content:space-between; gap:10px;
    text-align:left; cursor:pointer; }
  .version-option:hover,.version-option.active { background:color-mix(in srgb,var(--accent) 7%,var(--panel)); }
  .version-option.selected { background:var(--color-primary-soft); }
  .version-option-copy { min-width:0; }
  .version-option-name { display:block; overflow:hidden; text-overflow:ellipsis; white-space:nowrap;
    font-size:13px; font-weight:700; }
  .version-option-meta { display:block; color:var(--text-muted); font-size:11px; margin-top:2px; }
  .version-empty { padding:14px 10px; color:var(--text-muted); font-size:12px; text-align:center; }
  .combo-selected { display:none !important; }
  .runtime-badge { flex:none; display:inline-flex; align-items:center; gap:4px; padding:3px 8px;
    border:1px solid currentColor; border-radius:var(--radius-pill); font-size:9.5px; font-weight:800; }
  .runtime-badge.active { color:var(--ok-text); background:var(--ok-bg); }
  .runtime-badge.inactive { color:var(--text-secondary); background:var(--surface-subtle); }
  .meta { color:var(--muted); font-size:11.5px; }

  /* ── Buttons ──────────────────────────────────────────────────── */
  button { font-family:inherit; }
  .btn-row { display:flex; gap:10px; flex-wrap:wrap; align-items:center; margin-top:14px; }
  .btn { min-height:44px; border:1px solid transparent; border-radius:var(--radius-control);
    padding:10px 18px; font-size:13.5px; font-weight:700;
    cursor:pointer; transition:transform .16s ease,background .16s ease,border-color .16s ease,box-shadow .16s ease;
    width:auto; white-space:nowrap; display:inline-flex; align-items:center; justify-content:center; gap:8px; }
  .btn svg { width:17px; height:17px; flex:none; }
  .btn:disabled { opacity:.46; cursor:not-allowed; box-shadow:none; }
  .btn:hover:not(:disabled) { transform:translateY(-1px); box-shadow:0 8px 18px rgba(37,99,235,.20); }
  .btn:active:not(:disabled) { box-shadow:none; }
  .btn-primary { background:linear-gradient(135deg,#3b82f6,#06b6d4); color:var(--on-accent);
    box-shadow:0 5px 14px color-mix(in srgb,var(--accent) 23%,transparent); }
  .btn-green { background:linear-gradient(135deg,#059669,#14b8a6); color:#fff;
    box-shadow:0 5px 14px color-mix(in srgb,var(--green) 20%,transparent); }
  .btn-purple { background:linear-gradient(135deg,var(--purple),#9333ea); color:#fff;
    box-shadow:0 5px 14px color-mix(in srgb,var(--purple) 20%,transparent); }
  .btn-danger { background:linear-gradient(135deg,#dc2626,#f97316); color:#fff;
    box-shadow:0 5px 14px color-mix(in srgb,var(--red) 20%,transparent); }
  .ghost { background:var(--panel); border:1px solid var(--line); color:var(--text);
    display:inline-flex; align-items:center; justify-content:center; gap:7px; font-weight:650;
    border-radius:var(--radius-control); min-height:36px; padding:7px 12px; font-size:11px; cursor:pointer;
    transition:background .16s,border-color .16s,color .16s;
    width:auto; white-space:nowrap; }
  .ghost:hover { background:color-mix(in srgb,var(--accent) 9%,var(--panel)); border-color:var(--accent); color:var(--accent); }
  button:focus-visible { outline:3px solid color-mix(in srgb,var(--accent) 35%,transparent); outline-offset:2px; }
  .linklike { background:none; border:none; color:var(--accent); font-weight:600; cursor:pointer;
    padding:4px 6px; font-size:12px; border-radius:6px; }
  .linklike:hover { background:color-mix(in srgb,var(--accent) 10%,transparent); }
  .linklike:disabled { opacity:.45; cursor:not-allowed; background:none; }

  /* Desktop CML actions */
  .cml-actions { margin-top:18px; }
  .fetch-header-action { flex:none; align-self:center; }
  .deploy-panel { display:grid; grid-template-columns:minmax(250px,1fr) minmax(300px,1fr) max-content;
    gap:14px; align-items:start; padding:14px; border:1px solid var(--line);
    border-radius:var(--radius-card); background:var(--surface-subtle); min-width:0; }
  .deploy-panel .field select { width:100% !important; min-height:44px; }
  .deploy-panel > .field > label { min-height:17px; }
  .deploy-action-stack { display:flex; flex-direction:column; align-items:stretch; gap:9px; padding-top:23px; }
  .cml-main-action { min-width:166px; min-height:46px; padding:11px 22px; font-size:13px;
    display:inline-flex; align-items:center; justify-content:center; gap:9px; }
  .cml-main-action svg { width:17px; height:17px; flex:none; }
  .restore-action { min-width:166px; min-height:38px; padding:8px 14px; font-size:11px;
    display:inline-flex; align-items:center; justify-content:center; gap:9px; }
  .restore-action svg { width:15px; height:15px; flex:none; }
  .restore-action { color:var(--color-danger); border-color:color-mix(in srgb,var(--red) 35%,var(--line)); }
  .restore-action:hover { color:var(--color-danger); border-color:var(--color-danger);
    background:var(--color-danger-soft); }

  /* ── Status / conn ────────────────────────────────────────────── */
  .conn { display:none; margin:0 0 16px; padding:11px 16px; border-radius:12px; font-size:13px;
    background:var(--err-bg); border:1px solid var(--red); color:var(--err-text); }
  .conn.show { display:flex; align-items:center; gap:8px; }
  .status { margin-top:16px; font-size:13px; padding:13px 16px; border-radius:14px; display:none;
    white-space:pre-wrap; font-family:"JetBrains Mono","Fira Code",ui-monospace,"SF Mono",Menlo,monospace; }
  .status.show { display:block; }
  .status.ok { background:var(--ok-bg); border:1px solid var(--green); color:var(--ok-text); }
  .status.err { background:var(--err-bg); border:1px solid var(--red); color:var(--err-text); }
  .status.info { background:var(--info-bg); border:1px solid var(--accent); color:var(--info-text); }
  .spinner { display:inline-block; width:13px; height:13px; border:2px solid rgba(128,128,128,.35);
    border-top-color:#fff; border-radius:50%; animation:spin .7s linear infinite; vertical-align:-2px; margin-right:6px; }
  @keyframes spin { to { transform:rotate(360deg); } }

  /* ── Editor toolbar ───────────────────────────────────────────── */
  .editor-wrap { border:1px solid var(--line); border-radius:16px; overflow:hidden;
    transition:border-color .16s,box-shadow .16s; }
  .editor-wrap:focus-within { border-color:var(--accent); box-shadow:0 0 0 4px color-mix(in srgb,var(--accent) 12%,transparent); }
  .editor-head { display:flex; align-items:center; justify-content:space-between; gap:8px;
    padding:9px 13px; border-bottom:1px solid var(--line); background:var(--gutter); }
  .editor-head .ttl { font-size:11px; font-weight:700; letter-spacing:.05em; text-transform:uppercase; color:var(--muted); }
  .editor-head .mini { display:flex; gap:6px; flex-wrap:wrap; justify-content:flex-end; }
  .editor-body { display:flex; align-items:stretch; min-width:0; background:var(--input-bg); }
  .editor-line-numbers { flex:0 0 auto; min-width:3.5em; height:640px;
    margin:0; padding:10px 10px; overflow:hidden; border-right:1px solid var(--line);
    background:var(--gutter); color:var(--gutter-text); text-align:right; user-select:none;
    pointer-events:none; white-space:pre; font-family:"JetBrains Mono","Fira Code",ui-monospace,
    "SF Mono",Menlo,Consolas,monospace; font-size:12.5px; line-height:1.5; }
  .editor-code-pane { position:relative; flex:1 1 auto; min-width:0; height:640px;
    background:var(--input-bg); }
  .editor-highlight,.editor-wrap textarea { position:absolute; inset:0; width:100%; height:100%;
    margin:0; padding:10px 13px; border:none; border-radius:0; font-size:12.5px;
    line-height:1.5; tab-size:2; white-space:pre; overflow-wrap:normal;
    font-family:"JetBrains Mono","Fira Code",ui-monospace,"SF Mono",Menlo,Consolas,monospace; }
  .editor-highlight { display:none; z-index:0; overflow:hidden; pointer-events:none; color:var(--text);
    background:var(--input-bg); }
  .editor-highlight .cml-comment { color:var(--comment); }
  .editor-wrap textarea { z-index:1; min-width:0; min-height:0; resize:none; overflow:auto;
    background:var(--input-bg); color:var(--text); -webkit-text-fill-color:var(--text);
    caret-color:var(--text); }
  .editor-wrap textarea::placeholder { color:var(--muted); -webkit-text-fill-color:var(--muted); }
  .editor-wrap textarea::selection { background:color-mix(in srgb,var(--accent) 28%,transparent); }
  .editor-wrap textarea:focus { border:none; box-shadow:none; }
  .key-field-compact { flex:0 1 270px !important; width:270px; max-width:270px !important; }
  .key-field-picker { position:relative; width:100%; }
  .key-field-picker input { width:100%; min-height:42px; padding:8px 40px 8px 13px; font-size:13.5px; }
  .key-field-picker:focus-within input { border-color:var(--accent);
    box-shadow:0 0 0 4px color-mix(in srgb,var(--accent) 12%,transparent); }
  .key-field-toggle { position:absolute; top:50%; right:8px; width:28px; height:28px;
    padding:0; border:0; border-radius:8px; transform:translateY(-50%);
    display:grid; place-items:center; color:var(--muted); background:transparent; cursor:pointer; }
  .key-field-toggle:hover { color:var(--text); background:var(--gutter); }
  .key-field-toggle svg { width:15px; height:15px; transition:transform .16s ease; }
  .key-field-picker.open .key-field-toggle svg { transform:rotate(180deg); }
  .key-field-menu { position:absolute; z-index:30; top:calc(100% + 7px); left:0; right:0;
    max-height:270px; overflow:auto; padding:6px; border:1px solid var(--line);
    border-radius:14px; background:var(--panel); box-shadow:0 18px 45px rgba(15,23,42,.18);
    animation:keyMenuIn .14s ease-out; }
  @keyframes keyMenuIn { from { opacity:0; transform:translateY(-4px); }
    to { opacity:1; transform:translateY(0); } }
  .key-field-option { width:100%; border:0; border-radius:10px; padding:9px 10px;
    display:flex; align-items:center; justify-content:space-between; gap:10px;
    color:var(--text); background:transparent; text-align:left; cursor:pointer; }
  .key-field-option:hover,.key-field-option.active { background:color-mix(in srgb,var(--accent) 10%,var(--panel)); }
  .key-field-option.selected { background:color-mix(in srgb,var(--green) 11%,var(--panel)); }
  .key-field-option-main { min-width:0; display:flex; flex-direction:column; gap:2px; }
  .key-field-option-name { overflow:hidden; text-overflow:ellipsis; font-size:12px;
    font-weight:700; font-family:"JetBrains Mono",ui-monospace,monospace; }
  .key-field-option-scope { overflow:hidden; text-overflow:ellipsis; color:var(--muted);
    font-size:10px; white-space:nowrap; }
  .key-field-option-mark { flex:none; color:var(--green); font-size:14px; font-weight:800; }
  .key-field-empty { padding:14px 10px; color:var(--muted); font-size:11px; text-align:center; }
  #keyFieldHelp { max-width:270px; margin:5px 0 0; color:var(--text-muted);
    font-size:10.5px; line-height:1.38; }
  @media (max-width:720px) {
    .key-field-compact { flex:1 1 100% !important; width:100%; max-width:none !important; }
  }

  /* ── Diff view ────────────────────────────────────────────────── */
  .diff { margin-top:22px; display:none; }
  .diff.show { display:block; }
  .diff-head { display:flex; align-items:center; justify-content:space-between; gap:12px; flex-wrap:wrap; margin-bottom:10px; }
  .summary { font-size:13px; font-weight:600; }
  .legend { font-size:12px; color:var(--muted); display:flex; gap:14px; flex-wrap:wrap; align-items:center; }
  .legend span { display:inline-flex; align-items:center; }
  .legend i { width:14px; height:14px; border-radius:4px; margin-right:6px; display:inline-flex; align-items:center; justify-content:center; font-size:10px; font-weight:700; color:var(--text); }
  .lg-chg { background:var(--chg-bg); border:1px solid var(--chg-line); }
  .lg-del { background:var(--del-bg); border:1px solid var(--del-line); }
  .lg-ins { background:var(--ins-bg); border:1px solid var(--ins-line); }
  .diff-panes { display:grid; grid-template-columns:minmax(0,1fr) 48px minmax(0,1fr);
    gap:8px; align-items:stretch; }
  .pane { flex:1; min-width:0; border:1px solid var(--line); border-radius:16px; overflow:hidden; display:flex; flex-direction:column; }
  .pane-title { min-height:40px; padding:6px 10px; font-size:12px; font-weight:600; color:var(--muted);
    border-bottom:1px solid var(--line); background:var(--gutter); white-space:nowrap;
    overflow:hidden; display:flex; align-items:center; justify-content:space-between; gap:8px; }
  .pane-title-text { overflow:hidden; text-overflow:ellipsis; }
  .pane-copy { display:inline-flex; align-items:center; gap:5px; flex:none; padding:4px 8px;
    border:1px solid var(--line); border-radius:7px; background:var(--panel); color:var(--text);
    font-size:11px; font-weight:700; cursor:pointer; }
  .pane-copy:hover { border-color:var(--accent); color:var(--accent); background:var(--info-bg); }
  .pane-copy svg { width:13px; height:13px; }
  .pane-title-actions { display:flex; align-items:center; gap:5px; flex:none; }
  .pane-scroll { overflow:auto; max-height:600px; }
  .target-draft-editor { display:block; width:100%; height:clamp(320px,48vh,600px); min-height:240px;
    resize:vertical; overflow:auto; border:0; border-radius:0; outline:none; padding:10px 12px;
    background:var(--input-bg); color:var(--text); caret-color:var(--accent);
    font:12.5px/18.75px "JetBrains Mono","SF Mono",Menlo,Consolas,monospace;
    tab-size:2; white-space:pre; }
  .target-draft-editor:focus { box-shadow:inset 0 0 0 2px var(--accent); }
  .diff-panes.target-editing .merge-rail { opacity:.48; }
  .diff-panes.target-editing .merge-arrow { pointer-events:none; cursor:not-allowed; }
  table.pane-table { border-collapse:collapse; width:100%; font-family:"JetBrains Mono","SF Mono",Menlo,Consolas,monospace; font-size:12.5px; }
  .pane-table td { height:18.75px; padding:0 8px; vertical-align:top; white-space:pre; line-height:18.75px; }
  .gutter { text-align:right; color:var(--gutter-text); background:var(--gutter); user-select:none; width:1%; white-space:nowrap; border-right:1px solid var(--line); position:sticky; left:0; }
  .code { width:100%; border-left:3px solid transparent; }
  .mk { user-select:none; display:inline-block; width:1ch; margin-right:7px; color:var(--muted); font-weight:700; }
  .row-chg .code { background:var(--chg-bg); border-left-color:var(--chg-line); }
  .row-del .code { background:var(--del-bg); border-left-color:var(--del-line); }
  .row-ins .code { background:var(--ins-bg); border-left-color:var(--ins-line); }
  .row-filler td { background:repeating-linear-gradient(45deg,transparent,transparent 6px,rgba(128,128,128,.06) 6px,rgba(128,128,128,.06) 12px); }
  .diff-panes.hide-eq tr.eqrow { display:none; }
  .diff-opts { font-size:12px; color:var(--muted); display:inline-flex; align-items:center; gap:6px; }
  .diff-opts input { width:auto; }
  .merge-rail { min-width:0; border:1px solid var(--line); border-radius:12px; overflow:hidden;
    background:var(--gutter); display:flex; flex-direction:column; }
  .merge-rail .pane-title { padding-left:4px; padding-right:4px; text-align:center; }
  .merge-scroll { overflow:hidden; max-height:600px; flex:1; }
  table.merge-table { border-collapse:collapse; width:100%; font-family:"JetBrains Mono","SF Mono",Menlo,Consolas,monospace;
    font-size:12.5px; }
  .merge-table td { height:18.75px; padding:0; text-align:center; vertical-align:top; white-space:nowrap; }
  .merge-table tr:not(.eqrow) td { background:color-mix(in srgb,var(--accent) 5%,var(--gutter)); }
  .merge-arrow { width:34px; height:18px; padding:0; border:1px solid var(--accent);
    border-radius:6px; background:var(--panel); color:var(--accent); font-size:14px;
    font-weight:850; line-height:16px; cursor:pointer; display:block; margin:0 auto; }
  .merge-arrow:hover { background:var(--accent); color:var(--on-accent); transform:none; }
  .merge-workflow { margin:0 0 12px; padding:10px 12px; border:1px solid var(--accent);
    border-radius:12px; background:var(--info-bg); display:flex; align-items:center;
    justify-content:space-between; gap:12px; flex-wrap:wrap; }
  .merge-workflow-copy { color:var(--text); font-size:12px; }
  .merge-workflow-actions { display:flex; align-items:center; gap:8px; flex-wrap:wrap; }

  /* ── Semantic overlay (never replaces the two code panes) ───── */
  .summary-stack { display:flex; flex-direction:column; gap:3px; min-width:0; }
  .semantic-inline-summary { color:var(--muted); font-size:12px; }
  .semantic-inline-summary strong { color:var(--text); }
  .semantic-badge { display:inline-flex; align-items:center; margin:0 7px 0 1px;
    padding:1px 6px; border-radius:999px; font-family:Inter,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;
    font-size:9px; font-weight:850; line-height:14px; letter-spacing:.035em; text-transform:uppercase;
    vertical-align:1px; }
  .semantic-badge.moved { background:var(--info-bg); color:var(--accent); border:1px solid var(--accent); }
  .semantic-badge.modified { background:color-mix(in srgb,var(--amber) 13%,var(--panel)); color:var(--amber); border:1px solid var(--amber); }
  .semantic-badge.added { background:var(--ins-bg); color:var(--ins-line); border:1px solid var(--ins-line); }
  .semantic-badge.removed { background:var(--del-bg); color:var(--del-line); border:1px solid var(--del-line); }
  .semantic-badge.ambiguous { background:var(--chg-bg); color:var(--purple); border:1px solid var(--purple); }
  .pane-table tr.sem-moved .code { background:var(--info-bg); box-shadow:inset 4px 0 0 var(--accent); }
  .pane-table tr.sem-modified .code { background:color-mix(in srgb,var(--amber) 11%,var(--panel)); box-shadow:inset 4px 0 0 var(--amber); }
  .pane-table tr.sem-added .code { box-shadow:inset 4px 0 0 var(--ins-line); }
  .pane-table tr.sem-removed .code { box-shadow:inset 4px 0 0 var(--del-line); }
  .pane-table tr.sem-ambiguous .code { background:var(--chg-bg); box-shadow:inset 4px 0 0 var(--purple); }

  /* ── Lint / best-practices ────────────────────────────────────── */
  .lint { display:none; margin-top:16px; }
  .lint.show { display:block; }
  .lint-head { display:flex; align-items:center; justify-content:space-between; gap:12px; flex-wrap:wrap; margin-bottom:10px; }
  .lint-head h4 { margin:0; font-size:15px; font-weight:700; }
  .lint-score { font-size:13px; font-weight:700; padding:5px 14px; border-radius:999px; }
  .lint-score.good { background:var(--ok-bg); color:var(--ok-text); }
  .lint-score.mid { background:color-mix(in srgb,var(--amber) 18%,var(--panel)); color:var(--amber); }
  .lint-score.bad { background:var(--err-bg); color:var(--err-text); }
  .lint-counts { font-size:12px; color:var(--muted); display:flex; gap:10px; flex-wrap:wrap; }
  .lint-caption { font-size:12px; color:var(--muted); margin:8px 0 12px; line-height:1.5; }
  .lint-item { border:1px solid var(--line); border-left-width:4px; border-radius:12px; padding:10px 14px; margin-bottom:8px; font-size:13px; }
  .lint-item .rmeta { font-size:11px; color:var(--muted); text-transform:uppercase; letter-spacing:.04em; margin-bottom:3px; }
  .lint-item .msg { color:var(--text); }
  .lint-item .fix { color:var(--muted); font-size:12px; margin-top:4px; }
  .lint-item.error { border-left-color:var(--red); }
  .lint-item.warn { border-left-color:var(--amber); }
  .lint-item.info { border-left-color:var(--accent); }
  .lint-line { font-family:"JetBrains Mono","SF Mono",Menlo,monospace; color:var(--accent); cursor:pointer; font-weight:700; }
  .lint-empty { padding:14px 16px; border-radius:12px; background:var(--ok-bg); color:var(--ok-text); font-size:13px; }
  .lint-fix { margin-top:8px; }
  .lint-fix .fixhead { font-size:11px; font-weight:700; color:var(--muted); text-transform:uppercase; letter-spacing:.04em; margin:8px 0 3px; display:flex; align-items:center; gap:8px; }
  .lint-code { font-family:"JetBrains Mono","SF Mono",Menlo,monospace; font-size:12px; white-space:pre-wrap; word-break:break-word; padding:8px 12px; border-radius:8px; border:1px solid var(--line); }
  .lint-code.before { background:var(--del-bg); color:var(--del-line); }
  .lint-code.after { background:var(--ins-bg); color:var(--ins-line); }
  .lint-copy { font-size:11px; padding:2px 8px; }

  /* ── Constraint data ──────────────────────────────────────────── */
  .safety-alert { display:flex; align-items:flex-start; gap:10px; margin-bottom:14px; padding:10px 12px;
    border:1px solid var(--color-primary-border); border-radius:var(--radius-control); background:var(--info-bg);
    color:var(--info-text); }
  .safety-alert-icon { width:18px; height:18px; flex:0 0 18px; display:grid; place-items:center;
    margin-top:1px; border-radius:50%; background:var(--accent); color:#fff; font-size:11px; font-weight:850; }
  .safety-alert p { margin:0; font-size:10.5px; line-height:1.5; }
  .safety-alert p + p { margin-top:4px; color:var(--text-secondary); }
  .data-action-row { display:flex; align-items:flex-end; justify-content:space-between; gap:18px;
    margin-bottom:14px; }
  .data-action-row > .btn-row { margin-left:auto !important; }
  .data-workspace-card { padding:18px; }
  .data-workspace-card .card-head { padding-bottom:10px; margin-bottom:10px; }
  .data-workspace-card .safety-alert { margin-bottom:10px; padding:8px 10px; }
  .data-workspace-card .data-action-row { margin-bottom:9px; }
  .data-workspace-card .deploy-bar { margin-top:8px; padding:8px 10px; }
  .chips { display:flex; gap:8px; flex-wrap:wrap; }
  .chip { font-size:11.5px; font-weight:700; padding:4px 10px; border-radius:var(--radius-pill);
    border:1px solid var(--line); color:var(--muted); background:var(--surface-subtle); }
  .chip.neutral { color:var(--text-secondary); font-weight:650;
    border-color:color-mix(in srgb,var(--line) 65%,transparent);
    background:color-mix(in srgb,var(--surface-subtle) 55%,transparent); }
  .chip.ok { background:var(--ok-bg); color:var(--ok-text); border-color:var(--green); }
  .chip.add { background:var(--ins-bg); color:var(--ins-line); border-color:var(--ins-line); }
  .chip.extra { background:var(--del-bg); color:var(--del-line); border-color:var(--del-line); }
  .chip.warn { background:var(--err-bg); color:var(--err-text); border-color:var(--red); }
  .chip.cml-diff { background:var(--color-warning-soft); color:var(--color-warning);
    border-color:color-mix(in srgb,var(--color-warning) 68%,transparent); }
  .chip.dup { background:color-mix(in srgb,#f97316 12%,var(--panel)); color:#c2410c;
    border-color:color-mix(in srgb,#f97316 68%,transparent); }
  html[data-theme="dark"] .chip.dup { color:#fdba74; }
  .data { margin-top:14px; display:none; }
  .data.show { display:block; }
  .data-head { display:flex; align-items:center; justify-content:space-between; gap:12px; flex-wrap:wrap; margin-bottom:10px; }
  .data-filter { font-size:12px; color:var(--muted); display:inline-flex; align-items:center; gap:6px; }
  .data-filter select { width:auto; padding:6px 10px; border-radius:9px; }
  .table-scroll { overflow:auto; max-height:560px; border:1px solid var(--line); border-radius:var(--radius-control); }
  table.data-table { border-collapse:separate; border-spacing:0; width:100%; min-width:900px; font-size:12px; table-layout:fixed; }
  .data-table th,.data-table td { padding:7px 11px; text-align:left; border-bottom:1px solid var(--line); vertical-align:top; word-break:break-word; }
  .data-table th + th,.data-table td + td {
    border-left:1px solid color-mix(in srgb,var(--line) 72%,transparent); }
  .data-table th { position:sticky; top:0; background:var(--surface-subtle); color:var(--text-secondary);
    font-size:9.5px; text-transform:uppercase; letter-spacing:.055em; z-index:1; white-space:nowrap; }
  .data-table tbody tr { transition:background .14s; }
  .data-table tbody tr:hover { background:var(--surface-hover); }
  /* narrow columns — short content, no wrap needed */
  .data-table td.col-sel,.data-table th.col-sel { width:62px; text-align:center; white-space:nowrap; }
  .data-table td.col-reftype,.data-table th.col-reftype { width:110px; white-space:nowrap; }
  .data-table td.col-tagtype,.data-table th.col-tagtype { width:80px; white-space:nowrap; }
  /* wide columns — allow wrap so full value is always visible */
  .data-table td.col-status,.data-table th.col-status { width:156px; }
  .data-table td.col-status .badge { max-width:100%; white-space:normal; line-height:1.25; }
  .data-table td.col-tag,.data-table th.col-tag { width:170px; }
  .data-table td.col-ref,.data-table th.col-ref { width:230px; }
  .data-table td.col-key,.data-table th.col-key { width:190px; font-family:"JetBrains Mono","SF Mono",Menlo,Consolas,monospace; font-size:11px; color:var(--muted); word-break:break-all; }
  .data-table .gkey { font-family:"JetBrains Mono","SF Mono",Menlo,Consolas,monospace; font-size:11px; color:var(--muted); word-break:break-all; }
  .data-table td.col-sel input[type=checkbox] { width:auto; cursor:pointer; accent-color:var(--accent); }
  .badge { display:inline-flex; align-items:center; gap:4px; font-size:10px; font-weight:750;
    padding:3px 8px; border-radius:var(--radius-pill); }
  .b-match { background:var(--ok-bg); color:var(--ok-text); }
  .b-add { background:var(--ins-bg); color:var(--ins-line); }
  .b-extra { background:var(--del-bg); color:var(--del-line); }
  .b-blocked,.b-unmappable { background:var(--err-bg); color:var(--err-text); }
  .b-type { background:var(--info-bg); color:var(--info-text); }
  .b-dup { background:color-mix(in srgb,var(--amber) 18%,var(--panel)); color:var(--amber); border:1px solid var(--amber); margin-left:6px; }
  .block-note { display:block; margin-top:4px; font-size:11px; color:var(--muted); font-style:italic; white-space:normal; }
  .deploy-bar { display:none; margin-top:14px; padding:10px 12px; border-radius:var(--radius-control);
    background:var(--color-primary-soft); border:1px solid var(--accent); align-items:center;
    justify-content:space-between; gap:12px; flex-wrap:wrap; }
  .deploy-bar.show { display:flex; }
  .deploy-bar .sel-summary { font-size:13px; color:var(--text); }
  .deploy-bar .sel-actions { display:flex; gap:8px; align-items:center; flex-wrap:wrap; }
  .warn-note { color:var(--err-text); font-size:12px; }
  .results { display:none; margin-top:16px; }
  .results.show { display:block; }
  .results h4 { margin:0 0 8px; font-size:14px; }
  .result-row { font-family:"JetBrains Mono","SF Mono",Menlo,Consolas,monospace; font-size:12px;
    padding:7px 12px; border-radius:8px; margin-bottom:5px; display:flex; gap:8px; }
  .result-row.good { background:var(--ok-bg); color:var(--ok-text); }
  .result-row.bad { background:var(--err-bg); color:var(--err-text); }
  .result-row .ico { font-weight:700; }

  /* ── Tool guide ──────────────────────────────────────────────── */
  .guide-hero { display:flex; justify-content:space-between; gap:18px; align-items:flex-start;
    padding:18px; margin-bottom:16px; border:1px solid var(--line); border-radius:16px;
    background:linear-gradient(135deg,color-mix(in srgb,var(--accent) 12%,var(--panel)),var(--panel)); }
  .guide-hero h2 { margin:0 0 7px; }
  .guide-prereqs { margin-bottom:16px; padding:15px 17px; border:1px solid var(--color-primary-border);
    border-radius:14px; background:var(--info-bg); color:var(--info-text); }
  .guide-prereqs h3 { margin:0 0 7px; font-size:14px; }
  .guide-prereqs p { margin:0 0 7px; font-size:12.5px; line-height:1.55; }
  .guide-prereqs ul,.guide-detail-list { margin:0; padding-left:19px; font-size:12px; line-height:1.55; }
  .guide-badges { display:flex; gap:8px; flex-wrap:wrap; }
  .guide-badge { display:inline-flex; align-items:center; padding:5px 10px; border-radius:999px;
    font-size:11px; font-weight:850; white-space:nowrap; border:1px solid currentColor; }
  .guide-badge.read { color:var(--ok-text); background:var(--ok-bg); }
  .guide-badge.write { color:var(--color-warning); background:var(--color-warning-soft); }
  .guide-steps { display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:12px; }
  .guide-step { display:grid; grid-template-columns:38px minmax(0,1fr); gap:12px; padding:15px;
    border:1px solid var(--line); border-radius:14px; background:var(--input-bg); }
  .guide-number { width:36px; height:36px; display:grid; place-items:center; border-radius:11px;
    color:var(--on-accent); font-weight:900; background:var(--accent); }
  .guide-step h3 { margin:1px 0 5px; font-size:14px; }
  .guide-step p { margin:0; color:var(--muted); font-size:12.5px; line-height:1.55; }
  .guide-detail-list { margin-top:7px; color:var(--text-secondary); }
  .guide-detail-list li + li { margin-top:3px; }
  .guide-boundaries { margin-top:16px; padding:15px 17px; border:2px solid var(--amber);
    border-radius:14px; background:color-mix(in srgb,var(--amber) 10%,var(--panel)); }
  .guide-boundaries h3 { margin:0 0 7px; font-size:14px; }
  .guide-boundaries ul { margin:0; padding-left:20px; color:var(--text); font-size:12.5px; line-height:1.65; }

  /* ── Responsive ───────────────────────────────────────────────── */
  @media (max-width:1180px) {
    .app-header { grid-template-columns:minmax(350px,1fr) auto minmax(170px,1fr); gap:10px; }
    .guide-steps { grid-template-columns:1fr; }
  }
  @media (max-width:1120px) {
    .app-header { min-height:116px; grid-template-columns:1fr auto; grid-template-rows:auto auto;
      padding:9px 16px; }
    .brand-cluster { grid-column:1; grid-row:1; }
    .top-actions { grid-column:2; grid-row:1; }
    .nav-island { grid-column:1 / -1; grid-row:2; max-width:100%; overflow-x:auto;
      justify-self:stretch; scrollbar-width:none; }
    .nav-island::-webkit-scrollbar { display:none; }
    .tabs { width:max-content; min-width:100%; justify-content:center; }
    .deploy-panel { grid-template-columns:minmax(0,1fr) minmax(0,1fr); }
    .deploy-action-stack { grid-column:1 / -1; flex-direction:row; padding-top:0; }
  }
  @media (max-width:900px) {
    body::before { height:140px; opacity:.58; }
    body::after { height:145px; opacity:.72; }
    .app-shell::before { height:100px; opacity:.72; }
    .app-shell::after { height:82px; opacity:.76; }
  }
  @media (max-width:700px) {
    .app-header { min-height:104px; }
    .brand-mark { width:34px; height:34px; flex-basis:34px; }
    .credit,.local-badge { display:none; }
    .header-links { gap:0; margin-left:0; }
    .header-link { padding:6px; }
    .header-link span { display:none; }
    .header-link + .header-link::before { display:none; }
    .top-actions { gap:4px; }
    .topbar { min-height:46px; padding-top:10px; }
    .card-head { flex-wrap:wrap; }
    .fetch-header-action { width:100%; }
    .conn-strip { grid-template-columns:1fr; }
    .org-workspace { padding:14px; }
    .workspace-head { align-items:flex-start; }
    .workspace-org-id { white-space:normal; text-align:right; overflow-wrap:anywhere; }
    .data-action-row { align-items:stretch; flex-direction:column; }
    .data-action-row > .field { width:100% !important; max-width:none !important; }
    .data-action-row > .btn-row { margin-left:0 !important; }
    .diff-panes { grid-template-columns:1fr; }
    .merge-rail { display:none; }
    .tabs { justify-content:flex-start; }
    .side-nav,.tab { min-width:max-content; }
    .deploy-group { flex-wrap:wrap; }
    .guide-hero { flex-direction:column; }
    .deploy-panel { grid-template-columns:1fr; }
    .deploy-action-stack { grid-column:auto; flex-direction:column; }
  }
  @media (max-width:460px) {
    .brand-copy strong { font-size:11px; }
    .brand-copy small { font-size:10px; }
    #appver { display:none; }
  }
  @media (prefers-reduced-motion:reduce) {
    *,*::before,*::after { animation-duration:.01ms !important; animation-iteration-count:1 !important;
      scroll-behavior:auto !important; transition-duration:.01ms !important; }
  }
</style>
</head>
<body>
<div class="app-shell">
  <header class="app-header">
    <div class="brand-cluster">
      <a class="brand" href="#" onclick="return false;">
        <span class="brand-mark" aria-hidden="true">
          <svg viewBox="0 0 24 24"><path d="M7.4 18.3c-2.9 0-5.2-2-5.2-4.6 0-2.2 1.7-4.1 4-4.5C6.8 6.7 9 5 11.6 5c2.1 0 4 1.1 5 2.8.4-.1.8-.2 1.2-.2 2.3 0 4.1 1.8 4.1 4.1s-1.8 4.1-4.1 4.1c-.4 0-.7 0-1.1-.1-1 1.6-2.8 2.6-4.8 2.6H7.4z"/></svg>
        </span>
        <span class="brand-copy">
          <strong>Salesforce CML Tool</strong>
          <span class="credit">Made with <svg class="heart" viewBox="0 0 24 24" aria-label="care"><path d="M20.8 4.6a5.5 5.5 0 0 0-7.8 0L12 5.7l-1.1-1.1a5.5 5.5 0 0 0-7.8 7.8l1.1 1.1L12 21l7.7-7.5 1.1-1.1a5.5 5.5 0 0 0 0-7.8z"/></svg> by Mritunjaya Pancholi</span>
        </span>
      </a>
      <div class="header-links">
      <div class="donate-wrap">
          <button type="button" class="header-link donate-link" id="donateBtn"
            aria-expanded="false" aria-controls="donateOptions">
            <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M20.8 4.6a5.5 5.5 0 0 0-7.8 0L12 5.7l-1.1-1.1a5.5 5.5 0 0 0-7.8 7.8l1.1 1.1L12 21l7.7-7.5 1.1-1.1a5.5 5.5 0 0 0 0-7.8z"/></svg>
            <span>Donate</span>
          </button>
        <div class="donate-options" id="donateOptions" hidden>
          <button type="button" class="donate-option" id="donateUpiBtn">
            <span class="payment-icon upi-icon" aria-hidden="true">UPI</span>
            <span>UPI</span>
          </button>
          <a class="donate-option" id="donateRazorpayBtn"
            href="https://razorpay.me/@mpancholi" target="_blank"
            rel="noopener noreferrer" title="Open secure Razorpay payment page">
            <span class="payment-icon razorpay-icon" aria-hidden="true">R</span>
            <span>Razorpay</span>
          </a>
        </div>
      </div>
        <a class="header-link about-link" href="https://www.linkedin.com/in/mrpancholi/"
           target="_blank" rel="noopener noreferrer">
          <svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="9"/><path d="M12 11v6M12 7h.01"/></svg>
          <span>About</span>
        </a>
      </div>
    </div>

    <nav class="nav-island side-menu" id="sideNav" aria-label="Primary navigation">
      <div class="tabs" id="tabRow" role="tablist">
        <button class="side-nav tab active" data-view="fetch" role="tab" aria-selected="true">
          <span class="nav-icon"><svg viewBox="0 0 24 24"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4M7 10l5 5 5-5M12 15V3"/></svg></span>
          <span>Fetch &amp; Deploy</span>
        </button>
        <button class="side-nav tab" data-view="data" role="tab" aria-selected="false">
          <span class="nav-icon"><svg viewBox="0 0 24 24"><ellipse cx="12" cy="5" rx="9" ry="3"/><path d="M21 12c0 1.66-4 3-9 3s-9-1.34-9-3M3 5v14c0 1.66 4 3 9 3s9-1.34 9-3V5"/></svg></span>
          <span>Constraint Data Deploy</span>
        </button>
        <button class="side-nav tab" data-view="compare" role="tab" aria-selected="false">
          <span class="nav-icon"><svg viewBox="0 0 24 24"><path d="M8 3H5a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h3M16 3h3a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2h-3M10 8l-3 4 3 4M14 8l3 4-3 4"/></svg></span>
          <span>Compare</span>
        </button>
        <button class="side-nav tab" data-view="lint" role="tab" aria-selected="false">
          <span class="nav-icon"><svg viewBox="0 0 24 24"><path d="M9 11l3 3L22 4M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11"/></svg></span>
          <span>Best Practices</span>
        </button>
        <button class="side-nav tab" data-view="guide" role="tab" aria-selected="false">
          <span class="nav-icon"><svg viewBox="0 0 24 24"><path d="M4 5.5A2.5 2.5 0 0 1 6.5 3H11v17H6.5A2.5 2.5 0 0 0 4 22V5.5zM20 5.5A2.5 2.5 0 0 0 17.5 3H13v17h4.5A2.5 2.5 0 0 1 20 22V5.5z"/></svg></span>
          <span>Guide Me</span>
        </button>
      </div>
    </nav>

      <div class="top-actions">
        <span class="local-badge"><span class="live-dot"></span>Runs locally</span>
        <span id="appver" style="font-size:11px;color:var(--muted);font-family:'JetBrains Mono',ui-monospace,monospace;opacity:.8;white-space:nowrap;" title="Running build"></span>
        <button class="ghost theme-toggle" id="themeBtn" title="Toggle day/night">
          <svg id="themeIcon" viewBox="0 0 24 24" aria-hidden="true"><path d="M20.8 15.4A9 9 0 0 1 8.6 3.2 9 9 0 1 0 20.8 15.4Z"/></svg>
          <span id="themeLabel">Night mode</span>
        </button>
      </div>
  </header>

  <!-- ═══════════ MAIN ═══════════ -->
  <main class="app-main">
    <header class="topbar">
      <div>
        <h1 class="sr-only" id="pageTitle">Fetch &amp; Deploy</h1>
        <p class="sub" id="pageSubtitle">Pick a source org — CMLs load automatically. Fetch, edit, and deploy to any org.</p>
      </div>
    </header>

    <div class="wrap">
      <!-- connection error banner -->
      <div class="conn" id="conn"></div>

      <!-- ═══ ORG WORKSPACES (omitted from the instructional Guide Me view) ═══ -->
      <div class="card connection-card" id="connectionCard">
        <div class="conn-strip">
          <section class="org-workspace source-workspace" aria-labelledby="sourceWorkspaceTitle">
            <div class="workspace-head">
              <div class="workspace-title">
                <span class="workspace-icon" aria-hidden="true"><svg viewBox="0 0 24 24"><path d="M4 21V8l8-5 8 5v13M8 21v-4h8v4M8 10h.01M12 10h.01M16 10h.01M8 13h.01M12 13h.01M16 13h.01"/></svg></span>
                <span><strong id="sourceWorkspaceTitle">Source org</strong><span>Select the source org and exact CML version.</span></span>
              </div>
              <span class="workspace-org-id" id="sourceOrgId">Org ID: —</span>
            </div>
            <div class="field">
              <label for="org">Source org</label>
              <div class="org-picker" id="sourceOrgPicker">
                <button type="button" class="org-trigger" id="sourceOrgTrigger" aria-haspopup="listbox" aria-expanded="false" disabled>
                  <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 21V8l8-5 8 5v13M8 21v-4h8v4M8 10h.01M12 10h.01M16 10h.01M8 13h.01M12 13h.01M16 13h.01"/></svg>
                  <span class="org-trigger-copy" id="sourceOrgDisplay">Loading orgs…</span>
                  <svg class="version-chevron" viewBox="0 0 24 24" aria-hidden="true"><path d="m6 9 6 6 6-6"/></svg>
                </button>
                <div class="org-menu" id="sourceOrgMenu" role="listbox" aria-label="Source orgs" hidden></div>
                <select class="sr-only" id="org" tabindex="-1" aria-hidden="true"><option>Loading orgs…</option></select>
              </div>
            </div>
            <div class="field model-field">
              <label for="model" class="label-with-icon">
                <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M6 2h9l4 4v16H6zM14 2v5h5M9 12h7M9 16h7"/></svg>
                <span>Source CML exact version <span id="cmlCount" class="meta"></span></span>
              </label>
              <div class="combo version-picker" id="combo">
                <button type="button" class="version-trigger" id="sourceVersionTrigger"
                  aria-haspopup="listbox" aria-expanded="false" disabled>
                  <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M6 2h9l4 4v16H6zM14 2v5h5M9 12h7M9 16h7"/></svg>
                  <span class="version-trigger-copy" id="selectedName">Select a source org first…</span>
                  <svg class="version-chevron" viewBox="0 0 24 24" aria-hidden="true"><path d="m6 9 6 6 6-6"/></svg>
                </button>
                <div class="version-menu" id="sourceVersionMenu" hidden>
                  <div class="version-search-wrap">
                    <svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="11" cy="11" r="7"/><path d="m20 20-4-4"/></svg>
                    <input class="version-search" id="cmlFilter" placeholder="Search CML versions…" autocomplete="off" spellcheck="false" />
                  </div>
                  <div class="version-options" id="sourceVersionOptions" role="listbox" aria-label="Source CML versions"></div>
                </div>
                <select class="sr-only" id="model" tabindex="-1" aria-hidden="true"><option value="">Choose an org first…</option></select>
              </div>
              <div class="combo-selected" id="comboSelected" hidden></div>
            </div>
          </section>

          <section class="org-workspace target-workspace" aria-labelledby="targetWorkspaceTitle">
            <div class="workspace-head">
              <div class="workspace-title">
                <span class="workspace-icon" aria-hidden="true"><svg viewBox="0 0 24 24"><path d="M4 21V8l8-5 8 5v13M8 21v-4h8v4M8 10h.01M12 10h.01M16 10h.01M8 13h.01M12 13h.01M16 13h.01"/></svg></span>
                <span><strong id="targetWorkspaceTitle">Target org (compare-with)</strong><span>Select the target org and exact CML version.</span></span>
              </div>
              <span class="workspace-org-id" id="targetOrgId">Org ID: —</span>
            </div>
            <div class="field">
              <label for="targetOrg">Target org (compare-with)</label>
              <div class="org-picker" id="targetOrgPicker">
                <button type="button" class="org-trigger" id="targetOrgTrigger" aria-haspopup="listbox" aria-expanded="false" disabled>
                  <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 21V8l8-5 8 5v13M8 21v-4h8v4M8 10h.01M12 10h.01M16 10h.01M8 13h.01M12 13h.01M16 13h.01"/></svg>
                  <span class="org-trigger-copy" id="targetOrgDisplay">Loading orgs…</span>
                  <svg class="version-chevron" viewBox="0 0 24 24" aria-hidden="true"><path d="m6 9 6 6 6-6"/></svg>
                </button>
                <div class="org-menu" id="targetOrgMenu" role="listbox" aria-label="Target orgs" hidden></div>
                <select class="sr-only" id="targetOrg" tabindex="-1" aria-hidden="true"><option>Loading orgs…</option></select>
              </div>
            </div>
            <div class="field">
              <label for="targetVersion" class="label-with-icon">
                <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M6 2h9l4 4v16H6zM14 2v5h5M9 12h7M9 16h7"/></svg>
                <span>Target exact version (compare-with)</span>
              </label>
              <div class="version-picker" id="targetVersionPicker">
                <button type="button" class="version-trigger" id="targetVersionTrigger"
                  aria-haspopup="listbox" aria-expanded="false" disabled>
                  <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M6 2h9l4 4v16H6zM14 2v5h5M9 12h7M9 16h7"/></svg>
                  <span class="version-trigger-copy" id="targetVersionDisplay">Select target org and source version…</span>
                  <svg class="version-chevron" viewBox="0 0 24 24" aria-hidden="true"><path d="m6 9 6 6 6-6"/></svg>
                </button>
                <div class="version-menu" id="targetVersionMenu" hidden>
                  <div class="version-search-wrap">
                    <svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="11" cy="11" r="7"/><path d="m20 20-4-4"/></svg>
                    <input class="version-search" id="targetVersionFilter" placeholder="Search CML versions…" autocomplete="off" spellcheck="false" />
                  </div>
                  <div class="version-options" id="targetVersionOptions" role="listbox" aria-label="Target CML versions"></div>
                </div>
                <select class="sr-only" id="targetVersion" tabindex="-1" aria-hidden="true"><option value="">None — select target org and source version</option></select>
              </div>
              <span class="meta">Target-org runtime status can differ from the source.</span>
            </div>
          </section>
        </div>
      </div>

      <!-- ══════════════ VIEW: FETCH & DEPLOY ══════════════ -->
      <div class="view-panel active" id="view-fetch">
        <div class="card">
          <div class="card-head">
            <div class="card-title">
              <span class="step-dot">1</span>
              <div>
                <h2>CML Editor</h2>
                <p>Fetch the CML from a source org, edit it, then deploy to any target org.</p>
              </div>
            </div>
            <button class="btn btn-primary cml-main-action fetch-header-action" id="fetchBtn">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4M7 10l5 5 5-5M12 15V3"/></svg>
              Fetch CML
            </button>
          </div>

          <div class="editor-wrap">
            <div class="editor-head">
              <span class="ttl">CML Content</span>
              <div class="mini">
                <button class="ghost" id="lineCommentBtn" title="Toggle // on the selected line or lines (Cmd+/)">// Line comment</button>
                <button class="ghost" id="blockCommentBtn" title="Wrap or unwrap the selection with /* and */">/* */ Block comment</button>
                <button class="ghost" id="lintBtn" title="Scan against built-in best-practice rules">Check best practices</button>
                <button class="ghost" id="copyBtn">Copy</button>
              </div>
            </div>
            <div class="editor-body">
              <pre class="editor-line-numbers" id="contentLineNumbers" aria-hidden="true">1</pre>
              <div class="editor-code-pane">
                <pre class="editor-highlight" id="contentHighlight" aria-hidden="true"></pre>
                <textarea id="content" placeholder="Fetched CML appears here. You can also paste CML and Deploy it." spellcheck="false" wrap="off"></textarea>
              </div>
            </div>
          </div>

          <div class="cml-actions">
            <div class="deploy-panel">
              <div class="field">
                <label for="deployOrg">Deploy to org</label>
                <div class="org-picker" id="deployOrgPicker">
                  <button type="button" class="org-trigger" id="deployOrgTrigger" aria-haspopup="listbox" aria-expanded="false" disabled>
                    <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 21V8l8-5 8 5v13M8 21v-4h8v4M8 10h.01M12 10h.01M16 10h.01M8 13h.01M12 13h.01M16 13h.01"/></svg>
                    <span class="org-trigger-copy" id="deployOrgDisplay">Loading orgs…</span>
                    <svg class="version-chevron" viewBox="0 0 24 24" aria-hidden="true"><path d="m6 9 6 6 6-6"/></svg>
                  </button>
                  <div class="org-menu" id="deployOrgMenu" role="listbox" aria-label="Deployment orgs" hidden></div>
                  <select class="sr-only" id="deployOrg" tabindex="-1" aria-hidden="true"><option>Loading orgs…</option></select>
                </div>
              </div>
              <div class="field">
                <label for="deployVersion">Target exact CML version</label>
                <select id="deployVersion"><option value="">None — select deployment target</option></select>
                <span class="meta">Deployment-target runtime status can differ from the source.</span>
              </div>
              <div class="deploy-action-stack">
                <button class="btn btn-green cml-main-action" id="deployBtn">
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 16V3M7 8l5-5 5 5"/><path d="M5 21h14a2 2 0 0 0 2-2v-4M3 15v4a2 2 0 0 0 2 2"/></svg>
                  Deploy CML
                </button>
                <button class="ghost restore-action" id="rollbackBtn" title="Restore the newest saved backup for this target and model">
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 12a9 9 0 1 0 3-6.7L3 8"/><path d="M3 3v5h5"/></svg>
                  Restore Backup CML
                </button>
              </div>
            </div>
          </div>

          <div class="lint" id="lint"></div>
          <div class="status" id="status"></div>
        </div>
      </div>

      <!-- ══════════════ VIEW: COMPARE ══════════════ -->
      <div class="view-panel" id="view-compare">
        <div class="card">
          <div class="card-head">
            <div class="card-title">
              <span class="step-dot">2</span>
              <div>
                <h2>Compare CML</h2>
                <p>Review a VS Code-style side-by-side diff and apply selected source changes to a target draft.</p>
              </div>
            </div>
            <button class="btn btn-purple" id="compareBtn">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" style="vertical-align:-2px;margin-right:5px"><path d="M8 3H5a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h3M16 3h3a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2h-3M10 8l-3 4 3 4M14 8l3 4-3 4"/></svg>Compare source ↔ target
            </button>
          </div>

          <div class="diff" id="diff">
            <div class="diff-head">
              <div class="summary-stack">
                <div class="summary" id="diffSummary"></div>
                <div class="semantic-inline-summary" id="semanticInlineSummary" hidden></div>
              </div>
              <div class="legend">
                <span id="lineLegend">
                  <span><i class="lg-chg">~</i>Changed</span>
                  <span><i class="lg-del">&minus;</i>Only in source</span>
                  <span><i class="lg-ins">+</i>Only in target</span>
                </span>
                <label class="diff-opts" id="onlyDiffsWrap"><input type="checkbox" id="onlyDiffs" /> Show only differences</label>
                <label class="diff-opts" title="Show a separate structural summary without hiding either code pane"><input type="checkbox" id="semanticDiff" /> Semantic summary</label>
              </div>
            </div>
            <div class="merge-workflow" id="mergeWorkflow" hidden>
              <div class="merge-workflow-copy" id="mergeWorkflowCopy"></div>
              <div class="merge-workflow-actions">
                <button class="ghost" id="resetMergeBtn">Reset target draft</button>
                <button class="btn btn-green" id="reviewMergeBtn">Review &amp; Deploy target draft</button>
              </div>
            </div>
            <div class="diff-panes" id="diffPanes">
              <div class="pane">
                <div class="pane-title"><span class="pane-title-text" id="srcTitle">Source</span></div>
                <div class="pane-scroll" id="srcScroll"><table class="pane-table" id="srcTable"></table></div>
              </div>
              <div class="merge-rail" aria-label="Merge source changes into target draft">
                <div class="pane-title" title="Apply a source change to the target draft">→</div>
                <div class="merge-scroll" id="mergeScroll"><table class="merge-table" id="mergeTable"></table></div>
              </div>
              <div class="pane">
                <div class="pane-title">
                  <span class="pane-title-text" id="tgtTitle">Target</span>
                  <span class="pane-title-actions">
                    <button type="button" class="pane-copy" id="editTargetBtn" title="Edit any line in the local target working draft">
                      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 20h9"/><path d="M16.5 3.5a2.1 2.1 0 0 1 3 3L8 18l-4 1 1-4Z"/></svg>
                      <span>Edit target</span>
                    </button>
                    <button type="button" class="pane-copy" id="saveTargetEditBtn" hidden>Save edits</button>
                    <button type="button" class="pane-copy" id="cancelTargetEditBtn" hidden>Cancel</button>
                    <button type="button" class="pane-copy" id="copyTargetCmlBtn" title="Copy the complete target CML or current target draft">
                      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="9" y="9" width="11" height="11" rx="2"/><path d="M15 9V6a2 2 0 0 0-2-2H6a2 2 0 0 0-2 2v7a2 2 0 0 0 2 2h3"/></svg>
                      <span>Copy</span>
                    </button>
                  </span>
                </div>
                <div class="pane-scroll" id="tgtScroll">
                  <textarea class="target-draft-editor" id="tgtEditArea" aria-label="Edit target CML working draft" spellcheck="false" hidden></textarea>
                  <table class="pane-table" id="tgtTable"></table>
                </div>
              </div>
            </div>
          </div>

          <div id="compareStatus" class="status" style="margin-top:14px;display:none;"></div>
        </div>
      </div>

      <!-- ══════════════ VIEW: BEST PRACTICES ══════════════ -->
      <div class="view-panel" id="view-lint">
        <div class="card">
          <div class="card-head">
            <div class="card-title">
              <span class="step-dot" style="background:linear-gradient(135deg,var(--green),var(--teal));">3</span>
              <div>
                <h2>CML Quality Review</h2>
                <p>Client-side CML linter — checks rules, scores quality, and provides paste-ready fixes.</p>
              </div>
            </div>
            <button class="ghost" id="lintPanelBtn">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" style="vertical-align:-2px;margin-right:5px"><path d="M9 11l3 3L22 4"/><path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11"/></svg>Check best practices
            </button>
          </div>
          <p class="sub" style="margin-bottom:14px;">Paste or fetch a CML first using the <strong>Fetch &amp; Deploy</strong> tab, then run the check here.</p>
          <div class="lint" id="lintPanel"></div>
          <div class="status" id="lintStatus"></div>
        </div>
      </div>

      <!-- ══════════════ VIEW: CONSTRAINT DATA ══════════════ -->
      <div class="view-panel" id="view-data">
        <div class="card data-workspace-card">
          <div class="card-head">
            <div class="card-title">
              <span class="step-dot" style="background:linear-gradient(135deg,var(--teal),var(--accent-strong));">4</span>
              <div>
                <h2>Product Association Workspace</h2>
                <p>View, compare, and deploy ExpressionSetConstraintObj rows (Product associations).</p>
              </div>
            </div>
          </div>

          <div class="safety-alert" role="note">
            <span class="safety-alert-icon" aria-hidden="true">i</span>
            <div>
              <p>Deploying CML code alone doesn't recreate Product associations. These rows are matched across orgs by a <strong>foreign key</strong> — a field whose value is stable across orgs — instead of by record Id.</p>
              <p><strong>Safe deployment boundary:</strong> catalog records are read-only. The tool reports missing products, classifications, attributes, component groups, and relationships, but it only writes CML content and ExpressionSetConstraintObj associations.</p>
            </div>
          </div>

          <div class="data-action-row">
            <div class="field key-field-compact">
              <label for="keyField">Match records by (foreign key field)</label>
              <div class="key-field-picker" id="keyFieldPicker">
                <input id="keyField" value="" spellcheck="false" autocomplete="off"
                       role="combobox" aria-autocomplete="list" aria-expanded="false"
                       aria-controls="keyFieldMenu" placeholder="Select orgs to discover fields"
                       title="Search or enter a field API name that identifies the same record across orgs" />
                <button type="button" class="key-field-toggle" id="keyFieldToggle"
                        aria-label="Show detected foreign-key fields" tabindex="-1">
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2"
                       stroke-linecap="round" stroke-linejoin="round"><path d="m7 10 5 5 5-5"/></svg>
                </button>
                <div class="key-field-menu" id="keyFieldMenu" role="listbox" hidden></div>
              </div>
              <p class="meta" id="keyFieldHelp">Choose a unique external ID when possible. <code>Name</code> requires matching, unique values; duplicates are blocked.</p>
            </div>
            <div class="btn-row" style="margin-top:0;gap:8px;">
              <button class="btn btn-primary" id="loadDataBtn"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><circle cx="11" cy="11" r="7"/><path d="m20 20-4-4"/></svg>View data</button>
              <button class="btn btn-purple" id="compareDataBtn"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><path d="M7 7h11l-3-3M18 17H7l3 3M18 7l-3 3M7 17l3-3"/></svg>Compare data</button>
              <button class="btn btn-danger" id="stopCompareDataBtn" hidden><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><rect x="6" y="6" width="12" height="12" rx="1"/></svg>Stop Comparison</button>
            </div>
          </div>

          <div class="deploy-bar show" id="deployBar">
            <div class="sel-summary" id="selSummary">Compare source and target data to select rows for deployment.</div>
            <div class="sel-actions">
              <button class="linklike" id="selAllAdds" disabled>Select all adds</button>
              <button class="linklike" id="selNoAdds" disabled>Clear adds</button>
              <button class="linklike" id="selAllDels" disabled>Select all deletes</button>
              <button class="linklike" id="selNoDels" disabled>Clear deletes</button>
              <button class="btn btn-green" id="deployDataBtn" disabled><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><path d="m8 5 11 7-11 7z"/></svg>Deploy selected to target</button>
            </div>
          </div>

          <div class="data" id="data">
            <div class="data-head">
              <div class="chips" id="dataChips"></div>
              <div style="display:flex;align-items:center;gap:10px;flex-wrap:wrap;">
                <label class="data-filter">Show
                  <select id="dataFilter">
                    <option value="all">All rows</option>
                    <option value="match">Matched only</option>
                    <option value="add">Only in source (to add)</option>
                    <option value="extra">Only in target (extra)</option>
                    <option value="cml-difference">CML definition differences</option>
                    <option value="ambiguous-key">Ambiguous portable keys</option>
                    <option value="blocked">Blocked / unmappable</option>
                    <option value="stale">Unused association — absent from same org's CML</option>
                    <option value="dups">Duplicates only</option>
                  </select>
                </label>
                <button class="ghost" id="copyExcelBtn" disabled title="Copy visible rows as tab-separated values for Excel">Copy for Excel</button>
              </div>
            </div>

            <div class="table-scroll">
              <table class="data-table" id="dataTable"></table>
            </div>

            <div class="results" id="results"></div>
          </div>

          <div class="status" id="dataStatus"></div>
        </div>
      </div>

      <!-- ══════════════ VIEW: TOOL GUIDE ══════════════ -->
      <div class="view-panel" id="view-guide">
        <div class="card">
          <div class="guide-hero"><div><div class="eyebrow">Eight-step guide</div><h2>Safe operating workflow</h2>
            <p class="sub">Follow the complete path from prerequisite metadata through review, deployment, validation, and recovery.</p></div>
            <div class="guide-badges"><span class="guide-badge read"><span aria-hidden="true">✓</span>&nbsp; Read-only</span><span class="guide-badge write"><span aria-hidden="true">!</span>&nbsp; Writes Salesforce</span></div>
          </div>
          <section class="guide-prereqs" aria-labelledby="guidePrereqTitle">
            <h3 id="guidePrereqTitle">Before you move CML between orgs</h3>
            <p>CML text is only one part of a working constraint model. Confirm its dependent metadata and catalog data are available in the target org.</p>
            <ul>
              <li><strong>Context Definition tags and mappings:</strong> deploy every tag referenced by CML attributes to the target org. Without the corresponding Context Definition metadata, those attributes cannot resolve correctly at runtime.</li>
              <li><strong>Product associations:</strong> compare the related <code>ExpressionSetConstraintObj</code> rows separately in Constraint Data Deploy.</li>
              <li><strong>Catalog dependencies:</strong> products, classifications, attributes, component groups, and relationships are checked here but must be deployed through their owning process.</li>
              <li><strong>Exact versions:</strong> source, comparison target, and deployment target are separate selections and can have different runtime status.</li>
            </ul>
          </section>
          <div class="guide-steps">
            <article class="guide-step" data-guide-step="1">
              <span class="guide-number">1</span><div><span class="guide-badge read">Read-only</span>
              <h3>Choose the source</h3><p>Select the source org and exact CML version; do not assume the newest version is intended.</p>
              <ul class="guide-detail-list"><li>Confirm the org ID and model name.</li><li>Review whether status is runtime- or definition-based.</li><li>Fetching reads Salesforce and also saves a local working copy.</li></ul></div>
            </article>
            <article class="guide-step" data-guide-step="2">
              <span class="guide-number">2</span><div><span class="guide-badge read">Read-only</span>
              <h3>Fetch and inspect CML</h3><p>Load the exact source content into the editor and inspect it before comparing or deploying.</p>
              <ul class="guide-detail-list"><li>Confirm the fetched model is not empty.</li><li>Review comments, tags, relations, cardinalities, and attribute references.</li><li>Use Copy when an external review is required.</li></ul></div>
            </article>
            <article class="guide-step" data-guide-step="3">
              <span class="guide-number">3</span><div><span class="guide-badge read">Read-only</span>
              <h3>Compare and prepare the target draft</h3><p>Compare exact versions, then combine merge actions with direct target-draft edits.</p>
              <ul class="guide-detail-list"><li>Line comparison exposes exact text changes.</li><li>Semantic summary distinguishes structural changes from formatting.</li><li>Use <strong>Edit target</strong> to add comments or modify any line; saving refreshes the comparison.</li><li>No Salesforce data changes until the reviewed draft is deployed.</li></ul></div>
            </article>
            <article class="guide-step" data-guide-step="4">
              <span class="guide-number">4</span><div><span class="guide-badge read">Read-only</span>
              <h3>Check best practices</h3><p>Run the client-side quality review against the final draft before deployment.</p>
              <ul class="guide-detail-list"><li>Review every error, warning, and recommendation.</li><li>Validate generated fixes rather than applying them blindly.</li><li>The quality score is guidance—not proof that Salesforce will compile or activate the CML.</li></ul></div>
            </article>
            <article class="guide-step" data-guide-step="5">
              <span class="guide-number">5</span><div><span class="guide-badge read">Read-only</span>
              <h3>Validate target prerequisites</h3><p>Confirm the target is ready before selecting it for deployment.</p>
              <ul class="guide-detail-list"><li>Deploy referenced Context Definition tags and mappings first.</li><li>Verify required catalog records and relationships exist.</li><li>Compare Product associations using a unique, portable foreign key.</li><li>Active versions remain read-only in this tool.</li></ul></div>
            </article>
            <article class="guide-step" data-guide-step="6">
              <span class="guide-number">6</span><div><span class="guide-badge write">Writes Salesforce</span>
              <h3>Review and deploy CML</h3><p>Send the merged or manually edited target draft to Fetch &amp; Deploy for final review.</p>
              <ul class="guide-detail-list"><li>Re-read the complete target text in the editor.</li><li>Confirm the exact target org alias and version.</li><li>The tool creates a backup, writes CML, re-fetches it, and verifies its hash.</li><li>The tool does not activate or compile the model.</li></ul></div>
            </article>
            <article class="guide-step" data-guide-step="7">
              <span class="guide-number">7</span><div><span class="guide-badge write">Writes Salesforce</span>
              <h3>Deploy constraint data safely</h3><p>Deploy selected Product associations only after the dependency preflight is clear.</p>
              <ul class="guide-detail-list"><li>Additions are selected by default; deletions require explicit opt-in.</li><li>Blocked, ambiguous, stale, or CML-difference rows cannot be deployed.</li><li>Context Definition metadata is outside this association deployment and must already exist.</li><li>Review every row-level result and preserve the audit report.</li></ul></div>
            </article>
            <article class="guide-step" data-guide-step="8">
              <span class="guide-number">8</span><div><span class="guide-badge write">Writes Salesforce</span>
              <h3>Validate, activate, or recover</h3><p>Complete the platform validation that the local tool cannot perform, and recover deliberately if needed.</p>
              <ul class="guide-detail-list"><li>Validate Context Definition resolution and attribute behavior in the target org.</li><li>Compile, activate, and run scenario tests through the approved Salesforce process.</li><li>Use saved CML backups or association archives only after confirming the exact target again.</li><li>Treat a failed post-write refresh as partial deployment requiring recovery review.</li></ul></div>
            </article>
          </div>
          <aside class="guide-boundaries"><h3>What this tool does not prove</h3><ul>
            <li>Target status may differ by org; always review the selected target version in its own org.</li>
            <li>The tool does not compile, activate, or prove runtime behavior of CML.</li>
            <li>The tool does not deploy Context Definition tags or mappings; referenced metadata must be promoted separately.</li>
            <li>Catalog prerequisites are checked read-only and must be created or corrected externally.</li>
          </ul></aside>
        </div>
      </div>

    </div><!-- .wrap -->
  </main>
</div><!-- .app-shell -->

<dialog class="donate-dialog" id="donateDialog" aria-labelledby="donateTitle">
  <div class="donate-dialog-body">
    <div class="donate-dialog-head">
      <div>
        <div class="eyebrow">Optional contribution</div>
        <h2 id="donateTitle">UPI</h2>
      </div>
      <button type="button" class="ghost" id="donateCloseBtn" aria-label="Close donation dialog">Close</button>
    </div>
    <img class="donate-qr" src="/donate/upi-qr.png" alt="UPI payment QR code" />
    <p class="disclaimer">Contributions do not purchase support, features, priority
      service, or warranty. This project is not affiliated with or endorsed by Salesforce.</p>
    <div class="donate-actions">
      <a class="btn btn-primary" id="upiDonateLink"
        href="upi://pay?pa=mpancholi17%40ybl&amp;pn=Mritunjaya%20Pancholi&amp;tn=Support%20CML%20Tool&amp;cu=INR">
        Open UPI
      </a>
      <button type="button" class="ghost" id="copyUpiBtn" data-upi="mpancholi17@ybl">Copy UPI ID</button>
    </div>
    <p class="upi-note">Scan the QR code or open UPI. On desktop, copy the UPI ID.</p>
  </div>
</dialog>

<script>
  const $ = (id) => document.getElementById(id);
  const CSRF_TOKEN = "__CML_CSRF_TOKEN__";

  // ── Navigation ──────────────────────────────────────────────────
  const PAGE_META = {
    fetch:   { title:"Fetch &amp; Deploy",  sub:"Pick a source org — CMLs load automatically. Fetch, edit, and deploy to any org." },
    compare: { title:"Compare",             sub:"Use a VS Code-style diff to review and merge source changes into a guarded target draft." },
    lint:    { title:"Best Practices",      sub:"Client-side CML linter — checks rules, scores quality, and provides paste-ready fixes." },
    data:    { title:"Constraint Data Deploy", sub:"View, compare, and deploy ExpressionSetConstraintObj rows (Product associations)." },
    guide:   { title:"Guide Me on Tool",    sub:"A safe, numbered workflow for reviewing, deploying, and recovering CML." },
  };
  function switchView(view) {
    document.querySelectorAll(".view-panel").forEach(p => p.classList.remove("active"));
    const panel = $("view-" + view);
    if (panel) panel.classList.add("active");
    const connectionCard = $("connectionCard");
    if (connectionCard) connectionCard.hidden = view === "guide";
    document.querySelectorAll(".side-nav,.tab").forEach(b => {
      const active = b.dataset.view === view;
      b.classList.toggle("active", active);
      b.setAttribute("aria-selected", String(active));
    });
    const m = PAGE_META[view] || {};
    if ($("pageTitle")) $("pageTitle").innerHTML = m.title || view;
    if ($("pageSubtitle")) $("pageSubtitle").textContent = (m.sub || "").replace(/&amp;/g,"&");
  }
  document.querySelectorAll(".side-nav,.tab").forEach(b => {
    b.addEventListener("click", () => switchView(b.dataset.view));
  });
  const primaryNavButtons = Array.from(document.querySelectorAll("#sideNav [data-view]"));
  primaryNavButtons.forEach((button, index) => {
    button.addEventListener("keydown", event => {
      let next = null;
      if (event.key === "ArrowRight") next = (index + 1) % primaryNavButtons.length;
      if (event.key === "ArrowLeft") next = (index - 1 + primaryNavButtons.length) % primaryNavButtons.length;
      if (event.key === "Home") next = 0;
      if (event.key === "End") next = primaryNavButtons.length - 1;
      if (next !== null) {
        event.preventDefault();
        primaryNavButtons[next].focus();
        switchView(primaryNavButtons[next].dataset.view);
      }
    });
  });

  const orgSel = $("org"), targetSel = $("targetOrg"), targetVersionSel = $("targetVersion"), model = $("model"), content = $("content"), status = $("status");
  const sourceOrgPicker = $("sourceOrgPicker"), sourceOrgTrigger = $("sourceOrgTrigger");
  const sourceOrgDisplay = $("sourceOrgDisplay"), sourceOrgMenu = $("sourceOrgMenu");
  const targetOrgPicker = $("targetOrgPicker"), targetOrgTrigger = $("targetOrgTrigger");
  const targetOrgDisplay = $("targetOrgDisplay"), targetOrgMenu = $("targetOrgMenu");
  const sourceOrgId = $("sourceOrgId"), targetOrgId = $("targetOrgId");
  const contentLineNumbers = $("contentLineNumbers"), contentHighlight = $("contentHighlight");
  const fetchBtn = $("fetchBtn"), deployBtn = $("deployBtn"), rollbackBtn = $("rollbackBtn"), compareBtn = $("compareBtn"), copyBtn = $("copyBtn");
  const lineCommentBtn = $("lineCommentBtn"), blockCommentBtn = $("blockCommentBtn");
  const cmlFilter = $("cmlFilter"), cmlCount = $("cmlCount");
  const combo = $("combo"), comboSelected = $("comboSelected"), selectedName = $("selectedName");
  const sourceVersionTrigger = $("sourceVersionTrigger"), sourceVersionMenu = $("sourceVersionMenu");
  const sourceVersionOptions = $("sourceVersionOptions");
  const targetVersionPicker = $("targetVersionPicker"), targetVersionTrigger = $("targetVersionTrigger");
  const targetVersionDisplay = $("targetVersionDisplay"), targetVersionMenu = $("targetVersionMenu");
  const targetVersionFilter = $("targetVersionFilter"), targetVersionOptions = $("targetVersionOptions");
  const deployOrgSel = $("deployOrg"), deployVersionSel = $("deployVersion");
  const deployOrgPicker = $("deployOrgPicker"), deployOrgTrigger = $("deployOrgTrigger");
  const deployOrgDisplay = $("deployOrgDisplay"), deployOrgMenu = $("deployOrgMenu");
  const themeBtn = $("themeBtn"), themeIcon = $("themeIcon"), themeLabel = $("themeLabel"), conn = $("conn");
  const diffBox = $("diff"), diffSummary = $("diffSummary"), onlyDiffs = $("onlyDiffs");
  const diffPanes = $("diffPanes"), srcTable = $("srcTable"), tgtTable = $("tgtTable"), mergeTable = $("mergeTable");
  const srcTitle = $("srcTitle"), tgtTitle = $("tgtTitle"), srcScroll = $("srcScroll"), tgtScroll = $("tgtScroll"), mergeScroll = $("mergeScroll");
  const lintBtn = $("lintBtn"), lintBox = $("lint");
  const lintPanelBtn = $("lintPanelBtn"), lintPanel = $("lintPanel"), lintStatus = $("lintStatus");
  const semanticChk = $("semanticDiff"), semanticInlineSummary = $("semanticInlineSummary");
  const lineLegend = $("lineLegend"), onlyDiffsWrap = $("onlyDiffsWrap");
  const mergeWorkflow = $("mergeWorkflow"), mergeWorkflowCopy = $("mergeWorkflowCopy");
  const resetMergeBtn = $("resetMergeBtn"), reviewMergeBtn = $("reviewMergeBtn");
  const copyTargetCmlBtn = $("copyTargetCmlBtn"), editTargetBtn = $("editTargetBtn");
  const saveTargetEditBtn = $("saveTargetEditBtn"), cancelTargetEditBtn = $("cancelTargetEditBtn");
  const tgtEditArea = $("tgtEditArea");
  let lastCompare = null;
  let activeMergeHunks = [];
  let editingTarget = false;
  let semanticRefreshSequence = 0;
  const loadDataBtn = $("loadDataBtn"), compareDataBtn = $("compareDataBtn"), stopCompareDataBtn = $("stopCompareDataBtn"), keyField = $("keyField");
  const keyFieldPicker = $("keyFieldPicker"), keyFieldMenu = $("keyFieldMenu");
  const keyFieldToggle = $("keyFieldToggle"), keyFieldHelp = $("keyFieldHelp");
  const keyName = () => (keyField.value || "").trim();
  const dataBox = $("data"), dataChips = $("dataChips"), dataTable = $("dataTable"), dataFilter = $("dataFilter");
  const deployBar = $("deployBar"), selSummary = $("selSummary"), deployDataBtn = $("deployDataBtn");
  const selAllAdds = $("selAllAdds"), selNoAdds = $("selNoAdds"), selAllDels = $("selAllDels"), selNoDels = $("selNoDels");
  const copyExcelBtn = $("copyExcelBtn");
  const results = $("results");
  const donateBtn = $("donateBtn"), donateOptions = $("donateOptions");
  const donateUpiBtn = $("donateUpiBtn"), donateDialog = $("donateDialog");
  const donateCloseBtn = $("donateCloseBtn"), copyUpiBtn = $("copyUpiBtn");
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
  const selectedSourceVersion = () => allModels.find(m => m.versionId === model.value) || null;
  const selectedModelName = () => (selectedSourceVersion() || {}).name || "";
  const versionStatusLabel = (m) => {
    const basis = m && m.statusBasis === "runtime" ? "Runtime" : "Definition";
    return `${basis}: ${(m && m.status) || "Unknown"}`;
  };
  const selectedVersionLabel = (m) => m
    ? `${m.name} · V${m.version} · ${(m && m.status) || "Unknown"}`
    : "";

  // Size native picklists from their current option text. Containers wrap, so
  // a long exact-version label gets room instead of forcing button truncation.
  function fitPicklist(select) {
    if (!select) return;
    const texts = Array.from(select.options || []).map(option =>
      (option.textContent || "").trim());
    const selectedText = select.selectedOptions?.[0]?.textContent?.trim() || "";
    select.title = selectedText;
    if (select.hasAttribute("size")) {
      select.style.width = "100%";
      select.style.maxWidth = "100%";
      return;
    }
    const longest = Math.max(10, selectedText.length, ...texts.map(text => text.length));
    const desiredCh = Math.max(16, Math.min(96, longest + 5));
    select.style.width = `min(100%, ${desiredCh}ch)`;
    select.style.maxWidth = "100%";
    const field = select.closest(".field");
    if (field && field.parentElement?.classList.contains("conn-strip")) {
      const labelLength = (field.querySelector("label")?.textContent || "").trim().length;
      const fieldCh = Math.max(desiredCh, Math.min(96, labelLength + 4));
      field.style.flexBasis = `min(100%, ${fieldCh}ch)`;
    }
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
      helper.style.position = "fixed";
      helper.style.opacity = "0";
      document.body.appendChild(helper);
      helper.select();
      document.execCommand("copy");
      helper.remove();
    }
    copyUpiBtn.textContent = "UPI ID copied";
    setTimeout(() => { copyUpiBtn.textContent = "Copy UPI ID"; }, 1400);
  };

  // ---- CML editor line-number gutter ----
  function editorEsc(value) {
    return String(value).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
  }
  function renderEditorHighlight() {
    const source = content.value || "";
    let rendered = "", index = 0;
    while (index < source.length) {
      const quote = source[index];
      if (quote === '"' || quote === "'") {
        let end = index + 1;
        while (end < source.length) {
          if (source[end] === "\\\\") { end += 2; continue; }
          if (source[end] === quote) { end += 1; break; }
          end += 1;
        }
        rendered += editorEsc(source.slice(index, end));
        index = end;
        continue;
      }
      if (source.startsWith("//", index)) {
        let end = source.indexOf("\n", index);
        if (end < 0) end = source.length;
        rendered += `<span class="cml-comment">${editorEsc(source.slice(index, end))}</span>`;
        index = end;
        continue;
      }
      if (source.startsWith("/*", index)) {
        const close = source.indexOf("*/", index + 2);
        const end = close < 0 ? source.length : close + 2;
        rendered += `<span class="cml-comment">${editorEsc(source.slice(index, end))}</span>`;
        index = end;
        continue;
      }
      rendered += editorEsc(source[index]);
      index += 1;
    }
    contentHighlight.innerHTML = rendered + (source.endsWith("\n") ? " " : "\n");
    contentHighlight.scrollTop = content.scrollTop;
    contentHighlight.scrollLeft = content.scrollLeft;
  }
  function updateEditorLineNumbers() {
    const lineCount = Math.max(1, content.value.replace(/\r\n?/g, "\n").split("\n").length);
    contentLineNumbers.textContent = Array.from({ length: lineCount }, (_, index) => index + 1).join("\n");
    contentLineNumbers.scrollTop = content.scrollTop;
    renderEditorHighlight();
  }
  function setEditorContent(value) {
    content.value = value == null ? "" : String(value);
    updateEditorLineNumbers();
  }
  function syncEditorGutter() {
    contentLineNumbers.scrollTop = content.scrollTop;
    contentHighlight.scrollTop = content.scrollTop;
    contentHighlight.scrollLeft = content.scrollLeft;
  }
  function syncEditorGutterSize() {
    contentLineNumbers.style.height = content.offsetHeight + "px";
    syncEditorGutter();
  }
  function scrollEditorLineIntoView(line) {
    const styles = getComputedStyle(content);
    const lineHeight = parseFloat(styles.lineHeight) || (parseFloat(styles.fontSize) || 12.5) * 1.5;
    const topPadding = parseFloat(styles.paddingTop) || 0;
    const targetTop = topPadding + (Math.max(1, Number(line) || 1) - 1) * lineHeight;
    content.scrollTop = Math.max(0, targetTop - content.clientHeight / 2 + lineHeight / 2);
    syncEditorGutter();
  }
  content.addEventListener("input", updateEditorLineNumbers);
  content.addEventListener("scroll", syncEditorGutter, { passive: true });
  function replaceEditorRange(start, end, replacement, selectionStart, selectionEnd) {
    content.setRangeText(replacement, start, end, "select");
    content.setSelectionRange(selectionStart, selectionEnd);
    content.dispatchEvent(new Event("input", { bubbles:true }));
    content.focus();
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
  updateEditorLineNumbers();
  syncEditorGutterSize();
  if (typeof ResizeObserver === "function") {
    new ResizeObserver(syncEditorGutterSize).observe(content);
  } else {
    window.addEventListener("resize", syncEditorGutterSize);
  }

  // ---- Theme (day/night) ----
  function applyThemeLabel() {
    const t = document.documentElement.getAttribute("data-theme") || "light";
    themeLabel.textContent = t === "light" ? "Night mode" : "Day mode";
    themeIcon.innerHTML = t === "light"
      ? '<path d="M20.8 15.4A9 9 0 0 1 8.6 3.2 9 9 0 1 0 20.8 15.4Z"/>'
      : '<circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/>';
  }
  themeBtn.onclick = () => {
    const cur = document.documentElement.getAttribute("data-theme") || "light";
    const next = cur === "light" ? "dark" : "light";
    document.documentElement.setAttribute("data-theme", next);
    try { localStorage.setItem("cml-theme", next); } catch (e) {}
    applyThemeLabel();
  };
  applyThemeLabel();

  function setStatus(kind, msg, targetEl) {
    const el = targetEl || status;
    el.className = "status show " + kind;
    el.textContent = msg;
    el.scrollIntoView({ behavior: "smooth", block: "nearest" });
  }

  // A network-level failure means the local server isn't reachable (window
  // closed, restarted, etc). Mark it as a connection error so callers can
  // trigger auto-reconnect instead of showing a confusing message.
  async function apiGet(path) {
    let res;
    try { res = await fetch(path, { cache: "no-store" }); }
    catch (e) { throw { conn: true }; }
    const text = await res.text();
    try { return JSON.parse(text); }
    catch (e) { return { error: "Unexpected server response (HTTP " + res.status + "):\n" + text.slice(0, 500) }; }
  }

  async function postJSON(url, payload, options = {}) {
    let res;
    try {
      res = await fetch(url, {
        method: "POST", headers: {
          "Content-Type": "application/json", "X-CML-CSRF": CSRF_TOKEN
        },
        body: JSON.stringify(payload),
        signal: options.signal
      });
    } catch (e) {
      if (e && e.name === "AbortError") throw { aborted: true };
      throw { conn: true };
    }
    const text = await res.text();
    try { return JSON.parse(text); }
    catch (e) { return { ok: false, log: "Server returned an unexpected response (HTTP " + res.status + "):\n" + text.slice(0, 500) }; }
  }

  function showConn() {
    conn.className = "conn show";
    conn.innerHTML = '<span class="spinner"></span>Lost connection to the CML Tool. Make sure its window is still open — reconnecting automatically…';
  }
  function hideConn() { conn.className = "conn"; }

  function handleDisconnect() {
    if (reconnecting) return;
    reconnecting = true;
    showConn();
    const timer = setInterval(async () => {
      try {
        const r = await fetch("/api/orgs", { cache: "no-store" });
        if (r.ok) {
          clearInterval(timer);
          reconnecting = false;
          hideConn();
          setStatus("ok", "Reconnected to the CML Tool.");
          loadOrgs();
        }
      } catch (e) { /* still down; keep trying */ }
    }, 1500);
  }
  const actionBtns = [fetchBtn, deployBtn, rollbackBtn, compareBtn, loadDataBtn, compareDataBtn, deployDataBtn ];
  function busy(btn, label) {
    btn.innerHTML = '<span class="spinner"></span>' + label;
    actionBtns.forEach(b => b.disabled = true);
  }
  function idle() {
    fetchBtn.innerHTML = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4M7 10l5 5 5-5M12 15V3"/></svg>Fetch CML';
    deployBtn.innerHTML = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 16V3M7 8l5-5 5 5"/><path d="M5 21h14a2 2 0 0 0 2-2v-4M3 15v4a2 2 0 0 0 2 2"/></svg>Deploy CML';
    rollbackBtn.innerHTML = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 12a9 9 0 1 0 3-6.7L3 8"/><path d="M3 3v5h5"/></svg>Restore Backup CML';
    compareBtn.innerHTML = '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" style="vertical-align:-2px;margin-right:5px"><path d="M8 3H5a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h3M16 3h3a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2h-3M10 8l-3 4 3 4M14 8l3 4-3 4"/></svg>Compare source ↔ target';
    loadDataBtn.innerHTML = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><circle cx="11" cy="11" r="7"/><path d="m20 20-4-4"/></svg>View data';
    compareDataBtn.innerHTML = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><path d="M7 7h11l-3-3M18 17H7l3 3M18 7l-3 3M7 17l3-3"/></svg>Compare data';
    deployDataBtn.innerHTML = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><path d="m8 5 11 7-11 7z"/></svg>Deploy selected to target';
    actionBtns.forEach(b => b.disabled = false);
    updateDeployBar();
  }

  function selectedOrgInfo(alias) {
    return allOrgs.find(org => org.alias === alias) || null;
  }

  const ORG_ICON = '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 21V8l8-5 8 5v13M8 21v-4h8v4M8 10h.01M12 10h.01M16 10h.01M8 13h.01M12 13h.01M16 13h.01"/></svg>';
  const orgPickers = [
    { select:orgSel, picker:sourceOrgPicker, trigger:sourceOrgTrigger, display:sourceOrgDisplay,
      menu:sourceOrgMenu, placeholder:"Select a source org" },
    { select:targetSel, picker:targetOrgPicker, trigger:targetOrgTrigger, display:targetOrgDisplay,
      menu:targetOrgMenu, placeholder:"Select a target org" },
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
    config.display.textContent = selected ? selected.alias : config.placeholder;
    config.trigger.disabled = !allOrgs.length;
    config.menu.innerHTML = allOrgs.map(org => {
      const isSelected = org.alias === config.select.value;
      return `<button type="button" class="org-option${isSelected ? " selected" : ""}" role="option"`
        + ` aria-selected="${isSelected}" data-value="${esc(org.alias)}">${ORG_ICON}`
        + `<span class="org-option-copy"><span class="org-option-name">${esc(org.alias)}</span>`
        + `<span class="org-option-meta">${esc(org.username || "Salesforce org")}</span></span></button>`;
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
    sourceOrgId.textContent = `Org ID: ${(source && source.orgId) || "—"}`;
    targetOrgId.textContent = `Org ID: ${(target && target.orgId) || "—"}`;
  }

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

  async function loadOrgs() {
    try {
      const orgs = await apiGet("/api/orgs");
      if (orgs.error) {
        orgSel.innerHTML = '<option value="">(could not load orgs)</option>';
        setStatus("err", orgs.error);
        return;
      }
      if (!orgs.length) {
        orgSel.innerHTML = '<option value="">(no orgs found)</option>';
        setStatus("err",
          "No Salesforce orgs are authorized for THIS user on THIS computer.\n"
          + "Org logins are stored per operating-system user, so each person must log in on their own account:\n\n"
          + "    sf org login web --alias <name>\n\n"
          + "Then refresh the CML Tool. Open http://127.0.0.1:" + location.port + "/api/debug to see details (sf path, OS user, saved logins).");
        return;
      }
      allOrgs = orgs;
      const opts = orgs.map(o => `<option value="${o.alias}">${o.alias}${o.username ? "  —  " + o.username : ""}</option>`).join("");
      orgSel.innerHTML = '<option value="">None — select a source org</option>' + opts;
      targetSel.innerHTML = '<option value="">None — select a target org</option>' + opts;
      deployOrgSel.innerHTML = '<option value="">None — select a deployment target</option>' + opts;
      orgSel.value = "";
      targetSel.value = "";
      deployOrgSel.value = "";
      targetVersionSel.innerHTML = '<option value="">None — select target org and source version</option>';
      deployVersionSel.innerHTML = '<option value="">None — select deployment target and source version</option>';
      orgPickers.forEach(renderOrgPicker);
      renderSelectedOrgIds();
      loadKeyFields();
      loadModels();
    } catch (e) {
      if (e && e.conn) { handleDisconnect(); return; }
      orgSel.innerHTML = '<option value="">(could not load orgs)</option>';
      setStatus("err", "Could not load orgs: " + e);
    }
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
    selectedName.textContent = selected ? selectedVersionLabel(selected) : "Select exact CML version";
    closeVersionPicker(combo, sourceVersionTrigger, sourceVersionMenu);
  }
  function expandModelView() {
    openVersionPicker(combo, sourceVersionTrigger, sourceVersionMenu, cmlFilter);
  }
  model.addEventListener("change", () => {
    collapseModelView();
    renderModels();
    loadTargetVersions(targetSel, targetVersionSel, "compare");
    loadTargetVersions(deployOrgSel, deployVersionSel, "deployment");
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

  async function loadTargetVersions(orgControl, versionControl, purpose) {
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
      const data = await getOrgModels(org);
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
    targetVersionSel.innerHTML = '<option value="">None — select target org and source version</option>';
    deployVersionSel.innerHTML = '<option value="">None — select deployment target and source version</option>';
    renderSelectedOrgIds();
    loadKeyFields();
    loadModels();
  };
  targetSel.onchange = () => {
    renderSelectedOrgIds();
    loadKeyFields();
    loadTargetVersions(targetSel, targetVersionSel, "compare");
  };
  deployOrgSel.onchange = () => loadTargetVersions(deployOrgSel, deployVersionSel, "deployment");
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
    targetVersionDisplay.textContent = selected ? selectedVersionLabel(selected) : "Select exact CML version";
    renderTargetVersions();
    closeVersionPicker(targetVersionPicker, targetVersionTrigger, targetVersionMenu);
    targetVersionSel.dispatchEvent(new Event("change", { bubbles:true }));
  };
  targetVersionSel.addEventListener("change", () => {
    const selected = targetModels.find(item => item.versionId === targetVersionSel.value);
    targetVersionDisplay.textContent = selected ? selectedVersionLabel(selected) : "Select exact CML version";
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
        setEditorContent(data.content);
        setStatus("ok", data.log + "\n\nSaved to: " + data.file);
      } else {
        setStatus("err", data.log || "Fetch failed.");
      }
    } catch (e) {
      if (e && e.conn) { handleDisconnect(); } else { setStatus("err", "Fetch error: " + e); }
    }
    idle();
  };

  deployBtn.onclick = async () => {
    const dest = deployOrgSel.value;
    if (!dest) { setStatus("err", "Please choose an org to deploy to."); deployOrgSel.focus(); return; }
    const source = selectedSourceVersion();
    if (!source) { setStatus("err", "Please select an exact source CML version."); sourceVersionTrigger.focus(); return; }
    if (!deployVersionSel.value) { setStatus("err", "Please select an exact deployment target version."); deployVersionSel.focus(); return; }
    if (!content.value.trim()) { setStatus("err", "There is no CML content to deploy."); return; }
    const crossOrg = dest !== orgSel.value;
    let msg = `Deploy "${source.name}" to org "${dest}" exact version "${deployVersionSel.value}"?\n\nThis overwrites only that selected version's Constraint Model.`;
    if (crossOrg) msg += `\n\nNote: you are deploying to "${dest}", which is NOT the source org "${orgSel.value}".`;
    if (!confirm(msg)) return;
    const typed = prompt(`Production safety check:\nType the target org alias exactly to deploy:\n\n${dest}`);
    if (typed !== dest) { setStatus("err", "Deployment cancelled: target org alias did not match."); return; }
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
      setStatus(data.ok ? "ok" : "err", details);
    } catch (e) {
      if (e && e.conn) { handleDisconnect(); } else { setStatus("err", "Deploy error: " + e); }
    }
    idle();
  };

  rollbackBtn.onclick = async () => {
    const dest = deployOrgSel.value;
    const source = selectedSourceVersion();
    const selectedModel = source && source.name;
    const targetVersionId = deployVersionSel.value;
    if (!dest || !selectedModel || !targetVersionId) { setStatus("err", "Choose a target org, model, and exact target version first."); return; }
    try {
      const list = await apiGet(`/api/backups?org=${encodeURIComponent(dest)}&model=${encodeURIComponent(selectedModel)}&versionId=${encodeURIComponent(targetVersionId)}`);
      const backup = list.backups && list.backups[0];
      if (!backup) { setStatus("err", "No saved backup exists for this exact target version."); return; }
      const typed = prompt(`Restore the newest backup from ${backup.createdAt || "unknown time"}?\n\nType the target org alias exactly:\n${dest}`);
      if (typed !== dest) { setStatus("err", "Rollback cancelled: target org alias did not match."); return; }
      busy(rollbackBtn, "Restoring…");
      const data = await postJSON("/api/rollback", {
        org: dest, model: selectedModel, backupId: backup.id,
        targetVersionId,
        confirmTarget: typed
      });
      if (data.ok && typeof data.content === "string") setEditorContent(data.content);
      let details = data.log || (data.ok ? "Rollback complete." : "Rollback failed.");
      if (data.report && data.report.file) details += `\nDeployment report: ${data.report.file}`;
      setStatus(data.ok ? "ok" : "err", details);
    } catch (e) {
      if (e && e.conn) { handleDisconnect(); } else { setStatus("err", "Rollback error: " + e); }
    }
    idle();
  };

  copyBtn.onclick = async () => {
    if (!content.value) return;
    try { await navigator.clipboard.writeText(content.value); copyBtn.textContent = "Copied!"; setTimeout(() => copyBtn.textContent = "Copy", 1200); }
    catch (e) { content.select(); document.execCommand("copy"); }
  };

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

  function paneRow(rowType, num, codeHtml, marker, semanticMark) {
    const baseClass = rowType === "eq" ? "eqrow"
      : rowType === "chg" ? "row-chg"
      : rowType === "del" ? "row-del"
      : rowType === "ins" ? "row-ins" : "row-filler";
    if (rowType === "filler") {
      return `<tr class="row-filler"><td class="gutter">&nbsp;</td><td class="code">&nbsp;</td></tr>`;
    }
    const semantic = semanticDecoration(semanticMark);
    const mk = `<span class="mk">${marker}</span>`;
    return `<tr class="${baseClass}${semantic.className}"><td class="gutter">${num}</td><td class="code">${mk}${semantic.badges}${codeHtml}</td></tr>`;
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
      const buttons = ids.map(index => {
        const action = activeMergeHunks[index];
        return `<button type="button" class="merge-arrow semantic-merge-arrow" data-merge-hunk="${index}" title="${esc(action.title)}" aria-label="${esc(action.title)}">→</button>`;
      }).join("");
      return `<tr${row.type === "eq" ? ' class="eqrow"' : ""}><td>${buttons || "&nbsp;"}</td></tr>`;
    }
    if (row.type === "eq") return '<tr class="eqrow"><td>&nbsp;</td></tr>';
    const button = row.mergeLead
      ? `<button type="button" class="merge-arrow" data-merge-hunk="${row.mergeId}" title="Apply this source change to the target draft" aria-label="Apply source change to target draft">→</button>`
      : "&nbsp;";
    return `<tr><td>${button}</td></tr>`;
  }

  function updateMergeWorkflow() {
    const count = lastCompare ? lastCompare.mergeCount || 0 : 0;
    mergeWorkflow.hidden = count === 0;
    if (!count) return;
    mergeWorkflowCopy.textContent = `${count} change${count === 1 ? "" : "s"} applied to the target working draft by merge or direct edit. Salesforce has not been changed yet.`;
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

    let chg = 0, del = 0, ins = 0, left = "", middle = "", right = "";
    const renderedSemanticActions = new Set();
    for (const r of rows) {
      middle += mergeRailRow(r, renderedSemanticActions);
      if (r.type === "eq") {
        left += paneRow("eq", r.a + 1, esc(a[r.a]), " ", semanticMaps.source.get(r.a + 1));
        right += paneRow("eq", r.b + 1, esc(b[r.b]), " ", semanticMaps.target.get(r.b + 1));
      } else if (r.type === "chg") {
        chg++;
        left += paneRow("chg", r.a + 1, esc(a[r.a]), "~", semanticMaps.source.get(r.a + 1));
        right += paneRow("chg", r.b + 1, esc(b[r.b]), "~", semanticMaps.target.get(r.b + 1));
      } else if (r.type === "del") {
        del++;
        left += paneRow("del", r.a + 1, esc(a[r.a]), "−", semanticMaps.source.get(r.a + 1));
        right += paneRow("filler");
      } else {
        ins++;
        left += paneRow("filler");
        right += paneRow("ins", r.b + 1, esc(b[r.b]), "+", semanticMaps.target.get(r.b + 1));
      }
    }
    srcTable.innerHTML = "<tbody>" + left + "</tbody>";
    mergeTable.innerHTML = "<tbody>" + middle + "</tbody>";
    tgtTable.innerHTML = "<tbody>" + right + "</tbody>";
    srcTitle.textContent = "Source — " + src.org;
    tgtTitle.textContent = (lastCompare && lastCompare.mergeCount ? "Target draft — " : "Target — ") + tgt.org;
    diffPanes.classList.toggle("hide-eq", onlyDiffs.checked);
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
      requestAnimationFrame(() => { syncing = false; });
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

  onlyDiffs.onchange = () => diffPanes.classList.toggle("hide-eq", onlyDiffs.checked);
  mergeTable.onclick = async event => {
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
    setEditorContent(lastCompare.tgt.content);
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
      helper.style.position = "fixed";
      helper.style.opacity = "0";
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
    let html = `<div class="lint-head"><h4>Best practices</h4>`
      + `<span class="lint-score ${scoreCls}">Quality score ${score}/100</span></div>`
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
    lintBox.scrollIntoView({ behavior: "smooth", block: "nearest" });
  }

  function doLint() {
    if (!content.value.trim()) {
      setStatus("err", "Paste or fetch some CML first (Fetch & Deploy tab), then check best practices.");
      if (lintStatus) { lintStatus.className = "status show err"; lintStatus.textContent = "No CML to check. Go to Fetch & Deploy, fetch or paste a CML, then return here."; }
      return;
    }
    renderLint(content.value);
    // also populate the dedicated panel
    if (lintPanel) { lintPanel.innerHTML = lintBox.innerHTML; lintPanel.className = "lint show"; }
    if (lintStatus) lintStatus.className = "status";
  }
  lintBtn.onclick = () => { doLint(); };
  if (lintPanelBtn) lintPanelBtn.onclick = () => { doLint(); switchView("lint"); };

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

  function dataRowHtml(r, withStatus) {
    const hasKeyValue = r.gkey !== null && r.gkey !== undefined && String(r.gkey).trim() !== "";
    const gk = hasKeyValue
      ? `<span class="gkey">${esc(r.gkey)}</span>`
      : `<span class="badge b-unmappable">${esc(currentKeyField)} is blank</span>`;
    const blockNote = r.blockNote ? `<span class="block-note">${esc(r.blockNote)}</span>` : "";
    let sel = "";
    if (withStatus) {
      if (isAdd(r) || isDel(r)) {
        sel = `<td class="col-sel"><input type="checkbox" data-i="${r._i}" ${r._selected ? "checked" : ""} aria-label="Select ${esc(statusText(r))} association"></td>`;
      } else {
        sel = `<td class="col-sel"></td>`;
      }
    }
    return "<tr>"
      + sel
      + (withStatus ? `<td class="col-status">${statusBadge(r._status)}${blockNote}</td>` : "")
      + `<td class="col-reftype"><span class="badge b-type">${esc(shortType(r.refType))}</span></td>`
      + `<td class="col-tagtype">${esc(r.tagType)}</td>`
      + `<td class="col-tag">${esc(r.tag)}</td>`
      + `<td class="col-ref">${referenceRecordHtml(r)}${dupBadges(r)}</td>`
      + `<td class="col-key">${gk}</td>`
      + "</tr>";
  }

  function renderDataTable() {
    const withStatus = dataMode === "compare";
    const f = dataFilter.value;
    const visible = dataRows.filter(r => {
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
    });
    const cols = (withStatus ? 7 : 5);
    const head = "<thead><tr>"
      + (withStatus ? '<th class="col-sel" scope="col" title="Select associations for the deploy action">Select</th><th class="col-status">Status</th>' : "")
      + '<th class="col-reftype">Ref type</th><th class="col-tagtype">Tag type</th><th class="col-tag">Tag</th><th class="col-ref">Reference record</th><th class="col-key">' + esc(currentKeyField) + "</th>"
      + "</tr></thead>";
    const body = visible.length
      ? visible.map(r => dataRowHtml(r, withStatus)).join("")
      : `<tr><td colspan="${cols}" style="text-align:center;color:var(--muted);padding:18px;">No rows for this filter.</td></tr>`;
    dataTable.innerHTML = head + "<tbody>" + body + "</tbody>";
    dataTable.querySelectorAll("input[type=checkbox]").forEach(cb => {
      cb.onchange = () => { dataRows[+cb.dataset.i]._selected = cb.checked; updateDeployBar(); };
    });
    copyExcelBtn.disabled = visible.length === 0;
    updateDeployBar();
  }
  dataFilter.onchange = renderDataTable;

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
    const f = dataFilter.value;
    const visible = dataRows.filter(r => {
      if (f === "all") return true;
      if (f === "match")   return r._status === "match";
      if (f === "add")     return r._status === "add";
      if (f === "extra")   return r._status === "extra";
      if (f === "cml-difference") return r._status === "cml-difference";
      if (f === "blocked") return r._status === "blocked" || r._status === "unmappable" || r._status === "dependency-unverified";
      if (f === "stale")   return r._status === "stale";
      if (f === "dups")    return r.dups && r.dups.length;
      return true;
    });
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
      ta.value = tsv; ta.style.position = "fixed"; ta.style.opacity = "0";
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
        renderDataChips({ single: false, s: data.stats, src: data.source, tgt: data.target });
        renderDataTable();
        dataBox.classList.add("show");
        dataBox.scrollIntoView({ behavior: "smooth", block: "nearest" });
        setStatus("ok", `Compared constraint data for "${data.model}".\n`
          + `${data.stats.matched} matched · ${data.stats.sourceOnly} only in source · ${data.stats.targetOnly} only in target`
          + (data.stats.cmlDifferences ? ` · ${data.stats.cmlDifferences} explained by different CML definitions` : "")
          + (data.stats.ambiguousKeys ? ` · ${data.stats.ambiguousKeys} ambiguous portable key(s)` : "")
          + (data.stats.dependencyIssues ? ` · ${data.stats.dependencyIssues} catalog dependency finding(s)` : "")
          + (data.stats.dependencyUnverified ? ` · ${data.stats.dependencyUnverified} dependency check(s) need a key` : "")
          + (data.stats.stale ? ` · ${data.stats.stale} stale (excluded)` : "")
          + `.\n${data.associationScopeNote}`
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

  function renderDataChips(o) {
    if (o.single) {
      const dn = dupSum(o.dups);
      const scope = o.duplicateScope?.expressionSetId || "selected parent";
      dataChips.innerHTML =
        `<span class="chip ok">${o.total} rows · ${o.org}</span>`
        + `<span class="chip" title="ExpressionSet.ApiName and definition DeveloperName">${esc(o.apiName || "")}</span>`
        + (o.unmappable ? `<span class="chip warn">${o.unmappable} without ${currentKeyField}</span>` : "")
        + (o.duplicateCheckError ? `<span class="chip warn">Duplicate check unavailable</span>` : "")
        + (dn ? `<span class="chip warn" title="Checked only within Expression Set ${esc(scope)}">${dn} duplicate flags · selected model only</span>` : "");
      return;
    }
    const s = o.s;
    const sd = dupSum(o.src.duplicates), td = dupSum(o.tgt.duplicates);
    dataChips.innerHTML =
      `<span class="chip neutral">Source ${o.src.org}: ${o.src.total}</span>`
      + `<span class="chip neutral">Target ${o.tgt.org}: ${o.tgt.total}</span>`
      + `<span class="chip ok">${s.matched} matched</span>`
      + `<span class="chip add">${s.sourceOnly} only in source</span>`
      + `<span class="chip extra">${s.targetOnly} only in target</span>`
      + (s.cmlDifferences ? `<span class="chip cml-diff">${s.cmlDifferences} CML definition differences (not errors)</span>` : "")
      + (s.ambiguousKeys ? `<span class="chip warn">${s.ambiguousKeys} ambiguous portable keys</span>` : "")
      + (s.dependencyIssues ? `<span class="chip warn">${s.dependencyIssues} catalog dependency findings</span>` : "")
      + (s.dependencyUnverified ? `<span class="chip warn">${s.dependencyUnverified} dependency checks need review</span>` : "")
      + (s.exactDuplicates ? `<span class="chip dup">${s.exactDuplicates} exact duplicate rows</span>` : "")
      + (s.stale ? `<span class="chip warn">${s.stale} stale (excluded from deploy)</span>` : "")
      + (s.blocked ? `<span class="chip warn">${s.blocked} blocked by catalog dependencies</span>` : "")
      + (s.unmappable ? `<span class="chip warn">${s.unmappable} unmappable</span>` : "")
      + ((o.src.duplicateCheckError || o.tgt.duplicateCheckError)
        ? `<span class="chip warn">Duplicate check unavailable for one selected CML</span>` : "")
      + ((sd + td) ? `<span class="chip dup" title="Each org is checked independently inside the exact selected version's resolved parent Expression Set">${sd + td} duplicate flags (selected source ${sd} / selected target ${td})</span>` : "");
  }

  // ---- Deploy selected constraint data to the target ----
  function renderResults(data) {
    const s = data.stats;
    let html = `<h4>Deployment results — target ${esc(data.target)}</h4>`;
    if (data.outcome === "partial") {
      const partialText = data.recoveryRequired
        ? (data.log || "RECOVERY REQUIRED — associations changed but runtime validation is not established.")
        : "Partial deployment: Salesforce applied some rows and rejected others because allOrNone=false. Review every failed row before retrying.";
      html += `<div class="status show err" style="margin-bottom:10px;"><strong>${esc(partialText)}</strong></div>`;
    }
    html += `<div class="chips" style="margin-bottom:10px;">`
      + `<span class="chip ok">${s.insertOk} added</span>`
      + (s.insertSkipped ? `<span class="chip warn">${s.insertSkipped} duplicate add skipped</span>` : "")
      + (s.insertFail ? `<span class="chip warn">${s.insertFail} add failed</span>` : "")
      + `<span class="chip extra">${s.deleteOk} deleted</span>`
      + (s.deleteFail ? `<span class="chip warn">${s.deleteFail} delete failed</span>` : "")
      + `</div>`;
    const line = (r, verb) => `<div class="result-row ${r.success ? "good" : "bad"}">`
      + `<span class="ico">${r.success ? "✓" : (r.skipped ? "○" : "✗")}</span>`
      + `<span>${r.skipped ? "Skip" : verb} ${esc(r.label)}${r.success ? "" : " — " + esc(r.error || "failed")}</span></div>`;
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
      html += `<div style="margin-top:10px;"><button class="ghost" id="restoreArchiveBtn">Restore deleted associations</button></div>`;
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
      const typed = prompt(`Restore deleted associations?\n\nType the target org alias exactly:\n${dest}`);
      if (typed !== dest) { setStatus("err", "Restore cancelled: target org alias did not match.", dSt()); return; }
      busy(restoreBtn, "Restoring…");
      try {
        const restored = await postJSON("/api/data/restore", {
          targetOrg: dest, model: data.model,
          targetVersionId: data.targetVersionId,
          archiveId: data.archive.id, confirmTarget: typed
        });
        setStatus(restored.ok ? "ok" : "err", restored.log || "Association restore finished.", dSt());
      } catch (e) {
        if (e && e.conn) { handleDisconnect(); } else { setStatus("err", "Restore error: " + e, dSt()); }
      }
      restoreBtn.textContent = "Restore deleted associations";
      idle();
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
    let msg = `Deploy to "${targetSel.value}"?\n\n• ${adds.length} association(s) will be ADDED.`;
    if (deletes.length) msg += `\n• ${deletes.length} association(s) will be DELETED (permanent).`;
    msg += `\n\nProceed?`;
    if (!confirm(msg)) return;
    const typed = prompt(`Production safety check:\nType the target org alias exactly to deploy:\n\n${targetSel.value}`);
    if (typed !== targetSel.value) { setStatus("err", "Deployment cancelled: target org alias did not match.", dSt()); return; }
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
          `Done. Added ${s.insertOk}/${adds.length}, deleted ${s.deleteOk}/${deletes.length}.`
          + (s.insertFail + s.deleteFail ? ` ${s.insertFail + s.deleteFail} failed — see details below.` : "")
          + (s.insertSkipped ? ` ${s.insertSkipped} exact duplicate add skipped.` : "")
          + (refreshFailed ? ` RECOVERY REQUIRED — associations changed, but the tool-specific CML save/verification refresh failed; runtime validation is not established.` : "")
          + `\nReview the saved report and recovery options below, then click Compare data to refresh.`, dSt());
      } else {
        setStatus("err", data.log || "Deploy failed.", dSt());
      }
    } catch (e) {
      if (e && e.conn) { handleDisconnect(); } else { setStatus("err", "Deploy error: " + e, dSt()); }
    }
    idle();
  };

  fetch("/api/ping", { cache: "no-store" })
    .then(r => r.json())
    .then(d => { const e = $("appver"); if (e) e.textContent = "build " + (d.build || "?").slice(0, 8); })
    .catch(() => {});

  loadOrgs();
</script>
</body>
</html>"""
