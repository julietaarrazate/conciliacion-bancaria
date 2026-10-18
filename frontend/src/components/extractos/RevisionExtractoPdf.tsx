import React, { useCallback, useEffect, useId, useMemo, useRef, useState } from 'react'
import { apiClient } from '@/services/api'
import { confirmDialog } from '@/store/confirm'
import { toast } from '@/store/toast'
import type { BorradorExtractoPdf, ConfirmarExtractoPdfResult, MetodoLecturaExtractoPdf } from '@/types'
import { TOLERANCIA_CENTAVOS, aCentavos, formatearPesos } from '@/utils/saldoExtracto'
import {
  MAX_MOVIMIENTOS,
  armarPayload,
  evaluarFilas,
  filaVacia,
  filasDesdeBorrador,
  fmtFechaAr,
  formatearSaldoInput,
  type FilaForm,
} from './filasExtracto'
import { FilaMovimiento, GRILLA_FILA, type CampoFila } from './FilaMovimiento'

const PAGINA = 100

const METODO: Record<MetodoLecturaExtractoPdf, { label: string; cls: string; ayuda: string }> = {
  molde: { label: 'Formato aprendido', cls: 'badge-ok', ayuda: 'Se leyó con un formato que Cuadra ya aprendió de este banco.' },
  automatico: { label: 'Lectura automática', cls: 'badge-info', ayuda: 'Se leyó sin IA, con las columnas del PDF.' },
  ia: { label: 'Leído con IA', cls: 'badge-warn', ayuda: 'Lo leyó la IA: revisá bien los importes.' },
}

const NIVEL_ALERTA: Record<string, string> = {
  info: 'bg-blue-50 text-blue-800 dark:bg-blue-500/10 dark:text-blue-200',
  aviso: 'bg-amber-50 text-amber-800 dark:bg-amber-500/10 dark:text-amber-200',
  error: 'bg-red-50 text-red-700 dark:bg-red-500/10 dark:text-red-300',
}

const labelCls = 'block text-xs font-medium text-gray-600 dark:text-gray-400 mb-1'

const errMsg = (e: unknown, fallback: string) => {
  const d = (e as { response?: { data?: { detail?: unknown } } })?.response?.data?.detail
  return typeof d === 'string' && d ? d : fallback
}

const sinExtension = (nombre: string) => nombre.replace(/\.pdf$/i, '')

function pantallaAncha(): boolean {
  try {
    return typeof window.matchMedia === 'function' && window.matchMedia('(min-width: 1024px)').matches
  } catch {
    return false
  }
}

/** URL local del PDF que subió la persona, para mostrarlo al lado de la tabla. */
function useUrlLocal(file: File | null): string | null {
  const [url, setUrl] = useState<string | null>(null)
  useEffect(() => {
    if (!file || typeof URL === 'undefined' || typeof URL.createObjectURL !== 'function') { setUrl(null); return }
    let creada: string | null = null
    try {
      creada = URL.createObjectURL(file)
      setUrl(creada)
    } catch {
      setUrl(null)
    }
    return () => {
      if (creada && typeof URL.revokeObjectURL === 'function') URL.revokeObjectURL(creada)
    }
  }, [file])
  return url
}

interface Props {
  borrador: BorradorExtractoPdf
  /** PDF original en memoria; null si se abrió un borrador viejo (no guardamos el archivo). */
  file: File | null
  orgId?: number | null
  /** Banco a proponer cuando la lectura no pudo detectarlo. */
  bancoPorDefecto?: string
  puedeLeerConIa: boolean
  onLeerConIa: () => void
  onDescartar: () => void
  onGuardado: (r: ConfirmarExtractoPdfResult) => void
  onAbrirExtracto?: (extractoId: number) => void
  /** La persona tocó algo: al cerrar hay que avisarle que pierde los cambios. */
  onDirty: () => void
}

