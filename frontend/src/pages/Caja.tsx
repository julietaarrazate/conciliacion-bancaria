import React, { useEffect, useState, useRef, useCallback } from 'react'
import { apiClient } from '@/services/api'
import { useOrgStore } from '@/store/org'

const DENOMINACIONES = [20000, 10000, 2000, 1000, 500, 200, 100]

const fmt = (n: number) =>
  new Intl.NumberFormat('es-AR', { style: 'currency', currency: 'ARS', minimumFractionDigits: 0 }).format(n)

const toISO = (d: Date) => d.toISOString().slice(0, 10)
const today = () => toISO(new Date())

const fmtDayLabel = (iso: string) => {
  const d = new Date(iso + 'T12:00:00')
  return d.toLocaleDateString('es-AR', { weekday: 'long', day: 'numeric', month: 'long', year: 'numeric' })
}

const fmtDayLabelShort = (iso: string) => {
  const d = new Date(iso + 'T12:00:00')
  return d.toLocaleDateString('es-AR', { weekday: 'short', day: 'numeric', month: 'short', year: '2-digit' })
}

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

interface ArqueoResumen {
  id: number
  fecha: string
  caja_restante: number
  cruce: number
  cerrado: boolean
}

export const Caja: React.FC = () => {
  const { activeOrgId } = useOrgStore()
  const [selectedDate, setSelectedDate] = useState(today())
  const [arqueo, setArqueo]             = useState<Arqueo | null>(null)
  const [loading, setLoading]           = useState(true)
  const [saving, setSaving]             = useState(false)
  const [exportando, setExportando]     = useState(false)
  const [msg, setMsg]                   = useState('')
  const [dens, setDens]                 = useState<Record<string, string>>({})
  const [editando, setEditando]         = useState<'saldo_inicial' | 'pesos_agregados' | 'ingresos' | null>(null)
  const [tempVal, setTempVal]           = useState('')

  // Historial panel
  const [showHistorial, setShowHistorial]   = useState(false)
  const [historial, setHistorial]           = useState<ArqueoResumen[]>([])
  const [loadingHist, setLoadingHist]       = useState(false)

  // EFT export filters
  const [filtroDesde, setFiltroDesde] = useState('')
  const [filtroHasta, setFiltroHasta] = useState('')

  const load = useCallback(async (fecha?: string) => {
    setLoading(true)
    try {
      const f = fecha || selectedDate
      const params: Record<string, string | number> = { fecha_str: f }
      if (activeOrgId) params.org_id = activeOrgId
      const res = await apiClient.client.get('/caja/arqueo/hoy', { params })
      setArqueo(res.data)
      setDens(Object.fromEntries(
        Object.entries(res.data.denominaciones).map(([k, v]) => [k, String(v)])
      ))
    } catch { setArqueo(null) }
    finally { setLoading(false) }
  }, [selectedDate, activeOrgId])

  useEffect(() => { load() }, [load])

  const loadHistorial = async () => {
    setLoadingHist(true)
    try {
      const params: Record<string, string | number> = { limit: 60 }
      if (activeOrgId) params.org_id = activeOrgId
      const res = await apiClient.client.get('/caja/arqueo/historial', { params })
      setHistorial(res.data.items || res.data)
    } catch { }
    finally { setLoadingHist(false) }
  }

  const goToDate = (iso: string) => {
    setSelectedDate(iso)
    setShowHistorial(false)
  }

  const prevDay = () => {
    const d = new Date(selectedDate + 'T12:00:00')
    d.setDate(d.getDate() - 1)
    setSelectedDate(toISO(d))
  }

  const nextDay = () => {
    const d = new Date(selectedDate + 'T12:00:00')
    d.setDate(d.getDate() + 1)
    const next = toISO(d)
    if (next <= today()) setSelectedDate(next)
  }

  const saveDens = async () => {
    setSaving(true)
    try {
      const parsed = Object.fromEntries(
        Object.entries(dens).map(([k, v]) => [k, parseInt(v) || 0])
      )
      const res = await apiClient.client.put('/caja/arqueo/hoy', { denominaciones: parsed, fecha: selectedDate })
      setArqueo(res.data)
      setMsg('✓ Arqueo actualizado')
      setTimeout(() => setMsg(''), 3000)
    } catch { setMsg('Error al guardar') }
    finally { setSaving(false) }
  }

  const saveField = async (field: string, value: number) => {
    try {
      const res = await apiClient.client.put('/caja/arqueo/hoy', { [field]: value, fecha: selectedDate })
      setArqueo(res.data)
    } catch { }
    setEditando(null)
  }

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

  const totalFisico   = DENOMINACIONES.reduce((s, d) => s + d * (parseInt(dens[String(d)]) || 0), 0)
  const cajaRestante  = (arqueo?.saldo_inicial || 0) + (arqueo?.pesos_agregados || 0) + (arqueo?.ingresos || 0) - (arqueo?.pagos_dia || 0)
  const cruce         = totalFisico - cajaRestante
  const cruceCorrecto = Math.abs(cruce) < 1
  const isToday       = selectedDate === today()

  return (
    <div className="p-4 md:p-6 max-w-2xl mx-auto space-y-4">

      {/* Header con navegación de fechas — dos filas */}
      <div className="space-y-2">
        {/* Fila 1: flechas + fecha */}
        <div className="flex items-center gap-2">
          <button onClick={prevDay}
            className="p-1.5 rounded-lg bg-gray-100 dark:bg-white/5 hover:bg-gray-200 dark:hover:bg-white/10 text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-200 transition-colors text-sm shrink-0">
            ←
          </button>
          <div className="flex-1 min-w-0">
            <h1 className="font-bold dark:text-white capitalize leading-tight text-sm sm:hidden">
              {fmtDayLabelShort(selectedDate)}
            </h1>
            <h1 className="font-bold dark:text-white capitalize leading-tight text-base hidden sm:block">
              {fmtDayLabel(selectedDate)}
            </h1>
            {!isToday && (
              <button onClick={() => setSelectedDate(today())}
                className="text-xs text-indigo-400 hover:text-indigo-300">
                Ir a hoy →
              </button>
            )}
          </div>
          <button onClick={nextDay} disabled={isToday}
            className="p-1.5 rounded-lg bg-gray-100 dark:bg-white/5 hover:bg-gray-200 dark:hover:bg-white/10 text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-200 transition-colors text-sm disabled:opacity-30 shrink-0">
            →
          </button>
        </div>
        {/* Fila 2: controles */}
        <div className="flex items-center gap-2 flex-wrap">
          <input type="date" value={selectedDate} max={today()}
            onChange={e => e.target.value && setSelectedDate(e.target.value)}
            className="bg-white dark:bg-white/5 border border-gray-200 dark:border-white/10 rounded-lg px-2 py-1 text-xs text-gray-600 dark:text-gray-300 focus:outline-none" />
          <button onClick={() => { setShowHistorial(v => !v); if (!showHistorial) loadHistorial() }}
            className="px-3 py-1.5 bg-gray-100 dark:bg-white/5 hover:bg-gray-200 dark:hover:bg-white/10 text-gray-600 dark:text-gray-300 text-xs rounded-lg transition-colors">
            {showHistorial ? 'Ocultar' : 'Historial'}
          </button>
          <button onClick={() => load()} className="px-2.5 py-1.5 bg-gray-100 dark:bg-white/5 hover:bg-gray-200 dark:hover:bg-white/10 text-gray-600 dark:text-gray-300 text-xs rounded-lg">
            ↺
          </button>
        </div>
      </div>

      {/* Historial panel */}
      {showHistorial && (
        <div className="bg-white/3 border border-white/8 rounded-xl overflow-hidden">
          <div className="px-4 py-2 border-b border-white/8 text-xs text-gray-400 font-medium">Historial de arqueos</div>
          {loadingHist ? (
            <div className="text-center py-4 text-gray-500 text-xs">Cargando…</div>
          ) : historial.length === 0 ? (
            <div className="text-center py-4 text-gray-500 text-xs">Sin historial</div>
          ) : (
            <div className="divide-y divide-white/5 max-h-64 overflow-y-auto">
              {historial.map(h => (
                <button key={h.id} onClick={() => goToDate(h.fecha)}
                  className={`w-full flex items-center justify-between px-4 py-2 text-xs hover:bg-white/5 transition-colors ${h.fecha === selectedDate ? 'bg-indigo-500/10' : ''}`}>
                  <span className="text-gray-300">{fmtDayLabel(h.fecha)}</span>
                  <div className="flex items-center gap-3 shrink-0">
                    <span className="font-mono text-gray-200">{fmt(h.caja_restante)}</span>
                    <span className={`w-2 h-2 rounded-full ${Math.abs(h.cruce) < 1 ? 'bg-green-500' : 'bg-red-500'}`} title={Math.abs(h.cruce) < 1 ? 'Cuadra' : 'Revisar'} />
                  </div>
                </button>
              ))}
            </div>
          )}
        </div>
      )}

      {msg && (
        <div className={`px-3 py-2 rounded-lg text-sm ${msg.startsWith('✓') ? 'bg-green-50 text-green-700 dark:bg-green-900/20 dark:text-green-400' : 'bg-red-50 text-red-600'}`}>
          {msg}
        </div>
      )}

      {loading ? (
        <div className="py-8 text-center text-gray-400">Cargando arqueo...</div>
      ) : (
        <>
          {/* Resumen */}
          <div className="card space-y-3">
            {(['saldo_inicial', 'pesos_agregados', 'ingresos'] as const).map(field => {
              const labels: Record<string, string> = {
                saldo_inicial:   'Saldo inicial (del día anterior)',
                pesos_agregados: 'Pesos agregados (te dieron más)',
                ingresos:        'Ingresos (clientes que trajeron plata)',
              }
              const val = arqueo?.[field] || 0
              return (
                <div key={field} className="flex items-center justify-between gap-3">
                  <span className="text-sm text-gray-500 dark:text-zinc-400 flex-1">{labels[field]}</span>
                  {editando === field ? (
                    <div className="flex items-center gap-2">
                      <input type="number"
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
                    <button onClick={() => { setEditando(field); setTempVal(String(val)) }}
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

          {/* Arqueo físico */}
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
                    <input type="number" min="0"
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
                  OPs pagadas ({arqueo.ordenes.length})
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

          {/* Exportar EFT */}
          <div className="card space-y-3">
            <p className="font-semibold text-sm dark:text-white">Exportar historial EFT</p>
            <div className="flex flex-wrap gap-2">
              <input type="date" value={filtroDesde} onChange={e => setFiltroDesde(e.target.value)}
                className="bg-white/5 border border-white/10 rounded px-2 py-1 text-xs text-gray-300 focus:outline-none" />
              <input type="date" value={filtroHasta} onChange={e => setFiltroHasta(e.target.value)}
                className="bg-white/5 border border-white/10 rounded px-2 py-1 text-xs text-gray-300 focus:outline-none" />
              <button onClick={exportarEFT} disabled={exportando}
                className="btn-ghost text-sm">
                {exportando ? 'Exportando...' : '↓ Exportar EFT'}
              </button>
            </div>
          </div>
        </>
      )}
    </div>
  )
}
