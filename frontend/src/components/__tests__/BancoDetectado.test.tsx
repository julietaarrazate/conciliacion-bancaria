import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import type { BancoOpcion, DeteccionBanco, PreviewExtracto } from '@/types'

const api = vi.hoisted(() => ({
  getBancosExtracto: vi.fn(),
  importarExtractoPdf: vi.fn(),
  getBorradorExtractoPdf: vi.fn(),
  confirmarBorradorExtractoPdf: vi.fn(),
  descartarBorradorExtractoPdf: vi.fn(),
}))
vi.mock('@/services/api', () => ({ apiClient: api }))
vi.mock('@/store/confirm', () => ({
  confirmDialog: vi.fn().mockResolvedValue(true),
  useConfirmStore: { getState: () => ({ open: false }) },
}))

import { BancoDetectado, bancoInicial } from '../extractos/BancoDetectado'
import { ExtractoMapperModal } from '../extractos/ExtractoMapperModal'
import { ImportarExtractoPdfModal } from '../extractos/ImportarExtractoPdfModal'

const BANCOS: BancoOpcion[] = [
  { clave: 'galicia', nombre: 'Galicia' },
  { clave: 'macro', nombre: 'Banco Macro' },
  { clave: 'brubank', nombre: 'Brubank' },
]

const det = (c: Partial<DeteccionBanco> = {}): DeteccionBanco => ({
  banco_clave: 'galicia', nombre: 'Galicia', confianza: 0.95, motivo: 'por el CBU de la cuenta',
  origen: 'cbu', conflicto: null, pedir_confirmacion: false, ...c,
})

const GENERICO = det({
  banco_clave: 'generico', nombre: null, confianza: 0, motivo: 'no encontramos el banco en el archivo: elegilo de la lista',
  origen: 'ninguno', pedir_confirmacion: true,
})

function preview(d: DeteccionBanco): PreviewExtracto {
  return {
    hoja: 'Hoja1', hojas: ['Hoja1'], banco_clave: d.banco_clave, banco: d.nombre, banco_deteccion: d,
    origen: 'heuristica', plantilla_id: null,
    mapeo: { hoja: 'Hoja1', fila_encabezado: 0, columnas: { fecha: 0, titular: 1, monto: 2, saldo: 3 },
             signo: 'columna_unica', formato_fecha: 'auto', decimal: 'auto' },
    firma: 'abc', confianza: 0.9, necesita_mapeo: false, motivos: [], aviso_saldos: null,
    grilla: { desde: 0, columnas: 4, filas: [['Fecha', 'Concepto', 'Importe', 'Saldo'], ['01/05/2026', 'Cobro', '1.000,00', '2.000,00']] },
    encabezados: ['Fecha', 'Concepto', 'Importe', 'Saldo'], total_movimientos: 1, filas_descartadas: 0,
    filas_resumen: 0, muestra: [], cuadre: { tiene_saldo: true, cuadra: true, orden: 'asc', mensaje: '' },
  }
}

describe('BancoDetectado', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    api.getBancosExtracto.mockResolvedValue(BANCOS)
  })

  it('muestra el banco detectado con el motivo', () => {
    render(<BancoDetectado deteccion={det()} value="galicia" onChange={vi.fn()} bancos={BANCOS} />)
    expect(screen.getByText('Galicia', { selector: 'span' })).toBeInTheDocument()
    expect(screen.getByText('(por el CBU de la cuenta)')).toBeInTheDocument()
    expect(screen.getByLabelText('Banco del extracto')).toHaveValue('galicia')
  })

  it('sin banco reconocido pide elegirlo', () => {
    render(<BancoDetectado deteccion={GENERICO} value="" onChange={vi.fn()} bancos={BANCOS} />)
    expect(screen.getByText('No reconocimos el banco: elegilo de la lista')).toBeInTheDocument()
    expect(bancoInicial(GENERICO)).toBe('')
  })

  it('muestra el conflicto entre señales', () => {
    const d = det({ conflicto: 'El archivo también indica Banco Macro (por el nombre en el encabezado).', pedir_confirmacion: true })
    render(<BancoDetectado deteccion={d} value="galicia" onChange={vi.fn()} bancos={BANCOS} />)
    expect(screen.getByText(/también indica Banco Macro/)).toBeInTheDocument()
  })

  it('cambiar el banco avisa con clave y nombre', () => {
    const onChange = vi.fn()
    render(<BancoDetectado deteccion={det()} value="galicia" onChange={onChange} bancos={BANCOS} />)
    fireEvent.change(screen.getByLabelText('Banco del extracto'), { target: { value: 'brubank' } })
    expect(onChange).toHaveBeenCalledWith('brubank', 'Brubank')
  })

  it('pide la lista al servidor si no se la pasan', async () => {
    render(<BancoDetectado deteccion={det()} value="galicia" onChange={vi.fn()} />)
    await waitFor(() => expect(screen.getByRole('option', { name: 'Brubank' })).toBeInTheDocument())
  })
})

