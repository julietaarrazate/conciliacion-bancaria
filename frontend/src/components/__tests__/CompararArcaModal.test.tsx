import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { CompararArcaModal } from '../CompararArcaModal'
import { CompararComprobantesIvaResult } from '@/types'

const compararComprobantesIva = vi.fn()
const importarComprobantesIva = vi.fn()

vi.mock('@/services/api', () => ({
  apiClient: {
    compararComprobantesIva: (...a: unknown[]) => compararComprobantesIva(...a),
    importarComprobantesIva: (...a: unknown[]) => importarComprobantesIva(...a),
  },
}))

const fila = (numero: number, extra: object = {}) => ({
  clave: `1-20-${numero}-30666666661`, fecha: '2026-05-07', tipo_codigo: 1, tipo_desc: '1 - Factura A',
  punto_venta: 20, numero, cuit_contraparte: '30666666661', denominacion: `PROV ${numero}`,
  neto_gravado_total: 3000, total_iva: 630, imp_total: 3630, es_nota_credito: false, ...extra,
})

const resultado: CompararComprobantesIvaResult = {
  periodo: '2026-05', direccion: 'recibido',
  faltantes: [fila(7), fila(8, { total_iva: 210, imp_total: 1210 })],
  iva_faltante: 840,
  ya_cargados: [fila(100, { comprobante_id: 1, importe_distinto: true, total_iva_cuadra: 600, imp_total_cuadra: 3600 })],
  solo_en_cuadra: [{
    id: 9, direccion: 'recibido', fecha: '2026-05-09', tipo_codigo: '1', tipo_desc: '1 - Factura A',
    punto_venta: 99, numero: '1', cuit_contraparte: '30555555551', denominacion: 'PROV FANTASMA',
    neto_gravado_total: 500, total_iva: 105, imp_total: 605,
  } as any],
  fuera_de_periodo: 2,
}

const archivo = new File(['x'], 'mc.xlsx')

describe('CompararArcaModal', () => {
  beforeEach(() => {
    compararComprobantesIva.mockReset().mockResolvedValue(resultado)
    importarComprobantesIva.mockReset().mockResolvedValue({ importados: 2, duplicados: 0, fuera_de_periodo: 2, no_elegidos: 0, periodo: '2026-05', lote: 'abc' })
  })

  it('muestra lo que falta, lo que difiere y lo que ARCA no tiene', async () => {
    render(<CompararArcaModal file={archivo} direccion="recibido" periodo="2026-05" orgId={3}
      onClose={() => {}} onImportado={() => {}} />)
    expect(await screen.findByText(/2 faltan en Cuadra/i)).toBeInTheDocument()
    expect(compararComprobantesIva).toHaveBeenCalledWith(archivo, 'recibido', '2026-05', 3)
    expect(screen.getByText('PROV 7')).toBeInTheDocument()
    expect(screen.getByText(/IVA ARCA .* Cuadra/)).toBeInTheDocument()
    expect(screen.getByText('PROV FANTASMA')).toBeInTheDocument()
    expect(screen.getByText(/2 de otro período/i)).toBeInTheDocument()
  })

  it('importa solo las faltantes tildadas', async () => {
    const onImportado = vi.fn()
    render(<CompararArcaModal file={archivo} direccion="recibido" periodo="2026-05"
      onClose={() => {}} onImportado={onImportado} />)
    await screen.findByText('PROV 8')
    fireEvent.click(screen.getByLabelText(/PROV 8/))
    fireEvent.click(screen.getByRole('button', { name: /importar 1/i }))
    await waitFor(() => expect(onImportado).toHaveBeenCalled())
    expect(importarComprobantesIva).toHaveBeenCalledWith(
      archivo, 'recibido', '2026-05', undefined, ['1-20-7-30666666661'])
  })

  it('sin faltantes no ofrece importar', async () => {
    compararComprobantesIva.mockResolvedValue({ ...resultado, faltantes: [], iva_faltante: 0 })
    render(<CompararArcaModal file={archivo} direccion="recibido" periodo="2026-05"
      onClose={() => {}} onImportado={() => {}} />)
    expect(await screen.findByText(/no falta nada/i)).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /importar/i })).not.toBeInTheDocument()
  })

  it('muestra el error si el archivo no es de ARCA', async () => {
    compararComprobantesIva.mockRejectedValue({ response: { data: { detail: 'El archivo no parece ser un export' } } })
    render(<CompararArcaModal file={archivo} direccion="recibido" periodo="2026-05"
      onClose={() => {}} onImportado={() => {}} />)
    expect(await screen.findByText(/no parece ser un export/)).toBeInTheDocument()
  })
})
