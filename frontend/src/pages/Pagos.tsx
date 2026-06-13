import React, { useEffect, useRef, useState, useCallback } from 'react'
import { useSearchParams } from 'react-router-dom'
import { apiClient } from '@/services/api'
import { useOrgStore } from '@/store/org'
import { useAuthStore } from '@/store/auth'
import { confirmDialog } from '@/store/confirm'
import { useLockStore } from '@/store/lock'
import { localIsoDate } from '@/utils/fecha'

// Evita que el share sheet nativo dispare el bloqueo PIN (el share sheet
// hace perder foco; puede tardar hasta ~15s si el usuario tarda en elegir la app).
function suppressLockForShare() {
  try { useLockStore.getState().suppressLock(20000) } catch { /* noop */ }
}
// Para el selector de archivos (cámara): suppress corto porque la cámara
// cierra sola en segundos. 20s sería demasiado: si el usuario minimiza
// luego de tomar la foto, el lock no se dispararía.
function suppressLockForCamera() {
  try { useLockStore.getState().suppressLock(8000) } catch { /* noop */ }
}

interface EgresoResultado { id: number }

const fmt = (n: number) =>
  new Intl.NumberFormat('es-AR', { style: 'currency', currency: 'ARS', minimumFractionDigits: 0 }).format(n)

// Parse monto from OCR: handles number OR string (incl. Argentine "15.000,00" / US "15,000.00")
const parseMonto = (raw: unknown): number | null => {
  if (raw == null) return null
  if (typeof raw === 'number') return isNaN(raw) ? null : raw
  // quitar símbolo $ y espacios, luego analizar formato
  const s = String(raw).trim().replace(/[$\s]/g, '')
  if (!s) return null
  // formato argentino: 1.200.000,50 o 15.000,50
  if (/^\d{1,3}(\.\d{3})+(,\d{0,2})?$/.test(s))
    return parseFloat(s.replace(/\./g, '').replace(',', '.'))
  // formato con coma de miles: 1,200,000.50
  if (/^\d{1,3}(,\d{3})+(\.\d{0,2})?$/.test(s))
    return parseFloat(s.replace(/,/g, ''))
  // número con coma decimal: 15000,50
  if (/^\d+(,\d{1,2})$/.test(s))
    return parseFloat(s.replace(',', '.'))
  // número plano con o sin punto decimal
  const n = parseFloat(s.replace(',', '.'))
  return isNaN(n) ? null : n
}

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

