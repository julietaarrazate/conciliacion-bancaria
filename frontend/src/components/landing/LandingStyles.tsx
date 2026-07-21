import React from 'react'

export const LandingStyles: React.FC = () => (
  <style>{`
    @import url('https://fonts.googleapis.com/css2?family=Cormorant+Garamond:ital,wght@1,600;1,700&display=swap');

    .landing-root {
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

    /* Reveal al entrar al viewport — única animación permitida en la landing,
       dispara una sola vez y queda fija (ver docs/ux/UX_RULES.md, tono sobrio). */
    .land-reveal { opacity: 0; transform: translateY(18px); transition: opacity 0.6s ease calc(var(--d,0ms)), transform 0.6s ease calc(var(--d,0ms)); }
    .land-reveal[data-visible="true"] { opacity: 1; transform: none; }
    @media (max-width: 719px) { .land-reveal { opacity: 1 !important; transform: none !important; transition: none !important; } }

    .em-serif {
      font-family: 'Cormorant Garamond', Georgia, serif;
      font-style: italic; font-weight: 600;
      color: var(--accent);
    }

    /* Badge estático del hero — sin animación, sin gradiente */
    .eyebrow-badge {
      display: inline-flex; align-items: center; gap: 8px; padding: 6px 14px; border-radius: 999px;
      background: var(--accent-soft); border: 1px solid var(--accent-line); color: var(--accent);
      font-size: 12px; font-weight: 600; margin-bottom: 24px;
    }

    /* Section label */
    .sec-label {
      display: inline-flex; align-items: center; gap: 8px;
      font-size: 10px; font-weight: 700; letter-spacing: 0.16em; text-transform: uppercase;
      color: var(--muted-2); margin-bottom: 20px;
    }
    .sec-label::before { content: ''; display: inline-block; width: 18px; height: 1px; background: var(--muted-2); }

    /* Cards */
    .grad-border { position:relative; background:var(--card); border-radius:16px; border:1px solid var(--border); transition:border-color .2s,transform .2s,box-shadow .2s; }
    .grad-border:hover { border-color:var(--accent-line); transform:translateY(-3px); box-shadow:0 12px 32px rgba(0,0,0,.06); }
    .dark .grad-border:hover { box-shadow:0 12px 32px rgba(0,0,0,.4); }

    /* Nav */
    .land-nav { position:fixed; top:0; left:0; right:0; z-index:50; display:flex; align-items:center; justify-content:space-between; padding:0 20px; height:60px; background:rgba(255,255,255,0.95); backdrop-filter:blur(20px); -webkit-backdrop-filter:blur(20px); border-bottom:1px solid var(--border); transition:background .2s; }
    .dark .land-nav { background:rgba(9,9,13,0.92); }
    .nav-logo { display:flex; align-items:center; gap:8px; font-size:17px; font-weight:700; letter-spacing:-.5px; color:var(--accent); text-decoration:none; flex-shrink:0; }
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

    .btn-ghost { display:inline-flex; align-items:center; gap:6px; padding:8px 16px; border-radius:10px; background:transparent; color:var(--muted); font-weight:500; font-size:13px; border:1px solid var(--border); cursor:pointer; transition:all .15s; text-decoration:none; white-space:nowrap; }
    .btn-ghost:hover { background:var(--bg-soft); color:var(--text); border-color:var(--accent-line); }
    @media (min-width:640px) { .btn-ghost { font-size:14px; padding:9px 18px; } }

    .theme-toggle { width:34px; height:34px; display:inline-flex; align-items:center; justify-content:center; border-radius:10px; background:transparent; border:1px solid var(--border); cursor:pointer; font-size:15px; transition:background .15s,transform .1s; color:var(--text); flex-shrink:0; }
    .theme-toggle:hover { background:var(--bg-soft); }
    .theme-toggle:active { transform:scale(0.92); }

    /* WA */
    .wa-btn { display:inline-flex; align-items:center; gap:10px; padding:13px 24px; border-radius:12px; background:#25D366; color:#fff; font-weight:600; font-size:15px; border:none; cursor:pointer; text-decoration:none; transition:background .15s,transform .1s,box-shadow .15s; box-shadow:0 4px 24px #25D36633; }
    .wa-btn:hover { background:#20C25A; box-shadow:0 6px 32px #25D36644; }
    .wa-btn:active { transform:scale(0.97); }

    /* Footer */
    .footer-link { font-size:12px; color:var(--muted-2); text-decoration:none; transition:color .15s; }
    .footer-link:hover { color:var(--text-2); }

    /* Step num */
    .step-num { display:inline-flex; width:44px; height:44px; border-radius:50%; background:var(--step-num-bg); border:2px solid var(--step-num-bd); align-items:center; justify-content:center; font-weight:800; font-size:13px; color:var(--accent); margin-bottom:16px; flex-shrink:0; }


    /* Hero — sin min-height:100vh a propósito: no es una pantalla de splash
       inmersiva, es un título + CTA seguido inmediatamente por el producto. */
    .hero-section { padding:128px 20px 64px; text-align:center; }
    .hero-title { font-size:clamp(32px,7vw,58px); font-weight:700; line-height:1.12; letter-spacing:-1.5px; max-width:760px; margin:0 auto 20px; }
    .hero-sub { font-size:clamp(15px,2.6vw,18px); color:var(--muted); max-width:520px; margin:0 auto 32px; line-height:1.65; padding:0 8px; }

    /* Sections */
    .section { padding:72px 20px; }
    @media (min-width:720px) { .section { padding:96px 24px; } }
    .section-title { font-size:clamp(26px,6vw,46px); font-weight:700; letter-spacing:-1.5px; margin-bottom:14px; line-height:1.1; }

    /* Feature spotlight */
    .spotlight { display:grid; grid-template-columns:1fr; gap:48px; align-items:center; max-width:960px; margin:0 auto; }
    @media (min-width:820px) { .spotlight { grid-template-columns:1fr 1fr; } }

    /* Cómo funciona — pasos */
    .steps-grid { display:grid; grid-template-columns:1fr; gap:28px; max-width:960px; margin:0 auto; }
    @media (min-width:720px) { .steps-grid { grid-template-columns:repeat(3,1fr); gap:32px; } }

    /* Closing CTA card — color sólido de marca, sin gradiente */
    .cta-card { background:var(--accent); border-radius:24px; padding:56px 32px; text-align:center; }
  `}</style>
)
