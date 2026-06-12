import React, { useEffect, useMemo, useState, useCallback } from 'react'
import { apiClient } from '@/services/api'
import { confirmDialog } from '@/store/confirm'
import { useOrgStore } from '@/store/org'
import { useAuthStore } from '@/store/auth'
import { FileUpload } from '@/components/FileUpload'
import { hoyIso } from '@/utils/fecha'

// ── Helpers ─────────────────────────────────────────────────────────────────
const fmt = (n: number) =>
  new Intl.NumberFormat('es-AR', { style: 'currency', currency: 'ARS', minimumFractionDigits: 2 }).format(n || 0)

const fmtDate = (d?: string | null) =>
  d ? new Date(d + (d.includes('T') ? '' : 'T00:00:00')).toLocaleDateString('es-AR') : '—'

type Marca = 'visa' | 'mastercard' | 'amex'

interface LiqTarjeta {
  id: number
  organizacion_id: number
  marca: Marca
  periodo: string
  fecha_acreditacion: string
  monto_bruto: number
  aranceles: number
  iva_df: number
  percepciones_iibb: number
  retenciones: number
  neto: number
  estado: 'pendiente' | 'conciliada' | 'anulada'
  extracto_movimiento_id: number | null
  archivo_original: string | null
  asiento_id: number | null
  notas: string | null
  created_at: string
}

const MARCAS: { value: Marca; label: string }[] = [
  { value: 'visa', label: 'Visa' },
  { value: 'mastercard', label: 'Mastercard' },
  { value: 'amex', label: 'Amex' },
]

// Color por marca (dual-mode)
const MARCA_BADGE: Record<Marca, string> = {
  visa: 'bg-blue-100 text-blue-700 dark:bg-blue-500/15 dark:text-blue-300',
  mastercard: 'bg-orange-100 text-orange-700 dark:bg-orange-500/15 dark:text-orange-300',
  amex: 'bg-green-100 text-green-700 dark:bg-green-500/15 dark:text-green-300',
}

const ESTADO_BADGE: Record<string, string> = {
  pendiente: 'bg-amber-100 text-amber-700 dark:bg-amber-500/15 dark:text-amber-300',
  conciliada: 'bg-green-100 text-green-700 dark:bg-green-500/15 dark:text-green-300',
  anulada: 'bg-red-100 text-red-700 dark:bg-red-500/15 dark:text-red-300',
}

const inputClass =
  'w-full px-3 py-2 rounded-lg border bg-white dark:bg-white/5 border-gray-300 dark:border-white/10 text-gray-900 dark:text-gray-100 placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-ml-blue/40 text-sm'

// SVG icons (Heroicons)
const IconUpload = () => (
  <svg className="w-4 h-4" fill="none" stroke="currentColor" strokeWidth={1.8} viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5m-13.5-9L12 3m0 0l4.5 4.5M12 3v13.5" /></svg>
)
const IconLink = () => (
  <svg className="w-4 h-4" fill="none" stroke="currentColor" strokeWidth={1.8} viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" d="M13.19 8.688a4.5 4.5 0 011.242 7.244l-4.5 4.5a4.5 4.5 0 01-6.364-6.364l1.757-1.757m13.35-.622l1.757-1.757a4.5 4.5 0 00-6.364-6.364l-4.5 4.5a4.5 4.5 0 001.242 7.244" /></svg>
)
const IconTrash = () => (
  <svg className="w-4 h-4" fill="none" stroke="currentColor" strokeWidth={1.8} viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" d="M14.74 9l-.346 9m-4.788 0L9.26 9m9.968-3.21c.342.052.682.107 1.022.166m-1.022-.165L18.16 19.673a2.25 2.25 0 01-2.244 2.077H8.084a2.25 2.25 0 01-2.244-2.077L4.772 5.79m14.456 0a48.108 48.108 0 00-3.478-.397m-12 .562c.34-.059.68-.114 1.022-.165m0 0a48.11 48.11 0 013.478-.397m7.5 0v-.916c0-1.18-.91-2.164-2.09-2.201a51.964 51.964 0 00-3.32 0c-1.18.037-2.09 1.022-2.09 2.201v.916m7.5 0a48.667 48.667 0 00-7.5 0" /></svg>
)

