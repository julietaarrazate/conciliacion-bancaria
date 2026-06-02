import React, { useState, useEffect, useRef } from 'react'
import { useNavigate, Link } from 'react-router-dom'
import { apiClient } from '@/services/api'
import { useAuthStore } from '@/store/auth'
import { useLockStore } from '@/store/lock'
import { CuadraLogo } from '@/components/CuadraLogo'

export const Login: React.FC = () => {
  const navigate = useNavigate()
  const { setUser, setToken } = useAuthStore()
  const forceUnlock = useLockStore(s => s.forceUnlock)

  const [formData, setFormData] = useState({
    email: '',
    password: ''
  })
  const [showPassword, setShowPassword] = useState(false)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const [waking, setWaking] = useState(false)
  // Aprobación en vivo (rol contador)
  const [pending, setPending] = useState<{ id: number; secret: string } | null>(null)
  const pollRef = useRef<number | null>(null)
  // 2FA superadmin
  const [twofa, setTwofa] = useState<{ email: string } | null>(null)
  const [twofaCode, setTwofaCode] = useState('')
  const [twofaLoading, setTwofaLoading] = useState(false)

  // Polling del estado de aprobación mientras esperamos al superadmin
  useEffect(() => {
    if (!pending) return
    let cancelled = false
    const tick = async () => {
      try {
        const st = await apiClient.getLoginApprovalStatus(pending.id, pending.secret)
        if (cancelled) return
        if (st.status === 'approved' && st.access_token && st.user) {
          setUser(st.user)
          setToken(st.access_token)
          forceUnlock()
          setPending(null)
          navigate('/dashboard')
        } else if (st.status === 'denied') {
          setPending(null)
          setError('El superadmin rechazó tu ingreso.')
        } else if (st.status === 'expired') {
          setPending(null)
          setError('La solicitud expiró. Volvé a iniciar sesión.')
        }
      } catch {
        if (!cancelled) {
          setPending(null)
          setError('No se pudo verificar la solicitud. Intentá de nuevo.')
        }
      }
    }
    pollRef.current = window.setInterval(tick, 3000)
    tick()
    return () => {
      cancelled = true
      if (pollRef.current) window.clearInterval(pollRef.current)
    }
  }, [pending, setUser, setToken, forceUnlock, navigate])

  const handleTwofaSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')
    setTwofaLoading(true)
    try {
      const res = await apiClient.client.post('/auth/verify-2fa', {
        email: twofa!.email,
        code: twofaCode.trim(),
      })
      const data = res.data
      apiClient.setToken(data.access_token)
      setUser(data.user)
      setToken(data.access_token)
      forceUnlock()
      navigate('/dashboard')
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Código inválido o expirado')
    } finally {
      setTwofaLoading(false)
    }
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')
    setLoading(true)
    try {
      const response = await apiClient.login(formData.email, formData.password)
      if ('requires_2fa' in response) {
        setTwofa({ email: (response as any).email })
        return
      }
      if ('pending_approval' in response) {
        setPending({ id: (response as any).approval_id, secret: (response as any).poll_secret })
        return
      }
      setUser((response as any).user)
      setToken((response as any).access_token)
      forceUnlock()
      navigate('/dashboard')
    } catch (err: any) {
      const detail = err.response?.data?.detail
      const code = err.response?.status
      if (code === 401) {
        setError('Email o contraseña incorrectos')
      } else if (err.code === 'ERR_NETWORK' || !err.response) {
        setWaking(true)
        setError('')
        for (let attempt = 0; attempt < 4; attempt++) {
          await new Promise(r => setTimeout(r, 8000))
          try {
            const response2 = await apiClient.login(formData.email, formData.password)
            if ('requires_2fa' in response2) {
              setWaking(false)
              setTwofa({ email: (response2 as any).email })
              return
            }
            if ('pending_approval' in response2) {
              setWaking(false)
              setPending({ id: (response2 as any).approval_id, secret: (response2 as any).poll_secret })
              return
            }
            setUser((response2 as any).user)
            setToken((response2 as any).access_token)
            forceUnlock()
            setWaking(false)
            navigate('/dashboard')
            return
          } catch (retryErr: any) {
            if (retryErr.response?.status === 401) {
              setWaking(false)
              setError('Email o contraseña incorrectos')
              return
            }
          }
        }
        setWaking(false)
        setError('El servidor tardó en responder. Intentá de nuevo.')
      } else {
        setError(detail || 'Error en autenticación')
      }
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen bg-ml-gray-bg dark:bg-ml-dark-bg flex items-center justify-center p-4">
      <div className="w-full max-w-sm">

        {/* Logo / título */}
        <div className="text-center mb-8">
          <div className="inline-flex items-center justify-center mb-5 dark:drop-shadow-[0_0_20px_rgba(34,197,94,0.25)]">
            <CuadraLogo size={88} />
          </div>
          <h1 className="text-3xl font-bold text-ml-text dark:text-white tracking-tight font-mono">
            Cuadra
          </h1>
          <p className="text-[11px] text-ml-text-soft dark:text-zinc-500 mt-2 font-mono tracking-[0.2em] uppercase">
            Conciliación bancaria
          </p>
        </div>

        {/* Card */}
        <div className="bg-white dark:bg-ml-dark-surface rounded-2xl p-6 shadow-sm border border-gray-100 dark:border-ml-dark-border dark:shadow-none">

          {twofa ? (
            <div className="py-4">
              <div className="text-center mb-5">
                <div className="text-4xl mb-3">📧</div>
                <h2 className="text-lg font-semibold text-ml-text dark:text-white mb-1">
                  Verificación en dos pasos
                </h2>
                <p className="text-sm text-ml-text-soft dark:text-zinc-400">
                  Ingresá el código que enviamos a
                </p>
                <p className="text-sm font-medium text-ml-text dark:text-white mt-1">
                  {twofa.email}
                </p>
              </div>
              {error && (
                <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded-lg text-red-700 text-sm dark:bg-red-950/40 dark:border-red-800/50 dark:text-red-400">
                  {error}
                </div>
              )}
              <form onSubmit={handleTwofaSubmit} className="space-y-4">
                <div>
                  <label className="label">Código de 6 dígitos</label>
                  <input
                    type="text"
                    inputMode="numeric"
                    pattern="[0-9]*"
                    maxLength={6}
                    className="input-field text-center font-mono text-2xl tracking-widest"
                    placeholder="000000"
                    value={twofaCode}
                    onChange={(e) => setTwofaCode(e.target.value.replace(/\D/g, ''))}
                    autoFocus
                    required
                  />
                </div>
                <button
                  type="submit"
                  className="btn-yellow w-full py-3 text-base"
                  disabled={twofaLoading || twofaCode.length < 6}
                >
                  {twofaLoading
                    ? <span className="font-mono tracking-widest">verificando...</span>
                    : 'Verificar'}
                </button>
                <div className="text-center">
                  <button
                    type="button"
                    onClick={() => { setTwofa(null); setTwofaCode(''); setError('') }}
                    className="text-xs text-ml-text-soft dark:text-zinc-500 hover:text-ml-text dark:hover:text-ml-green transition-colors"
                  >
                    Volver al login
                  </button>
                </div>
              </form>
            </div>
          ) : pending ? (
            <div className="text-center py-6">
              <div className="text-4xl mb-4 animate-pulse">🔐</div>
              <h2 className="text-lg font-semibold text-ml-text dark:text-white mb-2">
                Esperando aprobación
              </h2>
              <p className="text-sm text-ml-text-soft dark:text-zinc-400 mb-1">
                Se le envió una solicitud al administrador para autorizar tu ingreso.
              </p>
              <p className="text-xs text-ml-text-soft dark:text-zinc-500 mb-5">
                Dejá esta pantalla abierta — apenas te aprueben, entrás solo.
              </p>
              <div className="flex items-center justify-center gap-2 text-ml-green text-sm">
                <span className="animate-spin text-base">⏳</span>
                <span>Aguardando…</span>
              </div>
              <button
                type="button"
                onClick={() => { setPending(null); setError('') }}
                className="mt-6 text-xs text-ml-text-soft dark:text-zinc-500 hover:text-ml-text dark:hover:text-ml-green transition-colors"
              >
                Cancelar
              </button>
            </div>
          ) : (
          <>
          {waking && (
            <div className="mb-4 p-3 bg-amber-50 border border-amber-200 rounded-lg text-amber-700 text-sm dark:bg-amber-950/30 dark:border-amber-800/40 dark:text-amber-400 flex items-center gap-2">
              <span className="animate-spin text-base">⏳</span>
              <span>Servidor despertando… reintentando automáticamente</span>
            </div>
          )}
          {error && !waking && (
            <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded-lg text-red-700 text-sm dark:bg-red-950/40 dark:border-red-800/50 dark:text-red-400">
              {error}
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="label">Email</label>
              <input
                type="email"
                className="input-field"
                placeholder="tu@email.com"
                value={formData.email}
                onChange={(e) => setFormData({ ...formData, email: e.target.value })}
                required
                autoComplete="email"
                inputMode="email"
              />
            </div>

            <div>
              <label className="label">Contraseña</label>
              <div className="relative">
                <input
                  type={showPassword ? 'text' : 'password'}
                  className="input-field pr-12"
                  placeholder="••••••••"
                  value={formData.password}
                  onChange={(e) => setFormData({ ...formData, password: e.target.value })}
                  required
                  autoComplete="current-password"
                />
                <button
                  type="button"
                  onPointerDown={(e) => { e.preventDefault(); setShowPassword((s) => !s) }}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600 dark:text-zinc-500 dark:hover:text-ml-green transition-colors p-1"
                  tabIndex={-1}
                  aria-label={showPassword ? 'Ocultar contraseña' : 'Mostrar contraseña'}
                >
                  {showPassword ? '🙈' : '👁️'}
                </button>
              </div>
            </div>

            <button
              type="submit"
              className="btn-yellow w-full mt-2 py-3 text-base"
              disabled={loading}
            >
              {loading
                ? <span className="font-mono tracking-widest">cargando...</span>
                : 'Ingresar'}
            </button>

            <div className="text-center pt-2">
              <Link
                to="/recuperar-password"
                className="text-xs text-ml-text-soft dark:text-zinc-500 hover:text-ml-text dark:hover:text-ml-green transition-colors"
              >
                ¿Olvidaste tu contraseña?
              </Link>
            </div>
          </form>
          </>
          )}
        </div>

        <p className="text-center text-xs text-gray-400 dark:text-zinc-700 mt-6 font-mono">
          © 2026 Julieta Arrazate
        </p>
        <div className="flex justify-center gap-4 mt-2">
          <Link
            to="/privacidad"
            className="text-xs text-gray-400 dark:text-zinc-600 hover:text-gray-600 dark:hover:text-zinc-400 transition-colors"
          >
            Privacidad
          </Link>
          <span className="text-gray-300 dark:text-zinc-700">·</span>
          <Link
            to="/terminos"
            className="text-xs text-gray-400 dark:text-zinc-600 hover:text-gray-600 dark:hover:text-zinc-400 transition-colors"
          >
            Términos
          </Link>
        </div>
      </div>
    </div>
  )
}
