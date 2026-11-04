import React from 'react'
import { Link } from 'react-router-dom'
import { Logo, WA_LINK } from './shared'

export const Footer: React.FC = () => (
  <footer className="l-foot">
    <div className="l-wrap l-foot-in">
      <span className="l-brand" style={{ fontSize: 15 }}><Logo size={20} /> Cuadra</span>
      <nav className="l-foot-links" aria-label="Legales y contacto">
        <a href={WA_LINK} target="_blank" rel="noopener noreferrer">WhatsApp</a>
        <Link to="/login">Ingresar</Link>
        <Link to="/privacidad">Privacidad</Link>
        <Link to="/terminos">Términos</Link>
      </nav>
      <small>© {new Date().getFullYear()} Julieta Arrazate</small>
    </div>
  </footer>
)
