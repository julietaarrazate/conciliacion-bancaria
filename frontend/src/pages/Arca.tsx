import React, { useCallback, useEffect, useState } from 'react'
import { apiClient } from '@/services/api'
import { useOrgStore } from '@/store/org'
import { useAuthStore } from '@/store/auth'
import type { ArcaConfig, ComprobanteArca } from '@/types'

// ── Helpers ─────────────────────────────────────────────────────────────────
const fmt = (n: number) =>
  new Intl.NumberFormat('es-AR', { style: 'currency', currency: 'ARS', minimumFractionDigits: 2 }).format(n || 0)

const fmtDate = (d?: string | null) => (d ? new Date(d).toLocaleString('es-AR') : '—')

const inputClass =
  'w-full px-3 py-2 rounded-lg border bg-white dark:bg-white/5 border-gray-300 dark:border-white/10 text-gray-900 dark:text-gray-100 placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-ml-blue/40 text-sm'

const ESTADO_BADGE: Record<string, string> = {
  borrador: 'bg-gray-100 text-gray-700 dark:bg-white/10 dark:text-gray-300',
  emitido: 'bg-green-100 text-green-700 dark:bg-green-500/15 dark:text-green-300',
  rechazado: 'bg-red-100 text-red-700 dark:bg-red-500/15 dark:text-red-300',
  error: 'bg-amber-100 text-amber-700 dark:bg-amber-500/15 dark:text-amber-300',
}

const TIPOS_COMPROBANTE: Record<number, string> = {
  1: 'Factura A',
  6: 'Factura B',
  11: 'Factura C',
}

// SVG icons (Heroicons outline)
const IconSend = () => (
  <svg className="w-4 h-4" fill="none" stroke="currentColor" strokeWidth={1.8} viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" d="M6 12L3.269 3.125A59.769 59.769 0 0121.485 12 59.768 59.768 0 013.27 20.875L5.999 12zm0 0h7.5" /></svg>
)
const IconPlus = () => (
  <svg className="w-4 h-4" fill="none" stroke="currentColor" strokeWidth={1.8} viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" d="M12 4.5v15m7.5-7.5h-15" /></svg>
)

interface ClienteOpt { id: number; nombre: string }

