// Subtotal de un grupo de conciliación (varias filas contra un movimiento, o una
// fila contra varios movimientos). Se suma en centavos enteros para no arrastrar
// errores de punto flotante (0.1 + 0.2): mismo criterio que el backend, que
// compara en Decimal con la tolerancia de la organización (estrictamente menor).

export interface SubtotalGrupo {
  totalFilas: number
  totalMovimientos: number
  /** movimientos − filas (negativo = el banco recibió menos que lo declarado) */
  diferencia: number
  cuadra: boolean
}

const aCentavos = (n: number) => Math.round(Number(n || 0) * 100)

export function subtotalGrupo(filas: number[], movimientos: number[], tolerancia = 0.01): SubtotalGrupo {
  const cf = filas.reduce((acc, n) => acc + aCentavos(n), 0)
  const cm = movimientos.reduce((acc, n) => acc + aCentavos(n), 0)
  const dif = cm - cf
  return {
    totalFilas: cf / 100,
    totalMovimientos: cm / 100,
    diferencia: dif / 100,
    cuadra: Math.abs(dif) < aCentavos(tolerancia),
  }
}

/** Forma válida de un grupo: al menos una fila y un movimiento, uno de los dos lados
 *  con un solo elemento y 3+ elementos en total (1 contra 1 se resuelve con "Asignar"). */
export function formaGrupoValida(nFilas: number, nMovimientos: number): boolean {
  if (nFilas < 1 || nMovimientos < 1) return false
  if (nFilas > 1 && nMovimientos > 1) return false
  return nFilas + nMovimientos >= 3
}
