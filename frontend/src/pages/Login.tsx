import React, { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { apiClient } from '@/services/api'
import { useAuthStore } from '@/store/auth'
import { Button } from '@/components/Button'
import { Input } from '@/components/Input'

export const Login: React.FC = () => {
  const navigate = useNavigate()
  const { setUser, setToken } = useAuthStore()

  const [formData, setFormData] = useState({ email: '', password: '' })
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setFormData({
      ...formData,
      [e.target.name]: e.target.value
    })
  }

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
    <div className="min-h-screen bg-gradient-to-br from-primary-600 to-primary-900 flex items-center justify-center p-4">
      <div className="card w-full max-w-md">
        <h1 className="text-3xl font-bold mb-2 text-gray-800">Conciliación Bancaria</h1>
        <p className="text-gray-600 mb-8">Ingresa tus credenciales</p>

        {error && (
          <div className="mb-4 p-3 bg-red-100 border border-red-400 rounded text-red-700 text-sm">
            {error}
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-4">
          <Input
            label="Email"
            type="email"
            name="email"
            placeholder="tu@email.com"
            value={formData.email}
            onChange={handleInputChange}
            required
          />

          <Input
            label="Contraseña"
            type="password"
            name="password"
            placeholder="••••••••"
            value={formData.password}
            onChange={handleInputChange}
            required
          />

          <Button
            type="submit"
            variant="primary"
            loading={loading}
            className="w-full"
          >
            Ingresar
          </Button>
        </form>

        <div className="mt-6 pt-6 border-t">
          <p className="text-sm text-gray-600 text-center">
            ¿No tienes cuenta? <a href="/register" className="text-primary-600 hover:underline">Regístrate</a>
          </p>
        </div>
      </div>
    </div>
  )
}
