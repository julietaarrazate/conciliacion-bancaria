import { render, screen } from '@testing-library/react'
import { describe, it, expect } from 'vitest'
import { DiagnosticoPanel } from '../DiagnosticoPanel'
import { DiagnosticoConciliacion } from '@/types'

const base: DiagnosticoConciliacion = {
  banco_trae_identidad: true,
  cobertura_montos: { en_extracto: 10, total: 10 },
  periodo_planilla: { desde: '2026-06-03', hasta: '2026-06-24' },
  periodo_extracto: { desde: '2026-06-01', hasta: '2026-06-30' },
  solapan_fechas: true,
}

describe('DiagnosticoPanel', () => {
  it('no renderiza nada cuando el diagnóstico es null', () => {
    const { container } = render(<DiagnosticoPanel diagnostico={null} />)
    expect(container).toBeEmptyDOMElement()
  })

  it('no renderiza nada cuando todo está OK (identidad, cobertura total, fechas solapan)', () => {
    const { container } = render(<DiagnosticoPanel diagnostico={base} />)
    expect(container).toBeEmptyDOMElement()
  })

  it('muestra el aviso de banco sin identidad y la cobertura parcial', () => {
    const diagnostico: DiagnosticoConciliacion = {
      ...base,
      banco_trae_identidad: false,
      cobertura_montos: { en_extracto: 7, total: 10 },
    }
    render(<DiagnosticoPanel diagnostico={diagnostico} />)
    expect(screen.getByText(/no incluye el nombre ni el CUIT/)).toBeInTheDocument()
    expect(screen.getByText(/7 de 10 montos de la planilla aparecen en el extracto/)).toBeInTheDocument()
    expect(screen.getByText(/Los otros 3 no aparecen en este extracto/)).toBeInTheDocument()
  })

  it('muestra el aviso de fechas que no solapan con el rango formateado', () => {
    const diagnostico: DiagnosticoConciliacion = { ...base, solapan_fechas: false }
    render(<DiagnosticoPanel diagnostico={diagnostico} />)
    expect(screen.getByText(/no coinciden/)).toBeInTheDocument()
  })
})
