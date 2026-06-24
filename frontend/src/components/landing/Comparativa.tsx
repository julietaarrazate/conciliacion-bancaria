import React from 'react'
import { R } from './shared'
import { COMPARISON } from './data'

export const Comparativa: React.FC = () => (
  <section className="section">
    <div style={{ maxWidth: 900, margin: '0 auto' }}>
      <R>
        <div style={{ textAlign: 'center', marginBottom: 44 }}>
          <div className="sec-label">Comparativa</div>
          <h2 className="section-title">Excel manual<br />vs <em className="em-serif">Cuadra</em></h2>
          <p style={{ color: 'var(--muted)', fontSize: 15 }}>Si hoy hacés todo en planillas, esto te interesa.</p>
        </div>
      </R>
      <R delay={100}>
        <div style={{ overflowX: 'auto', borderRadius: 12 }}>
          <table className="compare-table">
            <thead>
              <tr><th>Tarea</th><th>Excel manual</th><th>Cuadra</th></tr>
            </thead>
            <tbody>
              {COMPARISON.map(c => (
                <tr key={c.feature}>
                  <td className="feature">{c.feature}</td>
                  <td className="excel">{c.excel}</td>
                  <td className="cuadra">✓ {c.cuadra}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </R>
    </div>
  </section>
)
