import React, { useEffect, useState, useRef } from 'react'
import { apiClient } from '@/services/api'

const DENOMINACIONES = [20000, 10000, 2000, 1000, 500, 200, 100]

const fmt = (n: number) =>
  new Intl.NumberFormat('es-AR', { style: 'currency', currency: 'ARS', minimumFractionDigits: 0 }).format(n)

interface Arqueo {
  id: number
  fecha: string
  saldo_inicial: number
  pesos_agregados: number
  ingresos: number
  pagos_dia: number
  caja_restante: number
  total_arqueo_fisico: number
  cruce: number
  denominaciones: Record<string, number>
  cerrado: boolean
  notas?: string
  ordenes: OpResumen[]
}

interface OpResumen {
  id: number
  beneficiario: string
  cliente_nombre: string
  importe: number
  compartido_whatsapp: boolean
  tiene_foto: boolean
  created_at: string
}

export const Caja: React.FC = () => {
  const [arqueo, setArqueo] = useState<Arqueo | null>(null)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [exportando, setExportando] = useState(false)
  const [filtroDesde, setFiltroDesde] = useState('')
  const [filtroHasta, setFiltroHasta] = useState('')

  const exportarEFT = async () => {
    setExportando(true)
    try {
      const params = new URLSearchParams()
      if (filtroDesde) params.set('desde', filtroDesde)
      if (filtroHasta) params.set('hasta', filtroHasta)
      const res = await apiClient.client.get(`/caja/op/exportar-eft?${params}`, { responseType: 'blob' })
      const url = URL.createObjectURL(res.data)
      const a = document.createElement('a')
      a.href = url; a.download = `pago_eft.xlsx`; a.click()
      URL.revokeObjectURL(url)
    } catch { setMsg('Error al exportar') }
    finally { setExportando(false) }
  }
  const [msg, setMsg] = useState('')
  const [dens, setDens] = useState<Record<string, string>>({})
  const [editando, setEditando] = useState<'saldo' | 'agregados' | 'ingresos' | null>(null)
  const [tempVal, setTempVal] = useState('')

  const load = async () => {
    setLoading(true)
    try {
      const res = await apiClient.client.get('/caja/arqueo/hoy')
      setArqueo(res.data)
      setDens(Object.fromEntries(
        Object.entries(res.data.denominaciones).map(([k, v]) => [k, String(v)])
      ))
    } catch { setArqueo(null) }
    finally { setLoading(false) }
  }

  useEffect(() => { load() }, [])

  const saveDens = async () => {
    setSaving(true)
    try {
      const parsed = Object.fromEntries(
        Object.entries(dens).map(([k, v]) => [k, parseInt(v) || 0])
      )
      const res = await apiClient.client.put('/caja/arqueo/hoy', { denominaciones: parsed })
      setArqueo(res.data)
      setMsg('✓ Arqueo actualizado')
      setTimeout(() => setMsg(''), 3000)
    } catch { setMsg('Error al guardar') }
    finally { setSaving(false) }
  }

  const saveField = async (field: string, value: number) => {
    try {
      const res = await apiClient.client.put('/caja/arqueo/hoy', { [field]: value })
      setArqueo(res.data)
    } catch { }
    setEditando(null)
  }

  if (loading) return <div className="p-8 text-center text-gray-400">Cargando arqueo...</div>

  const totalFisico = DENOMINACIONES.reduce((s, d) => s + d * (parseInt(dens[String(d)]) || 0), 0)
  const cajaRestante = (arqueo?.saldo_inicial || 0) + (arqueo?.pesos_agregados || 0) + (arqueo?.ingresos || 0) - (arqueo?.pagos_dia || 0)
  const cruce = totalFisico - cajaRestante
  const cruceCorrecto = Math.abs(cruce) < 1

  return (
    <div className="p-4 md:p-6 max-w-2xl mx-auto space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold dark:text-white">Caja del día</h1>
          <p className="text-sm text-gray-400 dark:text-zinc-500">
            {new Date().toLocaleDateString('es-AR', { weekday: 'long', day: 'numeric', month: 'long' })}
          </p>
        </div>
        <button onClick={load} className="btn-ghost text-sm">Actualizar</button>
      </div>

      {msg && (
        <div className={`px-3 py-2 rounded-lg text-sm ${msg.startsWith('✓') ? 'bg-green-50 text-green-700 dark:bg-green-900/20 dark:text-green-400' : 'bg-red-50 text-red-600'}`}>
          {msg}
        </div>
      )}

      {/* Resumen */}
      <div className="card space-y-3">
        {/* Saldo inicial */}
        {(['saldo_inicial', 'pesos_agregados', 'ingresos'] as const).map(field => {
          const labels: Record<string, string> = {
            saldo_inicial: 'Saldo inicial (del día anterior)',
            pesos_agregados: 'Pesos agregados (te dieron más)',
            ingresos: 'Ingresos (clientes que trajeron plata)'
          }
          const val = arqueo?.[field] || 0
          return (
            <div key={field} className="flex items-center justify-between gap-3">
              <span className="text-sm text-gray-500 dark:text-zinc-400 flex-1">{labels[field]}</span>
              {editando === field ? (
                <div className="flex items-center gap-2">
                  <input
                    type="number"
                    className="input-field !w-36 text-right font-mono"
                    value={tempVal}
                    onChange={e => setTempVal(e.target.value)}
                    autoFocus
                    onKeyDown={e => e.key === 'Enter' && saveField(field, parseFloat(tempVal) || 0)}
                  />
                  <button onClick={() => saveField(field, parseFloat(tempVal) || 0)} className="btn-primary text-xs py-1">✓</button>
                  <button onClick={() => setEditando(null)} className="btn-ghost text-xs py-1">✕</button>
                </div>
              ) : (
                <button onClick={() => { setEditando(field as any); setTempVal(String(val)) }}
                  className="font-mono font-semibold dark:text-white hover:text-ml-blue dark:hover:text-ml-green transition-colors">
                  {fmt(val)} ✏
                </button>
              )}
            </div>
          )
        })}

        <div className="border-t border-ml-gray dark:border-ml-dark-border pt-3 space-y-1.5">
          <div className="flex justify-between text-sm">
            <span className="text-gray-500 dark:text-zinc-400">Pagos del día (OPs)</span>
            <span className="font-mono font-semibold text-red-500">- {fmt(arqueo?.pagos_dia || 0)}</span>
          </div>
          <div className="flex justify-between">
            <span className="font-semibold dark:text-white">Caja restante</span>
            <span className="font-mono font-bold text-lg dark:text-white">{fmt(cajaRestante)}</span>
          </div>
        </div>
      </div>

      {/* Arqueo físico por denominación */}
      <div className="card">
        <h2 className="font-semibold dark:text-white mb-3">Arqueo físico — billetes en caja</h2>
        <div className="space-y-2">
          {DENOMINACIONES.map(d => {
            const cant = parseInt(dens[String(d)]) || 0
            const subtotal = d * cant
            return (
              <div key={d} className="flex items-center gap-3">
                <span className="text-sm font-mono text-gray-500 dark:text-zinc-400 w-20 text-right">
                  ${d.toLocaleString('es-AR')}
                </span>
                <span className="text-gray-400 dark:text-zinc-600 text-sm">×</span>
                <input
                  type="number"
                  min="0"
                  className="input-field !w-24 text-center font-mono"
                  value={dens[String(d)] || ''}
                  placeholder="0"
                  onChange={e => setDens(prev => ({ ...prev, [String(d)]: e.target.value }))}
                />
                <span className="text-sm font-mono text-gray-500 dark:text-zinc-400 flex-1 text-right">
                  {subtotal > 0 ? fmt(subtotal) : '—'}
                </span>
              </div>
            )
          })}
        </div>

        <div className="border-t border-ml-gray dark:border-ml-dark-border mt-3 pt-3">
          <div className="flex justify-between items-center">
            <span className="font-semibold dark:text-white">Total físico</span>
            <span className="font-mono font-bold text-lg dark:text-white">{fmt(totalFisico)}</span>
          </div>
        </div>

        <button onClick={saveDens} disabled={saving} className="btn-yellow w-full mt-3">
          {saving ? 'Guardando...' : 'Guardar arqueo'}
        </button>
      </div>

      {/* Cruce */}
      <div className={`card border-2 ${cruceCorrecto ? 'border-green-400 dark:border-green-600' : 'border-red-400 dark:border-red-600'}`}>
        <div className="flex items-center justify-between">
          <div>
            <p className="font-bold dark:text-white">Cruce</p>
            <p className="text-xs text-gray-400 dark:text-zinc-500">Físico − Caja restante</p>
          </div>
          <div className="text-right">
            <p className={`text-2xl font-bold font-mono ${cruceCorrecto ? 'text-green-500' : 'text-red-500'}`}>
              {cruce >= 0 ? '+' : ''}{fmt(cruce)}
            </p>
            <p className={`text-xs font-semibold ${cruceCorrecto ? 'text-green-500' : 'text-red-500'}`}>
              {cruceCorrecto ? '✓ Cuadra' : '✗ Revisar'}
            </p>
          </div>
        </div>
      </div>

      {/* OPs del día */}
      {arqueo?.ordenes && arqueo.ordenes.length > 0 && (
        <div className="card p-0 overflow-hidden">
          <div className="px-4 py-3 border-b border-ml-gray dark:border-ml-dark-border">
            <p className="font-semibold text-sm dark:text-white">
              OPs pagadas hoy ({arqueo.ordenes.length})
            </p>
          </div>
          <div className="divide-y divide-ml-gray dark:divide-ml-dark-border">
            {arqueo.ordenes.map(op => (
              <div key={op.id} className="flex items-center gap-3 px-4 py-3">
                <div className="flex-1 min-w-0">
                  <p className="font-medium text-sm dark:text-white truncate">{op.beneficiario}</p>
                  <p className="text-xs text-gray-400 dark:text-zinc-500">{op.cliente_nombre}</p>
                </div>
                <div className="text-right shrink-0">
                  <p className="font-mono font-semibold text-sm dark:text-white">{fmt(op.importe)}</p>
                  <div className="flex gap-1 justify-end mt-0.5">
                    {op.tiene_foto && <span className="badge badge-ok text-2xs">📷</span>}
                    {op.compartido_whatsapp && <span className="badge badge-info text-2xs">WA</span>}
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
