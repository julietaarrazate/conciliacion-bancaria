// Matemática de saldos de un extracto bancario en CENTAVOS ENTEROS.
//
// Espeja `validar_saldos` del backend (app/services/extracto_pdf/saldos.py): la
// pantalla de revisión recalcula con esto mientras la persona edita, y el
// servidor vuelve a validar al confirmar (él es la autoridad). Nunca usar
// floats para sumar importes: 0.1 + 0.2 !== 0.3 y un extracto tiene cientos de filas.
//
//     saldo_inicial + créditos − débitos = saldo_final      (tolerancia 1 centavo)
//
// Convenciones: un monto es crédito si es > 0 y débito si es < 0. "Centavos"
// siempre es un entero (number) con signo.

export const TOLERANCIA_CENTAVOS = 1

// Formas válidas de un importe SIN signo. Estrictas a propósito: el parseo
// laxo de parseMonto lee "1.234,567" como 1.234 y en pantalla de plata eso no sirve.
const PLANO = /^\d+(?:[.,]\d{1,2})?$/                       // 1234 · 1234,5 · 1234.56
const MILES_AR = /^\d{1,3}(?:\.\d{3})+(?:,\d{1,2})?$/       // 1.234 · 1.234,56
const MILES_US = /^\d{1,3}(?:,\d{3})+\.\d{1,2}$/            // 1,234.56 (los decimales son obligatorios)

/** Separa signo y cuerpo: "-1.234,56", "1.234,56-", "(1.234,56)", "−1.234,56". */
function separarSigno(raw: string): { negativo: boolean; cuerpo: string } {
  let s = raw.trim().replace(/[$\s]/g, '').replace(/−/g, '-')
  let negativo = false
  const par = /^\((.*)\)$/.exec(s)
  if (par) { negativo = true; s = par[1] }
  if (s.startsWith('-')) { negativo = !negativo; s = s.slice(1) }
  else if (s.endsWith('-')) { negativo = !negativo; s = s.slice(0, -1) }
  else if (s.startsWith('+')) { s = s.slice(1) }
  return { negativo, cuerpo: s }
}

/**
 * Importe → centavos enteros, o null si no es un importe válido.
 *
 * Acepta number, "1234.56" (lo que manda el servidor), "1.234,56", "1234,56",
 * "-1.234,56", "1.234,56-", "(1.234,56)", "$ 1.234,56". Rechaza (null) lo
 * ambiguo o con más de 2 decimales ("1.234,567", "1,234") antes que adivinar.
 * Regla de miles: "1.234" (punto + exactamente 3 dígitos) es MIL doscientos
 * treinta y cuatro, como se escribe en Argentina.
 */
export function aCentavos(raw: unknown): number | null {
  if (raw == null) return null
  if (typeof raw === 'number') return Number.isFinite(raw) ? Math.round(raw * 100) : null
  if (typeof raw !== 'string') return null
  const { negativo, cuerpo } = separarSigno(raw)
  if (!cuerpo) return null
  let entero: string
  let dec = ''
  if (MILES_AR.test(cuerpo)) {
    const [e, d = ''] = cuerpo.replace(/\./g, '').split(',')
    entero = e; dec = d
  } else if (MILES_US.test(cuerpo)) {
    const [e, d = ''] = cuerpo.replace(/,/g, '').split('.')
    entero = e; dec = d
  } else if (PLANO.test(cuerpo)) {
    const [e, d = ''] = cuerpo.replace(',', '.').split('.')
    entero = e; dec = d
  } else {
    return null
  }
  const centavos = Number(entero) * 100 + Number(dec.padEnd(2, '0'))
  if (!Number.isSafeInteger(centavos)) return null
  return negativo && centavos !== 0 ? -centavos : centavos
}

const agrupar = (entero: string) => entero.replace(/\B(?=(\d{3})+(?!\d))/g, '.')

/** 123456 → "1.234,56"; -50 → "-0,50". Sin símbolo de moneda. */
export function formatearCentavos(centavos: number): string {
  const abs = Math.abs(centavos)
  const entero = Math.floor(abs / 100)
  const dec = String(abs % 100).padStart(2, '0')
  return `${centavos < 0 ? '-' : ''}${agrupar(String(entero))},${dec}`
}

/** 123456 → "$ 1.234,56"; -123456 → "-$ 1.234,56". */
export function formatearPesos(centavos: number | null | undefined): string {
  if (centavos == null) return '—'
  const txt = formatearCentavos(Math.abs(centavos))
  return `${centavos < 0 ? '-' : ''}$ ${txt}`
}

/** Para un input de importe SIN signo (columnas Débito/Crédito): 123456 → "1.234,56". */
export function centavosAInput(centavos: number): string {
  return formatearCentavos(Math.abs(centavos))
}

/** Formato de la API: string con punto y 2 decimales, sin miles. -123456 → "-1234.56". */
export function centavosAServidor(centavos: number): string {
  const abs = Math.abs(centavos)
  return `${centavos < 0 ? '-' : ''}${Math.floor(abs / 100)}.${String(abs % 100).padStart(2, '0')}`
}

