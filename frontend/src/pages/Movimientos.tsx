import React, { useEffect, useState, useCallback, useRef, useMemo } from 'react'
import { useSearchParams } from 'react-router-dom'
import { apiClient } from '@/services/api'
import { ExtractoListItem, MovimientoFiltrado, MovimientosFiltros } from '@/types'

function useDebounce<T>(value: T, delay: number): T {
  const [debounced, setDebounced] = useState(value)
  useEffect(() => {
    const id = setTimeout(() => setDebounced(value), delay)
    return () => clearTimeout(id)
  }, [value, delay])
  return debounced
}

// ── Utilidades ────────────────────────────────────────────────
function fmtARS(n: number) {
  return new Intl.NumberFormat('es-AR', { style: 'currency', currency: 'ARS', minimumFractionDigits: 0 }).format(n)
}
function fmtDate(d?: string | null) {
  if (!d) return '—'
  try { return new Date(d + 'T00:00:00').toLocaleDateString('es-AR', { day: '2-digit', month: '2-digit', year: '2-digit' }) }
  catch { return d }
}

// ── Componente de filtro desplegable tipo Excel ───────────────
interface ExcelFilterProps {
  label: string
  active: boolean
  children: React.ReactNode
  align?: 'left' | 'right'
}
const ExcelFilter: React.FC<ExcelFilterProps> = ({ label, active, children, align = 'left' }) => {
  const [open, setOpen] = useState(false)
  const ref = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const fn = (e: MouseEvent) => { if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false) }
    document.addEventListener('mousedown', fn)
    return () => document.removeEventListener('mousedown', fn)
  }, [])

  return (
    <div ref={ref} className="relative inline-flex items-center gap-1 cursor-pointer select-none w-full" onClick={() => setOpen(o => !o)}>
      <span className="truncate">{label}</span>
      <span className={`text-[10px] ml-auto flex-shrink-0 ${active ? 'text-ml-yellow' : 'text-blue-200'}`}>
        {active ? '▼●' : '▼'}
      </span>
      {open && (
        <div
          className={`absolute top-full mt-1 z-50 bg-white dark:bg-slate-800 border border-gray-200 dark:border-slate-600 rounded-lg shadow-xl p-3 min-w-[200px] ${align === 'right' ? 'right-0' : 'left-0'}`}
          onClick={e => e.stopPropagation()}
        >
          {children}
        </div>
      )}
    </div>
  )
}

// ── Estado filtros ────────────────────────────────────────────
interface ColFilter {
  cliente: string
  cuit: string
  titular: string
  desde: string
  hasta: string
  fecha_desde: string
  fecha_hasta: string
  sin_acreditar: string
  importe_min: string
  importe_max: string
}
const EMPTY: ColFilter = { cliente:'', cuit:'', titular:'', desde:'', hasta:'', fecha_desde:'', fecha_hasta:'', sin_acreditar:'', importe_min:'', importe_max:'' }

