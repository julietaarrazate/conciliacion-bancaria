import React, { useEffect, useState, useCallback } from 'react'
import { apiClient } from '@/services/api'
import {
  ExtractoListItem,
  MovimientoFiltrado,
  MovimientosFiltros
} from '@/types'

export const Movimientos: React.FC = () => {
  const [extractos, setExtractos] = useState<ExtractoListItem[]>([])
  const [extractoId, setExtractoId] = useState<number | null>(null)
  const [movimientos, setMovimientos] = useState<MovimientoFiltrado[]>([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(false)
  const [filters, setFilters] = useState<MovimientosFiltros>({ limit: 500 })
  const [umLoading, setUmLoading] = useState(false)
  const [umMsg, setUmMsg] = useState('')

  // cargar lista de extractos
  useEffect(() => {
    apiClient.listExtractos().then((data) => {
      setExtractos(data.items)
      if (data.items.length > 0 && !extractoId) {
        setExtractoId(data.items[0].id)
      }
    })
  }, [])

  const loadMovimientos = useCallback(async () => {
    if (!extractoId) return
    setLoading(true)
    try {
      const data = await apiClient.getMovimientos(extractoId, filters)
      setMovimientos(data.items)
      setTotal(data.total)
    } catch {
      setMovimientos([])
      setTotal(0)
    } finally {
      setLoading(false)
    }
  }, [extractoId, filters])

  useEffect(() => {
    loadMovimientos()
  }, [loadMovimientos])

  const updateFilter = (k: keyof MovimientosFiltros, v: string | boolean | undefined) => {
    setFilters((prev) => ({ ...prev, [k]: v === '' ? undefined : v }))
  }

  const clearFilters = () => {
    setFilters({ limit: 500 })
  }

  const handleAppendUM = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file || !extractoId) return

    setUmLoading(true)
    setUmMsg('')
    try {
      const res = await apiClient.appendUM(extractoId, file)
      setUmMsg(
        `✓ UM procesado: ${res.agregados} nuevos, ${res.duplicados} duplicados (${res.total_recibido} total recibidos)`
      )
      loadMovimientos()
    } catch (err: any) {
      setUmMsg(`✗ Error: ${err.response?.data?.detail || 'falló'}`)
    } finally {
      setUmLoading(false)
      e.target.value = '' // permite re-subir mismo archivo
    }
  }

  const fmtCurrency = (n: number) =>
    new Intl.NumberFormat('es-AR', {
      style: 'currency',
      currency: 'ARS',
      minimumFractionDigits: 2
    }).format(n)

  const fmtDate = (d?: string) => (d ? new Date(d).toLocaleDateString('es-AR') : '—')

  return (
    <div className="p-6 max-w-full mx-auto">
      <h1 className="text-2xl font-bold text-gray-900 mb-1">Movimientos del extracto</h1>
      <p className="text-gray-600 mb-4">
        Filtros tipo Excel sobre el extracto bancario
      </p>

      {/* Selector de extracto + UM */}
      <div className="card mb-4">
        <div className="flex items-end gap-3 flex-wrap">
          <div className="flex-1 min-w-[300px]">
            <label className="label">Extracto bancario</label>
            <select
              className="input-field"
              value={extractoId ?? ''}
              onChange={(e) => setExtractoId(Number(e.target.value))}
            >
              {extractos.length === 0 && <option value="">— sin extractos —</option>}
              {extractos.map((e) => (
                <option key={e.id} value={e.id}>
                  #{e.id} · {e.nombre_archivo} · {e.total_movimientos} movs
                </option>
              ))}
            </select>
          </div>

          {extractoId && (
            <div>
              <label className="label">Agregar Últimos Movimientos</label>
              <label className="btn-primary cursor-pointer inline-block">
                {umLoading ? 'Procesando...' : '+ Subir UM'}
                <input
                  type="file"
                  accept=".xlsx"
                  hidden
                  onChange={handleAppendUM}
                  disabled={umLoading}
                />
              </label>
            </div>
          )}
        </div>
        {umMsg && (
          <p className={`mt-3 text-sm ${umMsg.startsWith('✓') ? 'text-green-700' : 'text-red-700'}`}>
            {umMsg}
          </p>
        )}
      </div>

      {/* Filtros */}
      <div className="card mb-4">
        <div className="grid grid-cols-1 md:grid-cols-3 lg:grid-cols-4 gap-3">
          <div>
            <label className="label">Cliente acreditado</label>
            <input
              className="input-field"
              placeholder="Green, Tucu..."
              value={filters.cliente || ''}
              onChange={(e) => updateFilter('cliente', e.target.value)}
            />
          </div>
          <div>
            <label className="label">CUIT</label>
            <input
              className="input-field"
              placeholder="20123456789"
              value={filters.cuit || ''}
              onChange={(e) => updateFilter('cuit', e.target.value)}
            />
          </div>
          <div>
            <label className="label">Titular (texto)</label>
            <input
              className="input-field"
              placeholder="Nombre, concepto..."
              value={filters.titular || ''}
              onChange={(e) => updateFilter('titular', e.target.value)}
            />
          </div>
          <div>
            <label className="label">Estado</label>
            <select
              className="input-field"
              value={
                filters.sin_acreditar === true
                  ? 'no'
                  : filters.sin_acreditar === false
                  ? 'si'
                  : ''
              }
              onChange={(e) =>
                updateFilter(
                  'sin_acreditar',
                  e.target.value === 'no'
                    ? true
                    : e.target.value === 'si'
                    ? false
                    : undefined
                )
              }
            >
              <option value="">Todos</option>
              <option value="si">Solo acreditados</option>
              <option value="no">Solo no acreditados</option>
            </select>
          </div>

          <div>
            <label className="label">Acreditado desde</label>
            <input
              type="date"
              className="input-field"
              value={filters.desde || ''}
              onChange={(e) => updateFilter('desde', e.target.value)}
            />
          </div>
          <div>
            <label className="label">Acreditado hasta</label>
            <input
              type="date"
              className="input-field"
              value={filters.hasta || ''}
              onChange={(e) => updateFilter('hasta', e.target.value)}
            />
          </div>
          <div>
            <label className="label">Mov. desde</label>
            <input
              type="date"
              className="input-field"
              value={filters.fecha_desde || ''}
              onChange={(e) => updateFilter('fecha_desde', e.target.value)}
            />
          </div>
          <div>
            <label className="label">Mov. hasta</label>
            <input
              type="date"
              className="input-field"
              value={filters.fecha_hasta || ''}
              onChange={(e) => updateFilter('fecha_hasta', e.target.value)}
            />
          </div>
        </div>

        <div className="mt-4 flex gap-2">
          <button onClick={loadMovimientos} className="btn-primary">
            Aplicar filtros
          </button>
          <button onClick={clearFilters} className="btn-secondary">
            Limpiar
          </button>
        </div>
      </div>

      {/* Tabla */}
      <div className="card overflow-hidden p-0">
        <div className="px-4 py-2 bg-gray-50 border-b text-sm text-gray-700">
          <strong>{total}</strong> movimiento{total !== 1 ? 's' : ''} encontrado
          {total !== 1 ? 's' : ''}
          {movimientos.length < total && ` (mostrando ${movimientos.length})`}
        </div>

        {loading ? (
          <div className="p-8 text-center text-gray-500">Cargando...</div>
        ) : movimientos.length === 0 ? (
          <div className="p-8 text-center text-gray-500">Sin resultados</div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-gray-50 border-b sticky top-0">
                <tr>
                  <th className="px-3 py-2 text-left text-xs font-semibold text-gray-600">Orden</th>
                  <th className="px-3 py-2 text-left text-xs font-semibold text-gray-600">Fecha</th>
                  <th className="px-3 py-2 text-left text-xs font-semibold text-gray-600">Mes</th>
                  <th className="px-3 py-2 text-left text-xs font-semibold text-gray-600">Titular / CUIT</th>
                  <th className="px-3 py-2 text-right text-xs font-semibold text-gray-600">Importe</th>
                  <th className="px-3 py-2 text-right text-xs font-semibold text-gray-600">Saldo</th>
                  <th className="px-3 py-2 text-left text-xs font-semibold text-gray-600">Cliente</th>
                  <th className="px-3 py-2 text-left text-xs font-semibold text-gray-600">Acred.</th>
                </tr>
              </thead>
              <tbody className="divide-y">
                {movimientos.map((m) => (
                  <tr key={m.id} className="hover:bg-gray-50">
                    <td className="px-3 py-2 text-gray-600">{m.orden ?? '—'}</td>
                    <td className="px-3 py-2 text-gray-600 whitespace-nowrap">
                      {fmtDate(m.fecha)}
                    </td>
                    <td className="px-3 py-2 text-gray-600">{m.mes || '—'}</td>
                    <td className="px-3 py-2 text-gray-700 max-w-md truncate" title={m.titular || ''}>
                      {m.titular || '—'}
                    </td>
                    <td className="px-3 py-2 text-right font-mono text-gray-900">
                      {fmtCurrency(m.monto)}
                    </td>
                    <td className="px-3 py-2 text-right font-mono text-gray-500">
                      {m.saldo !== null && m.saldo !== undefined ? fmtCurrency(m.saldo) : '—'}
                    </td>
                    <td className="px-3 py-2">
                      {m.cliente_acreditado ? (
                        <span className="px-2 py-0.5 rounded text-xs font-semibold bg-green-100 text-green-700">
                          {m.cliente_acreditado}
                        </span>
                      ) : (
                        <span className="text-gray-400 text-xs">no acreditado</span>
                      )}
                    </td>
                    <td className="px-3 py-2 text-gray-600 whitespace-nowrap">
                      {fmtDate(m.fecha_acred)}
                    </td>
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
