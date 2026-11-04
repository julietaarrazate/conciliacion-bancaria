import React from 'react'
import { useThemeStore } from '@/store/theme'
import { LandingStyles } from '@/components/landing/LandingStyles'
import { Nav } from '@/components/landing/Nav'
import { Hero } from '@/components/landing/Hero'
import { ComoFunciona } from '@/components/landing/ComoFunciona'
import { Funciones } from '@/components/landing/Funciones'
import { Confianza } from '@/components/landing/Confianza'
import { Pricing } from '@/components/landing/Pricing'
import { Faq } from '@/components/landing/Faq'
import { PedirDemo } from '@/components/landing/PedirDemo'
import { Footer } from '@/components/landing/Footer'

/**
 * Landing pública (`/` sin sesión y `/landing`). Siete secciones:
 * hero con la conciliación animada → cómo funciona → funciones → para quién
 * y seguridad → precio → preguntas → pedido de demo. Dirección de diseño
 * (oct 2026) en CLAUDE.md, sección "Diseño".
 */
export const Landing: React.FC = () => {
  const { theme, toggle } = useThemeStore()
  return (
    <div className="landing-root">
      <LandingStyles />
      <Nav theme={theme} toggle={toggle} />
      <main>
        <Hero />
        <ComoFunciona />
        <Funciones />
        <Confianza />
        <Pricing />
        <Faq />
        <PedirDemo />
      </main>
      <Footer />
    </div>
  )
}
