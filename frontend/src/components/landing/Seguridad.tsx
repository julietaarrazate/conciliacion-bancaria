import React from 'react'
import { R } from './shared'
import { CONFIANZA } from './data'

export const Seguridad: React.FC = () => (
  <section id="confianza" className="section">
    <div style={{ maxWidth: 1000, margin: '0 auto' }}>
      <R>
        <div style={{ textAlign: 'center', marginBottom: 52 }}>
          <div className="sec-label" style={{ justifyContent: 'center' }}>Por qué confiar los números de tus clientes acá</div>
          <h2 className="section-title">Rigor contable,<br /><em className="em-serif">no promesa de marketing.</em></h2>
          <p style={{ color: 'var(--muted)', fontSize: 15, maxWidth: 560, margin: '0 auto' }}>
            Son prácticas de ingeniería concretas, no eslóganes: podés verificarlas en el código.
          </p>
        </div>
      </R>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(260px, 1fr))', gap: 14 }}>
        {CONFIANZA.map((s, i) => (
          <R key={s.title} delay={i * 60}>
            <div className="grad-border" style={{ padding: 24, height: '100%', boxSizing: 'border-box' }}>
              <div style={{ marginBottom: 10 }}>{s.icon}</div>
              <div style={{ fontWeight: 700, fontSize: 14, marginBottom: 7, color: 'var(--text)' }}>{s.title}</div>
              <div style={{ fontSize: 13, color: 'var(--muted)', lineHeight: 1.65 }}>{s.desc}</div>
            </div>
          </R>
        ))}
      </div>
    </div>
  </section>
)
