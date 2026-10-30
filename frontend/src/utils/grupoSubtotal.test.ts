import { describe, it, expect } from 'vitest'
import { subtotalGrupo, formaGrupoValida } from './grupoSubtotal'

describe('subtotalGrupo', () => {
  it('cuadra cuando la suma de las filas es igual al movimiento', () => {
    const s = subtotalGrupo([1000, 2000], [3000])
    expect(s).toEqual({ totalFilas: 3000, totalMovimientos: 3000, diferencia: 0, cuadra: true })
  })

  it('no arrastra errores de punto flotante', () => {
    expect(subtotalGrupo([0.1, 0.2], [0.3]).cuadra).toBe(true)
    expect(subtotalGrupo([1000.1, 1999.95], [3000.05]).diferencia).toBe(0)
  })

  it('marca la diferencia con signo (movimientos − filas)', () => {
    const s = subtotalGrupo([1000, 2000], [2990])
    expect(s.cuadra).toBe(false)
    expect(s.diferencia).toBe(-10)
    expect(subtotalGrupo([5000], [2000, 3500]).diferencia).toBe(500)
  })

  it('respeta la tolerancia de la organización', () => {
    expect(subtotalGrupo([100], [100.5], 1).cuadra).toBe(true)
    expect(subtotalGrupo([100], [101], 1).cuadra).toBe(false)
  })
})

describe('formaGrupoValida', () => {
  it('acepta varias filas contra un movimiento o una fila contra varios', () => {
    expect(formaGrupoValida(2, 1)).toBe(true)
    expect(formaGrupoValida(1, 3)).toBe(true)
  })

  it('rechaza 1 contra 1, varios contra varios y lados vacíos', () => {
    expect(formaGrupoValida(1, 1)).toBe(false)
    expect(formaGrupoValida(2, 2)).toBe(false)
    expect(formaGrupoValida(0, 3)).toBe(false)
    expect(formaGrupoValida(3, 0)).toBe(false)
  })
})
