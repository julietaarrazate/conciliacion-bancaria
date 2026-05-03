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
        const apiUrl = err.config?.baseURL || 'desconocido'
        setError(
          `No se puede conectar al servidor (${apiUrl}). Verificá que el backend esté corriendo y que el celular esté en la misma red WiFi que la PC.`
        )
      } else {
        setError(detail || 'Error en autenticación')
      }
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen bg-ml-gray-bg dark:bg-slate-900 flex items-center justify-center p-4">
      <div className="w-full max-w-md">
        <div className="text-center mb-6">
          <div className="inline-flex items-center justify-center w-16 h-16 rounded-full bg-ml-yellow mb-3">
            <span className="text-2xl">💰</span>
          </div>
          <h1 className="text-2xl font-bold text-ml-text dark:text-white">
            Conciliación Bancaria
          </h1>
          <p className="text-sm text-ml-text-soft dark:text-gray-400 mt-1">
            Sistema de Conciliación Bancaria
          </p>
        </div>

        <div className="card">
          {error && (
            <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded-md text-red-700 text-sm dark:bg-red-900/20 dark:border-red-800 dark:text-red-300">
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
                onChange={(e) =>
                  setFormData({ ...formData, email: e.target.value })
                }
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
                  onChange={(e) =>
                    setFormData({ ...formData, password: e.target.value })
                  }
                  required
                  autoComplete="current-password"
                />
                <button
                  type="button"
                  onClick={() => setShowPassword((s) => !s)}
                  className="absolute right-2 top-1/2 -translate-y-1/2 px-2 py-1 text-sm text-ml-text-soft hover:text-ml-text dark:text-gray-400 dark:hover:text-white"
                  aria-label={showPassword ? 'Ocultar contraseña' : 'Mostrar contraseña'}
                  tabIndex={-1}
                >
                  {showPassword ? '🙈' : '👁️'}
                </button>
              </div>
            </div>

            <button
              type="submit"
              className="btn-yellow w-full"
              disabled={loading}
            >
              {loading ? 'Ingresando...' : 'Ingresar'}
            </button>
          </form>

        </div>
      </div>
    </div>
  )
}
