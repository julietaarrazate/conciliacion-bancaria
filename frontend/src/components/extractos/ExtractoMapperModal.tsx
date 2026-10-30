import React, { useEffect, useMemo, useRef, useState } from 'react'
import type { MapeoExtracto, PreviewExtracto, RolExtracto, SignoExtracto } from '@/types'
import { BancoDetectado, bancoInicial } from './BancoDetectado'

// Pantalla para confirmar o corregir qué es cada columna de un extracto en
// Excel/CSV (misma idea que ColumnMapperModal de las planillas). Cada cambio se
// vuelve a leer en el servidor (`onRevisar`) para mostrar al toque si los saldos
// cuadran y cómo quedan los movimientos.

interface Props {
  preview: PreviewExtracto
  onRevisar: (mapeo: MapeoExtracto) => Promise<PreviewExtracto>
  /** `bancoClave`: el banco que quedó elegido en el desplegable (null si no hay detección). */
  onConfirm: (mapeo: MapeoExtracto, bancoClave: string | null) => void
  onCancel: () => void
}

const IGNORAR = '__ignorar__'

export const ROLES_EXTRACTO: { key: RolExtracto; label: string }[] = [
  { key: 'fecha', label: 'Fecha' },
  { key: 'titular', label: 'Detalle / titular' },
  { key: 'monto', label: 'Importe' },
  { key: 'debito', label: 'Débito' },
  { key: 'credito', label: 'Crédito' },
  { key: 'indicador', label: 'Débito o crédito (D/C)' },
  { key: 'saldo', label: 'Saldo' },
  { key: 'orden', label: 'Nº de orden / referencia' },
  { key: 'cuit', label: 'CUIT' },
  { key: 'mes', label: 'Mes' },
  { key: 'cliente_acreditado', label: 'Cliente acreditado' },
  { key: 'fecha_acred', label: 'Fecha de acreditación' },
]

const ORIGEN: Record<PreviewExtracto['origen'], { label: string; badge: string }> = {
  plantilla: { label: 'Formato guardado', badge: 'badge-ok' },
  heuristica: { label: 'Detección automática', badge: 'badge-info' },
  sugerencia: { label: 'Propuesta (sin títulos)', badge: 'badge-neutral' },
  manual: { label: 'Elegido a mano', badge: 'badge-neutral' },
  ninguno: { label: 'Sin detectar', badge: 'badge-neutral' },
}

const SIGNOS: { key: SignoExtracto; label: string }[] = [
  { key: 'columna_unica', label: 'Una columna de importe (negativo = débito)' },
  { key: 'debito_credito', label: 'Dos columnas: Débito y Crédito' },
  { key: 'indicador', label: 'Importe + columna que dice débito o crédito' },
]

/** Mismo criterio que el backend (`extracto_mapper.inferir_signo`). */
export function inferirSigno(columnas: MapeoExtracto['columnas']): SignoExtracto {
  if (columnas.monto != null && columnas.indicador != null) return 'indicador'
  const tieneDc = columnas.debito != null || columnas.credito != null
  if (tieneDc && (columnas.monto == null || (columnas.debito != null && columnas.credito != null))) {
    return 'debito_credito'
  }
  return 'columna_unica'
}

export function mapeoCompleto(m: MapeoExtracto): boolean {
  const c = m.columnas
  if (m.signo === 'debito_credito') return c.debito != null || c.credito != null
  if (m.signo === 'indicador') return c.monto != null && c.indicador != null
  return c.monto != null
}

const mapeoInicial = (p: PreviewExtracto): MapeoExtracto => p.mapeo ?? {
  hoja: p.hoja,
  fila_encabezado: 0,
  columnas: {},
  signo: 'columna_unica',
  formato_fecha: 'auto',
  decimal: 'auto',
}

const fmtPesos = (s: string | null | undefined) => {
  if (s == null) return '—'
  const n = Number(s)
  if (Number.isNaN(n)) return s
  return n.toLocaleString('es-AR', { style: 'currency', currency: 'ARS', minimumFractionDigits: 2 })
}

const fmtFecha = (iso: string | null) => {
  if (!iso) return '—'
  const [y, m, d] = iso.split('-')
  return `${d}/${m}/${y}`
}

