import { create } from 'zustand'
import { persist } from 'zustand/middleware'

async function hashPin(pin: string): Promise<string> {
  const enc = new TextEncoder()
  const buf = await crypto.subtle.digest('SHA-256', enc.encode('cuadra-pin-v1:' + pin))
  return Array.from(new Uint8Array(buf)).map(b => b.toString(16).padStart(2, '0')).join('')
}

interface LockState {
  pinHash: string | null
  enabled: boolean
  isLocked: boolean
  setupPin: (pin: string) => Promise<void>
  removePin: (pin: string) => Promise<boolean>
  unlock: (pin: string) => Promise<boolean>
  lock: () => void
  forceUnlock: () => void
}

export const useLockStore = create<LockState>()(
  persist(
    (set, get) => ({
      pinHash: null,
      enabled: false,
      isLocked: false,
      setupPin: async (pin) => {
        const h = await hashPin(pin)
        set({ pinHash: h, enabled: true, isLocked: false })
      },
      removePin: async (pin) => {
        const h = await hashPin(pin)
        if (h !== get().pinHash) return false
        set({ pinHash: null, enabled: false, isLocked: false })
        return true
      },
      unlock: async (pin) => {
        const h = await hashPin(pin)
        if (h !== get().pinHash) return false
        set({ isLocked: false })
        return true
      },
      lock: () => {
        const s = get()
        if (s.enabled && s.pinHash) set({ isLocked: true })
      },
      forceUnlock: () => set({ isLocked: false }),
    }),
    {
      name: 'cuadra-lock',
      // Persist isLocked too: si recargás la página y tenías PIN activo, queda bloqueada
      partialize: (s) => ({ pinHash: s.pinHash, enabled: s.enabled, isLocked: s.isLocked }),
    }
  )
)
