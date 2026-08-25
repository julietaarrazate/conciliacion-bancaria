import { describe, it, expect } from 'vitest'
import { parseMonto } from './monto'

describe('parseMonto', () => {
  it('null/undefined/vacío → null', () => {
    expect(parseMonto(null)).toBeNull()
    expect(parseMonto(undefined)).toBeNull()
    expect(parseMonto('')).toBeNull()
    expect(parseMonto('   ')).toBeNull()
  })

  it('number se devuelve tal cual (NaN → null)', () => {
    expect(parseMonto(15000)).toBe(15000)
    expect(parseMonto(0)).toBe(0)
    expect(parseMonto(1234.56)).toBe(1234.56)
    expect(parseMonto(NaN)).toBeNull()
  })

  it('formato argentino: punto miles + coma decimal', () => {
    expect(parseMonto('15.000,50')).toBe(15000.5)
    expect(parseMonto('1.200.000,50')).toBe(1200000.5)
    expect(parseMonto('15.000')).toBe(15000)        // solo miles, sin decimales
    expect(parseMonto('1.787.142')).toBe(1787142)
  })

  it('formato US: coma miles + punto decimal', () => {
    expect(parseMonto('15,000.50')).toBe(15000.5)
    expect(parseMonto('1,200,000.50')).toBe(1200000.5)
  })

  it('coma decimal sin separador de miles', () => {
    expect(parseMonto('15000,50')).toBe(15000.5)
    expect(parseMonto('120697,20')).toBe(120697.2)
  })

  it('número plano con o sin punto decimal', () => {
    expect(parseMonto('15000')).toBe(15000)
    expect(parseMonto('15000.50')).toBe(15000.5)
    expect(parseMonto('143637')).toBe(143637)
  })

  it('ignora símbolo $ y espacios', () => {
    expect(parseMonto('$ 15.000,50')).toBe(15000.5)
    expect(parseMonto(' $1.200.000,50 ')).toBe(1200000.5)
  })

  it('basura → null o número parcial pero nunca rompe', () => {
    expect(parseMonto('abc')).toBeNull()
    expect(parseMonto('--')).toBeNull()
  })

  it('casos reales del extracto (no pierde centavos)', () => {
    expect(parseMonto('3.607.774,80')).toBe(3607774.8)
    expect(parseMonto('547.796,00')).toBe(547796)
  })
})
