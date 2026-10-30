import React, { useState } from 'react'
import { ResumenExtracto as ResumenExtractoData } from '@/types'

interface ResumenExtractoProps {
  resumen: ResumenExtractoData | null | undefined
}

function fmtARS(n: number | string) {
  return new Intl.NumberFormat('es-AR', { style: 'currency', currency: 'ARS', minimumFractionDigits: 2 }).format(Number(n))
}

function colorDe(pct: number | null) {
  return pct == null ? 'text-gray-400'
    : pct >= 90 ? 'text-green-600 dark:text-green-400'
    : pct >= 60 ? 'text-amber-600 dark:text-amber-400'
    : 'text-red-600 dark:text-red-400'
}

/**
 * Barra de resumen del extracto: % de ingresos ya acreditados a un cliente,
 * % de egresos explicados (gasto bancario o pago vinculado) y gastos bancarios
 * agrupados por concepto (para cuadrar la nota de débito del banco al centavo).
 * Read-only. Se despliega al tocarla.
 */
export const ResumenExtracto: React.FC<ResumenExtractoProps> = ({ resumen }) => {
  const [abierto, setAbierto] = useState(false)
  if (!resumen) return null

  const { explicado, gastos_bancarios: gastos, debitos } = resumen
  const hayDebitos = !!debitos && debitos.debitos > 0
  if (explicado.creditos === 0 && gastos.cantidad === 0 && !hayDebitos) return null

  const pct = explicado.porcentaje
  const colorPct = colorDe(pct)
  const pctDeb = hayDebitos ? debitos!.porcentaje : null

  return (
    <div className="mb-3 bg-white dark:bg-slate-800 border border-gray-100 dark:border-slate-700 rounded-lg shadow-xs" data-testid="resumen-extracto">
      <button
        type="button"
        onClick={() => setAbierto(a => !a)}
        aria-expanded={abierto}
        className="w-full flex flex-wrap items-center gap-x-4 gap-y-1 px-3 py-2 text-left text-xs"
      >
        {pct != null && (
          <span className="dark:text-gray-200">
            <b className={`text-sm ${colorPct}`}>{pct.toLocaleString('es-AR')}%</b> de los ingresos acreditados
            <span className="text-gray-400 dark:text-gray-500"> · {explicado.acreditados} de {explicado.creditos}</span>
          </span>
        )}
        {pctDeb != null && (
          <span className="dark:text-gray-200">
            <b className={`text-sm ${colorDe(pctDeb)}`}>{pctDeb.toLocaleString('es-AR')}%</b> de los egresos explicados
            <span className="text-gray-400 dark:text-gray-500"> · {debitos!.explicados} de {debitos!.debitos}</span>
          </span>
        )}
        {gastos.cantidad > 0 && (
          <span className="dark:text-gray-200">
            Gastos bancarios <b className="font-mono">{fmtARS(gastos.total)}</b>
            <span className="text-gray-400 dark:text-gray-500"> · {gastos.cantidad} mov.</span>
          </span>
        )}
        <span className="ml-auto text-gray-400">{abierto ? 'Ocultar ▴' : 'Ver detalle ▾'}</span>
      </button>

      {abierto && (
        <div className="px-3 pb-3 border-t border-gray-100 dark:border-slate-700">
          {pct != null && (
            <div className="pt-2">
              <div className="h-1.5 rounded-full bg-gray-100 dark:bg-slate-700 overflow-hidden">
                <div className="h-full bg-green-500" style={{ width: `${Math.min(100, pct)}%` }} />
              </div>
              {explicado.sin_acreditar > 0 && (
                <p className="mt-1 text-[11px] text-gray-500 dark:text-gray-400">
                  {explicado.sin_acreditar === 1 ? 'Queda 1 ingreso' : `Quedan ${explicado.sin_acreditar} ingresos`} sin acreditar a un cliente. Filtrá la columna "Acred." por "Sin acreditar" para verlos.
                </p>
              )}
            </div>
          )}

          {pctDeb != null && debitos!.sin_explicar > 0 && (
            <p className="mt-2 text-[11px] text-gray-500 dark:text-gray-400">
              {debitos!.sin_explicar === 1 ? 'Queda 1 egreso sin explicar' : `Quedan ${debitos!.sin_explicar} egresos sin explicar`}
              {' '}por <b className="font-mono">{fmtARS(debitos!.total_sin_explicar)}</b>. Usá "＋ Resolver" en cada uno para registrar el pago que lo explica.
            </p>
          )}

          {gastos.cantidad > 0 && (
            <table className="mt-3 w-full text-xs">
              <thead>
                <tr className="text-[10px] uppercase text-gray-400 dark:text-gray-500">
                  <th className="text-left font-semibold py-1">Gasto bancario</th>
                  <th className="text-right font-semibold py-1 w-16">Cant.</th>
                  <th className="text-right font-semibold py-1 w-32">Total</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100 dark:divide-slate-700">
                {gastos.conceptos.map(c => (
                  <tr key={c.concepto}>
                    <td className="py-1 dark:text-gray-200">{c.concepto}</td>
                    <td className="py-1 text-right text-gray-500 dark:text-gray-400">{c.cantidad}</td>
                    <td className="py-1 text-right font-mono dark:text-gray-200">{fmtARS(c.total)}</td>
                  </tr>
                ))}
                <tr className="font-semibold">
                  <td className="py-1.5 dark:text-white">Total según extracto</td>
                  <td className="py-1.5 text-right dark:text-white">{gastos.cantidad}</td>
                  <td className="py-1.5 text-right font-mono dark:text-white">{fmtARS(gastos.total)}</td>
                </tr>
              </tbody>
            </table>
          )}
          {gastos.cantidad > 0 && (
            <p className="mt-1 text-[11px] text-gray-400 dark:text-gray-500">
              Compará este total con la nota de débito o el resumen de gastos del banco.
            </p>
          )}
        </div>
      )}
    </div>
  )
}
