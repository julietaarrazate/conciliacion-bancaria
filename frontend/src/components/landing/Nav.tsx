import React from 'react'
import { Link } from 'react-router-dom'
import { Logo } from './shared'

export const Nav: React.FC<{
  theme: string
  toggle: () => void
  menuOpen: boolean
  setMenuOpen: React.Dispatch<React.SetStateAction<boolean>>
}> = ({ theme, toggle, menuOpen, setMenuOpen }) => {
  const closeMenu = () => setMenuOpen(false)

  return (
    <>
      {menuOpen && (
        <div className="mobile-menu-overlay">
          <a href="#como-funciona" onClick={closeMenu}>✦ Cómo funciona</a>
          <a href="#seguridad"     onClick={closeMenu}>✦ Seguridad</a>
          <a href="#faq"           onClick={closeMenu}>✦ FAQ</a>
          <a href="#contacto"      onClick={closeMenu}>✦ Contacto</a>
        </div>
      )}

      <nav className="land-nav">
        <a href="#top" className="nav-logo">
          <span style={{ color: 'var(--accent)' }}><Logo size={24} /></span>
          Cuadra
        </a>
        <div className="nav-actions">
          <div className="nav-links">
            <a href="#como-funciona" className="btn-ghost" style={{ padding: '7px 12px', fontSize: 13 }}>Cómo funciona</a>
            <a href="#seguridad"     className="btn-ghost" style={{ padding: '7px 12px', fontSize: 13 }}>Seguridad</a>
            <a href="#faq"           className="btn-ghost" style={{ padding: '7px 12px', fontSize: 13 }}>FAQ</a>
            <a href="#contacto"      className="btn-ghost" style={{ padding: '7px 12px', fontSize: 13 }}>Contacto</a>
          </div>
          <button onClick={toggle} className="theme-toggle" title={theme === 'dark' ? 'Modo claro' : 'Modo oscuro'} aria-label="Cambiar tema">
            {theme === 'dark' ? '☀' : '☾'}
          </button>
          <button onClick={() => setMenuOpen(o => !o)} className="ham-btn" aria-label="Menú">
            {menuOpen ? '✕' : '☰'}
          </button>
          <Link to="/login" className="btn-green">Ingresar</Link>
        </div>
      </nav>
    </>
  )
}
