import React, { useEffect, useState } from 'react'
import { apiClient } from '@/services/api'
import { AuditoriaLog } from '@/types'

export const Auditoria: React.FC = () => {
  const [items, setItems] = useState<AuditoriaLog[]>([])
  const [loading, setLoading] = useState(true)
  const [tabla, setTabla] = useState('')
  const [accion, setAccion] = useState('')

  const load = async () => {
    setLoading(true)
    try {
      const res = await apiClient.getAuditoria({
        tabla: tabla || undefined,
        accion: accion || undefined,
        limit: 200
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

  const accionColor = (a: string) => {
    if (a === 'INSERT') return 'bg-green-100 text-green-700'
    if (a === 'UPDATE') return 'bg-blue-100 text-blue-700'
    if (a === 'DELETE') return 'bg-red-100 text-red-700'
    if (a === 'CONCILIAR') return 'bg-purple-100 text-purple-700'
    return 'bg-gray-100 text-gray-700'
  }

  return (
    <div className="p-8 max-w-6xl mx-auto">
      <h1 className="text-2xl font-bold text-gray-900 mb-2">Auditoría</h1>
      <p className="text-gray-600 mb-6">Registro completo de operaciones del sistema</p>

      <div className="card mb-6 flex gap-3 items-end">
        <div className="flex-1">
          <label className="label">Tabla</label>
          <select
            className="input-field"
            value={tabla}
            onChange={(e) => setTabla(e.target.value)}
          >
            <option value="">Todas</option>
            <option value="users">Usuarios</option>
            <option value="planillas">Planillas</option>
            <option value="extractos_bancarios">Extractos</option>
          </select>
        </div>
        <div className="flex-1">
          <label className="label">Acción</label>
          <select
            className="input-field"
            value={accion}
            onChange={(e) => setAccion(e.target.value)}
          >
            <option value="">Todas</option>
            <option value="INSERT">Crear</option>
            <option value="UPDATE">Modificar</option>
            <option value="DELETE">Borrar</option>
            <option value="CONCILIAR">Conciliar</option>
          </select>
        </div>
        <button onClick={load} className="btn-primary">
          Filtrar
        </button>
      </div>

      <div className="card overflow-hidden p-0">
        {loading ? (
          <div className="p-8 text-center text-gray-500">Cargando...</div>
        ) : items.length === 0 ? (
          <div className="p-8 text-center text-gray-500">Sin registros</div>
        ) : (
          <table className="w-full">
            <thead className="bg-gray-50 border-b">
              <tr>
                <th className="px-4 py-3 text-left text-xs font-semibold text-gray-600 uppercase">Fecha</th>
                <th className="px-4 py-3 text-left text-xs font-semibold text-gray-600 uppercase">Usuario</th>
                <th className="px-4 py-3 text-left text-xs font-semibold text-gray-600 uppercase">Acción</th>
                <th className="px-4 py-3 text-left text-xs font-semibold text-gray-600 uppercase">Tabla</th>
                <th className="px-4 py-3 text-left text-xs font-semibold text-gray-600 uppercase">Registro</th>
                <th className="px-4 py-3 text-left text-xs font-semibold text-gray-600 uppercase">Detalles</th>
              </tr>
            </thead>
            <tbody className="divide-y">
              {items.map((it) => (
                <tr key={it.id} className="hover:bg-gray-50">
                  <td className="px-4 py-3 text-sm text-gray-600 whitespace-nowrap">
                    {new Date(it.timestamp).toLocaleString('es-AR')}
                  </td>
                  <td className="px-4 py-3 text-sm text-gray-900">
                    {it.usuario_nombre || `#${it.usuario_id}`}
                  </td>
                  <td className="px-4 py-3 text-sm">
                    <span className={`px-2 py-1 rounded text-xs font-semibold ${accionColor(it.accion)}`}>
                      {it.accion}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-sm text-gray-600">{it.tabla}</td>
                  <td className="px-4 py-3 text-sm text-gray-600">#{it.registro_id}</td>
                  <td className="px-4 py-3 text-xs text-gray-500 font-mono max-w-xs truncate">
                    {it.cambios ? JSON.stringify(it.cambios) : '—'}
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
