import React from 'react'
import { R, LazyMount } from './shared'
import { ConciliacionMockup } from './ConciliacionMockup'

export const SpotlightConciliacion: React.FC = () => (
  <section id="producto" className="section">
    <div className="spotlight">
      <R className="spotlight-text">
        <div className="sec-label">El producto</div>
        <h2 style={{ fontSize: 'clamp(24px,5vw,38px)', fontWeight: 700, letterSpacing: '-1.2px', lineHeight: 1.12, marginBottom: 16 }}>
          Subís el extracto.<br />
          <em className="em-serif">Cuadra solo.</em>
        </h2>
        <p style={{ color: 'var(--muted)', lineHeight: 1.7, marginBottom: 22, fontSize: 14 }}>
          El motor de conciliación cruza tu extracto bancario contra cada planilla por CUIT, CBU y referencia. Lo que coincide se marca automáticamente. Lo ambiguo queda para que vos decidás.
        </p>
        <ul style={{ listStyle: 'none', padding: 0, margin: 0, display: 'flex', flexDirection: 'column', gap: 10 }}>
          {['16 bancos argentinos + Mercado Pago', 'Detección de duplicados automática', 'Export Excel para el contador en un click', 'PDF de cierre mensual incluido'].map(item => (
            <li key={item} style={{ display: 'flex', alignItems: 'center', gap: 10, fontSize: 14, color: 'var(--text-2)' }}>
              <span style={{ color: 'var(--accent)', fontWeight: 700 }}>✓</span>{item}
            </li>
          ))}
        </ul>
      </R>
      <R delay={100} className="spotlight-mock"><LazyMount><ConciliacionMockup /></LazyMount></R>
    </div>
  </section>
)
