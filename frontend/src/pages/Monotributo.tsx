import React, { useCallback, useEffect, useMemo, useState } from 'react'
import { apiClient } from '@/services/api'
import { confirmDialog } from '@/store/confirm'
import { useOrgStore } from '@/store/org'
import { useAuthStore } from '@/store/auth'
import { localIsoDate } from '@/utils/fecha'
import type {
  MonotributoConfig,
  CategoriaMonotributo,
  MonotributoControlPreview,
  ControlMonotributo,
} from '@/types'

// ── Helpers ─────────────────────────────────────────────────────────────────
const fmt = (n: number) =>
  new Intl.NumberFormat('es-AR', { style: 'currency', currency: 'ARS', minimumFractionDigits: 2 }).format(n || 0)

const fmtDate = (d?: string | null) =>
  d ? new Date(d).toLocaleString('es-AR') : '—'

/** Semestre actual (YYYY-S1/YYYY-S2) en hora local — NUNCA toISOString (da el mes de UTC). */
function semestreActual(): string {
  const d = new Date(localIsoDate())
  const anio = d.getFullYear()
  const mes = d.getMonth() + 1
  const sem = mes <= 6 ? 1 : 2
  return `${anio}-S${sem}`
}

/** Lista de semestres recientes para el selector (actual + 5 anteriores). */
function semestresRecientes(): string[] {
  const d = new Date(localIsoDate())
  let anio = d.getFullYear()
  let sem = d.getMonth() + 1 <= 6 ? 1 : 2
  const out: string[] = []
  for (let i = 0; i < 6; i++) {
    out.push(`${anio}-S${sem}`)
    sem -= 1
    if (sem === 0) { sem = 2; anio -= 1 }
  }
  return out
}

const inputClass =
  'w-full px-3 py-2 rounded-lg border bg-white dark:bg-white/5 border-gray-300 dark:border-white/10 text-gray-900 dark:text-gray-100 placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-ml-blue/40 text-sm'

const ESTADO_BADGE: Record<string, string> = {
  pendiente: 'bg-amber-100 text-amber-700 dark:bg-amber-500/15 dark:text-amber-300',
  revisado: 'bg-green-100 text-green-700 dark:bg-green-500/15 dark:text-green-300',
}

// SVG icons (Heroicons outline)
const IconCalc = () => (
  <svg className="w-4 h-4" fill="none" stroke="currentColor" strokeWidth={1.8} viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" d="M9 7.5h6m-6 3h6m-6 3h3m-9 4.5h12a2.25 2.25 0 002.25-2.25V5.25A2.25 2.25 0 0015 3H6a2.25 2.25 0 00-2.25 2.25v13.5A2.25 2.25 0 006 21z" /></svg>
)
const IconCheck = () => (
  <svg className="w-4 h-4" fill="none" stroke="currentColor" strokeWidth={1.8} viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" d="M9 12.75L11.25 15 15 9.75M21 12a9 9 0 11-18 0 9 9 0 0118 0z" /></svg>
)

function colorBarra(pct: number, excede: boolean): string {
  if (excede || pct > 95) return 'bg-red-500'
  if (pct >= 70) return 'bg-amber-500'
  return 'bg-green-500'
}

function colorTextoPct(pct: number, excede: boolean): string {
  if (excede || pct > 95) return 'text-red-700 dark:text-red-300'
  if (pct >= 70) return 'text-amber-700 dark:text-amber-300'
  return 'text-green-700 dark:text-green-300'
}

