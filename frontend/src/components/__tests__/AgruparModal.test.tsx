import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { AgruparModal } from '../AgruparModal'

const movimientosLibres = vi.fn()
const crearGrupo = vi.fn()

vi.mock('@/services/api', () => ({
  apiClient: {
    movimientosLibres: (...a: unknown[]) => movimientosLibres(...a),
    crearGrupo: (...a: unknown[]) => crearGrupo(...a),
  },
}))

const MOVS = [
  { id: 11, orden: 1, fecha: '2026-10-10', titular: 'TRANSF JUAN PEREZ', monto: 3000, source: 'extracto' },
  { id: 12, orden: 2, fecha: '2026-10-10', titular: 'TRANSF OTRO', monto: 2990, source: 'extracto' },
  { id: 13, orden: 3, fecha: '2026-10-11', titular: 'TRANSF JUAN PEREZ', monto: 2000, source: 'um' },
]

const dosFilas = [{ id: 1, monto: 1000, titular: 'Juan Perez' }, { id: 2, monto: 2000, titular: 'Juan Perez' }]

describe('AgruparModal', () => {
  beforeEach(() => {
    movimientosLibres.mockReset().mockResolvedValue({ planilla_id: 5, tolerancia: 0.01, movimientos: MOVS })
    crearGrupo.mockReset().mockResolvedValue({ id: 9 })
  })

  it('subtotal en verde cuando cuadra y concilia el grupo', async () => {
    const onHecho = vi.fn()
    render(<AgruparModal planillaId={5} filas={dosFilas} onClose={() => {}} onHecho={onHecho} />)
    fireEvent.click(await screen.findByLabelText(/Movimiento TRANSF JUAN PEREZ .*3\.000,00/))
    const sub = screen.getByTestId('subtotal-grupo')
    expect(sub).toHaveTextContent('Cuadra')
    expect(sub.className).toMatch(/green/)
    fireEvent.click(screen.getByRole('button', { name: 'Conciliar grupo' }))
    await waitFor(() => expect(onHecho).toHaveBeenCalled())
    expect(crearGrupo).toHaveBeenCalledWith(5, [1, 2], [11], false)
  })

  it('subtotal en rojo con la diferencia; solo se confirma marcando "con diferencia"', async () => {
    render(<AgruparModal planillaId={5} filas={dosFilas} onClose={() => {}} onHecho={() => {}} />)
    fireEvent.click(await screen.findByLabelText(/Movimiento TRANSF OTRO/))
    const sub = screen.getByTestId('subtotal-grupo')
    expect(sub.className).toMatch(/red/)
    expect(sub).toHaveTextContent('Diferencia')
    expect(sub).toHaveTextContent(/-\s?\$\s?10,00/)
    const boton = screen.getByRole('button', { name: 'Conciliar con diferencia' })
    expect(boton).toBeDisabled()
    fireEvent.click(screen.getByRole('checkbox', { name: /conciliar igual/i }))
    expect(boton).toBeEnabled()
    fireEvent.click(boton)
    await waitFor(() => expect(crearGrupo).toHaveBeenCalledWith(5, [1, 2], [12], true))
  })

  it('una fila contra varios movimientos suma en vivo', async () => {
    render(<AgruparModal planillaId={5} filas={[{ id: 7, monto: 5000 }]} onClose={() => {}} onHecho={() => {}} />)
    const checks = await screen.findAllByRole('checkbox')
    fireEvent.click(checks[0]) // 3000
    expect(screen.getByRole('button', { name: /Conciliar/ })).toBeDisabled() // 1 contra 1: usar Asignar
    fireEvent.click(checks[2]) // + 2000 = 5000
    expect(screen.getByTestId('subtotal-grupo')).toHaveTextContent('Cuadra')
    fireEvent.click(screen.getByRole('button', { name: 'Conciliar grupo' }))
    await waitFor(() => expect(crearGrupo).toHaveBeenCalledWith(5, [7], [11, 13], false))
  })

  it('muestra el error del servidor', async () => {
    crearGrupo.mockRejectedValue({ response: { data: { detail: 'Algún movimiento ya está en otro grupo' } } })
    render(<AgruparModal planillaId={5} filas={dosFilas} onClose={() => {}} onHecho={() => {}} />)
    fireEvent.click(await screen.findByLabelText(/Movimiento TRANSF JUAN PEREZ .*3\.000,00/))
    fireEvent.click(screen.getByRole('button', { name: 'Conciliar grupo' }))
    expect(await screen.findByText('Algún movimiento ya está en otro grupo')).toBeInTheDocument()
  })
})
