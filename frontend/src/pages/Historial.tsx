import React, { useEffect, useState } from 'react'
import { apiClient } from '@/services/api'
import { PlanillaHistorialItem } from '@/types'
import { PlanillaPanel } from '@/components/PlanillaPanel'
import { useOrgStore } from '@/store/org'

export const Historial: React.FC = () => {
  const { activeOrgId } = useOrgStore()
  const [items, setItems] = useState<PlanillaHistorialItem[]>([])
  const [loading, setLoading] = useState(true)
  const [filter, setFilter] = useState('')
  const [deletingId, setDeletingId] = useState<number | null>(null)
  const [downloadingId, setDownloadingId] = useState<number | null>(null)
  const [savingId, setSavingId] = useState<number | null>(null)
  const [panelId, setPanelId] = useState<number | null>(null)
  const [msg, setMsg] = useState('')

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
    if (!confirm('¿Borrar esta planilla?')) return
    setDeletingId(id)
    try {
      await apiClient.deletePlanilla(id)
      setItems(prev => prev.filter(i => i.id !== id))
    } catch (err: any) {
      alert(err.response?.data?.detail || 'Error al borrar')
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
          <button
            onClick={() => apiClient.exportHistorial({ cliente: filter || undefined })}
            className="btn-primary text-xs px-3 py-1.5 shrink-0"
          >
            ⬇️ Excel
          </button>
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
        <div className={`mx-4 mt-2 px-3 py-2 rounded text-sm ${msg.startsWith('✓') ? 'bg-green-50 text-green-700 dark:bg-green-900/20 dark:text-green-300' : 'bg-red-50 text-red-600'}`}>
          {msg}
        </div>
      )}

      {/* ── Contenido ────────────────────────────────────── */}
      <div className="flex-1 overflow-y-auto p-4 space-y-2">
        {loading ? (
          <div className="py-12 text-center text-gray-400">Cargando...</div>
        ) : filtered.length === 0 ? (
          <div className="py-12 text-center text-gray-400">Sin planillas</div>
        ) : (
          filtered.map(it => {
            const acc = it.total_filas > 0 ? Math.round((it.acreditadas / it.total_filas) * 100) : 0
            return (
              <div key={it.id}
                className="bg-white dark:bg-ml-dark-surface rounded-xl border border-gray-100 dark:border-ml-dark-border p-4 active:bg-gray-50 dark:active:bg-ml-dark-card"
              >
                {/* Fila 1: cliente + badge */}
                <div className="flex items-start justify-between gap-2 mb-2">
                  <div className="min-w-0">
                    <p className="font-semibold dark:text-white truncate">{it.cliente_nombre}</p>
                    <p className="text-xs text-gray-400 dark:text-zinc-500 truncate">{it.nombre_archivo}</p>
                    <p className="text-xs text-gray-400 dark:text-zinc-600 mt-0.5">
                      {new Date(it.fecha_carga).toLocaleString('es-AR', { dateStyle: 'short', timeStyle: 'short' })}
                    </p>
                  </div>
                  <span className={`shrink-0 badge ${acc === 100 ? 'badge-ok' : acc >= 80 ? 'badge-warn' : 'badge-error'}`}>
                    {acc}%
                  </span>
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
                    onClick={() => handleDownload(it.id)}
                    disabled={downloadingId === it.id}
                    className="flex-1 flex items-center justify-center gap-1.5 py-2 text-sm rounded-lg bg-green-50 dark:bg-green-900/20 text-green-600 dark:text-green-400 font-medium disabled:opacity-40 active:scale-95"
                  >
                    {downloadingId === it.id ? '⏳' : '⬇️ Excel'}
                  </button>
                  <button
                    onClick={() => handleGuardar(it.id, it.cliente_nombre)}
                    disabled={savingId === it.id}
                    className="flex items-center justify-center gap-1 py-2 px-3 text-sm rounded-lg bg-purple-50 dark:bg-purple-900/20 text-purple-600 dark:text-purple-400 disabled:opacity-40 active:scale-95"
                    title="Guardar en carpeta"
                  >
                    {savingId === it.id ? '⏳' : '📁'}
                  </button>
                  <button
                    onClick={() => handleDelete(it.id)}
                    disabled={deletingId === it.id}
                    className="flex items-center justify-center py-2 px-3 text-sm rounded-lg bg-red-50 dark:bg-red-900/20 text-red-400 dark:text-red-500 disabled:opacity-40 active:scale-95"
                    title="Eliminar"
                  >
                    {deletingId === it.id ? '⏳' : '🗑️'}
                  </button>
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
        onDelete={async id => { await apiClient.deletePlanilla(id); setPanelId(null); load(filter) }}
      />
    </div>
  )
}
