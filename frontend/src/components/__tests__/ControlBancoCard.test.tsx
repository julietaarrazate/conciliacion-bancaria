import { render, screen } from '@testing-library/react'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { ControlBancoCard } from '../contabilidad/ControlBancoCard'

const getControlBanco = vi.fn()

vi.mock('@/services/api', () => ({
  apiClient: { getControlBanco: (...a: unknown[]) => getControlBanco(...a) },
}))

const base = {
  org_id: 1,
  saldo_libro_banco: '1000.00',
  suma_movimientos_extractos: '1000.00',
  diferencia_libro_vs_movimientos: '0.00',
  saldo_ultimo_extracto: '1000.00',
  saldo_inicial_primer_extracto: '0.00',
  diferencia_libro_vs_extracto: '0.00',
  movimientos_extracto_sin_asiento: 0,
  saldos: {
    banco: { codigo: '1-1-1-3-1', saldo: '1000.00' },
    banco_cuenta_madre: { codigo: '1-1-1-3', saldo: '1000.00' },
    pasivo_corriente: { codigo: '2-1-0-0', saldo: '0.00' },
    cobros_a_imputar: { codigo: '2-1-1-1', saldo: '-500.00' },
    pagos_a_imputar: { codigo: '2-1-1-2', saldo: '200.00' },
  },
  ok: true,
  nota: '',
}

describe('ControlBancoCard', () => {
  beforeEach(() => getControlBanco.mockReset())

  it('muestra el estado OK y las transitorias', async () => {
    getControlBanco.mockResolvedValue(base)
    render(<ControlBancoCard orgId={3} />)
    expect(await screen.findByText(/coincide con el extracto/i)).toBeInTheDocument()
    expect(getControlBanco).toHaveBeenCalledWith(3)
    expect(screen.getByText('$ 500,00')).toBeInTheDocument()
    expect(screen.getByText('$ 200,00')).toBeInTheDocument()
    expect(screen.queryByText(/todavía no está(n)? registrado/)).not.toBeInTheDocument()
  })

  it('muestra la diferencia y los movimientos sin asiento', async () => {
    getControlBanco.mockResolvedValue({ ...base, diferencia_libro_vs_extracto: '-1234.50', movimientos_extracto_sin_asiento: 3 })
    render(<ControlBancoCard />)
    expect(await screen.findByText(/no coincide con el extracto/i)).toBeInTheDocument()
    expect(screen.getByText(/1\.234,50/)).toBeInTheDocument()
    expect(screen.getByText(/3 movimientos del extracto/)).toBeInTheDocument()
  })

  it('si la diferencia son huecos entre extractos, avisa que faltan movimientos (no un error)', async () => {
    getControlBanco.mockResolvedValue({
      ...base,
      diferencia_libro_vs_extracto: '-180133367.02',
      huecos: [
        { desde: '2026-08-20', hasta: '2026-08-20', saldo_antes: '241181442.25', saldo_despues: '245768692.42', monto_faltante: '4587250.17' },
        { desde: '2026-08-24', hasta: '2026-10-13', saldo_antes: '273638333.25', saldo_despues: '88917716.06', monto_faltante: '-184720617.19' },
      ],
      saldo_real_banco: '62897724.68',
      fecha_saldo_real_banco: '2026-10-19',
    })
    render(<ControlBancoCard />)
    expect(await screen.findByText(/faltan movimientos del banco sin subir/i)).toBeInTheDocument()
    expect(screen.queryByText(/no coincide con el extracto/i)).not.toBeInTheDocument()
    const huecos = screen.getByTestId('control-banco-huecos')
    expect(huecos.textContent).toMatch(/24\/08\/2026 y el 13\/10\/2026/)
    expect(huecos.textContent).toMatch(/184\.720\.617,19/)
    expect(huecos.textContent).toMatch(/62\.897\.724,68/)
  })
})
