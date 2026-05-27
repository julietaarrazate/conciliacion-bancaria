import React, { useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { useThemeStore } from '@/store/theme'

const WA_NUMBER = '543774504024'
const WA_LINK   = `https://wa.me/${WA_NUMBER}?text=Hola%20Julieta%2C%20me%20interesa%20conocer%20m%C3%A1s%20sobre%20Cuadra`

function useReveal(threshold = 0.1) {
  const ref = useRef<HTMLDivElement>(null)
  useEffect(() => {
    const el = ref.current
    if (!el) return
    const obs = new IntersectionObserver(
      ([e]) => { if (e.isIntersecting) { el.dataset.visible = 'true'; obs.disconnect() } },
      { threshold }
    )
    obs.observe(el)
    return () => obs.disconnect()
  }, [threshold])
  return ref
}

const R: React.FC<{ children: React.ReactNode; delay?: number; className?: string }> = ({
  children, delay = 0, className = ''
}) => {
  const ref = useReveal()
  return (
    <div ref={ref} className={`land-reveal ${className}`} style={{ '--d': `${delay}ms` } as React.CSSProperties}>
      {children}
    </div>
  )
}

const FEATURES = [
  { icon: '⚡', title: 'Conciliación automática', desc: 'Cruza extractos bancarios con planillas de clientes por CUIT, CBU y referencia. Lo que cuadra, cuadra solo — sin tocar nada.' },
  { icon: '📸', title: 'OPs desde el celular', desc: 'Registrá órdenes de pago firmadas con foto del comprobante. Tres pasos, desde el celular, en movimiento.' },
  { icon: '🏦', title: 'Cheques y pagos', desc: 'Seguimiento de cheques propios y de terceros con alertas automáticas antes del vencimiento.' },
  { icon: '💰', title: 'Caja diaria', desc: 'Arqueo físico de billetes, saldo inicial e ingresos. El cruce contra la caja en tiempo real.' },
  { icon: '🏢', title: 'Multi-empresa', desc: 'Todos tus clientes desde un solo lugar. Cada empresa ve solo sus propios datos, sin mezclas.' },
  { icon: '📤', title: 'Export para el contador', desc: 'Excel formato Macro, PDF de cierre mensual y estado de cuenta por cliente. Listo para entregar.' },
]

const STEPS = [
  { n: '01', title: 'Subís el extracto bancario', desc: 'Arrastrás el Excel del banco. El sistema lo parsea automáticamente.' },
  { n: '02', title: 'Cargás la planilla del cliente', desc: 'Subís la planilla de pagos. La conciliación corre sola.' },
  { n: '03', title: 'Revisás y exportás', desc: 'Lo ambiguo queda para revisión manual. El resto, listo para el contador.' },
]

const STATS = [
  { value: '124', label: 'tests automatizados' },
  { value: '99%', label: 'uptime en producción' },
  { value: '< 1s', label: 'tiempo de conciliación' },
  { value: '0', label: 'instalaciones necesarias' },
]

// Filas de ejemplo — nombres genéricos, no clientes reales
const MOCKUP_ROWS = [
  { cliente: 'Cliente Norte SRL',  importe: '$124.500', ok: true  },
  { cliente: 'Constructora Sur',   importe: '$89.200',  ok: true  },
  { cliente: 'Distribuidora Este', importe: '$212.000', ok: false },
  { cliente: 'Servicios Centro',   importe: '$56.800',  ok: true  },
  { cliente: 'Comercial Oeste',    importe: '$98.400',  ok: true  },
]

export const Landing: React.FC = () => {
  const { theme, toggle } = useThemeStore()
  const [form, setForm] = useState({ nombre: '', email: '', mensaje: '' })
  const [formSent, setFormSent] = useState(false)

  const handleContact = (e: React.FormEvent) => {
    e.preventDefault()
    const texto = encodeURIComponent(
      `Hola Julieta, soy ${form.nombre}${form.email ? ` (${form.email})` : ''}.\n\n${form.mensaje}`
    )
    window.open(`https://wa.me/${WA_NUMBER}?text=${texto}`, '_blank')
    setFormSent(true)
  }

  return (
    <div className="landing-root">

      <style>{`
        /* ─── Variables claro/oscuro ───────────────────────────────────── */
        .landing-root {
          --bg:           #FAFAFA;
          --bg-2:         #FFFFFF;
          --bg-soft:      #F4F4F5;
          --card:         #FFFFFF;
          --card-2:       #FAFAFA;
          --border:       #E4E4E7;
          --border-soft:  #EEEEEF;
          --text:         #18181B;
          --text-2:       #3F3F46;
          --muted:        #71717A;
          --muted-2:      #A1A1AA;
          --accent:       #16A34A;
          --accent-2:     #15803D;
          --accent-soft:  #16A34A14;
          --accent-line:  #16A34A33;
          --topbar-bg:    #F4F4F5;
          --mock-shadow:  0 24px 60px rgba(0,0,0,.08), 0 0 0 1px #16A34A10;
        }
        .dark .landing-root {
          --bg:           #09090D;
          --bg-2:         #0D0D13;
          --bg-soft:      #0F0F16;
          --card:         #13131A;
          --card-2:       #0F0F16;
          --border:       #1E1E26;
          --border-soft:  #1A1A24;
          --text:         #E4E4E7;
          --text-2:       #D4D4D8;
          --muted:        #71717A;
          --muted-2:      #52525B;
          --accent:       #22C55E;
          --accent-2:     #4ADE80;
          --accent-soft:  #22C55E12;
          --accent-line:  #22C55E30;
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
          transition: background 0.2s, color 0.2s;
        }

        .land-reveal {
          opacity: 0;
          transform: translateY(20px);
          transition: opacity 0.65s ease calc(var(--d, 0ms)), transform 0.65s ease calc(var(--d, 0ms));
        }
        .land-reveal[data-visible="true"] { opacity: 1; transform: none; }

        .grad-text {
          background: linear-gradient(135deg, var(--accent-2) 0%, var(--accent) 50%, var(--accent-2) 100%);
          -webkit-background-clip: text;
          -webkit-text-fill-color: transparent;
          background-clip: text;
        }

        @keyframes glowPulse {
          0%, 100% { opacity: 0.3; transform: scale(1); }
          50%       { opacity: 0.6; transform: scale(1.05); }
        }
        .glow-orb { animation: glowPulse 5s ease-in-out infinite; }

        @keyframes floatMock {
          0%   { transform: translateY(0) rotateX(2deg); }
          100% { transform: translateY(-10px) rotateX(0deg); }
        }
        .mock-float { animation: floatMock 3.5s ease-in-out infinite alternate; }

        .grad-border {
          position: relative;
          background: var(--card);
          border-radius: 16px;
          border: 1px solid var(--border);
          transition: border-color 0.2s, transform 0.2s, box-shadow 0.2s;
        }
        .grad-border:hover {
          border-color: var(--accent-line);
          transform: translateY(-3px);
          box-shadow: 0 12px 32px rgba(0,0,0,.06);
        }
        .dark .grad-border:hover {
          box-shadow: 0 12px 32px rgba(0,0,0,.4);
        }

        .land-nav {
          position: fixed; top: 0; left: 0; right: 0; z-index: 50;
          display: flex; align-items: center; justify-content: space-between;
          padding: 16px 24px;
          background: rgba(250,250,250,0.85);
          backdrop-filter: blur(16px);
          border-bottom: 1px solid var(--border);
          transition: background 0.2s;
        }
        .dark .land-nav { background: rgba(9,9,13,0.85); }

        .btn-green {
          display: inline-flex; align-items: center; gap: 8px;
          padding: 10px 22px; border-radius: 10px;
          background: var(--accent); color: #fff; font-weight: 600; font-size: 14px;
          border: none; cursor: pointer;
          transition: background 0.15s, transform 0.1s;
          text-decoration: none;
        }
        .dark .btn-green { color: #000; }
        .btn-green:hover { background: var(--accent-2); }
        .btn-green:active { transform: scale(0.97); }
        .btn-green.large { padding: 14px 32px; font-size: 16px; border-radius: 12px; }

        .btn-ghost {
          display: inline-flex; align-items: center; gap: 8px;
          padding: 10px 22px; border-radius: 10px;
          background: transparent; color: var(--muted); font-weight: 500; font-size: 14px;
          border: 1px solid var(--border); cursor: pointer;
          transition: all 0.15s;
          text-decoration: none;
        }
        .btn-ghost:hover {
          background: var(--card);
          color: var(--text);
        }

        .theme-toggle {
          width: 36px; height: 36px;
          display: inline-flex; align-items: center; justify-content: center;
          border-radius: 10px;
          background: transparent;
          border: 1px solid var(--border);
          cursor: pointer;
          font-size: 15px;
          transition: background 0.15s, transform 0.1s;
          color: var(--text);
        }
        .theme-toggle:hover { background: var(--card); }
        .theme-toggle:active { transform: scale(0.92); }

        .land-input {
          width: 100%;
          background: var(--card-2); border: 1px solid var(--border); border-radius: 10px;
          padding: 12px 16px; color: var(--text); font-size: 14px;
          outline: none; transition: border 0.15s;
          font-family: inherit;
        }
        .land-input:focus {
          border-color: var(--accent-line);
          box-shadow: 0 0 0 3px var(--accent-soft);
        }
        .land-input::placeholder { color: var(--muted-2); }

        @keyframes badgeFade {
          0%, 100% { opacity: 1; }
          50%       { opacity: 0.6; }
        }
        .live-badge { animation: badgeFade 2.5s ease-in-out infinite; }

        .pill {
          display: inline-block; padding: 5px 14px; border-radius: 999px;
          background: var(--accent-soft); border: 1px solid var(--accent-line);
          color: var(--accent); font-size: 12px; font-weight: 600;
          letter-spacing: 0.06em; text-transform: uppercase;
        }

        .wa-btn {
          display: inline-flex; align-items: center; gap: 10px;
          padding: 14px 28px; border-radius: 12px;
          background: #25D366; color: #fff; font-weight: 600; font-size: 15px;
          border: none; cursor: pointer; text-decoration: none;
          transition: background 0.15s, transform 0.1s, box-shadow 0.15s;
          box-shadow: 0 4px 24px #25D36633;
        }
        .wa-btn:hover { background: #20C25A; box-shadow: 0 6px 32px #25D36644; }
        .wa-btn:active { transform: scale(0.97); }

        .footer-link {
          font-size: 12px; color: var(--muted-2); text-decoration: none;
          transition: color 0.15s;
        }
        .footer-link:hover { color: var(--text-2); }
      `}</style>

      {/* ── NAV ── */}
      <nav className="land-nav">
        <span style={{ fontSize: 18, fontWeight: 700, letterSpacing: '-0.5px', color: 'var(--accent)' }}>
          Cuadra
        </span>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <a href="#features" className="btn-ghost" style={{ padding: '7px 14px' }}>
            Features
          </a>
          <a href="#contacto" className="btn-ghost" style={{ padding: '7px 14px' }}>
            Contacto
          </a>
          <button
            onClick={toggle}
            className="theme-toggle"
            title={theme === 'dark' ? 'Cambiar a modo claro' : 'Cambiar a modo oscuro'}
            aria-label="Cambiar tema"
          >
            {theme === 'dark' ? '☀' : '☾'}
          </button>
          <Link to="/login" className="btn-green">
            Ingresar →
          </Link>
        </div>
      </nav>

      {/* ── HERO ── */}
      <section style={{ position: 'relative', minHeight: '100vh', display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', padding: '96px 24px 64px', textAlign: 'center', overflow: 'hidden' }}>

        <div className="glow-orb" style={{ position: 'absolute', top: '20%', left: '50%', transform: 'translateX(-50%)', width: 700, height: 400, borderRadius: '50%', background: 'radial-gradient(circle, var(--accent-soft) 0%, transparent 70%)', pointerEvents: 'none' }} />

        <div className="live-badge" style={{ display: 'inline-flex', alignItems: 'center', gap: 8, padding: '6px 14px', borderRadius: 999, background: 'var(--accent-soft)', border: '1px solid var(--accent-line)', color: 'var(--accent)', fontSize: 12, fontWeight: 600, marginBottom: 28 }}>
          <span style={{ width: 6, height: 6, borderRadius: '50%', background: 'var(--accent)', display: 'inline-block' }} />
          Sistema de conciliación bancaria · en producción
        </div>

        <h1 style={{ fontSize: 'clamp(40px, 7vw, 80px)', fontWeight: 800, lineHeight: 1.08, letterSpacing: '-2px', maxWidth: 800, marginBottom: 24 }}>
          Los números<br />
          <span className="grad-text">cuadran solos.</span>
        </h1>

        <p style={{ fontSize: 'clamp(16px, 2.5vw, 20px)', color: 'var(--muted)', maxWidth: 520, lineHeight: 1.65, marginBottom: 40 }}>
          Conciliación bancaria automática, gestión de caja, cheques y órdenes de pago.
          Para vos y tu equipo, desde el celular o la web.
        </p>

        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 12, justifyContent: 'center', marginBottom: 72 }}>
          <Link to="/login" className="btn-green large">
            Ingresar al sistema →
          </Link>
          <a href="#contacto" className="btn-ghost" style={{ padding: '14px 28px', fontSize: 16, borderRadius: 12 }}>
            Conocer más
          </a>
        </div>

        {/* Mockup */}
        <div className="mock-float" style={{ width: '100%', maxWidth: 560, perspective: 1000 }}>
          <div style={{ borderRadius: 20, border: '1px solid var(--border)', background: 'var(--card)', boxShadow: 'var(--mock-shadow)', overflow: 'hidden' }}>

            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '12px 16px', borderBottom: '1px solid var(--border)', background: 'var(--topbar-bg)' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <div style={{ width: 28, height: 28, borderRadius: 8, background: 'var(--accent-soft)', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 14 }}>⚡</div>
                <span style={{ fontSize: 13, fontWeight: 600, color: 'var(--accent)' }}>Cuadra</span>
              </div>
              <div style={{ display: 'flex', gap: 6 }}>
                {['#FF5F57','#FFBD2E','#28C840'].map(c => <div key={c} style={{ width: 10, height: 10, borderRadius: '50%', background: c }} />)}
              </div>
            </div>

            <div style={{ padding: 16 }}>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 8, marginBottom: 16 }}>
                {[
                  { label: 'Conciliados', val: '47', color: 'var(--accent)' },
                  { label: 'Pendientes', val: '3', color: '#F59E0B' },
                  { label: 'Caja', val: '$482k', color: '#5E6AD2' },
                ].map(s => (
                  <div key={s.label} style={{ background: 'var(--card-2)', borderRadius: 10, padding: '10px 12px', border: '1px solid var(--border-soft)' }}>
                    <div style={{ fontSize: 18, fontWeight: 700, color: s.color, fontFamily: 'monospace' }}>{s.val}</div>
                    <div style={{ fontSize: 10, color: 'var(--muted-2)', marginTop: 2 }}>{s.label}</div>
                  </div>
                ))}
              </div>

              <div style={{ fontSize: 11, color: 'var(--muted-2)', fontWeight: 600, marginBottom: 8, textTransform: 'uppercase', letterSpacing: '0.08em' }}>
                Planilla del mes
              </div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                {MOCKUP_ROWS.map((r, i) => (
                  <div key={i} style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '8px 12px', borderRadius: 8, background: 'var(--card-2)', border: '1px solid var(--border-soft)' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                      <div style={{ width: 6, height: 6, borderRadius: '50%', flexShrink: 0, background: r.ok ? 'var(--accent)' : '#F59E0B' }} />
                      <span style={{ fontSize: 12, fontWeight: 500, color: 'var(--text-2)' }}>{r.cliente}</span>
                    </div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                      <span style={{ fontSize: 12, fontFamily: 'monospace', color: 'var(--muted)' }}>{r.importe}</span>
                      <span style={{ fontSize: 10, padding: '2px 7px', borderRadius: 4, background: r.ok ? 'var(--accent-soft)' : '#F59E0B18', color: r.ok ? 'var(--accent)' : '#F59E0B', fontWeight: 600 }}>
                        {r.ok ? 'OK' : 'REVISAR'}
                      </span>
                    </div>
                  </div>
                ))}
              </div>

              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: 12, paddingTop: 12, borderTop: '1px solid var(--border)' }}>
                <span style={{ fontSize: 11, color: 'var(--muted-2)' }}>4 conciliados · 1 para revisar</span>
                <div style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 11, color: 'var(--accent)', fontWeight: 600, cursor: 'pointer' }}>
                  ↓ Exportar Excel
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* ── STATS ── */}
      <section style={{ padding: '0 24px 80px' }}>
        <div style={{ maxWidth: 900, margin: '0 auto', display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: 1, background: 'var(--border)', borderRadius: 16, overflow: 'hidden', border: '1px solid var(--border)' }}>
          {STATS.map((s, i) => (
            <R key={s.label} delay={i * 60}>
              <div style={{ padding: '28px 24px', background: 'var(--bg)', textAlign: 'center' }}>
                <div style={{ fontSize: 32, fontWeight: 800, color: 'var(--accent)', fontFamily: 'monospace', letterSpacing: '-1px' }}>{s.value}</div>
                <div style={{ fontSize: 12, color: 'var(--muted-2)', marginTop: 4 }}>{s.label}</div>
              </div>
            </R>
          ))}
        </div>
      </section>

      {/* ── FEATURES ── */}
      <section id="features" style={{ padding: '80px 24px' }}>
        <div style={{ maxWidth: 1000, margin: '0 auto' }}>
          <R>
            <div style={{ textAlign: 'center', marginBottom: 56 }}>
              <div className="pill" style={{ marginBottom: 16 }}>Todo en un lugar</div>
              <h2 style={{ fontSize: 'clamp(28px, 4vw, 44px)', fontWeight: 800, letterSpacing: '-1px', marginBottom: 12 }}>
                Diseñado para el trabajo diario
              </h2>
              <p style={{ color: 'var(--muted)', fontSize: 16, maxWidth: 460, margin: '0 auto' }}>
                Cada módulo construido para que sea rápido usarlo, no para que sea lindo explicarlo.
              </p>
            </div>
          </R>

          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))', gap: 16 }}>
            {FEATURES.map((f, i) => (
              <R key={f.title} delay={i * 70}>
                <div className="grad-border" style={{ padding: 24, height: '100%' }}>
                  <div style={{ fontSize: 28, marginBottom: 14 }}>{f.icon}</div>
                  <div style={{ fontWeight: 700, fontSize: 15, marginBottom: 8, color: 'var(--text)' }}>{f.title}</div>
                  <div style={{ fontSize: 13, color: 'var(--muted)', lineHeight: 1.65 }}>{f.desc}</div>
                </div>
              </R>
            ))}
          </div>
        </div>
      </section>

      {/* ── CÓMO FUNCIONA ── */}
      <section style={{ padding: '80px 24px', background: 'var(--bg-2)', borderTop: '1px solid var(--border-soft)', borderBottom: '1px solid var(--border-soft)' }}>
        <div style={{ maxWidth: 900, margin: '0 auto' }}>
          <R>
            <div style={{ textAlign: 'center', marginBottom: 56 }}>
              <div className="pill" style={{ marginBottom: 16 }}>Simple por diseño</div>
              <h2 style={{ fontSize: 'clamp(28px, 4vw, 44px)', fontWeight: 800, letterSpacing: '-1px' }}>
                De la planilla al Excel del contador
              </h2>
            </div>
          </R>

          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))', gap: 8 }}>
            {STEPS.map((s, i) => (
              <R key={s.n} delay={i * 100}>
                <div style={{ padding: '28px 24px', borderRadius: 16, background: 'var(--card)', border: '1px solid var(--border)' }}>
                  <div style={{ fontSize: 56, fontWeight: 900, color: 'var(--accent-soft)', fontFamily: 'monospace', lineHeight: 1, marginBottom: 12, letterSpacing: '-2px' }}>{s.n}</div>
                  <div style={{ fontWeight: 700, fontSize: 16, marginBottom: 8, color: 'var(--text)' }}>{s.title}</div>
                  <div style={{ fontSize: 13, color: 'var(--muted)', lineHeight: 1.65 }}>{s.desc}</div>
                </div>
              </R>
            ))}
          </div>
        </div>
      </section>

      {/* ── PARA TU EQUIPO ── */}
      <section style={{ padding: '80px 24px' }}>
        <div style={{ maxWidth: 900, margin: '0 auto', display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))', gap: 48, alignItems: 'center' }}>
          <R>
            <div>
              <div className="pill" style={{ marginBottom: 20 }}>PWA instalable</div>
              <h2 style={{ fontSize: 'clamp(26px, 3.5vw, 38px)', fontWeight: 800, letterSpacing: '-1px', marginBottom: 16, lineHeight: 1.2 }}>
                Desde el celular<br />o la web
              </h2>
              <p style={{ color: 'var(--muted)', lineHeight: 1.7, marginBottom: 24, fontSize: 15 }}>
                Instalala como app sin pasar por el App Store ni el Play Store.
                Actualizaciones automáticas — sin reinstalar nunca.
              </p>
              <ul style={{ listStyle: 'none', padding: 0, margin: 0, display: 'flex', flexDirection: 'column', gap: 12 }}>
                {['Android e iPhone', 'Sin instalación desde tiendas', 'Actualizaciones silenciosas', 'Notificaciones push'].map(item => (
                  <li key={item} style={{ display: 'flex', alignItems: 'center', gap: 10, fontSize: 14, color: 'var(--text-2)' }}>
                    <span style={{ color: 'var(--accent)', fontWeight: 700, fontSize: 16 }}>✓</span>
                    {item}
                  </li>
                ))}
              </ul>
            </div>
          </R>

          <R delay={150}>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
              {[
                { icon: '📱', title: 'Campo / cobranza', sub: 'Celular · OPs, fotos, caja', color: 'var(--accent)' },
                { icon: '💻', title: 'Contabilidad', sub: 'Web · extractos, conciliación, exports', color: '#5E6AD2' },
                { icon: '👁', title: 'Supervisión', sub: 'Web o celular · solo lectura', color: '#F59E0B' },
              ].map(r => (
                <div key={r.title} className="grad-border" style={{ display: 'flex', alignItems: 'center', gap: 14, padding: '16px 20px' }}>
                  <div style={{ width: 44, height: 44, borderRadius: 12, background: `color-mix(in srgb, ${r.color} 12%, transparent)`, display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 20, flexShrink: 0 }}>
                    {r.icon}
                  </div>
                  <div>
                    <div style={{ fontWeight: 600, fontSize: 14, color: 'var(--text)' }}>{r.title}</div>
                    <div style={{ fontSize: 12, color: 'var(--muted-2)', marginTop: 2 }}>{r.sub}</div>
                  </div>
                </div>
              ))}
            </div>
          </R>
        </div>
      </section>

      {/* ── CONTACTO ── */}
      <section id="contacto" style={{ padding: '80px 24px', background: 'var(--bg-2)', borderTop: '1px solid var(--border-soft)' }}>
        <div style={{ maxWidth: 560, margin: '0 auto' }}>
          <R>
            <div style={{ textAlign: 'center', marginBottom: 40 }}>
              <div className="pill" style={{ marginBottom: 16 }}>Contacto</div>
              <h2 style={{ fontSize: 'clamp(26px, 3.5vw, 38px)', fontWeight: 800, letterSpacing: '-1px', marginBottom: 12 }}>
                ¿Querés implementar Cuadra?
              </h2>
              <p style={{ color: 'var(--muted)', fontSize: 15, lineHeight: 1.65 }}>
                Escribime directo por WhatsApp o completá el formulario y te contacto a la brevedad.
              </p>
            </div>
          </R>

          <R delay={100}>
            <div style={{ textAlign: 'center', marginBottom: 32 }}>
              <a href={WA_LINK} target="_blank" rel="noopener noreferrer" className="wa-btn">
                <svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor">
                  <path d="M17.472 14.382c-.297-.149-1.758-.867-2.03-.967-.273-.099-.471-.148-.67.15-.197.297-.767.966-.94 1.164-.173.199-.347.223-.644.075-.297-.15-1.255-.463-2.39-1.475-.883-.788-1.48-1.761-1.653-2.059-.173-.297-.018-.458.13-.606.134-.133.298-.347.446-.52.149-.174.198-.298.298-.497.099-.198.05-.371-.025-.52-.075-.149-.669-1.612-.916-2.207-.242-.579-.487-.5-.669-.51-.173-.008-.371-.01-.57-.01-.198 0-.52.074-.792.372-.272.297-1.04 1.016-1.04 2.479 0 1.462 1.065 2.875 1.213 3.074.149.198 2.096 3.2 5.077 4.487.709.306 1.262.489 1.694.625.712.227 1.36.195 1.871.118.571-.085 1.758-.719 2.006-1.413.248-.694.248-1.289.173-1.413-.074-.124-.272-.198-.57-.347m-5.421 7.403h-.004a9.87 9.87 0 01-5.031-1.378l-.361-.214-3.741.982.998-3.648-.235-.374a9.86 9.86 0 01-1.51-5.26c.001-5.45 4.436-9.884 9.888-9.884 2.64 0 5.122 1.03 6.988 2.898a9.825 9.825 0 012.893 6.994c-.003 5.45-4.437 9.884-9.885 9.884m8.413-18.297A11.815 11.815 0 0012.05 0C5.495 0 .16 5.335.157 11.892c0 2.096.547 4.142 1.588 5.945L.057 24l6.305-1.654a11.882 11.882 0 005.683 1.448h.005c6.554 0 11.89-5.335 11.893-11.893a11.821 11.821 0 00-3.48-8.413z"/>
                </svg>
                Escribir por WhatsApp
              </a>
            </div>

            <div style={{ display: 'flex', alignItems: 'center', gap: 16, marginBottom: 28 }}>
              <div style={{ flex: 1, height: 1, background: 'var(--border)' }} />
              <span style={{ fontSize: 12, color: 'var(--muted-2)' }}>o completá el formulario</span>
              <div style={{ flex: 1, height: 1, background: 'var(--border)' }} />
            </div>

            {formSent ? (
              <div style={{ textAlign: 'center', padding: '32px 24px', borderRadius: 16, background: 'var(--accent-soft)', border: '1px solid var(--accent-line)' }}>
                <div style={{ fontSize: 32, marginBottom: 12 }}>✅</div>
                <div style={{ fontWeight: 700, color: 'var(--accent)', marginBottom: 8 }}>¡Mensaje enviado!</div>
                <div style={{ fontSize: 13, color: 'var(--muted)' }}>Te abrió WhatsApp con tu mensaje. Respondemos a la brevedad.</div>
              </div>
            ) : (
              <form onSubmit={handleContact} style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
                  <div>
                    <label style={{ fontSize: 12, fontWeight: 500, color: 'var(--text-2)', display: 'block', marginBottom: 6 }}>Nombre</label>
                    <input
                      className="land-input"
                      placeholder="Tu nombre"
                      value={form.nombre}
                      onChange={e => setForm(p => ({ ...p, nombre: e.target.value }))}
                      required
                    />
                  </div>
                  <div>
                    <label style={{ fontSize: 12, fontWeight: 500, color: 'var(--text-2)', display: 'block', marginBottom: 6 }}>Email (opcional)</label>
                    <input
                      className="land-input"
                      type="email"
                      placeholder="tu@email.com"
                      value={form.email}
                      onChange={e => setForm(p => ({ ...p, email: e.target.value }))}
                    />
                  </div>
                </div>
                <div>
                  <label style={{ fontSize: 12, fontWeight: 500, color: 'var(--text-2)', display: 'block', marginBottom: 6 }}>¿En qué puedo ayudarte?</label>
                  <textarea
                    className="land-input"
                    placeholder="Contame sobre tu empresa y qué necesitás..."
                    rows={4}
                    value={form.mensaje}
                    onChange={e => setForm(p => ({ ...p, mensaje: e.target.value }))}
                    required
                    style={{ resize: 'vertical' }}
                  />
                </div>
                <button type="submit" className="btn-green" style={{ padding: '13px 24px', fontSize: 15, borderRadius: 12, justifyContent: 'center' }}>
                  Enviar por WhatsApp →
                </button>
                <p style={{ fontSize: 11, color: 'var(--muted-2)', textAlign: 'center', marginTop: -4 }}>
                  Al enviar, se abre WhatsApp con tu mensaje listo para mandar.
                </p>
              </form>
            )}
          </R>
        </div>
      </section>

      {/* ── FOOTER ── */}
      <footer style={{ padding: '28px 24px', borderTop: '1px solid var(--border-soft)' }}>
        <div style={{ maxWidth: 900, margin: '0 auto', display: 'flex', flexWrap: 'wrap', alignItems: 'center', justifyContent: 'space-between', gap: 12 }}>
          <span style={{ fontWeight: 700, color: 'var(--accent)', fontSize: 15 }}>Cuadra</span>
          <div style={{ display: 'flex', gap: 20 }}>
            <Link to="/privacidad" className="footer-link">Política de privacidad</Link>
            <Link to="/terminos" className="footer-link">Términos y condiciones</Link>
          </div>
          <span style={{ fontSize: 11, color: 'var(--muted-2)' }}>© {new Date().getFullYear()} Julieta Arrazate</span>
        </div>
      </footer>
    </div>
  )
}
