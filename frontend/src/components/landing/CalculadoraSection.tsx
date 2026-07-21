import React from 'react'
import { R } from './shared'
import { Calculadora } from './Calculadora'

export const CalculadoraSection: React.FC = () => (
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
)
