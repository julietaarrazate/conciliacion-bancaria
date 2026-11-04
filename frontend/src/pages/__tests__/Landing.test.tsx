import { describe, it, expect, vi, beforeAll } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'

// jsdom no trae matchMedia: el store de tema y el chequeo de reduced-motion lo usan.
let reduced = false
beforeAll(() => {
  vi.stubGlobal('matchMedia', (q: string) => ({
    matches: q.includes('reduce') ? reduced : false,
    media: q, onchange: null,
    addListener: () => {}, removeListener: () => {},
    addEventListener: () => {}, removeEventListener: () => {}, dispatchEvent: () => false,
  }))
})

const montar = async () => {
  const { Landing } = await import('@/pages/Landing')
  return render(<MemoryRouter><Landing /></MemoryRouter>)
}

// FNV-1a de 32 bits sobre UTF-8: alcanza para comparar huellas en un test.
function fnv1a(texto: string): string {
  let h = 0x811c9dc5
  for (const b of new TextEncoder().encode(texto)) {
    h ^= b
    h = Math.imul(h, 0x01000193) >>> 0
  }
  return h.toString(16).padStart(8, '0')
}

describe('Landing', () => {
  it('tiene un solo h1 y las secciones del recorrido', async () => {
    const { container } = await montar()
    expect(screen.getAllByRole('heading', { level: 1 })).toHaveLength(1)
    for (const id of ['top', 'como-funciona', 'funciones', 'para-quien', 'precio', 'preguntas', 'demo']) {
      expect(container.querySelector(`#${id}`)).not.toBeNull()
    }
    // Ni más ni menos: 7 secciones (el recorte de 15 a 7 es intencional).
    expect(container.querySelectorAll('main > section')).toHaveLength(7)
  })

  it('no usa jerga interna ni testimonios inventados', async () => {
    const { container } = await montar()
    const texto = container.textContent ?? ''
    for (const prohibido of ['Decimal', 'inmutable', '25.326', 'multi-tenant', 'partida doble', 'Lic. Beatriz']) {
      expect(texto).not.toContain(prohibido)
    }
  })

  it('no muestra nombres de clientes reales de la operadora', async () => {
    const { container } = await montar()
    // Solo texto visible (textContent), no clases CSS: "green" puede estar en un className.
    const texto = container.textContent ?? ''
    // Huellas (FNV-1a de 32 bits) de nombres de clientes reales de la organización de origen:
    // así el test los detecta sin que los nombres queden escritos en el código.
    const HUELLAS_REALES = new Set([
      '011decbc',
      '09354b67',
      '19cb622e',
      '29b5d95b',
      '34c306e1',
      '67a821ba',
      '7c26e092',
      '878751ef',
      '89ceeed8',
      'b645a05d',
      'ca5a3065',
      'd4a8f653',
      'd63aa7eb',
      'e2611ce0',
      'e80e4d92',
    ])
    const palabras = texto.toLowerCase().match(/\p{L}+/gu) ?? []
    for (const p of new Set(palabras)) {
      const h = fnv1a(p)
      expect(HUELLAS_REALES.has(h), `aparece un nombre de cliente real: "${p}"`).toBe(false)
    }
  })

  it('el formulario de demo abre WhatsApp con los datos cargados', async () => {
    const open = vi.spyOn(window, 'open').mockImplementation(() => null)
    await montar()
    fireEvent.change(screen.getByLabelText('Nombre'), { target: { value: 'Ana Gómez' } })
    fireEvent.change(screen.getByLabelText('Empresa o estudio'), { target: { value: 'Estudio Gómez' } })
    fireEvent.change(screen.getByLabelText('¿Cuántos clientes te pagan por banco?'), { target: { value: 'Más de 100 clientes' } })
    fireEvent.change(screen.getByLabelText('¿Cómo te contactamos?'), { target: { value: 'Mail' } })
    fireEvent.change(screen.getByLabelText('Tu mail'), { target: { value: 'ana@estudio.com.ar' } })
    fireEvent.click(screen.getByRole('button', { name: /Pedir demo por WhatsApp/ }))

    expect(open).toHaveBeenCalledTimes(1)
    const url = String(open.mock.calls[0][0])
    expect(url.startsWith('https://wa.me/543774504024?text=')).toBe(true)
    const msg = decodeURIComponent(url.split('text=')[1])
    expect(msg).toContain('Nombre: Ana Gómez')
    expect(msg).toContain('Empresa o estudio: Estudio Gómez')
    expect(msg).toContain('Volumen: Más de 100 clientes')
    expect(msg).toContain('Prefiero que me contacten por Mail: ana@estudio.com.ar')
    open.mockRestore()
  })

  it('no abre WhatsApp si faltan datos y avisa qué falta', async () => {
    const open = vi.spyOn(window, 'open').mockImplementation(() => null)
    await montar()
    fireEvent.click(screen.getByRole('button', { name: /Pedir demo por WhatsApp/ }))
    expect(open).not.toHaveBeenCalled()
    expect(screen.getByRole('alert')).toHaveTextContent('Completá tu nombre.')
    open.mockRestore()
  })

  it('con reduced-motion el demo del hero arranca en el cuadro final', async () => {
    reduced = true
    vi.resetModules()
    await montar()
    const demo = screen.getByTestId('hero-demo')
    expect(demo).toHaveAttribute('data-p-ok', 'true')
    expect(demo.textContent).toContain('El banco en libros coincide con el extracto')
    reduced = false
  })
})
