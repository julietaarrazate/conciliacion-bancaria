import { create } from 'zustand'
import { persist } from 'zustand/middleware'

async function hashPin(pin: string): Promise<string> {
  const enc = new TextEncoder()
  const buf = await crypto.subtle.digest('SHA-256', enc.encode('cuadra-pin-v1:' + pin))
  return Array.from(new Uint8Array(buf)).map(b => b.toString(16).padStart(2, '0')).join('')
}

// ── WebAuthn helpers ─────────────────────────────────
function b64uEncode(buf: ArrayBuffer): string {
  return btoa(String.fromCharCode(...new Uint8Array(buf)))
    .replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '')
}
function b64uDecode(s: string): Uint8Array {
  const pad = '='.repeat((4 - (s.length % 4)) % 4)
  const b64 = (s + pad).replace(/-/g, '+').replace(/_/g, '/')
  return Uint8Array.from(atob(b64), c => c.charCodeAt(0))
}

export async function isBiometricAvailable(): Promise<boolean> {
  try {
    if (!window.PublicKeyCredential) return false
    return await PublicKeyCredential.isUserVerifyingPlatformAuthenticatorAvailable()
  } catch { return false }
}

interface LockState {
  pinHash: string | null
  enabled: boolean
  isLocked: boolean
  biometricEnabled: boolean
  credentialId: string | null
  suppressUntil: number  // timestamp: no bloquear por background hasta esta hora (descargas/PDF)
  setupPin: (pin: string) => Promise<void>
  removePin: (pin: string) => Promise<boolean>
  unlock: (pin: string) => Promise<boolean>
  lock: () => void
  forceUnlock: () => void
  suppressLock: (ms?: number) => void
  enrollBiometric: () => Promise<{ ok: boolean; error?: string }>
  unlockBiometric: () => Promise<boolean>
  disableBiometric: () => void
}

export const useLockStore = create<LockState>()(
  persist(
    (set, get) => ({
      pinHash: null,
      enabled: false,
      isLocked: false,
      biometricEnabled: false,
      credentialId: null,
      suppressUntil: 0,
      setupPin: async (pin) => {
        const h = await hashPin(pin)
        set({ pinHash: h, enabled: true, isLocked: false })
      },
      removePin: async (pin) => {
        const h = await hashPin(pin)
        if (h !== get().pinHash) return false
        // Al sacar el PIN también se desactiva la biometría
        set({ pinHash: null, enabled: false, isLocked: false, biometricEnabled: false, credentialId: null })
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
      // Evita el bloqueo automático por pérdida de foco durante una descarga
      // deliberada (PDF/Excel): el navegador dispara visibilitychange al abrir
      // el diálogo de guardar, pero no es que el usuario salió de la app.
      suppressLock: (ms = 8000) => set({ suppressUntil: Date.now() + ms }),

      enrollBiometric: async () => {
        if (!(await isBiometricAvailable())) {
          return { ok: false, error: 'Tu dispositivo no soporta biometría en este navegador' }
        }
        try {
          const challenge = crypto.getRandomValues(new Uint8Array(32))
          const userId = crypto.getRandomValues(new Uint8Array(16))
          const cred = await navigator.credentials.create({
            publicKey: {
              challenge,
              rp: { name: 'Cuadra' },
              user: {
                id: userId,
                name: 'cuadra-local',
                displayName: 'Cuadra',
              },
              pubKeyCredParams: [
                { type: 'public-key', alg: -7 },   // ES256
                { type: 'public-key', alg: -257 }, // RS256
              ],
              authenticatorSelection: {
                authenticatorAttachment: 'platform',
                userVerification: 'required',
                residentKey: 'preferred',
              },
              timeout: 60000,
              attestation: 'none',
            },
          }) as PublicKeyCredential | null
          if (!cred) return { ok: false, error: 'No se pudo registrar' }
          const credId = b64uEncode(cred.rawId)
          set({ biometricEnabled: true, credentialId: credId })
          return { ok: true }
        } catch (e: any) {
          if (e?.name === 'NotAllowedError') {
            return { ok: false, error: 'Cancelaste el registro' }
          }
          return { ok: false, error: e?.message || 'Error registrando biometría' }
        }
      },

      unlockBiometric: async () => {
        const credentialId = get().credentialId
        if (!credentialId) return false
        try {
          const challenge = crypto.getRandomValues(new Uint8Array(32))
          const rawId = b64uDecode(credentialId)
          const assertion = await navigator.credentials.get({
            publicKey: {
              challenge,
              allowCredentials: [{ id: rawId.buffer as ArrayBuffer, type: 'public-key' }],
              userVerification: 'required',
              timeout: 60000,
            },
          })
          if (!assertion) return false
          set({ isLocked: false })
          return true
        } catch {
          return false
        }
      },

      disableBiometric: () => set({ biometricEnabled: false, credentialId: null }),
    }),
    {
      name: 'cuadra-lock',
      // Persist isLocked too: si recargás la página y tenías PIN activo, queda bloqueada
      partialize: (s) => ({
        pinHash: s.pinHash,
        enabled: s.enabled,
        isLocked: s.isLocked,
        biometricEnabled: s.biometricEnabled,
        credentialId: s.credentialId,
      }),
    }
  )
)
