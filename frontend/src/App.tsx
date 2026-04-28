import React, { useEffect, useState } from 'react'
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom'
import { useAuthStore } from '@/store/auth'
import { apiClient } from '@/services/api'
import { Login } from '@/pages/Login'
import { Dashboard } from '@/pages/Dashboard'
import '@/styles/index.css'

const ProtectedRoute: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const { isAuthenticated } = useAuthStore()
  return isAuthenticated ? <>{children}</> : <Navigate to="/login" />
}

export function App() {
  const { setUser, token } = useAuthStore()
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const loadUser = async () => {
      if (token) {
        try {
          const user = await apiClient.getCurrentUser()
          setUser(user)
        } catch (err) {
          // Token inválido
          useAuthStore.setState({ token: null, isAuthenticated: false })
        }
      }
      setLoading(false)
    }

    loadUser()
  }, [token, setUser])

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="text-gray-600">Cargando...</div>
      </div>
    )
  }

  return (
    <Router>
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route
          path="/dashboard"
          element={
            <ProtectedRoute>
              <Dashboard />
            </ProtectedRoute>
          }
        />
        <Route path="/" element={<Navigate to="/dashboard" />} />
      </Routes>
    </Router>
  )
}
