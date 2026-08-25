import { render } from '@testing-library/react'
import { describe, it, expect } from 'vitest'
import { Skeleton, SkeletonText } from '../Skeleton'

describe('Skeleton', () => {
  it('renderiza el placeholder con la clase de animación', () => {
    const { container } = render(<Skeleton />)
    const el = container.querySelector('.skeleton')
    expect(el).toBeInTheDocument()
  })

  it('propaga className extra', () => {
    const { container } = render(<Skeleton className="h-8 w-8" />)
    const el = container.querySelector('.skeleton')
    expect(el).toHaveClass('h-8', 'w-8')
  })

  it('SkeletonText renderiza una línea por cada line', () => {
    const { container } = render(<SkeletonText lines={3} />)
    expect(container.querySelectorAll('.skeleton')).toHaveLength(3)
  })
})
