import React from 'react'
import type { FilaForm } from './filasExtracto'

export type CampoFila = 'fecha' | 'descripcion' | 'debito' | 'credito' | 'saldo'

/** Grilla compartida por el encabezado y las filas (desde md; en celular cada fila es una tarjeta). */
export const GRILLA_FILA =
  'grid grid-cols-6 md:grid-cols-[1.75rem_8.25rem_minmax(7rem,1fr)_6.5rem_6.5rem_7rem_4.25rem] gap-x-2 gap-y-1.5 items-center'

const inputBase =
  'w-full min-w-0 px-2 py-1.5 rounded-md border bg-white dark:bg-white/5 text-gray-900 dark:text-gray-100 ' +
  'placeholder-gray-400 text-base md:text-xs focus:outline-hidden focus:ring-2 focus:ring-ml-blue/40 dark:focus:ring-ml-green/30 ' +
  'disabled:opacity-60'
const borde = (error: boolean) =>
  error ? 'border-red-400 dark:border-red-500/70' : 'border-gray-300 dark:border-white/10'
const montoCls = 'text-right font-mono tabular-nums'
const etiquetaMovil = 'md:hidden text-2xs uppercase tracking-wide text-gray-500 dark:text-gray-400'

interface Props {
  fila: FilaForm
  /** Posición de la fila en la lista completa (1 = primera). Es el número que nombra el servidor en sus errores. */
  numero: number
  errFecha: boolean
  errImporte: boolean
  errSaldo: boolean
  /** Problemas que impiden guardar, unidos con " · ". */
  errores: string
  /** Dudas (no impiden guardar), unidas con " · ". */
  avisos: string
  onCambio: (key: string, campo: CampoFila, valor: string) => void
  onEliminar: (key: string) => void
  onInsertarDebajo: (key: string) => void
  onRevisada: (key: string) => void
}

const FilaMovimientoBase: React.FC<Props> = ({
  fila, numero, errFecha, errImporte, errSaldo, errores, avisos,
  onCambio, onEliminar, onInsertarDebajo, onRevisada,
}) => {
  const tieneError = errores.length > 0
  const tinte = tieneError
    ? 'bg-red-50/70 dark:bg-red-500/10 border-l-red-500'
    : avisos
      ? 'bg-amber-50/80 dark:bg-amber-500/10 border-l-amber-400'
      : 'border-l-transparent'
  const lbl = (txt: string) => `${txt}, fila ${numero}`

  return (
    <li
      className={`${GRILLA_FILA} px-3 py-2 border-b border-gray-100 dark:border-white/5 border-l-4 ${tinte}`}
      data-testid="fila-movimiento"
      data-estado={tieneError ? 'error' : avisos ? 'dudosa' : 'ok'}
    >
      <span className="order-1 md:order-0 col-span-1 text-2xs md:text-right text-gray-400 dark:text-gray-500 tabular-nums">
        <span className="md:hidden">Fila </span>{numero}
      </span>

      <input
        type="date"
        aria-label={lbl('Fecha')}
        value={fila.fecha}
        onChange={e => onCambio(fila.key, 'fecha', e.target.value)}
        className={`order-2 md:order-0 col-span-4 md:col-span-1 ${inputBase} ${borde(errFecha)}`}
      />

      <input
        type="text"
        aria-label={lbl('Descripción')}
        placeholder="Descripción"
        value={fila.descripcion}
        onChange={e => onCambio(fila.key, 'descripcion', e.target.value)}
        className={`order-4 md:order-0 col-span-6 md:col-span-1 ${inputBase} ${borde(false)}`}
      />

      <label className="order-5 md:order-0 col-span-2 md:col-span-1 flex flex-col gap-0.5 min-w-0">
        <span className={etiquetaMovil} aria-hidden="true">Débito</span>
        <input
          type="text"
          inputMode="decimal"
          autoComplete="off"
          aria-label={lbl('Débito')}
          placeholder="0,00"
          value={fila.debito}
          onChange={e => onCambio(fila.key, 'debito', e.target.value)}
          className={`${inputBase} ${montoCls} ${borde(errImporte)}`}
        />
      </label>

      <label className="order-6 md:order-0 col-span-2 md:col-span-1 flex flex-col gap-0.5 min-w-0">
        <span className={etiquetaMovil} aria-hidden="true">Crédito</span>
        <input
          type="text"
          inputMode="decimal"
          autoComplete="off"
          aria-label={lbl('Crédito')}
          placeholder="0,00"
          value={fila.credito}
          onChange={e => onCambio(fila.key, 'credito', e.target.value)}
          className={`${inputBase} ${montoCls} ${borde(errImporte)}`}
        />
      </label>

      <label className="order-7 md:order-0 col-span-2 md:col-span-1 flex flex-col gap-0.5 min-w-0">
        <span className={etiquetaMovil} aria-hidden="true">Saldo</span>
        <input
          type="text"
          inputMode="text"
          autoComplete="off"
          aria-label={lbl('Saldo')}
          placeholder="—"
          value={fila.saldo}
          onChange={e => onCambio(fila.key, 'saldo', e.target.value)}
          className={`${inputBase} ${montoCls} ${borde(errSaldo)}`}
        />
      </label>

      <div className="order-3 md:order-0 col-span-1 flex items-center justify-end gap-0.5">
        <button
          type="button"
          onClick={() => onInsertarDebajo(fila.key)}
          className="p-1.5 rounded-md text-gray-400 hover:text-ml-blue dark:hover:text-ml-green hover:bg-gray-100 dark:hover:bg-white/10"
          aria-label={`Agregar una fila debajo de la fila ${numero}`}
          title="Agregar una fila debajo"
        >
          <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} aria-hidden="true">
            <path strokeLinecap="round" strokeLinejoin="round" d="M12 5v14M5 12h14" />
          </svg>
        </button>
        <button
          type="button"
          onClick={() => onEliminar(fila.key)}
          className="p-1.5 rounded-md text-gray-400 hover:text-red-500 hover:bg-red-50 dark:hover:bg-red-500/10"
          aria-label={`Eliminar la fila ${numero}`}
          title="Eliminar esta fila"
        >
          <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} aria-hidden="true">
            <path strokeLinecap="round" strokeLinejoin="round" d="M6 6l12 12M18 6L6 18" />
          </svg>
        </button>
      </div>

      {(tieneError || avisos) && (
        <p className="order-8 md:order-0 col-span-6 md:col-span-full text-xs flex flex-wrap items-center gap-x-2 gap-y-1">
          {tieneError && (
            <span className="text-red-700 dark:text-red-300 font-medium">{errores}</span>
          )}
          {!tieneError && avisos && (
            <>
              <span className="text-amber-800 dark:text-amber-300 font-medium">Revisá: {avisos}</span>
              {fila.motivosLectura.length > 0 && (
                <button
                  type="button"
                  onClick={() => onRevisada(fila.key)}
                  className="text-ml-blue dark:text-ml-green hover:underline"
                >
                  Está bien
                </button>
              )}
            </>
          )}
        </p>
      )}
    </li>
  )
}

export const FilaMovimiento = React.memo(FilaMovimientoBase)
