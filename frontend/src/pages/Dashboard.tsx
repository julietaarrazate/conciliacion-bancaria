import React, { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { FileUpload } from '@/components/FileUpload'
import { PlanillaPanel } from '@/components/PlanillaPanel'
import { apiClient } from '@/services/api'
import {
  ConciliacionResultado,
  ExtractoListItem,
  PlanillaHistorialItem
} from '@/types'

function fmtFecha(s: string) {
  if (!s) return '—'
  try {
    // El backend devuelve ISO sin timezone → parsear como local
    const d = new Date(s.endsWith('Z') ? s : s + 'Z')
    return d.toLocaleString('es-AR', { day: '2-digit', month: '2-digit', year: '2-digit', hour: '2-digit', minute: '2-digit' })
  } catch { return s }
}

export const Dashboard: React.FC = () => {
  const navigate = useNavigate()
  const [extractos, setExtractos] = useState<ExtractoListItem[]>([])
  const [planillas, setPlanillas] = useState<PlanillaHistorialItem[]>([])
  const [extractoId, setExtractoId] = useState<number | null>(null)
  const [extractoNombre, setExtractoNombre] = useState<string>('')
  const [clienteNombre, setClienteNombre] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')
  const [resultado, setResultado] = useState<ConciliacionResultado | null>(null)
  const [panelId, setPanelId] = useState<number | null>(null)

  useEffect(() => {
    apiClient.listExtractos().then((data) => {
      setExtractos(data.items)
      if (data.items.length > 0) {
        setExtractoId(data.items[0].id)
        setExtractoNombre(data.items[0].nombre_archivo)
      }
    })
    apiClient.getHistorialPlanillas({ limit: 5 }).then((d) => setPlanillas(d.items))
  }, [])

  const refreshExtractos = async () => {
    const data = await apiClient.listExtractos()
    setExtractos(data.items)
  }

  const handleDeleteExtracto = async (id: number) => {
    if (!confirm('¿Borrar este extracto? También se borran las planillas conciliadas con él.')) return
    try {
      await apiClient.deleteExtracto(id)
      const data = await apiClient.listExtractos()
      setExtractos(data.items)
      if (extractoId === id) {
        setExtractoId(data.items[0]?.id ?? null)
        setExtractoNombre(data.items[0]?.nombre_archivo ?? '')
      }
      setSuccess('Extracto eliminado')
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Error al eliminar')
    }
  }

  const handleUploadExtraco = async (file: File) => {
    setLoading(true)
    setError('')
    setSuccess('')
    try {
      const data = await apiClient.uploadExtraco(file)
      setExtractoId(data.id)
      setExtractoNombre(data.nombre_archivo)
      setSuccess(`Extracto cargado: ${data.movimientos.length} movimientos`)
      await refreshExtractos()
    } catch (err: any) {
      // Detectar duplicado (409)
      if (err.response?.status === 409) {
        const det = err.response.data?.detail
        const msg = typeof det === 'object' ? det.message : det
        const existId = typeof det === 'object' ? det.extracto_id : null
        setError(msg || 'Extracto duplicado')
        if (existId) { setExtractoId(existId); await refreshExtractos() }
      } else {
        setError(err.response?.data?.detail || 'Error al cargar extracto')
      }
    } finally {
      setLoading(false)
    }
  }

  const handleUploadUM = async (file: File) => {
    if (!extractoId) {
      setError('Cargá primero un extracto')
      return
    }
    setLoading(true)
    setError('')
    setSuccess('')
    try {
      const r = await apiClient.appendUM(extractoId, file)
      setSuccess(
        `UM procesado: ${r.agregados} nuevos · ${r.duplicados} duplicados ignorados`
      )
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Error al cargar UM')
    } finally {
      setLoading(false)
    }
  }

  const handleUploadPlanilla = async (file: File) => {
    if (!extractoId || !clienteNombre.trim()) {
      setError('Cargá primero un extracto e ingresá el cliente')
      return
    }
    setLoading(true)
    setError('')
    setSuccess('')
    setResultado(null)
    try {
      const planilla = await apiClient.uploadPlanilla(
        clienteNombre,
        extractoId,
        file
      )
      const r = await apiClient.conciliarPlanilla(planilla.id)
      setResultado(r)
      setSuccess(`Conciliación completa: ${r.acreditadas}/${r.filas_procesadas} acreditadas`)
      apiClient.getHistorialPlanillas({ limit: 5 }).then((d) => setPlanillas(d.items))
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Error en la conciliación')
    } finally {
      setLoading(false)
    }
  }

  // Stats — usa solo el extracto activo para movimientos (no sumar duplicados)
  const extractoActivo = extractos.find(e => e.id === extractoId)
  const totalMovimientos = extractoActivo?.total_movimientos ?? 0
  const totalAcreditadas = planillas.reduce((s, p) => s + p.acreditadas, 0)
  const totalProcesadas = planillas.reduce((s, p) => s + p.total_filas, 0)
  const accuracy = totalProcesadas > 0
    ? Math.round((totalAcreditadas / totalProcesadas) * 100)
    : 0

  return (
    <div className="p-6 max-w-7xl mx-auto">
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-ml-text">Conciliar transferencias</h1>
        <p className="text-ml-text-soft text-sm mt-1">
          Subí el extracto bancario y las planillas de cliente. El sistema concilia automáticamente.
        </p>
      </div>

      {/* KPIs */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
        <div className="kpi">
          <p className="kpi-label">Movimientos (extracto activo)</p>
          <p className="kpi-value">{totalMovimientos.toLocaleString('es-AR')}</p>
        </div>
        <div className="kpi">
          <p className="kpi-label">Acreditadas</p>
          <p className="kpi-value text-green-600">{totalAcreditadas}</p>
        </div>
        <div className="kpi">
          <p className="kpi-label">Precisión</p>
          <p className="kpi-value text-ml-blue">{accuracy}%</p>
        </div>
        <div className="kpi">
          <p className="kpi-label">Extractos cargados</p>
          <p className="kpi-value">{extractos.length}</p>
        </div>
      </div>

      {error && (
        <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded-md text-red-700 text-sm">
          {error}
        </div>
      )}
      {success && (
        <div className="mb-4 p-3 bg-green-50 border border-green-200 rounded-md text-green-700 text-sm">
          {success}
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        {/* Paso 1: Extracto */}
        <div className="card">
          <div className="flex items-start justify-between mb-3">
            <div>
              <span className="badge badge-info">PASO 1</span>
              <h3 className="text-base font-semibold text-ml-text mt-2">
                Extracto bancario
              </h3>
            </div>
          </div>

          {extractos.length > 0 && (
            <div className="flex gap-2 mb-3">
              <select
                className="input-field flex-1"
                value={extractoId ?? ''}
                onChange={(e) => {
                  const id = Number(e.target.value)
                  setExtractoId(id)
                  setExtractoNombre(extractos.find((x) => x.id === id)?.nombre_archivo || '')
                }}
              >
                {extractos.map((e) => (
                  <option key={e.id} value={e.id}>
                    #{e.id} · {e.nombre_archivo} ({e.total_movimientos} movs)
                  </option>
                ))}
              </select>
              {extractoId && (
                <button
                  onClick={() => handleDeleteExtracto(extractoId)}
                  className="px-2 text-red-500 hover:text-red-700 hover:bg-red-50 dark:hover:bg-red-900/20 rounded-md transition-colors"
                  title="Borrar este extracto"
                >
                  🗑️
                </button>
              )}
            </div>
          )}

          <FileUpload
            onFileSelected={handleUploadExtraco}
            label="Subir nuevo extracto (.xlsx)"
          />

          {extractoId && (
            <>
              <button
                onClick={() => navigate(`/movimientos?extracto=${extractoId}`)}
                className="w-full mt-2 flex items-center justify-center gap-2 px-3 py-2 text-sm text-ml-blue border border-ml-blue rounded-md hover:bg-ml-blue/5 dark:hover:bg-ml-blue/10 transition-colors"
              >
                📊 Ver y filtrar movimientos
              </button>
              <div className="mt-3 pt-3 border-t border-gray-100 dark:border-slate-700">
                <p className="text-xs text-ml-text-soft dark:text-gray-400 mb-2">
                  ¿Tenés Últimos Movimientos del banco? Sumalos sin duplicar:
                </p>
                <FileUpload onFileSelected={handleUploadUM} label="+ Agregar UM" />
              </div>
            </>
          )}
        </div>

        {/* Paso 2: Cliente + Planilla */}
        <div className="card">
          <div className="mb-3">
            <span className="badge badge-info">PASO 2</span>
            <h3 className="text-base font-semibold text-ml-text mt-2">
              Cliente y planilla
            </h3>
          </div>

          <div className="mb-3">
            <label className="label">Nombre del cliente</label>
            <input
              type="text"
              className="input-field"
              placeholder="Green, Tucu, David, Alojando..."
              value={clienteNombre}
              onChange={(e) => setClienteNombre(e.target.value)}
              disabled={!extractoId}
            />
          </div>

          <FileUpload
            onFileSelected={handleUploadPlanilla}
            label={
              !extractoId
                ? 'Cargá primero un extracto'
                : !clienteNombre.trim()
                ? 'Ingresá el cliente primero'
                : 'Subir planilla del cliente (.xlsx)'
            }
          />
        </div>

        {/* Paso 3: Resultado */}
        <div className="card">
          <div className="mb-3">
            <span className="badge badge-info">PASO 3</span>
            <h3 className="text-base font-semibold text-ml-text mt-2">
              Resultado
            </h3>
          </div>

          {resultado ? (
            <div className="space-y-2">
              <div className="flex justify-between p-2 bg-green-50 rounded">
                <span className="text-sm">Acreditadas</span>
                <span className="font-bold text-green-700">{resultado.acreditadas}</span>
              </div>
              <div className="flex justify-between p-2 bg-red-50 rounded">
                <span className="text-sm">No encontradas</span>
                <span className="font-bold text-red-700">{resultado.no_encontradas}</span>
              </div>
              <div className="flex justify-between p-2 bg-yellow-50 rounded">
                <span className="text-sm">Duplicadas</span>
                <span className="font-bold text-yellow-700">{resultado.duplicadas}</span>
              </div>
              <div className="flex justify-between p-2 bg-blue-50 rounded">
                <span className="text-sm">Sin datos</span>
                <span className="font-bold text-blue-700">{resultado.sin_datos}</span>
              </div>
              <div className="pt-2 border-t border-gray-100 text-xs text-ml-text-soft text-center">
                Total procesadas: {resultado.filas_procesadas} filas
              </div>
            </div>
          ) : (
            <p className="text-sm text-ml-text-soft py-8 text-center">
              Esperando carga de planilla...
            </p>
          )}
        </div>
      </div>

      {/* Reconciliaciones recientes */}
      {planillas.length > 0 && (
        <div className="card mt-6 p-0 overflow-hidden">
          <div className="px-5 py-3 border-b border-gray-100 dark:border-slate-700 bg-ml-gray-bg dark:bg-slate-900 flex justify-between items-center">
            <h3 className="text-sm font-semibold text-ml-text dark:text-white">
              Reconciliaciones recientes
            </h3>
            <span className="text-xs text-ml-text-soft dark:text-gray-400">
              Hacé clic en una fila para ver el detalle
            </span>
          </div>
          <table className="w-full text-sm">
            <thead className="bg-white dark:bg-slate-800 border-b border-gray-100 dark:border-slate-700">
              <tr>
                <th className="px-4 py-2 text-left text-xs font-semibold text-ml-text-soft uppercase">Cliente</th>
                <th className="px-4 py-2 text-left text-xs font-semibold text-ml-text-soft uppercase">Fecha</th>
                <th className="px-4 py-2 text-center text-xs font-semibold text-ml-text-soft uppercase">Total</th>
                <th className="px-4 py-2 text-center text-xs font-semibold text-green-700 uppercase">OK</th>
                <th className="px-4 py-2 text-center text-xs font-semibold text-red-700 uppercase">Error</th>
                <th className="px-4 py-2 text-left text-xs font-semibold text-ml-text-soft uppercase">%</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100 dark:divide-slate-700">
              {planillas.map((p) => {
                const errores = p.no_encontradas + p.duplicadas + p.sin_datos
                const acc = p.total_filas > 0 ? Math.round((p.acreditadas / p.total_filas) * 100) : 0
                return (
                  <tr
                    key={p.id}
                    onClick={() => setPanelId(p.id)}
                    className="hover:bg-ml-gray-bg dark:hover:bg-slate-700/50 cursor-pointer transition-colors"
                  >
                    <td className="px-4 py-2.5 font-medium text-ml-text dark:text-white">{p.cliente_nombre}</td>
                    <td className="px-4 py-2.5 text-ml-text-soft dark:text-gray-400 whitespace-nowrap">
                      {fmtFecha(p.fecha_carga)}
                    </td>
                    <td className="px-4 py-2.5 text-center dark:text-gray-300">{p.total_filas}</td>
                    <td className="px-4 py-2.5 text-center text-green-600 dark:text-green-400 font-bold">
                      {p.acreditadas}
                    </td>
                    <td className="px-4 py-2.5 text-center text-red-600 dark:text-red-400 font-bold">
                      {errores || '—'}
                    </td>
                    <td className="px-4 py-2.5">
                      <span className={`badge ${acc === 100 ? 'badge-ok' : acc >= 80 ? 'badge-warn' : 'badge-error'}`}>
                        {acc === 100 ? '✓' : `${acc}%`}
                      </span>
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      )}

      {/* Panel deslizante de detalle */}
      <PlanillaPanel
        planillaId={panelId}
        onClose={() => setPanelId(null)}
        onDelete={async (id) => {
          await apiClient.deletePlanilla(id)
          setPanelId(null)
          const d = await apiClient.getHistorialPlanillas({ limit: 5 })
          setPlanillas(d.items)
        }}
      />
    </div>
  )
}
