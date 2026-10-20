import { render, screen, fireEvent } from '@testing-library/react'
import { describe, it, expect } from 'vitest'
import { ResumenExtracto } from '../ResumenExtracto'
import { ResumenExtracto as ResumenExtractoData } from '@/types'

const base: ResumenExtractoData = {
  gastos_bancarios: {
    conceptos: [
      { concepto: 'Impuesto Ley 25.413 (débitos y créditos)', cantidad: 2, total: '12884.16' },
      { concepto: 'Comisiones y mantenimiento', cantidad: 1, total: 32800 },
    ],
    cantidad: 3,
    total: '45684.16',
  },
  explicado: { creditos: 4, acreditados: 3, sin_acreditar: 1, porcentaje: 75 },
}

describe('ResumenExtracto', () => {
  it('no renderiza nada sin datos', () => {
    const { container } = render(<ResumenExtracto resumen={null} />)
    expect(container).toBeEmptyDOMElement()
  })

  it('no renderiza nada si el extracto no tiene ingresos ni gastos', () => {
    const vacio: ResumenExtractoData = {
      gastos_bancarios: { conceptos: [], cantidad: 0, total: 0 },
      explicado: { creditos: 0, acreditados: 0, sin_acreditar: 0, porcentaje: null },
    }
    const { container } = render(<ResumenExtracto resumen={vacio} />)
    expect(container).toBeEmptyDOMElement()
  })

  it('muestra el % y el total de gastos, y el detalle al desplegar', () => {
    render(<ResumenExtracto resumen={base} />)
    expect(screen.getByText('75%')).toBeInTheDocument()
    expect(screen.getByText(/3 de 4/)).toBeInTheDocument()
    expect(screen.queryByText(/Impuesto Ley 25.413/)).not.toBeInTheDocument()

    fireEvent.click(screen.getByRole('button'))
    expect(screen.getByText(/Impuesto Ley 25.413/)).toBeInTheDocument()
    expect(screen.getByText('Total según extracto')).toBeInTheDocument()
    expect(screen.getByText(/Queda 1 ingreso sin acreditar/)).toBeInTheDocument()
  })

  it('muestra el % de débitos explicados y lo que falta justificar', () => {
    const conDebitos: ResumenExtractoData = {
      ...base,
      debitos: { debitos: 4, explicados: 3, sin_explicar: 1, total_sin_explicar: '300.50', porcentaje: 75 },
    }
    render(<ResumenExtracto resumen={conDebitos} />)
    expect(screen.getByText(/de los egresos explicados/)).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button'))
    expect(screen.getByText(/Queda 1 egreso sin explicar/)).toBeInTheDocument()
    expect(screen.getByText(/300,50/)).toBeInTheDocument()
  })

  it('sin bloque de débitos (backend viejo) no rompe', () => {
    render(<ResumenExtracto resumen={base} />)
    expect(screen.queryByText(/egresos explicados/)).not.toBeInTheDocument()
  })
})
