import React, { useState, useMemo } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import { apiClient } from '@/services/api'

export const RestablecerPassword: React.FC = () => {
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const token = searchParams.get('token') || ''

  const [password, setPassword] = useState('')
  const [confirm, setConfirm] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [ok, setOk] = useState(false)

  const validacion = useMemo(() => {
    if (!password) return null
    if (password.length < 8) return 'Mínimo 8 caracteres'
    if (confirm && password !== confirm) return 'No coinciden'
    return null
  }, [password, confirm])

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')
    if (validacion) {
      setError(validacion)
      return
    }
    if (password !== confirm) {
      setError('Las contraseñas no coinciden')
      return
    }
    setLoading(true)
    try {
      await apiClient.resetPassword(token, password)
      setOk(true)
      setTimeout(() => navigate('/login'), 2500)
    } catch (err: any) {
      const detail = err.response?.data?.detail
      const code = err.response?.status
      if (code === 400) {
        setError(detail || 'El link expiró o ya fue usado. Pedí uno nuevo.')
      } else if (code === 429) {
        setError('Demasiados intentos. Esperá unos minutos.')
      } else if (err.code === 'ERR_NETWORK' || !err.response) {
        setError('No se pudo conectar al servidor. Intentá de nuevo.')
      } else {
        setError('Algo salió mal. Intentá de nuevo.')
      }
    } finally {
      setLoading(false)
    }
  }

  if (!token) {
    return (
      <div className="min-h-screen bg-ml-gray-bg dark:bg-ml-dark-bg flex items-center justify-center p-4">
        <div className="w-full max-w-sm text-center">
          <div className="bg-white dark:bg-ml-dark-surface rounded-2xl p-6 shadow-sm border border-gray-100 dark:border-ml-dark-border">
            <p className="text-red-700 dark:text-red-400 text-sm mb-4">
              Link inválido. Faltan datos en la URL.
            </p>
            <Link to="/recuperar-password" className="btn-yellow inline-block px-4 py-2 text-sm">
              Pedir un link nuevo
            </Link>
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-ml-gray-bg dark:bg-ml-dark-bg flex items-center justify-center p-4">
      <div className="w-full max-w-sm">

        <div className="text-center mb-8">
          <div className="inline-flex items-center justify-center w-16 h-16 rounded-2xl bg-ml-yellow dark:bg-ml-dark-surface dark:border dark:border-ml-green/40 mb-4 dark:shadow-green-glow">
            <span className="text-2xl dark:hidden">🔒</span>
            <span className="text-2xl hidden dark:inline font-mono text-ml-green">$_</span>
          </div>
          <h1 className="text-2xl font-bold text-ml-text dark:text-white tracking-tight">
            Nueva contraseña
          </h1>
          <p className="text-xs text-ml-text-soft dark:text-zinc-500 mt-1">
            Elegí una contraseña fuerte
          </p>
        </div>

        <div className="bg-white dark:bg-ml-dark-surface rounded-2xl p-6 shadow-sm border border-gray-100 dark:border-ml-dark-border dark:shadow-none">

          {ok ? (
            <div className="space-y-4">
              <div className="p-4 bg-emerald-50 border border-emerald-200 rounded-lg text-emerald-800 text-sm dark:bg-emerald-950/30 dark:border-emerald-800/40 dark:text-emerald-400 text-center">
                <div className="text-2xl mb-2">✓</div>
                <div className="font-semibold mb-1">Listo</div>
                Contraseña actualizada. Redirigiendo al login...
              </div>
            </div>
          ) : (
            <>
              {error && (
                <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded-lg text-red-700 text-sm dark:bg-red-950/40 dark:border-red-800/50 dark:text-red-400">
                  {error}
                </div>
              )}

              <form onSubmit={handleSubmit} className="space-y-4">
                <div>
                  <label className="label">Nueva contraseña</label>
                  <div className="relative">
                    <input
                      type={showPassword ? 'text' : 'password'}
                      className="input-field pr-12"
                      placeholder="Mínimo 8 caracteres"
                      value={password}
                      onChange={(e) => setPassword(e.target.value)}
                      required
                      minLength={8}
                      autoComplete="new-password"
                      autoFocus
                    />
                    <button
                      type="button"
                      onPointerDown={(e) => { e.preventDefault(); setShowPassword((s) => !s) }}
                      className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600 dark:text-zinc-500 dark:hover:text-ml-green transition-colors p-1"
                      tabIndex={-1}
                      aria-label={showPassword ? 'Ocultar' : 'Mostrar'}
                    >
                      {showPassword ? '🙈' : '👁️'}
                    </button>
                  </div>
                </div>

                <div>
                  <label className="label">Repetir contraseña</label>
                  <input
                    type={showPassword ? 'text' : 'password'}
                    className="input-field"
                    placeholder="Igual a la anterior"
                    value={confirm}
                    onChange={(e) => setConfirm(e.target.value)}
                    required
                    autoComplete="new-password"
                  />
                </div>

                {validacion && (
                  <p className="text-xs text-amber-700 dark:text-amber-500">{validacion}</p>
                )}

                <button
                  type="submit"
                  className="btn-yellow w-full mt-2 py-3 text-base disabled:opacity-50"
                  disabled={loading || !password || !confirm || !!validacion}
                >
                  {loading
                    ? <span className="font-mono tracking-widest">guardando...</span>
                    : 'Cambiar contraseña'}
                </button>
              </form>

              <div className="mt-6 text-center">
                <Link
                  to="/login"
                  className="text-xs text-ml-text-soft dark:text-zinc-500 hover:text-ml-text dark:hover:text-ml-green transition-colors"
                >
                  ← Volver al login
                </Link>
              </div>
            </>
          )}
        </div>

        <p className="text-center text-xs text-gray-400 dark:text-zinc-700 mt-6 font-mono">
          © 2026 Julieta Arrazate
        </p>
      </div>
    </div>
  )
}
