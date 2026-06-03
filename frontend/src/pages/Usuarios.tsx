import React, { useEffect, useState } from 'react'
import { apiClient } from '@/services/api'
import { User, UserRole } from '@/types'
import { toast } from '@/store/toast'
import { confirmDialog } from '@/store/confirm'
import { useAuthStore } from '@/store/auth'
import { useOrgStore } from '@/store/org'

export const Usuarios: React.FC = () => {
  const me = useAuthStore(s => s.user)
  const canDelete = useAuthStore(s => s.hasPermission('delete_records'))
  const { activeOrgId } = useOrgStore()
  const [users, setUsers] = useState<User[]>([])
  const [loading, setLoading] = useState(true)
  const [savingId, setSavingId] = useState<number | null>(null)
  const [deletingId, setDeletingId] = useState<number | null>(null)
  const [showForm, setShowForm] = useState(false)
  const [formError, setFormError] = useState('')
  const [formLoading, setFormLoading] = useState(false)
  const [newUser, setNewUser] = useState<{ email: string; full_name: string; password: string; role: UserRole; orgId: number | ''; allowedOrgIds: number[] }>({ email: '', full_name: '', password: '', role: UserRole.OPERADOR, orgId: '', allowedOrgIds: [] })
  const [showPass, setShowPass] = useState(false)
  const [orgs, setOrgs] = useState<{ id: number; nombre: string }[]>([])

  const load = async () => {
    setLoading(true)
    try {
      const params: { limit: number; org_id?: number } = { limit: 200 }
      if (activeOrgId) params.org_id = activeOrgId
      const res = await apiClient.getUsers(params)
      setUsers(res.items)
    } catch { setUsers([]) }
    finally { setLoading(false) }
  }

  useEffect(() => { load() }, [activeOrgId])
  useEffect(() => {
    if (me?.is_superadmin) {
      apiClient.listOrganizaciones().then(setOrgs).catch(() => setOrgs([]))
    }
  }, [me?.is_superadmin])

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
      // register crea como OPERADOR en la org por defecto; ajustamos rol, org y allowed_org_ids
      const needsPatch = newUser.role !== UserRole.OPERADOR || (!!me?.is_superadmin && (newUser.orgId !== '' || newUser.allowedOrgIds.length > 0))
      if (needsPatch) {
        const created = (await apiClient.getUsers({ limit: 200 })).items.find(u => u.email === newUser.email)
        if (created) {
          const patch: { role?: UserRole; organizacion_id?: number; allowed_org_ids?: number[] } = {}
          if (newUser.role !== UserRole.OPERADOR) patch.role = newUser.role
          if (me?.is_superadmin && newUser.orgId !== '') patch.organizacion_id = Number(newUser.orgId)
          if (me?.is_superadmin && newUser.allowedOrgIds.length > 0) patch.allowed_org_ids = newUser.allowedOrgIds
          await apiClient.updateUser(created.id, patch)
        }
      }
      setNewUser({ email: '', full_name: '', password: '', role: UserRole.OPERADOR, orgId: '', allowedOrgIds: [] })
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
    if (!await confirmDialog({ title: 'Eliminar usuario', message: `¿Eliminar permanentemente a ${user.full_name} (${user.email})?`, confirmLabel: 'Eliminar', danger: true })) return
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
          <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
            Administradora: Julieta Arrazate
            {activeOrgId && orgs.length > 0 && (
              <span className="ml-2 text-xs px-2 py-0.5 rounded-full bg-ml-blue/10 text-ml-blue border border-ml-blue/20">
                {orgs.find(o => o.id === activeOrgId)?.nombre ?? `Org #${activeOrgId}`}
              </span>
            )}
          </p>
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
                <option value={UserRole.CONTADOR}>Contador — opera sin borrar (aprobación)</option>
              </select>
            </div>
            {me?.is_superadmin && orgs.length > 0 && (
              <div>
                <label className="label">Organización principal</label>
                <select className="input-field" value={newUser.orgId}
                  onChange={e => setNewUser(p => ({ ...p, orgId: e.target.value === '' ? '' : Number(e.target.value) }))}>
                  <option value="">Por defecto (Organización A)</option>
                  {orgs.map(o => <option key={o.id} value={o.id}>{o.nombre}</option>)}
                </select>
                <p className="text-xs text-ml-text-soft dark:text-zinc-500 mt-1">
                  Para contadores de prueba, elegí la organización de prueba — no la real.
                </p>
              </div>
            )}
            {me?.is_superadmin && newUser.role === UserRole.CONTADOR && orgs.length > 0 && (
              <div className="md:col-span-2">
                <label className="label">Organizaciones permitidas (switch de org)</label>
                <div className="flex flex-wrap gap-2 mt-1">
                  {orgs.map(o => (
                    <label key={o.id} className="flex items-center gap-1.5 cursor-pointer text-sm">
                      <input
                        type="checkbox"
                        className="w-4 h-4 rounded accent-ml-blue"
                        checked={newUser.allowedOrgIds.includes(o.id)}
                        onChange={e => setNewUser(p => ({
                          ...p,
                          allowedOrgIds: e.target.checked
                            ? [...p.allowedOrgIds, o.id]
                            : p.allowedOrgIds.filter(id => id !== o.id)
                        }))}
                      />
                      <span className="dark:text-gray-300">{o.nombre}</span>
                    </label>
                  ))}
                </div>
                <p className="text-xs text-ml-text-soft dark:text-zinc-500 mt-1">
                  El contador podrá cambiar entre estas orgs desde el menú lateral.
                </p>
              </div>
            )}
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
                  {['Nombre', 'Email', 'Org', 'Rol', 'Estado', 'Creado', ''].map(h => (
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
                    <td className="px-4 py-2.5 text-xs text-gray-400 dark:text-gray-500">
                      {u.organizacion_id
                        ? (orgs.find(o => o.id === u.organizacion_id)?.nombre ?? `#${u.organizacion_id}`)
                        : <span className="italic">—</span>}
                    </td>
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
                          <option value={UserRole.CONTADOR}>Contador</option>
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
                      {canDelete && !u.is_superadmin && (
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
