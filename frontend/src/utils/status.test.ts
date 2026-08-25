import { describe, it, expect } from 'vitest'
import { statusLabel } from './status'

describe('statusLabel', () => {
  it('traduce los estados base', () => {
    expect(statusLabel('ok')).toBe('Acreditado ✓')
    expect(statusLabel('no está')).toBe('No encontrado ✕')
    expect(statusLabel('duplicado')).toBe('Duplicado ⚠')
    expect(statusLabel('faltan datos')).toBe('Sin datos ?')
    expect(statusLabel('pendiente')).toBe('Pendiente')
  })

  it('maneja variantes con detalle', () => {
    expect(statusLabel('ok (aprendido)')).toBe('Acreditado ✓')
    expect(statusLabel('acreditado 15/06')).toBe('Acreditado ✓ 15/06')
    expect(statusLabel('ambiguo (2 candidatos, mismo score)')).toBe('Ambiguo — elegir a mano')
    expect(statusLabel('sin datos (3 mov. del mismo monto — agregar CUIT/CBU/titular)')).toBe('Sin datos ?')
    expect(statusLabel('no coincide (2 mov. del mismo monto — revisar CUIT/CBU/titular)')).toBe('No coincide — revisar')
  })

  it('estados ricos y desconocidos', () => {
    expect(statusLabel('PAGO_PARCIAL')).toBe('Pago parcial')
    expect(statusLabel('EN_REVISION')).toBe('En revisión')
    expect(statusLabel('algo raro')).toBe('algo raro')
    expect(statusLabel(null)).toBe('—')
    expect(statusLabel(undefined)).toBe('—')
  })
})
