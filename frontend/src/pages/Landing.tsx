import React, { useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { useThemeStore } from '@/store/theme'

const WA_NUMBER = '543774504024'
const WA_LINK   = `https://wa.me/${WA_NUMBER}?text=Hola%20Julieta%2C%20me%20interesa%20conocer%20m%C3%A1s%20sobre%20Cuadra`

// ── Logo SVG ────────────────────────────────────────────────────────────────
const Logo: React.FC<{ size?: number }> = ({ size = 28 }) => (
  <svg width={size} height={size} viewBox="0 0 32 32" aria-hidden="true">
    <rect width="32" height="32" rx="7" fill="currentColor"/>
    <path d="M9 16.5L13.5 21L23 11.5" stroke="white" strokeWidth="3.2" strokeLinecap="round" strokeLinejoin="round" fill="none"/>
  </svg>
)

// ── Hook scroll reveal ──────────────────────────────────────────────────────
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

const MOCKUP_ROWS = [
  { cliente: 'Cliente Norte SRL',  importe: '$124.500', ok: true  },
  { cliente: 'Constructora Sur',   importe: '$89.200',  ok: true  },
  { cliente: 'Distribuidora Este', importe: '$212.000', ok: false },
  { cliente: 'Servicios Centro',   importe: '$56.800',  ok: true  },
  { cliente: 'Comercial Oeste',    importe: '$98.400',  ok: true  },
]

const SECURITY = [
  { icon: '🔐', title: 'Autenticación JWT', desc: 'Tokens firmados con expiración de 8 horas. Logout invalida el token en el servidor.' },
  { icon: '🏢', title: 'Aislamiento multi-tenant', desc: 'Cada organización ve solo sus datos. Imposible que un usuario acceda a otra empresa.' },
  { icon: '🔑', title: 'Contraseñas hasheadas', desc: 'pbkdf2_sha256 con salt único por usuario. Nunca se almacenan en texto plano.' },
  { icon: '💾', title: 'Backups diarios', desc: 'Backup completo de la base cada noche a las 03:00, encriptado y enviado por email.' },
  { icon: '📋', title: 'Auditoría completa', desc: 'Cada acción queda registrada con usuario, fecha, IP y diff de los cambios.' },
  { icon: '🇦🇷', title: 'Ley 25.326 (PDPA)', desc: 'Política de privacidad y términos publicados. Respetamos la ley de protección de datos personales argentina.' },
]

const FAQ = [
  {
    q: '¿Cuánto cuesta usar Cuadra?',
    a: 'El precio se ajusta según la cantidad de empresas y usuarios. Coordiná un contacto por WhatsApp y te paso la propuesta con condiciones para tu caso.'
  },
  {
    q: '¿Qué bancos soporta el sistema?',
    a: 'Banco Macro, BBVA, Santander, Galicia, ICBC y un parser genérico para extractos en formato Excel. Si tu banco no está, lo agregamos en el onboarding.'
  },
  {
    q: '¿Cómo se instala?',
    a: 'No se instala. Abrís el link en el navegador y listo. Si querés tenerla como app en el celular, desde Chrome o Safari: menú → "Agregar a pantalla de inicio". Funciona como app nativa sin pasar por Play Store ni App Store.'
  },
  {
    q: '¿Mis datos están seguros?',
    a: 'Sí. Datos aislados por empresa, contraseñas hasheadas, autenticación JWT, backup diario encriptado y auditoría completa de cada acción. Conexiones por HTTPS en toda la app.'
  },
  {
    q: '¿Funciona sin conexión?',
    a: 'Las consultas básicas sí (lectura de cache). Para cargar planillas, registrar OPs o conciliar necesitás conexión. Las acciones que hagas offline se sincronizan cuando volvés.'
  },
  {
    q: '¿Se conecta con AFIP?',
    a: 'Por ahora no directamente. Lo que sí hace es exportar Excel en formato Banco Macro (que es el que usa el contador) y PDF de cierre mensual, todo listo para entregar.'
  },
  {
    q: '¿Cuántos usuarios puedo tener por empresa?',
    a: 'Sin límite. Cada empresa puede tener todos los empleados que necesite, con roles diferenciados (admin, operador, solo lectura).'
  },
  {
    q: '¿Puedo importar mis datos viejos?',
    a: 'Sí. Las planillas y extractos en Excel se importan directamente. Para datos en otros formatos, lo coordinamos en el onboarding inicial.'
  },
]

const COMPARISON = [
  { feature: 'Conciliar 100 movimientos', excel: '4–6 horas', cuadra: '2 minutos', winner: 'cuadra' },
  { feature: 'Errores humanos', excel: 'Frecuentes', cuadra: 'Mínimos (auto-detección)', winner: 'cuadra' },
  { feature: 'Acceso desde el celular', excel: 'No', cuadra: 'Sí, app PWA', winner: 'cuadra' },
  { feature: 'Multi-empresa', excel: 'Un archivo por empresa', cuadra: 'Todo en un sistema', winner: 'cuadra' },
  { feature: 'Backup automático', excel: 'Manual o ninguno', cuadra: 'Diario encriptado', winner: 'cuadra' },
  { feature: 'Auditoría de cambios', excel: 'Ninguna', cuadra: 'Log completo', winner: 'cuadra' },
  { feature: 'Trabajo en equipo', excel: 'Conflictos al editar', cuadra: 'En tiempo real', winner: 'cuadra' },
  { feature: 'Costo de archivos', excel: 'Crece con cada planilla', cuadra: 'Almacenamiento incluido', winner: 'cuadra' },
]

// ── Componente principal ─────────────────────────────────────────────────────
export const Landing: React.FC = () => {
  const { theme, toggle } = useThemeStore()
  const [form, setForm] = useState({ nombre: '', email: '', mensaje: '' })
  const [formSent, setFormSent] = useState(false)
  const [faqOpen, setFaqOpen] = useState<number | null>(0)

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
          0%   { transform: translateY(0); }
          100% { transform: translateY(-10px); }
        }
        .mock-float { animation: floatMock 3.5s ease-in-out infinite alternate; }

        @keyframes flowMove {
          0%   { transform: translateX(0); opacity: 0; }
          15%  { opacity: 1; }
          85%  { opacity: 1; }
          100% { transform: translateX(calc(100% + 16px)); opacity: 0; }
        }
        .flow-dot { animation: flowMove 3s ease-in-out infinite; }

        @keyframes rowCheck {
          0%, 100% { background: var(--card-2); }
          50%       { background: var(--accent-soft); }
        }
        .row-pulse { animation: rowCheck 2.5s ease-in-out infinite; }

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
        .dark .grad-border:hover { box-shadow: 0 12px 32px rgba(0,0,0,.4); }

        .land-nav {
          position: fixed; top: 0; left: 0; right: 0; z-index: 50;
          display: flex; align-items: center; justify-content: space-between;
          padding: 14px 20px;
          background: rgba(250,250,250,0.85);
          backdrop-filter: blur(16px);
          border-bottom: 1px solid var(--border);
          transition: background 0.2s;
        }
        .dark .land-nav { background: rgba(9,9,13,0.85); }

        .nav-logo {
          display: flex; align-items: center; gap: 8px;
          font-size: 17px; font-weight: 700; letter-spacing: -0.5px;
          color: var(--accent);
          text-decoration: none;
        }

        .nav-actions { display: flex; align-items: center; gap: 8px; }

        .nav-links { display: none; }
        @media (min-width: 720px) {
          .nav-links { display: flex; gap: 4px; }
        }

        .btn-green {
          display: inline-flex; align-items: center; gap: 6px;
          padding: 9px 18px; border-radius: 10px;
          background: var(--accent); color: #fff; font-weight: 600;
          font-size: 14px; line-height: 1;
          border: none; cursor: pointer;
          transition: background 0.15s, transform 0.1s;
          text-decoration: none;
          white-space: nowrap;
        }
        .dark .btn-green { color: #000; }
        .btn-green:hover { background: var(--accent-2); }
        .btn-green:active { transform: scale(0.97); }
        .btn-green.large {
          padding: 14px 28px; font-size: 15px; border-radius: 12px;
        }
        @media (min-width: 640px) {
          .btn-green.large { padding: 14px 32px; font-size: 16px; }
        }

        .btn-ghost {
          display: inline-flex; align-items: center; gap: 6px;
          padding: 8px 16px; border-radius: 10px;
          background: transparent; color: var(--muted);
          font-weight: 500; font-size: 13px;
          border: 1px solid var(--border); cursor: pointer;
          transition: all 0.15s;
          text-decoration: none;
          white-space: nowrap;
        }
        .btn-ghost:hover {
          background: var(--card); color: var(--text);
          border-color: var(--accent-line);
        }
        @media (min-width: 640px) {
          .btn-ghost { font-size: 14px; padding: 9px 18px; }
        }

        .theme-toggle {
          width: 34px; height: 34px;
          display: inline-flex; align-items: center; justify-content: center;
          border-radius: 10px;
          background: transparent;
          border: 1px solid var(--border);
          cursor: pointer; font-size: 15px;
          transition: background 0.15s, transform 0.1s;
          color: var(--text);
          flex-shrink: 0;
        }
        .theme-toggle:hover { background: var(--card); }
        .theme-toggle:active { transform: scale(0.92); }

        .land-input {
          width: 100%;
          background: var(--card-2); border: 1px solid var(--border); border-radius: 10px;
          padding: 12px 14px; color: var(--text); font-size: 14px;
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
          color: var(--accent); font-size: 11px; font-weight: 600;
          letter-spacing: 0.06em; text-transform: uppercase;
        }

        .wa-btn {
          display: inline-flex; align-items: center; gap: 10px;
          padding: 13px 24px; border-radius: 12px;
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

        .faq-item {
          border: 1px solid var(--border);
          border-radius: 12px;
          background: var(--card);
          overflow: hidden;
          transition: border-color 0.15s;
        }
        .faq-item:hover { border-color: var(--accent-line); }
        .faq-q {
          width: 100%;
          display: flex; align-items: center; justify-content: space-between;
          gap: 12px;
          padding: 18px 20px;
          background: transparent;
          border: none;
          cursor: pointer;
          text-align: left;
          font-size: 15px;
          font-weight: 600;
          color: var(--text);
          font-family: inherit;
        }
        .faq-q-icon {
          width: 24px; height: 24px;
          display: flex; align-items: center; justify-content: center;
          color: var(--accent); font-size: 20px;
          transition: transform 0.25s;
          flex-shrink: 0;
        }
        .faq-q-icon.open { transform: rotate(45deg); }
        .faq-a {
          padding: 0 20px 20px;
          font-size: 14px;
          line-height: 1.65;
          color: var(--muted);
          border-top: 1px solid var(--border-soft);
          padding-top: 16px;
        }

        .compare-table {
          width: 100%;
          border-collapse: collapse;
          background: var(--card);
          border-radius: 12px;
          overflow: hidden;
          border: 1px solid var(--border);
        }
        .compare-table th {
          padding: 16px 20px;
          font-size: 12px;
          font-weight: 600;
          text-transform: uppercase;
          letter-spacing: 0.06em;
          color: var(--muted-2);
          text-align: left;
          background: var(--card-2);
          border-bottom: 1px solid var(--border);
        }
        .compare-table th:last-child { color: var(--accent); }
        .compare-table td {
          padding: 14px 20px;
          font-size: 14px;
          color: var(--text-2);
          border-bottom: 1px solid var(--border-soft);
        }
        .compare-table tr:last-child td { border-bottom: none; }
        .compare-table td.feature { font-weight: 500; color: var(--text); }
        .compare-table td.excel { color: var(--muted); }
        .compare-table td.cuadra { color: var(--accent); font-weight: 600; }

        /* Hero responsive */
        .hero-section {
          position: relative;
          min-height: 100vh;
          display: flex; flex-direction: column;
          align-items: center; justify-content: center;
          padding: 90px 20px 56px;
          text-align: center;
          overflow: hidden;
        }
        .hero-title {
          font-size: clamp(36px, 9vw, 80px);
          font-weight: 800;
          line-height: 1.08;
          letter-spacing: -2px;
          max-width: 800px;
          margin-bottom: 22px;
        }
        .hero-sub {
          font-size: clamp(15px, 3.5vw, 20px);
          color: var(--muted);
          max-width: 520px;
          line-height: 1.65;
          margin-bottom: 36px;
          padding: 0 8px;
        }

        /* Mockup */
        .mockup-wrap {
          width: 100%; max-width: 560px;
          padding: 0 4px;
        }
        .mockup-card {
          border-radius: 18px;
          border: 1px solid var(--border);
          background: var(--card);
          box-shadow: var(--mock-shadow);
          overflow: hidden;
        }

        /* Stats grid */
        .stats-grid {
          display: grid;
          grid-template-columns: repeat(2, 1fr);
          gap: 1px;
          background: var(--border);
          border-radius: 16px;
          overflow: hidden;
          border: 1px solid var(--border);
        }
        @media (min-width: 720px) {
          .stats-grid { grid-template-columns: repeat(4, 1fr); }
        }

        /* Section padding mobile */
        .section { padding: 64px 20px; }
        @media (min-width: 720px) { .section { padding: 80px 24px; } }

        .section-title {
          font-size: clamp(26px, 6vw, 44px);
          font-weight: 800;
          letter-spacing: -1px;
          margin-bottom: 12px;
        }
      `}</style>

      {/* ── NAV ── */}
      <nav className="land-nav">
        <a href="#top" className="nav-logo">
          <span style={{ color: 'var(--accent)' }}><Logo size={24} /></span>
          Cuadra
        </a>

        <div className="nav-actions">
          <div className="nav-links">
            <a href="#features" className="btn-ghost" style={{ padding: '7px 12px', fontSize: 13 }}>
              Features
            </a>
            <a href="#seguridad" className="btn-ghost" style={{ padding: '7px 12px', fontSize: 13 }}>
              Seguridad
            </a>
            <a href="#faq" className="btn-ghost" style={{ padding: '7px 12px', fontSize: 13 }}>
              FAQ
            </a>
            <a href="#contacto" className="btn-ghost" style={{ padding: '7px 12px', fontSize: 13 }}>
              Contacto
            </a>
          </div>
          <button
            onClick={toggle}
            className="theme-toggle"
            title={theme === 'dark' ? 'Modo claro' : 'Modo oscuro'}
            aria-label="Cambiar tema"
          >
            {theme === 'dark' ? '☀' : '☾'}
          </button>
          <Link to="/login" className="btn-green">Ingresar</Link>
        </div>
      </nav>

      {/* ── HERO ── */}
      <section id="top" className="hero-section">
        <div className="glow-orb" style={{ position: 'absolute', top: '20%', left: '50%', transform: 'translateX(-50%)', width: 'min(700px, 90vw)', height: 400, borderRadius: '50%', background: 'radial-gradient(circle, var(--accent-soft) 0%, transparent 70%)', pointerEvents: 'none' }} />

        <div className="live-badge" style={{ display: 'inline-flex', alignItems: 'center', gap: 8, padding: '6px 14px', borderRadius: 999, background: 'var(--accent-soft)', border: '1px solid var(--accent-line)', color: 'var(--accent)', fontSize: 12, fontWeight: 600, marginBottom: 24 }}>
          <span style={{ width: 6, height: 6, borderRadius: '50%', background: 'var(--accent)', display: 'inline-block' }} />
          Sistema de gestión bancaria
        </div>

        <h1 className="hero-title">
          Los números<br />
          <span className="grad-text">cuadran solos.</span>
        </h1>

        <p className="hero-sub">
          Conciliación bancaria automática, gestión de caja, cheques y órdenes de pago.
          Para vos y tu equipo, desde el celular o la web.
        </p>

        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 10, justifyContent: 'center', marginBottom: 56 }}>
          <Link to="/login" className="btn-green large">
            Ingresar al sistema →
          </Link>
          <a href="#contacto" className="btn-ghost" style={{ padding: '14px 24px', fontSize: 15, borderRadius: 12 }}>
            Conocer más
          </a>
        </div>

        {/* Mockup */}
        <div className="mock-float mockup-wrap">
          <div className="mockup-card">
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '12px 16px', borderBottom: '1px solid var(--border)', background: 'var(--topbar-bg)' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <span style={{ color: 'var(--accent)' }}><Logo size={20} /></span>
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
                  <div key={i} className={i === 1 ? 'row-pulse' : ''} style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '8px 12px', borderRadius: 8, background: 'var(--card-2)', border: '1px solid var(--border-soft)' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 10, minWidth: 0 }}>
                      <div style={{ width: 6, height: 6, borderRadius: '50%', flexShrink: 0, background: r.ok ? 'var(--accent)' : '#F59E0B' }} />
                      <span style={{ fontSize: 12, fontWeight: 500, color: 'var(--text-2)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{r.cliente}</span>
                    </div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexShrink: 0 }}>
                      <span style={{ fontSize: 12, fontFamily: 'monospace', color: 'var(--muted)' }}>{r.importe}</span>
                      <span style={{ fontSize: 10, padding: '2px 7px', borderRadius: 4, background: r.ok ? 'var(--accent-soft)' : '#F59E0B18', color: r.ok ? 'var(--accent)' : '#F59E0B', fontWeight: 600 }}>
                        {r.ok ? 'OK' : 'REVISAR'}
                      </span>
                    </div>
                  </div>
                ))}
              </div>

              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: 12, paddingTop: 12, borderTop: '1px solid var(--border)' }}>
                <span style={{ fontSize: 11, color: 'var(--muted-2)' }}>4 conciliados · 1 revisar</span>
                <span style={{ fontSize: 11, color: 'var(--accent)', fontWeight: 600 }}>↓ Exportar Excel</span>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* ── STATS ── */}
      <section style={{ padding: '0 20px 64px' }}>
        <div style={{ maxWidth: 900, margin: '0 auto' }}>
          <div className="stats-grid">
            {STATS.map((s, i) => (
              <R key={s.label} delay={i * 60}>
                <div style={{ padding: '24px 18px', background: 'var(--bg)', textAlign: 'center' }}>
                  <div style={{ fontSize: 28, fontWeight: 800, color: 'var(--accent)', fontFamily: 'monospace', letterSpacing: '-1px' }}>{s.value}</div>
                  <div style={{ fontSize: 11, color: 'var(--muted-2)', marginTop: 4 }}>{s.label}</div>
                </div>
              </R>
            ))}
          </div>
        </div>
      </section>

      {/* ── FLOW DEMO ── */}
      <section className="section" style={{ background: 'var(--bg-2)', borderTop: '1px solid var(--border-soft)', borderBottom: '1px solid var(--border-soft)' }}>
        <div style={{ maxWidth: 900, margin: '0 auto' }}>
          <R>
            <div style={{ textAlign: 'center', marginBottom: 40 }}>
              <div className="pill" style={{ marginBottom: 16 }}>Cómo funciona</div>
              <h2 className="section-title">De la planilla al Excel del contador</h2>
              <p style={{ color: 'var(--muted)', fontSize: 15 }}>En 3 pasos, sin configuración compleja.</p>
            </div>
          </R>

          {/* Flujo animado */}
          <R delay={100}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 48, justifyContent: 'center', flexWrap: 'wrap' }}>
              {['📊 Extracto', '⚡ Conciliar', '📤 Excel'].map((label, i) => (
                <React.Fragment key={label}>
                  <div style={{
                    padding: '14px 22px', borderRadius: 12,
                    background: 'var(--card)', border: '1px solid var(--border)',
                    fontSize: 14, fontWeight: 600, color: 'var(--text)',
                    boxShadow: '0 2px 8px rgba(0,0,0,0.04)'
                  }}>
                    {label}
                  </div>
                  {i < 2 && (
                    <div style={{ position: 'relative', width: 50, height: 2, background: 'var(--border)', borderRadius: 2, overflow: 'visible' }}>
                      <div className="flow-dot" style={{
                        position: 'absolute', top: -3, left: -8,
                        width: 8, height: 8, borderRadius: '50%',
                        background: 'var(--accent)',
                        boxShadow: '0 0 8px var(--accent)',
                        animationDelay: `${i * 0.4}s`,
                      }} />
                    </div>
                  )}
                </React.Fragment>
              ))}
            </div>
          </R>

          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))', gap: 12 }}>
            {STEPS.map((s, i) => (
              <R key={s.n} delay={i * 100}>
                <div style={{ padding: '24px', borderRadius: 16, background: 'var(--card)', border: '1px solid var(--border)' }}>
                  <div style={{ fontSize: 48, fontWeight: 900, color: 'var(--accent-soft)', fontFamily: 'monospace', lineHeight: 1, marginBottom: 12, letterSpacing: '-2px' }}>{s.n}</div>
                  <div style={{ fontWeight: 700, fontSize: 16, marginBottom: 6, color: 'var(--text)' }}>{s.title}</div>
                  <div style={{ fontSize: 13, color: 'var(--muted)', lineHeight: 1.6 }}>{s.desc}</div>
                </div>
              </R>
            ))}
          </div>
        </div>
      </section>

      {/* ── FEATURES ── */}
      <section id="features" className="section">
        <div style={{ maxWidth: 1000, margin: '0 auto' }}>
          <R>
            <div style={{ textAlign: 'center', marginBottom: 48 }}>
              <div className="pill" style={{ marginBottom: 16 }}>Todo en un lugar</div>
              <h2 className="section-title">Diseñado para el trabajo diario</h2>
              <p style={{ color: 'var(--muted)', fontSize: 15, maxWidth: 460, margin: '0 auto' }}>
                Cada módulo construido para que sea rápido usarlo.
              </p>
            </div>
          </R>

          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(260px, 1fr))', gap: 14 }}>
            {FEATURES.map((f, i) => (
              <R key={f.title} delay={i * 60}>
                <div className="grad-border" style={{ padding: 22, height: '100%' }}>
                  <div style={{ fontSize: 26, marginBottom: 12 }}>{f.icon}</div>
                  <div style={{ fontWeight: 700, fontSize: 15, marginBottom: 6, color: 'var(--text)' }}>{f.title}</div>
                  <div style={{ fontSize: 13, color: 'var(--muted)', lineHeight: 1.6 }}>{f.desc}</div>
                </div>
              </R>
            ))}
          </div>
        </div>
      </section>

      {/* ── COMPARATIVA ── */}
      <section className="section" style={{ background: 'var(--bg-2)', borderTop: '1px solid var(--border-soft)', borderBottom: '1px solid var(--border-soft)' }}>
        <div style={{ maxWidth: 900, margin: '0 auto' }}>
          <R>
            <div style={{ textAlign: 'center', marginBottom: 40 }}>
              <div className="pill" style={{ marginBottom: 16 }}>Comparativa</div>
              <h2 className="section-title">Excel manual vs Cuadra</h2>
              <p style={{ color: 'var(--muted)', fontSize: 15 }}>
                Si hoy hacés todo en planillas, esto te interesa.
              </p>
            </div>
          </R>

          <R delay={100}>
            <div style={{ overflowX: 'auto', borderRadius: 12 }}>
              <table className="compare-table">
                <thead>
                  <tr>
                    <th>Tarea</th>
                    <th>Excel manual</th>
                    <th>Cuadra</th>
                  </tr>
                </thead>
                <tbody>
                  {COMPARISON.map(c => (
                    <tr key={c.feature}>
                      <td className="feature">{c.feature}</td>
                      <td className="excel">{c.excel}</td>
                      <td className="cuadra">✓ {c.cuadra}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </R>
        </div>
      </section>

      {/* ── SEGURIDAD ── */}
      <section id="seguridad" className="section">
        <div style={{ maxWidth: 1000, margin: '0 auto' }}>
          <R>
            <div style={{ textAlign: 'center', marginBottom: 48 }}>
              <div className="pill" style={{ marginBottom: 16 }}>Seguridad y privacidad</div>
              <h2 className="section-title">Construido para datos sensibles</h2>
              <p style={{ color: 'var(--muted)', fontSize: 15, maxWidth: 520, margin: '0 auto' }}>
                Tus datos contables y los de tus clientes están en una infraestructura pensada para eso desde el primer día.
              </p>
            </div>
          </R>

          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(260px, 1fr))', gap: 14 }}>
            {SECURITY.map((s, i) => (
              <R key={s.title} delay={i * 60}>
                <div className="grad-border" style={{ padding: 22, height: '100%' }}>
                  <div style={{ fontSize: 24, marginBottom: 10 }}>{s.icon}</div>
                  <div style={{ fontWeight: 700, fontSize: 14, marginBottom: 6, color: 'var(--text)' }}>{s.title}</div>
                  <div style={{ fontSize: 13, color: 'var(--muted)', lineHeight: 1.6 }}>{s.desc}</div>
                </div>
              </R>
            ))}
          </div>
        </div>
      </section>

      {/* ── PARA TU EQUIPO ── */}
      <section className="section" style={{ background: 'var(--bg-2)', borderTop: '1px solid var(--border-soft)', borderBottom: '1px solid var(--border-soft)' }}>
        <div style={{ maxWidth: 900, margin: '0 auto', display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: 40, alignItems: 'center' }}>
          <R>
            <div>
              <div className="pill" style={{ marginBottom: 18 }}>PWA instalable</div>
              <h2 style={{ fontSize: 'clamp(24px, 5vw, 36px)', fontWeight: 800, letterSpacing: '-1px', marginBottom: 14, lineHeight: 1.2 }}>
                Desde el celular<br />o la web
              </h2>
              <p style={{ color: 'var(--muted)', lineHeight: 1.65, marginBottom: 20, fontSize: 14 }}>
                Instalala como app sin pasar por App Store ni Play Store.
                Actualizaciones automáticas, sin reinstalar nunca.
              </p>
              <ul style={{ listStyle: 'none', padding: 0, margin: 0, display: 'flex', flexDirection: 'column', gap: 10 }}>
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
            <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
              {[
                { icon: '📱', title: 'Campo / cobranza', sub: 'Celular · OPs, fotos, caja', color: 'var(--accent)' },
                { icon: '💻', title: 'Contabilidad', sub: 'Web · extractos, conciliación, exports', color: '#5E6AD2' },
                { icon: '👁', title: 'Supervisión', sub: 'Web o celular · solo lectura', color: '#F59E0B' },
              ].map(r => (
                <div key={r.title} className="grad-border" style={{ display: 'flex', alignItems: 'center', gap: 14, padding: '14px 18px' }}>
                  <div style={{ width: 42, height: 42, borderRadius: 11, background: `color-mix(in srgb, ${r.color} 12%, transparent)`, display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 19, flexShrink: 0 }}>
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

      {/* ── FAQ ── */}
      <section id="faq" className="section">
        <div style={{ maxWidth: 720, margin: '0 auto' }}>
          <R>
            <div style={{ textAlign: 'center', marginBottom: 40 }}>
              <div className="pill" style={{ marginBottom: 16 }}>Preguntas frecuentes</div>
              <h2 className="section-title">Todo lo que querés saber</h2>
            </div>
          </R>

          <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
            {FAQ.map((item, i) => (
              <R key={i} delay={i * 40}>
                <div className="faq-item">
                  <button
                    className="faq-q"
                    onClick={() => setFaqOpen(faqOpen === i ? null : i)}
                    aria-expanded={faqOpen === i}
                  >
                    <span>{item.q}</span>
                    <span className={`faq-q-icon ${faqOpen === i ? 'open' : ''}`}>+</span>
                  </button>
                  {faqOpen === i && (
                    <div className="faq-a">{item.a}</div>
                  )}
                </div>
              </R>
            ))}
          </div>

          <R delay={300}>
            <div style={{ textAlign: 'center', marginTop: 36, fontSize: 14, color: 'var(--muted)' }}>
              ¿Tu pregunta no está acá?{' '}
              <a href="#contacto" style={{ color: 'var(--accent)', fontWeight: 600, textDecoration: 'none' }}>
                Escribime →
              </a>
            </div>
          </R>
        </div>
      </section>

      {/* ── PRICING ── */}
      <section className="section" style={{ background: 'var(--bg-2)', borderTop: '1px solid var(--border-soft)', borderBottom: '1px solid var(--border-soft)' }}>
        <div style={{ maxWidth: 720, margin: '0 auto' }}>
          <R>
            <div style={{ textAlign: 'center', marginBottom: 40 }}>
              <div className="pill" style={{ marginBottom: 16 }}>Precio</div>
              <h2 className="section-title">Una propuesta a tu medida</h2>
              <p style={{ color: 'var(--muted)', fontSize: 15, maxWidth: 480, margin: '0 auto' }}>
                El precio se ajusta a la cantidad de empresas, usuarios y volumen de operaciones.
                Sin sorpresas, sin contratos largos.
              </p>
            </div>
          </R>

          <R delay={100}>
            <div className="grad-border" style={{ padding: '32px 28px', textAlign: 'center' }}>
              <div style={{ display: 'inline-block', padding: '5px 12px', borderRadius: 999, background: 'var(--accent-soft)', border: '1px solid var(--accent-line)', color: 'var(--accent)', fontSize: 11, fontWeight: 600, marginBottom: 16, letterSpacing: '0.06em', textTransform: 'uppercase' }}>
                Onboarding incluido
              </div>
              <h3 style={{ fontSize: 22, fontWeight: 700, marginBottom: 8 }}>Plan empresa</h3>
              <p style={{ color: 'var(--muted)', fontSize: 14, marginBottom: 24, maxWidth: 380, marginLeft: 'auto', marginRight: 'auto' }}>
                Implementación, capacitación al equipo y soporte directo.
                Coordinamos los detalles según tu caso.
              </p>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(160px, 1fr))', gap: 14, marginBottom: 28, textAlign: 'left', maxWidth: 480, margin: '0 auto 28px' }}>
                {[
                  'Usuarios ilimitados', 'Empresas multiples', 'Backups diarios',
                  'Soporte WhatsApp', 'Actualizaciones', 'Capacitación inicial',
                ].map(item => (
                  <div key={item} style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 13, color: 'var(--text-2)' }}>
                    <span style={{ color: 'var(--accent)', fontWeight: 700 }}>✓</span>
                    {item}
                  </div>
                ))}
              </div>
              <a href="#contacto" className="btn-green large" style={{ textDecoration: 'none' }}>
                Consultar precio →
              </a>
            </div>
          </R>
        </div>
      </section>

      {/* ── CONTACTO ── */}
      <section id="contacto" className="section">
        <div style={{ maxWidth: 560, margin: '0 auto' }}>
          <R>
            <div style={{ textAlign: 'center', marginBottom: 36 }}>
              <div className="pill" style={{ marginBottom: 16 }}>Contacto</div>
              <h2 className="section-title">¿Querés implementar Cuadra?</h2>
              <p style={{ color: 'var(--muted)', fontSize: 15, lineHeight: 1.6 }}>
                Escribime por WhatsApp o completá el formulario.
              </p>
            </div>
          </R>

          <R delay={100}>
            <div style={{ textAlign: 'center', marginBottom: 28 }}>
              <a href={WA_LINK} target="_blank" rel="noopener noreferrer" className="wa-btn">
                <svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor">
                  <path d="M17.472 14.382c-.297-.149-1.758-.867-2.03-.967-.273-.099-.471-.148-.67.15-.197.297-.767.966-.94 1.164-.173.199-.347.223-.644.075-.297-.15-1.255-.463-2.39-1.475-.883-.788-1.48-1.761-1.653-2.059-.173-.297-.018-.458.13-.606.134-.133.298-.347.446-.52.149-.174.198-.298.298-.497.099-.198.05-.371-.025-.52-.075-.149-.669-1.612-.916-2.207-.242-.579-.487-.5-.669-.51-.173-.008-.371-.01-.57-.01-.198 0-.52.074-.792.372-.272.297-1.04 1.016-1.04 2.479 0 1.462 1.065 2.875 1.213 3.074.149.198 2.096 3.2 5.077 4.487.709.306 1.262.489 1.694.625.712.227 1.36.195 1.871.118.571-.085 1.758-.719 2.006-1.413.248-.694.248-1.289.173-1.413-.074-.124-.272-.198-.57-.347m-5.421 7.403h-.004a9.87 9.87 0 01-5.031-1.378l-.361-.214-3.741.982.998-3.648-.235-.374a9.86 9.86 0 01-1.51-5.26c.001-5.45 4.436-9.884 9.888-9.884 2.64 0 5.122 1.03 6.988 2.898a9.825 9.825 0 012.893 6.994c-.003 5.45-4.437 9.884-9.885 9.884m8.413-18.297A11.815 11.815 0 0012.05 0C5.495 0 .16 5.335.157 11.892c0 2.096.547 4.142 1.588 5.945L.057 24l6.305-1.654a11.882 11.882 0 005.683 1.448h.005c6.554 0 11.89-5.335 11.893-11.893a11.821 11.821 0 00-3.48-8.413z"/>
                </svg>
                Escribir por WhatsApp
              </a>
            </div>

            <div style={{ display: 'flex', alignItems: 'center', gap: 16, marginBottom: 24 }}>
              <div style={{ flex: 1, height: 1, background: 'var(--border)' }} />
              <span style={{ fontSize: 12, color: 'var(--muted-2)' }}>o por formulario</span>
              <div style={{ flex: 1, height: 1, background: 'var(--border)' }} />
            </div>

            {formSent ? (
              <div style={{ textAlign: 'center', padding: '28px 24px', borderRadius: 16, background: 'var(--accent-soft)', border: '1px solid var(--accent-line)' }}>
                <div style={{ fontSize: 32, marginBottom: 10 }}>✅</div>
                <div style={{ fontWeight: 700, color: 'var(--accent)', marginBottom: 6 }}>¡Mensaje enviado!</div>
                <div style={{ fontSize: 13, color: 'var(--muted)' }}>Te abrió WhatsApp con tu mensaje. Te respondo a la brevedad.</div>
              </div>
            ) : (
              <form onSubmit={handleContact} style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: 12 }}>
                  <div>
                    <label style={{ fontSize: 12, fontWeight: 500, color: 'var(--text-2)', display: 'block', marginBottom: 6 }}>Nombre</label>
                    <input className="land-input" placeholder="Tu nombre" value={form.nombre} onChange={e => setForm(p => ({ ...p, nombre: e.target.value }))} required />
                  </div>
                  <div>
                    <label style={{ fontSize: 12, fontWeight: 500, color: 'var(--text-2)', display: 'block', marginBottom: 6 }}>Email (opcional)</label>
                    <input className="land-input" type="email" placeholder="tu@email.com" value={form.email} onChange={e => setForm(p => ({ ...p, email: e.target.value }))} />
                  </div>
                </div>
                <div>
                  <label style={{ fontSize: 12, fontWeight: 500, color: 'var(--text-2)', display: 'block', marginBottom: 6 }}>¿En qué puedo ayudarte?</label>
                  <textarea className="land-input" placeholder="Contame sobre tu empresa..." rows={4} value={form.mensaje} onChange={e => setForm(p => ({ ...p, mensaje: e.target.value }))} required style={{ resize: 'vertical' }} />
                </div>
                <button type="submit" className="btn-green" style={{ padding: '13px 24px', fontSize: 15, borderRadius: 12, justifyContent: 'center' }}>
                  Enviar por WhatsApp →
                </button>
                <p style={{ fontSize: 11, color: 'var(--muted-2)', textAlign: 'center', marginTop: -2 }}>
                  Al enviar, se abre WhatsApp con tu mensaje listo.
                </p>
              </form>
            )}
          </R>
        </div>
      </section>

      {/* ── FOOTER ── */}
      <footer style={{ padding: '24px 20px', borderTop: '1px solid var(--border-soft)' }}>
        <div style={{ maxWidth: 900, margin: '0 auto', display: 'flex', flexWrap: 'wrap', alignItems: 'center', justifyContent: 'space-between', gap: 12 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <span style={{ color: 'var(--accent)' }}><Logo size={20} /></span>
            <span style={{ fontWeight: 700, color: 'var(--accent)', fontSize: 14 }}>Cuadra</span>
          </div>
          <div style={{ display: 'flex', gap: 18, flexWrap: 'wrap' }}>
            <Link to="/privacidad" className="footer-link">Privacidad</Link>
            <Link to="/terminos" className="footer-link">Términos</Link>
            <a href={WA_LINK} target="_blank" rel="noopener noreferrer" className="footer-link">WhatsApp</a>
          </div>
          <span style={{ fontSize: 11, color: 'var(--muted-2)' }}>© {new Date().getFullYear()} Julieta Arrazate</span>
        </div>
      </footer>
    </div>
  )
}
