import { describe, it, expect } from 'vitest'
import { fmtARS, fmtFechaCorta } from './formato'

describe('formato', () => {
  it('fmtARS formatea igual que un Intl.NumberFormat nuevo (es-AR, ARS)', () => {
    const ref = (n: number) => new Intl.NumberFormat('es-AR', { style: 'currency', currency: 'ARS', minimumFractionDigits: 0 }).format(n)
    for (const n of [0, 1500, -2500.5, 1234567.89]) expect(fmtARS(n)).toBe(ref(n))
    expect(fmtARS(null)).toBe('—')
    expect(fmtARS(undefined)).toBe('—')
  })

  it('fmtFechaCorta da dd/mm/aa desde fecha ISO o con hora, sin correrse de día', () => {
    expect(fmtFechaCorta('2026-09-01')).toBe('01/09/26')
    expect(fmtFechaCorta('2026-09-01T00:00:00')).toBe('01/09/26')
    expect(fmtFechaCorta(null)).toBe('—')
    expect(fmtFechaCorta('')).toBe('—')
    expect(fmtFechaCorta('no-es-fecha')).toBe('no-es-fecha')
  })
})
