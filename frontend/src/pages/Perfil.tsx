import React, { useState } from 'react'
import { useAuthStore } from '@/store/auth'
import { apiClient } from '@/services/api'

export const Perfil: React.FC = () => {
  const user = useAuthStore(s => s.user)
  const setUser = useAuthStore(s => s.setUser)

  const [email, setEmail] = useState(user?.email || '')
  const [nombre, setNombre] = useState(user?.full_name || '')
  const [saving, setSaving] = useState(false)
  const [profileMsg, setProfileMsg] = useState('')

  const [pwActual, setPwActual] = useState('')
  const [pwNueva, setPwNueva] = useState('')
  const [pwConfirm, setPwConfirm] = useState('')
  const [showPw, setShowPw] = useState(false)
  const [pwMsg, setPwMsg] = useState('')
  const [pwLoading, setPwLoading] = useState(false)

  const handleSavePerfil = async (e: React.FormEvent) => {
    e.preventDefault()
    setSaving(true)
    setProfileMsg('')
    try {
      const updated = await apiClient.client.patch('/me', {
        email: email !== user?.email ? email : undefined,
        full_name: nombre !== user?.full_name ? nombre : undefined
      })
      setUser(updated.data)
      setProfileMsg('✓ Perfil actualizado')
    } catch (err: any) {
      setProfileMsg('✗ ' + (err.response?.data?.detail || 'Error al guardar'))
    } finally { setSaving(false) }
  }

  const handleChangePassword = async (e: React.FormEvent) => {
    e.preventDefault()
    if (pwNueva !== pwConfirm) { setPwMsg('✗ Las contraseñas no coinciden'); return }
    if (pwNueva.length < 6) { setPwMsg('✗ Mínimo 6 caracteres'); return }
    setPwLoading(true)
    setPwMsg('')
    try {
      await apiClient.client.post('/me/change-password', {
        current_password: pwActual,
        new_password: pwNueva
      })
      setPwMsg('✓ Contraseña cambiada correctamente')
      setPwActual(''); setPwNueva(''); setPwConfirm('')
    } catch (err: any) {
      setPwMsg('✗ ' + (err.response?.data?.detail || 'Error al cambiar contraseña'))
    } finally { setPwLoading(false) }
  }

  return (
    <div className="p-4 md:p-8 max-w-lg mx-auto">
      <h1 className="text-xl md:text-2xl font-bold dark:text-white mb-6">Mi perfil</h1>

      {/* Datos personales */}
      <div className="card mb-4">
        <h2 className="text-base font-semibold dark:text-white mb-4">Datos de acceso</h2>
        {profileMsg && (
          <div className={`mb-3 px-3 py-2 rounded text-sm ${profileMsg.startsWith('✓') ? 'bg-green-50 dark:bg-green-900/20 text-green-700 dark:text-green-300' : 'bg-red-50 text-red-700'}`}>
            {profileMsg}
          </div>
        )}
        <form onSubmit={handleSavePerfil} className="space-y-3">
          <div>
            <label className="label">Nombre</label>
            <input className="input-field" value={nombre} onChange={e => setNombre(e.target.value)} />
          </div>
          <div>
            <label className="label">Email (para iniciar sesión)</label>
            <input type="email" className="input-field" value={email} onChange={e => setEmail(e.target.value)} />
          </div>
          <div className="flex items-center gap-3 pt-1">
            <button type="submit" disabled={saving} className="btn-yellow">
              {saving ? 'Guardando...' : 'Guardar cambios'}
            </button>
            <p className="text-xs text-gray-400 dark:text-gray-500">Rol: <span className="font-medium capitalize">{user?.role}</span></p>
          </div>
        </form>
      </div>

      {/* Cambiar contraseña */}
      <div className="card">
        <h2 className="text-base font-semibold dark:text-white mb-4">Cambiar contraseña</h2>
        {pwMsg && (
          <div className={`mb-3 px-3 py-2 rounded text-sm ${pwMsg.startsWith('✓') ? 'bg-green-50 dark:bg-green-900/20 text-green-700 dark:text-green-300' : 'bg-red-50 text-red-700'}`}>
            {pwMsg}
          </div>
        )}
        <form onSubmit={handleChangePassword} className="space-y-3">
          {[
            { label: 'Contraseña actual', val: pwActual, set: setPwActual },
            { label: 'Nueva contraseña', val: pwNueva, set: setPwNueva },
            { label: 'Confirmar nueva contraseña', val: pwConfirm, set: setPwConfirm },
          ].map((f, i) => (
            <div key={i}>
              <label className="label">{f.label}</label>
              <div className="relative">
                <input type={showPw ? 'text' : 'password'} className="input-field pr-10"
                  value={f.val} onChange={e => f.set(e.target.value)} />
                {i === 0 && (
                  <button type="button" tabIndex={-1} onClick={() => setShowPw(s => !s)}
                    className="absolute right-2 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600">
                    {showPw ? '🙈' : '👁️'}
                  </button>
                )}
              </div>
            </div>
          ))}
          <button type="submit" disabled={pwLoading} className="btn-primary w-full">
            {pwLoading ? 'Cambiando...' : 'Cambiar contraseña'}
          </button>
        </form>
      </div>
    </div>
  )
}
