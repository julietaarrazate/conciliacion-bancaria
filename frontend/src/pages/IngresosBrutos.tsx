import React, { useCallback, useEffect, useMemo, useState } from 'react'
import { apiClient } from '@/services/api'
import { confirmDialog } from '@/store/confirm'
import { useOrgStore } from '@/store/org'
import { useAuthStore } from '@/store/auth'
import { localIsoDate } from '@/utils/fecha'
import type {
  IIBBConfig,
  IIBBJurisdiccion,
  IIBBProyeccionPreview,
  IIBBProyeccion,
} from '@/types'

// ── Helpers ─────────────────────────────────────────────────────────────────
const fmt = (n: number) =>
  new Intl.NumberFormat('es-AR', { style: 'currency', currency: 'ARS', minimumFractionDigits: 2 }).format(n || 0)

const fmtPct = (n: number) => `${(n * 100).toFixed(2)}%`

/** Mes actual (YYYY-MM) en hora local — NUNCA toISOString (da el mes de UTC). */
function mesActual(): string {
  const d = new Date(localIsoDate())
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}`
}

/** Lista de meses recientes para el selector (actual + 11 anteriores). */
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
  proyectado: 'bg-amber-100 text-amber-700 dark:bg-amber-500/15 dark:text-amber-300',
  presentado: 'bg-green-100 text-green-700 dark:bg-green-500/15 dark:text-green-300',
}

// SVG icons (Heroicons outline)
const IconCalc = () => (
  <svg className="w-4 h-4" fill="none" stroke="currentColor" strokeWidth={1.8} viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" d="M9 7.5h6m-6 3h6m-6 3h3m-9 4.5h12a2.25 2.25 0 002.25-2.25V5.25A2.25 2.25 0 0015 3H6a2.25 2.25 0 00-2.25 2.25v13.5A2.25 2.25 0 006 21z" /></svg>
)
const IconCheck = () => (
  <svg className="w-4 h-4" fill="none" stroke="currentColor" strokeWidth={1.8} viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" d="M9 12.75L11.25 15 15 9.75M21 12a9 9 0 11-18 0 9 9 0 0118 0z" /></svg>
)

/** Parser de % escrito por el usuario: acepta "5", "5,5", "0.055". Devuelve la
 * fracción (0..1). Si el valor es > 1 se interpreta como porcentaje (÷100). */
function parseTasaInput(raw: string): number | null {
  const s = (raw ?? '').trim().replace('%', '').replace(',', '.')
  if (s === '') return 0
  const n = parseFloat(s)
  if (isNaN(n) || n < 0) return null
  const frac = n > 1 ? n / 100 : n
  if (frac > 1) return null
  return frac
}

export const IngresosBrutos: React.FC = () => {
  const { activeOrgId } = useOrgStore()
  const { hasPermission } = useAuthStore()
  const canManageFinance = hasPermission('manage_finance')
  const canAdminAccounting = hasPermission('admin_accounting')

  const [tab, setTab] = useState<'proyeccion' | 'historial' | 'config'>('proyeccion')
  const [msg, setMsg] = useState<{ type: 'error' | 'ok'; text: string } | null>(null)

  // ── Config (cargada siempre — determina si el módulo está activo) ────────
  const [config, setConfig] = useState<IIBBConfig | null>(null)
  const [configLoaded, setConfigLoaded] = useState(false)

  const cargarConfigBase = useCallback(async () => {
    try {
      const data = await apiClient.getIIBBConfig(activeOrgId || undefined)
      setConfig(data)
    } catch {
      setConfig(null)
    } finally {
      setConfigLoaded(true)
    }
  }, [activeOrgId])

  useEffect(() => { cargarConfigBase() }, [cargarConfigBase])

  // ── Tab Proyección ──────────────────────────────────────────────────────
  const [periodo, setPeriodo] = useState(mesActual())
  const [preview, setPreview] = useState<IIBBProyeccionPreview | null>(null)
  const [persistido, setPersistido] = useState<IIBBProyeccion | null>(null)
  const [loadingPreview, setLoadingPreview] = useState(false)
  const [calculando, setCalculando] = useState(false)
  const [marcando, setMarcando] = useState(false)

  const cargarPreview = useCallback(async () => {
    if (!periodo || !config?.activo) return
    setLoadingPreview(true)
    setMsg(null)
    try {
      const data = await apiClient.previewProyeccionIIBB(periodo, activeOrgId || undefined)
      setPreview(data)
    } catch (e: unknown) {
      setPreview(null)
      const detail = (e as { response?: { data?: { detail?: unknown } } })?.response?.data?.detail
      setMsg({ type: 'error', text: typeof detail === 'string' ? detail : 'No se pudo calcular la proyección del período.' })
    } finally {
      setLoadingPreview(false)
    }
  }, [periodo, activeOrgId, config?.activo])

  const buscarPersistido = useCallback(async () => {
    if (!config?.activo) return
    try {
      const data = await apiClient.getHistorialIIBB({ orgId: activeOrgId || undefined, limit: 500 })
      const found = (data.items || []).find(p => p.periodo === periodo) || null
      setPersistido(found)
    } catch {
      setPersistido(null)
    }
  }, [periodo, activeOrgId, config?.activo])

  useEffect(() => { if (tab === 'proyeccion') cargarPreview() }, [tab, cargarPreview])
  useEffect(() => { if (tab === 'proyeccion') buscarPersistido() }, [tab, buscarPersistido])

  const calcularYGuardar = async () => {
    setCalculando(true)
    setMsg(null)
    try {
      const p = await apiClient.calcularProyeccionIIBB(periodo, activeOrgId || undefined)
      setPersistido(p)
      setMsg({ type: 'ok', text: 'Proyección calculada y guardada.' })
      await cargarPreview()
    } catch (e: unknown) {
      const detail = (e as { response?: { data?: { detail?: unknown } } })?.response?.data?.detail
      setMsg({ type: 'error', text: typeof detail === 'string' ? detail : 'No se pudo calcular la proyección.' })
    } finally {
      setCalculando(false)
    }
  }

  const marcarPresentada = async () => {
    if (!persistido) return
    const ok = await confirmDialog({
      title: 'Marcar proyección como presentada',
      message: `El período ${persistido.periodo} quedará marcado como presentado e inmutable (recalcular no lo pisará). ¿Confirmás que ya presentaste la DDJJ?`,
      confirmLabel: 'Marcar como presentada',
      danger: false,
    })
    if (!ok) return
    setMarcando(true)
    setMsg(null)
    try {
      const p = await apiClient.marcarProyeccionIIBBPresentada(persistido.id, activeOrgId || undefined)
      setPersistido(p)
      setMsg({ type: 'ok', text: 'Proyección marcada como presentada.' })
    } catch {
      setMsg({ type: 'error', text: 'No se pudo marcar la proyección como presentada.' })
    } finally {
      setMarcando(false)
    }
  }

  const detalle = preview?.detalle ?? []
  const coefNoSuman = !!preview?.warning

  // ── Tab Historial ────────────────────────────────────────────────────────
  const [historial, setHistorial] = useState<IIBBProyeccion[]>([])
  const [historialTotal, setHistorialTotal] = useState(0)
  const [historialLoading, setHistorialLoading] = useState(false)
  const [historialOffset, setHistorialOffset] = useState(0)
  const HISTORIAL_LIMIT = 20

  const cargarHistorial = useCallback(async () => {
    setHistorialLoading(true)
    try {
      const data = await apiClient.getHistorialIIBB({
        orgId: activeOrgId || undefined,
        limit: HISTORIAL_LIMIT,
        offset: historialOffset,
      })
      setHistorial(data.items || [])
      setHistorialTotal(data.total || 0)
    } catch {
      setHistorial([])
    } finally {
      setHistorialLoading(false)
    }
  }, [activeOrgId, historialOffset])

  useEffect(() => { if (tab === 'historial') cargarHistorial() }, [tab, cargarHistorial])

  // ── Tab Config ───────────────────────────────────────────────────────────
  const [configActivo, setConfigActivo] = useState(false)
  const [configModo, setConfigModo] = useState<'simple' | 'convenio_multilateral'>('simple')
  const [configJurUnica, setConfigJurUnica] = useState<string>('')
  const [guardandoConfig, setGuardandoConfig] = useState(false)

  const [jurisdicciones, setJurisdicciones] = useState<IIBBJurisdiccion[]>([])
  const [jurLoading, setJurLoading] = useState(false)
  const [savingJurId, setSavingJurId] = useState<number | null>(null)

  // edición inline de filas existentes
  const [editVals, setEditVals] = useState<Record<number, { alicuota: string; coef: string }>>({})

  // alta de nueva jurisdicción
  const [nuevoNombre, setNuevoNombre] = useState('')
  const [nuevoAlic, setNuevoAlic] = useState('')
  const [nuevoCoef, setNuevoCoef] = useState('')
  const [creandoJur, setCreandoJur] = useState(false)

  useEffect(() => {
    if (config) {
      setConfigActivo(config.activo)
      setConfigModo(config.modo)
      setConfigJurUnica(config.jurisdiccion_unica_id ? String(config.jurisdiccion_unica_id) : '')
    }
  }, [config])

  const cargarJurisdicciones = useCallback(async () => {
    setJurLoading(true)
    try {
      const data = await apiClient.getIIBBJurisdicciones(activeOrgId || undefined)
      const items = data.items || []
      setJurisdicciones(items)
      const ev: Record<number, { alicuota: string; coef: string }> = {}
      for (const j of items) {
        ev[j.id] = {
          alicuota: (j.alicuota * 100).toString(),
          coef: (j.coeficiente_distribucion * 100).toString(),
        }
      }
      setEditVals(ev)
    } catch {
      setJurisdicciones([])
    } finally {
      setJurLoading(false)
    }
  }, [activeOrgId])

  useEffect(() => {
    if (tab === 'config' && canAdminAccounting) cargarJurisdicciones()
  }, [tab, canAdminAccounting, cargarJurisdicciones])

  const guardarConfig = async () => {
    setGuardandoConfig(true)
    setMsg(null)
    try {
      const updated = await apiClient.setIIBBConfig(
        {
          activo: configActivo,
          modo: configModo,
          jurisdiccion_unica_id: configModo === 'simple' && configJurUnica ? Number(configJurUnica) : null,
        },
        activeOrgId || undefined,
      )
      setConfig(updated)
      setMsg({ type: 'ok', text: 'Configuración guardada.' })
    } catch (e: unknown) {
      const detail = (e as { response?: { data?: { detail?: unknown } } })?.response?.data?.detail
      setMsg({ type: 'error', text: typeof detail === 'string' ? detail : 'No se pudo guardar la configuración.' })
    } finally {
      setGuardandoConfig(false)
    }
  }

  const guardarJurisdiccion = async (j: IIBBJurisdiccion) => {
    const ev = editVals[j.id]
    if (!ev) return
    const alic = parseTasaInput(ev.alicuota)
    const coef = parseTasaInput(ev.coef)
    if (alic === null || coef === null) {
      setMsg({ type: 'error', text: 'Ingresá una alícuota y un coeficiente válidos (0 a 100%).' })
      return
    }
    setSavingJurId(j.id)
    setMsg(null)
    try {
      const updated = await apiClient.updateIIBBJurisdiccion(j.id, {
        alicuota: alic, coeficiente_distribucion: coef,
      }, activeOrgId || undefined)
      setJurisdicciones(prev => prev.map(x => (x.id === j.id ? updated : x)))
      setMsg({ type: 'ok', text: `Jurisdicción "${j.nombre}" actualizada.` })
    } catch {
      setMsg({ type: 'error', text: 'No se pudo guardar la jurisdicción.' })
    } finally {
      setSavingJurId(null)
    }
  }

  const toggleActiva = async (j: IIBBJurisdiccion) => {
    setSavingJurId(j.id)
    setMsg(null)
    try {
      const updated = await apiClient.updateIIBBJurisdiccion(j.id, { activa: !j.activa }, activeOrgId || undefined)
      setJurisdicciones(prev => prev.map(x => (x.id === j.id ? updated : x)))
    } catch {
      setMsg({ type: 'error', text: 'No se pudo cambiar el estado de la jurisdicción.' })
    } finally {
      setSavingJurId(null)
    }
  }

  const crearJurisdiccion = async () => {
    const nombre = nuevoNombre.trim()
    if (!nombre) {
      setMsg({ type: 'error', text: 'Ingresá el nombre de la jurisdicción.' })
      return
    }
    const alic = parseTasaInput(nuevoAlic)
    const coef = parseTasaInput(nuevoCoef)
    if (alic === null || coef === null) {
      setMsg({ type: 'error', text: 'Alícuota/coeficiente inválidos (0 a 100%).' })
      return
    }
    setCreandoJur(true)
    setMsg(null)
    try {
      const orden = jurisdicciones.length + 1
      await apiClient.createIIBBJurisdiccion({
        nombre, alicuota: alic, coeficiente_distribucion: coef, activa: true, orden,
      }, activeOrgId || undefined)
      setNuevoNombre(''); setNuevoAlic(''); setNuevoCoef('')
      setMsg({ type: 'ok', text: `Jurisdicción "${nombre}" creada.` })
      await cargarJurisdicciones()
    } catch (e: unknown) {
      const detail = (e as { response?: { data?: { detail?: unknown } } })?.response?.data?.detail
      setMsg({ type: 'error', text: typeof detail === 'string' ? detail : 'No se pudo crear la jurisdicción.' })
    } finally {
      setCreandoJur(false)
    }
  }

  const jurisdiccionesOrdenadas = useMemo(
    () => [...jurisdicciones].sort((a, b) => a.orden - b.orden || a.id - b.id),
    [jurisdicciones],
  )

  const esConvenio = configModo === 'convenio_multilateral'

  // ── Render ──────────────────────────────────────────────────────────────
  return (
    <div className="p-4 md:p-6 max-w-6xl mx-auto">
      <h1 className="text-xl md:text-2xl font-semibold text-gray-900 dark:text-gray-100 mb-1">
        Ingresos Brutos — Proyección
      </h1>
      <p className="text-sm text-gray-500 dark:text-gray-400 mb-1">
        Herramienta de estimación interna. Esto es una proyección de control y
        <strong> no sustituye la DDJJ oficial ante AGIP/ARBA o el organismo provincial</strong>.
      </p>
      <p className="text-sm text-gray-500 dark:text-gray-400 mb-4">
        Las alícuotas y los coeficientes de distribución deben verificarse contra el organismo de
        cada jurisdicción — los valores configurados pueden estar desactualizados.
      </p>

      {/* Tabs */}
      <div className="flex gap-1 mb-4 border-b border-gray-200 dark:border-white/10">
        {([
          ['proyeccion', 'Proyección'],
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

      {/* ── Tab Proyección ── */}
      {tab === 'proyeccion' && (
        <div className="space-y-4">
          {!configLoaded && (
            <div className="text-sm text-gray-500 dark:text-gray-400">Cargando configuración…</div>
          )}

          {configLoaded && !config?.activo && (
            <div className="rounded-xl border border-amber-200 dark:border-amber-500/30 bg-amber-50 dark:bg-amber-500/10 p-4 text-sm text-amber-800 dark:text-amber-200">
              El módulo de Ingresos Brutos no está activo para esta organización.{' '}
              {canAdminAccounting ? (
                <>Activalo en la pestaña <strong>Config</strong> para empezar a proyectar.</>
              ) : (
                <>Pedile a un administrador de contabilidad que lo active en la pestaña Config.</>
              )}
            </div>
          )}

          {configLoaded && config?.activo && (
            <>
              <div className="flex flex-col sm:flex-row gap-3 sm:items-end">
                <div className="w-full sm:w-48">
                  <label className="block text-xs font-medium text-gray-600 dark:text-gray-400 mb-1">Período (mes)</label>
                  <select
                    className={inputClass}
                    value={periodo}
                    onChange={e => setPeriodo(e.target.value)}
                  >
                    {mesesRecientes().map(m => (
                      <option key={m} value={m}>{m}</option>
                    ))}
                  </select>
                </div>
                {canManageFinance && (
                  <button
                    onClick={calcularYGuardar}
                    disabled={calculando || loadingPreview}
                    className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-ml-blue text-white text-sm font-medium hover:opacity-90 disabled:opacity-50"
                  >
                    <IconCalc />
                    {calculando ? 'Calculando…' : 'Calcular y guardar'}
                  </button>
                )}
                {persistido && (
                  <span className={`px-2 py-1 rounded-md text-xs font-semibold ${ESTADO_BADGE[persistido.estado] || ''}`}>
                    {persistido.estado === 'presentado' ? 'Presentada' : 'Proyectada'}
                  </span>
                )}
                {canAdminAccounting && persistido && persistido.estado === 'proyectado' && (
                  <button
                    onClick={marcarPresentada}
                    disabled={marcando}
                    className="inline-flex items-center gap-2 px-4 py-2 rounded-lg border border-green-300 dark:border-green-500/30 text-green-700 dark:text-green-300 text-sm font-medium hover:bg-green-50 dark:hover:bg-green-500/10 disabled:opacity-50"
                  >
                    <IconCheck />
                    {marcando ? 'Marcando…' : 'Marcar como presentada'}
                  </button>
                )}
              </div>

              {loadingPreview && (
                <div className="text-sm text-gray-500 dark:text-gray-400">Calculando proyección…</div>
              )}

              {!loadingPreview && preview && (
                <>
                  <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
                    <div className="rounded-xl border border-gray-200 dark:border-white/10 bg-white dark:bg-white/5 p-4 overflow-hidden">
                      <div className="text-xs text-gray-500 dark:text-gray-400 mb-1">Ingreso del período</div>
                      <div className="text-base font-semibold text-gray-900 dark:text-gray-100 truncate">{fmt(preview.ingreso_total)}</div>
                    </div>
                    <div className="rounded-xl border border-gray-200 dark:border-white/10 bg-white dark:bg-white/5 p-4 overflow-hidden">
                      <div className="text-xs text-gray-500 dark:text-gray-400 mb-1">Modo</div>
                      <div className="text-base font-semibold text-gray-900 dark:text-gray-100 truncate">
                        {preview.modo === 'convenio_multilateral' ? 'Convenio Multilateral' : 'Jurisdicción única'}
                      </div>
                    </div>
                    <div className="rounded-xl border border-gray-200 dark:border-white/10 bg-white dark:bg-white/5 p-4 overflow-hidden">
                      <div className="text-xs text-gray-500 dark:text-gray-400 mb-1">Impuesto proyectado</div>
                      <div className="text-xl font-semibold text-gray-900 dark:text-gray-100 truncate">{fmt(preview.impuesto_total)}</div>
                    </div>
                  </div>

                  {coefNoSuman && (
                    <div className="rounded-xl border border-amber-200 dark:border-amber-500/30 bg-amber-50 dark:bg-amber-500/10 p-4 text-sm font-medium text-amber-700 dark:text-amber-300">
                      {preview.warning} (suman {fmtPct(preview.suma_coeficientes)})
                    </div>
                  )}

                  <div className="rounded-xl border border-gray-200 dark:border-white/10 overflow-x-auto">
                    <table className="w-full text-sm">
                      <thead>
                        <tr className="text-left text-xs text-gray-500 dark:text-gray-400 border-b border-gray-200 dark:border-white/10">
                          <th className="px-3 py-2 font-medium">Jurisdicción</th>
                          {preview.modo === 'convenio_multilateral' && (
                            <th className="px-3 py-2 font-medium text-right">Coeficiente</th>
                          )}
                          <th className="px-3 py-2 font-medium text-right">Ingreso atribuido</th>
                          <th className="px-3 py-2 font-medium text-right">Alícuota</th>
                          <th className="px-3 py-2 font-medium text-right">Impuesto</th>
                        </tr>
                      </thead>
                      <tbody>
                        {detalle.length === 0 && (
                          <tr><td colSpan={5} className="px-3 py-6 text-center text-gray-400">
                            Sin jurisdicciones para proyectar.
                          </td></tr>
                        )}
                        {detalle.map((d, i) => (
                          <tr key={d.jurisdiccion_id} className={`border-b border-gray-100 dark:border-white/5 ${i % 2 ? 'bg-gray-50/50 dark:bg-white/[0.02]' : ''}`}>
                            <td className="px-3 py-2 text-gray-900 dark:text-gray-100 whitespace-nowrap">{d.nombre}</td>
                            {preview.modo === 'convenio_multilateral' && (
                              <td className="px-3 py-2 text-right text-gray-700 dark:text-gray-300 whitespace-nowrap">{fmtPct(d.coeficiente)}</td>
                            )}
                            <td className="px-3 py-2 text-right text-gray-700 dark:text-gray-300 whitespace-nowrap">{fmt(d.ingreso_atribuido)}</td>
                            <td className="px-3 py-2 text-right text-gray-700 dark:text-gray-300 whitespace-nowrap">{fmtPct(d.alicuota)}</td>
                            <td className="px-3 py-2 text-right font-medium text-gray-900 dark:text-gray-100 whitespace-nowrap">{fmt(d.impuesto)}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </>
              )}
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
                  <th className="px-3 py-2 font-medium text-right">Ingreso total</th>
                  <th className="px-3 py-2 font-medium text-right">Impuesto</th>
                  <th className="px-3 py-2 font-medium">Estado</th>
                </tr>
              </thead>
              <tbody>
                {historialLoading && (
                  <tr><td colSpan={4} className="px-3 py-6 text-center text-gray-400">Cargando…</td></tr>
                )}
                {!historialLoading && historial.length === 0 && (
                  <tr><td colSpan={4} className="px-3 py-6 text-center text-gray-400">Sin proyecciones calculadas.</td></tr>
                )}
                {!historialLoading && historial.map((p, i) => (
                  <tr key={p.id} className={`border-b border-gray-100 dark:border-white/5 ${i % 2 ? 'bg-gray-50/50 dark:bg-white/[0.02]' : ''}`}>
                    <td className="px-3 py-2 text-gray-900 dark:text-gray-100 whitespace-nowrap">{p.periodo}</td>
                    <td className="px-3 py-2 text-right text-gray-700 dark:text-gray-300 whitespace-nowrap">{fmt(p.ingreso_total)}</td>
                    <td className="px-3 py-2 text-right font-medium text-gray-900 dark:text-gray-100 whitespace-nowrap">{fmt(p.impuesto_total)}</td>
                    <td className="px-3 py-2">
                      <span className={`px-2 py-0.5 rounded-md text-xs font-semibold ${ESTADO_BADGE[p.estado] || ''}`}>
                        {p.estado === 'presentado' ? 'Presentada' : 'Proyectada'}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="flex items-center justify-between text-sm text-gray-500 dark:text-gray-400">
            <span>{historialTotal} período{historialTotal === 1 ? '' : 's'}</span>
            <div className="flex gap-2">
              <button
                onClick={() => setHistorialOffset(o => Math.max(0, o - HISTORIAL_LIMIT))}
                disabled={historialOffset === 0}
                className="px-3 py-1.5 rounded-lg border border-gray-300 dark:border-white/10 disabled:opacity-40"
              >
                Anterior
              </button>
              <button
                onClick={() => setHistorialOffset(o => o + HISTORIAL_LIMIT)}
                disabled={historialOffset + HISTORIAL_LIMIT >= historialTotal}
                className="px-3 py-1.5 rounded-lg border border-gray-300 dark:border-white/10 disabled:opacity-40"
              >
                Siguiente
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ── Tab Config ── */}
      {tab === 'config' && canAdminAccounting && (
        <div className="space-y-6">
          <div className="rounded-xl border border-gray-200 dark:border-white/10 bg-white dark:bg-white/5 p-4 space-y-4">
            <div className="flex items-center gap-3">
              <input
                id="iibb-activo"
                type="checkbox"
                checked={configActivo}
                onChange={e => setConfigActivo(e.target.checked)}
                className="w-4 h-4 rounded border-gray-300 dark:border-white/20"
              />
              <label htmlFor="iibb-activo" className="text-sm font-medium text-gray-800 dark:text-gray-200">
                Activar módulo de Ingresos Brutos para esta organización
              </label>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div>
                <label className="block text-xs font-medium text-gray-600 dark:text-gray-400 mb-1">Modo de cálculo</label>
                <select
                  className={inputClass}
                  value={configModo}
                  onChange={e => setConfigModo(e.target.value as 'simple' | 'convenio_multilateral')}
                >
                  <option value="simple">Jurisdicción única (simple)</option>
                  <option value="convenio_multilateral">Convenio Multilateral</option>
                </select>
              </div>
              {!esConvenio && (
                <div>
                  <label className="block text-xs font-medium text-gray-600 dark:text-gray-400 mb-1">Jurisdicción única</label>
                  <select
                    className={inputClass}
                    value={configJurUnica}
                    onChange={e => setConfigJurUnica(e.target.value)}
                  >
                    <option value="">— Elegir jurisdicción —</option>
                    {jurisdiccionesOrdenadas.map(j => (
                      <option key={j.id} value={j.id}>{j.nombre} ({fmtPct(j.alicuota)})</option>
                    ))}
                  </select>
                </div>
              )}
            </div>

            <button
              onClick={guardarConfig}
              disabled={guardandoConfig}
              className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-ml-blue text-white text-sm font-medium hover:opacity-90 disabled:opacity-50"
            >
              {guardandoConfig ? 'Guardando…' : 'Guardar configuración'}
            </button>
          </div>

          <div>
            <p className="text-xs text-amber-700 dark:text-amber-300 bg-amber-50 dark:bg-amber-500/10 border border-amber-200 dark:border-amber-500/30 rounded-lg px-3 py-2 mb-3">
              Las alícuotas y coeficientes deben verificarse contra AGIP (CABA), ARBA (Buenos Aires) o el
              organismo de cada provincia. Cuadra NO siembra valores reales — completalos vos. En Convenio
              Multilateral los coeficientes deben sumar 100%.
            </p>
            <h2 className="text-sm font-semibold text-gray-800 dark:text-gray-200 mb-2">Jurisdicciones</h2>

            <div className="rounded-xl border border-gray-200 dark:border-white/10 overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-left text-xs text-gray-500 dark:text-gray-400 border-b border-gray-200 dark:border-white/10">
                    <th className="px-3 py-2 font-medium">Jurisdicción</th>
                    <th className="px-3 py-2 font-medium w-28">Alícuota (%)</th>
                    {esConvenio && <th className="px-3 py-2 font-medium w-28">Coef. (%)</th>}
                    <th className="px-3 py-2 font-medium w-24">Activa</th>
                    <th className="px-3 py-2 font-medium w-24"></th>
                  </tr>
                </thead>
                <tbody>
                  {jurLoading && (
                    <tr><td colSpan={esConvenio ? 5 : 4} className="px-3 py-4 text-center text-gray-400">Cargando…</td></tr>
                  )}
                  {!jurLoading && jurisdiccionesOrdenadas.length === 0 && (
                    <tr><td colSpan={esConvenio ? 5 : 4} className="px-3 py-4 text-center text-gray-400">Sin jurisdicciones. Agregá una abajo.</td></tr>
                  )}
                  {!jurLoading && jurisdiccionesOrdenadas.map((j, i) => (
                    <tr key={j.id} className={`border-b border-gray-100 dark:border-white/5 ${i % 2 ? 'bg-gray-50/50 dark:bg-white/[0.02]' : ''}`}>
                      <td className="px-3 py-2 text-gray-900 dark:text-gray-100 whitespace-nowrap">{j.nombre}</td>
                      <td className="px-3 py-2">
                        <input
                          className={inputClass}
                          inputMode="decimal"
                          placeholder="ej. 5"
                          value={editVals[j.id]?.alicuota ?? ''}
                          onChange={e => setEditVals(prev => ({ ...prev, [j.id]: { ...prev[j.id], alicuota: e.target.value, coef: prev[j.id]?.coef ?? '' } }))}
                        />
                      </td>
                      {esConvenio && (
                        <td className="px-3 py-2">
                          <input
                            className={inputClass}
                            inputMode="decimal"
                            placeholder="ej. 60"
                            value={editVals[j.id]?.coef ?? ''}
                            onChange={e => setEditVals(prev => ({ ...prev, [j.id]: { ...prev[j.id], coef: e.target.value, alicuota: prev[j.id]?.alicuota ?? '' } }))}
                          />
                        </td>
                      )}
                      <td className="px-3 py-2">
                        <button
                          onClick={() => toggleActiva(j)}
                          disabled={savingJurId === j.id}
                          className={`px-2 py-1 rounded-md text-xs font-semibold disabled:opacity-50 ${
                            j.activa
                              ? 'bg-green-100 text-green-700 dark:bg-green-500/15 dark:text-green-300'
                              : 'bg-gray-100 text-gray-500 dark:bg-white/10 dark:text-gray-400'
                          }`}
                        >
                          {j.activa ? 'Sí' : 'No'}
                        </button>
                      </td>
                      <td className="px-3 py-2">
                        <button
                          onClick={() => guardarJurisdiccion(j)}
                          disabled={savingJurId === j.id}
                          className="px-3 py-1.5 rounded-lg bg-ml-blue text-white text-xs font-medium hover:opacity-90 disabled:opacity-50"
                        >
                          {savingJurId === j.id ? 'Guardando…' : 'Guardar'}
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            {/* Alta de jurisdicción */}
            <div className="mt-3 rounded-xl border border-gray-200 dark:border-white/10 bg-white dark:bg-white/5 p-4">
              <h3 className="text-xs font-semibold text-gray-700 dark:text-gray-300 mb-2">Agregar jurisdicción</h3>
              <div className="grid grid-cols-1 sm:grid-cols-4 gap-2 items-end">
                <div className="sm:col-span-2">
                  <label className="block text-xs text-gray-500 dark:text-gray-400 mb-1">Nombre</label>
                  <input
                    className={inputClass}
                    placeholder="ej. Córdoba"
                    value={nuevoNombre}
                    onChange={e => setNuevoNombre(e.target.value)}
                  />
                </div>
                <div>
                  <label className="block text-xs text-gray-500 dark:text-gray-400 mb-1">Alícuota (%)</label>
                  <input
                    className={inputClass}
                    inputMode="decimal"
                    placeholder="ej. 5"
                    value={nuevoAlic}
                    onChange={e => setNuevoAlic(e.target.value)}
                  />
                </div>
                <div>
                  <label className="block text-xs text-gray-500 dark:text-gray-400 mb-1">Coef. (%)</label>
                  <input
                    className={inputClass}
                    inputMode="decimal"
                    placeholder="ej. 60"
                    value={nuevoCoef}
                    onChange={e => setNuevoCoef(e.target.value)}
                  />
                </div>
              </div>
              <button
                onClick={crearJurisdiccion}
                disabled={creandoJur}
                className="mt-3 inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-ml-blue text-white text-sm font-medium hover:opacity-90 disabled:opacity-50"
              >
                {creandoJur ? 'Creando…' : 'Agregar'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

export default IngresosBrutos
