import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { CuitOrganizacionCard } from '../CuitOrganizacionCard'

const getCuitOrganizacion = vi.fn()
const setCuitOrganizacion = vi.fn()

vi.mock('@/services/api', () => ({
  apiClient: {
    getCuitOrganizacion: (...a: unknown[]) => getCuitOrganizacion(...a),
    setCuitOrganizacion: (...a: unknown[]) => setCuitOrganizacion(...a),
  },
}))

describe('CuitOrganizacionCard', () => {
  beforeEach(() => {
    getCuitOrganizacion.mockReset().mockResolvedValue({ cuit: null })
    setCuitOrganizacion.mockReset().mockResolvedValue({ cuit: '30700000008' })
  })

  it('sin CUIT avisa que el control no corre y deja cargarlo', async () => {
    render(<CuitOrganizacionCard orgId={4} puedeEditar />)
    expect(await screen.findByText(/no se controla/i)).toBeInTheDocument()
    fireEvent.change(screen.getByLabelText(/CUIT de la organización/i), { target: { value: '30-70000000-8' } })
    fireEvent.click(screen.getByRole('button', { name: /guardar/i }))
    await waitFor(() => expect(setCuitOrganizacion).toHaveBeenCalledWith('30-70000000-8', 4))
    expect(await screen.findByText('30-70000000-8')).toBeInTheDocument()
  })

  it('con CUIT lo muestra formateado', async () => {
    getCuitOrganizacion.mockResolvedValue({ cuit: '30700000008' })
    render(<CuitOrganizacionCard puedeEditar={false} />)
    expect(await screen.findByText('30-70000000-8')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /guardar/i })).not.toBeInTheDocument()
  })

  it('sin permiso y sin CUIT pide a un administrador', async () => {
    render(<CuitOrganizacionCard puedeEditar={false} />)
    expect(await screen.findByText(/administrador/i)).toBeInTheDocument()
    expect(screen.queryByLabelText(/CUIT de la organización/i)).not.toBeInTheDocument()
  })

  it('muestra el error del servidor', async () => {
    setCuitOrganizacion.mockRejectedValue({ response: { data: { detail: 'El CUIT no es válido (revisá los dígitos).' } } })
    render(<CuitOrganizacionCard puedeEditar />)
    await screen.findByText(/no se controla/i)
    fireEvent.change(screen.getByLabelText(/CUIT de la organización/i), { target: { value: '30700000009' } })
    fireEvent.click(screen.getByRole('button', { name: /guardar/i }))
    expect(await screen.findByText(/no es válido/)).toBeInTheDocument()
  })
})
