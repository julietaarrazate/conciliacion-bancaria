import React, { useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { useThemeStore } from '@/store/theme'

const WA_NUMBER = '543774504024'
const WA_LINK   = `https://wa.me/${WA_NUMBER}?text=Hola%20Julieta%2C%20me%20interesa%20conocer%20m%C3%A1s%20sobre%20Cuadra`

const Logo: React.FC<{ size?: number }> = ({ size = 28 }) => (
  <svg width={size} height={size} viewBox="0 0 32 32" aria-hidden="true">
    <rect width="32" height="32" rx="7" fill="currentColor"/>
    <path d="M9 16.5L13.5 21L23 11.5" stroke="white" strokeWidth="3.2" strokeLinecap="round" strokeLinejoin="round" fill="none"/>
  </svg>
)

function useReveal() {
  const ref = useRef<HTMLDivElement>(null)
  useEffect(() => {
    const el = ref.current
    if (!el) return
    const show = () => { el.dataset.visible = 'true' }
    const rect = el.getBoundingClientRect()
    if (rect.top < window.innerHeight + 40) { show(); return }
    const obs = new IntersectionObserver(
      ([e]) => { if (e.isIntersecting) { show(); obs.disconnect() } },
      { threshold: 0, rootMargin: '0px 0px -20px 0px' }
    )
    obs.observe(el)
    const t = setTimeout(show, 2500)
    return () => { obs.disconnect(); clearTimeout(t) }
  }, [])
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

// ── StatCounter ───────────────────────────────────────────────────────────────
const StatCounter: React.FC<{
  numericEnd: number; prefix: string; suffix: string; label: string; delay?: number
}> = ({ numericEnd, prefix, suffix, label, delay = 0 }) => {
  const ref = useRef<HTMLDivElement>(null)
  const [count, setCount] = useState(0)
  const animDone = useRef(false)
  useEffect(() => {
    if (numericEnd === 0) return
    const el = ref.current; if (!el) return
    const run = () => {
      if (animDone.current) return
      animDone.current = true
      setTimeout(() => {
        const dur = numericEnd >= 20 ? 1400 : 900
        const t0 = performance.now()
        const tick = (now: number) => {
          const p = Math.min((now - t0) / dur, 1)
          setCount(Math.round((1 - Math.pow(1 - p, 3)) * numericEnd))
          if (p < 1) requestAnimationFrame(tick)
        }
        requestAnimationFrame(tick)
      }, delay)
    }
    if (window.innerWidth < 720) { run(); return }
    const obs = new IntersectionObserver(([e]) => { if (e.isIntersecting) { run(); obs.disconnect() } }, { threshold: 0.4 })
    obs.observe(el)
    return () => obs.disconnect()
  }, [])
  return (
    <div ref={ref} style={{ padding: '28px 18px', background: 'var(--bg)', textAlign: 'center' }}>
      <div style={{ fontSize: 30, fontWeight: 700, color: 'var(--accent)', fontFamily: 'monospace', letterSpacing: '-1px' }}>{prefix}{count}{suffix}</div>
      <div style={{ fontSize: 11, color: 'var(--muted-2)', marginTop: 5 }}>{label}</div>
    </div>
  )
}

// ── ConciliacionMockup ────────────────────────────────────────────────────────
const CONCIL_ROWS = [
  { cliente: 'Comercial Norte SRL', importe: '$124.500', cuit: '30-71234567-8' },
  { cliente: 'Distribuidora Sur',   importe: '$89.200',  cuit: '20-28345678-9' },
  { cliente: 'Constructora Este SA', importe: '$212.000', cuit: '30-69123456-7' },
  { cliente: 'Servicios del Oeste', importe: '$56.800',  cuit: '27-34567890-1' },
  { cliente: 'Logística Central',   importe: '$98.400',  cuit: '30-70987654-3' },
]

const ConciliacionMockup: React.FC = () => {
  const ref = useRef<HTMLDivElement>(null)
  const [step, setStep] = useState(-1)
  const started = useRef(false)

  const run = (s: React.MutableRefObject<boolean>, setter: (n: number) => void) => {
    if (s.current) return
    s.current = true
    setter(-1)
    CONCIL_ROWS.forEach((_, i) => setTimeout(() => setter(i), 600 + i * 650))
    setTimeout(() => {
      s.current = false
      setTimeout(() => run(s, setter), 1500)
    }, 600 + CONCIL_ROWS.length * 650 + 2200)
  }

  useEffect(() => {
    const el = ref.current; if (!el) return
    const obs = new IntersectionObserver(([e]) => { if (e.isIntersecting) run(started, setStep) }, { threshold: 0.3 })
    obs.observe(el)
    if (window.innerWidth < 720) setTimeout(() => run(started, setStep), 400)
    return () => obs.disconnect()
  }, [])

  return (
    <div ref={ref} style={{ background: 'var(--card)', borderRadius: 18, border: '1px solid var(--border)', overflow: 'hidden', boxShadow: 'var(--mock-shadow)' }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '10px 16px', borderBottom: '1px solid var(--border)', background: 'var(--topbar-bg)' }}>
        <div style={{ display: 'flex', gap: 6 }}>
          {['#FF5F57','#FFBD2E','#28C840'].map(c => <div key={c} style={{ width: 10, height: 10, borderRadius: '50%', background: c }} />)}
        </div>
        <div style={{ flex: 1, margin: '0 14px', background: 'var(--bg-2)', borderRadius: 6, padding: '4px 10px', fontSize: 11, color: 'var(--muted-2)', textAlign: 'center' }}>
          cuadra.app / conciliaciones
        </div>
        <span style={{ color: 'var(--accent)' }}><Logo size={16} /></span>
      </div>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '9px 16px', borderBottom: '1px solid var(--border-soft)' }}>
        <span style={{ fontSize: 13, fontWeight: 700, color: 'var(--text)' }}>Planilla Mayo 2026</span>
        <div style={{ display: 'flex', gap: 6 }}>
          <span style={{ fontSize: 10, padding: '2px 7px', borderRadius: 5, background: 'var(--accent-soft)', color: 'var(--accent)', fontWeight: 700 }}>{step + 1}/{CONCIL_ROWS.length} OK</span>
          <span style={{ fontSize: 10, padding: '2px 7px', borderRadius: 5, background: '#F59E0B18', color: '#F59E0B', fontWeight: 700 }}>{Math.max(0, CONCIL_ROWS.length - step - 1)} pend.</span>
        </div>
      </div>
      <div style={{ padding: '10px 14px', display: 'flex', flexDirection: 'column', gap: 6 }}>
        {CONCIL_ROWS.map((r, i) => {
          const done = step >= i
          return (
            <div key={i} style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '9px 12px', borderRadius: 10, background: done ? 'var(--accent-soft)' : 'var(--card-2)', border: `1px solid ${done ? 'var(--accent-line)' : 'var(--border-soft)'}`, transition: 'all 0.45s ease' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 9, minWidth: 0 }}>
                <div style={{ width: 22, height: 22, borderRadius: '50%', flexShrink: 0, background: done ? 'var(--accent)' : 'var(--border)', display: 'flex', alignItems: 'center', justifyContent: 'center', transition: 'all 0.35s' }}>
                  {done ? <span style={{ color: '#fff', fontSize: 11, fontWeight: 700 }}>✓</span> : <span style={{ color: 'var(--muted-2)', fontSize: 9 }}>···</span>}
                </div>
                <div>
                  <div style={{ fontSize: 12, fontWeight: 600, color: done ? 'var(--accent)' : 'var(--text-2)', transition: 'color 0.3s' }}>{r.cliente}</div>
                  <div style={{ fontSize: 10, color: 'var(--muted-2)' }}>CUIT {r.cuit}</div>
                </div>
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: 7, flexShrink: 0 }}>
                <span style={{ fontSize: 12, fontFamily: 'monospace', color: done ? 'var(--accent)' : 'var(--muted)', fontWeight: done ? 700 : 400 }}>{r.importe}</span>
                <span style={{ fontSize: 10, padding: '2px 7px', borderRadius: 5, fontWeight: 700, background: done ? 'var(--accent)' : '#F59E0B18', color: done ? '#fff' : '#F59E0B', transition: 'all 0.3s' }}>{done ? 'OK' : 'PEND.'}</span>
              </div>
            </div>
          )
        })}
      </div>
      <div style={{ padding: '10px 16px 14px', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <span style={{ fontSize: 11, color: 'var(--muted-2)' }}>Motor de conciliación corriendo…</span>
        <span style={{ fontSize: 11, color: 'var(--accent)', fontWeight: 600 }}>↓ Exportar Excel</span>
      </div>
    </div>
  )
}

