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
import { Conciliaciones } from '@/pages/Conciliaciones'
import { Bulk } from '@/pages/Bulk'
import { Clientes } from '@/pages/Clientes'
import { ExtractosArchivo } from '@/pages/ExtractosArchivo'
import { Perfil } from '@/pages/Perfil'
import { Organizaciones } from '@/pages/Organizaciones'
import { Actividad } from '@/pages/Actividad'
import { Liquidaciones } from '@/pages/Liquidaciones'
import { Revision } from '@/pages/Revision'
import { Caja } from '@/pages/Caja'
import { OrdenDePago } from '@/pages/OrdenDePago'
import { Layout } from '@/components/Layout'
import { useThemeStore } from '@/store/theme'
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
  const applyTheme = useThemeStore((s) => s.applyToDocument)
  const [loading, setLoading] = useState(true)

  // Aplicar tema (light/dark) al cargar
  useEffect(() => {
    applyTheme()
  }, [applyTheme])

  // Keep-alive: ping cada 14 min para que Render no duerma
  useEffect(() => {
    const ping = () => apiClient.client.get('/health').catch(() => {})
    const id = setInterval(ping, 14 * 60 * 1000)
    return () => clearInterval(id)
  }, [])

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
          <Route path="/clientes" element={<Clientes />} />
          <Route path="/extractos-archivo" element={<ExtractosArchivo />} />
          <Route path="/bulk" element={<Bulk />} />
          <Route path="/perfil" element={<Perfil />} />
          <Route path="/liquidaciones" element={
            <ProtectedRoute permission="manage_users">
              <Liquidaciones />
            </ProtectedRoute>
          } />
          <Route path="/caja" element={<ProtectedRoute permission="reconcile"><Caja /></ProtectedRoute>} />
          <Route path="/op" element={<ProtectedRoute permission="reconcile"><OrdenDePago /></ProtectedRoute>} />
          <Route path="/revision" element={
            <ProtectedRoute permission="reconcile">
              <Revision />
            </ProtectedRoute>
          } />
          <Route path="/actividad" element={<ProtectedRoute permission="manage_users"><Actividad /></ProtectedRoute>} />
          <Route path="/organizaciones" element={
            <ProtectedRoute permission="manage_users">
              <Organizaciones />
            </ProtectedRoute>
          } />
          <Route path="/movimientos" element={<Movimientos />} />
          <Route path="/conciliaciones" element={<Conciliaciones />} />
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
