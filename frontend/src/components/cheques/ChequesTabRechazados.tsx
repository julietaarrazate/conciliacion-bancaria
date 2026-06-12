import React from 'react'
import { Cheque, LiBadge, fmt, fmtDate } from './shared'

interface Props {
  rechazadosList: Cheque[]
  rechazadosLoading: boolean
}

export const ChequesTabRechazados: React.FC<Props> = ({ rechazadosList, rechazadosLoading }) => (
  <div className="space-y-4">
    {rechazadosLoading ? (
      <p className="text-sm text-gray-500 text-center py-8">Cargando…</p>
    ) : rechazadosList.length === 0 ? (
      <p className="text-sm text-gray-500 text-center py-8">No hay cheques rechazados</p>
    ) : (
      <div className="rounded-xl overflow-hidden border border-gray-200 dark:border-white/8">
        <div className="overflow-x-auto">
          <table className="w-full text-xs min-w-[960px]">
            <thead>
              <tr className="bg-gray-50 dark:bg-white/4 text-left text-gray-400">
                <th className="px-3 py-2 font-medium">F. Depósito</th>
                <th className="px-3 py-2 font-medium">F. Rechazo</th>
                <th className="px-3 py-2 font-medium">Cliente</th>
                <th className="px-3 py-2 font-medium">F. Cheque</th>
                <th className="px-3 py-2 font-medium">N° Banco</th>
                <th className="px-3 py-2 font-medium">Banco</th>
                <th className="px-3 py-2 font-medium">Librador</th>
                <th className="px-3 py-2 font-medium">N° Cheque</th>
                <th className="px-3 py-2 font-medium">CP</th>
                <th className="px-3 py-2 font-medium">L/I</th>
                <th className="px-3 py-2 font-medium text-right">Importe</th>
                <th className="px-3 py-2 font-medium">Físico</th>
                <th className="px-3 py-2 font-medium">F. Devolución</th>
              </tr>
            </thead>
            <tbody>
              {rechazadosList.map((c, i) => (
                <tr key={c.id} className={`border-t border-gray-100 dark:border-white/5 hover:bg-gray-50 dark:hover:bg-white/2 ${i % 2 === 0 ? '' : 'bg-gray-50/60 dark:bg-white/1'}`}>
                  <td className="px-3 py-2 text-gray-400 whitespace-nowrap">{fmtDate(c.fecha_deposito)}</td>
                  <td className="px-3 py-2 text-red-600 dark:text-red-400 whitespace-nowrap">{fmtDate(c.fecha_rechazo)}</td>
                  <td className="px-3 py-2 text-gray-800 dark:text-gray-200">{c.cliente_nombre || '—'}</td>
                  <td className="px-3 py-2 text-gray-400 whitespace-nowrap">{fmtDate(c.fecha_emision)}</td>
                  <td className="px-3 py-2 text-gray-400">{c.numero || '—'}</td>
                  <td className="px-3 py-2 text-gray-400">{c.banco_origen || '—'}</td>
                  <td className="px-3 py-2 text-gray-700 dark:text-gray-300 max-w-[100px] truncate" title={c.librador || c.titular || ''}>{c.librador || c.titular || '—'}</td>
                  <td className="px-3 py-2 text-gray-400">{c.numero || '—'}</td>
                  <td className="px-3 py-2 text-gray-400">{c.codigo_postal || '—'}</td>
                  <td className="px-3 py-2"><LiBadge value={c.local_interior} /></td>
                  <td className="px-3 py-2 text-right font-mono text-gray-900 dark:text-gray-100">{fmt(c.monto)}</td>
                  <td className="px-3 py-2">
                    {c.fisico
                      ? <span className="px-1.5 py-0.5 rounded text-xs bg-blue-50 text-blue-700 dark:bg-blue-500/15 dark:text-blue-400">Sí</span>
                      : <span className="text-gray-600">No</span>
                    }
                  </td>
                  <td className="px-3 py-2 text-gray-400 whitespace-nowrap">{fmtDate(c.fecha_devolucion)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    )}
  </div>
)
