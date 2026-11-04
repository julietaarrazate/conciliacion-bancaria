import React from 'react'
import { IconArrow, IconCheck, Reveal } from './shared'
import { PRECIO_INCLUYE } from './data'

export const Pricing: React.FC = () => (
  <section id="precio" className="l-section">
    <div className="l-wrap">
      <Reveal>
        <div className="l-price">
          <div>
            <span className="l-eyebrow">Precio</span>
            <h2 className="l-h2">Un precio según tu volumen.</h2>
            <p className="l-lead">Depende de cuántas empresas y clientes manejás. Te pasamos la propuesta después de la demo, sin letra chica.</p>
            <div style={{ marginTop: 28 }}>
              <a href="#demo" className="l-btn primary">Pedí tu propuesta <IconArrow size={16} /></a>
            </div>
          </div>
          <ul className="l-price-list" aria-label="Qué incluye">
            {PRECIO_INCLUYE.map(item => <li key={item}><IconCheck size={16} />{item}</li>)}
          </ul>
        </div>
      </Reveal>
    </div>
  </section>
)