export type ErrorImporte = 'vacio' | 'invalido' | 'ambos' | 'cero'

/**
 * Monto con signo de una fila a partir de sus columnas Débito y Crédito (los
 * dos inputs son positivos; el signo lo da la columna). `error` explica por qué
 * no hay monto: vacío, texto que no es un importe (o con signo), importe en las
 * dos columnas, o cero.
 */
export function montoDeFila(
  debito: string,
  credito: string,
): { centavos: number | null; error: ErrorImporte | null } {
  const d = debito.trim()
  const c = credito.trim()
  if (!d && !c) return { centavos: null, error: 'vacio' }
  const dc = d ? aCentavos(d) : 0
  const cc = c ? aCentavos(c) : 0
  if (dc == null || cc == null || dc < 0 || cc < 0) return { centavos: null, error: 'invalido' }
  if (dc > 0 && cc > 0) return { centavos: null, error: 'ambos' }
  if (dc === 0 && cc === 0) return { centavos: null, error: 'cero' }
  return { centavos: cc > 0 ? cc : -dc, error: null }
}

export interface FilaSaldo {
  /** Crédito +, débito −. null = no se pudo interpretar (cuenta como 0). */
  monto: number | null
  /** Saldo después del movimiento, si la fila lo trae. */
  saldo: number | null
}

export interface OpcionesCuadre {
  /** Orden en que están las filas: "asc" = la más vieja primero. */
  orden: 'asc' | 'desc'
  saldoInicial: number | null
  saldoFinal: number | null
}

export interface CuadreCentavos {
  saldoInicial: number | null
  saldoInicialInferido: boolean
  saldoFinal: number | null
  saldoFinalInferido: boolean
  totalCreditos: number
  /** Positivo. */
  totalDebitos: number
  cantidad: number
  saldoFinalCalculado: number | null
  /** saldoFinal − saldoFinalCalculado. */
  diferencia: number | null
  /** |diferencia| ≤ 1 centavo y sin saltos. false si no se puede calcular. */
  cierra: boolean
  /** Índices (en el orden recibido) donde se corta el saldo corrido. */
  filasConSalto: number[]
}

/**
 * Valida un extracto. Mismo algoritmo que el backend: si falta el saldo inicial
 * se deduce de la primera fila (cronológica) con saldo; si falta el final, solo
 * del saldo de la última fila cronológica; y se controla fila por fila que
 * `saldo[i] = saldo[i-1] + monto[i]`. Cierra si la diferencia es ≤ 1 centavo
 * y no hay saltos en el saldo corrido.
 */
export function validarSaldos(filas: readonly FilaSaldo[], opciones: OpcionesCuadre): CuadreCentavos {
  const n = filas.length
  const indices = Array.from({ length: n }, (_, i) => (opciones.orden === 'desc' ? n - 1 - i : i))
  const montos = filas.map(f => f.monto ?? 0)
  const saldos = filas.map(f => f.saldo)

  let si = opciones.saldoInicial
  let sf = opciones.saldoFinal
  let siInferido = false
  let sfInferido = false

  if (si == null) {
    let acumulado = 0
    for (const i of indices) {
      acumulado += montos[i]
      const s = saldos[i]
      if (s != null) { si = s - acumulado; siInferido = true; break }
    }
  }
  if (sf == null && n > 0) {
    // Solo de la última fila cronológica: si no trae saldo, sus importes no se
    // pueden controlar y deducir el final de ellos sería darlos por buenos.
    const s = saldos[indices[n - 1]]
    if (s != null) { sf = s; sfInferido = true }
  }

  let totalCreditos = 0
  let totalDebitos = 0
  for (const m of montos) {
    if (m > 0) totalCreditos += m
    else if (m < 0) totalDebitos += -m
  }

  const calculado = si != null ? si + totalCreditos - totalDebitos : null
  const diferencia = sf != null && calculado != null ? sf - calculado : null
  const saltos: number[] = []
  let previo = si
  for (const i of indices) {
    const s = saldos[i]
    if (s != null) {
      if (previo != null && Math.abs(previo + montos[i] - s) > TOLERANCIA_CENTAVOS) saltos.push(i)
      previo = s
    } else if (previo != null) {
      previo = previo + montos[i]
    }
  }
  saltos.sort((a, b) => a - b)
  // Dos saltos pueden compensarse y dejar la diferencia en cero.
  const cierra = diferencia != null && Math.abs(diferencia) <= TOLERANCIA_CENTAVOS && saltos.length === 0

  return {
    saldoInicial: si ?? null,
    saldoInicialInferido: siInferido,
    saldoFinal: sf ?? null,
    saldoFinalInferido: sfInferido,
    totalCreditos,
    totalDebitos,
    cantidad: n,
    saldoFinalCalculado: calculado,
    diferencia,
    cierra,
    filasConSalto: saltos,
  }
}