export const Arca: React.FC = () => {
  const { activeOrgId } = useOrgStore()
  const { hasPermission } = useAuthStore()
  const canManageFinance = hasPermission('manage_finance')
  const canAdminAccounting = hasPermission('admin_accounting')
  const canViewAccounting = hasPermission('view_accounting')

  const [tab, setTab] = useState<'comprobantes' | 'config'>('comprobantes')
  const [msg, setMsg] = useState<{ type: 'error' | 'ok'; text: string } | null>(null)

  // ── Tab Config ───────────────────────────────────────────────────────────
  const [config, setConfig] = useState<ArcaConfig | null>(null)
  const [configLoading, setConfigLoading] = useState(false)
  const [cuit, setCuit] = useState('')
  const [ambiente, setAmbiente] = useState<'homologacion' | 'produccion'>('homologacion')
  const [puntoVenta, setPuntoVenta] = useState(1)
  const [activo, setActivo] = useState(false)
  const [savingConfig, setSavingConfig] = useState(false)
  const [certPem, setCertPem] = useState('')
  const [keyPem, setKeyPem] = useState('')
  const [savingCert, setSavingCert] = useState(false)

  const cargarConfig = useCallback(async () => {
    if (!canAdminAccounting) return
    setConfigLoading(true)
    try {
      const data = await apiClient.getArcaConfig(activeOrgId || undefined)
      setConfig(data)
      setCuit(data.cuit || '')
      setAmbiente(data.ambiente)
      setPuntoVenta(data.punto_venta)
      setActivo(data.activo)
    } catch {
      setConfig(null)
    } finally {
      setConfigLoading(false)
    }
  }, [activeOrgId, canAdminAccounting])

  useEffect(() => { if (tab === 'config') cargarConfig() }, [tab, cargarConfig])

  const guardarConfig = async () => {
    setSavingConfig(true)
    setMsg(null)
    try {
      const data = await apiClient.putArcaConfig({
        activo, cuit: cuit.trim() || null, ambiente, punto_venta: puntoVenta,
      }, activeOrgId || undefined)
      setConfig(data)
      setActivo(data.activo)
      setMsg({ type: 'ok', text: 'Configuración de ARCA guardada.' })
    } catch (e: any) {
      const detail = e?.response?.data?.detail
      setMsg({ type: 'error', text: typeof detail === 'string' ? detail : 'No se pudo guardar la configuración.' })
    } finally {
      setSavingConfig(false)
    }
  }

  const subirCertificado = async () => {
    if (!certPem.trim() || !keyPem.trim()) {
      setMsg({ type: 'error', text: 'Pegá el certificado (.crt) y la clave privada (.key) en formato PEM.' })
      return
    }
    setSavingCert(true)
    setMsg(null)
    try {
      const data = await apiClient.subirCertificadoArca(certPem, keyPem, activeOrgId || undefined)
      setConfig(data)
      setCertPem('')
      setKeyPem('')
      setMsg({ type: 'ok', text: 'Certificado cargado y cifrado correctamente.' })
    } catch (e: any) {
      const detail = e?.response?.data?.detail
      setMsg({ type: 'error', text: typeof detail === 'string' ? detail : 'No se pudo cargar el certificado.' })
    } finally {
      setSavingCert(false)
    }
  }

  const borrarCertificado = async () => {
    if (!window.confirm('¿Borrar el certificado y la clave privada cargados? El módulo se desactivará.')) return
    setSavingCert(true)
    setMsg(null)
    try {
      const data = await apiClient.borrarCertificadoArca(activeOrgId || undefined)
      setConfig(data)
      setActivo(data.activo)
      setMsg({ type: 'ok', text: 'Certificado borrado.' })
    } catch {
      setMsg({ type: 'error', text: 'No se pudo borrar el certificado.' })
    } finally {
      setSavingCert(false)
    }
  }

  // ── Tab Comprobantes ─────────────────────────────────────────────────────
  const [comprobantes, setComprobantes] = useState<ComprobanteArca[]>([])
  const [total, setTotal] = useState(0)
  const [loadingList, setLoadingList] = useState(false)
  const [offset, setOffset] = useState(0)
  const LIMIT = 20

  const cargarComprobantes = useCallback(async () => {
    setLoadingList(true)
    try {
      const data = await apiClient.getComprobantesArca({ orgId: activeOrgId || undefined, limit: LIMIT, offset })
      setComprobantes(data.items || [])
      setTotal(data.total || 0)
    } catch {
      setComprobantes([])
    } finally {
      setLoadingList(false)
    }
  }, [activeOrgId, offset])

  useEffect(() => { if (tab === 'comprobantes') cargarComprobantes() }, [tab, cargarComprobantes])

  // Formulario de nuevo comprobante
  const [showForm, setShowForm] = useState(false)
  const [clientes, setClientes] = useState<ClienteOpt[]>([])
  const [form, setForm] = useState({
    cliente_id: '', tipo_comprobante: 11, concepto: 1, importe_neto: '', importe_iva: '', importe_total: '',
    fecha_serv_desde: '', fecha_serv_hasta: '', fecha_vto_pago: '',
  })
  const [creando, setCreando] = useState(false)
  const [emitiendoId, setEmitiendoId] = useState<number | null>(null)

  useEffect(() => {
    if (!showForm) return
    const params = activeOrgId ? { org_id: activeOrgId } : {}
    apiClient.client.get('/clientes/archivos', { params }).then(r => {
      interface OrgRaw { clientes?: { id: number; nombre: string }[] }
      const orgs: OrgRaw[] = r.data.organizaciones || []
      const todos = orgs.flatMap(o => o.clientes || [])
      setClientes(todos.map(c => ({ id: c.id, nombre: c.nombre })).sort((a, b) => a.nombre.localeCompare(b.nombre)))
    }).catch(() => {})
  }, [showForm, activeOrgId])

  const crearComprobante = async () => {
    const total = parseFloat(form.importe_total.replace(',', '.'))
    if (!total || total <= 0) {
      setMsg({ type: 'error', text: 'El importe total debe ser mayor a 0.' })
      return
    }
    if (form.concepto !== 1 && (!form.fecha_serv_desde || !form.fecha_serv_hasta || !form.fecha_vto_pago)) {
      setMsg({ type: 'error', text: 'Servicios/Productos y servicios requiere completar el período del servicio y la fecha de vencimiento de pago.' })
      return
    }
    setCreando(true)
    setMsg(null)
    try {
      await apiClient.crearComprobanteArca({
        cliente_id: form.cliente_id ? Number(form.cliente_id) : null,
        tipo_comprobante: form.tipo_comprobante,
        concepto: form.concepto,
        importe_neto: parseFloat((form.importe_neto || '0').replace(',', '.')) || 0,
        importe_iva: parseFloat((form.importe_iva || '0').replace(',', '.')) || 0,
        importe_total: total,
        fecha_serv_desde: form.concepto !== 1 ? form.fecha_serv_desde : null,
        fecha_serv_hasta: form.concepto !== 1 ? form.fecha_serv_hasta : null,
        fecha_vto_pago: form.concepto !== 1 ? form.fecha_vto_pago : null,
      }, activeOrgId || undefined)
      setMsg({ type: 'ok', text: 'Comprobante creado en borrador.' })
      setShowForm(false)
      setForm({
        cliente_id: '', tipo_comprobante: 11, concepto: 1, importe_neto: '', importe_iva: '', importe_total: '',
        fecha_serv_desde: '', fecha_serv_hasta: '', fecha_vto_pago: '',
      })
      setOffset(0)
      await cargarComprobantes()
    } catch (e: any) {
      const detail = e?.response?.data?.detail
      setMsg({ type: 'error', text: typeof detail === 'string' ? detail : 'No se pudo crear el comprobante.' })
    } finally {
      setCreando(false)
    }
  }

  const emitir = async (c: ComprobanteArca) => {
    if (!window.confirm(`¿Pedir el CAE a ARCA para este comprobante por ${fmt(c.importe_total)}? Una vez emitido es inmutable.`)) return
    setEmitiendoId(c.id)
    setMsg(null)
    try {
      await apiClient.emitirComprobanteArca(c.id, activeOrgId || undefined)
      setMsg({ type: 'ok', text: 'Comprobante emitido — CAE obtenido de ARCA.' })
      await cargarComprobantes()
    } catch (e: any) {
      const detail = e?.response?.data?.detail
      setMsg({ type: 'error', text: typeof detail === 'string' ? detail : 'No se pudo emitir el comprobante.' })
      await cargarComprobantes()
    } finally {
      setEmitiendoId(null)
    }
  }

  // ── Render ──────────────────────────────────────────────────────────────
  return (
    <div className="p-4 md:p-6 max-w-6xl mx-auto">
      <h1 className="text-xl md:text-2xl font-semibold text-gray-900 dark:text-gray-100 mb-1">ARCA — Facturación electrónica</h1>
      <p className="text-sm text-gray-500 dark:text-gray-400 mb-4">
        Integración propia con WSFEv1/WSAA de ARCA (ex-AFIP). El certificado y la clave privada se
        cifran antes de guardarse y <strong>nunca</strong> se muestran ni se exponen por la API.
      </p>

      {/* Tabs */}
      <div className="flex gap-1 mb-4 border-b border-gray-200 dark:border-white/10">
        {([
          ['comprobantes', 'Comprobantes'],
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

      {/* ── Tab Comprobantes ── */}
      {tab === 'comprobantes' && canViewAccounting && (
        <div className="space-y-3">
          {config && !config.activo && (
            <div className="px-3 py-2 rounded-lg text-sm bg-amber-50 text-amber-700 dark:bg-amber-500/10 dark:text-amber-300">
              El módulo ARCA no está activo para esta organización. Activalo en la pestaña Config (cargar
              certificado primero).
            </div>
          )}

          {canManageFinance && (
            <div className="flex justify-end">
              <button
                onClick={() => setShowForm(s => !s)}
                className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-ml-blue text-white text-sm font-medium hover:opacity-90"
              >
                <IconPlus />
                Nuevo comprobante
              </button>
            </div>
          )}

          {showForm && canManageFinance && (
            <div className="rounded-xl border border-gray-200 dark:border-white/10 bg-white dark:bg-white/5 p-4 space-y-3">
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-medium text-gray-600 dark:text-gray-400 mb-1">Cliente (opcional)</label>
                  <select
                    className={inputClass}
                    value={form.cliente_id}
                    onChange={e => setForm(p => ({ ...p, cliente_id: e.target.value }))}
                  >
                    <option value="">— Sin cliente —</option>
                    {clientes.map(c => (
                      <option key={c.id} value={c.id}>{c.nombre}</option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className="block text-xs font-medium text-gray-600 dark:text-gray-400 mb-1">Tipo de comprobante</label>
                  <select
                    className={inputClass}
                    value={form.tipo_comprobante}
                    onChange={e => setForm(p => ({ ...p, tipo_comprobante: Number(e.target.value) }))}
                  >
                    {Object.entries(TIPOS_COMPROBANTE).map(([v, label]) => (
                      <option key={v} value={v}>{label}</option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className="block text-xs font-medium text-gray-600 dark:text-gray-400 mb-1">Concepto</label>
                  <select
                    className={inputClass}
                    value={form.concepto}
                    onChange={e => setForm(p => ({ ...p, concepto: Number(e.target.value) }))}
                  >
                    <option value={1}>Productos</option>
                    <option value={2}>Servicios</option>
                    <option value={3}>Productos y servicios</option>
                  </select>
                </div>
                {form.concepto !== 1 && (
                  <>
                    <div>
                      <label className="block text-xs font-medium text-gray-600 dark:text-gray-400 mb-1">Período servicio — desde</label>
                      <input
                        type="date"
                        className={inputClass}
                        value={form.fecha_serv_desde}
                        onChange={e => setForm(p => ({ ...p, fecha_serv_desde: e.target.value }))}
                      />
                    </div>
                    <div>
                      <label className="block text-xs font-medium text-gray-600 dark:text-gray-400 mb-1">Período servicio — hasta</label>
                      <input
                        type="date"
                        className={inputClass}
                        value={form.fecha_serv_hasta}
                        onChange={e => setForm(p => ({ ...p, fecha_serv_hasta: e.target.value }))}
                      />
                    </div>
                    <div>
                      <label className="block text-xs font-medium text-gray-600 dark:text-gray-400 mb-1">Vencimiento de pago</label>
                      <input
                        type="date"
                        className={inputClass}
                        value={form.fecha_vto_pago}
                        onChange={e => setForm(p => ({ ...p, fecha_vto_pago: e.target.value }))}
                      />
                    </div>
                  </>
                )}
                <div>
                  <label className="block text-xs font-medium text-gray-600 dark:text-gray-400 mb-1">Importe neto</label>
                  <input
                    className={inputClass}
                    inputMode="decimal"
                    placeholder="0.00"
                    value={form.importe_neto}
                    onChange={e => setForm(p => ({ ...p, importe_neto: e.target.value }))}
                  />
                </div>
                <div>
                  <label className="block text-xs font-medium text-gray-600 dark:text-gray-400 mb-1">Importe IVA</label>
                  <input
                    className={inputClass}
                    inputMode="decimal"
                    placeholder="0.00"
                    value={form.importe_iva}
                    onChange={e => setForm(p => ({ ...p, importe_iva: e.target.value }))}
                  />
                </div>
                <div>
                  <label className="block text-xs font-medium text-gray-600 dark:text-gray-400 mb-1">Importe total</label>
                  <input
                    className={inputClass}
                    inputMode="decimal"
                    placeholder="0.00"
                    value={form.importe_total}
                    onChange={e => setForm(p => ({ ...p, importe_total: e.target.value }))}
                  />
                </div>
              </div>
              <div className="flex gap-2">
                <button
                  onClick={crearComprobante}
                  disabled={creando}
                  className="px-4 py-2 rounded-lg bg-ml-blue text-white text-sm font-medium hover:opacity-90 disabled:opacity-50"
                >
                  {creando ? 'Creando…' : 'Crear borrador'}
                </button>
                <button
                  onClick={() => setShowForm(false)}
                  className="px-4 py-2 rounded-lg border border-gray-300 dark:border-white/10 text-sm text-gray-700 dark:text-gray-300"
                >
                  Cancelar
                </button>
              </div>
            </div>
          )}

          <div className="rounded-xl border border-gray-200 dark:border-white/10 overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-xs text-gray-500 dark:text-gray-400 border-b border-gray-200 dark:border-white/10">
                  <th className="px-3 py-2 font-medium">Tipo</th>
                  <th className="px-3 py-2 font-medium">Cliente</th>
                  <th className="px-3 py-2 font-medium">N°</th>
                  <th className="px-3 py-2 font-medium text-right">Total</th>
                  <th className="px-3 py-2 font-medium">CAE</th>
                  <th className="px-3 py-2 font-medium">Estado</th>
                  <th className="px-3 py-2 font-medium"></th>
                </tr>
              </thead>
              <tbody>
                {loadingList && (
                  <tr><td colSpan={7} className="px-3 py-6 text-center text-gray-400">Cargando…</td></tr>
                )}
                {!loadingList && comprobantes.length === 0 && (
                  <tr><td colSpan={7} className="px-3 py-6 text-center text-gray-400">Sin comprobantes.</td></tr>
                )}
                {!loadingList && comprobantes.map((c, i) => (
                  <tr key={c.id} className={`border-b border-gray-100 dark:border-white/5 ${i % 2 ? 'bg-gray-50/50 dark:bg-white/[0.02]' : ''}`}>
                    <td className="px-3 py-2 text-gray-900 dark:text-gray-100 whitespace-nowrap">{TIPOS_COMPROBANTE[c.tipo_comprobante] || c.tipo_comprobante}</td>
                    <td className="px-3 py-2 text-gray-700 dark:text-gray-300 whitespace-nowrap">{c.cliente_nombre || '—'}</td>
                    <td className="px-3 py-2 text-gray-700 dark:text-gray-300 whitespace-nowrap">{c.numero ?? '—'}</td>
                    <td className="px-3 py-2 text-right text-gray-900 dark:text-gray-100 whitespace-nowrap">{fmt(c.importe_total)}</td>
                    <td className="px-3 py-2 text-gray-500 dark:text-gray-400 whitespace-nowrap">{c.cae || '—'}</td>
                    <td className="px-3 py-2">
                      <span className={`px-2 py-0.5 rounded-md text-xs font-semibold ${ESTADO_BADGE[c.estado] || ''}`}>
                        {c.estado}
                      </span>
                      {c.error_detalle && (
                        <div className="text-xs text-red-500 dark:text-red-400 mt-0.5 max-w-xs truncate" title={c.error_detalle}>
                          {c.error_detalle}
                        </div>
                      )}
                    </td>
                    <td className="px-3 py-2">
                      {canManageFinance && c.estado !== 'emitido' && (
                        <button
                          onClick={() => emitir(c)}
                          disabled={emitiendoId === c.id}
                          className="inline-flex items-center gap-1 px-3 py-1.5 rounded-lg bg-ml-blue text-white text-xs font-medium hover:opacity-90 disabled:opacity-50"
                        >
                          <IconSend />
                          {emitiendoId === c.id ? 'Emitiendo…' : 'Emitir'}
                        </button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="flex items-center justify-between text-sm text-gray-500 dark:text-gray-400">
            <span>{total} comprobante{total === 1 ? '' : 's'}</span>
            <div className="flex gap-2">
              <button
                onClick={() => setOffset(o => Math.max(0, o - LIMIT))}
                disabled={offset === 0}
                className="px-3 py-1.5 rounded-lg border border-gray-300 dark:border-white/10 disabled:opacity-40"
              >
                Anterior
              </button>
              <button
                onClick={() => setOffset(o => o + LIMIT)}
                disabled={offset + LIMIT >= total}
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
          {configLoading && <div className="text-sm text-gray-500 dark:text-gray-400">Cargando configuración…</div>}

          {!configLoading && (
            <>
              <div className="rounded-xl border border-gray-200 dark:border-white/10 bg-white dark:bg-white/5 p-4 space-y-3">
                <h2 className="text-sm font-semibold text-gray-800 dark:text-gray-200">Datos de la organización</h2>
                <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                  <div>
                    <label className="block text-xs font-medium text-gray-600 dark:text-gray-400 mb-1">CUIT (11 dígitos)</label>
                    <input
                      className={inputClass}
                      placeholder="20123456789"
                      value={cuit}
                      onChange={e => setCuit(e.target.value.replace(/\D/g, '').slice(0, 11))}
                    />
                  </div>
                  <div>
                    <label className="block text-xs font-medium text-gray-600 dark:text-gray-400 mb-1">Ambiente</label>
                    <select className={inputClass} value={ambiente} onChange={e => setAmbiente(e.target.value as 'homologacion' | 'produccion')}>
                      <option value="homologacion">Homologación (testing)</option>
                      <option value="produccion">Producción</option>
                    </select>
                  </div>
                  <div>
                    <label className="block text-xs font-medium text-gray-600 dark:text-gray-400 mb-1">Punto de venta</label>
                    <input
                      className={inputClass}
                      type="number"
                      min={1}
                      value={puntoVenta}
                      onChange={e => setPuntoVenta(Number(e.target.value) || 1)}
                    />
                  </div>
                </div>
                <label className="flex items-center gap-2 text-sm text-gray-700 dark:text-gray-300">
                  <input type="checkbox" checked={activo} onChange={e => setActivo(e.target.checked)} />
                  Activar facturación electrónica para esta organización
                  {!config?.tiene_certificado && (
                    <span className="text-xs text-amber-600 dark:text-amber-400">(necesita certificado cargado)</span>
                  )}
                </label>
                <button
                  onClick={guardarConfig}
                  disabled={savingConfig}
                  className="px-4 py-2 rounded-lg bg-ml-blue text-white text-sm font-medium hover:opacity-90 disabled:opacity-50"
                >
                  {savingConfig ? 'Guardando…' : 'Guardar configuración'}
                </button>
              </div>

              <div className="rounded-xl border border-gray-200 dark:border-white/10 bg-white dark:bg-white/5 p-4 space-y-3">
                <h2 className="text-sm font-semibold text-gray-800 dark:text-gray-200">Certificado digital</h2>
                <p className="text-xs text-gray-500 dark:text-gray-400">
                  El certificado y la clave privada (par PEM emitido por ARCA) se cifran antes de guardarse
                  y nunca se devuelven por la API. Subí un certificado nuevo para reemplazar el actual.
                </p>
                <div className="text-sm">
                  Estado: {config?.tiene_certificado
                    ? <span className="text-green-600 dark:text-green-400 font-medium">cargado{config.certificado_subido_en ? ` (${fmtDate(config.certificado_subido_en)})` : ''}</span>
                    : <span className="text-gray-500 dark:text-gray-400">sin certificado</span>}
                </div>
                <div>
                  <label className="block text-xs font-medium text-gray-600 dark:text-gray-400 mb-1">Certificado (.crt, formato PEM)</label>
                  <textarea
                    className={`${inputClass} font-mono text-xs`}
                    rows={4}
                    placeholder="-----BEGIN CERTIFICATE-----"
                    value={certPem}
                    onChange={e => setCertPem(e.target.value)}
                  />
                </div>
                <div>
                  <label className="block text-xs font-medium text-gray-600 dark:text-gray-400 mb-1">Clave privada (.key, formato PEM)</label>
                  <textarea
                    className={`${inputClass} font-mono text-xs`}
                    rows={4}
                    placeholder="-----BEGIN PRIVATE KEY-----"
                    value={keyPem}
                    onChange={e => setKeyPem(e.target.value)}
                  />
                </div>
                <div className="flex gap-2">
                  <button
                    onClick={subirCertificado}
                    disabled={savingCert}
                    className="px-4 py-2 rounded-lg bg-ml-blue text-white text-sm font-medium hover:opacity-90 disabled:opacity-50"
                  >
                    {savingCert ? 'Subiendo…' : 'Subir / reemplazar certificado'}
                  </button>
                  {config?.tiene_certificado && (
                    <button
                      onClick={borrarCertificado}
                      disabled={savingCert}
                      className="px-4 py-2 rounded-lg border border-red-300 dark:border-red-500/30 text-red-700 dark:text-red-300 text-sm font-medium hover:bg-red-50 dark:hover:bg-red-500/10 disabled:opacity-50"
                    >
                      Borrar certificado
                    </button>
                  )}
                </div>
              </div>
            </>
          )}
        </div>
      )}
    </div>
  )
}

export default Arca
