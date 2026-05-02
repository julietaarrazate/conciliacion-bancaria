import React, { useEffect, useState } from 'react'
import { apiClient } from '@/services/api'

interface Row {
  id: number
  monto: number
  cuit?: string
  titular?: string
  status: string
  orden_movimiento_acreditado?: number
}

interface Detalle {
  id: number
  nombre_archivo: string
  cliente_nombre: string
  extracto_nombre: string
  fecha_carga: string
  usuario_nombre: string
  rows: Row[]
  total: number
  acreditadas: number
  no_encontradas: number
  duplicadas: number
  sin_datos: number
}

interface Props {
  planillaId: number | null
  onClose: () => void
  onDelete?: (id: number) => void
}

const statusStyle = (s: string) => {
  if (s === 'ok') return 'bg-green-100 text-green-800 dark:bg-green-900/40 dark:text-green-300'
  if (s === 'no está') return 'bg-red-100 text-red-700 dark:bg-red-900/40 dark:text-red-300'
  if (s === 'faltan datos') return 'bg-blue-100 text-blue-700 dark:bg-blue-900/40 dark:text-blue-300'
  if (s === 'duplicado' || s.startsWith('acreditado')) return 'bg-yellow-100 text-yellow-700 dark:bg-yellow-900/40 dark:text-yellow-300'
  return 'bg-gray-100 text-gray-700'
}

export const PlanillaPanel: React.FC<Props> = ({ planillaId, onClose, onDelete }) => {
  const [detalle, setDetalle] = useState<Detalle | null>(null)
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    if (!planillaId) { setDetalle(null); return }
    setLoading(true)
    apiClient.client
      .get(`/planillas/${planillaId}/detalle`)
      .then(r => setDetalle(r.data))
      .catch(() => setDetalle(null))
      .finally(() => setLoading(false))
  }, [planillaId])

  if (!planillaId) return null

  const fmtARS = (n: number) =>
    new Intl.NumberFormat('es-AR', { style: 'currency', currency: 'ARS' }).format(n)

  return (
    <>
      {/* Overlay */}
      <div
        className="fixed inset-0 bg-black/40 z-40"
        onClick={onClose}
      />

      {/* Panel deslizante desde la derecha */}
      <div className="fixed right-0 top-0 h-full w-full max-w-xl bg-white dark:bg-slate-800 shadow-2xl z-50 flex flex-col">
        {/* Header */}
        <div className="flex items-start justify-between p-4 border-b dark:border-slate-700 bg-ml-yellow">
          <div>
            <p className="font-bold text-ml-text text-sm">
              {detalle?.cliente_nombre ?? '...'}
            </p>
            <p className="text-xs text-ml-text-soft truncate max-w-[300px]">
              {detalle?.nombre_archivo}
            </p>
          </div>
          <div className="flex items-center gap-2">
            {detalle && onDelete && (
              <button
                onClick={() => { onDelete(detalle.id); onClose() }}
                className="text-red-600 hover:bg-red-100 p-1.5 rounded text-sm"
                title="Borrar planilla"
              >🗑️</button>
            )}
            <button
              onClick={onClose}
              className="text-ml-text hover:bg-ml-yellow-dark p-1.5 rounded text-lg leading-none"
            >✕</button>
          </div>
        </div>

        {loading && (
          <div className="flex-1 flex items-center justify-center text-ml-text-soft">
            Cargando...
          </div>
        )}

        {detalle && (
          <>
            {/* Stats */}
            <div className="grid grid-cols-4 gap-px bg-gray-100 dark:bg-slate-700 border-b dark:border-slate-700">
              {[
                { label: 'Acreditadas', val: detalle.acreditadas, cls: 'text-green-600 dark:text-green-400' },
                { label: 'No encontradas', val: detalle.no_encontradas, cls: 'text-red-600 dark:text-red-400' },
                { label: 'Duplicadas', val: detalle.duplicadas, cls: 'text-yellow-600 dark:text-yellow-400' },
                { label: 'Sin datos', val: detalle.sin_datos, cls: 'text-blue-600 dark:text-blue-400' },
              ].map(s => (
                <div key={s.label} className="bg-white dark:bg-slate-800 p-3 text-center">
                  <p className={`text-xl font-bold ${s.cls}`}>{s.val}</p>
                  <p className="text-[10px] text-ml-text-soft uppercase">{s.label}</p>
                </div>
              ))}
            </div>

            {/* Metadata */}
            <div className="px-4 py-2 text-xs text-ml-text-soft dark:text-gray-400 flex gap-4 border-b dark:border-slate-700">
              <span>📅 {new Date(detalle.fecha_carga).toLocaleString('es-AR', { dateStyle: 'short', timeStyle: 'short' })}</span>
              <span>👤 {detalle.usuario_nombre}</span>
              <span>📄 {detalle.total} filas</span>
            </div>

            {/* Tabla de filas */}
            <div className="flex-1 overflow-y-auto">
              <table className="w-full text-sm">
                <thead className="sticky top-0 bg-ml-gray-bg dark:bg-slate-900 border-b dark:border-slate-700">
                  <tr>
                    <th className="px-3 py-2 text-left text-xs text-ml-text-soft uppercase">#</th>
                    <th className="px-3 py-2 text-right text-xs text-ml-text-soft uppercase">Importe</th>
                    <th className="px-3 py-2 text-left text-xs text-ml-text-soft uppercase">CUIT</th>
                    <th className="px-3 py-2 text-left text-xs text-ml-text-soft uppercase">Estado</th>
                  </tr>
                </thead>
                <tbody className="divide-y dark:divide-slate-700">
                  {detalle.rows.map((row, i) => (
                    <tr key={row.id} className="hover:bg-ml-gray-bg dark:hover:bg-slate-700/50">
                      <td className="px-3 py-2 text-ml-text-soft dark:text-gray-400">{i + 1}</td>
                      <td className="px-3 py-2 text-right font-mono dark:text-white">
                        {fmtARS(row.monto)}
                      </td>
                      <td className="px-3 py-2 text-xs text-ml-text-soft dark:text-gray-400 max-w-[100px] truncate">
                        {row.cuit || row.titular || '—'}
                      </td>
                      <td className="px-3 py-2">
                        <span className={`inline-flex px-2 py-0.5 rounded-full text-xs font-medium ${statusStyle(row.status)}`}>
                          {row.status}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </>
        )}
      </div>
    </>
  )
}
