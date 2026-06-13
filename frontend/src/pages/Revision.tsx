import React, { useEffect, useState } from 'react'
import { apiClient } from '@/services/api'
import { useAuthStore } from '@/store/auth'
import { useOrgStore } from '@/store/org'

interface FilaRevision {
  id: number
  monto: number
  cuit?: string
  titular?: string
  referencia?: string
  comentario_revision?: string
}

interface PlanillaConRevision {
  planilla_id: number
  nombre_archivo: string
  cliente_nombre: string
  total_en_revision: number
  filas: FilaRevision[]
}

const ACCIONES = [
  { value: 'aprobar',      label: 'Aprobar — marcar ok',              cls: 'bg-green-600 text-white hover:bg-green-700' },
  { value: 'rechazar',     label: 'Rechazar — marcar no está',         cls: 'bg-red-500 text-white hover:bg-red-600' },
  { value: 'pago_parcial', label: 'Pago parcial',                      cls: 'bg-amber-500 text-white hover:bg-amber-600' },
  { value: 'diferencia',   label: 'Conciliado con diferencia',         cls: 'bg-blue-500 text-white hover:bg-blue-600' },
  { value: 'vencido',      label: 'Marcar como vencido',               cls: 'bg-gray-500 text-white hover:bg-gray-600' },
]

const fmt = (n: number) =>
  new Intl.NumberFormat('es-AR', { style: 'currency', currency: 'ARS', minimumFractionDigits: 0 }).format(n)

