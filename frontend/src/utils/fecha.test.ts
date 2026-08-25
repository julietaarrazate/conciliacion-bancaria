import { describe, it, expect } from 'vitest'
import { localIsoDate, hoyIso, isoHaceNDias } from './fecha'

describe('localIsoDate', () => {
  it('usa componentes LOCALES (no UTC) y devuelve YYYY-MM-DD', () => {
    // Mes 0-indexado en Date: (2026, 0, 5) = 5 de enero de 2026
    expect(localIsoDate(new Date(2026, 0, 5))).toBe('2026-01-05')
    expect(localIsoDate(new Date(2026, 11, 31))).toBe('2026-12-31')
  })

  it('paddea mes y día de un dígito', () => {
    expect(localIsoDate(new Date(2026, 8, 9))).toBe('2026-09-09')
  })

  it('una fecha local de madrugada no se corre al día anterior (bug UTC-3)', () => {
    // 15/06/2026 01:30 hora local → debe ser 2026-06-15, no 2026-06-14.
    // (toISOString().slice(0,10) daría la fecha en UTC y rompería esto.)
    expect(localIsoDate(new Date(2026, 5, 15, 1, 30))).toBe('2026-06-15')
  })
})

describe('hoyIso / isoHaceNDias', () => {
  it('hoyIso devuelve formato YYYY-MM-DD', () => {
    expect(hoyIso()).toMatch(/^\d{4}-\d{2}-\d{2}$/)
  })

  it('isoHaceNDias(0) === hoyIso()', () => {
    expect(isoHaceNDias(0)).toBe(hoyIso())
  })

  it('isoHaceNDias(7) es 7 días antes de hoy', () => {
    const hoy = new Date()
    const hace7 = new Date()
    hace7.setDate(hoy.getDate() - 7)
    expect(isoHaceNDias(7)).toBe(localIsoDate(hace7))
  })
})
