import React, { useEffect, useState } from 'react'
import { apiClient } from '@/services/api'

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
  created_at: string
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

function fmtDate(s: string) {
  try {
    return new Date(s.endsWith('Z') ? s : s + 'Z').toLocaleDateString('es-AR', { day: '2-digit', month: '2-digit', year: 'numeric' })
  } catch { return s }
}

const MODULO_LABEL: Record<string, string> = {
  extracto: '🏦 Extracto',
  planilla: '📋 Planilla',
  caja:     '💵 Caja',
  cheque:   '🗒️ Cheque',
}

export const Contabilidad: React.FC = () => {
  const [cuentas, setCuentas]   = useState<CuentaItem[]>([])
  const [reglas, setReglas]     = useState<ReglaItem[]>([])
  const [asientos, setAsientos] = useState<AsientoItem[]>([])
  const [totalAsientos, setTotalAsientos] = useState(0)
  const [loading, setLoading]   = useState(true)
  const [tab, setTab]           = useState<'plan' | 'reglas' | 'diario'>('plan')

  useEffect(() => {
    Promise.all([
      apiClient.client.get('/contabilidad/plan-cuentas').then(r => r.data),
      apiClient.client.get('/contabilidad/reglas').then(r => r.data),
      apiClient.client.get('/contabilidad/asientos?limit=100').then(r => r.data),
    ]).then(([c, r, a]) => {
      setCuentas(c)
      setReglas(r)
      setAsientos(a.items)
      setTotalAsientos(a.total)
      setLoading(false)
    }).catch(() => setLoading(false))
  }, [])

  const raices  = cuentas.filter(c => c.nivel === 1)
  const hijos   = (pid: number) => cuentas.filter(c => c.parent_id === pid)

  const renderCuenta = (c: CuentaItem, depth = 0): React.ReactNode => {
    const children = hijos(c.id)
    const textClass = depth === 0 ? 'font-bold' : depth === 1 ? 'font-semibold' : 'font-normal'
    const colorClass = c.tipo ? (TIPO_TEXT[c.tipo] || 'text-ml-text dark:text-gray-200') : 'text-ml-text dark:text-gray-200'

    return (
      <React.Fragment key={c.id}>
        <div
          className="flex items-center gap-2 py-1 px-2 hover:bg-gray-50 dark:hover:bg-slate-800/50 transition-colors"
          style={{ paddingLeft: `${8 + depth * 20}px` }}
        >
          <span className="text-[11px] font-mono text-gray-400 w-16 shrink-0">{c.codigo}</span>
          <span className={`text-xs ${textClass} ${colorClass}`}>{c.nombre}</span>
          {c.tipo && depth === 0 && (
            <span className={`text-[10px] px-1.5 py-0.5 rounded-full border ${TIPO_BADGE[c.tipo] || ''}`}>
              {c.tipo}
            </span>
          )}
        </div>
        {children.map(ch => renderCuenta(ch, depth + 1))}
      </React.Fragment>
    )
  }

  return (
    <div className="p-4 md:p-6 max-w-4xl mx-auto">
      <div className="mb-6">
        <h1 className="text-xl font-bold text-ml-text dark:text-white">Contabilidad</h1>
        <p className="text-xs text-gray-500 dark:text-gray-400 mt-0.5">
          Plan de cuentas · Reglas contables · Asientos automáticos (próximamente)
        </p>
      </div>

      <div className="flex gap-2 mb-4 flex-wrap">
        {([
          ['plan',   '📊 Plan de cuentas'],
          ['reglas', '⚙️ Reglas contables'],
          ['diario', `📒 Libro diario${totalAsientos > 0 ? ` (${totalAsientos})` : ''}`],
        ] as const).map(([t, label]) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={`px-4 py-1.5 rounded-lg text-sm font-medium transition-colors ${
              tab === t
                ? 'bg-ml-blue text-white'
                : 'bg-gray-100 dark:bg-slate-800 text-gray-600 dark:text-gray-400 hover:bg-gray-200 dark:hover:bg-slate-700'
            }`}
          >
            {label}
          </button>
        ))}
      </div>

      {loading ? (
        <div className="py-16 text-center text-gray-400">Cargando...</div>
      ) : tab === 'diario' ? (
        <div className="border border-gray-200 dark:border-slate-700 rounded-xl overflow-hidden">
          {asientos.length === 0 ? (
            <div className="py-16 text-center text-gray-400">
              <p className="text-3xl mb-2">📒</p>
              <p className="text-sm">Sin asientos todavía.</p>
              <p className="text-xs mt-1">Se generarán automáticamente al subir extractos y conciliar planillas.</p>
            </div>
          ) : (
            <table className="w-full text-xs">
              <thead className="bg-gray-50 dark:bg-slate-800">
                <tr>
                  <th className="text-left px-4 py-2 font-medium text-gray-600 dark:text-gray-400 w-8">#</th>
                  <th className="text-left px-4 py-2 font-medium text-gray-600 dark:text-gray-400">Fecha</th>
                  <th className="text-left px-4 py-2 font-medium text-gray-600 dark:text-gray-400">Módulo</th>
                  <th className="text-left px-4 py-2 font-medium text-gray-600 dark:text-gray-400">Descripción</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100 dark:divide-slate-700/50">
                {asientos.map(a => (
                  <tr key={a.id} className="hover:bg-gray-50 dark:hover:bg-slate-800/40">
                    <td className="px-4 py-2 text-gray-400 font-mono">{a.id}</td>
                    <td className="px-4 py-2 text-gray-700 dark:text-gray-300 whitespace-nowrap">{fmtDate(a.fecha)}</td>
                    <td className="px-4 py-2">
                      <span className="text-[10px] px-1.5 py-0.5 rounded bg-gray-100 dark:bg-slate-700 text-gray-600 dark:text-gray-400">
                        {(a.modulo && MODULO_LABEL[a.modulo]) || a.modulo || '—'}
                      </span>
                    </td>
                    <td className="px-4 py-2 text-gray-700 dark:text-gray-300">{a.descripcion || '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      ) : tab === 'plan' ? (
        <div className="border border-gray-200 dark:border-slate-700 rounded-xl overflow-hidden bg-white dark:bg-slate-900/50">
          {raices.length === 0 ? (
            <p className="text-center py-8 text-gray-400 text-sm">Sin datos</p>
          ) : (
            <div className="divide-y divide-gray-100 dark:divide-slate-800">
              {raices.map(r => renderCuenta(r, 0))}
            </div>
          )}
        </div>
      ) : (
        <div className="border border-gray-200 dark:border-slate-700 rounded-xl overflow-hidden">
          {reglas.length === 0 ? (
            <p className="text-center py-8 text-gray-400 text-sm">Sin reglas configuradas</p>
          ) : (
            <table className="w-full text-xs">
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
                      {r.descripcion && (
                        <p className="text-gray-400 dark:text-gray-500 mt-0.5">{r.descripcion}</p>
                      )}
                    </td>
                    <td className="px-4 py-2 text-blue-700 dark:text-blue-300">
                      <span className="font-mono text-[10px] text-gray-400 mr-1">{r.debe.codigo}</span>
                      {r.debe.nombre}
                    </td>
                    <td className="px-4 py-2 text-orange-700 dark:text-orange-300">
                      <span className="font-mono text-[10px] text-gray-400 mr-1">{r.haber.codigo}</span>
                      {r.haber.nombre}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      )}
    </div>
  )
}
