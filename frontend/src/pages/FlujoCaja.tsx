import React, { useEffect, useMemo, useState } from 'react'
import { apiClient } from '@/services/api'
import { LineChart } from '@/components/charts/LineChart'
import { BarChart } from '@/components/charts/BarChart'
import { SkeletonKpi } from '@/components/Skeleton'

type MesFlujo = {
  label: string
  anio: number
  mes: number
  ingresos: number
  egresos: number
  neto: number
}

type MesEvolucion = {
  label: string
  anio: number
  mes: number
  conciliado: number
  pendiente: number
  tasa_pct: number
}

const fmtMoney = (n: number) =>
  new Intl.NumberFormat('es-AR', { style: 'currency', currency: 'ARS', maximumFractionDigits: 0 }).format(n)

const fmtCompact = (n: number) =>
  new Intl.NumberFormat('es-AR', { notation: 'compact', maximumFractionDigits: 1 }).format(n)

function KpiCard({ label, value, sub, positive }: { label: string; value: string; sub?: string; positive?: boolean }) {
  return (
    <div className="bg-white dark:bg-white/5 border border-gray-100 dark:border-white/10 rounded-xl p-4 flex flex-col gap-1">
      <span className="text-xs text-ml-text-soft dark:text-zinc-400 uppercase tracking-wide">{label}</span>
      <span className={`text-2xl font-semibold tabular-nums ${
        positive === true ? 'text-emerald-600 dark:text-emerald-400' :
        positive === false ? 'text-red-500 dark:text-red-400' :
        'text-ml-text dark:text-white'
      }`}>{value}</span>
      {sub && <span className="text-xs text-ml-text-soft dark:text-zinc-500">{sub}</span>}
    </div>
  )
}

