import { create } from 'zustand'

type Theme = 'light' | 'dark'

interface ThemeState {
  theme: Theme
  toggle: () => void
  applyToDocument: () => void
}

const STORAGE_KEY = 'app-theme'

const getInitialTheme = (): Theme => {
  if (typeof window === 'undefined') return 'light'
  const stored = localStorage.getItem(STORAGE_KEY) as Theme | null
  if (stored === 'light' || stored === 'dark') return stored
  return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'
}

export const useThemeStore = create<ThemeState>((set, get) => ({
  theme: getInitialTheme(),

  toggle: () => {
    const next = get().theme === 'light' ? 'dark' : 'light'
    set({ theme: next })
    localStorage.setItem(STORAGE_KEY, next)
    if (typeof document !== 'undefined') {
      document.documentElement.classList.toggle('dark', next === 'dark')
    }
  },

  applyToDocument: () => {
    if (typeof document === 'undefined') return
    document.documentElement.classList.toggle('dark', get().theme === 'dark')
  }
}))
