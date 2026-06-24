import React, { useState } from 'react'
import { useThemeStore } from '@/store/theme'
import { LandingStyles } from '@/components/landing/LandingStyles'
import { Nav } from '@/components/landing/Nav'
import { Hero } from '@/components/landing/Hero'
import { StatsSection } from '@/components/landing/StatsSection'
import { ElProblema } from '@/components/landing/ElProblema'
import { SpotlightConciliacion } from '@/components/landing/SpotlightConciliacion'
import { SpotlightCheques } from '@/components/landing/SpotlightCheques'
import { SpotlightIA } from '@/components/landing/SpotlightIA'
import { CalculadoraSection } from '@/components/landing/CalculadoraSection'
import { Comparativa } from '@/components/landing/Comparativa'
import { Testimoniales } from '@/components/landing/Testimoniales'
import { Seguridad } from '@/components/landing/Seguridad'
import { ClosingCTA } from '@/components/landing/ClosingCTA'
import { Faq } from '@/components/landing/Faq'
import { Pricing } from '@/components/landing/Pricing'
import { Contacto } from '@/components/landing/Contacto'
import { Footer } from '@/components/landing/Footer'

export const Landing: React.FC = () => {
  const { theme, toggle } = useThemeStore()
  const [faqOpen, setFaqOpen] = useState<number | null>(0)
  const [menuOpen, setMenuOpen] = useState(false)

  return (
    <div className="landing-root">
      <LandingStyles />
      <Nav theme={theme} toggle={toggle} menuOpen={menuOpen} setMenuOpen={setMenuOpen} />
      <Hero />
      <StatsSection />
      <ElProblema />
      <SpotlightConciliacion />
      <SpotlightCheques />
      <SpotlightIA />
      <CalculadoraSection />
      <Comparativa />
      <Testimoniales />
      <Seguridad />
      <ClosingCTA />
      <Faq faqOpen={faqOpen} setFaqOpen={setFaqOpen} />
      <Pricing />
      <Contacto />
      <Footer />
    </div>
  )
}
