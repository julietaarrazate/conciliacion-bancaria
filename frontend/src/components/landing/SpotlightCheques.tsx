import React from 'react'
import { R, LazyMount } from './shared'
import { OCRMockup } from './OCRMockup'

export const SpotlightCheques: React.FC = () => (
  <section className="section" style={{ background: 'var(--bg-2)', borderTop: '1px solid var(--border-soft)', borderBottom: '1px solid var(--border-soft)' }}>
    <div className="spotlight reverse">
      <R className="spotlight-mock"><LazyMount><OCRMockup /></LazyMount></R>
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
)
