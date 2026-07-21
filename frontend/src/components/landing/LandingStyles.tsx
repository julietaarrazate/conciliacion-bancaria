import React from 'react'

export const LandingStyles: React.FC = () => (
  <style>{`
    @import url('https://fonts.googleapis.com/css2?family=Cormorant+Garamond:ital,wght@1,600;1,700&family=Fraunces:opsz,wght@9..144,500;9..144,600;9..144,700;9..144,800&display=swap');

    .landing-root {
      --font-display: 'Fraunces', Georgia, serif;
      --bg:           #FFFFFF;
      --bg-2:         #FFFFFF;
      --bg-soft:      #F4F4F5;
      --card:         #FFFFFF;
      --card-2:       #F4F4F5;
      --border:       #E8E8E8;
      --border-soft:  #EFEFEF;
      --text:         #111111;
      --text-2:       #3F3F46;
      --muted:        #71717A;
      --muted-2:      #A1A1AA;
      --accent:       #16A34A;
      --accent-2:     #15803D;
      --accent-soft:  #16A34A12;
      --accent-line:  #16A34A30;
      --step-num-bg:  #16A34A16;
      --step-num-bd:  #16A34A38;
      --topbar-bg:    #FFFFFF;
      --mock-shadow:  0 24px 60px rgba(0,0,0,.06), 0 0 0 1px #16A34A0D;
    }
    .dark .landing-root {
      --bg:           #050508;
      --bg-2:         #0A0A0F;
      --bg-soft:      #0D0D14;
      --card:         #111118;
      --card-2:       #0D0D14;
      --border:       #1E1E26;
      --border-soft:  #1A1A24;
      --text:         #E4E4E7;
      --text-2:       #D4D4D8;
      --muted:        #71717A;
      --muted-2:      #52525B;
      --accent:       #4ADE80;
      --accent-2:     #4ADE80;
      --accent-soft:  #22C55E12;
      --accent-line:  #22C55E30;
      --step-num-bg:  #22C55E20;
      --step-num-bd:  #22C55E45;
      --topbar-bg:    #0F0F16;
      --mock-shadow:  0 32px 80px rgba(0,0,0,.6), 0 0 0 1px #22C55E18;
    }

    .landing-root {
      min-height: 100vh;
      background: var(--bg);
      color: var(--text);
      font-family: 'Inter', -apple-system, sans-serif;
      -webkit-font-smoothing: antialiased;
      overflow-x: hidden;
    }

    .land-reveal { opacity: 0; transform: translateY(18px); transition: opacity 0.6s ease calc(var(--d,0ms)), transform 0.6s ease calc(var(--d,0ms)); }
    .land-reveal[data-visible="true"] { opacity: 1; transform: none; }
    @media (max-width: 719px) { .land-reveal { opacity: 1 !important; transform: none !important; transition: none !important; } }

    .grad-text {
      background: linear-gradient(135deg, var(--accent-2) 0%, var(--accent) 50%, var(--accent-2) 100%);
      -webkit-background-clip: text; -webkit-text-fill-color: transparent; background-clip: text;
    }

    .em-serif {
      font-family: 'Cormorant Garamond', Georgia, serif;
      font-style: italic; font-weight: 600;
      color: var(--accent);
      -webkit-text-fill-color: var(--accent);
    }

    /* Section label */
    .sec-label {
      display: inline-flex; align-items: center; gap: 8px;
      font-size: 10px; font-weight: 700; letter-spacing: 0.16em; text-transform: uppercase;
      color: var(--muted-2); margin-bottom: 20px;
    }
    .sec-label::before { content: ''; display: inline-block; width: 18px; height: 1px; background: var(--muted-2); }

    /* Animations */
    @keyframes glowPulse { 0%,100%{opacity:.2;transform:scale(1)} 50%{opacity:.45;transform:scale(1.05)} }
    .glow-orb { animation: glowPulse 6s ease-in-out infinite; }
    @keyframes floatMock { 0%{transform:translateY(0)} 100%{transform:translateY(-9px)} }
    .mock-float { animation: floatMock 3.5s ease-in-out infinite alternate; }
    @keyframes flowMove { 0%{transform:translateX(0);opacity:0} 15%{opacity:1} 85%{opacity:1} 100%{transform:translateX(calc(100% + 16px));opacity:0} }
    .flow-dot { animation: flowMove 3s ease-in-out infinite; }
    @keyframes badgeFade { 0%,100%{opacity:1} 50%{opacity:.5} }
    .live-badge { animation: badgeFade 2.5s ease-in-out infinite; }
    @keyframes scanLine { 0%{top:0;opacity:1} 100%{top:100%;opacity:0} }

    /* Cards */
    .grad-border { position:relative; background:var(--card); border-radius:16px; border:1px solid var(--border); transition:border-color .2s,transform .2s,box-shadow .2s; }
    .grad-border:hover { border-color:var(--accent-line); transform:translateY(-3px); box-shadow:0 12px 32px rgba(0,0,0,.06); }
    .dark .grad-border:hover { box-shadow:0 12px 32px rgba(0,0,0,.4); }

    /* Nav */
    .land-nav { position:fixed; top:0; left:0; right:0; z-index:50; display:flex; align-items:center; justify-content:space-between; padding:0 20px; height:60px; background:rgba(255,255,255,0.95); backdrop-filter:blur(20px); -webkit-backdrop-filter:blur(20px); border-bottom:1px solid var(--border); transition:background .2s; }
    .dark .land-nav { background:rgba(9,9,13,0.92); }
    .nav-logo { display:flex; align-items:center; gap:8px; font-family:var(--font-display); font-size:18px; font-weight:600; letter-spacing:-.3px; color:var(--accent); text-decoration:none; flex-shrink:0; }
    .nav-actions { display:flex; align-items:center; gap:8px; }
    .nav-links { display:none; }
    @media (min-width:720px) { .nav-links { display:flex; gap:2px; align-items:center; } }

    .mobile-menu-overlay { display:block; position:fixed; top:60px; left:0; right:0; z-index:49; background:var(--card); border-bottom:1px solid var(--border); padding:8px 12px 16px; box-shadow:0 8px 32px rgba(0,0,0,.12); }
    .dark .mobile-menu-overlay { box-shadow:0 8px 32px rgba(0,0,0,.5); }
    @media (min-width:720px) { .mobile-menu-overlay { display:none; } }
    .mobile-menu-overlay a { display:block; padding:12px 14px; border-radius:10px; font-size:15px; font-weight:500; color:var(--text); text-decoration:none; transition:background .1s; }
    .mobile-menu-overlay a:hover { background:var(--bg-soft); }

    .ham-btn { display:inline-flex; align-items:center; justify-content:center; width:34px; height:34px; border-radius:10px; background:transparent; border:1px solid var(--border); cursor:pointer; color:var(--text); font-size:16px; transition:background .15s; flex-shrink:0; }
    .ham-btn:hover { background:var(--bg-soft); }
    @media (min-width:720px) { .ham-btn { display:none; } }

    /* Buttons */
    .btn-green { display:inline-flex; align-items:center; gap:6px; padding:9px 18px; border-radius:10px; background:var(--accent); color:#fff; font-weight:600; font-size:14px; line-height:1; border:none; cursor:pointer; transition:background .15s,transform .1s; text-decoration:none; white-space:nowrap; }
    .dark .btn-green { color:#000; }
    .btn-green:hover { background:var(--accent-2); }
    .btn-green:active { transform:scale(0.97); }
    .btn-green.large { padding:14px 28px; font-size:15px; border-radius:12px; }
    @media (min-width:640px) { .btn-green.large { padding:14px 32px; font-size:16px; } }

    .btn-ghost { display:inline-flex; align-items:center; gap:6px; padding:8px 16px; border-radius:10px; background:transparent; color:var(--muted); font-weight:500; font-size:13px; border:1px solid var(--border); cursor:pointer; transition:all .15s; text-decoration:none; white-space:nowrap; }
    .btn-ghost:hover { background:var(--bg-soft); color:var(--text); border-color:var(--accent-line); }
    @media (min-width:640px) { .btn-ghost { font-size:14px; padding:9px 18px; } }

    .theme-toggle { width:34px; height:34px; display:inline-flex; align-items:center; justify-content:center; border-radius:10px; background:transparent; border:1px solid var(--border); cursor:pointer; font-size:15px; transition:background .15s,transform .1s; color:var(--text); flex-shrink:0; }
    .theme-toggle:hover { background:var(--bg-soft); }
    .theme-toggle:active { transform:scale(0.92); }

    /* Form */
    .land-input { width:100%; background:var(--card-2); border:1px solid var(--border); border-radius:10px; padding:12px 14px; color:var(--text); font-size:14px; outline:none; transition:border .15s; font-family:inherit; box-sizing:border-box; }
    .land-input:focus { border-color:var(--accent-line); box-shadow:0 0 0 3px var(--accent-soft); }
    .land-input::placeholder { color:var(--muted-2); }

    /* Pills */
    .pill { display:inline-block; padding:5px 14px; border-radius:999px; background:var(--accent-soft); border:1px solid var(--accent-line); color:var(--accent); font-size:11px; font-weight:600; letter-spacing:.06em; text-transform:uppercase; }

    /* WA */
    .wa-btn { display:inline-flex; align-items:center; gap:10px; padding:13px 24px; border-radius:12px; background:#25D366; color:#fff; font-weight:600; font-size:15px; border:none; cursor:pointer; text-decoration:none; transition:background .15s,transform .1s,box-shadow .15s; box-shadow:0 4px 24px #25D36633; }
    .wa-btn:hover { background:#20C25A; box-shadow:0 6px 32px #25D36644; }
    .wa-btn:active { transform:scale(0.97); }

    /* Footer */
    .footer-link { font-size:12px; color:var(--muted-2); text-decoration:none; transition:color .15s; }
    .footer-link:hover { color:var(--text-2); }

    /* FAQ */
    .faq-item { border:1px solid var(--border); border-radius:12px; background:var(--card); overflow:hidden; transition:border-color .15s; }
    .faq-item:hover { border-color:var(--accent-line); }
    .faq-q { width:100%; display:flex; align-items:center; justify-content:space-between; gap:12px; padding:18px 20px; background:transparent; border:none; cursor:pointer; text-align:left; font-size:15px; font-weight:600; color:var(--text); font-family:inherit; }
    .faq-q-icon { width:22px; height:22px; display:flex; align-items:center; justify-content:center; color:var(--accent); font-size:20px; transition:transform .25s; flex-shrink:0; }
    .faq-q-icon.open { transform:rotate(45deg); }
    .faq-a { padding:0 20px 18px; font-size:14px; line-height:1.65; color:var(--muted); border-top:1px solid var(--border-soft); padding-top:14px; }

    /* Table */
    .compare-table { width:100%; border-collapse:collapse; background:var(--card); border-radius:12px; overflow:hidden; border:1px solid var(--border); }
    .compare-table th { padding:14px 18px; font-size:11px; font-weight:600; text-transform:uppercase; letter-spacing:.07em; color:var(--muted-2); text-align:left; background:var(--card-2); border-bottom:1px solid var(--border); }
    .compare-table th:last-child { color:var(--accent); }
    .compare-table td { padding:13px 18px; font-size:14px; color:var(--text-2); border-bottom:1px solid var(--border-soft); }
    .compare-table tr:last-child td { border-bottom:none; }
    .compare-table td.feature { font-weight:500; color:var(--text); }
    .compare-table td.excel { color:var(--muted); }
    .compare-table td.cuadra { color:var(--accent); font-weight:600; }

    /* Stats grid */
    .stats-grid { display:grid; grid-template-columns:repeat(2,1fr); gap:1px; background:var(--border); border-radius:16px; overflow:hidden; border:1px solid var(--border); }
    @media (min-width:720px) { .stats-grid { grid-template-columns:repeat(4,1fr); } }

    /* Step num */
    .step-num { display:inline-flex; width:44px; height:44px; border-radius:50%; background:var(--step-num-bg); border:2px solid var(--step-num-bd); align-items:center; justify-content:center; font-weight:800; font-size:13px; color:var(--accent); margin-bottom:16px; flex-shrink:0; }


    /* Hero */
    .hero-section { position:relative; min-height:100vh; display:flex; flex-direction:column; align-items:center; justify-content:center; padding:90px 20px 56px; text-align:center; overflow:hidden; }
    .hero-title { font-family:var(--font-display); font-size:clamp(40px,10vw,88px); font-weight:600; line-height:1.04; letter-spacing:-0.02em; max-width:820px; margin-bottom:24px; }
    .hero-sub { font-size:clamp(15px,3.5vw,20px); color:var(--muted); max-width:500px; line-height:1.65; margin-bottom:36px; padding:0 8px; font-weight:400; }
    .mockup-wrap { width:100%; max-width:560px; padding:0 4px; }

    /* Sections */
    .section { padding:72px 20px; }
    @media (min-width:720px) { .section { padding:96px 24px; } }
    .section-title { font-family:var(--font-display); font-size:clamp(27px,6vw,48px); font-weight:600; letter-spacing:-0.015em; margin-bottom:14px; line-height:1.12; }

    /* Feature spotlight */
    .spotlight { display:grid; grid-template-columns:1fr; gap:48px; align-items:center; max-width:960px; margin:0 auto; }
    @media (min-width:820px) { .spotlight { grid-template-columns:1fr 1fr; } }
    .spotlight.reverse { }
    @media (min-width:820px) { .spotlight.reverse .spotlight-text { order:2; } .spotlight.reverse .spotlight-mock { order:1; } }

    /* Range input */
    .calc-range { -webkit-appearance:none; appearance:none; height:5px; background:var(--border); border-radius:3px; outline:none; cursor:pointer; }
    .calc-range::-webkit-slider-thumb { -webkit-appearance:none; appearance:none; width:20px; height:20px; border-radius:50%; background:var(--accent); cursor:pointer; border:2px solid var(--bg); box-shadow:0 2px 8px rgba(0,0,0,.18); }
    .calc-range::-moz-range-thumb { width:20px; height:20px; border-radius:50%; background:var(--accent); cursor:pointer; border:2px solid var(--bg); }

    /* Closing CTA card */
    .cta-card { background:var(--accent); border-radius:24px; padding:56px 32px; text-align:center; position:relative; overflow:hidden; }
    .cta-card::before { content:''; position:absolute; top:-60px; right:-60px; width:300px; height:300px; border-radius:50%; background:rgba(255,255,255,.06); pointer-events:none; }
    .cta-card::after { content:''; position:absolute; bottom:-80px; left:-40px; width:240px; height:240px; border-radius:50%; background:rgba(255,255,255,.04); pointer-events:none; }
  `}</style>
)
