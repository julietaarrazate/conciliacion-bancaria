import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import type { MovimientoFiltrado } from '@/types'

const api = vi.hoisted(() => ({
  listExtractos: vi.fn(),
  getMovimientos: vi.fn(),
  getResumenExtracto: vi.fn(),
  deleteMovimiento: vi.fn(),
  updateMovimiento: vi.fn(),
}))

// Permisos del usuario del test: null = todos (admin); una lista = solo esos.
const auth = vi.hoisted(() => ({ permisos: null as string[] | null }))

vi.mock('@/services/api', () => ({ apiClient: api }))
vi.mock('@/store/auth', () => ({
  useAuthStore: (sel: (s: { hasPermission: (p: string) => boolean }) => unknown) =>
    sel({ hasPermission: (p: string) => auth.permisos === null || auth.permisos.includes(p) }),
}))
vi.mock('@/store/org', () => ({ useOrgStore: () => ({ activeOrgId: null }) }))
vi.mock('@/store/confirm', () => ({ confirmDialog: () => Promise.resolve(true) }))

import { Movimientos } from '../Movimientos'

const movs: MovimientoFiltrado[] = [
  { id: 1, extracto_id: 7, orden: 1, fecha: '2026-09-01', titular: 'GARCIA LOPEZ', monto: 1500, saldo: 1500, source: 'extracto' },
  { id: 2, extracto_id: 7, orden: 2, fecha: '2026-09-02', titular: 'PEREZ DIAZ', monto: 2500, saldo: 4000, source: 'extracto' },
]

const renderPage = () => render(<MemoryRouter><Movimientos /></MemoryRouter>)

describe('Movimientos', () => {
  beforeEach(() => {
    Object.values(api).forEach(f => f.mockReset())
    auth.permisos = null
    api.listExtractos.mockResolvedValue({ total: 1, items: [{ id: 7, nombre_archivo: 'ext.xlsx', total_movimientos: 2 }] })
    api.getMovimientos.mockResolvedValue({ extracto_id: 7, total: 2, items: movs })
    api.getResumenExtracto.mockResolvedValue(null)
    api.deleteMovimiento.mockResolvedValue(undefined)
  })

  it('pide el resumen del extracto una sola vez al entrar (no otra vez al llegar la lista)', async () => {
    renderPage()
    expect(await screen.findByText('GARCIA LOPEZ')).toBeInTheDocument()
    await waitFor(() => expect(api.getMovimientos).toHaveBeenCalledTimes(1))
    expect(api.getResumenExtracto).toHaveBeenCalledTimes(1)
    expect(api.getResumenExtracto).toHaveBeenCalledWith(7)
  })

  it('recalcula el resumen después de borrar un movimiento', async () => {
    renderPage()
    await screen.findByText('GARCIA LOPEZ')
    fireEvent.click(screen.getAllByTitle('Borrar movimiento')[0])
    await waitFor(() => expect(api.deleteMovimiento).toHaveBeenCalledWith(7, 1))
    await waitFor(() => expect(screen.queryByText('GARCIA LOPEZ')).not.toBeInTheDocument())
    expect(api.getResumenExtracto).toHaveBeenCalledTimes(2)
  })

  it('al revisor (solo lectura) no le muestra editar, borrar, acreditar ni agregar UM', async () => {
    auth.permisos = ['view_results', 'view_accounting']
    renderPage()
    expect(await screen.findByText('GARCIA LOPEZ')).toBeInTheDocument()
    expect(screen.queryByTitle('Editar datos (titular, importe, fecha)')).not.toBeInTheDocument()
    expect(screen.queryByTitle('Borrar movimiento')).not.toBeInTheDocument()
    expect(screen.queryByText('＋ Acreditar')).not.toBeInTheDocument()
    expect(screen.queryByText(/Agregar UM/)).not.toBeInTheDocument()
  })

  it('al operador le muestra editar, acreditar y agregar UM (sin borrar)', async () => {
    auth.permisos = ['upload_files', 'reconcile', 'manage_finance', 'view_accounting']
    renderPage()
    await screen.findByText('GARCIA LOPEZ')
    expect(screen.getAllByTitle('Editar datos (titular, importe, fecha)')).toHaveLength(2)
    expect(screen.getAllByText('＋ Acreditar')).toHaveLength(2)
    expect(screen.getByText(/Agregar UM/)).toBeInTheDocument()
    expect(screen.queryByTitle('Borrar movimiento')).not.toBeInTheDocument()
  })
})
