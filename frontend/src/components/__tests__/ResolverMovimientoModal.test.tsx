import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { ResolverMovimientoModal } from '../ResolverMovimientoModal'
import { MovimientoFiltrado } from '@/types'

const listarCategoriasEgreso = vi.fn()
const crearPagoDesdeMovimiento = vi.fn()
const pagosCandidatosMovimiento = vi.fn()
const vincularPagoAMovimiento = vi.fn()

vi.mock('@/services/api', () => ({
  apiClient: {
    listarCategoriasEgreso: (...a: unknown[]) => listarCategoriasEgreso(...a),
    crearPagoDesdeMovimiento: (...a: unknown[]) => crearPagoDesdeMovimiento(...a),
    pagosCandidatosMovimiento: (...a: unknown[]) => pagosCandidatosMovimiento(...a),
    vincularPagoAMovimiento: (...a: unknown[]) => vincularPagoAMovimiento(...a),
  },
}))

const debito: MovimientoFiltrado = {
  id: 7, extracto_id: 3, fecha: '2026-10-01', titular: 'TRANSF A PROVEEDOR SA', monto: -1500.5,
}

describe('ResolverMovimientoModal', () => {
  beforeEach(() => {
    listarCategoriasEgreso.mockReset().mockResolvedValue([{ id: 1, nombre: 'Bancarios' }, { id: 2, nombre: 'Alquiler' }])
    crearPagoDesdeMovimiento.mockReset().mockResolvedValue({ ok: true, egreso: { id: 42 } })
    pagosCandidatosMovimiento.mockReset().mockResolvedValue([])
    vincularPagoAMovimiento.mockReset().mockResolvedValue({ ok: true, egreso: { id: 31 } })
  })

  it('precarga los datos del movimiento con el importe en positivo y fijo', async () => {
    render(<ResolverMovimientoModal mov={debito} onClose={() => {}} onResuelto={() => {}} />)
    expect(screen.getByLabelText('Concepto')).toHaveValue('TRANSF A PROVEEDOR SA')
    expect(screen.getByLabelText('Beneficiario')).toHaveValue('TRANSF A PROVEEDOR SA')
    expect(screen.getByDisplayValue('2026-10-01')).toBeInTheDocument()
    expect(screen.getByText(/1\.500,50/)).toBeInTheDocument()
    await waitFor(() => expect(listarCategoriasEgreso).toHaveBeenCalled())
  })

  it('crea el pago vinculado al movimiento y avisa el id', async () => {
    const onResuelto = vi.fn()
    render(<ResolverMovimientoModal mov={debito} orgId={5} onClose={() => {}} onResuelto={onResuelto} />)
    fireEvent.click(screen.getByRole('button', { name: /registrar pago/i }))
    await waitFor(() => expect(onResuelto).toHaveBeenCalledWith(42))
    expect(crearPagoDesdeMovimiento).toHaveBeenCalledWith(expect.objectContaining({
      movimiento_banco_id: 7, monto: 1500.5, forma_pago: 'banco', tipo: 'gasto',
      fecha: '2026-10-01', concepto: 'TRANSF A PROVEEDOR SA', org_id: 5,
    }))
  })

  it('un gasto bancario reconocido sugiere la categoría bancaria', async () => {
    render(<ResolverMovimientoModal mov={{ ...debito, gasto_bancario: 'Comisiones y mantenimiento' }}
      onClose={() => {}} onResuelto={() => {}} />)
    await waitFor(() => expect((screen.getByLabelText('Categoría') as HTMLSelectElement).value).toBe('Bancarios'))
  })

  it('un proveedor exige el nombre', async () => {
    render(<ResolverMovimientoModal mov={debito} onClose={() => {}} onResuelto={() => {}} />)
    fireEvent.change(screen.getByLabelText('Tipo'), { target: { value: 'proveedor' } })
    fireEvent.change(screen.getByLabelText('Proveedor'), { target: { value: '' } })
    fireEvent.click(screen.getByRole('button', { name: /registrar pago/i }))
    expect(await screen.findByText(/Ingresá el proveedor/)).toBeInTheDocument()
    expect(crearPagoDesdeMovimiento).not.toHaveBeenCalled()
  })

  it('muestra el error del servidor', async () => {
    crearPagoDesdeMovimiento.mockRejectedValue({ response: { data: { detail: 'El movimiento ya está explicado por el pago #9' } } })
    render(<ResolverMovimientoModal mov={debito} onClose={() => {}} onResuelto={() => {}} />)
    fireEvent.click(screen.getByRole('button', { name: /registrar pago/i }))
    expect(await screen.findByText(/ya está explicado por el pago #9/)).toBeInTheDocument()
  })

  it('ofrece vincular un pago ya cargado por el mismo importe en vez de crear otro', async () => {
    pagosCandidatosMovimiento.mockResolvedValue([
      { id: 31, fecha: '2026-09-29', beneficiario: 'Proveedor SA', concepto: 'Factura 0001-123', monto: 1500.5, dias_diferencia: 2 },
    ])
    const onResuelto = vi.fn()
    render(<ResolverMovimientoModal mov={debito} orgId={5} onClose={() => {}} onResuelto={onResuelto} />)
    expect(await screen.findByText(/ya cargado/i)).toBeInTheDocument()
    expect(screen.getByText('Proveedor SA')).toBeInTheDocument()
    expect(pagosCandidatosMovimiento).toHaveBeenCalledWith(7, 5)
    fireEvent.click(screen.getByRole('button', { name: /vincular/i }))
    await waitFor(() => expect(onResuelto).toHaveBeenCalledWith(31))
    expect(vincularPagoAMovimiento).toHaveBeenCalledWith(31, 7)
    expect(crearPagoDesdeMovimiento).not.toHaveBeenCalled()
  })

  it('sin pagos parecidos no muestra la sección de vincular', async () => {
    render(<ResolverMovimientoModal mov={debito} onClose={() => {}} onResuelto={() => {}} />)
    await waitFor(() => expect(pagosCandidatosMovimiento).toHaveBeenCalled())
    expect(screen.queryByRole('button', { name: /vincular/i })).not.toBeInTheDocument()
  })
})
