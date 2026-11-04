import React, { useId, useState } from 'react'
import { IconPlus, Reveal, WA_LINK } from './shared'
import { FAQ } from './data'

export const Faq: React.FC = () => {
  const [open, setOpen] = useState<number | null>(0)
  const base = useId()
  return (
    <section id="preguntas" className="l-section alt">
      <div className="l-wrap l-faq-grid">
        <Reveal>
          <span className="l-eyebrow">Preguntas frecuentes</span>
          <h2 className="l-h2">Lo que más nos preguntan.</h2>
          <p className="l-lead">
            ¿Te quedó otra duda?{' '}
            <a className="l-link" href={WA_LINK} target="_blank" rel="noopener noreferrer">Escribinos por WhatsApp</a>.
          </p>
        </Reveal>
        <Reveal delay={80}>
          <div className="l-faq">
            {FAQ.map((item, i) => {
              const abierto = open === i
              return (
                <div key={item.q} className="l-faq-item">
                  <h3 style={{ margin: 0 }}>
                    <button type="button" className="l-faq-q" aria-expanded={abierto} aria-controls={`${base}-${i}`}
                      onClick={() => setOpen(abierto ? null : i)}>
                      <span>{item.q}</span>
                      <IconPlus size={18} />
                    </button>
                  </h3>
                  <p id={`${base}-${i}`} className="l-faq-a" hidden={!abierto}>{item.a}</p>
                </div>
              )
            })}
          </div>
        </Reveal>
      </div>
    </section>
  )
}
