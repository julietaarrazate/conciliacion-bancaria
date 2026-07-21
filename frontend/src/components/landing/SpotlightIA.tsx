import React from 'react'
import { R, LazyMount } from './shared'
import { AlertaMockup } from './AlertaMockup'

export const SpotlightIA: React.FC = () => (
  <section className="section">
    <div className="spotlight">
      <R className="spotlight-text">
        <div className="sec-label">03 · Asistente IA</div>
        <h2 style={{ fontSize: 'clamp(24px,5vw,38px)', fontWeight: 700, letterSpacing: '-1.2px', lineHeight: 1.12, marginBottom: 16 }}>
          Preguntás en<br />
          <em className="em-serif">lenguaje natural.</em>
        </h2>
        <p style={{ color: 'var(--muted)', lineHeight: 1.7, marginBottom: 22, fontSize: 14 }}>
          El asistente IA tiene acceso a tus datos reales. Consultá saldos, comisiones del mes, cheques por vencer o movimientos sin conciliar — con tu voz o escribiendo.
        </p>
        <ul style={{ listStyle: 'none', padding: 0, margin: 0, display: 'flex', flexDirection: 'column', gap: 10 }}>
          {['Dictado por voz desde el celular', 'Alertas automáticas de cheques y movimientos', 'Consultas de comisión y liquidaciones', 'Disponible en todas las pantallas del sistema'].map(item => (
            <li key={item} style={{ display: 'flex', alignItems: 'center', gap: 10, fontSize: 14, color: 'var(--text-2)' }}>
              <span style={{ color: 'var(--accent)', fontWeight: 700 }}>✓</span>{item}
            </li>
          ))}
        </ul>
      </R>
      <R delay={100} className="spotlight-mock"><LazyMount><AlertaMockup /></LazyMount></R>
    </div>
  </section>
)
