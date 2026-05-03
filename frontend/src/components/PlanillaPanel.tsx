import React, { useEffect, useState, useMemo } from 'react'
import { apiClient } from '@/services/api'

interface Row {
  id: number
  monto: number
  cuit?: string
  titular?: string
  status: string
  orden_movimiento_acreditado?: number
  mov_titular?: string
  mov_fecha?: string
  mov_fecha_acred?: string
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

interface Filters {
  importe: string
  cuit: string
  titular: string
  mov_titular: string
  mov_fecha: string
  mov_fecha_acred: string
  status: string
}

const EMPTY_FILTERS: Filters = {
  importe: '', cuit: '', titular: '', mov_titular: '',
  mov_fecha: '', mov_fecha_acred: '', status: ''
}

const statusStyle = (s: string) => {
  if (s === 'ok') return 'bg-green-100 text-green-800 dark:bg-green-900/40 dark:text-green-300'
  if (s === 'no está') return 'bg-red-100 text-red-700 dark:bg-red-900/40 dark:text-red-300'
  if (s === 'faltan datos') return 'bg-blue-100 text-blue-700 dark:bg-blue-900/40 dark:text-blue-300'
  if (s === 'duplicado' || s.startsWith('acreditado'))
    return 'bg-yellow-100 text-yellow-700 dark:bg-yellow-900/40 dark:text-yellow-300'
  return 'bg-gray-100 text-gray-700 dark:bg-gray-700 dark:text-gray-300'
}

const fmtDate = (d?: string | null) => {
  if (!d) return '—'
  try {
    const dt = new Date(d.includes('T') ? d : d + 'T00:00:00')
    return dt.toLocaleDateString('es-AR', { day: '2-digit', month: '2-digit', year: '2-digit' })
  } catch { return d }
}

const fmtARS = (n: number) =>
  new Intl.NumberFormat('es-AR', { style: 'currency', currency: 'ARS', minimumFractionDigits: 0 }).format(n)

interface Props {
  planillaId: number | null
  onClose: () => void
  onDelete?: (id: number) => void
}

const ESTADOS_DISPONIBLES = [
  'ok', 'no está', 'duplicado', 'faltan datos', 'pendiente',
  'PAGO_PARCIAL', 'CONCILIADO_CON_DIFERENCIA', 'VENCIDO', 'EN_REVISION'
]

export const PlanillaPanel: React.FC<Props> = ({ planillaId, onClose, onDelete }) => {
  const [detalle, setDetalle] = useState<Detalle | null>(null)
  const [loading, setLoading] = useState(false)
  const [filters, setFilters] = useState<Filters>(EMPTY_FILTERS)
  const [showFilters, setShowFilters] = useState(false)
  const [editingRowId, setEditingRowId] = useState<number | null>(null)
  const [editStatus, setEditStatus] = useState('')
  const [savingRow, setSavingRow] = useState(false)

  useEffect(() => {
    if (!planillaId) { setDetalle(null); setFilters(EMPTY_FILTERS); return }
    setLoading(true)
    apiClient.client
      .get(`/planillas/${planillaId}/detalle`)
      .then(r => setDetalle(r.data))
      .catch(() => setDetalle(null))
      .finally(() => setLoading(false))
  }, [planillaId])


  const filteredRows = useMemo(() => {
    if (!detalle) return []
    return detalle.rows.filter(row => {
      const f = filters
      if (f.importe && !String(row.monto).includes(f.importe.replace(/\./g, '').replace(/,/g, '.'))) return false
      if (f.cuit && !(row.cuit || '').toLowerCase().includes(f.cuit.toLowerCase())) return false
      if (f.titular && !(row.titular || '').toLowerCase().includes(f.titular.toLowerCase())) return false
      if (f.mov_titular && !(row.mov_titular || '').toLowerCase().includes(f.mov_titular.toLowerCase())) return false
      if (f.mov_fecha && !(row.mov_fecha || '').includes(f.mov_fecha)) return false
      if (f.mov_fecha_acred && !(row.mov_fecha_acred || '').includes(f.mov_fecha_acred)) return false
      if (f.status && row.status !== f.status) return false
      return true
    })
  }, [detalle, filters])

  const hasFilters = Object.values(filters).some(v => v !== '')
  const clearFilters = () => setFilters(EMPTY_FILTERS)

  const setFilter = (k: keyof Filters, v: string) =>
    setFilters(prev => ({ ...prev, [k]: v }))

  const uniqueStatuses = useMemo(() => {
    if (!detalle) return []
    return [...new Set(detalle.rows.map(r => r.status))].sort()
  }, [detalle])

  const startEdit = (row: Row) => {
    setEditingRowId(row.id)
    setEditStatus(row.status)
  }

  const saveEdit = async (rowId: number) => {
    setSavingRow(true)
    try {
      await apiClient.patchRowStatus(rowId, editStatus)
      setDetalle(prev => prev ? {
        ...prev,
        rows: prev.rows.map(r => r.id === rowId ? { ...r, status: editStatus } : r)
      } : prev)
      setEditingRowId(null)
    } finally { setSavingRow(false) }
  }


  if (!planillaId) return null

  const FilterInput = ({ field, placeholder }: { field: keyof Filters; placeholder: string }) => (
    <input
      className="w-full px-1.5 py-0.5 text-xs border border-gray-300 dark:border-slate-600 rounded bg-white dark:bg-slate-700 dark:text-gray-200 focus:outline-none focus:border-ml-blue"
      placeholder={placeholder}
      value={filters[field]}
      onChange={e => setFilter(field, e.target.value)}
    />
  )

  return (
    <>
      <div className="fixed inset-0 bg-black/40 z-40" onClick={onClose} />

      <div
        className="fixed right-0 top-0 h-full w-full max-w-2xl bg-white dark:bg-slate-800 shadow-2xl z-50 flex flex-col"
      >
        {/* Header */}
        <div className="flex items-start justify-between px-4 py-3 bg-ml-yellow dark:bg-ml-dark-surface dark:border-b dark:border-ml-green/30 border-b">
          <div className="flex-1 min-w-0">
            <p className="font-bold text-ml-text text-sm truncate">{detalle?.cliente_nombre ?? '...'}</p>
            <p className="text-xs text-ml-text-soft truncate">{detalle?.nombre_archivo}</p>
          </div>
          <div className="flex items-center gap-1 ml-2 shrink-0">
            <button
              onClick={() => setShowFilters(s => !s)}
              className={`px-2 py-1 text-xs rounded font-medium ${showFilters || hasFilters ? 'bg-ml-blue text-white' : 'bg-white/70 text-ml-text hover:bg-white'}`}
              title="Filtros por columna"
            >
              🔽 {hasFilters ? `Filtros (${Object.values(filters).filter(Boolean).length})` : 'Filtrar'}
            </button>
            {hasFilters && (
              <button onClick={clearFilters} className="px-2 py-1 text-xs bg-white/70 text-red-600 rounded hover:bg-white">
                ✕ Limpiar
              </button>
            )}
            {detalle && onDelete && (
              <button
                onClick={() => { onDelete(detalle.id); onClose() }}
                className="px-2 py-1 text-red-700 hover:bg-red-100 rounded text-sm"
              >🗑️</button>
            )}
            <button onClick={onClose} className="px-2 py-1 text-ml-text dark:text-gray-300 hover:bg-ml-yellow-dark dark:hover:bg-ml-dark-border rounded text-lg leading-none">✕</button>
          </div>
        </div>

        {/* Stats */}
        {detalle && (
          <div className="grid grid-cols-4 gap-px bg-gray-100 dark:bg-slate-700">
            {[
              { label: 'OK', val: detalle.acreditadas, cls: 'text-green-600 dark:text-green-400', filter: 'ok' },
              { label: 'No está', val: detalle.no_encontradas, cls: 'text-red-600 dark:text-red-400', filter: 'no está' },
              { label: 'Duplicadas', val: detalle.duplicadas, cls: 'text-yellow-600 dark:text-yellow-400', filter: 'duplicado' },
              { label: 'Sin datos', val: detalle.sin_datos, cls: 'text-blue-600 dark:text-blue-400', filter: 'faltan datos' },
            ].map(s => (
              <button
                key={s.label}
                onClick={() => setFilter('status', filters.status === s.filter ? '' : s.filter)}
                className={`bg-white dark:bg-slate-800 p-2.5 text-center hover:bg-ml-gray-bg dark:hover:bg-slate-700 transition-colors ${filters.status === s.filter ? 'ring-2 ring-inset ring-ml-blue' : ''}`}
                title={`Filtrar por ${s.label}`}
              >
                <p className={`text-xl font-bold ${s.cls}`}>{s.val}</p>
                <p className="text-[10px] text-ml-text-soft uppercase">{s.label}</p>
              </button>
            ))}
          </div>
        )}

        {/* Meta */}
        {detalle && (
          <div className="px-4 py-1.5 text-xs text-ml-text-soft dark:text-gray-400 flex gap-4 border-b dark:border-slate-700 bg-ml-gray-bg dark:bg-slate-900">
            <span>📅 {fmtDate(detalle.fecha_carga)}</span>
            <span>👤 {detalle.usuario_nombre}</span>
            <span>{filteredRows.length}/{detalle.total} filas{hasFilters ? ' (filtrado)' : ''}</span>
          </div>
        )}

        {loading && <div className="flex-1 flex items-center justify-center text-ml-text-soft">Cargando...</div>}

        {detalle && (
          <div className="flex-1 overflow-auto">
            <table className="w-full text-xs min-w-[780px]">
              <thead className="sticky top-0 z-10">
                {/* Headers azul banco Macro — con Estado al FINAL */}
                <tr>
                  {['#','Importe','CUIT','Titular planilla','Titular extracto','Fecha mov.','Saldo','Cliente acred.','Fecha acred.','Estado'].map(h => (
                    <th key={h} className="px-2 py-2.5 text-left font-bold text-white bg-ml-blue border-r border-blue-400 last:border-r-0 whitespace-nowrap">
                      {h}
                    </th>
                  ))}
                </tr>

                {/* Fila de filtros (se muestra/oculta) */}
                {showFilters && (
                  <tr className="bg-blue-50 dark:bg-blue-900/10 border-b border-ml-blue/30">
                    <td className="px-1 py-1"></td>
                    <td className="px-1 py-1"><FilterInput field="importe" placeholder="🔍" /></td>
                    <td className="px-1 py-1"><FilterInput field="cuit" placeholder="🔍 CUIT" /></td>
                    <td className="px-1 py-1"><FilterInput field="titular" placeholder="🔍 titular" /></td>
                    <td className="px-1 py-1"><FilterInput field="mov_titular" placeholder="🔍 extracto" /></td>
                    <td className="px-1 py-1"><FilterInput field="mov_fecha" placeholder="🔍 fecha" /></td>
                    <td className="px-1 py-1"></td>
                    <td className="px-1 py-1"></td>
                    <td className="px-1 py-1"><FilterInput field="mov_fecha_acred" placeholder="🔍 acred." /></td>
                    <td className="px-1 py-1">
                      <select className="w-full px-1.5 py-0.5 text-xs border border-gray-300 dark:border-slate-600 rounded bg-white dark:bg-slate-700 dark:text-gray-200"
                        value={filters.status} onChange={e => setFilter('status', e.target.value)}>
                        <option value="">Todos</option>
                        {uniqueStatuses.map(s => <option key={s} value={s}>{s}</option>)}
                      </select>
                    </td>
                  </tr>
                )}
              </thead>

              <tbody className="divide-y dark:divide-slate-700">
                {filteredRows.length === 0 ? (
                  <tr>
                    <td colSpan={8} className="px-4 py-6 text-center text-ml-text-soft">
                      Sin resultados para los filtros aplicados
                    </td>
                  </tr>
                ) : (
                  filteredRows.map((row, i) => (
                    <tr key={row.id} className="hover:bg-ml-gray-bg dark:hover:bg-slate-700/50 divide-x divide-gray-100 dark:divide-slate-700">
                      <td className="px-2 py-1.5 text-gray-400 dark:text-gray-500">{i + 1}</td>
                      <td className="px-2 py-1.5 text-right font-mono font-semibold dark:text-white whitespace-nowrap">{fmtARS(row.monto)}</td>
                      <td className="px-2 py-1.5 text-gray-500 dark:text-gray-400 font-mono text-[10px]">{row.cuit || '—'}</td>
                      <td className="px-2 py-1.5 dark:text-gray-300 max-w-[130px] truncate" title={row.titular || ''}>{row.titular || '—'}</td>
                      <td className="px-2 py-1.5 text-gray-500 dark:text-gray-400 max-w-[180px] truncate" title={row.mov_titular || ''}>{row.mov_titular || '—'}</td>
                      <td className="px-2 py-1.5 whitespace-nowrap text-gray-500 dark:text-gray-400">{fmtDate(row.mov_fecha)}</td>
                      <td className="px-2 py-1.5 text-right font-mono text-gray-400 dark:text-gray-500">—</td>
                      <td className="px-2 py-1.5 text-gray-500 dark:text-gray-400 whitespace-nowrap">
                        {row.status === 'ok' ? <span className="text-green-600 dark:text-green-400 text-[10px] font-medium">{row.mov_titular?.split(' ').slice(0,2).join(' ') || '—'}</span> : '—'}
                      </td>
                      <td className="px-2 py-1.5 whitespace-nowrap text-gray-500 dark:text-gray-400">{fmtDate(row.mov_fecha_acred)}</td>
                      <td className="px-2 py-1.5 min-w-[130px]">
                        {editingRowId === row.id ? (
                          <div className="flex items-center gap-1">
                            <select
                              className="text-[10px] border border-ml-blue rounded px-1 py-0.5 bg-white dark:bg-slate-700 dark:text-white"
                              value={editStatus}
                              onChange={e => setEditStatus(e.target.value)}
                              autoFocus
                            >
                              {ESTADOS_DISPONIBLES.map(s => (
                                <option key={s} value={s}>{s}</option>
                              ))}
                            </select>
                            <button onClick={() => saveEdit(row.id)} disabled={savingRow}
                              className="text-green-600 hover:text-green-700 text-xs px-1 disabled:opacity-50">✓</button>
                            <button onClick={() => setEditingRowId(null)}
                              className="text-gray-400 hover:text-gray-600 text-xs px-1">✕</button>
                          </div>
                        ) : (
                          <div className="flex items-center gap-1 group">
                            <span className={`inline-flex px-2 py-0.5 rounded-full text-[10px] font-semibold ${statusStyle(row.status)}`}>
                              {row.status}
                            </span>
                            <button
                              onClick={() => startEdit(row)}
                              className="opacity-0 group-hover:opacity-100 text-gray-400 hover:text-ml-blue dark:hover:text-ml-green text-[10px] transition-opacity"
                              title="Editar estado"
                            >✏️</button>
                          </div>
                        )}
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </>
  )
}
