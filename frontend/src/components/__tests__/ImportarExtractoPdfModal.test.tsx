import { render, screen, fireEvent, waitFor, within, act } from '@testing-library/react'
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import type { BorradorExtractoPdf, ConfirmarExtractoPdfResult } from '@/types'

const api = vi.hoisted(() => ({
  importarExtractoPdf: vi.fn(),
  getBorradorExtractoPdf: vi.fn(),
  confirmarBorradorExtractoPdf: vi.fn(),
  descartarBorradorExtractoPdf: vi.fn(),
}))
const confirmarDialogo = vi.hoisted(() => vi.fn())

vi.mock('@/services/api', () => ({ apiClient: api }))
vi.mock('@/store/confirm', () => ({
  confirmDialog: confirmarDialogo,
  useConfirmStore: { getState: () => ({ open: false }) },
}))

import { ImportarExtractoPdfModal } from '../extractos/ImportarExtractoPdfModal'

const borrador = (cambios: Partial<BorradorExtractoPdf> = {}): BorradorExtractoPdf => ({
  id: 5,
  estado: 'listo',
  nombre_archivo: 'resumen-sep.pdf',
  creado_at: '2026-10-04T12:00:00',
  metodo: 'automatico',
  banco: 'Galicia',
  banco_clave: 'galicia',
  periodo_desde: '2026-09-01',
  periodo_hasta: '2026-09-30',
  saldo_inicial: '1000.00',
  saldo_final: '1400.00',
  orden: 'asc',
  paginas: 2,
  escaneado: false,
  movimientos: [
    { fecha: '2026-09-02', descripcion: 'TRANSF A PROVEEDOR', monto: '-200.00', saldo: '800.00', pagina: 1, dudosa: false, motivos: [] },
    { fecha: '2026-09-05', descripcion: 'DEPOSITO', monto: '700.00', saldo: '1500.00', pagina: 1, dudosa: false, motivos: [] },
    { fecha: '2026-09-10', descripcion: 'COMISION', monto: '-100.00', saldo: '1400.00', pagina: 2, dudosa: true, motivos: ['Signo deducido'] },
  ],
  cuadre: {
    saldo_inicial: '1000.00', saldo_inicial_inferido: false,
    saldo_final: '1400.00', saldo_final_inferido: false,
    total_creditos: '700.00', total_debitos: '300.00', cantidad: 3,
    saldo_final_calculado: '1400.00', diferencia: '0.00', cierra: true, filas_con_salto: [],
  },
  alertas: [],
  duplicado: null,
  extracto_id: null,
  ia_disponible: true,
  ia_usada: false,
  puede_aprender: true,
  error: null,
  ...cambios,
})

const resultado: ConfirmarExtractoPdfResult = {
  extracto_id: 9, destino: 'nuevo', ya_existia: false, agregados: 3, duplicados: 0, no_agregados: 0,
  molde_aprendido: true, contabilidad_ok: true, mensaje: 'Extracto guardado: 3 movimientos.',
}

const pdf = () => new File(['%PDF-1.4'], 'resumen-sep.pdf', { type: 'application/pdf' })

function montar(props: Partial<React.ComponentProps<typeof ImportarExtractoPdfModal>> = {}) {
  const onCerrar = vi.fn()
  const onGuardado = vi.fn()
  const onAbrirExtracto = vi.fn()
  const r = render(
    <ImportarExtractoPdfModal
      file={pdf()}
      orgId={null}
      onCerrar={onCerrar}
      onGuardado={onGuardado}
      onAbrirExtracto={onAbrirExtracto}
      {...props}
    />,
  )
  return { ...r, onCerrar, onGuardado, onAbrirExtracto }
}

const botonGuardar = () => screen.getByRole('button', { name: /Guardar extracto|Agregar los nuevos|Guardando/ })

