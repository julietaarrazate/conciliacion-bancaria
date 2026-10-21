import { render, screen, fireEvent, waitFor, within } from '@testing-library/react'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import type { Proveedor } from '@/types'

const api = vi.hoisted(() => ({
  listarProveedores: vi.fn(),
  crearProveedor: vi.fn(),
  actualizarProveedor: vi.fn(),
  bajaProveedor: vi.fn(),
  sincronizarProveedores: vi.fn(),
}))
const auth = vi.hoisted(() => ({ permisos: true }))

vi.mock('@/services/api', () => ({ apiClient: api }))
vi.mock('@/store/auth', () => ({ useAuthStore: () => ({ hasPermission: () => auth.permisos }) }))
vi.mock('@/store/org', () => ({ useOrgStore: () => ({ activeOrgId: null }) }))

import { Proveedores } from '../Proveedores'

const papelera: Proveedor = {
  id: 9, organizacion_id: 1, cuit: '30712345671', razon_social: 'Papelera SA',
  condicion_iva: 'responsable_inscripto', email: null, cbu: null, notas: null,
  origen: 'comprobantes', activo: true, total_facturado: 900, total_pagado: 600, saldo: 300,
}

describe('Proveedores', () => {
  beforeEach(() => {
    auth.permisos = true
    Object.values(api).forEach(f => f.mockReset())
    api.listarProveedores.mockResolvedValue([papelera])
    api.crearProveedor.mockResolvedValue({ ...papelera, id: 10 })
    api.actualizarProveedor.mockResolvedValue(papelera)
    api.bajaProveedor.mockResolvedValue({ ok: true })
    api.sincronizarProveedores.mockResolvedValue({ creados: 2 })
  })

  it('lista los proveedores con lo facturado, pagado y saldo', async () => {
    render(<Proveedores />)
    const fila = (await screen.findByText('Papelera SA')).closest('tr')!
    expect(within(fila).getByText('30-71234567-1')).toBeInTheDocument()
    expect(within(fila).getByText('Responsable inscripto')).toBeInTheDocument()
    expect(within(fila).getByText(/300,00/)).toBeInTheDocument()
  })

  it('aclara que los proveedores de los clientes no van acá', async () => {
    render(<Proveedores />)
    expect(await screen.findByText(/por cuenta de un cliente/i)).toBeInTheDocument()
  })

  it('trae los proveedores de las facturas recibidas', async () => {
    render(<Proveedores />)
    await screen.findByText('Papelera SA')
    fireEvent.click(screen.getByRole('button', { name: /traer de las facturas/i }))
    expect(await screen.findByText(/2 proveedores nuevos/i)).toBeInTheDocument()
    expect(api.listarProveedores).toHaveBeenCalledTimes(2)
  })

  it('da de alta un proveedor', async () => {
    render(<Proveedores />)
    await screen.findByText('Papelera SA')
    fireEvent.click(screen.getByRole('button', { name: /nuevo proveedor/i }))
    fireEvent.change(screen.getByLabelText('Razón social'), { target: { value: 'Fletes Juan' } })
    fireEvent.change(screen.getByLabelText('CUIT'), { target: { value: '20-11111111-2' } })
    fireEvent.change(screen.getByLabelText('Condición frente al IVA'), { target: { value: 'monotributo' } })
    fireEvent.click(screen.getByRole('button', { name: /guardar/i }))
    await waitFor(() => expect(api.crearProveedor).toHaveBeenCalledWith(
      expect.objectContaining({ razon_social: 'Fletes Juan', cuit: '20-11111111-2', condicion_iva: 'monotributo' }),
      undefined,
    ))
  })

  it('muestra el error del servidor al guardar', async () => {
    api.crearProveedor.mockRejectedValue({ response: { data: { detail: 'Ya hay un proveedor con ese CUIT.' } } })
    render(<Proveedores />)
    await screen.findByText('Papelera SA')
    fireEvent.click(screen.getByRole('button', { name: /nuevo proveedor/i }))
    fireEvent.change(screen.getByLabelText('Razón social'), { target: { value: 'X' } })
    fireEvent.click(screen.getByRole('button', { name: /guardar/i }))
    expect(await screen.findByText(/Ya hay un proveedor con ese CUIT/)).toBeInTheDocument()
  })

  it('sin permiso para editar solo consulta', async () => {
    auth.permisos = false
    render(<Proveedores />)
    await screen.findByText('Papelera SA')
    expect(screen.queryByRole('button', { name: /nuevo proveedor/i })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /traer de las facturas/i })).not.toBeInTheDocument()
  })
})
