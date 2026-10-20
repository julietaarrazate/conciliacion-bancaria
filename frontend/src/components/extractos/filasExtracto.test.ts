import { describe, it, expect } from 'vitest'
import { armarPayload, esFechaIso, evaluarFilas, filaDesdeMovimiento, filaVacia, fmtFechaAr } from './filasExtracto'

describe('esFechaIso', () => {
  it('acepta fechas reales y rechaza las que no existen', () => {
    expect(esFechaIso('2026-09-30')).toBe(true)
    expect(esFechaIso('2028-02-29')).toBe(true)
    expect(esFechaIso('2026-02-29')).toBe(false)
    expect(esFechaIso('2026-02-31')).toBe(false)
    expect(esFechaIso('2026-13-01')).toBe(false)
    expect(esFechaIso('30/09/2026')).toBe(false)
    expect(esFechaIso('')).toBe(false)
  })
})

describe('fmtFechaAr', () => {
  it('da vuelta YYYY-MM-DD sin pasar por Date', () => {
    expect(fmtFechaAr('2026-09-01')).toBe('01/09/2026')
    expect(fmtFechaAr(null)).toBe('')
  })
})

const mov = (monto: string, saldo: string | null, fecha = '2026-09-02') => ({
  fecha, descripcion: 'X', monto, saldo, pagina: 1, dudosa: false, motivos: [],
})

describe('evaluarFilas', () => {
  it('pasa del monto con signo a las columnas y de vuelta', () => {
    const f = filaDesdeMovimiento(mov('-1234.50', '99.00'))
    expect(f.debito).toBe('1.234,50')
    expect(f.credito).toBe('')
    expect(f.saldo).toBe('99,00')
    const ev = evaluarFilas([f], 'asc', '', '')
    expect(ev.filas[0].centavos).toBe(-123450)
    expect(ev.filas[0].errores).toEqual([])
  })

  it('un saldo negativo (descubierto) conserva el signo', () => {
    const f = filaDesdeMovimiento(mov('-10.00', '-25.50'))
    expect(f.saldo).toBe('-25,50')
    expect(evaluarFilas([f], 'asc', '', '').filas[0].saldoCentavos).toBe(-2550)
  })

  it('marca fecha, importe y saldo inválidos por separado', () => {
    const f = { ...filaVacia(''), debito: 'abc', saldo: '1.2.3' }
    const [ev] = evaluarFilas([f], 'asc', '', '').filas
    expect(ev.errores.map(e => e.campo).sort()).toEqual(['fecha', 'importe', 'saldo'])
  })

  it('rechaza importes de 10^10 pesos o más, como el servidor', () => {
    const justo = { ...filaVacia('2026-09-01'), credito: '9.999.999.999,99' }
    const pasado = { ...filaVacia('2026-09-01'), credito: '10.000.000.000,00' }
    expect(evaluarFilas([justo], 'asc', '', '').filasConError).toBe(0)
    expect(evaluarFilas([pasado], 'asc', '', '').filasConError).toBe(1)
  })

  it('cuenta filas dudosas: las de la lectura y las que cortan el saldo', () => {
    const a = filaDesdeMovimiento({ ...mov('-10.00', '90.00'), dudosa: true, motivos: ['Signo deducido'] })
    const b = filaDesdeMovimiento(mov('-10.00', '70.00')) // debería ser 80
    const c = filaDesdeMovimiento(mov('-10.00', '60.00'))
    const ev = evaluarFilas([a, b, c], 'asc', '100,00', '')
    expect(ev.filas[0].avisos).toEqual(['Signo deducido'])
    expect(ev.filas[1].avisos).toEqual(['El saldo no sigue'])
    expect(ev.filas[2].avisos).toEqual([]) // 70 − 10 = 60: desde b el saldo vuelve a seguir
    expect(ev.filasDudosas).toBe(2)
  })

  it('"El saldo no sigue" de la lectura se recalcula: al borrar el saldo inicial que no coincide, se va', () => {
    const a = filaDesdeMovimiento({ ...mov('500.00', '1500.00'), dudosa: true, motivos: ['El saldo no sigue'] })
    const b = filaDesdeMovimiento({ ...mov('-200.00', '1300.00'), dudosa: true, motivos: ['Sin fecha', 'El saldo no sigue'] })
    expect(a.motivosLectura).toEqual([])
    expect(b.motivosLectura).toEqual(['Sin fecha'])
    const conElDelPdf = evaluarFilas([a, b], 'asc', '2.000,00', '')
    expect(conElDelPdf.filas[0].avisos).toEqual(['El saldo no sigue'])
    const borrado = evaluarFilas([a, b], 'asc', '', '')
    expect(borrado.cuadre.cierra).toBe(true)
    expect(borrado.filas[0].avisos).toEqual([])
    expect(borrado.filasDudosas).toBe(1)
  })

  it('el saldo inicial o final escrito pero ilegible se reporta', () => {
    const ev = evaluarFilas([], 'asc', 'x', '1.000,00')
    expect(ev.saldoInicialInvalido).toBe(true)
    expect(ev.saldoFinalInvalido).toBe(false)
  })
})

describe('armarPayload', () => {
  it('manda strings con punto, respeta el orden y omite el nombre no tocado', () => {
    const filas = [filaDesdeMovimiento(mov('-200.00', '800.00')), filaDesdeMovimiento(mov('700.00', null, '2026-09-05'))]
    const evaluacion = evaluarFilas(filas, 'asc', '1.000,00', '1.500,00')
    const p = armarPayload({
      filas, evaluacion, saldoInicial: '1.000,00', saldoFinal: '1.500,00', banco: ' Galicia ',
      nombre: null, destino: 'nuevo', extractoDestinoId: 7, confirmarSinCuadre: false,
    })
    expect(p.movimientos).toEqual([
      { fecha: '2026-09-02', descripcion: 'X', monto: '-200.00', saldo: '800.00' },
      { fecha: '2026-09-05', descripcion: 'X', monto: '700.00', saldo: null },
    ])
    expect(p.saldo_inicial).toBe('1000.00')
    expect(p.saldo_final).toBe('1500.00')
    expect(p.banco).toBe('Galicia')
    expect(p.nombre).toBeNull()
    expect(p.extracto_id).toBeNull() // destino nuevo: el id del extracto existente no viaja
  })

  it('saldos vacíos viajan como null (el servidor los deduce)', () => {
    const filas = [filaDesdeMovimiento(mov('5.00', '5.00'))]
    const p = armarPayload({
      filas, evaluacion: evaluarFilas(filas, 'asc', '', ''), saldoInicial: '', saldoFinal: '  ', banco: '',
      nombre: '  ', destino: 'existente', extractoDestinoId: 7, confirmarSinCuadre: true,
    })
    expect(p.saldo_inicial).toBeNull()
    expect(p.saldo_final).toBeNull()
    expect(p.banco).toBeNull()
    expect(p.nombre).toBeNull()
    expect(p.destino).toBe('existente')
    expect(p.extracto_id).toBe(7)
    expect(p.confirmar_sin_cuadre).toBe(true)
  })
})