// ── OCRMockup ─────────────────────────────────────────────────────────────────
const OCR_FIELDS = [
  { label: 'Número',     value: '05812346' },
  { label: 'Banco',      value: 'Macro' },
  { label: 'Librador',   value: 'Constructora Sur SA' },
  { label: 'Monto',      value: '$212.000,00' },
  { label: 'Vencimiento', value: '15/06/2026' },
]

const OCRMockup: React.FC = () => {
  const ref = useRef<HTMLDivElement>(null)
  const [phase, setPhase] = useState<'idle' | 'scanning' | 'done'>('idle')
  const [visible, setVisible] = useState(0)
  const started = useRef(false)

  const run = () => {
    if (started.current) return
    started.current = true
    setPhase('idle'); setVisible(0)
    setTimeout(() => { setPhase('scanning') }, 400)
    setTimeout(() => {
      setPhase('done')
      OCR_FIELDS.forEach((_, i) => setTimeout(() => setVisible(v => Math.max(v, i + 1)), i * 380))
    }, 2000)
    setTimeout(() => { started.current = false; setTimeout(run, 1200) }, 2000 + OCR_FIELDS.length * 380 + 2200)
  }

  useEffect(() => {
    const el = ref.current; if (!el) return
    const obs = new IntersectionObserver(([e]) => { if (e.isIntersecting) run() }, { threshold: 0.3 })
    obs.observe(el)
    if (window.innerWidth < 720) setTimeout(run, 600)
    return () => obs.disconnect()
  }, [])

  return (
    <div ref={ref} style={{ background: 'var(--card)', borderRadius: 18, border: '1px solid var(--border)', overflow: 'hidden', boxShadow: 'var(--mock-shadow)' }}>
      <div style={{ padding: '11px 16px', borderBottom: '1px solid var(--border)', background: 'var(--topbar-bg)', display: 'flex', alignItems: 'center', gap: 8 }}>
        <span style={{ color: 'var(--accent)' }}><Logo size={16} /></span>
        <span style={{ fontSize: 13, fontWeight: 700, color: 'var(--text)' }}>Cargar cheque</span>
        <span style={{ marginLeft: 'auto', fontSize: 10, padding: '2px 8px', borderRadius: 6, background: 'var(--accent-soft)', color: 'var(--accent)', fontWeight: 700 }}>✨ OCR IA</span>
      </div>
      <div style={{ padding: 16 }}>
        <div style={{ borderRadius: 12, overflow: 'hidden', marginBottom: 14, position: 'relative', background: 'var(--bg-2)', border: `2px dashed ${phase === 'scanning' ? 'var(--accent)' : 'var(--border)'}`, height: 86, display: 'flex', alignItems: 'center', justifyContent: 'center', transition: 'border-color 0.3s' }}>
          {phase === 'idle' && <div style={{ textAlign: 'center' }}><div style={{ fontSize: 22 }}>📸</div><div style={{ fontSize: 11, color: 'var(--muted-2)', marginTop: 4 }}>Adjuntar foto del cheque</div></div>}
          {phase === 'scanning' && (
            <div style={{ textAlign: 'center' }}>
              <div style={{ fontSize: 22 }}>🔍</div>
              <div style={{ fontSize: 11, color: 'var(--accent)', marginTop: 4, fontWeight: 600 }}>Escaneando con IA…</div>
              <div style={{ position: 'absolute', top: 0, left: 0, right: 0, height: 2, background: 'linear-gradient(90deg, transparent, var(--accent), transparent)', animation: 'scanLine 0.9s ease-in-out infinite' }} />
            </div>
          )}
          {phase === 'done' && <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}><span style={{ fontSize: 20 }}>✅</span><span style={{ fontSize: 12, color: 'var(--accent)', fontWeight: 600 }}>Datos extraídos</span></div>}
        </div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
          {OCR_FIELDS.map((f, i) => (
            <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '7px 10px', borderRadius: 8, background: i < visible ? 'var(--accent-soft)' : 'var(--card-2)', border: `1px solid ${i < visible ? 'var(--accent-line)' : 'var(--border-soft)'}`, transition: 'all 0.35s ease', opacity: i < visible ? 1 : 0.35 }}>
              <span style={{ fontSize: 10, color: 'var(--muted-2)', width: 68, flexShrink: 0 }}>{f.label}</span>
              <span style={{ fontSize: 12, fontWeight: 600, fontFamily: ['Monto','Número'].includes(f.label) ? 'monospace' : 'inherit', color: i < visible ? 'var(--accent)' : 'var(--muted-2)', transition: 'color 0.3s' }}>
                {i < visible ? f.value : '· · ·'}
              </span>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}

// ── AlertaMockup ──────────────────────────────────────────────────────────────
const AlertaMockup: React.FC = () => {
  const ref = useRef<HTMLDivElement>(null)
  const [chatStep, setChatStep] = useState(0)
  const started = useRef(false)

  const run = () => {
    if (started.current) return
    started.current = true
    setChatStep(0)
    setTimeout(() => setChatStep(1), 500)
    setTimeout(() => setChatStep(2), 1900)
    setTimeout(() => setChatStep(3), 3400)
    setTimeout(() => { started.current = false; setChatStep(0); setTimeout(run, 1200) }, 6500)
  }

  useEffect(() => {
    const el = ref.current; if (!el) return
    const obs = new IntersectionObserver(([e]) => { if (e.isIntersecting) run() }, { threshold: 0.3 })
    obs.observe(el)
    if (window.innerWidth < 720) setTimeout(run, 800)
    return () => obs.disconnect()
  }, [])

  return (
    <div ref={ref} style={{ background: 'var(--card)', borderRadius: 18, border: '1px solid var(--border)', overflow: 'hidden', boxShadow: 'var(--mock-shadow)' }}>
      <div style={{ padding: '11px 14px', borderBottom: '1px solid var(--border)', background: 'var(--bg-2)', display: 'flex', alignItems: 'flex-start', gap: 10 }}>
        <div style={{ width: 32, height: 32, borderRadius: 8, background: 'var(--accent-soft)', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 16, flexShrink: 0 }}>🔔</div>
        <div>
          <div style={{ fontSize: 12, fontWeight: 700, color: 'var(--text)', marginBottom: 2 }}>Cuadra · Alerta automática</div>
          <div style={{ fontSize: 11, color: 'var(--muted)', lineHeight: 1.5 }}>2 cheques vencen mañana — Comercial Norte ($124.500) y Logística Central ($98.400)</div>
        </div>
      </div>
      <div style={{ padding: '12px 14px', display: 'flex', flexDirection: 'column', gap: 8, minHeight: 148 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 2 }}>
          <span style={{ fontSize: 11, fontWeight: 600, color: 'var(--accent)' }}>✨ Asistente IA Cuadra</span>
          <span style={{ fontSize: 9, color: 'var(--muted-2)', padding: '1px 6px', borderRadius: 99, border: '1px solid var(--border)' }}>en línea</span>
        </div>
        {chatStep >= 1 && (
          <div style={{ alignSelf: 'flex-end', background: 'var(--accent-soft)', border: '1px solid var(--accent-line)', borderRadius: '10px 10px 2px 10px', padding: '7px 11px', maxWidth: '80%' }}>
            <span style={{ fontSize: 12, color: 'var(--text)' }}>¿Cuánto cobro de comisión este mes?</span>
          </div>
        )}
        {chatStep >= 2 && (
          <div style={{ alignSelf: 'flex-start', background: 'var(--card-2)', border: '1px solid var(--border)', borderRadius: '10px 10px 10px 2px', padding: '7px 11px', maxWidth: '90%' }}>
            <span style={{ fontSize: 11, color: 'var(--text-2)', lineHeight: 1.5 }}>
              Conciliaste <strong style={{ color: 'var(--accent)' }}>$1.284.700</strong> en 12 planillas. Con tu comisión del 1,5%, son <strong style={{ color: 'var(--accent)' }}>$19.270</strong> a facturar.
            </span>
          </div>
        )}
        {chatStep >= 3 && (
          <div style={{ alignSelf: 'flex-end', background: 'var(--accent-soft)', border: '1px solid var(--accent-line)', borderRadius: '10px 10px 2px 10px', padding: '7px 11px', maxWidth: '70%' }}>
            <span style={{ fontSize: 12, color: 'var(--text)' }}>Perfecto, generá la liquidación 🙌</span>
          </div>
        )}
      </div>
    </div>
  )
}

// ── Calculadora ───────────────────────────────────────────────────────────────
const Calculadora: React.FC = () => {
  const [planillas, setPlanillas] = useState(10)
  const [horasCada, setHorasCada] = useState(3)
  const horasSin = planillas * horasCada
  const horasCon = Math.round(planillas * 2 / 60 * 10) / 10
  const ahorro = Math.max(0, horasSin - horasCon)

  return (
    <div style={{ background: 'var(--card)', borderRadius: 18, border: '1px solid var(--border)', padding: '28px 24px', boxShadow: 'var(--mock-shadow)' }}>
      {[
        { label: 'Planillas por mes', val: `${planillas}`, min: 1, max: 300, cur: planillas, set: setPlanillas, unit: '' },
        { label: 'Horas por planilla (hoy)', val: `${horasCada}hs`, min: 1, max: 8, cur: horasCada, set: setHorasCada, unit: 'hs' },
      ].map((s, i) => (
        <div key={i} style={{ marginBottom: i === 0 ? 22 : 26 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
            <label style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-2)' }}>{s.label}</label>
            <span style={{ fontSize: 17, fontWeight: 800, color: 'var(--accent)', fontFamily: 'monospace' }}>{s.val}</span>
          </div>
          <input type="range" min={s.min} max={s.max} value={s.cur}
            onChange={e => s.set(+e.target.value)} className="calc-range" style={{ width: '100%' }} />
          <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: 3 }}>
            <span style={{ fontSize: 10, color: 'var(--muted-2)' }}>{s.min}{s.unit}</span>
            <span style={{ fontSize: 10, color: 'var(--muted-2)' }}>{s.max}{s.unit}</span>
          </div>
        </div>
      ))}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10, marginBottom: 12 }}>
        <div style={{ textAlign: 'center', padding: '16px 12px', borderRadius: 12, background: '#F59E0B10', border: '1px solid #F59E0B30' }}>
          <div style={{ fontSize: 10, color: '#F59E0B', fontWeight: 700, marginBottom: 5, textTransform: 'uppercase', letterSpacing: '0.06em' }}>Hoy</div>
          <div style={{ fontSize: 28, fontWeight: 800, color: '#F59E0B', fontFamily: 'monospace' }}>{horasSin}hs</div>
          <div style={{ fontSize: 10, color: 'var(--muted-2)', marginTop: 3 }}>en conciliación</div>
        </div>
        <div style={{ textAlign: 'center', padding: '16px 12px', borderRadius: 12, background: 'var(--accent-soft)', border: '1px solid var(--accent-line)' }}>
          <div style={{ fontSize: 10, color: 'var(--accent)', fontWeight: 700, marginBottom: 5, textTransform: 'uppercase', letterSpacing: '0.06em' }}>Con Cuadra</div>
          <div style={{ fontSize: 28, fontWeight: 800, color: 'var(--accent)', fontFamily: 'monospace' }}>{horasCon}hs</div>
          <div style={{ fontSize: 10, color: 'var(--muted-2)', marginTop: 3 }}>en conciliación</div>
        </div>
      </div>
      <div style={{ textAlign: 'center', padding: '13px', borderRadius: 10, background: 'var(--accent-soft)', border: '1px solid var(--accent-line)' }}>
        <span style={{ fontSize: 14, color: 'var(--accent)', fontWeight: 700 }}>
          ✓ Recuperás <span style={{ fontSize: 19 }}>{ahorro}hs</span> por mes
        </span>
      </div>
    </div>
  )
}

