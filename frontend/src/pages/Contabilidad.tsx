import React, { useEffect, useRef, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { apiClient } from '@/services/api'
import { useOrgStore } from '@/store/org'
import { useAuthStore } from '@/store/auth'
import { toast } from '@/store/toast'
import { confirmDialog } from '@/store/confirm'
import { localIsoDate } from '@/utils/fecha'

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
  if (!s) return '—'
  try {
    const m = s.match(/^(\d{4})-(\d{2})-(\d{2})/)
    if (m) return new Date(+m[1], +m[2] - 1, +m[3]).toLocaleDateString('es-AR', { day: '2-digit', month: '2-digit', year: 'numeric' })
    return new Date(s.endsWith('Z') ? s : s + 'Z').toLocaleDateString('es-AR', { day: '2-digit', month: '2-digit', year: 'numeric' })
  }
  catch { return s }
}
function fmtNum(n: number) { return n.toLocaleString('es-AR', { minimumFractionDigits: 2, maximumFractionDigits: 2 }) }

const MODULO_LABEL: Record<string, string> = {
  extracto: '🏦 Extracto', planilla: '📋 Planilla', caja: '💵 Caja', cheque: '🗒️ Cheque',
  ajuste_manual: '✏️ Ajuste manual', ajuste_manual_reverso: '↩️ Reverso ajuste',
  um_lote: '📥 UM lote', um_mov: '📥 UM mov', um_reclass: '🔀 Reclasif.', cc_inicial: '🔁 Backfill',
  cheque_registro: '🗒️ Cheque registro', cheque_acred_banco: '🗒️ Cheque banco', cheque_acred_cliente: '🗒️ Cheque cliente',
  cheque_rechazo_banco: '🗒️ Rechazo banco', cheque_rechazo_cliente: '🗒️ Rechazo cliente', cheque_rechazo_gasto: '🗒️ Rechazo gasto',
  egreso: '💸 Egreso', caja_op: '💵 Caja OP', caja_efectivo: '💵 Efectivo',
}

// ── Filtro desplegable tipo Excel ────────────────────────────
const ExcelFilterCtb: React.FC<{ label: string; active: boolean; align?: 'left'|'right'; children: React.ReactNode }> = ({ label, active, align = 'left', children }) => {
  const [open, setOpen] = useState(false)
  const ref = useRef<HTMLDivElement>(null)
  useEffect(() => {
    const fn = (e: MouseEvent) => { if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false) }
    document.addEventListener('mousedown', fn)
    return () => document.removeEventListener('mousedown', fn)
  }, [])
  return (
    <div ref={ref} className="relative flex items-center gap-1 cursor-pointer select-none" onClick={() => setOpen(o => !o)}>
      <span>{label}</span>
      <span className={`text-[10px] ${active ? 'text-yellow-400' : 'text-blue-200'}`}>{active ? '▼●' : '▼'}</span>
      {open && (
        <div className={`absolute top-full mt-1 z-50 bg-white dark:bg-slate-800 border border-gray-200 dark:border-slate-600 rounded-lg shadow-xl p-3 min-w-[210px] ${align === 'right' ? 'right-0' : 'left-0'}`}
          onClick={e => e.stopPropagation()}>
          {children}
        </div>
      )}
    </div>
  )
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
  plan:     'view_accounting',
  reglas:   'view_accounting',
  diario:   'view_accounting',
  sumas:    'view_accounting',
  balance:  'view_accounting',
  mayor:    'view_accounting',
  clientes: 'view_accounting',
  ctacte:   'manage_finance',
}

