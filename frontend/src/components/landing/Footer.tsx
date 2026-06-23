import React from 'react'
import { Link } from 'react-router-dom'
import { Logo } from './shared'

export const Footer: React.FC = () => (
  <footer style={{ padding: '32px 20px', borderTop: '1px solid var(--border-soft)', textAlign: 'center' }}>
    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 8, marginBottom: 14 }}>
      <span style={{ color: 'var(--accent)' }}><Logo size={20} /></span>
      <span style={{ fontWeight: 700, color: 'var(--accent)', fontSize: 14 }}>Cuadra</span>
    </div>
    <div style={{ display: 'flex', gap: 24, justifyContent: 'center', marginBottom: 12 }}>
      <Link to="/privacidad" className="footer-link">Privacidad</Link>
      <Link to="/terminos" className="footer-link">Términos</Link>
    </div>
    <span style={{ fontSize: 11, color: 'var(--muted-2)' }}>© {new Date().getFullYear()} Julieta Arrazate</span>
  </footer>
)
