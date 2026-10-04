import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import type { BorradorComprobante } from '@/types'

const borrador: BorradorComprobante = {
  id: 7,
  organizacion_id: 1,
  origen: 'email',
  estado: 'listo',
  remitente: 'facturacion@proveedor.com',
  asunto: 'Factura',
  archivo_nombre: 'FA-0010-999.pdf',
  archivo_mime: 'application/pdf',
  archivo: null,
  datos: {
    tipo_codigo: 1, punto_venta: 10, numero: 999, fecha: '2026-09-15',
    cuit_emisor: '30690783521', razon_social: 'INTERBANKING SA', cae: null,
    alicuotas: { '21%': { neto: '20000.00', iva: '4200.00' } },
    neto_no_gravado: null, exento: null, percepciones_iva: '600.00',
    percepciones_iibb: '500.00', otros_tributos: null, total: '25300.00',
  },
  alertas: [],
  error: null,
  comprobante_iva_id: null,
  egreso_id: null,
  confirmado_at: null,
  created_at: '2026-10-04T12:00:00',
}

const api = vi.hoisted(() => ({
  getBorradoresComprobante: vi.fn(),
  getBuzonComprobantes: vi.fn(),
  getBorradorComprobante: vi.fn(),
  confirmarBorradorComprobante: vi.fn(),
}))

vi.mock('@/services/api', () => ({ apiClient: api }))
vi.mock('@/store/auth', () => ({ useAuthStore: () => ({ hasPermission: () => true }) }))
vi.mock('@/store/org', () => ({ useOrgStore: () => ({ activeOrgId: null }) }))

import { ComprobantesCompra } from '../ComprobantesCompra'

describe('ComprobantesCompra', () => {
  beforeEach(() => {
    api.getBorradoresComprobante.mockResolvedValue({ items: [borrador], conteo: { listo: 1 } })
    api.getBuzonComprobantes.mockResolvedValue({
      configurado: true, activo: true, direccion: 'facturas-abc123def456ghij@x.resend.app',
    })
    api.getBorradorComprobante.mockResolvedValue(borrador)
    api.confirmarBorradorComprobante.mockResolvedValue({
      ok: true, comprobante_iva_id: 1, periodo: '2026-09', egreso_id: null, contabilidad_ok: null, borrador,
    })
  })

  it('muestra la dirección de mail y la bandeja', async () => {
    render(<ComprobantesCompra />)
    expect(await screen.findByText('INTERBANKING SA')).toBeInTheDocument()
    expect(screen.getByText('facturas-abc123def456ghij@x.resend.app')).toBeInTheDocument()
    expect(screen.getByText('Para revisar')).toBeInTheDocument()
  })

  it('abre la revisión, muestra que cierra y confirma', async () => {
    render(<ComprobantesCompra />)
    fireEvent.click(await screen.findByText('INTERBANKING SA'))
    expect(await screen.findByText(/Cierra: la suma da/)).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Confirmar' }))
    await waitFor(() => expect(api.confirmarBorradorComprobante).toHaveBeenCalled())
    const [id, payload] = api.confirmarBorradorComprobante.mock.calls[0]
    expect(id).toBe(7)
    expect(payload.periodo).toBe('2026-09')
    expect(payload.registrar_pago).toBe(false)
    expect(payload.datos.total).toBe(25300)
    expect(payload.datos.alicuotas).toEqual([{ alicuota: '21%', neto: 20000, iva: 4200 }])
  })
})
