import React, { useEffect, useRef, useState } from 'react'
import { Logo } from './shared'

const CONCIL_ROWS = [
  { cliente: 'Comercial Norte SRL', importe: '$124.500', cuit: '30-71234567-8' },
  { cliente: 'Distribuidora Sur',   importe: '$89.200',  cuit: '20-28345678-9' },
  { cliente: 'Constructora Este SA', importe: '$212.000', cuit: '30-69123456-7' },
  { cliente: 'Servicios del Oeste', importe: '$56.800',  cuit: '27-34567890-1' },
  { cliente: 'Logística Central',   importe: '$98.400',  cuit: '30-70987654-3' },
]

export const ConciliacionMockup: React.FC = () => {
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
