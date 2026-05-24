import React, { useEffect, useState } from 'react'
import { apiClient } from '@/services/api'

interface ItemPapelera {
  id: number
  tipo: 'extracto' | 'planilla'
  nombre?: string
  cliente_nombre?: string | null
  nombre_archivo?: string
  organizacion_id: number
  fecha_creacion?: string
  fecha_carga?: string
  deleted_at: string
  movimientos?: number
  filas?: number
}

interface PapeleraData {
  extractos: ItemPapelera[]
  planillas: ItemPapelera[]
  total: number
}

export const Papelera: React.FC = () => {
  const [data, setData] = useState<PapeleraData | null>(null)
  const [loading, setLoading] = useState(true)
  const [actionId, setActionId] = useState<string | null>(null)
  const [mensaje, setMensaje] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  const cargar = async () => {
    setLoading(true)
    try {
      const res = await apiClient.client.get('/admin/papelera')
      setData(res.data)
    } catch (ex: any) {
      setError(ex?.response?.data?.detail || 'Error al cargar papelera')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { cargar() }, [])

  const restaurar = async (tipo: string, id: number) => {
    const key = `${tipo}-${id}`
    setActionId(key)
    setMensaje(null); setError(null)
    try {
      await apiClient.client.post(`/admin/papelera/restaurar/${tipo}/${id}`)
      setMensaje(`${tipo === 'extracto' ? 'Extracto' : 'Planilla'} #${id} restaurada`)
      await cargar()
    } catch (ex: any) {
      setError(ex?.response?.data?.detail || 'Error al restaurar')
    } finally {
      setActionId(null)
    }
  }

  const purgar = async (tipo: string, id: number, nombre: string) => {
    const confirma = window.prompt(
      `BORRAR DEFINITIVAMENTE el ${tipo} "${nombre}"?\n` +
      `Esto NO se puede deshacer.\n\nEscribí BORRAR para confirmar:`
    )
    if (confirma !== 'BORRAR') return

    const key = `${tipo}-${id}`
    setActionId(key)
    setMensaje(null); setError(null)
    try {
      await apiClient.client.delete(`/admin/papelera/purgar/${tipo}/${id}?confirmar=BORRAR`)
      setMensaje(`${tipo === 'extracto' ? 'Extracto' : 'Planilla'} #${id} borrado definitivamente`)
      await cargar()
    } catch (ex: any) {
      setError(ex?.response?.data?.detail || 'Error al purgar')
    } finally {
      setActionId(null)
    }
  }

  const fmtFecha = (iso?: string) => {
    if (!iso) return '-'
    const d = new Date(iso)
    return d.toLocaleString('es-AR', {
      day: '2-digit', month: '2-digit', year: '2-digit',
      hour: '2-digit', minute: '2-digit'
    })
  }

  return (
    <div className="p-4 md:p-6 max-w-6xl mx-auto">
      <div className="mb-5">
        <h1 className="text-xl font-bold dark:text-white">Papelera de reciclaje</h1>
        <p className="text-sm text-gray-400 dark:text-zinc-500 mt-0.5">
          Registros borrados — se pueden restaurar o purgar definitivamente.
        </p>
      </div>

      {mensaje && (
        <div className="mb-4 p-3 rounded-lg bg-green-50 border border-green-200 text-green-700 text-sm
                        dark:bg-green-900/20 dark:border-green-900 dark:text-green-400">
          {mensaje}
        </div>
      )}
      {error && (
        <div className="mb-4 p-3 rounded-lg bg-red-50 border border-red-200 text-red-700 text-sm
                        dark:bg-red-900/20 dark:border-red-900 dark:text-red-400">
          {error}
        </div>
      )}

      {loading ? (
        <div className="text-gray-500 dark:text-zinc-500 text-sm">Cargando...</div>
      ) : !data || data.total === 0 ? (
        <div className="card text-center py-12">
          <div className="text-4xl mb-2">🗑️</div>
          <div className="text-gray-500 dark:text-zinc-400">La papelera está vacía</div>
          <div className="text-xs text-gray-400 dark:text-zinc-600 mt-1">
            Cuando borrés un extracto o planilla aparecerá acá, listo para restaurar.
          </div>
        </div>
      ) : (
        <div className="space-y-6">
          {/* Extractos borrados */}
          {data.extractos.length > 0 && (
            <div className="card">
              <h2 className="text-sm font-bold uppercase tracking-wide text-ml-text-soft dark:text-zinc-400 mb-3">
                Extractos ({data.extractos.length})
              </h2>
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-ml-gray dark:border-ml-dark-border">
                      <th className="text-left py-2 px-2 font-semibold text-ml-text-soft dark:text-zinc-400">#</th>
                      <th className="text-left py-2 px-2 font-semibold text-ml-text-soft dark:text-zinc-400">Archivo</th>
                      <th className="text-right py-2 px-2 font-semibold text-ml-text-soft dark:text-zinc-400">Movs</th>
                      <th className="text-left py-2 px-2 font-semibold text-ml-text-soft dark:text-zinc-400">Borrado</th>
                      <th className="text-right py-2 px-2"></th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.extractos.map(e => {
                      const key = `extracto-${e.id}`
                      const busy = actionId === key
                      return (
                        <tr key={e.id} className="border-b border-ml-gray/40 dark:border-ml-dark-border/40">
                          <td className="py-2 px-2 dark:text-zinc-300">{e.id}</td>
                          <td className="py-2 px-2 dark:text-zinc-200 max-w-xs truncate">{e.nombre}</td>
                          <td className="py-2 px-2 text-right monto dark:text-ml-green">{e.movimientos}</td>
                          <td className="py-2 px-2 text-xs text-ml-text-soft dark:text-zinc-500">{fmtFecha(e.deleted_at)}</td>
                          <td className="py-2 px-2 text-right whitespace-nowrap">
                            <button
                              onClick={() => restaurar('extracto', e.id)}
                              disabled={busy}
                              className="btn-secondary text-xs mr-1 disabled:opacity-50"
                            >
                              {busy ? '...' : 'Restaurar'}
                            </button>
                            <button
                              onClick={() => purgar('extracto', e.id, e.nombre || `#${e.id}`)}
                              disabled={busy}
                              className="text-xs px-3 py-1.5 rounded-lg bg-red-50 text-red-700 border border-red-200
                                         hover:bg-red-100 disabled:opacity-50
                                         dark:bg-red-900/20 dark:text-red-400 dark:border-red-900"
                            >
                              Purgar
                            </button>
                          </td>
                        </tr>
                      )
                    })}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* Planillas borradas */}
          {data.planillas.length > 0 && (
            <div className="card">
              <h2 className="text-sm font-bold uppercase tracking-wide text-ml-text-soft dark:text-zinc-400 mb-3">
                Planillas ({data.planillas.length})
              </h2>
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-ml-gray dark:border-ml-dark-border">
                      <th className="text-left py-2 px-2 font-semibold text-ml-text-soft dark:text-zinc-400">#</th>
                      <th className="text-left py-2 px-2 font-semibold text-ml-text-soft dark:text-zinc-400">Cliente</th>
                      <th className="text-left py-2 px-2 font-semibold text-ml-text-soft dark:text-zinc-400">Archivo</th>
                      <th className="text-right py-2 px-2 font-semibold text-ml-text-soft dark:text-zinc-400">Filas</th>
                      <th className="text-left py-2 px-2 font-semibold text-ml-text-soft dark:text-zinc-400">Borrado</th>
                      <th className="text-right py-2 px-2"></th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.planillas.map(p => {
                      const key = `planilla-${p.id}`
                      const busy = actionId === key
                      return (
                        <tr key={p.id} className="border-b border-ml-gray/40 dark:border-ml-dark-border/40">
                          <td className="py-2 px-2 dark:text-zinc-300">{p.id}</td>
                          <td className="py-2 px-2 dark:text-zinc-200">{p.cliente_nombre || '-'}</td>
                          <td className="py-2 px-2 dark:text-zinc-200 max-w-xs truncate">{p.nombre_archivo}</td>
                          <td className="py-2 px-2 text-right monto dark:text-ml-green">{p.filas}</td>
                          <td className="py-2 px-2 text-xs text-ml-text-soft dark:text-zinc-500">{fmtFecha(p.deleted_at)}</td>
                          <td className="py-2 px-2 text-right whitespace-nowrap">
                            <button
                              onClick={() => restaurar('planilla', p.id)}
                              disabled={busy}
                              className="btn-secondary text-xs mr-1 disabled:opacity-50"
                            >
                              {busy ? '...' : 'Restaurar'}
                            </button>
                            <button
                              onClick={() => purgar('planilla', p.id, p.nombre_archivo || `#${p.id}`)}
                              disabled={busy}
                              className="text-xs px-3 py-1.5 rounded-lg bg-red-50 text-red-700 border border-red-200
                                         hover:bg-red-100 disabled:opacity-50
                                         dark:bg-red-900/20 dark:text-red-400 dark:border-red-900"
                            >
                              Purgar
                            </button>
                          </td>
                        </tr>
                      )
                    })}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
