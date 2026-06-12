import React from 'react'
import type { ContabilidadCtx } from './useContabilidad'

export const ContabilidadReglas: React.FC<{ c: ContabilidadCtx }> = ({ c }) => (
  <div className="border border-gray-200 dark:border-slate-700 rounded-xl overflow-hidden">
    {c.reglas.length === 0 ? <p className="text-center py-8 text-gray-400 text-sm">Sin reglas</p> : (
      <div className="overflow-x-auto"><table className="w-full text-xs min-w-[480px]">
        <thead className="bg-gray-50 dark:bg-slate-800">
          <tr>
            <th className="text-left px-4 py-2 font-medium text-gray-600 dark:text-gray-400">Evento</th>
            <th className="text-left px-4 py-2 font-medium text-blue-600 dark:text-blue-400">Debe</th>
            <th className="text-left px-4 py-2 font-medium text-orange-600 dark:text-orange-400">Haber</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-gray-100 dark:divide-slate-700/50">
          {c.reglas.map(r => (
            <tr key={r.id} className="hover:bg-gray-50 dark:hover:bg-slate-800/40">
              <td className="px-4 py-2">
                <span className="font-mono text-gray-700 dark:text-gray-300">{r.evento}</span>
                {r.descripcion && <p className="text-gray-400 dark:text-gray-500 mt-0.5">{r.descripcion}</p>}
              </td>
              <td className="px-4 py-2 text-blue-700 dark:text-blue-300">
                <span className="font-mono text-[10px] text-gray-400 mr-1">{r.debe.codigo}</span>{r.debe.nombre}
              </td>
              <td className="px-4 py-2 text-orange-700 dark:text-orange-300">
                <span className="font-mono text-[10px] text-gray-400 mr-1">{r.haber.codigo}</span>{r.haber.nombre}
              </td>
            </tr>
          ))}
        </tbody>
      </table></div>
    )}
  </div>
)