interface FormState {
  marca: Marca
  periodo: string
  fecha_acreditacion: string
  monto_bruto: string
  aranceles: string
  iva_df: string
  percepciones_iibb: string
  retenciones: string
  archivo_original: string
  notas: string
}

const emptyForm = (): FormState => ({
  marca: 'visa',
  periodo: hoyIso().slice(0, 7),
  fecha_acreditacion: hoyIso(),
  monto_bruto: '',
  aranceles: '',
  iva_df: '',
  percepciones_iibb: '',
  retenciones: '',
  archivo_original: '',
  notas: '',
})

const num = (s: string) => {
  const v = parseFloat((s || '').toString().replace(',', '.'))
  return isNaN(v) ? 0 : v
}

export const Tarjetas: React.FC = () => {
  const { activeOrgId } = useOrgStore()
  const { hasPermission } = useAuthStore()
  const canDelete = hasPermission('delete_records')

  const [tab, setTab] = useState<'resumen' | 'cargar' | 'historial'>('resumen')
  const [items, setItems] = useState<LiqTarjeta[]>([])
  const [loading, setLoading] = useState(false)
  const [msg, setMsg] = useState<{ type: 'error' | 'ok'; text: string } | null>(null)

  // Form (tab Cargar)
  const [form, setForm] = useState<FormState>(emptyForm())
  const [saving, setSaving] = useState(false)
  const [parsing, setParsing] = useState(false)

  // Conciliar modal
  const [conciliarLiq, setConciliarLiq] = useState<LiqTarjeta | null>(null)
  const [extractos, setExtractos] = useState<any[]>([])
  const [extractoSel, setExtractoSel] = useState<number | null>(null)
  const [movimientos, setMovimientos] = useState<any[]>([])
  const [movSel, setMovSel] = useState<number | null>(null)

  const cargar = useCallback(async () => {
    setLoading(true)
    try {
      const data = await apiClient.listTarjetas({ orgId: activeOrgId || undefined, limit: 200 })
      setItems(data.items || [])
    } catch {
      setMsg({ type: 'error', text: 'No se pudieron cargar las liquidaciones.' })
    } finally {
      setLoading(false)
    }
  }, [activeOrgId])

  useEffect(() => { cargar() }, [cargar])

  // ── Resumen por marca ───────────────────────────────────────────────────
  const resumen = useMemo(() => {
    const base: Record<Marca, { bruto: number; aranceles: number; pendientes: number }> = {
      visa: { bruto: 0, aranceles: 0, pendientes: 0 },
      mastercard: { bruto: 0, aranceles: 0, pendientes: 0 },
      amex: { bruto: 0, aranceles: 0, pendientes: 0 },
    }
    for (const l of items) {
      const r = base[l.marca as Marca]
      if (!r) continue
      r.bruto += Number(l.monto_bruto) || 0
      r.aranceles += Number(l.aranceles) || 0
      if (l.estado === 'pendiente') r.pendientes += 1
    }
    return base
  }, [items])

  const netoPreview = useMemo(() => {
    const bruto = num(form.monto_bruto)
    const comp = num(form.aranceles) + num(form.iva_df) + num(form.percepciones_iibb) + num(form.retenciones)
    return Math.round((bruto - comp) * 100) / 100
  }, [form])

  // ── Upload + parse ──────────────────────────────────────────────────────
  const onFile = async (file: File) => {
    setParsing(true)
    setMsg(null)
    try {
      const data = await apiClient.uploadTarjeta(file, form.marca)
      setForm(f => ({
        ...f,
        periodo: data.periodo || f.periodo,
        fecha_acreditacion: data.fecha_acreditacion || f.fecha_acreditacion,
        monto_bruto: data.monto_bruto ? String(data.monto_bruto) : f.monto_bruto,
        aranceles: data.aranceles ? String(data.aranceles) : f.aranceles,
        iva_df: data.iva_df ? String(data.iva_df) : f.iva_df,
        percepciones_iibb: data.percepciones_iibb ? String(data.percepciones_iibb) : f.percepciones_iibb,
        retenciones: data.retenciones ? String(data.retenciones) : f.retenciones,
        archivo_original: data.archivo_original || file.name,
      }))
      const warns: string[] = data.parse_warnings || []
      setMsg(warns.length
        ? { type: 'error', text: 'Archivo leído. Revisá: ' + warns.join(' · ') }
        : { type: 'ok', text: 'Archivo leído. Verificá los campos y guardá.' })
    } catch {
      setMsg({ type: 'error', text: 'No se pudo leer el archivo. Cargá los datos manualmente.' })
      setForm(f => ({ ...f, archivo_original: file.name }))
    } finally {
      setParsing(false)
    }
  }

  // ── Guardar + generar asiento ───────────────────────────────────────────
  const guardar = async () => {
    const bruto = num(form.monto_bruto)
    if (bruto <= 0) { setMsg({ type: 'error', text: 'El monto bruto debe ser mayor a 0.' }); return }
    setSaving(true)
    setMsg(null)
    try {
      await apiClient.createTarjeta({
        marca: form.marca,
        periodo: form.periodo,
        fecha_acreditacion: form.fecha_acreditacion,
        monto_bruto: bruto,
        aranceles: num(form.aranceles),
        iva_df: num(form.iva_df),
        percepciones_iibb: num(form.percepciones_iibb),
        retenciones: num(form.retenciones),
        neto: netoPreview,
        archivo_original: form.archivo_original || null,
        notas: form.notas || null,
      }, activeOrgId || undefined)
      setMsg({ type: 'ok', text: 'Liquidación guardada y asiento generado.' })
      setForm(emptyForm())
      await cargar()
      setTab('historial')
    } catch (e: any) {
      const detail = e?.response?.data?.detail
      setMsg({ type: 'error', text: typeof detail === 'string' ? detail : 'No se pudo guardar la liquidación.' })
    } finally {
      setSaving(false)
    }
  }

  // ── Eliminar ────────────────────────────────────────────────────────────
  const eliminar = async (l: LiqTarjeta) => {
    const ok = await confirmDialog({
      title: 'Eliminar liquidación',
      message: `¿Eliminar la liquidación ${l.marca} ${l.periodo} (${fmt(Number(l.monto_bruto))})? Se reversa el asiento contable.`,
      confirmLabel: 'Eliminar',
      danger: true,
    })
    if (!ok) return
    try {
      await apiClient.deleteTarjeta(l.id)
      await cargar()
    } catch {
      setMsg({ type: 'error', text: 'No se pudo eliminar la liquidación.' })
    }
  }

  // ── Conciliar ───────────────────────────────────────────────────────────
  const abrirConciliar = async (l: LiqTarjeta) => {
    setConciliarLiq(l)
    setExtractoSel(null)
    setMovimientos([])
    setMovSel(null)
    try {
      const data = await apiClient.listExtractos(activeOrgId || undefined)
      setExtractos(data.items || [])
    } catch {
      setExtractos([])
    }
  }

  useEffect(() => {
    if (!extractoSel) { setMovimientos([]); return }
    apiClient.getMovimientos(extractoSel, { limit: 500 })
      .then(r => setMovimientos(r.items || []))
      .catch(() => setMovimientos([]))
  }, [extractoSel])

  const confirmarConciliar = async () => {
    if (!conciliarLiq || !movSel) return
    try {
      await apiClient.conciliarTarjeta(conciliarLiq.id, movSel)
      setConciliarLiq(null)
      await cargar()
    } catch {
      setMsg({ type: 'error', text: 'No se pudo conciliar.' })
    }
  }

  // ── Render ──────────────────────────────────────────────────────────────
  return (
    <div className="p-4 md:p-6 max-w-6xl mx-auto">
      <h1 className="text-xl md:text-2xl font-semibold text-gray-900 dark:text-gray-100 mb-1">Tarjetas</h1>
      <p className="text-sm text-gray-500 dark:text-gray-400 mb-4">Liquidaciones de Visa, Mastercard y Amex.</p>

      {/* Tabs */}
      <div className="flex gap-1 mb-4 border-b border-gray-200 dark:border-white/10">
        {([['resumen', 'Resumen'], ['cargar', 'Cargar'], ['historial', 'Historial']] as const).map(([k, label]) => (
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

      {/* ── Tab Resumen ── */}
      {tab === 'resumen' && (
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
          {MARCAS.map(({ value, label }) => {
            const r = resumen[value]
            return (
              <div key={value} className="rounded-xl border border-gray-200 dark:border-white/10 bg-white dark:bg-white/5 p-4 overflow-hidden">
                <div className="flex items-center justify-between mb-3">
                  <span className={`px-2 py-0.5 rounded-md text-xs font-semibold ${MARCA_BADGE[value]}`}>{label}</span>
                  <span className="text-xs text-gray-400">{r.pendientes} pend.</span>
                </div>
                <div className="space-y-2">
                  <div>
                    <div className="text-xs text-gray-500 dark:text-gray-400">Monto bruto total</div>
                    <div className="text-base font-semibold text-gray-900 dark:text-gray-100 truncate">{fmt(r.bruto)}</div>
                  </div>
                  <div>
                    <div className="text-xs text-gray-500 dark:text-gray-400">Aranceles acumulados</div>
                    <div className="text-sm font-medium text-gray-700 dark:text-gray-300 truncate">{fmt(r.aranceles)}</div>
                  </div>
                </div>
              </div>
            )
          })}
        </div>
      )}

      {/* ── Tab Cargar ── */}
      {tab === 'cargar' && (
        <div className="max-w-2xl space-y-4">
          <div className="flex flex-col sm:flex-row gap-3 sm:items-end">
            <div className="flex-1">
              <label className="block text-xs font-medium text-gray-600 dark:text-gray-400 mb-1">Marca</label>
              <select className={inputClass} value={form.marca} onChange={e => setForm(f => ({ ...f, marca: e.target.value as Marca }))}>
                {MARCAS.map(m => <option key={m.value} value={m.value}>{m.label}</option>)}
              </select>
            </div>
            <div className="flex-1">
              <FileUpload
                accept=".xlsx,.xls,.csv,.pdf"
                label={parsing ? 'Leyendo…' : 'Subir liquidación'}
                onFileSelected={onFile}
              />
            </div>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <div>
              <label className="block text-xs font-medium text-gray-600 dark:text-gray-400 mb-1">Período</label>
              <input className={inputClass} type="month" value={form.periodo} onChange={e => setForm(f => ({ ...f, periodo: e.target.value }))} />
            </div>
            <div>
              <label className="block text-xs font-medium text-gray-600 dark:text-gray-400 mb-1">Fecha acreditación</label>
              <input className={inputClass} type="date" value={form.fecha_acreditacion} onChange={e => setForm(f => ({ ...f, fecha_acreditacion: e.target.value }))} />
            </div>
            <div>
              <label className="block text-xs font-medium text-gray-600 dark:text-gray-400 mb-1">Monto bruto</label>
              <input className={inputClass} inputMode="decimal" placeholder="0.00" value={form.monto_bruto} onChange={e => setForm(f => ({ ...f, monto_bruto: e.target.value }))} />
            </div>
            <div>
              <label className="block text-xs font-medium text-gray-600 dark:text-gray-400 mb-1">Aranceles</label>
              <input className={inputClass} inputMode="decimal" placeholder="0.00" value={form.aranceles} onChange={e => setForm(f => ({ ...f, aranceles: e.target.value }))} />
            </div>
            <div>
              <label className="block text-xs font-medium text-gray-600 dark:text-gray-400 mb-1">IVA Crédito Fiscal</label>
              <input className={inputClass} inputMode="decimal" placeholder="0.00" value={form.iva_df} onChange={e => setForm(f => ({ ...f, iva_df: e.target.value }))} />
            </div>
            <div>
              <label className="block text-xs font-medium text-gray-600 dark:text-gray-400 mb-1">Percepciones IIBB</label>
              <input className={inputClass} inputMode="decimal" placeholder="0.00" value={form.percepciones_iibb} onChange={e => setForm(f => ({ ...f, percepciones_iibb: e.target.value }))} />
            </div>
            <div>
              <label className="block text-xs font-medium text-gray-600 dark:text-gray-400 mb-1">Retenciones</label>
              <input className={inputClass} inputMode="decimal" placeholder="0.00" value={form.retenciones} onChange={e => setForm(f => ({ ...f, retenciones: e.target.value }))} />
            </div>
            <div>
              <label className="block text-xs font-medium text-gray-600 dark:text-gray-400 mb-1">Neto a acreditar (calculado)</label>
              <div className={`px-3 py-2 rounded-lg border text-sm font-semibold ${
                netoPreview < 0
                  ? 'bg-red-50 border-red-200 text-red-700 dark:bg-red-500/10 dark:border-red-500/30 dark:text-red-300'
                  : 'bg-gray-50 border-gray-200 text-gray-900 dark:bg-white/5 dark:border-white/10 dark:text-gray-100'
              }`}>
                {fmt(netoPreview)}
              </div>
            </div>
          </div>

          <div>
            <label className="block text-xs font-medium text-gray-600 dark:text-gray-400 mb-1">Notas</label>
            <input className={inputClass} value={form.notas} onChange={e => setForm(f => ({ ...f, notas: e.target.value }))} placeholder="Opcional" />
          </div>

          <p className="text-xs text-gray-400">
            Bruto = Neto + Aranceles + IVA + Percepciones + Retenciones. Si no balancea, el guardado se rechaza.
          </p>

          <div className="flex gap-2">
            <button
              onClick={guardar}
              disabled={saving || parsing}
              className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-ml-blue text-white text-sm font-medium hover:opacity-90 disabled:opacity-50"
            >
              <IconUpload />
              {saving ? 'Guardando…' : 'Guardar y generar asiento'}
            </button>
            <button
              onClick={() => { setForm(emptyForm()); setMsg(null) }}
              className="px-4 py-2 rounded-lg border border-gray-300 dark:border-white/10 text-sm text-gray-700 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-white/5"
            >
              Limpiar
            </button>
          </div>
        </div>
      )}

      {/* ── Tab Historial ── */}
      {tab === 'historial' && (
        <div className="rounded-xl border border-gray-200 dark:border-white/10 overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-xs text-gray-500 dark:text-gray-400 border-b border-gray-200 dark:border-white/10">
                <th className="px-3 py-2 font-medium">Fecha</th>
                <th className="px-3 py-2 font-medium">Período</th>
                <th className="px-3 py-2 font-medium">Marca</th>
                <th className="px-3 py-2 font-medium text-right">Bruto</th>
                <th className="px-3 py-2 font-medium text-right">Aranceles</th>
                <th className="px-3 py-2 font-medium text-right">Neto</th>
                <th className="px-3 py-2 font-medium">Estado</th>
                <th className="px-3 py-2 font-medium text-right">Acciones</th>
              </tr>
            </thead>
            <tbody>
              {loading && (
                <tr><td colSpan={8} className="px-3 py-6 text-center text-gray-400">Cargando…</td></tr>
              )}
              {!loading && items.length === 0 && (
                <tr><td colSpan={8} className="px-3 py-6 text-center text-gray-400">Sin liquidaciones.</td></tr>
              )}
              {!loading && items.map((l, i) => (
                <tr key={l.id} className={`border-b border-gray-100 dark:border-white/5 ${i % 2 ? 'bg-gray-50/50 dark:bg-white/[0.02]' : ''}`}>
                  <td className="px-3 py-2 text-gray-700 dark:text-gray-300 whitespace-nowrap">{fmtDate(l.fecha_acreditacion)}</td>
                  <td className="px-3 py-2 text-gray-700 dark:text-gray-300 whitespace-nowrap">{l.periodo}</td>
                  <td className="px-3 py-2">
                    <span className={`px-2 py-0.5 rounded-md text-xs font-semibold ${MARCA_BADGE[l.marca as Marca] || ''}`}>
                      {MARCAS.find(m => m.value === l.marca)?.label || l.marca}
                    </span>
                  </td>
                  <td className="px-3 py-2 text-right text-gray-900 dark:text-gray-100 whitespace-nowrap">{fmt(Number(l.monto_bruto))}</td>
                  <td className="px-3 py-2 text-right text-gray-600 dark:text-gray-400 whitespace-nowrap">{fmt(Number(l.aranceles))}</td>
                  <td className="px-3 py-2 text-right text-gray-900 dark:text-gray-100 whitespace-nowrap">{fmt(Number(l.neto))}</td>
                  <td className="px-3 py-2">
                    <span className={`px-2 py-0.5 rounded-md text-xs font-semibold ${ESTADO_BADGE[l.estado] || ''}`}>{l.estado}</span>
                  </td>
                  <td className="px-3 py-2">
                    <div className="flex items-center justify-end gap-1">
                      {l.estado !== 'anulada' && (
                        <button
                          onClick={() => abrirConciliar(l)}
                          title="Conciliar con movimiento"
                          className="p-1.5 rounded-md text-gray-500 hover:text-ml-blue hover:bg-gray-100 dark:hover:bg-white/10"
                        >
                          <IconLink />
                        </button>
                      )}
                      {canDelete && (
                        <button
                          onClick={() => eliminar(l)}
                          title="Eliminar"
                          className="p-1.5 rounded-md text-gray-500 hover:text-red-600 hover:bg-gray-100 dark:hover:bg-white/10"
                        >
                          <IconTrash />
                        </button>
                      )}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* ── Modal conciliar ── */}
      {conciliarLiq && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4" onClick={() => setConciliarLiq(null)}>
          <div className="w-full max-w-lg rounded-xl bg-white dark:bg-[#15151b] border border-gray-200 dark:border-white/10 p-5 shadow-xl" onClick={e => e.stopPropagation()}>
            <h3 className="text-base font-semibold text-gray-900 dark:text-gray-100 mb-1">Conciliar liquidación</h3>
            <p className="text-xs text-gray-500 dark:text-gray-400 mb-4">
              {MARCAS.find(m => m.value === conciliarLiq.marca)?.label} · {conciliarLiq.periodo} · neto {fmt(Number(conciliarLiq.neto))}
            </p>

            <div className="space-y-3">
              <div>
                <label className="block text-xs font-medium text-gray-600 dark:text-gray-400 mb-1">Extracto</label>
                <select className={inputClass} value={extractoSel ?? ''} onChange={e => setExtractoSel(e.target.value ? Number(e.target.value) : null)}>
                  <option value="">Seleccionar extracto…</option>
                  {extractos.map(ex => (
                    <option key={ex.id} value={ex.id}>{ex.nombre_archivo}</option>
                  ))}
                </select>
              </div>
              <div>
                <label className="block text-xs font-medium text-gray-600 dark:text-gray-400 mb-1">Movimiento</label>
                <select className={inputClass} value={movSel ?? ''} onChange={e => setMovSel(e.target.value ? Number(e.target.value) : null)} disabled={!extractoSel}>
                  <option value="">{extractoSel ? 'Seleccionar movimiento…' : 'Elegí un extracto primero'}</option>
                  {movimientos.map(m => (
                    <option key={m.id} value={m.id}>
                      {fmtDate(m.fecha)} · {fmt(Number(m.monto))} · {m.titular || m.cliente_acreditado || '—'}
                    </option>
                  ))}
                </select>
              </div>
            </div>

            <div className="flex justify-end gap-2 mt-5">
              <button onClick={() => setConciliarLiq(null)} className="px-4 py-2 rounded-lg border border-gray-300 dark:border-white/10 text-sm text-gray-700 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-white/5">
                Cancelar
              </button>
              <button onClick={confirmarConciliar} disabled={!movSel} className="px-4 py-2 rounded-lg bg-ml-blue text-white text-sm font-medium hover:opacity-90 disabled:opacity-50">
                Conciliar
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

export default Tarjetas
