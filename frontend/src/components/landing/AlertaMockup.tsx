import React, { useEffect, useRef, useState } from 'react'

export const AlertaMockup: React.FC = () => {
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
        <div style={{ width: 32, height: 32, borderRadius: 8, background: 'var(--accent-soft)', display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0 }}>
          <svg width="16" height="16" fill="none" stroke="currentColor" strokeWidth={1.8} strokeLinecap="round" strokeLinejoin="round" viewBox="0 0 24 24" style={{ color: 'var(--accent)' }}><path d="M14.857 17.082a23.848 23.848 0 005.454-1.31A8.967 8.967 0 0118 9.75v-.7V9A6 6 0 006 9v.75a8.967 8.967 0 01-2.312 6.022c1.733.64 3.56 1.085 5.455 1.31m5.714 0a24.255 24.255 0 01-5.714 0m5.714 0a3 3 0 11-5.714 0"/></svg>
        </div>
        <div>
          <div style={{ fontSize: 12, fontWeight: 700, color: 'var(--text)', marginBottom: 2 }}>Cuadra · Alerta automática</div>
          <div style={{ fontSize: 11, color: 'var(--muted)', lineHeight: 1.5 }}>2 cheques vencen mañana — Comercial Norte ($124.500) y Logística Central ($98.400)</div>
        </div>
      </div>
      <div style={{ padding: '12px 14px', display: 'flex', flexDirection: 'column', gap: 8, minHeight: 148 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 2 }}>
          <span style={{ fontSize: 11, fontWeight: 600, color: 'var(--accent)' }}>Asistente IA Cuadra</span>
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
            <span style={{ fontSize: 12, color: 'var(--text)' }}>Perfecto, generá la liquidación</span>
          </div>
        )}
      </div>
    </div>
  )
}
