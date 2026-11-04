import React, { useEffect, useRef, useState } from 'react'

// ── Contacto ────────────────────────────────────────────────────────────────
// No hay endpoint de leads en el backend: el pedido de demo sale por WhatsApp
// (mensaje armado con los datos del formulario) o por mail como alternativa.
export const WA_NUMBER = '543774504024'
export const CONTACT_EMAIL = 'julietaarrazate@gmail.com'

export const waLink = (texto = 'Hola Julieta, me interesa conocer más sobre Cuadra') =>
  `https://wa.me/${WA_NUMBER}?text=${encodeURIComponent(texto)}`

export const mailLink = (asunto: string, cuerpo: string) =>
  `mailto:${CONTACT_EMAIL}?subject=${encodeURIComponent(asunto)}&body=${encodeURIComponent(cuerpo)}`

export const WA_LINK = waLink()

// ── Movimiento ──────────────────────────────────────────────────────────────
export function prefersReducedMotion(): boolean {
  if (typeof window === 'undefined' || typeof window.matchMedia !== 'function') return false
  return window.matchMedia('(prefers-reduced-motion: reduce)').matches
}

/**
 * Marca `data-visible="true"` cuando el elemento entra al viewport. Sin
 * IntersectionObserver (jsdom, navegadores viejos) o con reduced-motion se
 * muestra de entrada: nunca queda contenido escondido.
 */
export function useReveal<T extends HTMLElement = HTMLDivElement>() {
  const ref = useRef<T>(null)
  useEffect(() => {
    const el = ref.current
    if (!el) return
    const show = () => { el.dataset.visible = 'true' }
    if (typeof IntersectionObserver === 'undefined' || prefersReducedMotion()) { show(); return }
    const obs = new IntersectionObserver(
      ([e]) => { if (e.isIntersecting) { show(); obs.disconnect() } },
      { threshold: 0.12, rootMargin: '0px 0px -40px 0px' },
    )
    obs.observe(el)
    // Red de seguridad: si el observer nunca dispara (pestaña en segundo plano,
    // captura de pantalla), el contenido aparece igual.
    const t = window.setTimeout(show, 4000)
    return () => { obs.disconnect(); window.clearTimeout(t) }
  }, [])
  return ref
}

export const Reveal: React.FC<{ children: React.ReactNode; delay?: number; className?: string }> = ({
  children, delay = 0, className = '',
}) => {
  const ref = useReveal()
  return (
    <div ref={ref} className={`l-reveal ${className}`} style={{ '--d': `${delay}ms` } as React.CSSProperties}>
      {children}
    </div>
  )
}

/** true mientras el elemento está (aunque sea en parte) en pantalla. */
export function useInView<T extends HTMLElement>(ref: React.RefObject<T | null>, rootMargin = '0px') {
  const [inView, setInView] = useState(false)
  useEffect(() => {
    const el = ref.current
    if (!el) return
    if (typeof IntersectionObserver === 'undefined') { setInView(true); return }
    const obs = new IntersectionObserver(([e]) => setInView(e.isIntersecting), { rootMargin })
    obs.observe(el)
    return () => obs.disconnect()
  }, [ref, rootMargin])
  return inView
}

// ── Íconos (SVG inline, sin emojis) ─────────────────────────────────────────
type IconProps = { size?: number; className?: string }

export const Logo: React.FC<IconProps> = ({ size = 24 }) => (
  <svg width={size} height={size} viewBox="0 0 32 32" aria-hidden="true">
    <rect width="32" height="32" rx="8" fill="currentColor" />
    <path d="M9 16.5L13.5 21L23 11.5" stroke="#fff" strokeWidth="3.2" strokeLinecap="round" strokeLinejoin="round" fill="none" />
  </svg>
)

const Stroke: React.FC<IconProps & { children: React.ReactNode; sw?: number }> = ({ size = 18, children, sw = 1.8, className }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={sw}
    strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" className={className}>
    {children}
  </svg>
)

