import React, { useEffect, useRef, useState } from 'react'

export const WA_NUMBER = '543774504024'
export const WA_LINK   = `https://wa.me/${WA_NUMBER}?text=Hola%20Julieta%2C%20me%20interesa%20conocer%20m%C3%A1s%20sobre%20Cuadra`

export const Logo: React.FC<{ size?: number }> = ({ size = 28 }) => (
  <svg width={size} height={size} viewBox="0 0 32 32" aria-hidden="true">
    <rect width="32" height="32" rx="7" fill="currentColor"/>
    <path d="M9 16.5L13.5 21L23 11.5" stroke="white" strokeWidth="3.2" strokeLinecap="round" strokeLinejoin="round" fill="none"/>
  </svg>
)

export function useReveal() {
  const ref = useRef<HTMLDivElement>(null)
  useEffect(() => {
    const el = ref.current
    if (!el) return
    const show = () => { el.dataset.visible = 'true' }
    const rect = el.getBoundingClientRect()
    if (rect.top < window.innerHeight + 40) { show(); return }
    const obs = new IntersectionObserver(
      ([e]) => { if (e.isIntersecting) { show(); obs.disconnect() } },
      { threshold: 0, rootMargin: '0px 0px -20px 0px' }
    )
    obs.observe(el)
    const t = setTimeout(show, 2500)
    return () => { obs.disconnect(); clearTimeout(t) }
  }, [])
  return ref
}

export const R: React.FC<{ children: React.ReactNode; delay?: number; className?: string }> = ({
  children, delay = 0, className = ''
}) => {
  const ref = useReveal()
  return (
    <div ref={ref} className={`land-reveal ${className}`} style={{ '--d': `${delay}ms` } as React.CSSProperties}>
      {children}
    </div>
  )
}

// ── LazyMount: monta el hijo solo cuando entra al viewport ───────────────────
export const LazyMount: React.FC<{ children: React.ReactNode; minHeight?: number }> = ({ children, minHeight = 320 }) => {
  const ref = useRef<HTMLDivElement>(null)
  const [mounted, setMounted] = useState(false)
  useEffect(() => {
    if (window.innerWidth < 720) { setMounted(true); return }
    const el = ref.current; if (!el) return
    const obs = new IntersectionObserver(([e]) => { if (e.isIntersecting) { setMounted(true); obs.disconnect() } }, { rootMargin: '200px' })
    obs.observe(el)
    return () => obs.disconnect()
  }, [])
  return <div ref={ref}>{mounted ? children : <div style={{ minHeight }} />}</div>
}

export const SecIcon: React.FC<{ d: string | string[] }> = ({ d }) => (
  <svg width="24" height="24" fill="none" stroke="currentColor" strokeWidth={1.6} strokeLinecap="round" strokeLinejoin="round" viewBox="0 0 24 24" style={{ color: 'var(--accent)' }}>
    {(Array.isArray(d) ? d : [d]).map((path, i) => <path key={i} d={path} />)}
  </svg>
)