// Comparte el comprobante como PDF (foto + datos del pago). jsPDF on-demand.
// Es la opción preferida; si el dispositivo no acepta compartir PDF, el caller
// cae a sharePagoImagen (imagen compuesta) y nunca a la foto sola.
const sharePagoPdf = async (
  nombre: string, tipo: string, montoNum: number, fecha: string,
  formaPago: string, referencia: string, fotoB64: string
): Promise<boolean> => {
  try {
    const { jsPDF } = await import('jspdf')
    const pdf = new jsPDF({ orientation: 'portrait', unit: 'mm', format: 'a4' })

    const tipoLabel: Record<string, string> = { proveedor: 'PROVEEDOR', gasto: 'GASTO OPERATIVO', pago_cliente: 'PAGO A CLIENTE' }
    pdf.setFont('helvetica', 'bold')
    pdf.setFontSize(13)
    pdf.text(`COMPROBANTE DE ${tipoLabel[tipo] || 'PAGO'}`, 105, 16, { align: 'center' })
    pdf.setFont('helvetica', 'normal')
    pdf.setFontSize(9)
    pdf.text(nombre, 105, 23, { align: 'center' })

    // Re-renderizar la foto sobre fondo blanco para evitar que salga negra
    // (transparencia → negro en JPEG) y respetar el aspect ratio real.
    const { jpeg, w, h } = await new Promise<{ jpeg: string; w: number; h: number }>((resolve, reject) => {
      const img = new Image()
      img.onload = () => {
        const iw = img.naturalWidth || 1000
        const ih = img.naturalHeight || 700
        const canvas = document.createElement('canvas')
        canvas.width = iw; canvas.height = ih
        const ctx = canvas.getContext('2d')
        if (!ctx) { reject(new Error('no ctx')); return }
        ctx.fillStyle = '#ffffff'
        ctx.fillRect(0, 0, iw, ih)
        ctx.drawImage(img, 0, 0)
        resolve({ jpeg: canvas.toDataURL('image/jpeg', 0.85), w: iw, h: ih })
      }
      img.onerror = () => reject(new Error('img load'))
      img.src = fotoB64
    })

    // Encajar la imagen dentro del área disponible conservando proporción
    const maxW = 190, maxH = 135, x0 = 10, y0 = 28
    const ratio = Math.min(maxW / w, maxH / h)
    const drawW = w * ratio
    const drawH = h * ratio
    const dx = x0 + (maxW - drawW) / 2
    pdf.addImage(jpeg, 'JPEG', dx, y0, drawW, drawH)

    pdf.setDrawColor(180, 180, 180)
    pdf.line(10, 169, 200, 169)

    pdf.setFontSize(10)
    const fmtN = (n: number) => new Intl.NumberFormat('es-AR', { style: 'currency', currency: 'ARS', minimumFractionDigits: 2 }).format(n)
    const rows = [
      ['Importe:', fmtN(montoNum)],
      ['Forma de pago:', formaPago === 'banco' ? 'Banco' : 'Efectivo'],
      ['Fecha:', new Date(fecha + 'T00:00:00').toLocaleDateString('es-AR')],
      ['Referencia:', referencia || '—'],
      ['Generado:', new Date().toLocaleDateString('es-AR')],
    ]
    rows.forEach(([label, value], i) => {
      const y = 177 + i * 8
      pdf.setFont('helvetica', 'bold'); pdf.text(label, 12, y)
      pdf.setFont('helvetica', 'normal'); pdf.text(value, 52, y)
    })

    const blob = pdf.output('blob')
    const file = new File([blob], `Pago_${nombre.replace(/\s+/g, '_')}.pdf`, { type: 'application/pdf' })
    if (navigator.share && navigator.canShare?.({ files: [file] })) {
      suppressLockForShare()
      await navigator.share({ title: `Pago - ${nombre}`, files: [file] })
      return true
    }
  } catch (e: any) {
    // Si el usuario cancela el share sheet (AbortError), considerarlo "compartido"
    // para NO caer al fallback.
    if (e?.name === 'AbortError') return true
  }
  return false
}

