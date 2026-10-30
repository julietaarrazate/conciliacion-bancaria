import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { describe, it, expect, vi } from 'vitest'
import { ExtractoMapperModal, inferirSigno, mapeoCompleto } from '../extractos/ExtractoMapperModal'
import type { PreviewExtracto } from '@/types'

function buildPreview(overrides: Partial<PreviewExtracto> = {}): PreviewExtracto {
  return {
    hoja: 'Hoja1',
    hojas: ['Hoja1'],
    banco_clave: 'generico',
    banco: null,
    origen: 'heuristica',
    plantilla_id: null,
    mapeo: {
      hoja: 'Hoja1',
      fila_encabezado: 0,
      columnas: { fecha: 0, titular: 1, monto: 2, saldo: 3 },
      signo: 'columna_unica',
      formato_fecha: 'auto',
      decimal: 'auto',
    },
    firma: 'abc',
    confianza: 0.45,
    necesita_mapeo: true,
    motivos: ['No cuadra en la fila 3: el saldo no sigue al de la fila anterior.'],
    aviso_saldos: null,
    grilla: {
      desde: 0,
      columnas: 4,
      filas: [
        ['Fecha', 'Concepto', 'Importe', 'Saldo'],
        ['01/05/2026', 'Cobro', '1.000,00', '2.000,00'],
        ['02/05/2026', 'Pago', '-500,00', '1.400,00'],
      ],
    },
    encabezados: ['Fecha', 'Concepto', 'Importe', 'Saldo'],
    total_movimientos: 2,
    filas_descartadas: 0,
    filas_resumen: 0,
    muestra: [
      { fila: 2, fecha: '2026-05-01', titular: 'Cobro', monto: '1000.00', saldo: '2000.00', orden: null },
      { fila: 3, fecha: '2026-05-02', titular: 'Pago', monto: '-500.00', saldo: '1400.00', orden: null },
    ],
    cuadre: { tiene_saldo: true, cuadra: false, orden: 'asc', mensaje: 'No cuadra', primera_fila_con_error: 3 },
    ...overrides,
  }
}

describe('ExtractoMapperModal', () => {
  it('muestra origen, confianza, motivo y el aviso de saldos que no cuadran', () => {
    render(<ExtractoMapperModal preview={buildPreview()} onRevisar={vi.fn()} onConfirm={vi.fn()} onCancel={vi.fn()} />)
    expect(screen.getByText('Detección automática')).toBeInTheDocument()
    expect(screen.getByText('45%')).toBeInTheDocument()
    expect(screen.getByText(/No cuadra en la fila 3$/)).toBeInTheDocument()
    expect(screen.getAllByText('Cobro')).toHaveLength(2) // en la grilla y en la muestra
  })

  it('muestra "Los saldos cuadran" cuando cuadra', () => {
    const preview = buildPreview({ cuadre: { tiene_saldo: true, cuadra: true, orden: 'desc', mensaje: '' } })
    render(<ExtractoMapperModal preview={preview} onRevisar={vi.fn()} onConfirm={vi.fn()} onCancel={vi.fn()} />)
    expect(screen.getByText('✓ Los saldos cuadran')).toBeInTheDocument()
    expect(screen.getByText(/del más nuevo al más viejo/)).toBeInTheDocument()
  })

  it('confirma con el mapeo detectado', () => {
    const onConfirm = vi.fn()
    render(<ExtractoMapperModal preview={buildPreview()} onRevisar={vi.fn()} onConfirm={onConfirm} onCancel={vi.fn()} />)
    fireEvent.click(screen.getByRole('button', { name: 'Importar extracto' }))
    expect(onConfirm).toHaveBeenCalledWith(expect.objectContaining({
      fila_encabezado: 0,
      columnas: { fecha: 0, titular: 1, monto: 2, saldo: 3 },
      signo: 'columna_unica',
    }))
  })

  it('sin importe no deja importar', () => {
    const preview = buildPreview({ origen: 'ninguno', mapeo: null })
    render(<ExtractoMapperModal preview={preview} onRevisar={vi.fn()} onConfirm={vi.fn()} onCancel={vi.fn()} />)
    expect(screen.getByRole('button', { name: 'Importar extracto' })).toBeDisabled()
    expect(screen.getByText(/Indicá al menos la columna del importe/)).toBeInTheDocument()
  })

  it('al cambiar una columna vuelve a leer y actualiza el control de saldos', async () => {
    const onRevisar = vi.fn().mockResolvedValue(buildPreview({
      origen: 'manual',
      confianza: 1,
      motivos: [],
      cuadre: { tiene_saldo: true, cuadra: true, orden: 'asc', mensaje: '' },
    }))
    render(<ExtractoMapperModal preview={buildPreview()} onRevisar={onRevisar} onConfirm={vi.fn()} onCancel={vi.fn()} />)
    fireEvent.change(screen.getByLabelText('Uso de la columna Concepto'), { target: { value: '__ignorar__' } })
    await waitFor(() => expect(onRevisar).toHaveBeenCalledTimes(1))
    expect(onRevisar.mock.calls[0][0].columnas).toEqual({ fecha: 0, monto: 2, saldo: 3 })
    await waitFor(() => expect(screen.getByText('✓ Los saldos cuadran')).toBeInTheDocument())
  })

  it('elegir Débito y Crédito cambia a dos columnas', () => {
    const onConfirm = vi.fn()
    render(<ExtractoMapperModal preview={buildPreview()} onRevisar={vi.fn().mockResolvedValue(buildPreview())} onConfirm={onConfirm} onCancel={vi.fn()} />)
    fireEvent.change(screen.getByLabelText('Uso de la columna Importe'), { target: { value: 'debito' } })
    fireEvent.change(screen.getByLabelText('Uso de la columna Concepto'), { target: { value: 'credito' } })
    fireEvent.click(screen.getByRole('button', { name: 'Importar extracto' }))
    expect(onConfirm.mock.calls[0][0].signo).toBe('debito_credito')
  })

  it('Cancelar llama a onCancel', () => {
    const onCancel = vi.fn()
    render(<ExtractoMapperModal preview={buildPreview()} onRevisar={vi.fn()} onConfirm={vi.fn()} onCancel={onCancel} />)
    fireEvent.click(screen.getByRole('button', { name: 'Cancelar' }))
    expect(onCancel).toHaveBeenCalled()
  })
})

describe('reglas del mapeo', () => {
  it('inferirSigno', () => {
    expect(inferirSigno({ monto: 1 })).toBe('columna_unica')
    expect(inferirSigno({ debito: 1, credito: 2 })).toBe('debito_credito')
    expect(inferirSigno({ monto: 1, indicador: 2 })).toBe('indicador')
    expect(inferirSigno({ credito: 2 })).toBe('debito_credito')
  })

  it('mapeoCompleto', () => {
    const base = { fila_encabezado: 0, formato_fecha: 'auto' as const, decimal: 'auto' as const }
    expect(mapeoCompleto({ ...base, signo: 'columna_unica', columnas: {} })).toBe(false)
    expect(mapeoCompleto({ ...base, signo: 'columna_unica', columnas: { monto: 0 } })).toBe(true)
    expect(mapeoCompleto({ ...base, signo: 'indicador', columnas: { monto: 0 } })).toBe(false)
    expect(mapeoCompleto({ ...base, signo: 'debito_credito', columnas: { debito: 0 } })).toBe(true)
  })
})
