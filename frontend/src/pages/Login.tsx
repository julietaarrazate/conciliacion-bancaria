import React, { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { apiClient } from '@/services/api'
import { useAuthStore } from '@/store/auth'

export const Login: React.FC = () => {
  const navigate = useNavigate()
  const { setUser, setToken } = useAuthStore()

  const [formData, setFormData] = useState({
    email: 'admin@caneland.com',
    password: 'admin123'
  })
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
      setError(err.response?.data?.detail || 'Error en autenticación')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen bg-ml-gray-bg flex items-center justify-center p-4">
      <div className="w-full max-w-md">
        <div className="text-center mb-6">
          <div className="inline-flex items-center justify-center w-16 h-16 rounded-full bg-ml-yellow mb-3">
            <span className="text-2xl">💰</span>
          </div>
          <h1 className="text-2xl font-bold text-ml-text">Conciliación Bancaria</h1>
          <p className="text-sm text-ml-text-soft mt-1">Caneland SA</p>
        </div>

        <div className="card">
          {error && (
            <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded-md text-red-700 text-sm">
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
              />
            </div>

            <div>
              <label className="label">Contraseña</label>
              <input
                type="password"
                className="input-field"
                placeholder="••••••••"
                value={formData.password}
                onChange={(e) =>
                  setFormData({ ...formData, password: e.target.value })
                }
                required
                autoComplete="current-password"
              />
            </div>

            <button
              type="submit"
              className="btn-yellow w-full"
              disabled={loading}
            >
              {loading ? 'Ingresando...' : 'Ingresar'}
            </button>
          </form>

          <div className="mt-5 pt-5 border-t border-gray-100">
            <p className="text-xs text-ml-text-soft text-center">
              Demo: admin@caneland.com / admin123
            </p>
          </div>
        </div>
      </div>
    </div>
  )
}
