import { render, screen, fireEvent, waitFor, within } from '@testing-library/react'
import { describe, it, expect, vi, beforeEach } from 'vitest'

const api = vi.hoisted(() => ({
  calcularMasivo: vi.fn(),
  compararMisComprobantesVarios: vi.fn(),
  importarMisComprobantesVarios: vi.fn(),
  deshacerImportacionIva: vi.fn(),
}))
const auth = vi.hoisted(() => ({ permisos: true, variasOrgs: true }))
vi.mock('@/services/api', () => ({ apiClient: api }))
vi.mock('@/store/auth', () => ({
  useAuthStore: () => ({
    hasPermission: () => auth.permisos,
    user: { is_superadmin: false, allowed_org_ids: auth.variasOrgs ? [2] : [] },
  }),
}))
vi.mock('@/store/confirm', () => ({ confirmDialog: () => Promise.resolve(true) }))

import { ProcesosMasivos } from '../ProcesosMasivos'

const fila = (archivo: string, extra: object) => ({
  archivo, cuit: '30700000008', organizacion_id: 1, nombre: 'Estudio', error: null,
  faltantes: 2, iva_faltante: 4200, ya_cargados: 5, importes_distintos: 1, solo_en_cuadra: 0,
  fuera_de_periodo: 0, ...extra,
})

describe('ProcesosMasivos', () => {
  beforeEach(() => {
    auth.permisos = true
    auth.variasOrgs = true
    Object.values(api).forEach(f => f.mockReset())
    api.calcularMasivo.mockResolvedValue({
      accion: 'iva_liquidacion', periodo: '2026-09', resultados: [
        { organizacion_id: 1, nombre: 'Estudio', resultado: 'calculado', detalle: null, resumen: { saldo_a_pagar: 1500 } },
        { organizacion_id: 2, nombre: 'Cliente Dos', resultado: 'ya_presentado', detalle: 'Ya estaba presentado: no se recalculó', resumen: {} },
        { organizacion_id: 3, nombre: 'Cliente Tres', resultado: 'omitido', detalle: 'No usa el módulo de IVA', resumen: null },
        { organizacion_id: 4, nombre: 'Cliente Cuatro', resultado: 'error', detalle: 'Sin cuentas configuradas', resumen: null },
      ],
    })
    api.compararMisComprobantesVarios.mockResolvedValue({
      direccion: 'recibido', periodo: '2026-09', archivos: [
        fila('org1.xlsx', {}),
        fila('ajena.xlsx', { organizacion_id: null, nombre: null, faltantes: 0, iva_faltante: 0, error: 'No hay una organización con el CUIT 30555555551.' }),
      ],
    })
    api.importarMisComprobantesVarios.mockResolvedValue({
      direccion: 'recibido', periodo: '2026-09', archivos: [
        { archivo: 'org1.xlsx', cuit: '30700000008', organizacion_id: 1, nombre: 'Estudio', error: null, importados: 2, duplicados: 0, lote: 'abc' },
        { archivo: 'ajena.xlsx', cuit: '30555555551', organizacion_id: null, nombre: null, error: 'No hay…', importados: 0, duplicados: 0, lote: null },
      ],
    })
    api.deshacerImportacionIva.mockResolvedValue({ ok: true, borrados: 2 })
  })

  it('calcula para todas y muestra el resultado de cada organización', async () => {
    render(<ProcesosMasivos />)
    fireEvent.change(screen.getByLabelText('Acción'), { target: { value: 'iva_liquidacion' } })
    fireEvent.change(screen.getByLabelText('Período'), { target: { value: '2026-09' } })
    fireEvent.click(screen.getByRole('button', { name: /calcular para todas/i }))
    await waitFor(() => expect(api.calcularMasivo).toHaveBeenCalledWith('iva_liquidacion', '2026-09'))
    expect(await screen.findByText('Estudio')).toBeInTheDocument()
    expect(screen.getByText('Calculado')).toBeInTheDocument()
    expect(screen.getByText('Ya presentado')).toBeInTheDocument()
    expect(screen.getByText('No usa el módulo de IVA')).toBeInTheDocument()
    expect(screen.getByText('Sin cuentas configuradas')).toBeInTheDocument()
    expect(screen.getByText(/1 calculada/i)).toBeInTheDocument()
  })

  it('el control de Monotributo pide período semestral', async () => {
    render(<ProcesosMasivos />)
    fireEvent.change(screen.getByLabelText('Acción'), { target: { value: 'monotributo_control' } })
    fireEvent.change(screen.getByLabelText('Período'), { target: { value: '2026-S2' } })
    fireEvent.click(screen.getByRole('button', { name: /calcular para todas/i }))
    await waitFor(() => expect(api.calcularMasivo).toHaveBeenCalledWith('monotributo_control', '2026-S2'))
  })

  it('compara Mis Comprobantes de varias organizaciones, importa y deshace', async () => {
    render(<ProcesosMasivos />)
    const archivos = [new File(['a'], 'org1.xlsx'), new File(['b'], 'ajena.xlsx')]
    fireEvent.change(screen.getByLabelText(/Excels de Mis Comprobantes/i), { target: { files: archivos } })
    await waitFor(() => expect(api.compararMisComprobantesVarios).toHaveBeenCalled())
    const org1 = (await screen.findByText('org1.xlsx')).closest('tr')!
    expect(within(org1).getByText('Estudio')).toBeInTheDocument()
    expect(within(org1).getByText('2')).toBeInTheDocument()
    expect(screen.getByText(/No hay una organización con el CUIT/)).toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: /importar faltantes de 1 organización/i }))
    await waitFor(() => expect(api.importarMisComprobantesVarios).toHaveBeenCalled())
    const fila1 = (await screen.findByText(/2 importados/)).closest('tr')!
    fireEvent.click(within(fila1).getByRole('button', { name: /deshacer/i }))
    await waitFor(() => expect(api.deshacerImportacionIva).toHaveBeenCalledWith('abc', 1))
  })

  it('con una sola organización explica que no aplica', () => {
    auth.variasOrgs = false
    render(<ProcesosMasivos />)
    expect(screen.queryByRole('button', { name: /calcular para todas/i })).not.toBeInTheDocument()
    expect(screen.getByText(/más de una organización/i)).toBeInTheDocument()
  })

  it('no habla de clientes: son organizaciones', () => {
    render(<ProcesosMasivos />)
    expect(screen.queryByText(/clientes/i)).not.toBeInTheDocument()
    expect(screen.getByText(/Mis Comprobantes de varias organizaciones/i)).toBeInTheDocument()
  })

  it('sin permiso no muestra las acciones', () => {
    auth.permisos = false
    render(<ProcesosMasivos />)
    expect(screen.queryByRole('button', { name: /calcular para todas/i })).not.toBeInTheDocument()
    expect(screen.getByText(/no tenés permiso/i)).toBeInTheDocument()
  })
})
