import React, { useEffect, useRef, useState, useCallback } from 'react'
import { useSearchParams } from 'react-router-dom'
import { apiClient } from '@/services/api'
import { useOrgStore } from '@/store/org'
import { useAuthStore } from '@/store/auth'
import { confirmDialog } from '@/store/confirm'

const fmt = (n: number) =>
  new Intl.NumberFormat('es-AR', { style: 'currency', currency: 'ARS', minimumFractionDigits: 0 }).format(n)

interface Cliente { id: number; nombre: string }
interface Categoria { id: number; nombre: string }
interface Egreso {
  id: number
  tipo: string
  categoria: string | null
  forma_pago: string
  monto: number
  fecha: string | null
  beneficiario: string | null
  cliente_nombre: string | null
  concepto: string | null
  referencia: string | null
  compartido_whatsapp: boolean
  tiene_foto: boolean
}

const TIPO_LABEL: Record<string, string> = {
  proveedor: 'Proveedor',
  gasto: 'Gasto operativo',
  pago_cliente: 'Pago a cliente',
}

type Vista = 'lista' | 'nuevo'
type Step = 'foto' | 'datos' | 'exito'

export const Pagos: React.FC = () => {
  const { activeOrgId } = useOrgStore()
  const { hasPermission } = useAuthStore()
  const canDelete = hasPermission('delete_records')

  const [vista, setVista] = useState<Vista>('lista')

  // ── Lista / historial ────────────────────────────────────────────
  const [items, setItems] = useState<Egreso[]>([])
  const [loadingList, setLoadingList] = useState(false)
  const [fTipo, setFTipo] = useState('')
  const [fForma, setFForma] = useState('')
  const [fDesde, setFDesde] = useState('')
  const [fHasta, setFHasta] = useState('')

  const cargarLista = useCallback(async () => {
    setLoadingList(true)
    try {
      const params: Record<string, string | number> = { limit: 200 }
      if (activeOrgId) params.org_id = activeOrgId
      if (fTipo) params.tipo = fTipo
      if (fForma) params.forma_pago = fForma
      if (fDesde) params.desde = fDesde
      if (fHasta) params.hasta = fHasta
      const res = await apiClient.client.get('/pagos', { params })
      setItems(res.data.items || [])
    } catch { setItems([]) }
    finally { setLoadingList(false) }
  }, [activeOrgId, fTipo, fForma, fDesde, fHasta])

  useEffect(() => { if (vista === 'lista') cargarLista() }, [vista, cargarLista])

  const eliminar = async (e: Egreso) => {
    const nombre = e.beneficiario || e.cliente_nombre || e.concepto || 'egreso'
    const ok = await confirmDialog({
      title: 'Eliminar pago',
      message: `Se eliminará el pago a ${nombre} (${fmt(e.monto)}). Se reversa el asiento contable.`,
      confirmLabel: 'Eliminar',
      danger: true,
    })
    if (!ok) return
    try {
      await apiClient.client.delete(`/pagos/${e.id}`)
      cargarLista()
    } catch (err: any) {
      alert(err.response?.data?.detail || 'No se pudo eliminar')
    }
  }

  // ── Nuevo egreso (flujo foto → datos → éxito) ─────────────────────
  const [step, setStep] = useState<Step>('datos')
  const [clientes, setClientes] = useState<Cliente[]>([])
  const [categorias, setCategorias] = useState<Categoria[]>([])
  const [foto, setFoto] = useState<string | null>(null)
  const [fotoPreview, setFotoPreview] = useState<string | null>(null)
  const [form, setForm] = useState({
    tipo: 'proveedor',
    forma_pago: 'banco',
    beneficiario: '',
    cliente_nombre: '',
    categoria: '',
    monto: '',
    concepto: '',
    referencia: '',
    fecha: new Date().toISOString().slice(0, 10),
  })
  const [saving, setSaving] = useState(false)
  const [resultado, setResultado] = useState<any>(null)
  const [msg, setMsg] = useState('')
  const [nuevaCat, setNuevaCat] = useState('')
  const fileInputRef = useRef<HTMLInputElement>(null)

  const [searchParams, setSearchParams] = useSearchParams()

  // Compartir desde WhatsApp/galería (share target)
  useEffect(() => {
    if (searchParams.get('compartido') !== '1') return
    const destino = sessionStorage.getItem('compartido:destino')
    const archivosRaw = sessionStorage.getItem('compartido:archivos')
    if ((destino === 'op' || destino === 'pago' || destino === 'gasto') && archivosRaw) {
      try {
        const archivos = JSON.parse(archivosRaw) as { name: string; type: string; dataUrl: string }[]
        const imagen = archivos.find(a => a.type.startsWith('image/')) || archivos[0]
        if (imagen?.dataUrl) {
          setFotoPreview(imagen.dataUrl)
          setFoto(imagen.dataUrl)
        }
        if (destino === 'gasto') setForm(p => ({ ...p, tipo: 'gasto' }))
        setVista('nuevo')
        setStep('datos')
      } catch {}
      ;['destino', 'archivos', 'titulo', 'texto', 'ts'].forEach(k =>
        sessionStorage.removeItem(`compartido:${k}`))
    }
    const sp = new URLSearchParams(searchParams)
    sp.delete('compartido')
    setSearchParams(sp, { replace: true })
  }, [searchParams, setSearchParams])

  useEffect(() => {
    const params = activeOrgId ? { org_id: activeOrgId } : {}
    apiClient.client.get('/clientes/archivos', { params }).then(r => {
      setClientes(r.data.clientes?.map((c: any) => ({ id: c.id || 0, nombre: c.nombre })) || [])
    }).catch(() => {})
    apiClient.client.get('/pagos/categorias', { params }).then(r => {
      setCategorias(r.data || [])
    }).catch(() => {})
  }, [activeOrgId])

  const handleFoto = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return
    const reader = new FileReader()
    reader.onload = ev => {
      const base64 = (ev.target?.result as string) || ''
      setFotoPreview(base64)
      const img = new Image()
      img.onload = () => {
        const canvas = document.createElement('canvas')
        const MAX = 1200
        let w = img.width, h = img.height
        if (w > MAX) { h = h * MAX / w; w = MAX }
        if (h > MAX) { w = w * MAX / h; h = MAX }
        canvas.width = w; canvas.height = h
        canvas.getContext('2d')?.drawImage(img, 0, 0, w, h)
        const compressed = canvas.toDataURL('image/jpeg', 0.7)
        setFoto(compressed)
        // Compress further to 768px for OCR (1 Gemini tile = 258 tokens)
        const OCR_MAX = 768
        let ow = w, oh = h
        if (ow > OCR_MAX) { oh = Math.round(oh * OCR_MAX / ow); ow = OCR_MAX }
        if (oh > OCR_MAX) { ow = Math.round(ow * OCR_MAX / oh); oh = OCR_MAX }
        const ocrCanvas = document.createElement('canvas')
        ocrCanvas.width = ow; ocrCanvas.height = oh
        const ocrCtx = ocrCanvas.getContext('2d')!
        ocrCtx.filter = 'grayscale(1) contrast(1.4) brightness(1.1)'
        ocrCtx.drawImage(img, 0, 0, ow, oh)
        const ocrCompressed = ocrCanvas.toDataURL('image/jpeg', 0.7)
        apiClient.client.post('/agente/ocr-transferencia', { imagen_base64: ocrCompressed })
          .then(res => {
            const d = res.data
            setForm(prev => ({
              ...prev,
              monto:        prev.monto        || (d.monto != null ? String(d.monto) : prev.monto),
              fecha:        prev.fecha        || d.fecha        || prev.fecha,
              beneficiario: prev.beneficiario || d.beneficiario || prev.beneficiario,
              referencia:   prev.referencia   || d.referencia   || prev.referencia,
            }))
          })
          .catch(() => { /* OCR no disponible — el usuario carga manualmente */ })
      }
      img.src = base64
    }
    reader.readAsDataURL(file)
  }

  const montoNum = parseFloat(form.monto.replace(/\./g, '').replace(',', '.')) || 0

  const crearCategoria = async () => {
    const nombre = nuevaCat.trim()
    if (!nombre) return
    try {
      const body: Record<string, unknown> = { nombre }
      if (activeOrgId) body.org_id = activeOrgId
      const r = await apiClient.client.post('/pagos/categorias', body)
      setCategorias(prev => [...prev.filter(c => c.id !== r.data.id), r.data].sort((a, b) => a.nombre.localeCompare(b.nombre)))
      setForm(p => ({ ...p, categoria: r.data.nombre }))
      setNuevaCat('')
    } catch (e: any) {
      setMsg(e.response?.data?.detail || 'No se pudo crear la categoría')
    }
  }

  const confirmar = async () => {
    if (montoNum <= 0) { setMsg('Ingresá un monto mayor a 0'); return }
    if (form.tipo === 'pago_cliente' && !form.cliente_nombre) { setMsg('Elegí el cliente'); return }
    if (form.tipo === 'proveedor' && !form.beneficiario) { setMsg('Ingresá el proveedor'); return }
    setSaving(true); setMsg('')
    try {
      const res = await apiClient.client.post('/pagos', {
        tipo: form.tipo,
        forma_pago: form.forma_pago,
        monto: montoNum,
        fecha: form.fecha,
        beneficiario: form.beneficiario || undefined,
        cliente_nombre: form.cliente_nombre || undefined,
        categoria: form.categoria || undefined,
        concepto: form.concepto || undefined,
        referencia: form.referencia || undefined,
        foto_base64: foto,
        ...(activeOrgId ? { org_id: activeOrgId } : {}),
      })
      setResultado(res.data.egreso)
      setStep('exito')
    } catch (err: any) {
      setMsg(err.response?.data?.detail || 'Error al registrar')
    } finally { setSaving(false) }
  }

  const compartirWhatsApp = async () => {
    if (!resultado) return
    const nombre = form.beneficiario || form.cliente_nombre || form.concepto || 'Pago'
    const texto = `Pago registrado%0A• ${TIPO_LABEL[form.tipo]}: ${nombre}%0A• Importe: ${fmt(montoNum)}%0A• ${form.forma_pago === 'banco' ? 'Banco' : 'Efectivo'}%0A• Fecha: ${new Date(form.fecha).toLocaleDateString('es-AR')}`
    await apiClient.client.post(`/pagos/${resultado.id}/compartir`).catch(() => {})
    if (foto && navigator.share && navigator.canShare) {
      try {
        const blob = await fetch(foto).then(r => r.blob())
        const file = new File([blob], `Pago_${nombre}.jpg`, { type: 'image/jpeg' })
        if (navigator.canShare({ files: [file] })) {
          await navigator.share({
            title: `Pago - ${nombre} - ${fmt(montoNum)}`,
            text: `Pago - ${nombre} - ${fmt(montoNum)} - ${new Date(form.fecha).toLocaleDateString('es-AR')}`,
            files: [file],
          })
          return
        }
      } catch {}
    }
    window.open(`whatsapp://send?text=${texto}`, '_blank')
  }

  const reiniciar = () => {
    setStep('datos')
    setFoto(null); setFotoPreview(null)
    setForm({
      tipo: 'proveedor', forma_pago: 'banco', beneficiario: '', cliente_nombre: '',
      categoria: '', monto: '', concepto: '', referencia: '',
      fecha: new Date().toISOString().slice(0, 10),
    })
    setResultado(null); setMsg('')
  }

  // ── Render ────────────────────────────────────────────────────────
  return (
    <div className="p-4 md:p-6 max-w-2xl mx-auto space-y-4">
      <div className="flex items-center justify-between gap-3">
        <h1 className="text-xl font-bold dark:text-white">Pagos</h1>
        <div className="flex gap-2">
          <button
            onClick={() => setVista('lista')}
            className={vista === 'lista' ? 'btn-yellow text-sm' : 'btn-secondary text-sm'}>
            Historial
          </button>
          <button
            onClick={() => { reiniciar(); setVista('nuevo') }}
            className={vista === 'nuevo' ? 'btn-yellow text-sm' : 'btn-secondary text-sm'}>
            + Nuevo pago
          </button>
        </div>
      </div>

      {/* ── HISTORIAL ── */}
      {vista === 'lista' && (
        <>
          <div className="card flex flex-wrap gap-2 items-end">
            <div>
              <label className="label text-2xs">Tipo</label>
              <select className="input-field text-sm" value={fTipo} onChange={e => setFTipo(e.target.value)}>
                <option value="">Todos</option>
                <option value="proveedor">Proveedor</option>
                <option value="gasto">Gasto operativo</option>
                <option value="pago_cliente">Pago a cliente</option>
              </select>
            </div>
            <div>
              <label className="label text-2xs">Forma</label>
              <select className="input-field text-sm" value={fForma} onChange={e => setFForma(e.target.value)}>
                <option value="">Todas</option>
                <option value="banco">Banco</option>
                <option value="efectivo">Efectivo</option>
              </select>
            </div>
            <div>
              <label className="label text-2xs">Desde</label>
              <input type="date" className="input-field text-sm" value={fDesde} onChange={e => setFDesde(e.target.value)} />
            </div>
            <div>
              <label className="label text-2xs">Hasta</label>
              <input type="date" className="input-field text-sm" value={fHasta} onChange={e => setFHasta(e.target.value)} />
            </div>
          </div>

          {loadingList ? (
            <div className="py-8 text-center text-gray-400">Cargando...</div>
          ) : items.length === 0 ? (
            <div className="py-8 text-center text-gray-400 dark:text-zinc-500">No hay pagos en este filtro.</div>
          ) : (
            <div className="card p-0 overflow-hidden">
              <div className="divide-y divide-ml-gray dark:divide-ml-dark-border">
                {items.map(e => (
                  <div key={e.id} className="flex items-center gap-3 px-4 py-3">
                    <div className="flex-1 min-w-0">
                      <p className="font-medium text-sm dark:text-white truncate">
                        {e.beneficiario || e.cliente_nombre || e.concepto || '—'}
                      </p>
                      <p className="text-xs text-gray-400 dark:text-zinc-500">
                        {TIPO_LABEL[e.tipo] || e.tipo}
                        {e.categoria ? ` · ${e.categoria}` : ''}
                        {e.fecha ? ` · ${e.fecha}` : ''}
                      </p>
                    </div>
                    <div className="text-right shrink-0">
                      <p className="font-mono font-semibold text-sm dark:text-white">{fmt(e.monto)}</p>
                      <div className="flex gap-1 justify-end mt-0.5">
                        <span className={`badge text-2xs ${e.forma_pago === 'banco' ? 'badge-info' : 'badge-ok'}`}>
                          {e.forma_pago === 'banco' ? 'Banco' : 'Efectivo'}
                        </span>
                        {e.tiene_foto && <span className="badge badge-ok text-2xs">📷</span>}
                      </div>
                    </div>
                    {canDelete && (
                      <button
                        onClick={() => eliminar(e)}
                        title="Eliminar"
                        className="shrink-0 p-1.5 rounded-lg text-gray-400 hover:text-red-500 hover:bg-red-50 dark:hover:bg-red-900/20 transition-colors">
                        <svg className="w-4 h-4" fill="none" stroke="currentColor" strokeWidth={1.8} viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" d="M14.74 9l-.346 9m-4.788 0L9.26 9m9.968-3.21c.342.052.682.107 1.022.166m-1.022-.165L18.16 19.673a2.25 2.25 0 01-2.244 2.077H8.084a2.25 2.25 0 01-2.244-2.077L4.772 5.79m14.456 0a48.108 48.108 0 00-3.478-.397m-12 .562c.34-.059.68-.114 1.022-.165m0 0a48.11 48.11 0 013.478-.397m7.5 0v-.916c0-1.18-.91-2.164-2.09-2.201a51.964 51.964 0 00-3.32 0c-1.18.037-2.09 1.022-2.09 2.201v.916m7.5 0a48.667 48.667 0 00-7.5 0"/></svg>
                      </button>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}
        </>
      )}

      {/* ── NUEVO PAGO ── */}
      {vista === 'nuevo' && step !== 'exito' && (
        <div className="space-y-4">
          {msg && (
            <div className="px-3 py-2 bg-red-50 dark:bg-red-900/20 text-red-600 dark:text-red-400 rounded-lg text-sm">{msg}</div>
          )}

          <div className="card space-y-4">
            {/* Tipo */}
            <div>
              <label className="label">Tipo de pago</label>
              <div className="grid grid-cols-3 gap-2">
                {(['proveedor', 'gasto', 'pago_cliente'] as const).map(t => (
                  <button key={t} type="button"
                    onClick={() => setForm(p => ({ ...p, tipo: t }))}
                    className={`py-2 px-2 rounded-lg text-xs font-medium transition-colors ${
                      form.tipo === t
                        ? 'bg-ml-blue dark:bg-ml-green text-white dark:text-black'
                        : 'bg-ml-gray dark:bg-ml-dark-card text-gray-500 dark:text-zinc-400'}`}>
                    {TIPO_LABEL[t]}
                  </button>
                ))}
              </div>
            </div>

            {/* Forma de pago */}
            <div>
              <label className="label">Forma de pago</label>
              <div className="grid grid-cols-2 gap-2">
                {(['banco', 'efectivo'] as const).map(f => (
                  <button key={f} type="button"
                    onClick={() => setForm(p => ({ ...p, forma_pago: f }))}
                    className={`py-2 rounded-lg text-sm font-medium transition-colors ${
                      form.forma_pago === f
                        ? 'bg-ml-blue dark:bg-ml-green text-white dark:text-black'
                        : 'bg-ml-gray dark:bg-ml-dark-card text-gray-500 dark:text-zinc-400'}`}>
                    {f === 'banco' ? '🏦 Banco' : '💵 Efectivo'}
                  </button>
                ))}
              </div>
              {form.forma_pago === 'efectivo' && (
                <p className="text-2xs text-amber-600 dark:text-amber-400 mt-1">
                  Se descuenta del arqueo de caja del día.
                </p>
              )}
            </div>

            {/* Cliente (solo pago a cliente) o Proveedor */}
            {form.tipo === 'pago_cliente' ? (
              <div>
                <label className="label">Cliente</label>
                <select className="input-field" value={form.cliente_nombre}
                  onChange={e => setForm(p => ({ ...p, cliente_nombre: e.target.value }))}>
                  <option value="">Seleccionar cliente...</option>
                  {clientes.map(c => <option key={c.id} value={c.nombre}>{c.nombre}</option>)}
                </select>
              </div>
            ) : (
              <div>
                <label className="label">{form.tipo === 'proveedor' ? 'Proveedor' : 'Beneficiario'}</label>
                <input className="input-field" placeholder="Nombre"
                  value={form.beneficiario}
                  onChange={e => setForm(p => ({ ...p, beneficiario: e.target.value }))} />
              </div>
            )}

            {/* Categoría (gasto/proveedor) */}
            {form.tipo !== 'pago_cliente' && (
              <div>
                <label className="label">Categoría</label>
                <select className="input-field" value={form.categoria}
                  onChange={e => setForm(p => ({ ...p, categoria: e.target.value }))}>
                  <option value="">Sin categoría</option>
                  {categorias.map(c => <option key={c.id} value={c.nombre}>{c.nombre}</option>)}
                </select>
                <div className="flex gap-2 mt-2">
                  <input className="input-field text-sm flex-1" placeholder="Nueva categoría..."
                    value={nuevaCat} onChange={e => setNuevaCat(e.target.value)}
                    onKeyDown={e => { if (e.key === 'Enter') { e.preventDefault(); crearCategoria() } }} />
                  <button type="button" onClick={crearCategoria} className="btn-secondary text-sm whitespace-nowrap">+ Agregar</button>
                </div>
              </div>
            )}

            <div>
              <label className="label">Importe</label>
              <input className="input-field font-mono text-lg" type="number" placeholder="0"
                value={form.monto}
                onChange={e => setForm(p => ({ ...p, monto: e.target.value }))} />
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="label">Fecha</label>
                <input type="date" className="input-field" value={form.fecha}
                  onChange={e => setForm(p => ({ ...p, fecha: e.target.value }))} />
              </div>
              <div>
                <label className="label">Referencia</label>
                <input className="input-field" placeholder="opcional"
                  value={form.referencia}
                  onChange={e => setForm(p => ({ ...p, referencia: e.target.value }))} />
              </div>
            </div>

            <div>
              <label className="label">Concepto / notas</label>
              <input className="input-field" placeholder="opcional"
                value={form.concepto}
                onChange={e => setForm(p => ({ ...p, concepto: e.target.value }))} />
            </div>

            {/* Foto */}
            <div>
              <label className="label">Comprobante (foto)</label>
              {fotoPreview ? (
                <div className="space-y-2">
                  <img src={fotoPreview} alt="comprobante" className="max-h-48 mx-auto rounded-lg object-contain border border-ml-gray dark:border-ml-dark-border" />
                  <button type="button" onClick={() => { setFoto(null); setFotoPreview(null) }} className="btn-secondary text-sm w-full">
                    Quitar foto
                  </button>
                </div>
              ) : (
                <>
                  <input ref={fileInputRef} type="file" accept="image/*" capture="environment"
                    className="hidden" onChange={handleFoto} />
                  <button type="button" onClick={() => fileInputRef.current?.click()} className="btn-secondary w-full text-sm">
                    📷 Sacar / subir foto
                  </button>
                </>
              )}
            </div>
          </div>

          <button onClick={confirmar} disabled={saving} className="btn-yellow w-full text-base py-3">
            {saving ? 'Registrando...' : '✓ Registrar pago'}
          </button>
        </div>
      )}

      {/* ── ÉXITO ── */}
      {vista === 'nuevo' && step === 'exito' && resultado && (
        <div className="space-y-4">
          <div className="card text-center py-6">
            <div className="text-5xl mb-3">✅</div>
            <p className="font-bold text-lg dark:text-white">Pago registrado</p>
            <p className="text-sm text-gray-400 dark:text-zinc-500 mt-1">
              {form.beneficiario || form.cliente_nombre || form.concepto} · {fmt(montoNum)}
            </p>
            <p className="text-xs text-gray-400 dark:text-zinc-600 mt-1">
              {TIPO_LABEL[form.tipo]} · {form.forma_pago === 'banco' ? 'Banco' : 'Efectivo'}
            </p>
          </div>

          <button
            onClick={compartirWhatsApp}
            className="w-full py-3 rounded-xl text-base font-semibold bg-[#25D366] text-white hover:bg-[#20c25a] transition-colors flex items-center justify-center gap-2">
            <span className="text-xl">📤</span>
            Compartir por WhatsApp
          </button>

          <div className="flex gap-3">
            <button onClick={reiniciar} className="btn-secondary flex-1">+ Otro pago</button>
            <button onClick={() => { setVista('lista'); reiniciar() }} className="btn-yellow flex-1">Ver historial</button>
          </div>
        </div>
      )}
    </div>
  )
}
