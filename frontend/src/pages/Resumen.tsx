import React, { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { apiClient } from '@/services/api'
import { Skeleton, SkeletonKpi } from '@/components/Skeleton'
import { LineChart } from '@/components/charts/LineChart'
import { useOrgStore } from '@/store/org'

type Periodo = 'hoy' | 'semana' | 'mes'

type Cantidad = { total: number; cantidad: number }
type KpisPeriodo = {
  rango: { desde: string; hasta: string }
  conciliado: Cantidad
  pendiente: Cantidad
  total_reportado: Cantidad
  tasa_conciliacion_pct: number
  movimientos_banco: Cantidad
  cheques_cargados: Cantidad
  pagos: Cantidad
  gastos: Cantidad
}
type Dashboard = {
  organizacion_id: number
  periodo: Periodo
  periodo_label: string
  periodo_actual: KpisPeriodo
  periodo_anterior: KpisPeriodo
  variaciones: Record<string, number | null>
  top_clientes: { cliente_id: number; nombre: string; total: number; cantidad: number }[]
  cheques: {
    resumen: Record<string, Cantidad>
    proximos_a_vencer: {
      id: number
      numero: string | null
      monto: number
      fecha_deposito: string | null
      dias_para_vencer: number | null
      cliente_nombre: string | null
      titular: string | null
      banco_origen: string | null
    }[]
  }
}

function fmtMoney(n: number): string {
  return new Intl.NumberFormat('es-AR', { style: 'currency', currency: 'ARS', maximumFractionDigits: 0 }).format(n)
}

function fmtPct(n: number | null | undefined): string {
  if (n === null || n === undefined) return '—'
  return `${n > 0 ? '+' : ''}${n.toFixed(1)}%`
}

const MESES = ['Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio', 'Julio', 'Agosto', 'Septiembre', 'Octubre', 'Noviembre', 'Diciembre']

export const Resumen: React.FC = () => {
  const hoy = useMemo(() => new Date(), [])
  const { activeOrgId } = useOrgStore()
  // Default "hoy" porque para financiera la visibilidad diaria es lo critico
  const [periodo, setPeriodo] = useState<Periodo>('hoy')
  const [anio, setAnio] = useState(hoy.getFullYear())
  const [mes, setMes] = useState(hoy.getMonth() + 1)
  const [data, setData] = useState<Dashboard | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [downloadingPdf, setDownloadingPdf] = useState(false)
  const [evolucion, setEvolucion] = useState<{ label: string; conciliado: number; pendiente: number }[]>([])

  useEffect(() => {
    let activo = true
    setLoading(true)
    setError('')
    const params: any = { periodo }
    if (periodo === 'mes') { params.anio = anio; params.mes = mes }
    if (activeOrgId) params.org_id = activeOrgId
    Promise.all([
      apiClient.getDashboard(params),
      apiClient.getEvolucion(6, activeOrgId ?? undefined),
    ])
      .then(([d, ev]) => {
        if (!activo) return
        setData(d)
        setEvolucion(ev.meses || [])
      })
      .catch((e) => { if (activo) setError(e.response?.data?.detail || 'Error cargando dashboard') })
      .finally(() => { if (activo) setLoading(false) })
    return () => { activo = false }
  }, [periodo, anio, mes, activeOrgId])

  const evolucionLine = useMemo(
    () => evolucion.map(m => ({ label: m.label, value: m.conciliado })),
    [evolucion]
  )

  const navegarMes = (delta: number) => {
    let m = mes + delta
    let a = anio
    if (m < 1) { m = 12; a -= 1 }
    if (m > 12) { m = 1; a += 1 }
    setMes(m)
    setAnio(a)
  }

  const labelComparativa = periodo === 'hoy' ? 'vs ayer' : periodo === 'semana' ? 'vs semana pasada' : 'vs mes pasado'

  if (loading && !data) {
    return (
      <div className="p-4 sm:p-6 space-y-6 max-w-7xl">
        <div className="space-y-2">
          <Skeleton className="h-7 w-56" />
          <Skeleton className="h-3 w-72" />
        </div>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          {Array.from({ length: 4 }).map((_, i) => <SkeletonKpi key={i} />)}
        </div>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          {Array.from({ length: 4 }).map((_, i) => <SkeletonKpi key={i} />)}
        </div>
        <div className="card space-y-3">
          <Skeleton className="h-4 w-40" />
          {Array.from({ length: 5 }).map((_, i) => (
            <div key={i} className="flex items-center justify-between gap-3 py-1">
              <Skeleton className="h-3 w-1/3" />
              <Skeleton className="h-2 flex-1 max-w-[40%]" />
              <Skeleton className="h-3 w-20" />
            </div>
          ))}
        </div>
      </div>
    )
  }

  if (error) {
    return <div className="p-6 text-red-600 dark:text-red-400">{error}</div>
  }

  if (!data) return null

  const k = data.periodo_actual
  const v = data.variaciones

  return (
    <div className="p-4 sm:p-6 space-y-6 max-w-7xl">
      {/* Header */}
      <div className="space-y-3">
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
          <div>
            <h1 className="text-2xl font-bold text-ml-text dark:text-white tracking-tight">Resumen ejecutivo</h1>
            <p className="text-xs text-ml-text-soft dark:text-zinc-500 mt-1">
              {periodo === 'hoy' && `Hoy · ${k.rango.desde}`}
              {periodo === 'semana' && `Últimos 7 días · ${k.rango.desde} → ${k.rango.hasta}`}
              {periodo === 'mes' && `${MESES[mes - 1]} ${anio} · ${k.rango.desde} → ${k.rango.hasta}`}
            </p>
          </div>

          {/* Selector de periodo (segment control) */}
          <div className="flex items-center gap-1 bg-white dark:bg-ml-dark-surface rounded-lg border border-gray-200 dark:border-ml-dark-border p-1">
            {(['hoy', 'semana', 'mes'] as Periodo[]).map((p) => (
              <button
                key={p}
                onClick={() => setPeriodo(p)}
                className={`px-3 py-1.5 text-xs font-medium rounded transition-colors capitalize ${
                  periodo === p
                    ? 'bg-ml-text dark:bg-ml-green text-white dark:text-ml-dark-bg'
                    : 'text-ml-text-soft dark:text-zinc-400 hover:bg-gray-50 dark:hover:bg-white/5'
                }`}
              >
                {p}
              </button>
            ))}
          </div>
        </div>

        {/* Navegacion de mes (solo cuando periodo=mes) + boton PDF */}
        {periodo === 'mes' && (
          <div className="flex items-center gap-2 flex-wrap">
            <div className="flex items-center gap-2 bg-white dark:bg-ml-dark-surface rounded-lg border border-gray-200 dark:border-ml-dark-border p-1 w-fit">
              <button
                onClick={() => navegarMes(-1)}
                className="px-3 py-1.5 text-sm hover:bg-gray-50 dark:hover:bg-white/5 rounded transition-colors text-ml-text dark:text-zinc-300"
                aria-label="Mes anterior"
              >
                ←
              </button>
              <span className="px-3 py-1.5 text-sm font-medium text-ml-text dark:text-white whitespace-nowrap">
                {MESES[mes - 1]} {anio}
              </span>
              <button
                onClick={() => navegarMes(1)}
                className="px-3 py-1.5 text-sm hover:bg-gray-50 dark:hover:bg-white/5 rounded transition-colors text-ml-text dark:text-zinc-300"
                aria-label="Mes siguiente"
              >
                →
              </button>
            </div>
            <button
              onClick={async () => {
                setDownloadingPdf(true)
                try { await apiClient.downloadCierreMensualPdf(anio, mes) }
                catch { /* error silent */ }
                finally { setDownloadingPdf(false) }
              }}
              disabled={downloadingPdf || !data}
              className="px-3 py-1.5 text-sm rounded-lg bg-ml-text dark:bg-ml-green text-white dark:text-ml-dark-bg font-semibold hover:opacity-90 transition-opacity disabled:opacity-50"
              title="Descargar cierre mensual en PDF"
            >
              {downloadingPdf ? 'Generando…' : '📄 PDF cierre'}
            </button>
            <button
              onClick={async () => {
                try { await apiClient.downloadCierreMensualXlsx(anio, mes) }
                catch { /* silently fail */ }
              }}
              className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-emerald-600 dark:text-emerald-400 border border-emerald-200 dark:border-emerald-800 rounded-lg hover:bg-emerald-50 dark:hover:bg-emerald-900/20 transition-colors"
              title="Excel de cierre mensual para el contador"
            >📊 Excel mes</button>
          </div>
        )}
      </div>

      {/* KPIs principales (4 cards grandes) */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <KpiCard
          label="Conciliado"
          monto={k.conciliado.total}
          cantidad={`${k.conciliado.cantidad} mov`}
          variacion={v.conciliado_pct}
          color="emerald"
        />
        <KpiCard
          label="Pendiente"
          monto={k.pendiente.total}
          cantidad={`${k.pendiente.cantidad} mov`}
          variacion={v.pendiente_pct}
          color="amber"
          invertirVariacion
        />
        <KpiCard
          label="Tasa conciliación"
          monto={k.tasa_conciliacion_pct}
          esPorcentaje
          cantidad={`${fmtMoney(k.total_reportado.total)} reportado`}
          color="indigo"
        />
        <KpiCard
          label="Movimientos banco"
          monto={k.movimientos_banco.total}
          cantidad={`${k.movimientos_banco.cantidad} movs`}
          variacion={v.movimientos_pct}
          color="cyan"
        />
      </div>

      {/* Sub-KPIs */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        <MiniKpi label="Cheques cargados" monto={k.cheques_cargados.total} count={k.cheques_cargados.cantidad} />
        <MiniKpi label="Pagos a clientes" monto={k.pagos.total} count={k.pagos.cantidad} />
        <MiniKpi label="Gastos" monto={k.gastos.total} count={k.gastos.cantidad} variacion={v.gastos_pct} invertirVariacion />
        <MiniKpi
          label="Diferencia neta"
          monto={k.movimientos_banco.total - k.gastos.total}
          count="ingresos - gastos"
        />
      </div>

      {/* Grid de 2 columnas: Top clientes + Cheques */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">

        {/* Top 5 clientes */}
        <div className="bg-white dark:bg-ml-dark-surface rounded-xl border border-gray-100 dark:border-ml-dark-border p-5">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-sm font-semibold text-ml-text dark:text-white uppercase tracking-wide">
              Top clientes del mes
            </h2>
            <Link to="/clientes" className="text-xs text-ml-text-soft hover:text-ml-text dark:text-zinc-500 dark:hover:text-ml-green">
              Ver todos →
            </Link>
          </div>
          {data.top_clientes.length === 0 ? (
            <p className="text-sm text-ml-text-soft dark:text-zinc-500">Sin movimientos OK este mes</p>
          ) : (
            <div className="space-y-2">
              {data.top_clientes.map((c, i) => {
                const max = data.top_clientes[0]?.total || 1
                const pct = (c.total / max) * 100
                return (
                  <div key={c.cliente_id}>
                    <div className="flex items-center justify-between text-sm mb-1">
                      <Link
                        to={`/clientes/${c.cliente_id}/estado-cuenta`}
                        className="font-medium text-ml-text dark:text-white hover:text-indigo-600 dark:hover:text-ml-green transition-colors"
                      >
                        {i + 1}. {c.nombre}
                      </Link>
                      <span className="font-mono text-xs text-ml-text dark:text-white">{fmtMoney(c.total)}</span>
                    </div>
                    <div className="h-1.5 bg-gray-100 dark:bg-white/5 rounded-full overflow-hidden">
                      <div className="h-full bg-emerald-500 dark:bg-ml-green rounded-full" style={{ width: `${pct}%` }} />
                    </div>
                    <p className="text-[10px] text-ml-text-soft dark:text-zinc-600 mt-0.5">{c.cantidad} movimientos</p>
                  </div>
                )
              })}
            </div>
          )}
        </div>

        {/* Cheques en cartera */}
        <div className="bg-white dark:bg-ml-dark-surface rounded-xl border border-gray-100 dark:border-ml-dark-border p-5">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-sm font-semibold text-ml-text dark:text-white uppercase tracking-wide">
              Cheques en cartera
            </h2>
            <Link to="/cheques" className="text-xs text-ml-text-soft hover:text-ml-text dark:text-zinc-500 dark:hover:text-ml-green">
              Ver todos →
            </Link>
          </div>
          <div className="grid grid-cols-3 gap-3 mb-4">
            <ChequeStatBox label="Pendientes" data={data.cheques.resumen.pendiente} color="amber" />
            <ChequeStatBox label="Acreditados" data={data.cheques.resumen.acreditado} color="emerald" />
            <ChequeStatBox label="Rechazados" data={data.cheques.resumen.rechazado} color="red" />
          </div>

          <div>
            <p className="text-xs text-ml-text-soft dark:text-zinc-500 uppercase tracking-wide mb-2">
              Próximos a vencer (30 días)
            </p>
            {data.cheques.proximos_a_vencer.length === 0 ? (
              <p className="text-sm text-ml-text-soft dark:text-zinc-500">Ningún cheque por vencer</p>
            ) : (
              <div className="space-y-1.5 max-h-48 overflow-y-auto">
                {data.cheques.proximos_a_vencer.map((c) => {
                  const urgente = (c.dias_para_vencer ?? 99) <= 7
                  return (
                    <div key={c.id} className="flex items-center justify-between gap-2 text-xs py-1.5 px-2 rounded bg-gray-50 dark:bg-white/5">
                      <div className="min-w-0 flex-1">
                        <div className="font-medium text-ml-text dark:text-white truncate">
                          {c.cliente_nombre || c.titular || 'Sin titular'}
                        </div>
                        <div className="text-[10px] text-ml-text-soft dark:text-zinc-500">
                          {c.fecha_deposito} {c.numero ? `· #${c.numero}` : ''}
                        </div>
                      </div>
                      <div className="text-right shrink-0">
                        <div className="font-mono text-ml-text dark:text-white">{fmtMoney(c.monto)}</div>
                        <div className={`text-[10px] ${urgente ? 'text-red-600 dark:text-red-400 font-semibold' : 'text-ml-text-soft dark:text-zinc-500'}`}>
                          {c.dias_para_vencer === 0 ? 'hoy' : `${c.dias_para_vencer} días`}
                        </div>
                      </div>
                    </div>
                  )
                })}
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Evolución 6 meses */}
      <div className="bg-white dark:bg-ml-dark-surface rounded-xl border border-gray-100 dark:border-ml-dark-border p-5">
        <div className="flex items-center justify-between mb-3">
          <h2 className="text-sm font-semibold text-ml-text dark:text-white uppercase tracking-wide">
            Evolución conciliado · 6 meses
          </h2>
          <Link to="/flujo-de-caja" className="text-xs text-ml-text-soft hover:text-ml-text dark:text-zinc-500 dark:hover:text-ml-green">
            Ver flujo de caja →
          </Link>
        </div>
        {loading ? (
          <div className="h-[160px] animate-pulse bg-gray-100 dark:bg-white/5 rounded" />
        ) : (
          <LineChart
            data={evolucionLine}
            height={160}
            color="#10b981"
            formatValue={(n) => new Intl.NumberFormat('es-AR', { notation: 'compact', maximumFractionDigits: 1 }).format(n)}
          />
        )}
      </div>

      {/* Footer info */}
      <p className="text-xs text-ml-text-soft dark:text-zinc-600 text-center">
        Comparativa: {data.periodo_anterior.rango.desde}
        {data.periodo_anterior.rango.desde !== data.periodo_anterior.rango.hasta && ` → ${data.periodo_anterior.rango.hasta}`}
        {' '}({labelComparativa})
      </p>
    </div>
  )
}

/* ─── Sub-componentes ─────────────────────────────────────────── */

const COLOR_CLASSES: Record<string, string> = {
  emerald: 'text-emerald-700 dark:text-emerald-400 bg-emerald-50 dark:bg-emerald-950/30 border-emerald-200 dark:border-emerald-900/40',
  amber:   'text-amber-800  dark:text-amber-400  bg-amber-50  dark:bg-amber-950/30  border-amber-200  dark:border-amber-900/40',
  indigo:  'text-indigo-700 dark:text-indigo-400 bg-indigo-50 dark:bg-indigo-950/30 border-indigo-200 dark:border-indigo-900/40',
  cyan:    'text-cyan-700   dark:text-cyan-400   bg-cyan-50   dark:bg-cyan-950/30   border-cyan-200   dark:border-cyan-900/40',
  red:     'text-red-700    dark:text-red-400    bg-red-50    dark:bg-red-950/30    border-red-200    dark:border-red-900/40',
}

const KpiCard: React.FC<{
  label: string
  monto: number
  cantidad?: string
  variacion?: number | null
  color: 'emerald' | 'amber' | 'indigo' | 'cyan' | 'red'
  esPorcentaje?: boolean
  invertirVariacion?: boolean
}> = ({ label, monto, cantidad, variacion, color, esPorcentaje, invertirVariacion }) => {
  const variacionPositiva = variacion !== null && variacion !== undefined && variacion > 0
  const variacionBuena = invertirVariacion ? !variacionPositiva : variacionPositiva
  return (
    <div className={`rounded-xl border p-4 ${COLOR_CLASSES[color]}`}>
      <p className="text-xs font-semibold uppercase tracking-wide opacity-75">{label}</p>
      <p className="text-2xl font-bold mt-2">
        {esPorcentaje ? `${monto.toFixed(1)}%` : fmtMoney(monto)}
      </p>
      <div className="flex items-baseline justify-between mt-1 gap-2">
        <span className="text-[11px] opacity-70 truncate">{cantidad}</span>
        {variacion !== undefined && variacion !== null && (
          <span className={`text-[11px] font-semibold whitespace-nowrap ${variacionBuena ? 'text-emerald-700 dark:text-emerald-400' : 'text-red-600 dark:text-red-400'}`}>
            {fmtPct(variacion)}
          </span>
        )}
      </div>
    </div>
  )
}

const MiniKpi: React.FC<{ label: string; monto: number; count: string | number; variacion?: number | null; invertirVariacion?: boolean }> = ({ label, monto, count, variacion, invertirVariacion }) => {
  const positiva = (variacion ?? 0) > 0
  const buena = invertirVariacion ? !positiva : positiva
  return (
    <div className="bg-white dark:bg-ml-dark-surface border border-gray-100 dark:border-ml-dark-border rounded-lg p-3">
      <p className="text-[10px] uppercase tracking-wide text-ml-text-soft dark:text-zinc-500 font-semibold">{label}</p>
      <p className="text-base font-bold text-ml-text dark:text-white mt-1">{fmtMoney(monto)}</p>
      <div className="flex items-center justify-between mt-1 gap-2">
        <span className="text-[10px] text-ml-text-soft dark:text-zinc-600">{count}</span>
        {variacion !== undefined && variacion !== null && (
          <span className={`text-[10px] font-semibold ${buena ? 'text-emerald-600 dark:text-emerald-400' : 'text-red-600 dark:text-red-400'}`}>
            {fmtPct(variacion)}
          </span>
        )}
      </div>
    </div>
  )
}

const ChequeStatBox: React.FC<{ label: string; data?: Cantidad; color: 'emerald' | 'amber' | 'red' }> = ({ label, data, color }) => {
  const colorTxt = color === 'emerald' ? 'text-emerald-700 dark:text-emerald-400' : color === 'amber' ? 'text-amber-700 dark:text-amber-400' : 'text-red-700 dark:text-red-400'
  return (
    <div className="text-center p-2 rounded bg-gray-50 dark:bg-white/5">
      <p className="text-[10px] uppercase tracking-wide text-ml-text-soft dark:text-zinc-500 font-semibold">{label}</p>
      <p className={`text-sm font-bold mt-1 ${colorTxt}`}>{fmtMoney(data?.total || 0)}</p>
      <p className="text-[10px] text-ml-text-soft dark:text-zinc-600">{data?.cantidad || 0} chq</p>
    </div>
  )
}
