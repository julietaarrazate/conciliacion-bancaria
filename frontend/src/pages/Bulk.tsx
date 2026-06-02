import React, { useEffect, useState } from 'react'
import { apiClient } from '@/services/api'
import { ExtractoListItem, ConciliacionResultado } from '@/types'
import { localIsoDate } from '@/utils/fecha'

interface BulkItem {
  id: string
  file: File
  clienteNombre: string
  status: 'pending' | 'loading' | 'ok' | 'error'
  resultado?: ConciliacionResultado
  error?: string
}

export const Bulk: React.FC = () => {
  const [extractos, setExtractos] = useState<ExtractoListItem[]>([])
  const [extractoId, setExtractoId] = useState<number | null>(null)
  const [items, setItems] = useState<BulkItem[]>([])
  const [running, setRunning] = useState(false)
  const [fechaAcred, setFechaAcred] = useState<string>(localIsoDate())

  useEffect(() => {
    apiClient.listExtractos().then(d => {
      setExtractos(d.items)
      if (d.items.length > 0) setExtractoId(d.items[0].id)
    })
  }, [])

  const handleFiles = (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = Array.from(e.target.files || [])
    const newItems: BulkItem[] = files.map(f => ({
      id: `${f.name}-${Date.now()}-${Math.random()}`,
      file: f,
      clienteNombre: f.name.replace(/\.[^.]+$/, '').replace(/[_-]/g, ' ').trim(),
      status: 'pending'
    }))
    setItems(prev => [...prev, ...newItems])
    e.target.value = ''
  }

  const updateItem = (id: string, patch: Partial<BulkItem>) =>
    setItems(prev => prev.map(it => it.id === id ? { ...it, ...patch } : it))

  const removeItem = (id: string) =>
    setItems(prev => prev.filter(it => it.id !== id))

  const handleRun = async () => {
    if (!extractoId || items.length === 0) return
    setRunning(true)

    for (const item of items) {
      if (item.status === 'ok') continue
      updateItem(item.id, { status: 'loading', error: undefined })
      try {
        const planilla = await apiClient.uploadPlanilla(
          item.clienteNombre, extractoId, item.file
        )
        const resultado = await apiClient.conciliarPlanilla(planilla.id, fechaAcred)
        updateItem(item.id, { status: 'ok', resultado })
      } catch (err: any) {
        updateItem(item.id, {
          status: 'error',
          error: err.response?.data?.detail || 'Error al procesar'
        })
      }
    }

    setRunning(false)
  }

  const pendingCount = items.filter(i => i.status === 'pending' || i.status === 'error').length
  const okCount = items.filter(i => i.status === 'ok').length
  const totalAcred = items.reduce((s, i) => s + (i.resultado?.acreditadas || 0), 0)
  const totalFilas = items.reduce((s, i) => s + (i.resultado?.filas_procesadas || 0), 0)

  return (
    <div className="p-6 max-w-5xl mx-auto">
      <h1 className="text-2xl font-bold text-ml-text dark:text-white mb-1">
        Bulk — Múltiples planillas
      </h1>
      <p className="text-sm text-ml-text-soft dark:text-gray-400 mb-5">
        Subí varias planillas a la vez. Se concilian todas contra el mismo extracto.
      </p>

      {/* Extracto selector */}
      <div className="card mb-4">
        <label className="label">Extracto bancario</label>
        <select
          className="input-field max-w-sm"
          value={extractoId ?? ''}
          onChange={e => setExtractoId(Number(e.target.value))}
        >
          {extractos.map(e => (
            <option key={e.id} value={e.id}>
              #{e.id} · {e.nombre_archivo} ({e.total_movimientos} movs)
            </option>
          ))}
        </select>
      </div>

      {/* Fecha de acreditación */}
      <div className="card mb-4 flex flex-wrap gap-4 items-end">
        <div>
          <label className="label">Fecha de acreditación</label>
          <input
            type="date"
            className="input-field font-mono w-auto"
            value={fechaAcred}
            onChange={e => setFechaAcred(e.target.value)}
          />
        </div>
        <p className="text-xs text-gray-400 dark:text-zinc-600 pb-2">
          Todas las planillas se acreditarán con esta fecha
        </p>
      </div>

      {/* Drop zone */}
      <div className="card mb-4">
        <label className="block border-2 border-dashed border-gray-300 dark:border-slate-600 rounded-lg p-6 text-center cursor-pointer hover:border-ml-blue dark:hover:border-ml-blue transition-colors">
          <span className="text-3xl block mb-2">📂</span>
          <span className="text-sm font-medium text-ml-text dark:text-white">
            Clic o arrastrá las planillas aquí
          </span>
          <span className="text-xs text-ml-text-soft dark:text-gray-400 block mt-1">
            Podés seleccionar múltiples archivos a la vez
          </span>
          <input type="file" accept="*/*" multiple hidden onChange={handleFiles} />
        </label>
      </div>

      {/* Lista de planillas */}
      {items.length > 0 && (
        <>
          <div className="card mb-4 p-0 overflow-hidden">
            <div className="px-4 py-3 bg-ml-gray-bg dark:bg-slate-900 border-b dark:border-slate-700 flex justify-between items-center">
              <span className="text-sm font-medium dark:text-white">
                {items.length} planillas · {okCount} procesadas
                {totalFilas > 0 && ` · ${totalAcred}/${totalFilas} acreditadas`}
              </span>
              <button
                onClick={() => setItems([])}
                className="text-xs text-red-600 dark:text-red-400 hover:underline"
                disabled={running}
              >
                Limpiar todo
              </button>
            </div>

            <table className="w-full text-sm">
              <thead>
                <tr className="border-b dark:border-slate-700">
                  <th className="px-4 py-2 text-left text-xs font-semibold text-ml-text-soft uppercase">Archivo</th>
                  <th className="px-4 py-2 text-left text-xs font-semibold text-ml-text-soft uppercase">Cliente</th>
                  <th className="px-4 py-2 text-center text-xs font-semibold text-ml-text-soft uppercase">Estado</th>
                  <th className="px-4 py-2 text-center text-xs font-semibold text-ml-text-soft uppercase">Resultado</th>
                  <th className="px-4 py-2 w-8"></th>
                </tr>
              </thead>
              <tbody className="divide-y dark:divide-slate-700">
                {items.map(item => (
                  <tr key={item.id} className="hover:bg-ml-gray-bg dark:hover:bg-slate-700/50">
                    <td className="px-4 py-2.5 dark:text-gray-300 max-w-[200px] truncate">
                      {item.file.name}
                    </td>
                    <td className="px-4 py-2.5">
                      <input
                        className="input-field !py-1 text-sm"
                        value={item.clienteNombre}
                        onChange={e => updateItem(item.id, { clienteNombre: e.target.value })}
                        disabled={running || item.status === 'ok'}
                        placeholder="Nombre cliente..."
                      />
                    </td>
                    <td className="px-4 py-2.5 text-center">
                      {item.status === 'pending' && <span className="badge badge-info">Pendiente</span>}
                      {item.status === 'loading' && <span className="badge badge-warn">⏳ Procesando</span>}
                      {item.status === 'ok' && <span className="badge badge-ok">✓ OK</span>}
                      {item.status === 'error' && (
                        <span className="badge badge-error" title={item.error}>Error</span>
                      )}
                    </td>
                    <td className="px-4 py-2.5 text-center text-xs text-ml-text-soft dark:text-gray-400">
                      {item.resultado ? (
                        <span>
                          <span className="text-green-600 font-bold">{item.resultado.acreditadas}</span>
                          /{item.resultado.filas_procesadas}
                        </span>
                      ) : item.error ? (
                        <span className="text-red-500 text-xs">{item.error.slice(0, 40)}</span>
                      ) : '—'}
                    </td>
                    <td className="px-4 py-2.5 text-center">
                      <button
                        onClick={() => removeItem(item.id)}
                        disabled={running}
                        className="text-ml-text-soft hover:text-red-600 dark:text-gray-500 dark:hover:text-red-400 disabled:opacity-30"
                      >
                        ✕
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div className="flex gap-3">
            <button
              onClick={handleRun}
              disabled={running || pendingCount === 0 || !extractoId}
              className="btn-yellow disabled:opacity-50"
            >
              {running ? '⏳ Conciliando...' : `⚡ Conciliar ${pendingCount} planilla${pendingCount !== 1 ? 's' : ''}`}
            </button>
            {okCount > 0 && (
              <div className="flex items-center gap-2 text-sm text-green-700 dark:text-green-400 bg-green-50 dark:bg-green-900/20 px-4 py-2 rounded-md">
                ✓ {okCount} procesadas · {totalAcred} acreditadas de {totalFilas}
              </div>
            )}
          </div>
        </>
      )}
    </div>
  )
}