export const Movimientos: React.FC = () => {
  const [searchParams] = useSearchParams()
  const [extractos, setExtractos] = useState<ExtractoListItem[]>([])
  const [extractoId, setExtractoId] = useState<number | null>(null)
  const [movimientos, setMovimientos] = useState<MovimientoFiltrado[]>([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(false)
  const [filters, setFilters] = useState<ColFilter>(EMPTY)
  const [page, setPage] = useState(0)
  const PAGE_SIZE = 200
  const [umLoading, setUmLoading] = useState(false)
  const [umMsg, setUmMsg] = useState('')
  const [exporting, setExporting] = useState(false)
  const [tab, setTab] = useState<'todos' | 'um'>('todos')
  const [editingId, setEditingId] = useState<number | null>(null)
  const [editValues, setEditValues] = useState<Record<string, string>>({})
  const umRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    apiClient.listExtractos().then(data => {
      setExtractos(data.items)
      const p = searchParams.get('extracto')
      setExtractoId(p ? Number(p) : data.items[0]?.id ?? null)
    })
  }, [])

  const debouncedFilters = useDebounce(filters, 800)

  const buildApiFilters = useCallback((): MovimientosFiltros => {
    const f: MovimientosFiltros = { limit: 0 }
    if (debouncedFilters.cliente) f.cliente = debouncedFilters.cliente
    if (debouncedFilters.cuit) f.cuit = debouncedFilters.cuit
    if (debouncedFilters.titular) f.titular = debouncedFilters.titular
    if (debouncedFilters.desde) f.desde = debouncedFilters.desde
    if (debouncedFilters.hasta) f.hasta = debouncedFilters.hasta
    if (debouncedFilters.fecha_desde) f.fecha_desde = debouncedFilters.fecha_desde
    if (debouncedFilters.fecha_hasta) f.fecha_hasta = debouncedFilters.fecha_hasta
    if (debouncedFilters.sin_acreditar === 'no') f.sin_acreditar = true
    if (debouncedFilters.sin_acreditar === 'si') f.sin_acreditar = false
    return f
  }, [debouncedFilters])

  const filteredMovs = useMemo(() => {
    let m = tab === 'um' ? movimientos.filter(x => x.source === 'um') : movimientos
    if (debouncedFilters.importe_min) {
      const min = parseFloat(debouncedFilters.importe_min.replace(/\./g,'').replace(',','.'))
      if (!isNaN(min)) m = m.filter(x => x.monto >= min)
    }
    if (debouncedFilters.importe_max) {
      const max = parseFloat(debouncedFilters.importe_max.replace(/\./g,'').replace(',','.'))
      if (!isNaN(max)) m = m.filter(x => x.monto <= max)
    }
    return m
  }, [movimientos, debouncedFilters.importe_min, debouncedFilters.importe_max, tab])

  const startEdit = (m: MovimientoFiltrado) => {
    setEditingId(m.id)
    setEditValues({ titular: m.titular || '', monto: String(m.monto) })
  }

  const saveEdit = async (m: MovimientoFiltrado) => {
    if (!extractoId) return
    try {
      await apiClient.updateMovimiento(extractoId, m.id, {
        titular: editValues.titular,
        monto: parseFloat(editValues.monto)
      })
      setMovimientos(prev => prev.map(x => x.id === m.id
        ? { ...x, titular: editValues.titular, monto: parseFloat(editValues.monto) }
        : x
      ))
    } catch { /* silencioso */ }
    setEditingId(null)
  }

  const load = useCallback(async () => {
    if (!extractoId) return
    setLoading(true)
    try {
      const data = await apiClient.getMovimientos(extractoId, buildApiFilters())
      setMovimientos(data.items)
      setTotal(data.total)
      setPage(0)
    } catch { setMovimientos([]); setTotal(0) }
    finally { setLoading(false) }
  }, [extractoId, buildApiFilters])

  useEffect(() => { load() }, [load])

  const set = (k: keyof ColFilter, v: string) => setFilters(p => ({ ...p, [k]: v }))
  const hasFilters = Object.values(filters).some(Boolean)
  const clearAll = () => setFilters(EMPTY)

  const handleAppendUM = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file || !extractoId) return
    setUmLoading(true); setUmMsg('')
    try {
      const r = await apiClient.appendUM(extractoId, file)
      setUmMsg(`✓ ${r.agregados} nuevos desde el corte · ${r.duplicados} ya existían (ignorados)`)
      // Refrescar extracto y movimientos
      const data = await apiClient.listExtractos()
      setExtractos(data.items)
      load()
    } catch (err: any) {
      setUmMsg(`✗ ${err.response?.data?.detail || 'Error al agregar UM'}`)
    } finally {
      setUmLoading(false)
      if (umRef.current) umRef.current.value = ''
    }
  }

  const handleExport = async () => {
    if (!extractoId) return
    setExporting(true)
    try { await apiClient.exportMovimientos(extractoId, buildApiFilters()) }
    finally { setExporting(false) }
  }

  const extractoActivo = extractos.find(e => e.id === extractoId)
  const umCount = filteredMovs.filter(m => m.source === 'um').length

  return (
    <div className="p-3 md:p-6 max-w-full">
      {/* Header */}
      <div className="flex flex-wrap items-start gap-2 mb-3">
        <div className="flex-1 min-w-0">
          <h1 className="text-lg md:text-xl font-bold dark:text-white">Movimientos del extracto</h1>
          {extractoActivo && (
            <p className="text-xs text-gray-500 dark:text-gray-400 mt-0.5">
              {extractoActivo.nombre_archivo} · <b>{extractoActivo.total_movimientos}</b> movimientos
              {umCount > 0 && <span className="ml-2 text-emerald-600 dark:text-emerald-400 font-medium">· {umCount} de UM</span>}
              {hasFilters && <span className="ml-2 text-ml-blue font-medium">· {filteredMovs.length} filtrados</span>}
            </p>
          )}
        </div>
        <div className="flex gap-1.5 flex-wrap">
          {hasFilters && (
            <button onClick={clearAll} className="px-3 py-1.5 text-xs text-red-600 border border-red-300 rounded-md hover:bg-red-50 dark:text-red-400 dark:border-red-700">
              ✕ Limpiar filtros
            </button>
          )}
          <button onClick={handleExport} disabled={exporting || filteredMovs.length === 0}
            className="flex items-center gap-1 px-3 py-1.5 text-xs bg-green-600 text-white rounded-md hover:bg-green-700 disabled:opacity-50">
            {exporting ? '⏳' : '⬇️'} Excel
          </button>
          {extractoId && (
            <button
              onClick={() => apiClient.exportExtractoContador(extractoId)}
              className="flex items-center gap-1 px-3 py-1.5 text-xs bg-blue-600 text-white rounded-md hover:bg-blue-700 font-medium"
              title="Exportar extracto completo conciliado para el contador"
            >
              📤 Para contador
            </button>
          )}
        </div>
      </div>

      {/* Selector + UM */}
      <div className="flex flex-wrap gap-2 mb-3 items-end">
        <div className="flex-1 min-w-[220px]">
          <select className="input-field" value={extractoId ?? ''} onChange={e => setExtractoId(Number(e.target.value))}>
            {extractos.map(e => (
              <option key={e.id} value={e.id}>#{e.id} · {e.nombre_archivo} ({e.total_movimientos})</option>
            ))}
          </select>
        </div>
        <label className={`flex items-center gap-1.5 px-3 py-2 rounded-md border text-sm font-medium cursor-pointer transition-colors ${umLoading ? 'opacity-50' : 'bg-ml-blue text-white border-ml-blue hover:bg-ml-blue-dark'}`}>
          {umLoading ? '⏳' : '📎'} {umLoading ? 'Procesando...' : 'Agregar UM'}
          <input ref={umRef} type="file" accept="*/*" hidden onChange={handleAppendUM} disabled={umLoading || !extractoId} />
        </label>
      </div>

      {umMsg && (
        <div className={`mb-3 px-3 py-2 rounded-md text-sm ${umMsg.startsWith('✓') ? 'bg-emerald-50 text-emerald-700 dark:bg-emerald-900/20 dark:text-emerald-300 border border-emerald-200 dark:border-emerald-800' : 'bg-red-50 text-red-700 dark:bg-red-900/20 dark:text-red-300'}`}>
          {umMsg}
        </div>
      )}

      {/* Leyenda UM */}
      {umCount > 0 && (
        <div className="mb-2 flex items-center gap-2 text-xs text-gray-600 dark:text-gray-400">
          <span className="inline-block w-3 h-3 rounded bg-emerald-100 dark:bg-emerald-900/40 border border-emerald-300"></span>
          Filas en verde = agregadas desde Últimos Movimientos
        </div>
      )}

      {/* Tabs: Todos / UM */}
      {umCount > 0 && (
        <div className="flex gap-0 mb-0 border-b border-gray-200 dark:border-slate-700">
          {([['todos', 'Todos'], ['um', `UM (${umCount})`]] as const).map(([t, label]) => (
            <button key={t} onClick={() => setTab(t)}
              className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors ${tab === t ? 'border-ml-blue text-ml-blue dark:text-blue-400' : 'border-transparent text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-200'}`}>
              {label}
            </button>
          ))}
          {tab === 'um' && (
            <span className="ml-auto px-3 py-2 text-xs text-emerald-600 dark:text-emerald-400 self-center">
              ✏️ Hacé doble clic en una fila para editar
            </span>
          )}
        </div>
      )}

      {/* Tabla */}
      <div className={`bg-white dark:bg-slate-800 border border-gray-100 dark:border-slate-700 overflow-hidden shadow-sm ${umCount > 0 ? 'rounded-b-lg' : 'rounded-lg'}`}>
        <div className="px-3 py-1.5 bg-gray-50 dark:bg-slate-900 border-b dark:border-slate-700 flex items-center justify-between gap-2 flex-wrap">
          <span className="text-xs text-gray-500 dark:text-gray-400">
            <b>{filteredMovs.length}</b> de {total} movimientos
            {filteredMovs.length > PAGE_SIZE && (
              <span className="ml-2 text-gray-400">
                · mostrando {page * PAGE_SIZE + 1}–{Math.min((page + 1) * PAGE_SIZE, filteredMovs.length)}
              </span>
            )}
          </span>
          {filteredMovs.length > PAGE_SIZE && (
            <div className="flex items-center gap-1">
              <button onClick={() => setPage(p => Math.max(0, p - 1))} disabled={page === 0}
                className="px-2 py-0.5 text-xs rounded border border-gray-300 dark:border-slate-600 disabled:opacity-30 hover:bg-gray-100 dark:hover:bg-slate-700">
                ← Ant.
              </button>
              <span className="text-xs text-gray-500 dark:text-gray-400 px-1">
                {page + 1} / {Math.ceil(filteredMovs.length / PAGE_SIZE)}
              </span>
              <button onClick={() => setPage(p => Math.min(Math.ceil(filteredMovs.length / PAGE_SIZE) - 1, p + 1))}
                disabled={page >= Math.ceil(filteredMovs.length / PAGE_SIZE) - 1}
                className="px-2 py-0.5 text-xs rounded border border-gray-300 dark:border-slate-600 disabled:opacity-30 hover:bg-gray-100 dark:hover:bg-slate-700">
                Sig. →
              </button>
            </div>
          )}
        </div>

        {loading ? (
          <div className="p-8 text-center text-gray-400">Cargando...</div>
        ) : (
          <div className="overflow-x-auto max-h-[calc(100dvh-240px)]" style={{ WebkitOverflowScrolling: 'touch' }}>
            <table className="w-full text-xs border-collapse min-w-[640px]">
              <thead className="sticky top-0 z-20">
                <tr>
                  {/* Orden */}
                  <th className="th-macro w-12 text-center">Orden</th>

                  {/* Fecha — con filtro de rango */}
                  <th className="th-macro w-28">
                    <ExcelFilter label="Fecha" active={!!(filters.fecha_desde || filters.fecha_hasta)}>
                      <p className="text-xs font-semibold text-gray-700 dark:text-gray-200 mb-2">Fecha del movimiento</p>
                      <label className="label text-xs">Desde</label>
                      <input type="date" className="input-field text-xs mb-2" value={filters.fecha_desde} onChange={e => set('fecha_desde', e.target.value)} />
                      <label className="label text-xs">Hasta</label>
                      <input type="date" className="input-field text-xs" value={filters.fecha_hasta} onChange={e => set('fecha_hasta', e.target.value)} />
                    </ExcelFilter>
                  </th>

                  {/* Mes */}
                  <th className="th-macro w-16">Mes</th>

                  {/* Titular/CUIT — con búsqueda */}
                  <th className="th-macro">
                    <ExcelFilter label="Titular / CUIT" active={!!(filters.titular || filters.cuit)}>
                      <p className="text-xs font-semibold text-gray-700 dark:text-gray-200 mb-2">Buscar en Titular</p>
                      <label className="label text-xs">Titular</label>
                      <input className="input-field text-xs mb-2" placeholder="Buscar..." value={filters.titular} onChange={e => set('titular', e.target.value)} />
                      <label className="label text-xs">CUIT</label>
                      <input className="input-field text-xs" placeholder="20112233440" value={filters.cuit} onChange={e => set('cuit', e.target.value)} />
                    </ExcelFilter>
                  </th>

                  {/* Importe — con rango min/max */}
                  <th className="th-macro w-28 text-right">
                    <ExcelFilter label="Importe" active={!!(filters.importe_min || filters.importe_max)} align="right">
                      <p className="text-xs font-semibold text-gray-700 dark:text-gray-200 mb-2">Rango de importe</p>
                      <label className="label text-xs">Mínimo</label>
                      <input className="input-field text-xs mb-2" placeholder="0" value={filters.importe_min} onChange={e => set('importe_min', e.target.value)} />
                      <label className="label text-xs">Máximo</label>
                      <input className="input-field text-xs" placeholder="999999999" value={filters.importe_max} onChange={e => set('importe_max', e.target.value)} />
                    </ExcelFilter>
                  </th>

                  {/* Saldo */}
                  <th className="th-macro w-28 text-right">Saldo</th>

                  {/* Cliente */}
                  <th className="th-macro w-28">
                    <ExcelFilter label="Cliente" active={!!filters.cliente} align="right">
                      <p className="text-xs font-semibold text-gray-700 dark:text-gray-200 mb-2">Cliente acreditado</p>
                      <input className="input-field text-xs" placeholder="Green, Tucu..." value={filters.cliente} onChange={e => set('cliente', e.target.value)} />
                    </ExcelFilter>
                  </th>

                  {/* Acred. — con rango de fecha + estado */}
                  <th className="th-macro w-32">
                    <ExcelFilter label="Acred." active={!!(filters.desde || filters.hasta || filters.sin_acreditar)} align="right">
                      <p className="text-xs font-semibold text-gray-700 dark:text-gray-200 mb-2">Fecha acreditación</p>
                      <label className="label text-xs">Desde</label>
                      <input type="date" className="input-field text-xs mb-2" value={filters.desde} onChange={e => set('desde', e.target.value)} />
                      <label className="label text-xs">Hasta</label>
                      <input type="date" className="input-field text-xs mb-2" value={filters.hasta} onChange={e => set('hasta', e.target.value)} />
                      <label className="label text-xs mt-1">Estado</label>
                      <select className="input-field text-xs" value={filters.sin_acreditar} onChange={e => set('sin_acreditar', e.target.value)}>
                        <option value="">Todos</option>
                        <option value="si">Acreditados</option>
                        <option value="no">Sin acreditar</option>
                      </select>
                    </ExcelFilter>
                  </th>
                </tr>
              </thead>

              <tbody className="divide-y divide-gray-100 dark:divide-slate-700">
                {filteredMovs.length === 0 ? (
                  <tr><td colSpan={8} className="py-8 text-center text-gray-400">Sin resultados</td></tr>
                ) : filteredMovs.slice(page * PAGE_SIZE, (page + 1) * PAGE_SIZE).map(m => {
                  const isEditing = editingId === m.id && tab === 'um'
                  return (
                    <tr key={m.id}
                      onDoubleClick={() => tab === 'um' && m.source === 'um' && startEdit(m)}
                      className={`transition-colors row-15 ${m.source === 'um' ? 'row-um' : 'hover:bg-gray-50 dark:hover:bg-slate-700/40'} ${tab === 'um' && m.source === 'um' ? 'cursor-pointer' : ''}`}>
                      <td className="px-2 text-center text-gray-400 dark:text-gray-500 font-mono">{m.orden ?? '—'}</td>
                      <td className="px-2 whitespace-nowrap dark:text-gray-300">{fmtDate(m.fecha)}</td>
                      <td className="px-2 text-gray-500 dark:text-gray-400">{
                        m.fecha ? new Date(m.fecha + 'T00:00:00').getMonth() + 1 : (m.mes || '—')
                      }</td>
                      <td className="px-2 max-w-[220px]">
                        {isEditing ? (
                          <input className="input-field !py-0 text-xs w-full" value={editValues.titular}
                            onChange={e => setEditValues(p => ({ ...p, titular: e.target.value }))}
                            onKeyDown={e => { if (e.key === 'Enter') saveEdit(m); if (e.key === 'Escape') setEditingId(null) }}
                            autoFocus />
                        ) : (
                          <p className="truncate dark:text-gray-200" title={m.titular || ''}>{m.titular || '—'}</p>
                        )}
                      </td>
                      <td className="px-2 text-right font-mono font-semibold dark:text-white">
                        {isEditing ? (
                          <input className="input-field !py-0 text-xs text-right w-24" value={editValues.monto}
                            onChange={e => setEditValues(p => ({ ...p, monto: e.target.value }))}
                            onKeyDown={e => { if (e.key === 'Enter') saveEdit(m); if (e.key === 'Escape') setEditingId(null) }} />
                        ) : fmtARS(m.monto)}
                      </td>
                      <td className="px-2 text-right font-mono text-gray-400 dark:text-gray-500">
                        {m.saldo != null ? fmtARS(m.saldo) : '—'}
                      </td>
                      <td className="px-2">
                        {m.cliente_acreditado && m.cliente_acreditado.toLowerCase() !== 'no identificado'
                          ? <span className="pill bg-green-100 dark:bg-green-900/40 text-green-800 dark:text-green-300 rounded-full text-[10px] font-medium">{m.cliente_acreditado}</span>
                          : <span className="text-gray-300 dark:text-gray-600 text-[10px]">—</span>}
                      </td>
                      <td className="px-2 whitespace-nowrap text-gray-500 dark:text-gray-400">
                        {fmtDate(m.fecha_acred)}
                        {isEditing && (
                          <div className="flex gap-1 mt-0.5">
                            <button onClick={() => saveEdit(m)} className="text-[10px] text-green-600 hover:underline">Guardar</button>
                            <button onClick={() => setEditingId(null)} className="text-[10px] text-gray-400 hover:underline">X</button>
                          </div>
                        )}
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  )
}
