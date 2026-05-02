import React, { useEffect, useState } from 'react'
import { PlanillaPanel } from '@/components/PlanillaPanel'
import { apiClient } from '@/services/api'

interface Archivo {
  id: number
  nombre_archivo: string
  fecha_carga: string
  total: number
  acreditadas: number
}

interface MesArchivos {
  mes: string
  archivos: Archivo[]
}

interface ClienteData {
  nombre: string
  meses: MesArchivos[]
}

const ICONOS: Record<string, string> = {
  Green: '🟢', Tucu: '🟡', David: '🔵', Smt: '🔴',
  Gwinn: '🟠', Innova: '⚪', Camparo: '🟤',
  Alojando: '🏠', Pinares: '🌲', Paraguay: '🇵🇾'
}

export const Clientes: React.FC = () => {
  const [clientes, setClientes] = useState<ClienteData[]>([])
  const [loading, setLoading] = useState(true)
  const [expanded, setExpanded] = useState<Record<string, boolean>>({})
  const [expandedMes, setExpandedMes] = useState<Record<string, boolean>>({})
  const [panelId, setPanelId] = useState<number | null>(null)
  const [savingId, setSavingId] = useState<number | null>(null)
  const [msg, setMsg] = useState('')

  useEffect(() => {
    apiClient.client.get('/clientes/archivos')
      .then(r => setClientes(r.data.clientes))
      .catch(() => setClientes([]))
      .finally(() => setLoading(false))
  }, [])

  const toggle = (nombre: string) =>
    setExpanded(p => ({ ...p, [nombre]: !p[nombre] }))

  const toggleMes = (key: string) =>
    setExpandedMes(p => ({ ...p, [key]: !p[key] }))

  const handleGuardar = async (id: number, clienteNombre: string) => {
    setSavingId(id)
    setMsg('')
    try {
      const { path, blob } = await apiClient.guardarEnCarpeta(id)
      if (path) {
        setMsg(`✓ Guardado en clientes/${clienteNombre}/...`)
      } else {
        const url = URL.createObjectURL(blob)
        const a = document.createElement('a')
        a.href = url; a.download = `${clienteNombre}_acreditado.xlsx`; a.click()
        URL.revokeObjectURL(url)
      }
    } catch { setMsg('✗ Error al guardar') }
    finally { setSavingId(null) }
  }

  const fmtFecha = (s: string) => {
    try { return new Date(s + 'Z').toLocaleDateString('es-AR', { day: '2-digit', month: '2-digit', year: '2-digit', hour: '2-digit', minute: '2-digit' }) }
    catch { return s }
  }

  const totalGlobal = clientes.reduce((s, c) =>
    s + c.meses.reduce((ms, m) => ms + m.archivos.length, 0), 0)

  return (
    <div className="p-4 md:p-6 max-w-4xl mx-auto">
      <div className="mb-4">
        <h1 className="text-xl md:text-2xl font-bold dark:text-white">Clientes</h1>
        <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
          {clientes.length} clientes · {totalGlobal} conciliaciones guardadas
        </p>
      </div>

      {msg && (
        <div className={`mb-3 px-3 py-2 rounded text-sm ${msg.startsWith('✓') ? 'bg-green-50 text-green-700 dark:bg-green-900/20 dark:text-green-300' : 'bg-red-50 text-red-700'}`}>
          {msg}
        </div>
      )}

      {loading ? (
        <div className="card p-8 text-center text-gray-400">Cargando...</div>
      ) : clientes.length === 0 ? (
        <div className="card p-8 text-center">
          <p className="text-gray-400 mb-2">Sin conciliaciones guardadas aún</p>
          <p className="text-sm text-gray-400">Conciliá una planilla desde el Dashboard para verla acá</p>
        </div>
      ) : (
        <div className="space-y-2">
          {clientes.map(cliente => {
            const isOpen = expanded[cliente.nombre]
            const total = cliente.meses.reduce((s, m) => s + m.archivos.length, 0)
            const acred = cliente.meses.reduce((s, m) =>
              s + m.archivos.reduce((as, a) => as + a.acreditadas, 0), 0)
            const icono = ICONOS[cliente.nombre] || '📁'

            return (
              <div key={cliente.nombre} className="card p-0 overflow-hidden">
                {/* Header cliente */}
                <button
                  onClick={() => toggle(cliente.nombre)}
                  className="w-full flex items-center gap-3 px-4 py-3.5 hover:bg-gray-50 dark:hover:bg-slate-700/50 transition-colors text-left"
                >
                  <span className="text-xl">{icono}</span>
                  <div className="flex-1">
                    <p className="font-semibold dark:text-white">{cliente.nombre}</p>
                    <p className="text-xs text-gray-500 dark:text-gray-400">
                      {total} archivo{total !== 1 ? 's' : ''} · {acred} acreditaciones
                    </p>
                  </div>
                  <span className="text-gray-400 dark:text-gray-500 text-sm">{isOpen ? '▲' : '▼'}</span>
                </button>

                {/* Meses */}
                {isOpen && (
                  <div className="border-t dark:border-slate-700">
                    {cliente.meses.map(mes => {
                      const mesKey = `${cliente.nombre}:${mes.mes}`
                      const mesOpen = expandedMes[mesKey] !== false // abierto por defecto

                      return (
                        <div key={mes.mes}>
                          <button
                            onClick={() => toggleMes(mesKey)}
                            className="w-full flex items-center gap-2 px-6 py-2.5 bg-gray-50 dark:bg-slate-900/50 hover:bg-gray-100 dark:hover:bg-slate-700/50 text-left transition-colors"
                          >
                            <span className="text-sm">📅</span>
                            <span className="text-sm font-medium text-gray-700 dark:text-gray-300 flex-1">{mes.mes}</span>
                            <span className="text-xs text-gray-400">{mes.archivos.length} archivos {mesOpen ? '▲' : '▼'}</span>
                          </button>

                          {mesOpen && (
                            <div className="divide-y dark:divide-slate-700/50">
                              {mes.archivos.map(archivo => {
                                const pct = archivo.total > 0 ? Math.round((archivo.acreditadas / archivo.total) * 100) : 0
                                return (
                                  <div key={archivo.id} className="flex items-center gap-3 px-6 py-2.5 hover:bg-gray-50 dark:hover:bg-slate-700/30 transition-colors">
                                    <span className="text-sm">📄</span>
                                    <div className="flex-1 min-w-0">
                                      <p className="text-sm truncate dark:text-gray-200">{archivo.nombre_archivo}</p>
                                      <p className="text-xs text-gray-400 dark:text-gray-500">
                                        {fmtFecha(archivo.fecha_carga)} · {archivo.acreditadas}/{archivo.total} ({pct}%)
                                      </p>
                                    </div>
                                    <div className="flex items-center gap-1 flex-shrink-0">
                                      <span className={`text-xs px-1.5 py-0.5 rounded-full font-medium ${pct === 100 ? 'bg-green-100 text-green-700 dark:bg-green-900/40 dark:text-green-300' : pct >= 80 ? 'bg-amber-100 text-amber-700 dark:bg-amber-900/40 dark:text-amber-300' : 'bg-red-100 text-red-700 dark:bg-red-900/40 dark:text-red-300'}`}>
                                        {pct}%
                                      </span>
                                      <button onClick={() => setPanelId(archivo.id)} className="p-1 text-blue-500 hover:text-blue-700 dark:text-blue-400" title="Ver detalle">👁️</button>
                                      <button onClick={() => handleGuardar(archivo.id, cliente.nombre)} disabled={savingId === archivo.id}
                                        className="p-1 text-purple-500 hover:text-purple-700 dark:text-purple-400 disabled:opacity-30" title="Guardar en carpeta">
                                        {savingId === archivo.id ? '⏳' : '📁'}
                                      </button>
                                      <button onClick={() => apiClient.downloadPlanillaConciliada(archivo.id)}
                                        className="p-1 text-green-600 hover:text-green-700 dark:text-green-400" title="Descargar Excel">⬇️</button>
                                    </div>
                                  </div>
                                )
                              })}
                            </div>
                          )}
                        </div>
                      )
                    })}
                  </div>
                )}
              </div>
            )
          })}
        </div>
      )}

      <PlanillaPanel planillaId={panelId} onClose={() => setPanelId(null)} />
    </div>
  )
}
