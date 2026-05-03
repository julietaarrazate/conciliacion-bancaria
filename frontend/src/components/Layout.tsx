import React, { useEffect, useState } from 'react'
import { NavLink, Outlet, useNavigate } from 'react-router-dom'
import { useAuthStore } from '@/store/auth'
import { useThemeStore } from '@/store/theme'
import { useOrgStore } from '@/store/org'
import { apiClient } from '@/services/api'
import { UserRole } from '@/types'
import { ThemeToggle } from './ThemeToggle'

interface NavItem {
  to: string
  label: string
  icon: string
  permission?: string
}

const navItems: NavItem[] = [
  { to: '/dashboard',      label: 'Conciliar',  icon: '⚡' },
  { to: '/clientes',       label: 'Clientes',   icon: '📁' },
  { to: '/bulk',           label: 'Bulk',       icon: '📦' },
  { to: '/movimientos',    label: 'Movimientos',icon: '📊' },
  { to: '/historial',      label: 'Historial',  icon: '📋' },
  { to: '/auditoria',      label: 'Auditoría',  icon: '🔍', permission: 'view_audit' },
  { to: '/usuarios',       label: 'Usuarios',   icon: '👥', permission: 'manage_users' },
  { to: '/organizaciones', label: 'Orgs',       icon: '🏢', permission: 'manage_users' },
  { to: '/perfil',         label: 'Mi perfil',  icon: '👤' },
]

