// Modelo editable de la pantalla de revisión de un extracto PDF.
//
// Todo lo que la persona edita vive como string (así los inputs no pelean con
// el formato argentino) y se convierte a centavos enteros solo para calcular.
// La conversión a lo que espera la API está en `armarPayload`.

import type { BorradorExtractoPdf, ConfirmarExtractoPdfPayload, MovimientoPdf } from '@/types'
import {
  aCentavos,
  centavosAInput,
  centavosAServidor,
  montoDeFila,
  validarSaldos,
  type CuadreCentavos,
  type ErrorImporte,
} from '@/utils/saldoExtracto'

/** Máximo de movimientos por extracto que acepta el servidor. */
export const MAX_MOVIMIENTOS = 5000
/** El servidor rechaza importes de 10^10 pesos o más (la columna es Numeric(12,2)). */
const LIMITE_CENTAVOS = 10 ** 12

export const MOTIVO_SALTO = 'El saldo no sigue'

export interface FilaForm {
  key: string
  fecha: string                 // YYYY-MM-DD, o '' si falta
  descripcion: string
  debito: string                // importe SIN signo; el signo lo da la columna
  credito: string
  saldo: string
  pagina: number | null
  /** Dudas que trajo la lectura. Se limpian al editar la fila o al marcarla como revisada. */
  motivosLectura: string[]
}

export interface ErrorFila {
  campo: 'fecha' | 'importe' | 'saldo'
  mensaje: string
}

export interface FilaEvaluada {
  centavos: number | null
  saldoCentavos: number | null
  /** Problemas que impiden guardar (fecha, importe o saldo inválidos). */
  errores: ErrorFila[]
  /** Dudas que no impiden guardar (saldo que no sigue, signo deducido…). */
  avisos: string[]
}

export interface EvaluacionExtracto {
  filas: FilaEvaluada[]
  cuadre: CuadreCentavos
  filasConError: number
  filasDudosas: number
  /** Saldo inicial/final escritos pero que no son un importe. */
  saldoInicialInvalido: boolean
  saldoFinalInvalido: boolean
}

let secuencia = 0
export const nuevaClave = () => `f${++secuencia}`

export function filaDesdeMovimiento(m: MovimientoPdf): FilaForm {
  const monto = aCentavos(m.monto)
  const saldo = aCentavos(m.saldo)
  return {
    key: nuevaClave(),
    fecha: m.fecha || '',
    descripcion: m.descripcion || '',
    debito: monto != null && monto < 0 ? centavosAInput(monto) : '',
    credito: monto != null && monto > 0 ? centavosAInput(monto) : '',
    saldo: saldo != null ? formatearSaldoInput(saldo) : '',
    pagina: m.pagina ?? null,
    motivosLectura: m.dudosa ? (m.motivos.length ? [...m.motivos] : ['Revisá esta fila']) : [],
  }
}

/** Un saldo sí puede ser negativo (descubierto): se muestra con signo. */
export function formatearSaldoInput(centavos: number): string {
  return (centavos < 0 ? '-' : '') + centavosAInput(centavos)
}

export function filaVacia(fecha: string): FilaForm {
  return { key: nuevaClave(), fecha, descripcion: '', debito: '', credito: '', saldo: '', pagina: null, motivosLectura: [] }
}

export function filasDesdeBorrador(b: BorradorExtractoPdf): FilaForm[] {
  return b.movimientos.map(filaDesdeMovimiento)
}

/** 2026-02-31 no es una fecha: se compara contra el calendario, no solo contra el formato. */
export function esFechaIso(s: string): boolean {
  const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(s)
  if (!m) return false
  const [y, mo, d] = [Number(m[1]), Number(m[2]), Number(m[3])]
  if (y < 1990 || y > 2100) return false
  const f = new Date(y, mo - 1, d)
  return f.getFullYear() === y && f.getMonth() === mo - 1 && f.getDate() === d
}

const MENSAJE_IMPORTE: Record<ErrorImporte, string> = {
  vacio: 'Falta el importe',
  cero: 'El importe no puede ser cero',
  invalido: 'Importe inválido (sin signo: lo da la columna)',
  ambos: 'Poné el importe en una sola columna',
}

