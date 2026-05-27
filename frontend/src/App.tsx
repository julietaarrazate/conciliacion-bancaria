import React, { useEffect, useState, lazy, Suspense } from 'react'
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom'
import { useAuthStore } from '@/store/auth'
import { apiClient } from '@/services/api'
import { Login } from '@/pages/Login'
import { RecuperarPassword } from '@/pages/RecuperarPassword'
import { RestablecerPassword } from '@/pages/RestablecerPassword'
import { Layout } from '@/components/Layout'
import { useThemeStore } from '@/store/theme'
import '@/styles/index.css'

// Lazy-loaded routes: cada pagina baja sola al navegar, no en el bundle inicial.
// Login y password reset quedan eager para que el primer paint sea instantaneo.
const lazyPage = (loader: () => Promise<any>, name: string) =>
  lazy(() => loader().then((m) => ({ default: m[name] })))

const Resumen           = lazyPage(() => import('@/pages/Resumen'),           'Resumen')
const EstadoCuenta      = lazyPage(() => import('@/pages/EstadoCuenta'),      'EstadoCuenta')
const Dashboard         = lazyPage(() => import('@/pages/Dashboard'),         'Dashboard')
const Historial         = lazyPage(() => import('@/pages/Historial'),         'Historial')
const Auditoria         = lazyPage(() => import('@/pages/Auditoria'),         'Auditoria')
const Usuarios          = lazyPage(() => import('@/pages/Usuarios'),          'Usuarios')
const Movimientos       = lazyPage(() => import('@/pages/Movimientos'),       'Movimientos')
const Conciliaciones    = lazyPage(() => import('@/pages/Conciliaciones'),    'Conciliaciones')
const Clientes          = lazyPage(() => import('@/pages/Clientes'),          'Clientes')
const ExtractosArchivo  = lazyPage(() => import('@/pages/ExtractosArchivo'),  'ExtractosArchivo')
const Perfil            = lazyPage(() => import('@/pages/Perfil'),            'Perfil')
const Organizaciones    = lazyPage(() => import('@/pages/Organizaciones'),    'Organizaciones')
const Actividad         = lazyPage(() => import('@/pages/Actividad'),         'Actividad')
const Liquidaciones     = lazyPage(() => import('@/pages/Liquidaciones'),     'Liquidaciones')
const Revision          = lazyPage(() => import('@/pages/Revision'),          'Revision')
const Caja              = lazyPage(() => import('@/pages/Caja'),              'Caja')
const OrdenDePago       = lazyPage(() => import('@/pages/OrdenDePago'),       'OrdenDePago')
const Contabilidad      = lazyPage(() => import('@/pages/Contabilidad'),      'Contabilidad')
const Cheques           = lazyPage(() => import('@/pages/Cheques'),           'Cheques')
const PagosGastos       = lazyPage(() => import('@/pages/PagosGastos'),       'PagosGastos')
const Papelera          = lazyPage(() => import('@/pages/Papelera'),          'Papelera')
const Compartir         = lazyPage(() => import('@/pages/Compartir'),         'Compartir')
const FlujoCaja         = lazyPage(() => import('@/pages/FlujoCaja'),         'FlujoCaja')
const PaginaPublica     = lazyPage(() => import('@/pages/PaginaPublica'),     'PaginaPublica')
const Privacidad        = lazyPage(() => import('@/pages/Privacidad'),        'Privacidad')
const Terminos          = lazyPage(() => import('@/pages/Terminos'),          'Terminos')
const Landing           = lazyPage(() => import('@/pages/Landing'),           'Landing')

const PageFallback: React.FC = () => (
  <div className="flex items-center justify-center min-h-[200px] p-8">
    <div className="text-sm text-gray-400 dark:text-zinc-500 font-mono">cargando...</div>
  </div>
)

const RootRoute: React.FC = () => {
  const { isAuthenticated } = useAuthStore()
  return isAuthenticated ? <Navigate to="/dashboard" replace /> : <Landing />
}

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
      <Suspense fallback={<PageFallback />}>
        <Routes>
          <Route path="/login" element={<Login />} />
          <Route path="/recuperar-password" element={<RecuperarPassword />} />
          <Route path="/restablecer-password" element={<RestablecerPassword />} />
          <Route path="/p/:token" element={<PaginaPublica />} />
          <Route path="/privacidad" element={<Privacidad />} />
          <Route path="/terminos" element={<Terminos />} />
          <Route path="/landing" element={<Landing />} />

          <Route
            element={
              <ProtectedRoute>
                <Layout />
              </ProtectedRoute>
            }
          >
            <Route path="/dashboard" element={<Dashboard />} />
            <Route path="/resumen" element={<Resumen />} />
            <Route path="/flujo-de-caja" element={<FlujoCaja />} />
            <Route path="/clientes" element={<Clientes />} />
            <Route path="/clientes/:id/estado-cuenta" element={<EstadoCuenta />} />
            <Route path="/extractos-archivo" element={<ExtractosArchivo />} />
            <Route path="/bulk" element={<Navigate to="/dashboard" replace />} />
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
            <Route path="/contabilidad" element={<ProtectedRoute permission="manage_users"><Contabilidad /></ProtectedRoute>} />
            <Route path="/cheques" element={<ProtectedRoute permission="reconcile"><Cheques /></ProtectedRoute>} />
            <Route path="/pagos-gastos" element={<ProtectedRoute permission="reconcile"><PagosGastos /></ProtectedRoute>} />
            <Route path="/papelera" element={<ProtectedRoute permission="manage_users"><Papelera /></ProtectedRoute>} />
            <Route path="/compartir" element={<Compartir />} />
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

          <Route path="/" element={<RootRoute />} />
          <Route path="*" element={<Navigate to="/dashboard" replace />} />
        </Routes>
      </Suspense>
    </Router>
  )
}
