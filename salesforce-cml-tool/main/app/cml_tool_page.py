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
    --bg:#f7f8fc; --panel:#ffffff; --gutter:#f0f3fa; --input-bg:#fbfcff;
    --line:#dce2ef; --text:#172033; --muted:#667085; --gutter-text:#8490a6; --comment:#9aa4b5;
    --accent:#3b82f6; --accent-strong:#06b6d4; --green:#22c55e; --red:#ef4444;
    --purple:#8b5cf6; --amber:#f59e0b; --teal:#06b6d4; --on-accent:#ffffff;
    --radius:18px;
    --ok-bg:color-mix(in srgb,var(--green) 11%,var(--panel)); --ok-text:#08734f;
    --err-bg:color-mix(in srgb,var(--red) 10%,var(--panel)); --err-text:#b4233f;
    --info-bg:color-mix(in srgb,var(--accent) 9%,var(--panel)); --info-text:#3f40bd;
    --teal-bg:color-mix(in srgb,var(--teal) 10%,var(--panel)); --teal-text:#07657c;
    --chg-bg:color-mix(in srgb,var(--purple) 14%,var(--panel));
    --del-bg:color-mix(in srgb,var(--red) 12%,var(--panel));
    --ins-bg:color-mix(in srgb,var(--teal) 13%,var(--panel));
    --chg-line:var(--purple); --del-line:var(--red); --ins-line:var(--teal);
    --shadow:0 16px 44px rgba(29,39,70,.08);
  }
  html[data-theme="dark"] {
    color-scheme: dark;
    --bg:#090e1a; --panel:#11182a; --gutter:#171f34; --input-bg:#0c1323;
    --line:#303b57; --text:#f4f7ff; --muted:#b5bfd3; --gutter-text:#7f8ba5; --comment:#929db2;
    --accent:#60a5fa; --accent-strong:#22d3ee; --green:#4ade80; --red:#f87171;
    --purple:#a78bfa; --amber:#fbbf24; --teal:#22d3ee;
    --ok-bg:color-mix(in srgb,var(--green) 13%,var(--panel)); --ok-text:#a7f3d0;
    --err-bg:color-mix(in srgb,var(--red) 13%,var(--panel)); --err-text:#fecdd3;
    --info-bg:color-mix(in srgb,var(--accent) 13%,var(--panel)); --info-text:#d9dcff;
    --teal-bg:color-mix(in srgb,var(--teal) 12%,var(--panel)); --teal-text:#a5f3fc;
    --shadow:0 20px 60px rgba(0,0,0,.30);
  }
  * { box-sizing: border-box; }
  html,body { width:100%; height:100%; max-width:100%; overflow:hidden; }
  body {
    margin:0; font-family:Inter,-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;
    min-height:100vh;
    background:
      radial-gradient(circle at 8% 0%,color-mix(in srgb,var(--accent) 8%,transparent),transparent 28rem),
      radial-gradient(circle at 92% 5%,color-mix(in srgb,var(--teal) 7%,transparent),transparent 30rem),
      var(--bg);
    color:var(--text); line-height:1.5;
    transition:background-color .2s ease,color .2s ease;
  }
  button,input,select,textarea { font:inherit; }
  [hidden] { display:none !important; }

  /* ── App shell ────────────────────────────────────────────────── */
  .app-shell { height:100vh; min-height:0; display:grid; grid-template-columns:244px minmax(0,1fr); overflow:hidden; }
  .sidebar { position:relative; height:100vh; min-height:0; display:flex; flex-direction:column;
    padding:22px 14px 16px; background:color-mix(in srgb,var(--panel) 92%,var(--bg));
    border-right:1px solid var(--line); z-index:20; overflow-y:auto; }
  .brand { display:flex; align-items:center; gap:11px; padding:0 8px 26px; color:var(--text); text-decoration:none; }
  .brand-mark { width:36px; height:36px; flex:0 0 36px; display:grid; place-items:center; border-radius:12px;
    background:linear-gradient(135deg,var(--accent),var(--accent-strong));
    box-shadow:0 8px 22px color-mix(in srgb,var(--accent) 24%,transparent); }
  .brand-mark svg { width:22px; fill:var(--on-accent); }
  .brand strong,.brand small { display:block; line-height:1.2; }
  .brand strong { font-size:13px; }
  .brand small { margin-top:3px; color:var(--muted); font-size:11px; font-weight:600; }
  .side-label { color:var(--muted); font-size:10px; font-weight:800; letter-spacing:.12em;
    text-transform:uppercase; padding:0 12px 8px; }
  .side-menu { display:grid; min-width:0; gap:5px; }
  .side-nav { width:100%; border:0; display:flex; align-items:center; gap:10px; padding:10px 12px;
    border-radius:12px; background:transparent; color:var(--muted); font-size:13px; font-weight:650;
    text-align:left; cursor:pointer; transition:background .2s,color .2s,transform .2s; }
  .side-nav:hover { color:var(--text); background:var(--gutter); transform:translateX(2px); }
  .side-nav.active { color:var(--accent); background:color-mix(in srgb,var(--accent) 11%,var(--panel));
    box-shadow:inset 3px 0 0 var(--accent); }
  .nav-icon { width:21px; height:21px; display:grid; place-items:center; flex:0 0 21px; }
  .nav-icon svg { width:17px; height:17px; fill:none; stroke:currentColor; stroke-width:1.8;
    stroke-linecap:round; stroke-linejoin:round; }
  .sidebar-footer { margin-top:auto; border-top:1px solid var(--line); padding-top:12px; }
  .about-link { width:100%; border:0; display:flex; align-items:center; gap:10px; padding:10px 12px;
    border-radius:12px; background:transparent; color:var(--muted); text-decoration:none; font-size:13px;
    font-weight:650; cursor:pointer; transition:background .2s,color .2s,transform .2s; }
  .about-link:hover { color:var(--text); background:var(--gutter); transform:translateX(2px); }
  .donate-link { color:var(--accent); }
  .donate-wrap { width:100%; position:relative; }
  .donate-options { display:grid; gap:5px; margin:3px 6px 8px 12px; padding-left:9px;
    border-left:1px solid var(--line); }
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
  .sidebar .credit { padding:10px 12px 0; margin:0; font-size:10px; line-height:1.5; color:var(--muted); }
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
  .app-main { min-width:0; min-height:0; height:100vh; display:flex; flex-direction:column;
    overflow-y:auto; overflow-x:hidden; scrollbar-gutter:stable; }
  .topbar { display:flex; align-items:center; justify-content:space-between; gap:20px;
    padding:22px clamp(14px,2.2vw,36px) 18px; position:relative; overflow:hidden; min-height:100px; }
  .topbar::after { content:""; position:absolute; right:-80px; top:-130px; width:420px; height:260px;
    pointer-events:none; background:radial-gradient(circle,color-mix(in srgb,var(--teal) 18%,transparent),transparent 68%); }
  .topbar > * { position:relative; z-index:1; }
  .eyebrow { color:var(--muted); font-size:10px; font-weight:800; letter-spacing:.12em; text-transform:uppercase; margin-bottom:4px; }
  h1 { font-size:clamp(22px,2vw,30px); letter-spacing:-.03em; margin:0 0 3px; }
  .sub { color:var(--muted); font-size:13px; margin:0; }
  .top-actions { display:flex; align-items:center; gap:10px; flex-shrink:0; }
  .local-badge { display:inline-flex; align-items:center; gap:7px; padding:8px 11px;
    border:1px solid var(--line); border-radius:12px;
    background:color-mix(in srgb,var(--panel) 88%,transparent); color:var(--muted); font-size:11px; font-weight:700; }
  .live-dot { width:7px; height:7px; border-radius:50%; background:var(--green);
    box-shadow:0 0 0 4px color-mix(in srgb,var(--green) 14%,transparent); }
  .wrap { padding:0 clamp(14px,2.2vw,36px) 64px; }

  /* ── Tabs ─────────────────────────────────────────────────────── */
  .tabs { display:inline-flex; max-width:100%; gap:5px; background:var(--gutter); border:1px solid var(--line);
    border-radius:14px; padding:5px; margin-bottom:18px; flex-wrap:wrap; }
  .tab { border:none; background:transparent; color:var(--muted); font-weight:600; font-size:13px;
    padding:8px 16px; border-radius:10px; cursor:pointer; transition:background .2s,color .2s; }
  .tab:hover { background:color-mix(in srgb,var(--accent) 10%,transparent); color:var(--text); }
  .tab.active { background:var(--accent); color:var(--on-accent);
    box-shadow:0 6px 18px color-mix(in srgb,var(--accent) 28%,transparent); }

  /* ── Panels ───────────────────────────────────────────────────── */
  .view-panel { display:none; }
  .view-panel.active { display:block; }
  .card { background:var(--panel); border:1px solid var(--line); border-radius:var(--radius);
    padding:clamp(14px,1.5vw,24px); box-shadow:var(--shadow); margin-bottom:18px; }
  .card-head { display:flex; align-items:flex-start; justify-content:space-between; gap:14px;
    padding-bottom:16px; margin-bottom:18px; border-bottom:1px solid var(--line); }
  .card-title { display:flex; align-items:flex-start; gap:11px; min-width:0; }
  .step-dot { width:27px; height:27px; flex:0 0 27px; display:grid; place-items:center; border-radius:9px;
    background:linear-gradient(135deg,var(--accent),var(--accent-strong)); color:var(--on-accent);
    font-size:12px; font-weight:800; box-shadow:0 7px 16px color-mix(in srgb,var(--accent) 22%,transparent); }
  .card-title h2 { margin:0; font-size:15px; letter-spacing:-.01em; }
  .card-title p { margin:3px 0 0; color:var(--muted); font-size:12px; }

  /* ── Connection strip ─────────────────────────────────────────── */
  .conn-strip { display:grid; grid-template-columns:minmax(0,1fr) minmax(0,1fr);
    gap:14px; align-items:start; }
  .conn-strip > .field { max-width:100%; }
  .conn-strip > .reload-field { grid-column:1 / -1; justify-self:start; }
  .field { min-width:0; max-width:100%; }
  label { display:block; font-size:11px; color:var(--muted); margin-bottom:5px;
    text-transform:uppercase; letter-spacing:.05em; font-weight:700; }
  select,input { width:100%; background:var(--input-bg); color:var(--text); border:1px solid var(--line);
    border-radius:12px; padding:9px 13px; font-size:13px; outline:none;
    transition:border-color .16s,box-shadow .16s; }
  select:focus,input:focus { border-color:var(--accent); box-shadow:0 0 0 4px color-mix(in srgb,var(--accent) 16%,transparent); }
  textarea { width:100%; background:var(--input-bg); color:var(--text); border:1px solid var(--line);
    border-radius:14px; padding:10px 13px; font-size:12.5px; outline:none;
    font-family:"JetBrains Mono","Fira Code",ui-monospace,"SF Mono",Menlo,Consolas,monospace;
    min-height:320px; resize:vertical; white-space:pre; tab-size:2;
    transition:border-color .16s,box-shadow .16s; }
  textarea:focus { border-color:var(--accent); box-shadow:0 0 0 4px color-mix(in srgb,var(--accent) 16%,transparent); }

  /* combo / model picker */
  .combo { display:flex; flex-direction:column; gap:6px; }
  select[size] { padding:0; height:auto; border-radius:12px; }
  select[size] option { padding:7px 12px; border-bottom:1px solid var(--line); }
  select[size] option:checked { background:var(--accent); color:#fff; }
  .combo-selected { display:flex; align-items:center; gap:10px; flex-wrap:wrap; }
  .selchip { flex:1; display:inline-flex; align-items:center; gap:8px; padding:9px 13px;
    border-radius:12px; background:linear-gradient(135deg,var(--accent),var(--accent-strong));
    color:#fff; font-weight:700; font-size:13px; min-width:0; }
  .selchip .name { overflow:visible; text-overflow:clip; white-space:normal; overflow-wrap:anywhere; }
  .selchip::before { content:"✓"; font-weight:700; flex:none; }
  .meta { color:var(--muted); font-size:11px; }

  /* ── Buttons ──────────────────────────────────────────────────── */
  button { font-family:inherit; }
  .btn-row { display:flex; gap:10px; flex-wrap:wrap; align-items:center; margin-top:14px; }
  .btn { border:none; border-radius:12px; padding:9px 20px; font-size:13px; font-weight:700;
    cursor:pointer; transition:transform .14s,filter .14s,box-shadow .14s;
    width:auto; white-space:nowrap; }
  .btn:disabled { opacity:.5; cursor:not-allowed; }
  .btn:hover:not(:disabled) { transform:translateY(-1px); filter:brightness(1.08); }
  .btn:active:not(:disabled) { transform:translateY(1px) scale(.97); filter:brightness(.92); }
  .btn-primary { background:linear-gradient(135deg,var(--accent),var(--accent-strong)); color:var(--on-accent);
    box-shadow:0 8px 20px color-mix(in srgb,var(--accent) 28%,transparent); }
  .btn-green { background:linear-gradient(135deg,var(--green),color-mix(in srgb,var(--green) 75%,var(--text))); color:var(--on-accent);
    box-shadow:0 8px 20px color-mix(in srgb,var(--green) 22%,transparent); }
  .btn-purple { background:linear-gradient(135deg,var(--purple),color-mix(in srgb,var(--purple) 75%,var(--text))); color:var(--on-accent);
    box-shadow:0 8px 20px color-mix(in srgb,var(--purple) 22%,transparent); }
  .btn-danger { background:linear-gradient(135deg,var(--red),color-mix(in srgb,var(--red) 75%,var(--text))); color:var(--on-accent);
    box-shadow:0 8px 20px color-mix(in srgb,var(--red) 22%,transparent); }
  .ghost { background:var(--panel); border:1px solid var(--line); color:var(--text);
    font-weight:650; border-radius:10px; padding:8px 14px; font-size:12px; cursor:pointer;
    transition:transform .14s,background .14s,border-color .14s,color .14s;
    width:auto; white-space:nowrap; }
  .ghost:hover { background:color-mix(in srgb,var(--accent) 9%,var(--panel)); border-color:var(--accent); color:var(--accent); }
  .ghost:active { transform:scale(.96); }
  button:focus-visible { outline:3px solid color-mix(in srgb,var(--accent) 35%,transparent); outline-offset:3px; }
  .linklike { background:none; border:none; color:var(--accent); font-weight:600; cursor:pointer;
    padding:4px 6px; font-size:12px; border-radius:6px; }
  .linklike:hover { background:color-mix(in srgb,var(--accent) 10%,transparent); }
  .linklike:disabled { opacity:.45; cursor:not-allowed; background:none; }

  /* Desktop CML actions */
  .cml-actions { margin-top:18px; }
  .fetch-header-action { flex:none; align-self:center; }
  .deploy-panel { display:grid; grid-template-columns:minmax(210px,.8fr) minmax(300px,1.35fr) max-content;
    gap:14px; align-items:end; padding:14px; border:1px solid var(--line);
    border-radius:16px; background:var(--gutter); min-width:0; }
  .deploy-panel .field select { width:100% !important; min-height:44px; }
  .deploy-action-stack { display:flex; flex-direction:column; align-items:stretch; gap:9px; }
  .cml-main-action { min-width:176px; min-height:56px; padding:14px 26px; font-size:15px;
    display:inline-flex; align-items:center; justify-content:center; gap:9px; }
  .cml-main-action svg { width:19px; height:19px; flex:none; }
  .restore-action { min-width:176px; min-height:52px; padding:12px 20px; font-size:14px;
    display:inline-flex; align-items:center; justify-content:center; gap:9px; }
  .restore-action svg { width:18px; height:18px; flex:none; }

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
  .editor-highlight { z-index:0; overflow:hidden; pointer-events:none; color:var(--text);
    background:var(--input-bg); }
  .editor-highlight .cml-comment { color:var(--comment); }
  .editor-wrap textarea { z-index:1; min-width:0; min-height:0; resize:none; overflow:auto;
    background:transparent; color:transparent; -webkit-text-fill-color:transparent;
    caret-color:var(--text); }
  .editor-wrap textarea::placeholder { color:var(--muted); -webkit-text-fill-color:var(--muted); }
  .editor-wrap textarea::selection { background:color-mix(in srgb,var(--accent) 28%,transparent); }
  .editor-wrap textarea:focus { border:none; box-shadow:none; }
  .key-field-compact { flex:0 1 170px !important; width:170px; max-width:170px !important; }

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
  .pane-scroll { overflow:auto; max-height:600px; }
  table.pane-table { border-collapse:collapse; width:100%; font-family:"JetBrains Mono","SF Mono",Menlo,Consolas,monospace; font-size:12.5px; }
  .pane-table td { padding:0 8px; vertical-align:top; white-space:pre; }
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
    font-weight:850; line-height:16px; cursor:pointer; }
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
  .chips { display:flex; gap:8px; flex-wrap:wrap; }
  .chip { font-size:12px; font-weight:600; padding:4px 12px; border-radius:999px; border:1px solid var(--line); color:var(--muted); }
  .chip.ok { background:var(--ok-bg); color:var(--ok-text); border-color:var(--green); }
  .chip.add { background:var(--ins-bg); color:var(--ins-line); border-color:var(--ins-line); }
  .chip.extra { background:var(--del-bg); color:var(--del-line); border-color:var(--del-line); }
  .chip.warn { background:var(--err-bg); color:var(--err-text); border-color:var(--red); }
  .data { margin-top:14px; display:none; }
  .data.show { display:block; }
  .data-head { display:flex; align-items:center; justify-content:space-between; gap:12px; flex-wrap:wrap; margin-bottom:10px; }
  .data-filter { font-size:12px; color:var(--muted); display:inline-flex; align-items:center; gap:6px; }
  .data-filter select { width:auto; padding:6px 10px; border-radius:9px; }
  .table-scroll { overflow:auto; max-height:560px; border:1px solid var(--line); border-radius:14px; }
  table.data-table { border-collapse:collapse; width:100%; font-size:12.5px; table-layout:auto; }
  .data-table th,.data-table td { padding:8px 12px; text-align:left; border-bottom:1px solid var(--line); vertical-align:top; word-break:break-word; }
  .data-table th { position:sticky; top:0; background:var(--gutter); color:var(--muted); font-size:11px; text-transform:uppercase; letter-spacing:.04em; z-index:1; white-space:nowrap; }
  .data-table tbody tr:hover { background:var(--gutter); }
  /* narrow columns — short content, no wrap needed */
  .data-table td.col-sel,.data-table th.col-sel { width:32px; text-align:center; white-space:nowrap; }
  .data-table td.col-reftype,.data-table th.col-reftype { width:110px; white-space:nowrap; }
  .data-table td.col-tagtype,.data-table th.col-tagtype { width:80px; white-space:nowrap; }
  /* wide columns — allow wrap so full value is always visible */
  .data-table td.col-status,.data-table th.col-status { min-width:160px; }
  .data-table td.col-tag,.data-table th.col-tag { min-width:120px; }
  .data-table td.col-ref,.data-table th.col-ref { min-width:180px; }
  .data-table td.col-key,.data-table th.col-key { min-width:140px; font-family:"JetBrains Mono","SF Mono",Menlo,Consolas,monospace; font-size:11px; color:var(--muted); word-break:break-all; }
  .data-table .gkey { font-family:"JetBrains Mono","SF Mono",Menlo,Consolas,monospace; font-size:11px; color:var(--muted); word-break:break-all; }
  .data-table td.col-sel input[type=checkbox] { width:auto; cursor:pointer; accent-color:var(--accent); }
  .badge { display:inline-block; font-size:11px; font-weight:700; padding:2px 8px; border-radius:6px; }
  .b-match { background:var(--ok-bg); color:var(--ok-text); }
  .b-add { background:var(--ins-bg); color:var(--ins-line); }
  .b-extra { background:var(--del-bg); color:var(--del-line); }
  .b-blocked,.b-unmappable { background:var(--err-bg); color:var(--err-text); }
  .b-type { background:var(--info-bg); color:var(--info-text); }
  .b-dup { background:color-mix(in srgb,var(--amber) 18%,var(--panel)); color:var(--amber); border:1px solid var(--amber); margin-left:6px; }
  .block-note { display:block; margin-top:4px; font-size:11px; color:var(--muted); font-style:italic; white-space:normal; }
  .deploy-bar { display:none; margin-top:14px; padding:13px 16px; border-radius:14px;
    background:var(--info-bg); border:1px solid var(--accent); align-items:center;
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
  .guide-badges { display:flex; gap:8px; flex-wrap:wrap; }
  .guide-badge { display:inline-flex; align-items:center; padding:5px 10px; border-radius:999px;
    font-size:11px; font-weight:850; white-space:nowrap; border:1px solid currentColor; }
  .guide-badge.read { color:var(--ok-text); background:var(--ok-bg); }
  .guide-badge.write { color:var(--err-text); background:var(--err-bg); }
  .guide-steps { display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:12px; }
  .guide-step { display:grid; grid-template-columns:38px minmax(0,1fr); gap:12px; padding:15px;
    border:1px solid var(--line); border-radius:14px; background:var(--input-bg); }
  .guide-number { width:36px; height:36px; display:grid; place-items:center; border-radius:11px;
    color:var(--on-accent); font-weight:900; background:linear-gradient(135deg,var(--accent),var(--purple)); }
  .guide-step h3 { margin:1px 0 5px; font-size:14px; }
  .guide-step p { margin:0; color:var(--muted); font-size:12.5px; line-height:1.55; }
  .guide-boundaries { margin-top:16px; padding:15px 17px; border:2px solid var(--amber);
    border-radius:14px; background:color-mix(in srgb,var(--amber) 10%,var(--panel)); }
  .guide-boundaries h3 { margin:0 0 7px; font-size:14px; }
  .guide-boundaries ul { margin:0; padding-left:20px; color:var(--text); font-size:12.5px; line-height:1.65; }

  /* ── Responsive ───────────────────────────────────────────────── */
  @media (max-width:1050px) {
    .app-shell { display:flex; flex-direction:column; height:100vh; }
    .sidebar { position:relative; height:auto; min-height:auto; flex:0 0 auto;
      padding:9px 12px; flex-direction:row;
      align-items:center; gap:12px; border-right:0; border-bottom:1px solid var(--line); }
    .app-main { height:auto; min-height:0; flex:1 1 auto; overflow-y:auto; }
    .brand { padding:0; min-width:max-content; }
    .brand-mark { width:30px; height:30px; }
    .brand small,.side-label { display:none; }
    .side-menu { display:flex; flex:1; gap:4px; overflow-x:auto; scrollbar-width:none; }
    .side-menu::-webkit-scrollbar { display:none; }
    .side-nav { width:auto; min-width:max-content; padding:7px 10px; }
    .side-nav:hover { transform:none; }
    .side-nav.active { box-shadow:inset 0 -2px 0 var(--accent); }
    .sidebar-footer { display:flex; flex:0 0 auto; align-items:center; gap:4px;
      margin:0 0 0 auto; padding:0; border:0; }
    .sidebar-footer .about-link { width:auto; min-width:max-content; padding:7px 9px; }
    .sidebar-footer .credit { display:none; }
    .donate-wrap { width:auto; }
    .donate-options { position:absolute; z-index:40; top:calc(100% + 6px); right:0;
      width:190px; margin:0; padding:7px; border:1px solid var(--line); border-radius:11px;
      background:var(--panel); }
    .topbar { min-height:80px; }
    .conn-strip { grid-template-columns:1fr 1fr; }
    .guide-steps { grid-template-columns:1fr; }
  }
  @media (max-width:700px) {
    .topbar { flex-direction:column; align-items:flex-start; gap:8px; }
    .top-actions { width:100%; justify-content:space-between; }
    .card-head { flex-wrap:wrap; }
    .fetch-header-action { width:100%; }
    .conn-strip { grid-template-columns:1fr; }
    .diff-panes { grid-template-columns:1fr; }
    .merge-rail { display:none; }
    .tabs { width:100%; }
    .tab { flex:1; }
    .deploy-group { flex-wrap:wrap; }
    .guide-hero { flex-direction:column; }
  }
</style>
</head>
<body>
<div class="app-shell">

  <!-- ═══════════ SIDEBAR ═══════════ -->
  <aside class="sidebar" aria-label="Primary navigation">
    <a class="brand" href="#" onclick="return false;">
      <span class="brand-mark" aria-hidden="true">
        <svg viewBox="0 0 24 24"><path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-1 14H9V8h2v8zm4 0h-2V8h2v8z"/></svg>
      </span>
      <span><strong>Salesforce</strong><small>CML Tool</small></span>
    </a>
    <div class="side-label">Tools</div>
    <nav class="side-menu" id="sideNav">
      <button class="side-nav active" data-view="fetch">
        <span class="nav-icon"><svg viewBox="0 0 24 24"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4M7 10l5 5 5-5M12 15V3"/></svg></span>
        <span>Fetch &amp; Deploy</span>
      </button>
      <button class="side-nav" data-view="compare">
        <span class="nav-icon"><svg viewBox="0 0 24 24"><path d="M8 3H5a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h3M16 3h3a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2h-3M10 8l-3 4 3 4M14 8l3 4-3 4"/></svg></span>
        <span>Compare</span>
      </button>
      <button class="side-nav" data-view="lint">
        <span class="nav-icon"><svg viewBox="0 0 24 24"><path d="M9 11l3 3L22 4M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11"/></svg></span>
        <span>Best Practices</span>
      </button>
      <button class="side-nav" data-view="data">
        <span class="nav-icon"><svg viewBox="0 0 24 24"><ellipse cx="12" cy="5" rx="9" ry="3"/><path d="M21 12c0 1.66-4 3-9 3s-9-1.34-9-3M3 5v14c0 1.66 4 3 9 3s9-1.34 9-3V5"/></svg></span>
        <span>Constraint Data Deploy</span>
      </button>
      <button class="side-nav" data-view="guide">
        <span class="nav-icon"><svg viewBox="0 0 24 24"><path d="M8 4h8M8 20h8M12 4v5M12 15v5M5 9h14v6H5z"/></svg></span>
        <span>Guide Me on Tool</span>
      </button>
    </nav>
    <div class="sidebar-footer">
      <div class="donate-wrap">
        <button type="button" class="about-link donate-link" id="donateBtn"
          aria-expanded="false" aria-controls="donateOptions">
          <span class="nav-icon"><svg viewBox="0 0 24 24"><path d="M12 21s-7-4.35-9.33-8.28C.8 9.56 2.14 5.5 5.8 4.55 8 3.98 10.12 5 12 7c1.88-2 4-3.02 6.2-2.45 3.66.95 5 5.01 3.13 8.17C19 16.65 12 21 12 21z"/></svg></span>
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
      <a class="about-link" href="https://www.linkedin.com/in/mrpancholi/" target="_blank" rel="noopener noreferrer">
        <span class="nav-icon"><svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="9"/><path d="M12 11v6M12 7h.01"/></svg></span>
        <span>About</span>
      </a>
      <p class="credit">Made with 💙 by <strong>Mritunjaya Pancholi</strong></p>
    </div>
  </aside>

  <!-- ═══════════ MAIN ═══════════ -->
  <main class="app-main">
    <header class="topbar">
      <div>
        <div class="eyebrow">Developer tools</div>
        <h1 id="pageTitle">Fetch &amp; Deploy</h1>
        <p class="sub" id="pageSubtitle">Pick a source org — CMLs load automatically. Fetch, edit, and deploy to any org.</p>
      </div>
      <div class="top-actions">
        <span class="local-badge"><span class="live-dot"></span>Runs locally</span>
        <span id="appver" style="font-size:11px;color:var(--muted);font-family:'JetBrains Mono',ui-monospace,monospace;opacity:.8;white-space:nowrap;" title="Running build"></span>
        <button class="ghost" id="themeBtn" title="Toggle day/night">Night mode</button>
      </div>
    </header>

    <div class="wrap">
      <!-- connection error banner -->
      <div class="conn" id="conn"></div>

      <!-- ── Tabs (synced with sidebar) ── -->
      <div class="tabs" id="tabRow" role="tablist">
        <button class="tab active" data-view="fetch">Fetch &amp; Deploy</button>
        <button class="tab" data-view="compare">Compare</button>
        <button class="tab" data-view="lint">Best Practices</button>
        <button class="tab" data-view="data">Constraint Data Deploy</button>
        <button class="tab" data-view="guide">Guide Me on Tool</button>
      </div>

      <!-- ═══ CONNECTION STRIP (shared across all views, always visible) ═══ -->
      <div class="card">
        <div class="conn-strip">
          <div class="field">
            <label for="org">Source org</label>
            <select id="org"><option>Loading orgs…</option></select>
          </div>
          <div class="field">
            <label for="targetOrg">Target org (compare-with)</label>
            <select id="targetOrg"><option>Loading orgs…</option></select>
          </div>
          <div class="field model-field">
            <label for="model">Source CML exact version <span id="cmlCount" class="meta"></span></label>
            <div class="combo" id="combo">
              <input id="cmlFilter" placeholder="Type to filter CMLs…" autocomplete="off" spellcheck="false" />
              <select id="model" size="5"><option value="">Choose an org first…</option></select>
            </div>
            <div class="combo-selected" id="comboSelected" hidden>
              <span class="selchip"><span class="name" id="selectedName"></span></span>
              <button type="button" class="ghost" id="changeModelBtn">Change CML</button>
            </div>
          </div>
          <div class="field">
            <label for="targetVersion">Target exact version (compare-with)</label>
            <select id="targetVersion"><option value="">None — select target org and source version</option></select>
            <span class="meta">Target-org runtime status can differ from the source.</span>
          </div>
          <div class="field reload-field">
            <button class="ghost" id="reloadBtn">Reload list</button>
          </div>
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
                <select id="deployOrg"><option>Loading orgs…</option></select>
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
                <button class="btn btn-green" id="reviewMergeBtn">Review &amp; Deploy merged target</button>
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
                  <button type="button" class="pane-copy" id="copyTargetCmlBtn" title="Copy the complete target CML or current target draft">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="9" y="9" width="11" height="11" rx="2"/><path d="M15 9V6a2 2 0 0 0-2-2H6a2 2 0 0 0-2 2v7a2 2 0 0 0 2 2h3"/></svg>
                    <span>Copy</span>
                  </button>
                </div>
                <div class="pane-scroll" id="tgtScroll"><table class="pane-table" id="tgtTable"></table></div>
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
                <h2>Best Practices</h2>
                <p>Client-side CML linter — checks rules, scores quality, and provides paste-ready fixes.</p>
              </div>
            </div>
            <button class="btn btn-green" id="lintPanelBtn">
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
        <div class="card">
          <div class="card-head">
            <div class="card-title">
              <span class="step-dot" style="background:linear-gradient(135deg,var(--teal),var(--accent-strong));">4</span>
              <div>
                <h2>Constraint Data Deploy</h2>
                <p>View, compare, and deploy ExpressionSetConstraintObj rows (Product associations).</p>
              </div>
            </div>
          </div>

          <p class="sub" style="margin:0 0 14px;">Deploying CML code alone doesn't recreate Product associations. These rows are matched across orgs by a <strong>foreign key</strong> — a field whose value is stable across orgs — instead of by record Id.</p>
          <p class="meta" style="margin:0 0 14px;"><strong>Safe deployment boundary:</strong> catalog records are read-only. The tool reports missing products, classifications, attributes, component groups, and relationships, but it only writes CML content and ExpressionSetConstraintObj associations.</p>

          <div class="conn-strip" style="gap:14px;align-items:end;margin-bottom:16px;">
            <div class="field key-field-compact">
              <label for="keyField">Match records by (foreign key field)</label>
              <input id="keyField" list="keyFieldOpts" value="Global_Key__c" spellcheck="false" autocomplete="off"
                     placeholder="Global_Key__c" title="API name of a field that identifies the same record across orgs" />
              <datalist id="keyFieldOpts">
                <option value="Global_Key__c"></option>
                <option value="Name"></option>
                <option value="ProductCode"></option>
                <option value="ExternalId"></option>
                <option value="External_Id__c"></option>
                <option value="StockKeepingUnit"></option>
              </datalist>
              <p class="meta" style="margin:5px 0 0;"><code>Name</code> may be selected only when it is present and uniquely portable in both orgs; prefer a stable custom/external Id.</p>
            </div>
            <div class="btn-row" style="margin-top:0;gap:8px;">
              <button class="btn btn-primary" id="loadDataBtn">View data</button>
              <button class="btn btn-purple" id="compareDataBtn">Compare data</button>
              <button class="btn btn-danger" id="stopCompareDataBtn" hidden>Stop Comparison</button>
            </div>
          </div>

          <div class="deploy-bar show" id="deployBar">
            <div class="sel-summary" id="selSummary">Compare source and target data to select rows for deployment.</div>
            <div class="sel-actions">
              <button class="linklike" id="selAllAdds" disabled>Select all adds</button>
              <button class="linklike" id="selNoAdds" disabled>Clear adds</button>
              <button class="linklike" id="selAllDels" disabled>Select all deletes</button>
              <button class="linklike" id="selNoDels" disabled>Clear deletes</button>
              <button class="btn btn-green" id="deployDataBtn" disabled>Deploy selected to target</button>
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
          <div class="guide-hero"><div><div class="eyebrow">Safe operating workflow</div><h2>Guide Me on Tool</h2>
            <p class="sub">Follow these steps in order to review exact versions and keep every Salesforce write deliberate.</p></div>
            <div class="guide-badges"><span class="guide-badge read">Read-only</span><span class="guide-badge write">Writes Salesforce</span></div>
          </div>
          <div class="guide-steps">
            <article class="guide-step" data-guide-step="1">
              <span class="guide-number">1</span><div><span class="guide-badge read">Read-only</span>
              <h3>Choose the source</h3><p>Select the source org and the exact source CML version. Do not assume the newest version is the intended one.</p></div>
            </article>
            <article class="guide-step" data-guide-step="2">
              <span class="guide-number">2</span><div><span class="guide-badge read">Read-only</span>
              <h3>Fetch CML</h3><p>Fetch the selected version into the editor. Fetching reads Salesforce and does not change the org.</p></div>
            </article>
            <article class="guide-step" data-guide-step="3">
              <span class="guide-number">3</span><div><span class="guide-badge read">Read-only</span>
              <h3>Compare exact versions</h3><p>Compare source and target exact versions. Optionally enable semantic overlays and apply selected changes to a local merge draft.</p></div>
            </article>
            <article class="guide-step" data-guide-step="4">
              <span class="guide-number">4</span><div><span class="guide-badge read">Read-only</span>
              <h3>Check best practices</h3><p>Run the client-side checks and review every warning before considering a deployment.</p></div>
            </article>
            <article class="guide-step" data-guide-step="5">
              <span class="guide-number">5</span><div><span class="guide-badge read">Read-only</span>
              <h3>Choose the deployment target</h3><p>Select the deployment org and exact target version, then review the target status. Target status may differ by org.</p></div>
            </article>
            <article class="guide-step" data-guide-step="6">
              <span class="guide-number">6</span><div><span class="guide-badge write">Writes Salesforce</span>
              <h3>Deploy after confirmation</h3><p>Back up and confirm the exact destination before deploying CML. This action writes Salesforce.</p></div>
            </article>
            <article class="guide-step" data-guide-step="7">
              <span class="guide-number">7</span><div><span class="guide-badge write">Writes Salesforce</span>
              <h3>Deploy constraint data safely</h3><p>Use Constraint Data Deploy only after dependency preflight. Catalog prerequisites are read-only here and must be fixed externally.</p></div>
            </article>
            <article class="guide-step" data-guide-step="8">
              <span class="guide-number">8</span><div><span class="guide-badge write">Writes Salesforce</span>
              <h3>Restore and recover</h3><p>Use the saved CML backup or association archive for recovery. A restore writes Salesforce, so verify the exact target again.</p></div>
            </article>
          </div>
          <aside class="guide-boundaries"><h3>What this tool does not prove</h3><ul>
            <li>Target status may differ by org; always review the selected target version in its own org.</li>
            <li>The tool does not compile, activate, or prove runtime behavior of CML.</li>
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
    document.querySelectorAll(".side-nav").forEach(b => b.classList.toggle("active", b.dataset.view === view));
    document.querySelectorAll(".tab").forEach(b => b.classList.toggle("active", b.dataset.view === view));
    const m = PAGE_META[view] || {};
    if ($("pageTitle")) $("pageTitle").innerHTML = m.title || view;
    if ($("pageSubtitle")) $("pageSubtitle").textContent = (m.sub || "").replace(/&amp;/g,"&");
  }
  document.querySelectorAll(".side-nav,.tab").forEach(b => {
    b.addEventListener("click", () => switchView(b.dataset.view));
  });

  const orgSel = $("org"), targetSel = $("targetOrg"), targetVersionSel = $("targetVersion"), model = $("model"), content = $("content"), status = $("status");
  const contentLineNumbers = $("contentLineNumbers"), contentHighlight = $("contentHighlight");
  const fetchBtn = $("fetchBtn"), deployBtn = $("deployBtn"), rollbackBtn = $("rollbackBtn"), compareBtn = $("compareBtn"), copyBtn = $("copyBtn");
  const lineCommentBtn = $("lineCommentBtn"), blockCommentBtn = $("blockCommentBtn");
  const cmlFilter = $("cmlFilter"), reloadBtn = $("reloadBtn"), cmlCount = $("cmlCount");
  const combo = $("combo"), comboSelected = $("comboSelected"), selectedName = $("selectedName"), changeModelBtn = $("changeModelBtn");
  const deployOrgSel = $("deployOrg"), deployVersionSel = $("deployVersion");
  const themeBtn = $("themeBtn"), conn = $("conn");
  const diffBox = $("diff"), diffSummary = $("diffSummary"), onlyDiffs = $("onlyDiffs");
  const diffPanes = $("diffPanes"), srcTable = $("srcTable"), tgtTable = $("tgtTable"), mergeTable = $("mergeTable");
  const srcTitle = $("srcTitle"), tgtTitle = $("tgtTitle"), srcScroll = $("srcScroll"), tgtScroll = $("tgtScroll"), mergeScroll = $("mergeScroll");
  const lintBtn = $("lintBtn"), lintBox = $("lint");
  const lintPanelBtn = $("lintPanelBtn"), lintPanel = $("lintPanel"), lintStatus = $("lintStatus");
  const semanticChk = $("semanticDiff"), semanticInlineSummary = $("semanticInlineSummary");
  const lineLegend = $("lineLegend"), onlyDiffsWrap = $("onlyDiffsWrap");
  const mergeWorkflow = $("mergeWorkflow"), mergeWorkflowCopy = $("mergeWorkflowCopy");
  const resetMergeBtn = $("resetMergeBtn"), reviewMergeBtn = $("reviewMergeBtn");
  const copyTargetCmlBtn = $("copyTargetCmlBtn");
  let lastCompare = null;
  let activeMergeHunks = [];
  const loadDataBtn = $("loadDataBtn"), compareDataBtn = $("compareDataBtn"), stopCompareDataBtn = $("stopCompareDataBtn"), keyField = $("keyField");
  const keyName = () => (keyField.value || "Global_Key__c").trim();
  const dataBox = $("data"), dataChips = $("dataChips"), dataTable = $("dataTable"), dataFilter = $("dataFilter");
  const deployBar = $("deployBar"), selSummary = $("selSummary"), deployDataBtn = $("deployDataBtn");
  const selAllAdds = $("selAllAdds"), selNoAdds = $("selNoAdds"), selAllDels = $("selAllDels"), selNoDels = $("selNoDels");
  const copyExcelBtn = $("copyExcelBtn");
  const results = $("results");
  const donateBtn = $("donateBtn"), donateOptions = $("donateOptions");
  const donateUpiBtn = $("donateUpiBtn"), donateDialog = $("donateDialog");
  const donateCloseBtn = $("donateCloseBtn"), copyUpiBtn = $("copyUpiBtn");
  let allModels = [];
  let reconnecting = false;
  let dataRows = [];        // current rows shown in the data table
  let dataMode = "single";  // "single" (one org) or "compare"
  let currentKeyField = "Global_Key__c";  // foreign key the shown data was matched on
  let dataCompareController = null;
  let dataCompareOperationId = null;
  const selectedSourceVersion = () => allModels.find(m => m.versionId === model.value) || null;
  const selectedModelName = () => (selectedSourceVersion() || {}).name || "";
  const versionStatusLabel = (m) => {
    const basis = m && m.statusBasis === "runtime" ? "Runtime" : "Definition";
    return `${basis}: ${(m && m.status) || "Unknown"}`;
  };
  const selectedVersionLabel = (m) => m
    ? `${m.name} · V${m.version} · Source ${versionStatusLabel(m)} · ${m.versionId}`
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
    themeBtn.textContent = t === "light" ? "Night mode" : "Day mode";
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
    loadDataBtn.textContent = "View data";
    compareDataBtn.textContent = "Compare data";
    deployDataBtn.textContent = "Deploy selected to target";
    actionBtns.forEach(b => b.disabled = false);
    updateDeployBar();
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
          + "Then click \u201cReload list\u201d. Open http://127.0.0.1:" + location.port + "/api/debug to see details (sf path, OS user, saved logins).");
        return;
      }
      const opts = orgs.map(o => `<option value="${o.alias}">${o.alias}${o.username ? "  —  " + o.username : ""}</option>`).join("");
      orgSel.innerHTML = '<option value="">None — select a source org</option>' + opts;
      targetSel.innerHTML = '<option value="">None — select a target org</option>' + opts;
      deployOrgSel.innerHTML = '<option value="">None — select a deployment target</option>' + opts;
      orgSel.value = "";
      targetSel.value = "";
      deployOrgSel.value = "";
      targetVersionSel.innerHTML = '<option value="">None — select target org and source version</option>';
      deployVersionSel.innerHTML = '<option value="">None — select deployment target and source version</option>';
      loadModels();
    } catch (e) {
      if (e && e.conn) { handleDisconnect(); return; }
      orgSel.innerHTML = '<option value="">(could not load orgs)</option>';
      setStatus("err", "Could not load orgs: " + e);
    }
  }

  // Collapse the picklist down to just the chosen CML once one is picked, and
  // let the user re-open the full list with "Change CML".
  function collapseModelView() {
    if (!model.value) return;
    selectedName.textContent = selectedVersionLabel(selectedSourceVersion());
    combo.hidden = true;
    comboSelected.hidden = false;
  }
  function expandModelView() {
    comboSelected.hidden = true;
    combo.hidden = false;
    try { cmlFilter.focus(); } catch (e) {}
  }
  model.addEventListener("change", () => {
    if (model.value) collapseModelView();
    loadTargetVersions(targetSel, targetVersionSel, "compare");
    loadTargetVersions(deployOrgSel, deployVersionSel, "deployment");
  });
  model.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && model.value) { e.preventDefault(); collapseModelView(); }
  });
  changeModelBtn.onclick = expandModelView;

  function renderModels() {
    expandModelView();
    targetVersionSel.innerHTML = '<option value="">None — select target org and source version</option>';
    deployVersionSel.innerHTML = '<option value="">None — select deployment target and source version</option>';
    const f = cmlFilter.value.trim().toLowerCase();
    const list = allModels.filter(m =>
      !f || m.name.toLowerCase().includes(f)
      || (m.label || "").toLowerCase().includes(f)
      || String(m.version || "").includes(f)
      || (m.status || "").toLowerCase().includes(f)
      || (m.versionId || "").toLowerCase().includes(f));
    if (!list.length) {
      model.innerHTML = `<option value="">${allModels.length ? "No CMLs match your filter" : "No CMLs found in this org"}</option>`;
      model.size = 2;
    } else {
      const optionHtml = m => {
        const tag = `  [V${m.version} · ${versionStatusLabel(m)}]`;
        return `<option value="${m.versionId}">${m.name}${tag} · ${m.versionId}</option>`;
      };
      const active = list.filter(m =>
        String(m.status || "").trim().toLowerCase() === "active");
      const inactive = list.filter(m =>
        String(m.status || "").trim().toLowerCase() !== "active");
      model.innerHTML = '<option value="">None — select an exact version</option>'
        + (active.length
          ? `<optgroup label="Active CML versions">${active.map(optionHtml).join("")}</optgroup>`
          : "")
        + (inactive.length
          ? `<optgroup label="Inactive / other CML versions">${inactive.map(optionHtml).join("")}</optgroup>`
          : "");
      model.size = Math.min(10, Math.max(3, list.length + 1));
      model.value = "";
    }
    cmlCount.textContent = allModels.length ? `(${list.length} of ${allModels.length})` : "";
    fitPicklist(model);
  }

  async function loadModels() {
    const org = orgSel.value;
    if (!org) {
      expandModelView();
      allModels = [];
      cmlCount.textContent = "";
      cmlFilter.value = "";
      model.innerHTML = '<option value="">Choose a source org first…</option>';
      targetVersionSel.innerHTML = '<option value="">None — select target org and source version</option>';
      deployVersionSel.innerHTML = '<option value="">None — select deployment target and source version</option>';
      return;
    }
    expandModelView();
    allModels = [];
    cmlCount.textContent = "";
    model.innerHTML = '<option value="">Loading CMLs…</option>';
    try {
      const data = await apiGet("/api/models?org=" + encodeURIComponent(org));
      if (data.error) {
        model.innerHTML = '<option value="">(could not load CMLs)</option>';
        setStatus("err", "Could not load CMLs from " + org + ":\n" + data.error);
        return;
      }
      allModels = data.models || [];
      renderModels();
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
      if (e && e.conn) { handleDisconnect(); return; }
      model.innerHTML = '<option value="">(could not load CMLs)</option>';
      setStatus("err", "Could not load CMLs: " + e);
    }
  }

  async function loadTargetVersions(orgControl, versionControl, purpose) {
    versionControl.innerHTML = `<option value="">None — select exact ${purpose} version</option>`;
    const org = orgControl.value;
    const modelName = selectedModelName();
    if (!org || !modelName) return;
    versionControl.innerHTML = '<option value="">Loading exact versions…</option>';
    try {
      const data = await apiGet("/api/models?org=" + encodeURIComponent(org));
      if (data.error) {
        versionControl.innerHTML = '<option value="">(could not load exact versions)</option>';
        setStatus("err", `Could not load ${purpose} versions from ${org}:\n${data.error}`);
        return;
      }
      const versions = (data.models || []).filter(m => m.name === modelName);
      const targetRole = purpose === "compare" ? "Compare target" : "Deployment target";
      versionControl.innerHTML = `<option value="">None — select exact ${purpose} version</option>`
        + versions.map(m => `<option value="${m.versionId}">${m.name} · V${m.version} · ${targetRole} ${versionStatusLabel(m)} · ${m.versionId}</option>`).join("");
      versionControl.value = "";
      if (data.runtimeStatusWarning) {
        setStatus(
          "info",
          `${targetRole} runtime activity could not be loaded. Labels are using `
          + "definition-version status.\n" + data.runtimeStatusWarning);
      }
    } catch (e) {
      if (e && e.conn) handleDisconnect();
      else setStatus("err", `Could not load ${purpose} versions: ${e}`);
    }
  }

  orgSel.onchange = () => {
    targetVersionSel.innerHTML = '<option value="">None — select target org and source version</option>';
    deployVersionSel.innerHTML = '<option value="">None — select deployment target and source version</option>';
    loadModels();
  };
  targetSel.onchange = () => loadTargetVersions(targetSel, targetVersionSel, "compare");
  deployOrgSel.onchange = () => loadTargetVersions(deployOrgSel, deployVersionSel, "deployment");
  reloadBtn.onclick = loadModels;
  cmlFilter.oninput = renderModels;

  fetchBtn.onclick = async () => {
    if (!orgSel.value) { setStatus("err", "Please choose an org first."); return; }
    const source = selectedSourceVersion();
    if (!source) { setStatus("err", "Please select an exact CML version."); model.focus(); return; }
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
    if (!source) { setStatus("err", "Please select an exact source CML version."); model.focus(); return; }
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
    if (!source) { setStatus("err", "Please select an exact source CML version.", cmpStatus); model.focus(); return; }
    if (!targetVersionSel.value) { setStatus("err", "Please select an exact compare target version.", cmpStatus); targetVersionSel.focus(); return; }
    busy(compareBtn, "Comparing…");
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
        const targetMatch = action.targetLead && row.b + 1 === action.targetLead;
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
    mergeWorkflowCopy.textContent = `${count} source change${count === 1 ? "" : "s"} applied to the target working draft. Salesforce has not been changed yet.`;
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

  onlyDiffs.onchange = () => diffPanes.classList.toggle("hide-eq", onlyDiffs.checked);
  mergeTable.onclick = async event => {
    const button = event.target.closest("[data-merge-hunk]");
    if (!button || !lastCompare) return;
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
    try {
      lastCompare.semantic = await postJSON("/api/semantic/compare", {
        sourceContent: lastCompare.src.content || "",
        targetContent: lastCompare.tgt.content || ""
      });
      renderCompare();
    } catch (e) {
      if (e && e.conn) handleDisconnect();
    }
  };
  resetMergeBtn.onclick = () => {
    if (!lastCompare) return;
    lastCompare.tgt.content = lastCompare.originalTargetContent;
    lastCompare.mergeCount = 0;
    lastCompare.semantic = null;
    renderCompare();
    postJSON("/api/semantic/compare", {
      sourceContent: lastCompare.src.content || "",
      targetContent: lastCompare.tgt.content || ""
    }).then(data => {
      if (!lastCompare) return;
      lastCompare.semantic = data;
      renderCompare();
    }).catch(e => { if (e && e.conn) handleDisconnect(); });
    setStatus("info", "Target draft reset to the version fetched from Salesforce. No org data was changed.", cmpStatus);
  };
  reviewMergeBtn.onclick = async () => {
    if (!lastCompare || !lastCompare.mergeCount) return;
    setEditorContent(lastCompare.tgt.content);
    deployOrgSel.value = targetSel.value;
    await loadTargetVersions(deployOrgSel, deployVersionSel, "deployment");
    deployVersionSel.value = targetVersionSel.value;
    fitPicklist(deployOrgSel);
    fitPicklist(deployVersionSel);
    switchView("fetch");
    setStatus("info", `Merged target draft loaded for review.\nDeployment target: ${targetSel.value} · exact version ${targetVersionSel.value}.\nReview the CML, then use Deploy CML. The normal backup, confirmation, and verification safeguards still apply.`);
  };
  copyTargetCmlBtn.onclick = async () => {
    if (!lastCompare) return;
    const value = lastCompare.tgt.content || "";
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
    if (s === "match")      return '<span class="badge b-match">Matched</span>';
    if (s === "add")        return '<span class="badge b-add">Add to target</span>';
    if (s === "ready")      return '<span class="badge b-add">Add to target</span>';
    if (s === "extra")      return '<span class="badge b-extra">Only in target</span>';
    if (s === "cml-difference") return '<span class="badge b-extra">CML definitions differ</span>';
    if (s === "blocked")    return '<span class="badge b-blocked">Blocked — catalog dependency</span>';
    if (s === "ambiguous-key") return '<span class="badge b-blocked">Blocked — ambiguous key</span>';
    if (s === "dependency-unverified") return '<span class="badge b-unmappable">Needs review — dependency key missing</span>';
    if (s === "exact-duplicate") return '<span class="badge b-dup">Skipped — exact duplicate</span>';
    if (s === "unmappable") return '<span class="badge b-unmappable">No ' + esc(currentKeyField) + '</span>';
    if (s === "stale")      return '<span class="badge b-unmappable">Unused association in this org</span>';
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
    const gk = r.mappable ? `<span class="gkey">${esc(r.gkey)}</span>`
                          : '<span class="badge b-unmappable">missing</span>';
    const blockNote = r.blockNote ? `<span class="block-note">${esc(r.blockNote)}</span>` : "";
    let sel = "";
    if (withStatus) {
      if (isAdd(r) || isDel(r)) {
        sel = `<td class="col-sel"><input type="checkbox" data-i="${r._i}" ${r._selected ? "checked" : ""}></td>`;
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
      + (withStatus ? '<th class="col-sel"></th><th class="col-status">Status</th>' : "")
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
    const source = selectedSourceVersion();
    if (!source) { setStatus("err", "Please select an exact source CML version.", dSt()); model.focus(); return; }
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
    const source = selectedSourceVersion();
    if (!source) { setStatus("err", "Please select an exact source CML version.", dSt()); model.focus(); return; }
    if (!targetVersionSel.value) { setStatus("err", "Please select an exact compare target version.", dSt()); targetVersionSel.focus(); return; }
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
      `<span class="chip">Source ${o.src.org}: ${o.src.total}</span>`
      + `<span class="chip">Target ${o.tgt.org}: ${o.tgt.total}</span>`
      + `<span class="chip ok">${s.matched} matched</span>`
      + `<span class="chip add">${s.sourceOnly} only in source</span>`
      + `<span class="chip extra">${s.targetOnly} only in target</span>`
      + (s.cmlDifferences ? `<span class="chip warn">${s.cmlDifferences} CML definition differences (not errors)</span>` : "")
      + (s.ambiguousKeys ? `<span class="chip warn">${s.ambiguousKeys} ambiguous portable keys</span>` : "")
      + (s.dependencyIssues ? `<span class="chip warn">${s.dependencyIssues} catalog dependency findings</span>` : "")
      + (s.dependencyUnverified ? `<span class="chip warn">${s.dependencyUnverified} dependency checks need review</span>` : "")
      + (s.exactDuplicates ? `<span class="chip warn">${s.exactDuplicates} exact duplicate rows</span>` : "")
      + (s.stale ? `<span class="chip warn">${s.stale} stale (excluded from deploy)</span>` : "")
      + (s.blocked ? `<span class="chip warn">${s.blocked} blocked by catalog dependencies</span>` : "")
      + (s.unmappable ? `<span class="chip warn">${s.unmappable} unmappable</span>` : "")
      + ((o.src.duplicateCheckError || o.tgt.duplicateCheckError)
        ? `<span class="chip warn">Duplicate check unavailable for one selected CML</span>` : "")
      + ((sd + td) ? `<span class="chip warn" title="Each org is checked independently inside the exact selected version's resolved parent Expression Set">${sd + td} duplicate flags (selected source ${sd} / selected target ${td})</span>` : "");
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
