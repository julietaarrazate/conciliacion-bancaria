import React, { useEffect, useState, useCallback, useRef } from 'react'
import { useSearchParams } from 'react-router-dom'
import { apiClient } from '@/services/api'
import { ExtractoListItem, MovimientoFiltrado, MovimientosFiltros } from '@/types'

// ── Filtros inline en header (estilo Excel) ──────────────────────────────────
interface ColFilter { cliente: string; cuit: string; titular: string; desde: string; hasta: string; fecha_desde: string; fecha_hasta: string; sin_acreditar: string }
const EMPTY_COL: ColFilter = { cliente: '', cuit: '', titular: '', desde: '', hasta: '', fecha_desde: '', fecha_hasta: '', sin_acreditar: '' }

type FilterKey = keyof ColFilter

function ColFilterInput({ field, placeholder, value, onChange, type = 'text' }: {
  field: FilterKey; placeholder: string; value: string
  onChange: (k: FilterKey, v: string) => void; type?: string
}) {
  return (
    <input
      type={type}
      className="w-full mt-1 px-1.5 py-0.5 text-[11px] border border-blue-300 rounded bg-blue-50 dark:bg-blue-900/20 dark:border-blue-700 dark:text-blue-100 focus:outline-none focus:border-ml-blue placeholder:text-blue-300"
      placeholder={placeholder}
      value={value}
      onChange={e => onChange(field, e.target.value)}
    />
  )
}

function fmtARS(n: number) {
  return new Intl.NumberFormat('es-AR', { style: 'currency', currency: 'ARS', minimumFractionDigits: 0 }).format(n)
}
function fmtDate(d?: string | null) {
  if (!d) return '—'
  try { return new Date(d + 'T00:00:00').toLocaleDateString('es-AR', { day: '2-digit', month: '2-digit', year: '2-digit' }) }
  catch { return d }
}

