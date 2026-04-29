import React, { useEffect, useState } from 'react'
import { apiClient } from '@/services/api'
import { User, UserRole } from '@/types'

export const Usuarios: React.FC = () => {
  const [users, setUsers] = useState<User[]>([])
  const [loading, setLoading] = useState(true)
  const [savingId, setSavingId] = useState<number | null>(null)

  const load = async () => {
    setLoading(true)
    try {
      const res = await apiClient.getUsers({ limit: 200 })
      setUsers(res.items)
    } catch {
      setUsers([])
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    load()
  }, [])

  const handleRoleChange = async (user: User, role: UserRole) => {
    setSavingId(user.id)
    try {
      const updated = await apiClient.updateUser(user.id, { role })
      setUsers((prev) => prev.map((u) => (u.id === user.id ? updated : u)))
    } finally {
      setSavingId(null)
    }
  }

  const handleActiveToggle = async (user: User) => {
    setSavingId(user.id)
    try {
      const updated = await apiClient.updateUser(user.id, {
        is_active: !user.is_active
      })
      setUsers((prev) => prev.map((u) => (u.id === user.id ? updated : u)))
    } finally {
      setSavingId(null)
    }
  }

  return (
    <div className="p-8 max-w-6xl mx-auto">
      <h1 className="text-2xl font-bold text-gray-900 mb-2">Gestión de usuarios</h1>
      <p className="text-gray-600 mb-6">
        Administra roles y estado de los usuarios del sistema
      </p>

      <div className="card overflow-hidden p-0">
        {loading ? (
          <div className="p-8 text-center text-gray-500">Cargando...</div>
        ) : users.length === 0 ? (
          <div className="p-8 text-center text-gray-500">No hay usuarios</div>
        ) : (
          <table className="w-full">
            <thead className="bg-gray-50 border-b">
              <tr>
                <th className="px-4 py-3 text-left text-xs font-semibold text-gray-600 uppercase">Nombre</th>
                <th className="px-4 py-3 text-left text-xs font-semibold text-gray-600 uppercase">Email</th>
                <th className="px-4 py-3 text-left text-xs font-semibold text-gray-600 uppercase">Rol</th>
                <th className="px-4 py-3 text-left text-xs font-semibold text-gray-600 uppercase">Estado</th>
                <th className="px-4 py-3 text-left text-xs font-semibold text-gray-600 uppercase">Creado</th>
              </tr>
            </thead>
            <tbody className="divide-y">
              {users.map((u) => (
                <tr key={u.id} className="hover:bg-gray-50">
                  <td className="px-4 py-3 text-sm font-medium text-gray-900">
                    {u.full_name}
                  </td>
                  <td className="px-4 py-3 text-sm text-gray-600">{u.email}</td>
                  <td className="px-4 py-3 text-sm">
                    <select
                      className="input-field !py-1 !text-sm"
                      value={u.role}
                      disabled={savingId === u.id}
                      onChange={(e) =>
                        handleRoleChange(u, e.target.value as UserRole)
                      }
                    >
                      <option value={UserRole.ADMIN}>Admin</option>
                      <option value={UserRole.OPERADOR}>Operador</option>
                      <option value={UserRole.REVISOR}>Revisor</option>
                      <option value={UserRole.AUDITOR}>Auditor</option>
                    </select>
                  </td>
                  <td className="px-4 py-3 text-sm">
                    <button
                      onClick={() => handleActiveToggle(u)}
                      disabled={savingId === u.id}
                      className={`px-3 py-1 rounded text-xs font-semibold ${
                        u.is_active
                          ? 'bg-green-100 text-green-700 hover:bg-green-200'
                          : 'bg-red-100 text-red-700 hover:bg-red-200'
                      }`}
                    >
                      {u.is_active ? 'Activo' : 'Inactivo'}
                    </button>
                  </td>
                  <td className="px-4 py-3 text-sm text-gray-600">
                    {new Date(u.created_at).toLocaleDateString('es-AR')}
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