export const Revision: React.FC = () => {
  const { user } = useAuthStore()
  const { activeOrgId } = useOrgStore()
  const [loading, setLoading] = useState(true)
  const [planillas, setPlanillas] = useState<PlanillaConRevision[]>([])
  const [resolving, setResolving] = useState<number | null>(null)
  const [comentarios, setComentarios] = useState<Record<number, string>>({})
  const [msg, setMsg] = useState('')
  const [expandedPlanilla, setExpandedPlanilla] = useState<number | null>(null)

  const load = async () => {
    setLoading(true)
    setMsg('')
    try {
      // Buscar planillas con filas EN_REVISION
      const oid = activeOrgId || user?.organizacion_id || 1
      const histRes = await apiClient.client.get('/historial/planillas', {
        params: { limit: 100, org_id: oid }
      })
      const planillaIds: number[] = histRes.data.items.map((p: { id: number }) => p.id)

      // Para cada planilla verificar si tiene EN_REVISION
      const conRevision: PlanillaConRevision[] = []
      await Promise.all(planillaIds.map(async (id) => {
        try {
          const res = await apiClient.client.get(`/planillas/${id}/revision`)
          if (res.data.total_en_revision > 0) {
            const histItem = histRes.data.items.find((p: { id: number; nombre_archivo?: string; cliente_nombre?: string }) => p.id === id)
            conRevision.push({
              planilla_id: id,
              nombre_archivo: histItem?.nombre_archivo || `Planilla #${id}`,
              cliente_nombre: histItem?.cliente_nombre || '—',
              total_en_revision: res.data.total_en_revision,
              filas: res.data.filas
            })
          }
        } catch { /* org sin cierre de periodo — endpoint devuelve 400 */ }
      }))

      setPlanillas(conRevision.sort((a, b) => b.total_en_revision - a.total_en_revision))
      if (conRevision.length > 0) setExpandedPlanilla(conRevision[0].planilla_id)
    } catch { setPlanillas([]) }
    finally { setLoading(false) }
  }

  useEffect(() => { load() }, [activeOrgId])

  const handleResolver = async (planillaId: number, rowId: number, accion: string) => {
    setResolving(rowId)
    setMsg('')
    try {
      const comentario = comentarios[rowId] || ''
      await apiClient.client.post(`/planillas/${planillaId}/revision/${rowId}/resolver`, {
        accion,
        comentario
      })
      setMsg(`✓ Fila resuelta como "${accion}"`)
      // Actualizar lista removiendo la fila resuelta
      setPlanillas(prev => prev.map(p => {
        if (p.planilla_id !== planillaId) return p
        const nuevasFilas = p.filas.filter(f => f.id !== rowId)
        return { ...p, filas: nuevasFilas, total_en_revision: nuevasFilas.length }
      }).filter(p => p.total_en_revision > 0))
    } catch (err: any) {
      setMsg(err.response?.data?.detail || 'Error al resolver')
    } finally { setResolving(null) }
  }

  const totalGlobal = planillas.reduce((s, p) => s + p.total_en_revision, 0)

  return (
    <div className="p-4 md:p-6 max-w-4xl mx-auto">
      {/* Header */}
      <div className="flex items-start justify-between mb-5 flex-wrap gap-3">
        <div>
          <h1 className="text-xl font-bold dark:text-white flex items-center gap-2">
            Cola de Revisión
            {totalGlobal > 0 && (
              <span className="badge badge-warn text-sm px-2.5 py-1">{totalGlobal} pendientes</span>
            )}
          </h1>
          <p className="text-sm text-gray-400 dark:text-zinc-500 mt-0.5">
            Filas que necesitan revisión manual antes de cerrar el período
          </p>
        </div>
        <button onClick={load} className="btn-secondary text-sm">
          Actualizar
        </button>
      </div>

      {msg && (
        <div className={`mb-4 px-3 py-2 rounded-lg text-sm ${msg.startsWith('✓') ? 'bg-green-50 text-green-700 dark:bg-green-900/20 dark:text-green-400' : 'bg-red-50 text-red-600 dark:bg-red-900/20 dark:text-red-400'}`}>
          {msg}
        </div>
      )}

      {loading ? (
        <div className="card p-10 text-center text-gray-400">Buscando filas en revisión...</div>
      ) : planillas.length === 0 ? (
        <div className="card p-10 text-center">
          <p className="text-3xl mb-3">✅</p>
          <p className="font-semibold dark:text-white">Sin pendientes de revisión</p>
          <p className="text-sm text-gray-400 dark:text-zinc-500 mt-1">
            Todas las filas están resueltas. El período puede cerrarse.
          </p>
        </div>
      ) : (
        <div className="space-y-3">
          {planillas.map(p => (
            <div key={p.planilla_id} className="card p-0 overflow-hidden">
              {/* Header planilla */}
              <button
                className="w-full flex items-center gap-3 px-4 py-3.5 hover:bg-ml-gray-bg dark:hover:bg-ml-dark-hover transition-colors text-left"
                onClick={() => setExpandedPlanilla(ep => ep === p.planilla_id ? null : p.planilla_id)}
              >
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 flex-wrap">
                    <p className="font-semibold dark:text-white">{p.cliente_nombre}</p>
                    <span className="badge badge-warn">{p.total_en_revision} en revisión</span>
                  </div>
                  <p className="text-xs text-gray-400 dark:text-zinc-500 mt-0.5 truncate">
                    {p.nombre_archivo}
                  </p>
                </div>
                <span className="text-gray-400 text-sm">
                  {expandedPlanilla === p.planilla_id ? '▲' : '▼'}
                </span>
              </button>

              {/* Filas en revisión */}
              {expandedPlanilla === p.planilla_id && (
                <div className="border-t border-ml-gray dark:border-ml-dark-border divide-y divide-ml-gray dark:divide-ml-dark-border">
                  {p.filas.map(fila => (
                    <div key={fila.id} className="px-4 py-4">
                      {/* Datos de la fila */}
                      <div className="flex items-start gap-3 mb-3">
                        <div className="flex-1 min-w-0">
                          <p className="font-bold text-lg font-mono text-ml-text dark:text-white">
                            {fmt(fila.monto)}
                          </p>
                          <div className="flex flex-wrap gap-x-4 gap-y-0.5 mt-1">
                            {fila.cuit && (
                              <span className="text-xs text-gray-500 dark:text-zinc-400 font-mono">
                                CUIT: {fila.cuit}
                              </span>
                            )}
                            {fila.titular && (
                              <span className="text-xs text-gray-500 dark:text-zinc-400">
                                {fila.titular}
                              </span>
                            )}
                            {fila.referencia && (
                              <span className="text-xs text-gray-500 dark:text-zinc-400">
                                Ref: {fila.referencia}
                              </span>
                            )}
                            {!fila.cuit && !fila.titular && !fila.referencia && (
                              <span className="text-xs text-amber-500">Sin datos de identidad</span>
                            )}
                          </div>
                        </div>
                      </div>

                      {/* Comentario */}
                      <div className="mb-3">
                        <input
                          className="input-field text-xs"
                          placeholder="Comentario (opcional — ej: cliente confirmó transferencia)"
                          value={comentarios[fila.id] || ''}
                          onChange={e => setComentarios(prev => ({ ...prev, [fila.id]: e.target.value }))}
                        />
                      </div>

                      {/* Acciones */}
                      <div className="flex flex-wrap gap-2">
                        {ACCIONES.map(accion => (
                          <button
                            key={accion.value}
                            disabled={resolving === fila.id}
                            onClick={() => handleResolver(p.planilla_id, fila.id, accion.value)}
                            className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition-all disabled:opacity-40 ${accion.cls}`}
                          >
                            {resolving === fila.id ? '⏳' : accion.label}
                          </button>
                        ))}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          ))}

          {/* Aviso cierre */}
          <div className="card bg-amber-50 dark:bg-amber-900/10 border-amber-200 dark:border-amber-900/30 p-4">
            <p className="text-sm text-amber-700 dark:text-amber-400 font-medium">
              Necesitas resolver todas las filas antes de cerrar el período.
            </p>
            <p className="text-xs text-amber-600 dark:text-amber-500 mt-1">
              Cuando la lista quede vacía, podés ir a Liquidaciones y cerrar el período.
            </p>
          </div>
        </div>
      )}
    </div>
  )
}
