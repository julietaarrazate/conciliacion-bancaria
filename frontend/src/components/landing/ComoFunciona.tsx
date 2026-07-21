import React from 'react'
import { R } from './shared'
import { COMO_FUNCIONA } from './data'

export const ComoFunciona: React.FC = () => (
  <section id="como-funciona" className="section" style={{ background: 'var(--bg-soft)' }}>
    <div style={{ maxWidth: 960, margin: '0 auto' }}>
      <R>
        <div style={{ textAlign: 'center', marginBottom: 52 }}>
          <div className="sec-label" style={{ justifyContent: 'center' }}>Cómo funciona</div>
          <h2 className="section-title">Tres pasos, no un curso<br /><em className="em-serif">de Excel.</em></h2>
        </div>
      </R>
      <div className="steps-grid">
        {COMO_FUNCIONA.map((s, i) => (
          <R key={s.n} delay={i * 80}>
            <div>
              <div className="step-num">{s.n}</div>
              <div style={{ fontWeight: 700, fontSize: 17, marginBottom: 8, color: 'var(--text)' }}>{s.title}</div>
              <div style={{ fontSize: 14, color: 'var(--muted)', lineHeight: 1.7 }}>{s.desc}</div>
            </div>
          </R>
        ))}
      </div>
    </div>
  </section>
)
