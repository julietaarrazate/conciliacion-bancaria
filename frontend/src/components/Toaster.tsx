import React from 'react'
import { useToastStore } from '@/store/toast'

const styles: Record<string, string> = {
  success: 'bg-white border-green-200 text-green-700 dark:bg-ml-dark-surface dark:border-green-800/40 dark:text-green-400',
  error:   'bg-white border-red-200 text-red-700 dark:bg-ml-dark-surface dark:border-red-800/40 dark:text-red-400',
  info:    'bg-white border-blue-200 text-blue-700 dark:bg-ml-dark-surface dark:border-blue-800/40 dark:text-blue-400',
  warn:    'bg-white border-amber-200 text-amber-700 dark:bg-ml-dark-surface dark:border-amber-800/40 dark:text-amber-400',
}

const accents: Record<string, string> = {
  success: 'bg-green-500',
  error:   'bg-red-500',
  info:    'bg-blue-500',
  warn:    'bg-amber-500',
}

const icons: Record<string, string> = {
  success: '✓',
  error:   '✕',
  info:    'i',
  warn:    '!',
}

export const Toaster: React.FC = () => {
  const toasts = useToastStore(s => s.toasts)
  const dismiss = useToastStore(s => s.dismiss)

  return (
    <div className="fixed top-3 inset-x-3 md:top-4 md:right-4 md:left-auto md:inset-x-auto z-[100] flex flex-col gap-2 pointer-events-none md:w-96">
      {toasts.map(t => (
        <div
          key={t.id}
          onClick={() => dismiss(t.id)}
          className={`pointer-events-auto rounded-xl border shadow-lg flex items-stretch gap-0 overflow-hidden cursor-pointer toast-enter ${styles[t.kind]}`}
        >
          <div className={`w-1 shrink-0 ${accents[t.kind]}`} />
          <div className="flex items-start gap-2.5 px-3.5 py-2.5 flex-1">
            <span className={`shrink-0 w-5 h-5 rounded-full flex items-center justify-center text-white text-[11px] font-bold mt-0.5 ${accents[t.kind]}`}>
              {icons[t.kind]}
            </span>
            <span className="flex-1 text-sm font-medium leading-snug">{t.message}</span>
          </div>
        </div>
      ))}
    </div>
  )
}