describe('ExtractoMapperModal con banco', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    api.getBancosExtracto.mockResolvedValue(BANCOS)
  })

  it('manda el banco elegido al importar', async () => {
    const onConfirm = vi.fn()
    render(<ExtractoMapperModal preview={preview(det())} onRevisar={vi.fn()} onConfirm={onConfirm} onCancel={vi.fn()} />)
    await waitFor(() => expect(screen.getByRole('option', { name: 'Brubank' })).toBeInTheDocument())
    fireEvent.change(screen.getByLabelText('Banco del extracto'), { target: { value: 'brubank' } })
    fireEvent.click(screen.getByRole('button', { name: 'Importar extracto' }))
    expect(onConfirm).toHaveBeenCalledWith(expect.any(Object), 'brubank')
  })

  it('sin banco reconocido no deja importar hasta elegir uno', async () => {
    const onConfirm = vi.fn()
    render(<ExtractoMapperModal preview={preview(GENERICO)} onRevisar={vi.fn()} onConfirm={onConfirm} onCancel={vi.fn()} />)
    const boton = screen.getByRole('button', { name: 'Importar extracto' })
    expect(boton).toBeDisabled()
    expect(screen.getByText(/Elegí de qué banco es el extracto/)).toBeInTheDocument()
    fireEvent.change(screen.getByLabelText('Banco del extracto'), { target: { value: 'generico' } })
    fireEvent.click(boton)
    expect(onConfirm).toHaveBeenCalledWith(expect.any(Object), 'generico')
  })
})

describe('Revisión del PDF con banco', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    api.getBancosExtracto.mockResolvedValue(BANCOS)
    const borrador = {
      id: 7, estado: 'listo', nombre_archivo: 'resumen.pdf', creado_at: null, metodo: 'automatico',
      banco: 'Banco Macro', banco_clave: 'generico', banco_deteccion: GENERICO,
      periodo_desde: '2026-09-01', periodo_hasta: '2026-09-30', saldo_inicial: '1000.00', saldo_final: '1500.00',
      orden: 'asc', paginas: 1, escaneado: false,
      movimientos: [{ fecha: '2026-09-02', descripcion: 'DEPOSITO', monto: '500.00', saldo: '1500.00', pagina: 1, dudosa: false, motivos: [] }],
      cuadre: { saldo_inicial: '1000.00', saldo_inicial_inferido: false, saldo_final: '1500.00', saldo_final_inferido: false,
                total_creditos: '500.00', total_debitos: '0.00', cantidad: 1, saldo_final_calculado: '1500.00',
                diferencia: '0.00', cierra: true, filas_con_salto: [] },
      alertas: [], duplicado: null, extracto_id: null, ia_disponible: false, ia_usada: false, puede_aprender: true, error: null,
    }
    api.importarExtractoPdf.mockResolvedValue(borrador)
    api.getBorradorExtractoPdf.mockResolvedValue(borrador)
    api.confirmarBorradorExtractoPdf.mockResolvedValue({
      extracto_id: 1, destino: 'nuevo', ya_existia: false, agregados: 1, duplicados: 0, no_agregados: 0,
      molde_aprendido: true, contabilidad_ok: true, mensaje: 'ok',
    })
  })

  it('pide el banco y lo manda al guardar', async () => {
    render(
      <ImportarExtractoPdfModal
        file={new File(['%PDF-1.4'], 'resumen.pdf', { type: 'application/pdf' })}
        orgId={null} onCerrar={vi.fn()} onGuardado={vi.fn()} onAbrirExtracto={vi.fn()}
      />,
    )
    expect(await screen.findByText('No reconocimos el banco: elegilo de la lista')).toBeInTheDocument()
    const guardar = () => screen.getByRole('button', { name: /Guardar extracto/ })
    fireEvent.click(guardar())
    expect(await screen.findByText(/Elegí de qué banco es el extracto/)).toBeInTheDocument()
    expect(api.confirmarBorradorExtractoPdf).not.toHaveBeenCalled()

    await waitFor(() => expect(screen.getByRole('option', { name: 'Brubank' })).toBeInTheDocument())
    fireEvent.change(screen.getByLabelText('Banco del extracto'), { target: { value: 'brubank' } })
    fireEvent.click(guardar())
    await waitFor(() => expect(api.confirmarBorradorExtractoPdf).toHaveBeenCalledTimes(1))
    const payload = api.confirmarBorradorExtractoPdf.mock.calls[0][1]
    expect(payload.banco_clave).toBe('brubank')
    expect(payload.banco).toBe('Brubank')
  })
})
