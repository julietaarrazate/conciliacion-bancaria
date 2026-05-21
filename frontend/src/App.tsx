import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { useAuthStore } from './store/auth'
import LoginPage from './pages/Login'
import DashboardPage from './pages/Dashboard'
import AccountsPage from './pages/Accounts'
import ReconciliationPage from './pages/Reconciliation'
import ClientesPage from './pages/Clientes'

function PrivateRoute({ children }: { children: React.ReactNode }) {
  const token = useAuthStore((s) => s.token)
  return token ? <>{children}</> : <Navigate to="/login" replace />
}

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route path="/" element={<PrivateRoute><DashboardPage /></PrivateRoute>} />
        <Route path="/accounts" element={<PrivateRoute><AccountsPage /></PrivateRoute>} />
        <Route path="/clientes" element={<PrivateRoute><ClientesPage /></PrivateRoute>} />
        <Route path="/reconciliation/:id" element={<PrivateRoute><ReconciliationPage /></PrivateRoute>} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  )
}
