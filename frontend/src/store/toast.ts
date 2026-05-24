import { create } from 'zustand'

export type ToastKind = 'success' | 'error' | 'info' | 'warn'

export interface Toast {
  id: number
  kind: ToastKind
  message: string
  duration: number
}

interface ToastState {
  toasts: Toast[]
  push: (kind: ToastKind, message: string, duration?: number) => void
  dismiss: (id: number) => void
}

let counter = 0

export const useToastStore = create<ToastState>((set, get) => ({
  toasts: [],
  push: (kind, message, duration) => {
    const id = ++counter
    const ttl = duration ?? (kind === 'error' ? 5000 : 3500)
    set(s => ({ toasts: [...s.toasts, { id, kind, message, duration: ttl }] }))
    setTimeout(() => get().dismiss(id), ttl)
  },
  dismiss: (id) => set(s => ({ toasts: s.toasts.filter(t => t.id !== id) })),
}))

// Helper para usar fuera de componentes React
export const toast = {
  success: (msg: string, d?: number) => useToastStore.getState().push('success', msg, d),
  error:   (msg: string, d?: number) => useToastStore.getState().push('error',   msg, d),
  info:    (msg: string, d?: number) => useToastStore.getState().push('info',    msg, d),
  warn:    (msg: string, d?: number) => useToastStore.getState().push('warn',    msg, d),
}