export const BadgeCuadre: React.FC<{ cuadre: PreviewExtracto['cuadre'] }> = ({ cuadre }) => {
  if (!cuadre.tiene_saldo) {
    return <span className="badge-neutral">Sin columna de saldo: no se puede controlar</span>
  }
  if (cuadre.cuadra) return <span className="badge-ok">✓ Los saldos cuadran</span>
  return (
    <span className="badge-warn">
      ⚠ {cuadre.primera_fila_con_error != null
        ? `No cuadra en la fila ${cuadre.primera_fila_con_error}`
        : 'Los saldos no cuadran'}
    </span>
  )
}

export const ExtractoMapperModal: React.FC<Props> = ({ preview, onRevisar, onConfirm, onCancel }) => {
  const [mapeo, setMapeo] = useState<MapeoExtracto>(() => mapeoInicial(preview))
  const [actual, setActual] = useState<PreviewExtracto>(preview)
  const [revisando, setRevisando] = useState(false)
  const [errorRevision, setErrorRevision] = useState('')
  const [bancoClave, setBancoClave] = useState(() => bancoInicial(preview.banco_deteccion))
  const [bancoTocado, setBancoTocado] = useState(false)
  const primera = useRef(true)

  // Si al cambiar las columnas el banco se reconoce distinto (otra fila de títulos),
  // se sigue lo detectado mientras la persona no lo haya elegido a mano.
  useEffect(() => {
    if (!bancoTocado) setBancoClave(bancoInicial(actual.banco_deteccion))
  }, [actual.banco_deteccion, bancoTocado])

  // Cada cambio del mapeo se relee en el servidor (con una pequeña espera para
  // no mandar el archivo en cada clic seguido).
  useEffect(() => {
    if (primera.current) { primera.current = false; return }
    if (!mapeoCompleto(mapeo)) return
    let vigente = true
    const t = setTimeout(async () => {
      setRevisando(true)
      setErrorRevision('')
      try {
        const r = await onRevisar(mapeo)
        if (vigente) setActual(r)
      } catch (err: any) {
        const det = err?.response?.data?.detail
        if (vigente) setErrorRevision(typeof det === 'string' ? det : 'No se pudo leer con estas columnas.')
      } finally {
        if (vigente) setRevisando(false)
      }
    }, 400)
    return () => { vigente = false; clearTimeout(t) }
  }, [mapeo, onRevisar])

  const rolDeColumna = useMemo(() => {
    const r: Record<number, RolExtracto> = {}
    for (const [rol, idx] of Object.entries(mapeo.columnas)) {
      if (idx != null) r[idx] = rol as RolExtracto
    }
    return r
  }, [mapeo.columnas])

  const cambiarRol = (idx: number, valor: string) => {
    setMapeo(prev => {
      const columnas = { ...prev.columnas }
      for (const [rol, i] of Object.entries(columnas)) {
        if (i === idx) delete columnas[rol as RolExtracto]
      }
      if (valor !== IGNORAR) columnas[valor as RolExtracto] = idx
      return { ...prev, columnas, signo: inferirSigno(columnas) }
    })
  }

  const { grilla } = preview
  const hayDeteccion = !!actual.banco_deteccion
  const faltaBanco = hayDeteccion && bancoClave === ''
  const valido = mapeoCompleto(mapeo)
  const origen = ORIGEN[actual.origen] ?? ORIGEN.manual
  const encabezado = (c: number) => {
    const fila = mapeo.fila_encabezado - grilla.desde
    const texto = fila >= 0 ? grilla.filas[fila]?.[c] : ''
    return texto || `Columna ${c + 1}`
  }

  return (
    <div className="fixed inset-0 z-150 flex items-center justify-center p-4">
      <div className="absolute inset-0 bg-black/50 backdrop-blur-xs" onClick={onCancel} />
      <div
        role="dialog"
        aria-label="Columnas del extracto"
        className="relative bg-white dark:bg-ml-dark-surface rounded-2xl shadow-xl border border-gray-200 dark:border-ml-dark-border p-5 md:p-6 w-full max-w-5xl max-h-[92vh] overflow-y-auto"
      >
        <div className="flex flex-wrap items-start justify-between gap-2 mb-1">
          <h3 className="text-base font-semibold text-ml-text dark:text-white">
            Revisá las columnas del extracto
          </h3>
          <span className={origen.badge}>{origen.label}</span>
        </div>
        {hayDeteccion && (
          <div className="mb-2">
            <BancoDetectado
              deteccion={actual.banco_deteccion}
              value={bancoClave}
              onChange={clave => { setBancoClave(clave); setBancoTocado(true) }}
            />
          </div>
        )}
        <p className="text-xs text-ml-text-soft dark:text-zinc-400 mb-3">
          {!hayDeteccion && actual.banco ? <>Banco: <span className="font-semibold">{actual.banco}</span> · </> : null}
          Confianza: <span className="font-semibold">{Math.round(actual.confianza * 100)}%</span>
          {preview.hojas.length > 1 && preview.hoja ? <> · Hoja: <span className="font-semibold">{preview.hoja}</span></> : null}
        </p>

        {actual.motivos.length > 0 && (
          <ul className="mb-3 text-xs text-amber-700 dark:text-amber-400 list-disc pl-4 space-y-0.5">
            {actual.motivos.map((m, i) => <li key={i}>{m}</li>)}
          </ul>
        )}

        <div className="grid grid-cols-1 md:grid-cols-4 gap-3 mb-4 text-xs">
          <label className="flex flex-col gap-1">
            <span className="text-ml-text-soft dark:text-zinc-400">Fila de títulos</span>
            <select
              className="input-field py-1! text-xs!"
              value={mapeo.fila_encabezado}
              onChange={e => setMapeo(m => ({ ...m, fila_encabezado: Number(e.target.value) }))}
            >
              <option value={-1}>Sin fila de títulos</option>
              {grilla.filas.map((f, i) => (
                <option key={i} value={grilla.desde + i}>
                  Fila {grilla.desde + i + 1}: {f.filter(Boolean).slice(0, 3).join(' · ').slice(0, 40)}
                </option>
              ))}
            </select>
          </label>
          <label className="flex flex-col gap-1">
            <span className="text-ml-text-soft dark:text-zinc-400">Débitos y créditos</span>
            <select
              className="input-field py-1! text-xs!"
              value={mapeo.signo}
              onChange={e => setMapeo(m => ({ ...m, signo: e.target.value as SignoExtracto }))}
            >
              {SIGNOS.map(s => <option key={s.key} value={s.key}>{s.label}</option>)}
            </select>
          </label>
          <label className="flex flex-col gap-1">
            <span className="text-ml-text-soft dark:text-zinc-400">Fechas</span>
            <select
              className="input-field py-1! text-xs!"
              value={mapeo.formato_fecha}
              onChange={e => setMapeo(m => ({ ...m, formato_fecha: e.target.value as MapeoExtracto['formato_fecha'] }))}
            >
              <option value="auto">Automático</option>
              <option value="dmy">Día/mes/año (19/05/2026)</option>
              <option value="mdy">Mes/día/año (05/19/2026)</option>
              <option value="ymd">Año-mes-día (2026-05-19)</option>
            </select>
          </label>
          <label className="flex flex-col gap-1">
            <span className="text-ml-text-soft dark:text-zinc-400">Decimales</span>
            <select
              className="input-field py-1! text-xs!"
              value={mapeo.decimal}
              onChange={e => setMapeo(m => ({ ...m, decimal: e.target.value as MapeoExtracto['decimal'] }))}
            >
              <option value="auto">Automático</option>
              <option value="coma">Con coma (1.234,56)</option>
              <option value="punto">Con punto (1,234.56)</option>
            </select>
          </label>
        </div>

        <div className="overflow-x-auto rounded-lg border border-gray-100 dark:border-white/10">
          <table className="min-w-full text-xs">
            <thead>
              <tr>
                {Array.from({ length: grilla.columnas }, (_, c) => (
                  <th key={c} className="px-2 py-2 bg-gray-50 dark:bg-white/5 border-b border-gray-100 dark:border-white/10 align-top text-left">
                    <select
                      className="input-field py-1! text-xs! mb-1 w-full min-w-[120px]"
                      value={rolDeColumna[c] ?? IGNORAR}
                      onChange={e => cambiarRol(c, e.target.value)}
                      aria-label={`Uso de la columna ${encabezado(c)}`}
                    >
                      <option value={IGNORAR}>(No usar)</option>
                      {ROLES_EXTRACTO.map(r => <option key={r.key} value={r.key}>{r.label}</option>)}
                    </select>
                    <div className="font-semibold text-ml-text dark:text-white truncate max-w-[160px]" title={encabezado(c)}>
                      {encabezado(c)}
                    </div>
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {grilla.filas.map((fila, i) => {
                const n = grilla.desde + i
                const esTitulo = n === mapeo.fila_encabezado
                const antes = n < mapeo.fila_encabezado
                return (
                  <tr
                    key={n}
                    className={`border-b border-gray-50 dark:border-white/5 last:border-0 ${esTitulo ? 'bg-blue-50 dark:bg-blue-500/10 font-semibold' : ''} ${antes ? 'opacity-40' : ''}`}
                  >
                    {Array.from({ length: grilla.columnas }, (_, c) => (
                      <td key={c} className="px-2 py-1 text-ml-text-soft dark:text-zinc-400 whitespace-nowrap max-w-[160px] truncate">
                        {fila[c] ?? ''}
                      </td>
                    ))}
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>

        <div className="mt-4 flex flex-wrap items-center gap-3 text-sm">
          <BadgeCuadre cuadre={actual.cuadre} />
          <span className="text-ml-text-soft dark:text-zinc-400 text-xs">
            {actual.total_movimientos} movimiento{actual.total_movimientos === 1 ? '' : 's'}
            {actual.filas_resumen > 0 && ` · ${actual.filas_resumen} fila${actual.filas_resumen === 1 ? '' : 's'} de total/saldo salteada${actual.filas_resumen === 1 ? '' : 's'}`}
            {actual.filas_descartadas > 0 && ` · ${actual.filas_descartadas} fila${actual.filas_descartadas === 1 ? '' : 's'} sin importe o sin fecha`}
            {actual.cuadre.tiene_saldo && ` · ${actual.cuadre.orden === 'desc' ? 'del más nuevo al más viejo' : 'del más viejo al más nuevo'}`}
          </span>
          {revisando && <span className="text-xs text-ml-text-soft dark:text-zinc-400">Revisando…</span>}
          {errorRevision && <span className="text-xs text-red-600 dark:text-red-400">{errorRevision}</span>}
        </div>

        {actual.muestra.length > 0 && (
          <div className="mt-3 overflow-x-auto rounded-lg border border-gray-100 dark:border-white/10">
            <table className="min-w-full text-xs">
              <thead>
                <tr className="bg-gray-50 dark:bg-white/5 text-ml-text-soft dark:text-zinc-400">
                  <th className="px-2 py-1 text-left">Fila</th>
                  <th className="px-2 py-1 text-left">Fecha</th>
                  <th className="px-2 py-1 text-left">Detalle</th>
                  <th className="px-2 py-1 text-right">Importe</th>
                  <th className="px-2 py-1 text-right">Saldo</th>
                </tr>
              </thead>
              <tbody>
                {actual.muestra.map(m => (
                  <tr key={m.fila} className="border-t border-gray-50 dark:border-white/5">
                    <td className="px-2 py-1 text-ml-text-soft dark:text-zinc-400">{m.fila}</td>
                    <td className="px-2 py-1 text-ml-text dark:text-white whitespace-nowrap">{fmtFecha(m.fecha)}</td>
                    <td className="px-2 py-1 text-ml-text dark:text-white truncate max-w-[260px]">{m.titular ?? ''}</td>
                    <td className={`px-2 py-1 text-right whitespace-nowrap ${Number(m.monto) < 0 ? 'text-red-600 dark:text-red-400' : 'text-ml-text dark:text-white'}`}>
                      {fmtPesos(m.monto)}
                    </td>
                    <td className="px-2 py-1 text-right whitespace-nowrap text-ml-text-soft dark:text-zinc-400">{fmtPesos(m.saldo)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        <div className="flex flex-wrap items-center justify-between gap-3 mt-5">
          <p className="text-xs text-ml-text-soft dark:text-zinc-400 max-w-md">
            {!valido
              ? '⚠ Indicá al menos la columna del importe (o las de débito y crédito).'
              : faltaBanco
                ? '⚠ Elegí de qué banco es el extracto (o "Otro banco").'
                : 'Al importar, este formato queda guardado y la próxima vez se lee solo.'}
          </p>
          <div className="flex gap-3 shrink-0">
            <button onClick={onCancel} className="btn-secondary">Cancelar</button>
            <button
              onClick={() => valido && !faltaBanco && onConfirm(mapeo, hayDeteccion ? bancoClave : null)}
              disabled={!valido || faltaBanco || revisando}
              className="btn-primary"
            >
              Importar extracto
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