// ── Data ──────────────────────────────────────────────────────────────────────
const STATS = [
  { label: 'para conciliar 100 movimientos', numericEnd: 2,  prefix: '< ', suffix: ' min' },
  { label: 'bancos argentinos soportados',   numericEnd: 10, prefix: '',   suffix: '+' },
  { label: 'instalaciones necesarias',       numericEnd: 0,  prefix: '',   suffix: '' },
  { label: 'para estar operativo',           numericEnd: 24, prefix: '',   suffix: 'hs' },
]

const MOCKUP_ROWS = [
  { cliente: 'Cliente Norte SRL',  importe: '$124.500', ok: true  },
  { cliente: 'Constructora Sur',   importe: '$89.200',  ok: true  },
  { cliente: 'Distribuidora Este', importe: '$212.000', ok: false },
  { cliente: 'Servicios Centro',   importe: '$56.800',  ok: true  },
  { cliente: 'Comercial Oeste',    importe: '$98.400',  ok: true  },
]

const SECURITY = [
  { icon: '🔐', title: 'Acceso protegido siempre', desc: 'Las sesiones se cierran automáticamente por inactividad. Sin tu clave no puede entrar nadie más, aunque tengan el dispositivo.' },
  { icon: '🏢', title: 'Datos separados por empresa', desc: 'Cada empresa ve solo sus propios datos. Imposible que un usuario de una empresa vea información de otra.' },
  { icon: '🔑', title: 'Contraseñas cifradas', desc: 'Las contraseñas se guardan cifradas. Aunque alguien accediera a la base de datos, no podría leerlas.' },
  { icon: '💾', title: 'Backup diario automático', desc: 'Copia completa de todos los datos cada noche. Si algo falla, recuperamos todo sin perder información.' },
  { icon: '📋', title: 'Registro de actividad completo', desc: 'Cada acción queda registrada: quién hizo qué, cuándo y desde dónde. Ideal para auditorías internas.' },
  { icon: '🇦🇷', title: 'Ley de protección de datos', desc: 'Cumplimos la Ley 25.326 argentina. Tus datos y los de tus clientes son tuyos — no se usan para nada más.' },
]

