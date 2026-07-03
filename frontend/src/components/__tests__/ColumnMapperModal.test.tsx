import { render, screen, fireEvent } from '@testing-library/react'
import { describe, it, expect, vi } from 'vitest'
import { ColumnMapperModal } from '../ColumnMapperModal'
import { ResultadoMapeoPlanilla } from '@/types'

function buildResultado(overrides: Partial<ResultadoMapeoPlanilla> = {}): ResultadoMapeoPlanilla {
  return {
    origen: 'heuristica',
    confianza: 0.4,
    header_row: 1,
    columnas: { monto: 2, cuit: 1, titular: null, fecha: null, referencia: null },
    columnas_disponibles: [
      { idx: 1, header: 'CUIT', muestras: ['20111111112'] },
      { idx: 2, header: 'Importe', muestras: ['1500.50'] },
    ],
    preview: [
      { fila: 1, valores: ['20111111112', '1500.50'] },
      { fila: 2, valores: ['20222222223', '2300.00'] },
    ],
    filas_totales: 2,
    filas_descartadas: 0,
    fingerprint: 'abc123',
    ...overrides,
  }
}

describe('ColumnMapperModal', () => {
  it('muestra el badge de origen y la confianza', () => {
    render(<ColumnMapperModal resultado={buildResultado()} onConfirm={vi.fn()} onCancel={vi.fn()} />)
    expect(screen.getByText('Detección automática')).toBeInTheDocument()
    expect(screen.getByText('40%')).toBeInTheDocument()
  })

  it('habilita Confirmar cuando ya hay Monto + CUIT detectados', () => {
    render(<ColumnMapperModal resultado={buildResultado()} onConfirm={vi.fn()} onCancel={vi.fn()} />)
    const boton = screen.getByRole('button', { name: 'Confirmar mapeo' })
    expect(boton).not.toBeDisabled()
  })

  it('deshabilita Confirmar si no hay Monto mapeado', () => {
    const resultado = buildResultado({ columnas: { monto: null, cuit: 1, titular: null, fecha: null, referencia: null } })
    render(<ColumnMapperModal resultado={resultado} onConfirm={vi.fn()} onCancel={vi.fn()} />)
    const boton = screen.getByRole('button', { name: 'Confirmar mapeo' })
    expect(boton).toBeDisabled()
    expect(screen.getByText(/Mapeá al menos Monto/)).toBeInTheDocument()
  })

  it('llama a onConfirm con el mapeo y header_row al confirmar', () => {
    const onConfirm = vi.fn()
    render(<ColumnMapperModal resultado={buildResultado()} onConfirm={onConfirm} onCancel={vi.fn()} />)
    fireEvent.click(screen.getByRole('button', { name: 'Confirmar mapeo' }))
    expect(onConfirm).toHaveBeenCalledWith({ monto: 2, cuit: 1, titular: null, fecha: null, referencia: null, header_row: 1 })
  })

  it('llama a onCancel al hacer click en Cancelar', () => {
    const onCancel = vi.fn()
    render(<ColumnMapperModal resultado={buildResultado()} onConfirm={vi.fn()} onCancel={onCancel} />)
    fireEvent.click(screen.getByRole('button', { name: 'Cancelar' }))
    expect(onCancel).toHaveBeenCalled()
  })

  it('muestra aviso de filas descartadas cuando corresponde', () => {
    const resultado = buildResultado({ filas_descartadas: 3 })
    render(<ColumnMapperModal resultado={resultado} onConfirm={vi.fn()} onCancel={vi.fn()} />)
    expect(screen.getByText(/3 filas descartadas/)).toBeInTheDocument()
  })
})
