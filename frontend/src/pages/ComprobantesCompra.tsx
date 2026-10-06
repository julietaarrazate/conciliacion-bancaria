import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { apiClient } from '@/services/api'
import { useOrgStore } from '@/store/org'
import { useAuthStore } from '@/store/auth'
import { confirmDialog } from '@/store/confirm'
import { toast } from '@/store/toast'
import { parseMonto } from '@/utils/monto'
import { fmtFechaCorta, hoyIso } from '@/utils/fecha'
import type {
  BorradorComprobante,
  BuzonComprobantes,
  DatosComprobanteCompra,
  EstadoBorradorComprobante,
} from '@/types'

// ── Helpers ─────────────────────────────────────────────────────────────────
const fmt = (n: number | null | undefined) =>
  new Intl.NumberFormat('es-AR', { style: 'currency', currency: 'ARS', minimumFractionDigits: 2 }).format(n || 0)

const errMsg = (e: unknown, fallback: string) =>
  (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail || fallback

const TIPOS: { value: number; label: string }[] = [
  { value: 1, label: 'Factura A' }, { value: 6, label: 'Factura B' }, { value: 11, label: 'Factura C' },
  { value: 51, label: 'Factura M' },
  { value: 3, label: 'Nota de Crédito A' }, { value: 8, label: 'Nota de Crédito B' }, { value: 13, label: 'Nota de Crédito C' },
  { value: 2, label: 'Nota de Débito A' }, { value: 7, label: 'Nota de Débito B' }, { value: 12, label: 'Nota de Débito C' },
  { value: 201, label: 'FCE MiPyME A' }, { value: 206, label: 'FCE MiPyME B' }, { value: 211, label: 'FCE MiPyME C' },
]
const TIPOS_NC = new Set([3, 8, 13, 53, 203, 208, 213])
const ALICUOTAS = ['21%', '10.5%', '27%', '5%', '2.5%', '0%']
const TASA: Record<string, number> = { '21%': 0.21, '10.5%': 0.105, '27%': 0.27, '5%': 0.05, '2.5%': 0.025, '0%': 0 }

const ESTADO_LABEL: Record<EstadoBorradorComprobante, string> = {
  procesando: 'Leyendo…',
  listo: 'Para revisar',
  error: 'No se pudo leer',
  sin_adjunto: 'Mail sin adjunto',
  confirmado: 'Confirmado',
  descartado: 'Descartado',
}
const ESTADO_BADGE: Record<EstadoBorradorComprobante, string> = {
  procesando: 'bg-blue-100 text-blue-700 dark:bg-blue-500/15 dark:text-blue-300',
  listo: 'bg-amber-100 text-amber-700 dark:bg-amber-500/15 dark:text-amber-300',
  error: 'bg-red-100 text-red-700 dark:bg-red-500/15 dark:text-red-300',
  sin_adjunto: 'bg-gray-100 text-gray-600 dark:bg-white/10 dark:text-gray-300',
  confirmado: 'bg-green-100 text-green-700 dark:bg-green-500/15 dark:text-green-300',
  descartado: 'bg-gray-100 text-gray-500 dark:bg-white/10 dark:text-gray-400',
}

const inputClass =
  'w-full px-3 py-2 rounded-lg border bg-white dark:bg-white/5 border-gray-300 dark:border-white/10 text-gray-900 dark:text-gray-100 placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-ml-blue/40 text-sm'
const labelClass = 'block text-xs font-medium text-gray-600 dark:text-gray-400 mb-1'
const btnPrimary = 'inline-flex items-center justify-center gap-2 px-4 py-2 rounded-lg bg-ml-blue text-white text-sm font-medium hover:opacity-90 disabled:opacity-50'
const btnSecondary = 'inline-flex items-center justify-center gap-2 px-4 py-2 rounded-lg border border-gray-300 dark:border-white/10 text-sm text-gray-700 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-white/5 disabled:opacity-50'

type Tab = 'pendientes' | 'confirmado' | 'descartado'

// Formulario editable: todo como string para no pelear con los inputs.
interface FormState {
  tipo_codigo: string
  punto_venta: string
  numero: string
  fecha: string
  cuit_emisor: string
  razon_social: string
  alicuotas: { alicuota: string; neto: string; iva: string }[]
  neto_no_gravado: string
  exento: string
  percepciones_iva: string
  percepciones_iibb: string
  otros_tributos: string
  total: string
  periodo: string
  registrar_pago: boolean
  fecha_pago: string
}

const aStr = (v: string | number | null | undefined) => (v == null ? '' : String(v).replace('.', ','))

const formDesde = (d: DatosComprobanteCompra | null): FormState => {
  const ali = Object.entries(d?.alicuotas || {}).map(([alicuota, v]) => ({ alicuota, neto: aStr(v.neto), iva: aStr(v.iva) }))
  return {
    tipo_codigo: d?.tipo_codigo ? String(d.tipo_codigo) : '',
    punto_venta: d?.punto_venta ? String(d.punto_venta) : '',
    numero: d?.numero ? String(d.numero) : '',
    fecha: d?.fecha || '',
    cuit_emisor: d?.cuit_emisor || '',
    razon_social: d?.razon_social || '',
    alicuotas: ali.length ? ali : [{ alicuota: '21%', neto: '', iva: '' }],
    neto_no_gravado: aStr(d?.neto_no_gravado),
    exento: aStr(d?.exento),
    percepciones_iva: aStr(d?.percepciones_iva),
    percepciones_iibb: aStr(d?.percepciones_iibb),
    otros_tributos: aStr(d?.otros_tributos),
    total: aStr(d?.total),
    periodo: d?.fecha ? d.fecha.slice(0, 7) : hoyIso().slice(0, 7),
    registrar_pago: false,
    fecha_pago: hoyIso(),
  }
}

const n = (s: string) => parseMonto(s) ?? 0

// Data URL → blob URL: los navegadores bloquean PDFs en data: dentro de un iframe.
function useArchivoUrl(archivo: string | null | undefined): string | null {
  const [url, setUrl] = useState<string | null>(null)
  useEffect(() => {
    if (!archivo) { setUrl(null); return }
    if (!archivo.startsWith('data:')) { setUrl(archivo); return }
    let objectUrl: string | null = null
    try {
      const [header, data] = archivo.split(',', 2)
      const mime = header.slice(5).split(';')[0]
      const bin = atob(data)
      const bytes = new Uint8Array(bin.length)
      for (let i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i)
      objectUrl = URL.createObjectURL(new Blob([bytes], { type: mime }))
      setUrl(objectUrl)
    } catch {
      setUrl(null)
    }
    return () => { if (objectUrl) URL.revokeObjectURL(objectUrl) }
  }, [archivo])
  return url
}

// ── Revisión de un comprobante ─────────────────────────────────────────────
const Revision: React.FC<{
  borradorId: number
  orgId?: number
  onCerrar: () => void
  onCambio: () => void
}> = ({ borradorId, orgId, onCerrar, onCambio }) => {
  const { hasPermission } = useAuthStore()
  const [b, setB] = useState<BorradorComprobante | null>(null)
  const [form, setForm] = useState<FormState | null>(null)
  const [guardando, setGuardando] = useState(false)
  const url = useArchivoUrl(b?.archivo)

  useEffect(() => {
    apiClient.getBorradorComprobante(borradorId, orgId)
      .then(data => { setB(data); setForm(formDesde(data.datos)) })
      .catch(e => { toast.error(errMsg(e, 'No se pudo abrir el comprobante.')); onCerrar() })
  }, [borradorId, orgId, onCerrar])

  const sumas = useMemo(() => {
    if (!form) return { suma: 0, total: 0, cierra: true }
    const ali = form.alicuotas.reduce((acc, a) => acc + n(a.neto) + n(a.iva), 0)
    const otros = n(form.neto_no_gravado) + n(form.exento) + n(form.percepciones_iva) +
      n(form.percepciones_iibb) + n(form.otros_tributos)
    const suma = Math.round((ali + otros) * 100) / 100
    const total = n(form.total)
    return { suma, total, cierra: Math.abs(suma - total) <= 0.1 }
  }, [form])

  if (!b || !form) {
    return <div className="p-6 text-sm text-gray-500 dark:text-gray-400">Abriendo comprobante…</div>
  }

  const editable = b.estado === 'listo' || b.estado === 'error'
  const canConfirm = hasPermission('manage_finance') && editable
  const canEditar = hasPermission('upload_files')
  const set = (k: keyof FormState, v: string | boolean) => setForm(f => (f ? { ...f, [k]: v } : f))
  const setAli = (i: number, k: 'alicuota' | 'neto' | 'iva', v: string) =>
    setForm(f => {
      if (!f) return f
      const alicuotas = f.alicuotas.map((a, j) => {
        if (j !== i) return a
        const nuevo = { ...a, [k]: v }
        // Al cargar el neto, proponer el IVA si estaba vacío.
        if (k === 'neto' && !a.iva && TASA[a.alicuota] !== undefined) {
          const iva = Math.round(n(v) * TASA[a.alicuota] * 100) / 100
          nuevo.iva = iva ? String(iva).replace('.', ',') : ''
        }
        return nuevo
      })
      return { ...f, alicuotas }
    })

  const confirmar = async () => {
    const montos = (s: string) => (s.trim() ? parseMonto(s) : null)
    const datos = {
      tipo_codigo: form.tipo_codigo ? Number(form.tipo_codigo) : null,
      punto_venta: form.punto_venta || null,
      numero: form.numero || null,
      fecha: form.fecha || null,
      cuit_emisor: form.cuit_emisor || null,
      razon_social: form.razon_social || null,
      cae: b.datos?.cae || null,
      alicuotas: form.alicuotas
        .filter(a => a.neto.trim() || a.iva.trim())
        .map(a => ({ alicuota: a.alicuota, neto: montos(a.neto), iva: montos(a.iva) })),
      neto_no_gravado: montos(form.neto_no_gravado),
      exento: montos(form.exento),
      percepciones_iva: montos(form.percepciones_iva),
      percepciones_iibb: montos(form.percepciones_iibb),
      otros_tributos: montos(form.otros_tributos),
      total: montos(form.total),
    }
    if (!sumas.cierra) {
      const ok = await confirmDialog({
        title: 'La suma no cierra',
        message: `Neto + IVA + otros da ${fmt(sumas.suma)} y el total es ${fmt(sumas.total)}. ¿Confirmar igual?`,
        confirmLabel: 'Confirmar igual',
      })
      if (!ok) return
    }
    setGuardando(true)
    try {
      const r = await apiClient.confirmarBorradorComprobante(b.id, {
        datos,
        periodo: form.periodo || undefined,
        registrar_pago: form.registrar_pago,
        fecha_pago: form.registrar_pago ? form.fecha_pago : undefined,
      }, orgId)
      const extra = r.egreso_id ? ' y el pago quedó cargado en Pagos' : ''
      toast.success(`Listo: cargado en IVA (${r.periodo})${extra}.`)
      if (r.contabilidad_ok === false) toast.warn('El pago se guardó, pero el asiento contable falló. Revisalo en Contabilidad.')
      onCambio()
      onCerrar()
    } catch (e) {
      toast.error(errMsg(e, 'No se pudo confirmar.'))
    } finally {
      setGuardando(false)
    }
  }

  const descartar = async () => {
    const ok = await confirmDialog({ title: 'Descartar comprobante', message: 'No se va a cargar en IVA ni en Pagos.', confirmLabel: 'Descartar', danger: true })
    if (!ok) return
    try {
      await apiClient.descartarBorradorComprobante(b.id, orgId)
      onCambio()
      onCerrar()
    } catch (e) {
      toast.error(errMsg(e, 'No se pudo descartar.'))
    }
  }

  const releer = async () => {
    try {
      await apiClient.reprocesarBorradorComprobante(b.id, orgId)
      toast.info('Leyendo de nuevo con IA…')
      onCambio()
      onCerrar()
    } catch (e) {
      toast.error(errMsg(e, 'No se pudo volver a leer.'))
    }
  }

  const esNC = TIPOS_NC.has(Number(form.tipo_codigo))
  const campo = (k: keyof FormState, label: string, props: React.InputHTMLAttributes<HTMLInputElement> = {}) => (
    <div>
      <label className={labelClass}>{label}</label>
      <input className={inputClass} value={form[k] as string} disabled={!editable}
        onChange={e => set(k, e.target.value)} {...props} />
    </div>
  )

  return (
    <div className="fixed inset-0 z-50 bg-black/50 flex items-stretch md:items-center justify-center md:p-4" role="dialog" aria-modal="true">
      <div className="bg-white dark:bg-[#111116] w-full md:max-w-6xl md:rounded-xl overflow-hidden flex flex-col max-h-full md:max-h-[92vh] border border-gray-200 dark:border-white/10">
        <div className="flex items-center justify-between px-4 py-3 border-b border-gray-200 dark:border-white/10">
          <div className="min-w-0">
            <div className="text-sm font-semibold text-gray-900 dark:text-gray-100 truncate">{b.archivo_nombre || b.asunto || 'Comprobante'}</div>
            <div className="text-xs text-gray-500 dark:text-gray-400 truncate">
              {b.origen === 'email' ? `Por mail${b.remitente ? ` de ${b.remitente}` : ''}` : 'Subido a mano'} · {ESTADO_LABEL[b.estado]}
            </div>
          </div>
          <button onClick={onCerrar} className="p-2 rounded-lg text-gray-500 hover:bg-gray-100 dark:hover:bg-white/10" aria-label="Cerrar">✕</button>
        </div>

        <div className="flex-1 overflow-auto grid grid-cols-1 lg:grid-cols-2">
          {/* Archivo original */}
          <div className="bg-gray-50 dark:bg-black/30 min-h-[320px] lg:min-h-0 border-b lg:border-b-0 lg:border-r border-gray-200 dark:border-white/10">
            {url && (b.archivo_mime || '').startsWith('image/') && (
              <img src={url} alt="Comprobante" className="w-full h-full object-contain max-h-[80vh]" />
            )}
            {url && b.archivo_mime === 'application/pdf' && (
              <iframe src={url} title="Comprobante" className="w-full h-[60vh] lg:h-full min-h-[480px]" />
            )}
            {!url && <div className="p-6 text-sm text-gray-500 dark:text-gray-400">No hay archivo para mostrar.</div>}
          </div>

          {/* Datos */}
          <div className="p-4 space-y-4">
            {b.error && (
              <div className="px-3 py-2 rounded-lg text-sm bg-red-50 text-red-700 dark:bg-red-500/10 dark:text-red-300">{b.error}</div>
            )}
            {b.alertas.length > 0 && (
              <ul className="px-3 py-2 rounded-lg text-sm bg-amber-50 text-amber-800 dark:bg-amber-500/10 dark:text-amber-200 space-y-1 list-disc list-inside">
                {b.alertas.map((a, i) => <li key={i}>{a}</li>)}
              </ul>
            )}

            <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
              <div className="col-span-2 sm:col-span-1">
                <label className={labelClass}>Tipo</label>
                <select className={inputClass} value={form.tipo_codigo} disabled={!editable} onChange={e => set('tipo_codigo', e.target.value)}>
                  <option value="">Elegir…</option>
                  {TIPOS.map(t => <option key={t.value} value={t.value}>{t.label}</option>)}
                </select>
              </div>
              {campo('punto_venta', 'Punto de venta', { inputMode: 'numeric' })}
              {campo('numero', 'Número', { inputMode: 'numeric' })}
              {campo('fecha', 'Fecha', { type: 'date' })}
              {campo('cuit_emisor', 'CUIT proveedor', { inputMode: 'numeric', placeholder: '30-12345678-9' })}
              {campo('razon_social', 'Proveedor')}
            </div>

            <div>
              <div className="flex items-center justify-between mb-1">
                <span className="text-xs font-medium text-gray-600 dark:text-gray-400">Neto gravado e IVA por alícuota</span>
                {editable && (
                  <button className="text-xs text-ml-blue dark:text-blue-300 hover:underline"
                    onClick={() => setForm(f => (f ? { ...f, alicuotas: [...f.alicuotas, { alicuota: '10.5%', neto: '', iva: '' }] } : f))}>
                    + Agregar alícuota
                  </button>
                )}
              </div>
              <div className="space-y-2">
                {form.alicuotas.map((a, i) => (
                  <div key={i} className="grid grid-cols-[90px_1fr_1fr_auto] gap-2 items-center">
                    <select className={inputClass} value={a.alicuota} disabled={!editable} onChange={e => setAli(i, 'alicuota', e.target.value)}>
                      {ALICUOTAS.map(x => <option key={x} value={x}>{x}</option>)}
                    </select>
                    <input className={inputClass} inputMode="decimal" placeholder="Neto" value={a.neto} disabled={!editable} onChange={e => setAli(i, 'neto', e.target.value)} />
                    <input className={inputClass} inputMode="decimal" placeholder="IVA" value={a.iva} disabled={!editable} onChange={e => setAli(i, 'iva', e.target.value)} />
                    {editable ? (
                      <button className="p-2 text-gray-400 hover:text-red-500" aria-label="Quitar alícuota"
                        onClick={() => setForm(f => (f ? { ...f, alicuotas: f.alicuotas.filter((_, j) => j !== i) } : f))}>✕</button>
                    ) : <span />}
                  </div>
                ))}
              </div>
            </div>

            <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
              {campo('neto_no_gravado', 'No gravado', { inputMode: 'decimal' })}
              {campo('exento', 'Exento', { inputMode: 'decimal' })}
              {campo('percepciones_iva', 'Percepciones IVA', { inputMode: 'decimal' })}
              {campo('percepciones_iibb', 'Percepciones IIBB', { inputMode: 'decimal' })}
              {campo('otros_tributos', 'Otros tributos', { inputMode: 'decimal' })}
              {campo('total', 'Total', { inputMode: 'decimal' })}
            </div>

            <div className={`px-3 py-2 rounded-lg text-sm ${sumas.cierra
              ? 'bg-green-50 text-green-700 dark:bg-green-500/10 dark:text-green-300'
              : 'bg-red-50 text-red-700 dark:bg-red-500/10 dark:text-red-300'}`}>
              {sumas.cierra ? `Cierra: la suma da ${fmt(sumas.suma)}.` : `No cierra: la suma da ${fmt(sumas.suma)} y el total es ${fmt(sumas.total)}.`}
            </div>

            {editable && (
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 pt-2 border-t border-gray-200 dark:border-white/10">
                <div>
                  <label className={labelClass}>Período de IVA</label>
                  <input className={inputClass} type="month" value={form.periodo} onChange={e => set('periodo', e.target.value)} />
                </div>
                <div className="flex flex-col justify-end gap-2">
                  <label className={`flex items-center gap-2 text-sm text-gray-700 dark:text-gray-300 ${esNC ? 'opacity-50' : ''}`}>
                    <input type="checkbox" checked={form.registrar_pago && !esNC} disabled={esNC}
                      onChange={e => set('registrar_pago', e.target.checked)} />
                    Ya está pagada: cargar el pago en Pagos
                  </label>
                  {form.registrar_pago && !esNC && (
                    <input className={inputClass} type="date" value={form.fecha_pago} onChange={e => set('fecha_pago', e.target.value)} aria-label="Fecha de pago" />
                  )}
                </div>
              </div>
            )}

            {b.estado === 'confirmado' && (
              <p className="text-sm text-gray-600 dark:text-gray-300">
                Ya está cargado en IVA{b.egreso_id ? ' y en Pagos' : ''}. Si hay que sacarlo, borralo desde IVA.
              </p>
            )}
          </div>
        </div>

        {editable && (
          <div className="flex flex-col-reverse sm:flex-row sm:justify-between gap-2 px-4 py-3 border-t border-gray-200 dark:border-white/10">
            <div className="flex gap-2">
              {canEditar && <button className={btnSecondary} onClick={descartar}>Descartar</button>}
              {canEditar && <button className={btnSecondary} onClick={releer}>Volver a leer</button>}
            </div>
            {canConfirm && (
              <button className={btnPrimary} onClick={confirmar} disabled={guardando}>
                {guardando ? 'Confirmando…' : 'Confirmar'}
              </button>
            )}
          </div>
        )}
      </div>
    </div>
  )
}

// ── Página ─────────────────────────────────────────────────────────────────
export const ComprobantesCompra: React.FC = () => {
  const { activeOrgId } = useOrgStore()
  const { hasPermission } = useAuthStore()
  const orgId = activeOrgId || undefined
  const canUpload = hasPermission('upload_files')
  const isAdmin = hasPermission('admin_accounting')

  const [tab, setTab] = useState<Tab>('pendientes')
  const [items, setItems] = useState<BorradorComprobante[]>([])
  const [conteo, setConteo] = useState<Partial<Record<EstadoBorradorComprobante, number>>>({})
  const [buzon, setBuzon] = useState<BuzonComprobantes | null>(null)
  const [loading, setLoading] = useState(true)
  const [subiendo, setSubiendo] = useState(false)
  const [abierto, setAbierto] = useState<number | null>(null)
  const fileRef = useRef<HTMLInputElement>(null)

  const cargar = useCallback(async () => {
    try {
      const data = await apiClient.getBorradoresComprobante(tab, orgId)
      setItems(data.items)
      setConteo(data.conteo)
    } catch (e) {
      toast.error(errMsg(e, 'No se pudieron cargar los comprobantes.'))
    } finally {
      setLoading(false)
    }
  }, [tab, orgId])

  useEffect(() => { setLoading(true); cargar() }, [cargar])
  useEffect(() => {
    apiClient.getBuzonComprobantes(orgId).then(setBuzon).catch(() => setBuzon(null))
  }, [orgId])

  // Mientras la IA lee, refrescar solo.
  const hayProcesando = items.some(i => i.estado === 'procesando')
  useEffect(() => {
    if (!hayProcesando) return
    const t = setInterval(cargar, 3000)
    return () => clearInterval(t)
  }, [hayProcesando, cargar])

  const subir = async (lista: FileList | null) => {
    if (!lista || !lista.length) return
    const files = Array.from(lista)
    if (files.length > 10) { toast.error('Podés subir hasta 10 archivos a la vez.'); return }
    setSubiendo(true)
    try {
      await apiClient.subirComprobantesCompra(files, orgId)
      toast.success(files.length === 1 ? 'Subido. La IA lo está leyendo.' : `Subidos ${files.length}. La IA los está leyendo.`)
      setTab('pendientes')
      await cargar()
    } catch (e) {
      toast.error(errMsg(e, 'No se pudieron subir los archivos.'))
    } finally {
      setSubiendo(false)
      if (fileRef.current) fileRef.current.value = ''
    }
  }

  const activarBuzon = async (regenerar: boolean) => {
    if (regenerar) {
      const ok = await confirmDialog({
        title: 'Generar otra dirección',
        message: 'La dirección actual deja de funcionar. Vas a tener que avisarle al cliente o cambiar el reenvío de Gmail.',
        confirmLabel: 'Generar otra',
        danger: true,
      })
      if (!ok) return
    }
    try {
      setBuzon(await apiClient.activarBuzonComprobantes(regenerar, orgId))
    } catch (e) {
      toast.error(errMsg(e, 'No se pudo activar la dirección.'))
    }
  }

  const copiar = async () => {
    if (!buzon?.direccion) return
    try {
      await navigator.clipboard.writeText(buzon.direccion)
      toast.success('Dirección copiada.')
    } catch {
      toast.error('No se pudo copiar. Seleccionala y copiala a mano.')
    }
  }

  const descartarSinAdjunto = async (id: number) => {
    try {
      await apiClient.descartarBorradorComprobante(id, orgId)
      await cargar()
    } catch (e) {
      toast.error(errMsg(e, 'No se pudo descartar.'))
    }
  }

  const pendientes = (conteo.procesando || 0) + (conteo.listo || 0) + (conteo.error || 0) + (conteo.sin_adjunto || 0)
  const tabs: [Tab, string, number | undefined][] = [
    ['pendientes', 'Por revisar', pendientes],
    ['confirmado', 'Confirmados', conteo.confirmado],
    ['descartado', 'Descartados', conteo.descartado],
  ]

  const cerrar = useCallback(() => setAbierto(null), [])

  return (
    <div className="p-4 md:p-6 max-w-6xl mx-auto">
      <h1 className="text-xl md:text-2xl font-semibold text-gray-900 dark:text-gray-100 mb-1">Comprobantes por revisar</h1>
      <p className="text-sm text-gray-500 dark:text-gray-400 mb-4">
        Facturas de proveedores que llegan por mail o se suben acá. La IA completa los datos; nada entra a IVA ni a Pagos hasta que alguien lo confirma.
      </p>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-6">
        {/* Mail */}
        <div className="rounded-xl border border-gray-200 dark:border-white/10 bg-white dark:bg-white/5 p-4">
          <div className="text-sm font-semibold text-gray-900 dark:text-gray-100 mb-1">Recibir por mail</div>
          {buzon?.direccion ? (
            <>
              <p className="text-xs text-gray-500 dark:text-gray-400 mb-2">
                Reenviá las facturas a esta dirección, o armá un filtro en Gmail para que se reenvíen solas.
              </p>
              <div className="flex gap-2">
                <code className="flex-1 min-w-0 truncate px-3 py-2 rounded-lg bg-gray-50 dark:bg-black/30 border border-gray-200 dark:border-white/10 text-sm text-gray-900 dark:text-gray-100">
                  {buzon.direccion}
                </code>
                <button className={btnSecondary} onClick={copiar}>Copiar</button>
              </div>
              {isAdmin && (
                <button className="mt-2 text-xs text-gray-500 dark:text-gray-400 hover:underline" onClick={() => activarBuzon(true)}>
                  Generar otra dirección
                </button>
              )}
            </>
          ) : buzon?.configurado ? (
            <>
              <p className="text-xs text-gray-500 dark:text-gray-400 mb-3">
                Creá una dirección propia para esta empresa. Lo que llegue ahí aparece abajo para revisar.
              </p>
              {isAdmin
                ? <button className={btnPrimary} onClick={() => activarBuzon(false)}>Crear dirección de mail</button>
                : <p className="text-xs text-gray-500 dark:text-gray-400">Pedile a un administrador que la active.</p>}
            </>
          ) : (
            <p className="text-xs text-gray-500 dark:text-gray-400">
              La recepción por mail todavía no está configurada. Mientras tanto podés subir los archivos acá al lado.
            </p>
          )}
        </div>

        {/* Subida */}
        <div className="rounded-xl border border-dashed border-gray-300 dark:border-white/15 bg-white dark:bg-white/5 p-4 flex flex-col justify-between">
          <div>
            <div className="text-sm font-semibold text-gray-900 dark:text-gray-100 mb-1">Subir facturas</div>
            <p className="text-xs text-gray-500 dark:text-gray-400 mb-3">PDF o foto (JPG, PNG, WebP), hasta 10 a la vez y 5 MB cada una.</p>
          </div>
          {canUpload ? (
            <>
              <input ref={fileRef} type="file" multiple accept="application/pdf,image/jpeg,image/png,image/webp"
                className="hidden" onChange={e => subir(e.target.files)} />
              <button className={btnPrimary} disabled={subiendo} onClick={() => fileRef.current?.click()}>
                {subiendo ? 'Subiendo…' : 'Elegir archivos'}
              </button>
            </>
          ) : <p className="text-xs text-gray-500 dark:text-gray-400">Tu usuario no puede subir archivos.</p>}
        </div>
      </div>

      {/* Tabs */}
      <div className="flex gap-1 mb-4 border-b border-gray-200 dark:border-white/10 overflow-x-auto">
        {tabs.map(([k, label, c]) => (
          <button key={k} onClick={() => setTab(k)}
            className={`px-4 py-2 text-sm font-medium -mb-px border-b-2 whitespace-nowrap transition-colors ${tab === k
              ? 'border-ml-blue text-ml-blue dark:text-blue-300'
              : 'border-transparent text-gray-500 dark:text-gray-400 hover:text-gray-800 dark:hover:text-gray-200'}`}>
            {label}{c ? ` (${c})` : ''}
          </button>
        ))}
      </div>

      {loading ? (
        <div className="text-sm text-gray-500 dark:text-gray-400">Cargando…</div>
      ) : items.length === 0 ? (
        <div className="rounded-xl border border-gray-200 dark:border-white/10 p-8 text-center text-sm text-gray-500 dark:text-gray-400">
          {tab === 'pendientes' ? 'No hay comprobantes para revisar.' : 'Todavía no hay nada acá.'}
        </div>
      ) : (
        <div className="rounded-xl border border-gray-200 dark:border-white/10 divide-y divide-gray-200 dark:divide-white/10 bg-white dark:bg-white/5 overflow-hidden">
          {items.map(it => {
            const d = it.datos
            const titulo = it.estado === 'sin_adjunto'
              ? (it.asunto || 'Mail sin asunto')
              : (d?.razon_social || it.archivo_nombre || 'Comprobante')
            const sub = it.estado === 'sin_adjunto'
              ? `Llegó un mail sin factura adjunta${it.remitente ? ` de ${it.remitente}` : ''}.`
              : [
                d?.tipo_codigo ? TIPOS.find(t => t.value === d.tipo_codigo)?.label : null,
                d?.punto_venta && d?.numero ? `${String(d.punto_venta).padStart(5, '0')}-${String(d.numero).padStart(8, '0')}` : null,
                d?.fecha ? fmtFechaCorta(d.fecha) : null,
                it.origen === 'email' ? 'por mail' : null,
              ].filter(Boolean).join(' · ')
            const clickable = it.estado !== 'sin_adjunto' && it.estado !== 'procesando'
            return (
              <div key={it.id}
                className={`flex items-center gap-3 px-4 py-3 ${clickable ? 'cursor-pointer hover:bg-gray-50 dark:hover:bg-white/5' : ''}`}
                onClick={() => clickable && setAbierto(it.id)}>
                <div className="flex-1 min-w-0">
                  <div className="text-sm font-medium text-gray-900 dark:text-gray-100 truncate">{titulo}</div>
                  <div className="text-xs text-gray-500 dark:text-gray-400 truncate">{sub || it.archivo_nombre}</div>
                  {it.alertas.length > 0 && it.estado === 'listo' && (
                    <div className="text-xs text-amber-700 dark:text-amber-300 truncate">⚠ {it.alertas[0]}{it.alertas.length > 1 ? ` (+${it.alertas.length - 1})` : ''}</div>
                  )}
                </div>
                {d?.total && <div className="text-sm font-semibold text-gray-900 dark:text-gray-100 whitespace-nowrap">{fmt(Number(d.total))}</div>}
                <span className={`px-2 py-0.5 rounded-md text-xs font-semibold whitespace-nowrap ${ESTADO_BADGE[it.estado]}`}>{ESTADO_LABEL[it.estado]}</span>
                {it.estado === 'sin_adjunto' && canUpload && (
                  <button className="text-xs text-gray-500 dark:text-gray-400 hover:underline" onClick={() => descartarSinAdjunto(it.id)}>Descartar</button>
                )}
              </div>
            )
          })}
        </div>
      )}

      {abierto !== null && (
        <Revision borradorId={abierto} orgId={orgId} onCerrar={cerrar} onCambio={cargar} />
      )}
    </div>
  )
}

export default ComprobantesCompra