// Fallback cuando el dispositivo NO acepta compartir PDF: imagen compuesta
// (foto + datos del pago) en un solo JPEG. Nunca comparte la foto sola.
const sharePagoImagen = async (
  nombre: string, tipo: string, montoNum: number, fecha: string,
  formaPago: string, referencia: string, fotoB64: string
): Promise<boolean> => {
  try {
    const img = new Image()
    await new Promise<void>((resolve, reject) => {
      img.onload = () => resolve()
      img.onerror = () => reject(new Error('img'))
      img.src = fotoB64
    })

    const PX = 900          // ancho fijo del comprobante
    const PAD = 32
    const ROW_H = 48
    const fotoW = PX
    const fotoH = Math.round(img.naturalHeight * PX / (img.naturalWidth || PX))
    const fmtN = (n: number) => new Intl.NumberFormat('es-AR', { style: 'currency', currency: 'ARS', minimumFractionDigits: 2 }).format(n)
    const TIPO_LABEL_SHORT: Record<string, string> = { proveedor: 'Proveedor', gasto: 'Gasto', pago_cliente: 'Pago a cliente' }
    const rows = [
      ['Importe', fmtN(montoNum)],
      ['Tipo', TIPO_LABEL_SHORT[tipo] || tipo],
      ['Forma de pago', formaPago === 'banco' ? 'Banco' : 'Efectivo'],
      ['Fecha', new Date(fecha + 'T00:00:00').toLocaleDateString('es-AR')],
      ...(referencia ? [['Referencia', referencia]] : []),
    ]
    const headerH = 56
    const footerH = headerH + rows.length * ROW_H + PAD
    const totalH = fotoH + footerH

    const canvas = document.createElement('canvas')
    canvas.width = PX; canvas.height = totalH
    const ctx = canvas.getContext('2d')!

    // Foto sobre fondo blanco (evita negro de canales alpha en JPEG)
    ctx.fillStyle = '#ffffff'
    ctx.fillRect(0, 0, PX, totalH)
    ctx.drawImage(img, 0, 0, fotoW, fotoH)

    // Separador
    ctx.fillStyle = '#f3f4f6'
    ctx.fillRect(0, fotoH, PX, footerH)

    // Título
    ctx.fillStyle = '#111827'
    ctx.font = `bold 30px system-ui, sans-serif`
    ctx.fillText(`COMPROBANTE DE PAGO`, PAD, fotoH + 38)
    ctx.fillStyle = '#6b7280'
    ctx.font = `22px system-ui, sans-serif`
    ctx.fillText(nombre, PAD, fotoH + 62)

    // Línea divisora
    ctx.strokeStyle = '#d1d5db'
    ctx.lineWidth = 1
    ctx.beginPath(); ctx.moveTo(PAD, fotoH + 72); ctx.lineTo(PX - PAD, fotoH + 72); ctx.stroke()

    // Filas de datos
    rows.forEach(([label, value], i) => {
      const y = fotoH + headerH + i * ROW_H + 30
      ctx.fillStyle = '#6b7280'
      ctx.font = `20px system-ui, sans-serif`
      ctx.fillText(label, PAD, y)
      ctx.fillStyle = '#111827'
      ctx.font = `bold 22px system-ui, sans-serif`
      ctx.fillText(value, PX / 2, y)
    })

    const blob = await new Promise<Blob>((resolve, reject) =>
      canvas.toBlob(b => b ? resolve(b) : reject(new Error('toBlob')), 'image/jpeg', 0.92)
    )
    const file = new File([blob], `Pago_${nombre.replace(/\s+/g, '_')}.jpg`, { type: 'image/jpeg' })
    if (navigator.share && navigator.canShare?.({ files: [file] })) {
      suppressLockForShare()
      await navigator.share({ title: `Pago - ${nombre}`, files: [file] })
      return true
    }
  } catch (e: any) {
    if (e?.name === 'AbortError') return true
  }
  return false
}

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
      const params: Record<string, string | number> = { limit: 50 }
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
    fecha: localIsoDate(),
  })
  const [saving, setSaving] = useState(false)
  const [resultado, setResultado] = useState<EgresoResultado | null>(null)
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

  // Lazy: cargar clientes/categorías solo al abrir el form (no bloquea la carga inicial del historial)
  useEffect(() => {
    if (vista !== 'nuevo') return
    const params = activeOrgId ? { org_id: activeOrgId } : {}
    apiClient.client.get('/clientes/archivos', { params }).then(r => {
      // r.data.clientes solo incluye clientes con planillas; usar organizaciones[0].clientes
      // que incluye TODOS los clientes de la org (incluso los recién creados sin planillas)
      interface OrgRaw { clientes?: { id: number; nombre: string }[] }
      const orgs: OrgRaw[] = r.data.organizaciones || []
      const todos = orgs.flatMap(o => o.clientes || [])
      const lista: { id: number; nombre: string }[] = todos.length
        ? todos.map(c => ({ id: c.id, nombre: c.nombre }))
        : (r.data.clientes?.map((c: { id?: number; nombre: string }) => ({ id: c.id || 0, nombre: c.nombre })) || [])
      setClientes(lista.sort((a, b) => a.nombre.localeCompare(b.nombre)))
    }).catch(() => {})
    apiClient.client.get('/pagos/categorias', { params }).then(r => {
      setCategorias(r.data || [])
    }).catch(() => {})
  }, [activeOrgId, vista])

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
        const ctx = canvas.getContext('2d')!
        ctx.fillStyle = '#ffffff'; ctx.fillRect(0, 0, w, h)  // fondo blanco → evita negro en JPEG
        ctx.filter = 'grayscale(1) contrast(1.4) brightness(1.1)'
        ctx.drawImage(img, 0, 0, w, h)
        const compressed = canvas.toDataURL('image/jpeg', 0.7)
        setFoto(compressed)
        // Para OCR: máx 1024px, calidad alta, sin filtros (Gemini lee mejor color)
        const OCR_MAX = 1024
        let ow = img.width, oh = img.height
        if (ow > OCR_MAX) { oh = Math.round(oh * OCR_MAX / ow); ow = OCR_MAX }
        if (oh > OCR_MAX) { ow = Math.round(ow * OCR_MAX / oh); oh = OCR_MAX }
        const ocrCanvas = document.createElement('canvas')
        ocrCanvas.width = ow; ocrCanvas.height = oh
        const ocrCtx = ocrCanvas.getContext('2d')!
        ocrCtx.fillStyle = '#ffffff'; ocrCtx.fillRect(0, 0, ow, oh)
        ocrCtx.drawImage(img, 0, 0, ow, oh)
        const ocrCompressed = ocrCanvas.toDataURL('image/jpeg', 0.92)
        apiClient.client.post('/agente/ocr-transferencia', { imagen_base64: ocrCompressed })
          .then(res => {
            const d = res.data
            setForm(prev => {
              const ocrMonto = parseMonto(d.monto)
              return {
                ...prev,
                // type="number" input requires standard decimal format ("15000.5"), NOT Argentine ("15.000,50")
                monto:        prev.monto        || (ocrMonto != null ? String(Math.round(ocrMonto * 100) / 100) : prev.monto),
                fecha:        prev.fecha        || d.fecha        || prev.fecha,
                beneficiario: prev.beneficiario || d.beneficiario || prev.beneficiario,
                referencia:   prev.referencia   || d.referencia   || prev.referencia,
              }
            })
          })
          .catch(() => { setMsg('OCR no disponible — completá el importe manualmente') })
      }
      img.src = base64
    }
    reader.readAsDataURL(file)
  }

  const montoNum = parseFloat(form.monto) || 0

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
    // Fire-and-forget: NO usar await acá. navigator.share() requiere activación de
    // usuario transitoria (~5s); si esperamos el POST (Render cold start puede tardar),
    // la activación expira y share() lanza NotAllowedError → caía al fallback de foto.
    apiClient.client.post(`/pagos/${resultado.id}/compartir`).catch(() => {})
    if (foto) {
      // 1️⃣ Preferido: compartir como PDF con foto + datos.
      const sharedPdf = await sharePagoPdf(nombre, form.tipo, montoNum, form.fecha, form.forma_pago, form.referencia, foto)
      if (sharedPdf) return
      // 2️⃣ Si el dispositivo no acepta compartir PDF: imagen compuesta (foto + datos).
      const sharedImg = await sharePagoImagen(nombre, form.tipo, montoNum, form.fecha, form.forma_pago, form.referencia, foto)
      if (sharedImg) return
    }
    window.open(`whatsapp://send?text=${texto}`, '_blank')
  }

  const reiniciar = () => {
    setStep('datos')
    setFoto(null); setFotoPreview(null)
    setForm({
      tipo: 'proveedor', forma_pago: 'banco', beneficiario: '', cliente_nombre: '',
      categoria: '', monto: '', concepto: '', referencia: '',
      fecha: localIsoDate(),
    })
    setResultado(null); setMsg('')
  }

  // ── Editar egreso ─────────────────────────────────────────────────
  const [editItem, setEditItem] = useState<Egreso | null>(null)
  const [editForm, setEditForm] = useState({ monto: '', fecha: '', beneficiario: '', concepto: '', referencia: '', categoria: '' })
  const [editSaving, setEditSaving] = useState(false)
  const [editMsg, setEditMsg] = useState('')

  const abrirEdit = (e: Egreso) => {
    setEditItem(e)
    setEditForm({
      monto: String(e.monto),
      fecha: e.fecha || localIsoDate(),
      beneficiario: e.beneficiario || e.cliente_nombre || '',
      concepto: e.concepto || '',
      referencia: e.referencia || '',
      categoria: e.categoria || '',
    })
    setEditMsg('')
  }

  const guardarEdit = async () => {
    if (!editItem) return
    const m = parseFloat(editForm.monto)
    if (!m || m <= 0) { setEditMsg('Ingresá un monto válido'); return }
    setEditSaving(true); setEditMsg('')
    try {
      await apiClient.client.patch(`/pagos/${editItem.id}`, {
        monto: m,
        fecha: editForm.fecha,
        beneficiario: editForm.beneficiario || undefined,
        concepto: editForm.concepto || undefined,
        referencia: editForm.referencia || undefined,
        categoria: editForm.categoria || undefined,
      })
      setEditItem(null)
      cargarLista()
    } catch (err: any) {
      setEditMsg(err.response?.data?.detail || 'No se pudo guardar')
    } finally { setEditSaving(false) }
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
                        {e.tiene_foto && (
                          <span className="badge badge-ok text-2xs flex items-center gap-0.5">
                            <svg className="w-2.5 h-2.5" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" d="M6.827 6.175A2.31 2.31 0 015.186 7.23c-.38.054-.757.112-1.134.175C2.999 7.58 2.25 8.507 2.25 9.574V18a2.25 2.25 0 002.25 2.25h15A2.25 2.25 0 0021.75 18V9.574c0-1.067-.75-1.994-1.802-2.169a47.865 47.865 0 00-1.134-.175 2.31 2.31 0 01-1.64-1.055l-.822-1.316a2.192 2.192 0 00-1.736-1.039 48.774 48.774 0 00-5.232 0 2.192 2.192 0 00-1.736 1.039l-.821 1.316z"/><path strokeLinecap="round" strokeLinejoin="round" d="M16.5 12.75a4.5 4.5 0 11-9 0 4.5 4.5 0 019 0z"/></svg>
                          </span>
                        )}
                      </div>
                    </div>
                    <button
                      onClick={() => abrirEdit(e)}
                      title="Editar"
                      className="shrink-0 p-1.5 rounded-lg text-gray-400 hover:text-blue-500 hover:bg-blue-50 dark:hover:bg-blue-900/20 transition-colors">
                      <svg className="w-4 h-4" fill="none" stroke="currentColor" strokeWidth={1.8} viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" d="M16.862 4.487l1.687-1.688a1.875 1.875 0 112.652 2.652L10.582 16.07a4.5 4.5 0 01-1.897 1.13L6 18l.8-2.685a4.5 4.5 0 011.13-1.897l8.932-8.931zm0 0L19.5 7.125M18 14v4.75A2.25 2.25 0 0115.75 21H5.25A2.25 2.25 0 013 18.75V8.25A2.25 2.25 0 015.25 6H10"/></svg>
                    </button>
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
                    {f === 'banco' ? (
                      <span className="flex items-center justify-center gap-1.5">
                        <svg className="w-4 h-4" fill="none" stroke="currentColor" strokeWidth={1.8} viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" d="M12 21v-8.25M15.75 21v-8.25M8.25 21v-8.25M3 9l9-6 9 6m-1.5 12V10.332A48.36 48.36 0 0012 9.75c-2.551 0-5.056.2-7.5.582V21M3 21h18M12 6.75h.008v.008H12V6.75z"/></svg>
                        Banco
                      </span>
                    ) : (
                      <span className="flex items-center justify-center gap-1.5">
                        <svg className="w-4 h-4" fill="none" stroke="currentColor" strokeWidth={1.8} viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" d="M2.25 18.75a60.07 60.07 0 0115.797 2.101c.727.198 1.453-.342 1.453-1.096V18.75M3.75 4.5v.75A.75.75 0 013 6h-.75m0 0v-.375c0-.621.504-1.125 1.125-1.125H20.25M2.25 6v9m18-10.5v.75c0 .414.336.75.75.75h.75m-1.5-1.5h.375c.621 0 1.125.504 1.125 1.125v9.75c0 .621-.504 1.125-1.125 1.125h-.375m1.5-1.5H21a.75.75 0 00-.75.75v.75m0 0H3.75m0 0h-.375a1.125 1.125 0 01-1.125-1.125V15m1.5 1.5v-.75A.75.75 0 003 15h-.75M15 10.5a3 3 0 11-6 0 3 3 0 016 0zm3 0h.008v.008H18V10.5zm-12 0h.008v.008H6V10.5z"/></svg>
                        Efectivo
                      </span>
                    )}
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

            {/* A favor de: siempre visible para pago_cliente (proveedor del cliente) */}
            {form.tipo === 'pago_cliente' && (
              <div>
                <label className="label">A favor de (proveedor del cliente)</label>
                <input className="input-field" placeholder="Nombre del proveedor"
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
                <label className="label">Nro. OP</label>
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
                  <button type="button" onClick={() => { suppressLockForCamera(); fileInputRef.current?.click() }} className="btn-secondary w-full text-sm flex items-center justify-center gap-2">
                    <svg className="w-4 h-4" fill="none" stroke="currentColor" strokeWidth={1.8} viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" d="M6.827 6.175A2.31 2.31 0 015.186 7.23c-.38.054-.757.112-1.134.175C2.999 7.58 2.25 8.507 2.25 9.574V18a2.25 2.25 0 002.25 2.25h15A2.25 2.25 0 0021.75 18V9.574c0-1.067-.75-1.994-1.802-2.169a47.865 47.865 0 00-1.134-.175 2.31 2.31 0 01-1.64-1.055l-.822-1.316a2.192 2.192 0 00-1.736-1.039 48.774 48.774 0 00-5.232 0 2.192 2.192 0 00-1.736 1.039l-.821 1.316z"/><path strokeLinecap="round" strokeLinejoin="round" d="M16.5 12.75a4.5 4.5 0 11-9 0 4.5 4.5 0 019 0z"/></svg>
                    Sacar / subir foto
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

      {/* ── MODAL EDITAR ── */}
      {editItem && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60" onClick={e => { if (e.target === e.currentTarget) setEditItem(null) }}>
          <div className="w-full max-w-sm bg-white dark:bg-ml-dark-card rounded-2xl shadow-xl p-5 space-y-4">
            <h2 className="text-base font-bold dark:text-white">Editar pago</h2>

            <div>
              <label className="label">Importe</label>
              <input
                type="number"
                className="input-field font-mono text-lg"
                value={editForm.monto}
                onChange={e => setEditForm(p => ({ ...p, monto: e.target.value }))}
                autoFocus
              />
            </div>

            <div>
              <label className="label">Fecha</label>
              <input
                type="date"
                className="input-field"
                value={editForm.fecha}
                onChange={e => setEditForm(p => ({ ...p, fecha: e.target.value }))}
              />
            </div>

            <div>
              <label className="label">{editItem.tipo === 'pago_cliente' ? 'A favor de' : 'Proveedor / Beneficiario'}</label>
              <input
                className="input-field"
                placeholder="Nombre"
                value={editForm.beneficiario}
                onChange={e => setEditForm(p => ({ ...p, beneficiario: e.target.value }))}
              />
            </div>

            <div>
              <label className="label">Nro. OP / Referencia</label>
              <input
                className="input-field"
                placeholder="opcional"
                value={editForm.referencia}
                onChange={e => setEditForm(p => ({ ...p, referencia: e.target.value }))}
              />
            </div>

            <div>
              <label className="label">Concepto / notas</label>
              <input
                className="input-field"
                placeholder="opcional"
                value={editForm.concepto}
                onChange={e => setEditForm(p => ({ ...p, concepto: e.target.value }))}
              />
            </div>

            {editMsg && (
              <div className="px-3 py-2 bg-red-50 dark:bg-red-900/20 text-red-600 dark:text-red-400 rounded-lg text-sm">{editMsg}</div>
            )}

            <div className="flex gap-2 pt-1">
              <button onClick={() => setEditItem(null)} className="btn-secondary flex-1">
                Cancelar
              </button>
              <button onClick={guardarEdit} disabled={editSaving} className="btn-yellow flex-1">
                {editSaving ? 'Guardando...' : 'Guardar'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ── ÉXITO ── */}
      {vista === 'nuevo' && step === 'exito' && resultado && (
        <div className="space-y-4">
          <div className="card text-center py-6">
            <div className="flex items-center justify-center w-16 h-16 mx-auto mb-3 rounded-full bg-green-100 dark:bg-green-900/30">
              <svg className="w-9 h-9 text-green-600 dark:text-green-400" fill="none" stroke="currentColor" strokeWidth={1.8} viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" d="M4.5 12.75l6 6 9-13.5"/></svg>
            </div>
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
            <svg className="w-5 h-5" fill="none" stroke="currentColor" strokeWidth={1.8} viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5m-13.5-9L12 3m0 0l4.5 4.5M12 3v13.5"/></svg>
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
