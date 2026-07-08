import React, { useEffect, useState, useCallback, useMemo } from 'react'
import { apiClient } from '@/services/api'
import { useOrgStore } from '@/store/org'
import { parseMonto } from '@/utils/monto'

interface ConciliacionItem {
  id: number
  extracto_id: number
  orden: number | null
  fecha: string | null
  titular: string | null
  monto: number
  saldo: number | null
  cliente_acreditado: string
  fecha_acred: string | null
}

function useDebounce<T>(value: T, delay: number): T {
  const [d, setD] = useState(value)
  useEffect(() => {
    const id = setTimeout(() => setD(value), delay)
    return () => clearTimeout(id)
  }, [value, delay])
  return d
}

function fmtARS(n: number | null | undefined) {
  if (n == null) return '—'
  return new Intl.NumberFormat('es-AR', { style: 'currency', currency: 'ARS', minimumFractionDigits: 0 }).format(n)
}
function fmtDate(d?: string | null) {
  if (!d) return '—'
  try { return new Date(d + 'T00:00:00').toLocaleDateString('es-AR', { day: '2-digit', month: '2-digit', year: '2-digit' }) }
  catch { return d }
}

export const Conciliaciones: React.FC = () => {
  const { activeOrgId } = useOrgStore()
  const [items, setItems] = useState<ConciliacionItem[]>([])
  const [total, setTotal] = useState(0)
  const [suma, setSuma] = useState(0)
  const [loading, setLoading] = useState(false)
  const [exporting, setExporting] = useState(false)
  const [cliente, setCliente] = useState('')
  const [titular, setTitular] = useState('')
  const [desde, setDesde] = useState('')
  const [hasta, setHasta] = useState('')
  const [montoMin, setMontoMin] = useState('')
  const [montoMax, setMontoMax] = useState('')
  const [page, setPage] = useState(0)
  const PAGE_SIZE = 200

  const dCliente = useDebounce(cliente, 800)
  const dTitular = useDebounce(titular, 800)
  const dMontoMin = useDebounce(montoMin, 800)
  const dMontoMax = useDebounce(montoMax, 800)

  const filtros = useMemo(() => {
    const f: Record<string, string | number> = {}
    if (dCliente) f.cliente = dCliente
    if (dTitular) f.titular = dTitular
    if (desde) f.desde = desde
    if (hasta) f.hasta = hasta
    const mn = parseMonto(dMontoMin)  // util compartido y testeado (formatos AR/US)
    const mx = parseMonto(dMontoMax)
    if (mn != null) f.monto_min = mn
    if (mx != null) f.monto_max = mx
    if (activeOrgId) f.org_id = activeOrgId
    return f
  }, [dCliente, dTitular, desde, hasta, dMontoMin, dMontoMax, activeOrgId])

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const d = await apiClient.listConciliaciones({ ...filtros, limit: 2000 })
      setItems(d.items as ConciliacionItem[])
      setTotal(d.total)
      setSuma(d.suma)
      setPage(0)
    } catch {
      setItems([]); setTotal(0); setSuma(0)
    } finally {
      setLoading(false)
    }
  }, [filtros])

  useEffect(() => { load() }, [load])

  const handleExport = async () => {
    setExporting(true)
    try { await apiClient.exportConciliaciones(filtros) } finally { setExporting(false) }
  }

  const clienteOpts = useMemo(() => {
    const s = new Set<string>()
    items.forEach(i => { if (i.cliente_acreditado) s.add(i.cliente_acreditado) })
    return Array.from(s).sort()
  }, [items])

  const hayFiltros = !!(cliente || titular || desde || hasta || montoMin || montoMax)

  const clear = () => {
    setCliente(''); setTitular(''); setDesde(''); setHasta(''); setMontoMin(''); setMontoMax('')
  }

  return (
    <div className="pl-1 pr-3 py-3 md:pl-2 md:pr-6 md:py-6 max-w-full">
      <div className="flex flex-wrap items-start gap-2 mb-3">
        <div className="flex-1 min-w-0">
          <h1 className="text-lg md:text-xl font-bold dark:text-white">Conciliaciones</h1>
          <p className="text-xs text-gray-500 dark:text-gray-400 mt-0.5">
            Todas las acreditaciones de todos los extractos.
            <b className="ml-2">{total}</b> {total === 1 ? 'movimiento' : 'movimientos'}
            <span className="ml-2 text-emerald-600 dark:text-emerald-400 font-semibold">· total {fmtARS(suma)}</span>
          </p>
        </div>
        <div className="flex gap-1.5 flex-wrap">
          {hayFiltros && (
            <button onClick={clear} className="px-3 py-1.5 text-xs text-red-600 border border-red-300 rounded-md hover:bg-red-50 dark:text-red-400 dark:border-red-700">
              ✕ Limpiar
            </button>
          )}
          <button onClick={handleExport} disabled={exporting || total === 0}
            className="flex items-center gap-1 px-3 py-1.5 text-xs bg-green-600 text-white rounded-md hover:bg-green-700 disabled:opacity-50">
            {exporting ? '⏳' : '⬇️'} Exportar Excel
          </button>
        </div>
      </div>

      {/* Filtros */}
      <div className="grid grid-cols-2 md:grid-cols-6 gap-2 mb-3 bg-white dark:bg-slate-800 border border-gray-100 dark:border-slate-700 rounded-lg p-3 shadow-sm">
        <div className="col-span-2 md:col-span-1">
          <label className="label text-xs">Cliente</label>
          <input list="conc-clientes" className="input-field" placeholder="Green, Tucu..." value={cliente} onChange={e => setCliente(e.target.value)} />
          <datalist id="conc-clientes">
            {clienteOpts.map(c => <option key={c} value={c} />)}
          </datalist>
        </div>
        <div className="col-span-2 md:col-span-1">
          <label className="label text-xs">Titular</label>
          <input className="input-field" placeholder="Buscar titular..." value={titular} onChange={e => setTitular(e.target.value)} />
        </div>
        <div>
          <label className="label text-xs">Desde</label>
          <input type="date" className="input-field" value={desde} onChange={e => setDesde(e.target.value)} />
        </div>
        <div>
          <label className="label text-xs">Hasta</label>
          <input type="date" className="input-field" value={hasta} onChange={e => setHasta(e.target.value)} />
        </div>
        <div>
          <label className="label text-xs">Desde $</label>
          <input className="input-field" placeholder="0" value={montoMin} onChange={e => setMontoMin(e.target.value)} />
        </div>
        <div>
          <label className="label text-xs">Hasta $</label>
          <input className="input-field" placeholder="999999999" value={montoMax} onChange={e => setMontoMax(e.target.value)} />
        </div>
      </div>

      {/* Tabla */}
      <div className="bg-white dark:bg-slate-800 border border-gray-100 dark:border-slate-700 overflow-hidden shadow-sm rounded-lg">
        {loading ? (
          <div className="p-8 text-center text-gray-400">Cargando...</div>
        ) : items.length === 0 ? (
          <div className="p-8 text-center text-gray-400">
            {hayFiltros ? 'Sin resultados para los filtros aplicados' : 'No hay acreditaciones registradas todavía'}
          </div>
        ) : (
          <>
          {items.length > PAGE_SIZE && (
            <div className="px-3 py-1.5 bg-gray-50 dark:bg-slate-900 border-b dark:border-slate-700 flex items-center justify-between gap-2 flex-wrap">
              <span className="text-xs text-gray-500 dark:text-gray-400">
                mostrando {page * PAGE_SIZE + 1}–{Math.min((page + 1) * PAGE_SIZE, items.length)} de {items.length}
              </span>
              <div className="flex items-center gap-1">
                <button onClick={() => setPage(p => Math.max(0, p - 1))} disabled={page === 0}
                  className="px-2 py-0.5 text-xs rounded border border-gray-300 dark:border-slate-600 disabled:opacity-30 hover:bg-gray-100 dark:hover:bg-slate-700">
                  ← Ant.
                </button>
                <span className="text-xs text-gray-500 dark:text-gray-400 px-1">
                  {page + 1} / {Math.ceil(items.length / PAGE_SIZE)}
                </span>
                <button onClick={() => setPage(p => Math.min(Math.ceil(items.length / PAGE_SIZE) - 1, p + 1))}
                  disabled={page >= Math.ceil(items.length / PAGE_SIZE) - 1}
                  className="px-2 py-0.5 text-xs rounded border border-gray-300 dark:border-slate-600 disabled:opacity-30 hover:bg-gray-100 dark:hover:bg-slate-700">
                  Sig. →
                </button>
              </div>
            </div>
          )}
          <div className="overflow-x-auto max-h-[calc(100dvh-260px)]" style={{ WebkitOverflowScrolling: 'touch' }}>
            <table className="w-full text-xs border-collapse min-w-[700px]">
              <thead className="sticky top-0 z-10">
                <tr>
                  <th className="th-macro w-24">Fecha mov.</th>
                  <th className="th-macro">Titular</th>
                  <th className="th-macro w-28 text-right">Importe</th>
                  <th className="th-macro w-28">Cliente</th>
                  <th className="th-macro w-24">Acreditado</th>
                  <th className="th-macro w-16 text-center">Extracto</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100 dark:divide-slate-700">
                {items.slice(page * PAGE_SIZE, (page + 1) * PAGE_SIZE).map(m => (
                  <tr key={m.id} className="row-15 hover:bg-gray-50 dark:hover:bg-slate-700/40">
                    <td className="px-2 whitespace-nowrap dark:text-gray-300">{fmtDate(m.fecha)}</td>
                    <td className="px-2 max-w-[260px]">
                      <p className="truncate dark:text-gray-200" title={m.titular || ''}>{m.titular || '—'}</p>
                    </td>
                    <td className="px-2 text-right font-mono font-semibold dark:text-white">{fmtARS(m.monto)}</td>
                    <td className="px-2">
                      <span className="pill bg-green-100 dark:bg-green-900/40 text-green-800 dark:text-green-300 rounded-full text-[10px] font-medium">
                        {m.cliente_acreditado}
                      </span>
                    </td>
                    <td className="px-2 whitespace-nowrap text-gray-500 dark:text-gray-400">{fmtDate(m.fecha_acred)}</td>
                    <td className="px-2 text-center text-gray-400 font-mono">#{m.extracto_id}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          </>
        )}
      </div>
    </div>
  )
}
