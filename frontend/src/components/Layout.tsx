import React, { useEffect, useState, useCallback } from 'react'
import { NavLink, Outlet, useNavigate, useLocation } from 'react-router-dom'
import { useAuthStore } from '@/store/auth'
import { useThemeStore } from '@/store/theme'
import { useOrgStore } from '@/store/org'
import { apiClient } from '@/services/api'
import { ThemeToggle } from './ThemeToggle'
import { CuadraLogo } from './CuadraLogo'
import { Toaster } from './Toaster'
import { AppLockGuard } from './AppLockGuard'
import { ConfirmDialog } from './ConfirmDialog'
import { confirmDialog } from '@/store/confirm'
import { SearchModal } from './SearchModal'

// ── SVG Icons (Heroicons outline style) ──────────────────────
const Icon = {
  Bolt:    () => <svg className="w-4 h-4" fill="none" stroke="currentColor" strokeWidth={1.8} viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" d="M3.75 13.5l10.5-11.25L12 10.5h8.25L9.75 21.75 12 13.5H3.75z"/></svg>,
  Folder:  () => <svg className="w-4 h-4" fill="none" stroke="currentColor" strokeWidth={1.8} viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" d="M2.25 12.75V12A2.25 2.25 0 014.5 9.75h15A2.25 2.25 0 0121.75 12v.75m-8.69-6.44l-2.12-2.12a1.5 1.5 0 00-1.061-.44H4.5A2.25 2.25 0 002.25 6v12a2.25 2.25 0 002.25 2.25h15A2.25 2.25 0 0021.75 18V9a2.25 2.25 0 00-2.25-2.25h-5.379a1.5 1.5 0 01-1.06-.44z"/></svg>,
  Stack:   () => <svg className="w-4 h-4" fill="none" stroke="currentColor" strokeWidth={1.8} viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" d="M6.429 9.75L2.25 12l4.179 2.25m0-4.5l5.571 3 5.571-3m-11.142 0L2.25 7.5 12 2.25l9.75 5.25-4.179 2.25m0 0L21.75 12l-4.179 2.25m0 0l4.179 2.25L12 21.75 2.25 16.5l4.179-2.25m11.142 0l-5.571 3-5.571-3"/></svg>,
  Chart:   () => <svg className="w-4 h-4" fill="none" stroke="currentColor" strokeWidth={1.8} viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" d="M3 13.125C3 12.504 3.504 12 4.125 12h2.25c.621 0 1.125.504 1.125 1.125v6.75C7.5 20.496 6.996 21 6.375 21h-2.25A1.125 1.125 0 013 19.875v-6.75zM9.75 8.625c0-.621.504-1.125 1.125-1.125h2.25c.621 0 1.125.504 1.125 1.125v11.25c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 01-1.125-1.125V8.625zM16.5 4.125c0-.621.504-1.125 1.125-1.125h2.25C20.496 3 21 3.504 21 4.125v15.75c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 01-1.125-1.125V4.125z"/></svg>,
  List:    () => <svg className="w-4 h-4" fill="none" stroke="currentColor" strokeWidth={1.8} viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" d="M8.25 6.75h12M8.25 12h12m-12 5.25h12M3.75 6.75h.007v.008H3.75V6.75zm.375 0a.375.375 0 11-.75 0 .375.375 0 01.75 0zM3.75 12h.007v.008H3.75V12zm.375 0a.375.375 0 11-.75 0 .375.375 0 01.75 0zm-.375 5.25h.007v.008H3.75v-.008zm.375 0a.375.375 0 11-.75 0 .375.375 0 01.75 0z"/></svg>,
  Search:  () => <svg className="w-4 h-4" fill="none" stroke="currentColor" strokeWidth={1.8} viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" d="M21 21l-5.197-5.197m0 0A7.5 7.5 0 105.196 15.803a7.5 7.5 0 0010.607 10.607z"/></svg>,
  Users:   () => <svg className="w-4 h-4" fill="none" stroke="currentColor" strokeWidth={1.8} viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" d="M15 19.128a9.38 9.38 0 002.625.372 9.337 9.337 0 004.121-.952 4.125 4.125 0 00-7.533-2.493M15 19.128v-.003c0-1.113-.285-2.16-.786-3.07M15 19.128v.106A12.318 12.318 0 018.624 21c-2.331 0-4.512-.645-6.374-1.766l-.001-.109a6.375 6.375 0 0111.964-3.07M12 6.375a3.375 3.375 0 11-6.75 0 3.375 3.375 0 016.75 0zm8.25 2.25a2.625 2.625 0 11-5.25 0 2.625 2.625 0 015.25 0z"/></svg>,
  Activity: () => <svg className="w-4 h-4" fill="none" stroke="currentColor" strokeWidth={1.8} viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" d="M3 13.5l4-4 4 4 4-4.5 3.5 4"/>  </svg>,
  Building:() => <svg className="w-4 h-4" fill="none" stroke="currentColor" strokeWidth={1.8} viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" d="M3.75 21h16.5M4.5 3h15M5.25 3v18m13.5-18v18M9 6.75h1.5m-1.5 3h1.5m-1.5 3h1.5m3-6H15m-1.5 3H15m-1.5 3H15M9 21v-3.375c0-.621.504-1.125 1.125-1.125h3.75c.621 0 1.125.504 1.125 1.125V21"/></svg>,
  User:    () => <svg className="w-4 h-4" fill="none" stroke="currentColor" strokeWidth={1.8} viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" d="M15.75 6a3.75 3.75 0 11-7.5 0 3.75 3.75 0 017.5 0zM4.501 20.118a7.5 7.5 0 0114.998 0A17.933 17.933 0 0112 21.75c-2.676 0-5.216-.584-7.499-1.632z"/></svg>,
  Logout:  () => <svg className="w-4 h-4" fill="none" stroke="currentColor" strokeWidth={1.8} viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" d="M15.75 9V5.25A2.25 2.25 0 0013.5 3h-6a2.25 2.25 0 00-2.25 2.25v13.5A2.25 2.25 0 007.5 21h6a2.25 2.25 0 002.25-2.25V15M12 9l-3 3m0 0l3 3m-3-3h12.75"/></svg>,
  Menu:    () => <svg className="w-5 h-5" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" d="M3.75 6.75h16.5M3.75 12h16.5m-16.5 5.25h16.5"/></svg>,
  Sun:     () => <svg className="w-4 h-4" fill="none" stroke="currentColor" strokeWidth={1.8} viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" d="M12 3v2.25m6.364.386l-1.591 1.591M21 12h-2.25m-.386 6.364l-1.591-1.591M12 18.75V21m-4.773-4.227l-1.591 1.591M5.25 12H3m4.227-4.773L5.636 5.636M15.75 12a3.75 3.75 0 11-7.5 0 3.75 3.75 0 017.5 0z"/></svg>,
  Moon:    () => <svg className="w-4 h-4" fill="none" stroke="currentColor" strokeWidth={1.8} viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" d="M21.752 15.002A9.718 9.718 0 0118 15.75c-5.385 0-9.75-4.365-9.75-9.75 0-1.33.266-2.597.748-3.752A9.753 9.753 0 003 11.25C3 16.635 7.365 21 12.75 21a9.753 9.753 0 009.002-5.998z"/></svg>,
  Close:   () => <svg className="w-4 h-4" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12"/></svg>,
  Wallet:  () => <svg className="w-4 h-4" fill="none" stroke="currentColor" strokeWidth={1.8} viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" d="M21 12a2.25 2.25 0 00-2.25-2.25H15a3 3 0 11-6 0H5.25A2.25 2.25 0 003 12m18 0v6a2.25 2.25 0 01-2.25 2.25H5.25A2.25 2.25 0 013 18v-6m18 0V9M3 12V9m18 0a2.25 2.25 0 00-2.25-2.25H5.25A2.25 2.25 0 003 9m18 0V6a2.25 2.25 0 00-2.25-2.25H5.25A2.25 2.25 0 003 6v3"/>  </svg>,
  Flag:    () => <svg className="w-4 h-4" fill="none" stroke="currentColor" strokeWidth={1.8} viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" d="M3 3v1.5M3 21v-6m0 0l2.77-.693a9 9 0 016.208.682l.108.054a9 9 0 006.086.71l3.114-.732a48.524 48.524 0 01-.005-10.499l-3.11.732a9 9 0 01-6.085-.711l-.108-.054a9 9 0 00-6.208-.682L3 4.5M3 15V4.5"/></svg>,
  Check:   () => <svg className="w-4 h-4" fill="none" stroke="currentColor" strokeWidth={1.8} viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" d="M9 12.75L11.25 15 15 9.75M21 12a9 9 0 11-18 0 9 9 0 0118 0z"/></svg>,
  Trash:   () => <svg className="w-4 h-4" fill="none" stroke="currentColor" strokeWidth={1.8} viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" d="M14.74 9l-.346 9m-4.788 0L9.26 9m9.968-3.21c.342.052.682.107 1.022.166m-1.022-.165L18.16 19.673a2.25 2.25 0 01-2.244 2.077H8.084a2.25 2.25 0 01-2.244-2.077L4.772 5.79m14.456 0a48.108 48.108 0 00-3.478-.397m-12 .562c.34-.059.68-.114 1.022-.165m0 0a48.11 48.11 0 013.478-.397m7.5 0v-.916c0-1.18-.91-2.164-2.09-2.201a51.964 51.964 0 00-3.32 0c-1.18.037-2.09 1.022-2.09 2.201v.916m7.5 0a48.667 48.667 0 00-7.5 0"/></svg>,
  Bell:    () => <svg className="w-4 h-4" fill="none" stroke="currentColor" strokeWidth={1.8} viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" d="M14.857 17.082a23.848 23.848 0 005.454-1.31A8.967 8.967 0 0118 9.75v-.7V9A6 6 0 006 9v.75a8.967 8.967 0 01-2.312 6.022c1.733.64 3.56 1.085 5.455 1.31m5.714 0a24.255 24.255 0 01-5.714 0m5.714 0a3 3 0 11-5.714 0"/></svg>,
}