export const Movimientos: React.FC = () => {
  const [searchParams] = useSearchParams()
  const [extractos, setExtractos] = useState<ExtractoListItem[]>([])
  const [extractoId, setExtractoId] = useState<number | null>(null)
  const [movimientos, setMovimientos] = useState<MovimientoFiltrado[]>([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(false)
  const [colFilters, setColFilters] = useState<ColFilter>(EMPTY_COL)
  const [umLoading, setUmLoading] = useState(false)
  const [umMsg, setUmMsg] = useState('')
  const [exporting, setExporting] = useState(false)
  const umRef = useRef<HTMLInputElement>(null)

  // Cargar lista de extractos
  useEffect(() => {
    apiClient.listExtractos().then(data => {
      setExtractos(data.items)
      const paramId = searchParams.get('extracto')
      if (paramId) setExtractoId(Number(paramId))
      else if (data.items.length > 0) setExtractoId(data.items[0].id)
    })
  }, [])

  const buildFilters = (): MovimientosFiltros => {
    const f: MovimientosFiltros = { limit: 1000 }
    if (colFilters.cliente) f.cliente = colFilters.cliente
    if (colFilters.cuit) f.cuit = colFilters.cuit
    if (colFilters.titular) f.titular = colFilters.titular
    if (colFilters.desde) f.desde = colFilters.desde
    if (colFilters.hasta) f.hasta = colFilters.hasta
    if (colFilters.fecha_desde) f.fecha_desde = colFilters.fecha_desde
    if (colFilters.fecha_hasta) f.fecha_hasta = colFilters.fecha_hasta
    if (colFilters.sin_acreditar === 'no') f.sin_acreditar = true
    if (colFilters.sin_acreditar === 'si') f.sin_acreditar = false
    return f
  }

  const load = useCallback(async () => {
    if (!extractoId) return
    setLoading(true)
    try {
      const data = await apiClient.getMovimientos(extractoId, buildFilters())
      setMovimientos(data.items)
      setTotal(data.total)
    } catch { setMovimientos([]); setTotal(0) }
    finally { setLoading(false) }
  }, [extractoId, colFilters])

  useEffect(() => { load() }, [load])

  // Actualizar lista de extractos al volver a la página
  const refreshExtractos = async () => {
    const data = await apiClient.listExtractos()
    setExtractos(data.items)
    if (data.items.length > 0 && !extractoId) setExtractoId(data.items[0].id)
    // Actualizar el total del extracto activo
    const activo = data.items.find(e => e.id === extractoId)
    if (activo) setTotal(prev => prev) // refresh happens via load()
    load()
  }

  const setColFilter = (k: FilterKey, v: string) => setColFilters(prev => ({ ...prev, [k]: v }))
  const clearFilters = () => setColFilters(EMPTY_COL)
  const hasFilters = Object.values(colFilters).some(Boolean)

  const handleAppendUM = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file || !extractoId) return
    setUmLoading(true); setUmMsg('')
    try {
      const r = await apiClient.appendUM(extractoId, file)
      setUmMsg(`✓ UM: ${r.agregados} nuevos · ${r.duplicados} duplicados ignorados`)
      await refreshExtractos()
    } catch (err: any) {
      setUmMsg(`✗ ${err.response?.data?.detail || 'Error'}`)
    } finally {
      setUmLoading(false)
      if (umRef.current) umRef.current.value = ''
    }
  }

  const handleExport = async () => {
    if (!extractoId) return
    setExporting(true)
    try { await apiClient.exportMovimientos(extractoId, buildFilters()) }
    finally { setExporting(false) }
  }

  const extractoActivo = extractos.find(e => e.id === extractoId)

  // Encabezado azul tipo extracto Macro
  const TH = ({ children, className = '' }: { children: React.ReactNode; className?: string }) => (
    <th className={`px-2 py-2 text-left text-xs font-bold text-white bg-ml-blue border-r border-blue-500 last:border-r-0 ${className}`}>
      {children}
    </th>
  )

  return (
    <div className="p-4 max-w-full">
      <div className="flex flex-wrap items-start gap-3 mb-3">
        <div className="flex-1 min-w-[300px]">
          <h1 className="text-xl font-bold text-ml-text dark:text-white mb-1">Movimientos del extracto</h1>
          {extractoActivo && (
            <p className="text-xs text-ml-text-soft dark:text-gray-400">
              {extractoActivo.nombre_archivo} · <strong>{extractoActivo.total_movimientos}</strong> movimientos totales
              {hasFilters && ` · mostrando ${movimientos.length} (filtrado)`}
            </p>
          )}
        </div>
        <div className="flex gap-2 flex-wrap">
          <button onClick={handleExport} disabled={exporting || movimientos.length === 0}
            className="flex items-center gap-1.5 px-3 py-1.5 text-sm bg-green-600 text-white rounded hover:bg-green-700 disabled:opacity-50">
            {exporting ? '⏳' : '⬇️'} Excel
          </button>
        </div>
      </div>

      {/* Selector extracto + UM */}
      <div className="card mb-3 flex flex-wrap gap-3 items-end py-3">
        <div className="flex-1 min-w-[280px]">
          <label className="label">Extracto</label>
          <select className="input-field" value={extractoId ?? ''} onChange={e => setExtractoId(Number(e.target.value))}>
            {extractos.map(e => <option key={e.id} value={e.id}>#{e.id} · {e.nombre_archivo} ({e.total_movimientos} movs)</option>)}
          </select>
        </div>
        <div>
          <label className="label">+ Agregar UM</label>
          <label className={`flex items-center gap-2 px-3 py-2 rounded border cursor-pointer text-sm font-medium transition-colors ${umLoading ? 'opacity-50' : 'bg-ml-blue text-white hover:bg-ml-blue-dark border-ml-blue'}`}>
            {umLoading ? '⏳ Procesando...' : '📎 Subir UM'}
            <input ref={umRef} type="file" accept=".xlsx" hidden onChange={handleAppendUM} disabled={umLoading || !extractoId} />
          </label>
        </div>
        {hasFilters && (
          <button onClick={clearFilters} className="px-3 py-2 text-sm text-red-600 border border-red-300 rounded hover:bg-red-50 dark:text-red-400 dark:border-red-700">
            ✕ Limpiar filtros
          </button>
        )}
      </div>

      {umMsg && (
        <div className={`mb-3 p-2.5 rounded text-sm ${umMsg.startsWith('✓') ? 'bg-green-50 text-green-700 dark:bg-green-900/20 dark:text-green-300' : 'bg-red-50 text-red-700'}`}>
          {umMsg}
        </div>
      )}

      {/* Tabla con headers azules + filtros inline */}
      <div className="card overflow-hidden p-0 shadow-sm">
        <div className="px-3 py-2 bg-ml-gray-bg dark:bg-slate-900 border-b dark:border-slate-700 text-xs text-ml-text-soft">
          <strong>{total}</strong> movimiento{total !== 1 ? 's' : ''}
          {movimientos.length < total && ` · mostrando ${movimientos.length}`}
          {hasFilters && <span className="ml-2 text-ml-blue font-medium">· filtros activos</span>}
        </div>

        {loading ? (
          <div className="p-8 text-center text-ml-text-soft">Cargando...</div>
        ) : (
          <div className="overflow-x-auto max-h-[calc(100vh-280px)]">
            <table className="w-full text-sm border-collapse">
              <thead className="sticky top-0 z-10">
                <tr>
                  <TH className="w-14">Orden</TH>
                  <TH className="w-24">Fecha</TH>
                  <TH className="w-20">Mes</TH>
                  <TH>Titular / CUIT</TH>
                  <TH className="w-28 text-right">Importe</TH>
                  <TH className="w-28 text-right">Saldo</TH>
                  <TH className="w-28">Cliente</TH>
                  <TH className="w-24">Acred.</TH>
                </tr>
                {/* Fila de filtros inline */}
                <tr className="bg-blue-50 dark:bg-blue-900/10 border-b-2 border-ml-blue">
                  <td className="px-2 pb-2 pt-1">
                    <input className="w-full px-1.5 py-0.5 text-[11px] border border-blue-300 rounded bg-white dark:bg-slate-800 dark:text-gray-200" placeholder="🔍" />
                  </td>
                  <td className="px-2 pb-2 pt-1">
                    <ColFilterInput field="fecha_desde" placeholder="desde" value={colFilters.fecha_desde} onChange={setColFilter} type="date" />
                    <ColFilterInput field="fecha_hasta" placeholder="hasta" value={colFilters.fecha_hasta} onChange={setColFilter} type="date" />
                  </td>
                  <td className="px-2 pb-2 pt-1"></td>
                  <td className="px-2 pb-2 pt-1">
                    <ColFilterInput field="titular" placeholder="🔍 titular / concepto" value={colFilters.titular} onChange={setColFilter} />
                    <ColFilterInput field="cuit" placeholder="🔍 CUIT" value={colFilters.cuit} onChange={setColFilter} />
                  </td>
                  <td className="px-2 pb-2 pt-1"></td>
                  <td className="px-2 pb-2 pt-1"></td>
                  <td className="px-2 pb-2 pt-1">
                    <ColFilterInput field="cliente" placeholder="🔍 cliente" value={colFilters.cliente} onChange={setColFilter} />
                  </td>
                  <td className="px-2 pb-2 pt-1">
                    <select className="w-full mt-1 px-1.5 py-0.5 text-[11px] border border-blue-300 rounded bg-blue-50 dark:bg-blue-900/20 dark:text-blue-100"
                      value={colFilters.sin_acreditar} onChange={e => setColFilter('sin_acreditar', e.target.value)}>
                      <option value="">Todos</option>
                      <option value="si">Acreditados</option>
                      <option value="no">Sin acreditar</option>
                    </select>
                    <ColFilterInput field="desde" placeholder="acred desde" value={colFilters.desde} onChange={setColFilter} type="date" />
                    <ColFilterInput field="hasta" placeholder="acred hasta" value={colFilters.hasta} onChange={setColFilter} type="date" />
                  </td>
                </tr>
              </thead>

              <tbody className="divide-y dark:divide-slate-700">
                {movimientos.length === 0 ? (
                  <tr><td colSpan={8} className="p-6 text-center text-ml-text-soft">Sin resultados</td></tr>
                ) : movimientos.map(m => (
                  <tr key={m.id} className={`hover:bg-ml-gray-bg dark:hover:bg-slate-700/50 ${m.cliente_acreditado && m.cliente_acreditado.toLowerCase() !== 'no identificado' ? 'bg-green-50/40 dark:bg-green-900/10' : ''}`}>
                    <td className="px-2 py-1.5 text-center text-ml-text-soft dark:text-gray-400 font-mono text-xs">{m.orden ?? '—'}</td>
                    <td className="px-2 py-1.5 whitespace-nowrap text-xs dark:text-gray-300">{fmtDate(m.fecha)}</td>
                    <td className="px-2 py-1.5 text-xs text-ml-text-soft dark:text-gray-400">{m.mes || '—'}</td>
                    <td className="px-2 py-1.5 max-w-xs">
                      <p className="truncate text-xs dark:text-gray-200" title={m.titular || ''}>{m.titular || '—'}</p>
                    </td>
                    <td className="px-2 py-1.5 text-right font-mono text-xs font-medium dark:text-white">{fmtARS(m.monto)}</td>
                    <td className="px-2 py-1.5 text-right font-mono text-xs text-ml-text-soft dark:text-gray-400">
                      {m.saldo !== undefined && m.saldo !== null ? fmtARS(m.saldo) : '—'}
                    </td>
                    <td className="px-2 py-1.5">
                      {m.cliente_acreditado && m.cliente_acreditado.toLowerCase() !== 'no identificado'
                        ? <span className="px-2 py-0.5 bg-green-100 dark:bg-green-900/40 text-green-800 dark:text-green-300 rounded-full text-[11px] font-medium">{m.cliente_acreditado}</span>
                        : <span className="text-ml-text-soft text-[11px]">—</span>
                      }
                    </td>
                    <td className="px-2 py-1.5 text-xs text-ml-text-soft dark:text-gray-400 whitespace-nowrap">{fmtDate(m.fecha_acred)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  )
}
