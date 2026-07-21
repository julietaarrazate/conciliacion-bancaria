import React from 'react'
import { R, WA_LINK } from './shared'

export const Contacto: React.FC = () => (
  <section id="contacto" className="section">
    <div style={{ maxWidth: 480, margin: '0 auto', textAlign: 'center' }}>
      <R>
        <div className="sec-label">Contacto</div>
        <h2 className="section-title">¿Querés implementar <em className="em-serif">Cuadra?</em></h2>
        <p style={{ color: 'var(--muted)', fontSize: 15, lineHeight: 1.6, marginBottom: 32 }}>
          Escribime por WhatsApp y en menos de una semana tu empresa está operativa.
        </p>
        <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'center', gap: 0, marginBottom: 36, flexWrap: 'nowrap' }}>
          {[
            { n: '1', label: 'Me escribís', sub: 'por WhatsApp' },
            { n: '2', label: 'Demo de 10 min', sub: 'el sistema en vivo' },
            { n: '3', label: 'Tu empresa lista', sub: 'operativo en 24hs' },
          ].map((step, i) => (
            <React.Fragment key={step.n}>
              <div style={{ textAlign: 'center', padding: '0 12px', minWidth: 90 }}>
                <div style={{ width: 32, height: 32, borderRadius: '50%', background: 'var(--accent-soft)', border: '1px solid var(--accent-line)', color: 'var(--accent)', fontWeight: 700, fontSize: 13, display: 'inline-flex', alignItems: 'center', justifyContent: 'center', marginBottom: 8 }}>{step.n}</div>
                <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--text)' }}>{step.label}</div>
                <div style={{ fontSize: 11, color: 'var(--muted-2)', marginTop: 2 }}>{step.sub}</div>
              </div>
              {i < 2 && <div style={{ display: 'flex', alignItems: 'center', color: 'var(--muted-2)', fontSize: 16, paddingBottom: 22, paddingTop: 6 }}>→</div>}
            </React.Fragment>
          ))}
        </div>
        <a href={WA_LINK} target="_blank" rel="noopener noreferrer" className="wa-btn" style={{ display: 'inline-flex', fontSize: 16, padding: '15px 32px' }}>
          <svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor"><path d="M17.472 14.382c-.297-.149-1.758-.867-2.03-.967-.273-.099-.471-.148-.67.15-.197.297-.767.966-.94 1.164-.173.199-.347.223-.644.075-.297-.15-1.255-.463-2.39-1.475-.883-.788-1.48-1.761-1.653-2.059-.173-.297-.018-.458.13-.606.134-.133.298-.347.446-.52.149-.174.198-.298.298-.497.099-.198.05-.371-.025-.52-.075-.149-.669-1.612-.916-2.207-.242-.579-.487-.5-.669-.51-.173-.008-.371-.01-.57-.01-.198 0-.52.074-.792.372-.272.297-1.04 1.016-1.04 2.479 0 1.462 1.065 2.875 1.213 3.074.149.198 2.096 3.2 5.077 4.487.709.306 1.262.489 1.694.625.712.227 1.36.195 1.871.118.571-.085 1.758-.719 2.006-1.413.248-.694.248-1.289.173-1.413-.074-.124-.272-.198-.57-.347m-5.421 7.403h-.004a9.87 9.87 0 01-5.031-1.378l-.361-.214-3.741.982.998-3.648-.235-.374a9.86 9.86 0 01-1.51-5.26c.001-5.45 4.436-9.884 9.888-9.884 2.64 0 5.122 1.03 6.988 2.898a9.825 9.825 0 012.893 6.994c-.003 5.45-4.437 9.884-9.885 9.884m8.413-18.297A11.815 11.815 0 0012.05 0C5.495 0 .16 5.335.157 11.892c0 2.096.547 4.142 1.588 5.945L.057 24l6.305-1.654a11.882 11.882 0 005.683 1.448h.005c6.554 0 11.89-5.335 11.893-11.893a11.821 11.821 0 00-3.48-8.413z"/></svg>
          Escribime por WhatsApp
        </a>
      </R>
    </div>
  </section>
)
