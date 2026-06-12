import React from 'react'
import { fmtDate, fmtNum } from './shared'
import type { ContabilidadCtx } from './useContabilidad'

export const ContabilidadMayor: React.FC<{ c: ContabilidadCtx }> = ({ c }) => {
  const { libroMayor } = c
  return (
    <div className="space-y-4">
      <div className="flex items-center gap-3">
        <select
          className="input-field text-sm flex-1 max-w-xs"
          value={c.mayorCuentaId}
          onChange={e => {
            const id = Number(e.target.value)
            c.setMayorCuentaId(id || '')
            if (id) c.cargarLibroMayor(id)
            else c.setLibroMayor(null)
          }}
        >
          <option value="">— Seleccioná una cuenta —</option>
          {c.cuentas.map(cu => (
            <option key={cu.id} value={cu.id}>{cu.codigo} — {cu.nombre}</option>
          ))}
        </select>
      </div>

      {c.loadingMayor ? (
        <div className="py-8 text-center text-gray-400">Cargando...</div>
      ) : !libroMayor ? (
        <div className="py-12 text-center text-gray-400 text-sm">
          Seleccioná una cuenta para ver sus movimientos
        </div>
      ) : libroMayor.movimientos.length === 0 ? (
        <div className="py-12 text-center text-gray-400 text-sm">
          Sin movimientos para <strong>{libroMayor.cuenta.nombre}</strong>
        </div>
      ) : (
        <div className="border border-gray-200 dark:border-slate-700 rounded-xl overflow-hidden">
          <div className="px-4 py-2 bg-gray-50 dark:bg-slate-800 flex items-center justify-between">
            <p className="text-xs font-semibold text-ml-text dark:text-white">
              {libroMayor.cuenta.codigo} — {libroMayor.cuenta.nombre}
            </p>
            <p className="text-xs text-gray-500">
              Saldo final: <span className="font-mono font-medium">{fmtNum(libroMayor.saldo_final)}</span>
            </p>
          </div>
          <div className="overflow-x-auto"><table className="w-full text-xs min-w-[400px]">
            <thead className="bg-gray-50 dark:bg-slate-800 border-t border-gray-100 dark:border-slate-700">
              <tr>
                <th className="text-left px-4 py-2 font-medium text-gray-500">Fecha</th>
                <th className="text-left px-4 py-2 font-medium text-gray-500">Descripción</th>
                <th className="text-right px-4 py-2 font-medium text-blue-600 dark:text-blue-400">Debe</th>
                <th className="text-right px-4 py-2 font-medium text-orange-600 dark:text-orange-400">Haber</th>
                <th className="text-right px-4 py-2 font-medium text-gray-500">Saldo</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100 dark:divide-slate-700/50">
              {libroMayor.movimientos.map((m, i) => (
                <tr key={i} className="hover:bg-gray-50 dark:hover:bg-slate-800/40">
                  <td className="px-4 py-2 whitespace-nowrap text-gray-600 dark:text-gray-400">{fmtDate(m.fecha)}</td>
                  <td className="px-4 py-2 text-gray-700 dark:text-gray-300">{m.descripcion || '—'}</td>
                  <td className="px-4 py-2 text-right font-mono text-blue-700 dark:text-blue-300">{m.debe > 0 ? fmtNum(m.debe) : ''}</td>
                  <td className="px-4 py-2 text-right font-mono text-orange-700 dark:text-orange-300">{m.haber > 0 ? fmtNum(m.haber) : ''}</td>
                  <td className="px-4 py-2 text-right font-mono text-gray-700 dark:text-gray-300">{fmtNum(m.saldo)}</td>
                </tr>
              ))}
            </tbody>
            <tfoot className="bg-gray-50 dark:bg-slate-800 border-t border-gray-200 dark:border-slate-700">
              <tr>
                <td colSpan={2} className="px-4 py-2 text-xs font-semibold text-gray-600 dark:text-gray-400">Totales</td>
                <td className="px-4 py-2 text-right font-mono font-semibold text-blue-700 dark:text-blue-300">{fmtNum(libroMayor.total_debe)}</td>
                <td className="px-4 py-2 text-right font-mono font-semibold text-orange-700 dark:text-orange-300">{fmtNum(libroMayor.total_haber)}</td>
                <td className="px-4 py-2 text-right font-mono font-semibold">{fmtNum(libroMayor.saldo_final)}</td>
              </tr>
            </tfoot>
          </table></div>
        </div>
      )}
    </div>
  )
}
