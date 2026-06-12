import React from 'react'
import { CuentaItem, TIPO_TEXT, TIPO_BADGE } from './shared'
import type { ContabilidadCtx } from './useContabilidad'

export const ContabilidadPlanCuentas: React.FC<{ c: ContabilidadCtx }> = ({ c }) => {
  const renderCuenta = (cu: CuentaItem, depth = 0): React.ReactNode => {
    const children = c.hijos(cu.id)
    const textClass = depth === 0 ? 'font-bold' : depth === 1 ? 'font-semibold' : 'font-normal'
    const colorClass = cu.tipo ? (TIPO_TEXT[cu.tipo] || '') : 'text-ml-text dark:text-gray-200'
    return (
      <React.Fragment key={cu.id}>
        <div className="flex items-center gap-2 py-1 px-2 hover:bg-gray-50 dark:hover:bg-slate-800/50 transition-colors"
          style={{ paddingLeft: `${8 + depth * 20}px` }}>
          <span className="text-[11px] font-mono text-gray-400 w-16 shrink-0">{cu.codigo}</span>
          <span className={`text-xs ${textClass} ${colorClass}`}>{cu.nombre}</span>
          {cu.tipo && depth === 0 && (
            <span className={`text-[10px] px-1.5 py-0.5 rounded-full border ${TIPO_BADGE[cu.tipo] || ''}`}>{cu.tipo}</span>
          )}
        </div>
        {children.map(ch => renderCuenta(ch, depth + 1))}
      </React.Fragment>
    )
  }

  return (
    <div className="border border-gray-200 dark:border-slate-700 rounded-xl overflow-hidden bg-white dark:bg-slate-900/50">
      {c.raices.length === 0 ? <p className="text-center py-8 text-gray-400 text-sm">Sin datos</p> : (
        <div className="divide-y divide-gray-100 dark:divide-slate-800">
          {c.raices.map(r => renderCuenta(r, 0))}
        </div>
      )}
    </div>
  )
}
