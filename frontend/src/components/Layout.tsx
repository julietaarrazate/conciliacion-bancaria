import React from 'react'
import { NavLink, Outlet, useNavigate } from 'react-router-dom'
import { useAuthStore } from '@/store/auth'
import { UserRole } from '@/types'

interface NavItem {
  to: string
  label: string
  permission?: string
  roles?: UserRole[]
}

const navItems: NavItem[] = [
  { to: '/dashboard', label: 'Conciliar' },
  { to: '/historial', label: 'Historial' },
  { to: '/auditoria', label: 'Auditoría', permission: 'view_audit' },
  { to: '/usuarios', label: 'Usuarios', permission: 'manage_users' }
]

export const Layout: React.FC = () => {
  const navigate = useNavigate()
  const { user, logout, hasPermission } = useAuthStore()

  const handleLogout = () => {
    logout()
    navigate('/login')
  }

  const visibleItems = navItems.filter(
    (item) => !item.permission || hasPermission(item.permission)
  )

  return (
    <div className="flex h-screen bg-gray-50">
      {/* Sidebar */}
      <aside className="w-64 bg-white border-r border-gray-200 flex flex-col">
        <div className="p-6 border-b">
          <h1 className="text-lg font-bold text-gray-900">Conciliación</h1>
          <p className="text-xs text-gray-500">Caneland SA</p>
        </div>

        <nav className="flex-1 p-4 space-y-1">
          {visibleItems.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              className={({ isActive }) =>
                `block px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
                  isActive
                    ? 'bg-primary-100 text-primary-700'
                    : 'text-gray-700 hover:bg-gray-100'
                }`
              }
            >
              {item.label}
            </NavLink>
          ))}
        </nav>

        <div className="p-4 border-t">
          <div className="mb-2">
            <p className="text-sm font-medium text-gray-900">{user?.full_name}</p>
            <p className="text-xs text-gray-500 capitalize">{user?.role}</p>
          </div>
          <button
            onClick={handleLogout}
            className="w-full text-sm text-red-600 hover:text-red-700"
          >
            Cerrar sesión
          </button>
        </div>
      </aside>

      {/* Main content */}
      <main className="flex-1 overflow-y-auto">
        <Outlet />
      </main>
    </div>
  )
}
