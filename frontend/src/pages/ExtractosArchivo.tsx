import React, { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { apiClient } from '@/services/api'
import { ExtractoHistorialItem } from '@/types'

const MESES = ['Enero','Febrero','Marzo','Abril','Mayo','Junio','Julio','Agosto','Septiembre','Octubre','Noviembre','Diciembre']

function fmtDatetime(s: string) {
  try {
    const d = new Date(s.endsWith('Z') ? s : s + 'Z')
    return d.toLocaleString('es-AR', { day: '2-digit', month: '2-digit', year: 'numeric', hour: '2-digit', minute: '2-digit' })
  } catch { return s }
}

interface GroupMes {
  mes: number      // 1-12
  label: string
  items: ExtractoHistorialItem[]
}
interface GroupAnio {
  anio: number
  meses: GroupMes[]
}

function agrupar(items: ExtractoHistorialItem[]): GroupAnio[] {
  const map: Record<number, Record<number, ExtractoHistorialItem[]>> = {}
  for (const e of items) {
    const d = new Date(e.fecha_creacion.endsWith('Z') ? e.fecha_creacion : e.fecha_creacion + 'Z')
    const anio = d.getFullYear()
    const mes  = d.getMonth() + 1
    if (!map[anio]) map[anio] = {}
    if (!map[anio][mes]) map[anio][mes] = []
    map[anio][mes].push(e)
  }
  return Object.keys(map)
    .map(Number)
    .sort((a, b) => b - a)
    .map(anio => ({
      anio,
      meses: Object.keys(map[anio])
        .map(Number)
        .sort((a, b) => b - a)
        .map(mes => ({
          mes,
          label: `${MESES[mes - 1]} ${anio}`,
          items: map[anio][mes],
        }))
    }))
}

export const ExtractosArchivo: React.FC = () => {
  const navigate = useNavigate()
  const [items, setItems]       = useState<ExtractoHistorialItem[]>([])
  const [loading, setLoading]   = useState(true)
  const [openAnios, setOpenAnios] = useState<Set<number>>(new Set())
  const [openMeses, setOpenMeses] = useState<Set<string>>(new Set())
  const [dlError, setDlError]   = useState('')
  const [dlLoading, setDlLoading] = useState<number | null>(null)

  useEffect(() => {
    apiClient.getHistorialExtractos({ limit: 200 }).then(d => {
      setItems(d.items)
      // Abrir el año y mes más reciente por defecto
      const grupos = agrupar(d.items)
      if (grupos.length > 0) {
        const g = grupos[0]
        setOpenAnios(new Set([g.anio]))
        if (g.meses.length > 0) {
          setOpenMeses(new Set([`${g.anio}-${g.meses[0].mes}`]))
        }
      }
      setLoading(false)
    }).catch(() => setLoading(false))
  }, [])

  const toggleAnio = (anio: number) =>
    setOpenAnios(s => { const n = new Set(s); n.has(anio) ? n.delete(anio) : n.add(anio); return n })

  const toggleMes = (key: string) =>
    setOpenMeses(s => { const n = new Set(s); n.has(key) ? n.delete(key) : n.add(key); return n })

  const handleDownload = async (e: ExtractoHistorialItem) => {
    setDlError('')
    setDlLoading(e.id)
    try {
      await apiClient.exportExtractoContador(e.id)
    } catch (err: any) {
      setDlError(`Error al descargar "${e.nombre_archivo}": ${err.response?.data?.detail || err.message}`)
    }
    setDlLoading(null)
  }

  const grupos = agrupar(items)

  return (
    <div className="p-4 md:p-6 max-w-4xl mx-auto">
      <div className="flex items-center gap-3 mb-6">
        <div>
          <h1 className="text-xl font-bold text-ml-text dark:text-white">Archivo de Extractos</h1>
          <p className="text-xs text-gray-500 dark:text-gray-400 mt-0.5">
            Todos los extractos bancarios cargados, organizados por fecha · descargá el conciliado en cualquier momento
          </p>
        </div>
      </div>

      {dlError && (
        <div className="mb-4 px-4 py-2 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg text-sm text-red-700 dark:text-red-400">
          {dlError}
        </div>
      )}

      {loading ? (
        <div className="py-16 text-center text-gray-400">Cargando...</div>
      ) : grupos.length === 0 ? (
        <div className="py-16 text-center text-gray-400">
          <p className="text-4xl mb-3">🗂️</p>
          <p>Todavía no hay extractos cargados.</p>
          <button onClick={() => navigate('/dashboard')} className="mt-4 text-sm text-ml-blue hover:underline">
            Ir a cargar un extracto →
          </button>
        </div>
      ) : (
        <div className="space-y-2">
          {grupos.map(({ anio, meses }) => {
            const anioOpen = openAnios.has(anio)
            const totalAnio = meses.reduce((s, m) => s + m.items.length, 0)
            const acredAnio = meses.reduce((s, m) => s + m.items.reduce((ss, e) => ss + e.acreditados, 0), 0)

            return (
              <div key={anio} className="border border-gray-200 dark:border-slate-700 rounded-xl overflow-hidden">
                {/* Año */}
                <button
                  onClick={() => toggleAnio(anio)}
                  className="w-full flex items-center gap-3 px-4 py-3 bg-gray-50 dark:bg-slate-800 hover:bg-gray-100 dark:hover:bg-slate-750 text-left transition-colors"
                >
                  <span className="text-sm font-bold text-ml-text dark:text-white flex-1">
                    {anioOpen ? '▼' : '▶'} {anio}
                  </span>
                  <span className="text-xs text-gray-400 dark:text-gray-500">
                    {totalAnio} extracto{totalAnio !== 1 ? 's' : ''} · {acredAnio} acreditaciones
                  </span>
                </button>

                {anioOpen && (
                  <div className="divide-y divide-gray-100 dark:divide-slate-700">
                    {meses.map(({ mes, label, items: mesItems }) => {
                      const mesKey = `${anio}-${mes}`
                      const mesOpen = openMeses.has(mesKey)
                      const acredMes = mesItems.reduce((s, e) => s + e.acreditados, 0)
                      const movsMes  = mesItems.reduce((s, e) => s + e.total_movimientos, 0)

                      return (
                        <div key={mesKey}>
                          {/* Mes */}
                          <button
                            onClick={() => toggleMes(mesKey)}
                            className="w-full flex items-center gap-3 px-6 py-2.5 bg-white dark:bg-slate-800/50 hover:bg-gray-50 dark:hover:bg-slate-700/50 text-left transition-colors"
                          >
                            <span className="text-xs font-semibold text-gray-700 dark:text-gray-200 flex-1">
                              {mesOpen ? '▼' : '▶'} 📅 {label}
                            </span>
                            <span className="text-[11px] text-gray-400">
                              {mesItems.length} archivo{mesItems.length !== 1 ? 's' : ''} · {movsMes.toLocaleString('es-AR')} movimientos · {acredMes} acreditados
                            </span>
                          </button>

                          {/* Extractos del mes */}
                          {mesOpen && (
                            <div className="bg-white dark:bg-slate-900/30">
                              {mesItems.map(e => {
                                const pct = e.total_movimientos > 0
                                  ? Math.round((e.acreditados / e.total_movimientos) * 100)
                                  : 0

                                return (
                                  <div
                                    key={e.id}
                                    className="flex items-center gap-3 px-8 py-2.5 border-b border-gray-50 dark:border-slate-700/50 last:border-0 hover:bg-blue-50/30 dark:hover:bg-slate-700/30 transition-colors"
                                  >
                                    <span className="text-lg select-none">📄</span>
                                    <div className="flex-1 min-w-0">
                                      <p className="text-xs font-medium text-ml-text dark:text-gray-200 truncate" title={e.nombre_archivo}>
                                        {e.nombre_archivo}
                                      </p>
                                      <p className="text-[10px] text-gray-400 dark:text-gray-500 mt-0.5">
                                        Subido {fmtDatetime(e.fecha_creacion)} · por {e.usuario_nombre}
                                      </p>
                                    </div>

                                    {/* Stats */}
                                    <div className="hidden sm:flex items-center gap-3 text-[11px]">
                                      <span className="text-gray-500 dark:text-gray-400">
                                        {e.total_movimientos.toLocaleString('es-AR')} movs
                                      </span>
                                      <span className={`font-medium ${pct >= 80 ? 'text-green-600 dark:text-green-400' : pct >= 40 ? 'text-yellow-600 dark:text-yellow-400' : 'text-gray-400'}`}>
                                        {e.acreditados} acred. ({pct}%)
                                      </span>
                                    </div>

                                    {/* Acciones */}
                                    <div className="flex gap-1.5 ml-2">
                                      <button
                                        onClick={() => navigate(`/movimientos?extracto=${e.id}`)}
                                        className="px-2.5 py-1 text-[11px] text-ml-blue border border-ml-blue/30 rounded-md hover:bg-ml-blue/5 dark:hover:bg-ml-blue/10 transition-colors whitespace-nowrap"
                                        title="Ver movimientos"
                                      >
                                        📊 Ver
                                      </button>
                                      <button
                                        onClick={() => handleDownload(e)}
                                        disabled={dlLoading === e.id}
                                        className="px-2.5 py-1 text-[11px] bg-green-600 text-white rounded-md hover:bg-green-700 disabled:opacity-50 transition-colors whitespace-nowrap"
                                        title="Descargar extracto conciliado (.xlsx)"
                                      >
                                        {dlLoading === e.id ? '⏳' : '⬇️'} .xlsx
                                      </button>
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
    </div>
  )
}
