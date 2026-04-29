import React, { useEffect, useState } from 'react'
import { apiClient } from '@/services/api'
import { PlanillaHistorialItem } from '@/types'
import { Input } from '@/components/Input'

export const Historial: React.FC = () => {
  const [items, setItems] = useState<PlanillaHistorialItem[]>([])
  const [loading, setLoading] = useState(true)
  const [filter, setFilter] = useState('')

  const load = async () => {
    setLoading(true)
    try {
      const res = await apiClient.getHistorialPlanillas({
        cliente: filter || undefined,
        limit: 100
      })
      setItems(res.items)
    } catch {
      setItems([])
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    load()
  }, [])

  const handleFilter = (e: React.FormEvent) => {
    e.preventDefault()
    load()
  }

  return (
    <div className="p-8 max-w-6xl mx-auto">
      <h1 className="text-2xl font-bold text-gray-900 mb-2">Historial de conciliaciones</h1>
      <p className="text-gray-600 mb-6">Todas las planillas reconciliadas</p>

      <form onSubmit={handleFilter} className="card mb-6 flex gap-3 items-end">
        <div className="flex-1">
          <Input
            label="Buscar por cliente"
            placeholder="Ej: Green, Tucu..."
            value={filter}
            onChange={(e) => setFilter(e.target.value)}
          />
        </div>
        <button type="submit" className="btn-primary">
          Filtrar
        </button>
      </form>

      <div className="card overflow-hidden p-0">
        {loading ? (
          <div className="p-8 text-center text-gray-500">Cargando...</div>
        ) : items.length === 0 ? (
          <div className="p-8 text-center text-gray-500">
            No hay reconciliaciones registradas
          </div>
        ) : (
          <table className="w-full">
            <thead className="bg-gray-50 border-b">
              <tr>
                <th className="px-4 py-3 text-left text-xs font-semibold text-gray-600 uppercase">Cliente</th>
                <th className="px-4 py-3 text-left text-xs font-semibold text-gray-600 uppercase">Archivo</th>
                <th className="px-4 py-3 text-left text-xs font-semibold text-gray-600 uppercase">Fecha</th>
                <th className="px-4 py-3 text-left text-xs font-semibold text-gray-600 uppercase">Usuario</th>
                <th className="px-4 py-3 text-center text-xs font-semibold text-green-700 uppercase">OK</th>
                <th className="px-4 py-3 text-center text-xs font-semibold text-red-700 uppercase">No está</th>
                <th className="px-4 py-3 text-center text-xs font-semibold text-yellow-700 uppercase">Dup.</th>
                <th className="px-4 py-3 text-center text-xs font-semibold text-blue-700 uppercase">Datos</th>
              </tr>
            </thead>
            <tbody className="divide-y">
              {items.map((it) => (
                <tr key={it.id} className="hover:bg-gray-50">
                  <td className="px-4 py-3 text-sm font-medium text-gray-900">
                    {it.cliente_nombre}
                  </td>
                  <td className="px-4 py-3 text-sm text-gray-600 truncate max-w-xs">
                    {it.nombre_archivo}
                  </td>
                  <td className="px-4 py-3 text-sm text-gray-600">
                    {new Date(it.fecha_carga).toLocaleString('es-AR')}
                  </td>
                  <td className="px-4 py-3 text-sm text-gray-600">{it.usuario_nombre}</td>
                  <td className="px-4 py-3 text-sm text-center font-semibold text-green-600">
                    {it.acreditadas}
                  </td>
                  <td className="px-4 py-3 text-sm text-center font-semibold text-red-600">
                    {it.no_encontradas}
                  </td>
                  <td className="px-4 py-3 text-sm text-center font-semibold text-yellow-600">
                    {it.duplicadas}
                  </td>
                  <td className="px-4 py-3 text-sm text-center font-semibold text-blue-600">
                    {it.sin_datos}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  )
}
