import React, { useCallback, useEffect, useMemo, useState } from 'react'
import { apiClient } from '@/services/api'
import { confirmDialog } from '@/store/confirm'
import { useOrgStore } from '@/store/org'
import { useAuthStore } from '@/store/auth'
import { localIsoDate } from '@/utils/fecha'
import type {
  SueldosConfig,
  SueldosConvenio,
  SueldosCategoria,
  SueldosEmpleado,
  SueldosLiquidacionPreview,
  SueldosLiquidacion,
} from '@/types'

// ── Helpers ─────────────────────────────────────────────────────────────────
const fmt = (n: number) =>
  new Intl.NumberFormat('es-AR', { style: 'currency', currency: 'ARS', minimumFractionDigits: 2 }).format(n || 0)

function mesActual(): string {
  const d = new Date(localIsoDate())
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}`
}

function mesesRecientes(): string[] {
  const d = new Date(localIsoDate())
  let anio = d.getFullYear()
  let mes = d.getMonth() + 1
  const out: string[] = []
  for (let i = 0; i < 12; i++) {
    out.push(`${anio}-${String(mes).padStart(2, '0')}`)
    mes -= 1
    if (mes === 0) { mes = 12; anio -= 1 }
  }
  return out
}

const inputClass =
  'w-full px-3 py-2 rounded-lg border bg-white dark:bg-white/5 border-gray-300 dark:border-white/10 text-gray-900 dark:text-gray-100 placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-ml-blue/40 text-sm'

const ESTADO_BADGE: Record<string, string> = {
  borrador: 'bg-gray-100 text-gray-600 dark:bg-white/10 dark:text-gray-300',
  aprobado: 'bg-amber-100 text-amber-700 dark:bg-amber-500/15 dark:text-amber-300',
  presentado: 'bg-green-100 text-green-700 dark:bg-green-500/15 dark:text-green-300',
}

const ESTADO_LABEL: Record<string, string> = {
  borrador: 'Borrador', aprobado: 'Aprobado', presentado: 'Presentado',
}

/** % escrito por el usuario → fracción 0..1. Acepta "11", "11,5", "0.11". */
function parseTasaInput(raw: string): number | null {
  const s = (raw ?? '').trim().replace('%', '').replace(',', '.')
  if (s === '') return 0
  const n = parseFloat(s)
  if (isNaN(n) || n < 0) return null
  const frac = n > 1 ? n / 100 : n
  if (frac > 1) return null
  return frac
}

function parseMonto(raw: string): number | null {
  const s = (raw ?? '').trim().replace(/\./g, '').replace(',', '.')
  if (s === '') return null
  const n = parseFloat(s)
  return isNaN(n) || n < 0 ? null : n
}

const IconCalc = () => (
  <svg className="w-4 h-4" fill="none" stroke="currentColor" strokeWidth={1.8} viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" d="M9 7.5h6m-6 3h6m-6 3h3m-9 4.5h12a2.25 2.25 0 002.25-2.25V5.25A2.25 2.25 0 0015 3H6a2.25 2.25 0 00-2.25 2.25v13.5A2.25 2.25 0 006 21z" /></svg>
)
const IconCheck = () => (
  <svg className="w-4 h-4" fill="none" stroke="currentColor" strokeWidth={1.8} viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" d="M9 12.75L11.25 15 15 9.75M21 12a9 9 0 11-18 0 9 9 0 0118 0z" /></svg>
)

// Campos de alícuota: [key, label, grupo]
const APORTES: Array<[keyof SueldosConfig, string]> = [
  ['aporte_jubilacion', 'Jubilación'],
  ['aporte_inssjp', 'INSSJP (PAMI)'],
  ['aporte_obra_social', 'Obra social'],
]
const CONTRIBUCIONES: Array<[keyof SueldosConfig, string]> = [
  ['contrib_jubilacion', 'Jubilación'],
  ['contrib_inssjp', 'INSSJP (ley 19032)'],
  ['contrib_obra_social', 'Obra social'],
  ['contrib_asig_fam', 'Asignaciones familiares'],
  ['contrib_fondo_desempleo', 'Fondo de desempleo'],
  ['alicuota_art', 'ART (completar con tu póliza)'],
]

export const Sueldos: React.FC = () => {
  const { activeOrgId } = useOrgStore()
  const { hasPermission } = useAuthStore()
  const canManageFinance = hasPermission('manage_finance')
  const canAdminAccounting = hasPermission('admin_accounting')

  const [tab, setTab] = useState<'empleados' | 'liquidacion' | 'historial' | 'config'>('empleados')
  const [msg, setMsg] = useState<{ type: 'error' | 'ok'; text: string } | null>(null)

  // ── Config base (determina si el módulo está activo) ─────────────────────
  const [config, setConfig] = useState<SueldosConfig | null>(null)
  const [configLoaded, setConfigLoaded] = useState(false)

  const cargarConfigBase = useCallback(async () => {
    try {
      // GET /config requiere admin_accounting; si no tiene, derivamos "activo" del preview
      if (canAdminAccounting) {
        const data = await apiClient.getSueldosConfig(activeOrgId || undefined)
        setConfig(data)
      }
    } catch {
      setConfig(null)
    } finally {
      setConfigLoaded(true)
    }
  }, [activeOrgId, canAdminAccounting])

  useEffect(() => { cargarConfigBase() }, [cargarConfigBase])

  // ── Tab Empleados ─────────────────────────────────────────────────────────
  const [convenios, setConvenios] = useState<SueldosConvenio[]>([])
  const [categorias, setCategorias] = useState<Record<number, SueldosCategoria[]>>({})
  const [empleados, setEmpleados] = useState<SueldosEmpleado[]>([])
  const [empLoading, setEmpLoading] = useState(false)

  // form empleado
  const [empNombre, setEmpNombre] = useState('')
  const [empCuil, setEmpCuil] = useState('')
  const [empConvenio, setEmpConvenio] = useState('')
  const [empCategoria, setEmpCategoria] = useState('')
  const [empBasico, setEmpBasico] = useState('')
  const [empCargas, setEmpCargas] = useState('0')
  const [empEditId, setEmpEditId] = useState<number | null>(null)
  const [empSaving, setEmpSaving] = useState(false)

  // form convenio
  const [convNombre, setConvNombre] = useState('')
  const [convSaving, setConvSaving] = useState(false)

  const cargarConvenios = useCallback(async () => {
    try {
      const data = await apiClient.getSueldosConvenios(activeOrgId || undefined)
      setConvenios(data.items || [])
    } catch {
      setConvenios([])
    }
  }, [activeOrgId])

  const cargarEmpleados = useCallback(async () => {
    setEmpLoading(true)
    try {
      const data = await apiClient.getSueldosEmpleados({ orgId: activeOrgId || undefined, incluirInactivos: true, limit: 500 })
      setEmpleados(data.items || [])
    } catch {
      setEmpleados([])
    } finally {
      setEmpLoading(false)
    }
  }, [activeOrgId])

  useEffect(() => {
    if (tab === 'empleados') { cargarConvenios(); cargarEmpleados() }
  }, [tab, cargarConvenios, cargarEmpleados])

  const cargarCategoriasDe = useCallback(async (convenioId: number) => {
    try {
      const data = await apiClient.getSueldosCategorias(convenioId, activeOrgId || undefined)
      setCategorias(prev => ({ ...prev, [convenioId]: data.items || [] }))
    } catch {
      setCategorias(prev => ({ ...prev, [convenioId]: [] }))
    }
  }, [activeOrgId])

  useEffect(() => {
    if (empConvenio) cargarCategoriasDe(Number(empConvenio))
  }, [empConvenio, cargarCategoriasDe])

  const resetEmpForm = () => {
    setEmpNombre(''); setEmpCuil(''); setEmpConvenio(''); setEmpCategoria('')
    setEmpBasico(''); setEmpCargas('0'); setEmpEditId(null)
  }

  const abrirEditar = (e: SueldosEmpleado) => {
    setEmpEditId(e.id)
    setEmpNombre(e.nombre)
    setEmpCuil(e.cuil || '')
    setEmpConvenio(e.convenio_id ? String(e.convenio_id) : '')
    setEmpCategoria(e.categoria_id ? String(e.categoria_id) : '')
    setEmpBasico(e.sueldo_basico != null ? String(e.sueldo_basico) : '')
    setEmpCargas(String(e.cargas_familia))
  }

  const guardarEmpleado = async () => {
    const nombre = empNombre.trim()
    if (!nombre) { setMsg({ type: 'error', text: 'Ingresá el nombre del empleado.' }); return }
    const basico = empBasico.trim() ? parseMonto(empBasico) : null
    if (empBasico.trim() && basico === null) { setMsg({ type: 'error', text: 'Sueldo básico inválido.' }); return }
    setEmpSaving(true); setMsg(null)
    try {
      const body = {
        nombre,
        cuil: empCuil.trim() || null,
        convenio_id: empConvenio ? Number(empConvenio) : null,
        categoria_id: empCategoria ? Number(empCategoria) : null,
        sueldo_basico: basico,
        cargas_familia: Number(empCargas) || 0,
      }
      if (empEditId != null) {
        await apiClient.updateSueldosEmpleado(empEditId, body, activeOrgId || undefined)
        setMsg({ type: 'ok', text: 'Empleado actualizado.' })
      } else {
        await apiClient.createSueldosEmpleado(body, activeOrgId || undefined)
        setMsg({ type: 'ok', text: 'Empleado creado.' })
      }
      resetEmpForm()
      await cargarEmpleados()
    } catch (e: unknown) {
      const detail = (e as { response?: { data?: { detail?: unknown } } })?.response?.data?.detail
      setMsg({ type: 'error', text: typeof detail === 'string' ? detail : 'No se pudo guardar el empleado.' })
    } finally {
      setEmpSaving(false)
    }
  }

  const borrarEmpleado = async (e: SueldosEmpleado) => {
    const ok = await confirmDialog({
      title: 'Eliminar empleado',
      message: `¿Eliminar a "${e.nombre}"? Quedará archivado (soft delete) y no se incluirá en futuras liquidaciones.`,
      confirmLabel: 'Eliminar', danger: true,
    })
    if (!ok) return
    try {
      await apiClient.deleteSueldosEmpleado(e.id, activeOrgId || undefined)
      await cargarEmpleados()
    } catch {
      setMsg({ type: 'error', text: 'No se pudo eliminar el empleado.' })
    }
  }

  const crearConvenio = async () => {
    const nombre = convNombre.trim()
    if (!nombre) { setMsg({ type: 'error', text: 'Ingresá el nombre del convenio.' }); return }
    setConvSaving(true); setMsg(null)
    try {
      await apiClient.createSueldosConvenio({ nombre }, activeOrgId || undefined)
      setConvNombre('')
      setMsg({ type: 'ok', text: `Convenio "${nombre}" creado.` })
      await cargarConvenios()
    } catch (e: unknown) {
      const detail = (e as { response?: { data?: { detail?: unknown } } })?.response?.data?.detail
      setMsg({ type: 'error', text: typeof detail === 'string' ? detail : 'No se pudo crear el convenio.' })
    } finally {
      setConvSaving(false)
    }
  }

  const categoriasDelForm = empConvenio ? (categorias[Number(empConvenio)] || []) : []

  // ── Tab Liquidación ───────────────────────────────────────────────────────
  const [periodo, setPeriodo] = useState(mesActual())
  const [preview, setPreview] = useState<SueldosLiquidacionPreview | null>(null)
  const [persistido, setPersistido] = useState<SueldosLiquidacion | null>(null)
  const [loadingPreview, setLoadingPreview] = useState(false)
  const [calculando, setCalculando] = useState(false)
  const [aprobando, setAprobando] = useState(false)
  const [marcando, setMarcando] = useState(false)
  const [moduloInactivo, setModuloInactivo] = useState(false)

  const cargarPreview = useCallback(async () => {
    if (!periodo) return
    setLoadingPreview(true); setMsg(null); setModuloInactivo(false)
    try {
      const data = await apiClient.previewLiquidacionSueldos(periodo, activeOrgId || undefined)
      setPreview(data)
    } catch (e: unknown) {
      setPreview(null)
      const detail = (e as { response?: { data?: { detail?: unknown } } })?.response?.data?.detail
      const txt = typeof detail === 'string' ? detail : 'No se pudo calcular la liquidación.'
      if (txt.toLowerCase().includes('no está activado')) setModuloInactivo(true)
      else setMsg({ type: 'error', text: txt })
    } finally {
      setLoadingPreview(false)
    }
  }, [periodo, activeOrgId])

  const buscarPersistido = useCallback(async () => {
    try {
      const data = await apiClient.getHistorialSueldos({ orgId: activeOrgId || undefined, limit: 500 })
      setPersistido((data.items || []).find(p => p.periodo === periodo) || null)
    } catch {
      setPersistido(null)
    }
  }, [periodo, activeOrgId])

  useEffect(() => { if (tab === 'liquidacion') { cargarPreview(); buscarPersistido() } }, [tab, cargarPreview, buscarPersistido])

  const calcularYGuardar = async () => {
    setCalculando(true); setMsg(null)
    try {
      const p = await apiClient.calcularLiquidacionSueldos(periodo, activeOrgId || undefined)
      setPersistido(p)
      setMsg({ type: 'ok', text: 'Liquidación calculada y guardada (borrador).' })
    } catch (e: unknown) {
      const detail = (e as { response?: { data?: { detail?: unknown } } })?.response?.data?.detail
      setMsg({ type: 'error', text: typeof detail === 'string' ? detail : 'No se pudo calcular la liquidación.' })
    } finally {
      setCalculando(false)
    }
  }

  const aprobar = async () => {
    if (!persistido) return
    const ok = await confirmDialog({
      title: 'Aprobar liquidación',
      message: `Se aprobará la liquidación de ${persistido.periodo} y se generará el asiento contable. ¿Confirmás?`,
      confirmLabel: 'Aprobar', danger: false,
    })
    if (!ok) return
    setAprobando(true); setMsg(null)
    try {
      const p = await apiClient.aprobarLiquidacionSueldos(persistido.id, activeOrgId || undefined)
      setPersistido(p)
      setMsg({ type: 'ok', text: 'Liquidación aprobada y asiento generado.' })
    } catch (e: unknown) {
      const detail = (e as { response?: { data?: { detail?: unknown } } })?.response?.data?.detail
      setMsg({ type: 'error', text: typeof detail === 'string' ? detail : 'No se pudo aprobar la liquidación.' })
    } finally {
      setAprobando(false)
    }
  }

  const marcarPresentada = async () => {
    if (!persistido) return
    const ok = await confirmDialog({
      title: 'Marcar como presentada',
      message: `El período ${persistido.periodo} quedará marcado como presentado e inmutable (F931 enviado). ¿Confirmás?`,
      confirmLabel: 'Marcar presentada', danger: false,
    })
    if (!ok) return
    setMarcando(true); setMsg(null)
    try {
      const p = await apiClient.marcarLiquidacionSueldosPresentada(persistido.id, activeOrgId || undefined)
      setPersistido(p)
      setMsg({ type: 'ok', text: 'Liquidación marcada como presentada.' })
    } catch {
      setMsg({ type: 'error', text: 'No se pudo marcar como presentada.' })
    } finally {
      setMarcando(false)
    }
  }

  const detalle = preview?.detalle ?? []

  // ── Tab Historial ─────────────────────────────────────────────────────────
  const [historial, setHistorial] = useState<SueldosLiquidacion[]>([])
  const [historialTotal, setHistorialTotal] = useState(0)
  const [historialLoading, setHistorialLoading] = useState(false)
  const [historialOffset, setHistorialOffset] = useState(0)
  const HISTORIAL_LIMIT = 20

  const cargarHistorial = useCallback(async () => {
    setHistorialLoading(true)
    try {
      const data = await apiClient.getHistorialSueldos({ orgId: activeOrgId || undefined, limit: HISTORIAL_LIMIT, offset: historialOffset })
      setHistorial(data.items || [])
      setHistorialTotal(data.total || 0)
    } catch {
      setHistorial([])
    } finally {
      setHistorialLoading(false)
    }
  }, [activeOrgId, historialOffset])

  useEffect(() => { if (tab === 'historial') cargarHistorial() }, [tab, cargarHistorial])

  // ── Tab Config ────────────────────────────────────────────────────────────
  const [cfgActivo, setCfgActivo] = useState(false)
  const [cfgVals, setCfgVals] = useState<Record<string, string>>({})
  const [savingCfg, setSavingCfg] = useState(false)

  useEffect(() => {
    if (config) {
      setCfgActivo(config.activo)
      const vals: Record<string, string> = {}
      for (const [k] of [...APORTES, ...CONTRIBUCIONES]) {
        vals[k as string] = ((config[k] as number) * 100).toString()
      }
      setCfgVals(vals)
    }
  }, [config])

  const guardarConfig = async () => {
    const out: Record<string, number> = {}
    for (const [k] of [...APORTES, ...CONTRIBUCIONES]) {
      const f = parseTasaInput(cfgVals[k as string] ?? '')
      if (f === null) { setMsg({ type: 'error', text: `Valor inválido en ${k} (0 a 100%).` }); return }
      out[k as string] = f
    }
    setSavingCfg(true); setMsg(null)
    try {
      const updated = await apiClient.setSueldosConfig({ activo: cfgActivo, ...out } as SueldosConfig, activeOrgId || undefined)
      setConfig(updated)
      setMsg({ type: 'ok', text: 'Configuración guardada.' })
    } catch (e: unknown) {
      const detail = (e as { response?: { data?: { detail?: unknown } } })?.response?.data?.detail
      setMsg({ type: 'error', text: typeof detail === 'string' ? detail : 'No se pudo guardar la configuración.' })
    } finally {
      setSavingCfg(false)
    }
  }

  const empleadosActivos = useMemo(() => empleados.filter(e => e.activo), [empleados])

  // ── Render ──────────────────────────────────────────────────────────────
  return (
    <div className="p-4 md:p-6 max-w-6xl mx-auto">
      <h1 className="text-xl md:text-2xl font-semibold text-gray-900 dark:text-gray-100 mb-1">
        Sueldos y F931
      </h1>
      <p className="text-sm text-gray-500 dark:text-gray-400 mb-1">
        Herramienta de liquidación interna de sueldos + proyección del F931. Esto
        <strong> NO sustituye un sistema de liquidación de sueldos homologado ni reemplaza el SUSS/AFIP</strong>.
      </p>
      <p className="text-sm text-gray-500 dark:text-gray-400 mb-4">
        Las alícuotas de aportes/contribuciones son valores de referencia — verificá su vigencia con tu
        contador/AFIP antes de usarlas. La ART debe completarse con la alícuota de tu póliza.
      </p>

      {/* Tabs */}
      <div className="flex gap-1 mb-4 border-b border-gray-200 dark:border-white/10 flex-wrap">
        {([
          ['empleados', 'Empleados'],
          ['liquidacion', 'Liquidación'],
          ['historial', 'Historial'],
          ...(canAdminAccounting ? [['config', 'Config'] as const] : []),
        ] as const).map(([k, label]) => (
          <button
            key={k}
            onClick={() => setTab(k)}
            className={`px-4 py-2 text-sm font-medium -mb-px border-b-2 transition-colors ${
              tab === k
                ? 'border-ml-blue text-ml-blue dark:text-blue-300'
                : 'border-transparent text-gray-500 dark:text-gray-400 hover:text-gray-800 dark:hover:text-gray-200'
            }`}
          >
            {label}
          </button>
        ))}
      </div>

      {msg && (
        <div className={`mb-4 px-3 py-2 rounded-lg text-sm ${
          msg.type === 'error'
            ? 'bg-red-50 text-red-700 dark:bg-red-500/10 dark:text-red-300'
            : 'bg-green-50 text-green-700 dark:bg-green-500/10 dark:text-green-300'
        }`}>
          {msg.text}
        </div>
      )}

      {/* ── Tab Empleados ── */}
      {tab === 'empleados' && (
        <div className="space-y-6">
          {/* Convenios */}
          {canAdminAccounting && (
            <div className="rounded-xl border border-gray-200 dark:border-white/10 bg-white dark:bg-white/5 p-4">
              <h2 className="text-sm font-semibold text-gray-800 dark:text-gray-200 mb-2">Convenios colectivos</h2>
              <div className="flex flex-wrap gap-2 mb-3">
                {convenios.length === 0 && <span className="text-sm text-gray-400">Sin convenios. Agregá uno para definir categorías.</span>}
                {convenios.map(c => (
                  <span key={c.id} className="inline-flex items-center gap-2 px-2 py-1 rounded-md text-xs bg-gray-100 dark:bg-white/10 text-gray-700 dark:text-gray-300">
                    {c.nombre}
                    <button onClick={async () => {
                      const ok = await confirmDialog({ title: 'Eliminar convenio', message: `¿Eliminar "${c.nombre}" y sus categorías?`, confirmLabel: 'Eliminar', danger: true })
                      if (!ok) return
                      try { await apiClient.deleteSueldosConvenio(c.id, activeOrgId || undefined); await cargarConvenios() }
                      catch { setMsg({ type: 'error', text: 'No se pudo eliminar el convenio.' }) }
                    }} className="text-red-500 hover:text-red-600">✕</button>
                  </span>
                ))}
              </div>
              <div className="flex flex-col sm:flex-row gap-2 sm:items-end">
                <div className="w-full sm:w-64">
                  <label className="block text-xs text-gray-500 dark:text-gray-400 mb-1">Nuevo convenio</label>
                  <input className={inputClass} placeholder="ej. Comercio (CCT 130/75)" value={convNombre} onChange={e => setConvNombre(e.target.value)} />
                </div>
                <button onClick={crearConvenio} disabled={convSaving}
                  className="px-4 py-2 rounded-lg bg-ml-blue text-white text-sm font-medium hover:opacity-90 disabled:opacity-50">
                  {convSaving ? 'Creando…' : 'Agregar convenio'}
                </button>
              </div>
            </div>
          )}

          {/* Form empleado */}
          {canAdminAccounting && (
            <div className="rounded-xl border border-gray-200 dark:border-white/10 bg-white dark:bg-white/5 p-4">
              <h2 className="text-sm font-semibold text-gray-800 dark:text-gray-200 mb-3">
                {empEditId != null ? 'Editar empleado' : 'Nuevo empleado'}
              </h2>
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
                <div>
                  <label className="block text-xs text-gray-500 dark:text-gray-400 mb-1">Nombre *</label>
                  <input className={inputClass} value={empNombre} onChange={e => setEmpNombre(e.target.value)} />
                </div>
                <div>
                  <label className="block text-xs text-gray-500 dark:text-gray-400 mb-1">CUIL (11 dígitos)</label>
                  <input className={inputClass} inputMode="numeric" placeholder="20123456789" value={empCuil} onChange={e => setEmpCuil(e.target.value)} />
                </div>
                <div>
                  <label className="block text-xs text-gray-500 dark:text-gray-400 mb-1">Convenio</label>
                  <select className={inputClass} value={empConvenio} onChange={e => { setEmpConvenio(e.target.value); setEmpCategoria('') }}>
                    <option value="">— Sin convenio —</option>
                    {convenios.map(c => <option key={c.id} value={c.id}>{c.nombre}</option>)}
                  </select>
                </div>
                <div>
                  <label className="block text-xs text-gray-500 dark:text-gray-400 mb-1">Categoría</label>
                  <select className={inputClass} value={empCategoria} onChange={e => setEmpCategoria(e.target.value)} disabled={!empConvenio}>
                    <option value="">— Sin categoría —</option>
                    {categoriasDelForm.map(c => <option key={c.id} value={c.id}>{c.nombre} ({fmt(c.sueldo_basico)})</option>)}
                  </select>
                </div>
                <div>
                  <label className="block text-xs text-gray-500 dark:text-gray-400 mb-1">Sueldo básico (override)</label>
                  <input className={inputClass} inputMode="decimal" placeholder="opcional — usa el de la categoría" value={empBasico} onChange={e => setEmpBasico(e.target.value)} />
                </div>
                <div>
                  <label className="block text-xs text-gray-500 dark:text-gray-400 mb-1">Cargas de familia</label>
                  <input className={inputClass} inputMode="numeric" value={empCargas} onChange={e => setEmpCargas(e.target.value)} />
                </div>
              </div>
              <div className="flex gap-2 mt-3">
                <button onClick={guardarEmpleado} disabled={empSaving}
                  className="px-4 py-2 rounded-lg bg-ml-blue text-white text-sm font-medium hover:opacity-90 disabled:opacity-50">
                  {empSaving ? 'Guardando…' : empEditId != null ? 'Guardar cambios' : 'Crear empleado'}
                </button>
                {empEditId != null && (
                  <button onClick={resetEmpForm} className="px-4 py-2 rounded-lg border border-gray-300 dark:border-white/10 text-sm">Cancelar</button>
                )}
              </div>
            </div>
          )}

          {/* Lista empleados */}
          <div className="rounded-xl border border-gray-200 dark:border-white/10 overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-xs text-gray-500 dark:text-gray-400 border-b border-gray-200 dark:border-white/10">
                  <th className="px-3 py-2 font-medium">Empleado</th>
                  <th className="px-3 py-2 font-medium">CUIL</th>
                  <th className="px-3 py-2 font-medium text-right">Sueldo básico</th>
                  <th className="px-3 py-2 font-medium">Estado</th>
                  {canAdminAccounting && <th className="px-3 py-2 font-medium w-32"></th>}
                </tr>
              </thead>
              <tbody>
                {empLoading && <tr><td colSpan={5} className="px-3 py-6 text-center text-gray-400">Cargando…</td></tr>}
                {!empLoading && empleados.length === 0 && <tr><td colSpan={5} className="px-3 py-6 text-center text-gray-400">Sin empleados.</td></tr>}
                {!empLoading && empleados.map((e, i) => (
                  <tr key={e.id} className={`border-b border-gray-100 dark:border-white/5 ${i % 2 ? 'bg-gray-50/50 dark:bg-white/[0.02]' : ''}`}>
                    <td className="px-3 py-2 text-gray-900 dark:text-gray-100 whitespace-nowrap">{e.nombre}</td>
                    <td className="px-3 py-2 text-gray-700 dark:text-gray-300 whitespace-nowrap">{e.cuil || '—'}</td>
                    <td className="px-3 py-2 text-right text-gray-700 dark:text-gray-300 whitespace-nowrap">{e.sueldo_basico != null ? fmt(e.sueldo_basico) : '—'}</td>
                    <td className="px-3 py-2">
                      <span className={`px-2 py-0.5 rounded-md text-xs font-semibold ${e.activo ? 'bg-green-100 text-green-700 dark:bg-green-500/15 dark:text-green-300' : 'bg-gray-100 text-gray-500 dark:bg-white/10 dark:text-gray-400'}`}>
                        {e.activo ? 'Activo' : 'Inactivo'}
                      </span>
                    </td>
                    {canAdminAccounting && (
                      <td className="px-3 py-2 whitespace-nowrap">
                        <button onClick={() => abrirEditar(e)} className="px-2 py-1 rounded-md text-xs text-ml-blue hover:bg-ml-blue/10">Editar</button>
                        <button onClick={() => borrarEmpleado(e)} className="px-2 py-1 rounded-md text-xs text-red-500 hover:bg-red-500/10">Borrar</button>
                      </td>
                    )}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="text-xs text-gray-500 dark:text-gray-400">{empleadosActivos.length} empleado(s) activo(s) — se incluyen en la liquidación.</p>
        </div>
      )}

      {/* ── Tab Liquidación ── */}
      {tab === 'liquidacion' && (
        <div className="space-y-4">
          {moduloInactivo && (
            <div className="rounded-xl border border-amber-200 dark:border-amber-500/30 bg-amber-50 dark:bg-amber-500/10 p-4 text-sm text-amber-800 dark:text-amber-200">
              El módulo de Sueldos no está activo para esta organización.{' '}
              {canAdminAccounting ? <>Activalo en la pestaña <strong>Config</strong>.</> : <>Pedile a un administrador que lo active en Config.</>}
            </div>
          )}

          <div className="flex flex-col sm:flex-row gap-3 sm:items-end flex-wrap">
            <div className="w-full sm:w-48">
              <label className="block text-xs font-medium text-gray-600 dark:text-gray-400 mb-1">Período (mes)</label>
              <select className={inputClass} value={periodo} onChange={e => setPeriodo(e.target.value)}>
                {mesesRecientes().map(m => <option key={m} value={m}>{m}</option>)}
              </select>
            </div>
            {canManageFinance && !moduloInactivo && (
              <button onClick={calcularYGuardar} disabled={calculando || loadingPreview}
                className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-ml-blue text-white text-sm font-medium hover:opacity-90 disabled:opacity-50">
                <IconCalc />{calculando ? 'Calculando…' : 'Calcular y guardar'}
              </button>
            )}
            {persistido && (
              <span className={`px-2 py-1 rounded-md text-xs font-semibold ${ESTADO_BADGE[persistido.estado] || ''}`}>
                {ESTADO_LABEL[persistido.estado]}
              </span>
            )}
            {canManageFinance && persistido && persistido.estado === 'borrador' && (
              <button onClick={aprobar} disabled={aprobando}
                className="inline-flex items-center gap-2 px-4 py-2 rounded-lg border border-ml-blue text-ml-blue dark:text-blue-300 text-sm font-medium hover:bg-ml-blue/10 disabled:opacity-50">
                <IconCheck />{aprobando ? 'Aprobando…' : 'Aprobar (genera asiento)'}
              </button>
            )}
            {canAdminAccounting && persistido && persistido.estado === 'aprobado' && (
              <button onClick={marcarPresentada} disabled={marcando}
                className="inline-flex items-center gap-2 px-4 py-2 rounded-lg border border-green-300 dark:border-green-500/30 text-green-700 dark:text-green-300 text-sm font-medium hover:bg-green-50 dark:hover:bg-green-500/10 disabled:opacity-50">
                <IconCheck />{marcando ? 'Marcando…' : 'Marcar como presentada'}
              </button>
            )}
          </div>

          {loadingPreview && <div className="text-sm text-gray-500 dark:text-gray-400">Calculando liquidación…</div>}

          {!loadingPreview && preview && !moduloInactivo && (
            <>
              <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
                <div className="rounded-xl border border-gray-200 dark:border-white/10 bg-white dark:bg-white/5 p-4 overflow-hidden">
                  <div className="text-xs text-gray-500 dark:text-gray-400 mb-1">Total bruto (remuneraciones)</div>
                  <div className="text-base font-semibold text-gray-900 dark:text-gray-100 truncate">{fmt(preview.total_bruto)}</div>
                </div>
                <div className="rounded-xl border border-gray-200 dark:border-white/10 bg-white dark:bg-white/5 p-4 overflow-hidden">
                  <div className="text-xs text-gray-500 dark:text-gray-400 mb-1">Aportes (empleado)</div>
                  <div className="text-base font-semibold text-gray-900 dark:text-gray-100 truncate">{fmt(preview.total_aportes)}</div>
                </div>
                <div className="rounded-xl border border-gray-200 dark:border-white/10 bg-white dark:bg-white/5 p-4 overflow-hidden">
                  <div className="text-xs text-gray-500 dark:text-gray-400 mb-1">Contribuciones (empleador)</div>
                  <div className="text-base font-semibold text-gray-900 dark:text-gray-100 truncate">{fmt(preview.total_contribuciones)}</div>
                </div>
                <div className="rounded-xl border border-gray-200 dark:border-white/10 bg-white dark:bg-white/5 p-4 overflow-hidden">
                  <div className="text-xs text-gray-500 dark:text-gray-400 mb-1">Total neto a pagar</div>
                  <div className="text-xl font-semibold text-gray-900 dark:text-gray-100 truncate">{fmt(preview.total_neto)}</div>
                </div>
              </div>

              <div className="rounded-xl border border-ml-blue/30 bg-ml-blue/5 dark:bg-ml-blue/10 p-4 text-sm text-gray-700 dark:text-gray-200">
                <strong>Base del F931</strong> — Total remuneraciones: {fmt(preview.f931.total_remuneraciones)} ·
                Aportes: {fmt(preview.f931.total_aportes)} · Contribuciones: {fmt(preview.f931.total_contribuciones)}
              </div>

              <div className="rounded-xl border border-gray-200 dark:border-white/10 overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="text-left text-xs text-gray-500 dark:text-gray-400 border-b border-gray-200 dark:border-white/10">
                      <th className="px-3 py-2 font-medium">Empleado</th>
                      <th className="px-3 py-2 font-medium text-right">SAC prop.</th>
                      <th className="px-3 py-2 font-medium text-right">Bruto</th>
                      <th className="px-3 py-2 font-medium text-right">Aportes</th>
                      <th className="px-3 py-2 font-medium text-right">Contribuciones</th>
                      <th className="px-3 py-2 font-medium text-right">Neto</th>
                    </tr>
                  </thead>
                  <tbody>
                    {detalle.length === 0 && <tr><td colSpan={6} className="px-3 py-6 text-center text-gray-400">Sin empleados activos para liquidar.</td></tr>}
                    {detalle.map((d, i) => (
                      <tr key={d.empleado_id} className={`border-b border-gray-100 dark:border-white/5 ${i % 2 ? 'bg-gray-50/50 dark:bg-white/[0.02]' : ''}`}>
                        <td className="px-3 py-2 text-gray-900 dark:text-gray-100 whitespace-nowrap">{d.nombre}</td>
                        <td className="px-3 py-2 text-right text-gray-700 dark:text-gray-300 whitespace-nowrap">{fmt(d.sac_proporcional)}</td>
                        <td className="px-3 py-2 text-right text-gray-700 dark:text-gray-300 whitespace-nowrap">{fmt(d.sueldo_bruto)}</td>
                        <td className="px-3 py-2 text-right text-gray-700 dark:text-gray-300 whitespace-nowrap">{fmt(d.total_aportes)}</td>
                        <td className="px-3 py-2 text-right text-gray-700 dark:text-gray-300 whitespace-nowrap">{fmt(d.total_contribuciones)}</td>
                        <td className="px-3 py-2 text-right font-medium text-gray-900 dark:text-gray-100 whitespace-nowrap">{fmt(d.sueldo_neto)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </>
          )}
        </div>
      )}

      {/* ── Tab Historial ── */}
      {tab === 'historial' && (
        <div className="space-y-3">
          <div className="rounded-xl border border-gray-200 dark:border-white/10 overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-xs text-gray-500 dark:text-gray-400 border-b border-gray-200 dark:border-white/10">
                  <th className="px-3 py-2 font-medium">Período</th>
                  <th className="px-3 py-2 font-medium text-right">Bruto</th>
                  <th className="px-3 py-2 font-medium text-right">Aportes</th>
                  <th className="px-3 py-2 font-medium text-right">Contribuciones</th>
                  <th className="px-3 py-2 font-medium text-right">Neto</th>
                  <th className="px-3 py-2 font-medium">Estado</th>
                </tr>
              </thead>
              <tbody>
                {historialLoading && <tr><td colSpan={6} className="px-3 py-6 text-center text-gray-400">Cargando…</td></tr>}
                {!historialLoading && historial.length === 0 && <tr><td colSpan={6} className="px-3 py-6 text-center text-gray-400">Sin liquidaciones calculadas.</td></tr>}
                {!historialLoading && historial.map((p, i) => (
                  <tr key={p.id} className={`border-b border-gray-100 dark:border-white/5 ${i % 2 ? 'bg-gray-50/50 dark:bg-white/[0.02]' : ''}`}>
                    <td className="px-3 py-2 text-gray-900 dark:text-gray-100 whitespace-nowrap">{p.periodo}</td>
                    <td className="px-3 py-2 text-right text-gray-700 dark:text-gray-300 whitespace-nowrap">{fmt(p.total_bruto)}</td>
                    <td className="px-3 py-2 text-right text-gray-700 dark:text-gray-300 whitespace-nowrap">{fmt(p.total_aportes)}</td>
                    <td className="px-3 py-2 text-right text-gray-700 dark:text-gray-300 whitespace-nowrap">{fmt(p.total_contribuciones)}</td>
                    <td className="px-3 py-2 text-right font-medium text-gray-900 dark:text-gray-100 whitespace-nowrap">{fmt(p.total_neto)}</td>
                    <td className="px-3 py-2">
                      <span className={`px-2 py-0.5 rounded-md text-xs font-semibold ${ESTADO_BADGE[p.estado] || ''}`}>{ESTADO_LABEL[p.estado]}</span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="flex items-center justify-between text-sm text-gray-500 dark:text-gray-400">
            <span>{historialTotal} período{historialTotal === 1 ? '' : 's'}</span>
            <div className="flex gap-2">
              <button onClick={() => setHistorialOffset(o => Math.max(0, o - HISTORIAL_LIMIT))} disabled={historialOffset === 0}
                className="px-3 py-1.5 rounded-lg border border-gray-300 dark:border-white/10 disabled:opacity-40">Anterior</button>
              <button onClick={() => setHistorialOffset(o => o + HISTORIAL_LIMIT)} disabled={historialOffset + HISTORIAL_LIMIT >= historialTotal}
                className="px-3 py-1.5 rounded-lg border border-gray-300 dark:border-white/10 disabled:opacity-40">Siguiente</button>
            </div>
          </div>
        </div>
      )}

      {/* ── Tab Config ── */}
      {tab === 'config' && canAdminAccounting && (
        <div className="space-y-6">
          {!configLoaded && <div className="text-sm text-gray-500 dark:text-gray-400">Cargando configuración…</div>}
          {configLoaded && (
            <>
              <div className="rounded-xl border border-gray-200 dark:border-white/10 bg-white dark:bg-white/5 p-4 space-y-4">
                <div className="flex items-center gap-3">
                  <input id="sueldos-activo" type="checkbox" checked={cfgActivo} onChange={e => setCfgActivo(e.target.checked)}
                    className="w-4 h-4 rounded border-gray-300 dark:border-white/20" />
                  <label htmlFor="sueldos-activo" className="text-sm font-medium text-gray-800 dark:text-gray-200">
                    Activar módulo de Sueldos para esta organización
                  </label>
                </div>

                <p className="text-xs text-amber-700 dark:text-amber-300 bg-amber-50 dark:bg-amber-500/10 border border-amber-200 dark:border-amber-500/30 rounded-lg px-3 py-2">
                  Valores de referencia — verificá la vigencia con tu contador/AFIP antes de usarlos. La ART
                  varía por póliza: completala con tu alícuota contratada (por default es 0).
                </p>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                  <div>
                    <h3 className="text-sm font-semibold text-gray-800 dark:text-gray-200 mb-2">Aportes del empleado (%)</h3>
                    <div className="space-y-2">
                      {APORTES.map(([k, label]) => (
                        <div key={k as string} className="flex items-center gap-2">
                          <label className="text-xs text-gray-600 dark:text-gray-400 flex-1">{label}</label>
                          <input className={`${inputClass} w-28`} inputMode="decimal" value={cfgVals[k as string] ?? ''}
                            onChange={e => setCfgVals(prev => ({ ...prev, [k as string]: e.target.value }))} />
                        </div>
                      ))}
                    </div>
                  </div>
                  <div>
                    <h3 className="text-sm font-semibold text-gray-800 dark:text-gray-200 mb-2">Contribuciones del empleador (%)</h3>
                    <div className="space-y-2">
                      {CONTRIBUCIONES.map(([k, label]) => (
                        <div key={k as string} className="flex items-center gap-2">
                          <label className="text-xs text-gray-600 dark:text-gray-400 flex-1">{label}</label>
                          <input className={`${inputClass} w-28`} inputMode="decimal" value={cfgVals[k as string] ?? ''}
                            onChange={e => setCfgVals(prev => ({ ...prev, [k as string]: e.target.value }))} />
                        </div>
                      ))}
                    </div>
                  </div>
                </div>

                <button onClick={guardarConfig} disabled={savingCfg}
                  className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-ml-blue text-white text-sm font-medium hover:opacity-90 disabled:opacity-50">
                  {savingCfg ? 'Guardando…' : 'Guardar configuración'}
                </button>
              </div>
            </>
          )}
        </div>
      )}
    </div>
  )
}

export default Sueldos
