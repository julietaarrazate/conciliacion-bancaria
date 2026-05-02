import React, { useEffect, useState } from 'react'
import { apiClient } from '@/services/api'
import { PlanillaHistorialItem } from '@/types'
import { PlanillaPanel } from '@/components/PlanillaPanel'

export const Historial: React.FC = () => {
  const [items, setItems] = useState<PlanillaHistorialItem[]>([])
  const [loading, setLoading] = useState(true)
  const [filter, setFilter] = useState('')
  const [exporting, setExporting] = useState(false)
  const [deletingId, setDeletingId] = useState<number | null>(null)
  const [downloadingId, setDownloadingId] = useState<number | null>(null)
  const [panelId, setPanelId] = useState<number | null>(null)

  const handleDownload = async (id: number) => {
    setDownloadingId(id)
    try { await apiClient.downloadPlanillaConciliada(id) }
    finally { setDownloadingId(null) }
  }

  const handleDelete = async (id: number) => {
    if (!confirm('¿Borrar esta planilla? Se liberan los movimientos que había acreditado.')) return
    setDeletingId(id)
    try {
      await apiClient.deletePlanilla(id)
      setItems(prev => prev.filter(i => i.id !== id))
    } catch (err: any) {
      alert(err.response?.data?.detail || 'Error al borrar')
    } finally {
      setDeletingId(null)
    }
  }

  const load = async (f = filter) => {
    setLoading(true)
    try {
      const res = await apiClient.getHistorialPlanillas({ cliente: f || undefined, limit: 100 })
      setItems(res.items)
    } catch { setItems([]) }
    finally { setLoading(false) }
  }

  useEffect(() => { load() }, [])

  const handleExport = async () => {
    setExporting(true)
    try { await apiClient.exportHistorial({ cliente: filter || undefined }) }
    finally { setExporting(false) }
  }

  const totalAcred = items.reduce((s, i) => s + i.acreditadas, 0)
  const totalFilas = items.reduce((s, i) => s + i.total_filas, 0)
  const pct = totalFilas > 0 ? Math.round((totalAcred / totalFilas) * 100) : 0

  return (
    <div className="p-6 max-w-6xl mx-auto">
      <PlanillaPanel
        planillaId={panelId}
        onClose={() => setPanelId(null)}
        onDelete={async id => { await apiClient.deletePlanilla(id); setPanelId(null); load(filter) }}
      />
      <div className="flex items-start justify-between mb-4 flex-wrap gap-3">
        <div>
          <h1 className="text-2xl font-bold text-ml-text dark:text-white">Historial</h1>
          <p className="text-sm text-ml-text-soft dark:text-gray-400">
            {items.length} planillas · {totalAcred}/{totalFilas} acreditadas · {pct}% precisión
          </p>
        </div>
        <button
          onClick={handleExport}
          disabled={exporting || items.length === 0}
          className="flex items-center gap-2 px-4 py-2 bg-green-600 text-white rounded-md text-sm font-medium hover:bg-green-700 disabled:opacity-50 transition-colors"
        >
          {exporting ? '⏳ Exportando...' : '⬇️ Exportar Excel'}
        </button>
      </div>

      <div className="card mb-4 flex gap-3 items-end">
        <div className="flex-1">
          <label className="label">Filtrar por cliente</label>
          <input
            className="input-field"
            placeholder="Green, Tucu, Alojando..."
            value={filter}
            onChange={(e) => setFilter(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && load(filter)}
          />
        </div>
        <button onClick={() => load(filter)} className="btn-primary">Buscar</button>
        {filter && <button onClick={() => { setFilter(''); load('') }} className="btn-secondary">Limpiar</button>}
      </div>

      <div className="card overflow-hidden p-0">
        {loading ? (
          <div className="p-8 text-center text-ml-text-soft">Cargando...</div>
        ) : items.length === 0 ? (
          <div className="p-8 text-center text-ml-text-soft">Sin reconciliaciones registradas</div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-ml-gray-bg dark:bg-slate-900 border-b dark:border-slate-700">
                <tr>
                  {['Cliente','Archivo','Fecha','Usuario','Total','OK','No está','Dup.','Datos','%',''].map(h => (
                    <th key={h} className="px-3 py-2.5 text-left text-xs font-semibold text-ml-text-soft uppercase dark:text-gray-400">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y dark:divide-slate-700">
                {items.map((it) => {
                  const acc = it.total_filas > 0 ? Math.round((it.acreditadas / it.total_filas) * 100) : 0
                  return (
                    <tr key={it.id} className="hover:bg-ml-gray-bg dark:hover:bg-slate-700/50">
                      <td className="px-3 py-2 font-medium dark:text-white">{it.cliente_nombre}</td>
                      <td className="px-3 py-2 text-ml-text-soft dark:text-gray-400 max-w-[180px] truncate">{it.nombre_archivo}</td>
                      <td className="px-3 py-2 text-ml-text-soft dark:text-gray-400 whitespace-nowrap">{new Date(it.fecha_carga).toLocaleString('es-AR', { dateStyle: 'short', timeStyle: 'short' })}</td>
                      <td className="px-3 py-2 text-ml-text-soft dark:text-gray-400">{it.usuario_nombre}</td>
                      <td className="px-3 py-2 text-center">{it.total_filas}</td>
                      <td className="px-3 py-2 text-center font-bold text-green-600 dark:text-green-400">{it.acreditadas}</td>
                      <td className="px-3 py-2 text-center font-bold text-red-600 dark:text-red-400">{it.no_encontradas || '—'}</td>
                      <td className="px-3 py-2 text-center font-bold text-yellow-600 dark:text-yellow-400">{it.duplicadas || '—'}</td>
                      <td className="px-3 py-2 text-center font-bold text-blue-600 dark:text-blue-400">{it.sin_datos || '—'}</td>
                      <td className="px-3 py-2 text-center">
                        <span className={`badge ${acc === 100 ? 'badge-ok' : acc >= 80 ? 'badge-warn' : 'badge-error'}`}>{acc}%</span>
                      </td>
                      <td className="px-3 py-2 text-center">
                        <div className="flex items-center gap-1 justify-center">
                          <button
                            onClick={() => setPanelId(it.id)}
                            className="text-ml-blue hover:text-ml-blue-dark text-sm"
                            title="Ver detalle"
                          >👁️</button>
                          <button
                            onClick={() => handleDownload(it.id)}
                            disabled={downloadingId === it.id}
                            className="text-green-600 hover:text-green-700 disabled:opacity-30 text-sm"
                            title="Descargar Excel (Hoja1: cliente, Hoja2: extracto)"
                          >{downloadingId === it.id ? '⏳' : '⬇️'}</button>
                          <button
                            onClick={() => handleDelete(it.id)}
                            disabled={deletingId === it.id}
                            className="text-ml-text-soft hover:text-red-600 dark:text-gray-500 dark:hover:text-red-400 disabled:opacity-30 text-sm"
                            title="Borrar planilla"
                          >🗑️</button>
                        </div>
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  )
}
