import React from 'react'
import { StatCounter } from './StatCounter'
import { STATS } from './data'

export const StatsSection: React.FC = () => (
  <section style={{ padding: '0 20px 72px' }}>
    <div style={{ maxWidth: 900, margin: '0 auto' }}>
      <div className="stats-grid">
        {STATS.map((s, i) => <StatCounter key={s.label} {...s} delay={i * 150} />)}
      </div>
    </div>
  </section>
)
