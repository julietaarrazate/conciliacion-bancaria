import React, { useEffect, useRef, useState } from 'react'

export const StatCounter: React.FC<{
  numericEnd: number; prefix: string; suffix: string; label: string; delay?: number
}> = ({ numericEnd, prefix, suffix, label, delay = 0 }) => {
  const ref = useRef<HTMLDivElement>(null)
  const [count, setCount] = useState(0)
  const animDone = useRef(false)
  useEffect(() => {
    if (numericEnd === 0) return
    const el = ref.current; if (!el) return
    const run = () => {
      if (animDone.current) return
      animDone.current = true
      setTimeout(() => {
        const dur = numericEnd >= 20 ? 1400 : 900
        const t0 = performance.now()
        const tick = (now: number) => {
          const p = Math.min((now - t0) / dur, 1)
          setCount(Math.round((1 - Math.pow(1 - p, 3)) * numericEnd))
          if (p < 1) requestAnimationFrame(tick)
        }
        requestAnimationFrame(tick)
      }, delay)
    }
    if (window.innerWidth < 720) { run(); return }
    const obs = new IntersectionObserver(([e]) => { if (e.isIntersecting) { run(); obs.disconnect() } }, { threshold: 0.4 })
    obs.observe(el)
    return () => obs.disconnect()
  }, [])
  return (
    <div ref={ref} style={{ padding: '28px 18px', background: 'var(--bg)', textAlign: 'center' }}>
      <div style={{ fontSize: 30, fontWeight: 700, color: 'var(--accent)', fontFamily: 'monospace', letterSpacing: '-1px' }}>{prefix}{count}{suffix}</div>
      <div style={{ fontSize: 11, color: 'var(--muted-2)', marginTop: 5 }}>{label}</div>
    </div>
  )
}
