import React, { useEffect, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { apiClient } from '@/services/api'
import { useOrgStore } from '@/store/org'
import { useAuthStore } from '@/store/auth'
import { toast } from '@/store/toast'
import { confirmDialog } from '@/store/confirm'

interface CarteraItem {
  cliente_id: number
  cliente_nombre: string
  cuenta: { id: number; codigo: string; nombre: string } | null
  saldo: number
  ultimo_movimiento: string | null
  estado_general: 'deudor' | 'acreedor' | 'equilibrado' | 'sin_actividad'
  conciliacion: string
}

interface CuentaCliente { id: number; codigo: string; nombre: string }
interface ClienteCuentaRow {
  cliente_id: number
  cliente_nombre: string
  cuenta: CuentaCliente | null
}
interface CtaCteOrigen {
  asiento_id: number
  planilla_id?: number
  movimiento_id?: number
  extracto_id?: number
  cheque_id?: number
  pago_id?: number
}
interface CtaCteMov {
  fecha: string
  tipo_cat: 'banco' | 'tt' | 'cheques' | 'ajustes'
  tipo_label: string
  referencia: string
  debito: number
  credito: number
  saldo: number
  estado: string
  origen: CtaCteOrigen
}
interface CtaCteData {
  cliente: { id: number; nombre: string }
  cuenta: CuentaCliente | null
  sin_cuenta: boolean
  movimientos: CtaCteMov[]
  total_debito: number
  total_credito: number
  saldo_final: number
}

interface CuentaItem {
  id: number
  codigo: string
  nombre: string
  tipo: string | null
  parent_id: number | null
  nivel: number
  activo: boolean
}

interface ReglaItem {
  id: number
  evento: string
  descripcion: string | null
  debe: { id: number; codigo: string; nombre: string }
  haber: { id: number; codigo: string; nombre: string }
}

interface AsientoItem {
  id: number
  fecha: string
  descripcion: string | null
  modulo: string | null
  referencia_id: number | null
}

interface AsientoLinea {
  id: number
  cuenta: { id: number; codigo: string; nombre: string }
  debe: number
  haber: number
}

interface SumaRow {
  id: number
  codigo: string
  nombre: string
  tipo: string | null
  nivel: number
  total_debe: number
  total_haber: number
  saldo_deudor: number
  saldo_acreedor: number
}

interface BalanceData {
  activo:    { total_debe: number; total_haber: number; saldo: number }
  pasivo:    { total_debe: number; total_haber: number; saldo: number }
  resultado: { total_debe: number; total_haber: number; saldo: number }
  ecuacion_ok: boolean
}

interface LibroMayorData {
  cuenta: { id: number; codigo: string; nombre: string; tipo: string | null }
  movimientos: { fecha: string; descripcion: string | null; modulo: string | null; debe: number; haber: number; saldo: number }[]
  total_debe: number
  total_haber: number
  saldo_final: number
}

const TIPO_BADGE: Record<string, string> = {
  activo:    'border-blue-200 text-blue-600 dark:border-blue-800 dark:text-blue-400',
  pasivo:    'border-orange-200 text-orange-600 dark:border-orange-800 dark:text-orange-400',
  resultado: 'border-green-200 text-green-600 dark:border-green-800 dark:text-green-400',
}
const TIPO_TEXT: Record<string, string> = {
  activo:    'text-blue-700 dark:text-blue-300',
  pasivo:    'text-orange-700 dark:text-orange-300',
  resultado: 'text-green-700 dark:text-green-300',
}
const TIPO_BG: Record<string, string> = {
  activo:    'bg-blue-50 dark:bg-blue-900/20 border-blue-200 dark:border-blue-800',
  pasivo:    'bg-orange-50 dark:bg-orange-900/20 border-orange-200 dark:border-orange-800',
  resultado: 'bg-green-50 dark:bg-green-900/20 border-green-200 dark:border-green-800',
}

function fmtDate(s: string) {
  try { return new Date(s.endsWith('Z') ? s : s + 'Z').toLocaleDateString('es-AR', { day:'2-digit', month:'2-digit', year:'numeric' }) }
  catch { return s }
}
function fmtNum(n: number) { return n.toLocaleString('es-AR', { minimumFractionDigits: 2, maximumFractionDigits: 2 }) }

const MODULO_LABEL: Record<string, string> = {
  extracto: '🏦 Extracto', planilla: '📋 Planilla', caja: '💵 Caja', cheque: '🗒️ Cheque',
}

type Tab = 'plan' | 'reglas' | 'diario' | 'sumas' | 'balance' | 'mayor' | 'clientes' | 'ctacte'

const CAT_LABEL: Record<string, string> = { banco: 'Banco (UM)', tt: 'TT', cheques: 'Cheques', ajustes: 'Ajustes' }
const CAT_KEYS = ['banco', 'tt', 'cheques', 'ajustes'] as const

const ESTADO_BADGE: Record<string, string> = {
  Conciliado: 'bg-emerald-50 text-emerald-700 border-emerald-200 dark:bg-emerald-900/20 dark:text-emerald-300 dark:border-emerald-800',
  Pendiente:  'bg-amber-50 text-amber-700 border-amber-200 dark:bg-amber-900/20 dark:text-amber-300 dark:border-amber-800',
  Revertido:  'bg-red-50 text-red-700 border-red-200 dark:bg-red-900/20 dark:text-red-300 dark:border-red-800',
  Parcial:    'bg-blue-50 text-blue-700 border-blue-200 dark:bg-blue-900/20 dark:text-blue-300 dark:border-blue-800',
}

const GEN_BADGE: Record<string, { label: string; cls: string }> = {
  deudor:        { label: 'Deudor',       cls: 'bg-blue-50 text-blue-700 border-blue-200 dark:bg-blue-900/20 dark:text-blue-300 dark:border-blue-800' },
  acreedor:      { label: 'Acreedor',     cls: 'bg-orange-50 text-orange-700 border-orange-200 dark:bg-orange-900/20 dark:text-orange-300 dark:border-orange-800' },
  equilibrado:   { label: 'Equilibrado',  cls: 'bg-emerald-50 text-emerald-700 border-emerald-200 dark:bg-emerald-900/20 dark:text-emerald-300 dark:border-emerald-800' },
  sin_actividad: { label: 'Sin actividad', cls: 'bg-gray-100 text-gray-500 border-gray-200 dark:bg-slate-800 dark:text-gray-400 dark:border-slate-600' },
}

type CcFiltro = 'todos' | 'deudores' | 'acreedores' | 'cero' | 'recientes' | 'sin_actividad'

const TAB_PERM: Record<Tab, string> = {
  plan:     'admin_accounting',
  reglas:   'admin_accounting',
  diario:   'view_accounting',
  sumas:    'view_accounting',
  balance:  'view_accounting',
  mayor:    'view_accounting',
  clientes: 'admin_accounting',
  ctacte:   'manage_finance',
}

export const Contabilidad: React.FC<{ modo?: 'full' | 'ctacte' }> = ({ modo = 'full' }) => {
  const { activeOrgId } = useOrgStore()
  const { hasPermission } = useAuthStore()
  const canAdminAccounting = hasPermission('admin_accounting')
  const canManageFinance   = hasPermission('manage_finance')
  const [cuentas, setCuentas]         = useState<CuentaItem[]>([])
  const [reglas, setReglas]           = useState<ReglaItem[]>([])
  const [asientos, setAsientos]       = useState<AsientoItem[]>([])
  const [totalAsientos, setTotalAsientos] = useState(0)
  const [sumasSaldo, setSumasSaldo]   = useState<SumaRow[]>([])
  const [balance, setBalance]         = useState<BalanceData | null>(null)
  const [libroMayor, setLibroMayor]   = useState<LibroMayorData | null>(null)
  const [mayorCuentaId, setMayorCuentaId] = useState<number | ''>('')
  const [loading, setLoading]         = useState(true)
  const [loadingMayor, setLoadingMayor] = useState(false)
  const [openAsientos, setOpenAsientos] = useState<Set<number>>(new Set())
  const [asientoLineas, setAsientoLineas] = useState<Record<number, AsientoLinea[]>>({})
  const [loadingLineas, setLoadingLineas] = useState<Set<number>>(new Set())
  const [tab, setTab] = useState<Tab>(() => {
    if (modo === 'ctacte') return 'ctacte'
    const s = useAuthStore.getState()
    const ordered: Tab[] = ['plan', 'reglas', 'diario', 'sumas', 'balance', 'mayor', 'clientes']
    return ordered.find(t => s.hasPermission(TAB_PERM[t])) ?? 'diario'
  })
  const [cliCuentas, setCliCuentas]   = useState<ClienteCuentaRow[]>([])
  const [cuentasDisp, setCuentasDisp] = useState<CuentaCliente[]>([])
  const [loadingCli, setLoadingCli]   = useState(false)
  const [savingCli, setSavingCli]     = useState<number | null>(null)
  const [ctaCte, setCtaCte]           = useState<CtaCteData | null>(null)
  const [ctaCteClienteId, setCtaCteClienteId] = useState<number | ''>('')
  const [loadingCtaCte, setLoadingCtaCte] = useState(false)
  const [catFiltro, setCatFiltro]     = useState<Set<string>>(new Set(CAT_KEYS))
  const [ccMode, setCcMode]           = useState<'list' | 'detail'>('list')
  const [cartera, setCartera]         = useState<CarteraItem[]>([])
  const [loadingCartera, setLoadingCartera] = useState(false)
  const [ccFiltro, setCcFiltro]       = useState<CcFiltro>('todos')
  const [ccBusqueda, setCcBusqueda]   = useState('')
  const [searchParams, setSearchParams] = useSearchParams()

  useEffect(() => {
    if (modo === 'ctacte') { setLoading(false); return }
    const q = activeOrgId ? `?org_id=${activeOrgId}` : ''
    Promise.all([
      canAdminAccounting
        ? apiClient.client.get(`/contabilidad/plan-cuentas${q}`).then(r => r.data)
        : Promise.resolve([]),
      canAdminAccounting
        ? apiClient.client.get(`/contabilidad/reglas${q}`).then(r => r.data)
        : Promise.resolve([]),
      apiClient.client.get(`/contabilidad/asientos?limit=100${activeOrgId ? `&org_id=${activeOrgId}` : ''}`).then(r => r.data),
      apiClient.client.get(`/contabilidad/sumas-saldo${q}`).then(r => r.data),
      apiClient.client.get(`/contabilidad/balance${q}`).then(r => r.data),
    ]).then(([c, r, a, ss, b]) => {
      setCuentas(c); setReglas(r)
      setAsientos(a.items); setTotalAsientos(a.total)
      setSumasSaldo(ss); setBalance(b)
      setLoading(false)
    }).catch(() => setLoading(false))
  }, [activeOrgId])

  const cargarLibroMayor = (id: number) => {
    setLoadingMayor(true)
    setLibroMayor(null)
    apiClient.client.get(`/contabilidad/libro-mayor?cuenta_id=${id}`)
      .then(r => { setLibroMayor(r.data); setLoadingMayor(false) })
      .catch(() => setLoadingMayor(false))
  }

  const cargarClientesCuentas = () => {
    setLoadingCli(true)
    const q = activeOrgId ? `?org_id=${activeOrgId}` : ''
    apiClient.client.get(`/contabilidad/clientes-cuentas${q}`)
      .then(r => { setCliCuentas(r.data.clientes); setCuentasDisp(r.data.cuentas_disponibles) })
      .finally(() => setLoadingCli(false))
  }

  useEffect(() => {
    if (tab === 'clientes' && canAdminAccounting) cargarClientesCuentas()
    if (tab === 'ctacte' && canManageFinance) { cargarClientesCuentas(); cargarCartera() }
  }, [tab, activeOrgId])

  // Deep-link desde Clientes: /contabilidad?cc=<cliente_id>
  useEffect(() => {
    const cc = searchParams.get('cc')
    if (cc && canManageFinance) {
      setTab('ctacte')
      verCtaCteCliente(Number(cc))
      searchParams.delete('cc')
      setSearchParams(searchParams, { replace: true })
    }
  }, [])

  const cargarCartera = () => {
    setLoadingCartera(true)
    const q = activeOrgId ? `?org_id=${activeOrgId}` : ''
    apiClient.client.get(`/contabilidad/cuentas-corrientes${q}`)
      .then(r => setCartera(r.data.items))
      .finally(() => setLoadingCartera(false))
  }

  const cargarCtaCte = (clienteId: number) => {
    setLoadingCtaCte(true)
    setCtaCte(null)
    const q = activeOrgId ? `&org_id=${activeOrgId}` : ''
    apiClient.client.get(`/contabilidad/cuenta-corriente?cliente_id=${clienteId}${q}`)
      .then(r => setCtaCte(r.data))
      .catch(() => setCtaCte(null))
      .finally(() => setLoadingCtaCte(false))
  }

  const verCtaCteCliente = (clienteId: number) => {
    setCtaCteClienteId(clienteId)
    setCcMode('detail')
    cargarCtaCte(clienteId)
  }

  const toggleCat = (cat: string) => {
    setCatFiltro(prev => {
      const next = new Set(prev)
      if (next.has(cat)) next.delete(cat); else next.add(cat)
      return next
    })
  }

  const qOrg = activeOrgId ? `?org_id=${activeOrgId}` : ''

  const asignarCuenta = async (clienteId: number, cuentaId: number | null) => {
    setSavingCli(clienteId)
    try {
      await apiClient.client.put(`/contabilidad/clientes/${clienteId}/cuenta${qOrg}`, { cuenta_id: cuentaId })
      toast.success(cuentaId ? 'Cuenta vinculada' : 'Cuenta desvinculada')
      cargarClientesCuentas()
    } catch (e: any) {
      toast.error(e.response?.data?.detail || 'No se pudo vincular')
    } finally {
      setSavingCli(null)
    }
  }

  const crearCuenta = async (clienteId: number) => {
    setSavingCli(clienteId)
    try {
      const r = await apiClient.client.post(`/contabilidad/clientes/${clienteId}/cuenta/crear${qOrg}`, {})
      toast.success(`Cuenta ${r.data.cuenta.codigo} creada y vinculada`)
      cargarClientesCuentas()
    } catch (e: any) {
      toast.error(e.response?.data?.detail || 'No se pudo crear la cuenta')
    } finally {
      setSavingCli(null)
    }
  }

  const [revirtiendo, setRevirtiendo] = useState(false)
  const revertirPlanillasExtracto = async () => {
    setRevirtiendo(true)
    const orgQ = activeOrgId ? `&org_id=${activeOrgId}` : ''
    try {
      const prev = await apiClient.client.post(`/contabilidad/revertir-planillas-extracto?dry_run=true${orgQ}`, {})
      const { planillas, filas, asientos_a_revertir } = prev.data
      if (!planillas) {
        toast.success('No hay planillas auto-recuperadas para revertir')
        return
      }
      const asientosNote = asientos_a_revertir > 0
        ? ` y se revertirán ${asientos_a_revertir} asiento(s) contable(s)` : ''
      const ok = await confirmDialog({
        title: 'Revertir planillas del extracto',
        message: `Se borrarán ${planillas} planilla(s) con ${filas} fila(s) creadas automáticamente desde el extracto${asientosNote}.\n\nEsta acción es reversible: las planillas quedan en la papelera y los asientos quedan con su reverso contable.`,
        confirmLabel: 'Revertir',
      })
      if (!ok) return
      const r = await apiClient.client.post(`/contabilidad/revertir-planillas-extracto${orgQ ? `?${orgQ.slice(1)}` : ''}`, {})
      const clientesMsg = r.data.clientes_borrados > 0 ? ` · ${r.data.clientes_borrados} cliente(s) eliminado(s)` : ''
      toast.success(`${r.data.planillas} planilla(s) revertida(s)${r.data.asientos_revertidos > 0 ? ` · ${r.data.asientos_revertidos} asiento(s) revertido(s)` : ''}${clientesMsg}`)
      cargarCartera()
    } catch (e: any) {
      toast.error(e.response?.data?.detail || 'No se pudo revertir')
    } finally {
      setRevirtiendo(false)
    }
  }

  const [recuperando, setRecuperando] = useState(false)
  const recuperarPlanillasExtracto = async () => {
    setRecuperando(true)
    const orgQ = activeOrgId ? `&org_id=${activeOrgId}` : ''
    try {
      // Paso 1: preview
      const prev = await apiClient.client.post(`/contabilidad/planillas-desde-extracto?dry_run=true${orgQ}`, {})
      const { identificados, clientes, planillas_a_crear, filas_a_crear, grupos,
              clientes_nuevos_count, clientes_nuevos, filas_nuevos } = prev.data

      if (!identificados && !clientes_nuevos_count) {
        toast.success('No hay movimientos nuevos para recuperar del extracto')
        return
      }

      // Paso 2: recuperar clientes conocidos
      if (identificados > 0) {
        const top5 = (grupos as any[]).slice(0, 5).map((g: any) => `• ${g.cliente_nombre} — ${g.fecha} (${g.count} mov.)`)
        const extra = grupos.length > 5 ? `\n  …y ${grupos.length - 5} grupo(s) más` : ''
        const noIdNote = clientes_nuevos_count > 0
          ? `\n\n⚠️ ${filas_nuevos} movimiento(s) de ${clientes_nuevos_count} nombre(s) no reconocidos (se ofrecerá a continuación).`
          : ''
        const ok = await confirmDialog({
          title: 'Recuperar planillas del extracto',
          message: `${identificados} movimiento(s) de ${clientes} cliente(s) → ${planillas_a_crear} planilla(s).\n\n${top5.join('\n')}${extra}${noIdNote}`,
          confirmLabel: 'Recuperar',
        })
        if (!ok) return
        const r = await apiClient.client.post(`/contabilidad/planillas-desde-extracto${orgQ ? `?${orgQ.slice(1)}` : ''}`, {})
        toast.success(`${r.data.filas_creadas} fila(s) recuperada(s) en ${r.data.planillas_creadas} planilla(s)`)
      }

      // Paso 3: ofrecer crear clientes nuevos del extracto
      if (clientes_nuevos_count > 0) {
        const nombres = (clientes_nuevos as string[]).slice(0, 8).map((n: string) => `• ${n}`)
        const extraN = clientes_nuevos_count > 8 ? `\n  …y ${clientes_nuevos_count - 8} más` : ''
        const ok2 = await confirmDialog({
          title: 'Crear clientes del extracto',
          message: `Hay ${filas_nuevos} movimiento(s) de ${clientes_nuevos_count} nombre(s) no reconocidos en el extracto:\n${nombres.join('\n')}${extraN}\n\n¿Crear como clientes y recuperar sus planillas?`,
          confirmLabel: 'Crear y recuperar',
        })
        if (ok2) {
          const r2 = await apiClient.client.post(`/contabilidad/planillas-desde-extracto?crear_clientes=true${orgQ}`, {})
          toast.success(`${r2.data.clientes_creados} cliente(s) creado(s) · ${r2.data.filas_creadas} fila(s) adicionales`)
        }
      }

      cargarCartera()
    } catch (e: any) {
      toast.error(e.response?.data?.detail || 'No se pudo recuperar del extracto')
    } finally {
      setRecuperando(false)
    }
  }

  const [limpiando, setLimpiando] = useState(false)
  const limpiarClientesExtracto = async () => {
    setLimpiando(true)
    const orgQ = activeOrgId ? `&org_id=${activeOrgId}` : ''
    try {
      const prev = await apiClient.client.post(`/contabilidad/limpiar-clientes-extracto?dry_run=true${orgQ}`, {})
      const { clientes_a_borrar, nombres } = prev.data
      if (!clientes_a_borrar) {
        toast.success('No hay clientes del extracto para limpiar')
        return
      }
      const lista = (nombres as string[]).slice(0, 10).map((n: string) => `• ${n}`).join('\n')
      const extra = clientes_a_borrar > 10 ? `\n  …y ${clientes_a_borrar - 10} más` : ''
      const ok = await confirmDialog({
        title: 'Limpiar clientes del extracto',
        message: `Se eliminarán ${clientes_a_borrar} cliente(s) creados automáticamente (solo tienen planillas auto-recuperadas):\n\n${lista}${extra}\n\nEsta acción no se puede deshacer.`,
        confirmLabel: 'Eliminar',
      })
      if (!ok) return
      const r = await apiClient.client.post(`/contabilidad/limpiar-clientes-extracto${orgQ ? `?${orgQ.slice(1)}` : ''}`, {})
      toast.success(`${r.data.clientes_borrados} cliente(s) eliminado(s)`)
      cargarCartera()
    } catch (e: any) {
      toast.error(e.response?.data?.detail || 'No se pudo limpiar clientes')
    } finally {
      setLimpiando(false)
    }
  }

  const [backfilling, setBackfilling] = useState(false)
  const reconstruirCtaCte = async () => {
    setBackfilling(true)
    const orgQ = activeOrgId ? `&org_id=${activeOrgId}` : ''
    try {
      const prev = await apiClient.client.post(`/contabilidad/backfill-cuentas-corrientes?dry_run=true${orgQ}`, {})
      const { pendientes, clientes, ya_cubiertas, total_filas_ok, sin_cuenta_cliente } = prev.data
      if (!pendientes) {
        if (ya_cubiertas > 0) {
          const extra = sin_cuenta_cliente > 0 ? ` · ${sin_cuenta_cliente} fila(s) sin cuenta de cliente` : ''
          toast.success(`Cuentas corrientes al día — ${ya_cubiertas} de ${total_filas_ok} fila(s) cubiertas${extra}`)
        } else {
          toast.success('No hay conciliaciones para reconstruir')
        }
        return
      }
      const ok = await confirmDialog({
        title: 'Reconstruir cuentas corrientes',
        message: `Se generarán ${pendientes} acreditación(es) de ${clientes} cliente(s) a partir de las conciliaciones ya cargadas (Banco D / Cliente H). Es idempotente: no duplica lo ya registrado.${sin_cuenta_cliente > 0 ? ` Nota: ${sin_cuenta_cliente} fila(s) sin cuenta de cliente serán ignoradas.` : ''}`,
        confirmLabel: 'Reconstruir',
      })
      if (!ok) return
      const r = await apiClient.client.post(`/contabilidad/backfill-cuentas-corrientes?${orgQ.slice(1)}`, {})
      toast.success(`${r.data.creados} acreditación(es) agregada(s) en ${r.data.clientes} cliente(s)`)
      cargarCartera()
    } catch (e: any) {
      toast.error(e.response?.data?.detail || 'No se pudo reconstruir')
    } finally {
      setBackfilling(false)
    }
  }

  const [creandoFaltantes, setCreandoFaltantes] = useState(false)
  const crearCuentasFaltantes = async () => {
    setCreandoFaltantes(true)
    try {
      const r = await apiClient.client.post(`/contabilidad/clientes/cuentas/crear-faltantes${qOrg}`, {})
      toast.success(r.data.total > 0 ? `${r.data.total} cuenta(s) creada(s) y vinculada(s)` : 'Todos los clientes ya tienen cuenta')
      cargarClientesCuentas()
    } catch (e: any) {
      toast.error(e.response?.data?.detail || 'No se pudieron crear las cuentas')
    } finally {
      setCreandoFaltantes(false)
    }
  }

  const toggleAsiento = (id: number) => {
    const next = new Set(openAsientos)
    if (next.has(id)) {
      next.delete(id)
      setOpenAsientos(next)
    } else {
      next.add(id)
      setOpenAsientos(next)
      if (!asientoLineas[id]) {
        setLoadingLineas(prev => new Set(prev).add(id))
        apiClient.client.get(`/contabilidad/asientos/${id}`)
          .then(r => {
            setAsientoLineas(prev => ({ ...prev, [id]: r.data.lineas }))
            setLoadingLineas(prev => { const s = new Set(prev); s.delete(id); return s })
          })
          .catch(() => {
            setLoadingLineas(prev => { const s = new Set(prev); s.delete(id); return s })
          })
      }
    }
  }

  const raices = cuentas.filter(c => c.nivel === 1)
  const hijos  = (pid: number) => cuentas.filter(c => c.parent_id === pid)

  const renderCuenta = (c: CuentaItem, depth = 0): React.ReactNode => {
    const children = hijos(c.id)
    const textClass = depth === 0 ? 'font-bold' : depth === 1 ? 'font-semibold' : 'font-normal'
    const colorClass = c.tipo ? (TIPO_TEXT[c.tipo] || '') : 'text-ml-text dark:text-gray-200'
    return (
      <React.Fragment key={c.id}>
        <div className="flex items-center gap-2 py-1 px-2 hover:bg-gray-50 dark:hover:bg-slate-800/50 transition-colors"
          style={{ paddingLeft: `${8 + depth * 20}px` }}>
          <span className="text-[11px] font-mono text-gray-400 w-16 shrink-0">{c.codigo}</span>
          <span className={`text-xs ${textClass} ${colorClass}`}>{c.nombre}</span>
          {c.tipo && depth === 0 && (
            <span className={`text-[10px] px-1.5 py-0.5 rounded-full border ${TIPO_BADGE[c.tipo] || ''}`}>{c.tipo}</span>
          )}
        </div>
        {children.map(ch => renderCuenta(ch, depth + 1))}
      </React.Fragment>
    )
  }

  const FULL_TABS: [Tab, string][] = [
    ['plan',    '📊 Plan de cuentas'],
    ['reglas',  '⚙️ Reglas'],
    ['diario',  `📒 Libro diario${totalAsientos > 0 ? ` (${totalAsientos})` : ''}`],
    ['sumas',   '🧾 Sumas y saldo'],
    ['balance', '⚖️ Balance'],
    ['mayor',   '📖 Libro mayor'],
    ['clientes', '🔗 Clientes'],
  ]
  const TABS = modo === 'ctacte' ? [] : FULL_TABS.filter(([t]) => hasPermission(TAB_PERM[t]))

  return (
    <div className="p-4 md:p-6 max-w-5xl mx-auto">
      <div className="mb-6">
        <h1 className="text-xl font-bold text-ml-text dark:text-white">{modo === 'ctacte' ? 'Cuentas corrientes' : 'Contabilidad'}</h1>
        <p className="text-xs text-gray-500 dark:text-gray-400 mt-0.5">
          {modo === 'ctacte'
            ? 'Cartera de clientes · saldo, movimientos y estado por cuenta'
            : `${canAdminAccounting ? 'Plan de cuentas · Reglas · ' : ''}Libro diario · Sumas y saldo · Balance · Libro mayor`}
        </p>
      </div>

      {TABS.length > 0 && (
      <div className="grid grid-cols-3 gap-2 mb-4">
        {TABS.map(([t, label]) => (
          <button key={t} onClick={() => setTab(t)}
            className={`px-2 py-2 rounded-lg text-xs font-medium transition-colors text-center leading-tight ${
              tab === t ? 'bg-ml-blue text-white' : 'bg-gray-100 dark:bg-slate-800 text-gray-600 dark:text-gray-400 hover:bg-gray-200 dark:hover:bg-slate-700'
            }`}>
            {label}
          </button>
        ))}
      </div>
      )}

      {loading ? (
        <div className="py-16 text-center text-gray-400">Cargando...</div>

      ) : tab === 'plan' ? (
        <div className="border border-gray-200 dark:border-slate-700 rounded-xl overflow-hidden bg-white dark:bg-slate-900/50">
          {raices.length === 0 ? <p className="text-center py-8 text-gray-400 text-sm">Sin datos</p> : (
            <div className="divide-y divide-gray-100 dark:divide-slate-800">
              {raices.map(r => renderCuenta(r, 0))}
            </div>
          )}
        </div>

      ) : tab === 'reglas' ? (
        <div className="border border-gray-200 dark:border-slate-700 rounded-xl overflow-hidden">
          {reglas.length === 0 ? <p className="text-center py-8 text-gray-400 text-sm">Sin reglas</p> : (
            <div className="overflow-x-auto"><table className="w-full text-xs min-w-[480px]">
              <thead className="bg-gray-50 dark:bg-slate-800">
                <tr>
                  <th className="text-left px-4 py-2 font-medium text-gray-600 dark:text-gray-400">Evento</th>
                  <th className="text-left px-4 py-2 font-medium text-blue-600 dark:text-blue-400">Debe</th>
                  <th className="text-left px-4 py-2 font-medium text-orange-600 dark:text-orange-400">Haber</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100 dark:divide-slate-700/50">
                {reglas.map(r => (
                  <tr key={r.id} className="hover:bg-gray-50 dark:hover:bg-slate-800/40">
                    <td className="px-4 py-2">
                      <span className="font-mono text-gray-700 dark:text-gray-300">{r.evento}</span>
                      {r.descripcion && <p className="text-gray-400 dark:text-gray-500 mt-0.5">{r.descripcion}</p>}
                    </td>
                    <td className="px-4 py-2 text-blue-700 dark:text-blue-300">
                      <span className="font-mono text-[10px] text-gray-400 mr-1">{r.debe.codigo}</span>{r.debe.nombre}
                    </td>
                    <td className="px-4 py-2 text-orange-700 dark:text-orange-300">
                      <span className="font-mono text-[10px] text-gray-400 mr-1">{r.haber.codigo}</span>{r.haber.nombre}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table></div>
          )}
        </div>

      ) : tab === 'diario' ? (
        <div className="border border-gray-200 dark:border-slate-700 rounded-xl overflow-hidden">
          {asientos.length === 0 ? (
            <div className="py-16 text-center text-gray-400">
              <p className="text-3xl mb-2">📒</p>
              <p className="text-sm">Sin asientos todavía.</p>
              <p className="text-xs mt-1">Se generan automáticamente al subir extractos y conciliar planillas.</p>
            </div>
          ) : (
            <div className="overflow-x-auto"><table className="w-full text-xs min-w-[420px]">
              <thead className="bg-gray-50 dark:bg-slate-800">
                <tr>
                  <th className="w-6 px-2 py-2"></th>
                  <th className="text-left px-3 py-2 font-medium text-gray-500 w-8">#</th>
                  <th className="text-left px-3 py-2 font-medium text-gray-500">Fecha</th>
                  <th className="text-left px-3 py-2 font-medium text-gray-500">Módulo</th>
                  <th className="text-left px-3 py-2 font-medium text-gray-500">Descripción</th>
                </tr>
              </thead>
              <tbody>
                {asientos.map(a => {
                  const isOpen = openAsientos.has(a.id)
                  const isLoading = loadingLineas.has(a.id)
                  const lineas = asientoLineas[a.id]
                  return (
                    <React.Fragment key={a.id}>
                      <tr
                        className="border-b border-gray-100 dark:border-slate-700/50 hover:bg-gray-50 dark:hover:bg-slate-800/40 cursor-pointer select-none"
                        onClick={() => toggleAsiento(a.id)}
                      >
                        <td className="px-2 py-2 text-gray-400 text-center">{isOpen ? '▾' : '▸'}</td>
                        <td className="px-3 py-2 text-gray-400 font-mono">{a.id}</td>
                        <td className="px-3 py-2 whitespace-nowrap text-gray-700 dark:text-gray-300">{fmtDate(a.fecha)}</td>
                        <td className="px-3 py-2">
                          <span className="text-[10px] px-1.5 py-0.5 rounded bg-gray-100 dark:bg-slate-700 text-gray-500">
                            {(a.modulo && MODULO_LABEL[a.modulo]) || a.modulo || '—'}
                          </span>
                        </td>
                        <td className="px-3 py-2 text-gray-700 dark:text-gray-300">{a.descripcion || '—'}</td>
                      </tr>
                      {isOpen && (
                        <tr className="border-b border-gray-100 dark:border-slate-700/50 bg-gray-50/60 dark:bg-slate-800/30">
                          <td colSpan={5} className="px-6 py-2">
                            {isLoading ? (
                              <p className="text-gray-400 py-1">Cargando...</p>
                            ) : !lineas || lineas.length === 0 ? (
                              <p className="text-gray-400 py-1">Sin líneas</p>
                            ) : (
                              <table className="w-full text-[11px]">
                                <thead>
                                  <tr className="text-gray-400">
                                    <th className="text-left font-medium pr-3 py-0.5 w-20">Código</th>
                                    <th className="text-left font-medium pr-3 py-0.5">Cuenta</th>
                                    <th className="text-right font-medium pr-3 py-0.5 w-24 text-blue-500">Debe</th>
                                    <th className="text-right font-medium py-0.5 w-24 text-orange-500">Haber</th>
                                  </tr>
                                </thead>
                                <tbody>
                                  {lineas.map(l => (
                                    <tr key={l.id}>
                                      <td className="font-mono text-gray-400 pr-3 py-0.5">{l.cuenta.codigo}</td>
                                      <td className="text-gray-700 dark:text-gray-300 pr-3 py-0.5">{l.cuenta.nombre}</td>
                                      <td className="text-right font-mono text-blue-700 dark:text-blue-300 pr-3 py-0.5">
                                        {l.debe > 0 ? fmtNum(l.debe) : ''}
                                      </td>
                                      <td className="text-right font-mono text-orange-700 dark:text-orange-300 py-0.5">
                                        {l.haber > 0 ? fmtNum(l.haber) : ''}
                                      </td>
                                    </tr>
                                  ))}
                                </tbody>
                              </table>
                            )}
                          </td>
                        </tr>
                      )}
                    </React.Fragment>
                  )
                })}
              </tbody>
            </table></div>
          )}
        </div>

      ) : tab === 'sumas' ? (
        <div className="border border-gray-200 dark:border-slate-700 rounded-xl overflow-hidden">
          {sumasSaldo.length === 0 ? (
            <div className="py-16 text-center text-gray-400">
              <p className="text-sm">Sin movimientos contables todavía.</p>
            </div>
          ) : (
            <div className="overflow-x-auto"><table className="w-full text-xs min-w-[500px]">
              <thead className="bg-gray-50 dark:bg-slate-800">
                <tr>
                  <th className="text-left px-4 py-2 font-medium text-gray-500">Código</th>
                  <th className="text-left px-4 py-2 font-medium text-gray-500">Cuenta</th>
                  <th className="text-right px-4 py-2 font-medium text-blue-600 dark:text-blue-400">Debe</th>
                  <th className="text-right px-4 py-2 font-medium text-orange-600 dark:text-orange-400">Haber</th>
                  <th className="text-right px-4 py-2 font-medium text-gray-500">Saldo D</th>
                  <th className="text-right px-4 py-2 font-medium text-gray-500">Saldo H</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100 dark:divide-slate-700/50">
                {sumasSaldo.map(r => (
                  <tr key={r.id} className="hover:bg-gray-50 dark:hover:bg-slate-800/40">
                    <td className="px-4 py-2 font-mono text-gray-400">{r.codigo}</td>
                    <td className="px-4 py-2 text-gray-700 dark:text-gray-300">{r.nombre}</td>
                    <td className="px-4 py-2 text-right text-blue-700 dark:text-blue-300 font-mono">{fmtNum(r.total_debe)}</td>
                    <td className="px-4 py-2 text-right text-orange-700 dark:text-orange-300 font-mono">{fmtNum(r.total_haber)}</td>
                    <td className="px-4 py-2 text-right font-mono text-gray-700 dark:text-gray-300">{r.saldo_deudor > 0 ? fmtNum(r.saldo_deudor) : ''}</td>
                    <td className="px-4 py-2 text-right font-mono text-gray-700 dark:text-gray-300">{r.saldo_acreedor > 0 ? fmtNum(r.saldo_acreedor) : ''}</td>
                  </tr>
                ))}
              </tbody>
            </table></div>
          )}
        </div>

      ) : tab === 'balance' ? (
        <div className="space-y-3">
          {!balance ? (
            <p className="text-center py-8 text-gray-400 text-sm">Sin datos</p>
          ) : (
            <>
              {(['activo', 'pasivo', 'resultado'] as const).map(tipo => (
                <div key={tipo} className={`border rounded-xl p-4 ${TIPO_BG[tipo] || ''}`}>
                  <div className="flex items-center justify-between">
                    <div>
                      <p className={`text-xs font-bold uppercase tracking-wider ${TIPO_TEXT[tipo]}`}>{tipo}</p>
                      <p className="text-2xl font-bold text-ml-text dark:text-white mt-1">
                        $ {fmtNum(Math.abs(balance[tipo].saldo))}
                      </p>
                    </div>
                    <div className="text-right text-xs text-gray-500 dark:text-gray-400 space-y-1">
                      <p>Debe: <span className="font-mono">{fmtNum(balance[tipo].total_debe)}</span></p>
                      <p>Haber: <span className="font-mono">{fmtNum(balance[tipo].total_haber)}</span></p>
                    </div>
                  </div>
                </div>
              ))}
              <div className={`border rounded-xl p-3 text-center text-xs ${balance.ecuacion_ok ? 'bg-green-50 dark:bg-green-900/20 border-green-200 text-green-700 dark:text-green-400' : 'bg-red-50 dark:bg-red-900/20 border-red-200 text-red-700 dark:text-red-400'}`}>
                {balance.ecuacion_ok ? '✓ Ecuación contable OK: Activo = Pasivo + Resultado' : '⚠ Ecuación contable desequilibrada — revisar asientos'}
              </div>
            </>
          )}
        </div>

      ) : tab === 'mayor' ? (
        <div className="space-y-4">
          <div className="flex items-center gap-3">
            <select
              className="input-field text-sm flex-1 max-w-xs"
              value={mayorCuentaId}
              onChange={e => {
                const id = Number(e.target.value)
                setMayorCuentaId(id || '')
                if (id) cargarLibroMayor(id)
                else setLibroMayor(null)
              }}
            >
              <option value="">— Seleccioná una cuenta —</option>
              {cuentas.map(c => (
                <option key={c.id} value={c.id}>{c.codigo} — {c.nombre}</option>
              ))}
            </select>
          </div>

          {loadingMayor ? (
            <div className="py-8 text-center text-gray-400">Cargando...</div>
          ) : !libroMayor ? (
            <div className="py-12 text-center text-gray-400 text-sm">
              Seleccioná una cuenta para ver sus movimientos
            </div>
          ) : libroMayor.movimientos.length === 0 ? (
            <div className="py-12 text-center text-gray-400 text-sm">
              Sin movimientos para <strong>{libroMayor.cuenta.nombre}</strong>
            </div>
          ) : (
            <div className="border border-gray-200 dark:border-slate-700 rounded-xl overflow-hidden">
              <div className="px-4 py-2 bg-gray-50 dark:bg-slate-800 flex items-center justify-between">
                <p className="text-xs font-semibold text-ml-text dark:text-white">
                  {libroMayor.cuenta.codigo} — {libroMayor.cuenta.nombre}
                </p>
                <p className="text-xs text-gray-500">
                  Saldo final: <span className="font-mono font-medium">{fmtNum(libroMayor.saldo_final)}</span>
                </p>
              </div>
              <div className="overflow-x-auto"><table className="w-full text-xs min-w-[400px]">
                <thead className="bg-gray-50 dark:bg-slate-800 border-t border-gray-100 dark:border-slate-700">
                  <tr>
                    <th className="text-left px-4 py-2 font-medium text-gray-500">Fecha</th>
                    <th className="text-left px-4 py-2 font-medium text-gray-500">Descripción</th>
                    <th className="text-right px-4 py-2 font-medium text-blue-600 dark:text-blue-400">Debe</th>
                    <th className="text-right px-4 py-2 font-medium text-orange-600 dark:text-orange-400">Haber</th>
                    <th className="text-right px-4 py-2 font-medium text-gray-500">Saldo</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-100 dark:divide-slate-700/50">
                  {libroMayor.movimientos.map((m, i) => (
                    <tr key={i} className="hover:bg-gray-50 dark:hover:bg-slate-800/40">
                      <td className="px-4 py-2 whitespace-nowrap text-gray-600 dark:text-gray-400">{fmtDate(m.fecha)}</td>
                      <td className="px-4 py-2 text-gray-700 dark:text-gray-300">{m.descripcion || '—'}</td>
                      <td className="px-4 py-2 text-right font-mono text-blue-700 dark:text-blue-300">{m.debe > 0 ? fmtNum(m.debe) : ''}</td>
                      <td className="px-4 py-2 text-right font-mono text-orange-700 dark:text-orange-300">{m.haber > 0 ? fmtNum(m.haber) : ''}</td>
                      <td className="px-4 py-2 text-right font-mono text-gray-700 dark:text-gray-300">{fmtNum(m.saldo)}</td>
                    </tr>
                  ))}
                </tbody>
                <tfoot className="bg-gray-50 dark:bg-slate-800 border-t border-gray-200 dark:border-slate-700">
                  <tr>
                    <td colSpan={2} className="px-4 py-2 text-xs font-semibold text-gray-600 dark:text-gray-400">Totales</td>
                    <td className="px-4 py-2 text-right font-mono font-semibold text-blue-700 dark:text-blue-300">{fmtNum(libroMayor.total_debe)}</td>
                    <td className="px-4 py-2 text-right font-mono font-semibold text-orange-700 dark:text-orange-300">{fmtNum(libroMayor.total_haber)}</td>
                    <td className="px-4 py-2 text-right font-mono font-semibold">{fmtNum(libroMayor.saldo_final)}</td>
                  </tr>
                </tfoot>
              </table></div>
            </div>
          )}
        </div>

      ) : tab === 'clientes' ? (
        <div>
          <div className="flex flex-wrap items-start justify-between gap-2 mb-3">
            <p className="text-xs text-gray-500 dark:text-gray-400 flex-1 min-w-[220px]">
              Vinculá cada cliente a su cuenta corriente contable (subcuenta de <span className="font-mono">2-1-2-0</span>).
              Cada cuenta pertenece a un solo cliente. Los sin vincular se resuelven asignando una cuenta existente o creando una nueva.
            </p>
            <button
              onClick={crearCuentasFaltantes}
              disabled={creandoFaltantes}
              className="shrink-0 text-xs px-3 py-2 rounded-lg bg-ml-blue text-white font-medium hover:bg-ml-blue-dark disabled:opacity-50"
              title="Crea y vincula la cuenta contable de todos los clientes que aún no tienen una"
            >
              {creandoFaltantes ? 'Creando…' : '+ Crear cuentas faltantes'}
            </button>
          </div>
          {loadingCli ? (
            <div className="py-12 text-center text-gray-400">Cargando...</div>
          ) : cliCuentas.length === 0 ? (
            <p className="text-center py-8 text-gray-400 text-sm">Sin clientes</p>
          ) : (
            <div className="border border-gray-200 dark:border-slate-700 rounded-xl overflow-hidden">
              <div className="overflow-x-auto"><table className="w-full text-xs min-w-[520px]">
                <thead className="bg-gray-50 dark:bg-slate-800">
                  <tr>
                    <th className="text-left px-4 py-2 font-medium text-gray-500">Cliente</th>
                    <th className="text-left px-4 py-2 font-medium text-gray-500">Cuenta contable</th>
                    <th className="text-right px-4 py-2 font-medium text-gray-500">Acciones</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-100 dark:divide-slate-700/50">
                  {cliCuentas.map(row => {
                    const saving = savingCli === row.cliente_id
                    return (
                      <tr key={row.cliente_id} className="hover:bg-gray-50 dark:hover:bg-slate-800/40">
                        <td className="px-4 py-2 font-medium text-ml-text dark:text-gray-200">{row.cliente_nombre}</td>
                        <td className="px-4 py-2">
                          {row.cuenta ? (
                            <span className="inline-flex items-center gap-1.5">
                              <span className="font-mono text-[11px] text-gray-400">{row.cuenta.codigo}</span>
                              <span className="text-amber-600 dark:text-amber-400">{row.cuenta.nombre}</span>
                            </span>
                          ) : (
                            <span className="text-[10px] px-1.5 py-0.5 rounded-full border border-gray-300 dark:border-slate-600 text-gray-400">sin vincular</span>
                          )}
                        </td>
                        <td className="px-4 py-2">
                          <div className="flex items-center justify-end gap-1.5 flex-wrap">
                            <select
                              value={row.cuenta?.id ?? ''}
                              disabled={saving}
                              onChange={e => asignarCuenta(row.cliente_id, e.target.value ? Number(e.target.value) : null)}
                              className="text-[11px] px-1.5 py-1 rounded-md border border-gray-300 dark:border-slate-600 bg-white dark:bg-slate-800 text-gray-700 dark:text-gray-300 max-w-[180px]"
                            >
                              <option value="">— sin vincular —</option>
                              {cuentasDisp.map(c => (
                                <option key={c.id} value={c.id}>{c.codigo} · {c.nombre}</option>
                              ))}
                            </select>
                            {!row.cuenta && (
                              <button
                                onClick={() => crearCuenta(row.cliente_id)}
                                disabled={saving}
                                className="text-[11px] px-2 py-1 rounded-md bg-ml-blue text-white hover:bg-ml-blue-dark disabled:opacity-50"
                              >
                                + Crear cuenta
                              </button>
                            )}
                          </div>
                        </td>
                      </tr>
                    )
                  })}
                </tbody>
              </table></div>
            </div>
          )}
        </div>

      ) : tab === 'ctacte' && ccMode === 'list' ? (
        <div>
          <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-2 mb-3">
            <p className="text-xs text-gray-500 dark:text-gray-400 flex-1">
              Visión global de la cartera. Saldo, último movimiento y estado por cliente — vista derivada de los asientos. No genera asientos.
            </p>
            {canAdminAccounting && (
              <div className="flex flex-col sm:flex-row gap-2 shrink-0">
                <button
                  onClick={reconstruirCtaCte}
                  disabled={backfilling || recuperando || revirtiendo}
                  className="w-full sm:w-auto text-xs px-3 py-2 rounded-lg bg-ml-blue text-white font-medium hover:bg-ml-blue-dark disabled:opacity-50"
                  title="Genera las acreditaciones históricas en cada cuenta corriente a partir de las conciliaciones ya cargadas"
                >
                  {backfilling ? 'Reconstruyendo…' : '↻ Reconstruir desde conciliaciones'}
                </button>
                <button
                  onClick={recuperarPlanillasExtracto}
                  disabled={recuperando || backfilling || revirtiendo}
                  className="w-full sm:w-auto text-xs px-3 py-2 rounded-lg bg-emerald-600 text-white font-medium hover:bg-emerald-700 disabled:opacity-50"
                  title="Crea planillas faltantes a partir de los movimientos del extracto bancario que aún no tienen planilla vinculada"
                >
                  {recuperando ? 'Buscando…' : '🔍 Recuperar del extracto'}
                </button>
                <button
                  onClick={revertirPlanillasExtracto}
                  disabled={revirtiendo || recuperando || backfilling}
                  className="w-full sm:w-auto text-xs px-3 py-2 rounded-lg bg-red-600 text-white font-medium hover:bg-red-700 disabled:opacity-50"
                  title="Revierte las planillas creadas automáticamente desde el extracto (van a la papelera)"
                >
                  {revirtiendo ? 'Revirtiendo…' : '↩ Revertir del extracto'}
                </button>
                <button
                  onClick={limpiarClientesExtracto}
                  disabled={limpiando || revirtiendo || recuperando || backfilling}
                  className="w-full sm:w-auto text-xs px-3 py-2 rounded-lg bg-orange-600 text-white font-medium hover:bg-orange-700 disabled:opacity-50"
                  title="Elimina clientes creados automáticamente por la recuperación (solo tienen planillas auto-recuperadas)"
                >
                  {limpiando ? 'Limpiando…' : '🧹 Limpiar clientes'}
                </button>
              </div>
            )}
          </div>
          <div className="flex flex-wrap items-center gap-2 mb-3">
            <input
              type="text" placeholder="Buscar cliente…"
              value={ccBusqueda} onChange={e => setCcBusqueda(e.target.value)}
              className="input-field max-w-[200px]"
            />
            <div className="flex items-center gap-1 flex-wrap">
              {([
                ['todos', 'Todos'], ['deudores', 'Deudores'], ['acreedores', 'Acreedores'],
                ['cero', 'Saldo cero'], ['recientes', 'Recientes'], ['sin_actividad', 'Sin actividad'],
              ] as [CcFiltro, string][]).map(([f, label]) => (
                <button key={f} onClick={() => setCcFiltro(f)}
                  className={`px-2 py-1 rounded-md text-[11px] font-medium transition-colors ${
                    ccFiltro === f ? 'bg-ml-blue text-white' : 'bg-gray-100 dark:bg-slate-800 text-gray-600 dark:text-gray-400 hover:bg-gray-200 dark:hover:bg-slate-700'
                  }`}>{label}</button>
              ))}
            </div>
          </div>
          {loadingCartera ? (
            <div className="py-12 text-center text-gray-400">Cargando...</div>
          ) : (() => {
            const ahora = Date.now()
            const filtradas = cartera.filter(c => {
              if (ccBusqueda && !c.cliente_nombre.toLowerCase().includes(ccBusqueda.toLowerCase())) return false
              if (ccFiltro === 'deudores') return c.saldo > 0
              if (ccFiltro === 'acreedores') return c.saldo < 0
              if (ccFiltro === 'cero') return c.saldo === 0 && c.estado_general !== 'sin_actividad'
              if (ccFiltro === 'sin_actividad') return c.estado_general === 'sin_actividad'
              if (ccFiltro === 'recientes') return c.ultimo_movimiento != null && (ahora - new Date(c.ultimo_movimiento).getTime()) < 30 * 86400000
              return true
            })
            return filtradas.length === 0 ? (
              <p className="text-center py-8 text-gray-400 text-sm">Sin clientes para este filtro.</p>
            ) : (
              <div className="border border-gray-200 dark:border-slate-700 rounded-xl overflow-hidden">
                <div className="overflow-x-auto"><table className="w-full text-xs min-w-[560px]">
                  <thead className="bg-gray-50 dark:bg-slate-800">
                    <tr>
                      <th className="text-left px-3 py-2 font-medium text-gray-500">Cliente</th>
                      <th className="text-left px-3 py-2 font-medium text-gray-500">Cuenta</th>
                      <th className="text-right px-3 py-2 font-medium text-gray-500">Saldo</th>
                      <th className="text-left px-3 py-2 font-medium text-gray-500">Último mov.</th>
                      <th className="text-left px-3 py-2 font-medium text-gray-500">Estado</th>
                      <th className="text-right px-3 py-2 font-medium text-gray-500"></th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-100 dark:divide-slate-700/50">
                    {filtradas.map(c => {
                      const g = GEN_BADGE[c.estado_general]
                      return (
                        <tr key={c.cliente_id} className="hover:bg-gray-50 dark:hover:bg-slate-800/40 cursor-pointer" onClick={() => verCtaCteCliente(c.cliente_id)}>
                          <td className="px-3 py-2 font-medium text-ml-text dark:text-gray-200">{c.cliente_nombre}</td>
                          <td className="px-3 py-2 font-mono text-[11px] text-gray-400">{c.cuenta?.codigo}</td>
                          <td className="px-3 py-2 text-right font-mono text-gray-700 dark:text-gray-300">{fmtNum(c.saldo)}</td>
                          <td className="px-3 py-2 text-gray-500 dark:text-gray-400">{c.ultimo_movimiento ? fmtDate(c.ultimo_movimiento) : '—'}</td>
                          <td className="px-3 py-2"><span className={`text-[10px] px-1.5 py-0.5 rounded-full border ${g.cls}`} title={c.estado_general === 'sin_actividad' ? 'Cuenta vinculada sin movimientos contables (no implica inactividad comercial)' : undefined}>{g.label}</span></td>
                          <td className="px-3 py-2 text-right"><span className="text-ml-blue text-[11px] hover:underline">Ver →</span></td>
                        </tr>
                      )
                    })}
                  </tbody>
                </table></div>
              </div>
            )
          })()}
          <p className="text-[10px] text-gray-400 mt-2">
            "Sin actividad" = cuenta contable vinculada pero sin movimientos en la cuenta corriente. No implica inactividad comercial del cliente.
          </p>
        </div>

      ) : tab === 'ctacte' ? (
        <div>
          <div className="flex flex-wrap items-center gap-2 mb-3">
            <button onClick={() => { setCcMode('list'); setCtaCte(null); setCtaCteClienteId(''); cargarCartera() }}
              className="text-xs text-ml-blue hover:underline">← Volver a cartera</button>
            <select
              value={ctaCteClienteId}
              onChange={e => { const v = e.target.value ? Number(e.target.value) : ''; if (v) verCtaCteCliente(v) }}
              className="input-field max-w-[220px]"
            >
              <option value="">Elegí un cliente…</option>
              {cliCuentas.map(c => (
                <option key={c.cliente_id} value={c.cliente_id}>{c.cliente_nombre}</option>
              ))}
            </select>
            <div className="flex items-center gap-2 flex-wrap">
              {CAT_KEYS.map(cat => (
                <label key={cat} className="flex items-center gap-1 text-xs text-gray-600 dark:text-gray-300 cursor-pointer">
                  <input type="checkbox" checked={catFiltro.has(cat)} onChange={() => toggleCat(cat)} className="accent-ml-blue" />
                  {CAT_LABEL[cat]}
                </label>
              ))}
            </div>
          </div>

          {loadingCtaCte ? (
            <div className="py-12 text-center text-gray-400">Cargando...</div>
          ) : !ctaCte ? (
            <p className="text-center py-8 text-gray-400 text-sm">Elegí un cliente para ver su cuenta corriente.</p>
          ) : ctaCte.sin_cuenta ? (
            <div className="text-center py-8 text-sm text-amber-600 dark:text-amber-400">
              {ctaCte.cliente.nombre} no tiene cuenta contable vinculada. Vinculala en el tab 🔗 Clientes.
            </div>
          ) : (() => {
            const visibles = ctaCte.movimientos.filter(m => catFiltro.has(m.tipo_cat))
            return (
              <div>
                <div className="flex flex-wrap gap-3 mb-3 text-xs">
                  <span className="text-gray-500 dark:text-gray-400">Cuenta: <span className="font-mono text-amber-600 dark:text-amber-400">{ctaCte.cuenta?.codigo} {ctaCte.cuenta?.nombre}</span></span>
                  <span className="text-gray-500 dark:text-gray-400">Saldo: <b className="text-ml-text dark:text-white">{fmtNum(ctaCte.saldo_final)}</b></span>
                  <span className="text-gray-400">({visibles.length} de {ctaCte.movimientos.length} movimientos)</span>
                </div>
                {visibles.length === 0 ? (
                  <p className="text-center py-8 text-gray-400 text-sm">Sin movimientos para los filtros elegidos.</p>
                ) : (
                  <div className="border border-gray-200 dark:border-slate-700 rounded-xl overflow-hidden">
                    <div className="overflow-x-auto"><table className="w-full text-xs min-w-[640px]">
                      <thead className="bg-gray-50 dark:bg-slate-800">
                        <tr>
                          <th className="text-left px-3 py-2 font-medium text-gray-500">Fecha</th>
                          <th className="text-left px-3 py-2 font-medium text-gray-500">Tipo</th>
                          <th className="text-left px-3 py-2 font-medium text-gray-500">Referencia</th>
                          <th className="text-left px-3 py-2 font-medium text-gray-500">Estado</th>
                          <th className="text-right px-3 py-2 font-medium text-blue-600 dark:text-blue-400">Débito</th>
                          <th className="text-right px-3 py-2 font-medium text-orange-600 dark:text-orange-400">Crédito</th>
                          <th className="text-right px-3 py-2 font-medium text-gray-500">Saldo</th>
                          <th className="text-right px-3 py-2 font-medium text-gray-500">Origen</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-gray-100 dark:divide-slate-700/50">
                        {visibles.map((m, i) => (
                          <tr key={i} className="hover:bg-gray-50 dark:hover:bg-slate-800/40">
                            <td className="px-3 py-2 whitespace-nowrap text-gray-600 dark:text-gray-400">{fmtDate(m.fecha)}</td>
                            <td className="px-3 py-2 text-gray-700 dark:text-gray-300">{m.tipo_label}</td>
                            <td className="px-3 py-2 text-gray-700 dark:text-gray-300 max-w-[200px] truncate" title={m.referencia}>{m.referencia}</td>
                            <td className="px-3 py-2">
                              <span className={`text-[10px] px-1.5 py-0.5 rounded-full border ${ESTADO_BADGE[m.estado] || ''}`}>{m.estado}</span>
                            </td>
                            <td className="px-3 py-2 text-right font-mono text-blue-700 dark:text-blue-300">{m.debito > 0 ? fmtNum(m.debito) : ''}</td>
                            <td className="px-3 py-2 text-right font-mono text-orange-700 dark:text-orange-300">{m.credito > 0 ? fmtNum(m.credito) : ''}</td>
                            <td className="px-3 py-2 text-right font-mono text-gray-700 dark:text-gray-300">{fmtNum(m.saldo)}</td>
                            <td className="px-3 py-2 text-right whitespace-nowrap">
                              {m.origen.extracto_id && (
                                <a href={`/movimientos?extracto=${m.origen.extracto_id}`} className="text-ml-blue hover:underline mr-2" title="Movimiento bancario">🏦</a>
                              )}
                              {m.origen.planilla_id && (
                                <a href={`/historial?planilla=${m.origen.planilla_id}`} className="text-ml-blue hover:underline" title="Planilla origen">📄</a>
                              )}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                      <tfoot className="bg-gray-50 dark:bg-slate-800 border-t border-gray-200 dark:border-slate-700">
                        <tr>
                          <td colSpan={4} className="px-3 py-2 font-semibold text-gray-600 dark:text-gray-400">Totales (todos los movimientos)</td>
                          <td className="px-3 py-2 text-right font-mono font-semibold text-blue-700 dark:text-blue-300">{fmtNum(ctaCte.total_debito)}</td>
                          <td className="px-3 py-2 text-right font-mono font-semibold text-orange-700 dark:text-orange-300">{fmtNum(ctaCte.total_credito)}</td>
                          <td className="px-3 py-2 text-right font-mono font-semibold">{fmtNum(ctaCte.saldo_final)}</td>
                          <td></td>
                        </tr>
                      </tfoot>
                    </table></div>
                  </div>
                )}
              </div>
            )
          })()}
        </div>
      ) : null}
    </div>
  )
}
