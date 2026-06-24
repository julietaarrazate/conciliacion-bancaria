import React, { useEffect, useRef, useState } from 'react'
import { Logo } from './shared'

const OCR_FIELDS = [
  { label: 'Número',     value: '05812346' },
  { label: 'Banco',      value: 'Macro' },
  { label: 'Librador',   value: 'Constructora Sur SA' },
  { label: 'Monto',      value: '$212.000,00' },
  { label: 'Vencimiento', value: '15/06/2026' },
]

export const OCRMockup: React.FC = () => {
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
        <span style={{ marginLeft: 'auto', fontSize: 10, padding: '2px 8px', borderRadius: 6, background: 'var(--accent-soft)', color: 'var(--accent)', fontWeight: 700 }}>OCR IA</span>
      </div>
      <div style={{ padding: 16 }}>
        <div style={{ borderRadius: 12, overflow: 'hidden', marginBottom: 14, position: 'relative', background: 'var(--bg-2)', border: `2px dashed ${phase === 'scanning' ? 'var(--accent)' : 'var(--border)'}`, height: 86, display: 'flex', alignItems: 'center', justifyContent: 'center', transition: 'border-color 0.3s' }}>
          {phase === 'idle' && <div style={{ textAlign: 'center' }}>
            <svg width="22" height="22" fill="none" stroke="currentColor" strokeWidth={1.6} strokeLinecap="round" strokeLinejoin="round" viewBox="0 0 24 24" style={{ color: 'var(--muted-2)', margin: '0 auto' }}><path d="M6.827 6.175A2.31 2.31 0 015.186 7.23c-.38.054-.757.112-1.134.175C2.999 7.58 2.25 8.507 2.25 9.574V18a2.25 2.25 0 002.25 2.25h15A2.25 2.25 0 0021.75 18V9.574c0-1.067-.75-1.994-1.802-2.169a47.865 47.865 0 00-1.134-.175 2.31 2.31 0 01-1.64-1.055l-.822-1.316a2.192 2.192 0 00-1.736-1.039 48.774 48.774 0 00-5.232 0 2.192 2.192 0 00-1.736 1.039l-.821 1.316z"/><path d="M16.5 12.75a4.5 4.5 0 11-9 0 4.5 4.5 0 019 0zM18.75 10.5h.008v.008h-.008V10.5z"/></svg>
            <div style={{ fontSize: 11, color: 'var(--muted-2)', marginTop: 4 }}>Adjuntar foto del cheque</div>
          </div>}
          {phase === 'scanning' && (
            <div style={{ textAlign: 'center' }}>
              <svg width="22" height="22" fill="none" stroke="currentColor" strokeWidth={1.6} strokeLinecap="round" strokeLinejoin="round" viewBox="0 0 24 24" style={{ color: 'var(--accent)', margin: '0 auto' }}><path d="M21 21l-5.197-5.197m0 0A7.5 7.5 0 105.196 15.803a7.5 7.5 0 0010.607 10.607z"/></svg>
              <div style={{ fontSize: 11, color: 'var(--accent)', marginTop: 4, fontWeight: 600 }}>Escaneando con IA…</div>
              <div style={{ position: 'absolute', top: 0, left: 0, right: 0, height: 2, background: 'linear-gradient(90deg, transparent, var(--accent), transparent)', animation: 'scanLine 0.9s ease-in-out infinite' }} />
            </div>
          )}
          {phase === 'done' && <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <svg width="18" height="18" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" viewBox="0 0 24 24" style={{ color: 'var(--accent)', flexShrink: 0 }}><path d="M9 12.75L11.25 15 15 9.75M21 12a9 9 0 11-18 0 9 9 0 0118 0z"/></svg>
            <span style={{ fontSize: 12, color: 'var(--accent)', fontWeight: 600 }}>Datos extraídos</span>
          </div>}
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
