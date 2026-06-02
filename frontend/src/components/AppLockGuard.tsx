import React, { useEffect, useRef } from 'react'
import { useLockStore } from '@/store/lock'
import { useAuthStore } from '@/store/auth'
import { LockScreen } from './LockScreen'

const IDLE_MS = 5 * 60 * 1000 // 5 minutos

export const AppLockGuard: React.FC = () => {
  const enabled = useLockStore(s => s.enabled)
  const pinHash = useLockStore(s => s.pinHash)
  const isLocked = useLockStore(s => s.isLocked)
  const lock = useLockStore(s => s.lock)
  const isAuthenticated = useAuthStore(s => s.isAuthenticated)
  const idleTimer = useRef<number | null>(null)
  const didLockOnMount = useRef(false)

  const active = enabled && !!pinHash && isAuthenticated

  // Bloquear siempre al cargar la app (nuevo tab, link externo, refresh)
  useEffect(() => {
    if (active && !didLockOnMount.current) {
      didLockOnMount.current = true
      lock()
    }
  }, [active, lock])

  // Bloquear al minimizar / pasar a background.
  // Debounce de 500ms para evitar falsos positivos durante animaciones de
  // navegación en mobile (Chrome Android dispara visibilitychange brevemente).
  const bgTimer = useRef<number | null>(null)
  useEffect(() => {
    if (!active) return
    const handler = () => {
      if (document.hidden) {
        // No bloquear si hay una descarga deliberada en curso (PDF/Excel)
        if (useLockStore.getState().suppressUntil > Date.now()) return
        bgTimer.current = window.setTimeout(() => {
          // Re-chequear al disparar: la página ya puede ser visible de nuevo
          // (animación de navegación SPA en mobile dura más de 500ms a veces)
          if (!document.hidden) return
          if (useLockStore.getState().suppressUntil > Date.now()) return
          lock()
        }, 1500)
      } else {
        if (bgTimer.current) {
          window.clearTimeout(bgTimer.current)
          bgTimer.current = null
        }
      }
    }
    document.addEventListener('visibilitychange', handler)
    return () => {
      document.removeEventListener('visibilitychange', handler)
      if (bgTimer.current) window.clearTimeout(bgTimer.current)
    }
  }, [active, lock])

  // Bloquear por inactividad (5 min sin tocar nada)
  useEffect(() => {
    if (!active || isLocked) return
    const reset = () => {
      if (idleTimer.current) window.clearTimeout(idleTimer.current)
      idleTimer.current = window.setTimeout(() => lock(), IDLE_MS)
    }
    const events: (keyof DocumentEventMap)[] = ['mousemove', 'keydown', 'touchstart', 'scroll']
    events.forEach(e => document.addEventListener(e, reset, { passive: true } as any))
    reset()
    return () => {
      events.forEach(e => document.removeEventListener(e, reset as any))
      if (idleTimer.current) window.clearTimeout(idleTimer.current)
    }
  }, [active, isLocked, lock])

  if (!active || !isLocked) return null
  return <LockScreen />
}
