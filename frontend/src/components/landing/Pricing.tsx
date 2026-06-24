import React from 'react'
import { R } from './shared'

export const Pricing: React.FC = () => (
  <section className="section" style={{ background: 'var(--bg-2)', borderTop: '1px solid var(--border-soft)', borderBottom: '1px solid var(--border-soft)' }}>
    <div style={{ maxWidth: 640, margin: '0 auto' }}>
      <R>
        <div style={{ textAlign: 'center', marginBottom: 40 }}>
          <div className="sec-label">Precio</div>
          <h2 className="section-title">Una propuesta a <em className="em-serif">tu medida</em></h2>
          <p style={{ color: 'var(--muted)', fontSize: 15, maxWidth: 440, margin: '0 auto', lineHeight: 1.6 }}>
            El precio se ajusta a la cantidad de empresas, usuarios y volumen de operaciones. Sin sorpresas.
          </p>
        </div>
      </R>
      <R delay={100}>
        <div className="grad-border" style={{ padding: '36px 28px', textAlign: 'center' }}>
          <div style={{ display: 'inline-block', padding: '5px 12px', borderRadius: 999, background: 'var(--accent-soft)', border: '1px solid var(--accent-line)', color: 'var(--accent)', fontSize: 11, fontWeight: 600, marginBottom: 18, letterSpacing: '0.06em', textTransform: 'uppercase' }}>
            Onboarding incluido
          </div>
          <h3 style={{ fontSize: 22, fontWeight: 700, marginBottom: 8, letterSpacing: '-0.5px' }}>Plan empresa</h3>
          <p style={{ color: 'var(--muted)', fontSize: 14, marginBottom: 28, maxWidth: 340, marginLeft: 'auto', marginRight: 'auto', lineHeight: 1.6 }}>
            Implementación, capacitación al equipo y soporte directo.
          </p>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))', gap: 12, marginBottom: 32, textAlign: 'left', maxWidth: 460, margin: '0 auto 32px' }}>
            {['Usuarios ilimitados', 'Múltiples empresas', 'Backups diarios', 'Soporte WhatsApp', 'Actualizaciones', 'Capacitación inicial'].map(item => (
              <div key={item} style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 13, color: 'var(--text-2)' }}>
                <span style={{ color: 'var(--accent)', fontWeight: 700 }}>✓</span>{item}
              </div>
            ))}
          </div>
          <a href="#contacto" className="btn-green large" style={{ textDecoration: 'none' }}>Consultar precio →</a>
        </div>
      </R>
    </div>
  </section>
)
