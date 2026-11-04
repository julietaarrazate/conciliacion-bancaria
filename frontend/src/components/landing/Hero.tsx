import React from 'react'
import { IconArrow, IconCheck, IconWhatsApp, WA_LINK } from './shared'
import { HERO_FACTS } from './data'
import { HeroDemo } from './HeroDemo'

export const Hero: React.FC = () => (
  <section id="top" className="l-hero">
    <div className="l-wrap">
      <div className="l-hero-copy">
        <span className="l-eyebrow">Conciliación bancaria para estudios contables y empresas</span>
        <h1 className="l-h1">Los números cuadran solos.</h1>
        <p className="l-lead">
          Subís el extracto del banco y las planillas de pago de tus clientes, como te las manden.
          Cuadra cruza cada movimiento y te deja a mano solo lo que no cerró.
        </p>
        <div className="l-hero-ctas">
          <a href="#demo" className="l-btn primary">Pedí una demo <IconArrow size={16} /></a>
          <a href={WA_LINK} target="_blank" rel="noopener noreferrer" className="l-btn secondary">
            <IconWhatsApp size={17} /> Escribinos por WhatsApp
          </a>
        </div>
        <ul className="l-hero-facts">
          {HERO_FACTS.map(f => <li key={f}><IconCheck size={15} />{f}</li>)}
        </ul>
      </div>
      <div className="l-stage">
        <HeroDemo />
      </div>
    </div>
  </section>
)
