import React, { useCallback, useEffect, useRef, useState } from 'react'
import { apiClient } from '@/services/api'
import { confirmDialog, useConfirmStore } from '@/store/confirm'
import { toast } from '@/store/toast'
import type { BorradorExtractoPdf, ConfirmarExtractoPdfResult } from '@/types'
import { RevisionExtractoPdf } from './RevisionExtractoPdf'

const CADA_MS = 2500
const FALLOS_SEGUIDOS_MAX = 5

export interface ImportarExtractoPdfModalProps {
  /** PDF recién elegido: se sube y se lee. */
  file?: File | null
  /** O bien un borrador que ya existe (de la lista "PDF por revisar"). */
  borradorId?: number | null
  orgId?: number | null
  /** Banco que se propone si la lectura no logra detectarlo. */
  bancoPorDefecto?: string
  /** Cierra la ventana sin guardar. El borrador queda pendiente para retomarlo. */
  onCerrar: () => void
  /** El extracto quedó guardado (o agregado a uno existente). La ventana se cierra sola después. */
  onGuardado: (resultado: ConfirmarExtractoPdfResult) => void
  /** Abrir un extracto ya cargado (para los "ya importado"). */
  onAbrirExtracto?: (extractoId: number) => void
}

const errMsg = (e: unknown, fallback: string) => {
  const d = (e as { response?: { data?: { detail?: unknown } } })?.response?.data?.detail
  return typeof d === 'string' && d ? d : fallback
}

const Spinner: React.FC = () => (
  <svg className="w-8 h-8 animate-spin text-ml-blue dark:text-ml-green" viewBox="0 0 24 24" fill="none" aria-hidden="true">
    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
  </svg>
)

const Marco: React.FC<{
  subtitulo: string
  alto: boolean
  onCerrar: () => void
  children: React.ReactNode
}> = ({ subtitulo, alto, onCerrar, children }) => {
  const ref = useRef<HTMLDivElement>(null)
  useEffect(() => { ref.current?.focus() }, [])
  return (
    <div className="fixed inset-0 z-50 bg-black/50 flex items-stretch md:items-center justify-center md:p-4">
      <div
        ref={ref}
        tabIndex={-1}
        role="dialog"
        aria-modal="true"
        aria-labelledby="importar-pdf-titulo"
        className={`bg-white dark:bg-ml-dark-surface w-full md:max-w-7xl md:rounded-xl overflow-hidden flex flex-col max-h-full md:max-h-[94vh] border border-gray-200 dark:border-white/10 outline-hidden ${
          alto ? 'h-full md:h-[94vh]' : ''
        }`}
      >
        <div className="flex items-center justify-between gap-3 px-4 py-3 border-b border-gray-200 dark:border-white/10">
          <div className="min-w-0">
            <h2 id="importar-pdf-titulo" className="text-sm font-semibold text-gray-900 dark:text-gray-100">
              Importar extracto en PDF
            </h2>
            {subtitulo && <p className="text-xs text-gray-500 dark:text-gray-400 truncate">{subtitulo}</p>}
          </div>
          <button
            type="button"
            onClick={onCerrar}
            className="p-2 rounded-lg text-gray-500 hover:bg-gray-100 dark:hover:bg-white/10"
            aria-label="Cerrar"
          >
            ✕
          </button>
        </div>
        {children}
      </div>
    </div>
  )
}

const Centrado: React.FC<{ children: React.ReactNode }> = ({ children }) => (
  <div className="flex-1 flex flex-col items-center justify-center gap-4 text-center px-6 py-12">{children}</div>
)

