import React, { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { FileUpload } from '@/components/FileUpload'
import { PlanillaPanel } from '@/components/PlanillaPanel'
import { apiClient } from '@/services/api'
import { useOrgStore } from '@/store/org'
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
  const { activeOrgId, activeOrgNombre } = useOrgStore()
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
  const [fechaAcred, setFechaAcred] = useState<string>(
    new Date().toISOString().split('T')[0]
  )
  const [umCorteDetectado, setUmCorteDetectado] = useState<number | null>(null)
  const [umCorteManual, setUmCorteManual] = useState<string>('')
  const [umFile, setUmFile] = useState<File | null>(null)

  // ── Carga masiva ──────────────────────────────────────────────
  interface BulkItem {
    id: string; file: File; clienteNombre: string
    status: 'pending' | 'loading' | 'ok' | 'error'
    resultado?: ConciliacionResultado; error?: string
  }
  const [tab, setTab] = useState<'individual' | 'masiva'>('individual')
  const [bulkItems, setBulkItems] = useState<BulkItem[]>([])
  const [bulkRunning, setBulkRunning] = useState(false)
  const [bulkFecha, setBulkFecha] = useState(new Date().toISOString().split('T')[0])

  const handleBulkFiles = (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = Array.from(e.target.files || [])
    setBulkItems(prev => [...prev, ...files.map(f => ({
      id: `${f.name}-${Date.now()}-${Math.random()}`,
      file: f,
      clienteNombre: f.name.replace(/\.[^.]+$/, '').replace(/[_-]/g, ' ').trim(),
      status: 'pending' as const
    }))])
    e.target.value = ''
  }
  const updateBulkItem = (id: string, patch: Partial<BulkItem>) =>
    setBulkItems(prev => prev.map(it => it.id === id ? { ...it, ...patch } : it))
  const handleBulkRun = async () => {
    if (!extractoId || bulkItems.length === 0) return
    setBulkRunning(true)
    for (const item of bulkItems) {
      if (item.status === 'ok') continue
      updateBulkItem(item.id, { status: 'loading', error: undefined })
      try {
        const planilla = await apiClient.uploadPlanilla(item.clienteNombre, extractoId, item.file)
        const resultado = await apiClient.conciliarPlanilla(planilla.id, bulkFecha)
        updateBulkItem(item.id, { status: 'ok', resultado })
      } catch (err: any) {
        updateBulkItem(item.id, { status: 'error', error: err.response?.data?.detail || 'Error' })
      }
    }
    setBulkRunning(false)
    apiClient.getHistorialPlanillas({ limit: 5, org_id: activeOrgId }).then(d => setPlanillas(d.items))
  }
  const bulkPendingCount = bulkItems.filter(i => i.status === 'pending' || i.status === 'error').length
  const bulkOkCount = bulkItems.filter(i => i.status === 'ok').length
  const bulkTotalAcred = bulkItems.reduce((s, i) => s + (i.resultado?.acreditadas || 0), 0)
  const bulkTotalFilas = bulkItems.reduce((s, i) => s + (i.resultado?.filas_procesadas || 0), 0)

  useEffect(() => {
    setExtractoId(null)
    setExtractoNombre('')
    apiClient.listExtractos(activeOrgId).then((data) => {
      setExtractos(data.items)
      if (data.items.length > 0) {
        setExtractoId(data.items[0].id)
        setExtractoNombre(data.items[0].nombre_archivo)
      }
    })
    apiClient.getHistorialPlanillas({ limit: 5, org_id: activeOrgId }).then((d) => setPlanillas(d.items))
  }, [activeOrgId])

  const refreshExtractos = async () => {
    const data = await apiClient.listExtractos()
    setExtractos(data.items)
  }

  const handleDeleteExtracto = async (id: number) => {
    if (!confirm('¿Borrar este extracto?\n\nLos movimientos se eliminan, pero las planillas conciliadas quedan conservadas como historial (no se borran).')) return
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

  const handleLimpiarTodo = async () => {
    const confirmacion = window.prompt('⚠️ PELIGRO: Esto borra TODOS los extractos, movimientos y planillas.\n\nEscribí BORRAR para confirmar:')
    if (confirmacion !== 'BORRAR') return
    try {
      const r = await apiClient.deleteTodosExtractos()
      setExtractos([])
      setExtractoId(null)
      setExtractoNombre('')
      setPlanillas([])
      setResultado(null)
      setSuccess(r.mensaje)
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Error al limpiar')
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

  const handleUploadUM = async (file: File, corteSaldoOverride?: number) => {
    if (!extractoId) {
      setError('Cargá primero un extracto')
      return
    }
    setLoading(true)
    setError('')
    setSuccess('')
    try {
      const r = await apiClient.appendUM(extractoId, file, corteSaldoOverride)
      setUmCorteDetectado(r.corte_saldo_detectado ?? null)
      setUmFile(file)
      const metodo = r.corte_metodo === 'manual' ? ' (corte manual)' : r.corte_metodo === 'fallback' ? ' ⚠️ corte por fallback — verificar' : ''
      setSuccess(
        r.agregados > 0
          ? `UM agregado: ${r.agregados} movimientos nuevos · ${r.duplicados} ya existían${metodo}`
          : `UM procesado: no había movimientos nuevos — ${r.duplicados} ya existían${metodo}`
      )
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Error al cargar UM')
    } finally {
      setLoading(false)
    }
  }

  const handleReintentarUMConCorteManual = async () => {
    if (!umFile) return
    const saldo = parseFloat(umCorteManual.replace(/\./g, '').replace(',', '.'))
    if (isNaN(saldo)) { setError('Ingresá un saldo válido para el corte manual'); return }
    await handleUploadUM(umFile, saldo)
    setUmCorteManual('')
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
      const r = await apiClient.conciliarPlanilla(planilla.id, fechaAcred)
      setResultado(r)
      setSuccess(`Conciliación completa: ${r.acreditadas}/${r.filas_procesadas} acreditadas`)
      apiClient.getHistorialPlanillas({ limit: 5, org_id: activeOrgId }).then((d) => setPlanillas(d.items))
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
        <h1 className="text-2xl font-bold text-ml-text dark:text-white">Conciliar transferencias</h1>
        {activeOrgId ? (
          <p className="text-sm mt-1 text-ml-green dark:text-ml-green font-mono">
            ▸ Viendo: <strong>{activeOrgNombre}</strong>
          </p>
        ) : (
          <p className="text-ml-text-soft dark:text-gray-400 text-sm mt-1">
            Subí el extracto bancario y las planillas de cliente.
          </p>
        )}
      </div>

      {/* Tabs */}
      <div className="flex gap-1 mb-6 border-b border-gray-200 dark:border-slate-700">
        {([['individual', '📄 Individual'], ['masiva', '📂 Carga masiva']] as const).map(([key, label]) => (
          <button
            key={key}
            onClick={() => setTab(key)}
            className={`px-4 py-2 text-sm font-medium border-b-2 -mb-px transition-colors ${
              tab === key
                ? 'border-ml-blue text-ml-blue dark:border-ml-green dark:text-ml-green'
                : 'border-transparent text-ml-text-soft hover:text-ml-text dark:hover:text-gray-300'
            }`}
          >{label}</button>
        ))}
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

      {tab === 'individual' && (<>
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
            <div className="mb-3">
              <div className="flex gap-2">
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
                  >🗑️</button>
                )}
              </div>
              {extractos.length > 1 && (
                <details className="mt-2">
                  <summary className="text-xs text-gray-400 dark:text-zinc-600 cursor-pointer select-none">
                    Opciones avanzadas
                  </summary>
                  <button
                    onClick={handleLimpiarTodo}
                    className="mt-1.5 text-xs text-red-600 dark:text-red-400 hover:underline block"
                  >
                    🗑️ Borrar todo ({extractos.length} extractos)
                  </button>
                </details>
              )}
            </div>
          )}

          <FileUpload
            onFileSelected={handleUploadExtraco}
            label="Subir extracto (.xlsx, .xls, .csv)"
          />

          {extractoId && (
            <>
              <button
                onClick={() => navigate(`/movimientos?extracto=${extractoId}`)}
                className="w-full mt-2 flex items-center justify-center gap-2 px-3 py-2 text-sm text-ml-blue border border-ml-blue rounded-md hover:bg-ml-blue/5 dark:hover:bg-ml-blue/10 transition-colors"
              >
                📊 Ver y filtrar movimientos
              </button>
              <button
                onClick={async () => {
                  if (!extractoId) return
                  setError('')
                  try {
                    await apiClient.exportExtractoContador(extractoId)
                  } catch (err: any) {
                    const msg = err.response?.data?.detail || err.message || 'Error al exportar'
                    setError(`Export falló: ${msg}`)
                  }
                }}
                className="w-full mt-2 flex items-center justify-center gap-2 px-3 py-2 text-sm text-green-700 dark:text-green-400 border border-green-600 dark:border-green-700 rounded-md hover:bg-green-50 dark:hover:bg-green-900/20 transition-colors font-medium"
              >
                📤 Exportar para contador (.xlsx)
              </button>
              <div className="mt-3 pt-3 border-t border-gray-100 dark:border-slate-700">
                <p className="text-xs text-ml-text-soft dark:text-gray-400 mb-2">
                  ¿Tenés Últimos Movimientos del banco? Sumalos sin duplicar:
                </p>
                <div className="flex gap-2 items-center">
                  <div className="flex-1">
                    <FileUpload onFileSelected={(f) => handleUploadUM(f)} label="+ Agregar UM" />
                  </div>
                  <button
                    onClick={async () => {
                      if (!extractoId) return
                      setLoading(true)
                      setError('')
                      try {
                        const r = await apiClient.deleteUM(extractoId)
                        setUmCorteDetectado(null)
                        setUmFile(null)
                        setSuccess(`UM limpiado: ${r.eliminados} movimientos eliminados. Ahora podés re-subir el UM.`)
                      } catch (err: any) {
                        if (err.response?.status === 409) {
                          const det = err.response.data?.detail
                          const msg = typeof det === 'object' ? det.mensaje : det
                          const total = typeof det === 'object' ? det.total : 0
                          if (confirm(`${msg}\n\n¿Borrar los ${total} movimientos UM?`)) {
                            try {
                              const r = await apiClient.deleteUM(extractoId, true)
                              setUmCorteDetectado(null)
                              setUmFile(null)
                              setSuccess(`UM limpiado: ${r.eliminados} movimientos eliminados.`)
                            } catch (e2: any) {
                              setError(e2.response?.data?.detail || 'Error al limpiar UM')
                            }
                          }
                        } else {
                          setError(err.response?.data?.detail || 'Error al limpiar UM')
                        }
                      } finally {
                        setLoading(false)
                      }
                    }}
                    className="text-xs px-2 py-1.5 text-red-500 border border-red-300 dark:border-red-800 rounded hover:bg-red-50 dark:hover:bg-red-900/20 whitespace-nowrap"
                    title="Limpiar UM para re-subir desde cero"
                  >
                    🗑 UM
                  </button>
                </div>
                {umCorteDetectado && (
                  <p className="text-xs text-ml-text-soft dark:text-gray-400 mt-2">
                    Corte detectado en saldo <span className="font-mono font-medium">${umCorteDetectado.toLocaleString('es-AR', { minimumFractionDigits: 2 })}</span>
                  </p>
                )}
                {umFile && (
                  <div className="mt-2 flex gap-2 items-center">
                    <input
                      type="text"
                      value={umCorteManual}
                      onChange={(e) => setUmCorteManual(e.target.value)}
                      placeholder="Saldo del corte manual ej: 99657675.21"
                      className="flex-1 text-xs px-2 py-1.5 rounded border border-gray-200 dark:border-slate-600 bg-white dark:bg-slate-800 text-ml-text dark:text-gray-200 focus:outline-none focus:border-ml-blue"
                    />
                    <button
                      onClick={handleReintentarUMConCorteManual}
                      className="text-xs px-3 py-1.5 bg-ml-blue text-white rounded hover:bg-ml-blue/90 whitespace-nowrap"
                    >
                      Reintentar
                    </button>
                  </div>
                )}
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

          <div className="mb-3">
            <label className="label">Fecha de acreditación</label>
            <input
              type="date"
              className="input-field font-mono"
              value={fechaAcred}
              onChange={(e) => setFechaAcred(e.target.value)}
              disabled={!extractoId}
            />
            <p className="mt-1 text-xs text-gray-400 dark:text-zinc-600">
              Con esta fecha se registran los movimientos acreditados
            </p>
          </div>

          <FileUpload
            onFileSelected={handleUploadPlanilla}
            label={!extractoId ? 'Cargá primero un extracto (Paso 1)' : 'Subir planilla (.xlsx, .xls, .csv)'}
          />
          {!clienteNombre.trim() && extractoId && (
            <p className="mt-1.5 text-xs text-amber-600 dark:text-amber-400">
              ⚠ Completá el nombre del cliente antes de subir
            </p>
          )}
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
              {[
                { label: 'Acreditadas', val: resultado.acreditadas, cls: 'bg-green-50 dark:bg-green-900/30', txt: 'text-green-700 dark:text-green-300' },
                { label: 'No encontradas', val: resultado.no_encontradas, cls: 'bg-red-50 dark:bg-red-900/30', txt: 'text-red-700 dark:text-red-300' },
                { label: 'Ya acreditadas', val: resultado.duplicadas, cls: 'bg-amber-50 dark:bg-amber-900/30', txt: 'text-amber-700 dark:text-amber-300' },
                { label: 'Faltan datos', val: resultado.sin_datos, cls: 'bg-blue-50 dark:bg-blue-900/30', txt: 'text-blue-700 dark:text-blue-300' },
              ].map(r => (
                <div key={r.label} className={`flex justify-between items-center px-3 py-2 rounded-lg ${r.cls}`}>
                  <span className={`text-sm font-medium ${r.txt}`}>{r.label}</span>
                  <span className={`text-lg font-bold ${r.txt}`}>{r.val}</span>
                </div>
              ))}
              <div className="pt-2 border-t border-gray-100 dark:border-slate-700 text-xs text-gray-500 dark:text-gray-400 text-center">
                Total: {resultado.filas_procesadas} filas procesadas
              </div>
              <button
                onClick={() => setPanelId(resultado.planilla_id)}
                className="mt-3 w-full px-3 py-2 text-sm font-medium bg-ml-blue text-white rounded-md hover:bg-ml-blue-dark transition-colors flex items-center justify-center gap-2"
                title="Ver, editar estados, corregir errores y descargar"
              >
                ✏️ Revisar y editar estados
              </button>
              <p className="text-[10px] text-gray-400 dark:text-gray-500 text-center mt-1">
                Podés cambiar cualquier estado antes de exportar al contador
              </p>
            </div>
          ) : (
            <p className="text-sm text-ml-text-soft py-8 text-center">
              Esperando carga de planilla...
            </p>
          )}
        </div>
      </div>

      {/* Conciliaciones recientes */}
      {planillas.length > 0 && (
        <div className="card mt-6 p-0 overflow-hidden">
          <div className="px-5 py-3 border-b border-gray-100 dark:border-slate-700 bg-ml-gray-bg dark:bg-slate-900 flex justify-between items-center">
            <h3 className="text-sm font-semibold text-ml-text dark:text-white">
              Conciliaciones recientes
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
      </>)}

      {/* ── Tab: Carga masiva ─────────────────────────────── */}
      {tab === 'masiva' && (
        <div className="space-y-4">
          {/* Extracto selector */}
          <div className="card">
            <label className="label">Extracto bancario</label>
            {extractos.length > 0 ? (
              <select
                className="input-field max-w-sm"
                value={extractoId ?? ''}
                onChange={e => {
                  const id = Number(e.target.value)
                  setExtractoId(id)
                  setExtractoNombre(extractos.find(x => x.id === id)?.nombre_archivo || '')
                }}
              >
                {extractos.map(e => (
                  <option key={e.id} value={e.id}>#{e.id} · {e.nombre_archivo} ({e.total_movimientos} movs)</option>
                ))}
              </select>
            ) : (
              <p className="text-sm text-amber-600 dark:text-amber-400">⚠ Cargá primero un extracto en la pestaña Individual</p>
            )}
          </div>

          {/* Fecha + drop zone */}
          <div className="card">
            <div className="flex flex-wrap gap-4 items-end mb-4">
              <div>
                <label className="label">Fecha de acreditación</label>
                <input type="date" className="input-field font-mono w-auto" value={bulkFecha} onChange={e => setBulkFecha(e.target.value)} />
              </div>
              <p className="text-xs text-gray-400 dark:text-zinc-600 pb-2">Todas las planillas se acreditarán con esta fecha</p>
            </div>
            <label className="block border-2 border-dashed border-gray-300 dark:border-slate-600 rounded-lg p-6 text-center cursor-pointer hover:border-ml-blue dark:hover:border-ml-blue transition-colors">
              <span className="text-3xl block mb-2">📂</span>
              <span className="text-sm font-medium text-ml-text dark:text-white">Clic o arrastrá las planillas aquí</span>
              <span className="text-xs text-ml-text-soft dark:text-gray-400 block mt-1">Podés seleccionar múltiples archivos a la vez</span>
              <input type="file" accept="*/*" multiple hidden onChange={handleBulkFiles} />
            </label>
          </div>

          {/* Lista de planillas */}
          {bulkItems.length > 0 && (
            <>
              <div className="card p-0 overflow-hidden">
                <div className="px-4 py-3 bg-ml-gray-bg dark:bg-slate-900 border-b dark:border-slate-700 flex justify-between items-center">
                  <span className="text-sm font-medium dark:text-white">
                    {bulkItems.length} planillas · {bulkOkCount} procesadas
                    {bulkTotalFilas > 0 && ` · ${bulkTotalAcred}/${bulkTotalFilas} acreditadas`}
                  </span>
                  <button onClick={() => setBulkItems([])} className="text-xs text-red-600 dark:text-red-400 hover:underline" disabled={bulkRunning}>
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
                    {bulkItems.map(item => (
                      <tr key={item.id} className="hover:bg-ml-gray-bg dark:hover:bg-slate-700/50">
                        <td className="px-4 py-2.5 dark:text-gray-300 max-w-[200px] truncate">{item.file.name}</td>
                        <td className="px-4 py-2.5">
                          <input
                            className="input-field !py-1 text-sm"
                            value={item.clienteNombre}
                            onChange={e => updateBulkItem(item.id, { clienteNombre: e.target.value })}
                            disabled={bulkRunning || item.status === 'ok'}
                            placeholder="Nombre cliente..."
                          />
                        </td>
                        <td className="px-4 py-2.5 text-center">
                          {item.status === 'pending' && <span className="badge badge-info">Pendiente</span>}
                          {item.status === 'loading' && <span className="badge badge-warn">⏳ Procesando</span>}
                          {item.status === 'ok' && <span className="badge badge-ok">✓ OK</span>}
                          {item.status === 'error' && <span className="badge badge-error" title={item.error}>Error</span>}
                        </td>
                        <td className="px-4 py-2.5 text-center text-xs text-ml-text-soft dark:text-gray-400">
                          {item.resultado
                            ? <span><span className="text-green-600 font-bold">{item.resultado.acreditadas}</span>/{item.resultado.filas_procesadas}</span>
                            : item.error ? <span className="text-red-500">{item.error.slice(0, 40)}</span>
                            : '—'}
                        </td>
                        <td className="px-4 py-2.5 text-center">
                          <button onClick={() => setBulkItems(prev => prev.filter(i => i.id !== item.id))} disabled={bulkRunning}
                            className="text-ml-text-soft hover:text-red-600 dark:text-gray-500 dark:hover:text-red-400 disabled:opacity-30">✕</button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <div className="flex gap-3">
                <button
                  onClick={handleBulkRun}
                  disabled={bulkRunning || bulkPendingCount === 0 || !extractoId}
                  className="btn-yellow disabled:opacity-50"
                >
                  {bulkRunning ? '⏳ Conciliando...' : `⚡ Conciliar ${bulkPendingCount} planilla${bulkPendingCount !== 1 ? 's' : ''}`}
                </button>
                {bulkOkCount > 0 && (
                  <div className="flex items-center gap-2 text-sm text-green-700 dark:text-green-400 bg-green-50 dark:bg-green-900/20 px-4 py-2 rounded-md">
                    ✓ {bulkOkCount} procesadas · {bulkTotalAcred} acreditadas de {bulkTotalFilas}
                  </div>
                )}
              </div>
            </>
          )}
        </div>
      )}
    </div>
  )
}
