import { render } from '@testing-library/react'
import { describe, it, expect } from 'vitest'
import { CuadraLogo } from '../CuadraLogo'

describe('CuadraLogo', () => {
  it('renderiza un svg con el tamaño pedido', () => {
    const { container } = render(<CuadraLogo size={48} animate={false} />)
    const svg = container.querySelector('svg')
    expect(svg).toBeInTheDocument()
    expect(svg).toHaveAttribute('width', '48')
    expect(svg).toHaveAttribute('height', '48')
  })

  it('usa el acento de la app (#818CF8) en el arco de relleno, no el verde', () => {
    const { container } = render(<CuadraLogo animate={false} />)
    const strokes = Array.from(container.querySelectorAll('path[stroke]')).map((p) =>
      p.getAttribute('stroke'),
    )
    expect(strokes).toContain('#818CF8')
    expect(strokes).not.toContain('#4ADE80')
  })

  it('respeta un fillColor custom', () => {
    const { container } = render(<CuadraLogo animate={false} fillColor="#123456" />)
    const strokes = Array.from(container.querySelectorAll('path[stroke]')).map((p) =>
      p.getAttribute('stroke'),
    )
    expect(strokes).toContain('#123456')
  })
})