export const ImportarExtractoPdfModal: React.FC<ImportarExtractoPdfModalProps> = ({
  file = null, borradorId = null, orgId, bancoPorDefecto, onCerrar, onGuardado, onAbrirExtracto,
}) => {
  const [borrador, setBorrador] = useState<BorradorExtractoPdf | null>(null)
  // Se incrementa cada vez que llega una lectura nueva: la revisión arranca de cero con sus datos.
  const [revision, setRevision] = useState(0)
  const [subiendo, setSubiendo] = useState(!!file || borradorId != null)
  const [fallo, setFallo] = useState('')
  const montado = useRef(true)
  const arrancado = useRef(false)
  const sucio = useRef(false)

  useEffect(() => {
    montado.current = true
    return () => { montado.current = false }
  }, [])

  // Mientras el modal está abierto la página de atrás no se desplaza.
  useEffect(() => {
    const previo = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    return () => { document.body.style.overflow = previo }
  }, [])

  const adoptar = useCallback((b: BorradorExtractoPdf) => {
    setBorrador(b)
    setRevision(r => r + 1)
  }, [])

  const subir = useCallback(async (forzarIa: boolean) => {
    if (!file) return
    setSubiendo(true)
    setFallo('')
    setBorrador(null)
    try {
      const b = await apiClient.importarExtractoPdf(file, { orgId, forzarIa })
      if (montado.current) adoptar(b)
    } catch (e) {
      if (montado.current) setFallo(errMsg(e, 'No se pudo leer el PDF. Probá de nuevo en un momento.'))
    } finally {
      if (montado.current) setSubiendo(false)
    }
  }, [file, orgId, adoptar])

  const abrir = useCallback(async (id: number) => {
    setSubiendo(true)
    setFallo('')
    try {
      const b = await apiClient.getBorradorExtractoPdf(id, orgId)
      if (montado.current) adoptar(b)
    } catch (e) {
      if (montado.current) setFallo(errMsg(e, 'No se pudo abrir el PDF. Probá de nuevo en un momento.'))
    } finally {
      if (montado.current) setSubiendo(false)
    }
  }, [orgId, adoptar])

  // Arranque único (StrictMode monta dos veces: sin esto el PDF se subiría dos veces).
  useEffect(() => {
    if (arrancado.current) return
    arrancado.current = true
    if (file) void subir(false)
    else if (borradorId != null) void abrir(borradorId)
    else { setSubiendo(false); setFallo('No hay ningún PDF para importar.') }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  // Mientras la IA lee (o alguien más está guardando) se consulta el borrador cada pocos segundos.
  const estado = borrador?.estado
  const idBorrador = borrador?.id
  useEffect(() => {
    if (idBorrador == null || (estado !== 'procesando' && estado !== 'confirmando')) return
    let activo = true
    let fallos = 0
    let timer: ReturnType<typeof setTimeout>
    const tick = async () => {
      try {
        const b = await apiClient.getBorradorExtractoPdf(idBorrador, orgId)
        if (!activo) return
        fallos = 0
        adoptar(b)
        if (b.estado === 'procesando' || b.estado === 'confirmando') timer = setTimeout(tick, CADA_MS)
      } catch {
        if (!activo) return
        fallos += 1
        if (fallos >= FALLOS_SEGUIDOS_MAX) {
          setFallo('Perdimos la conexión con el servidor. La lectura sigue en curso: encontrá el PDF en «PDF por revisar» dentro de un rato.')
          return
        }
        timer = setTimeout(tick, CADA_MS)
      }
    }
    timer = setTimeout(tick, CADA_MS)
    return () => { activo = false; clearTimeout(timer) }
  }, [idBorrador, estado, orgId, adoptar])

  const marcarSucio = useCallback(() => { sucio.current = true }, [])

  const pedirCerrar = useCallback(async () => {
    if (sucio.current && estado === 'listo') {
      const ok = await confirmDialog({
        title: '¿Cerrar sin guardar?',
        message: 'Perdés los cambios que hiciste en esta pantalla. El PDF queda en «PDF por revisar» para retomarlo más tarde.',
        confirmLabel: 'Cerrar',
        cancelLabel: 'Seguir editando',
      })
      if (!ok) return
    }
    onCerrar()
  }, [estado, onCerrar])

  // Escape cierra, salvo que haya un diálogo de confirmación encima.
  const pedirCerrarRef = useRef(pedirCerrar)
  pedirCerrarRef.current = pedirCerrar
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key !== 'Escape' || useConfirmStore.getState().open) return
      void pedirCerrarRef.current()
    }
    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  }, [])

  const leerConIa = useCallback(async () => {
    if (sucio.current) {
      const ok = await confirmDialog({
        title: 'Leer de nuevo con IA',
        message: 'Se pierden los cambios que hiciste en esta pantalla.',
        confirmLabel: 'Leer con IA',
      })
      if (!ok) return
    }
    sucio.current = false
    await subir(true)
  }, [subir])

  const descartar = useCallback(async () => {
    if (!borrador) return
    const ok = await confirmDialog({
      title: 'Descartar este PDF',
      message: 'No se guarda ningún movimiento. Si lo necesitás más adelante, tenés que volver a subirlo.',
      confirmLabel: 'Descartar',
      danger: true,
    })
    if (!ok) return
    try {
      await apiClient.descartarBorradorExtractoPdf(borrador.id, orgId)
      sucio.current = false
      toast.info('Descartaste el PDF.')
      onCerrar()
    } catch (e) {
      toast.error(errMsg(e, 'No se pudo descartar el PDF.'))
    }
  }, [borrador, orgId, onCerrar])

  const guardado = useCallback((r: ConfirmarExtractoPdfResult) => {
    sucio.current = false
    onGuardado(r)
    onCerrar()
  }, [onGuardado, onCerrar])

  const subtitulo = file?.name || borrador?.nombre_archivo || ''
  const puedeLeerConIa = !!file && !!borrador?.ia_disponible && borrador.metodo !== 'ia'
  const revisando = !subiendo && !fallo && borrador?.estado === 'listo'

  return (
    <Marco subtitulo={subtitulo} alto={revisando} onCerrar={pedirCerrar}>
      {subiendo && (
        <Centrado>
          <Spinner />
          <p className="text-sm text-gray-700 dark:text-gray-200">
            {file ? 'Subiendo y leyendo el PDF…' : 'Abriendo el PDF…'}
          </p>
        </Centrado>
      )}

      {!subiendo && fallo && (
        <Centrado>
          <p role="alert" className="max-w-md text-sm text-red-700 dark:text-red-300">{fallo}</p>
          <div className="flex gap-2">
            <button type="button" className="btn-secondary" onClick={pedirCerrar}>Cerrar</button>
            {file && !borrador && (
              <button type="button" className="btn-primary" onClick={() => void subir(false)}>Probar de nuevo</button>
            )}
          </div>
        </Centrado>
      )}

      {!subiendo && !fallo && borrador?.estado === 'procesando' && (
        <Centrado>
          <Spinner />
          <div className="space-y-1">
            <p className="text-sm font-medium text-gray-900 dark:text-gray-100">Leyendo el PDF con IA…</p>
            <p className="text-xs text-gray-500 dark:text-gray-400 max-w-sm">
              Puede tardar hasta un minuto. Podés cerrar esta ventana: sigue leyendo y lo encontrás después en «PDF por revisar».
            </p>
          </div>
          <button type="button" className="btn-secondary" onClick={pedirCerrar}>Cerrar y seguir después</button>
        </Centrado>
      )}

      {!subiendo && !fallo && borrador?.estado === 'confirmando' && (
        <Centrado>
          <Spinner />
          <p className="text-sm text-gray-700 dark:text-gray-200">Se está guardando este extracto…</p>
        </Centrado>
      )}

      {!subiendo && !fallo && borrador?.estado === 'error' && (
        <Centrado>
          <p role="alert" className="max-w-md text-sm text-red-700 dark:text-red-300">
            {borrador.error || 'No se pudo leer el PDF.'}
          </p>
          {borrador.alertas.length > 0 && (
            <ul className="max-w-md text-xs text-gray-600 dark:text-gray-300 space-y-1">
              {borrador.alertas.map((a, i) => <li key={`${a.codigo}-${i}`}>{a.mensaje}</li>)}
            </ul>
          )}
          <div className="flex flex-wrap justify-center gap-2">
            <button type="button" className="btn-secondary" onClick={descartar}>Descartar</button>
            {file && <button type="button" className="btn-secondary" onClick={() => void subir(false)}>Probar de nuevo</button>}
            {puedeLeerConIa && <button type="button" className="btn-primary" onClick={() => void subir(true)}>Leer con IA</button>}
            {!file && <button type="button" className="btn-primary" onClick={pedirCerrar}>Cerrar</button>}
          </div>
          {!file && (
            <p className="text-xs text-gray-500 dark:text-gray-400 max-w-sm">
              Para volver a leerlo, descartá este borrador y subí el PDF de nuevo.
            </p>
          )}
        </Centrado>
      )}

      {!subiendo && !fallo && borrador?.estado === 'confirmado' && (
        <Centrado>
          <p className="text-sm font-medium text-gray-900 dark:text-gray-100">Este PDF ya está importado.</p>
          <div className="flex gap-2">
            <button type="button" className="btn-secondary" onClick={pedirCerrar}>Cerrar</button>
            {borrador.extracto_id != null && onAbrirExtracto && (
              <button type="button" className="btn-primary" onClick={() => onAbrirExtracto(borrador.extracto_id as number)}>
                Abrir el extracto
              </button>
            )}
          </div>
        </Centrado>
      )}

      {!subiendo && !fallo && borrador?.estado === 'descartado' && (
        <Centrado>
          <p className="text-sm text-gray-700 dark:text-gray-200">Este PDF ya fue descartado.</p>
          <button type="button" className="btn-secondary" onClick={pedirCerrar}>Cerrar</button>
        </Centrado>
      )}

      {revisando && borrador && (
        <RevisionExtractoPdf
          key={revision}
          borrador={borrador}
          file={file}
          orgId={orgId}
          bancoPorDefecto={bancoPorDefecto}
          puedeLeerConIa={puedeLeerConIa}
          onLeerConIa={leerConIa}
          onDescartar={descartar}
          onGuardado={guardado}
          onAbrirExtracto={onAbrirExtracto}
          onDirty={marcarSucio}
        />
      )}
    </Marco>
  )
}
