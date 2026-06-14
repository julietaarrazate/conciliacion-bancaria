import React, { useEffect, useState } from 'react'
import { apiClient } from '@/services/api'
import { useAuthStore } from '@/store/auth'
import { useOrgStore } from '@/store/org'

interface Org {
  id: number
  nombre: string
  plan: string
  activo: boolean
  configuracion: Record<string, any>
}

const CONFIG_DEFAULT = {
  match_rules: ['monto_cuit'],
  tolerancia_monto: 0.01,
  dias_tolerancia_fecha: 0,
  estados_habilitados: ['pendiente', 'ok', 'no está', 'duplicado', 'faltan datos'],
  requiere_cierre_periodo: false,
  notificaciones_whatsapp: false,
  exportar_formato_contador: 'excel_actual'
}

export const Organizaciones: React.FC = () => {
  const { user } = useAuthStore()
  const { activeOrgId, setActiveOrg, clearActiveOrg } = useOrgStore()
  const [orgs, setOrgs] = useState<Org[]>([])
  const [loading, setLoading] = useState(true)
  const [showForm, setShowForm] = useState(false)
  const [editingOrg, setEditingOrg] = useState<Org | null>(null)
  const [saving, setSaving] = useState(false)
  const [msg, setMsg] = useState('')
  const [showUserForm, setShowUserForm] = useState<number | null>(null)
  const [userForm, setUserForm] = useState({ full_name: '', email: '', password: '' })
  const [savingUser, setSavingUser] = useState(false)

  const [form, setForm] = useState({
    nombre: '',
    plan: 'basic',
    activo: true,
    configuracion: JSON.stringify(CONFIG_DEFAULT, null, 2)
  })

  const load = async () => {
    setLoading(true)
    try {
      const res = await apiClient.client.get('/admin/organizaciones')
      setOrgs(res.data)
    } catch { setOrgs([]) }
    finally { setLoading(false) }
  }

  useEffect(() => { load() }, [])

  const openCreate = () => {
    setEditingOrg(null)
    setForm({ nombre: '', plan: 'basic', activo: true, configuracion: JSON.stringify(CONFIG_DEFAULT, null, 2) })
    setShowForm(true)
  }

  const openEdit = (org: Org) => {
    setEditingOrg(org)
    setForm({
      nombre: org.nombre,
      plan: org.plan,
      activo: org.activo,
      configuracion: JSON.stringify(org.configuracion, null, 2)
    })
    setShowForm(true)
  }

  const handleSave = async () => {
    setSaving(true)
    setMsg('')
    try {
      let config: Record<string, unknown>
      try { config = JSON.parse(form.configuracion) as Record<string, unknown> } catch {
        setMsg('El JSON de configuración no es válido')
        setSaving(false)
        return
      }
      const payload = { nombre: form.nombre, plan: form.plan, activo: form.activo, configuracion: config }
      if (editingOrg) {
        await apiClient.client.put(`/admin/organizaciones/${editingOrg.id}`, payload)
        setMsg(`✓ ${form.nombre} actualizada`)
      } else {
        await apiClient.client.post('/admin/organizaciones', payload)
        setMsg(`✓ ${form.nombre} creada`)
      }
      setShowForm(false)
      await load()
    } catch (err: any) {
      setMsg(err.response?.data?.detail || 'Error al guardar')
    } finally { setSaving(false) }
  }

  if (!user?.is_superadmin) {
    return <div className="p-8 text-center text-gray-400">Solo el superadmin puede acceder a esta sección.</div>
  }

  return (
    <div className="p-4 md:p-6 max-w-5xl mx-auto">
      <div className="flex items-start justify-between mb-6 gap-3 flex-wrap">
        <div>
          <h1 className="text-xl font-bold dark:text-white">Organizaciones</h1>
          <p className="text-sm text-gray-400 mt-0.5">{orgs.length} clientes B2B registrados</p>
        </div>
        <button onClick={openCreate} className="btn-yellow">+ Nueva organización</button>
      </div>

      {msg && (
        <div className={`mb-4 px-3 py-2 rounded text-sm ${msg.startsWith('✓') ? 'bg-green-50 text-green-700 dark:bg-green-900/20 dark:text-green-400' : 'bg-red-50 text-red-600 dark:bg-red-900/20 dark:text-red-400'}`}>
          {msg}
        </div>
      )}

      {/* Formulario crear/editar */}
      {showForm && (
        <div className="card mb-6 border-l-4 border-ml-blue dark:border-ml-green">
          <h2 className="font-semibold dark:text-white mb-4">{editingOrg ? `Editar: ${editingOrg.nombre}` : 'Nueva organización'}</h2>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="label">Nombre</label>
              <input className="input-field" placeholder="Ej: Empresa SA"
                value={form.nombre} onChange={e => setForm(p => ({ ...p, nombre: e.target.value }))} />
            </div>
            <div>
              <label className="label">Plan</label>
              <select className="input-field" value={form.plan} onChange={e => setForm(p => ({ ...p, plan: e.target.value }))}>
                <option value="basic">Basic</option>
                <option value="pro">Pro</option>
              </select>
            </div>
            <div className="flex items-center gap-3 pt-1">
              <label className="label mb-0">Activa</label>
              <button onClick={() => setForm(p => ({ ...p, activo: !p.activo }))}
                className={`px-3 py-1 rounded text-xs font-semibold ${form.activo ? 'bg-green-100 text-green-700 dark:bg-green-900/40 dark:text-green-300' : 'bg-red-100 text-red-700 dark:bg-red-900/40 dark:text-red-400'}`}>
                {form.activo ? 'Activa' : 'Inactiva'}
              </button>
            </div>
            <div className="md:col-span-2">
              <label className="label">Configuración de flujo (JSON)</label>
              <textarea
                className="input-field font-mono text-xs"
                rows={12}
                value={form.configuracion}
                onChange={e => setForm(p => ({ ...p, configuracion: e.target.value }))}
              />
              <p className="text-xs text-gray-400 mt-1">
                match_rules: ["monto_cuit"] | ["referencia","monto_cuit"] · tolerancia_monto: 0.01 · requiere_cierre_periodo: true/false
              </p>
            </div>
          </div>
          <div className="flex gap-3 mt-4 justify-end">
            <button onClick={() => setShowForm(false)} className="btn-secondary">Cancelar</button>
            <button onClick={handleSave} disabled={saving} className="btn-yellow">
              {saving ? 'Guardando...' : editingOrg ? 'Guardar cambios' : 'Crear organización'}
            </button>
          </div>
        </div>
      )}

      {/* Lista de orgs */}
      {loading ? (
        <div className="card p-8 text-center text-gray-400">Cargando...</div>
      ) : (
        <div className="space-y-3">
          {orgs.map(org => {
            const isActive = activeOrgId === org.id
            return (
              <div key={org.id}
                className={`card p-0 overflow-hidden transition-all ${isActive ? 'ring-2 ring-ml-green dark:ring-ml-green' : ''}`}>
                <div className="flex flex-col sm:flex-row sm:items-center gap-2 px-4 py-3">
                  <div className="flex items-center gap-3 min-w-0">
                    {/* Indicador plan */}
                    <div className={`w-2.5 h-2.5 rounded-full shrink-0 ${org.activo ? 'bg-green-400' : 'bg-gray-300'}`} />

                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 flex-wrap">
                        <p className="font-semibold dark:text-white">{org.nombre}</p>
                        <span className={`text-[10px] px-1.5 py-0.5 rounded-full font-mono uppercase ${org.plan === 'pro' ? 'bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400' : 'bg-gray-100 text-gray-600 dark:bg-slate-700 dark:text-gray-400'}`}>
                          {org.plan}
                        </span>
                        {!org.activo && <span className="text-[10px] text-red-500">inactiva</span>}
                      </div>
                      <p className="text-xs text-gray-400 dark:text-zinc-500 font-mono mt-0.5">
                        match: {(org.configuracion?.match_rules || []).join(' + ')} ·
                        tol: ${org.configuracion?.tolerancia_monto ?? 0.01}
                      </p>
                    </div>
                  </div>

                  <div className="flex gap-2 flex-wrap sm:ml-auto sm:shrink-0">
                    <button
                      onClick={() => isActive ? clearActiveOrg() : setActiveOrg(org.id, org.nombre)}
                      className={`px-3 py-1.5 text-xs rounded-lg font-medium transition-all ${isActive
                        ? 'bg-ml-green text-black'
                        : 'bg-gray-100 dark:bg-ml-dark-card text-gray-600 dark:text-gray-300 hover:bg-ml-green/10'}`}
                    >
                      {isActive ? 'Viendo' : 'Ver'}
                    </button>
                    <button onClick={() => openEdit(org)}
                      className="px-3 py-1.5 text-xs rounded-lg bg-blue-50 dark:bg-blue-900/20 text-blue-600 dark:text-blue-400 hover:bg-blue-100">
                      Config
                    </button>
                    <button
                      onClick={() => { apiClient.client.get(`/admin/organizaciones/${org.id}/backup`, { responseType: 'blob' }).then(r => { const url = URL.createObjectURL(r.data); const a = document.createElement('a'); a.href = url; a.download = `backup_${org.nombre}.xlsx`; a.click(); URL.revokeObjectURL(url) }) }}
                      className="px-3 py-1.5 text-xs rounded-lg bg-green-50 dark:bg-green-900/20 text-green-600 dark:text-green-400 hover:bg-green-100"
                      title="Descargar backup Excel"
                    >
                      Excel
                    </button>
                    <button
                      onClick={() => { setShowUserForm(org.id); setUserForm({ full_name: '', email: '', password: '' }) }}
                      className="px-3 py-1.5 text-xs rounded-lg bg-purple-50 dark:bg-purple-900/20 text-purple-600 dark:text-purple-400 hover:bg-purple-100"
                    >
                      + Usuario
                    </button>
                  </div>
                </div>

                {/* Form crear primer usuario */}
                {showUserForm === org.id && (
                  <div className="border-t border-ml-gray dark:border-ml-dark-border px-4 py-3 bg-gray-50 dark:bg-ml-dark-card">
                    <p className="text-xs font-semibold dark:text-white mb-2">Crear usuario para {org.nombre}</p>
                    <div className="grid grid-cols-1 md:grid-cols-3 gap-2">
                      <input className="input-field !text-xs" placeholder="Nombre completo"
                        value={userForm.full_name} onChange={e => setUserForm(p => ({ ...p, full_name: e.target.value }))} />
                      <input className="input-field !text-xs" placeholder="Email" type="email"
                        value={userForm.email} onChange={e => setUserForm(p => ({ ...p, email: e.target.value }))} />
                      <input className="input-field !text-xs" placeholder="Contraseña (mín 6)" type="password"
                        value={userForm.password} onChange={e => setUserForm(p => ({ ...p, password: e.target.value }))} />
                    </div>
                    <div className="flex gap-2 mt-2">
                      <button
                        disabled={savingUser}
                        onClick={async () => {
                          setSavingUser(true)
                          try {
                            await apiClient.client.post(`/admin/organizaciones/${org.id}/primer-usuario`, userForm)
                            setMsg(`✓ Usuario ${userForm.email} creado en ${org.nombre}`)
                            setShowUserForm(null)
                          } catch (err: any) {
                            setMsg(err.response?.data?.detail || 'Error al crear usuario')
                          } finally { setSavingUser(false) }
                        }}
                        className="btn-yellow text-xs py-1.5"
                      >
                        {savingUser ? 'Creando...' : 'Crear'}
                      </button>
                      <button onClick={() => setShowUserForm(null)} className="btn-ghost text-xs">Cancelar</button>
                    </div>
                  </div>
                )}
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}
