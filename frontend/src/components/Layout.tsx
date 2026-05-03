import React from 'react'
import { NavLink, Outlet, useNavigate } from 'react-router-dom'
import { useAuthStore } from '@/store/auth'
import { useThemeStore } from '@/store/theme'
import { UserRole } from '@/types'
import { ThemeToggle } from './ThemeToggle'

interface NavItem {
  to: string
  label: string
  icon: string
  permission?: string
  roles?: UserRole[]
}

const navItems: NavItem[] = [
  { to: '/dashboard', label: 'Conciliar', icon: '⚡' },
  { to: '/clientes', label: 'Clientes', icon: '📁' },
  { to: '/bulk', label: 'Bulk', icon: '📦' },
  { to: '/movimientos', label: 'Movim.', icon: '📊' },
  { to: '/historial', label: 'Historial', icon: '📋' },
  { to: '/auditoria', label: 'Audit.', icon: '🔍', permission: 'view_audit' },
  { to: '/usuarios', label: 'Usuarios', icon: '👥', permission: 'manage_users' },
  { to: '/perfil', label: 'Mi perfil', icon: '👤' }
]

export const Layout: React.FC = () => {
  const navigate = useNavigate()
  const { user, logout, hasPermission } = useAuthStore()
  const { theme, toggle } = useThemeStore()

  const handleLogout = () => {
    if (!confirm('¿Querés cerrar sesión?')) return
    logout()
    navigate('/login')
  }

  const visibleItems = navItems.filter(
    (item) => !item.permission || hasPermission(item.permission)
  )

  return (
    <div className="flex flex-col md:flex-row h-screen bg-ml-gray-bg dark:bg-slate-900 overflow-hidden">
      {/* Header mobile */}
      <header className="md:hidden bg-ml-yellow flex items-center justify-between px-4 py-2.5 z-30 shadow">
        <div>
          <p className="font-bold text-sm text-ml-text dark:text-ml-green font-mono">Conciliación</p>
          <p className="text-[11px] text-ml-text-soft truncate max-w-[180px]">
            {user?.full_name}
          </p>
        </div>
        <div className="flex items-center gap-1">
          <button
            onClick={toggle}
            className="p-2 text-ml-text rounded-md hover:bg-ml-yellow-dark"
            aria-label="Toggle theme"
          >
            <span className="text-lg">{theme === 'light' ? '🌙' : '☀️'}</span>
          </button>
          <button
            onClick={handleLogout}
            className="p-2 text-red-700 rounded-md hover:bg-red-100"
            aria-label="Logout"
          >
            <span className="text-lg">⏻</span>
          </button>
        </div>
      </header>

      {/* Sidebar desktop */}
      <aside className="hidden md:flex w-60 bg-white dark:bg-slate-800 border-r border-gray-200 dark:border-slate-700 flex-col">
        <div className="px-5 py-4 border-b border-gray-100 dark:border-slate-700 bg-ml-yellow">
          <h1 className="text-base font-bold text-ml-text dark:text-ml-green font-mono">Conciliación</h1>
          <p className="text-xs text-ml-text-soft">Julieta Arrazate</p>
        </div>

        <nav className="flex-1 p-3 space-y-0.5 overflow-y-auto">
          {visibleItems.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              className={({ isActive }) =>
                `flex items-center gap-3 px-3 py-2.5 rounded-md text-sm font-medium transition-colors ${
                  isActive
                    ? 'bg-ml-blue text-white'
                    : 'text-ml-text dark:text-gray-300 hover:bg-ml-gray-bg dark:hover:bg-slate-700'
                }`
              }
            >
              <span className="text-base">{item.icon}</span>
              <span>{item.label}</span>
            </NavLink>
          ))}
        </nav>

        <div className="p-3 border-t border-gray-100 dark:border-slate-700 space-y-1">
          <ThemeToggle />
          <div className="px-3 py-2">
            <p className="text-sm font-medium text-ml-text dark:text-white truncate">
              {user?.full_name}
            </p>
            <p className="text-xs text-ml-text-soft dark:text-gray-400 capitalize">
              {user?.role}
            </p>
          </div>
          <button
            onClick={handleLogout}
            className="w-full text-left px-3 py-2 text-sm text-red-600 dark:text-red-400 hover:bg-red-50 dark:hover:bg-red-900/20 rounded-md transition-colors"
          >
            Cerrar sesión
          </button>
        </div>
      </aside>

      <main className="flex-1 overflow-y-auto text-ml-text dark:text-gray-100 pb-16 md:pb-0">
        <Outlet />
      </main>

      {/* Bottom nav mobile */}
      <nav className="md:hidden fixed bottom-0 left-0 right-0 bg-white dark:bg-slate-800 border-t border-gray-200 dark:border-slate-700 flex z-30">
        {visibleItems.slice(0, 5).map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            className={({ isActive }) =>
              `flex-1 flex flex-col items-center justify-center py-2 ${
                isActive
                  ? 'text-ml-blue dark:text-blue-400'
                  : 'text-ml-text-soft dark:text-gray-400'
              }`
            }
          >
            <span className="text-lg">{item.icon}</span>
            <span className="text-[10px] mt-0.5 font-medium">{item.label}</span>
          </NavLink>
        ))}
      </nav>
    </div>
  )
}
