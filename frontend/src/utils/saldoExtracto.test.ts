import { describe, it, expect } from 'vitest'
import {
  aCentavos,
  centavosAInput,
  centavosAServidor,
  formatearCentavos,
  formatearPesos,
  montoDeFila,
  validarSaldos,
} from './saldoExtracto'

describe('aCentavos', () => {
  it('vacío o tipos raros → null', () => {
    expect(aCentavos(null)).toBeNull()
    expect(aCentavos(undefined)).toBeNull()
    expect(aCentavos('')).toBeNull()
    expect(aCentavos('   ')).toBeNull()
    expect(aCentavos({})).toBeNull()
    expect(aCentavos(NaN)).toBeNull()
    expect(aCentavos(Infinity)).toBeNull()
  })

  it('lo que manda el servidor (punto decimal, 2 decimales)', () => {
    expect(aCentavos('1234.56')).toBe(123456)
    expect(aCentavos('-1234.56')).toBe(-123456)
    expect(aCentavos('0.05')).toBe(5)
    expect(aCentavos('-0.05')).toBe(-5)
    expect(aCentavos('1000.00')).toBe(100000)
  })

  it('formato argentino con y sin miles', () => {
    expect(aCentavos('1.234,56')).toBe(123456)
    expect(aCentavos('1234,56')).toBe(123456)
    expect(aCentavos('1.234.567,89')).toBe(123456789)
    expect(aCentavos('1.234')).toBe(123400)          // miles, no 1,234 pesos
    expect(aCentavos('15.000,5')).toBe(1500050)
    expect(aCentavos('0,50')).toBe(50)
    expect(aCentavos('7')).toBe(700)
  })

  it('formato US', () => {
    expect(aCentavos('1,234.56')).toBe(123456)
    expect(aCentavos('1,234,567.89')).toBe(123456789)
  })

  it('signo: adelante, atrás, paréntesis, tipográfico', () => {
    expect(aCentavos('-1.234,56')).toBe(-123456)
    expect(aCentavos('1.234,56-')).toBe(-123456)
    expect(aCentavos('(1.234,56)')).toBe(-123456)
    expect(aCentavos('−1.234,56')).toBe(-123456)
    expect(aCentavos('+1.234,56')).toBe(123456)
    expect(aCentavos('$ 1.234,56')).toBe(123456)
    expect(aCentavos('-$ 1.234,56')).toBe(-123456)
  })

  it('cero con signo no da -0', () => {
    expect(Object.is(aCentavos('-0,00'), 0)).toBe(true)
    expect(Object.is(aCentavos('(0)'), 0)).toBe(true)
  })

  it('números: redondea a centavos sin errores de float', () => {
    expect(aCentavos(1234.56)).toBe(123456)
    expect(aCentavos(0.1 + 0.2)).toBe(30)
    expect(aCentavos(-19.99)).toBe(-1999)
    expect(aCentavos(1.1)).toBe(110)
  })

  it('rechaza lo ambiguo o con más de 2 decimales antes que adivinar', () => {
    expect(aCentavos('1.234,567')).toBeNull()
    expect(aCentavos('1234.567')).toBeNull()
    expect(aCentavos('1,234')).toBeNull()
    expect(aCentavos('12.34.56')).toBeNull()
    expect(aCentavos('abc')).toBeNull()
    expect(aCentavos('12a')).toBeNull()
    expect(aCentavos('--5')).toBeNull()
    expect(aCentavos('-')).toBeNull()
    expect(aCentavos('()')).toBeNull()
    expect(aCentavos('1e5')).toBeNull()
    expect(aCentavos('1.234,')).toBeNull()
  })
})

describe('formato', () => {
  it('formatearCentavos agrupa miles con punto y decimales con coma', () => {
    expect(formatearCentavos(0)).toBe('0,00')
    expect(formatearCentavos(5)).toBe('0,05')
    expect(formatearCentavos(123456)).toBe('1.234,56')
    expect(formatearCentavos(-123456)).toBe('-1.234,56')
    expect(formatearCentavos(100000000)).toBe('1.000.000,00')
    expect(formatearCentavos(-50)).toBe('-0,50')
  })

  it('formatearPesos', () => {
    expect(formatearPesos(123456)).toBe('$ 1.234,56')
    expect(formatearPesos(-123456)).toBe('-$ 1.234,56')
    expect(formatearPesos(0)).toBe('$ 0,00')
    expect(formatearPesos(null)).toBe('—')
    expect(formatearPesos(undefined)).toBe('—')
  })

  it('centavosAInput no lleva signo y vuelve a parsear igual', () => {
    expect(centavosAInput(-123456)).toBe('1.234,56')
    expect(aCentavos(centavosAInput(123456))).toBe(123456)
    expect(aCentavos(centavosAInput(5))).toBe(5)
  })

  it('centavosAServidor: punto, 2 decimales, sin miles', () => {
    expect(centavosAServidor(123456)).toBe('1234.56')
    expect(centavosAServidor(-123456)).toBe('-1234.56')
    expect(centavosAServidor(5)).toBe('0.05')
    expect(centavosAServidor(-5)).toBe('-0.05')
    expect(centavosAServidor(0)).toBe('0.00')
    expect(aCentavos(centavosAServidor(-987654321))).toBe(-987654321)
  })
})