export const Layout: React.FC = () => {
  const navigate = useNavigate()
  const { user, logout, hasPermission } = useAuthStore()
  const { theme, toggle } = useThemeStore()
  const { activeOrgId, activeOrgNombre, setActiveOrg, clearActiveOrg } = useOrgStore()
  const [orgs, setOrgs] = useState<{ id: number; nombre: string }[]>([])
  const [drawerOpen, setDrawerOpen] = useState(false)

  useEffect(() => {
    if (user?.is_superadmin) {
      apiClient.client.get('/admin/organizaciones')
        .then(r => setOrgs(r.data))
        .catch(() => {})
    }
  }, [user?.is_superadmin])

  const handleLogout = () => {
    if (!confirm('¿Querés cerrar sesión?')) return
    logout()
    navigate('/login')
  }

  const closeDrawer = () => setDrawerOpen(false)

  const visibleItems = navItems.filter(
    item => !item.permission || hasPermission(item.permission)
  )

  const NavContent = ({ onNav }: { onNav?: () => void }) => (
    <>
      <nav className="flex-1 p-3 space-y-0.5 overflow-y-auto">
        {visibleItems.map(item => (
          <NavLink
            key={item.to}
            to={item.to}
            onClick={onNav}
            className={({ isActive }) =>
              `flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm font-medium transition-all ${
                isActive
                  ? 'bg-ml-blue dark:bg-ml-green text-white dark:text-black shadow-sm'
                  : 'text-ml-text dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-slate-700'
              }`
            }
          >
            <span className="text-base">{item.icon}</span>
            <span>{item.label}</span>
          </NavLink>
        ))}
      </nav>

      <div className="p-3 border-t border-gray-100 dark:border-slate-700 space-y-2">
        {/* Org switcher — solo superadmin */}
        {user?.is_superadmin && orgs.length > 0 && (
          <div className="px-1">
            <p className="text-[10px] text-gray-400 dark:text-zinc-600 uppercase tracking-wider px-2 mb-1">Viendo org</p>
            <select
              className="input-field !py-1 !text-xs w-full"
              value={activeOrgId ?? ''}
              onChange={e => {
                const id = Number(e.target.value)
                if (!id) { clearActiveOrg(); return }
                const org = orgs.find(o => o.id === id)
                if (org) setActiveOrg(org.id, org.nombre)
              }}
            >
              <option value="">— Todas —</option>
              {orgs.map(o => (
                <option key={o.id} value={o.id}>{o.nombre}</option>
              ))}
            </select>
            {activeOrgId && (
              <p className="text-[10px] text-ml-green font-mono px-2 mt-0.5">▸ {activeOrgNombre}</p>
            )}
          </div>
        )}

        <ThemeToggle />

        <div className="px-3 py-1.5">
          <p className="text-sm font-medium dark:text-white truncate">{user?.full_name}</p>
          <p className="text-xs text-gray-400 dark:text-zinc-500">
            {user?.is_superadmin ? '⭐ superadmin' : user?.role}
          </p>
        </div>

        <button
          onClick={handleLogout}
          className="w-full text-left px-3 py-2 text-sm text-red-600 dark:text-red-400 hover:bg-red-50 dark:hover:bg-red-900/20 rounded-xl transition-colors"
        >
          ⏻ Cerrar sesión
        </button>
      </div>
    </>
  )

  return (
    <div className="flex flex-col md:flex-row h-screen bg-ml-gray-bg dark:bg-[#09090B] overflow-hidden">

      {/* ── Header mobile ─────────────────────────────── */}
      <header className="md:hidden bg-ml-yellow dark:bg-ml-dark-surface border-b border-transparent dark:border-ml-dark-border flex items-center justify-between px-4 py-2.5 z-30 shadow dark:shadow-none shrink-0">
        <button
          onClick={() => setDrawerOpen(true)}
          className="p-1.5 rounded-lg text-ml-text dark:text-ml-green hover:bg-black/5 dark:hover:bg-ml-dark-border"
          aria-label="Abrir menú"
        >
          <svg className="w-5 h-5" fill="none" stroke="currentColor" strokeWidth={2.5} viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" d="M3 6h18M3 12h18M3 18h18" />
          </svg>
        </button>

        <p className="font-bold text-sm font-mono app-title absolute left-1/2 -translate-x-1/2">
          Conciliación
        </p>

        <div className="flex items-center gap-1">
          <button onClick={toggle} className="p-1.5 rounded-lg text-ml-text dark:text-ml-green hover:bg-black/5 dark:hover:bg-ml-dark-border">
            <span className="text-base">{theme === 'light' ? '🌙' : '☀️'}</span>
          </button>
        </div>
      </header>

      {/* ── Drawer mobile ──────────────────────────────── */}
      {drawerOpen && (
        <>
          {/* Overlay */}
          <div
            className="md:hidden fixed inset-0 bg-black/50 z-40 backdrop-blur-sm"
            onClick={closeDrawer}
          />
          {/* Panel */}
          <div className="md:hidden fixed left-0 top-0 h-full w-72 bg-white dark:bg-ml-dark-surface z-50 flex flex-col shadow-2xl">
            {/* Cabecera del drawer */}
            <div className="flex items-center justify-between px-4 py-3 bg-ml-yellow dark:bg-ml-dark-card border-b border-transparent dark:border-ml-dark-border shrink-0">
              <div>
                <p className="font-bold text-sm font-mono app-title">Conciliación</p>
                <p className="text-[11px] text-ml-text-soft dark:text-zinc-500 truncate max-w-[180px]">
                  {user?.full_name}
                </p>
              </div>
              <button
                onClick={closeDrawer}
                className="p-1.5 rounded-lg text-ml-text dark:text-gray-400 hover:bg-black/10 dark:hover:bg-ml-dark-border text-lg leading-none"
              >
                ✕
              </button>
            </div>
            <NavContent onNav={closeDrawer} />
          </div>
        </>
      )}

      {/* ── Sidebar desktop ────────────────────────────── */}
      <aside className="hidden md:flex w-60 bg-white dark:bg-ml-dark-surface border-r border-gray-200 dark:border-ml-dark-border flex-col">
        <div className="px-5 py-4 border-b border-gray-100 dark:border-ml-dark-border bg-ml-yellow dark:bg-ml-dark-card">
          <h1 className="text-base font-bold font-mono app-title">Conciliación</h1>
          <p className="text-xs text-ml-text-soft dark:text-zinc-500">Julieta Arrazate</p>
        </div>
        <NavContent />
      </aside>

      {/* ── Contenido principal ────────────────────────── */}
      <main className="flex-1 overflow-y-auto text-ml-text dark:text-gray-100">
        <Outlet />
      </main>
    </div>
  )
}