export const Contabilidad: React.FC<{ modo?: 'full' | 'ctacte' }> = ({ modo = 'full' }) => {
  const { activeOrgId } = useOrgStore()
  const { hasPermission, user } = useAuthStore()
  const canAdminAccounting = hasPermission('admin_accounting')
  const canViewAccounting  = hasPermission('view_accounting')
  const canManageFinance   = hasPermission('manage_finance')
  const [cuentas, setCuentas]         = useState<CuentaItem[]>([])
  const [reglas, setReglas]           = useState<ReglaItem[]>([])
  const [asientos, setAsientos]       = useState<AsientoItem[]>([])
  const [totalAsientos, setTotalAsientos] = useState(0)
  const firstRenderRef = useRef(true)
  const [diarioDesde, setDiarioDesde]   = useState('')
  const [diarioHasta, setDiarioHasta]   = useState('')
  const [diarioModulo, setDiarioModulo] = useState('')
  const [diarioCuentaId, setDiarioCuentaId] = useState<number | ''>('')
  const [diarioCuentaBusq, setDiarioCuentaBusq] = useState('')
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
    recargarTodo()
  }, [activeOrgId])

  const recargarTodo = () => {
    if (modo === 'ctacte') return
    const q = activeOrgId ? `?org_id=${activeOrgId}` : ''
    setLoading(true)
    cargarAsientos()  // dispara en paralelo, no espera los otros 4
    Promise.all([
      canViewAccounting
        ? apiClient.client.get(`/contabilidad/plan-cuentas${q}`).then(r => r.data)
        : Promise.resolve([]),
      canViewAccounting
        ? apiClient.client.get(`/contabilidad/reglas${q}`).then(r => r.data)
        : Promise.resolve([]),
      apiClient.client.get(`/contabilidad/sumas-saldo${q}`).then(r => r.data),
      apiClient.client.get(`/contabilidad/balance${q}`).then(r => r.data),
    ]).then(([c, r, ss, b]) => {
      setCuentas(c); setReglas(r)
      setSumasSaldo(ss); setBalance(b)
      setLoading(false)
    }).catch(() => setLoading(false))
  }

  const cargarAsientos = () => {
    const params = new URLSearchParams()
    params.set('limit', '2000')
    if (activeOrgId) params.set('org_id', String(activeOrgId))
    if (diarioDesde)    params.set('desde', diarioDesde)
    if (diarioHasta)    params.set('hasta', diarioHasta)
    if (diarioModulo)   params.set('modulo', diarioModulo)
    if (diarioCuentaId) params.set('cuenta_id', String(diarioCuentaId))
    apiClient.client.get(`/contabilidad/asientos?${params}`).then(r => {
      setAsientos(r.data.items)
      setTotalAsientos(r.data.total)
    })
  }

  useEffect(() => {
    // skip first render — recargarTodo handles the initial load and calls cargarAsientos() at the end
    if (firstRenderRef.current) { firstRenderRef.current = false; return }
    cargarAsientos()
  }, [diarioDesde, diarioHasta, diarioModulo, diarioCuentaId, activeOrgId])

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
    if (tab === 'clientes' && canViewAccounting) cargarClientesCuentas()
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
      .then(r => setCartera(r.data.items ?? []))
      .catch(() => setCartera([]))
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

  const resetYRebuild = async () => {
    const orgQ = activeOrgId ? `?org_id=${activeOrgId}` : ''
    try {
      // dry_run primero — muestra qué haría
      const prev = await apiClient.client.post(`/contabilidad/reset-y-rebuild?dry_run=true${orgQ ? '&' + orgQ.slice(1) : ''}`, {})
      const { a_borrar, a_crear } = prev.data
      const confirmar = window.confirm(
        `⚠️ RESET LIBRO DIARIO\n\n` +
        `Se van a BORRAR: ${a_borrar.asientos} asientos (${a_borrar.detalles} líneas)\n` +
        `Se van a CREAR: ${a_crear.total_asientos_nuevos} asientos nuevos\n` +
        `  · ${a_crear.um_lotes} lote(s) UM\n` +
        `  · ${a_crear.cc_iniciales} acreditaciones de clientes\n\n` +
        `¿Confirmar el reset?`
      )
      if (!confirmar) return
      const r = await apiClient.client.post(`/contabilidad/reset-y-rebuild?dry_run=false${orgQ ? '&' + orgQ.slice(1) : ''}`, {}, { timeout: 300000 })
      toast.success(r.data.msg)
      recargarTodo()
      cargarCartera()
    } catch (e: any) {
      const detail = e.response?.data?.detail || e.message || 'Error desconocido'
      alert(`❌ Error en el reset:\n\n${detail}`)
    }
  }

  // ── Fix fechas UTC — modal propio (reemplaza window.prompt que no anda en mobile) ──
  const [fixFechasOpen, setFixFechasOpen] = useState(false)
  const [fixDesde, setFixDesde] = useState('2026-05-31')
  const [fixHasta, setFixHasta] = useState('2026-06-01')
  const [fixDir, setFixDir] = useState<'adelantar' | 'atrasar'>('adelantar')
  const [fixSoloEgresos, setFixSoloEgresos] = useState(true)
  const [fixPreview, setFixPreview] = useState<null | { asientos_afectados: number; egresos_afectados: number; detalle_asientos: any[]; detalle_egresos: any[] }>(null)
  const [fixLoading, setFixLoading] = useState(false)
  const [fixMsg, setFixMsg] = useState('')

  const fixFechasDryRun = async () => {
    setFixLoading(true); setFixMsg(''); setFixPreview(null)
    const orgQ = activeOrgId ? `&org_id=${activeOrgId}` : ''
    const moduloQ = fixSoloEgresos ? '&modulo=egreso' : ''
    try {
      const r = await apiClient.client.post(`/contabilidad/fix-fechas-utc?dry_run=true&desde=${fixDesde}&hasta=${fixHasta}&direccion=${fixDir}${orgQ}${moduloQ}`)
      setFixPreview(r.data)
    } catch (e: any) {
      setFixMsg(`❌ ${e.response?.data?.detail || e.message}`)
    } finally { setFixLoading(false) }
  }

  const fixFechasEjecutar = async () => {
    setFixLoading(true); setFixMsg('')
    const orgQ = activeOrgId ? `&org_id=${activeOrgId}` : ''
    const moduloQ = fixSoloEgresos ? '&modulo=egreso' : ''
    try {
      const r = await apiClient.client.post(`/contabilidad/fix-fechas-utc?dry_run=false&desde=${fixDesde}&hasta=${fixHasta}&direccion=${fixDir}${orgQ}${moduloQ}`)
      setFixMsg(`✓ ${r.data.mensaje}`)
      setFixPreview(null)
      recargarTodo()
    } catch (e: any) {
      setFixMsg(`❌ ${e.response?.data?.detail || e.message}`)
    } finally { setFixLoading(false) }
  }

  const fixFechasUtc = () => { setFixFechasOpen(true); setFixPreview(null); setFixMsg('') }

  // ── Ajuste manual ───────────────────────────────────────────────────────────
  const [ajusteModalOpen, setAjusteModalOpen] = useState(false)
  const [ajusteGuardando, setAjusteGuardando] = useState(false)
  const [ajusteError, setAjusteError] = useState('')
  const [ajusteDebeId, setAjusteDebeId] = useState<number | ''>('')
  const [ajusteHaberId, setAjusteHaberId] = useState<number | ''>('')
  const [ajusteMonto, setAjusteMonto] = useState('')
  const [ajusteFecha, setAjusteFecha] = useState(localIsoDate())
  const [ajusteDesc, setAjusteDesc] = useState('')
  const [ajusteDebeBusq, setAjusteDebeBusq] = useState('')
  const [ajusteHaberBusq, setAjusteHaberBusq] = useState('')

  const submitAjusteManual = async () => {
    if (!ajusteDebeId || !ajusteHaberId || !ajusteMonto || !ajusteFecha) {
      setAjusteError('Completá todos los campos obligatorios')
      return
    }
    setAjusteGuardando(true)
    setAjusteError('')
    const orgQ = activeOrgId ? `?org_id=${activeOrgId}` : ''
    try {
      await apiClient.client.post(`/contabilidad/asiento-manual${orgQ}`, {
        cuenta_debe_id: ajusteDebeId,
        cuenta_haber_id: ajusteHaberId,
        monto: parseFloat(ajusteMonto),
        fecha: ajusteFecha,
        descripcion: ajusteDesc,
      })
      setAjusteModalOpen(false)
      setAjusteDebeId(''); setAjusteHaberId(''); setAjusteMonto(''); setAjusteDesc('')
      setAjusteDebeBusq(''); setAjusteHaberBusq('')
      recargarTodo()
    } catch (e: any) {
      setAjusteError(e.response?.data?.detail || 'Error al guardar')
    } finally {
      setAjusteGuardando(false)
    }
  }

  const deleteAjusteManual = async (asientoId: number) => {
    const orgQ = activeOrgId ? `?org_id=${activeOrgId}` : ''
    try {
      await apiClient.client.delete(`/contabilidad/asientos/${asientoId}${orgQ}`)
      recargarTodo()
    } catch (e: any) {
      alert(e.response?.data?.detail || 'No se pudo revertir el asiento')
    }
  }

  const [editFechaId, setEditFechaId] = useState<number | null>(null)
  const [editFechaVal, setEditFechaVal] = useState('')

  const saveFechaAsiento = async (asientoId: number) => {
    const orgQ = activeOrgId ? `?org_id=${activeOrgId}` : ''
    try {
      const r = await apiClient.client.patch(`/contabilidad/asientos/${asientoId}/fecha${orgQ}`, { fecha: editFechaVal })
      const nuevaFecha = r.data.fecha  // "YYYY-MM-DD" confirmado por el backend
      setAsientos(prev => prev.map(a => a.id === asientoId ? { ...a, fecha: nuevaFecha } : a))
      setEditFechaId(null)
    } catch (e: any) {
      alert(e.response?.data?.detail || 'No se pudo guardar')
    }
  }

  const [recuperandoCli, setRecuperandoCli] = useState(false)
  const [recModalOpen, setRecModalOpen] = useState(false)
  const [recCandidatos, setRecCandidatos] = useState<string[]>([])
  const [recSeleccion, setRecSeleccion] = useState<Set<string>>(new Set())
  const [recGuardando, setRecGuardando] = useState(false)

  const recuperarClientesBorrados = async () => {
    setRecuperandoCli(true)
    const orgQ = activeOrgId ? `&org_id=${activeOrgId}` : ''
    try {
      const prev = await apiClient.client.post(`/contabilidad/recuperar-clientes-borrados?dry_run=true${orgQ}`, {})
      const { clientes_a_recrear, nombres } = prev.data
      if (!clientes_a_recrear) {
        toast.success('No hay clientes para recuperar — todos los acreditados del extracto ya existen')
        return
      }
      setRecCandidatos(nombres as string[])
      setRecSeleccion(new Set())  // nada tildado por defecto → no recrear basura sin querer
      setRecModalOpen(true)
    } catch (e: any) {
      toast.error(e.response?.data?.detail || 'No se pudieron buscar los clientes')
    } finally {
      setRecuperandoCli(false)
    }
  }

  const toggleRecSel = (nombre: string) => {
    setRecSeleccion(prev => {
      const next = new Set(prev)
      next.has(nombre) ? next.delete(nombre) : next.add(nombre)
      return next
    })
  }

  const confirmarRecuperarClientes = async () => {
    if (recSeleccion.size === 0) { toast.error('Elegí al menos un cliente'); return }
    setRecGuardando(true)
    const orgQ = activeOrgId ? `?org_id=${activeOrgId}` : ''
    try {
      const r = await apiClient.client.post(
        `/contabilidad/recuperar-clientes-borrados${orgQ}`,
        { nombres: Array.from(recSeleccion) },
      )
      toast.success(`${r.data.recreados} cliente(s) recuperado(s) con su cuenta`)
      setRecModalOpen(false)
      cargarClientesCuentas()
    } catch (e: any) {
      toast.error(e.response?.data?.detail || 'No se pudieron recuperar los clientes')
    } finally {
      setRecGuardando(false)
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
  const parentIds = new Set(cuentas.map(c => c.parent_id).filter(Boolean))
  const cuentasHoja = cuentas.filter(c => !parentIds.has(c.id))
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
            : 'Plan de cuentas · Reglas · Libro diario · Sumas y saldo · Balance · Libro mayor'}
          {modo !== 'ctacte' && !canAdminAccounting && (
            <span className="ml-2 text-[10px] px-1.5 py-0.5 rounded-full bg-amber-50 dark:bg-amber-900/20 border border-amber-200 dark:border-amber-800 text-amber-600 dark:text-amber-400">
              solo lectura
            </span>
          )}
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
        <>
        {canAdminAccounting && (
          <div className="flex justify-end mb-3">
            <button
              onClick={() => { setAjusteError(''); setAjusteModalOpen(true) }}
              className="text-xs px-3 py-2 rounded-lg bg-ml-blue text-white font-medium hover:bg-ml-blue-dark flex items-center gap-1.5"
            >
              <span>✏️</span> Ajuste manual
            </button>
          </div>
        )}
        <div className="border border-gray-200 dark:border-slate-700 rounded-xl overflow-hidden">
          {asientos.length === 0 && !diarioDesde && !diarioHasta && !diarioModulo && !diarioCuentaId ? (
            <div className="py-16 text-center text-gray-400">
              <p className="text-3xl mb-2">📒</p>
              <p className="text-sm">Sin asientos todavía.</p>
              <p className="text-xs mt-1">Se generan automáticamente al subir extractos y conciliar planillas.</p>
            </div>
          ) : (
            <>
            {/* Barra de chips de filtros activos */}
            {(diarioDesde || diarioHasta || diarioModulo || diarioCuentaId) && (
              <div className="flex flex-wrap gap-2 px-3 py-2 bg-yellow-50 dark:bg-yellow-900/10 border-b border-yellow-200 dark:border-yellow-800 text-xs">
                <span className="text-gray-500">Filtros:</span>
                {diarioDesde && <span className="px-2 py-0.5 rounded-full bg-yellow-100 dark:bg-yellow-900/30 text-yellow-800 dark:text-yellow-300">Desde {diarioDesde}</span>}
                {diarioHasta && <span className="px-2 py-0.5 rounded-full bg-yellow-100 dark:bg-yellow-900/30 text-yellow-800 dark:text-yellow-300">Hasta {diarioHasta}</span>}
                {diarioModulo && <span className="px-2 py-0.5 rounded-full bg-yellow-100 dark:bg-yellow-900/30 text-yellow-800 dark:text-yellow-300">{(MODULO_LABEL[diarioModulo] || diarioModulo)}</span>}
                {diarioCuentaId && <span className="px-2 py-0.5 rounded-full bg-yellow-100 dark:bg-yellow-900/30 text-yellow-800 dark:text-yellow-300">
                  {cuentas.find(c => c.id === diarioCuentaId)?.nombre || `Cuenta #${diarioCuentaId}`}
                </span>}
                <button onClick={() => { setDiarioDesde(''); setDiarioHasta(''); setDiarioModulo(''); setDiarioCuentaId(''); setDiarioCuentaBusq('') }}
                  className="ml-auto text-gray-400 hover:text-red-500">✕ Limpiar</button>
              </div>
            )}
            <div className="overflow-x-auto"><table className="w-full text-xs min-w-[420px]">
              <thead className="bg-gray-50 dark:bg-slate-800 text-gray-500">
                <tr>
                  <th className="w-6 px-2 py-2"></th>
                  <th className="px-3 py-2 font-medium w-14 text-left">
                    <ExcelFilterCtb label="Nro" active={false}>
                      <p className="text-xs text-gray-400 mb-1">Los números se asignan al hacer el reset del Libro Diario.</p>
                    </ExcelFilterCtb>
                  </th>
                  <th className="px-3 py-2 font-medium text-left">
                    <ExcelFilterCtb label="Fecha" active={!!(diarioDesde || diarioHasta)}>
                      <div className="flex flex-col gap-2">
                        <label className="text-xs text-gray-500">Desde</label>
                        <input type="date" value={diarioDesde} onChange={e => setDiarioDesde(e.target.value)}
                          className="border border-gray-200 dark:border-slate-600 rounded px-2 py-1 text-xs bg-white dark:bg-slate-700 text-gray-800 dark:text-gray-200 w-full" />
                        <label className="text-xs text-gray-500">Hasta</label>
                        <input type="date" value={diarioHasta} onChange={e => setDiarioHasta(e.target.value)}
                          className="border border-gray-200 dark:border-slate-600 rounded px-2 py-1 text-xs bg-white dark:bg-slate-700 text-gray-800 dark:text-gray-200 w-full" />
                        {(diarioDesde || diarioHasta) && (
                          <button onClick={() => { setDiarioDesde(''); setDiarioHasta('') }} className="text-xs text-red-400 hover:text-red-600 text-left">✕ Limpiar</button>
                        )}
                      </div>
                    </ExcelFilterCtb>
                  </th>
                  <th className="px-3 py-2 font-medium text-left">
                    <ExcelFilterCtb label="Concepto" active={!!diarioModulo}>
                      <div className="flex flex-col gap-1">
                        {['', 'um_lote', 'um_reclass', 'cc_inicial', 'cheque_registro', 'cheque_acred_banco', 'cheque_acred_cliente', 'cheque_rechazo_banco', 'cheque_rechazo_cliente', 'cheque_rechazo_gasto', 'egreso', 'caja_op', 'caja_efectivo', 'ajuste_manual', 'ajuste_manual_reverso'].map(m => (
                          <button key={m} onClick={() => setDiarioModulo(m)}
                            className={`text-left px-2 py-1 rounded text-xs hover:bg-gray-100 dark:hover:bg-slate-700 ${diarioModulo === m ? 'bg-ml-blue text-white' : 'text-gray-700 dark:text-gray-300'}`}>
                            {m === '' ? '(Todos)' : (MODULO_LABEL[m] || m)}
                          </button>
                        ))}
                      </div>
                    </ExcelFilterCtb>
                  </th>
                  <th className="px-3 py-2 font-medium text-left">
                    <ExcelFilterCtb label="Cuenta" active={!!diarioCuentaId} align="right">
                      <div className="flex flex-col gap-2">
                        <input placeholder="Buscar cuenta..." value={diarioCuentaBusq} onChange={e => setDiarioCuentaBusq(e.target.value)}
                          className="border border-gray-200 dark:border-slate-600 rounded px-2 py-1 text-xs bg-white dark:bg-slate-700 text-gray-800 dark:text-gray-200 w-full" />
                        <div className="max-h-48 overflow-y-auto flex flex-col gap-0.5">
                          <button onClick={() => { setDiarioCuentaId(''); setDiarioCuentaBusq('') }}
                            className={`text-left px-2 py-1 rounded text-xs hover:bg-gray-100 dark:hover:bg-slate-700 ${!diarioCuentaId ? 'bg-ml-blue text-white' : 'text-gray-700 dark:text-gray-300'}`}>
                            (Todas)
                          </button>
                          {cuentas.filter(c => !diarioCuentaBusq || `${c.codigo} ${c.nombre}`.toLowerCase().includes(diarioCuentaBusq.toLowerCase())).map(c => (
                            <button key={c.id} onClick={() => setDiarioCuentaId(c.id)}
                              className={`text-left px-2 py-1 rounded text-xs hover:bg-gray-100 dark:hover:bg-slate-700 ${diarioCuentaId === c.id ? 'bg-ml-blue text-white' : 'text-gray-700 dark:text-gray-300'}`}>
                              <span className="font-mono">{c.codigo}</span> {c.nombre}
                            </button>
                          ))}
                        </div>
                      </div>
                    </ExcelFilterCtb>
                  </th>
                  <th className="px-3 py-2 font-medium text-left">Descripción</th>
                  {canAdminAccounting && <th className="w-8 px-2 py-2"></th>}
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
                        <td className="px-3 py-2 text-gray-400 font-mono">{(a as any).numero_asiento ?? a.id}</td>
                        <td className="px-3 py-2 whitespace-nowrap" onClick={e => e.stopPropagation()}>
                          {user?.is_superadmin && editFechaId === a.id ? (
                            <div className="flex flex-col gap-1 min-w-[130px]">
                              <input type="date" value={editFechaVal}
                                onChange={e => setEditFechaVal(e.target.value)}
                                className="text-xs border border-orange-300 dark:border-orange-600 rounded px-2 py-1 bg-white dark:bg-slate-800 text-gray-900 dark:text-white w-full"
                                onKeyDown={e => { if (e.key === 'Enter') saveFechaAsiento(a.id); if (e.key === 'Escape') setEditFechaId(null) }}
                                autoFocus
                              />
                              <button onClick={() => saveFechaAsiento(a.id)}
                                className="w-full text-xs px-2 py-1 rounded bg-orange-500 hover:bg-orange-600 text-white font-semibold">
                                Guardar
                              </button>
                            </div>
                          ) : (
                            <span
                              className={`text-gray-700 dark:text-gray-300 ${user?.is_superadmin ? 'cursor-pointer hover:underline hover:text-orange-600 dark:hover:text-orange-400' : ''}`}
                              title={user?.is_superadmin ? 'Clic para editar fecha' : undefined}
                              onClick={() => { if (user?.is_superadmin) { setEditFechaId(a.id); setEditFechaVal(a.fecha || '') } }}
                            >{fmtDate(a.fecha)}</span>
                          )}
                        </td>
                        <td className="px-3 py-2">
                          <span className="text-[10px] px-1.5 py-0.5 rounded bg-gray-100 dark:bg-slate-700 text-gray-500">
                            {(a.modulo && MODULO_LABEL[a.modulo]) || a.modulo || '—'}
                          </span>
                        </td>
                        <td className="px-3 py-2 max-w-[180px]">
                          {((a as any).cuentas as string[] || []).map((c, i) => (
                            <span key={i} className="block font-mono text-[10px] text-gray-500 dark:text-gray-400 truncate" title={c}>{c}</span>
                          ))}
                        </td>
                        <td className="px-3 py-2 text-gray-700 dark:text-gray-300">{a.descripcion || '—'}</td>
                        {canAdminAccounting && (
                          <td className="px-2 py-2 text-center" onClick={e => e.stopPropagation()}>
                            {a.modulo === 'ajuste_manual' && (
                              <button
                                onClick={() => { if (confirm('¿Revertir este ajuste manual?')) deleteAjusteManual(a.id) }}
                                className="text-red-400 hover:text-red-600 dark:hover:text-red-300 p-1 rounded hover:bg-red-50 dark:hover:bg-red-900/20"
                                title="Revertir ajuste"
                              >🗑️</button>
                            )}
                          </td>
                        )}
                      </tr>
                      {isOpen && (
                        <tr className="border-b border-gray-100 dark:border-slate-700/50 bg-gray-50/60 dark:bg-slate-800/30">
                          <td colSpan={canAdminAccounting ? 7 : 6} className="px-6 py-2">
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
                {asientos.length === 0 && (
                  <tr><td colSpan={canAdminAccounting ? 7 : 6} className="px-4 py-8 text-center text-gray-400 text-xs">Sin asientos para los filtros aplicados.</td></tr>
                )}
              </tbody>
            </table></div>
            </>
          )}
        </div>
        </>

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
                        $ {fmtNum(tipo === 'resultado' ? -(balance[tipo].saldo) : Math.abs(balance[tipo].saldo))}
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
            {canAdminAccounting && (
              <div className="flex flex-col sm:flex-row gap-2 shrink-0">
                <button
                  onClick={recuperarClientesBorrados}
                  disabled={recuperandoCli || creandoFaltantes}
                  className="text-xs px-3 py-2 rounded-lg bg-emerald-600 text-white font-medium hover:bg-emerald-700 disabled:opacity-50"
                  title="Recrea clientes que están acreditados en el extracto pero ya no existen, con su cuenta contable"
                >
                  {recuperandoCli ? 'Recuperando…' : '↺ Recuperar clientes borrados'}
                </button>
                <button
                  onClick={crearCuentasFaltantes}
                  disabled={creandoFaltantes || recuperandoCli}
                  className="text-xs px-3 py-2 rounded-lg bg-ml-blue text-white font-medium hover:bg-ml-blue-dark disabled:opacity-50"
                  title="Crea y vincula la cuenta contable de todos los clientes que aún no tienen una"
                >
                  {creandoFaltantes ? 'Creando…' : '+ Crear cuentas faltantes'}
                </button>
              </div>
            )}
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
                    {canAdminAccounting && <th className="text-right px-4 py-2 font-medium text-gray-500">Acciones</th>}
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
                        {canAdminAccounting && (
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
                        )}
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
                  disabled={backfilling}
                  className="w-full sm:w-auto text-xs px-3 py-2 rounded-lg bg-ml-blue text-white font-medium hover:bg-ml-blue-dark disabled:opacity-50"
                  title="Genera las acreditaciones históricas en cada cuenta corriente a partir de las conciliaciones ya cargadas"
                >
                  {backfilling ? 'Reconstruyendo…' : '↻ Reconstruir desde conciliaciones'}
                </button>
                {user?.is_superadmin && (
                  <>
                    <button
                      onClick={resetYRebuild}
                      disabled={backfilling}
                      className="w-full sm:w-auto text-xs px-3 py-2 rounded-lg border border-red-300 dark:border-red-800 text-red-600 dark:text-red-400 font-medium hover:bg-red-50 dark:hover:bg-red-900/20 disabled:opacity-50"
                      title="Borra TODOS los asientos y los reconstruye limpio desde los datos reales"
                    >
                      ⚠️ Reset Libro Diario
                    </button>
                    <button
                      onClick={fixFechasUtc}
                      className="w-full sm:w-auto text-xs px-3 py-2 rounded-lg border border-orange-300 dark:border-orange-800 text-orange-600 dark:text-orange-400 font-medium hover:bg-orange-50 dark:hover:bg-orange-900/20"
                      title="Identifica y corrige registros con fecha UTC en vez de ART"
                    >
                      🕐 Fix fechas UTC
                    </button>
                    <button
                      onClick={async () => {
                        const q = activeOrgId ? `?org_id=${activeOrgId}` : ''
                        const r = await apiClient.client.get(`/contabilidad/asientos/gaps${q}`)
                        const d = r.data
                        if (d.total_gaps === 0) {
                          alert(`✅ Secuencia completa: ${d.count} asientos, máximo #${d.max}, sin gaps.`)
                        } else {
                          alert(`⚠️ ${d.total_gaps} gap(s) en la secuencia (${d.count} activos, máx #${d.max}):\n\nNros faltantes: ${d.gaps.join(', ')}`)
                        }
                      }}
                      className="w-full sm:w-auto text-xs px-3 py-2 rounded-lg border border-gray-300 dark:border-gray-700 text-gray-600 dark:text-gray-400 font-medium hover:bg-gray-50 dark:hover:bg-gray-800"
                      title="Ver qué números de asiento están faltando en la secuencia"
                    >
                      🔍 Ver gaps
                    </button>
                  </>
                )}
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
                <div className="flex flex-wrap gap-3 mb-2 text-xs">
                  <span className="text-gray-500 dark:text-gray-400">Cuenta: <span className="font-mono text-amber-600 dark:text-amber-400">{ctaCte.cuenta?.codigo} {ctaCte.cuenta?.nombre}</span></span>
                  <span className="text-gray-400">({visibles.length} de {ctaCte.movimientos.length} movimientos)</span>
                </div>
                <div className="grid grid-cols-1 sm:grid-cols-3 gap-2 mb-3">
                  <div className="bg-blue-50 dark:bg-blue-900/20 border border-blue-200 dark:border-blue-800 rounded-lg px-3 py-2 flex sm:block items-center justify-between sm:text-center">
                    <p className="text-[10px] text-blue-600 dark:text-blue-400 font-medium">Total Débito</p>
                    <p className="font-mono text-sm font-semibold text-blue-700 dark:text-blue-300">{fmtNum(ctaCte.total_debito)}</p>
                  </div>
                  <div className="bg-orange-50 dark:bg-orange-900/20 border border-orange-200 dark:border-orange-800 rounded-lg px-3 py-2 flex sm:block items-center justify-between sm:text-center">
                    <p className="text-[10px] text-orange-600 dark:text-orange-400 font-medium">Total Crédito</p>
                    <p className="font-mono text-sm font-semibold text-orange-700 dark:text-orange-300">{fmtNum(ctaCte.total_credito)}</p>
                  </div>
                  <div className={`rounded-lg px-3 py-2 flex sm:block items-center justify-between sm:text-center border ${ctaCte.saldo_final >= 0 ? 'bg-green-50 dark:bg-green-900/20 border-green-200 dark:border-green-800' : 'bg-red-50 dark:bg-red-900/20 border-red-200 dark:border-red-800'}`}>
                    <p className={`text-[10px] font-medium ${ctaCte.saldo_final >= 0 ? 'text-green-600 dark:text-green-400' : 'text-red-600 dark:text-red-400'}`}>Saldo Final</p>
                    <p className={`font-mono text-sm font-bold ${ctaCte.saldo_final >= 0 ? 'text-green-700 dark:text-green-300' : 'text-red-700 dark:text-red-300'}`}>{fmtNum(ctaCte.saldo_final)}</p>
                  </div>
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
                            <td className="px-3 py-2 text-gray-700 dark:text-gray-300 max-w-[150px] truncate" title={m.referencia}>{m.referencia}</td>
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
                                <button onClick={async () => { try { await apiClient.downloadPlanillaConciliada(m.origen.planilla_id!) } catch { toast.error('No se pudo descargar') } }} className="text-ml-blue hover:underline" title="Descargar Excel planilla">📄</button>
                              )}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                      <tfoot className="bg-gray-50 dark:bg-slate-800 border-t border-gray-200 dark:border-slate-700">
                        <tr>
                          <td colSpan={3} className="px-3 py-2 font-semibold text-gray-600 dark:text-gray-400">Totales (todos los movimientos)</td>
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

      {recModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4" onClick={() => !recGuardando && setRecModalOpen(false)}>
          <div className="bg-white dark:bg-ml-dark-surface rounded-xl shadow-xl w-full max-w-md max-h-[80vh] flex flex-col" onClick={e => e.stopPropagation()}>
            <div className="p-4 border-b border-gray-200 dark:border-ml-dark-border">
              <h3 className="text-sm font-semibold text-ml-text dark:text-white">Recuperar clientes del extracto</h3>
              <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
                Tildá solo los clientes reales que querés recrear. Los demás (nombres sueltos del extracto) dejalos sin marcar.
              </p>
            </div>
            <div className="p-2 overflow-y-auto flex-1">
              <div className="flex items-center justify-between px-2 py-1 mb-1">
                <button
                  onClick={() => setRecSeleccion(new Set(recCandidatos))}
                  className="text-xs text-ml-blue dark:text-ml-green hover:underline"
                >Marcar todos</button>
                <button
                  onClick={() => setRecSeleccion(new Set())}
                  className="text-xs text-gray-500 hover:underline"
                >Limpiar</button>
              </div>
              {recCandidatos.map(nombre => (
                <label key={nombre} className="flex items-center gap-2 px-2 py-1.5 rounded hover:bg-gray-50 dark:hover:bg-white/5 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={recSeleccion.has(nombre)}
                    onChange={() => toggleRecSel(nombre)}
                    className="rounded"
                  />
                  <span className="text-sm text-ml-text dark:text-zinc-200">{nombre}</span>
                </label>
              ))}
            </div>
            <div className="p-4 border-t border-gray-200 dark:border-ml-dark-border flex items-center justify-between gap-2">
              <span className="text-xs text-gray-500">{recSeleccion.size} seleccionado(s)</span>
              <div className="flex gap-2">
                <button
                  onClick={() => setRecModalOpen(false)}
                  disabled={recGuardando}
                  className="text-xs px-3 py-2 rounded-lg border border-gray-300 dark:border-ml-dark-border text-gray-600 dark:text-zinc-300 disabled:opacity-50"
                >Cancelar</button>
                <button
                  onClick={confirmarRecuperarClientes}
                  disabled={recGuardando || recSeleccion.size === 0}
                  className="text-xs px-3 py-2 rounded-lg bg-emerald-600 text-white font-medium hover:bg-emerald-700 disabled:opacity-50"
                >{recGuardando ? 'Recuperando…' : `Recuperar ${recSeleccion.size || ''}`}</button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* ── Modal Ajuste Manual ──────────────────────────────────── */}
      {ajusteModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4" onClick={() => !ajusteGuardando && setAjusteModalOpen(false)}>
          <div className="bg-white dark:bg-ml-dark-surface rounded-xl shadow-xl w-full max-w-lg" onClick={e => e.stopPropagation()}>
            <div className="p-4 border-b border-gray-200 dark:border-ml-dark-border">
              <h3 className="text-sm font-semibold text-ml-text dark:text-white">✏️ Ajuste manual del Libro Diario</h3>
              <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">Solo cuentas hoja. El asiento es reversible con 🗑️ en la tabla.</p>
            </div>
            <div className="p-4 flex flex-col gap-4">
              <div>
                <label className="block text-xs font-medium text-blue-600 dark:text-blue-400 mb-1">Cuenta Debe *</label>
                <input type="text" placeholder="Buscar cuenta…" value={ajusteDebeBusq} onChange={e => setAjusteDebeBusq(e.target.value)}
                  className="border border-gray-200 dark:border-slate-600 rounded px-2 py-1.5 text-xs bg-white dark:bg-slate-700 text-gray-800 dark:text-gray-200 w-full mb-1" />
                <div className="max-h-36 overflow-y-auto border border-gray-100 dark:border-slate-700 rounded">
                  {cuentasHoja.filter(c => !ajusteDebeBusq || `${c.codigo} ${c.nombre}`.toLowerCase().includes(ajusteDebeBusq.toLowerCase())).map(c => (
                    <button key={c.id} onClick={() => { setAjusteDebeId(c.id); setAjusteDebeBusq(`${c.codigo} ${c.nombre}`) }}
                      className={`w-full text-left px-2 py-1 text-xs hover:bg-gray-50 dark:hover:bg-slate-700 ${ajusteDebeId === c.id ? 'bg-blue-50 dark:bg-blue-900/20 text-blue-700 dark:text-blue-300' : 'text-gray-700 dark:text-gray-300'}`}>
                      <span className="font-mono text-gray-400 mr-1">{c.codigo}</span>{c.nombre}
                    </button>
                  ))}
                </div>
              </div>
              <div>
                <label className="block text-xs font-medium text-orange-600 dark:text-orange-400 mb-1">Cuenta Haber *</label>
                <input type="text" placeholder="Buscar cuenta…" value={ajusteHaberBusq} onChange={e => setAjusteHaberBusq(e.target.value)}
                  className="border border-gray-200 dark:border-slate-600 rounded px-2 py-1.5 text-xs bg-white dark:bg-slate-700 text-gray-800 dark:text-gray-200 w-full mb-1" />
                <div className="max-h-36 overflow-y-auto border border-gray-100 dark:border-slate-700 rounded">
                  {cuentasHoja.filter(c => !ajusteHaberBusq || `${c.codigo} ${c.nombre}`.toLowerCase().includes(ajusteHaberBusq.toLowerCase())).map(c => (
                    <button key={c.id} onClick={() => { setAjusteHaberId(c.id); setAjusteHaberBusq(`${c.codigo} ${c.nombre}`) }}
                      className={`w-full text-left px-2 py-1 text-xs hover:bg-gray-50 dark:hover:bg-slate-700 ${ajusteHaberId === c.id ? 'bg-orange-50 dark:bg-orange-900/20 text-orange-700 dark:text-orange-300' : 'text-gray-700 dark:text-gray-300'}`}>
                      <span className="font-mono text-gray-400 mr-1">{c.codigo}</span>{c.nombre}
                    </button>
                  ))}
                </div>
              </div>
              <div className="flex gap-3">
                <div className="flex-1">
                  <label className="block text-xs font-medium text-gray-600 dark:text-gray-400 mb-1">Monto *</label>
                  <input type="number" min="0.01" step="0.01" placeholder="0.00" value={ajusteMonto} onChange={e => setAjusteMonto(e.target.value)}
                    className="border border-gray-200 dark:border-slate-600 rounded px-2 py-1.5 text-xs bg-white dark:bg-slate-700 text-gray-800 dark:text-gray-200 w-full" />
                </div>
                <div className="flex-1">
                  <label className="block text-xs font-medium text-gray-600 dark:text-gray-400 mb-1">Fecha *</label>
                  <input type="date" value={ajusteFecha} onChange={e => setAjusteFecha(e.target.value)}
                    className="border border-gray-200 dark:border-slate-600 rounded px-2 py-1.5 text-xs bg-white dark:bg-slate-700 text-gray-800 dark:text-gray-200 w-full" />
                </div>
              </div>
              <div>
                <label className="block text-xs font-medium text-gray-600 dark:text-gray-400 mb-1">Descripción</label>
                <input type="text" placeholder="Descripción del ajuste…" value={ajusteDesc} onChange={e => setAjusteDesc(e.target.value)}
                  className="border border-gray-200 dark:border-slate-600 rounded px-2 py-1.5 text-xs bg-white dark:bg-slate-700 text-gray-800 dark:text-gray-200 w-full" />
              </div>
              {ajusteError && <p className="text-xs text-red-500">{ajusteError}</p>}
            </div>
            <div className="p-4 border-t border-gray-200 dark:border-ml-dark-border flex justify-end gap-2">
              <button onClick={() => setAjusteModalOpen(false)} disabled={ajusteGuardando}
                className="text-xs px-3 py-2 rounded-lg border border-gray-300 dark:border-ml-dark-border text-gray-600 dark:text-zinc-300 disabled:opacity-50">
                Cancelar
              </button>
              <button onClick={submitAjusteManual} disabled={ajusteGuardando || !ajusteDebeId || !ajusteHaberId || !ajusteMonto}
                className="text-xs px-4 py-2 rounded-lg bg-ml-blue text-white font-medium hover:bg-ml-blue-dark disabled:opacity-50">
                {ajusteGuardando ? 'Guardando…' : 'Registrar asiento'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ── Modal Fix Fechas UTC ───────────────────────────────────────── */}
      {fixFechasOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
          <div className="bg-white dark:bg-ml-dark-surface rounded-2xl shadow-xl w-full max-w-md">
            <div className="p-4 border-b border-gray-200 dark:border-ml-dark-border flex items-center justify-between">
              <h3 className="font-semibold text-gray-900 dark:text-white text-sm">🕐 Corrección de fechas en Libro Diario</h3>
              <button onClick={() => setFixFechasOpen(false)} className="text-gray-400 hover:text-gray-600 dark:hover:text-gray-200">✕</button>
            </div>
            <div className="p-4 space-y-3">
              <p className="text-xs text-gray-500 dark:text-zinc-400">
                Corrige egresos o asientos cuya fecha quedó 1 día adelantada o atrasada por diferencia UTC/ART.
              </p>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs text-gray-500 mb-1">Desde</label>
                  <input type="date" value={fixDesde} onChange={e => { setFixDesde(e.target.value); setFixPreview(null) }}
                    className="input-field w-full text-sm" />
                </div>
                <div>
                  <label className="block text-xs text-gray-500 mb-1">Hasta</label>
                  <input type="date" value={fixHasta} onChange={e => { setFixHasta(e.target.value); setFixPreview(null) }}
                    className="input-field w-full text-sm" />
                </div>
              </div>
              <div>
                <label className="block text-xs text-gray-500 mb-1">Dirección</label>
                <select value={fixDir} onChange={e => { setFixDir(e.target.value as any); setFixPreview(null) }}
                  className="input-field w-full text-sm">
                  <option value="adelantar">Adelantar +1 día (muestran 1 día antes de lo correcto)</option>
                  <option value="atrasar">Atrasar −1 día (muestran 1 día después de lo correcto)</option>
                </select>
              </div>
              <label className="flex items-center gap-2 text-xs text-gray-600 dark:text-zinc-400 cursor-pointer">
                <input type="checkbox" checked={fixSoloEgresos} onChange={e => { setFixSoloEgresos(e.target.checked); setFixPreview(null) }} className="rounded" />
                Solo egresos (no tocar asientos de cheques, UM, etc.)
              </label>

              {fixPreview && (
                <div className="bg-orange-50 dark:bg-orange-900/20 border border-orange-200 dark:border-orange-700 rounded-lg p-3 text-xs space-y-1">
                  <p className="font-semibold text-orange-800 dark:text-orange-300">
                    Afectados: {fixPreview.asientos_afectados} asientos + {fixPreview.egresos_afectados} egresos
                  </p>
                  {[...fixPreview.detalle_asientos, ...fixPreview.detalle_egresos].slice(0, 5).map((a: any, i) => (
                    <p key={i} className="text-orange-700 dark:text-orange-400 truncate">
                      #{a.id} · {a.fecha_actual} → {a.fecha_nueva} · {a.descripcion}
                    </p>
                  ))}
                  {(fixPreview.asientos_afectados + fixPreview.egresos_afectados) > 5 && (
                    <p className="text-orange-600 dark:text-orange-500">…y más</p>
                  )}
                </div>
              )}

              {fixMsg && (
                <p className={`text-xs rounded-lg px-3 py-2 ${fixMsg.startsWith('✓') ? 'bg-green-50 dark:bg-green-900/20 text-green-700 dark:text-green-400' : 'bg-red-50 dark:bg-red-900/20 text-red-700 dark:text-red-400'}`}>
                  {fixMsg}
                </p>
              )}
            </div>
            <div className="p-4 border-t border-gray-200 dark:border-ml-dark-border flex flex-wrap justify-end gap-2">
              <button onClick={() => setFixFechasOpen(false)} className="text-xs px-3 py-2 rounded-lg border border-gray-300 dark:border-ml-dark-border text-gray-600 dark:text-zinc-300">
                Cerrar
              </button>
              <button onClick={fixFechasDryRun} disabled={fixLoading || !fixDesde || !fixHasta}
                className="text-xs px-3 py-2 rounded-lg border border-orange-300 dark:border-orange-700 text-orange-700 dark:text-orange-300 hover:bg-orange-50 dark:hover:bg-orange-900/20 disabled:opacity-50">
                {fixLoading && !fixPreview ? 'Buscando…' : '🔍 Vista previa'}
              </button>
              {fixPreview && (fixPreview.asientos_afectados + fixPreview.egresos_afectados) > 0 && (
                <button onClick={fixFechasEjecutar} disabled={fixLoading}
                  className="text-xs px-4 py-2 rounded-lg bg-orange-600 text-white font-medium hover:bg-orange-700 disabled:opacity-50">
                  {fixLoading ? 'Corrigiendo…' : `✓ Corregir ${fixPreview.asientos_afectados + fixPreview.egresos_afectados} registros`}
                </button>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
