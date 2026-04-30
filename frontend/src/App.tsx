import React, { useEffect, useState } from 'react'
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom'
import { useAuthStore } from '@/store/auth'
import { apiClient } from '@/services/api'
import { Login } from '@/pages/Login'
import { Dashboard } from '@/pages/Dashboard'
import { Historial } from '@/pages/Historial'
import { Auditoria } from '@/pages/Auditoria'
import { Usuarios } from '@/pages/Usuarios'
import { Movimientos } from '@/pages/Movimientos'
import { Layout } from '@/components/Layout'
import '@/styles/index.css'

const ProtectedRoute: React.FC<{
  children: React.ReactNode
  permission?: string
}> = ({ children, permission }) => {
  const { isAuthenticated, hasPermission } = useAuthStore()
  if (!isAuthenticated) return <Navigate to="/login" replace />
  if (permission && !hasPermission(permission)) {
    return <Navigate to="/dashboard" replace />
  }
  return <>{children}</>
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
        } catch {
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
          element={
            <ProtectedRoute>
              <Layout />
            </ProtectedRoute>
          }
        >
          <Route path="/dashboard" element={<Dashboard />} />
          <Route path="/movimientos" element={<Movimientos />} />
          <Route path="/historial" element={<Historial />} />
          <Route
            path="/auditoria"
            element={
              <ProtectedRoute permission="view_audit">
                <Auditoria />
              </ProtectedRoute>
            }
          />
          <Route
            path="/usuarios"
            element={
              <ProtectedRoute permission="manage_users">
                <Usuarios />
              </ProtectedRoute>
            }
          />
        </Route>

        <Route path="/" element={<Navigate to="/dashboard" replace />} />
        <Route path="*" element={<Navigate to="/dashboard" replace />} />
      </Routes>
    </Router>
  )
}
