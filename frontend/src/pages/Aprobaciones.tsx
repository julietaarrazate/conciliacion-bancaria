import React, { useEffect, useState, useCallback } from 'react'
import { apiClient } from '@/services/api'
import { PendingRequest } from '@/types'
import { toast } from '@/store/toast'

export const Aprobaciones: React.FC = () => {
  const [items, setItems] = useState<PendingRequest[]>([])
  const [loading, setLoading] = useState(true)
  const [deciding, setDeciding] = useState<number | null>(null)

  const cargar = useCallback(async () => {
    try {
      const data = await apiClient.getPendingApprovals()
      setItems(data)
    } catch {
      /* noop — se reintenta en el siguiente tick */
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    cargar()
    const t = window.setInterval(cargar, 4000)
    return () => window.clearInterval(t)
  }, [cargar])

  const decidir = async (id: number, approve: boolean) => {
    setDeciding(id)
    try {
      await apiClient.decideLoginApproval(id, approve)
      setItems(prev => prev.filter(i => i.id !== id))
      toast.success(approve ? 'Ingreso aprobado' : 'Ingreso rechazado')
    } catch (e: any) {
      toast.error(e?.response?.data?.detail || 'No se pudo procesar la solicitud')
      cargar()
    } finally {
      setDeciding(null)
    }
  }

  const hora = (iso: string) => {
    try { return new Date(iso).toLocaleTimeString('es-AR', { hour: '2-digit', minute: '2-digit' }) }
    catch { return '' }
  }

  return (
    <div className="max-w-3xl mx-auto">
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-ml-text dark:text-white">Aprobaciones de ingreso</h1>
        <p className="text-sm text-ml-text-soft dark:text-zinc-400 mt-1">
          Solicitudes de contadores esperando tu autorización. La lista se actualiza sola.
        </p>
      </div>

      {loading ? (
        <p className="text-sm text-ml-text-soft dark:text-zinc-500">Cargando…</p>
      ) : items.length === 0 ? (
        <div className="bg-white dark:bg-ml-dark-surface rounded-2xl p-10 text-center border border-gray-100 dark:border-ml-dark-border">
          <div className="text-4xl mb-3">✅</div>
          <p className="text-ml-text dark:text-white font-medium">No hay solicitudes pendientes</p>
          <p className="text-sm text-ml-text-soft dark:text-zinc-500 mt-1">
            Cuando un contador intente ingresar, aparecerá acá.
          </p>
        </div>
      ) : (
        <div className="space-y-3">
          {items.map(it => (
            <div key={it.id} className="bg-white dark:bg-ml-dark-surface rounded-xl p-4 border border-gray-100 dark:border-ml-dark-border flex items-center justify-between gap-4">
              <div className="min-w-0">
                <p className="font-medium text-ml-text dark:text-white truncate">{it.user_name}</p>
                <p className="text-sm text-ml-text-soft dark:text-zinc-400 truncate">{it.user_email}</p>
                <p className="text-xs text-ml-text-soft dark:text-zinc-500 mt-0.5">
                  {hora(it.created_at)}{it.ip ? ` · ${it.ip}` : ''}
                </p>
              </div>
              <div className="flex gap-2 shrink-0">
                <button
                  onClick={() => decidir(it.id, false)}
                  disabled={deciding === it.id}
                  className="px-3 py-2 text-sm rounded-lg border border-red-200 text-red-600 hover:bg-red-50 dark:border-red-800/50 dark:text-red-400 dark:hover:bg-red-950/30 transition-colors disabled:opacity-50"
                >
                  Rechazar
                </button>
                <button
                  onClick={() => decidir(it.id, true)}
                  disabled={deciding === it.id}
                  className="px-4 py-2 text-sm rounded-lg bg-ml-green text-white hover:opacity-90 transition-opacity disabled:opacity-50"
                >
                  Aprobar
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

export default Aprobaciones
