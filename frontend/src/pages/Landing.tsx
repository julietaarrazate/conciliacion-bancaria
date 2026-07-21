import React, { useState } from 'react'
import { useThemeStore } from '@/store/theme'
import { LandingStyles } from '@/components/landing/LandingStyles'
import { Nav } from '@/components/landing/Nav'
import { Hero } from '@/components/landing/Hero'
import { SpotlightConciliacion } from '@/components/landing/SpotlightConciliacion'
import { Seguridad } from '@/components/landing/Seguridad'
import { ComoFunciona } from '@/components/landing/ComoFunciona'
import { ClosingCTA } from '@/components/landing/ClosingCTA'
import { Footer } from '@/components/landing/Footer'

export const Landing: React.FC = () => {
  const { theme, toggle } = useThemeStore()
  const [menuOpen, setMenuOpen] = useState(false)

  return (
    <div className="landing-root">
      <LandingStyles />
      <Nav theme={theme} toggle={toggle} menuOpen={menuOpen} setMenuOpen={setMenuOpen} />
      <Hero />
      <SpotlightConciliacion />
      <Seguridad />
      <ComoFunciona />
      <ClosingCTA />
      <Footer />
    </div>
  )
}
