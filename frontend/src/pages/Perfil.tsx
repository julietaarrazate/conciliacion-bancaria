import React, { useState } from 'react'
import { useAuthStore } from '@/store/auth'
import { useLockStore } from '@/store/lock'
import { apiClient } from '@/services/api'
import { toast } from '@/store/toast'

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

  // PIN de bloqueo
  const pinEnabled = useLockStore(s => s.enabled)
  const setupPin = useLockStore(s => s.setupPin)
  const removePin = useLockStore(s => s.removePin)
  const [pinModal, setPinModal] = useState<'activar' | 'desactivar' | null>(null)
  const [pin1, setPin1] = useState('')
  const [pin2, setPin2] = useState('')
  const [pinErr, setPinErr] = useState('')

  const handleActivarPin = async (e: React.FormEvent) => {
    e.preventDefault()
    setPinErr('')
    if (pin1.length !== 4 || !/^\d{4}$/.test(pin1)) { setPinErr('El PIN debe tener 4 dígitos'); return }
    if (pin1 !== pin2) { setPinErr('Los PINs no coinciden'); return }
    await setupPin(pin1)
    toast.success('Bloqueo con PIN activado')
    setPinModal(null); setPin1(''); setPin2('')
  }

  const handleDesactivarPin = async (e: React.FormEvent) => {
    e.preventDefault()
    setPinErr('')
    const ok = await removePin(pin1)
    if (!ok) { setPinErr('PIN incorrecto'); return }
    toast.success('Bloqueo con PIN desactivado')
    setPinModal(null); setPin1('')
  }

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

      {/* Bloqueo con PIN */}
      <div className="card mt-4">
        <div className="flex items-start justify-between gap-3 mb-3">
          <div>
            <h2 className="text-base font-semibold dark:text-white">Bloqueo con PIN</h2>
            <p className="text-xs text-ml-text-soft dark:text-zinc-500 mt-1">
              Pide un PIN de 4 dígitos cuando minimices la app o pasen 5 minutos sin actividad. La sesión se mantiene.
            </p>
          </div>
          <span className={`badge ${pinEnabled ? 'badge-ok' : 'badge-neutral'} shrink-0`}>
            {pinEnabled ? 'Activado' : 'Desactivado'}
          </span>
        </div>
        {pinEnabled ? (
          <div className="flex gap-2">
            <button onClick={() => { setPinModal('desactivar'); setPin1(''); setPinErr('') }} className="btn-secondary">
              Desactivar
            </button>
            <button onClick={() => { setPinModal('activar'); setPin1(''); setPin2(''); setPinErr('') }} className="btn-ghost">
              Cambiar PIN
            </button>
          </div>
        ) : (
          <button onClick={() => { setPinModal('activar'); setPin1(''); setPin2(''); setPinErr('') }} className="btn-yellow">
            Activar bloqueo con PIN
          </button>
        )}
      </div>

      {/* Modal PIN */}
      {pinModal && (
        <div className="fixed inset-0 bg-black/50 z-[150] flex items-center justify-center p-3" onClick={() => setPinModal(null)}>
          <div onClick={e => e.stopPropagation()} className="bg-white dark:bg-ml-dark-surface rounded-2xl p-5 w-full max-w-sm">
            <h3 className="text-lg font-bold dark:text-white mb-1">
              {pinModal === 'activar' ? 'Configurar PIN' : 'Desactivar PIN'}
            </h3>
            <p className="text-xs text-ml-text-soft dark:text-zinc-500 mb-4">
              {pinModal === 'activar' ? 'Elegí un PIN numérico de 4 dígitos' : 'Ingresá tu PIN actual para confirmar'}
            </p>
            {pinErr && (
              <div className="mb-3 px-3 py-2 rounded-lg text-sm bg-red-50 border border-red-200 text-red-700 dark:bg-red-900/30 dark:border-red-800/40 dark:text-red-400">
                {pinErr}
              </div>
            )}
            <form onSubmit={pinModal === 'activar' ? handleActivarPin : handleDesactivarPin} className="space-y-3">
              <div>
                <label className="label">{pinModal === 'activar' ? 'Nuevo PIN' : 'PIN actual'}</label>
                <input
                  type="password"
                  inputMode="numeric"
                  pattern="\d{4}"
                  maxLength={4}
                  autoFocus
                  className="input-field text-center text-2xl tracking-[0.5em] font-mono"
                  value={pin1}
                  onChange={e => setPin1(e.target.value.replace(/\D/g, '').slice(0, 4))}
                  placeholder="••••"
                />
              </div>
              {pinModal === 'activar' && (
                <div>
                  <label className="label">Repetí el PIN</label>
                  <input
                    type="password"
                    inputMode="numeric"
                    pattern="\d{4}"
                    maxLength={4}
                    className="input-field text-center text-2xl tracking-[0.5em] font-mono"
                    value={pin2}
                    onChange={e => setPin2(e.target.value.replace(/\D/g, '').slice(0, 4))}
                    placeholder="••••"
                  />
                </div>
              )}
              <div className="flex gap-2 pt-2">
                <button type="button" onClick={() => setPinModal(null)} className="btn-secondary flex-1">
                  Cancelar
                </button>
                <button type="submit" className="btn-yellow flex-1">
                  {pinModal === 'activar' ? 'Activar' : 'Desactivar'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  )
}
