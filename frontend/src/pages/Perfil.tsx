import React, { useState, useEffect } from 'react'
import { useAuthStore } from '@/store/auth'
import { useLockStore, isBiometricAvailable } from '@/store/lock'
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
  const biometricEnabled = useLockStore(s => s.biometricEnabled)
  const enrollBiometric = useLockStore(s => s.enrollBiometric)
  const disableBiometric = useLockStore(s => s.disableBiometric)
  const [pinModal, setPinModal] = useState<'activar' | 'desactivar' | null>(null)
  const [pin1, setPin1] = useState('')
  const [pin2, setPin2] = useState('')
  const [pinErr, setPinErr] = useState('')
  const [bioAvailable, setBioAvailable] = useState(false)
  const [bioBusy, setBioBusy] = useState(false)

  // Push notifications
  const [pushSupported] = useState('serviceWorker' in navigator && 'PushManager' in window)
  const [pushEnabled, setPushEnabled] = useState(false)
  const [pushLoading, setPushLoading] = useState(false)

  // VAPID setup (sólo superadmin)
  const [vapidLoading, setVapidLoading] = useState(false)
  const [vapidKeys, setVapidKeys] = useState<{ vapid_public_key: string; vapid_private_key: string } | null>(null)
  const [vapidConfigured, setVapidConfigured] = useState<boolean | null>(null) // null = cargando

  useEffect(() => {
    isBiometricAvailable().then(setBioAvailable)
  }, [])

  useEffect(() => {
    if (!user?.is_superadmin) return
    apiClient.getPushPublicKey().then(k => setVapidConfigured(!!k)).catch(() => setVapidConfigured(false))
  }, [user?.is_superadmin])

  useEffect(() => {
    if (!pushSupported) return
    navigator.serviceWorker.ready.then(async reg => {
      const sub = await reg.pushManager.getSubscription()
      setPushEnabled(!!sub)
    }).catch(() => {})
  }, [pushSupported])

  const togglePush = async () => {
    if (!pushSupported) return
    setPushLoading(true)
    try {
      const reg = await navigator.serviceWorker.ready
      if (pushEnabled) {
        const sub = await reg.pushManager.getSubscription()
        if (sub) {
          await apiClient.unsubscribePush(sub.endpoint)
          await sub.unsubscribe()
          setPushEnabled(false)
        }
      } else {
        if (typeof Notification !== 'undefined' && Notification.permission === 'denied') {
          toast.error('Las notificaciones están bloqueadas en este navegador. Hacé clic en el ícono 🔒 en la barra de direcciones y habilitá "Notificaciones".')
          return
        }
        const permission = await Notification.requestPermission()
        if (permission !== 'granted') {
          toast.error('Se necesita permiso de notificaciones para activarlas.')
          return
        }
        const vapidKey = await apiClient.getPushPublicKey()
        if (!vapidKey) { toast.info('Notificaciones no configuradas aún. Contactá al admin.'); return }
        // Conversión base64url → Uint8Array (Safari no acepta string raw)
        const pad = '='.repeat((4 - (vapidKey.length % 4)) % 4)
        const b64 = (vapidKey + pad).replace(/-/g, '+').replace(/_/g, '/')
        const raw = atob(b64)
        const appKey = new Uint8Array(raw.length)
        for (let i = 0; i < raw.length; i++) appKey[i] = raw.charCodeAt(i)
        const sub = await reg.pushManager.subscribe({
          userVisibleOnly: true,
          applicationServerKey: appKey,
        })
        await apiClient.subscribePush(sub.toJSON() as PushSubscriptionJSON)
        setPushEnabled(true)
        toast.success('Notificaciones activadas')
      }
    } catch (e) {
      console.error('Push error:', e)
      toast.error('No se pudo configurar las notificaciones')
    } finally {
      setPushLoading(false)
    }
  }

  const handleActivarBio = async () => {
    setBioBusy(true)
    const r = await enrollBiometric()
    setBioBusy(false)
    if (r.ok) toast.success('Biometría activada')
    else toast.error(r.error || 'No se pudo activar la biometría')
  }

  const handleDesactivarBio = () => {
    disableBiometric()
    toast.info('Biometría desactivada')
  }

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
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-xl md:text-2xl font-bold dark:text-white">Mi perfil</h1>
        <span className="text-[10px] font-mono text-ml-text-soft dark:text-zinc-600">build v3.2</span>
      </div>

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

        {/* Biometría — sólo si hay PIN activo y el dispositivo soporta */}
        {pinEnabled && bioAvailable && (
          <div className="mt-4 pt-4 border-t border-gray-100 dark:border-ml-dark-border">
            <div className="flex items-start justify-between gap-3 mb-2">
              <div>
                <p className="text-sm font-semibold dark:text-white">Huella / Face ID</p>
                <p className="text-xs text-ml-text-soft dark:text-zinc-500 mt-0.5">
                  Desbloqueá la app con la biometría del dispositivo en vez de tipear el PIN.
                </p>
              </div>
              <span className={`badge ${biometricEnabled ? 'badge-ok' : 'badge-neutral'} shrink-0`}>
                {biometricEnabled ? 'Activada' : 'Desactivada'}
              </span>
            </div>
            {biometricEnabled ? (
              <button onClick={handleDesactivarBio} className="btn-secondary">
                Desactivar biometría
              </button>
            ) : (
              <button onClick={handleActivarBio} disabled={bioBusy} className="btn-yellow">
                {bioBusy ? 'Registrando...' : 'Activar biometría'}
              </button>
            )}
          </div>
        )}
        {pinEnabled && !bioAvailable && (
          <p className="mt-3 text-xs text-ml-text-soft dark:text-zinc-600 italic">
            Tu dispositivo o navegador no soporta biometría (huella/Face ID).
          </p>
        )}
      </div>

      {/* Notificaciones Push */}
      <div className="card mt-4">
        <div className="flex items-start justify-between gap-3 mb-3">
          <div>
            <h2 className="text-base font-semibold dark:text-white">Notificaciones push</h2>
            <p className="text-xs text-ml-text-soft dark:text-zinc-500 mt-1">
              Recibí alertas en tu dispositivo aunque la app esté cerrada. Requiere instalar la PWA.
            </p>
          </div>
          <span className={`badge ${pushEnabled ? 'badge-ok' : 'badge-neutral'} shrink-0`}>
            {pushEnabled ? 'Activadas' : 'Desactivadas'}
          </span>
        </div>
        {pushSupported ? (
          <button
            onClick={togglePush}
            disabled={pushLoading}
            className={pushEnabled ? 'btn-secondary' : 'btn-yellow'}
          >
            {pushLoading ? 'Configurando...' : pushEnabled ? 'Desactivar notificaciones' : 'Activar notificaciones'}
          </button>
        ) : (
          <p className="text-xs text-ml-text-soft dark:text-zinc-600 italic">
            Tu navegador no soporta notificaciones push. Instalá la PWA desde Chrome/Edge.
          </p>
        )}
      </div>

      {/* Setup VAPID — sólo superadmin */}
      {user?.is_superadmin && (
        <div className="card mt-4 border-violet-200 dark:border-violet-900/40">
          <div className="flex items-start justify-between gap-3 mb-1">
            <h2 className="text-base font-semibold dark:text-white">⚙️ Setup notificaciones push (admin)</h2>
            {vapidConfigured === true && !vapidKeys && (
              <span className="badge badge-ok shrink-0">Configuradas</span>
            )}
            {vapidConfigured === false && (
              <span className="badge badge-neutral shrink-0">Sin configurar</span>
            )}
          </div>
          <p className="text-xs text-ml-text-soft dark:text-zinc-500 mb-3">
            Generá las VAPID keys <strong>una sola vez</strong> y pegálas en Render como env vars <code className="font-mono text-[10px] bg-gray-100 dark:bg-white/10 px-1 rounded">VAPID_PUBLIC_KEY</code> y <code className="font-mono text-[10px] bg-gray-100 dark:bg-white/10 px-1 rounded">VAPID_PRIVATE_KEY</code>. Si ya lo hiciste y el badge dice "Configuradas", no regeneres.
          </p>

          {/* Ya configuradas y no se está mostrando un set nuevo */}
          {vapidConfigured === true && !vapidKeys && (
            <div className="flex gap-2 flex-wrap items-center">
              <p className="text-xs text-green-600 dark:text-green-400 flex-1">Las keys están activas en el servidor. No es necesario regenerar.</p>
              <button
                onClick={async () => {
                  try {
                    await apiClient.client.post('/push/test')
                    toast.success('Push de prueba enviado — debería llegarte en segundos')
                  } catch (e: any) {
                    toast.error(e.response?.data?.detail || 'Error enviando push')
                  }
                }}
                className="btn-secondary text-xs shrink-0"
              >
                Enviar push de prueba
              </button>
              <button
                onClick={async () => {
                  if (!confirm('¿Seguro? Generar keys nuevas invalida las anteriores y tenés que volver a pegarlas en Render.')) return                  setVapidLoading(true)
                  try { const r = await apiClient.setupVapid(); setVapidKeys(r); setVapidConfigured(false) }
                  catch (e: any) { toast.error(e.response?.data?.detail || 'Error') }
                  finally { setVapidLoading(false) }
                }}
                className="btn-ghost text-xs"
                disabled={vapidLoading}
              >
                Regenerar
              </button>
            </div>
          )}

          {/* No configuradas aún — mostrar botón Generar */}
          {(vapidConfigured === false || vapidConfigured === null) && !vapidKeys && (
            <button
              disabled={vapidLoading || vapidConfigured === null}
              onClick={async () => {
                setVapidLoading(true)
                try { const r = await apiClient.setupVapid(); setVapidKeys(r) }
                catch (e: any) { toast.error(e.response?.data?.detail || 'Error generando keys') }
                finally { setVapidLoading(false) }
              }}
              className="btn-yellow"
            >
              {vapidLoading ? 'Generando...' : vapidConfigured === null ? 'Verificando...' : 'Generar VAPID keys'}
            </button>
          )}

          {/* Keys recién generadas — mostrar para copiar */}
          {vapidKeys && (
            <div className="space-y-3">
              {(['vapid_public_key', 'vapid_private_key'] as const).map(k => (
                <div key={k}>
                  <label className="label text-xs">{k === 'vapid_public_key' ? 'VAPID_PUBLIC_KEY' : 'VAPID_PRIVATE_KEY'}</label>
                  <div className="flex gap-2">
                    <input
                      readOnly
                      value={vapidKeys[k]}
                      onClick={e => (e.target as HTMLInputElement).select()}
                      className="input-field font-mono text-[11px] selectable"
                    />
                    <button
                      type="button"
                      onClick={() => { navigator.clipboard.writeText(vapidKeys[k]); toast.success('Copiado') }}
                      className="btn-secondary shrink-0"
                    >
                      Copiar
                    </button>
                  </div>
                </div>
              ))}
              <p className="text-[11px] text-amber-600 dark:text-amber-400 font-medium pt-1">
                Copiá ambas a Render → Environment antes de cerrar esta pantalla. No se vuelven a mostrar.
              </p>
              <p className="text-[11px] text-ml-text-soft dark:text-zinc-500 italic">
                Render Dashboard → conciliacion-api → Environment → Add Variable → Save and Deploy.
              </p>
              <button onClick={() => setVapidKeys(null)} className="btn-ghost text-xs">Ocultar</button>
            </div>
          )}
        </div>
      )}

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
