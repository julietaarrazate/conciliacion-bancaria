import React from 'react'
import { fmtNum, TIPO_TEXT, TIPO_BG } from './shared'
import type { ContabilidadCtx } from './useContabilidad'

export const ContabilidadSumas: React.FC<{ c: ContabilidadCtx }> = ({ c }) => (
  <div className="border border-gray-200 dark:border-slate-700 rounded-xl overflow-hidden">
    {c.sumasSaldo.length === 0 ? (
      <div className="py-16 text-center text-gray-400">
        <p className="text-sm">Sin movimientos contables todavía.</p>
      </div>
    ) : (
      <div className="overflow-x-auto"><table className="w-full text-xs min-w-[500px]">
        <thead className="bg-gray-50 dark:bg-slate-800">
          <tr>
            <th className="text-left px-4 py-2 font-medium text-gray-500">Código</th>
            <th className="text-left px-4 py-2 font-medium text-gray-500">Cuenta</th>
            <th className="text-right px-4 py-2 font-medium text-blue-600 dark:text-blue-400">Debe</th>
            <th className="text-right px-4 py-2 font-medium text-orange-600 dark:text-orange-400">Haber</th>
            <th className="text-right px-4 py-2 font-medium text-gray-500">Saldo D</th>
            <th className="text-right px-4 py-2 font-medium text-gray-500">Saldo H</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-gray-100 dark:divide-slate-700/50">
          {c.sumasSaldo.map(r => (
            <tr key={r.id} className="hover:bg-gray-50 dark:hover:bg-slate-800/40">
              <td className="px-4 py-2 font-mono text-gray-400">{r.codigo}</td>
              <td className="px-4 py-2 text-gray-700 dark:text-gray-300">{r.nombre}</td>
              <td className="px-4 py-2 text-right text-blue-700 dark:text-blue-300 font-mono">{fmtNum(r.total_debe)}</td>
              <td className="px-4 py-2 text-right text-orange-700 dark:text-orange-300 font-mono">{fmtNum(r.total_haber)}</td>
              <td className="px-4 py-2 text-right font-mono text-gray-700 dark:text-gray-300">{r.saldo_deudor > 0 ? fmtNum(r.saldo_deudor) : ''}</td>
              <td className="px-4 py-2 text-right font-mono text-gray-700 dark:text-gray-300">{r.saldo_acreedor > 0 ? fmtNum(r.saldo_acreedor) : ''}</td>
            </tr>
          ))}
        </tbody>
      </table></div>
    )}
  </div>
)

export const ContabilidadBalance: React.FC<{ c: ContabilidadCtx }> = ({ c }) => {
  const { balance } = c
  return (
    <div className="space-y-3">
      {!balance ? (
        <p className="text-center py-8 text-gray-400 text-sm">Sin datos</p>
      ) : (
        <>
          {(['activo', 'pasivo', 'resultado'] as const).map(tipo => (
            <div key={tipo} className={`border rounded-xl p-4 ${TIPO_BG[tipo] || ''}`}>
              <div className="flex items-center justify-between">
                <div>
                  <p className={`text-xs font-bold uppercase tracking-wider ${TIPO_TEXT[tipo]}`}>{tipo}</p>
                  <p className="text-2xl font-bold text-ml-text dark:text-white mt-1">
                    $ {fmtNum(tipo === 'resultado' ? -(balance[tipo].saldo) : Math.abs(balance[tipo].saldo))}
                  </p>
                </div>
                <div className="text-right text-xs text-gray-500 dark:text-gray-400 space-y-1">
                  <p>Debe: <span className="font-mono">{fmtNum(balance[tipo].total_debe)}</span></p>
                  <p>Haber: <span className="font-mono">{fmtNum(balance[tipo].total_haber)}</span></p>
                </div>
              </div>
            </div>
          ))}
          <div className={`border rounded-xl p-3 text-center text-xs ${balance.ecuacion_ok ? 'bg-green-50 dark:bg-green-900/20 border-green-200 text-green-700 dark:text-green-400' : 'bg-red-50 dark:bg-red-900/20 border-red-200 text-red-700 dark:text-red-400'}`}>
            {balance.ecuacion_ok ? '✓ Ecuación contable OK: Activo = Pasivo + Resultado' : '⚠ Ecuación contable desequilibrada — revisar asientos'}
          </div>
        </>
      )}
    </div>
  )
}