export const RevisionExtractoPdf: React.FC<Props> = ({
  borrador, file, orgId, bancoPorDefecto, puedeLeerConIa,
  onLeerConIa, onDescartar, onGuardado, onAbrirExtracto, onDirty,
}) => {
  const uid = useId()
  const dup = borrador.duplicado
  // Solapado con un extracto activo: se pueden agregar solo los nuevos. A uno archivado, no.
  const puedeAgregar = dup?.tipo === 'solapado' && !dup.archivado
  const cuadreServidor = borrador.cuadre

  const [filas, setFilas] = useState<FilaForm[]>(() => filasDesdeBorrador(borrador))
  // Si el saldo se dedujo de las filas lo dejamos vacío: así sigue a las ediciones.
  const [saldoInicial, setSaldoInicial] = useState(() => {
    const c = cuadreServidor && !cuadreServidor.saldo_inicial_inferido ? aCentavos(cuadreServidor.saldo_inicial) : null
    return c == null ? '' : formatearSaldoInput(c)
  })
  const [saldoFinal, setSaldoFinal] = useState(() => {
    const c = cuadreServidor && !cuadreServidor.saldo_final_inferido ? aCentavos(cuadreServidor.saldo_final) : null
    return c == null ? '' : formatearSaldoInput(c)
  })
  const [banco, setBanco] = useState(borrador.banco || bancoPorDefecto || '')
  const [nombre, setNombre] = useState(() => sinExtension(borrador.nombre_archivo))
  const [nombreTocado, setNombreTocado] = useState(false)
  const [destino, setDestino] = useState<'nuevo' | 'existente'>(puedeAgregar ? 'existente' : 'nuevo')
  const [filtro, setFiltro] = useState<'todas' | 'dudosas'>('todas')
  const [fijas, setFijas] = useState<ReadonlySet<string>>(new Set())
  const [limite, setLimite] = useState(PAGINA)
  const [guardando, setGuardando] = useState(false)
  const [errorGuardar, setErrorGuardar] = useState('')
  const [verPdf, setVerPdf] = useState(pantallaAncha)
  const [eliminada, setEliminada] = useState<{ fila: FilaForm; indice: number } | null>(null)

  const url = useUrlLocal(file)
  const filtroRef = useRef(filtro)
  filtroRef.current = filtro
  const filasRef = useRef(filas)
  filasRef.current = filas
  // Cubre todo el guardado (diálogos incluidos): un segundo toque no dispara otro envío.
  const ocupadoRef = useRef(false)

  const evaluacion = useMemo(
    () => evaluarFilas(filas, borrador.orden, saldoInicial, saldoFinal),
    [filas, borrador.orden, saldoInicial, saldoFinal],
  )
  const { cuadre } = evaluacion

  // ── Edición de filas ────────────────────────────────────────────────────
  const onCambio = useCallback((key: string, campo: CampoFila, valor: string) => {
    setFilas(prev => prev.map(f => (f.key === key ? { ...f, [campo]: valor, motivosLectura: [] } : f)))
    if (filtroRef.current === 'dudosas') setFijas(prev => (prev.has(key) ? prev : new Set(prev).add(key)))
    onDirty()
  }, [onDirty])

  const onRevisada = useCallback((key: string) => {
    setFilas(prev => prev.map(f => (f.key === key ? { ...f, motivosLectura: [] } : f)))
    onDirty()
  }, [onDirty])

  const onEliminar = useCallback((key: string) => {
    const indice = filasRef.current.findIndex(f => f.key === key)
    if (indice < 0) return
    setEliminada({ fila: filasRef.current[indice], indice })
    setFilas(prev => prev.filter(f => f.key !== key))
    onDirty()
  }, [onDirty])

  const onInsertarDebajo = useCallback((key: string) => {
    const indice = filasRef.current.findIndex(f => f.key === key)
    if (indice < 0) return
    const nueva = filaVacia(filasRef.current[indice].fecha)
    setFilas(prev => {
      const i = prev.findIndex(f => f.key === key)
      return i < 0 ? prev : [...prev.slice(0, i + 1), nueva, ...prev.slice(i + 1)]
    })
    setFijas(prev => new Set(prev).add(nueva.key))
    setLimite(l => l + 1)
    onDirty()
  }, [onDirty])

  const agregarAlFinal = () => {
    const ultima = filas[filas.length - 1]
    const nueva = filaVacia(ultima?.fecha || borrador.periodo_desde || '')
    setFilas(prev => [...prev, nueva])
    setFijas(prev => new Set(prev).add(nueva.key))
    setLimite(l => Math.max(l, filas.length + 1))
    onDirty()
  }

  const deshacerEliminar = () => {
    if (!eliminada) return
    const { fila, indice } = eliminada
    setFilas(prev => [...prev.slice(0, Math.min(indice, prev.length)), fila, ...prev.slice(Math.min(indice, prev.length))])
    setEliminada(null)
  }

  // ── Qué filas se ven ────────────────────────────────────────────────────
  const indicesVisibles = useMemo(() => {
    const out: number[] = []
    filas.forEach((f, i) => {
      const ev = evaluacion.filas[i]
      if (filtro === 'todas' || ev.errores.length > 0 || ev.avisos.length > 0 || fijas.has(f.key)) out.push(i)
    })
    return out
  }, [filas, evaluacion.filas, filtro, fijas])
  const mostradas = indicesVisibles.slice(0, limite)
  const restantes = indicesVisibles.length - mostradas.length

  // ── Veredicto del cuadre ────────────────────────────────────────────────
  const dif = cuadre.diferencia
  const veredicto: 'cierra' | 'no_cierra' | 'sin_datos' = cuadre.cierra ? 'cierra' : dif != null ? 'no_cierra' : 'sin_datos'
  const difTxt = dif != null ? formatearPesos(Math.abs(dif)) : ''
  // Los totales dan pero el saldo corrido se corta: dos errores que se compensan.
  const saltosSinDiferencia =
    !cuadre.cierra && dif != null && Math.abs(dif) <= TOLERANCIA_CENTAVOS && cuadre.filasConSalto.length > 0
  const nSaltos = cuadre.filasConSalto.length

  const sobranFilas = filas.length > MAX_MOVIMIENTOS
  const camposSaldoMal = evaluacion.saldoInicialInvalido || evaluacion.saldoFinalInvalido
  const puedeGuardar =
    !guardando && filas.length > 0 && !sobranFilas && evaluacion.filasConError === 0 && !camposSaldoMal

  const motivoBloqueo = sobranFilas
    ? `Hay más de ${MAX_MOVIMIENTOS} movimientos: dividí el PDF en períodos más cortos.`
    : filas.length === 0
      ? 'Agregá al menos un movimiento para guardar.'
      : camposSaldoMal
        ? 'El saldo inicial o el final no es un importe válido.'
        : evaluacion.filasConError > 0
          ? `Corregí ${evaluacion.filasConError === 1 ? 'la fila marcada' : `las ${evaluacion.filasConError} filas marcadas`} en rojo para poder guardar.`
          : ''

  // ── Guardar ─────────────────────────────────────────────────────────────
  const exito = (r: ConfirmarExtractoPdfResult) => {
    if (r.contabilidad_ok === false) {
      toast.warn('El extracto se guardó, pero el asiento contable falló. Revisalo en Contabilidad.')
    }
    onGuardado(r)
  }

  // Si la respuesta se cortó (cold start, red), el guardado pudo haber terminado igual.
  const recuperarTrasCorte = async () => {
    try {
      const b = await apiClient.getBorradorExtractoPdf(borrador.id, orgId)
      if (b.estado === 'confirmado' && b.extracto_id) {
        exito({
          extracto_id: b.extracto_id, destino, ya_existia: true, agregados: 0, duplicados: 0, no_agregados: 0,
          molde_aprendido: false, contabilidad_ok: true, mensaje: 'El extracto ya estaba guardado.',
        })
        return
      }
      if (b.estado === 'confirmando') {
        setErrorGuardar('Se está guardando. Esperá unos segundos y revisá en Extractos antes de volver a intentar.')
        return
      }
      setErrorGuardar('No hubo respuesta del servidor y el extracto no se guardó. Probá de nuevo.')
    } catch {
      setErrorGuardar('No hubo respuesta del servidor. Antes de volver a guardar, fijate en Extractos si ya quedó cargado.')
    }
  }

  const enviar = async (sinCuadre: boolean): Promise<void> => {
    setGuardando(true)
    setErrorGuardar('')
    let resultado: ConfirmarExtractoPdfResult | null = null
    try {
      const destinoFinal = puedeAgregar ? destino : 'nuevo'
      const payload = armarPayload({
        filas, evaluacion, saldoInicial, saldoFinal, banco,
        // El nombre solo cuenta si se crea un extracto nuevo (en uno existente no se renombra).
        nombre: nombreTocado && destinoFinal === 'nuevo' ? nombre : null,
        destino: destinoFinal,
        extractoDestinoId: dup?.extracto_id ?? null,
        confirmarSinCuadre: sinCuadre,
      })
      resultado = await apiClient.confirmarBorradorExtractoPdf(borrador.id, payload, orgId)
    } catch (e) {
      const respuesta = (e as { response?: { status?: number } })?.response
      const detalle = errMsg(e, '')
      if (respuesta?.status === 422 && !sinCuadre && /no cierra/i.test(detalle)) {
        // El servidor suma distinto que la pantalla: que decida la persona, con el número del servidor.
        setGuardando(false)
        const ok = await confirmDialog({ title: 'El saldo no cierra', message: detalle, confirmLabel: 'Guardar igual' })
        if (ok) await enviar(true)
        return
      }
      if (!respuesta) await recuperarTrasCorte()
      else setErrorGuardar(detalle || 'No se pudo guardar el extracto.')
    } finally {
      setGuardando(false)
    }
    if (resultado) exito(resultado)
  }

  const guardar = async () => {
    if (!puedeGuardar || ocupadoRef.current) return
    ocupadoRef.current = true
    try {
      if (dup && dup.tipo !== 'solapado') {
        const ok = await confirmDialog({
          title: 'Ya está importado',
          message: `Estos movimientos ya están cargados en «${dup.nombre || `extracto #${dup.extracto_id}`}». ¿Querés guardarlos de todos modos?`,
          confirmLabel: 'Guardar igual',
        })
        if (!ok) return
      }
      let sinCuadre = false
      if (!cuadre.cierra) {
        const ok = await confirmDialog({
          title: 'El saldo no cierra',
          message: saltosSinDiferencia
            ? `Los totales dan, pero el saldo no sigue en ${nSaltos} ${nSaltos === 1 ? 'fila' : 'filas'}. ¿Guardar igual?`
            : dif != null
              ? `El saldo no cierra por ${difTxt}. ¿Guardar igual?`
              : 'No se pudo verificar el saldo porque falta el saldo inicial o el final. ¿Guardar igual?',
          confirmLabel: 'Guardar igual',
        })
        if (!ok) return
        sinCuadre = true
      }
      await enviar(sinCuadre)
    } finally {
      ocupadoRef.current = false
    }
  }

  const etiquetaGuardar = guardando
    ? 'Guardando…'
    : puedeAgregar && destino === 'existente'
      ? 'Agregar los nuevos'
      : 'Guardar extracto'

  const metodo = borrador.metodo ? METODO[borrador.metodo] : null
  const periodo =
    borrador.periodo_desde && borrador.periodo_hasta
      ? `${fmtFechaAr(borrador.periodo_desde)} al ${fmtFechaAr(borrador.periodo_hasta)}`
      : ''
  const nombreDup = dup ? `«${dup.nombre || `extracto #${dup.extracto_id}`}»` : ''
  const pdfVisible = !!file && verPdf

  return (
    <>
      <div
        className={`flex-1 min-h-0 overflow-y-auto lg:overflow-hidden grid grid-cols-1 lg:grid-rows-[minmax(0,1fr)] ${
          pdfVisible ? 'lg:grid-cols-[minmax(0,2fr)_minmax(0,3fr)]' : ''
        }`}
      >
        {pdfVisible && (
          <div className="bg-gray-50 dark:bg-black/30 border-b lg:border-b-0 lg:border-r border-gray-200 dark:border-white/10 flex flex-col lg:min-h-0">
            {url ? (
              <>
                <iframe src={url} title="PDF original" className="w-full h-[50vh] lg:h-auto lg:flex-1 min-h-[320px]" />
                <a
                  href={url} target="_blank" rel="noreferrer"
                  className="px-3 py-2 text-xs text-ml-blue dark:text-ml-green hover:underline border-t border-gray-200 dark:border-white/10"
                >
                  Abrir el PDF en otra pestaña
                </a>
              </>
            ) : (
              <div className="p-6 text-sm text-gray-500 dark:text-gray-400">No se puede mostrar el PDF en este dispositivo.</div>
            )}
          </div>
        )}

        <div className="p-4 space-y-4 lg:overflow-y-auto lg:min-h-0">
          {/* Encabezado de la lectura */}
          <div className="flex flex-wrap items-center gap-x-3 gap-y-2">
            {metodo ? (
              <span className={metodo.cls} title={metodo.ayuda}>{metodo.label}</span>
            ) : (
              <span className="badge-neutral">Sin lectura</span>
            )}
            {periodo && <span className="text-xs text-gray-500 dark:text-gray-400">Período: {periodo}</span>}
            <span className="text-xs text-gray-500 dark:text-gray-400">
              {borrador.paginas} página{borrador.paginas === 1 ? '' : 's'}
            </span>
            {file && (
              <button
                type="button"
                onClick={() => setVerPdf(v => !v)}
                aria-pressed={verPdf}
                className="ml-auto text-xs text-ml-blue dark:text-ml-green hover:underline"
              >
                {verPdf ? 'Ocultar el PDF' : 'Ver el PDF'}
              </button>
            )}
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <div>
              <label className={labelCls} htmlFor={`${uid}-banco`}>Banco</label>
              <input
                id={`${uid}-banco`} className="input-field" value={banco} placeholder="Ej: Banco Galicia"
                onChange={e => { setBanco(e.target.value); onDirty() }}
              />
            </div>
            <div>
              <label className={labelCls} htmlFor={`${uid}-nombre`}>Nombre del extracto</label>
              <input
                id={`${uid}-nombre`} className="input-field" value={nombre}
                onChange={e => { setNombre(e.target.value); setNombreTocado(true); onDirty() }}
                disabled={puedeAgregar && destino === 'existente'}
              />
            </div>
          </div>

          {/* Alertas de la lectura */}
          {borrador.alertas.length > 0 && (
            <ul className="space-y-1.5" aria-label="Avisos de la lectura">
              {borrador.alertas.map((a, i) => (
                <li key={`${a.codigo}-${i}`} className={`px-3 py-2 rounded-lg text-sm ${NIVEL_ALERTA[a.nivel] || NIVEL_ALERTA.aviso}`}>
                  {a.mensaje}
                </li>
              ))}
            </ul>
          )}

          {/* Duplicados */}
          {dup && (
            <section
              aria-label="Extracto repetido"
              className="rounded-xl border border-amber-300 dark:border-amber-500/40 bg-amber-50 dark:bg-amber-500/10 p-3 space-y-2"
            >
              {dup.tipo === 'solapado' && dup.archivado ? (
                <p className="text-sm text-amber-900 dark:text-amber-200">
                  {dup.coincidencias} de estos movimientos ya están en {nombreDup}, que está archivado (período
                  cerrado). Si guardás, se crea un extracto nuevo; para agregarle solo los nuevos, primero desarchivalo.
                </p>
              ) : dup.tipo === 'solapado' ? (
                <>
                  <p className="text-sm text-amber-900 dark:text-amber-200">
                    {dup.coincidencias} de estos movimientos ya están en {nombreDup}. ¿Qué querés hacer?
                  </p>
                  <fieldset className="space-y-1.5">
                    <legend className="sr-only">Qué hacer con los movimientos repetidos</legend>
                    <label className="flex items-start gap-2 text-sm text-gray-800 dark:text-gray-200 cursor-pointer">
                      <input
                        type="radio" name={`${uid}-destino`} className="mt-1"
                        checked={destino === 'existente'}
                        onChange={() => { setDestino('existente'); onDirty() }}
                      />
                      <span>
                        {dup.nuevos === 0
                          ? `Agregarlo a ${nombreDup} (no hay movimientos nuevos)`
                          : dup.nuevos === 1
                            ? `Agregar solo el movimiento nuevo a ${nombreDup}`
                            : `Agregar solo los ${dup.nuevos} nuevos a ${nombreDup}`}
                        {dup.anteriores > 0 && (
                          <span className="block text-xs text-amber-800 dark:text-amber-300 mt-0.5">
                            {dup.anteriores === 1
                              ? '1 movimiento del PDF es anterior al último del extracto y no está ahí: así no se suma.'
                              : `${dup.anteriores} movimientos del PDF son anteriores al último del extracto y no están ahí: así no se suman.`}
                          </span>
                        )}
                      </span>
                    </label>
                    <label className="flex items-start gap-2 text-sm text-gray-800 dark:text-gray-200 cursor-pointer">
                      <input
                        type="radio" name={`${uid}-destino`} className="mt-1"
                        checked={destino === 'nuevo'}
                        onChange={() => { setDestino('nuevo'); onDirty() }}
                      />
                      <span>Crear un extracto nuevo</span>
                    </label>
                  </fieldset>
                </>
              ) : (
                <div className="flex flex-wrap items-center gap-3">
                  <p className="text-sm text-amber-900 dark:text-amber-200 flex-1 min-w-[12rem]">
                    <strong>Ya está importado.</strong>{' '}
                    {dup.tipo === 'mismo_archivo'
                      ? `Este PDF ya se cargó como ${nombreDup}.`
                      : `Estos mismos movimientos ya están en ${nombreDup}.`}
                  </p>
                  {onAbrirExtracto && (
                    <button type="button" className="btn-secondary" onClick={() => onAbrirExtracto(dup.extracto_id)}>
                      Abrir el extracto
                    </button>
                  )}
                </div>
              )}
            </section>
          )}

          {/* Cuadre de saldos */}
          <section aria-label="Cuadre de saldos" className="rounded-xl border border-gray-200 dark:border-white/10 p-3 space-y-3">
            <div className="grid grid-cols-2 sm:grid-cols-5 gap-3 items-start">
              <div>
                <label className={labelCls} htmlFor={`${uid}-si`}>Saldo inicial</label>
                <input
                  id={`${uid}-si`} inputMode="text" autoComplete="off"
                  className={`input-field text-right font-mono tabular-nums ${evaluacion.saldoInicialInvalido ? '!border-red-400' : ''}`}
                  value={saldoInicial} placeholder={cuadre.saldoInicialInferido ? 'Se deduce' : '0,00'}
                  onChange={e => { setSaldoInicial(e.target.value); onDirty() }}
                />
                {cuadre.saldoInicialInferido && !saldoInicial.trim() && cuadre.saldoInicial != null && (
                  <p className="mt-1 text-2xs text-gray-500 dark:text-gray-400">Deducido de las filas: {formatearPesos(cuadre.saldoInicial)}</p>
                )}
              </div>
              <Cifra etiqueta="+ Créditos" valor={formatearPesos(cuadre.totalCreditos)} />
              <Cifra etiqueta="− Débitos" valor={formatearPesos(cuadre.totalDebitos)} />
              <Cifra etiqueta="= Saldo calculado" valor={formatearPesos(cuadre.saldoFinalCalculado)} />
              <div className="col-span-2 sm:col-span-1">
                <label className={labelCls} htmlFor={`${uid}-sf`}>Saldo final</label>
                <input
                  id={`${uid}-sf`} inputMode="text" autoComplete="off"
                  className={`input-field text-right font-mono tabular-nums ${evaluacion.saldoFinalInvalido ? '!border-red-400' : ''}`}
                  value={saldoFinal} placeholder={cuadre.saldoFinalInferido ? 'Se deduce' : '0,00'}
                  onChange={e => { setSaldoFinal(e.target.value); onDirty() }}
                />
                {cuadre.saldoFinalInferido && !saldoFinal.trim() && cuadre.saldoFinal != null && (
                  <p className="mt-1 text-2xs text-gray-500 dark:text-gray-400">Deducido de las filas: {formatearPesos(cuadre.saldoFinal)}</p>
                )}
              </div>
            </div>

            <div
              role="status"
              className={`px-3 py-2 rounded-lg text-sm font-medium ${
                veredicto === 'cierra'
                  ? 'bg-green-50 text-green-700 dark:bg-green-500/10 dark:text-green-300'
                  : veredicto === 'no_cierra'
                    ? 'bg-red-50 text-red-700 dark:bg-red-500/10 dark:text-red-300'
                    : 'bg-amber-50 text-amber-800 dark:bg-amber-500/10 dark:text-amber-200'
              }`}
            >
              {veredicto === 'cierra' && 'Cierra: saldo inicial + créditos − débitos = saldo final.'}
              {veredicto === 'no_cierra' && !saltosSinDiferencia && `No cierra por ${difTxt}. Revisá las filas marcadas o los saldos.`}
              {veredicto === 'no_cierra' && saltosSinDiferencia &&
                `No cierra: los totales dan, pero el saldo no sigue en ${nSaltos} ${nSaltos === 1 ? 'fila' : 'filas'}. Revisá las marcadas.`}
              {veredicto === 'sin_datos' && 'No se puede verificar: falta el saldo inicial o el final.'}
            </div>
          </section>

          {borrador.puede_aprender && borrador.metodo !== 'molde' && (
            <p className="text-xs text-gray-500 dark:text-gray-400">
              Cuando lo guardes, Cuadra aprende el formato de este banco para leer los próximos sin IA.
            </p>
          )}

          {/* Movimientos */}
          <section aria-label="Movimientos" className="space-y-2">
            <div className="flex flex-wrap items-center gap-2">
              <h3 className="text-sm font-semibold text-gray-900 dark:text-gray-100">
                Movimientos <span className="font-normal text-gray-500 dark:text-gray-400">({filas.length})</span>
              </h3>
              <button
                type="button"
                aria-pressed={filtro === 'dudosas'}
                onClick={() => { setFiltro(f => (f === 'dudosas' ? 'todas' : 'dudosas')); setFijas(new Set()); setLimite(PAGINA) }}
                className={`px-2.5 py-1 text-xs rounded-full border transition-colors ${
                  filtro === 'dudosas'
                    ? 'bg-amber-100 border-amber-400 text-amber-900 dark:bg-amber-500/20 dark:border-amber-500/60 dark:text-amber-200'
                    : 'border-gray-300 dark:border-white/15 text-gray-600 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-white/10'
                }`}
              >
                Solo para revisar ({evaluacion.filasDudosas})
              </button>
              <button type="button" className="ml-auto text-xs font-medium text-ml-blue dark:text-ml-green hover:underline" onClick={agregarAlFinal}>
                + Agregar movimiento
              </button>
            </div>

            {eliminada && (
              <div role="status" className="flex items-center gap-3 px-3 py-1.5 rounded-lg bg-gray-100 dark:bg-white/10 text-xs text-gray-700 dark:text-gray-200">
                <span>Se eliminó una fila.</span>
                <button type="button" className="font-semibold text-ml-blue dark:text-ml-green hover:underline" onClick={deshacerEliminar}>
                  Deshacer
                </button>
              </div>
            )}

            {filas.length === 0 ? (
              <div className="rounded-lg border border-dashed border-gray-300 dark:border-white/15 p-6 text-center text-sm text-gray-500 dark:text-gray-400">
                No encontramos movimientos en este PDF. Podés cargarlos a mano o descartar el borrador.
              </div>
            ) : indicesVisibles.length === 0 ? (
              <div className="rounded-lg border border-dashed border-gray-300 dark:border-white/15 p-6 text-center text-sm text-gray-500 dark:text-gray-400">
                No hay filas para revisar.
              </div>
            ) : (
              <div className="overflow-x-auto rounded-lg border border-gray-200 dark:border-white/10">
                <div className="md:min-w-[45rem]">
                  <div
                    className={`${GRILLA_FILA} hidden md:grid px-3 py-1.5 border-l-4 border-l-transparent bg-gray-50 dark:bg-white/5 text-2xs font-semibold uppercase tracking-wide text-gray-500 dark:text-gray-400`}
                    aria-hidden="true"
                  >
                    <span className="text-right">#</span>
                    <span>Fecha</span>
                    <span>Descripción</span>
                    <span className="text-right">Débito</span>
                    <span className="text-right">Crédito</span>
                    <span className="text-right">Saldo</span>
                    <span />
                  </div>
                  <ul>
                    {mostradas.map(i => {
                      const f = filas[i]
                      const ev = evaluacion.filas[i]
                      return (
                        <FilaMovimiento
                          key={f.key}
                          fila={f}
                          numero={i + 1}
                          errFecha={ev.errores.some(x => x.campo === 'fecha')}
                          errImporte={ev.errores.some(x => x.campo === 'importe')}
                          errSaldo={ev.errores.some(x => x.campo === 'saldo')}
                          errores={ev.errores.map(x => x.mensaje).join(' · ')}
                          avisos={ev.avisos.join(' · ')}
                          onCambio={onCambio}
                          onEliminar={onEliminar}
                          onInsertarDebajo={onInsertarDebajo}
                          onRevisada={onRevisada}
                        />
                      )
                    })}
                  </ul>
                </div>
              </div>
            )}

            {restantes > 0 && (
              <button type="button" className="btn-secondary w-full justify-center" onClick={() => setLimite(l => l + PAGINA)}>
                Mostrar {Math.min(PAGINA, restantes)} más (quedan {restantes})
              </button>
            )}
          </section>

          {errorGuardar && (
            <div role="alert" className="px-3 py-2 rounded-lg text-sm bg-red-50 text-red-700 dark:bg-red-500/10 dark:text-red-300">
              {errorGuardar}
            </div>
          )}
        </div>
      </div>

      {/* Pie fijo: el veredicto queda a la vista mientras se editan las filas */}
      <div className="border-t border-gray-200 dark:border-white/10 px-4 pt-3 pb-[max(0.75rem,env(safe-area-inset-bottom))] flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
        <div className="text-xs min-w-0" aria-hidden="true">
          <span
            className={`font-semibold ${
              veredicto === 'cierra'
                ? 'text-green-700 dark:text-green-400'
                : veredicto === 'no_cierra'
                  ? 'text-red-700 dark:text-red-400'
                  : 'text-amber-700 dark:text-amber-400'
            }`}
          >
            {veredicto === 'cierra'
              ? 'Cierra'
              : veredicto === 'no_cierra'
                ? saltosSinDiferencia ? 'No cierra: el saldo se corta' : `No cierra por ${difTxt}`
                : 'Sin verificar'}
          </span>
          <span className="text-gray-500 dark:text-gray-400">
            {' · '}{filas.length} movimiento{filas.length === 1 ? '' : 's'}
            {evaluacion.filasDudosas > 0 && ` · ${evaluacion.filasDudosas} para revisar`}
          </span>
          {motivoBloqueo && (
            <span className="block text-red-600 dark:text-red-400 mt-0.5">{motivoBloqueo}</span>
          )}
        </div>
        <div className="grid grid-cols-2 sm:flex gap-2">
          <button type="button" className="btn-secondary justify-center" onClick={onDescartar} disabled={guardando}>
            Descartar
          </button>
          {puedeLeerConIa && (
            <button type="button" className="btn-secondary justify-center" onClick={onLeerConIa} disabled={guardando}>
              Leer con IA
            </button>
          )}
          <button
            type="button"
            className={`btn-primary justify-center ${puedeLeerConIa ? 'col-span-2' : ''} order-first sm:order-none`}
            onClick={guardar}
            disabled={!puedeGuardar}
          >
            {etiquetaGuardar}
          </button>
        </div>
      </div>
    </>
  )
}

const Cifra: React.FC<{ etiqueta: string; valor: string }> = ({ etiqueta, valor }) => (
  <div className="min-w-0">
    <p className={labelCls}>{etiqueta}</p>
    <p className="monto text-sm font-semibold text-gray-900 dark:text-gray-100 truncate sm:py-2">{valor}</p>
  </div>
)
