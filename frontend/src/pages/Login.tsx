import React, { useState, useEffect, useRef } from 'react'
import { useNavigate, Link } from 'react-router-dom'
import { useGoogleLogin } from '@react-oauth/google'
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

  // Maneja el redirect de Google OAuth (mobile): lee el access_token del hash de la URL
  useEffect(() => {
    const hash = window.location.hash
    if (!hash.includes('access_token=')) return
    const params = new URLSearchParams(hash.slice(1))
    const token = params.get('access_token')
    if (!token) return
    window.history.replaceState(null, '', window.location.pathname)
    apiClient.client.post('/auth/google', { access_token: token })
      .then((res) => {
        const data = res.data as { access_token: string; user: import('@/types').User }
        apiClient.setToken(data.access_token)
        setUser(data.user)
        setToken(data.access_token)
        forceUnlock()
        navigate('/')
      })
      .catch((err: unknown) => {
        const e = err as { response?: { data?: { detail?: string } } }
        setError(e.response?.data?.detail || 'Error al iniciar sesión con Google')
      })
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  // Polling del estado de aprobación mientras esperamos al superadmin
  useEffect(() => {
    if (!pending) return
    let cancelled = false
    const tick = async () => {
      try {
        const st = await apiClient.getLoginApprovalStatus(pending.id, pending.secret)
        if (cancelled) return
        if (st.status === 'approved' && st.access_token && st.user) {
          apiClient.setToken(st.access_token)
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
        setTwofa({ email: (response as import('@/types').TwofaChallenge).email })
        return
      }
      if ('pending_approval' in response) {
        const pa = response as import('@/types').PendingApproval
        setPending({ id: pa.approval_id, secret: pa.poll_secret })
        return
      }
      const auth = response as import('@/types').AuthResponse
      setUser(auth.user)
      setToken(auth.access_token)
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
              setTwofa({ email: (response2 as import('@/types').TwofaChallenge).email })
              return
            }
            if ('pending_approval' in response2) {
              setWaking(false)
              const pa2 = response2 as import('@/types').PendingApproval
              setPending({ id: pa2.approval_id, secret: pa2.poll_secret })
              return
            }
            const auth2 = response2 as import('@/types').AuthResponse
            setUser(auth2.user)
            setToken(auth2.access_token)
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

  const googleLogin = useGoogleLogin({
    onSuccess: async (tokenResponse) => {
      setLoading(true)
      setError('')
      try {
        const res = await apiClient.client.post('/auth/google', {
          access_token: tokenResponse.access_token,
        })
        const data = res.data as { access_token: string; user: import('@/types').User }
        apiClient.setToken(data.access_token)
        setUser(data.user)
        setToken(data.access_token)
        forceUnlock()
        navigate('/')
      } catch (err: unknown) {
        const e = err as { response?: { data?: { detail?: string } } }
        setError(e.response?.data?.detail || 'Error al iniciar sesión con Google')
      } finally {
        setLoading(false)
      }
    },
    onError: () => setError('Error al iniciar sesión con Google'),
    flow: 'implicit',
    ux_mode: 'redirect',
    redirect_uri: `${window.location.origin}/login`,
  })

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
            Gestión financiera con IA
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
                  {showPassword ? (
                    <svg className="w-4 h-4" fill="none" stroke="currentColor" strokeWidth={1.8} viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" d="M3.98 8.223A10.477 10.477 0 001.934 12C3.226 16.338 7.244 19.5 12 19.5c.993 0 1.953-.138 2.863-.395M6.228 6.228A10.45 10.45 0 0112 4.5c4.756 0 8.773 3.162 10.065 7.498a10.523 10.523 0 01-4.293 5.774M6.228 6.228L3 3m3.228 3.228l3.65 3.65m7.894 7.894L21 21m-3.228-3.228l-3.65-3.65m0 0a3 3 0 10-4.243-4.243m4.242 4.242L9.88 9.88" />
                    </svg>
                  ) : (
                    <svg className="w-4 h-4" fill="none" stroke="currentColor" strokeWidth={1.8} viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" d="M2.036 12.322a1.012 1.012 0 010-.639C3.423 7.51 7.36 4.5 12 4.5c4.638 0 8.573 3.007 9.963 7.178.07.207.07.431 0 .639C20.577 16.49 16.64 19.5 12 19.5c-4.638 0-8.573-3.007-9.963-7.178z" />
                      <path strokeLinecap="round" strokeLinejoin="round" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                    </svg>
                  )}
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

          {import.meta.env.VITE_GOOGLE_CLIENT_ID && (
            <>
              <div className="relative my-5">
                <div className="absolute inset-0 flex items-center">
                  <div className="w-full border-t border-gray-200 dark:border-zinc-700" />
                </div>
                <div className="relative flex justify-center text-xs">
                  <span className="px-2 bg-white dark:bg-ml-dark-surface text-gray-400 dark:text-zinc-500">
                    o continuá con
                  </span>
                </div>
              </div>
              <button
                type="button"
                onClick={() => googleLogin()}
                className="w-full flex items-center justify-center gap-3 px-4 py-2.5 border border-gray-200 dark:border-zinc-700 rounded-xl bg-white dark:bg-ml-dark-surface hover:bg-gray-50 dark:hover:bg-zinc-800 transition-colors text-sm font-medium text-gray-700 dark:text-zinc-200"
              >
                <svg width="18" height="18" viewBox="0 0 24 24" aria-hidden="true">
                  <path d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z" fill="#4285F4"/>
                  <path d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" fill="#34A853"/>
                  <path d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z" fill="#FBBC05"/>
                  <path d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z" fill="#EA4335"/>
                </svg>
                Continuar con Google
              </button>
            </>
          )}
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
