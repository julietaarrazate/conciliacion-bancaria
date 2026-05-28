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
  [UserRole.ADMIN]: ['upload_files', 'reconcile', 'manage_users', 'view_audit', 'view_accounting', 'manage_finance', 'admin_accounting'],
  [UserRole.OPERADOR]: ['upload_files', 'reconcile', 'manage_finance', 'view_accounting'],
  [UserRole.REVISOR]: ['view_results', 'view_accounting'],
  [UserRole.AUDITOR]: ['view_audit', 'view_accounting', 'manage_finance'],
}

export const useAuthStore = create<AuthState>((set, get) => ({
  user: null,
  token: localStorage.getItem('token'),
  isAuthenticated: !!localStorage.getItem('token'),

  setUser: (user) => set({ user, isAuthenticated: !!user }),
  setToken: (token) => {
    set({ token, isAuthenticated: !!token })
    if (token) {
      localStorage.setItem('token', token)
    } else {
      localStorage.removeItem('token')
    }
  },

  logout: () => {
    // Revoca el token en el backend antes de limpiar el storage (best-effort).
    // No bloquea — si el servidor está caído, el logout local igual procede.
    const token = get().token || localStorage.getItem('token')
    if (token) {
      import('@/services/api').then(({ apiClient }) => {
        apiClient.client.post('/auth/logout').catch(() => {})
      })
    }
    set({ user: null, token: null, isAuthenticated: false })
    localStorage.removeItem('token')
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
