import React, { useCallback, useEffect, useMemo, useState } from 'react'
import { apiClient } from '@/services/api'
import { confirmDialog } from '@/store/confirm'
import { useOrgStore } from '@/store/org'
import { useAuthStore } from '@/store/auth'
import { FileUpload } from '@/components/FileUpload'
import type {
  IvaConfigCuenta,
  IvaProyeccionPreview,
  ProyeccionIva,
  ComprobanteIva,
  LiquidacionIva,
  LiquidacionIvaCalculoPayload,
} from '@/types'

// ── Helpers ─────────────────────────────────────────────────────────────────
const fmt = (n: number) =>
  new Intl.NumberFormat('es-AR', { style: 'currency', currency: 'ARS', minimumFractionDigits: 2 }).format(n || 0)

const fmtDate = (d?: string | null) =>
  d ? new Date(d).toLocaleString('es-AR') : '—'

/** Fecha corta (sin hora) para columnas de tabla, ej. fecha de emisión de un comprobante. */
const fmtFecha = (d?: string | null) =>
  d ? new Date(d).toLocaleDateString('es-AR') : '—'

/** Período actual YYYY-MM en hora local (NO usar toISOString — da el mes de UTC). */
function periodoActual(): string {
  const d = new Date()
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}`
}

const inputClass =
  'w-full px-3 py-2 rounded-lg border bg-white dark:bg-white/5 border-gray-300 dark:border-white/10 text-gray-900 dark:text-gray-100 placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-ml-blue/40 text-sm'

const ESTADO_BADGE: Record<string, string> = {
  proyectado: 'bg-amber-100 text-amber-700 dark:bg-amber-500/15 dark:text-amber-300',
  presentado: 'bg-green-100 text-green-700 dark:bg-green-500/15 dark:text-green-300',
}

// SVG icons (Heroicons outline)
const IconCalc = () => (
  <svg className="w-4 h-4" fill="none" stroke="currentColor" strokeWidth={1.8} viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" d="M9 7.5h6m-6 3h6m-6 3h3m-9 4.5h12a2.25 2.25 0 002.25-2.25V5.25A2.25 2.25 0 0015 3H6a2.25 2.25 0 00-2.25 2.25v13.5A2.25 2.25 0 006 21z" /></svg>
)
const IconCheck = () => (
  <svg className="w-4 h-4" fill="none" stroke="currentColor" strokeWidth={1.8} viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" d="M9 12.75L11.25 15 15 9.75M21 12a9 9 0 11-18 0 9 9 0 0118 0z" /></svg>
)

export const Iva: React.FC = () => {
  const { activeOrgId } = useOrgStore()
  const { hasPermission } = useAuthStore()
  const canManageFinance = hasPermission('manage_finance')
  const canAdminAccounting = hasPermission('admin_accounting')

  const [tab, setTab] = useState<'proyeccion' | 'comprobantes' | 'liquidacion' | 'historial' | 'config'>('proyeccion')
  const [msg, setMsg] = useState<{ type: 'error' | 'ok'; text: string } | null>(null)

  // ── Tab Proyección ──────────────────────────────────────────────────────
  const [periodo, setPeriodo] = useState(periodoActual())
  const [preview, setPreview] = useState<IvaProyeccionPreview | null>(null)
  const [persistida, setPersistida] = useState<ProyeccionIva | null>(null)
  const [loadingPreview, setLoadingPreview] = useState(false)
  const [calculando, setCalculando] = useState(false)
  const [marcando, setMarcando] = useState(false)

  const cargarPreview = useCallback(async () => {
    if (!periodo) return
    setLoadingPreview(true)
    setMsg(null)
    try {
      const data = await apiClient.previewProyeccionIva(periodo, activeOrgId || undefined)
      setPreview(data)
    } catch {
      setPreview(null)
      setMsg({ type: 'error', text: 'No se pudo calcular la proyección del período.' })
    } finally {
      setLoadingPreview(false)
    }
  }, [periodo, activeOrgId])

  // Busca si ya existe una proyección persistida para este período (en el historial reciente)
  const buscarPersistida = useCallback(async () => {
    try {
      const data = await apiClient.getHistorialIva({ orgId: activeOrgId || undefined, limit: 500 })
      const found = (data.items || []).find(p => p.periodo === periodo) || null
      setPersistida(found)
    } catch {
      setPersistida(null)
    }
  }, [periodo, activeOrgId])

  useEffect(() => { cargarPreview() }, [cargarPreview])
  useEffect(() => { buscarPersistida() }, [buscarPersistida])

  const calcularYGuardar = async () => {
    setCalculando(true)
    setMsg(null)
    try {
      const p = await apiClient.calcularProyeccionIva(periodo, activeOrgId || undefined)
      setPersistida(p)
      setMsg({ type: 'ok', text: 'Proyección calculada y guardada.' })
      await cargarPreview()
    } catch (e: any) {
      const detail = e?.response?.data?.detail
      setMsg({ type: 'error', text: typeof detail === 'string' ? detail : 'No se pudo calcular la proyección.' })
    } finally {
      setCalculando(false)
    }
  }

  const marcarPresentada = async () => {
    if (!persistida) return
    const ok = await confirmDialog({
      title: 'Marcar DDJJ como presentada',
      message: `El período ${persistida.periodo} quedará inmutable: no se podrá recalcular ni pisar este snapshot. ¿Confirmás que ya presentaste la DDJJ ante ARCA?`,
      confirmLabel: 'Marcar como presentada',
      danger: false,
    })
    if (!ok) return
    setMarcando(true)
    setMsg(null)
    try {
      const p = await apiClient.marcarProyeccionPresentada(persistida.id)
      setPersistida(p)
      setMsg({ type: 'ok', text: 'DDJJ marcada como presentada.' })
    } catch {
      setMsg({ type: 'error', text: 'No se pudo marcar la proyección como presentada.' })
    } finally {
      setMarcando(false)
    }
  }

  const saldo = preview?.saldo ?? 0
  const detalle = preview?.detalle ?? []

  // ── Tab Comprobantes ─────────────────────────────────────────────────────
  const [periodoComp, setPeriodoComp] = useState(periodoActual())
  const [direccionVista, setDireccionVista] = useState<'emitido' | 'recibido'>('emitido')
  const [comprobantes, setComprobantes] = useState<ComprobanteIva[]>([])
  const [totalesComp, setTotalesComp] = useState<{ debito_incluido: number; credito_incluido: number }>({
    debito_incluido: 0, credito_incluido: 0,
  })
  const [comprobantesLoading, setComprobantesLoading] = useState(false)
  const [importando, setImportando] = useState<'emitido' | 'recibido' | null>(null)
  const [togglingId, setTogglingId] = useState<number | null>(null)
  const [deletingId, setDeletingId] = useState<number | null>(null)

  const cargarComprobantes = useCallback(async () => {
    if (!periodoComp) return
    setComprobantesLoading(true)
    try {
      const data = await apiClient.getComprobantesIva({ periodo: periodoComp, orgId: activeOrgId || undefined })
      setComprobantes(data.items || [])
      setTotalesComp(data.totales || { debito_incluido: 0, credito_incluido: 0 })
    } catch {
      setComprobantes([])
      setTotalesComp({ debito_incluido: 0, credito_incluido: 0 })
    } finally {
      setComprobantesLoading(false)
    }
  }, [periodoComp, activeOrgId])

  useEffect(() => { if (tab === 'comprobantes') cargarComprobantes() }, [tab, cargarComprobantes])

  const importarComprobantes = async (direccion: 'emitido' | 'recibido', file: File) => {
    setImportando(direccion)
    setMsg(null)
    try {
      const res = await apiClient.importarComprobantesIva(file, direccion, periodoComp, activeOrgId || undefined)
      setMsg({
        type: 'ok',
        text: `${direccion === 'emitido' ? 'Ventas' : 'Compras'}: ${res.importados} importados · ${res.duplicados} duplicados · ${res.fuera_de_periodo} fuera del período.`,
      })
      await cargarComprobantes()
    } catch (e: any) {
      const detail = e?.response?.data?.detail
      setMsg({ type: 'error', text: typeof detail === 'string' ? detail : 'No se pudo importar el archivo.' })
    } finally {
      setImportando(null)
    }
  }

  const toggleIncluido = async (c: ComprobanteIva) => {
    const nuevoValor = !c.incluido
    setComprobantes(prev => prev.map(x => (x.id === c.id ? { ...x, incluido: nuevoValor } : x)))
    setTogglingId(c.id)
    try {
      await apiClient.setComprobanteIvaIncluido(c.id, nuevoValor, activeOrgId || undefined)
      await cargarComprobantes()
    } catch {
      setComprobantes(prev => prev.map(x => (x.id === c.id ? { ...x, incluido: !nuevoValor } : x)))
      setMsg({ type: 'error', text: 'No se pudo actualizar el comprobante.' })
    } finally {
      setTogglingId(null)
    }
  }

  const eliminarComprobante = async (c: ComprobanteIva) => {
    const ok = await confirmDialog({
      title: 'Eliminar comprobante',
      message: `¿Eliminar el comprobante ${c.tipo_desc} ${String(c.punto_venta).padStart(4, '0')}-${c.numero} (${c.denominacion || c.cuit_contraparte || 'sin datos'})? Esta acción no se puede deshacer.`,
      confirmLabel: 'Eliminar',
      danger: true,
    })
    if (!ok) return
    setDeletingId(c.id)
    setMsg(null)
    try {
      await apiClient.deleteComprobanteIva(c.id, activeOrgId || undefined)
      setMsg({ type: 'ok', text: 'Comprobante eliminado.' })
      await cargarComprobantes()
    } catch {
      setMsg({ type: 'error', text: 'No se pudo eliminar el comprobante.' })
    } finally {
      setDeletingId(null)
    }
  }

  const comprobantesFiltrados = useMemo(
    () => comprobantes.filter(c => c.direccion === direccionVista),
    [comprobantes, direccionVista],
  )

  // ── Tab Liquidación ──────────────────────────────────────────────────────
  const [periodoLiq, setPeriodoLiq] = useState(periodoActual())
  const [liquidacion, setLiquidacion] = useState<LiquidacionIva | null>(null)
  const [liqLoading, setLiqLoading] = useState(false)
  const [retenciones, setRetenciones] = useState('')
  const [percepciones, setPercepciones] = useState('')
  const [ajustesOpen, setAjustesOpen] = useState(false)
  const [saldoTecnicoAnteriorOv, setSaldoTecnicoAnteriorOv] = useState('')
  const [saldoLibreAnteriorOv, setSaldoLibreAnteriorOv] = useState('')
  const [calculandoLiq, setCalculandoLiq] = useState(false)
  const [presentandoLiq, setPresentandoLiq] = useState(false)
  const [historialLiq, setHistorialLiq] = useState<LiquidacionIva[]>([])
  const [historialLiqLoading, setHistorialLiqLoading] = useState(false)

  const cargarLiquidacion = useCallback(async () => {
    if (!periodoLiq) return
    setLiqLoading(true)
    try {
      const data = await apiClient.getLiquidacionIva(periodoLiq, activeOrgId || undefined)
      setLiquidacion(data)
      setRetenciones(data ? String(data.retenciones ?? '') : '')
      setPercepciones(data ? String(data.percepciones ?? '') : '')
    } catch {
      setLiquidacion(null)
    } finally {
      setLiqLoading(false)
    }
  }, [periodoLiq, activeOrgId])

  const cargarHistorialLiq = useCallback(async () => {
    setHistorialLiqLoading(true)
    try {
      const data = await apiClient.getHistorialLiquidacionIva(activeOrgId || undefined)
      setHistorialLiq(data.items || [])
    } catch {
      setHistorialLiq([])
    } finally {
      setHistorialLiqLoading(false)
    }
  }, [activeOrgId])

  useEffect(() => { if (tab === 'liquidacion') cargarLiquidacion() }, [tab, cargarLiquidacion])
  useEffect(() => { if (tab === 'liquidacion') cargarHistorialLiq() }, [tab, cargarHistorialLiq])

  const calcularLiquidacion = async () => {
    setCalculandoLiq(true)
    setMsg(null)
    try {
      const payload: LiquidacionIvaCalculoPayload = { periodo: periodoLiq }
      const ret = parseFloat(retenciones.replace(',', '.'))
      if (!isNaN(ret)) payload.retenciones = ret
      const perc = parseFloat(percepciones.replace(',', '.'))
      if (!isNaN(perc)) payload.percepciones = perc
      if (ajustesOpen) {
        const sta = parseFloat(saldoTecnicoAnteriorOv.replace(',', '.'))
        if (!isNaN(sta)) payload.saldo_tecnico_anterior = sta
        const sla = parseFloat(saldoLibreAnteriorOv.replace(',', '.'))
        if (!isNaN(sla)) payload.saldo_libre_anterior = sla
      }
      const data = await apiClient.calcularLiquidacionIva(payload, activeOrgId || undefined)
      setLiquidacion(data)
      setMsg({ type: 'ok', text: 'Liquidación calculada.' })
      await cargarHistorialLiq()
    } catch (e: any) {
      const detail = e?.response?.data?.detail
      setMsg({ type: 'error', text: typeof detail === 'string' ? detail : 'No se pudo calcular la liquidación.' })
    } finally {
      setCalculandoLiq(false)
    }
  }

  const presentarLiquidacion = async () => {
    if (!liquidacion) return
    const ok = await confirmDialog({
      title: 'Marcar liquidación como presentada',
      message: `El período ${liquidacion.periodo} quedará inmutable ante nuevos cálculos. ¿Confirmás que ya presentaste la DDJJ de IVA ante ARCA?`,
      confirmLabel: 'Marcar como presentada',
      danger: false,
    })
    if (!ok) return
    setPresentandoLiq(true)
    setMsg(null)
    try {
      await apiClient.presentarLiquidacionIva(liquidacion.id, activeOrgId || undefined)
      setLiquidacion({ ...liquidacion, estado: 'presentada', fecha_presentacion: new Date().toISOString() })
      setMsg({ type: 'ok', text: 'Liquidación marcada como presentada.' })
      await cargarHistorialLiq()
    } catch {
      setMsg({ type: 'error', text: 'No se pudo marcar la liquidación como presentada.' })
    } finally {
      setPresentandoLiq(false)
    }
  }

  // ── Tab Historial ────────────────────────────────────────────────────────
  const [historial, setHistorial] = useState<ProyeccionIva[]>([])
  const [historialTotal, setHistorialTotal] = useState(0)
  const [historialLoading, setHistorialLoading] = useState(false)
  const [historialOffset, setHistorialOffset] = useState(0)
  const HISTORIAL_LIMIT = 20

  const cargarHistorial = useCallback(async () => {
    setHistorialLoading(true)
    try {
      const data = await apiClient.getHistorialIva({
        orgId: activeOrgId || undefined,
        limit: HISTORIAL_LIMIT,
        offset: historialOffset,
      })
      setHistorial(data.items || [])
      setHistorialTotal(data.total || 0)
    } catch {
      setHistorial([])
    } finally {
      setHistorialLoading(false)
    }
  }, [activeOrgId, historialOffset])

  useEffect(() => { if (tab === 'historial') cargarHistorial() }, [tab, cargarHistorial])

  // ── Tab Config ───────────────────────────────────────────────────────────
  const [cuentas, setCuentas] = useState<IvaConfigCuenta[]>([])
  const [configLoading, setConfigLoading] = useState(false)
  const [editValues, setEditValues] = useState<Record<number, string>>({})
  const [savingId, setSavingId] = useState<number | null>(null)

  const cargarConfig = useCallback(async () => {
    if (!canAdminAccounting) return
    setConfigLoading(true)
    try {
      const data = await apiClient.getIvaConfig(activeOrgId || undefined)
      setCuentas(data.items || [])
      const ev: Record<number, string> = {}
      for (const c of data.items || []) {
        ev[c.id] = c.tasa_iva != null ? String(Math.round(c.tasa_iva * 10000) / 100) : ''
      }
      setEditValues(ev)
    } catch {
      setCuentas([])
    } finally {
      setConfigLoading(false)
    }
  }, [activeOrgId, canAdminAccounting])

  useEffect(() => { if (tab === 'config') cargarConfig() }, [tab, cargarConfig])

  const guardarTasa = async (cuenta: IvaConfigCuenta) => {
    const raw = (editValues[cuenta.id] ?? '').trim()
    let tasa: number | null = null
    if (raw !== '') {
      const pct = parseFloat(raw.replace(',', '.'))
      if (isNaN(pct) || pct < 0 || pct > 100) {
        setMsg({ type: 'error', text: 'Ingresá un porcentaje entre 0 y 100 (ej. 21).' })
        return
      }
      tasa = pct / 100
    }
    setSavingId(cuenta.id)
    setMsg(null)
    try {
      const updated = await apiClient.setIvaConfig(cuenta.id, tasa, activeOrgId || undefined)
      setCuentas(prev => prev.map(c => (c.id === cuenta.id ? { ...c, tasa_iva: updated.tasa_iva } : c)))
      setMsg({ type: 'ok', text: `Tasa de "${cuenta.nombre}" actualizada.` })
    } catch {
      setMsg({ type: 'error', text: 'No se pudo guardar la tasa de IVA.' })
    } finally {
      setSavingId(null)
    }
  }

  const cuentasIngreso = useMemo(() => cuentas.filter(c => c.es_ingreso), [cuentas])
  const cuentasGasto = useMemo(() => cuentas.filter(c => !c.es_ingreso), [cuentas])

  // ── Render ──────────────────────────────────────────────────────────────
  return (
    <div className="p-4 md:p-6 max-w-6xl mx-auto">
      <h1 className="text-xl md:text-2xl font-semibold text-gray-900 dark:text-gray-100 mb-1">IVA — Proyección y DDJJ</h1>
      <p className="text-sm text-gray-500 dark:text-gray-400 mb-4">
        Herramienta de estimación interna. Cuadra no emite facturas: estos números son una
        <strong> proyección</strong> calculada sobre las cuentas que marcaste como gravadas, no una
        liquidación oficial ante ARCA.
      </p>

      {/* Tabs */}
      <div className="flex gap-1 mb-4 border-b border-gray-200 dark:border-white/10">
        {([
          ['proyeccion', 'Proyección'],
          ['comprobantes', 'Comprobantes'],
          ['liquidacion', 'Liquidación'],
          ['historial', 'Historial'],
          ...(canAdminAccounting ? [['config', 'Config'] as const] : []),
        ] as const).map(([k, label]) => (
          <button
            key={k}
            onClick={() => setTab(k)}
            className={`px-4 py-2 text-sm font-medium -mb-px border-b-2 transition-colors ${
              tab === k
                ? 'border-ml-blue text-ml-blue dark:text-blue-300'
                : 'border-transparent text-gray-500 dark:text-gray-400 hover:text-gray-800 dark:hover:text-gray-200'
            }`}
          >
            {label}
          </button>
        ))}
      </div>

      {msg && (
        <div className={`mb-4 px-3 py-2 rounded-lg text-sm ${
          msg.type === 'error'
            ? 'bg-red-50 text-red-700 dark:bg-red-500/10 dark:text-red-300'
            : 'bg-green-50 text-green-700 dark:bg-green-500/10 dark:text-green-300'
        }`}>
          {msg.text}
        </div>
      )}

      {/* ── Tab Proyección ── */}
      {tab === 'proyeccion' && (
        <div className="space-y-4">
          <div className="flex flex-col sm:flex-row gap-3 sm:items-end">
            <div className="w-full sm:w-48">
              <label className="block text-xs font-medium text-gray-600 dark:text-gray-400 mb-1">Período</label>
              <input
                className={inputClass}
                type="month"
                value={periodo}
                onChange={e => setPeriodo(e.target.value)}
              />
            </div>
            {canManageFinance && (
              <button
                onClick={calcularYGuardar}
                disabled={calculando || loadingPreview || persistida?.estado === 'presentado'}
                title={persistida?.estado === 'presentado' ? 'Esta DDJJ ya fue presentada — el período es inmutable' : undefined}
                className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-ml-blue text-white text-sm font-medium hover:opacity-90 disabled:opacity-50"
              >
                <IconCalc />
                {calculando ? 'Calculando…' : 'Calcular y guardar'}
              </button>
            )}
            {persistida && (
              <span className={`px-2 py-1 rounded-md text-xs font-semibold ${ESTADO_BADGE[persistida.estado] || ''}`}>
                {persistida.estado === 'presentado' ? 'Presentada' : 'Proyectada (guardada)'}
              </span>
            )}
            {canAdminAccounting && persistida && persistida.estado === 'proyectado' && (
              <button
                onClick={marcarPresentada}
                disabled={marcando}
                className="inline-flex items-center gap-2 px-4 py-2 rounded-lg border border-green-300 dark:border-green-500/30 text-green-700 dark:text-green-300 text-sm font-medium hover:bg-green-50 dark:hover:bg-green-500/10 disabled:opacity-50"
              >
                <IconCheck />
                {marcando ? 'Marcando…' : 'Marcar como presentada'}
              </button>
            )}
          </div>

          {loadingPreview && (
            <div className="text-sm text-gray-500 dark:text-gray-400">Calculando proyección…</div>
          )}

          {!loadingPreview && preview && (
            <>
              <div className="grid grid-cols-1 sm:grid-cols-4 gap-4">
                <div className="rounded-xl border border-gray-200 dark:border-white/10 bg-white dark:bg-white/5 p-4 overflow-hidden">
                  <div className="text-xs text-gray-500 dark:text-gray-400 mb-1">Débito fiscal (proyectado)</div>
                  <div className="text-base font-semibold text-gray-900 dark:text-gray-100 truncate">{fmt(preview.debito_fiscal)}</div>
                </div>
                <div className="rounded-xl border border-gray-200 dark:border-white/10 bg-white dark:bg-white/5 p-4 overflow-hidden">
                  <div className="text-xs text-gray-500 dark:text-gray-400 mb-1">Crédito fiscal (total)</div>
                  <div className="text-base font-semibold text-gray-900 dark:text-gray-100 truncate">{fmt(preview.credito_fiscal)}</div>
                  <div className="text-xs text-gray-400 mt-1 truncate">
                    proyectado {fmt(preview.credito_fiscal_proyectado)} + real {fmt(preview.credito_fiscal_real)}
                  </div>
                </div>
                <div className={`rounded-xl border p-4 overflow-hidden sm:col-span-2 ${
                  saldo > 0
                    ? 'border-red-200 dark:border-red-500/30 bg-red-50 dark:bg-red-500/10'
                    : saldo < 0
                      ? 'border-green-200 dark:border-green-500/30 bg-green-50 dark:bg-green-500/10'
                      : 'border-gray-200 dark:border-white/10 bg-white dark:bg-white/5'
                }`}>
                  <div className="text-xs text-gray-500 dark:text-gray-400 mb-1">
                    Saldo proyectado del período
                  </div>
                  <div className={`text-xl font-semibold truncate ${
                    saldo > 0
                      ? 'text-red-700 dark:text-red-300'
                      : saldo < 0
                        ? 'text-green-700 dark:text-green-300'
                        : 'text-gray-900 dark:text-gray-100'
                  }`}>
                    {fmt(Math.abs(saldo))} {saldo > 0 ? '— a pagar (estimado)' : saldo < 0 ? '— a favor (estimado)' : ''}
                  </div>
                </div>
              </div>

              <div className="rounded-xl border border-gray-200 dark:border-white/10 overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="text-left text-xs text-gray-500 dark:text-gray-400 border-b border-gray-200 dark:border-white/10">
                      <th className="px-3 py-2 font-medium">Cuenta</th>
                      <th className="px-3 py-2 font-medium">Tipo</th>
                      <th className="px-3 py-2 font-medium text-right">Base imponible</th>
                      <th className="px-3 py-2 font-medium text-right">Tasa</th>
                      <th className="px-3 py-2 font-medium text-right">IVA</th>
                    </tr>
                  </thead>
                  <tbody>
                    {detalle.length === 0 && (
                      <tr><td colSpan={5} className="px-3 py-6 text-center text-gray-400">
                        Sin cuentas gravadas con movimientos en este período. Configurá las tasas en la pestaña Config.
                      </td></tr>
                    )}
                    {detalle.map((d, i) => (
                      <tr key={d.cuenta_id} className={`border-b border-gray-100 dark:border-white/5 ${i % 2 ? 'bg-gray-50/50 dark:bg-white/[0.02]' : ''}`}>
                        <td className="px-3 py-2 text-gray-900 dark:text-gray-100 whitespace-nowrap">{d.codigo} {d.nombre}</td>
                        <td className="px-3 py-2">
                          <span className={`px-2 py-0.5 rounded-md text-xs font-semibold ${
                            d.tipo === 'ingreso'
                              ? 'bg-blue-100 text-blue-700 dark:bg-blue-500/15 dark:text-blue-300'
                              : 'bg-orange-100 text-orange-700 dark:bg-orange-500/15 dark:text-orange-300'
                          }`}>
                            {d.tipo === 'ingreso' ? 'Ingreso' : 'Gasto'}
                          </span>
                        </td>
                        <td className="px-3 py-2 text-right text-gray-700 dark:text-gray-300 whitespace-nowrap">{fmt(d.base_imponible)}</td>
                        <td className="px-3 py-2 text-right text-gray-500 dark:text-gray-400 whitespace-nowrap">{(d.tasa_iva * 100).toFixed(0)}%</td>
                        <td className="px-3 py-2 text-right text-gray-900 dark:text-gray-100 whitespace-nowrap">{fmt(d.iva)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </>
          )}
        </div>
      )}

      {/* ── Tab Comprobantes ── */}
      {tab === 'comprobantes' && (
        <div className="space-y-4">
          <div className="w-full sm:w-48">
            <label className="block text-xs font-medium text-gray-600 dark:text-gray-400 mb-1">Período</label>
            <input
              className={inputClass}
              type="month"
              value={periodoComp}
              onChange={e => setPeriodoComp(e.target.value)}
            />
          </div>

          {canManageFinance && (
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div className="rounded-xl border border-gray-200 dark:border-white/10 bg-white dark:bg-white/5 p-4">
                <div className="text-sm font-semibold text-gray-800 dark:text-gray-200 mb-2">📤 Ventas (emitidos)</div>
                <FileUpload
                  label={importando === 'emitido' ? 'Importando…' : 'Subir Excel de Mis Comprobantes (ventas)'}
                  accept=".xlsx,.xls"
                  onFileSelected={file => importarComprobantes('emitido', file)}
                />
              </div>
              <div className="rounded-xl border border-gray-200 dark:border-white/10 bg-white dark:bg-white/5 p-4">
                <div className="text-sm font-semibold text-gray-800 dark:text-gray-200 mb-2">📥 Compras (recibidos)</div>
                <FileUpload
                  label={importando === 'recibido' ? 'Importando…' : 'Subir Excel de Mis Comprobantes (compras)'}
                  accept=".xlsx,.xls"
                  onFileSelected={file => importarComprobantes('recibido', file)}
                />
              </div>
            </div>
          )}

          <div className="flex gap-1 border-b border-gray-200 dark:border-white/10">
            {([
              ['emitido', 'Emitidos (ventas)'],
              ['recibido', 'Recibidos (compras)'],
            ] as const).map(([k, label]) => (
              <button
                key={k}
                onClick={() => setDireccionVista(k)}
                className={`px-3 py-1.5 text-xs font-medium -mb-px border-b-2 transition-colors ${
                  direccionVista === k
                    ? 'border-ml-blue text-ml-blue dark:text-blue-300'
                    : 'border-transparent text-gray-500 dark:text-gray-400 hover:text-gray-800 dark:hover:text-gray-200'
                }`}
              >
                {label}
              </button>
            ))}
          </div>

          {comprobantesLoading && (
            <div className="text-sm text-gray-500 dark:text-gray-400">Cargando comprobantes…</div>
          )}

          {!comprobantesLoading && (
            <div className="rounded-xl border border-gray-200 dark:border-white/10 overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-left text-xs text-gray-500 dark:text-gray-400 border-b border-gray-200 dark:border-white/10">
                    <th className="px-3 py-2 font-medium">Fecha</th>
                    <th className="px-3 py-2 font-medium">Tipo</th>
                    <th className="px-3 py-2 font-medium">Nº</th>
                    <th className="px-3 py-2 font-medium">CUIT</th>
                    <th className="px-3 py-2 font-medium">Denominación</th>
                    <th className="px-3 py-2 font-medium text-right">Neto</th>
                    <th className="px-3 py-2 font-medium text-right">IVA</th>
                    <th className="px-3 py-2 font-medium text-right">Total</th>
                    <th className="px-3 py-2 font-medium text-center">Incluir</th>
                    <th className="px-3 py-2 font-medium w-10"></th>
                  </tr>
                </thead>
                <tbody>
                  {comprobantesFiltrados.length === 0 && (
                    <tr><td colSpan={10} className="px-3 py-6 text-center text-gray-400">
                      Sin comprobantes {direccionVista === 'emitido' ? 'emitidos' : 'recibidos'} importados para este período.
                    </td></tr>
                  )}
                  {comprobantesFiltrados.map((c, i) => (
                    <tr key={c.id} className={`border-b border-gray-100 dark:border-white/5 ${i % 2 ? 'bg-gray-50/50 dark:bg-white/[0.02]' : ''} ${!c.incluido ? 'opacity-50' : ''}`}>
                      <td className="px-3 py-2 text-gray-700 dark:text-gray-300 whitespace-nowrap">{fmtFecha(c.fecha)}</td>
                      <td className="px-3 py-2 whitespace-nowrap">
                        <span className="text-gray-700 dark:text-gray-300">{c.tipo_desc}</span>
                        {c.es_nota_credito && (
                          <span className="ml-1.5 px-1.5 py-0.5 rounded-md text-2xs font-semibold bg-amber-100 text-amber-700 dark:bg-amber-500/15 dark:text-amber-300">NC</span>
                        )}
                      </td>
                      <td className="px-3 py-2 text-gray-700 dark:text-gray-300 whitespace-nowrap font-mono">
                        {String(c.punto_venta).padStart(4, '0')}-{c.numero}
                      </td>
                      <td className="px-3 py-2 text-gray-700 dark:text-gray-300 whitespace-nowrap font-mono">{c.cuit_contraparte || '—'}</td>
                      <td className="px-3 py-2 text-gray-700 dark:text-gray-300 max-w-[14rem] truncate">{c.denominacion || '—'}</td>
                      <td className={`px-3 py-2 text-right whitespace-nowrap ${c.es_nota_credito ? 'text-red-600 dark:text-red-400' : 'text-gray-700 dark:text-gray-300'}`}>
                        {fmt(c.neto_gravado_total)}
                      </td>
                      <td className={`px-3 py-2 text-right whitespace-nowrap ${c.es_nota_credito ? 'text-red-600 dark:text-red-400' : 'text-gray-700 dark:text-gray-300'}`}>
                        {fmt(c.total_iva)}
                      </td>
                      <td className={`px-3 py-2 text-right whitespace-nowrap font-medium ${c.es_nota_credito ? 'text-red-600 dark:text-red-400' : 'text-gray-900 dark:text-gray-100'}`}>
                        {fmt(c.imp_total)}
                      </td>
                      <td className="px-3 py-2 text-center">
                        <input
                          type="checkbox"
                          checked={c.incluido}
                          disabled={togglingId === c.id || !canManageFinance}
                          onChange={() => toggleIncluido(c)}
                          className="w-4 h-4 accent-ml-blue"
                        />
                      </td>
                      <td className="px-3 py-2 text-center">
                        {canManageFinance && (
                          <button
                            onClick={() => eliminarComprobante(c)}
                            disabled={deletingId === c.id}
                            title="Eliminar comprobante"
                            className="text-gray-400 hover:text-red-500 disabled:opacity-40"
                          >
                            ✕
                          </button>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div className="rounded-xl border border-gray-200 dark:border-white/10 bg-white dark:bg-white/5 p-4">
              <div className="text-xs text-gray-500 dark:text-gray-400 mb-1">Débito fiscal incluido (ventas)</div>
              <div className="text-lg font-semibold text-gray-900 dark:text-gray-100">{fmt(totalesComp.debito_incluido)}</div>
            </div>
            <div className="rounded-xl border border-gray-200 dark:border-white/10 bg-white dark:bg-white/5 p-4">
              <div className="text-xs text-gray-500 dark:text-gray-400 mb-1">Crédito fiscal incluido (compras)</div>
              <div className="text-lg font-semibold text-gray-900 dark:text-gray-100">{fmt(totalesComp.credito_incluido)}</div>
            </div>
          </div>
        </div>
      )}

      {/* ── Tab Liquidación ── */}
      {tab === 'liquidacion' && (
        <div className="space-y-4">
          <div className="flex flex-col sm:flex-row gap-3 sm:items-end">
            <div className="w-full sm:w-48">
              <label className="block text-xs font-medium text-gray-600 dark:text-gray-400 mb-1">Período</label>
              <input
                className={inputClass}
                type="month"
                value={periodoLiq}
                onChange={e => setPeriodoLiq(e.target.value)}
              />
            </div>
            {liquidacion && (
              <span className={`px-2 py-1 rounded-md text-xs font-semibold ${ESTADO_BADGE[liquidacion.estado === 'presentada' ? 'presentado' : 'proyectado']}`}>
                {liquidacion.estado === 'presentada' ? 'Presentada' : 'Borrador'}
              </span>
            )}
          </div>

          {liqLoading && (
            <div className="text-sm text-gray-500 dark:text-gray-400">Cargando liquidación…</div>
          )}

          {!liqLoading && (!liquidacion || liquidacion.estado !== 'presentada') && canManageFinance && (
            <div className="rounded-xl border border-gray-200 dark:border-white/10 bg-white dark:bg-white/5 p-4 space-y-3">
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-medium text-gray-600 dark:text-gray-400 mb-1">Retenciones</label>
                  <input
                    className={inputClass}
                    inputMode="decimal"
                    placeholder="0"
                    value={retenciones}
                    onChange={e => setRetenciones(e.target.value)}
                  />
                </div>
                <div>
                  <label className="block text-xs font-medium text-gray-600 dark:text-gray-400 mb-1">Percepciones</label>
                  <input
                    className={inputClass}
                    inputMode="decimal"
                    placeholder="0"
                    value={percepciones}
                    onChange={e => setPercepciones(e.target.value)}
                  />
                </div>
              </div>

              <details open={ajustesOpen} onToggle={e => setAjustesOpen((e.target as HTMLDetailsElement).open)}>
                <summary className="text-xs font-medium text-gray-500 dark:text-gray-400 cursor-pointer select-none">
                  Ajustes manuales del primer período
                </summary>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 mt-2">
                  <div>
                    <label className="block text-xs font-medium text-gray-600 dark:text-gray-400 mb-1">Saldo técnico anterior (override)</label>
                    <input
                      className={inputClass}
                      inputMode="decimal"
                      placeholder="Dejar vacío para usar el histórico"
                      value={saldoTecnicoAnteriorOv}
                      onChange={e => setSaldoTecnicoAnteriorOv(e.target.value)}
                    />
                  </div>
                  <div>
                    <label className="block text-xs font-medium text-gray-600 dark:text-gray-400 mb-1">Saldo libre disponibilidad anterior (override)</label>
                    <input
                      className={inputClass}
                      inputMode="decimal"
                      placeholder="Dejar vacío para usar el histórico"
                      value={saldoLibreAnteriorOv}
                      onChange={e => setSaldoLibreAnteriorOv(e.target.value)}
                    />
                  </div>
                </div>
              </details>

              <button
                onClick={calcularLiquidacion}
                disabled={calculandoLiq}
                className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-ml-blue text-white text-sm font-medium hover:opacity-90 disabled:opacity-50"
              >
                <IconCalc />
                {calculandoLiq ? 'Calculando…' : 'Calcular liquidación'}
              </button>
            </div>
          )}

          {!liqLoading && !liquidacion && (
            <div className="text-sm text-gray-400">Todavía no hay una liquidación calculada para este período.</div>
          )}

          {!liqLoading && liquidacion && (
            <>
              <div className="rounded-xl border border-gray-200 dark:border-white/10 bg-white dark:bg-white/5 divide-y divide-gray-100 dark:divide-white/5">
                <CascadaRow label="IVA Débito fiscal" valor={liquidacion.debito_fiscal} signo="+" />
                <CascadaRow label="IVA Crédito fiscal" valor={liquidacion.credito_fiscal} signo="−" />
                <CascadaRow label="Técnico del período" valor={liquidacion.tecnico_periodo} signo="=" destacado />
                <CascadaRow label="Saldo técnico anterior" valor={liquidacion.saldo_tecnico_anterior} signo="−" />
                <CascadaRow label="Saldo técnico nuevo" valor={liquidacion.saldo_tecnico_nuevo} signo="=" destacado />
                <CascadaRow label="Retenciones" valor={liquidacion.retenciones} signo="−" />
                <CascadaRow label="Percepciones" valor={liquidacion.percepciones} signo="−" />
                <CascadaRow label="Saldo libre disponibilidad anterior" valor={liquidacion.saldo_libre_anterior} signo="−" />
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div className={`rounded-xl border p-4 ${
                  liquidacion.saldo_a_pagar > 0
                    ? 'border-red-200 dark:border-red-500/30 bg-red-50 dark:bg-red-500/10'
                    : 'border-gray-200 dark:border-white/10 bg-white dark:bg-white/5'
                }`}>
                  <div className="text-xs text-gray-500 dark:text-gray-400 mb-1">SALDO A PAGAR</div>
                  <div className={`text-2xl font-bold truncate ${
                    liquidacion.saldo_a_pagar > 0
                      ? 'text-red-700 dark:text-red-300'
                      : 'text-gray-900 dark:text-gray-100'
                  }`}>
                    {fmt(Math.max(0, liquidacion.saldo_a_pagar))}
                  </div>
                </div>
                <div className="rounded-xl border border-green-200 dark:border-green-500/30 bg-green-50 dark:bg-green-500/10 p-4">
                  <div className="text-xs text-gray-500 dark:text-gray-400 mb-1">Saldo libre disponibilidad nuevo</div>
                  <div className="text-2xl font-bold text-green-700 dark:text-green-300 truncate">
                    {fmt(liquidacion.saldo_libre_nuevo)}
                  </div>
                </div>
              </div>

              <p className="text-xs text-gray-400">
                <strong>Técnico</strong>: solo compensa IVA de otros períodos. <strong>Libre disponibilidad</strong>:
                puede usarse para pagar otros impuestos. {liquidacion.cant_emitidos} comprobante(s) emitido(s) ·
                {' '}{liquidacion.cant_recibidos} recibido(s).
              </p>

              {liquidacion.estado === 'presentada' && (
                <p className="text-xs text-gray-400">Presentada el {fmtDate(liquidacion.fecha_presentacion)}. Este período es de solo lectura.</p>
              )}

              {canAdminAccounting && liquidacion.estado === 'borrador' && (
                <button
                  onClick={presentarLiquidacion}
                  disabled={presentandoLiq}
                  className="inline-flex items-center gap-2 px-4 py-2 rounded-lg border border-green-300 dark:border-green-500/30 text-green-700 dark:text-green-300 text-sm font-medium hover:bg-green-50 dark:hover:bg-green-500/10 disabled:opacity-50"
                >
                  <IconCheck />
                  {presentandoLiq ? 'Marcando…' : 'Marcar como presentada'}
                </button>
              )}
            </>
          )}

          <div>
            <h2 className="text-sm font-semibold text-gray-800 dark:text-gray-200 mb-2">Historial de liquidaciones</h2>
            <div className="rounded-xl border border-gray-200 dark:border-white/10 overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-left text-xs text-gray-500 dark:text-gray-400 border-b border-gray-200 dark:border-white/10">
                    <th className="px-3 py-2 font-medium">Período</th>
                    <th className="px-3 py-2 font-medium text-right">Débito</th>
                    <th className="px-3 py-2 font-medium text-right">Crédito</th>
                    <th className="px-3 py-2 font-medium text-right">A pagar</th>
                    <th className="px-3 py-2 font-medium">Estado</th>
                  </tr>
                </thead>
                <tbody>
                  {historialLiqLoading && (
                    <tr><td colSpan={5} className="px-3 py-6 text-center text-gray-400">Cargando…</td></tr>
                  )}
                  {!historialLiqLoading && historialLiq.length === 0 && (
                    <tr><td colSpan={5} className="px-3 py-6 text-center text-gray-400">Sin liquidaciones calculadas.</td></tr>
                  )}
                  {!historialLiqLoading && historialLiq.map((l, i) => (
                    <tr key={l.id} className={`border-b border-gray-100 dark:border-white/5 ${i % 2 ? 'bg-gray-50/50 dark:bg-white/[0.02]' : ''}`}>
                      <td className="px-3 py-2 text-gray-900 dark:text-gray-100 whitespace-nowrap">{l.periodo}</td>
                      <td className="px-3 py-2 text-right text-gray-700 dark:text-gray-300 whitespace-nowrap">{fmt(l.debito_fiscal)}</td>
                      <td className="px-3 py-2 text-right text-gray-700 dark:text-gray-300 whitespace-nowrap">{fmt(l.credito_fiscal)}</td>
                      <td className={`px-3 py-2 text-right font-medium whitespace-nowrap ${l.saldo_a_pagar > 0 ? 'text-red-600 dark:text-red-400' : 'text-gray-700 dark:text-gray-300'}`}>
                        {fmt(l.saldo_a_pagar)}
                      </td>
                      <td className="px-3 py-2">
                        <span className={`px-2 py-0.5 rounded-md text-xs font-semibold ${ESTADO_BADGE[l.estado === 'presentada' ? 'presentado' : 'proyectado']}`}>
                          {l.estado === 'presentada' ? 'Presentada' : 'Borrador'}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}

      {/* ── Tab Historial ── */}
      {tab === 'historial' && (
        <div className="space-y-3">
          <div className="rounded-xl border border-gray-200 dark:border-white/10 overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-xs text-gray-500 dark:text-gray-400 border-b border-gray-200 dark:border-white/10">
                  <th className="px-3 py-2 font-medium">Período</th>
                  <th className="px-3 py-2 font-medium text-right">Débito fiscal</th>
                  <th className="px-3 py-2 font-medium text-right">Crédito fiscal</th>
                  <th className="px-3 py-2 font-medium text-right">Saldo</th>
                  <th className="px-3 py-2 font-medium">Estado</th>
                  <th className="px-3 py-2 font-medium">Presentada</th>
                </tr>
              </thead>
              <tbody>
                {historialLoading && (
                  <tr><td colSpan={6} className="px-3 py-6 text-center text-gray-400">Cargando…</td></tr>
                )}
                {!historialLoading && historial.length === 0 && (
                  <tr><td colSpan={6} className="px-3 py-6 text-center text-gray-400">Sin proyecciones calculadas.</td></tr>
                )}
                {!historialLoading && historial.map((p, i) => (
                  <tr key={p.id} className={`border-b border-gray-100 dark:border-white/5 ${i % 2 ? 'bg-gray-50/50 dark:bg-white/[0.02]' : ''}`}>
                    <td className="px-3 py-2 text-gray-900 dark:text-gray-100 whitespace-nowrap">{p.periodo}</td>
                    <td className="px-3 py-2 text-right text-gray-700 dark:text-gray-300 whitespace-nowrap">{fmt(p.debito_fiscal)}</td>
                    <td className="px-3 py-2 text-right text-gray-700 dark:text-gray-300 whitespace-nowrap">{fmt(p.credito_fiscal)}</td>
                    <td className={`px-3 py-2 text-right font-medium whitespace-nowrap ${
                      p.saldo > 0
                        ? 'text-red-600 dark:text-red-400'
                        : p.saldo < 0
                          ? 'text-green-600 dark:text-green-400'
                          : 'text-gray-700 dark:text-gray-300'
                    }`}>
                      {fmt(p.saldo)}
                    </td>
                    <td className="px-3 py-2">
                      <span className={`px-2 py-0.5 rounded-md text-xs font-semibold ${ESTADO_BADGE[p.estado] || ''}`}>
                        {p.estado === 'presentado' ? 'Presentada' : 'Proyectada'}
                      </span>
                    </td>
                    <td className="px-3 py-2 text-gray-500 dark:text-gray-400 whitespace-nowrap">{fmtDate(p.fecha_presentacion)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="flex items-center justify-between text-sm text-gray-500 dark:text-gray-400">
            <span>{historialTotal} período{historialTotal === 1 ? '' : 's'}</span>
            <div className="flex gap-2">
              <button
                onClick={() => setHistorialOffset(o => Math.max(0, o - HISTORIAL_LIMIT))}
                disabled={historialOffset === 0}
                className="px-3 py-1.5 rounded-lg border border-gray-300 dark:border-white/10 disabled:opacity-40"
              >
                Anterior
              </button>
              <button
                onClick={() => setHistorialOffset(o => o + HISTORIAL_LIMIT)}
                disabled={historialOffset + HISTORIAL_LIMIT >= historialTotal}
                className="px-3 py-1.5 rounded-lg border border-gray-300 dark:border-white/10 disabled:opacity-40"
              >
                Siguiente
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ── Tab Config ── */}
      {tab === 'config' && canAdminAccounting && (
        <div className="space-y-6">
          <p className="text-xs text-gray-400">
            Marcá qué cuentas de ingresos y gastos están gravadas con IVA, y a qué tasa. Ingresá el
            porcentaje (ej. <strong>21</strong> para 21%). Dejá vacío para que la cuenta no se considere
            gravada.
          </p>

          {configLoading && <div className="text-sm text-gray-500 dark:text-gray-400">Cargando cuentas…</div>}

          {!configLoading && (
            <>
              <ConfigSeccion
                titulo="Ingresos (Débito fiscal)"
                cuentas={cuentasIngreso}
                editValues={editValues}
                setEditValues={setEditValues}
                onSave={guardarTasa}
                savingId={savingId}
              />
              <ConfigSeccion
                titulo="Gastos (Crédito fiscal proyectado)"
                cuentas={cuentasGasto}
                editValues={editValues}
                setEditValues={setEditValues}
                onSave={guardarTasa}
                savingId={savingId}
              />
            </>
          )}
        </div>
      )}
    </div>
  )
}

// ── Subcomponente: sección de config (ingresos / gastos) ───────────────────
interface ConfigSeccionProps {
  titulo: string
  cuentas: IvaConfigCuenta[]
  editValues: Record<number, string>
  setEditValues: React.Dispatch<React.SetStateAction<Record<number, string>>>
  onSave: (cuenta: IvaConfigCuenta) => void
  savingId: number | null
}

const ConfigSeccion: React.FC<ConfigSeccionProps> = ({ titulo, cuentas, editValues, setEditValues, onSave, savingId }) => (
  <div>
    <h2 className="text-sm font-semibold text-gray-800 dark:text-gray-200 mb-2">{titulo}</h2>
    <div className="rounded-xl border border-gray-200 dark:border-white/10 overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="text-left text-xs text-gray-500 dark:text-gray-400 border-b border-gray-200 dark:border-white/10">
            <th className="px-3 py-2 font-medium">Cuenta</th>
            <th className="px-3 py-2 font-medium w-40">Tasa IVA (%)</th>
            <th className="px-3 py-2 font-medium w-24"></th>
          </tr>
        </thead>
        <tbody>
          {cuentas.length === 0 && (
            <tr><td colSpan={3} className="px-3 py-4 text-center text-gray-400">Sin cuentas.</td></tr>
          )}
          {cuentas.map((c, i) => (
            <tr key={c.id} className={`border-b border-gray-100 dark:border-white/5 ${i % 2 ? 'bg-gray-50/50 dark:bg-white/[0.02]' : ''}`}>
              <td className="px-3 py-2 text-gray-900 dark:text-gray-100 whitespace-nowrap">{c.codigo} {c.nombre}</td>
              <td className="px-3 py-2">
                <input
                  className={inputClass}
                  inputMode="decimal"
                  placeholder="ej. 21"
                  value={editValues[c.id] ?? ''}
                  onChange={e => setEditValues(prev => ({ ...prev, [c.id]: e.target.value }))}
                />
              </td>
              <td className="px-3 py-2">
                <button
                  onClick={() => onSave(c)}
                  disabled={savingId === c.id}
                  className="px-3 py-1.5 rounded-lg bg-ml-blue text-white text-xs font-medium hover:opacity-90 disabled:opacity-50"
                >
                  {savingId === c.id ? 'Guardando…' : 'Guardar'}
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  </div>
)

// ── Subcomponente: fila de la cascada fiscal (Liquidación) ─────────────────
interface CascadaRowProps {
  label: string
  valor: number
  signo: '+' | '−' | '='
  destacado?: boolean
}

const CascadaRow: React.FC<CascadaRowProps> = ({ label, valor, signo, destacado }) => (
  <div className={`flex items-center justify-between px-4 py-2.5 ${destacado ? 'bg-gray-50 dark:bg-white/[0.03]' : ''}`}>
    <span className={`text-sm ${destacado ? 'font-semibold text-gray-900 dark:text-gray-100' : 'text-gray-600 dark:text-gray-400'}`}>
      <span className="inline-block w-4 text-gray-400 dark:text-gray-500">{signo}</span> {label}
    </span>
    <span className={`text-sm whitespace-nowrap ${destacado ? 'font-semibold text-gray-900 dark:text-gray-100' : 'text-gray-700 dark:text-gray-300'} ${
      valor < 0 ? 'text-green-600 dark:text-green-400' : ''
    }`}>
      {fmt(Math.abs(valor))}
    </span>
  </div>
)

export default Iva
