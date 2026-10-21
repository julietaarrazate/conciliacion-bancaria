import { render, screen, fireEvent, waitFor, within } from '@testing-library/react'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import type { GrillaVencimientos } from '@/types'

const api = vi.hoisted(() => ({
  getGrillaVencimientos: vi.fn(),
  marcarVencimiento: vi.fn(),
  desmarcarVencimiento: vi.fn(),
  getCalendarioVencimientos: vi.fn(),
  guardarCalendarioVencimientos: vi.fn(),
}))
const auth = vi.hoisted(() => ({ superadmin: false, permisos: true }))

vi.mock('@/services/api', () => ({ apiClient: api }))
vi.mock('@/store/auth', () => ({
  useAuthStore: () => ({ user: { is_superadmin: auth.superadmin }, hasPermission: () => auth.permisos }),
}))

import { Vencimientos } from '../Vencimientos'

const grilla: GrillaVencimientos = {
  mes: '2026-10',
  hoy: '2026-10-21',
  impuestos: { iva: 'IVA (F.2002)', monotributo: 'Monotributo', iibb_cm: 'IIBB Convenio Multilateral', f931: 'F.931 cargas sociales' },
  filas: [
    { organizacion_id: 1, nombre: 'Estudio', cuit: '30700000008', obligaciones: [
      { impuesto: 'iva', nombre: 'IVA (F.2002)', periodo: '2026-09', fecha: '2026-10-23', motivo: null, estado: 'proximo', presentado_por: null },
      { impuesto: 'f931', nombre: 'F.931 cargas sociales', periodo: '2026-09', fecha: '2026-10-14', motivo: null, estado: 'presentado', presentado_por: 'modulo' },
    ] },
    { organizacion_id: 2, nombre: 'Cliente Dos', cuit: null, obligaciones: [
      { impuesto: 'monotributo', nombre: 'Monotributo', periodo: '2026-10', fecha: null, motivo: 'sin_cuit', estado: 'pendiente', presentado_por: null },
    ] },
    { organizacion_id: 3, nombre: 'Cliente Tres', cuit: '20111111112', obligaciones: [
      { impuesto: 'iva', nombre: 'IVA (F.2002)', periodo: '2026-09', fecha: null, motivo: 'sin_calendario', estado: 'pendiente', presentado_por: null },
      { impuesto: 'monotributo', nombre: 'Monotributo', periodo: '2026-10', fecha: '2026-10-20', motivo: null, estado: 'presentado', presentado_por: 'manual' },
    ] },
  ],
}

describe('Vencimientos', () => {
  beforeEach(() => {
    auth.superadmin = false
    auth.permisos = true
    Object.values(api).forEach(f => f.mockReset())
    api.getGrillaVencimientos.mockResolvedValue(grilla)
    api.marcarVencimiento.mockResolvedValue({ ok: true })
    api.desmarcarVencimiento.mockResolvedValue({ ok: true })
    api.getCalendarioVencimientos.mockResolvedValue([])
    api.guardarCalendarioVencimientos.mockResolvedValue([])
  })

  it('muestra la grilla con estados y avisos', async () => {
    render(<Vencimientos />)
    const estudio = (await screen.findByText('Estudio')).closest('tr')!
    expect(within(estudio).getByText('23/10')).toBeInTheDocument()
    expect(within(estudio).getByText(/vence pronto/i)).toBeInTheDocument()
    expect(within(estudio).getByText('Presentado')).toBeInTheDocument()
    const dos = screen.getByText('Cliente Dos').closest('tr')!
    expect(within(dos).getByText('Sin CUIT')).toBeInTheDocument()
    expect(within(dos).getByText('Sin CUIT cargado')).toBeInTheDocument()
    const tres = screen.getByText('Cliente Tres').closest('tr')!
    expect(within(tres).getByText(/falta el calendario/i)).toBeInTheDocument()
    expect(api.getGrillaVencimientos).toHaveBeenCalledWith(expect.stringMatching(/^\d{4}-\d{2}$/))
  })

  it('marca y desmarca a mano', async () => {
    render(<Vencimientos />)
    const estudio = (await screen.findByText('Estudio')).closest('tr')!
    fireEvent.click(within(estudio).getByRole('button', { name: /marcar presentado/i }))
    await waitFor(() => expect(api.marcarVencimiento).toHaveBeenCalledWith(1, 'iva', '2026-09'))
    const tres = screen.getByText('Cliente Tres').closest('tr')!
    fireEvent.click(within(tres).getByRole('button', { name: /desmarcar/i }))
    await waitFor(() => expect(api.desmarcarVencimiento).toHaveBeenCalledWith(3, 'monotributo', '2026-10'))
    // lo presentado por un módulo no se desmarca desde acá
    expect(within(estudio).queryByRole('button', { name: /desmarcar/i })).not.toBeInTheDocument()
  })

  it('sin permiso no muestra los botones', async () => {
    auth.permisos = false
    render(<Vencimientos />)
    await screen.findByText('Estudio')
    expect(screen.queryByRole('button', { name: /marcar presentado/i })).not.toBeInTheDocument()
  })

  it('el superadmin carga el calendario de un mes', async () => {
    auth.superadmin = true
    render(<Vencimientos />)
    await screen.findByText('Estudio')
    fireEvent.click(screen.getByRole('button', { name: /cargar calendario/i }))
    fireEvent.change(screen.getByLabelText('Impuesto'), { target: { value: 'f931' } })
    fireEvent.change(screen.getByLabelText('Período'), { target: { value: '2026-10' } })
    const fechas = ['2026-11-09', '2026-11-10', '2026-11-11']
    fechas.forEach((f, i) => fireEvent.change(screen.getAllByLabelText(/^CUIT terminado en/)[i], { target: { value: f } }))
    fireEvent.click(screen.getByRole('button', { name: /guardar calendario/i }))
    await waitFor(() => expect(api.guardarCalendarioVencimientos).toHaveBeenCalled())
    const body = api.guardarCalendarioVencimientos.mock.lastCall![0]
    expect(body.impuesto).toBe('f931')
    expect(body.periodo).toBe('2026-10')
    expect(body.fechas).toEqual([
      { terminacion_desde: 0, terminacion_hasta: 3, fecha: '2026-11-09' },
      { terminacion_desde: 4, terminacion_hasta: 6, fecha: '2026-11-10' },
      { terminacion_desde: 7, terminacion_hasta: 9, fecha: '2026-11-11' },
    ])
  })

  it('sin superadmin no se puede cargar el calendario', async () => {
    render(<Vencimientos />)
    await screen.findByText('Estudio')
    expect(screen.queryByRole('button', { name: /cargar calendario/i })).not.toBeInTheDocument()
  })
})
