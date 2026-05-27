import React, { useEffect, useState } from 'react'
import { apiClient } from '@/services/api'
import { useAuthStore } from '@/store/auth'
import { useOrgStore } from '@/store/org'
import { confirmDialog } from '@/store/confirm'

interface Detalle {
  id: number
  cliente_nombre: string
  monto_conciliado: number
  porcentaje_comision: number
  monto_comision: number
  monto_neto: number
  observaciones?: string
}

interface Liq {
  id: number
  periodo_inicio: string
  periodo_fin: string
  estado: 'borrador' | 'aprobada' | 'pagada'
  total_conciliado: number
  total_comision: number
  total_neto: number
  notas?: string
  creador?: string
  aprobador?: string
  aprobado_at?: string
  created_at: string
  detalles?: Detalle[]
}

const fmt = (n: number) =>
  new Intl.NumberFormat('es-AR', { style: 'currency', currency: 'ARS', minimumFractionDigits: 0 }).format(n)

const estadoBadge = (e: string) => {
  if (e === 'borrador') return 'badge-warn'
  if (e === 'aprobada') return 'badge-ok'
  if (e === 'pagada')   return 'badge-info'
  return 'badge-neutral'
}

export const Liquidaciones: React.FC = () => {
  const { user } = useAuthStore()
  const { activeOrgId } = useOrgStore()
  const [items, setItems] = useState<Liq[]>([])
  const [loading, setLoading] = useState(true)
  const [selected, setSelected] = useState<Liq | null>(null)
  const [showGenerar, setShowGenerar] = useState(false)
  const [showCerrar, setShowCerrar] = useState(false)
  const [saving, setSaving] = useState(false)
  const [msg, setMsg] = useState('')
  const [form, setForm] = useState({
    periodo_inicio: '',
    periodo_fin: '',
    notas: '',
    porcentaje_comision: '' as string,
  })

  const isAdmin = user?.is_superadmin || user?.role === 'admin'

  const load = async () => {
    setLoading(true)
    try {
      const params = activeOrgId ? `?org_id=${activeOrgId}` : ''
      const res = await apiClient.client.get(`/liquidaciones${params}`)
      setItems(res.data)
    } catch { setItems([]) }
    finally { setLoading(false) }
  }

  const loadDetalle = async (id: number) => {
    const res = await apiClient.client.get(`/liquidaciones/${id}`)
    setSelected(res.data)
  }

  useEffect(() => { load() }, [activeOrgId])

  const handleGenerar = async () => {
    if (!form.periodo_inicio || !form.periodo_fin) {
      setMsg('Completá las fechas del período')
      return
    }
    setSaving(true)
    setMsg('')
    try {
      const payload: Record<string, any> = {
        periodo_inicio: form.periodo_inicio,
        periodo_fin: form.periodo_fin,
        notas: form.notas,
      }
      if (form.porcentaje_comision !== '') {
        const pct = parseFloat(form.porcentaje_comision)
        if (!isNaN(pct) && pct > 0) payload.porcentaje_comision = pct
      }
      await apiClient.client.post('/liquidaciones/generar', payload)
      setMsg('✓ Liquidación generada en estado borrador')
      setShowGenerar(false)
      load()
    } catch (err: any) {
      setMsg(err.response?.data?.detail || 'Error al generar')
    } finally { setSaving(false) }
  }

  const handleAprobar = async (id: number) => {
    if (!await confirmDialog({ title: 'Aprobar liquidación', message: '¿Aprobar esta liquidación?', confirmLabel: 'Aprobar' })) return
    try {
      await apiClient.client.post(`/liquidaciones/${id}/aprobar`)
      setMsg('✓ Liquidación aprobada')
      load()
      if (selected?.id === id) loadDetalle(id)
    } catch (err: any) {
      setMsg(err.response?.data?.detail || 'Error')
    }
  }

  const handlePagada = async (id: number) => {
    if (!await confirmDialog({ title: 'Marcar como pagada', message: '¿Marcar esta liquidación como pagada?', confirmLabel: 'Marcar pagada' })) return
    try {
      await apiClient.client.post(`/liquidaciones/${id}/marcar-pagada`)
      setMsg('✓ Marcada como pagada')
      load()
      if (selected?.id === id) loadDetalle(id)
    } catch (err: any) {
      setMsg(err.response?.data?.detail || 'Error')
    }
  }

  const handleExportar = async (id: number) => {
    const res = await apiClient.client.get(`/liquidaciones/${id}/exportar`, { responseType: 'blob' })
    const url = URL.createObjectURL(res.data)
    const a = document.createElement('a')
    a.href = url; a.download = `liquidacion_${id}.xlsx`; a.click()
    URL.revokeObjectURL(url)
  }

  const handleCerrarPeriodo = async () => {
    if (!form.periodo_inicio || !form.periodo_fin) {
      setMsg('Completá las fechas del período')
      return
    }
    const confirmacion = window.prompt(
      `¿Cerrar el período ${form.periodo_inicio} → ${form.periodo_fin}?\n\nEscribí CERRAR para confirmar:`
    )
    if (confirmacion !== 'CERRAR') return
    setSaving(true)
    try {
      const res = await apiClient.client.post('/liquidaciones/periodos/cerrar', {
        periodo_inicio: form.periodo_inicio,
        periodo_fin: form.periodo_fin
      })
      setMsg(`✓ ${res.data.mensaje}`)
      setShowCerrar(false)
      load()
    } catch (err: any) {
      setMsg(err.response?.data?.detail || 'Error al cerrar período')
    } finally { setSaving(false) }
  }

  return (
    <div className="flex h-full">
      {/* ── Lista ──────────────────────────────── */}
      <div className={`${selected ? 'hidden md:flex' : 'flex'} flex-col flex-1 p-4 md:p-6 overflow-y-auto`}>
        <div className="flex items-start justify-between mb-5 flex-wrap gap-3">
          <div>
            <h1 className="text-xl font-bold dark:text-white">Liquidaciones</h1>
            <p className="text-sm text-gray-400 dark:text-zinc-500 mt-0.5">
              Cierre de período y comisiones por cliente
            </p>
          </div>
          {isAdmin && (
            <div className="flex gap-2">
              <button onClick={() => { setShowCerrar(true); setShowGenerar(false) }}
                className="btn-secondary text-sm">
                🔒 Cerrar período
              </button>
              <button onClick={() => { setShowGenerar(true); setShowCerrar(false) }}
                className="btn-yellow text-sm">
                + Generar liquidación
              </button>
            </div>
          )}
        </div>

        {msg && (
          <div className={`mb-4 px-3 py-2 rounded-lg text-sm ${msg.startsWith('✓') ? 'bg-green-50 text-green-700 dark:bg-green-900/20 dark:text-green-400' : 'bg-red-50 text-red-600 dark:bg-red-900/20 dark:text-red-400'}`}>
            {msg}
          </div>
        )}

        {/* Form generar */}
        {showGenerar && (
          <div className="card mb-4 border-l-4 border-ml-blue dark:border-ml-green">
            <h2 className="font-semibold dark:text-white mb-3">Nueva liquidación</h2>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              <div>
                <label className="label">Inicio del período</label>
                <input type="date" className="input-field"
                  value={form.periodo_inicio} onChange={e => setForm(p => ({ ...p, periodo_inicio: e.target.value }))} />
              </div>
              <div>
                <label className="label">Fin del período</label>
                <input type="date" className="input-field"
                  value={form.periodo_fin} onChange={e => setForm(p => ({ ...p, periodo_fin: e.target.value }))} />
              </div>
              <div className="md:col-span-2">
                <label className="label">Notas (opcional)</label>
                <input className="input-field" placeholder="Observaciones..."
                  value={form.notas} onChange={e => setForm(p => ({ ...p, notas: e.target.value }))} />
              </div>
              <div className="md:col-span-2">
                <label className="label">Comisión (% — dejar vacío usa config de la org)</label>
                <div className="flex gap-2 flex-wrap items-center">
                  {['1.5', '1.8', '2'].map(pct => (
                    <button key={pct} type="button"
                      onClick={() => setForm(p => ({ ...p, porcentaje_comision: p.porcentaje_comision === pct ? '' : pct }))}
                      className={`px-3 py-1.5 rounded-md text-sm font-medium border transition-colors ${
                        form.porcentaje_comision === pct
                          ? 'bg-ml-blue text-white border-ml-blue dark:bg-ml-green dark:border-ml-green'
                          : 'bg-white dark:bg-zinc-800 text-gray-700 dark:text-zinc-300 border-gray-200 dark:border-zinc-700 hover:border-ml-blue dark:hover:border-ml-green'
                      }`}>
                      {pct}%
                    </button>
                  ))}
                  <input
                    type="number" step="0.1" min="0" max="100"
                    placeholder="Otro %"
                    className="input-field w-28"
                    value={form.porcentaje_comision}
                    onChange={e => setForm(p => ({ ...p, porcentaje_comision: e.target.value }))}
                  />
                  {form.porcentaje_comision !== '' && (
                    <span className="text-xs text-gray-400 dark:text-zinc-500">
                      = {form.porcentaje_comision}% para todos los clientes
                    </span>
                  )}
                </div>
              </div>
            </div>
            <div className="flex gap-2 mt-3 justify-end">
              <button onClick={() => setShowGenerar(false)} className="btn-ghost">Cancelar</button>
              <button onClick={handleGenerar} disabled={saving} className="btn-yellow">
                {saving ? 'Generando...' : 'Generar borrador'}
              </button>
            </div>
          </div>
        )}

        {/* Form cerrar período */}
        {showCerrar && (
          <div className="card mb-4 border-l-4 border-amber-500">
            <h2 className="font-semibold dark:text-white mb-1">Cerrar período</h2>
            <p className="text-xs text-gray-400 dark:text-zinc-500 mb-3">
              Valida que no haya casos EN_REVISION pendientes y genera la liquidación automáticamente.
            </p>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              <div>
                <label className="label">Inicio del período</label>
                <input type="date" className="input-field"
                  value={form.periodo_inicio} onChange={e => setForm(p => ({ ...p, periodo_inicio: e.target.value }))} />
              </div>
              <div>
                <label className="label">Fin del período</label>
                <input type="date" className="input-field"
                  value={form.periodo_fin} onChange={e => setForm(p => ({ ...p, periodo_fin: e.target.value }))} />
              </div>
            </div>
            <div className="flex gap-2 mt-3 justify-end">
              <button onClick={() => setShowCerrar(false)} className="btn-ghost">Cancelar</button>
              <button onClick={handleCerrarPeriodo} disabled={saving}
                className="px-4 py-2 rounded-lg text-sm font-semibold bg-amber-500 text-white hover:bg-amber-600 disabled:opacity-50">
                {saving ? 'Cerrando...' : '🔒 Confirmar cierre'}
              </button>
            </div>
          </div>
        )}

        {/* Lista */}
        {loading ? (
          <div className="card p-8 text-center text-gray-400">Cargando...</div>
        ) : items.length === 0 ? (
          <div className="card p-8 text-center text-gray-400">
            <p className="text-2xl mb-2">📄</p>
            <p>Sin liquidaciones aún</p>
            <p className="text-xs mt-1">Generá la primera desde el botón de arriba</p>
          </div>
        ) : (
          <div className="space-y-2">
            {items.map(liq => (
              <div key={liq.id}
                onClick={() => loadDetalle(liq.id)}
                className="card cursor-pointer hover:shadow-card-hover transition-all active:scale-[0.99]">
                <div className="flex items-start justify-between gap-3">
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 flex-wrap">
                      <p className="font-semibold dark:text-white text-sm">
                        {liq.periodo_inicio} → {liq.periodo_fin}
                      </p>
                      <span className={`badge ${estadoBadge(liq.estado)}`}>{liq.estado}</span>
                    </div>
                    <p className="text-xs text-gray-400 dark:text-zinc-500 mt-1">
                      Creado por {liq.creador} · {new Date(liq.created_at).toLocaleDateString('es-AR')}
                    </p>
                  </div>
                  <div className="text-right shrink-0">
                    <p className="font-bold text-ml-green dark:text-ml-green font-mono">
                      {fmt(liq.total_neto)}
                    </p>
                    <p className="text-xs text-gray-400 dark:text-zinc-500">neto</p>
                  </div>
                </div>
                <div className="grid grid-cols-3 gap-2 mt-3 pt-3 border-t border-ml-gray dark:border-ml-dark-border">
                  {[
                    { l: 'Conciliado', v: liq.total_conciliado },
                    { l: 'Comisión', v: liq.total_comision },
                    { l: 'Neto', v: liq.total_neto },
                  ].map(k => (
                    <div key={k.l}>
                      <p className="text-2xs text-gray-400 dark:text-zinc-600 uppercase tracking-wider">{k.l}</p>
                      <p className="text-sm font-mono font-semibold dark:text-gray-200">{fmt(k.v)}</p>
                    </div>
                  ))}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* ── Detalle ────────────────────────────── */}
      {selected && (
        <div className="flex flex-col flex-1 md:max-w-2xl border-l border-ml-gray dark:border-ml-dark-border bg-white dark:bg-ml-dark-surface overflow-y-auto">
          <div className="sticky top-0 bg-white dark:bg-ml-dark-surface border-b border-ml-gray dark:border-ml-dark-border px-4 py-3 flex items-center justify-between gap-2 z-10">
            <div className="flex items-center gap-2">
              <button onClick={() => setSelected(null)}
                className="p-1.5 rounded-lg hover:bg-ml-gray dark:hover:bg-ml-dark-hover text-gray-400">
                ←
              </button>
              <div>
                <p className="font-semibold text-sm dark:text-white">Liquidación #{selected.id}</p>
                <p className="text-xs text-gray-400 dark:text-zinc-500">{selected.periodo_inicio} → {selected.periodo_fin}</p>
              </div>
            </div>
            <div className="flex gap-2">
              <button onClick={() => handleExportar(selected.id)} className="btn-secondary text-xs py-1.5">
                ⬇ Excel
              </button>
              {isAdmin && selected.estado === 'borrador' && (
                <button onClick={() => handleAprobar(selected.id)} className="btn-primary text-xs py-1.5">
                  ✓ Aprobar
                </button>
              )}
              {isAdmin && selected.estado === 'aprobada' && (
                <button onClick={() => handlePagada(selected.id)}
                  className="px-3 py-1.5 rounded-lg text-xs font-semibold bg-blue-500 text-white hover:bg-blue-600">
                  💰 Pagada
                </button>
              )}
            </div>
          </div>

          <div className="p-4 space-y-4">
            {/* Estado y totales */}
            <div className="flex items-center gap-3">
              <span className={`badge ${estadoBadge(selected.estado)} text-sm px-3 py-1`}>
                {selected.estado.toUpperCase()}
              </span>
              {selected.aprobador && (
                <span className="text-xs text-gray-400 dark:text-zinc-500">
                  Aprobado por {selected.aprobador}
                </span>
              )}
            </div>

            <div className="grid grid-cols-3 gap-3">
              {[
                { l: 'Total conciliado', v: selected.total_conciliado, cls: 'dark:text-white' },
                { l: 'Comisión', v: selected.total_comision, cls: 'text-amber-600 dark:text-amber-400' },
                { l: 'Neto a cobrar', v: selected.total_neto, cls: 'text-green-600 dark:text-green-400' },
              ].map(k => (
                <div key={k.l} className="kpi">
                  <p className="kpi-label">{k.l}</p>
                  <p className={`text-lg font-bold font-mono ${k.cls}`}>{fmt(k.v)}</p>
                </div>
              ))}
            </div>

            {selected.notas && (
              <div className="px-3 py-2 rounded-lg bg-ml-gray-bg dark:bg-ml-dark-card text-sm text-gray-600 dark:text-gray-300">
                📝 {selected.notas}
              </div>
            )}

            {/* Detalles por cliente */}
            {selected.detalles && selected.detalles.length > 0 && (
              <div className="card p-0 overflow-hidden">
                <div className="px-4 py-2.5 border-b border-ml-gray dark:border-ml-dark-border">
                  <p className="font-semibold text-sm dark:text-white">Desglose por cliente</p>
                </div>
                <table className="w-full text-sm">
                  <thead className="bg-ml-gray-bg dark:bg-ml-dark-card">
                    <tr>
                      {['Cliente', 'Conciliado', 'Comisión', 'Neto'].map(h => (
                        <th key={h} className="px-3 py-2 text-left text-2xs font-semibold text-gray-500 dark:text-zinc-500 uppercase tracking-wider">{h}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-ml-gray dark:divide-ml-dark-border">
                    {selected.detalles.map(d => (
                      <tr key={d.id} className="hover:bg-ml-gray-bg dark:hover:bg-ml-dark-hover">
                        <td className="px-3 py-2.5 font-medium dark:text-white">{d.cliente_nombre}</td>
                        <td className="px-3 py-2.5 font-mono text-xs dark:text-gray-300">{fmt(d.monto_conciliado)}</td>
                        <td className="px-3 py-2.5 text-xs text-amber-600 dark:text-amber-400 font-mono">
                          {fmt(d.monto_comision)} <span className="text-gray-400">({d.porcentaje_comision}%)</span>
                        </td>
                        <td className="px-3 py-2.5 font-mono font-semibold text-green-600 dark:text-green-400">
                          {fmt(d.monto_neto)}
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
