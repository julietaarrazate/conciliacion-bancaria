import React, { useEffect, useState, useMemo, useCallback } from 'react'
import { apiClient } from '@/services/api'
import { confirmDialog } from '@/store/confirm'
import { statusLabel } from '@/utils/status'

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

interface Candidato {
  id: number
  fecha: string | null
  titular: string
  cliente_acreditado: string | null
  es_libre: boolean
  es_este_cliente: boolean
}

interface MetaDetalle {
  id: number
  nombre_archivo: string
  cliente_nombre: string
  extracto_nombre: string
  fecha_carga: string
  usuario_nombre: string
  total: number
  total_filtered: number
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

const PAGE_SIZE = 100

const ESTADOS_DISPONIBLES = [
  'ok', 'no está', 'duplicado', 'faltan datos', 'pendiente',
  'PAGO_PARCIAL', 'CONCILIADO_CON_DIFERENCIA', 'VENCIDO', 'EN_REVISION'
]

export const PlanillaPanel: React.FC<Props> = ({ planillaId, onClose, onDelete }) => {
  const [meta, setMeta] = useState<MetaDetalle | null>(null)
  const [rows, setRows] = useState<Row[]>([])
  const [loading, setLoading] = useState(false)
  const [fetchError, setFetchError] = useState('')
  // Two-state filter: draft (immediate UI) + applied (triggers server fetch after debounce)
  const [filtersDraft, setFiltersDraft] = useState<Filters>(EMPTY_FILTERS)
  const [filters, setFilters] = useState<Filters>(EMPTY_FILTERS)
  const [showFilters, setShowFilters] = useState(false)
  const [editingRowId, setEditingRowId] = useState<number | null>(null)
  const [editStatus, setEditStatus] = useState('')
  const [editFecha, setEditFecha] = useState('')
  const [savingRow, setSavingRow] = useState(false)
  const [selectedRows, setSelectedRows] = useState<Set<number>>(new Set())
  const [bulkStatus, setBulkStatus] = useState('')
  const [page, setPage] = useState(0)
  const [asignarRowId, setAsignarRowId] = useState<number | null>(null)
  const [candidatos, setCandidatos] = useState<Candidato[]>([])
  const [loadingCandidatos, setLoadingCandidatos] = useState(false)
  const [asignandoMovId, setAsignandoMovId] = useState<number | null>(null)
  const [asignarError, setAsignarError] = useState('')

  // Debounce text filter inputs → apply after 350ms of no changes
  useEffect(() => {
    const t = setTimeout(() => {
      setFilters(filtersDraft)
      setPage(0)
    }, 350)
    return () => clearTimeout(t)
  }, [filtersDraft])

  // Fetch from server on planillaId, page, or applied filters change
  const reload = useCallback(() => {
    if (!planillaId) return
    setLoading(true)
    setFetchError('')

    const params: Record<string, string | number> = {
      limit: PAGE_SIZE,
      offset: page * PAGE_SIZE,
    }
    if (filters.status) params.status = filters.status
    if (filters.importe) params.importe = filters.importe
    if (filters.cuit) params.cuit = filters.cuit
    if (filters.titular) params.titular = filters.titular
    if (filters.mov_titular) params.mov_titular = filters.mov_titular
    if (filters.mov_fecha) params.mov_fecha = filters.mov_fecha
    if (filters.mov_fecha_acred) params.mov_fecha_acred = filters.mov_fecha_acred

    apiClient.client
      .get(`/planillas/${planillaId}/detalle`, { params })
      .then(r => {
        const { rows: fetchedRows, ...rest } = r.data as { rows: Row[] } & MetaDetalle
        setMeta(rest)
        setRows(fetchedRows)
      })
      .catch((err: { response?: { data?: { detail?: string } } }) => {
        setMeta(null)
        setRows([])
        setFetchError(err.response?.data?.detail || `Error al cargar planilla #${planillaId}`)
      })
      .finally(() => setLoading(false))
  }, [planillaId, page, filters])

  useEffect(() => {
    if (!planillaId) {
      setMeta(null)
      setRows([])
      setFetchError('')
      setFiltersDraft(EMPTY_FILTERS)
      setFilters(EMPTY_FILTERS)
      setSelectedRows(new Set())
      return
    }
    setSelectedRows(new Set())
    reload()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [planillaId, page, filters])

  const totalPages = meta ? Math.ceil(meta.total_filtered / PAGE_SIZE) : 0

  const hasFilters = Object.values(filtersDraft).some(v => v !== '')

  const clearFilters = () => {
    setFiltersDraft(EMPTY_FILTERS)
    setFilters(EMPTY_FILTERS)
    setPage(0)
  }

  // For text inputs: update draft (debounce will apply)
  const setFilter = (k: keyof Filters, v: string) => {
    setFiltersDraft(prev => ({ ...prev, [k]: v }))
  }

  // For stat buttons: apply immediately (bypasses debounce)
  const applyStatusFilter = (statusVal: string) => {
    const newStatus = filtersDraft.status === statusVal ? '' : statusVal
    const updated = { ...filtersDraft, status: newStatus }
    setFiltersDraft(updated)
    setFilters(updated)
    setPage(0)
  }

  const startEdit = (row: Row) => {
    setEditingRowId(row.id)
    setEditStatus(row.status)
    setEditFecha(row.mov_fecha_acred ? row.mov_fecha_acred.split('T')[0] : '')
  }

  const saveEdit = async (rowId: number) => {
    setSavingRow(true)
    try {
      await apiClient.patchRowStatus(rowId, editStatus, undefined, editFecha || undefined)
      setRows(prev => prev.map(r => r.id === rowId
        ? { ...r, status: editStatus, mov_fecha_acred: editFecha || r.mov_fecha_acred }
        : r))
      setEditingRowId(null)
    } finally { setSavingRow(false) }
  }

  const deleteRow = useCallback(async (rowId: number) => {
    if (!await confirmDialog({ title: 'Eliminar fila', message: '¿Eliminar esta fila?', confirmLabel: 'Eliminar', danger: true })) return
    try {
      await apiClient.deleteRow(rowId)
      setRows(prev => prev.filter(r => r.id !== rowId))
      setSelectedRows(prev => { const n = new Set(prev); n.delete(rowId); return n })
      setMeta(prev => prev ? {
        ...prev,
        total: prev.total - 1,
        total_filtered: prev.total_filtered - 1,
      } : prev)
    } catch { /* silently fail */ }
  }, [])

  const toggleSelect = (id: number) => {
    setSelectedRows(prev => {
      const n = new Set(prev)
      if (n.has(id)) n.delete(id); else n.add(id)
      return n
    })
  }

  const selectAllPage = () => {
    if (selectedRows.size === rows.length && rows.length > 0) {
      setSelectedRows(new Set())
    } else {
      setSelectedRows(new Set(rows.map(r => r.id)))
    }
  }

  const applyBulkStatus = async () => {
    if (!bulkStatus || selectedRows.size === 0) return
    setSavingRow(true)
    try {
      await Promise.all(Array.from(selectedRows).map(id => apiClient.patchRowStatus(id, bulkStatus)))
      setRows(prev => prev.map(r => selectedRows.has(r.id) ? { ...r, status: bulkStatus } : r))
      setSelectedRows(new Set())
      setBulkStatus('')
    } finally { setSavingRow(false) }
  }

  const bulkDelete = async () => {
    if (selectedRows.size === 0) return
    if (!await confirmDialog({ title: 'Eliminar filas', message: `¿Eliminar ${selectedRows.size} filas?`, confirmLabel: 'Eliminar', danger: true })) return
    setSavingRow(true)
    try {
      await Promise.all(Array.from(selectedRows).map(id => apiClient.deleteRow(id)))
      const deletedCount = selectedRows.size
      setRows(prev => prev.filter(r => !selectedRows.has(r.id)))
      setMeta(prev => prev ? {
        ...prev,
        total: prev.total - deletedCount,
        total_filtered: prev.total_filtered - deletedCount,
      } : prev)
      setSelectedRows(new Set())
    } finally { setSavingRow(false) }
  }

  const openAsignar = async (row: Row) => {
    setAsignarRowId(row.id)
    setAsignarError('')
    setCandidatos([])
    setLoadingCandidatos(true)
    try {
      const data = await apiClient.candidatosMovimiento(row.id)
      setCandidatos(data.candidatos)
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail
      setAsignarError(msg || 'No se pudieron cargar los movimientos candidatos')
    } finally {
      setLoadingCandidatos(false)
    }
  }

  const closeAsignar = () => {
    setAsignarRowId(null)
    setCandidatos([])
    setAsignarError('')
  }

  const elegirMovimiento = async (movimientoId: number) => {
    if (!asignarRowId) return
    setAsignandoMovId(movimientoId)
    setAsignarError('')
    try {
      await apiClient.asignarMovimiento(asignarRowId, movimientoId)
      closeAsignar()
      reload()
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail
      setAsignarError(msg || 'No se pudo asignar el movimiento')
    } finally {
      setAsignandoMovId(null)
    }
  }

  // Derived values
  const allPageSelected = useMemo(
    () => rows.length > 0 && selectedRows.size === rows.length,
    [rows, selectedRows]
  )

  if (!planillaId) return null

  const FilterInput = ({ field, placeholder }: { field: keyof Filters; placeholder: string }) => (
    <input
      className="w-full px-1.5 py-0.5 text-xs border border-gray-300 dark:border-slate-600 rounded bg-white dark:bg-slate-700 dark:text-gray-200 focus:outline-none focus:border-ml-blue"
      placeholder={placeholder}
      value={filtersDraft[field]}
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
            <p className="font-bold text-ml-text text-sm truncate">{meta?.cliente_nombre ?? '...'}</p>
            <p className="text-xs text-ml-text-soft truncate">{meta?.nombre_archivo}</p>
          </div>
          <div className="flex items-center gap-1 ml-2 shrink-0">
            <button
              onClick={() => setShowFilters(s => !s)}
              className={`px-2 py-1 text-xs rounded font-medium ${showFilters || hasFilters ? 'bg-ml-blue text-white' : 'bg-white/70 text-ml-text hover:bg-white'}`}
              title="Filtros por columna"
            >
              {hasFilters ? `Filtros (${Object.values(filtersDraft).filter(Boolean).length})` : 'Filtrar'}
            </button>
            {hasFilters && (
              <button onClick={clearFilters} className="px-2 py-1 text-xs bg-white/70 text-red-600 rounded hover:bg-white">
                Limpiar
              </button>
            )}
            {meta && onDelete && (
              <button
                onClick={() => { onDelete(meta.id); onClose() }}
                className="px-2 py-1 text-red-700 hover:bg-red-100 rounded text-sm"
                title="Eliminar planilla"
              >Borrar</button>
            )}
            <button onClick={onClose} className="px-2 py-1 text-ml-text dark:text-gray-300 hover:bg-ml-yellow-dark dark:hover:bg-ml-dark-border rounded text-lg leading-none">X</button>
          </div>
        </div>

        {/* Stats */}
        {meta && (
          <div className="grid grid-cols-4 gap-px bg-gray-100 dark:bg-slate-700 shrink-0">
            {[
              { label: 'OK', val: meta.acreditadas, cls: 'text-green-600 dark:text-green-400', filter: 'ok' },
              { label: 'No esta', val: meta.no_encontradas, cls: 'text-red-600 dark:text-red-400', filter: 'no está' },
              { label: 'Duplicadas', val: meta.duplicadas, cls: 'text-yellow-600 dark:text-yellow-400', filter: 'duplicado' },
              { label: 'Sin datos', val: meta.sin_datos, cls: 'text-blue-600 dark:text-blue-400', filter: 'faltan datos' },
            ].map(s => (
              <button
                key={s.label}
                onClick={() => applyStatusFilter(s.filter)}
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
        {meta && (
          <div className="px-4 py-1.5 text-xs text-ml-text-soft dark:text-gray-400 flex flex-wrap items-center gap-2 border-b dark:border-slate-700 bg-ml-gray-bg dark:bg-slate-900 shrink-0">
            <span>{fmtDate(meta.fecha_carga)}</span>
            <span>{meta.usuario_nombre}</span>
            <span>
              {hasFilters
                ? `${meta.total_filtered} de ${meta.total} filas (filtrado)${totalPages > 1 ? ` · p.${page + 1}/${totalPages}` : ''}`
                : `${meta.total} filas${totalPages > 1 ? ` · p.${page + 1}/${totalPages}` : ''}`
              }
            </span>

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

        {meta && (
          <div className="flex-1 overflow-auto min-h-0">
            <p className="px-3 py-1.5 text-[10px] text-gray-400 dark:text-gray-500 border-b border-ml-gray/50 dark:border-ml-dark-border">
              ✓ Acreditado · ✕ No encontrado · ⚠ Duplicado · ? Sin datos — tocá un estado para corregirlo
            </p>
            <table className="w-full text-xs min-w-[780px]">
              <thead className="sticky top-0 z-10">
                <tr>
                  <th className="px-1 py-2.5 text-left font-bold text-white bg-ml-blue border-r border-blue-400 w-8">
                    <input
                      type="checkbox"
                      checked={allPageSelected}
                      onChange={selectAllPage}
                      className="w-3 h-3"
                      title="Seleccionar página actual"
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
                        value={filtersDraft.status}
                        onChange={e => {
                          const v = e.target.value
                          const updated = { ...filtersDraft, status: v }
                          setFiltersDraft(updated)
                          setFilters(updated)
                          setPage(0)
                        }}>
                        <option value="">Todos</option>
                        {ESTADOS_DISPONIBLES.map(s => <option key={s} value={s}>{s}</option>)}
                      </select>
                    </td>
                    <td className="px-1 py-1"></td>
                  </tr>
                )}
              </thead>

              <tbody className="divide-y dark:divide-slate-700">
                {rows.length === 0 && !loading ? (
                  <tr>
                    <td colSpan={12} className="px-4 py-6 text-center text-ml-text-soft">
                      {hasFilters ? 'Sin resultados para los filtros aplicados' : 'Sin filas'}
                    </td>
                  </tr>
                ) : (
                  rows.map((row, i) => (
                    <tr key={row.id} className="hover:bg-ml-gray-bg dark:hover:bg-slate-700/50 divide-x divide-gray-100 dark:divide-slate-700">
                      <td className="px-1 py-px text-center">
                        <input
                          type="checkbox"
                          checked={selectedRows.has(row.id)}
                          onChange={() => toggleSelect(row.id)}
                          className="w-3 h-3"
                        />
                      </td>
                      <td className="px-2 py-px text-gray-400 dark:text-gray-500">{page * PAGE_SIZE + i + 1}</td>
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
                            <span className={`inline-flex px-2 py-0.5 rounded-full ${statusStyle(row.status)}`} title={row.status}>
                              {statusLabel(row.status)}
                            </span>
                          </button>
                        )}
                      </td>
                      <td className="px-1 py-px text-center whitespace-nowrap">
                        {row.status !== 'ok' && (
                          <button
                            onClick={() => openAsignar(row)}
                            className="text-gray-300 hover:text-ml-blue dark:text-gray-600 dark:hover:text-ml-blue text-[10px] transition-colors mr-2"
                            title="Asignar movimiento manualmente"
                          >🔗</button>
                        )}
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

            {totalPages > 1 && (
              <div className="sticky bottom-0 flex items-center justify-between gap-2 px-4 py-2 bg-white dark:bg-ml-dark-surface border-t border-gray-100 dark:border-slate-700 text-xs text-ml-text-soft dark:text-gray-400">
                <button
                  onClick={() => setPage(p => Math.max(0, p - 1))}
                  disabled={page === 0}
                  className="px-2.5 py-1 rounded border border-gray-200 dark:border-slate-600 disabled:opacity-40 hover:bg-ml-gray-bg dark:hover:bg-slate-700"
                >← Anterior</button>
                <span>Página {page + 1} / {totalPages} · {meta?.total_filtered ?? 0} filas{hasFilters ? ' (filtrado)' : ''}</span>
                <button
                  onClick={() => setPage(p => Math.min(totalPages - 1, p + 1))}
                  disabled={page === totalPages - 1}
                  className="px-2.5 py-1 rounded border border-gray-200 dark:border-slate-600 disabled:opacity-40 hover:bg-ml-gray-bg dark:hover:bg-slate-700"
                >Siguiente →</button>
              </div>
            )}
          </div>
        )}
      </div>

      {asignarRowId !== null && (
        <div className="fixed inset-0 z-[150] flex items-center justify-center p-4">
          <div className="absolute inset-0 bg-black/50 backdrop-blur-sm" onClick={closeAsignar} />
          <div className="relative bg-white dark:bg-ml-dark-surface rounded-2xl shadow-xl border border-gray-200 dark:border-ml-dark-border p-6 w-full max-w-md">
            <h3 className="text-base font-semibold text-ml-text dark:text-white mb-1">Asignar movimiento</h3>
            <p className="text-xs text-ml-text-soft dark:text-zinc-400 mb-4">
              Elegí a qué movimiento del extracto corresponde esta fila. Resuelve la fila en su lugar — no crea una fila nueva.
            </p>

            {loadingCandidatos && (
              <p className="text-sm text-ml-text-soft dark:text-zinc-400 py-4 text-center">Buscando movimientos del mismo monto…</p>
            )}

            {!loadingCandidatos && asignarError && (
              <p className="text-sm text-red-500 mb-3">{asignarError}</p>
            )}

            {!loadingCandidatos && !asignarError && candidatos.length === 0 && (
              <p className="text-sm text-ml-text-soft dark:text-zinc-400 py-4 text-center">
                No hay movimientos en el extracto con ese monto.
              </p>
            )}

            {!loadingCandidatos && candidatos.length > 0 && (
              <div className="space-y-2 max-h-80 overflow-y-auto">
                {candidatos.map(c => (
                  <button
                    key={c.id}
                    onClick={() => elegirMovimiento(c.id)}
                    disabled={asignandoMovId !== null || (!c.es_libre && !c.es_este_cliente)}
                    className="w-full text-left px-3 py-2 rounded-lg border border-gray-200 dark:border-slate-600 hover:border-ml-blue hover:bg-ml-gray-bg dark:hover:bg-slate-700 transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
                  >
                    <div className="flex items-center justify-between gap-2">
                      <span className="text-sm dark:text-gray-200 truncate" title={c.titular}>{c.titular || '—'}</span>
                      <span className="text-xs font-mono text-ml-text-soft dark:text-zinc-400 shrink-0">{fmtDate(c.fecha)}</span>
                    </div>
                    {!c.es_libre && (
                      <span className="text-2xs text-yellow-600 dark:text-yellow-400">
                        {c.es_este_cliente ? 'Ya acreditado a este cliente' : `Ya acreditado a ${c.cliente_acreditado}`}
                      </span>
                    )}
                    {asignandoMovId === c.id && <span className="text-2xs text-ml-blue"> Asignando…</span>}
                  </button>
                ))}
              </div>
            )}

            <div className="flex justify-end mt-5">
              <button
                onClick={closeAsignar}
                className="px-4 py-2 text-sm rounded-lg border border-gray-200 dark:border-ml-dark-border text-ml-text dark:text-zinc-300 hover:bg-gray-50 dark:hover:bg-white/5 transition-colors"
              >Cerrar</button>
            </div>
          </div>
        </div>
      )}
    </>
  )
}
