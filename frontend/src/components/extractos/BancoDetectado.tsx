import React, { useEffect, useId, useState } from 'react'
import { apiClient } from '@/services/api'
import type { BancoOpcion, DeteccionBanco } from '@/types'

// "Banco detectado: X (motivo)" + desplegable para cambiarlo. Lo usan la pantalla
// de columnas del extracto Excel/CSV y la revisión del extracto en PDF. El valor
// es la clave interna del banco ("macro", "galicia"…); "generico" = otro banco.

export const OTRO_BANCO = 'generico'

interface Props {
  deteccion: DeteccionBanco | null | undefined
  /** Clave elegida ('' = todavía sin elegir). */
  value: string
  onChange: (clave: string, nombre: string | null) => void
  /** Para tests: lista fija en vez de pedirla al servidor. */
  bancos?: BancoOpcion[]
}

export const BancoDetectado: React.FC<Props> = ({ deteccion, value, onChange, bancos: fijos }) => {
  const uid = useId()
  const [bancos, setBancos] = useState<BancoOpcion[]>(fijos ?? [])

  useEffect(() => {
    if (fijos) return
    let vigente = true
    apiClient.getBancosExtracto()
      .then(b => { if (vigente) setBancos(b) })
      .catch(() => { /* sin lista: queda el detectado + "Otro banco" */ })
    return () => { vigente = false }
  }, [fijos])

  // El banco detectado siempre está entre las opciones, aunque la lista no cargue.
  const opciones = [...bancos]
  if (deteccion?.nombre && deteccion.banco_clave !== OTRO_BANCO
      && !opciones.some(b => b.clave === deteccion.banco_clave)) {
    opciones.unshift({ clave: deteccion.banco_clave, nombre: deteccion.nombre })
  }
  if (value && value !== OTRO_BANCO && !opciones.some(b => b.clave === value)) {
    opciones.unshift({ clave: value, nombre: value })
  }

  const reconocido = !!deteccion && deteccion.banco_clave !== OTRO_BANCO && !!deteccion.nombre
  const cambiado = !!deteccion && value !== '' && value !== deteccion.banco_clave
  const pedir = !!deteccion?.pedir_confirmacion && !cambiado

  return (
    <div
      className={`rounded-lg border px-3 py-2 text-xs ${
        pedir
          ? 'border-amber-300 bg-amber-50 dark:border-amber-500/40 dark:bg-amber-500/10'
          : 'border-gray-200 dark:border-white/10'
      }`}
    >
      <div className="flex flex-wrap items-center gap-2">
        <label htmlFor={`${uid}-banco`} className="text-ml-text-soft dark:text-zinc-400">
          {reconocido ? (
            <>
              Banco detectado: <span className="font-semibold text-ml-text dark:text-white">{deteccion!.nombre}</span>
              {' '}<span>({deteccion!.motivo})</span>
            </>
          ) : (
            <span className="font-semibold text-amber-800 dark:text-amber-300">
              No reconocimos el banco: elegilo de la lista
            </span>
          )}
        </label>
        <select
          id={`${uid}-banco`}
          aria-label="Banco del extracto"
          className="input-field py-1! text-xs! w-auto min-w-[160px]"
          value={value}
          onChange={e => {
            const clave = e.target.value
            const op = opciones.find(b => b.clave === clave)
            onChange(clave, clave === OTRO_BANCO ? null : op?.nombre ?? null)
          }}
        >
          {value === '' && <option value="">Elegí el banco…</option>}
          {opciones.map(b => <option key={b.clave} value={b.clave}>{b.nombre}</option>)}
          <option value={OTRO_BANCO}>Otro banco</option>
        </select>
      </div>
      {deteccion?.conflicto && !cambiado && (
        <p className="mt-1 text-amber-700 dark:text-amber-400">⚠ {deteccion.conflicto} Revisá que sea el banco correcto.</p>
      )}
      {cambiado && (
        <p className="mt-1 text-ml-text-soft dark:text-zinc-400">
          La próxima vez que subas un archivo con este formato vamos a usar el banco que elegiste.
        </p>
      )}
    </div>
  )
}

/** Valor inicial del desplegable: el detectado, o vacío si no se reconoció. */
export function bancoInicial(d: DeteccionBanco | null | undefined): string {
  if (!d || d.banco_clave === OTRO_BANCO || !d.nombre) return ''
  return d.banco_clave
}
