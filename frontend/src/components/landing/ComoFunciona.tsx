import React from 'react'
import { IconArrow, Reveal } from './shared'
import { PASOS } from './data'

export const ComoFunciona: React.FC = () => (
  <section id="como-funciona" className="l-section alt">
    <div className="l-wrap">
      <Reveal className="l-head">
        <span className="l-eyebrow">Cómo funciona</span>
        <h2 className="l-h2">Del extracto al cierre, en tres pasos.</h2>
        <p className="l-lead">No hace falta que cambien tu banco ni tus clientes: Cuadra se adapta a lo que ya te mandan.</p>
      </Reveal>
      <Reveal className="l-steps-wrap">
        <span className="l-steps-line" aria-hidden="true"><i /></span>
        <ol className="l-steps">
          {PASOS.map((p, i) => (
            <li key={p.titulo} className="l-step">
              <span className="l-step-n" aria-hidden="true">{String(i + 1).padStart(2, '0')}</span>
              <h3 className="l-h3">{p.titulo}</h3>
              <p className="l-body">{p.texto}</p>
            </li>
          ))}
        </ol>
      </Reveal>
      <Reveal className="l-inline-cta">
        <a href="#demo" className="l-btn primary">Pedí una demo <IconArrow size={16} /></a>
        <p>Te mostramos el sistema en vivo, en 20 minutos.</p>
      </Reveal>
    </div>
  </section>
)