const FAQ = [
  { q: '¿Cuánto cuesta usar Cuadra?', a: 'El precio se ajusta según la cantidad de empresas y usuarios. Coordiná un contacto por WhatsApp y te paso la propuesta con condiciones para tu caso.' },
  { q: '¿Qué bancos soporta el sistema?', a: 'Banco Macro, BBVA, Santander, Galicia, ICBC y un parser genérico para extractos en formato Excel. Si tu banco no está, lo agregamos en el onboarding.' },
  { q: '¿Mis datos están seguros?', a: 'Sí. Los datos de cada empresa están aislados, las contraseñas se guardan cifradas, hay backup automático cada noche y un registro completo de quién hizo qué y cuándo. Todo por HTTPS.' },
  { q: '¿Funciona sin conexión?', a: 'Las consultas básicas sí (lectura de cache). Para cargar planillas, registrar pagos o conciliar necesitás conexión.' },
  { q: '¿Se conecta con ARCA?', a: 'Por ahora no directamente. Exporta Excel en formato Banco Macro y PDF de cierre mensual, todo listo para entregar al contador.' },
  { q: '¿Cuántos usuarios puedo tener?', a: 'Sin límite. Cada empresa puede tener todos los empleados que necesite, con roles diferenciados (admin, operador, solo lectura).' },
  { q: '¿Puedo importar mis datos viejos?', a: 'Sí. Las planillas y extractos en Excel se importan directamente. Para datos en otros formatos, lo coordinamos en el onboarding inicial.' },
]

const COMPARISON = [
  { feature: 'Conciliar 100 movimientos', excel: '4–6 horas', cuadra: '2 minutos' },
  { feature: 'Errores humanos', excel: 'Frecuentes', cuadra: 'Mínimos (auto-detección)' },
  { feature: 'Acceso desde el celular', excel: 'No', cuadra: 'Sí, desde cualquier teléfono' },
  { feature: 'Multi-empresa', excel: 'Un archivo por empresa', cuadra: 'Todo en un sistema' },
  { feature: 'Backup automático', excel: 'Manual o ninguno', cuadra: 'Diario encriptado' },
  { feature: 'Auditoría de cambios', excel: 'Ninguna', cuadra: 'Log completo' },
  { feature: 'Trabajo en equipo', excel: 'Conflictos al editar', cuadra: 'En tiempo real' },
]

const TESTIMONIALES = [
  {
    quote: 'Antes me llevaba medio día cruzar el extracto con las planillas de cada cliente. Ahora lo subo y en dos minutos está listo para el contador.',
    nombre: 'Mariela R.',
    rol: 'Contadora, Rosario',
    inicial: 'M',
  },
  {
    quote: 'El módulo de cheques con las alertas automáticas me salvó de varios rechazos. Cuadra se paga solo en la primera semana del mes.',
    nombre: 'Diego F.',
    rol: 'Administración, constructora PyME',
    inicial: 'D',
  },
]

