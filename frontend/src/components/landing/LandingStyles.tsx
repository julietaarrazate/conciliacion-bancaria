import React from 'react'

/**
 * Estilos de la landing pública. TODO va scopeado a `.landing-root`: la app
 * autenticada no lee nada de acá (ni tokens, ni clases), y nada de acá pisa
 * los tokens globales de `styles/index.css`.
 *
 * Tipografía: un solo sistema, Inter (la misma fuente de la app) con tracking
 * cerrado en los titulares + JetBrains Mono para importes, igual que en el
 * producto. Las dos ya las carga `index.html`: la landing no baja fuentes extra.
 *
 * Color: acento de marca violeta, los mismos valores que la app (`--ml-accent`:
 * claro #5E6AD2 / oscuro #818CF8). El verde (`--ok*`) es solo estado de éxito:
 * "Acreditado", filas conciliadas, Control del banco ✓ y planillas completas.
 *
 * Movimiento: solo `transform` y `opacity` (compositor, 60fps, sin layout
 * shift). Con `prefers-reduced-motion` todo queda en su estado final.
 */
export const LandingStyles: React.FC = () => (
  <style>{`
    .landing-root {
      --bg:          #FFFFFF;
      --bg-2:        #FAFAFA;
      --card:        #FFFFFF;
      --card-2:      #F7F7F8;
      --border:      #E4E4E7;
      --border-soft: #EFEFF1;
      --text:        #0A0A0B;
      --text-2:      #3F3F46;
      --muted:       #5F5F69;
      --muted-2:     #8A8A93;
      --accent:      #5E6AD2;
      --accent-text: #4A55BE;
      --accent-soft: rgba(94,106,210,.08);
      --accent-line: rgba(94,106,210,.30);
      --ok:          #16A34A;
      --ok-text:     #15803D;
      --ok-soft:     rgba(22,163,74,.08);
      --ok-line:     rgba(22,163,74,.28);
      --ok-ink:      #FFFFFF;
      --btn-bg:      #5E6AD2;
      --btn-bg-h:    #4A55BE;
      --btn-ink:     #FFFFFF;
      --amber:       #B45309;
      --amber-soft:  rgba(245,158,11,.12);
      --amber-line:  rgba(245,158,11,.38);
      --nav-bg:      rgba(255,255,255,.82);
      --stage:       linear-gradient(180deg, rgba(94,106,210,.11) 0%, rgba(94,106,210,.03) 45%, rgba(94,106,210,0) 100%);
      --shadow-win:  0 1px 2px rgba(10,10,11,.04), 0 12px 32px -8px rgba(10,10,11,.10), 0 40px 80px -24px rgba(10,10,11,.14);
      --shadow-card: 0 1px 2px rgba(10,10,11,.04), 0 8px 24px -12px rgba(10,10,11,.10);
      --mono: 'JetBrains Mono', ui-monospace, 'SFMono-Regular', Consolas, monospace;
    }
    .dark .landing-root {
      --bg:          #08080B;
      --bg-2:        #0C0C10;
      --card:        #111116;
      --card-2:      #0E0E13;
      --border:      #24242C;
      --border-soft: #1A1A21;
      --text:        #F4F4F5;
      --text-2:      #D4D4D8;
      --muted:       #A1A1AA;
      --muted-2:     #71717A;
      --accent:      #818CF8;
      --accent-text: #A5B4FC;
      --accent-soft: rgba(129,140,248,.10);
      --accent-line: rgba(129,140,248,.32);
      --ok:          #4ADE80;
      --ok-text:     #4ADE80;
      --ok-soft:     rgba(74,222,128,.08);
      --ok-line:     rgba(74,222,128,.28);
      --ok-ink:      #052E16;
      --btn-bg:      #818CF8;
      --btn-bg-h:    #A5B4FC;
      --btn-ink:     #0B0B0F;
      --amber:       #FBBF24;
      --amber-soft:  rgba(251,191,36,.10);
      --amber-line:  rgba(251,191,36,.34);
      --nav-bg:      rgba(8,8,11,.78);
      --stage:       linear-gradient(180deg, rgba(129,140,248,.12) 0%, rgba(129,140,248,.03) 45%, rgba(129,140,248,0) 100%);
      --shadow-win:  0 0 0 1px rgba(255,255,255,.02), 0 24px 64px -16px rgba(0,0,0,.7), 0 0 80px -20px rgba(129,140,248,.14);
      --shadow-card: 0 0 0 1px rgba(255,255,255,.01), 0 12px 32px -16px rgba(0,0,0,.6);
    }

    .landing-root {
      min-height: 100vh;
      background: var(--bg);
      color: var(--text);
      font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
      font-size: 16px;
      line-height: 1.6;
      -webkit-font-smoothing: antialiased;
      text-rendering: optimizeLegibility;
      overflow-x: clip;
    }
    .landing-root *, .landing-root *::before, .landing-root *::after { box-sizing: border-box; }
    .landing-root a { color: inherit; }
    .landing-root :focus-visible { outline: 2px solid var(--accent); outline-offset: 3px; border-radius: 8px; }
    .landing-root .num { font-family: var(--mono); font-variant-numeric: tabular-nums; letter-spacing: -0.01em; }
    .landing-root .sr-only { position:absolute; width:1px; height:1px; padding:0; margin:-1px; overflow:hidden; clip:rect(0,0,0,0); white-space:nowrap; border:0; }

    /* ── Layout ─────────────────────────────────────────────────────────── */
    .l-wrap { width: 100%; max-width: 1160px; margin: 0 auto; padding: 0 16px; }
    @media (min-width: 720px) { .l-wrap { padding: 0 32px; } }
    .l-section { padding: 88px 0; scroll-margin-top: 64px; }
    @media (min-width: 900px) { .l-section { padding: 128px 0; } }
    .l-section.alt { background: var(--bg-2); border-top: 1px solid var(--border-soft); border-bottom: 1px solid var(--border-soft); }

    /* ── Tipografía ─────────────────────────────────────────────────────── */
    .l-eyebrow { display:inline-block; font-size: 13px; font-weight: 600; color: var(--accent-text); letter-spacing: -0.005em; margin-bottom: 16px; }
    .l-h1 { font-size: clamp(44px, 9.6vw, 92px); font-weight: 700; line-height: 0.98; letter-spacing: -0.048em; margin: 0 0 22px; color: var(--text); text-wrap: balance; }
    .l-h2 { font-size: clamp(32px, 5.2vw, 52px); font-weight: 700; line-height: 1.04; letter-spacing: -0.04em; margin: 0 0 16px; color: var(--text); text-wrap: balance; }
    .l-h3 { font-size: 18px; font-weight: 600; line-height: 1.3; letter-spacing: -0.02em; margin: 0 0 8px; color: var(--text); }
    .l-lead { font-size: clamp(17px, 2.1vw, 20px); line-height: 1.55; color: var(--muted); letter-spacing: -0.012em; margin: 0; max-width: 600px; text-wrap: pretty; }
    .l-body { font-size: 15px; line-height: 1.6; color: var(--muted); margin: 0; text-wrap: pretty; }
    .l-head { max-width: 720px; margin-bottom: 56px; }
    .l-head.center { margin-left: auto; margin-right: auto; text-align: center; }
    .l-head.center .l-lead { margin: 0 auto; }

    /* ── Botones ────────────────────────────────────────────────────────── */
    .l-btn { display:inline-flex; align-items:center; justify-content:center; gap:8px; height:48px; padding:0 22px; border-radius:12px; font: inherit; font-size:15px; font-weight:600; letter-spacing:-0.01em; line-height:1; text-decoration:none; white-space:nowrap; cursor:pointer; border:1px solid transparent; transition: background-color .15s ease, border-color .15s ease, color .15s ease, transform .15s ease; }
    .l-btn:active { transform: scale(.98); }
    .l-btn.primary { background: var(--btn-bg); color: var(--btn-ink); box-shadow: 0 1px 0 rgba(255,255,255,.18) inset, 0 6px 16px -6px var(--accent-line); }
    .l-btn.primary:hover { background: var(--btn-bg-h); }
    .l-btn.secondary { background: var(--card); color: var(--text); border-color: var(--border); }
    .l-btn.secondary:hover { border-color: var(--muted-2); }
    .l-btn.sm { height: 36px; padding: 0 14px; font-size: 14px; border-radius: 10px; }
    .l-btn .arrow { transition: transform .2s ease; }
    .l-btn:hover .arrow { transform: translateX(3px); }
    .l-link { color: var(--accent-text); font-weight: 600; text-decoration: none; display: inline-flex; align-items: center; gap: 6px; }
    .landing-root svg { display: inline-block; vertical-align: middle; }
    .l-link:hover { text-decoration: underline; text-underline-offset: 3px; }

    /* ── Nav ────────────────────────────────────────────────────────────── */
    .l-nav { position: fixed; inset: 0 0 auto 0; z-index: 50; height: 64px; background: var(--nav-bg); backdrop-filter: saturate(1.6) blur(16px); -webkit-backdrop-filter: saturate(1.6) blur(16px); border-bottom: 1px solid transparent; transition: border-color .2s ease; }
    .l-nav[data-scrolled="true"] { border-bottom-color: var(--border); }
    .l-nav-in { height: 100%; display: flex; align-items: center; justify-content: space-between; gap: 12px; }
    .l-brand { display:flex; align-items:center; gap:8px; font-size:17px; font-weight:700; letter-spacing:-0.03em; color: var(--text); text-decoration:none; }
    .l-brand svg { color: #5E6AD2; }
    .l-nav-links { display:none; gap: 4px; }
    @media (min-width: 900px) { .l-nav-links { display:flex; } }
    .l-nav-links a { padding: 8px 12px; border-radius: 8px; font-size: 14px; font-weight: 500; color: var(--muted); text-decoration: none; transition: color .15s ease; }
    .l-nav-links a:hover { color: var(--text); }
    .l-nav-actions { display:flex; align-items:center; gap: 8px; }
    .l-icon-btn { width:36px; height:36px; display:inline-flex; align-items:center; justify-content:center; border-radius:10px; background:transparent; border:1px solid var(--border); color: var(--muted); cursor:pointer; transition: color .15s ease, border-color .15s ease; }
    .l-icon-btn:hover { color: var(--text); border-color: var(--muted-2); }
    .l-nav-login { font-size: 14px; font-weight: 500; color: var(--text-2); text-decoration: none; padding: 8px 10px; border-radius: 8px; }
    .l-nav-login:hover { color: var(--text); }
    .l-nav-cta { transition: opacity .25s ease, transform .25s ease; }
    .l-nav-cta[data-show="false"] { opacity: 0; transform: translateY(-4px); pointer-events: none; }
    @media (max-width: 380px) { .l-nav-login { display: none; } }

    /* ── Reveal al hacer scroll ─────────────────────────────────────────── */
    .l-reveal { opacity: 0; transform: translate3d(0, 16px, 0); transition: opacity .7s cubic-bezier(.2,.7,.2,1) var(--d, 0ms), transform .7s cubic-bezier(.2,.7,.2,1) var(--d, 0ms); }
    .l-reveal[data-visible="true"] { opacity: 1; transform: none; }

    /* ── Hero ───────────────────────────────────────────────────────────── */
    .l-hero { position: relative; padding: 120px 0 72px; }
    @media (min-width: 900px) { .l-hero { padding: 168px 0 112px; } }
    .l-hero-copy { max-width: 820px; }
    .l-hero-ctas { display:flex; flex-wrap:wrap; gap: 12px; margin-top: 32px; }
    .l-hero-facts { display:flex; flex-wrap:wrap; gap: 8px 20px; margin: 24px 0 0; padding: 0; list-style: none; font-size: 14px; color: var(--muted); }
    .l-hero-facts li { display:flex; align-items:center; gap: 8px; }
    .l-hero-facts svg { color: var(--accent); flex-shrink: 0; }
    .l-stage { position: relative; margin-top: 56px; border-radius: 24px; padding: 12px; background: var(--stage); border: 1px solid var(--border-soft); }
    @media (min-width: 720px) { .l-stage { margin-top: 72px; padding: 24px; border-radius: 28px; } }

    /* ── Hero demo (ventana del producto) ───────────────────────────────── */
    .hd { position: relative; background: var(--card); border: 1px solid var(--border); border-radius: 16px; box-shadow: var(--shadow-win); overflow: hidden; font-size: 13px; }
    .hd-bar { display:flex; align-items:center; gap: 10px; height: 44px; padding: 0 14px; border-bottom: 1px solid var(--border); background: var(--card-2); }
    .hd-bar-title { font-size: 13px; font-weight: 600; color: var(--text); letter-spacing: -0.01em; }
    .hd-bar-crumb { display: none; font-size: 12px; color: var(--muted); }
    @media (min-width: 560px) { .hd-bar-crumb { display: inline; } }
    .hd-bar svg { color: #5E6AD2; flex-shrink: 0; }
    .hd-file { margin-left: auto; display:flex; align-items:center; gap: 8px; height: 28px; padding: 0 10px; border-radius: 8px; border: 1px solid var(--border); background: var(--card); font-size: 12px; color: var(--text-2); max-width: 52%; }
    .hd-file-name { overflow:hidden; text-overflow: ellipsis; white-space: nowrap; }
    .hd-file-bar { position: relative; width: 44px; height: 4px; border-radius: 4px; background: var(--border); overflow: hidden; flex-shrink: 0; }
    .hd-file-bar i { position:absolute; inset:0; background: var(--accent); transform-origin: left; transform: scaleX(0); transition: transform .9s cubic-bezier(.4,0,.2,1); }
    .hd[data-p-file="true"] .hd-file-bar i { transform: scaleX(1); }
    .hd-file { opacity: 0; transform: translateY(-4px); transition: opacity .35s ease, transform .35s ease; }
    .hd[data-p-file="true"] .hd-file { opacity: 1; transform: none; }

    .hd-body { display: grid; grid-template-columns: 1fr; }
    @media (min-width: 900px) { .hd-body { grid-template-columns: minmax(0, 1.55fr) minmax(0, 1fr); } }
    .hd-main { padding: 14px 14px 16px; min-width: 0; }
    @media (min-width: 900px) { .hd-main { padding: 18px 18px 20px; border-right: 1px solid var(--border); } }
    .hd-side { padding: 0 14px 14px; display: grid; gap: 12px; align-content: start; min-width: 0; }
    @media (min-width: 900px) { .hd-side { padding: 18px; } }
    .hd-label { display:flex; align-items:center; justify-content:space-between; gap: 8px; font-size: 11px; font-weight: 600; letter-spacing: .06em; text-transform: uppercase; color: var(--muted); margin-bottom: 10px; }
    .hd-label b { font-weight: 600; text-transform: none; letter-spacing: 0; color: var(--muted-2); }

    .hd-rows { display: grid; gap: 6px; }
    .hd-row { position: relative; display: grid; grid-template-columns: minmax(0,1fr) auto; align-items: center; gap: 4px 12px; padding: 9px 10px; border-radius: 10px; border: 1px solid var(--border-soft); background: var(--card-2);
      opacity: 0; transform: translate3d(0, 6px, 0); transition: opacity .45s ease calc(var(--i) * 70ms), transform .45s cubic-bezier(.2,.7,.2,1) calc(var(--i) * 70ms); }
    @media (min-width: 560px) { .hd-row { grid-template-columns: 44px minmax(0,1fr) auto auto; } }
    .hd[data-p-rows="true"] .hd-row { opacity: 1; transform: none; }
    .hd-row::before { content:''; position:absolute; inset:-1px; border-radius: 10px; border: 1px solid var(--ok-line); background: var(--ok-soft); opacity: 0; transition: opacity .4s ease; pointer-events: none; }
    .hd-row[data-st="ok"]::before { opacity: 1; }
    .hd-row::after { content:''; position:absolute; inset:-1px; border-radius: 10px; border: 1px solid var(--amber-line); background: var(--amber-soft); opacity: 0; transition: opacity .4s ease; pointer-events: none; }
    .hd-row[data-st="amb"]::after { opacity: 1; }
    .hd-row > * { position: relative; z-index: 1; }
    .hd-date { display: none; font-size: 12px; color: var(--muted); }
    @media (min-width: 560px) { .hd-date { display: block; } }
    .hd-concept { min-width: 0; grid-row: span 2; }
    @media (min-width: 560px) { .hd-concept { grid-row: auto; } }
    .hd-concept b { display:block; font-size: 12.5px; font-weight: 600; color: var(--text); overflow:hidden; text-overflow:ellipsis; white-space:nowrap; letter-spacing: -0.005em; }
    .hd-concept small { display:block; font-size: 11px; color: var(--muted); overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
    .hd-amount { font-size: 12.5px; color: var(--text); text-align: right; grid-column: 2; grid-row: 1; }
    @media (min-width: 560px) { .hd-amount { grid-column: auto; grid-row: auto; } }
    .hd-chip { display: grid; justify-items: end; grid-column: 2; }
    @media (min-width: 560px) { .hd-chip { grid-column: auto; min-width: 150px; } }
    .hd-chip > span { grid-area: 1 / 1; display:inline-flex; align-items:center; gap: 5px; height: 22px; padding: 0 8px; border-radius: 6px; font-size: 11px; font-weight: 600; white-space: nowrap; transition: opacity .35s ease, transform .35s ease; }
    .hd-chip .c-pend { color: var(--muted); background: var(--border-soft); }
    .hd-chip .c-ok   { color: var(--ok-text); background: var(--ok-soft); box-shadow: inset 0 0 0 1px var(--ok-line); opacity: 0; transform: scale(.92); }
    .hd-chip .c-amb  { color: var(--amber); background: var(--amber-soft); box-shadow: inset 0 0 0 1px var(--amber-line); opacity: 0; transform: scale(.92); }
    .hd-row[data-st="ok"]  .c-pend, .hd-row[data-st="amb"] .c-pend { opacity: 0; }
    .hd-row[data-st="ok"]  .c-ok  { opacity: 1; transform: none; }
    .hd-row[data-st="amb"] .c-amb { opacity: 1; transform: none; }
    .hd-lg { display: none; }
    @media (min-width: 560px) { .hd-lg { display: inline; } .hd-sm { display: none; } }
    .hd-cursor { position: absolute; right: 18px; bottom: -10px; z-index: 3; color: var(--text); opacity: 0; transform: translate3d(28px, 22px, 0); transition: opacity .3s ease, transform .6s cubic-bezier(.2,.7,.2,1); pointer-events: none; filter: drop-shadow(0 2px 4px rgba(0,0,0,.25)); }
    .hd-row[data-cursor="true"] .hd-cursor { opacity: 1; transform: none; }
    .hd-row[data-cursor="gone"] .hd-cursor { opacity: 0; transform: none; }

    .hd-card { border: 1px solid var(--border); border-radius: 12px; background: var(--card); padding: 12px; }
    .hd-clients { display: grid; gap: 10px; }
    .hd-client { display: grid; grid-template-columns: minmax(0,1fr) auto; gap: 6px 10px; align-items: center; }
    .hd-client-name { font-size: 12.5px; font-weight: 600; color: var(--text); overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
    .hd-client-name small { font-weight: 500; color: var(--muted); margin-left: 6px; font-size: 11px; }
    .hd-client-count { font-size: 11.5px; color: var(--muted); }
    .hd-track { grid-column: 1 / -1; height: 4px; border-radius: 4px; background: var(--border-soft); overflow: hidden; }
    .hd-track i { display:block; height: 100%; background: var(--accent); border-radius: 4px; transform-origin: left; transition: transform .5s cubic-bezier(.4,0,.2,1), background-color .3s ease; }
    .hd-client[data-done="true"] .hd-track i { background: var(--ok); }

    .hd-ctrl-head { display:flex; align-items:center; justify-content:space-between; gap:8px; margin-bottom: 8px; }
    .hd-ctrl-title { font-size: 12.5px; font-weight: 600; color: var(--text); }
    .hd-stack { display: grid; }
    .hd-stack > * { grid-area: 1 / 1; transition: opacity .4s ease, transform .4s ease; }
    .hd-ctrl-status { font-size: 12px; font-weight: 600; line-height: 1.4; }
    .hd-ctrl-status .s-wait { color: var(--muted); }
    .hd-ctrl-status .s-ok { color: var(--ok-text); opacity: 0; transform: translateY(4px); }
    .hd[data-p-ok="true"] .hd-ctrl-status .s-wait { opacity: 0; transform: translateY(-4px); }
    .hd[data-p-ok="true"] .hd-ctrl-status .s-ok { opacity: 1; transform: none; }
    .hd-ctrl-badge { width: 22px; height: 22px; border-radius: 999px; display: grid; place-items: center; background: var(--ok); color: var(--ok-ink); opacity: 0; transform: scale(.6); transition: opacity .35s ease, transform .5s cubic-bezier(.34,1.56,.64,1); }
    .hd[data-p-ok="true"] .hd-ctrl-badge { opacity: 1; transform: none; }
    .hd-ctrl-grid { display:grid; grid-template-columns: 1fr 1fr; gap: 10px; margin-top: 10px; padding-top: 10px; border-top: 1px solid var(--border-soft); }
    .hd-ctrl-grid small { display:block; font-size: 11px; color: var(--muted); }
    .hd-ctrl-grid .num { font-size: 13px; font-weight: 600; color: var(--text); }

    /* Sin animación: todo en su estado final, sin transiciones. */
    @media (prefers-reduced-motion: reduce) {
      .landing-root *, .landing-root *::before, .landing-root *::after { transition-duration: 0s !important; transition-delay: 0s !important; animation: none !important; }
      .l-reveal { opacity: 1; transform: none; }
    }

    /* ── Cómo funciona ──────────────────────────────────────────────────── */
    .l-steps-wrap { position: relative; }
    .l-steps { list-style: none; margin: 0; padding: 0; display: grid; gap: 40px; grid-template-columns: 1fr; counter-reset: paso; }
    @media (min-width: 860px) { .l-steps { grid-template-columns: repeat(3, 1fr); gap: 32px; } }
    .l-steps-line { display: none; }
    @media (min-width: 860px) {
      .l-steps-line { display:block; position:absolute; top: 20px; left: 40px; right: 40px; height: 1px; background: var(--border); overflow: hidden; }
      .l-steps-line i { position:absolute; inset:0; background: var(--accent); transform-origin: left; transform: scaleX(0); transition: transform 1.4s cubic-bezier(.4,0,.2,1) .2s; }
      .l-steps-wrap[data-visible="true"] .l-steps-line i { transform: scaleX(1); }
    }
    .l-step { position: relative; }
    .l-step-n { position: relative; z-index: 1; display:inline-grid; place-items:center; width: 40px; height: 40px; border-radius: 12px; background: var(--card); border: 1px solid var(--border); font-family: var(--mono); font-size: 14px; font-weight: 500; color: var(--accent-text); margin-bottom: 20px; box-shadow: var(--shadow-card); }
    .l-inline-cta { display:flex; flex-wrap: wrap; align-items:center; gap: 12px 20px; margin-top: 56px; padding-top: 32px; border-top: 1px solid var(--border-soft); }
    .l-inline-cta p { margin: 0; color: var(--muted); font-size: 15px; }

    /* ── Funciones (bento) ──────────────────────────────────────────────── */
    .l-bento { display:grid; gap: 16px; grid-template-columns: 1fr; }
    @media (min-width: 760px) { .l-bento { grid-template-columns: repeat(2, 1fr); } }
    @media (min-width: 1040px) { .l-bento { grid-template-columns: repeat(3, 1fr); } .l-bento .wide { grid-column: span 2; } }
    .l-tile { height: 100%; display:flex; flex-direction:column; gap: 20px; padding: 24px; border-radius: 20px; border: 1px solid var(--border); background: var(--card); box-shadow: var(--shadow-card); }
    .l-tile .l-viz { flex: 1; min-height: 132px; display:flex; align-items:center; justify-content:center; border-radius: 14px; background: var(--bg-2); border: 1px solid var(--border-soft); padding: 16px; overflow: hidden; }
    .l-tile-copy { margin-top: auto; }

    /* mini visuales dentro de las tarjetas */
    .v-ctrl { width: 100%; max-width: 440px; }
    .v-notif { width: 100%; max-width: 300px; display:grid; gap: 8px; }
    .v-notif > div { display:flex; gap: 10px; align-items:flex-start; padding: 10px 12px; border-radius: 12px; background: var(--card); border: 1px solid var(--border); box-shadow: var(--shadow-card); font-size: 12px; line-height: 1.4; color: var(--text-2); }
    .v-notif b { display:block; color: var(--text); font-size: 12px; }
    .v-notif .dot { width: 8px; height: 8px; border-radius: 99px; margin-top: 4px; flex-shrink: 0; }
    .v-notif > div:nth-child(2) { transform: scale(.96); opacity: .8; margin-top: -2px; }
    .v-fields { width: 100%; max-width: 280px; display:grid; gap: 6px; }
    .v-fields > div { display:flex; justify-content:space-between; gap: 10px; padding: 7px 10px; border-radius: 8px; background: var(--card); border: 1px solid var(--border-soft); font-size: 12px; }
    .v-fields span { color: var(--muted); }
    .v-fields b { color: var(--text); font-weight: 600; }
    .v-chips { display:flex; flex-wrap:wrap; gap: 8px; justify-content:center; max-width: 300px; }
    .v-chips span { display:inline-flex; align-items:center; gap: 6px; height: 30px; padding: 0 12px; border-radius: 999px; background: var(--card); border: 1px solid var(--border); font-size: 12.5px; font-weight: 500; color: var(--text-2); }
    .v-chips svg { color: var(--accent); }

    /* ── Confianza ──────────────────────────────────────────────────────── */
    .l-cases { display:grid; gap: 16px; grid-template-columns: 1fr; }
    @media (min-width: 860px) { .l-cases { grid-template-columns: repeat(3, 1fr); } }
    .l-case { height: 100%; padding: 28px 24px; border-radius: 20px; border: 1px solid var(--border); background: var(--card); }
    .l-case-tag { margin: 0 0 14px; letter-spacing: -0.01em; display:flex; align-items:center; gap: 8px; font-size: 16px; font-weight: 600; color: var(--text); }
    .l-case-tag svg { color: var(--accent); }
    .l-case p { margin: 0; font-size: 15px; line-height: 1.6; color: var(--text-2); }
    .l-trust { display:grid; grid-template-columns: 1fr; gap: 0; margin-top: 48px; border-top: 1px solid var(--border); }
    @media (min-width: 640px) { .l-trust { grid-template-columns: repeat(2, 1fr); } }
    @media (min-width: 1040px) { .l-trust { grid-template-columns: repeat(4, 1fr); } }
    .l-trust > li { display:flex; gap: 12px; align-items:flex-start; padding: 22px 4px; border-bottom: 1px solid var(--border-soft); }
    @media (min-width: 1040px) { .l-trust > li { border-bottom: none; padding: 24px 16px 0 0; } }
    .l-trust svg { color: var(--accent); flex-shrink: 0; margin-top: 2px; }
    .l-trust b { display:block; font-size: 14.5px; font-weight: 600; color: var(--text); letter-spacing: -0.01em; }
    .l-trust span { font-size: 13.5px; color: var(--muted); line-height: 1.5; }

    /* ── Precio ─────────────────────────────────────────────────────────── */
    .l-price { display:grid; gap: 32px; grid-template-columns: 1fr; align-items: center; padding: 32px 24px; border-radius: 24px; border: 1px solid var(--border); background: var(--card); box-shadow: var(--shadow-card); }
    @media (min-width: 860px) { .l-price { grid-template-columns: 1.1fr 1fr; padding: 48px; gap: 48px; } }
    .l-price-list { list-style:none; margin:0; padding:0; display:grid; gap: 12px; grid-template-columns: 1fr; }
    @media (min-width: 480px) { .l-price-list { grid-template-columns: 1fr 1fr; } }
    .l-price-list li { display:flex; gap: 10px; align-items:center; font-size: 15px; color: var(--text-2); }
    .l-price-list svg { color: var(--accent); flex-shrink: 0; }

    /* ── FAQ ────────────────────────────────────────────────────────────── */
    .l-faq-grid { display:grid; gap: 40px; grid-template-columns: 1fr; }
    @media (min-width: 960px) { .l-faq-grid { grid-template-columns: 1fr 1.6fr; gap: 64px; } }
    .l-faq { border-top: 1px solid var(--border); }
    .l-faq-item { border-bottom: 1px solid var(--border); }
    .l-faq-q { width:100%; display:flex; align-items:center; justify-content:space-between; gap: 16px; padding: 20px 0; background: transparent; border: 0; cursor: pointer; text-align: left; font: inherit; font-size: 16.5px; font-weight: 600; letter-spacing: -0.015em; color: var(--text); }
    .l-faq-q svg { flex-shrink: 0; color: var(--muted); transition: transform .25s ease; }
    .l-faq-q[aria-expanded="true"] svg { transform: rotate(45deg); color: var(--accent); }
    .l-faq-a { padding: 0 32px 22px 0; font-size: 15px; line-height: 1.65; color: var(--muted); margin: 0; }

    /* ── Cierre + formulario ────────────────────────────────────────────── */
    .l-close { position: relative; overflow: hidden; border-radius: 28px; padding: 40px 20px; background: linear-gradient(160deg, #1A1B3A 0%, #0E0F22 48%, #0B0B0F 100%); color: #F4F4F5; border: 1px solid rgba(129,140,248,.22); }
    @media (min-width: 860px) { .l-close { padding: 64px; } }
    .l-close::before { content:''; position:absolute; inset: 0; background: radial-gradient(120% 80% at 0% 0%, rgba(129,140,248,.22) 0%, rgba(129,140,248,0) 55%); pointer-events: none; }
    .l-close-grid { position: relative; display:grid; gap: 40px; grid-template-columns: 1fr; align-items: start; }
    @media (min-width: 960px) { .l-close-grid { grid-template-columns: 1fr 1fr; gap: 64px; } }
    .l-close .l-h2 { color: #FFFFFF; }
    .l-close .l-lead { color: #A9ABC4; }
    .l-close .l-eyebrow { color: #A5B4FC; }
    .l-close-points { list-style:none; margin: 28px 0 0; padding:0; display:grid; gap: 12px; }
    .l-close-points li { display:flex; gap:10px; align-items:center; font-size: 15px; color: #D6D7E6; }
    .l-close-points svg { color: #A5B4FC; flex-shrink: 0; }
    .l-form { display:grid; gap: 14px; padding: 24px; border-radius: 20px; background: rgba(255,255,255,.04); border: 1px solid rgba(255,255,255,.10); }
    @media (min-width: 560px) { .l-form { padding: 28px; } }
    .l-field { display:grid; gap: 6px; }
    .l-field label { font-size: 13px; font-weight: 600; color: #D6D7E6; }
    .l-field input, .l-field select { width:100%; height: 46px; padding: 0 14px; border-radius: 10px; border: 1px solid rgba(255,255,255,.14); background: rgba(0,0,0,.28); color: #FFFFFF; font: inherit; font-size: 16px; outline: none; transition: border-color .15s ease, box-shadow .15s ease; -webkit-appearance: none; appearance: none; }
    .l-field select { background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='12' height='12' viewBox='0 0 24 24' fill='none' stroke='%23A9ABC4' stroke-width='2.5' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpath d='m6 9 6 6 6-6'/%3E%3C/svg%3E"); background-repeat: no-repeat; background-position: right 14px center; padding-right: 36px; }
    .l-field select option { color: #0A0A0B; }
    .l-field input::placeholder { color: #7E809A; }
    .l-field input:focus, .l-field select:focus { border-color: #818CF8; box-shadow: 0 0 0 3px rgba(129,140,248,.28); }
    .l-field-row { display:grid; gap: 14px; grid-template-columns: 1fr; }
    @media (min-width: 560px) { .l-field-row { grid-template-columns: 1fr 1fr; } }
    .l-form .l-btn.primary { width: 100%; height: 52px; background: #818CF8; color: #0B0B0F; margin-top: 4px; }
    .l-form .l-btn.primary:hover { background: #A5B4FC; }
    .l-form-note { margin: 0; font-size: 13px; color: #A9ABC4; text-align: center; }
    .l-form-note a { color: #FFFFFF; font-weight: 600; }
    .l-form-error { margin: 0; font-size: 13px; color: #FCA5A5; }
    .l-close .l-link { color: #A5B4FC; }
    .l-close :focus-visible { outline-color: #A5B4FC; }

    /* ── Footer ─────────────────────────────────────────────────────────── */
    .l-foot { padding: 40px 0 48px; }
    .l-foot-in { display:flex; flex-wrap:wrap; align-items:center; justify-content:space-between; gap: 16px; }
    .l-foot-links { display:flex; gap: 20px; flex-wrap: wrap; }
    .l-foot a { font-size: 13px; color: var(--muted); text-decoration: none; }
    .l-foot a:hover { color: var(--text); }
    .l-foot small { font-size: 13px; color: var(--muted); }
  `}</style>
)
