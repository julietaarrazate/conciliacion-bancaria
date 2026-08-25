import { render, screen } from '@testing-library/react'
import { describe, it, expect } from 'vitest'
import { DonutChart, type DonutSlice } from '../charts/DonutChart'

const data: DonutSlice[] = [
  { label: 'Conciliado', value: 75, color: '#4ADE80' },
  { label: 'Pendiente', value: 25, color: '#F59E0B' },
]

describe('DonutChart', () => {
  it('muestra "Sin datos" cuando el total es 0', () => {
    render(<DonutChart data={[{ label: 'x', value: 0, color: '#000' }]} />)
    expect(screen.getByText('Sin datos')).toBeInTheDocument()
  })

  it('dibuja un arco por cada slice más el track de fondo', () => {
    const { container } = render(<DonutChart data={data} showLegend={false} />)
    // 1 círculo de fondo + 1 por slice
    expect(container.querySelectorAll('circle')).toHaveLength(1 + data.length)
  })

  it('muestra la leyenda con labels y porcentajes', () => {
    render(<DonutChart data={data} />)
    expect(screen.getByText('Conciliado')).toBeInTheDocument()
    expect(screen.getByText('Pendiente')).toBeInTheDocument()
    expect(screen.getByText('75%')).toBeInTheDocument()
    expect(screen.getByText('25%')).toBeInTheDocument()
  })

  it('renderiza el label central cuando se pasa', () => {
    render(<DonutChart data={data} centerLabel="100" centerSubLabel="total" />)
    expect(screen.getByText('100')).toBeInTheDocument()
    expect(screen.getByText('total')).toBeInTheDocument()
  })
})