export const Monotributo: React.FC = () => {
  const { activeOrgId } = useOrgStore()
  const { hasPermission } = useAuthStore()
  const canManageFinance = hasPermission('manage_finance')
  const canAdminAccounting = hasPermission('admin_accounting')

  const [tab, setTab] = useState<'control' | 'historial' | 'config'>('control')
  const [msg, setMsg] = useState<{ type: 'error' | 'ok'; text: string } | null>(null)

  // ── Config (cargada siempre — determina si el módulo está activo) ────────
  const [config, setConfig] = useState<MonotributoConfig | null>(null)
  const [configLoaded, setConfigLoaded] = useState(false)

  const cargarConfigBase = useCallback(async () => {
    try {
      const data = await apiClient.getMonotributoConfig(activeOrgId || undefined)
      setConfig(data)
    } catch {
      setConfig(null)
    } finally {
      setConfigLoaded(true)
    }
  }, [activeOrgId])

  useEffect(() => { cargarConfigBase() }, [cargarConfigBase])

  // ── Tab Control ────────────────────────────────────────────────────────
  const [periodo, setPeriodo] = useState(semestreActual())
  const [preview, setPreview] = useState<MonotributoControlPreview | null>(null)
  const [persistido, setPersistido] = useState<ControlMonotributo | null>(null)
  const [loadingPreview, setLoadingPreview] = useState(false)
  const [calculando, setCalculando] = useState(false)
  const [marcando, setMarcando] = useState(false)

  const cargarPreview = useCallback(async () => {
    if (!periodo || !config?.activo) return
    setLoadingPreview(true)
    setMsg(null)
    try {
      const data = await apiClient.previewControlMonotributo(periodo, activeOrgId || undefined)
      setPreview(data)
    } catch {
      setPreview(null)
      setMsg({ type: 'error', text: 'No se pudo calcular el control del período.' })
    } finally {
      setLoadingPreview(false)
    }
  }, [periodo, activeOrgId, config?.activo])

  const buscarPersistido = useCallback(async () => {
    if (!config?.activo) return
    try {
      const data = await apiClient.getHistorialMonotributo({ orgId: activeOrgId || undefined, limit: 500 })
      const found = (data.items || []).find(c => c.periodo === periodo) || null
      setPersistido(found)
    } catch {
      setPersistido(null)
    }
  }, [periodo, activeOrgId, config?.activo])

  useEffect(() => { if (tab === 'control') cargarPreview() }, [tab, cargarPreview])
  useEffect(() => { if (tab === 'control') buscarPersistido() }, [tab, buscarPersistido])

  const calcularYGuardar = async () => {
    setCalculando(true)
    setMsg(null)
    try {
      const c = await apiClient.calcularControlMonotributo(periodo, activeOrgId || undefined)
      setPersistido(c)
      setMsg({ type: 'ok', text: 'Control calculado y guardado.' })
      await cargarPreview()
    } catch (e: unknown) {
      const detail = (e as { response?: { data?: { detail?: unknown } } })?.response?.data?.detail
      setMsg({ type: 'error', text: typeof detail === 'string' ? detail : 'No se pudo calcular el control.' })
    } finally {
      setCalculando(false)
    }
  }

  const marcarRevisado = async () => {
    if (!persistido) return
    const ok = await confirmDialog({
      title: 'Marcar control como revisado',
      message: `El período ${persistido.periodo} quedará marcado como revisado. ¿Confirmás que ya revisaste la categorización?`,
      confirmLabel: 'Marcar como revisado',
      danger: false,
    })
    if (!ok) return
    setMarcando(true)
    setMsg(null)
    try {
      const c = await apiClient.marcarControlRevisado(persistido.id, activeOrgId || undefined)
      setPersistido(c)
      setMsg({ type: 'ok', text: 'Control marcado como revisado.' })
    } catch {
      setMsg({ type: 'error', text: 'No se pudo marcar el control como revisado.' })
    } finally {
      setMarcando(false)
    }
  }

  const detalle = preview?.detalle ?? []
  const pct = preview?.porcentaje_uso ?? 0
  const excedeFlag = preview?.excede ?? false
  const sugiereCambio = !!preview?.categoria_sugerida && preview.categoria_sugerida !== preview.categoria_actual

  // ── Tab Historial ────────────────────────────────────────────────────────
  const [historial, setHistorial] = useState<ControlMonotributo[]>([])
  const [historialTotal, setHistorialTotal] = useState(0)
  const [historialLoading, setHistorialLoading] = useState(false)
  const [historialOffset, setHistorialOffset] = useState(0)
  const HISTORIAL_LIMIT = 20

  const cargarHistorial = useCallback(async () => {
    setHistorialLoading(true)
    try {
      const data = await apiClient.getHistorialMonotributo({
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
  const [configTipoActividad, setConfigTipoActividad] = useState<'servicios' | 'bienes'>('servicios')
  const [configCategoriaActual, setConfigCategoriaActual] = useState<string>('')
  const [guardandoConfig, setGuardandoConfig] = useState(false)

  const [categorias, setCategorias] = useState<CategoriaMonotributo[]>([])
  const [categoriasLoading, setCategoriasLoading] = useState(false)
  const [editValues, setEditValues] = useState<Record<number, string>>({})
  const [savingId, setSavingId] = useState<number | null>(null)

  useEffect(() => {
    if (config) {
      setConfigActivo(config.activo)
      setConfigTipoActividad(config.tipo_actividad)
      setConfigCategoriaActual(config.categoria_actual ?? '')
    }
  }, [config])

  const cargarCategorias = useCallback(async (tipoActividad: string) => {
    setCategoriasLoading(true)
    try {
      const data = await apiClient.getMonotributoCategorias(tipoActividad, activeOrgId || undefined)
      setCategorias(data.items || [])
      const ev: Record<number, string> = {}
      for (const c of data.items || []) {
        ev[c.id] = String(c.limite_anual ?? '')
      }
      setEditValues(ev)
    } catch {
      setCategorias([])
    } finally {
      setCategoriasLoading(false)
    }
  }, [activeOrgId])

  useEffect(() => {
    if (tab === 'config' && canAdminAccounting) cargarCategorias(configTipoActividad)
  }, [tab, canAdminAccounting, configTipoActividad, cargarCategorias])

  const guardarConfig = async () => {
    setGuardandoConfig(true)
    setMsg(null)
    try {
      const updated = await apiClient.setMonotributoConfig(
        {
          activo: configActivo,
          categoria_actual: configCategoriaActual || null,
          tipo_actividad: configTipoActividad,
        },
        activeOrgId || undefined,
      )
      setConfig(updated)
      setMsg({ type: 'ok', text: 'Configuración guardada.' })
    } catch {
      setMsg({ type: 'error', text: 'No se pudo guardar la configuración.' })
    } finally {
      setGuardandoConfig(false)
    }
  }

  const guardarLimite = async (cat: CategoriaMonotributo) => {
    const raw = (editValues[cat.id] ?? '').trim()
    const limite = parseFloat(raw.replace(/\./g, '').replace(',', '.'))
    if (isNaN(limite) || limite < 0) {
      setMsg({ type: 'error', text: 'Ingresá un límite anual válido (número positivo).' })
      return
    }
    setSavingId(cat.id)
    setMsg(null)
    try {
      const updated = await apiClient.setMonotributoCategoria(cat.id, limite, activeOrgId || undefined)
      setCategorias(prev => prev.map(c => (c.id === cat.id ? { ...c, limite_anual: updated.limite_anual } : c)))
      setMsg({ type: 'ok', text: `Límite de categoría "${cat.categoria}" actualizado.` })
    } catch {
      setMsg({ type: 'error', text: 'No se pudo guardar el límite anual.' })
    } finally {
      setSavingId(null)
    }
  }

  const categoriasOrdenadas = useMemo(
    () => [...categorias].sort((a, b) => a.orden - b.orden),
    [categorias],
  )

  // ── Render ──────────────────────────────────────────────────────────────
  return (
    <div className="p-4 md:p-6 max-w-6xl mx-auto">
      <h1 className="text-xl md:text-2xl font-semibold text-gray-900 dark:text-gray-100 mb-1">
        Monotributo — Control Semestral
      </h1>
      <p className="text-sm text-gray-500 dark:text-gray-400 mb-1">
        Herramienta de estimación interna. Esto es un control de alerta interno y
        <strong> no sustituye la verificación oficial en ARCA</strong>.
      </p>
      <p className="text-sm text-gray-500 dark:text-gray-400 mb-4">
        Los límites de categoría deben verificarse contra la tabla vigente de ARCA — los valores
        configurados pueden estar desactualizados.
      </p>

      {/* Tabs */}
      <div className="flex gap-1 mb-4 border-b border-gray-200 dark:border-white/10">
        {([
          ['control', 'Control Semestral'],
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

      {/* ── Tab Control Semestral ── */}
      {tab === 'control' && (
        <div className="space-y-4">
          {!configLoaded && (
            <div className="text-sm text-gray-500 dark:text-gray-400">Cargando configuración…</div>
          )}

          {configLoaded && !config?.activo && (
            <div className="rounded-xl border border-amber-200 dark:border-amber-500/30 bg-amber-50 dark:bg-amber-500/10 p-4 text-sm text-amber-800 dark:text-amber-200">
              El módulo de Monotributo no está activo para esta organización.{' '}
              {canAdminAccounting ? (
                <>Activalo en la pestaña <strong>Config</strong> para empezar a usar el control semestral.</>
              ) : (
                <>Pedile a un administrador de contabilidad que lo active en la pestaña Config.</>
              )}
            </div>
          )}

          {configLoaded && config?.activo && (
            <>
              <div className="flex flex-col sm:flex-row gap-3 sm:items-end">
                <div className="w-full sm:w-48">
                  <label className="block text-xs font-medium text-gray-600 dark:text-gray-400 mb-1">Semestre</label>
                  <select
                    className={inputClass}
                    value={periodo}
                    onChange={e => setPeriodo(e.target.value)}
                  >
                    {semestresRecientes().map(s => (
                      <option key={s} value={s}>{s}</option>
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
                    {persistido.estado === 'revisado' ? 'Revisado' : 'Pendiente de revisión'}
                  </span>
                )}
                {canAdminAccounting && persistido && persistido.estado === 'pendiente' && (
                  <button
                    onClick={marcarRevisado}
                    disabled={marcando}
                    className="inline-flex items-center gap-2 px-4 py-2 rounded-lg border border-green-300 dark:border-green-500/30 text-green-700 dark:text-green-300 text-sm font-medium hover:bg-green-50 dark:hover:bg-green-500/10 disabled:opacity-50"
                  >
                    <IconCheck />
                    {marcando ? 'Marcando…' : 'Marcar como revisado'}
                  </button>
                )}
              </div>

              {loadingPreview && (
                <div className="text-sm text-gray-500 dark:text-gray-400">Calculando control…</div>
              )}

              {!loadingPreview && preview && (
                <>
                  <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
                    <div className="rounded-xl border border-gray-200 dark:border-white/10 bg-white dark:bg-white/5 p-4 overflow-hidden">
                      <div className="text-xs text-gray-500 dark:text-gray-400 mb-1">Ingresos últimos 12 meses</div>
                      <div className="text-base font-semibold text-gray-900 dark:text-gray-100 truncate">{fmt(preview.ingresos_12m)}</div>
                      <div className="text-xs text-gray-400 mt-1">Corte: {fmtDate(preview.fecha_corte)}</div>
                    </div>
                    <div className="rounded-xl border border-gray-200 dark:border-white/10 bg-white dark:bg-white/5 p-4 overflow-hidden">
                      <div className="text-xs text-gray-500 dark:text-gray-400 mb-1">Categoría actual</div>
                      <div className="text-base font-semibold text-gray-900 dark:text-gray-100 truncate">{preview.categoria_actual}</div>
                      <div className="text-xs text-gray-400 mt-1 truncate">Límite anual: {fmt(preview.limite_categoria_actual)}</div>
                    </div>
                    <div className={`rounded-xl border p-4 overflow-hidden ${
                      excedeFlag
                        ? 'border-red-200 dark:border-red-500/30 bg-red-50 dark:bg-red-500/10'
                        : sugiereCambio
                          ? 'border-amber-200 dark:border-amber-500/30 bg-amber-50 dark:bg-amber-500/10'
                          : 'border-gray-200 dark:border-white/10 bg-white dark:bg-white/5'
                    }`}>
                      <div className="text-xs text-gray-500 dark:text-gray-400 mb-1">% de uso del límite</div>
                      <div className={`text-xl font-semibold truncate ${colorTextoPct(pct, excedeFlag)}`}>
                        {pct.toFixed(1)}%
                      </div>
                    </div>
                  </div>

                  {/* Barra de progreso */}
                  <div>
                    <div className="w-full h-3 rounded-full bg-gray-200 dark:bg-white/10 overflow-hidden">
                      <div
                        className={`h-full rounded-full transition-all ${colorBarra(pct, excedeFlag)}`}
                        style={{ width: `${Math.min(100, Math.max(0, pct))}%` }}
                      />
                    </div>
                  </div>

                  {excedeFlag && (
                    <div className="rounded-xl border border-red-200 dark:border-red-500/30 bg-red-50 dark:bg-red-500/10 p-4 text-sm font-medium text-red-700 dark:text-red-300">
                      Supera el límite máximo del régimen — excluido de Monotributo. Verificá la situación
                      con tu contador y la tabla vigente de ARCA.
                    </div>
                  )}
                  {!excedeFlag && sugiereCambio && (
                    <div className="rounded-xl border border-amber-200 dark:border-amber-500/30 bg-amber-50 dark:bg-amber-500/10 p-4 text-sm font-medium text-amber-700 dark:text-amber-300">
                      Se sugiere recategorizar a {preview.categoria_sugerida}.
                    </div>
                  )}

                  <div className="rounded-xl border border-gray-200 dark:border-white/10 overflow-x-auto">
                    <table className="w-full text-sm">
                      <thead>
                        <tr className="text-left text-xs text-gray-500 dark:text-gray-400 border-b border-gray-200 dark:border-white/10">
                          <th className="px-3 py-2 font-medium">Mes</th>
                          <th className="px-3 py-2 font-medium text-right">Ingresos</th>
                        </tr>
                      </thead>
                      <tbody>
                        {detalle.length === 0 && (
                          <tr><td colSpan={2} className="px-3 py-6 text-center text-gray-400">
                            Sin movimientos en los últimos 12 meses.
                          </td></tr>
                        )}
                        {detalle.map((d, i) => (
                          <tr key={d.mes} className={`border-b border-gray-100 dark:border-white/5 ${i % 2 ? 'bg-gray-50/50 dark:bg-white/[0.02]' : ''}`}>
                            <td className="px-3 py-2 text-gray-900 dark:text-gray-100 whitespace-nowrap">{d.mes}</td>
                            <td className="px-3 py-2 text-right text-gray-700 dark:text-gray-300 whitespace-nowrap">{fmt(d.ingresos)}</td>
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
                  <th className="px-3 py-2 font-medium text-right">Ingresos 12m</th>
                  <th className="px-3 py-2 font-medium">Categoría (actual → sugerida)</th>
                  <th className="px-3 py-2 font-medium text-right">% uso</th>
                  <th className="px-3 py-2 font-medium">Estado</th>
                </tr>
              </thead>
              <tbody>
                {historialLoading && (
                  <tr><td colSpan={5} className="px-3 py-6 text-center text-gray-400">Cargando…</td></tr>
                )}
                {!historialLoading && historial.length === 0 && (
                  <tr><td colSpan={5} className="px-3 py-6 text-center text-gray-400">Sin controles calculados.</td></tr>
                )}
                {!historialLoading && historial.map((c, i) => (
                  <tr key={c.id} className={`border-b border-gray-100 dark:border-white/5 ${i % 2 ? 'bg-gray-50/50 dark:bg-white/[0.02]' : ''}`}>
                    <td className="px-3 py-2 text-gray-900 dark:text-gray-100 whitespace-nowrap">{c.periodo}</td>
                    <td className="px-3 py-2 text-right text-gray-700 dark:text-gray-300 whitespace-nowrap">{fmt(c.ingresos_12m)}</td>
                    <td className="px-3 py-2 text-gray-700 dark:text-gray-300 whitespace-nowrap">
                      {c.categoria_actual}
                      {c.categoria_sugerida && c.categoria_sugerida !== c.categoria_actual && (
                        <span className="text-amber-600 dark:text-amber-400"> → {c.categoria_sugerida}</span>
                      )}
                    </td>
                    <td className={`px-3 py-2 text-right font-medium whitespace-nowrap ${colorTextoPct(c.porcentaje_uso, c.excede)}`}>
                      {c.porcentaje_uso.toFixed(1)}%
                    </td>
                    <td className="px-3 py-2">
                      <span className={`px-2 py-0.5 rounded-md text-xs font-semibold ${ESTADO_BADGE[c.estado] || ''}`}>
                        {c.estado === 'revisado' ? 'Revisado' : 'Pendiente'}
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
                id="mono-activo"
                type="checkbox"
                checked={configActivo}
                onChange={e => setConfigActivo(e.target.checked)}
                className="w-4 h-4 rounded border-gray-300 dark:border-white/20"
              />
              <label htmlFor="mono-activo" className="text-sm font-medium text-gray-800 dark:text-gray-200">
                Activar módulo de Monotributo para esta organización
              </label>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div>
                <label className="block text-xs font-medium text-gray-600 dark:text-gray-400 mb-1">Tipo de actividad</label>
                <select
                  className={inputClass}
                  value={configTipoActividad}
                  onChange={e => setConfigTipoActividad(e.target.value as 'servicios' | 'bienes')}
                >
                  <option value="servicios">Servicios</option>
                  <option value="bienes">Venta de bienes</option>
                </select>
              </div>
              <div>
                <label className="block text-xs font-medium text-gray-600 dark:text-gray-400 mb-1">Categoría actual</label>
                <select
                  className={inputClass}
                  value={configCategoriaActual}
                  onChange={e => setConfigCategoriaActual(e.target.value)}
                >
                  <option value="">— Sin categoría —</option>
                  {categoriasOrdenadas.map(c => (
                    <option key={c.id} value={c.categoria}>{c.categoria}</option>
                  ))}
                </select>
              </div>
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
              Los límites de categoría deben verificarse contra la tabla vigente de ARCA — los valores
              cargados a continuación pueden estar desactualizados. Esta tabla es de mantenimiento manual.
            </p>
            <h2 className="text-sm font-semibold text-gray-800 dark:text-gray-200 mb-2">
              Categorías ({configTipoActividad === 'servicios' ? 'Servicios' : 'Venta de bienes'})
            </h2>
            <div className="rounded-xl border border-gray-200 dark:border-white/10 overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-left text-xs text-gray-500 dark:text-gray-400 border-b border-gray-200 dark:border-white/10">
                    <th className="px-3 py-2 font-medium">Categoría</th>
                    <th className="px-3 py-2 font-medium w-48">Límite anual ($)</th>
                    <th className="px-3 py-2 font-medium w-24"></th>
                  </tr>
                </thead>
                <tbody>
                  {categoriasLoading && (
                    <tr><td colSpan={3} className="px-3 py-4 text-center text-gray-400">Cargando…</td></tr>
                  )}
                  {!categoriasLoading && categoriasOrdenadas.length === 0 && (
                    <tr><td colSpan={3} className="px-3 py-4 text-center text-gray-400">Sin categorías.</td></tr>
                  )}
                  {!categoriasLoading && categoriasOrdenadas.map((c, i) => (
                    <tr key={c.id} className={`border-b border-gray-100 dark:border-white/5 ${i % 2 ? 'bg-gray-50/50 dark:bg-white/[0.02]' : ''}`}>
                      <td className="px-3 py-2 text-gray-900 dark:text-gray-100 whitespace-nowrap">{c.categoria}</td>
                      <td className="px-3 py-2">
                        <input
                          className={inputClass}
                          inputMode="decimal"
                          placeholder="ej. 8000000"
                          value={editValues[c.id] ?? ''}
                          onChange={e => setEditValues(prev => ({ ...prev, [c.id]: e.target.value }))}
                        />
                      </td>
                      <td className="px-3 py-2">
                        <button
                          onClick={() => guardarLimite(c)}
                          disabled={savingId === c.id}
                          className="px-3 py-1.5 rounded-lg bg-ml-blue text-white text-xs font-medium hover:opacity-90 disabled:opacity-50"
                        >
                          {savingId === c.id ? 'Guardando…' : 'Guardar'}
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

export default Monotributo
