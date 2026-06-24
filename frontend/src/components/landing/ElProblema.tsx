import React from 'react'
import { R } from './shared'

export const ElProblema: React.FC = () => (
  <section className="section" style={{ background: 'var(--bg-2)', borderTop: '1px solid var(--border-soft)', borderBottom: '1px solid var(--border-soft)' }}>
    <div style={{ maxWidth: 800, margin: '0 auto' }}>
      <R>
        <div style={{ textAlign: 'center', marginBottom: 44 }}>
          <div className="sec-label">El problema</div>
          <h2 className="section-title">El Excel no cuadra.<br /><em className="em-serif">Otra vez.</em></h2>
        </div>
      </R>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: 14 }}>
        {[
          { icon: <svg width="22" height="22" fill="none" stroke="currentColor" strokeWidth={1.6} strokeLinecap="round" strokeLinejoin="round" viewBox="0 0 24 24" style={{ color: 'var(--muted)', flexShrink: 0 }}><path d="M12 6v6h4.5m4.5 0a9 9 0 11-18 0 9 9 0 0118 0z"/></svg>, text: 'Pasás horas cruzando el extracto bancario contra las planillas de cada cliente.' },
          { icon: <svg width="22" height="22" fill="none" stroke="currentColor" strokeWidth={1.6} strokeLinecap="round" strokeLinejoin="round" viewBox="0 0 24 24" style={{ color: 'var(--muted)', flexShrink: 0 }}><path d="M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-3.032-1.5-3.898 0L2.697 16.126zM12 15.75h.007v.008H12v-.008z"/></svg>, text: 'Un cliente pagó, el banco lo registró diferente, y no sabés si cuadra o no.' },
          { icon: <svg width="22" height="22" fill="none" stroke="currentColor" strokeWidth={1.6} strokeLinecap="round" strokeLinejoin="round" viewBox="0 0 24 24" style={{ color: 'var(--muted)', flexShrink: 0 }}><path d="M21.75 6.75v10.5a2.25 2.25 0 01-2.25 2.25h-15a2.25 2.25 0 01-2.25-2.25V6.75m19.5 0A2.25 2.25 0 0019.5 4.5h-15a2.25 2.25 0 00-2.25 2.25m19.5 0v.243a2.25 2.25 0 01-1.07 1.916l-7.5 4.615a2.25 2.25 0 01-2.36 0L3.32 8.91a2.25 2.25 0 01-1.07-1.916V6.75"/></svg>, text: 'El contador pide el cierre y todavía estás buscando el movimiento que falta.' },
          { icon: <svg width="22" height="22" fill="none" stroke="currentColor" strokeWidth={1.6} strokeLinecap="round" strokeLinejoin="round" viewBox="0 0 24 24" style={{ color: 'var(--muted)', flexShrink: 0 }}><path d="M19.5 14.25v-2.625a3.375 3.375 0 00-3.375-3.375h-1.5A1.125 1.125 0 0113.5 7.125v-1.5a3.375 3.375 0 00-3.375-3.375H8.25m0 12.75h7.5m-7.5 3H12M10.5 2.25H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 00-9-9z"/></svg>, text: 'Cada mes es lo mismo: el Excel crece, los errores se multiplican, el tiempo se va.' },
        ].map((item, i) => (
          <R key={i} delay={i * 70}>
            <div style={{ padding: '20px 22px', borderRadius: 14, background: 'var(--card)', border: '1px solid var(--border)', display: 'flex', gap: 14, alignItems: 'flex-start' }}>
              <span style={{ marginTop: 2 }}>{item.icon}</span>
              <span style={{ fontSize: 13, color: 'var(--muted)', lineHeight: 1.65 }}>{item.text}</span>
            </div>
          </R>
        ))}
      </div>
      <R delay={200}>
        <div style={{ textAlign: 'center', marginTop: 36 }}>
          <p style={{ color: 'var(--muted)', fontSize: 15, marginBottom: 14 }}>Cuadra lo hace automático. Vos revisás solo lo que necesita atención.</p>
          <a href="#como-funciona" style={{ color: 'var(--accent)', fontWeight: 600, fontSize: 14, textDecoration: 'none' }}>Ver cómo funciona →</a>
        </div>
      </R>
    </div>
  </section>
)
