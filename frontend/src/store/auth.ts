import { create } from 'zustand'
import { User, UserRole } from '@/types'

interface AuthState {
  user: User | null
  token: string | null
  isAuthenticated: boolean

  setUser: (user: User | null) => void
  setToken: (token: string | null) => void
  logout: () => void
  hasPermission: (permission: string) => boolean
  hasRole: (role: UserRole) => boolean
}

const rolePermissions: Record<UserRole, string[]> = {
  [UserRole.ADMIN]: ['upload_files', 'reconcile', 'manage_users', 'view_audit', 'view_accounting', 'manage_finance', 'admin_accounting', 'delete_records'],
  [UserRole.OPERADOR]: ['upload_files', 'reconcile', 'manage_finance', 'view_accounting', 'delete_records'],
  [UserRole.REVISOR]: ['view_results', 'view_accounting'],
  [UserRole.AUDITOR]: ['view_audit', 'view_accounting', 'manage_finance'],
  // Contador de prueba: opera (sube, concilia, finanzas, liquidaciones) y ve
  // contabilidad + auditoría en solo lectura. SIN delete_records (no borra nada)
  // ni manage_users (no ve Usuarios/Orgs/Papelera/Actividad).
  [UserRole.CONTADOR]: ['upload_files', 'reconcile', 'manage_finance', 'view_accounting', 'view_audit'],
}

export const useAuthStore = create<AuthState>((set, get) => ({
  user: null,
  token: sessionStorage.getItem('token'),
  isAuthenticated: !!sessionStorage.getItem('token'),

  setUser: (user) => set({ user, isAuthenticated: !!user }),
  setToken: (token) => {
    set({ token, isAuthenticated: !!token })
    if (token) {
      sessionStorage.setItem('token', token)
    } else {
      sessionStorage.removeItem('token')
    }
  },

  logout: () => {
    // Revoca el token en el backend antes de limpiar el storage (best-effort).
    // No bloquea — si el servidor está caído, el logout local igual procede.
    const token = get().token || sessionStorage.getItem('token')
    if (token) {
      import('@/services/api').then(({ apiClient }) => {
        apiClient.client.post('/auth/logout').catch(() => {})
      })
    }
    set({ user: null, token: null, isAuthenticated: false })
    sessionStorage.removeItem('token')
  },

  hasPermission: (permission) => {
    const { user } = get()
    if (!user) return false
    if (user.is_superadmin) return true  // superadmin tiene todo
    const permissions = rolePermissions[user.role] || []
    return permissions.includes(permission)
  },

  hasRole: (role) => {
    const { user } = get()
    return user?.role === role
  }
}))
