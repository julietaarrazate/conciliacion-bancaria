import React, { useState } from 'react'
import { IconCheck, IconWhatsApp, Reveal, WA_LINK, mailLink, waLink } from './shared'
import { VOLUMENES } from './data'

export const MEDIOS = ['WhatsApp', 'Llamada', 'Mail'] as const
type Medio = typeof MEDIOS[number]

export type DatosDemo = { nombre: string; empresa: string; volumen: string; medio: Medio; contacto: string }

/** Mensaje que llega por WhatsApp (o por mail) con los datos del formulario. */
export function mensajeDemo(d: DatosDemo): string {
  return [
    'Hola Julieta, quiero pedir una demo de Cuadra.',
    `Nombre: ${d.nombre.trim()}`,
    `Empresa o estudio: ${d.empresa.trim()}`,
    `Volumen: ${d.volumen}`,
    `Prefiero que me contacten por ${d.medio}${d.contacto.trim() ? `: ${d.contacto.trim()}` : ''}`,
  ].join('\n')
}

const PLACEHOLDER: Record<Medio, string> = {
  WhatsApp: 'Si es otro número',
  Llamada: 'Tu teléfono',
  Mail: 'tu@empresa.com.ar',
}

export const PedirDemo: React.FC = () => {
  const [d, setD] = useState<DatosDemo>({ nombre: '', empresa: '', volumen: VOLUMENES[0], medio: 'WhatsApp', contacto: '' })
  const [error, setError] = useState('')
  const set = (k: keyof DatosDemo) => (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) =>
    setD(prev => ({ ...prev, [k]: e.target.value }))

  const faltante = !d.nombre.trim() ? 'tu nombre'
    : !d.empresa.trim() ? 'la empresa o el estudio'
    : d.medio !== 'WhatsApp' && !d.contacto.trim() ? (d.medio === 'Mail' ? 'tu mail' : 'tu teléfono')
    : ''

  const enviar = (e: React.FormEvent) => {
    e.preventDefault()
    if (faltante) { setError(`Completá ${faltante}.`); return }
    setError('')
    window.open(waLink(mensajeDemo(d)), '_blank', 'noopener,noreferrer')
  }

  return (
    <section id="demo" className="l-section">
      <div className="l-wrap">
        <Reveal>
          <div className="l-close">
            <div className="l-close-grid">
              <div>
                <span className="l-eyebrow">Pedí una demo</span>
                <h2 className="l-h2">Mirá tus números cuadrar.</h2>
                <p className="l-lead">Dejanos tus datos y te escribimos para coordinar. La demo es en vivo y dura 20 minutos.</p>
                <ul className="l-close-points">
                  <li><IconCheck size={16} />Te mostramos una conciliación completa</li>
                  <li><IconCheck size={16} />Puesta en marcha y capacitación incluidas</li>
                  <li><IconCheck size={16} />Soporte directo, sin intermediarios</li>
                </ul>
                <p className="l-form-note" style={{ textAlign: 'left', marginTop: 28 }}>
                  ¿Preferís hablar directo?{' '}
                  <a className="l-link" href={WA_LINK} target="_blank" rel="noopener noreferrer">
                    <IconWhatsApp size={14} /> Escribinos por WhatsApp
                  </a>
                </p>
              </div>

              <form className="l-form" onSubmit={enviar} noValidate aria-label="Pedir una demo">
                <div className="l-field">
                  <label htmlFor="demo-nombre">Nombre</label>
                  <input id="demo-nombre" name="nombre" autoComplete="name" placeholder="Tu nombre" value={d.nombre} onChange={set('nombre')} required />
                </div>
                <div className="l-field">
                  <label htmlFor="demo-empresa">Empresa o estudio</label>
                  <input id="demo-empresa" name="empresa" autoComplete="organization" placeholder="Ej.: Estudio Pérez" value={d.empresa} onChange={set('empresa')} required />
                </div>
                <div className="l-field">
                  <label htmlFor="demo-volumen">¿Cuántos clientes te pagan por banco?</label>
                  <select id="demo-volumen" name="volumen" value={d.volumen} onChange={set('volumen')}>
                    {VOLUMENES.map(v => <option key={v}>{v}</option>)}
                  </select>
                </div>
                <div className="l-field-row">
                  <div className="l-field">
                    <label htmlFor="demo-medio">¿Cómo te contactamos?</label>
                    <select id="demo-medio" name="medio" value={d.medio} onChange={set('medio')}>
                      {MEDIOS.map(m => <option key={m}>{m}</option>)}
                    </select>
                  </div>
                  <div className="l-field">
                    <label htmlFor="demo-contacto">{d.medio === 'Mail' ? 'Tu mail' : 'Tu teléfono'}{d.medio === 'WhatsApp' ? ' (opcional)' : ''}</label>
                    <input id="demo-contacto" name="contacto" type={d.medio === 'Mail' ? 'email' : 'tel'}
                      autoComplete={d.medio === 'Mail' ? 'email' : 'tel'} placeholder={PLACEHOLDER[d.medio]}
                      value={d.contacto} onChange={set('contacto')} />
                  </div>
                </div>
                {error && <p className="l-form-error" role="alert">{error}</p>}
                <button type="submit" className="l-btn primary"><IconWhatsApp size={18} /> Pedir demo por WhatsApp</button>
                <p className="l-form-note">
                  Se abre WhatsApp con el mensaje listo: solo tenés que enviarlo.{' '}
                  <a href={mailLink('Quiero una demo de Cuadra', mensajeDemo(d))}>Prefiero mandarlo por mail</a>
                </p>
              </form>
            </div>
          </div>
        </Reveal>
      </div>
    </section>
  )
}
