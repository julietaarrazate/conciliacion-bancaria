import React, { useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'

// ── Constantes de marca ──────────────────────────────────────────────────────
const WA_NUMBER = '543774504024'
const WA_LINK   = `https://wa.me/${WA_NUMBER}?text=Hola%20Julieta%2C%20me%20interesa%20conocer%20m%C3%A1s%20sobre%20Cuadra`

// ── Scroll reveal hook ───────────────────────────────────────────────────────
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

// ── Datos ────────────────────────────────────────────────────────────────────
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

// ── Componente principal ─────────────────────────────────────────────────────
export const Landing: React.FC = () => {
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

      {/* ── Estilos ── */}
      <style>{`
        .landing-root {
          min-height: 100vh;
          background: #09090D;
          color: #E4E4E7;
          font-family: 'Inter', -apple-system, sans-serif;
          -webkit-font-smoothing: antialiased;
          overflow-x: hidden;
        }

        /* Scroll reveal */
        .land-reveal {
          opacity: 0;
          transform: translateY(20px);
          transition: opacity 0.65s ease calc(var(--d, 0ms)), transform 0.65s ease calc(var(--d, 0ms));
        }
        .land-reveal[data-visible="true"] {
          opacity: 1;
          transform: none;
        }

        /* Gradient text */
        .grad-text {
          background: linear-gradient(135deg, #4ADE80 0%, #22C55E 50%, #86EFAC 100%);
          -webkit-background-clip: text;
          -webkit-text-fill-color: transparent;
          background-clip: text;
        }

        /* Glow pulsante del hero */
        @keyframes glowPulse {
          0%, 100% { opacity: 0.3; transform: scale(1); }
          50%       { opacity: 0.6; transform: scale(1.05); }
        }
        .glow-orb { animation: glowPulse 5s ease-in-out infinite; }

        /* Mockup flotante */
        @keyframes floatMock {
          0%   { transform: translateY(0) rotateX(2deg); }
          100% { transform: translateY(-10px) rotateX(0deg); }
        }
        .mock-float { animation: floatMock 3.5s ease-in-out infinite alternate; }

        /* Borde gradiente en cards */
        .grad-border {
          position: relative;
          background: #13131A;
          border-radius: 16px;
        }
        .grad-border::before {
          content: '';
          position: absolute;
          inset: -1px;
          border-radius: 17px;
          background: linear-gradient(135deg, #22C55E22, #1E1E2A, #22C55E11);
          z-index: -1;
        }
        .grad-border:hover::before {
          background: linear-gradient(135deg, #22C55E55, #1E1E2A, #22C55E33);
          transition: background 0.3s ease;
        }

        /* Nav */
        .land-nav {
          position: fixed; top: 0; left: 0; right: 0; z-index: 50;
          display: flex; align-items: center; justify-content: space-between;
          padding: 16px 24px;
          background: rgba(9,9,13,0.85);
          backdrop-filter: blur(16px);
          border-bottom: 1px solid #1E1E26;
        }

        /* Botones */
        .btn-green {
          display: inline-flex; align-items: center; gap: 8px;
          padding: 10px 22px; border-radius: 10px;
          background: #22C55E; color: #000; font-weight: 600; font-size: 14px;
          border: none; cursor: pointer;
          transition: background 0.15s, transform 0.1s;
          text-decoration: none;
        }
        .btn-green:hover { background: #4ADE80; }
        .btn-green:active { transform: scale(0.97); }
        .btn-green.large { padding: 14px 32px; font-size: 16px; border-radius: 12px; }

        .btn-ghost {
          display: inline-flex; align-items: center; gap: 8px;
          padding: 10px 22px; border-radius: 10px;
          background: transparent; color: #A1A1AA; font-weight: 500; font-size: 14px;
          border: 1px solid #2A2A35; cursor: pointer;
          transition: all 0.15s;
          text-decoration: none;
        }
        .btn-ghost:hover { background: #16161C; color: #E4E4E7; border-color: #3A3A48; }

        /* Input */
        .land-input {
          width: 100%;
          background: #111118; border: 1px solid #2A2A35; border-radius: 10px;
          padding: 12px 16px; color: #E4E4E7; font-size: 14px;
          outline: none; transition: border 0.15s;
          font-family: inherit;
        }
        .land-input:focus { border-color: #22C55E66; box-shadow: 0 0 0 3px #22C55E11; }
        .land-input::placeholder { color: #52525B; }

        /* Badge */
        @keyframes badgeFade {
          0%, 100% { opacity: 1; }
          50%       { opacity: 0.6; }
        }
        .live-badge { animation: badgeFade 2.5s ease-in-out infinite; }

        /* WA hover */
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
      `}</style>

      {/* ── NAV ── */}
      <nav className="land-nav">
        <span style={{ fontSize: 18, fontWeight: 700, letterSpacing: '-0.5px', color: '#22C55E' }}>
          Cuadra
        </span>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <a href="#features" className="btn-ghost" style={{ padding: '7px 14px', display: 'none' }}>
            Features
          </a>
          <a href="#contacto" className="btn-ghost" style={{ padding: '7px 14px' }}>
            Contacto
          </a>
          <Link to="/login" className="btn-green">
            Ingresar →
          </Link>
        </div>
      </nav>

      {/* ── HERO ── */}
      <section style={{ position: 'relative', minHeight: '100vh', display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', padding: '96px 24px 64px', textAlign: 'center', overflow: 'hidden' }}>

        {/* Orbes de fondo */}
        <div className="glow-orb" style={{ position: 'absolute', top: '20%', left: '50%', transform: 'translateX(-50%)', width: 700, height: 400, borderRadius: '50%', background: 'radial-gradient(circle, #22C55E18 0%, transparent 70%)', pointerEvents: 'none' }} />
        <div style={{ position: 'absolute', top: '30%', left: '25%', width: 300, height: 300, borderRadius: '50%', background: 'radial-gradient(circle, #5E6AD218 0%, transparent 70%)', pointerEvents: 'none', opacity: 0.5 }} />

        {/* Badge live */}
        <div className="live-badge" style={{ display: 'inline-flex', alignItems: 'center', gap: 8, padding: '6px 14px', borderRadius: 999, background: '#22C55E12', border: '1px solid #22C55E30', color: '#22C55E', fontSize: 12, fontWeight: 600, marginBottom: 28 }}>
          <span style={{ width: 6, height: 6, borderRadius: '50%', background: '#22C55E', display: 'inline-block' }} />
          Sistema de conciliación bancaria · en producción
        </div>

        {/* Headline */}
        <h1 style={{ fontSize: 'clamp(40px, 7vw, 80px)', fontWeight: 800, lineHeight: 1.08, letterSpacing: '-2px', maxWidth: 800, marginBottom: 24 }}>
          Los números<br />
          <span className="grad-text">cuadran solos.</span>
        </h1>

        <p style={{ fontSize: 'clamp(16px, 2.5vw, 20px)', color: '#71717A', maxWidth: 520, lineHeight: 1.65, marginBottom: 40 }}>
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
          <div style={{ borderRadius: 20, border: '1px solid #1E1E26', background: '#13131A', boxShadow: '0 32px 80px rgba(0,0,0,0.6), 0 0 0 1px #22C55E18', overflow: 'hidden' }}>

            {/* Topbar mockup */}
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '12px 16px', borderBottom: '1px solid #1E1E26', background: '#0F0F16' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <div style={{ width: 28, height: 28, borderRadius: 8, background: '#22C55E18', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 14 }}>⚡</div>
                <span style={{ fontSize: 13, fontWeight: 600, color: '#22C55E' }}>Cuadra</span>
              </div>
              <div style={{ display: 'flex', gap: 6 }}>
                {['#FF5F57','#FFBD2E','#28C840'].map(c => <div key={c} style={{ width: 10, height: 10, borderRadius: '50%', background: c }} />)}
              </div>
            </div>

            {/* Contenido mockup */}
            <div style={{ padding: 16 }}>
              {/* Stats row */}
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 8, marginBottom: 16 }}>
                {[
                  { label: 'Conciliados', val: '47', color: '#22C55E' },
                  { label: 'Pendientes', val: '3', color: '#F59E0B' },
                  { label: 'Caja', val: '$482k', color: '#5E6AD2' },
                ].map(s => (
                  <div key={s.label} style={{ background: '#0F0F16', borderRadius: 10, padding: '10px 12px', border: '1px solid #1E1E26' }}>
                    <div style={{ fontSize: 18, fontWeight: 700, color: s.color, fontFamily: 'monospace' }}>{s.val}</div>
                    <div style={{ fontSize: 10, color: '#52525B', marginTop: 2 }}>{s.label}</div>
                  </div>
                ))}
              </div>

              {/* Filas conciliación */}
              <div style={{ fontSize: 11, color: '#52525B', fontWeight: 600, marginBottom: 8, textTransform: 'uppercase', letterSpacing: '0.08em' }}>
                Planilla Mayo 2025
              </div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                {[
                  { cliente: 'Green SRL', importe: '$124.500', ok: true },
                  { cliente: 'Tucu Inversiones', importe: '$89.200', ok: true },
                  { cliente: 'David Prop.', importe: '$212.000', ok: false },
                  { cliente: 'Innova SA', importe: '$56.800', ok: true },
                  { cliente: 'Gwinn Group', importe: '$98.400', ok: true },
                ].map((r, i) => (
                  <div key={i} style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '8px 12px', borderRadius: 8, background: '#0F0F16', border: '1px solid #1A1A24' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                      <div style={{ width: 6, height: 6, borderRadius: '50%', flexShrink: 0, background: r.ok ? '#22C55E' : '#F59E0B', boxShadow: r.ok ? '0 0 6px #22C55E66' : '0 0 6px #F59E0B66' }} />
                      <span style={{ fontSize: 12, fontWeight: 500, color: '#D4D4D8' }}>{r.cliente}</span>
                    </div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                      <span style={{ fontSize: 12, fontFamily: 'monospace', color: '#71717A' }}>{r.importe}</span>
                      <span style={{ fontSize: 10, padding: '2px 7px', borderRadius: 4, background: r.ok ? '#22C55E18' : '#F59E0B18', color: r.ok ? '#22C55E' : '#F59E0B', fontWeight: 600 }}>
                        {r.ok ? 'OK' : 'REVISAR'}
                      </span>
                    </div>
                  </div>
                ))}
              </div>

              {/* Footer mockup */}
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: 12, paddingTop: 12, borderTop: '1px solid #1E1E26' }}>
                <span style={{ fontSize: 11, color: '#52525B' }}>4 conciliados · 1 para revisar</span>
                <div style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 11, color: '#22C55E', fontWeight: 600, cursor: 'pointer' }}>
                  ↓ Exportar Excel
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* ── STATS ── */}
      <section style={{ padding: '0 24px 80px' }}>
        <div style={{ maxWidth: 900, margin: '0 auto', display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: 1, background: '#1A1A24', borderRadius: 16, overflow: 'hidden', border: '1px solid #1E1E26' }}>
          {STATS.map((s, i) => (
            <R key={s.label} delay={i * 60}>
              <div style={{ padding: '28px 24px', background: '#09090D', textAlign: 'center' }}>
                <div style={{ fontSize: 32, fontWeight: 800, color: '#22C55E', fontFamily: 'monospace', letterSpacing: '-1px' }}>{s.value}</div>
                <div style={{ fontSize: 12, color: '#52525B', marginTop: 4 }}>{s.label}</div>
              </div>
            </R>
          ))}
        </div>
      </section>

      {/* ── FEATURES ── */}
      <section id="features" style={{ padding: '80px 24px' }}>
        <div style={{ maxWidth: 1000, margin: '0 auto' }}>
          <R className="">
            <div style={{ textAlign: 'center', marginBottom: 56 }}>
              <div style={{ display: 'inline-block', padding: '5px 14px', borderRadius: 999, background: '#22C55E12', border: '1px solid #22C55E25', color: '#22C55E', fontSize: 12, fontWeight: 600, marginBottom: 16, letterSpacing: '0.06em', textTransform: 'uppercase' }}>
                Todo en un lugar
              </div>
              <h2 style={{ fontSize: 'clamp(28px, 4vw, 44px)', fontWeight: 800, letterSpacing: '-1px', marginBottom: 12 }}>
                Diseñado para el trabajo diario
              </h2>
              <p style={{ color: '#71717A', fontSize: 16, maxWidth: 460, margin: '0 auto' }}>
                Cada módulo construido para que sea rápido usarlo, no para que sea lindo explicarlo.
              </p>
            </div>
          </R>

          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))', gap: 16 }}>
            {FEATURES.map((f, i) => (
              <R key={f.title} delay={i * 70}>
                <div className="grad-border" style={{ padding: 24, height: '100%', cursor: 'default', transition: 'transform 0.2s' }}
                     onMouseEnter={e => (e.currentTarget.style.transform = 'translateY(-3px)')}
                     onMouseLeave={e => (e.currentTarget.style.transform = '')}>
                  <div style={{ fontSize: 28, marginBottom: 14 }}>{f.icon}</div>
                  <div style={{ fontWeight: 700, fontSize: 15, marginBottom: 8, color: '#E4E4E7' }}>{f.title}</div>
                  <div style={{ fontSize: 13, color: '#71717A', lineHeight: 1.65 }}>{f.desc}</div>
                </div>
              </R>
            ))}
          </div>
        </div>
      </section>

      {/* ── CÓMO FUNCIONA ── */}
      <section style={{ padding: '80px 24px', background: '#0D0D13', borderTop: '1px solid #1A1A24', borderBottom: '1px solid #1A1A24' }}>
        <div style={{ maxWidth: 900, margin: '0 auto' }}>
          <R>
            <div style={{ textAlign: 'center', marginBottom: 56 }}>
              <div style={{ display: 'inline-block', padding: '5px 14px', borderRadius: 999, background: '#22C55E12', border: '1px solid #22C55E25', color: '#22C55E', fontSize: 12, fontWeight: 600, marginBottom: 16, letterSpacing: '0.06em', textTransform: 'uppercase' }}>
                Simple por diseño
              </div>
              <h2 style={{ fontSize: 'clamp(28px, 4vw, 44px)', fontWeight: 800, letterSpacing: '-1px' }}>
                De la planilla al Excel del contador
              </h2>
            </div>
          </R>

          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))', gap: 8 }}>
            {STEPS.map((s, i) => (
              <R key={s.n} delay={i * 100}>
                <div style={{ padding: '28px 24px', borderRadius: 16, background: '#13131A', border: '1px solid #1E1E26', position: 'relative', overflow: 'hidden' }}>
                  <div style={{ fontSize: 56, fontWeight: 900, color: '#22C55E10', fontFamily: 'monospace', lineHeight: 1, marginBottom: 12, letterSpacing: '-2px' }}>{s.n}</div>
                  <div style={{ fontWeight: 700, fontSize: 16, marginBottom: 8, color: '#E4E4E7' }}>{s.title}</div>
                  <div style={{ fontSize: 13, color: '#71717A', lineHeight: 1.65 }}>{s.desc}</div>
                  {i < STEPS.length - 1 && (
                    <div style={{ position: 'absolute', top: '50%', right: -16, width: 32, height: 1, background: 'linear-gradient(to right, #22C55E40, transparent)', display: 'none' }} />
                  )}
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
              <div style={{ display: 'inline-block', padding: '5px 14px', borderRadius: 999, background: '#22C55E12', border: '1px solid #22C55E25', color: '#22C55E', fontSize: 12, fontWeight: 600, marginBottom: 20, letterSpacing: '0.06em', textTransform: 'uppercase' }}>
                PWA instalable
              </div>
              <h2 style={{ fontSize: 'clamp(26px, 3.5vw, 38px)', fontWeight: 800, letterSpacing: '-1px', marginBottom: 16, lineHeight: 1.2 }}>
                Desde el celular<br />o la web
              </h2>
              <p style={{ color: '#71717A', lineHeight: 1.7, marginBottom: 24, fontSize: 15 }}>
                Instalala como app sin pasar por el App Store ni el Play Store.
                Actualizaciones automáticas — sin reinstalar nunca.
              </p>
              <ul style={{ listStyle: 'none', padding: 0, margin: 0, display: 'flex', flexDirection: 'column', gap: 12 }}>
                {['Android e iPhone', 'Sin instalación desde tiendas', 'Actualizaciones silenciosas', 'Notificaciones push'].map(item => (
                  <li key={item} style={{ display: 'flex', alignItems: 'center', gap: 10, fontSize: 14, color: '#A1A1AA' }}>
                    <span style={{ color: '#22C55E', fontWeight: 700, fontSize: 16 }}>✓</span>
                    {item}
                  </li>
                ))}
              </ul>
            </div>
          </R>

          <R delay={150}>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
              {[
                { icon: '📱', title: 'Campo / cobranza', sub: 'Celular · OPs, fotos, caja', color: '#22C55E' },
                { icon: '💻', title: 'Contabilidad', sub: 'Web · extractos, conciliación, exports', color: '#5E6AD2' },
                { icon: '👁', title: 'Supervisión', sub: 'Web o celular · solo lectura', color: '#F59E0B' },
              ].map(r => (
                <div key={r.title} className="grad-border" style={{ display: 'flex', alignItems: 'center', gap: 14, padding: '16px 20px' }}>
                  <div style={{ width: 44, height: 44, borderRadius: 12, background: `${r.color}15`, display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 20, flexShrink: 0 }}>
                    {r.icon}
                  </div>
                  <div>
                    <div style={{ fontWeight: 600, fontSize: 14, color: '#E4E4E7' }}>{r.title}</div>
                    <div style={{ fontSize: 12, color: '#52525B', marginTop: 2 }}>{r.sub}</div>
                  </div>
                </div>
              ))}
            </div>
          </R>
        </div>
      </section>

      {/* ── CONTACTO ── */}
      <section id="contacto" style={{ padding: '80px 24px', background: '#0D0D13', borderTop: '1px solid #1A1A24' }}>
        <div style={{ maxWidth: 560, margin: '0 auto' }}>
          <R>
            <div style={{ textAlign: 'center', marginBottom: 40 }}>
              <div style={{ display: 'inline-block', padding: '5px 14px', borderRadius: 999, background: '#22C55E12', border: '1px solid #22C55E25', color: '#22C55E', fontSize: 12, fontWeight: 600, marginBottom: 16, letterSpacing: '0.06em', textTransform: 'uppercase' }}>
                Contacto
              </div>
              <h2 style={{ fontSize: 'clamp(26px, 3.5vw, 38px)', fontWeight: 800, letterSpacing: '-1px', marginBottom: 12 }}>
                ¿Querés implementar Cuadra?
              </h2>
              <p style={{ color: '#71717A', fontSize: 15, lineHeight: 1.65 }}>
                Escribime directo por WhatsApp o completá el formulario y te contacto a la brevedad.
              </p>
            </div>
          </R>

          <R delay={100}>
            {/* WhatsApp directo */}
            <div style={{ textAlign: 'center', marginBottom: 32 }}>
              <a href={WA_LINK} target="_blank" rel="noopener noreferrer" className="wa-btn">
                <svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor">
                  <path d="M17.472 14.382c-.297-.149-1.758-.867-2.03-.967-.273-.099-.471-.148-.67.15-.197.297-.767.966-.94 1.164-.173.199-.347.223-.644.075-.297-.15-1.255-.463-2.39-1.475-.883-.788-1.48-1.761-1.653-2.059-.173-.297-.018-.458.13-.606.134-.133.298-.347.446-.52.149-.174.198-.298.298-.497.099-.198.05-.371-.025-.52-.075-.149-.669-1.612-.916-2.207-.242-.579-.487-.5-.669-.51-.173-.008-.371-.01-.57-.01-.198 0-.52.074-.792.372-.272.297-1.04 1.016-1.04 2.479 0 1.462 1.065 2.875 1.213 3.074.149.198 2.096 3.2 5.077 4.487.709.306 1.262.489 1.694.625.712.227 1.36.195 1.871.118.571-.085 1.758-.719 2.006-1.413.248-.694.248-1.289.173-1.413-.074-.124-.272-.198-.57-.347m-5.421 7.403h-.004a9.87 9.87 0 01-5.031-1.378l-.361-.214-3.741.982.998-3.648-.235-.374a9.86 9.86 0 01-1.51-5.26c.001-5.45 4.436-9.884 9.888-9.884 2.64 0 5.122 1.03 6.988 2.898a9.825 9.825 0 012.893 6.994c-.003 5.45-4.437 9.884-9.885 9.884m8.413-18.297A11.815 11.815 0 0012.05 0C5.495 0 .16 5.335.157 11.892c0 2.096.547 4.142 1.588 5.945L.057 24l6.305-1.654a11.882 11.882 0 005.683 1.448h.005c6.554 0 11.89-5.335 11.893-11.893a11.821 11.821 0 00-3.48-8.413z"/>
                </svg>
                Escribir por WhatsApp
              </a>
            </div>

            {/* Separador */}
            <div style={{ display: 'flex', alignItems: 'center', gap: 16, marginBottom: 28 }}>
              <div style={{ flex: 1, height: 1, background: '#1E1E26' }} />
              <span style={{ fontSize: 12, color: '#52525B' }}>o completá el formulario</span>
              <div style={{ flex: 1, height: 1, background: '#1E1E26' }} />
            </div>

            {/* Formulario */}
            {formSent ? (
              <div style={{ textAlign: 'center', padding: '32px 24px', borderRadius: 16, background: '#22C55E10', border: '1px solid #22C55E30' }}>
                <div style={{ fontSize: 32, marginBottom: 12 }}>✅</div>
                <div style={{ fontWeight: 700, color: '#22C55E', marginBottom: 8 }}>¡Mensaje enviado!</div>
                <div style={{ fontSize: 13, color: '#71717A' }}>Te abrió WhatsApp con tu mensaje. Respondemos a la brevedad.</div>
              </div>
            ) : (
              <form onSubmit={handleContact} style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
                  <div>
                    <label style={{ fontSize: 12, fontWeight: 500, color: '#A1A1AA', display: 'block', marginBottom: 6 }}>Nombre</label>
                    <input
                      className="land-input"
                      placeholder="Tu nombre"
                      value={form.nombre}
                      onChange={e => setForm(p => ({ ...p, nombre: e.target.value }))}
                      required
                    />
                  </div>
                  <div>
                    <label style={{ fontSize: 12, fontWeight: 500, color: '#A1A1AA', display: 'block', marginBottom: 6 }}>Email (opcional)</label>
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
                  <label style={{ fontSize: 12, fontWeight: 500, color: '#A1A1AA', display: 'block', marginBottom: 6 }}>¿En qué puedo ayudarte?</label>
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
                <p style={{ fontSize: 11, color: '#52525B', textAlign: 'center', marginTop: -4 }}>
                  Al enviar, se abre WhatsApp con tu mensaje listo para mandar.
                </p>
              </form>
            )}
          </R>
        </div>
      </section>

      {/* ── FOOTER ── */}
      <footer style={{ padding: '28px 24px', borderTop: '1px solid #1A1A24' }}>
        <div style={{ maxWidth: 900, margin: '0 auto', display: 'flex', flexWrap: 'wrap', alignItems: 'center', justifyContent: 'space-between', gap: 12 }}>
          <span style={{ fontWeight: 700, color: '#22C55E', fontSize: 15 }}>Cuadra</span>
          <div style={{ display: 'flex', gap: 20 }}>
            <Link to="/privacidad" style={{ fontSize: 12, color: '#52525B', textDecoration: 'none' }}
              onMouseEnter={e => (e.currentTarget.style.color = '#A1A1AA')}
              onMouseLeave={e => (e.currentTarget.style.color = '#52525B')}>
              Política de privacidad
            </Link>
            <Link to="/terminos" style={{ fontSize: 12, color: '#52525B', textDecoration: 'none' }}
              onMouseEnter={e => (e.currentTarget.style.color = '#A1A1AA')}
              onMouseLeave={e => (e.currentTarget.style.color = '#52525B')}>
              Términos y condiciones
            </Link>
          </div>
          <span style={{ fontSize: 11, color: '#3A3A48' }}>© {new Date().getFullYear()} Julieta Arrazate</span>
        </div>
      </footer>
    </div>
  )
}
