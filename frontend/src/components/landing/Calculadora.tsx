import React, { useState } from 'react'

export const Calculadora: React.FC = () => {
  const [planillas, setPlanillas] = useState(10)
  const [horasCada, setHorasCada] = useState(3)
  const horasSin = planillas * horasCada
  const horasCon = Math.round(planillas * 2 / 60 * 10) / 10
  const ahorro = Math.max(0, horasSin - horasCon)

  return (
    <div style={{ background: 'var(--card)', borderRadius: 18, border: '1px solid var(--border)', padding: '28px 24px', boxShadow: 'var(--mock-shadow)' }}>
      {[
        { label: 'Planillas por mes', val: `${planillas}`, min: 1, max: 300, cur: planillas, set: setPlanillas, unit: '' },
        { label: 'Horas por planilla (hoy)', val: `${horasCada}hs`, min: 1, max: 8, cur: horasCada, set: setHorasCada, unit: 'hs' },
      ].map((s, i) => (
        <div key={i} style={{ marginBottom: i === 0 ? 22 : 26 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
            <label style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-2)' }}>{s.label}</label>
            <span style={{ fontSize: 17, fontWeight: 800, color: 'var(--accent)', fontFamily: 'monospace' }}>{s.val}</span>
          </div>
          <input type="range" min={s.min} max={s.max} value={s.cur}
            onChange={e => s.set(+e.target.value)} className="calc-range" style={{ width: '100%' }} />
          <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: 3 }}>
            <span style={{ fontSize: 10, color: 'var(--muted-2)' }}>{s.min}{s.unit}</span>
            <span style={{ fontSize: 10, color: 'var(--muted-2)' }}>{s.max}{s.unit}</span>
          </div>
        </div>
      ))}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10, marginBottom: 12 }}>
        <div style={{ textAlign: 'center', padding: '16px 12px', borderRadius: 12, background: '#F59E0B10', border: '1px solid #F59E0B30' }}>
          <div style={{ fontSize: 10, color: '#F59E0B', fontWeight: 700, marginBottom: 5, textTransform: 'uppercase', letterSpacing: '0.06em' }}>Hoy</div>
          <div style={{ fontSize: 28, fontWeight: 800, color: '#F59E0B', fontFamily: 'monospace' }}>{horasSin}hs</div>
          <div style={{ fontSize: 10, color: 'var(--muted-2)', marginTop: 3 }}>en conciliación</div>
        </div>
        <div style={{ textAlign: 'center', padding: '16px 12px', borderRadius: 12, background: 'var(--accent-soft)', border: '1px solid var(--accent-line)' }}>
          <div style={{ fontSize: 10, color: 'var(--accent)', fontWeight: 700, marginBottom: 5, textTransform: 'uppercase', letterSpacing: '0.06em' }}>Con Cuadra</div>
          <div style={{ fontSize: 28, fontWeight: 800, color: 'var(--accent)', fontFamily: 'monospace' }}>{horasCon}hs</div>
          <div style={{ fontSize: 10, color: 'var(--muted-2)', marginTop: 3 }}>en conciliación</div>
        </div>
      </div>
      <div style={{ textAlign: 'center', padding: '13px', borderRadius: 10, background: 'var(--accent-soft)', border: '1px solid var(--accent-line)' }}>
        <span style={{ fontSize: 14, color: 'var(--accent)', fontWeight: 700 }}>
          ✓ Recuperás <span style={{ fontSize: 19 }}>{ahorro}hs</span> por mes
        </span>
      </div>
    </div>
  )
}
