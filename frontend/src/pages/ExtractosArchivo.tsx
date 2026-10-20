import React, { useCallback, useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { apiClient } from '@/services/api'
import { BorradorExtractoPdfResumen, ConfirmarExtractoPdfResult, ExtractoHistorialItem } from '@/types'
import { useOrgStore } from '@/store/org'
import { useAuthStore } from '@/store/auth'
import { useLockStore } from '@/store/lock'
import { confirmDialog } from '@/store/confirm'
import { toast } from '@/store/toast'
import { ImportarExtractoPdfModal } from '@/components/extractos/ImportarExtractoPdfModal'

const MESES = ['Enero','Febrero','Marzo','Abril','Mayo','Junio','Julio','Agosto','Septiembre','Octubre','Noviembre','Diciembre']

function fmtDatetime(s: string) {
  try {
    const d = new Date(s.endsWith('Z') ? s : s + 'Z')
    return d.toLocaleString('es-AR', { day: '2-digit', month: '2-digit', year: 'numeric', hour: '2-digit', minute: '2-digit' })
  } catch { return s }
}

interface GroupMes   { mes: number; label: string; items: ExtractoHistorialItem[] }
interface GroupAnio  { anio: number; meses: GroupMes[] }
interface GroupBanco { banco: string; anios: GroupAnio[] }

function agrupar(items: ExtractoHistorialItem[]): GroupBanco[] {
  const map: Record<string, Record<number, Record<number, ExtractoHistorialItem[]>>> = {}
  for (const e of items) {
    const banco = e.banco || 'Banco Macro'
    const d = new Date(e.fecha_creacion.endsWith('Z') ? e.fecha_creacion : e.fecha_creacion + 'Z')
    const anio = d.getFullYear()
    const mes  = d.getMonth() + 1
    if (!map[banco]) map[banco] = {}
    if (!map[banco][anio]) map[banco][anio] = {}
    if (!map[banco][anio][mes]) map[banco][anio][mes] = []
    map[banco][anio][mes].push(e)
  }
  return Object.keys(map).sort().map(banco => ({
    banco,
    anios: Object.keys(map[banco]).map(Number).sort((a, b) => b - a).map(anio => ({
      anio,
      meses: Object.keys(map[banco][anio]).map(Number).sort((a, b) => b - a).map(mes => ({
        mes,
        label: `${MESES[mes - 1]} ${anio}`,
        items: map[banco][anio][mes],
      }))
    }))
  }))
}

const PENDIENTE_ESTADO: Record<string, { label: string; cls: string }> = {
  procesando: { label: 'Leyendo…', cls: 'badge-info' },
  listo: { label: 'Para revisar', cls: 'badge-warn' },
  error: { label: 'No se pudo leer', cls: 'badge-error' },
}

const fmtFechaAr = (iso: string | null) => (iso ? iso.split('-').reverse().join('/') : '')

export const ExtractosArchivo: React.FC = () => {
  const navigate = useNavigate()
  const { activeOrgId } = useOrgStore()
  const canUpload = useAuthStore(s => s.hasPermission('upload_files'))
  const [items, setItems]         = useState<ExtractoHistorialItem[]>([])
  const [loading, setLoading]     = useState(true)
  const [openBancos, setOpenBancos] = useState<Set<string>>(new Set())
  const [openAnios, setOpenAnios] = useState<Set<string>>(new Set())   // `${banco}-${anio}`
  const [openMeses, setOpenMeses] = useState<Set<string>>(new Set())   // `${banco}-${anio}-${mes}`
  const [dlError, setDlError]     = useState('')
  const [dlLoading, setDlLoading] = useState<number | null>(null)
  const [renamingId, setRenamingId]     = useState<number | null>(null)
  const [renameVal, setRenameVal]       = useState('')
  const [renameSaving, setRenameSaving] = useState(false)
  const renameRef                       = useRef<HTMLInputElement>(null)

  // ── Importar extracto en PDF ────────────────────────────────────────
  const [modalPdf, setModalPdf] = useState<{ file: File | null; borradorId: number | null } | null>(null)
  const [pendientes, setPendientes] = useState<BorradorExtractoPdfResumen[]>([])
  const [pdfMsg, setPdfMsg] = useState('')
  const pdfInputRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    apiClient.getHistorialExtractos({ limit: 200, org_id: activeOrgId }).then(d => {
      setItems(d.items)
      const grupos = agrupar(d.items)
      if (grupos.length > 0) {
        const gb = grupos[0]
        setOpenBancos(new Set([gb.banco]))
        if (gb.anios.length > 0) {
          const ga = gb.anios[0]
          setOpenAnios(new Set([`${gb.banco}-${ga.anio}`]))
          if (ga.meses.length > 0) {
            setOpenMeses(new Set([`${gb.banco}-${ga.anio}-${ga.meses[0].mes}`]))
          }
        }
      }
      setLoading(false)
    }).catch(() => setLoading(false))
  }, [activeOrgId])

  const cargarPendientes = useCallback(async () => {
    if (!canUpload) { setPendientes([]); return }
    try {
      const r = await apiClient.getBorradoresExtractoPdf(activeOrgId)
      setPendientes(r.items)
    } catch { /* es un extra: si falla, la lista queda como estaba */ }
  }, [activeOrgId, canUpload])

  useEffect(() => { void cargarPendientes() }, [cargarPendientes])

  // Mientras alguno se está leyendo con IA, se refresca solo.
  const hayLeyendo = pendientes.some(p => p.estado === 'procesando')
  useEffect(() => {
    if (!hayLeyendo) return
    const t = setInterval(() => { void cargarPendientes() }, 4000)
    return () => clearInterval(t)
  }, [hayLeyendo, cargarPendientes])

  const elegirPdf = () => {
    // El selector de archivos le saca el foco a la app: sin esto el PIN la bloquea al volver.
    try { useLockStore.getState().suppressLock() } catch { /* noop */ }
    pdfInputRef.current?.click()
  }

  const onPdfElegido = (e: React.ChangeEvent<HTMLInputElement>) => {
    const f = e.target.files?.[0]
    e.target.value = ''
    if (!f) return
    if (!/\.pdf$/i.test(f.name) && f.type !== 'application/pdf') {
      setDlError('El archivo tiene que ser un PDF.')
      return
    }
    setDlError('')
    setPdfMsg('')
    setModalPdf({ file: f, borradorId: null })
  }

  const descartarPendiente = async (p: BorradorExtractoPdfResumen) => {
    const ok = await confirmDialog({
      title: 'Descartar este PDF',
      message: `«${p.nombre_archivo}» no se guarda. Si lo necesitás más adelante, tenés que volver a subirlo.`,
      confirmLabel: 'Descartar',
      danger: true,
    })
    if (!ok) return
    try {
      await apiClient.descartarBorradorExtractoPdf(p.id, activeOrgId)
      setPendientes(prev => prev.filter(x => x.id !== p.id))
    } catch (err: any) {
      toast.error(err.response?.data?.detail || 'No se pudo descartar el PDF.')
    }
  }

  // Después de guardar: trae la lista de nuevo y abre el grupo donde cayó el extracto nuevo.
  const onPdfGuardado = async (r: ConfirmarExtractoPdfResult) => {
    setPdfMsg(r.mensaje || 'Extracto guardado')
    try {
      const d = await apiClient.getHistorialExtractos({ limit: 200, org_id: activeOrgId })
      setItems(d.items)
      for (const gb of agrupar(d.items)) {
        for (const ga of gb.anios) {
          for (const gm of ga.meses) {
            if (gm.items.some(x => x.id === r.extracto_id)) {
              setOpenBancos(prev => new Set(prev).add(gb.banco))
              setOpenAnios(prev => new Set(prev).add(`${gb.banco}-${ga.anio}`))
              setOpenMeses(prev => new Set(prev).add(`${gb.banco}-${ga.anio}-${gm.mes}`))
            }
          }
        }
      }
    } catch { /* se actualiza al recargar la página */ }
  }

  const toggle = <T extends string | number>(set: Set<T>, val: T): Set<T> => {
    const n = new Set(set); n.has(val) ? n.delete(val) : n.add(val); return n
  }

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

  const [archLoading, setArchLoading] = useState<number | null>(null)

  const handleArchivar = async (e: ExtractoHistorialItem) => {
    setDlError('')
    setArchLoading(e.id)
    try {
      if (e.archivado) {
        await apiClient.desarchivarExtracto(e.id)
      } else {
        await apiClient.archivarExtracto(e.id)
      }
      setItems(prev => prev.map(x => x.id === e.id ? { ...x, archivado: !e.archivado } : x))
    } catch (err: any) {
      setDlError(err.response?.data?.detail || 'No se pudo cambiar el estado del extracto.')
    }
    setArchLoading(null)
  }

  const startRename = (e: ExtractoHistorialItem) => {
    setRenamingId(e.id)
    setRenameVal(e.nombre_archivo)
    setTimeout(() => { renameRef.current?.focus(); renameRef.current?.select() }, 50)
  }

  const cancelRename = () => { setRenamingId(null); setRenameVal('') }

  const saveRename = async (id: number) => {
    const nombre = renameVal.trim()
    if (!nombre) return
    setRenameSaving(true)
    try {
      await apiClient.client.patch(`/extractos/${id}/renombrar`, { nombre })
      setItems(prev => prev.map(x => x.id === id ? { ...x, nombre_archivo: nombre } : x))
      setRenamingId(null)
    } catch { /* silencioso — el nombre queda como estaba */ }
    setRenameSaving(false)
  }

  const grupos = agrupar(items)

  return (
    <div className="p-4 md:p-6 max-w-4xl mx-auto">
      <div className="flex flex-wrap items-center gap-3 mb-6">
        <div className="min-w-0 flex-1">
          <h1 className="text-xl font-bold text-ml-text dark:text-white">Archivo de Extractos</h1>
          <p className="text-xs text-gray-500 dark:text-gray-400 mt-0.5">
            Organizados por banco · año · mes — descargá el conciliado en cualquier momento
          </p>
        </div>
        {canUpload && (
          <>
            <button type="button" onClick={elegirPdf} className="btn-primary shrink-0">
              Importar PDF
            </button>
            <input ref={pdfInputRef} type="file" hidden accept=".pdf,application/pdf" onChange={onPdfElegido} aria-label="Elegir el PDF del extracto" />
          </>
        )}
      </div>

      {pdfMsg && (
        <div role="status" className="mb-4 px-4 py-2 bg-green-50 dark:bg-green-900/20 border border-green-200 dark:border-green-800 rounded-lg text-sm text-green-700 dark:text-green-400">
          {pdfMsg}
        </div>
      )}

      {pendientes.length > 0 && (
        <section aria-label="PDF por revisar" className="mb-6 border border-amber-200 dark:border-amber-500/30 rounded-xl overflow-hidden">
          <h2 className="px-4 py-2.5 text-sm font-semibold bg-amber-50 dark:bg-amber-500/10 text-amber-900 dark:text-amber-200">
            PDF por revisar ({pendientes.length})
          </h2>
          <ul className="divide-y divide-gray-100 dark:divide-slate-700">
            {pendientes.map(p => {
              const est = PENDIENTE_ESTADO[p.estado] ?? { label: p.estado, cls: 'badge-neutral' }
              const detalle = [
                p.banco,
                p.periodo_desde && p.periodo_hasta ? `${fmtFechaAr(p.periodo_desde)} al ${fmtFechaAr(p.periodo_hasta)}` : null,
                p.estado === 'listo' ? `${p.cantidad.toLocaleString('es-AR')} movimientos` : null,
              ].filter(Boolean).join(' · ')
              return (
                <li key={p.id} className="flex flex-wrap items-center gap-x-3 gap-y-2 px-4 py-2.5">
                  <div className="min-w-0 flex-1 basis-48">
                    <p className="text-xs font-medium text-ml-text dark:text-gray-200 truncate" title={p.nombre_archivo}>{p.nombre_archivo}</p>
                    <p className="text-[11px] text-gray-500 dark:text-gray-400 truncate">
                      {p.estado === 'error' && p.error ? p.error : detalle || 'Todavía sin datos'}
                    </p>
                  </div>
                  <span className={est.cls}>{est.label}</span>
                  <div className="flex gap-1.5">
                    <button
                      type="button"
                      onClick={() => setModalPdf({ file: null, borradorId: p.id })}
                      className="px-2.5 py-1 text-[11px] text-ml-blue border border-ml-blue/30 rounded-md hover:bg-ml-blue/5 dark:hover:bg-ml-blue/10 transition-colors whitespace-nowrap"
                      aria-label={`Revisar ${p.nombre_archivo}`}
                    >
                      Revisar
                    </button>
                    <button
                      type="button"
                      onClick={() => descartarPendiente(p)}
                      className="px-2.5 py-1 text-[11px] text-gray-500 border border-gray-300 dark:border-ml-dark-border rounded-md hover:bg-gray-50 dark:hover:bg-ml-dark-hover transition-colors whitespace-nowrap"
                      aria-label={`Descartar ${p.nombre_archivo}`}
                    >
                      Descartar
                    </button>
                  </div>
                </li>
              )
            })}
          </ul>
        </section>
      )}

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
        <div className="space-y-3">
          {grupos.map(({ banco, anios }) => {
            const bancoOpen = openBancos.has(banco)
            const totalBanco = anios.reduce((s, a) => s + a.meses.reduce((ss, m) => ss + m.items.length, 0), 0)

            return (
              <div key={banco} className="border border-gray-200 dark:border-slate-700 rounded-xl overflow-hidden">
                {/* Banco */}
                <button
                  onClick={() => setOpenBancos(toggle(openBancos, banco))}
                  className="w-full flex items-center gap-3 px-4 py-3.5 bg-ml-blue/5 dark:bg-slate-800 hover:bg-ml-blue/10 dark:hover:bg-slate-750 text-left transition-colors"
                >
                  <span className="text-base">🏦</span>
                  <span className="text-sm font-bold text-ml-text dark:text-white flex-1">
                    {bancoOpen ? '▼' : '▶'} {banco}
                  </span>
                  <span className="text-xs text-gray-400 dark:text-gray-500">
                    {totalBanco} extracto{totalBanco !== 1 ? 's' : ''}
                  </span>
                </button>

                {bancoOpen && (
                  <div className="divide-y divide-gray-100 dark:divide-slate-700">
                    {anios.map(({ anio, meses }) => {
                      const anioKey = `${banco}-${anio}`
                      const anioOpen = openAnios.has(anioKey)
                      const totalAnio = meses.reduce((s, m) => s + m.items.length, 0)

                      return (
                        <div key={anio}>
                          {/* Año */}
                          <button
                            onClick={() => setOpenAnios(toggle(openAnios, anioKey))}
                            className="w-full flex items-center gap-3 px-6 py-2.5 bg-gray-50 dark:bg-slate-800/60 hover:bg-gray-100 dark:hover:bg-slate-700/60 text-left transition-colors"
                          >
                            <span className="text-xs font-bold text-ml-text dark:text-white flex-1">
                              {anioOpen ? '▼' : '▶'} {anio}
                            </span>
                            <span className="text-[11px] text-gray-400">
                              {totalAnio} extracto{totalAnio !== 1 ? 's' : ''}
                            </span>
                          </button>

                          {anioOpen && (
                            <div className="divide-y divide-gray-50 dark:divide-slate-700/50">
                              {meses.map(({ mes, label, items: mesItems }) => {
                                const mesKey = `${banco}-${anio}-${mes}`
                                const mesOpen = openMeses.has(mesKey)
                                const acredMes = mesItems.reduce((s, e) => s + e.acreditados, 0)
                                const movsMes  = mesItems.reduce((s, e) => s + e.total_movimientos, 0)

                                return (
                                  <div key={mesKey}>
                                    {/* Mes */}
                                    <button
                                      onClick={() => setOpenMeses(toggle(openMeses, mesKey))}
                                      className="w-full flex items-center gap-3 px-8 py-2 bg-white dark:bg-slate-800/30 hover:bg-gray-50 dark:hover:bg-slate-700/40 text-left transition-colors"
                                    >
                                      <span className="text-xs font-semibold text-gray-700 dark:text-gray-200 flex-1">
                                        {mesOpen ? '▼' : '▶'} 📅 {label}
                                      </span>
                                      <span className="text-[11px] text-gray-400">
                                        {mesItems.length} archivo{mesItems.length !== 1 ? 's' : ''} · {movsMes.toLocaleString('es-AR')} movs · {acredMes} acred.
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
                                              className="flex items-center gap-3 px-10 py-2.5 border-b border-gray-50 dark:border-slate-700/50 last:border-0 hover:bg-blue-50/30 dark:hover:bg-slate-700/30 transition-colors"
                                            >
                                              <span className="text-lg select-none">📄</span>
                                              <div className="flex-1 min-w-0">
                                                {renamingId === e.id ? (
                                                  <div className="flex items-center gap-1.5">
                                                    <input
                                                      ref={renameRef}
                                                      value={renameVal}
                                                      onChange={ev => setRenameVal(ev.target.value)}
                                                      onKeyDown={ev => {
                                                        if (ev.key === 'Enter') saveRename(e.id)
                                                        if (ev.key === 'Escape') cancelRename()
                                                      }}
                                                      className="flex-1 text-xs px-2 py-1 rounded border border-ml-blue/40 bg-white dark:bg-slate-800 text-ml-text dark:text-gray-200 outline-none focus:border-ml-blue min-w-0"
                                                    />
                                                    <button onClick={() => saveRename(e.id)} disabled={renameSaving || !renameVal.trim()}
                                                      className="px-1.5 py-1 text-xs bg-ml-blue text-white rounded disabled:opacity-50">✓</button>
                                                    <button onClick={cancelRename}
                                                      className="px-1.5 py-1 text-xs text-gray-400 hover:text-gray-600 rounded">✕</button>
                                                  </div>
                                                ) : (
                                                  <div className="flex items-center gap-1 group">
                                                    <p className="text-xs font-medium text-ml-text dark:text-gray-200 truncate" title={e.nombre_archivo}>
                                                      {e.nombre_archivo}
                                                    </p>
                                                    <button onClick={() => startRename(e)}
                                                      className="opacity-0 group-hover:opacity-100 text-gray-400 hover:text-ml-blue transition-opacity text-[11px] shrink-0"
                                                      title="Renombrar">✏️</button>
                                                  </div>
                                                )}
                                                <p className="text-[10px] text-gray-400 dark:text-gray-500 mt-0.5">
                                                  Subido {fmtDatetime(e.fecha_creacion)} · {e.usuario_nombre}
                                                  {e.archivado && (
                                                    <span className="ml-1.5 px-1.5 py-0.5 rounded bg-gray-100 text-gray-500 dark:bg-ml-dark-card dark:text-gray-400 font-medium">
                                                      📦 Archivado
                                                    </span>
                                                  )}
                                                </p>
                                              </div>

                                              <div className="hidden sm:flex items-center gap-3 text-[11px]">
                                                <span className="text-gray-500 dark:text-gray-400">
                                                  {e.total_movimientos.toLocaleString('es-AR')} movs
                                                </span>
                                                <span className={`font-medium ${pct >= 80 ? 'text-green-600 dark:text-green-400' : pct >= 40 ? 'text-yellow-600 dark:text-yellow-400' : 'text-gray-400'}`}>
                                                  {e.acreditados} acred. ({pct}%)
                                                </span>
                                              </div>

                                              <div className="flex gap-1.5 ml-2">
                                                <button
                                                  onClick={() => navigate(`/movimientos?extracto=${e.id}`)}
                                                  className="px-2.5 py-1 text-[11px] text-ml-blue border border-ml-blue/30 rounded-md hover:bg-ml-blue/5 dark:hover:bg-ml-blue/10 transition-colors whitespace-nowrap"
                                                >
                                                  📊 Ver
                                                </button>
                                                <button
                                                  onClick={() => handleDownload(e)}
                                                  disabled={dlLoading === e.id}
                                                  className="px-2.5 py-1 text-[11px] bg-green-600 text-white rounded-md hover:bg-green-700 disabled:opacity-50 transition-colors whitespace-nowrap"
                                                >
                                                  {dlLoading === e.id ? '⏳' : '⬇️'} .xlsx
                                                </button>
                                                <button
                                                  onClick={() => handleArchivar(e)}
                                                  disabled={archLoading === e.id}
                                                  className="px-2.5 py-1 text-[11px] text-gray-500 border border-gray-300 dark:border-ml-dark-border rounded-md hover:bg-gray-50 dark:hover:bg-ml-dark-hover disabled:opacity-50 transition-colors whitespace-nowrap"
                                                  title={e.archivado
                                                    ? 'Reabrir este extracto (vuelve a aceptar movimientos nuevos)'
                                                    : 'Cerrar el período: queda guardado y consultable, pero no recibe más movimientos. Podés subir un extracto nuevo del banco.'}
                                                >
                                                  {archLoading === e.id ? '⏳' : e.archivado ? '↩️ Reabrir' : '📦 Archivar'}
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
          })}
        </div>
      )}

      {modalPdf && (
        <ImportarExtractoPdfModal
          file={modalPdf.file}
          borradorId={modalPdf.borradorId}
          orgId={activeOrgId}
          onCerrar={() => { setModalPdf(null); void cargarPendientes() }}
          onGuardado={onPdfGuardado}
          onAbrirExtracto={(id) => { setModalPdf(null); navigate(`/movimientos?extracto=${id}`) }}
        />
      )}
    </div>
  )
}
