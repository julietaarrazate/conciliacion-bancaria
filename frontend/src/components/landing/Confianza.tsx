import React from 'react'
import { IconBuilding, IconCheque, IconCloud, IconList, IconLock, IconTransfer, IconUsers, Reveal } from './shared'
import { CASOS, CONFIANZA } from './data'

const CASO_ICON = [IconBuilding, IconTransfer, IconCheque]
const CONF_ICON = [IconLock, IconCloud, IconList, IconUsers]

export const Confianza: React.FC = () => (
  <section id="para-quien" className="l-section alt">
    <div className="l-wrap">
      <Reveal className="l-head">
        <span className="l-eyebrow">Para quién es</span>
        <h2 className="l-h2">Hecho para quien vive conciliando.</h2>
        <p className="l-lead">Si cobrás por banco a muchos clientes, o llevás los bancos de varias empresas, esto es para vos.</p>
      </Reveal>
      <div className="l-cases">
        {CASOS.map((c, i) => {
          const Icon = CASO_ICON[i]
          return (
            <Reveal key={c.tag} delay={i * 70}>
              <article className="l-case">
                <h3 className="l-case-tag"><Icon size={18} />{c.tag}</h3>
                <p>{c.texto}</p>
              </article>
            </Reveal>
          )
        })}
      </div>
      <Reveal>
        <ul className="l-trust" aria-label="Seguridad de tus datos" style={{ listStyle: 'none', padding: 0, marginBottom: 0 }}>
          {CONFIANZA.map((c, i) => {
            const Icon = CONF_ICON[i]
            return (
              <li key={c.titulo} style={{ display: 'flex' }}>
                <Icon size={20} />
                <div><b>{c.titulo}</b><span>{c.texto}</span></div>
              </li>
            )
          })}
        </ul>
      </Reveal>
    </div>
  </section>
)