const navItems = [
  { to: '/resumen',        label: 'Resumen',       Icon: Icon.Chart },
  { to: '/flujo-de-caja',  label: 'Flujo de Caja', Icon: Icon.Activity },
  { to: '/dashboard',      label: 'Conciliar',     Icon: Icon.Bolt },
  { to: '/clientes',       label: 'Clientes',      Icon: Icon.Folder },
  { to: '/extractos-archivo', label: 'Extractos',  Icon: Icon.Folder },
  { to: '/movimientos',    label: 'Movimientos',   Icon: Icon.Chart },
  { to: '/conciliaciones', label: 'Conciliaciones', Icon: Icon.Check },
  { to: '/historial',      label: 'Historial',     Icon: Icon.List },
  { to: '/cheques',       label: 'Cheques',     Icon: Icon.Check,  permission: 'reconcile' },
  { to: '/pagos-gastos',  label: 'Pagos/Gastos', Icon: Icon.Chart, permission: 'reconcile' },
  { to: '/caja',          label: 'Caja',        Icon: Icon.Wallet, permission: 'reconcile' },
  { to: '/op',            label: 'Nueva OP',    Icon: Icon.Bolt, permission: 'reconcile' },
  { to: '/revision',       label: 'Revisión',      Icon: Icon.Flag, permission: 'reconcile' },
  { to: '/contabilidad',   label: 'Contabilidad',  Icon: Icon.Stack, permission: 'manage_users' },
  { to: '/liquidaciones',  label: 'Liquidaciones', Icon: Icon.Chart, permission: 'manage_users' },
  { to: '/auditoria',      label: 'Auditoría',     Icon: Icon.Search, permission: 'view_audit' },
  { to: '/usuarios',       label: 'Usuarios',      Icon: Icon.Users,  permission: 'manage_users' },
  { to: '/actividad',      label: 'Actividad',   Icon: Icon.Activity, permission: 'manage_users' },
  { to: '/organizaciones', label: 'Orgs',          Icon: Icon.Building, permission: 'manage_users' },
  { to: '/papelera',       label: 'Papelera',      Icon: Icon.Trash, permission: 'manage_users' },
  { to: '/perfil',         label: 'Mi perfil',     Icon: Icon.User },
]

