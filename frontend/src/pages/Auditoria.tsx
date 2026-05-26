import React, { useEffect, useState } from 'react'
import { apiClient } from '@/services/api'
import { AuditoriaLog } from '@/types'
import { useOrgStore } from '@/store/org'

interface Insights {
  periodo_dias: number
  resumen: {
    total_filas_procesadas: number
    auto_conciliadas: number
    correcciones_manuales: number
    faltan_datos: number
    no_encontradas: number
    duplicadas: number
    tasa_auto_conciliacion: number
  }
  clientes_problematicos: { cliente: string; total: number; faltan: number; ok: number; pct_problema: number }[]
  patrones_correcciones: Record<string, number>
  actividad_por_accion: Record<string, number>
  aprendizaje: {
    descripcion: string
    total_correcciones_historicas: number
    patrones_frecuentes: { patron: string; veces: number }[]
  }
}

export const Auditoria: React.FC = () => {
  const { activeOrgId } = useOrgStore()
  const [items, setItems] = useState<AuditoriaLog[]>([])
  const [insights, setInsights] = useState<Insights | null>(null)
  const [loading, setLoading] = useState(true)
  const [loadingInsights, setLoadingInsights] = useState(true)
  const [tabla, setTabla] = useState('')
  const [accion, setAccion] = useState('')
  const [tab, setTab] = useState<'insights' | 'log'>('insights')
  const [dias, setDias] = useState(30)

  const loadLog = async () => {
    setLoading(true)
    try {
      const res = await apiClient.getAuditoria({ tabla: tabla || undefined, accion: accion || undefined, limit: 200, org_id: activeOrgId })
      setItems(res.items)
    } catch { setItems([]) }
    finally { setLoading(false) }
  }

  const loadInsights = async () => {
    setLoadingInsights(true)
    try {
      const params: Record<string, string | number> = { dias }
      if (activeOrgId) params.org_id = activeOrgId
      const res = await apiClient.client.get('/auditoria/insights', { params })
      setInsights(res.data)
    } catch { setInsights(null) }
    finally { setLoadingInsights(false) }
  }

  useEffect(() => { loadInsights() }, [dias, activeOrgId])
  useEffect(() => { if (tab === 'log') loadLog() }, [tab, activeOrgId])

  const accionColor = (a: string) => {
    if (a === 'INSERT') return 'badge-ok'
    if (a === 'UPDATE' || a === 'UPDATE_STATUS') return 'badge-info'
    if (a === 'DELETE') return 'badge-error'
    if (a === 'CONCILIAR') return 'bg-purple-100 text-purple-700 dark:bg-purple-900/20 dark:text-purple-400 border border-purple-200 dark:border-purple-900'
    if (a === 'RESOLVER_REVISION') return 'badge-warn'
    return 'badge-neutral'
  }

  const r = insights?.resumen

  return (
    <div className="p-4 md:p-6 max-w-6xl mx-auto">
      {/* Header */}
      <div className="flex items-start justify-between mb-5 flex-wrap gap-3">
        <div>
          <h1 className="text-xl font-bold dark:text-white">Auditoría e Inteligencia</h1>
          <p className="text-sm text-gray-400 dark:text-zinc-500 mt-0.5">
            El sistema aprende de cada corrección manual que hacés
          </p>
        </div>
        <div className="flex gap-1 bg-ml-gray dark:bg-ml-dark-card rounded-lg p-1">
          {(['insights', 'log'] as const).map(t => (
            <button key={t} onClick={() => setTab(t)}
              className={`px-4 py-1.5 rounded-md text-sm font-medium transition-all ${tab === t
                ? 'bg-white dark:bg-ml-dark-surface text-ml-text dark:text-white shadow-sm'
                : 'text-ml-text-soft dark:text-gray-500 hover:text-ml-text dark:hover:text-gray-300'}`}>
              {t === 'insights' ? '📊 Inteligencia' : '📋 Log'}
            </button>
          ))}
        </div>
      </div>

      {/* ── TAB: INSIGHTS ──────────────────────────────── */}
      {tab === 'insights' && (
        <div className="space-y-5">
          {/* Selector periodo */}
          <div className="flex gap-2 items-center">
            <span className="text-sm text-gray-500 dark:text-zinc-500">Período:</span>
            {[7, 30, 90].map(d => (
              <button key={d} onClick={() => setDias(d)}
                className={`px-3 py-1 rounded-lg text-xs font-medium transition-all ${dias === d
                  ? 'bg-ml-blue dark:bg-ml-green text-white dark:text-black'
                  : 'bg-ml-gray dark:bg-ml-dark-card text-gray-600 dark:text-gray-400'}`}>
                {d === 7 ? 'Última semana' : d === 30 ? 'Último mes' : 'Últimos 3 meses'}
              </button>
            ))}
          </div>

          {loadingInsights ? (
            <div className="card p-10 text-center text-gray-400">Analizando datos...</div>
          ) : !insights ? (
            <div className="card p-10 text-center text-gray-400">Sin datos suficientes aún</div>
          ) : (
            <>
              {/* KPIs principales */}
              <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                {[
                  { label: 'Auto-conciliadas', val: r!.auto_conciliadas, cls: 'text-green-500 dark:text-green-400', sub: `de ${r!.total_filas_procesadas} filas` },
                  { label: 'Tasa de éxito', val: `${r!.tasa_auto_conciliacion}%`, cls: r!.tasa_auto_conciliacion >= 80 ? 'text-green-500' : r!.tasa_auto_conciliacion >= 60 ? 'text-amber-500' : 'text-red-500', sub: 'sin intervención manual' },
                  { label: 'Correcciones manuales', val: r!.correcciones_manuales, cls: 'text-blue-500 dark:text-blue-400', sub: 'te enseñan al sistema' },
                  { label: 'Faltan datos', val: r!.faltan_datos, cls: 'text-amber-500', sub: 'necesitan CUIT/CBU' },
                ].map(k => (
                  <div key={k.label} className="kpi">
                    <p className="kpi-label">{k.label}</p>
                    <p className={`kpi-value ${k.cls}`}>{k.val}</p>
                    <p className="text-xs text-gray-400 dark:text-zinc-600 mt-1">{k.sub}</p>
                  </div>
                ))}
              </div>

              {/* Aprendizaje */}
              <div className="card border-l-4 border-ml-blue dark:border-ml-green">
                <div className="flex items-start gap-3">
                  <div className="text-2xl">🧠</div>
                  <div className="flex-1">
                    <p className="font-semibold dark:text-white text-sm">Sistema de aprendizaje</p>
                    <p className="text-xs text-gray-500 dark:text-zinc-500 mt-0.5">{insights.aprendizaje.descripcion}</p>
                    <div className="mt-3 flex flex-wrap gap-2">
                      <span className="badge badge-info">
                        {insights.aprendizaje.total_correcciones_historicas} correcciones acumuladas
                      </span>
                      {insights.aprendizaje.patrones_frecuentes.map(p => (
                        <span key={p.patron} className="badge badge-neutral font-mono text-2xs">
                          {p.patron} × {p.veces}
                        </span>
                      ))}
                    </div>
                    {insights.aprendizaje.total_correcciones_historicas < 50 && (
                      <p className="text-xs text-amber-500 dark:text-amber-400 mt-2">
                        ⚠ Necesitás más correcciones para activar sugerencias automáticas. Meta: 50+
                      </p>
                    )}
                  </div>
                </div>
              </div>

              {/* Clientes problemáticos */}
              {insights.clientes_problematicos.length > 0 && (
                <div className="card p-0 overflow-hidden">
                  <div className="px-4 py-3 border-b border-ml-gray dark:border-ml-dark-border">
                    <p className="font-semibold text-sm dark:text-white">Clientes que más necesitan CUIT/CBU</p>
                    <p className="text-xs text-gray-400 dark:text-zinc-500 mt-0.5">
                      Pedíles estos datos para mejorar el match automático
                    </p>
                  </div>
                  <div className="divide-y dark:divide-ml-dark-border">
                    {insights.clientes_problematicos.map(c => (
                      <div key={c.cliente} className="flex items-center gap-3 px-4 py-3">
                        <div className="flex-1 min-w-0">
                          <p className="font-medium text-sm dark:text-white">{c.cliente}</p>
                          <p className="text-xs text-gray-400 dark:text-zinc-500">
                            {c.ok} auto · {c.faltan} sin datos · {c.total} total
                          </p>
                        </div>
                        <div className="flex items-center gap-2 shrink-0">
                          <div className="w-24 h-1.5 bg-ml-gray dark:bg-ml-dark-border rounded-full overflow-hidden">
                            <div className="h-full bg-amber-400 rounded-full"
                              style={{ width: `${c.pct_problema}%` }} />
                          </div>
                          <span className={`text-xs font-mono font-bold ${c.pct_problema > 50 ? 'text-red-500' : 'text-amber-500'}`}>
                            {c.pct_problema}%
                          </span>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Actividad */}
              {Object.keys(insights.actividad_por_accion).length > 0 && (
                <div className="card">
                  <p className="font-semibold text-sm dark:text-white mb-3">Actividad en el período</p>
                  <div className="flex flex-wrap gap-2">
                    {Object.entries(insights.actividad_por_accion)
                      .sort((a, b) => b[1] - a[1])
                      .map(([accion, cantidad]) => (
                        <div key={accion} className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-ml-gray-bg dark:bg-ml-dark-card border border-ml-gray dark:border-ml-dark-border">
                          <span className="text-xs font-mono text-gray-500 dark:text-zinc-400">{accion}</span>
                          <span className="text-sm font-bold text-ml-text dark:text-white">{cantidad}</span>
                        </div>
                      ))}
                  </div>
                </div>
              )}
            </>
          )}
        </div>
      )}

      {/* ── TAB: LOG ───────────────────────────────────── */}
      {tab === 'log' && (
        <div>
          <div className="card mb-4 flex gap-3 items-end flex-wrap">
            <div className="flex-1 min-w-[140px]">
              <label className="label">Tabla</label>
              <select className="input-field" value={tabla} onChange={e => setTabla(e.target.value)}>
                <option value="">Todas</option>
                <option value="users">Usuarios</option>
                <option value="planillas">Planillas</option>
                <option value="planilla_rows">Filas planilla</option>
                <option value="extractos_bancarios">Extractos</option>
                <option value="organizaciones">Orgs</option>
              </select>
            </div>
            <div className="flex-1 min-w-[140px]">
              <label className="label">Acción</label>
              <select className="input-field" value={accion} onChange={e => setAccion(e.target.value)}>
                <option value="">Todas</option>
                <option value="INSERT">Crear</option>
                <option value="UPDATE">Modificar</option>
                <option value="UPDATE_STATUS">Corrección manual</option>
                <option value="DELETE">Borrar</option>
                <option value="CONCILIAR">Conciliar</option>
                <option value="RESOLVER_REVISION">Resolver revisión</option>
              </select>
            </div>
            <button onClick={loadLog} className="btn-primary">Filtrar</button>
          </div>

          <div className="card overflow-hidden p-0">
            {loading ? (
              <div className="p-8 text-center text-gray-400">Cargando...</div>
            ) : items.length === 0 ? (
              <div className="p-8 text-center text-gray-400">Sin registros</div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-sm min-w-[640px]">
                  <thead className="bg-ml-gray-bg dark:bg-ml-dark-card border-b border-ml-gray dark:border-ml-dark-border">
                    <tr>
                      {['Fecha', 'Usuario', 'Acción', 'Tabla', 'Detalles'].map(h => (
                        <th key={h} className="px-4 py-2.5 text-left text-xs font-semibold text-gray-500 dark:text-zinc-500 uppercase tracking-wider">{h}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-ml-gray dark:divide-ml-dark-border">
                    {items.map(it => (
                      <tr key={it.id} className="hover:bg-ml-gray-bg dark:hover:bg-ml-dark-hover">
                        <td className="px-4 py-2.5 text-xs text-gray-500 dark:text-zinc-400 whitespace-nowrap font-mono">
                          {new Date(it.timestamp).toLocaleString('es-AR', { dateStyle: 'short', timeStyle: 'short' })}
                        </td>
                        <td className="px-4 py-2.5 text-sm dark:text-gray-200">
                          {it.usuario_nombre || `#${it.usuario_id}`}
                        </td>
                        <td className="px-4 py-2.5">
                          <span className={`badge text-2xs ${accionColor(it.accion)}`}>{it.accion}</span>
                        </td>
                        <td className="px-4 py-2.5 text-xs text-gray-500 dark:text-zinc-500 font-mono">{it.tabla}</td>
                        <td className="px-4 py-2.5 text-xs text-gray-400 dark:text-zinc-600 font-mono max-w-xs truncate">
                          {it.cambios ? JSON.stringify(it.cambios).slice(0, 80) : '—'}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  )
}
