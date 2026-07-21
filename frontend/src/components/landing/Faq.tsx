import React from 'react'
import { R } from './shared'
import { FAQ } from './data'

export const Faq: React.FC<{
  faqOpen: number | null
  setFaqOpen: React.Dispatch<React.SetStateAction<number | null>>
}> = ({ faqOpen, setFaqOpen }) => (
  <section id="faq" className="section">
    <div style={{ maxWidth: 720, margin: '0 auto' }}>
      <R>
        <div style={{ textAlign: 'center', marginBottom: 44 }}>
          <div className="sec-label">FAQ</div>
          <h2 className="section-title">Todo lo que querés <em className="em-serif">saber</em></h2>
        </div>
      </R>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
        {FAQ.map((item, i) => (
          <R key={i} delay={i * 40}>
            <div className="faq-item">
              <button className="faq-q" onClick={() => setFaqOpen(faqOpen === i ? null : i)} aria-expanded={faqOpen === i}>
                <span>{item.q}</span>
                <span className={`faq-q-icon ${faqOpen === i ? 'open' : ''}`}>+</span>
              </button>
              {faqOpen === i && <div className="faq-a">{item.a}</div>}
            </div>
          </R>
        ))}
      </div>
      <R delay={300}>
        <div style={{ textAlign: 'center', marginTop: 36, fontSize: 14, color: 'var(--muted)' }}>
          ¿Tu pregunta no está acá?{' '}
          <a href="#contacto" style={{ color: 'var(--accent)', fontWeight: 600, textDecoration: 'none' }}>Escribime →</a>
        </div>
      </R>
    </div>
  </section>
)
