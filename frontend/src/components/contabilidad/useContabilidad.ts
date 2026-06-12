import { useEffect, useRef, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { apiClient } from '@/services/api'
import { useOrgStore } from '@/store/org'
import { useAuthStore } from '@/store/auth'
import { toast } from '@/store/toast'
import { localIsoDate } from '@/utils/fecha'
import {
  CarteraItem, ClienteCuentaRow, CuentaCliente, CtaCteData, CuentaItem, ReglaItem,
  AsientoItem, AsientoLinea, SumaRow, BalanceData, LibroMayorData, FixPreview,
  Tab, CcFiltro, TAB_PERM, CAT_KEYS,
} from './shared'

export function useContabilidad(modo: 'full' | 'ctacte') {
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
      setBackfilling(true)
      // dry_run primero — muestra qué haría
      const prev = await apiClient.client.post(`/contabilidad/reset-y-rebuild?dry_run=true${orgQ ? '&' + orgQ.slice(1) : ''}`, {})
      const { a_borrar, a_crear } = prev.data
      const confirmar = window.confirm(
        `🧹 EMPEZAR LIMPIO — Libro Diario\n\n` +
        `Borra TODOS los asientos y reconstruye desde cero, prolijo y numerado desde 1, ` +
        `usando solo las fuentes confiables: importaciones del banco (UM) y conciliaciones agrupadas por planilla. ` +
        `Vincula la cuenta de cada cliente automáticamente.\n\n` +
        `Se van a BORRAR: ${a_borrar.asientos} asientos (${a_borrar.detalles} líneas)\n` +
        `Se van a CREAR: ${a_crear.total_asientos_nuevos} asientos limpios\n` +
        `  · ${a_crear.um_lotes} lote(s) de banco (UM)\n` +
        `  · ${a_crear.um_reclass_planilla} transferencia(s) conciliada(s) (TT)\n\n` +
        `¿Confirmás empezar limpio?`
      )
      if (!confirmar) return
      const r = await apiClient.client.post(`/contabilidad/reset-y-rebuild?dry_run=false${orgQ ? '&' + orgQ.slice(1) : ''}`, {}, { timeout: 300000 })
      toast.success(r.data.msg)
      recargarTodo()
      cargarCartera()
    } catch (e: any) {
      const detail = e.response?.data?.detail || e.message || 'Error desconocido'
      alert(`❌ Error al empezar limpio:\n\n${detail}`)
    } finally {
      setBackfilling(false)
    }
  }

  const verGaps = async () => {
    const q = activeOrgId ? `?org_id=${activeOrgId}` : ''
    const r = await apiClient.client.get(`/contabilidad/asientos/gaps${q}`)
    const d = r.data
    if (d.total_gaps === 0) {
      alert(`✅ Secuencia completa: ${d.count} asientos, máximo #${d.max}, sin gaps.`)
    } else {
      alert(`⚠️ ${d.total_gaps} gap(s) en la secuencia (${d.count} activos, máx #${d.max}):\n\nNros faltantes: ${d.gaps.join(', ')}`)
    }
  }

  // ── Fix fechas UTC — modal propio (reemplaza window.prompt que no anda en mobile) ──
  const [fixFechasOpen, setFixFechasOpen] = useState(false)
  const [fixDesde, setFixDesde] = useState('2026-05-31')
  const [fixHasta, setFixHasta] = useState('2026-06-01')
  const [fixDir, setFixDir] = useState<'adelantar' | 'atrasar'>('adelantar')
  const [fixSoloEgresos, setFixSoloEgresos] = useState(true)
  const [fixPreview, setFixPreview] = useState<null | FixPreview>(null)
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

  return {
    modo, user, activeOrgId,
    canAdminAccounting, canViewAccounting, canManageFinance,
    cuentas, reglas, asientos, totalAsientos,
    diarioDesde, setDiarioDesde, diarioHasta, setDiarioHasta, diarioModulo, setDiarioModulo,
    diarioCuentaId, setDiarioCuentaId, diarioCuentaBusq, setDiarioCuentaBusq,
    sumasSaldo, balance, libroMayor, setLibroMayor, mayorCuentaId, setMayorCuentaId,
    loading, loadingMayor, openAsientos, asientoLineas, loadingLineas,
    tab, setTab,
    cliCuentas, cuentasDisp, loadingCli, savingCli,
    ctaCte, ctaCteClienteId, loadingCtaCte, catFiltro, ccMode, setCcMode,
    cartera, loadingCartera, ccFiltro, setCcFiltro, ccBusqueda, setCcBusqueda,
    setCtaCte, setCtaCteClienteId,
    recargarTodo, cargarLibroMayor, cargarCartera, verCtaCteCliente, toggleCat,
    asignarCuenta, crearCuenta, crearCuentasFaltantes, resetYRebuild, verGaps,
    backfilling, creandoFaltantes,
    // fix fechas
    fixFechasOpen, setFixFechasOpen, fixDesde, setFixDesde, fixHasta, setFixHasta,
    fixDir, setFixDir, fixSoloEgresos, setFixSoloEgresos, fixPreview, setFixPreview,
    fixLoading, fixMsg, fixFechasDryRun, fixFechasEjecutar, fixFechasUtc,
    // ajuste manual
    ajusteModalOpen, setAjusteModalOpen, ajusteGuardando, ajusteError, setAjusteError,
    ajusteDebeId, setAjusteDebeId, ajusteHaberId, setAjusteHaberId,
    ajusteMonto, setAjusteMonto, ajusteFecha, setAjusteFecha, ajusteDesc, setAjusteDesc,
    ajusteDebeBusq, setAjusteDebeBusq, ajusteHaberBusq, setAjusteHaberBusq,
    submitAjusteManual, deleteAjusteManual,
    // edición fecha asiento
    editFechaId, setEditFechaId, editFechaVal, setEditFechaVal, saveFechaAsiento,
    // recuperar clientes
    recuperandoCli, recModalOpen, setRecModalOpen, recCandidatos, recSeleccion, setRecSeleccion,
    recGuardando, recuperarClientesBorrados, toggleRecSel, confirmarRecuperarClientes,
    // asientos
    toggleAsiento,
    // derivados del plan de cuentas
    raices, cuentasHoja, hijos,
  }
}

export type ContabilidadCtx = ReturnType<typeof useContabilidad>
