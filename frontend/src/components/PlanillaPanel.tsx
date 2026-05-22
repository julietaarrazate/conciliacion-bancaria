import React, { useEffect, useState, useMemo, useCallback } from 'react'
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
  const [fetchError, setFetchError] = useState('')
  const [filters, setFilters] = useState<Filters>(EMPTY_FILTERS)
  const [showFilters, setShowFilters] = useState(false)
  const [editingRowId, setEditingRowId] = useState<number | null>(null)
  const [editStatus, setEditStatus] = useState('')
  const [editFecha, setEditFecha] = useState('')
  const [savingRow, setSavingRow] = useState(false)
  const [selectedRows, setSelectedRows] = useState<Set<number>>(new Set())
  const [bulkStatus, setBulkStatus] = useState('')

  useEffect(() => {
    if (!planillaId) { setDetalle(null); setFetchError(''); setFilters(EMPTY_FILTERS); setSelectedRows(new Set()); return }
    setLoading(true)
    setFetchError('')
    apiClient.client
      .get(`/planillas/${planillaId}/detalle`)
      .then(r => setDetalle(r.data))
      .catch((err: any) => {
        setDetalle(null)
        setFetchError(err.response?.data?.detail || `Error al cargar planilla #${planillaId}`)
      })
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
    setEditFecha(row.mov_fecha_acred ? row.mov_fecha_acred.split('T')[0] : '')
  }

  const saveEdit = async (rowId: number) => {
    setSavingRow(true)
    try {
      await apiClient.patchRowStatus(rowId, editStatus, undefined, editFecha || undefined)
      setDetalle(prev => prev ? {
        ...prev,
        rows: prev.rows.map(r => r.id === rowId
          ? { ...r, status: editStatus, mov_fecha_acred: editFecha || r.mov_fecha_acred }
          : r)
      } : prev)
      setEditingRowId(null)
    } finally { setSavingRow(false) }
  }

  const deleteRow = useCallback(async (rowId: number) => {
    if (!confirm('Eliminar esta fila?')) return
    try {
      await apiClient.deleteRow(rowId)
      setDetalle(prev => prev ? {
        ...prev,
        rows: prev.rows.filter(r => r.id !== rowId),
        total: prev.total - 1
      } : prev)
      setSelectedRows(prev => { const n = new Set(prev); n.delete(rowId); return n })
    } catch { /* silently fail */ }
  }, [])

  const toggleSelect = (id: number) => {
    setSelectedRows(prev => {
      const n = new Set(prev)
      if (n.has(id)) n.delete(id); else n.add(id)
      return n
    })
  }

  const selectAllFiltered = () => {
    if (selectedRows.size === filteredRows.length) {
      setSelectedRows(new Set())
    } else {
      setSelectedRows(new Set(filteredRows.map(r => r.id)))
    }
  }

  const applyBulkStatus = async () => {
    if (!bulkStatus || selectedRows.size === 0) return
    setSavingRow(true)
    try {
      const promises = Array.from(selectedRows).map(id =>
        apiClient.patchRowStatus(id, bulkStatus)
      )
      await Promise.all(promises)
      setDetalle(prev => prev ? {
        ...prev,
        rows: prev.rows.map(r => selectedRows.has(r.id) ? { ...r, status: bulkStatus } : r)
      } : prev)
      setSelectedRows(new Set())
      setBulkStatus('')
    } finally { setSavingRow(false) }
  }

  const bulkDelete = async () => {
    if (selectedRows.size === 0) return
    if (!confirm(`Eliminar ${selectedRows.size} filas?`)) return
    setSavingRow(true)
    try {
      await Promise.all(Array.from(selectedRows).map(id => apiClient.deleteRow(id)))
      setDetalle(prev => prev ? {
        ...prev,
        rows: prev.rows.filter(r => !selectedRows.has(r.id)),
        total: prev.total - selectedRows.size
      } : prev)
      setSelectedRows(new Set())
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
        className="fixed right-0 top-12 md:top-0 bottom-0 w-full md:w-[75vw] lg:w-[65vw] xl:w-[55vw] bg-white dark:bg-ml-dark-surface shadow-2xl z-50 flex flex-col overflow-hidden"
      >
        {/* Header */}
        <div className="flex items-start justify-between px-4 py-3 bg-ml-yellow dark:bg-ml-dark-card border-b border-ml-yellow-dark dark:border-ml-dark-border shrink-0">
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
              {hasFilters ? `Filtros (${Object.values(filters).filter(Boolean).length})` : 'Filtrar'}
            </button>
            {hasFilters && (
              <button onClick={clearFilters} className="px-2 py-1 text-xs bg-white/70 text-red-600 rounded hover:bg-white">
                Limpiar
              </button>
            )}
            {detalle && onDelete && (
              <button
                onClick={() => { onDelete(detalle.id); onClose() }}
                className="px-2 py-1 text-red-700 hover:bg-red-100 rounded text-sm"
                title="Eliminar planilla"
              >Borrar</button>
            )}
            <button onClick={onClose} className="px-2 py-1 text-ml-text dark:text-gray-300 hover:bg-ml-yellow-dark dark:hover:bg-ml-dark-border rounded text-lg leading-none">X</button>
          </div>
        </div>

        {/* Stats */}
        {detalle && (
          <div className="grid grid-cols-4 gap-px bg-gray-100 dark:bg-slate-700 shrink-0">
            {[
              { label: 'OK', val: detalle.acreditadas, cls: 'text-green-600 dark:text-green-400', filter: 'ok' },
              { label: 'No esta', val: detalle.no_encontradas, cls: 'text-red-600 dark:text-red-400', filter: 'no está' },
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

        {/* Meta + bulk actions */}
        {detalle && (
          <div className="px-4 py-1.5 text-xs text-ml-text-soft dark:text-gray-400 flex flex-wrap items-center gap-2 border-b dark:border-slate-700 bg-ml-gray-bg dark:bg-slate-900 shrink-0">
            <span>{fmtDate(detalle.fecha_carga)}</span>
            <span>{detalle.usuario_nombre}</span>
            <span>{filteredRows.length}/{detalle.total} filas{hasFilters ? ' (filtrado)' : ''}</span>

            {selectedRows.size > 0 && (
              <div className="flex items-center gap-1 ml-auto">
                <span className="text-ml-blue font-semibold">{selectedRows.size} sel.</span>
                <select
                  className="text-[10px] border border-gray-300 dark:border-slate-600 rounded px-1 py-0.5 bg-white dark:bg-slate-700 dark:text-white"
                  value={bulkStatus}
                  onChange={e => setBulkStatus(e.target.value)}
                >
                  <option value="">Cambiar a...</option>
                  {ESTADOS_DISPONIBLES.map(s => <option key={s} value={s}>{s}</option>)}
                </select>
                {bulkStatus && (
                  <button
                    onClick={applyBulkStatus}
                    disabled={savingRow}
                    className="bg-ml-blue text-white text-[10px] rounded px-2 py-0.5 disabled:opacity-50"
                  >Aplicar</button>
                )}
                <button
                  onClick={bulkDelete}
                  disabled={savingRow}
                  className="bg-red-500 text-white text-[10px] rounded px-2 py-0.5 disabled:opacity-50"
                >Borrar</button>
              </div>
            )}
          </div>
        )}

        {loading && <div className="flex-1 flex items-center justify-center text-ml-text-soft">Cargando...</div>}
        {!loading && fetchError && (
          <div className="flex-1 flex items-center justify-center px-6 text-center">
            <p className="text-red-500 text-sm">{fetchError}</p>
          </div>
        )}

        {detalle && (
          <div className="flex-1 overflow-auto min-h-0">
            <table className="w-full text-xs min-w-[780px]">
              <thead className="sticky top-0 z-10">
                <tr>
                  <th className="px-1 py-2.5 text-left font-bold text-white bg-ml-blue border-r border-blue-400 w-8">
                    <input
                      type="checkbox"
                      checked={selectedRows.size > 0 && selectedRows.size === filteredRows.length}
                      onChange={selectAllFiltered}
                      className="w-3 h-3"
                    />
                  </th>
                  {['#','Importe','CUIT','Titular planilla','Titular extracto','Fecha mov.','Saldo','Cliente acred.','Fecha acred.','Estado',''].map(h => (
                    <th key={h} className="px-2 py-2.5 text-left font-bold text-white bg-ml-blue border-r border-blue-400 last:border-r-0 whitespace-nowrap">
                      {h}
                    </th>
                  ))}
                </tr>

                {showFilters && (
                  <tr className="bg-blue-50 dark:bg-blue-900/10 border-b border-ml-blue/30">
                    <td className="px-1 py-1"></td>
                    <td className="px-1 py-1"></td>
                    <td className="px-1 py-1"><FilterInput field="importe" placeholder="importe" /></td>
                    <td className="px-1 py-1"><FilterInput field="cuit" placeholder="CUIT" /></td>
                    <td className="px-1 py-1"><FilterInput field="titular" placeholder="titular" /></td>
                    <td className="px-1 py-1"><FilterInput field="mov_titular" placeholder="extracto" /></td>
                    <td className="px-1 py-1"><FilterInput field="mov_fecha" placeholder="fecha" /></td>
                    <td className="px-1 py-1"></td>
                    <td className="px-1 py-1"></td>
                    <td className="px-1 py-1"><FilterInput field="mov_fecha_acred" placeholder="acred." /></td>
                    <td className="px-1 py-1">
                      <select className="w-full px-1.5 py-0.5 text-xs border border-gray-300 dark:border-slate-600 rounded bg-white dark:bg-slate-700 dark:text-gray-200"
                        value={filters.status} onChange={e => setFilter('status', e.target.value)}>
                        <option value="">Todos</option>
                        {uniqueStatuses.map(s => <option key={s} value={s}>{s}</option>)}
                      </select>
                    </td>
                    <td className="px-1 py-1"></td>
                  </tr>
                )}
              </thead>

              <tbody className="divide-y dark:divide-slate-700">
                {filteredRows.length === 0 ? (
                  <tr>
                    <td colSpan={12} className="px-4 py-6 text-center text-ml-text-soft">
                      Sin resultados para los filtros aplicados
                    </td>
                  </tr>
                ) : (
                  filteredRows.map((row, i) => (
                    <tr key={row.id} className="hover:bg-ml-gray-bg dark:hover:bg-slate-700/50 divide-x divide-gray-100 dark:divide-slate-700">
                      <td className="px-1 py-px text-center">
                        <input
                          type="checkbox"
                          checked={selectedRows.has(row.id)}
                          onChange={() => toggleSelect(row.id)}
                          className="w-3 h-3"
                        />
                      </td>
                      <td className="px-2 py-px text-gray-400 dark:text-gray-500">{i + 1}</td>
                      <td className="px-2 py-px text-right font-mono font-semibold dark:text-white whitespace-nowrap">{fmtARS(row.monto)}</td>
                      <td className="px-2 py-px text-gray-500 dark:text-gray-400 font-mono text-[10px]">{row.cuit || '—'}</td>
                      <td className="px-2 py-px dark:text-gray-300 max-w-[130px] truncate" title={row.titular || ''}>{row.titular || '—'}</td>
                      <td className="px-2 py-px text-gray-500 dark:text-gray-400 max-w-[180px] truncate" title={row.mov_titular || ''}>{row.mov_titular || '—'}</td>
                      <td className="px-2 py-px whitespace-nowrap text-gray-500 dark:text-gray-400">{fmtDate(row.mov_fecha)}</td>
                      <td className="px-2 py-px text-right font-mono text-gray-400 dark:text-gray-500">—</td>
                      <td className="px-2 py-px text-gray-500 dark:text-gray-400 whitespace-nowrap">
                        {row.status === 'ok' ? <span className="text-green-600 dark:text-green-400 text-[10px] font-medium">{row.mov_titular?.split(' ').slice(0,2).join(' ') || '—'}</span> : '—'}
                      </td>
                      <td className="px-2 py-px whitespace-nowrap text-gray-500 dark:text-gray-400">{fmtDate(row.mov_fecha_acred)}</td>
                      <td className="px-2 py-px min-w-[130px]">
                        {editingRowId === row.id ? (
                          <div className="flex flex-col gap-1 min-w-[160px]">
                            <select
                              className="text-[10px] border border-ml-blue rounded px-1 py-0.5 bg-white dark:bg-slate-700 dark:text-white w-full"
                              value={editStatus}
                              onChange={e => setEditStatus(e.target.value)}
                              autoFocus
                            >
                              {ESTADOS_DISPONIBLES.map(s => (
                                <option key={s} value={s}>{s}</option>
                              ))}
                            </select>
                            <input
                              type="date"
                              className="text-[10px] border border-gray-300 dark:border-slate-600 rounded px-1 py-0.5 bg-white dark:bg-slate-700 dark:text-white w-full font-mono"
                              value={editFecha}
                              onChange={e => setEditFecha(e.target.value)}
                              title="Fecha de acreditacion"
                            />
                            <div className="flex gap-1">
                              <button onClick={() => saveEdit(row.id)} disabled={savingRow}
                                className="flex-1 bg-green-500 text-white text-[10px] rounded py-0.5 disabled:opacity-50">Guardar</button>
                              <button onClick={() => setEditingRowId(null)}
                                className="flex-1 bg-gray-200 dark:bg-slate-600 text-gray-700 dark:text-white text-[10px] rounded py-0.5">X</button>
                            </div>
                          </div>
                        ) : (
                          <button
                            onClick={() => startEdit(row)}
                            className="inline-flex px-2 py-0.5 rounded-full text-[10px] font-semibold cursor-pointer active:scale-95 transition-transform"
                          >
                            <span className={`inline-flex px-2 py-0.5 rounded-full ${statusStyle(row.status)}`}>
                              {row.status}
                            </span>
                          </button>
                        )}
                      </td>
                      <td className="px-1 py-px text-center">
                        <button
                          onClick={() => deleteRow(row.id)}
                          className="text-gray-300 hover:text-red-500 dark:text-gray-600 dark:hover:text-red-400 text-[10px] transition-colors"
                          title="Eliminar fila"
                        >X</button>
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
