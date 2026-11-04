import { render, screen } from '@testing-library/react'
import { describe, it, expect } from 'vitest'
import { LineChart } from '../charts/LineChart'
import { BarChart } from '../charts/BarChart'
import { CHART_EMPTY_MSG } from '../charts/ChartEmpty'

describe('estado vacío de los gráficos', () => {
  it('LineChart con todos los valores en 0 muestra el estado vacío en vez de una línea plana', () => {
    const { container } = render(<LineChart data={[{ label: 'sep', value: 0 }, { label: 'oct', value: 0 }]} />)
    expect(screen.getByText(CHART_EMPTY_MSG)).toBeInTheDocument()
    expect(container.querySelector('circle')).not.toBeInTheDocument()
  })

  it('LineChart sin puntos usa el mensaje que se le pase', () => {
    render(<LineChart data={[]} emptyMessage="Nada todavía" />)
    expect(screen.getByText('Nada todavía')).toBeInTheDocument()
  })

  it('LineChart con datos dibuja la línea', () => {
    const { container } = render(<LineChart data={[{ label: 'sep', value: 0 }, { label: 'oct', value: 5 }]} />)
    expect(screen.queryByText(CHART_EMPTY_MSG)).not.toBeInTheDocument()
    expect(container.querySelectorAll('circle').length).toBe(2)
  })

  it('BarChart con ingresos y egresos en 0 muestra el estado vacío', () => {
    render(<BarChart labels={['sep', 'oct']} series={[{ label: 'Ingresos', color: '#10b981', data: [0, 0] }, { label: 'Egresos', color: '#f43f5e', data: [0, 0] }]} />)
    expect(screen.getByText(CHART_EMPTY_MSG)).toBeInTheDocument()
  })

  it('BarChart con algún valor dibuja las barras', () => {
    const { container } = render(<BarChart labels={['sep']} series={[{ label: 'Ingresos', color: '#10b981', data: [3] }]} />)
    expect(screen.queryByText(CHART_EMPTY_MSG)).not.toBeInTheDocument()
    expect(container.querySelectorAll('rect').length).toBe(1)
  })
})