const bottomNavItems = [
  { to: '/resumen',   label: 'Resumen',   Icon: Icon.Chart },
  { to: '/dashboard', label: 'Conciliar', Icon: Icon.Bolt },
  { to: '/clientes',  label: 'Clientes',  Icon: Icon.Folder },
  { to: '/historial', label: 'Historial', Icon: Icon.List },
]

export const Layout: React.FC = () => {
  const navigate = useNavigate()
  const { user, logout, hasPermission } = useAuthStore()
  const { theme, toggle } = useThemeStore()
  const { activeOrgId, activeOrgNombre, setActiveOrg, clearActiveOrg } = useOrgStore()
  const [orgs, setOrgs] = useState<{ id: number; nombre: string }[]>([])
  const [drawerOpen, setDrawerOpen] = useState(false)
  const [alertasCount, setAlertasCount] = useState(0)
  const [searchOpen, setSearchOpen] = useState(false)
  const location = useLocation()
  const drawerTouchStartX = React.useRef(0)
  const drawerTouchStartY = React.useRef(0)
  const edgeTouchStartX = React.useRef(0)
  const edgeTouchStartY = React.useRef(0)

  // Swipe dentro del drawer → cerrar (deslizar a la izquierda)
  const handleDrawerTouchStart = (e: React.TouchEvent) => {
    drawerTouchStartX.current = e.touches[0].clientX
    drawerTouchStartY.current = e.touches[0].clientY
  }
  const handleDrawerTouchEnd = (e: React.TouchEvent) => {
    const dx = e.changedTouches[0].clientX - drawerTouchStartX.current
    const dy = Math.abs(e.changedTouches[0].clientY - drawerTouchStartY.current)
    if (dx < -60 && Math.abs(dx) > dy) setDrawerOpen(false)
  }

  // Swipe desde el borde izquierdo → abrir drawer
  React.useEffect(() => {
    if (drawerOpen) return
    const onStart = (e: TouchEvent) => {
      edgeTouchStartX.current = e.touches[0].clientX
      edgeTouchStartY.current = e.touches[0].clientY
    }
    const onEnd = (e: TouchEvent) => {
      const dx = e.changedTouches[0].clientX - edgeTouchStartX.current
      const dy = Math.abs(e.changedTouches[0].clientY - edgeTouchStartY.current)
      // Solo si empieza en el borde izquierdo (primeros 25px) y se desliza a la derecha
      if (edgeTouchStartX.current < 25 && dx > 50 && dx > dy) {
        setDrawerOpen(true)
      }
    }
    document.addEventListener('touchstart', onStart, { passive: true })
    document.addEventListener('touchend', onEnd, { passive: true })
    return () => {
      document.removeEventListener('touchstart', onStart)
      document.removeEventListener('touchend', onEnd)
    }
  }, [drawerOpen])

  useEffect(() => {
    if (user?.is_superadmin) {
      apiClient.client.get('/admin/organizaciones')
        .then(r => setOrgs(r.data))
        .catch(() => {})
    }
  }, [user?.is_superadmin])

  // Cmd+K / Ctrl+K global shortcut para búsqueda
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
        e.preventDefault()
        setSearchOpen(s => !s)
      }
    }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [])

  useEffect(() => {
    if (!user) return
    const fetch = () => {
      apiClient.getAlertas().then(d => setAlertasCount(d.total)).catch(() => {})
    }
    fetch()
    const id = setInterval(fetch, 5 * 60 * 1000)
    return () => clearInterval(id)
  }, [user])

  const handleLogout = async () => {
    const ok = await confirmDialog({
      title: 'Cerrar sesión',
      message: '¿Querés cerrar sesión?',
      confirmLabel: 'Cerrar sesión',
      danger: true,
    })
    if (!ok) return
    logout()
    navigate('/login')
  }

  const visibleItems = navItems.filter(
    item => !item.permission || hasPermission(item.permission)
  )

  const SidebarContent = ({ onNav }: { onNav?: () => void }) => (
    <div className="flex flex-col h-full">
      {/* Nav items */}
      <nav className="flex-1 px-2 py-3 space-y-0.5 overflow-y-auto">
        {visibleItems.map(item => (
          <NavLink
            key={item.to}
            to={item.to}
            onClick={onNav}
            className={({ isActive }) =>
              `group flex items-center gap-2.5 px-2.5 py-2 rounded-lg text-sm font-medium transition-all duration-100 ${
                isActive
                  ? 'bg-ml-blue/10 text-ml-blue dark:bg-ml-green/10 dark:text-ml-green'
                  : 'text-ml-text-soft dark:text-gray-500 hover:text-ml-text dark:hover:text-gray-200 hover:bg-ml-gray dark:hover:bg-ml-dark-hover'
              }`
            }
          >
            {({ isActive }) => (
              <>
                <span className={`transition-colors ${isActive ? 'text-ml-blue dark:text-ml-green' : 'text-ml-text-soft dark:text-gray-600 group-hover:text-ml-text dark:group-hover:text-gray-300'}`}>
                  <item.Icon />
                </span>
                <span>{item.label}</span>
              </>
            )}
          </NavLink>
        ))}
      </nav>

      {/* Footer */}
      <div className="px-2 py-3 border-t border-ml-gray dark:border-ml-dark-border space-y-1">

        {/* Org switcher — solo superadmin */}
        {user?.is_superadmin && orgs.length > 0 && (
          <div className="px-1 pb-1">
            <p className="text-2xs uppercase tracking-widest font-semibold text-ml-text-soft dark:text-gray-600 px-1.5 mb-1">Organización</p>
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
              <p className="text-2xs text-ml-green font-mono px-1.5 mt-1 flex items-center gap-1">
                <span className="w-1.5 h-1.5 rounded-full bg-ml-green inline-block" />
                {activeOrgNombre}
              </p>
            )}
          </div>
        )}

        {/* Toggle tema */}
        <button
          onClick={toggle}
          className="w-full flex items-center gap-2.5 px-2.5 py-2 rounded-lg text-sm font-medium text-ml-text-soft dark:text-gray-500 hover:text-ml-text dark:hover:text-gray-200 hover:bg-ml-gray dark:hover:bg-ml-dark-hover transition-all duration-100"
        >
          {theme === 'light' ? <Icon.Moon /> : <Icon.Sun />}
          <span>{theme === 'light' ? 'Modo oscuro' : 'Modo claro'}</span>
        </button>

        {/* Usuario */}
        <div className="flex items-center gap-2.5 px-2.5 py-2">
          <div className="w-7 h-7 rounded-full bg-ml-green dark:bg-ml-green flex items-center justify-center text-black text-xs font-bold shrink-0">
            {user?.full_name?.charAt(0).toUpperCase()}
          </div>
          <div className="min-w-0 flex-1">
            <p className="text-xs font-semibold text-ml-text dark:text-gray-200 truncate">{user?.full_name}</p>
            <p className="text-2xs text-ml-text-soft dark:text-gray-600 truncate">
              {user?.is_superadmin ? 'Superadmin' : user?.role}
            </p>
          </div>
        </div>

        {/* Logout */}
        <button
          onClick={handleLogout}
          className="w-full flex items-center gap-2.5 px-2.5 py-2 rounded-lg text-sm font-medium text-red-500 dark:text-red-500/70 hover:text-red-600 dark:hover:text-red-400 hover:bg-red-50 dark:hover:bg-red-900/10 transition-all duration-100"
        >
          <Icon.Logout />
          <span>Cerrar sesión</span>
        </button>
      </div>
    </div>
  )

  return (
    <div className="flex flex-col md:flex-row h-screen bg-ml-gray-bg dark:bg-ml-dark-bg overflow-hidden">
      <Toaster />
      <ConfirmDialog />
      <AppLockGuard />

      {/* ── Header mobile ──────────────────────────────── */}
      <header className="md:hidden shrink-0 bg-ml-text dark:bg-ml-dark-surface border-b border-black dark:border-ml-dark-border flex items-center justify-between px-4 h-12 z-30 relative">
        <div className="w-8 flex items-center">
          <CuadraLogo size={24} animate={false} />
        </div>

        <span className="font-bold text-sm font-mono app-title absolute left-1/2 -translate-x-1/2 tracking-wide text-ml-green dark:text-white">
          Cuadra
        </span>

        <div className="flex items-center gap-1">
          <button
            onClick={() => setSearchOpen(true)}
            className="p-1.5 rounded-lg text-ml-green/80 dark:text-gray-400 hover:bg-white/10 dark:hover:bg-ml-dark-hover transition-colors"
            title="Buscar (⌘K)"
          >
            <Icon.Search />
          </button>
          <button
            onClick={() => { setAlertasCount(0); navigate('/resumen') }}
            className="relative p-1.5 rounded-lg text-ml-green/80 dark:text-gray-400 hover:bg-white/10 dark:hover:bg-ml-dark-hover transition-colors"
          >
            <Icon.Bell />
            {alertasCount > 0 && (
              <span className="absolute -top-0.5 -right-0.5 min-w-[16px] h-4 flex items-center justify-center rounded-full bg-red-500 text-white text-[10px] font-bold px-0.5">
                {alertasCount > 99 ? '99+' : alertasCount}
              </span>
            )}
          </button>
          <button
            onClick={toggle}
            className="p-1.5 rounded-lg text-ml-green/80 dark:text-gray-400 hover:bg-white/10 dark:hover:bg-ml-dark-hover transition-colors"
          >
            {theme === 'light' ? <Icon.Moon /> : <Icon.Sun />}
          </button>
        </div>
      </header>

      {/* ── Drawer mobile ──────────────────────────────── */}
      {drawerOpen && (
        <>
          <div
            className="md:hidden fixed inset-0 bg-black/40 dark:bg-black/60 z-40 backdrop-blur-[2px]"
            onClick={() => setDrawerOpen(false)}
          />
          <div
            className="md:hidden fixed left-0 top-0 h-full w-64 bg-white dark:bg-ml-dark-surface z-50 shadow-2xl drawer-enter flex flex-col"
            onTouchStart={handleDrawerTouchStart}
            onTouchEnd={handleDrawerTouchEnd}
          >
            {/* Header del drawer */}
            <div className="flex items-center justify-between px-4 h-12 bg-ml-text dark:bg-ml-dark-card border-b border-black dark:border-ml-dark-border shrink-0">
              <span className="font-bold text-sm font-mono app-title tracking-wide text-ml-green dark:text-white">Cuadra</span>
              <button
                onClick={() => setDrawerOpen(false)}
                className="p-1.5 rounded-lg text-ml-green/80 dark:text-gray-400 hover:bg-white/10 dark:hover:bg-ml-dark-hover"
              >
                <Icon.Close />
              </button>
            </div>
            <div className="flex-1 overflow-y-auto">
              <SidebarContent onNav={() => setDrawerOpen(false)} />
            </div>
          </div>
        </>
      )}

      {/* ── Sidebar desktop ────────────────────────────── */}
      <aside className="hidden md:flex w-56 bg-white dark:bg-ml-dark-surface border-r border-ml-gray dark:border-ml-dark-border flex-col shrink-0">
        {/* Logo */}
        <div className="h-14 flex items-center px-4 border-b border-black dark:border-ml-dark-border shrink-0 bg-ml-text dark:bg-ml-dark-card">
          <div className="flex items-center gap-2.5 flex-1 min-w-0">
            <CuadraLogo size={28} />
            <span className="font-bold text-base font-mono app-title tracking-wide text-ml-green dark:text-white">Cuadra</span>
          </div>
          <button
            onClick={() => setSearchOpen(true)}
            className="p-1.5 rounded-lg text-ml-green/80 dark:text-gray-400 hover:bg-white/10 dark:hover:bg-ml-dark-hover transition-colors shrink-0"
            title="Buscar (⌘K)"
          >
            <Icon.Search />
          </button>
          <button
            onClick={() => { setAlertasCount(0); navigate('/resumen') }}
            className="relative p-1.5 rounded-lg text-ml-green/80 dark:text-gray-400 hover:bg-white/10 dark:hover:bg-ml-dark-hover transition-colors shrink-0"
          >
            <Icon.Bell />
            {alertasCount > 0 && (
              <span className="absolute -top-0.5 -right-0.5 min-w-[16px] h-4 flex items-center justify-center rounded-full bg-red-500 text-white text-[10px] font-bold px-0.5">
                {alertasCount > 99 ? '99+' : alertasCount}
              </span>
            )}
          </button>
        </div>
        <div className="flex-1 overflow-y-auto">
          <SidebarContent />
        </div>
      </aside>

      {/* ── Contenido ──────────────────────────────────── */}
      <main className="flex-1 min-w-0 overflow-y-auto overflow-x-hidden text-ml-text dark:text-gray-200 pb-safe-nav md:pb-0">
        <div key={location.pathname} className="page-enter">
          <Outlet />
        </div>
      </main>

      {/* ── Bottom navigation mobile ────────────────────── */}
      <nav className="md:hidden fixed bottom-0 inset-x-0 z-30 bg-white dark:bg-ml-dark-surface border-t border-gray-100 dark:border-ml-dark-border bottom-nav-bar flex items-stretch h-14">
        {bottomNavItems.map(item => (
          <NavLink
            key={item.to}
            to={item.to}
            className={({ isActive }) =>
              `flex-1 flex flex-col items-center justify-center gap-0.5 py-1.5 text-[10px] font-medium transition-colors ${
                isActive
                  ? 'text-ml-blue dark:text-ml-green'
                  : 'text-gray-400 dark:text-zinc-600'
              }`
            }
          >
            {({ isActive }) => (
              <>
                <span className={`[&>svg]:w-5 [&>svg]:h-5 transition-transform ${isActive ? 'scale-110' : ''}`}>
                  <item.Icon />
                </span>
                <span>{item.label}</span>
              </>
            )}
          </NavLink>
        ))}
        <button
          onClick={() => setDrawerOpen(true)}
          className="flex-1 flex flex-col items-center justify-center gap-0.5 py-1.5 text-[10px] font-medium text-gray-400 dark:text-zinc-600 transition-colors active:text-ml-blue dark:active:text-ml-green"
        >
          <span className="[&>svg]:w-5 [&>svg]:h-5"><Icon.Menu /></span>
          <span>Más</span>
        </button>
      </nav>

      <SearchModal open={searchOpen} onClose={() => setSearchOpen(false)} />
    </div>
  )
}
