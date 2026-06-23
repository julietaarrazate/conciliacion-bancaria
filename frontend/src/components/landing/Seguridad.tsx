import React from 'react'
import { R } from './shared'
import { SECURITY } from './data'

export const Seguridad: React.FC = () => (
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
