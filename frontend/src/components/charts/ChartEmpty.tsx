import React from 'react'

export const CHART_EMPTY_MSG = 'Todavía no hay movimientos en este período'

/** true si no hay puntos o todos valen 0: un gráfico así es una línea plana
 *  o barras vacías que no dicen nada; se muestra ChartEmpty en su lugar. */
export const sinDatos = (valores: number[]) => valores.length === 0 || valores.every(v => !v)

/** Estado vacío silencioso para gráficos y tarjetas sin datos. Ocupa el mismo
 *  alto que el gráfico para que el layout no salte al llegar los datos. */
export const ChartEmpty: React.FC<{ height?: number; message?: string }> = ({
  height = 180,
  message = CHART_EMPTY_MSG,
}) => (
  <div
    role="status"
    className="flex flex-col items-center justify-center gap-2 px-4 text-center rounded-lg border border-dashed border-ml-gray dark:border-ml-dark-border"
    style={{ minHeight: height }}
  >
    <svg className="w-5 h-5 text-ml-gray-dark dark:text-zinc-600" fill="none" stroke="currentColor" strokeWidth={1.6} viewBox="0 0 24 24" aria-hidden="true">
      <path strokeLinecap="round" strokeLinejoin="round" d="M3 3v18h18M7.5 15l3-3 3 2.5L18 9" />
    </svg>
    <p className="text-sm text-ml-text-soft dark:text-zinc-500">{message}</p>
  </div>
)