describe('ImportarExtractoPdfModal', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    api.importarExtractoPdf.mockResolvedValue(borrador())
    api.getBorradorExtractoPdf.mockResolvedValue(borrador())
    api.confirmarBorradorExtractoPdf.mockResolvedValue(resultado)
    api.descartarBorradorExtractoPdf.mockResolvedValue({ ok: true })
    confirmarDialogo.mockResolvedValue(true)
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('sube el PDF y muestra la revisión: método, totales y filas', async () => {
    montar()
    expect(await screen.findByText('Lectura automática')).toBeInTheDocument()
    expect(api.importarExtractoPdf).toHaveBeenCalledTimes(1)
    const [archivo, opts] = api.importarExtractoPdf.mock.calls[0]
    expect(archivo.name).toBe('resumen-sep.pdf')
    expect(opts).toEqual({ orgId: null, forzarIa: false })

    expect(screen.getByText(/Cierra: saldo inicial/)).toBeInTheDocument()
    expect(screen.getByText('$ 700,00')).toBeInTheDocument()   // créditos
    expect(screen.getByText('$ 300,00')).toBeInTheDocument()   // débitos
    expect(screen.getByText('Período: 01/09/2026 al 30/09/2026')).toBeInTheDocument()
    expect(screen.getAllByTestId('fila-movimiento')).toHaveLength(3)
    // el débito de la primera fila entra por su columna, sin signo
    expect(screen.getByLabelText('Débito, fila 1')).toHaveValue('200,00')
    expect(screen.getByLabelText('Crédito, fila 2')).toHaveValue('700,00')
    expect(screen.getByLabelText('Saldo, fila 3')).toHaveValue('1.400,00')
  })

  it('marca la fila dudosa con su motivo y deja filtrar solo esas', async () => {
    montar()
    await screen.findByText('Lectura automática')
    const filas = screen.getAllByTestId('fila-movimiento')
    expect(filas[0]).toHaveAttribute('data-estado', 'ok')
    expect(filas[2]).toHaveAttribute('data-estado', 'dudosa')
    expect(within(filas[2]).getByText(/Signo deducido/)).toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: /Solo para revisar \(1\)/ }))
    expect(screen.getAllByTestId('fila-movimiento')).toHaveLength(1)
    expect(screen.getByLabelText('Descripción, fila 3')).toHaveValue('COMISION')

    // "Está bien" limpia la duda y la fila deja de contar
    fireEvent.click(screen.getByRole('button', { name: 'Está bien' }))
    expect(screen.getByText('No hay filas para revisar.')).toBeInTheDocument()
  })

  it('editar un débito recalcula el cuadre y marca donde se corta el saldo', async () => {
    montar()
    await screen.findByText(/Cierra: saldo inicial/)

    fireEvent.change(screen.getByLabelText('Débito, fila 1'), { target: { value: '250,00' } })

    expect(screen.queryByText(/Cierra: saldo inicial/)).not.toBeInTheDocument()
    expect(screen.getAllByText(/No cierra por \$ 50,00/).length).toBeGreaterThan(0)
    expect(screen.getByText('$ 350,00')).toBeInTheDocument()   // débitos 250 + 100
    expect(within(screen.getAllByTestId('fila-movimiento')[0]).getByText(/El saldo no sigue/)).toBeInTheDocument()

    // vuelve al valor correcto y cierra otra vez
    fireEvent.change(screen.getByLabelText('Débito, fila 1'), { target: { value: '200' } })
    expect(screen.getByText(/Cierra: saldo inicial/)).toBeInTheDocument()
  })

  it('dos errores que se compensan: los totales dan pero no cierra y pregunta antes de guardar', async () => {
    montar()
    await screen.findByText(/Cierra: saldo inicial/)

    fireEvent.change(screen.getByLabelText('Débito, fila 1'), { target: { value: '250,00' } })
    fireEvent.change(screen.getByLabelText('Crédito, fila 2'), { target: { value: '750,00' } })

    expect(screen.queryByText(/Cierra: saldo inicial/)).not.toBeInTheDocument()
    expect(screen.getByText(/los totales dan, pero el saldo no sigue en 2 filas/)).toBeInTheDocument()
    expect(screen.getByText('No cierra: el saldo se corta')).toBeInTheDocument()

    confirmarDialogo.mockResolvedValueOnce(false)
    fireEvent.click(botonGuardar())
    await waitFor(() => expect(confirmarDialogo).toHaveBeenCalled())
    expect(confirmarDialogo.mock.calls[0][0].message).toMatch(/el saldo no sigue en 2 filas/)
    expect(api.confirmarBorradorExtractoPdf).not.toHaveBeenCalled()
  })

  it('si cierra, guarda sin preguntar y manda importes como string en el mismo orden', async () => {
    const { onGuardado, onCerrar } = montar()
    await screen.findByText('Lectura automática')

    fireEvent.click(botonGuardar())

    await waitFor(() => expect(api.confirmarBorradorExtractoPdf).toHaveBeenCalledTimes(1))
    expect(confirmarDialogo).not.toHaveBeenCalled()
    const [id, payload, org] = api.confirmarBorradorExtractoPdf.mock.calls[0]
    expect(id).toBe(5)
    expect(org).toBeNull()
    expect(payload).toEqual({
      movimientos: [
        { fecha: '2026-09-02', descripcion: 'TRANSF A PROVEEDOR', monto: '-200.00', saldo: '800.00' },
        { fecha: '2026-09-05', descripcion: 'DEPOSITO', monto: '700.00', saldo: '1500.00' },
        { fecha: '2026-09-10', descripcion: 'COMISION', monto: '-100.00', saldo: '1400.00' },
      ],
      saldo_inicial: '1000.00',
      saldo_final: '1400.00',
      banco: 'Galicia',
      banco_clave: null,
      nombre: null,
      destino: 'nuevo',
      extracto_id: null,
      confirmar_sin_cuadre: false,
    })
    await waitFor(() => expect(onGuardado).toHaveBeenCalledWith(resultado))
    expect(onCerrar).toHaveBeenCalled()
  })

  it('si no cierra pregunta; si la persona dice que no, no se guarda nada', async () => {
    confirmarDialogo.mockResolvedValue(false)
    montar()
    await screen.findByText('Lectura automática')
    fireEvent.change(screen.getByLabelText('Débito, fila 1'), { target: { value: '250,00' } })

    fireEvent.click(botonGuardar())

    await waitFor(() => expect(confirmarDialogo).toHaveBeenCalledTimes(1))
    expect(confirmarDialogo.mock.calls[0][0]).toMatchObject({
      title: 'El saldo no cierra',
      message: 'El saldo no cierra por $ 50,00. ¿Guardar igual?',
      confirmLabel: 'Guardar igual',
    })
    expect(api.confirmarBorradorExtractoPdf).not.toHaveBeenCalled()
  })

  it('si no cierra y la persona acepta, guarda con confirmar_sin_cuadre y el nombre editado', async () => {
    montar()
    await screen.findByText('Lectura automática')
    fireEvent.change(screen.getByLabelText('Débito, fila 1'), { target: { value: '250,00' } })
    fireEvent.change(screen.getByLabelText('Nombre del extracto'), { target: { value: 'Galicia sep 2026' } })
    fireEvent.change(screen.getByLabelText('Banco'), { target: { value: 'Banco Galicia' } })

    fireEvent.click(botonGuardar())

    await waitFor(() => expect(api.confirmarBorradorExtractoPdf).toHaveBeenCalledTimes(1))
    const payload = api.confirmarBorradorExtractoPdf.mock.calls[0][1]
    expect(payload.confirmar_sin_cuadre).toBe(true)
    expect(payload.nombre).toBe('Galicia sep 2026')
    expect(payload.banco).toBe('Banco Galicia')
    expect(payload.movimientos[0].monto).toBe('-250.00')
  })

  it('un saldo con coma, signo y miles se entiende bien (descubierto)', async () => {
    montar()
    await screen.findByText('Lectura automática')
    fireEvent.change(screen.getByLabelText('Saldo inicial'), { target: { value: '-1.234,56' } })
    // 1000 → -1234,56: ya no cierra, y la diferencia se calcula en centavos exactos
    expect(screen.getAllByText(/No cierra por \$ 2\.234,56/).length).toBeGreaterThan(0)
  })

  it('no deja guardar con filas inválidas y dice cuáles', async () => {
    montar()
    await screen.findByText('Lectura automática')

    fireEvent.change(screen.getByLabelText('Crédito, fila 1'), { target: { value: '10' } })
    expect(within(screen.getAllByTestId('fila-movimiento')[0]).getByText('Poné el importe en una sola columna')).toBeInTheDocument()
    expect(botonGuardar()).toBeDisabled()
    expect(screen.getByText('Corregí la fila marcada en rojo para poder guardar.')).toBeInTheDocument()

    fireEvent.change(screen.getByLabelText('Crédito, fila 1'), { target: { value: '' } })
    expect(botonGuardar()).toBeEnabled()

    fireEvent.change(screen.getByLabelText('Fecha, fila 2'), { target: { value: '' } })
    expect(within(screen.getAllByTestId('fila-movimiento')[1]).getByText('Falta la fecha')).toBeInTheDocument()
    expect(botonGuardar()).toBeDisabled()
  })

  it('agregar, eliminar y deshacer filas actualizan el cuadre', async () => {
    montar()
    await screen.findByText('Lectura automática')

    fireEvent.click(screen.getByRole('button', { name: 'Eliminar la fila 3' }))
    expect(screen.getAllByTestId('fila-movimiento')).toHaveLength(2)
    expect(screen.getAllByText(/No cierra por \$ 100,00/).length).toBeGreaterThan(0)

    fireEvent.click(screen.getByRole('button', { name: 'Deshacer' }))
    expect(screen.getAllByTestId('fila-movimiento')).toHaveLength(3)
    expect(screen.getByText(/Cierra: saldo inicial/)).toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: '+ Agregar movimiento' }))
    const filas = screen.getAllByTestId('fila-movimiento')
    expect(filas).toHaveLength(4)
    // la fila nueva hereda la fecha de la anterior y exige un importe
    expect(screen.getByLabelText('Fecha, fila 4')).toHaveValue('2026-09-10')
    expect(within(filas[3]).getByText('Falta el importe')).toBeInTheDocument()
    expect(botonGuardar()).toBeDisabled()
  })

  it('extracto solapado: ofrece agregar solo los nuevos y los manda al existente', async () => {
    api.importarExtractoPdf.mockResolvedValue(borrador({
      duplicado: { tipo: 'solapado', extracto_id: 7, nombre: 'Galicia agosto', banco: 'Galicia', coincidencias: 2, nuevos: 1, anteriores: 0, archivado: false },
    }))
    montar()
    await screen.findByText('Lectura automática')

    expect(screen.getByText(/2 de estos movimientos ya están en «Galicia agosto»/)).toBeInTheDocument()
    expect(screen.getByLabelText(/Agregar solo el movimiento nuevo a «Galicia agosto»/)).toBeChecked()
    expect(botonGuardar()).toHaveTextContent('Agregar los nuevos')

    fireEvent.click(botonGuardar())
    await waitFor(() => expect(api.confirmarBorradorExtractoPdf).toHaveBeenCalledTimes(1))
    const payload = api.confirmarBorradorExtractoPdf.mock.calls[0][1]
    expect(payload.destino).toBe('existente')
    expect(payload.extracto_id).toBe(7)
    expect(payload.nombre).toBeNull()
  })

  it('extracto solapado con filas anteriores: avisa que agregando solo los nuevos no se suman', async () => {
    api.importarExtractoPdf.mockResolvedValue(borrador({
      duplicado: { tipo: 'solapado', extracto_id: 7, nombre: 'Galicia sep', banco: 'Galicia', coincidencias: 1, nuevos: 0, anteriores: 2, archivado: false },
    }))
    montar()
    await screen.findByText('Lectura automática')
    expect(screen.getByText(/Agregarlo a «Galicia sep» \(no hay movimientos nuevos\)/)).toBeInTheDocument()
    expect(screen.getByText(/2 movimientos del PDF son anteriores al último del extracto/)).toBeInTheDocument()
  })

  it('extracto solapado archivado: no ofrece agregar y guarda como extracto nuevo', async () => {
    api.importarExtractoPdf.mockResolvedValue(borrador({
      duplicado: { tipo: 'solapado', extracto_id: 7, nombre: 'Galicia agosto', banco: 'Galicia', coincidencias: 2, nuevos: 1, anteriores: 0, archivado: true },
    }))
    montar()
    await screen.findByText('Lectura automática')
    expect(screen.getByText(/que está archivado \(período\s+cerrado\)/)).toBeInTheDocument()
    expect(screen.queryByRole('radio')).not.toBeInTheDocument()
    expect(botonGuardar()).toHaveTextContent('Guardar extracto')

    fireEvent.click(botonGuardar())
    await waitFor(() => expect(api.confirmarBorradorExtractoPdf).toHaveBeenCalledTimes(1))
    expect(api.confirmarBorradorExtractoPdf.mock.calls[0][1].destino).toBe('nuevo')
  })

  it('extracto solapado: se puede elegir crear uno nuevo igual', async () => {
    api.importarExtractoPdf.mockResolvedValue(borrador({
      duplicado: { tipo: 'solapado', extracto_id: 7, nombre: 'Galicia agosto', banco: 'Galicia', coincidencias: 2, nuevos: 1, anteriores: 0, archivado: false },
    }))
    montar()
    await screen.findByText('Lectura automática')
    fireEvent.click(screen.getByLabelText('Crear un extracto nuevo'))
    fireEvent.click(botonGuardar())
    await waitFor(() => expect(api.confirmarBorradorExtractoPdf).toHaveBeenCalledTimes(1))
    const payload = api.confirmarBorradorExtractoPdf.mock.calls[0][1]
    expect(payload.destino).toBe('nuevo')
    expect(payload.extracto_id).toBeNull()
  })

  it('mismo archivo: avisa que ya está importado y permite abrir el extracto', async () => {
    api.importarExtractoPdf.mockResolvedValue(borrador({
      duplicado: { tipo: 'mismo_archivo', extracto_id: 7, nombre: 'Galicia sep', banco: 'Galicia', coincidencias: 3, nuevos: 0, anteriores: 0, archivado: false },
    }))
    const { onAbrirExtracto } = montar()
    await screen.findByText('Lectura automática')

    expect(screen.getByText('Ya está importado.')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Abrir el extracto' }))
    expect(onAbrirExtracto).toHaveBeenCalledWith(7)

    // guardar igual pide confirmación antes de mandar nada
    confirmarDialogo.mockResolvedValueOnce(false)
    fireEvent.click(botonGuardar())
    await waitFor(() => expect(confirmarDialogo).toHaveBeenCalledTimes(1))
    expect(confirmarDialogo.mock.calls[0][0]).toMatchObject({ title: 'Ya está importado' })
    expect(api.confirmarBorradorExtractoPdf).not.toHaveBeenCalled()
  })

  it('un PDF ya confirmado antes se muestra como "ya importado" sin revisión', async () => {
    api.importarExtractoPdf.mockResolvedValue(borrador({ estado: 'confirmado', extracto_id: 7, movimientos: [] }))
    const { onAbrirExtracto } = montar()
    expect(await screen.findByText('Este PDF ya está importado.')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Abrir el extracto' }))
    expect(onAbrirExtracto).toHaveBeenCalledWith(7)
  })

  it('mientras la IA lee consulta cada 2,5 s y pasa a la revisión', async () => {
    vi.useFakeTimers()
    api.importarExtractoPdf.mockResolvedValue(borrador({ estado: 'procesando', movimientos: [], metodo: null }))
    api.getBorradorExtractoPdf
      .mockResolvedValueOnce(borrador({ estado: 'procesando', movimientos: [], metodo: null }))
      .mockResolvedValue(borrador({ metodo: 'ia' }))

    montar()
    await act(async () => { await vi.advanceTimersByTimeAsync(10) })
    expect(screen.getByText('Leyendo el PDF con IA…')).toBeInTheDocument()
    expect(api.getBorradorExtractoPdf).not.toHaveBeenCalled()

    await act(async () => { await vi.advanceTimersByTimeAsync(2600) })
    expect(api.getBorradorExtractoPdf).toHaveBeenCalledTimes(1)
    expect(screen.getByText('Leyendo el PDF con IA…')).toBeInTheDocument()

    await act(async () => { await vi.advanceTimersByTimeAsync(2600) })
    expect(api.getBorradorExtractoPdf).toHaveBeenCalledTimes(2)
    expect(screen.getByText('Leído con IA')).toBeInTheDocument()
    expect(screen.getAllByTestId('fila-movimiento')).toHaveLength(3)

    // ya no consulta más
    await act(async () => { await vi.advanceTimersByTimeAsync(10000) })
    expect(api.getBorradorExtractoPdf).toHaveBeenCalledTimes(2)
  })

  it('"Leer con IA" vuelve a subir el PDF pidiendo IA', async () => {
    montar()
    await screen.findByText('Lectura automática')
    api.importarExtractoPdf.mockResolvedValueOnce(borrador({ metodo: 'ia' }))

    fireEvent.click(screen.getByRole('button', { name: 'Leer con IA' }))

    expect(await screen.findByText('Leído con IA')).toBeInTheDocument()
    expect(api.importarExtractoPdf).toHaveBeenCalledTimes(2)
    expect(api.importarExtractoPdf.mock.calls[1][1]).toEqual({ orgId: null, forzarIa: true })
    // ya leído con IA: no se ofrece de nuevo
    expect(screen.queryByRole('button', { name: 'Leer con IA' })).not.toBeInTheDocument()
  })

  it('sin IA configurada no ofrece "Leer con IA"', async () => {
    api.importarExtractoPdf.mockResolvedValue(borrador({ ia_disponible: false }))
    montar()
    await screen.findByText('Lectura automática')
    expect(screen.queryByRole('button', { name: 'Leer con IA' })).not.toBeInTheDocument()
  })

  it('descartar pide confirmación, avisa al servidor y cierra', async () => {
    const { onCerrar } = montar()
    await screen.findByText('Lectura automática')

    confirmarDialogo.mockResolvedValueOnce(false)
    fireEvent.click(screen.getByRole('button', { name: 'Descartar' }))
    await waitFor(() => expect(confirmarDialogo).toHaveBeenCalledTimes(1))
    expect(api.descartarBorradorExtractoPdf).not.toHaveBeenCalled()

    fireEvent.click(screen.getByRole('button', { name: 'Descartar' }))
    await waitFor(() => expect(api.descartarBorradorExtractoPdf).toHaveBeenCalledWith(5, null))
    await waitFor(() => expect(onCerrar).toHaveBeenCalled())
  })

  it('cerrar sin tocar nada cierra directo; con cambios pregunta antes', async () => {
    const { onCerrar } = montar()
    await screen.findByText('Lectura automática')

    fireEvent.click(screen.getByRole('button', { name: 'Cerrar' }))
    await waitFor(() => expect(onCerrar).toHaveBeenCalledTimes(1))
    expect(confirmarDialogo).not.toHaveBeenCalled()

    fireEvent.change(screen.getByLabelText('Débito, fila 1'), { target: { value: '201' } })
    confirmarDialogo.mockResolvedValueOnce(false)
    fireEvent.click(screen.getByRole('button', { name: 'Cerrar' }))
    await waitFor(() => expect(confirmarDialogo).toHaveBeenCalledTimes(1))
    expect(confirmarDialogo.mock.calls[0][0]).toMatchObject({ cancelLabel: 'Seguir editando' })
    expect(onCerrar).toHaveBeenCalledTimes(1)
  })

  it('si falla la lectura muestra el motivo y deja reintentar', async () => {
    api.importarExtractoPdf.mockRejectedValueOnce({ response: { status: 400, data: { detail: 'El PDF tiene contraseña.' } } })
    montar()
    expect(await screen.findByText('El PDF tiene contraseña.')).toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: 'Probar de nuevo' }))
    expect(await screen.findByText('Lectura automática')).toBeInTheDocument()
    expect(api.importarExtractoPdf).toHaveBeenCalledTimes(2)
  })

  it('abre un borrador existente sin PDF local y no ofrece releer con IA', async () => {
    montar({ file: null, borradorId: 5 })
    expect(await screen.findByText('Lectura automática')).toBeInTheDocument()
    expect(api.importarExtractoPdf).not.toHaveBeenCalled()
    expect(api.getBorradorExtractoPdf).toHaveBeenCalledWith(5, null)
    expect(screen.queryByRole('button', { name: 'Leer con IA' })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /el PDF$/ })).not.toBeInTheDocument()
  })

  it('un borrador sin movimientos deja cargarlos a mano', async () => {
    api.importarExtractoPdf.mockResolvedValue(borrador({
      movimientos: [], metodo: null, saldo_inicial: null, saldo_final: null,
      cuadre: {
        saldo_inicial: null, saldo_inicial_inferido: false, saldo_final: null, saldo_final_inferido: false,
        total_creditos: '0.00', total_debitos: '0.00', cantidad: 0, saldo_final_calculado: null,
        diferencia: null, cierra: false, filas_con_salto: [],
      },
      alertas: [{ nivel: 'aviso', codigo: 'sin_movimientos', mensaje: 'No encontramos movimientos en el PDF.' }],
    }))
    montar()
    expect(await screen.findByText('Sin lectura')).toBeInTheDocument()
    expect(screen.getByText('No encontramos movimientos en el PDF.')).toBeInTheDocument()
    expect(botonGuardar()).toBeDisabled()
    expect(screen.getByText(/No se puede verificar/)).toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: '+ Agregar movimiento' }))
    fireEvent.change(screen.getByLabelText('Fecha, fila 1'), { target: { value: '2026-09-03' } })
    fireEvent.change(screen.getByLabelText('Crédito, fila 1'), { target: { value: '1.500,00' } })
    expect(botonGuardar()).toBeEnabled()
  })

  it('si el servidor dice que no cierra, pregunta con su mensaje y reintenta', async () => {
    api.confirmarBorradorExtractoPdf
      .mockRejectedValueOnce({ response: { status: 422, data: { detail: 'El saldo no cierra: hay una diferencia de $ 0,05. Revisá los movimientos o confirmá igual.' } } })
      .mockResolvedValueOnce(resultado)
    const { onGuardado } = montar()
    await screen.findByText('Lectura automática')

    fireEvent.click(botonGuardar())

    await waitFor(() => expect(api.confirmarBorradorExtractoPdf).toHaveBeenCalledTimes(2))
    expect(confirmarDialogo.mock.calls[0][0].message).toContain('diferencia de $ 0,05')
    expect(api.confirmarBorradorExtractoPdf.mock.calls[0][1].confirmar_sin_cuadre).toBe(false)
    expect(api.confirmarBorradorExtractoPdf.mock.calls[1][1].confirmar_sin_cuadre).toBe(true)
    await waitFor(() => expect(onGuardado).toHaveBeenCalledWith(resultado))
  })

  it('si se corta la respuesta, revisa si el guardado se hizo antes de dejar reintentar', async () => {
    api.confirmarBorradorExtractoPdf.mockRejectedValueOnce(new Error('Network Error'))
    api.getBorradorExtractoPdf.mockResolvedValue(borrador({ estado: 'confirmado', extracto_id: 9 }))
    const { onGuardado } = montar()
    await screen.findByText('Lectura automática')

    fireEvent.click(botonGuardar())

    await waitFor(() => expect(onGuardado).toHaveBeenCalledTimes(1))
    expect(onGuardado.mock.calls[0][0]).toMatchObject({ extracto_id: 9, ya_existia: true })
  })

  it('un error del servidor al guardar se muestra y se puede volver a intentar', async () => {
    api.confirmarBorradorExtractoPdf.mockRejectedValueOnce({ response: { status: 409, data: { detail: 'Ya se está guardando.' } } })
    const { onGuardado } = montar()
    await screen.findByText('Lectura automática')

    fireEvent.click(botonGuardar())

    expect(await screen.findByText('Ya se está guardando.')).toBeInTheDocument()
    expect(onGuardado).not.toHaveBeenCalled()
    expect(botonGuardar()).toBeEnabled()
  })

  it('muestra el PDF original al lado cuando se lo pide', async () => {
    const crear = vi.fn(() => 'blob:pdf-local')
    const revocar = vi.fn()
    Object.assign(URL, { createObjectURL: crear, revokeObjectURL: revocar })
    const { unmount } = montar()
    await screen.findByText('Lectura automática')

    fireEvent.click(screen.getByRole('button', { name: 'Ver el PDF' }))
    expect(screen.getByTitle('PDF original')).toHaveAttribute('src', 'blob:pdf-local')

    unmount()
    expect(revocar).toHaveBeenCalledWith('blob:pdf-local')
    // @ts-expect-error limpieza del stub
    delete URL.createObjectURL
    // @ts-expect-error limpieza del stub
    delete URL.revokeObjectURL
  })
})