export const FlujoCaja: React.FC = () => {
  const [meses, setMeses] = useState(6)
  const [flujo, setFlujo] = useState<MesFlujo[]>([])
  const [evolucion, setEvolucion] = useState<MesEvolucion[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    let activo = true
    setLoading(true)
    setError('')
    Promise.all([
      apiClient.getFlujoCaja(meses),
      apiClient.getEvolucion(meses),
    ])
      .then(([f, e]) => {
        if (!activo) return
        setFlujo(f.meses || [])
        setEvolucion(e.meses || [])
      })
      .catch((e) => {
        if (activo) setError(e.response?.data?.detail || 'Error cargando datos')
      })
      .finally(() => { if (activo) setLoading(false) })
    return () => { activo = false }
  }, [meses])

  const totales = useMemo(() => {
    const ingresos = flujo.reduce((s, m) => s + m.ingresos, 0)
    const egresos = flujo.reduce((s, m) => s + m.egresos, 0)
    return { ingresos, egresos, neto: ingresos - egresos }
  }, [flujo])

  const netoLine = useMemo(
    () => flujo.map(m => ({ label: m.label, value: m.neto })),
    [flujo]
  )

  const barLabels = useMemo(() => flujo.map(m => m.label), [flujo])
  const barSeries = useMemo(() => [
    { label: 'Ingresos', color: '#10b981', data: flujo.map(m => m.ingresos) },
    { label: 'Egresos',  color: '#f43f5e', data: flujo.map(m => m.egresos)  },
  ], [flujo])

  return (
    <div className="max-w-4xl mx-auto px-4 py-6 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between gap-4 flex-wrap">
        <div>
          <h1 className="text-xl font-semibold text-ml-text dark:text-white">Flujo de Caja</h1>
          <p className="text-xs text-ml-text-soft dark:text-zinc-400 mt-0.5">
            Ingresos vs egresos operativos — últimos {meses} meses
          </p>
        </div>
        <div className="flex gap-1">
          {[3, 6, 12].map(n => (
            <button
              key={n}
              onClick={() => setMeses(n)}
              className={`px-3 py-1.5 rounded-lg text-sm font-medium transition-colors ${
                meses === n
                  ? 'bg-violet-600 text-white'
                  : 'bg-gray-100 dark:bg-white/10 text-ml-text-soft dark:text-zinc-400 hover:bg-gray-200 dark:hover:bg-white/15'
              }`}
            >
              {n}m
            </button>
          ))}
        </div>
      </div>

      {error && (
        <div className="text-sm text-red-500 bg-red-50 dark:bg-red-900/20 rounded-lg px-4 py-3">{error}</div>
      )}

      {/* KPI cards */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        {loading ? (
          <>
            <SkeletonKpi />
            <SkeletonKpi />
            <SkeletonKpi />
          </>
        ) : (
          <>
            <KpiCard label="Ingresos" value={fmtMoney(totales.ingresos)} sub={`${meses} meses`} positive={true} />
            <KpiCard label="Egresos"  value={fmtMoney(totales.egresos)}  sub={`${meses} meses`} positive={false} />
            <KpiCard
              label="Neto"
              value={fmtMoney(totales.neto)}
              sub="ingresos − egresos"
              positive={totales.neto >= 0 ? true : false}
            />
          </>
        )}
      </div>

      {/* LineChart — neto mensual */}
      <div className="bg-white dark:bg-white/5 border border-gray-100 dark:border-white/10 rounded-xl p-4">
        <h2 className="text-sm font-medium text-ml-text dark:text-white mb-3">Neto mensual</h2>
        {loading ? (
          <div className="h-[180px] animate-pulse bg-gray-100 dark:bg-white/5 rounded" />
        ) : (
          <LineChart
            data={netoLine}
            color={totales.neto >= 0 ? '#10b981' : '#f43f5e'}
            formatValue={fmtCompact}
          />
        )}
      </div>

      {/* BarChart — ingresos vs egresos */}
      <div className="bg-white dark:bg-white/5 border border-gray-100 dark:border-white/10 rounded-xl p-4">
        <h2 className="text-sm font-medium text-ml-text dark:text-white mb-3">Ingresos vs Egresos</h2>
        {loading ? (
          <div className="h-[200px] animate-pulse bg-gray-100 dark:bg-white/5 rounded" />
        ) : (
          <BarChart labels={barLabels} series={barSeries} formatValue={fmtCompact} />
        )}
      </div>

      {/* Tabla mensual */}
      <div className="bg-white dark:bg-white/5 border border-gray-100 dark:border-white/10 rounded-xl overflow-hidden">
        <div className="px-4 py-3 border-b border-gray-100 dark:border-white/10">
          <h2 className="text-sm font-medium text-ml-text dark:text-white">Detalle mensual</h2>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-xs text-ml-text-soft dark:text-zinc-400 uppercase tracking-wide border-b border-gray-100 dark:border-white/10">
                <th className="px-4 py-2 font-medium">Mes</th>
                <th className="px-4 py-2 font-medium text-right">Ingresos</th>
                <th className="px-4 py-2 font-medium text-right">Egresos</th>
                <th className="px-4 py-2 font-medium text-right">Neto</th>
                <th className="px-4 py-2 font-medium text-right hidden sm:table-cell">Conciliado</th>
                <th className="px-4 py-2 font-medium text-right hidden sm:table-cell">Tasa</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-50 dark:divide-white/5">
              {loading ? (
                Array.from({ length: meses }).map((_, i) => (
                  <tr key={i}>
                    {Array.from({ length: 6 }).map((_, j) => (
                      <td key={j} className="px-4 py-2">
                        <div className="h-3 bg-gray-100 dark:bg-white/10 rounded animate-pulse" />
                      </td>
                    ))}
                  </tr>
                ))
              ) : flujo.length === 0 ? (
                <tr>
                  <td colSpan={6} className="px-4 py-6 text-center text-ml-text-soft dark:text-zinc-500 text-sm">
                    Sin datos para el período seleccionado
                  </td>
                </tr>
              ) : (
                [...flujo].reverse().map((m, i) => {
                  const ev = [...evolucion].reverse()[i]
                  const neto = m.neto
                  return (
                    <tr key={m.label} className="hover:bg-gray-50 dark:hover:bg-white/5 transition-colors">
                      <td className="px-4 py-2.5 font-medium text-ml-text dark:text-white">{m.label}</td>
                      <td className="px-4 py-2.5 text-right text-emerald-600 dark:text-emerald-400 tabular-nums">
                        {fmtMoney(m.ingresos)}
                      </td>
                      <td className="px-4 py-2.5 text-right text-red-500 dark:text-red-400 tabular-nums">
                        {fmtMoney(m.egresos)}
                      </td>
                      <td className={`px-4 py-2.5 text-right font-medium tabular-nums ${
                        neto >= 0 ? 'text-emerald-600 dark:text-emerald-400' : 'text-red-500 dark:text-red-400'
                      }`}>
                        {fmtMoney(neto)}
                      </td>
                      <td className="px-4 py-2.5 text-right text-ml-text dark:text-zinc-300 tabular-nums hidden sm:table-cell">
                        {ev ? fmtMoney(ev.conciliado) : '—'}
                      </td>
                      <td className="px-4 py-2.5 text-right tabular-nums hidden sm:table-cell">
                        {ev ? (
                          <span className={`text-xs font-medium px-1.5 py-0.5 rounded ${
                            ev.tasa_pct >= 80 ? 'bg-emerald-100 dark:bg-emerald-900/40 text-emerald-700 dark:text-emerald-400' :
                            ev.tasa_pct >= 50 ? 'bg-amber-100 dark:bg-amber-900/40 text-amber-700 dark:text-amber-400' :
                            'bg-red-100 dark:bg-red-900/40 text-red-700 dark:text-red-400'
                          }`}>
                            {ev.tasa_pct.toFixed(0)}%
                          </span>
                        ) : '—'}
                      </td>
                    </tr>
                  )
                })
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}
