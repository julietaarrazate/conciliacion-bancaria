import React, { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { apiClient } from '@/services/api'
import { useAuthStore } from '@/store/auth'

export const Login: React.FC = () => {
  const navigate = useNavigate()
  const { setUser, setToken } = useAuthStore()

  const [formData, setFormData] = useState({
    email: '',
    password: ''
  })
  const [showPassword, setShowPassword] = useState(false)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const [waking, setWaking] = useState(false)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')
    setLoading(true)
    try {
      const response = await apiClient.login(formData.email, formData.password)
      setUser(response.user)
      setToken(response.access_token)
      navigate('/dashboard')
    } catch (err: any) {
      const detail = err.response?.data?.detail
      const code = err.response?.status
      if (code === 401) {
        setError('Email o contraseña incorrectos')
      } else if (err.code === 'ERR_NETWORK' || !err.response) {
        setWaking(true)
        setError('')
        // Render free tier duerme — reintentamos automáticamente
        await new Promise(r => setTimeout(r, 30000))
        setWaking(false)
        try {
          const response2 = await apiClient.login(formData.email, formData.password)
          setUser(response2.user)
          setToken(response2.access_token)
          navigate('/dashboard')
          return
        } catch {
          setError('El servidor tardó en responder. Intentá de nuevo en unos segundos.')
        }
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
          <div className="inline-flex items-center justify-center w-16 h-16 rounded-2xl bg-ml-yellow dark:bg-ml-dark-surface dark:border dark:border-ml-green/40 mb-4 dark:shadow-green-glow">
            <span className="text-2xl dark:hidden">💰</span>
            <span className="text-2xl hidden dark:inline font-mono text-ml-green">$_</span>
          </div>
          <h1 className="text-2xl font-bold text-ml-text dark:text-white tracking-tight">
            Conciliación Bancaria
          </h1>
          <p className="text-xs text-ml-text-soft dark:text-zinc-500 mt-1 font-mono dark:tracking-widest uppercase">
            <span className="dark:text-ml-green/70">▸</span> Julieta Arrazate
          </p>
        </div>

        {/* Card */}
        <div className="bg-white dark:bg-ml-dark-surface rounded-2xl p-6 shadow-sm border border-gray-100 dark:border-ml-dark-border dark:shadow-none">

          {waking && (
            <div className="mb-4 p-3 bg-amber-50 border border-amber-200 rounded-lg text-amber-700 text-sm dark:bg-amber-950/30 dark:border-amber-800/40 dark:text-amber-400 flex items-center gap-2">
              <span className="animate-spin text-base">⏳</span>
              <span>Servidor despertando… reintentando en 30 seg</span>
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
                  onClick={() => setShowPassword((s) => !s)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600 dark:text-zinc-500 dark:hover:text-ml-green transition-colors"
                  tabIndex={-1}
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
          </form>
        </div>

        <p className="text-center text-xs text-gray-400 dark:text-zinc-700 mt-6 font-mono">
          © 2026 Julieta Arrazate
        </p>
      </div>
    </div>
  )
}