export function evaluarFilas(
  filas: readonly FilaForm[],
  orden: 'asc' | 'desc',
  saldoInicial: string,
  saldoFinal: string,
): EvaluacionExtracto {
  const base = filas.map(f => {
    const errores: ErrorFila[] = []
    if (!f.fecha) errores.push({ campo: 'fecha', mensaje: 'Falta la fecha' })
    else if (!esFechaIso(f.fecha)) errores.push({ campo: 'fecha', mensaje: 'Fecha inválida' })

    const { centavos, error } = montoDeFila(f.debito, f.credito)
    if (error) errores.push({ campo: 'importe', mensaje: MENSAJE_IMPORTE[error] })
    else if (centavos != null && Math.abs(centavos) >= LIMITE_CENTAVOS) errores.push({ campo: 'importe', mensaje: 'Importe demasiado grande' })

    let saldoCentavos: number | null = null
    if (f.saldo.trim()) {
      saldoCentavos = aCentavos(f.saldo)
      if (saldoCentavos == null) errores.push({ campo: 'saldo', mensaje: 'Saldo inválido' })
      else if (Math.abs(saldoCentavos) >= LIMITE_CENTAVOS) { errores.push({ campo: 'saldo', mensaje: 'Saldo demasiado grande' }); saldoCentavos = null }
    }
    return { centavos: error ? null : centavos, saldoCentavos, errores }
  })

  const siTxt = saldoInicial.trim()
  const sfTxt = saldoFinal.trim()
  const si = siTxt ? aCentavos(siTxt) : null
  const sf = sfTxt ? aCentavos(sfTxt) : null

  const cuadre = validarSaldos(
    base.map(b => ({ monto: b.centavos, saldo: b.saldoCentavos })),
    { orden, saldoInicial: si, saldoFinal: sf },
  )
  const saltos = new Set(cuadre.filasConSalto)

  const evaluadas: FilaEvaluada[] = base.map((b, i) => {
    const avisos = [...filas[i].motivosLectura]
    if (saltos.has(i) && !avisos.includes(MOTIVO_SALTO)) avisos.push(MOTIVO_SALTO)
    return { ...b, avisos }
  })

  return {
    filas: evaluadas,
    cuadre,
    filasConError: evaluadas.filter(f => f.errores.length > 0).length,
    filasDudosas: evaluadas.filter(f => f.errores.length > 0 || f.avisos.length > 0).length,
    saldoInicialInvalido: !!siTxt && si == null,
    saldoFinalInvalido: !!sfTxt && sf == null,
  }
}

export interface DatosConfirmacion {
  filas: readonly FilaForm[]
  evaluacion: EvaluacionExtracto
  saldoInicial: string
  saldoFinal: string
  banco: string
  nombre: string | null
  destino: 'nuevo' | 'existente'
  extractoDestinoId: number | null
  confirmarSinCuadre: boolean
}

/** Arma el cuerpo de `POST /extractos-pdf/borradores/{id}/confirmar`. Los importes van como string. */
export function armarPayload(d: DatosConfirmacion): ConfirmarExtractoPdfPayload {
  const aServidor = (txt: string): string | null => {
    const c = txt.trim() ? aCentavos(txt) : null
    return c == null ? null : centavosAServidor(c)
  }
  return {
    movimientos: d.filas.map((f, i) => {
      const ev = d.evaluacion.filas[i]
      return {
        fecha: f.fecha,
        descripcion: f.descripcion.trim(),
        monto: centavosAServidor(ev.centavos ?? 0),
        saldo: ev.saldoCentavos == null ? null : centavosAServidor(ev.saldoCentavos),
      }
    }),
    saldo_inicial: aServidor(d.saldoInicial),
    saldo_final: aServidor(d.saldoFinal),
    banco: d.banco.trim() || null,
    nombre: d.nombre && d.nombre.trim() ? d.nombre.trim() : null,
    destino: d.destino,
    extracto_id: d.destino === 'existente' ? d.extractoDestinoId : null,
    confirmar_sin_cuadre: d.confirmarSinCuadre,
  }
}

/** dd/mm/aaaa a partir de YYYY-MM-DD, sin pasar por Date (no depende de la zona horaria). */
export function fmtFechaAr(iso: string | null | undefined): string {
  if (!iso) return ''
  const [y, m, d] = iso.split('-')
  return y && m && d ? `${d}/${m}/${y}` : iso
}
