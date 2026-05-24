import React, { useEffect, useState } from 'react'
import { apiClient } from '@/services/api'
import { User, UserRole } from '@/types'
import { toast } from '@/store/toast'

export const Usuarios: React.FC = () => {
  const [users, setUsers] = useState<User[]>([])
  const [loading, setLoading] = useState(true)
  const [savingId, setSavingId] = useState<number | null>(null)
  const [deletingId, setDeletingId] = useState<number | null>(null)
  const [showForm, setShowForm] = useState(false)
  const [formError, setFormError] = useState('')
  const [formLoading, setFormLoading] = useState(false)
  const [newUser, setNewUser] = useState({ email: '', full_name: '', password: '', role: UserRole.OPERADOR })
  const [showPass, setShowPass] = useState(false)

  const load = async () => {
    setLoading(true)
    try {
      const res = await apiClient.getUsers({ limit: 200 })
      setUsers(res.items)
    } catch { setUsers([]) }
    finally { setLoading(false) }
  }

  useEffect(() => { load() }, [])

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!newUser.email || !newUser.full_name || !newUser.password) {
      setFormError('Completá todos los campos')
      return
    }
    if (newUser.password.length < 6) {
      setFormError('La contraseña debe tener al menos 6 caracteres')
      return
    }
    setFormLoading(true)
    setFormError('')
    try {
      await apiClient.client.post('/auth/register', {
        email: newUser.email,
        full_name: newUser.full_name,
        password: newUser.password,
        role: newUser.role
      })
      // Actualizar rol si no es OPERADOR (register crea como OPERADOR por defecto)
      if (newUser.role !== UserRole.OPERADOR) {
        const created = (await apiClient.getUsers({ limit: 200 })).items.find(u => u.email === newUser.email)
        if (created) await apiClient.updateUser(created.id, { role: newUser.role })
      }
      setNewUser({ email: '', full_name: '', password: '', role: UserRole.OPERADOR })
      setShowForm(false)
      await load()
    } catch (err: any) {
      setFormError(err.response?.data?.detail || 'Error al crear usuario')
    } finally {
      setFormLoading(false)
    }
  }

  const handleRoleChange = async (user: User, role: UserRole) => {
    setSavingId(user.id)
    try {
      const updated = await apiClient.updateUser(user.id, { role })
      setUsers(prev => prev.map(u => u.id === user.id ? updated : u))
    } finally { setSavingId(null) }
  }

  const handleActiveToggle = async (user: User) => {
    setSavingId(user.id)
    try {
      const updated = await apiClient.updateUser(user.id, { is_active: !user.is_active })
      setUsers(prev => prev.map(u => u.id === user.id ? updated : u))
    } finally { setSavingId(null) }
  }

  const handleDelete = async (user: User) => {
    if (!confirm(`¿Eliminar permanentemente a ${user.full_name} (${user.email})?`)) return
    setDeletingId(user.id)
    try {
      await apiClient.deleteUser(user.id)
      setUsers(prev => prev.filter(u => u.id !== user.id))
    } catch (err: any) {
      toast.error(err.response?.data?.detail || 'Error al eliminar')
    } finally { setDeletingId(null) }
  }

  return (
    <div className="p-4 md:p-8 max-w-5xl mx-auto">
      <div className="flex items-start justify-between mb-4 flex-wrap gap-3">
        <div>
          <h1 className="text-xl md:text-2xl font-bold dark:text-white">Gestión de usuarios</h1>
          <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">Administradora: Julieta Arrazate</p>
        </div>
        <button onClick={() => setShowForm(s => !s)} className="btn-yellow">
          {showForm ? '✕ Cancelar' : '+ Nuevo usuario'}
        </button>
      </div>

      {/* Formulario nuevo usuario */}
      {showForm && (
        <div className="card mb-6 border-l-4 border-ml-blue">
          <h2 className="text-base font-semibold dark:text-white mb-4">Crear nuevo usuario</h2>
          {formError && <div className="mb-3 p-2.5 bg-red-50 dark:bg-red-900/20 text-red-700 dark:text-red-300 rounded text-sm">{formError}</div>}
          <form onSubmit={handleCreate} className="grid grid-cols-1 md:grid-cols-2 gap-3">
            <div>
              <label className="label">Nombre completo</label>
              <input className="input-field" placeholder="Ej: Ana García" value={newUser.full_name}
                onChange={e => setNewUser(p => ({ ...p, full_name: e.target.value }))} />
            </div>
            <div>
              <label className="label">Email</label>
              <input type="email" className="input-field" placeholder="ana@empresa.com" value={newUser.email}
                onChange={e => setNewUser(p => ({ ...p, email: e.target.value }))} />
            </div>
            <div>
              <label className="label">Contraseña</label>
              <div className="relative">
                <input type={showPass ? 'text' : 'password'} className="input-field pr-10"
                  placeholder="Mínimo 6 caracteres" value={newUser.password}
                  onChange={e => setNewUser(p => ({ ...p, password: e.target.value }))} />
                <button type="button" tabIndex={-1} onClick={() => setShowPass(s => !s)}
                  className="absolute right-2 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600">
                  {showPass ? '🙈' : '👁️'}
                </button>
              </div>
            </div>
            <div>
              <label className="label">Rol</label>
              <select className="input-field" value={newUser.role}
                onChange={e => setNewUser(p => ({ ...p, role: e.target.value as UserRole }))}>
                <option value={UserRole.ADMIN}>Admin — acceso total</option>
                <option value={UserRole.OPERADOR}>Operador — puede conciliar</option>
                <option value={UserRole.REVISOR}>Revisor — solo lectura</option>
                <option value={UserRole.AUDITOR}>Auditor — solo auditoría</option>
              </select>
            </div>
            <div className="md:col-span-2 flex justify-end gap-3">
              <button type="button" onClick={() => setShowForm(false)} className="btn-secondary">Cancelar</button>
              <button type="submit" disabled={formLoading} className="btn-yellow">
                {formLoading ? 'Creando...' : 'Crear usuario'}
              </button>
            </div>
          </form>
        </div>
      )}

      {/* Lista de usuarios */}
      <div className="card overflow-hidden p-0">
        {loading ? (
          <div className="p-8 text-center text-gray-400">Cargando...</div>
        ) : users.length === 0 ? (
          <div className="p-8 text-center text-gray-400">No hay usuarios</div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm min-w-[500px]">
              <thead className="bg-gray-50 dark:bg-slate-900 border-b dark:border-slate-700">
                <tr>
                  {['Nombre', 'Email', 'Rol', 'Estado', 'Creado', ''].map(h => (
                    <th key={h} className="px-4 py-2.5 text-left text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y dark:divide-slate-700">
                {users.map(u => (
                  <tr key={u.id} className="hover:bg-gray-50 dark:hover:bg-slate-700/40">
                    <td className="px-4 py-2.5 font-medium dark:text-white">
                      <span>{u.full_name}</span>
                      {u.is_superadmin && (
                        <span className="ml-2 text-[10px] px-1.5 py-0.5 rounded-full bg-ml-green/20 text-ml-green dark:bg-ml-green/10 font-mono border border-ml-green/30">
                          superadmin
                        </span>
                      )}
                    </td>
                    <td className="px-4 py-2.5 text-gray-500 dark:text-gray-400 text-xs">{u.email}</td>
                    <td className="px-4 py-2.5">
                      {u.is_superadmin ? (
                        <span className="text-xs text-gray-400 dark:text-gray-500 italic">—</span>
                      ) : (
                        <select className="input-field !py-1 !text-xs max-w-[120px]" value={u.role}
                          disabled={savingId === u.id}
                          onChange={e => handleRoleChange(u, e.target.value as UserRole)}>
                          <option value={UserRole.ADMIN}>Admin</option>
                          <option value={UserRole.OPERADOR}>Operador</option>
                          <option value={UserRole.REVISOR}>Revisor</option>
                          <option value={UserRole.AUDITOR}>Auditor</option>
                        </select>
                      )}
                    </td>
                    <td className="px-4 py-2.5">
                      <button onClick={() => handleActiveToggle(u)} disabled={savingId === u.id || u.is_superadmin}
                        className={`px-2.5 py-1 rounded text-xs font-semibold transition-colors disabled:opacity-50 ${u.is_active ? 'bg-green-100 text-green-700 hover:bg-green-200 dark:bg-green-900/40 dark:text-green-300' : 'bg-red-100 text-red-700 hover:bg-red-200 dark:bg-red-900/40 dark:text-red-300'}`}>
                        {u.is_active ? 'Activo' : 'Inactivo'}
                      </button>
                    </td>
                    <td className="px-4 py-2.5 text-xs text-gray-400 dark:text-gray-500">
                      {new Date(u.created_at).toLocaleDateString('es-AR')}
                    </td>
                    <td className="px-4 py-2.5 text-center">
                      {!u.is_superadmin && (
                        <button
                          onClick={() => handleDelete(u)}
                          disabled={deletingId === u.id}
                          className="text-gray-300 hover:text-red-500 dark:text-slate-600 dark:hover:text-red-400 transition-colors disabled:opacity-30 text-base"
                          title="Eliminar usuario"
                        >
                          {deletingId === u.id ? '⏳' : '🗑️'}
                        </button>
                      )}
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
