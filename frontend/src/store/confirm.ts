import { create } from 'zustand'

interface ConfirmOptions {
  title: string
  message?: string
  confirmLabel?: string
  cancelLabel?: string
  danger?: boolean
}

interface ConfirmState extends ConfirmOptions {
  open: boolean
  resolve: ((v: boolean) => void) | null
  ask: (opts: ConfirmOptions) => Promise<boolean>
  close: (v: boolean) => void
}

export const useConfirmStore = create<ConfirmState>((set, get) => ({
  open: false,
  title: '',
  message: '',
  confirmLabel: 'Confirmar',
  cancelLabel: 'Cancelar',
  danger: false,
  resolve: null,
  ask: (opts) =>
    new Promise<boolean>((resolve) => {
      set({
        open: true,
        title: opts.title,
        message: opts.message ?? '',
        confirmLabel: opts.confirmLabel ?? 'Confirmar',
        cancelLabel: opts.cancelLabel ?? 'Cancelar',
        danger: opts.danger ?? false,
        resolve,
      })
    }),
  close: (v) => {
    const r = get().resolve
    set({ open: false, resolve: null })
    if (r) r(v)
  },
}))

export function confirmDialog(opts: ConfirmOptions): Promise<boolean> {
  return useConfirmStore.getState().ask(opts)
}
