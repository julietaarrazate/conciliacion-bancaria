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

vi.mock('@/services/api', () => ({ apiClient: api }))
vi.mock('@/store/auth', () => ({
  useAuthStore: (sel: (s: { hasPermission: () => boolean }) => unknown) => sel({ hasPermission: () => true }),
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
})