export const IconCheck: React.FC<IconProps> = (p) => <Stroke sw={2.4} {...p}><path d="M5 12.5l4.5 4.5L19 7.5" /></Stroke>
export const IconArrow: React.FC<IconProps> = (p) => <Stroke sw={2} {...p} className="arrow"><path d="M5 12h14M13 6l6 6-6 6" /></Stroke>
export const IconPlus: React.FC<IconProps> = (p) => <Stroke sw={2} {...p}><path d="M12 5v14M5 12h14" /></Stroke>
export const IconSun: React.FC<IconProps> = (p) => <Stroke {...p}><circle cx="12" cy="12" r="4" /><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4" /></Stroke>
export const IconMoon: React.FC<IconProps> = (p) => <Stroke {...p}><path d="M20 14.5A8 8 0 0 1 9.5 4a8 8 0 1 0 10.5 10.5z" /></Stroke>
export const IconBuilding: React.FC<IconProps> = (p) => <Stroke {...p}><path d="M4 21V5a1 1 0 0 1 1-1h9a1 1 0 0 1 1 1v16M15 9h4a1 1 0 0 1 1 1v11M3 21h18M8 8h3M8 12h3M8 16h3" /></Stroke>
export const IconTransfer: React.FC<IconProps> = (p) => <Stroke {...p}><path d="M4 8h14l-3-3M20 16H6l3 3" /></Stroke>
export const IconCheque: React.FC<IconProps> = (p) => <Stroke {...p}><rect x="2.5" y="6" width="19" height="12" rx="2" /><path d="M6 14h6M15 14h3M6 10h3" /></Stroke>
export const IconLock: React.FC<IconProps> = (p) => <Stroke {...p}><rect x="4.5" y="10.5" width="15" height="10" rx="2" /><path d="M8 10.5V7.5a4 4 0 0 1 8 0v3" /></Stroke>
export const IconCloud: React.FC<IconProps> = (p) => <Stroke {...p}><path d="M7 18a4.5 4.5 0 0 1-.5-9A6 6 0 0 1 18 8.5 4.75 4.75 0 0 1 17.5 18z" /><path d="M12 11v5M9.5 13.5 12 16l2.5-2.5" /></Stroke>
export const IconList: React.FC<IconProps> = (p) => <Stroke {...p}><path d="M9 6h11M9 12h11M9 18h11M4.5 6h.01M4.5 12h.01M4.5 18h.01" /></Stroke>
export const IconUsers: React.FC<IconProps> = (p) => <Stroke {...p}><circle cx="9" cy="8" r="3.5" /><path d="M2.5 20a6.5 6.5 0 0 1 13 0M16 4.5a3.5 3.5 0 0 1 0 7M18 14a6 6 0 0 1 3.5 6" /></Stroke>
export const IconCursor: React.FC<IconProps> = ({ size = 20 }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" aria-hidden="true">
    <path d="M5 3l14 7.5-6 1.6L10.4 18z" fill="currentColor" stroke="var(--card)" strokeWidth="1.4" strokeLinejoin="round" />
  </svg>
)
export const IconWhatsApp: React.FC<IconProps> = ({ size = 18 }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
    <path d="M17.47 14.38c-.3-.15-1.76-.87-2.03-.97-.27-.1-.47-.15-.67.15-.2.3-.77.97-.94 1.16-.17.2-.35.22-.64.07-.3-.15-1.26-.46-2.39-1.47-.88-.79-1.48-1.76-1.65-2.06-.17-.3-.02-.46.13-.6.13-.14.3-.35.45-.52.15-.18.2-.3.3-.5.1-.2.05-.37-.03-.52-.07-.15-.67-1.61-.91-2.2-.24-.58-.49-.5-.67-.51h-.57c-.2 0-.52.07-.8.37-.27.3-1.04 1.02-1.04 2.48s1.07 2.88 1.21 3.07c.15.2 2.1 3.2 5.08 4.49.71.31 1.26.49 1.7.63.71.22 1.36.19 1.87.12.57-.09 1.76-.72 2-1.41.25-.7.25-1.29.18-1.41-.08-.13-.28-.2-.57-.35M12.05 21.79h-.01a9.87 9.87 0 0 1-5.03-1.38l-.36-.21-3.74.98 1-3.65-.24-.37a9.86 9.86 0 0 1-1.51-5.26c0-5.45 4.44-9.88 9.89-9.88a9.83 9.83 0 0 1 9.88 9.89c0 5.45-4.44 9.88-9.88 9.88m8.41-18.3A11.82 11.82 0 0 0 12.05 0C5.5 0 .16 5.34.16 11.89c0 2.1.55 4.14 1.59 5.95L.06 24l6.3-1.65a11.88 11.88 0 0 0 5.69 1.45c6.55 0 11.89-5.34 11.89-11.89a11.82 11.82 0 0 0-3.48-8.41z" />
  </svg>
)