// ── Landing ───────────────────────────────────────────────────────────────────
export const Landing: React.FC = () => {
  const { theme, toggle } = useThemeStore()
  const [faqOpen, setFaqOpen]   = useState<number | null>(0)
  const [menuOpen, setMenuOpen] = useState(false)
  const closeMenu = () => setMenuOpen(false)

  return (
    <div className="landing-root">
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
          --accent:       #22C55E;
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
        .hero-title { font-size:clamp(38px,10vw,84px); font-weight:700; line-height:1.06; letter-spacing:-2px; max-width:820px; margin-bottom:22px; }
        .hero-sub { font-size:clamp(15px,3.5vw,20px); color:var(--muted); max-width:500px; line-height:1.65; margin-bottom:36px; padding:0 8px; }
        .mockup-wrap { width:100%; max-width:560px; padding:0 4px; }

        /* Sections */
        .section { padding:72px 20px; }
        @media (min-width:720px) { .section { padding:96px 24px; } }
        .section-title { font-size:clamp(26px,6vw,46px); font-weight:700; letter-spacing:-1.5px; margin-bottom:14px; line-height:1.1; }

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

      {menuOpen && (
        <div className="mobile-menu-overlay">
          <a href="#como-funciona" onClick={closeMenu}>✦ Cómo funciona</a>
          <a href="#seguridad"     onClick={closeMenu}>✦ Seguridad</a>
          <a href="#faq"           onClick={closeMenu}>✦ FAQ</a>
          <a href="#contacto"      onClick={closeMenu}>✦ Contacto</a>
        </div>
      )}

      <nav className="land-nav">
        <a href="#top" className="nav-logo">
          <span style={{ color: 'var(--accent)' }}><Logo size={24} /></span>
          Cuadra
        </a>
        <div className="nav-actions">
          <div className="nav-links">
            <a href="#como-funciona" className="btn-ghost" style={{ padding: '7px 12px', fontSize: 13 }}>Cómo funciona</a>
            <a href="#seguridad"     className="btn-ghost" style={{ padding: '7px 12px', fontSize: 13 }}>Seguridad</a>
            <a href="#faq"           className="btn-ghost" style={{ padding: '7px 12px', fontSize: 13 }}>FAQ</a>
            <a href="#contacto"      className="btn-ghost" style={{ padding: '7px 12px', fontSize: 13 }}>Contacto</a>
          </div>
          <button onClick={toggle} className="theme-toggle" title={theme === 'dark' ? 'Modo claro' : 'Modo oscuro'} aria-label="Cambiar tema">
            {theme === 'dark' ? '☀' : '☾'}
          </button>
          <button onClick={() => setMenuOpen(o => !o)} className="ham-btn" aria-label="Menú">
            {menuOpen ? '✕' : '☰'}
          </button>
          <Link to="/login" className="btn-green">Ingresar</Link>
        </div>
      </nav>

      {/* ── HERO ── */}
      <section id="top" className="hero-section">
        <div className="glow-orb" style={{ position: 'absolute', top: '18%', left: '50%', transform: 'translateX(-50%)', width: 'min(700px,90vw)', height: 400, borderRadius: '50%', background: 'radial-gradient(circle, var(--accent-soft) 0%, transparent 70%)', pointerEvents: 'none' }} />

        <div className="live-badge" style={{ display: 'inline-flex', alignItems: 'center', gap: 8, padding: '6px 14px', borderRadius: 999, background: 'var(--accent-soft)', border: '1px solid var(--accent-line)', color: 'var(--accent)', fontSize: 12, fontWeight: 600, marginBottom: 24 }}>
          <span style={{ width: 6, height: 6, borderRadius: '50%', background: 'var(--accent)', display: 'inline-block' }} />
          Gestión bancaria para empresas argentinas
        </div>

        <h1 className="hero-title">
          Los números<br />
          <span className="em-serif grad-text">cuadran solos.</span>
        </h1>

        <p className="hero-sub">
          Conciliación bancaria automática, cheques, caja y pagos.
          Para vos y tu equipo, desde el celular o la web.
        </p>

        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 10, justifyContent: 'center', marginBottom: 18 }}>
          <a href="#como-funciona" className="btn-green large">Ver cómo funciona →</a>
        </div>

        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', justifyContent: 'center', marginBottom: 44 }}>
          {['✓ Web y mobile', '✓ Soporte directo', '✓ Onboarding incluido'].map(b => (
            <span key={b} style={{ fontSize: 12, color: 'var(--muted)', background: 'var(--card)', border: '1px solid var(--border)', padding: '5px 12px', borderRadius: 999 }}>{b}</span>
          ))}
        </div>

        {/* Hero mockup */}
        <div className="mock-float mockup-wrap">
          <div style={{ borderRadius: 18, border: '1px solid var(--border)', background: 'var(--card)', boxShadow: 'var(--mock-shadow)', overflow: 'hidden' }}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '11px 16px', borderBottom: '1px solid var(--border)', background: 'var(--topbar-bg)' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <span style={{ color: 'var(--accent)' }}><Logo size={18} /></span>
                <span style={{ fontSize: 12, fontWeight: 700, color: 'var(--accent)' }}>Cuadra</span>
              </div>
              <div style={{ display: 'flex', gap: 6 }}>
                {['#FF5F57','#FFBD2E','#28C840'].map(c => <div key={c} style={{ width: 9, height: 9, borderRadius: '50%', background: c }} />)}
              </div>
            </div>
            <div style={{ padding: 16 }}>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 8, marginBottom: 14 }}>
                {[{ label: 'Conciliados', val: '47', color: 'var(--accent)' }, { label: 'Pendientes', val: '3', color: '#F59E0B' }, { label: 'Caja', val: '$482k', color: '#5E6AD2' }].map(s => (
                  <div key={s.label} style={{ background: 'var(--card-2)', borderRadius: 10, padding: '10px', border: '1px solid var(--border-soft)' }}>
                    <div style={{ fontSize: 18, fontWeight: 700, color: s.color, fontFamily: 'monospace' }}>{s.val}</div>
                    <div style={{ fontSize: 10, color: 'var(--muted-2)', marginTop: 2 }}>{s.label}</div>
                  </div>
                ))}
              </div>
              <div style={{ fontSize: 10, color: 'var(--muted-2)', fontWeight: 600, marginBottom: 8, textTransform: 'uppercase', letterSpacing: '0.08em' }}>Planilla del mes</div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 5 }}>
                {MOCKUP_ROWS.map((r, i) => (
                  <div key={i} style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '8px 10px', borderRadius: 8, background: r.ok ? 'var(--accent-soft)' : 'var(--card-2)', border: `1px solid ${r.ok ? 'var(--accent-line)' : 'var(--border-soft)'}` }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8, minWidth: 0 }}>
                      <div style={{ width: 6, height: 6, borderRadius: '50%', flexShrink: 0, background: r.ok ? 'var(--accent)' : '#F59E0B' }} />
                      <span style={{ fontSize: 12, fontWeight: 500, color: 'var(--text-2)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{r.cliente}</span>
                    </div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 6, flexShrink: 0 }}>
                      <span style={{ fontSize: 11, fontFamily: 'monospace', color: 'var(--muted)' }}>{r.importe}</span>
                      <span style={{ fontSize: 10, padding: '2px 6px', borderRadius: 4, background: r.ok ? 'var(--accent)' : '#F59E0B18', color: r.ok ? '#fff' : '#F59E0B', fontWeight: 700 }}>{r.ok ? 'OK' : 'REVISAR'}</span>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* ── STATS ── */}
      <section style={{ padding: '0 20px 72px' }}>
        <div style={{ maxWidth: 900, margin: '0 auto' }}>
          <div className="stats-grid">
            {STATS.map((s, i) => <StatCounter key={s.label} {...s} delay={i * 150} />)}
          </div>
        </div>
      </section>

      {/* ── EL PROBLEMA ── */}
      <section className="section" style={{ background: 'var(--bg-2)', borderTop: '1px solid var(--border-soft)', borderBottom: '1px solid var(--border-soft)' }}>
        <div style={{ maxWidth: 800, margin: '0 auto' }}>
          <R>
            <div style={{ textAlign: 'center', marginBottom: 44 }}>
              <div className="sec-label">El problema</div>
              <h2 className="section-title">El Excel no cuadra.<br /><em className="em-serif">Otra vez.</em></h2>
            </div>
          </R>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: 14 }}>
            {[
              { icon: '🕐', text: 'Pasás horas cruzando el extracto bancario contra las planillas de cada cliente.' },
              { icon: '😤', text: 'Un cliente pagó, el banco lo registró diferente, y no sabés si cuadra o no.' },
              { icon: '📧', text: 'El contador pide el cierre y todavía estás buscando el movimiento que falta.' },
              { icon: '📋', text: 'Cada mes es lo mismo: el Excel crece, los errores se multiplican, el tiempo se va.' },
            ].map((item, i) => (
              <R key={i} delay={i * 70}>
                <div style={{ padding: '20px 22px', borderRadius: 14, background: 'var(--card)', border: '1px solid var(--border)', display: 'flex', gap: 14, alignItems: 'flex-start' }}>
                  <span style={{ fontSize: 22, flexShrink: 0, marginTop: 2 }}>{item.icon}</span>
                  <span style={{ fontSize: 13, color: 'var(--muted)', lineHeight: 1.65 }}>{item.text}</span>
                </div>
              </R>
            ))}
          </div>
          <R delay={200}>
            <div style={{ textAlign: 'center', marginTop: 36 }}>
              <p style={{ color: 'var(--muted)', fontSize: 15, marginBottom: 14 }}>Cuadra lo hace automático. Vos revisás solo lo que necesita atención.</p>
              <a href="#como-funciona" style={{ color: 'var(--accent)', fontWeight: 600, fontSize: 14, textDecoration: 'none' }}>Ver cómo funciona →</a>
            </div>
          </R>
        </div>
      </section>

      {/* ── SPOTLIGHT 01 — CONCILIACIÓN ── */}
      <section id="como-funciona" className="section">
        <div className="spotlight">
          <R className="spotlight-text">
            <div className="sec-label">01 · Conciliación</div>
            <h2 style={{ fontSize: 'clamp(24px,5vw,38px)', fontWeight: 700, letterSpacing: '-1.2px', lineHeight: 1.12, marginBottom: 16 }}>
              Subís el extracto.<br />
              <em className="em-serif">Cuadra solo.</em>
            </h2>
            <p style={{ color: 'var(--muted)', lineHeight: 1.7, marginBottom: 22, fontSize: 14 }}>
              El motor de conciliación cruza tu extracto bancario contra cada planilla por CUIT, CBU y referencia. Lo que coincide se marca automáticamente. Lo ambiguo queda para que vos decidás.
            </p>
            <ul style={{ listStyle: 'none', padding: 0, margin: 0, display: 'flex', flexDirection: 'column', gap: 10 }}>
              {['Macro, BBVA, Santander, Galicia, ICBC', 'Detección de duplicados automática', 'Export Excel para el contador en un click', 'PDF de cierre mensual incluido'].map(item => (
                <li key={item} style={{ display: 'flex', alignItems: 'center', gap: 10, fontSize: 14, color: 'var(--text-2)' }}>
                  <span style={{ color: 'var(--accent)', fontWeight: 700 }}>✓</span>{item}
                </li>
              ))}
            </ul>
            <div style={{ marginTop: 28 }}>
              <a href={WA_LINK} target="_blank" rel="noopener noreferrer" className="wa-btn" style={{ fontSize: 14, padding: '12px 22px' }}>
                <svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><path d="M17.472 14.382c-.297-.149-1.758-.867-2.03-.967-.273-.099-.471-.148-.67.15-.197.297-.767.966-.94 1.164-.173.199-.347.223-.644.075-.297-.15-1.255-.463-2.39-1.475-.883-.788-1.48-1.761-1.653-2.059-.173-.297-.018-.458.13-.606.134-.133.298-.347.446-.52.149-.174.198-.298.298-.497.099-.198.05-.371-.025-.52-.075-.149-.669-1.612-.916-2.207-.242-.579-.487-.5-.669-.51-.173-.008-.371-.01-.57-.01-.198 0-.52.074-.792.372-.272.297-1.04 1.016-1.04 2.479 0 1.462 1.065 2.875 1.213 3.074.149.198 2.096 3.2 5.077 4.487.709.306 1.262.489 1.694.625.712.227 1.36.195 1.871.118.571-.085 1.758-.719 2.006-1.413.248-.694.248-1.289.173-1.413-.074-.124-.272-.198-.57-.347m-5.421 7.403h-.004a9.87 9.87 0 01-5.031-1.378l-.361-.214-3.741.982.998-3.648-.235-.374a9.86 9.86 0 01-1.51-5.26c.001-5.45 4.436-9.884 9.888-9.884 2.64 0 5.122 1.03 6.988 2.898a9.825 9.825 0 012.893 6.994c-.003 5.45-4.437 9.884-9.885 9.884m8.413-18.297A11.815 11.815 0 0012.05 0C5.495 0 .16 5.335.157 11.892c0 2.096.547 4.142 1.588 5.945L.057 24l6.305-1.654a11.882 11.882 0 005.683 1.448h.005c6.554 0 11.89-5.335 11.893-11.893a11.821 11.821 0 00-3.48-8.413z"/></svg>
                Quiero implementar Cuadra
              </a>
            </div>
          </R>
          <R delay={100} className="spotlight-mock"><ConciliacionMockup /></R>
        </div>
      </section>

      {/* ── SPOTLIGHT 02 — OCR ── */}
      <section className="section" style={{ background: 'var(--bg-2)', borderTop: '1px solid var(--border-soft)', borderBottom: '1px solid var(--border-soft)' }}>
        <div className="spotlight reverse">
          <R className="spotlight-mock"><OCRMockup /></R>
          <R delay={100} className="spotlight-text">
            <div className="sec-label">02 · Cheques</div>
            <h2 style={{ fontSize: 'clamp(24px,5vw,38px)', fontWeight: 700, letterSpacing: '-1.2px', lineHeight: 1.12, marginBottom: 16 }}>
              Sacás la foto.<br />
              <em className="em-serif">La IA lo carga.</em>
            </h2>
            <p style={{ color: 'var(--muted)', lineHeight: 1.7, marginBottom: 22, fontSize: 14 }}>
              Adjuntá una foto del cheque desde el celular. La IA lee número, banco, librador, monto y vencimiento automáticamente. No más carga manual, no más errores de tipeo.
            </p>
            <ul style={{ listStyle: 'none', padding: 0, margin: 0, display: 'flex', flexDirection: 'column', gap: 10 }}>
              {['Lectura automática de cheques con IA', 'Alertas antes del vencimiento (push)', 'Ciclo completo: registro → depósito → rechazo', 'Cheques Local e Interior con comisión diferenciada'].map(item => (
                <li key={item} style={{ display: 'flex', alignItems: 'center', gap: 10, fontSize: 14, color: 'var(--text-2)' }}>
                  <span style={{ color: 'var(--accent)', fontWeight: 700 }}>✓</span>{item}
                </li>
              ))}
            </ul>
          </R>
        </div>
      </section>

      {/* ── SPOTLIGHT 03 — IA ── */}
      <section className="section">
        <div className="spotlight">
          <R className="spotlight-text">
            <div className="sec-label">03 · Asistente IA</div>
            <h2 style={{ fontSize: 'clamp(24px,5vw,38px)', fontWeight: 700, letterSpacing: '-1.2px', lineHeight: 1.12, marginBottom: 16 }}>
              Preguntás en<br />
              <em className="em-serif">lenguaje natural.</em>
            </h2>
            <p style={{ color: 'var(--muted)', lineHeight: 1.7, marginBottom: 22, fontSize: 14 }}>
              El asistente IA tiene acceso a tus datos reales. Consultá saldos, comisiones del mes, cheques por vencer o movimientos sin conciliar — con tu voz o escribiendo.
            </p>
            <ul style={{ listStyle: 'none', padding: 0, margin: 0, display: 'flex', flexDirection: 'column', gap: 10 }}>
              {['Dictado por voz desde el celular', 'Alertas automáticas de cheques y movimientos', 'Consultas de comisión y liquidaciones', 'Disponible en todas las pantallas del sistema'].map(item => (
                <li key={item} style={{ display: 'flex', alignItems: 'center', gap: 10, fontSize: 14, color: 'var(--text-2)' }}>
                  <span style={{ color: 'var(--accent)', fontWeight: 700 }}>✓</span>{item}
                </li>
              ))}
            </ul>
          </R>
          <R delay={100} className="spotlight-mock"><AlertaMockup /></R>
        </div>
      </section>

      {/* ── CALCULADORA ── */}
      <section className="section" style={{ background: 'var(--bg-2)', borderTop: '1px solid var(--border-soft)', borderBottom: '1px solid var(--border-soft)' }}>
        <div style={{ maxWidth: 900, margin: '0 auto' }}>
          <R>
            <div style={{ textAlign: 'center', marginBottom: 44 }}>
              <div className="sec-label">04 · Tu tiempo vale</div>
              <h2 className="section-title">¿Cuántas horas<br /><em className="em-serif">estás perdiendo?</em></h2>
              <p style={{ color: 'var(--muted)', fontSize: 15 }}>Calculá el tiempo que recuperás cada mes.</p>
            </div>
          </R>
          <R delay={100}>
            <div style={{ maxWidth: 520, margin: '0 auto' }}>
              <Calculadora />
            </div>
          </R>
        </div>
      </section>

      {/* ── COMPARATIVA ── */}
      <section className="section">
        <div style={{ maxWidth: 900, margin: '0 auto' }}>
          <R>
            <div style={{ textAlign: 'center', marginBottom: 44 }}>
              <div className="sec-label">Comparativa</div>
              <h2 className="section-title">Excel manual<br />vs <em className="em-serif">Cuadra</em></h2>
              <p style={{ color: 'var(--muted)', fontSize: 15 }}>Si hoy hacés todo en planillas, esto te interesa.</p>
            </div>
          </R>
          <R delay={100}>
            <div style={{ overflowX: 'auto', borderRadius: 12 }}>
              <table className="compare-table">
                <thead>
                  <tr><th>Tarea</th><th>Excel manual</th><th>Cuadra</th></tr>
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

      {/* ── TESTIMONIALES ── */}
      <section className="section" style={{ background: 'var(--bg-2)', borderTop: '1px solid var(--border-soft)', borderBottom: '1px solid var(--border-soft)' }}>
        <div style={{ maxWidth: 900, margin: '0 auto' }}>
          <R>
            <div style={{ textAlign: 'center', marginBottom: 44 }}>
              <div className="sec-label">Clientes</div>
              <h2 className="section-title">Lo que dicen<br /><em className="em-serif">quienes lo usan</em></h2>
            </div>
          </R>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: 16 }}>
            {TESTIMONIALES.map((t, i) => (
              <R key={i} delay={i * 100}>
                <div className="grad-border" style={{ padding: '28px 26px', height: '100%', boxSizing: 'border-box' }}>
                  <div style={{ fontSize: 28, color: 'var(--accent)', marginBottom: 16, lineHeight: 1 }}>"</div>
                  <p style={{ fontSize: 14, lineHeight: 1.75, color: 'var(--text-2)', marginBottom: 20 }}>{t.quote}</p>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                    <div style={{ width: 36, height: 36, borderRadius: '50%', background: 'var(--accent-soft)', border: '1px solid var(--accent-line)', display: 'flex', alignItems: 'center', justifyContent: 'center', fontWeight: 700, fontSize: 14, color: 'var(--accent)', flexShrink: 0 }}>
                      {t.inicial}
                    </div>
                    <div>
                      <div style={{ fontSize: 13, fontWeight: 700, color: 'var(--text)' }}>{t.nombre}</div>
                      <div style={{ fontSize: 11, color: 'var(--muted-2)' }}>{t.rol}</div>
                    </div>
                  </div>
                </div>
              </R>
            ))}
          </div>
        </div>
      </section>

      {/* ── SEGURIDAD ── */}
      <section id="seguridad" className="section">
        <div style={{ maxWidth: 1000, margin: '0 auto' }}>
          <R>
            <div style={{ textAlign: 'center', marginBottom: 52 }}>
              <div className="sec-label">Seguridad y privacidad</div>
              <h2 className="section-title">Construido para<br /><em className="em-serif">datos sensibles</em></h2>
              <p style={{ color: 'var(--muted)', fontSize: 15, maxWidth: 500, margin: '0 auto' }}>
                Tus datos contables y los de tus clientes están en una infraestructura pensada para eso desde el primer día.
              </p>
            </div>
          </R>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(260px, 1fr))', gap: 14 }}>
            {SECURITY.map((s, i) => (
              <R key={s.title} delay={i * 60}>
                <div className="grad-border" style={{ padding: 24, height: '100%', boxSizing: 'border-box' }}>
                  <div style={{ fontSize: 24, marginBottom: 10 }}>{s.icon}</div>
                  <div style={{ fontWeight: 700, fontSize: 14, marginBottom: 7, color: 'var(--text)' }}>{s.title}</div>
                  <div style={{ fontSize: 13, color: 'var(--muted)', lineHeight: 1.65 }}>{s.desc}</div>
                </div>
              </R>
            ))}
          </div>
        </div>
      </section>

      {/* ── CLOSING CTA ── */}
      <section className="section" style={{ background: 'var(--bg-2)', borderTop: '1px solid var(--border-soft)', borderBottom: '1px solid var(--border-soft)' }}>
        <div style={{ maxWidth: 800, margin: '0 auto' }}>
          <R>
            <div className="cta-card">
              <div style={{ position: 'relative', zIndex: 1 }}>
                <div style={{ fontSize: 11, fontWeight: 700, letterSpacing: '0.14em', textTransform: 'uppercase', color: 'rgba(255,255,255,0.6)', marginBottom: 16 }}>Empezá hoy</div>
                <h2 style={{ fontSize: 'clamp(28px,6vw,52px)', fontWeight: 700, letterSpacing: '-1.5px', lineHeight: 1.08, color: '#fff', marginBottom: 16 }}>
                  Tu empresa operativa<br />en menos de 24 horas.
                </h2>
                <p style={{ fontSize: 16, color: 'rgba(255,255,255,0.75)', maxWidth: 420, margin: '0 auto 32px', lineHeight: 1.65 }}>
                  Demo en vivo de 20 minutos, onboarding incluido, soporte directo por WhatsApp. Sin burocracia.
                </p>
                <div style={{ display: 'flex', gap: 12, justifyContent: 'center', flexWrap: 'wrap' }}>
                  <a href="#contacto" style={{ display: 'inline-flex', alignItems: 'center', gap: 6, padding: '14px 28px', borderRadius: 12, background: '#fff', color: 'var(--accent-2)', fontWeight: 700, fontSize: 15, textDecoration: 'none', transition: 'transform .1s', border: 'none' }}
                    onMouseEnter={e => (e.currentTarget.style.transform = 'translateY(-2px)')}
                    onMouseLeave={e => (e.currentTarget.style.transform = '')}
                  >
                    Solicitar demo →
                  </a>
                  <a href={WA_LINK} target="_blank" rel="noopener noreferrer" style={{ display: 'inline-flex', alignItems: 'center', gap: 8, padding: '14px 24px', borderRadius: 12, background: 'rgba(255,255,255,.15)', color: '#fff', fontWeight: 600, fontSize: 15, textDecoration: 'none', border: '1px solid rgba(255,255,255,.25)' }}>
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor"><path d="M17.472 14.382c-.297-.149-1.758-.867-2.03-.967-.273-.099-.471-.148-.67.15-.197.297-.767.966-.94 1.164-.173.199-.347.223-.644.075-.297-.15-1.255-.463-2.39-1.475-.883-.788-1.48-1.761-1.653-2.059-.173-.297-.018-.458.13-.606.134-.133.298-.347.446-.52.149-.174.198-.298.298-.497.099-.198.05-.371-.025-.52-.075-.149-.669-1.612-.916-2.207-.242-.579-.487-.5-.669-.51-.173-.008-.371-.01-.57-.01-.198 0-.52.074-.792.372-.272.297-1.04 1.016-1.04 2.479 0 1.462 1.065 2.875 1.213 3.074.149.198 2.096 3.2 5.077 4.487.709.306 1.262.489 1.694.625.712.227 1.36.195 1.871.118.571-.085 1.758-.719 2.006-1.413.248-.694.248-1.289.173-1.413-.074-.124-.272-.198-.57-.347m-5.421 7.403h-.004a9.87 9.87 0 01-5.031-1.378l-.361-.214-3.741.982.998-3.648-.235-.374a9.86 9.86 0 01-1.51-5.26c.001-5.45 4.436-9.884 9.888-9.884 2.64 0 5.122 1.03 6.988 2.898a9.825 9.825 0 012.893 6.994c-.003 5.45-4.437 9.884-9.885 9.884m8.413-18.297A11.815 11.815 0 0012.05 0C5.495 0 .16 5.335.157 11.892c0 2.096.547 4.142 1.588 5.945L.057 24l6.305-1.654a11.882 11.882 0 005.683 1.448h.005c6.554 0 11.89-5.335 11.893-11.893a11.821 11.821 0 00-3.48-8.413z"/></svg>
                    WhatsApp
                  </a>
                </div>
              </div>
            </div>
          </R>
        </div>
      </section>

      {/* ── FAQ ── */}
      <section id="faq" className="section">
        <div style={{ maxWidth: 720, margin: '0 auto' }}>
          <R>
            <div style={{ textAlign: 'center', marginBottom: 44 }}>
              <div className="sec-label">FAQ</div>
              <h2 className="section-title">Todo lo que querés <em className="em-serif">saber</em></h2>
            </div>
          </R>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
            {FAQ.map((item, i) => (
              <R key={i} delay={i * 40}>
                <div className="faq-item">
                  <button className="faq-q" onClick={() => setFaqOpen(faqOpen === i ? null : i)} aria-expanded={faqOpen === i}>
                    <span>{item.q}</span>
                    <span className={`faq-q-icon ${faqOpen === i ? 'open' : ''}`}>+</span>
                  </button>
                  {faqOpen === i && <div className="faq-a">{item.a}</div>}
                </div>
              </R>
            ))}
          </div>
          <R delay={300}>
            <div style={{ textAlign: 'center', marginTop: 36, fontSize: 14, color: 'var(--muted)' }}>
              ¿Tu pregunta no está acá?{' '}
              <a href="#contacto" style={{ color: 'var(--accent)', fontWeight: 600, textDecoration: 'none' }}>Escribime →</a>
            </div>
          </R>
        </div>
      </section>

      {/* ── PRICING ── */}
      <section className="section" style={{ background: 'var(--bg-2)', borderTop: '1px solid var(--border-soft)', borderBottom: '1px solid var(--border-soft)' }}>
        <div style={{ maxWidth: 640, margin: '0 auto' }}>
          <R>
            <div style={{ textAlign: 'center', marginBottom: 40 }}>
              <div className="sec-label">Precio</div>
              <h2 className="section-title">Una propuesta a <em className="em-serif">tu medida</em></h2>
              <p style={{ color: 'var(--muted)', fontSize: 15, maxWidth: 440, margin: '0 auto', lineHeight: 1.6 }}>
                El precio se ajusta a la cantidad de empresas, usuarios y volumen de operaciones. Sin sorpresas.
              </p>
            </div>
          </R>
          <R delay={100}>
            <div className="grad-border" style={{ padding: '36px 28px', textAlign: 'center' }}>
              <div style={{ display: 'inline-block', padding: '5px 12px', borderRadius: 999, background: 'var(--accent-soft)', border: '1px solid var(--accent-line)', color: 'var(--accent)', fontSize: 11, fontWeight: 600, marginBottom: 18, letterSpacing: '0.06em', textTransform: 'uppercase' }}>
                Onboarding incluido
              </div>
              <h3 style={{ fontSize: 22, fontWeight: 700, marginBottom: 8, letterSpacing: '-0.5px' }}>Plan empresa</h3>
              <p style={{ color: 'var(--muted)', fontSize: 14, marginBottom: 28, maxWidth: 340, marginLeft: 'auto', marginRight: 'auto', lineHeight: 1.6 }}>
                Implementación, capacitación al equipo y soporte directo.
              </p>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))', gap: 12, marginBottom: 32, textAlign: 'left', maxWidth: 460, margin: '0 auto 32px' }}>
                {['Usuarios ilimitados', 'Múltiples empresas', 'Backups diarios', 'Soporte WhatsApp', 'Actualizaciones', 'Capacitación inicial'].map(item => (
                  <div key={item} style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 13, color: 'var(--text-2)' }}>
                    <span style={{ color: 'var(--accent)', fontWeight: 700 }}>✓</span>{item}
                  </div>
                ))}
              </div>
              <a href="#contacto" className="btn-green large" style={{ textDecoration: 'none' }}>Consultar precio →</a>
            </div>
          </R>
        </div>
      </section>

      {/* ── CONTACTO ── */}
      <section id="contacto" className="section">
        <div style={{ maxWidth: 480, margin: '0 auto', textAlign: 'center' }}>
          <R>
            <div className="sec-label">Contacto</div>
            <h2 className="section-title">¿Querés implementar <em className="em-serif">Cuadra?</em></h2>
            <p style={{ color: 'var(--muted)', fontSize: 15, lineHeight: 1.6, marginBottom: 32 }}>
              Escribime por WhatsApp y en menos de una semana tu empresa está operativa.
            </p>
            <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'center', gap: 0, marginBottom: 36, flexWrap: 'nowrap' }}>
              {[
                { n: '1', label: 'Me escribís', sub: 'por WhatsApp' },
                { n: '2', label: 'Demo de 10 min', sub: 'el sistema en vivo' },
                { n: '3', label: 'Tu empresa lista', sub: 'operativo en 24hs' },
              ].map((step, i) => (
                <React.Fragment key={step.n}>
                  <div style={{ textAlign: 'center', padding: '0 12px', minWidth: 90 }}>
                    <div style={{ width: 32, height: 32, borderRadius: '50%', background: 'var(--accent-soft)', border: '1px solid var(--accent-line)', color: 'var(--accent)', fontWeight: 700, fontSize: 13, display: 'inline-flex', alignItems: 'center', justifyContent: 'center', marginBottom: 8 }}>{step.n}</div>
                    <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--text)' }}>{step.label}</div>
                    <div style={{ fontSize: 11, color: 'var(--muted-2)', marginTop: 2 }}>{step.sub}</div>
                  </div>
                  {i < 2 && <div style={{ display: 'flex', alignItems: 'center', color: 'var(--muted-2)', fontSize: 16, paddingBottom: 22, paddingTop: 6 }}>→</div>}
                </React.Fragment>
              ))}
            </div>
            <a href={WA_LINK} target="_blank" rel="noopener noreferrer" className="wa-btn" style={{ display: 'inline-flex', fontSize: 16, padding: '15px 32px' }}>
              <svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor"><path d="M17.472 14.382c-.297-.149-1.758-.867-2.03-.967-.273-.099-.471-.148-.67.15-.197.297-.767.966-.94 1.164-.173.199-.347.223-.644.075-.297-.15-1.255-.463-2.39-1.475-.883-.788-1.48-1.761-1.653-2.059-.173-.297-.018-.458.13-.606.134-.133.298-.347.446-.52.149-.174.198-.298.298-.497.099-.198.05-.371-.025-.52-.075-.149-.669-1.612-.916-2.207-.242-.579-.487-.5-.669-.51-.173-.008-.371-.01-.57-.01-.198 0-.52.074-.792.372-.272.297-1.04 1.016-1.04 2.479 0 1.462 1.065 2.875 1.213 3.074.149.198 2.096 3.2 5.077 4.487.709.306 1.262.489 1.694.625.712.227 1.36.195 1.871.118.571-.085 1.758-.719 2.006-1.413.248-.694.248-1.289.173-1.413-.074-.124-.272-.198-.57-.347m-5.421 7.403h-.004a9.87 9.87 0 01-5.031-1.378l-.361-.214-3.741.982.998-3.648-.235-.374a9.86 9.86 0 01-1.51-5.26c.001-5.45 4.436-9.884 9.888-9.884 2.64 0 5.122 1.03 6.988 2.898a9.825 9.825 0 012.893 6.994c-.003 5.45-4.437 9.884-9.885 9.884m8.413-18.297A11.815 11.815 0 0012.05 0C5.495 0 .16 5.335.157 11.892c0 2.096.547 4.142 1.588 5.945L.057 24l6.305-1.654a11.882 11.882 0 005.683 1.448h.005c6.554 0 11.89-5.335 11.893-11.893a11.821 11.821 0 00-3.48-8.413z"/></svg>
              Escribime por WhatsApp
            </a>
          </R>
        </div>
      </section>

      {/* ── FOOTER ── */}
      <footer style={{ padding: '32px 20px', borderTop: '1px solid var(--border-soft)', textAlign: 'center' }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 8, marginBottom: 14 }}>
          <span style={{ color: 'var(--accent)' }}><Logo size={20} /></span>
          <span style={{ fontWeight: 700, color: 'var(--accent)', fontSize: 14 }}>Cuadra</span>
        </div>
        <div style={{ display: 'flex', gap: 24, justifyContent: 'center', marginBottom: 12 }}>
          <Link to="/privacidad" className="footer-link">Privacidad</Link>
          <Link to="/terminos" className="footer-link">Términos</Link>
        </div>
        <span style={{ fontSize: 11, color: 'var(--muted-2)' }}>© {new Date().getFullYear()} Julieta Arrazate</span>
      </footer>
    </div>
  )
}
