import React from 'react'
import { Logo, WA_LINK } from './shared'
import { MOCKUP_ROWS } from './data'

export const Hero: React.FC = () => {
  return (
    <section id="top" className="hero-section">
      <div className="glow-orb" style={{ position: 'absolute', top: '18%', left: '50%', transform: 'translateX(-50%)', width: 'min(700px,90vw)', height: 400, borderRadius: '50%', background: 'radial-gradient(circle, var(--accent-soft) 0%, transparent 70%)', pointerEvents: 'none' }} />

      <div className="live-badge" style={{ display: 'inline-flex', alignItems: 'center', gap: 8, padding: '6px 14px', borderRadius: 999, background: 'var(--accent-soft)', border: '1px solid var(--accent-line)', color: 'var(--accent)', fontSize: 12, fontWeight: 600, marginBottom: 24 }}>
        <span style={{ width: 6, height: 6, borderRadius: '50%', background: 'var(--accent)', display: 'inline-block' }} />
        Software financiero con IA para estudios argentinos
      </div>

      <h1 className="hero-title">
        Los números<br />
        <span className="em-serif grad-text">cuadran solos.</span>
      </h1>

      <p className="hero-sub">
        Conciliación bancaria automática, cheques, caja, pagos y contabilidad — con IA integrada.
        Para vos y tu equipo, desde el celular o la web.
      </p>

      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 10, justifyContent: 'center', marginBottom: 18 }}>
        <a href="#como-funciona" className="btn-green large">Ver cómo funciona →</a>
        <a href={WA_LINK} target="_blank" rel="noopener noreferrer" className="wa-btn" style={{ padding: '14px 24px', fontSize: 15, borderRadius: 12 }}>
          <svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><path d="M17.472 14.382c-.297-.149-1.758-.867-2.03-.967-.273-.099-.471-.148-.67.15-.197.297-.767.966-.94 1.164-.173.199-.347.223-.644.075-.297-.15-1.255-.463-2.39-1.475-.883-.788-1.48-1.761-1.653-2.059-.173-.297-.018-.458.13-.606.134-.133.298-.347.446-.52.149-.174.198-.298.298-.497.099-.198.05-.371-.025-.52-.075-.149-.669-1.612-.916-2.207-.242-.579-.487-.5-.669-.51-.173-.008-.371-.01-.57-.01-.198 0-.52.074-.792.372-.272.297-1.04 1.016-1.04 2.479 0 1.462 1.065 2.875 1.213 3.074.149.198 2.096 3.2 5.077 4.487.709.306 1.262.489 1.694.625.712.227 1.36.195 1.871.118.571-.085 1.758-.719 2.006-1.413.248-.694.248-1.289.173-1.413-.074-.124-.272-.198-.57-.347m-5.421 7.403h-.004a9.87 9.87 0 01-5.031-1.378l-.361-.214-3.741.982.998-3.648-.235-.374a9.86 9.86 0 01-1.51-5.26c.001-5.45 4.436-9.884 9.888-9.884 2.64 0 5.122 1.03 6.988 2.898a9.825 9.825 0 012.893 6.994c-.003 5.45-4.437 9.884-9.885 9.884m8.413-18.297A11.815 11.815 0 0012.05 0C5.495 0 .16 5.335.157 11.892c0 2.096.547 4.142 1.588 5.945L.057 24l6.305-1.654a11.882 11.882 0 005.683 1.448h.005c6.554 0 11.89-5.335 11.893-11.893a11.821 11.821 0 00-3.48-8.413z"/></svg>
          Escribime
        </a>
      </div>

      <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', justifyContent: 'center', marginBottom: 44 }}>
        {['✓ Web y mobile', '✓ Soporte directo', '✓ Onboarding incluido'].map(b => (
          <span key={b} style={{ fontSize: 12, color: 'var(--muted)', background: 'var(--card)', border: '1px solid var(--border)', padding: '5px 12px', borderRadius: 999 }}>{b}</span>
        ))}
      </div>

      {/* Hero mockup */}
      <div className="mock-float mockup-wrap">
        <div style={{ borderRadius: 18, border: '1px solid var(--border)', background: 'var(--card)', boxShadow: 'var(--mock-shadow)', overflow: 'hidden' }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '11px 16px', borderBottom: '1px solid var(--border)', background: 'var(--topbar-bg)' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <span style={{ color: 'var(--accent)' }}><Logo size={18} /></span>
              <span style={{ fontSize: 12, fontWeight: 700, color: 'var(--accent)' }}>Cuadra</span>
            </div>
            <div style={{ display: 'flex', gap: 6 }}>
              {['#FF5F57','#FFBD2E','#28C840'].map(c => <div key={c} style={{ width: 9, height: 9, borderRadius: '50%', background: c }} />)}
            </div>
          </div>
          <div style={{ padding: 16 }}>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 8, marginBottom: 14 }}>
              {[{ label: 'Conciliados', val: '47', color: 'var(--accent)' }, { label: 'Pendientes', val: '3', color: '#F59E0B' }, { label: 'Caja', val: '$482k', color: '#5E6AD2' }].map(s => (
                <div key={s.label} style={{ background: 'var(--card-2)', borderRadius: 10, padding: '10px', border: '1px solid var(--border-soft)' }}>
                  <div style={{ fontSize: 18, fontWeight: 700, color: s.color, fontFamily: 'monospace' }}>{s.val}</div>
                  <div style={{ fontSize: 10, color: 'var(--muted-2)', marginTop: 2 }}>{s.label}</div>
                </div>
              ))}
            </div>
            <div style={{ fontSize: 10, color: 'var(--muted-2)', fontWeight: 600, marginBottom: 8, textTransform: 'uppercase', letterSpacing: '0.08em' }}>Planilla del mes</div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 5 }}>
              {MOCKUP_ROWS.map((r, i) => (
                <div key={i} style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '8px 10px', borderRadius: 8, background: r.ok ? 'var(--accent-soft)' : 'var(--card-2)', border: `1px solid ${r.ok ? 'var(--accent-line)' : 'var(--border-soft)'}` }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8, minWidth: 0 }}>
                    <div style={{ width: 6, height: 6, borderRadius: '50%', flexShrink: 0, background: r.ok ? 'var(--accent)' : '#F59E0B' }} />
                    <span style={{ fontSize: 12, fontWeight: 500, color: 'var(--text-2)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{r.cliente}</span>
                  </div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 6, flexShrink: 0 }}>
                    <span style={{ fontSize: 11, fontFamily: 'monospace', color: 'var(--muted)' }}>{r.importe}</span>
                    <span style={{ fontSize: 10, padding: '2px 6px', borderRadius: 4, background: r.ok ? 'var(--accent)' : '#F59E0B18', color: r.ok ? '#fff' : '#F59E0B', fontWeight: 700 }}>{r.ok ? 'OK' : 'REVISAR'}</span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </section>
  )
}
