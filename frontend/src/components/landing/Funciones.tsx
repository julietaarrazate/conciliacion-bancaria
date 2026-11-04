import React from 'react'
import { IconCheck, Reveal } from './shared'
import { FUNCIONES } from './data'

const Tile: React.FC<{ titulo: string; texto: string; viz: React.ReactNode; wide?: boolean; delay?: number }> = ({
  titulo, texto, viz, wide, delay = 0,
}) => (
  <Reveal className={wide ? 'wide' : ''} delay={delay}>
    <article className="l-tile">
      <div className="l-viz" aria-hidden="true">{viz}</div>
      <div className="l-tile-copy">
        <h3 className="l-h3">{titulo}</h3>
        <p className="l-body">{texto}</p>
      </div>
    </article>
  </Reveal>
)

// Mini réplica de la tarjeta "Control del banco" de Contabilidad (mismos textos).
const VizControl = () => (
  <div className="v-ctrl hd-card" style={{ boxShadow: 'var(--shadow-card)' }}>
    <div className="hd-ctrl-head">
      <span className="hd-ctrl-title">Control del banco</span>
      <span className="hd-ctrl-badge" style={{ opacity: 1, transform: 'none' }}><IconCheck size={13} /></span>
    </div>
    <div className="hd-ctrl-status"><span style={{ color: 'var(--ok-text)' }}>El banco en libros coincide con el extracto</span></div>
    <div className="hd-ctrl-grid">
      <div><small>Cobros a imputar</small><span className="num">$ 0,00</span></div>
      <div><small>Pagos a imputar</small><span className="num">$ 0,00</span></div>
    </div>
  </div>
)

const VizAlertas = () => (
  <div className="v-notif">
    <div><span className="dot" style={{ background: '#F59E0B' }} /><span><b>2 cheques vencen el jueves</b>Ferretería Lima SRL · $ 250.000,00</span></div>
    <div><span className="dot" style={{ background: 'var(--accent)' }} /><span><b>Vence IVA en 3 días</b>Período septiembre</span></div>
  </div>
)

const VizCheque = () => (
  <div className="v-fields">
    {[['Número', '10483'], ['Banco', 'Galicia'], ['Librador', 'Ferretería Lima SRL'], ['Monto', '$ 250.000,00']].map(([k, v]) => (
      <div key={k}><span>{k}</span><b className={k === 'Monto' || k === 'Número' ? 'num' : ''}>{v}</b></div>
    ))}
  </div>
)

const VizFactura = () => (
  <div className="v-fields">
    {[['Factura A', '0003-00012874'], ['Neto', '$ 120.000,00'], ['IVA 21%', '$ 25.200,00']].map(([k, v]) => (
      <div key={k}><span>{k}</span><b className="num">{v}</b></div>
    ))}
  </div>
)

const VizImpuestos = () => (
  <div className="v-chips">
    {['IVA', 'Ingresos Brutos', 'Monotributo', 'Sueldos y F.931', 'Cierre en PDF'].map(t => (
      <span key={t}><IconCheck size={13} />{t}</span>
    ))}
  </div>
)

export const Funciones: React.FC = () => (
  <section id="funciones" className="l-section">
    <div className="l-wrap">
      <Reveal className="l-head">
        <span className="l-eyebrow">Funciones</span>
        <h2 className="l-h2">Todo lo que pasa por el banco, en un solo lugar.</h2>
        <p className="l-lead">Además de conciliar, Cuadra lleva los cheques, las facturas de compra y los impuestos del mes.</p>
      </Reveal>
      <div className="l-bento">
        <Tile wide viz={<VizControl />} {...FUNCIONES.control} />
        <Tile delay={60} viz={<VizAlertas />} {...FUNCIONES.alertas} />
        <Tile viz={<VizCheque />} {...FUNCIONES.cheques} />
        <Tile delay={60} viz={<VizFactura />} {...FUNCIONES.facturas} />
        <Tile delay={120} viz={<VizImpuestos />} {...FUNCIONES.impuestos} />
      </div>
    </div>
  </section>
)
