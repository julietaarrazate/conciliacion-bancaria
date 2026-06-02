import React, { useEffect, useState } from 'react'
import { apiClient } from '@/services/api'
import { PlanillaHistorialItem } from '@/types'
import { PlanillaPanel } from '@/components/PlanillaPanel'
import { useOrgStore } from '@/store/org'
import { confirmDialog } from '@/store/confirm'
import { Skeleton } from '@/components/Skeleton'
import { toast } from '@/store/toast'
import { useAuthStore } from '@/store/auth'

export const Historial: React.FC = () => {
  const { activeOrgId } = useOrgStore()
  const canDelete = useAuthStore(s => s.hasPermission('delete_records'))
  const [items, setItems] = useState<PlanillaHistorialItem[]>([])
  const [loading, setLoading] = useState(true)
  const [filter, setFilter] = useState('')
  const [deletingId, setDeletingId] = useState<number | null>(null)
  const [downloadingId, setDownloadingId] = useState<number | null>(null)
  const [savingId, setSavingId] = useState<number | null>(null)
  const [panelId, setPanelId] = useState<number | null>(null)
  const [msg, setMsg] = useState('')
  const [recModal, setRecModal] = useState<PlanillaHistorialItem | null>(null)
  const [recFecha, setRecFecha] = useState(new Date().toISOString().split('T')[0])
  const [recRunning, setRecRunning] = useState(false)
  const [recError, setRecError] = useState('')

  // Chip comisión por planilla
  const [editComId, setEditComId] = useState<number | null>(null)
  const [editComVal, setEditComVal] = useState('')
  const [savingCom, setSavingCom] = useState(false)

  const load = async (f = filter) => {
    setLoading(true)
    try {
      const res = await apiClient.getHistorialPlanillas({ cliente: f || undefined, limit: 200, org_id: activeOrgId })
      setItems(res.items)
    } catch { setItems([]) }
    finally { setLoading(false) }
  }

  useEffect(() => { load() }, [])

  const handleDelete = async (id: number) => {
    if (!await confirmDialog({ title: 'Borrar planilla', message: '¿Borrar esta planilla?', confirmLabel: 'Borrar', danger: true })) return
    setDeletingId(id)
    try {
      await apiClient.deletePlanilla(id)
      setItems(prev => prev.filter(i => i.id !== id))
    } catch (err: any) {
      toast.error(err.response?.data?.detail || 'Error al borrar')
    } finally { setDeletingId(null) }
  }

  const handleGuardar = async (id: number, clienteNombre: string) => {
    setSavingId(id)
    setMsg('')
    try {
      const { path, blob } = await apiClient.guardarEnCarpeta(id)
      if (path) {
        setMsg(`✓ Guardado: clientes/${clienteNombre}/...`)
      } else {
        const url = URL.createObjectURL(blob)
        const a = document.createElement('a')
        a.href = url; a.download = `${clienteNombre}_acreditado.xlsx`; a.click()
        URL.revokeObjectURL(url)
      }
    } catch { setMsg('✗ Error al guardar') }
    finally { setSavingId(null) }
  }

  const handleDownload = async (id: number) => {
    setDownloadingId(id)
    try { await apiClient.downloadPlanillaConciliada(id) }
    finally { setDownloadingId(null) }
  }

  const handleGuardarComision = async (planillaId: number) => {
    setSavingCom(true)
    try {
      const pct = editComVal.trim() === '' ? null : parseFloat(editComVal.replace(',', '.'))
      await apiClient.client.put(`/planillas/${planillaId}/comision`, { porcentaje_comision: pct })
      setItems(prev => prev.map(i =>
        i.id === planillaId ? { ...i, porcentaje_comision: pct } : i
      ))
      setEditComId(null)
    } catch (e: any) {
      toast.error(e.response?.data?.detail || 'Error al guardar comisión')
    } finally { setSavingCom(false) }
  }

  const handleReconciliar = async () => {
    if (!recModal) return
    setRecRunning(true)
    setRecError('')
    try {
      const r = await apiClient.conciliarPlanilla(recModal.id, recFecha, true)
      setMsg(`✓ Re-conciliación de ${recModal.cliente_nombre}: ${r.acreditadas} acreditadas, ${r.no_encontradas} no encontradas`)
      apiClient.invalidateCache('/analisis')
      setRecModal(null)
      load(filter)
    } catch (err: any) {
      setRecError(err.response?.data?.detail || 'Error al re-conciliar')
    }
    setRecRunning(false)
  }

  const totalAcred = items.reduce((s, i) => s + i.acreditadas, 0)
  const totalFilas = items.reduce((s, i) => s + i.total_filas, 0)
  const pct = totalFilas > 0 ? Math.round((totalAcred / totalFilas) * 100) : 0

  const filtered = filter
    ? items.filter(i => i.cliente_nombre.toLowerCase().includes(filter.toLowerCase()))
    : items

  return (
    <div className="flex flex-col h-full">

      {/* ── Header sticky con filtros ─────────────────────── */}
      <div className="sticky top-0 z-20 bg-white dark:bg-ml-dark-surface border-b border-gray-100 dark:border-ml-dark-border px-4 py-3 space-y-2">
        <div className="flex items-center justify-between gap-2">
          <div>
            <h1 className="text-base font-bold dark:text-white">Historial</h1>
            <p className="text-xs text-gray-400 dark:text-zinc-500">
              {filtered.length} planillas · {totalAcred}/{totalFilas} · {pct}%
            </p>
          </div>
        </div>

        {/* Barra de filtro */}
        <div className="flex gap-2">
          <input
            className="input-field flex-1 text-sm"
            placeholder="Buscar cliente..."
            value={filter}
            onChange={e => { setFilter(e.target.value); load(e.target.value) }}
          />
          {filter && (
            <button onClick={() => { setFilter(''); load('') }}
              className="px-3 text-gray-400 hover:text-gray-600 dark:hover:text-white text-sm">
              ✕
            </button>
          )}
        </div>
      </div>

      {/* ── Mensaje ──────────────────────────────────────── */}
      {msg && (
        <div className={`mx-4 mt-2 px-3 py-2 rounded text-sm ${msg.startsWith('✓') ? 'bg-green-50 text-green-700 dark:bg-green-900/20 dark:text-green-300' : 'bg-red-50 text-red-600 dark:bg-red-900/20 dark:text-red-400'}`}>
          {msg}
        </div>
      )}

      {/* ── Contenido ────────────────────────────────────── */}
      <div className="flex-1 overflow-y-auto p-4 space-y-2">
        {loading ? (
          <div className="space-y-2">
            {Array.from({ length: 5 }).map((_, i) => (
              <div key={i} className="bg-white dark:bg-ml-dark-surface rounded-xl border border-gray-100 dark:border-ml-dark-border p-4 space-y-2">
                <div className="flex items-start justify-between gap-2">
                  <div className="flex-1 space-y-1.5 min-w-0">
                    <Skeleton className="h-4 w-2/5" />
                    <Skeleton className="h-3 w-3/5" />
                    <Skeleton className="h-2.5 w-24" />
                  </div>
                  <Skeleton className="h-6 w-14 rounded-full shrink-0" />
                </div>
                <div className="flex gap-2 pt-2">
                  <Skeleton className="h-8 flex-1" />
                  <Skeleton className="h-8 flex-1" />
                </div>
              </div>
            ))}
          </div>
        ) : filtered.length === 0 ? (
          <div className="py-12 text-center text-gray-400">Sin planillas</div>
        ) : (
          filtered.map(it => {
            const acc = it.total_filas > 0 ? Math.round((it.acreditadas / it.total_filas) * 100) : 0
            return (
              <div key={it.id}
                className="bg-white dark:bg-ml-dark-surface rounded-xl border border-gray-100 dark:border-ml-dark-border p-4 active:bg-gray-50 dark:active:bg-ml-dark-card"
              >
                {/* Fila 1: cliente + badge + chip comisión */}
                <div className="flex items-start justify-between gap-2 mb-2">
                  <div className="min-w-0">
                    <p className="font-semibold dark:text-white truncate">{it.cliente_nombre}</p>
                    <p className="text-xs text-gray-400 dark:text-zinc-500 truncate">{it.nombre_archivo}</p>
                    <p className="text-xs text-gray-400 dark:text-zinc-600 mt-0.5">
                      {new Date(it.fecha_carga).toLocaleString('es-AR', { dateStyle: 'short', timeStyle: 'short' })}
                    </p>
                  </div>
                  <div className="flex items-center gap-1.5 shrink-0">
                    {/* Chip comisión editable */}
                    {editComId === it.id ? (
                      <div className="flex items-center gap-1" onClick={e => e.stopPropagation()}>
                        <input
                          type="number" step="0.1" min="0" max="100" placeholder="%"
                          className="input-field text-xs w-16 py-0.5 px-1.5"
                          value={editComVal}
                          onChange={e => setEditComVal(e.target.value)}
                          onKeyDown={e => { if (e.key === 'Enter') handleGuardarComision(it.id); if (e.key === 'Escape') setEditComId(null) }}
                          autoFocus
                        />
                        <button onClick={() => handleGuardarComision(it.id)} disabled={savingCom}
                          className="px-1.5 py-0.5 text-[10px] bg-amber-500 text-white rounded hover:bg-amber-600 disabled:opacity-30">
                          {savingCom ? '⏳' : '✓'}
                        </button>
                        <button onClick={() => setEditComId(null)} className="text-[10px] text-gray-400 hover:text-gray-600 px-0.5">✕</button>
                      </div>
                    ) : (
                      <button
                        onClick={() => { setEditComId(it.id); setEditComVal(it.porcentaje_comision != null ? String(it.porcentaje_comision) : '') }}
                        className={`px-2 py-1 text-[11px] rounded font-medium transition-colors ${it.porcentaje_comision != null ? 'bg-amber-100 dark:bg-amber-900/40 text-amber-700 dark:text-amber-300 hover:bg-amber-200' : 'bg-gray-100 dark:bg-zinc-700 text-gray-500 dark:text-zinc-400 hover:bg-gray-200'}`}
                        title="% comisión — click para editar"
                      >
                        {it.porcentaje_comision != null ? `${it.porcentaje_comision}% comi` : 'comi —'}
                      </button>
                    )}
                    <span className={`badge ${acc === 100 ? 'badge-ok' : acc >= 80 ? 'badge-warn' : 'badge-error'}`}>
                      {acc}%
                    </span>
                  </div>
                </div>

                {/* Fila 2: stats */}
                <div className="grid grid-cols-4 gap-1 mb-3 text-center">
                  {[
                    { label: 'Total', val: it.total_filas, cls: 'dark:text-white' },
                    { label: 'OK', val: it.acreditadas, cls: 'text-green-600 dark:text-green-400' },
                    { label: 'No está', val: it.no_encontradas || 0, cls: 'text-red-500 dark:text-red-400' },
                    { label: 'Sin datos', val: it.sin_datos || 0, cls: 'text-blue-500 dark:text-blue-400' },
                  ].map(s => (
                    <div key={s.label} className="bg-gray-50 dark:bg-ml-dark-bg rounded-lg py-1.5">
                      <p className={`text-base font-bold ${s.cls}`}>{s.val}</p>
                      <p className="text-[10px] text-gray-400 dark:text-zinc-600">{s.label}</p>
                    </div>
                  ))}
                </div>

                {/* Fila 3: acciones */}
                <div className="flex gap-2 flex-wrap">
                  <button
                    onClick={() => setPanelId(it.id)}
                    className="flex-1 flex items-center justify-center gap-1.5 py-2 text-sm rounded-lg bg-blue-50 dark:bg-blue-900/20 text-blue-600 dark:text-blue-400 font-medium active:scale-95"
                  >
                    👁️ Ver / Editar
                  </button>
                  <button
                    onClick={() => { const _d = new Date(); setRecFecha(`${_d.getFullYear()}-${String(_d.getMonth() + 1).padStart(2, '0')}-${String(_d.getDate()).padStart(2, '0')}`); setRecError(''); setRecModal(it) }}
                    className="flex-1 flex items-center justify-center gap-1.5 py-2 text-sm rounded-lg bg-orange-50 dark:bg-orange-900/20 text-orange-600 dark:text-orange-400 font-medium active:scale-95"
                    title="Re-conciliar: busca movimientos nuevos para las filas que no estaban"
                  >
                    🔄 Re-conciliar
                  </button>
                  <button
                    onClick={() => handleGuardar(it.id, it.cliente_nombre)}
                    disabled={savingId === it.id}
                    className="flex-1 flex items-center justify-center gap-1.5 py-2 text-sm rounded-lg bg-purple-50 dark:bg-purple-900/20 text-purple-600 dark:text-purple-400 font-medium disabled:opacity-40 active:scale-95"
                  >
                    {savingId === it.id ? '⏳' : '📁 Exportar'}
                  </button>
                  {canDelete && (
                    <button
                      onClick={() => handleDelete(it.id)}
                      disabled={deletingId === it.id}
                      className="flex items-center justify-center py-2 px-3 text-sm rounded-lg bg-red-50 dark:bg-red-900/20 text-red-400 dark:text-red-500 disabled:opacity-40 active:scale-95"
                      title="Eliminar"
                    >
                      {deletingId === it.id ? '⏳' : '🗑️'}
                    </button>
                  )}
                </div>
              </div>
            )
          })
        )}
      </div>

      {/* ── Panel detalle ────────────────────────────────── */}
      <PlanillaPanel
        planillaId={panelId}
        onClose={() => setPanelId(null)}
        onDelete={canDelete ? async id => { await apiClient.deletePlanilla(id); setPanelId(null); load(filter) } : undefined}
      />

      {/* ── Modal re-conciliar ───────────────────────────── */}
      {recModal && (
        <div className="fixed inset-0 z-50 flex items-end sm:items-center justify-center bg-black/50 p-4" onClick={() => setRecModal(null)}>
          <div className="bg-white dark:bg-slate-800 rounded-xl shadow-xl p-5 w-full max-w-sm" onClick={e => e.stopPropagation()}>
            <h3 className="text-sm font-semibold dark:text-white mb-1">🔄 Re-conciliar planilla</h3>
            <p className="text-xs text-gray-500 dark:text-gray-400 mb-4">
              <strong>{recModal.cliente_nombre}</strong> · {recModal.nombre_archivo}
              <br />
              Solo re-procesa las filas <em>no acreditadas</em>. Las que ya están OK no se tocan.
            </p>

            <div className="space-y-3">
              <div>
                <label className="label text-xs">Fecha de acreditación</label>
                <div className="flex gap-2 mb-1">
                  <button
                    onClick={() => setRecFecha(new Date().toISOString().split('T')[0])}
                    className={`px-3 py-1.5 text-xs rounded-md border transition-colors ${recFecha === new Date().toISOString().split('T')[0] ? 'bg-ml-blue text-white border-ml-blue' : 'border-gray-300 dark:border-slate-600 hover:bg-gray-50 dark:hover:bg-slate-700 dark:text-gray-300'}`}
                  >
                    Hoy
                  </button>
                  <button
                    onClick={() => { const d = new Date(); d.setDate(d.getDate()-1); setRecFecha(d.toISOString().split('T')[0]) }}
                    className={`px-3 py-1.5 text-xs rounded-md border transition-colors ${recFecha === (() => { const d = new Date(); d.setDate(d.getDate()-1); return d.toISOString().split('T')[0] })() ? 'bg-ml-blue text-white border-ml-blue' : 'border-gray-300 dark:border-slate-600 hover:bg-gray-50 dark:hover:bg-slate-700 dark:text-gray-300'}`}
                  >
                    Ayer
                  </button>
                </div>
                <input
                  type="date"
                  className="input-field text-xs"
                  value={recFecha}
                  onChange={e => setRecFecha(e.target.value)}
                />
              </div>
            </div>

            {recError && <p className="mt-3 text-xs text-red-600 dark:text-red-400">{recError}</p>}

            <div className="flex gap-2 mt-5 justify-end">
              <button onClick={() => setRecModal(null)} className="px-3 py-1.5 text-xs text-gray-500 border border-gray-200 dark:border-slate-600 rounded hover:bg-gray-50 dark:hover:bg-slate-700">
                Cancelar
              </button>
              <button
                onClick={handleReconciliar}
                disabled={recRunning || !recFecha}
                className="px-4 py-1.5 text-xs bg-orange-500 text-white rounded hover:bg-orange-600 disabled:opacity-50"
              >
                {recRunning ? '⏳ Procesando...' : '🔄 Re-conciliar'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