describe('montoDeFila', () => {
  it('débito → negativo, crédito → positivo', () => {
    expect(montoDeFila('200,00', '')).toEqual({ centavos: -20000, error: null })
    expect(montoDeFila('', '1.700,50')).toEqual({ centavos: 170050, error: null })
    expect(montoDeFila('0,00', '35')).toEqual({ centavos: 3500, error: null })
  })

  it('vacío, cero, texto inválido, signo y las dos columnas', () => {
    expect(montoDeFila('', '').error).toBe('vacio')
    expect(montoDeFila('  ', ' ').error).toBe('vacio')
    expect(montoDeFila('0', '').error).toBe('cero')
    expect(montoDeFila('0,00', '0,00').error).toBe('cero')
    expect(montoDeFila('abc', '').error).toBe('invalido')
    expect(montoDeFila('', '1.2.3').error).toBe('invalido')
    expect(montoDeFila('-200', '').error).toBe('invalido')
    expect(montoDeFila('', '(5)').error).toBe('invalido')
    expect(montoDeFila('10', '20').error).toBe('ambos')
  })
})

const fila = (monto: number | null, saldo: number | null = null) => ({ monto, saldo })

describe('validarSaldos (espeja el backend)', () => {
  it('ascendente con saldos explícitos: cierra', () => {
    const c = validarSaldos([fila(-20000, 80000), fila(70000, 150000)], {
      orden: 'asc', saldoInicial: 100000, saldoFinal: 150000,
    })
    expect(c.cierra).toBe(true)
    expect(c.diferencia).toBe(0)
    expect(c.totalCreditos).toBe(70000)
    expect(c.totalDebitos).toBe(20000)
    expect(c.cantidad).toBe(2)
    expect(c.saldoFinalCalculado).toBe(150000)
    expect(c.filasConSalto).toEqual([])
    expect(c.saldoInicialInferido).toBe(false)
    expect(c.saldoFinalInferido).toBe(false)
  })

  it('descendente: infiere saldo inicial y final de las filas', () => {
    const c = validarSaldos([fila(70000, 150000), fila(-20000, 80000)], {
      orden: 'desc', saldoInicial: null, saldoFinal: null,
    })
    expect(c.saldoInicial).toBe(100000)
    expect(c.saldoInicialInferido).toBe(true)
    expect(c.saldoFinal).toBe(150000)
    expect(c.saldoFinalInferido).toBe(true)
    expect(c.cierra).toBe(true)
  })

  it('salto de saldo: índices en el orden recibido (desc)', () => {
    const c = validarSaldos(
      [fila(1000, 13000), fila(1000, 11500), fila(1000, 11000)],
      { orden: 'desc', saldoInicial: 10000, saldoFinal: null },
    )
    expect(c.filasConSalto).toEqual([0, 1])
    // Los totales dan, pero dos saltos que se compensan no son un extracto que cierra.
    expect(c.diferencia).toBe(0)
    expect(c.cierra).toBe(false)
  })

  it('sin saldo en la última fila: no deduce el final de importes que no se pueden controlar', () => {
    const c = validarSaldos([fila(500, 10500), fila(-100)], { orden: 'asc', saldoInicial: null, saldoFinal: null })
    expect(c.saldoFinal).toBeNull()
    expect(c.saldoFinalInferido).toBe(false)
    expect(c.cierra).toBe(false)
  })

  it('sin saldos: no cierra y no hay diferencia', () => {
    const c = validarSaldos([fila(500), fila(-100)], { orden: 'asc', saldoInicial: null, saldoFinal: null })
    expect(c.cierra).toBe(false)
    expect(c.diferencia).toBeNull()
    expect(c.saldoFinalCalculado).toBeNull()
  })

  it('saldo solo en la segunda fila: se deduce el inicial restando los montos hasta ahí', () => {
    const c = validarSaldos([fila(500), fila(-100, 10400)], { orden: 'asc', saldoInicial: null, saldoFinal: null })
    expect(c.saldoInicial).toBe(10000)
    expect(c.cierra).toBe(true)
  })

  it('sin filas: cierra si los saldos coinciden', () => {
    const c = validarSaldos([], { orden: 'asc', saldoInicial: 100, saldoFinal: 100 })
    expect(c.cierra).toBe(true)
    expect(c.cantidad).toBe(0)
  })

  it('diferencia total: calcula cuánto falta', () => {
    const c = validarSaldos([fila(10000), fila(-3000)], { orden: 'asc', saldoInicial: 0, saldoFinal: 7500 })
    expect(c.saldoFinalCalculado).toBe(7000)
    expect(c.diferencia).toBe(500)
    expect(c.cierra).toBe(false)
  })

  it('tolerancia de 1 centavo (inclusive) y no más', () => {
    const base = [fila(10000)]
    expect(validarSaldos(base, { orden: 'asc', saldoInicial: 0, saldoFinal: 10001 }).cierra).toBe(true)
    expect(validarSaldos(base, { orden: 'asc', saldoInicial: 0, saldoFinal: 9999 }).cierra).toBe(true)
    expect(validarSaldos(base, { orden: 'asc', saldoInicial: 0, saldoFinal: 10002 }).cierra).toBe(false)
  })

  it('un monto ilegible (null) cuenta como cero', () => {
    const c = validarSaldos([fila(null), fila(500)], { orden: 'asc', saldoInicial: 0, saldoFinal: 500 })
    expect(c.cierra).toBe(true)
    expect(c.totalCreditos).toBe(500)
  })

  it('centavos exactos con muchas filas (sin deriva de float)', () => {
    const filas = Array.from({ length: 1000 }, () => fila(10)) // 1000 × $0,10
    const c = validarSaldos(filas, { orden: 'asc', saldoInicial: 0, saldoFinal: 10000 })
    expect(c.totalCreditos).toBe(10000)
    expect(c.cierra).toBe(true)
  })

  it('si falta el saldo inicial, sin saldos en filas, queda sin calcular', () => {
    const c = validarSaldos([fila(500)], { orden: 'asc', saldoInicial: null, saldoFinal: 500 })
    expect(c.saldoInicial).toBeNull()
    expect(c.diferencia).toBeNull()
    expect(c.cierra).toBe(false)
  })
})
