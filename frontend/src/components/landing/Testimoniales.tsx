import React from 'react'
import { R } from './shared'
import { TESTIMONIALES } from './data'

export const Testimoniales: React.FC = () => (
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
)
