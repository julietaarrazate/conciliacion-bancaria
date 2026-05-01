import React from 'react'
import { useThemeStore } from '@/store/theme'

export const ThemeToggle: React.FC = () => {
  const { theme, toggle } = useThemeStore()

  return (
    <button
      onClick={toggle}
      className="w-full flex items-center gap-3 px-3 py-2 text-sm rounded-md text-ml-text hover:bg-ml-gray-bg dark:text-gray-300 dark:hover:bg-slate-700 transition-colors"
      aria-label={theme === 'light' ? 'Activar modo oscuro' : 'Activar modo claro'}
    >
      <span className="text-base">{theme === 'light' ? '🌙' : '☀️'}</span>
      <span>{theme === 'light' ? 'Modo oscuro' : 'Modo claro'}</span>
    </button>
  )
}
