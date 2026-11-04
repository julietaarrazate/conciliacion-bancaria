import React, { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { IconMoon, IconSun, Logo } from './shared'

const LINKS = [
  { href: '#como-funciona', label: 'Cómo funciona' },
  { href: '#funciones', label: 'Funciones' },
  { href: '#precio', label: 'Precio' },
  { href: '#preguntas', label: 'Preguntas' },
]

/** Barra fija. El botón "Pedí una demo" aparece cuando el hero sale de pantalla. */
export const Nav: React.FC<{ theme: string; toggle: () => void }> = ({ theme, toggle }) => {
  const [scrolled, setScrolled] = useState(false)
  const [showCta, setShowCta] = useState(false)

  useEffect(() => {
    let raf = 0
    const onScroll = () => {
      cancelAnimationFrame(raf)
      raf = requestAnimationFrame(() => {
        const y = window.scrollY
        setScrolled(y > 8)
        setShowCta(y > Math.min(560, window.innerHeight * 0.6))
      })
    }
    onScroll()
    window.addEventListener('scroll', onScroll, { passive: true })
    return () => { window.removeEventListener('scroll', onScroll); cancelAnimationFrame(raf) }
  }, [])

  return (
    <header className="l-nav" data-scrolled={scrolled}>
      <div className="l-wrap l-nav-in">
        <a href="#top" className="l-brand" aria-label="Cuadra, inicio">
          <Logo size={24} /> Cuadra
        </a>
        <nav className="l-nav-links" aria-label="Secciones">
          {LINKS.map(l => <a key={l.href} href={l.href}>{l.label}</a>)}
        </nav>
        <div className="l-nav-actions">
          <button type="button" onClick={toggle} className="l-icon-btn"
            aria-label={theme === 'dark' ? 'Usar modo claro' : 'Usar modo oscuro'}>
            {theme === 'dark' ? <IconSun size={17} /> : <IconMoon size={17} />}
          </button>
          <Link to="/login" className="l-nav-login">Ingresar</Link>
          <a href="#demo" className="l-btn primary sm l-nav-cta" data-show={showCta}
            tabIndex={showCta ? 0 : -1} aria-hidden={!showCta}>
            Pedí una demo
          </a>
        </div>
      </div>
    </header>
  )
}
