import React, { useEffect, useState, useCallback, useRef } from 'react'
import { useSearchParams, useNavigate } from 'react-router-dom'
import { apiClient } from '@/services/api'
import { confirmDialog } from '@/store/confirm'
import { useOrgStore } from '@/store/org'
import { useAuthStore } from '@/store/auth'
import { useLockStore } from '@/store/lock'

// Evita que abrir el menú nativo de compartir dispare el bloqueo por PIN/huella.
function suppressLockForShare() {
  try { useLockStore.getState().suppressLock(20000) } catch { /* noop */ }
}

const fmt = (n: number) =>
  new Intl.NumberFormat('es-AR', { style: 'currency', currency: 'ARS', minimumFractionDigits: 2 }).format(n)

const fmtDate = (d?: string | null) =>
  d ? new Date(d + (d.includes('T') ? '' : 'T00:00:00')).toLocaleDateString('es-AR') : '—'

interface Cheque {
  id: number
  cliente_id: number | null
  cliente_nombre: string | null
  numero: string | null
  banco_origen: string | null
  librador: string | null
  titular: string | null
  portador_id: number | null
  portador_nombre: string | null
  codigo_postal: string | null
  local_interior: string | null
  monto: number
  comision: number
  porcentaje_comision: number | null
  fecha_emision: string | null
  fecha_deposito: string | null
  fecha_acred: string | null
  fecha_rechazo: string | null
  fisico: boolean | null
  fecha_devolucion: string | null
  estado: 'pendiente' | 'registrado' | 'depositado' | 'acreditado' | 'rechazado' | 'anulado'
  notas: string | null
  tiene_foto: boolean
  banco_cuenta_id: number | null
  created_at: string
}

interface ClienteOpt { id: number; nombre: string; porcentaje_comision: number | null; porcentaje_comision_local: number | null; porcentaje_comision_interior: number | null; cuenta_contable_id: number | null }
interface PortadorOpt { id: number; nombre: string }
interface BancoCuenta { id: number; codigo: string; nombre: string }

interface DepositoResumen {
  total: number
  por_cliente: { cliente: string; total: number; count: number }[]
  por_local_interior: { tipo: string; total: number; count: number }[]
}

interface DepositoData {
  fecha: string
  items: Cheque[]
  resumen: DepositoResumen
}

const ESTADO_BADGE: Record<string, string> = {
  pendiente:  'bg-yellow-500/15 text-yellow-400',
  registrado: 'bg-yellow-500/15 text-yellow-400',
  depositado: 'bg-orange-500/15 text-orange-400',
  acreditado: 'bg-green-500/15 text-green-400',
  rechazado:  'bg-red-500/15 text-red-400',
  anulado:    'bg-gray-500/15 text-gray-400',
}
const ESTADO_LABEL: Record<string, string> = {
  pendiente: 'Registrado', registrado: 'Registrado', depositado: 'Depositado',
  acreditado: 'Acreditado', rechazado: 'Rechazado', anulado: 'Anulado',
}
const esRegistrado = (estado: string) => estado === 'registrado' || estado === 'pendiente'

const emptyForm = () => ({
  cliente_id:          null as number | null,
  portador_id:         null as number | null,
  numero:              '',
  banco_origen:        '',
  librador:            '',
  codigo_postal:       '',
  local_interior:      '',
  monto:               0,
  comision:            0,
  porcentaje_comision: null as number | null,
  fecha_emision:       '',
  fecha_deposito:      '',
  notas:               '',
})

type FormState = ReturnType<typeof emptyForm>

const inputClass = "w-full bg-white/5 border border-white/10 rounded px-3 py-1.5 text-sm text-gray-100 focus:outline-none focus:border-indigo-500"

const computeLI = (cp: string): string => {
  if (!cp) return ''
  const n = parseInt(cp.replace(/\D/g, ''), 10)
  if (isNaN(n)) return ''
  return n < 2000 ? 'local' : 'interior'
}

// % de comisión que corresponde a un cliente según local/interior, con
// fallback al % general. Devuelve null si el cliente no tiene ninguno.
const pctParaCliente = (cli: ClienteOpt | null | undefined, li: string): number | null => {
  if (!cli) return null
  if (li === 'local'    && cli.porcentaje_comision_local    != null) return cli.porcentaje_comision_local
  if (li === 'interior' && cli.porcentaje_comision_interior != null) return cli.porcentaje_comision_interior
  return cli.porcentaje_comision ?? null
}

const LiBadge: React.FC<{ value: string | null }> = ({ value }) => {
  if (!value) return <span className="text-gray-600">—</span>
  return (
    <span className={`px-1.5 py-0.5 rounded text-xs font-medium ${
      value === 'local' ? 'bg-blue-500/15 text-blue-400' : 'bg-orange-500/15 text-orange-400'
    }`}>
      {value === 'local' ? 'L' : 'I'}
    </span>
  )
}

const toBase64 = (file: File): Promise<string> =>
  new Promise((resolve, reject) => {
    const reader = new FileReader()
    reader.onload = () => resolve(reader.result as string)
    reader.onerror = reject
    reader.readAsDataURL(file)
  })

const compressScanner = (src: string, maxPx: number, quality: number): Promise<string> =>
  new Promise(resolve => {
    const img = new Image()
    img.onload = () => {
      let w = img.width, h = img.height
      if (w > maxPx) { h = Math.round(h * maxPx / w); w = maxPx }
      if (h > maxPx) { w = Math.round(w * maxPx / h); h = maxPx }
      const canvas = document.createElement('canvas')
      canvas.width = w; canvas.height = h
      const ctx = canvas.getContext('2d')!
      ctx.fillStyle = '#ffffff'; ctx.fillRect(0, 0, w, h)  // fondo blanco → evita negro en JPEG
      ctx.filter = 'grayscale(1) contrast(1.4) brightness(1.1)'
      ctx.drawImage(img, 0, 0, w, h)
      resolve(canvas.toDataURL('image/jpeg', quality))
    }
    img.onerror = () => resolve(src)
    img.src = src
  })

const shareChequePdf = async (c: Cheque, fotoB64: string): Promise<boolean> => {
  try {
    const { jsPDF } = await import('jspdf')
    const pdf = new jsPDF({ orientation: 'portrait', unit: 'mm', format: 'a4' })
    const nombre = c.cliente_nombre || c.librador || c.titular || 'Sin nombre'
    pdf.setFont('helvetica', 'bold'); pdf.setFontSize(13)
    pdf.text('COMPROBANTE DE CHEQUE', 105, 16, { align: 'center' })
    pdf.setFont('helvetica', 'normal'); pdf.setFontSize(9)
    pdf.text(`N° ${c.numero || '—'} · ${c.banco_origen || '—'}`, 105, 23, { align: 'center' })
    pdf.addImage(fotoB64, 'JPEG', 10, 28, 190, 128)
    pdf.setDrawColor(180, 180, 180); pdf.line(10, 162, 200, 162)
    pdf.setFontSize(10)
    const rows = [
      ['Cliente:', nombre], ['Importe:', fmt(c.monto)],
      ['Emisión:', fmtDate(c.fecha_emision)], ['Vencimiento:', fmtDate(c.fecha_deposito)],
      ['Estado:', c.estado], ['Generado:', new Date().toLocaleDateString('es-AR')],
    ]
    rows.forEach(([label, value], i) => {
      const y = 170 + i * 8
      pdf.setFont('helvetica', 'bold'); pdf.text(label, 12, y)
      pdf.setFont('helvetica', 'normal'); pdf.text(value, 52, y)
    })
    const blob = pdf.output('blob')
    const file = new File([blob], `Cheque_${c.numero || c.id}.pdf`, { type: 'application/pdf' })
    if (navigator.share && navigator.canShare?.({ files: [file] })) {
      suppressLockForShare()
      await navigator.share({ title: `Cheque ${c.numero || ''}`, files: [file] })
      return true
    }
  } catch (e: any) {
    if (e?.name === 'AbortError') return true  // el usuario cerró el menú de compartir
  }
  return false
}

const PortadorSelector: React.FC<{
  portadores: PortadorOpt[]
  value: number | null
  onChange: (id: number | null) => void
  onAdd: (nombre: string) => Promise<void>
}> = ({ portadores, value, onChange, onAdd }) => {
  const [adding, setAdding]     = useState(false)
  const [newNombre, setNewNombre] = useState('')
  const [saving, setSaving]     = useState(false)
  const inputRef                = useRef<HTMLInputElement>(null)

  const handleAdd = async () => {
    const n = newNombre.trim(); if (!n) return
    setSaving(true)
    await onAdd(n)
    setNewNombre(''); setAdding(false); setSaving(false)
  }

  return (
    <div>
      <label className="block text-xs text-gray-400 mb-1">Portador (quien deposita)</label>
      {!adding ? (
        <div className="flex gap-1.5">
          <select value={value ?? ''} onChange={e => onChange(e.target.value ? parseInt(e.target.value) : null)}
            className={`${inputClass} flex-1`}>
            <option value="">Sin portador</option>
            {portadores.map(p => <option key={p.id} value={p.id}>{p.nombre}</option>)}
          </select>
          <button type="button"
            onClick={() => { setAdding(true); setTimeout(() => inputRef.current?.focus(), 50) }}
            className="px-2.5 py-1.5 bg-white/8 hover:bg-white/12 text-gray-300 text-sm rounded border border-white/10 transition-colors"
            title="Agregar portador">+</button>
        </div>
      ) : (
        <div className="flex gap-1.5">
          <input ref={inputRef} value={newNombre} onChange={e => setNewNombre(e.target.value)}
            onKeyDown={e => {
              if (e.key === 'Enter') handleAdd()
              if (e.key === 'Escape') { setAdding(false); setNewNombre('') }
            }}
            placeholder="Nombre del portador" className={`${inputClass} flex-1`} />
          <button type="button" onClick={handleAdd} disabled={saving || !newNombre.trim()}
            className="px-2 py-1.5 bg-indigo-600 hover:bg-indigo-500 text-white text-sm rounded disabled:opacity-50 transition-colors">✓</button>
          <button type="button" onClick={() => { setAdding(false); setNewNombre('') }}
            className="px-2 py-1.5 bg-white/8 hover:bg-white/12 text-gray-400 text-sm rounded transition-colors">✕</button>
        </div>
      )}
    </div>
  )
}

const ClienteSelector: React.FC<{
  clientes: ClienteOpt[]
  value: number | null
  onChangeCliente: (id: number | null, cli: ClienteOpt | null) => void
  onAdd: (nombre: string) => Promise<void>
}> = ({ clientes, value, onChangeCliente, onAdd }) => {
  const [adding, setAdding]     = useState(false)
  const [newNombre, setNewNombre] = useState('')
  const [saving, setSaving]     = useState(false)
  const inputRef                = useRef<HTMLInputElement>(null)

  const handleAdd = async () => {
    const n = newNombre.trim(); if (!n) return
    setSaving(true)
    await onAdd(n)
    setNewNombre(''); setAdding(false); setSaving(false)
  }

  return (
    <div>
      <label className="block text-xs text-gray-400 mb-1">Cliente</label>
      {!adding ? (
        <div className="flex gap-1.5">
          <select value={value ?? ''}
            onChange={e => {
              const id = e.target.value ? parseInt(e.target.value) : null
              const cli = clientes.find(c => c.id === id) ?? null
              onChangeCliente(id, cli)
            }}
            className={`${inputClass} flex-1`}>
            <option value="">Sin cliente</option>
            {clientes.map(c => <option key={c.id} value={c.id}>{c.nombre}</option>)}
          </select>
          <button type="button"
            onClick={() => { setAdding(true); setTimeout(() => inputRef.current?.focus(), 50) }}
            className="px-2.5 py-1.5 bg-white/8 hover:bg-white/12 text-gray-300 text-sm rounded border border-white/10 transition-colors"
            title="Agregar cliente">+</button>
        </div>
      ) : (
        <div className="flex gap-1.5">
          <input ref={inputRef} value={newNombre} onChange={e => setNewNombre(e.target.value)}
            onKeyDown={e => {
              if (e.key === 'Enter') handleAdd()
              if (e.key === 'Escape') { setAdding(false); setNewNombre('') }
            }}
            placeholder="Nombre del cliente" className={`${inputClass} flex-1`} />
          <button type="button" onClick={handleAdd} disabled={saving || !newNombre.trim()}
            className="px-2 py-1.5 bg-indigo-600 hover:bg-indigo-500 text-white text-sm rounded disabled:opacity-50 transition-colors">✓</button>
          <button type="button" onClick={() => { setAdding(false); setNewNombre('') }}
            className="px-2 py-1.5 bg-white/8 hover:bg-white/12 text-gray-400 text-sm rounded transition-colors">✕</button>
        </div>
      )}
    </div>
  )
}

export const Cheques: React.FC = () => {
  const { activeOrgId } = useOrgStore()
  const canDelete = useAuthStore(s => s.hasPermission('delete_records'))

  const [tab, setTab] = useState<'todos' | 'deposito' | 'rechazados'>('todos')

  // Main list
  const [cheques, setCheques]   = useState<Cheque[]>([])
  const [total, setTotal]       = useState(0)
  const [clientes, setClientes] = useState<ClienteOpt[]>([])
  const [portadores, setPortadores] = useState<PortadorOpt[]>([])
  const [loading, setLoading]   = useState(true)
  const [msg, setMsg]           = useState('')

  // Filters (Todos tab)
  const [filtroEstado, setFiltroEstado]   = useState('')
  const [filtroCliente, setFiltroCliente] = useState('')
  const [filtroDesde, setFiltroDesde]     = useState('')
  const [filtroHasta, setFiltroHasta]     = useState('')
  const [skip, setSkip]                   = useState(0)
  const LIMIT = 50

  // Rechazados tab
  const [rechazadosList, setRechazadosList]     = useState<Cheque[]>([])
  const [rechazadosLoading, setRechazadosLoading] = useState(false)

  // Deposito tab
  const [depositoFechas, setDepositoFechas]   = useState<string[]>([])
  const [depositoFecha, setDepositoFecha]     = useState('')
  const [depositoData, setDepositoData]       = useState<DepositoData | null>(null)
  const [depositoLoading, setDepositoLoading] = useState(false)
  const [exportandoDeposito, setExportandoDeposito] = useState(false)

  // Form modal
  const [showForm, setShowForm] = useState(false)
  const [formData, setFormData] = useState<FormState>(emptyForm())
  const [formFoto, setFormFoto] = useState<string | null>(null)
  const [saving, setSaving]     = useState(false)
  const fotoInputRef            = useRef<HTMLInputElement>(null)

  // Banco accounts for acreditación
  const [bancoCuentas, setBancoCuentas] = useState<BancoCuenta[]>([])

  // Action modals — individual
  const [acreditarId, setAcreditarId]     = useState<number | null>(null)
  const [acreditarFecha, setAcreditarFecha] = useState('')
  const [acreditarBancoId, setAcreditarBancoId] = useState<number | ''>('')
  const [rechazarId, setRechazarId]       = useState<number | null>(null)
  const [rechazarData, setRechazarData]   = useState({ fecha_rechazo: '', gastos_bancarios: '', fisico: false, fecha_devolucion: '' })
  const [actioning, setActioning]         = useState(false)

  // Acreditación masiva (tab Por depósito)
  const [selectedCheques, setSelectedCheques] = useState<Set<number>>(new Set())
  const [acredMasivoBanco, setAcredMasivoBanco] = useState<number | ''>('')
  const [acredMasivoFecha, setAcredMasivoFecha] = useState('')
  const [acreditandoMasivo, setAcreditandoMasivo] = useState(false)

  // Photo viewer
  const [verFotoId, setVerFotoId]     = useState<number | null>(null)
  const [fotoData, setFotoData]       = useState<string | null>(null)
  const [loadingFoto, setLoadingFoto] = useState(false)

  // Import Excel
  const [importando, setImportando] = useState(false)
  const importRef                   = useRef<HTMLInputElement>(null)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const params: Record<string, string | number> = { skip: String(skip), limit: String(LIMIT) }
      if (filtroEstado)  params.estado     = filtroEstado
      if (filtroCliente) params.cliente_id = filtroCliente
      if (filtroDesde)   params.desde      = filtroDesde
      if (filtroHasta)   params.hasta      = filtroHasta
      if (activeOrgId)   params.org_id     = activeOrgId
      const res = await apiClient.client.get('/cheques', { params })
      setCheques(res.data.items); setTotal(res.data.total)
    } catch { setMsg('Error al cargar cheques') }
    finally { setLoading(false) }
  }, [filtroEstado, filtroCliente, filtroDesde, filtroHasta, skip, activeOrgId])

  useEffect(() => { load() }, [load])

  // Rechazados tab load
  useEffect(() => {
    if (tab !== 'rechazados') return
    setRechazadosLoading(true)
    const params: Record<string, string | number> = { estado: 'rechazado', limit: '500' }
    if (activeOrgId) params.org_id = activeOrgId
    apiClient.client.get('/cheques', { params })
      .then(r => setRechazadosList(r.data.items))
      .catch(() => {})
      .finally(() => setRechazadosLoading(false))
  }, [tab, activeOrgId])

  // Deposito: load available dates
  useEffect(() => {
    if (tab !== 'deposito') return
    const params: Record<string, string | number> = {}
    if (activeOrgId) params.org_id = activeOrgId
    apiClient.client.get('/cheques/deposito', { params })
      .then(r => {
        const fechas: string[] = r.data.fechas || []
        setDepositoFechas(fechas)
        setDepositoFecha(prev => prev || (fechas.length > 0 ? fechas[0] : ''))
      })
      .catch(() => {})
  }, [tab, activeOrgId])

  // Deposito: load data for selected date
  useEffect(() => {
    if (tab !== 'deposito' || !depositoFecha) return
    setDepositoLoading(true)
    const params: Record<string, string | number> = { fecha: depositoFecha }
    if (activeOrgId) params.org_id = activeOrgId
    apiClient.client.get('/cheques/deposito', { params })
      .then(r => setDepositoData(r.data))
      .catch(() => {})
      .finally(() => setDepositoLoading(false))
  }, [depositoFecha, tab, activeOrgId])

  // Portadores
  useEffect(() => {
    const params: Record<string, string | number> = {}
    if (activeOrgId) params.org_id = activeOrgId
    apiClient.client.get('/cheques/portadores', { params })
      .then(r => setPortadores(r.data))
      .catch(() => {})
  }, [activeOrgId])

  // PWA share target
  const [searchParams, setSearchParams] = useSearchParams()
  const navigate = useNavigate()
  useEffect(() => {
    if (searchParams.get('compartido') !== '1') return
    const destino = sessionStorage.getItem('compartido:destino')
    const archivosRaw = sessionStorage.getItem('compartido:archivos')
    if (destino !== 'cheque' || !archivosRaw) return
    try {
      const archivos = JSON.parse(archivosRaw) as { name: string; type: string; dataUrl: string }[]
      const imagen = archivos.find(a => a.type.startsWith('image/')) || archivos[0]
      if (imagen) { setShowForm(true); setFormData(emptyForm()); setFormFoto(imagen.dataUrl); setMsg('') }
    } catch {}
    sessionStorage.removeItem('compartido:destino'); sessionStorage.removeItem('compartido:archivos')
    sessionStorage.removeItem('compartido:titulo');  sessionStorage.removeItem('compartido:texto')
    sessionStorage.removeItem('compartido:ts')
    const sp = new URLSearchParams(searchParams); sp.delete('compartido')
    setSearchParams(sp, { replace: true })
  }, [searchParams, setSearchParams, navigate])

  // Cuentas de banco (para selector en acreditación)
  useEffect(() => {
    const params: Record<string, string | number> = {}
    if (activeOrgId) params.org_id = activeOrgId
    apiClient.client.get('/contabilidad/plan-cuentas', { params })
      .then(r => {
        const all: any[] = Array.isArray(r.data) ? r.data : (r.data?.cuentas || [])
        // IDs que son cuenta madre (tienen hijos) → no se imputan
        const parentIds = new Set(all.map((c: any) => c.parent_id).filter(Boolean))
        const bancos = all.filter((c: any) =>
          typeof c.nombre === 'string' &&
          c.nombre.toLowerCase().startsWith('banco') &&
          !parentIds.has(c.id)  // solo cuentas hoja
        )
        setBancoCuentas(bancos.map((c: any) => ({ id: c.id, codigo: c.codigo, nombre: c.nombre })))
      })
      .catch(() => {})
  }, [activeOrgId])

  // Clientes
  useEffect(() => {
    const params: Record<string, number> = {}
    if (activeOrgId) params.org_id = activeOrgId
    apiClient.client.get('/clientes/archivos', { params }).then(r => {
      const orgs: any[] = r.data?.organizaciones || []
      const list: ClienteOpt[] = []
      orgs.forEach(org => (org.clientes || []).forEach((c: any) =>
        list.push({ id: c.id, nombre: c.nombre, porcentaje_comision: c.porcentaje_comision ?? null, porcentaje_comision_local: c.porcentaje_comision_local ?? null, porcentaje_comision_interior: c.porcentaje_comision_interior ?? null, cuenta_contable_id: c.cuenta_contable_id ?? null })))
      setClientes(list)
    }).catch(() => {})
  }, [activeOrgId])

  const handleAddPortador = async (nombre: string) => {
    const params: Record<string, string | number> = {}
    if (activeOrgId) params.org_id = activeOrgId
    const res = await apiClient.client.post('/cheques/portadores', { nombre }, { params })
    const nuevo = res.data as PortadorOpt
    setPortadores(prev => [...prev, nuevo])
    setFormData(p => ({ ...p, portador_id: nuevo.id }))
  }

  const handleAddCliente = async (nombre: string) => {
    const payload: Record<string, string | number> = { nombre }
    if (activeOrgId) payload.organizacion_id = activeOrgId
    const res = await apiClient.client.post('/clientes', payload)
    const nuevo: ClienteOpt = { id: res.data.id, nombre: res.data.nombre, porcentaje_comision: res.data.porcentaje_comision ?? null, porcentaje_comision_local: res.data.porcentaje_comision_local ?? null, porcentaje_comision_interior: res.data.porcentaje_comision_interior ?? null, cuenta_contable_id: res.data.cuenta_contable_id ?? null }
    setClientes(prev => [...prev, nuevo])
    setFormData(p => ({
      ...p, cliente_id: nuevo.id,
      porcentaje_comision: p.porcentaje_comision != null ? p.porcentaje_comision : pctParaCliente(nuevo, p.local_interior || computeLI(p.codigo_postal)),
    }))
  }

  const handleFotoChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]; if (!file) return
    const b64 = await toBase64(file)
    const compressed = await compressScanner(b64, 1200, 0.82)
    setFormFoto(compressed)
    try {
      const small = await compressScanner(b64, 768, 0.7)
      const res = await apiClient.client.post('/agente/ocr-cheque', { imagen_base64: small })
      const d = res.data
      setFormData(prev => ({
        ...prev,
        numero:         prev.numero        || (d.numero        != null ? String(d.numero)       : prev.numero),
        banco_origen:   prev.banco_origen  || (d.banco_origen  != null ? String(d.banco_origen) : prev.banco_origen),
        librador:       prev.librador      || (d.librador      != null ? String(d.librador)     : prev.librador),
        monto:          (prev.monto ?? 0) > 0 ? prev.monto : (d.monto ?? prev.monto),
        fecha_emision:  prev.fecha_emision  || (d.fecha_emision  != null ? String(d.fecha_emision)  : prev.fecha_emision),
        fecha_deposito: prev.fecha_deposito || (d.fecha_deposito != null ? String(d.fecha_deposito) : prev.fecha_deposito),
      }))
    } catch { /* OCR no disponible */ }
  }

  const handleCreate = async () => {
    if (!formData.monto || formData.monto <= 0) { setMsg('El monto es requerido'); return }
    setSaving(true); setMsg('')
    try {
      const li = formData.local_interior || computeLI(formData.codigo_postal)
      const res = await apiClient.client.post('/cheques', {
        cliente_id:          formData.cliente_id || null,
        portador_id:         formData.portador_id || null,
        numero:              formData.numero || null,
        banco_origen:        formData.banco_origen || null,
        librador:            formData.librador || null,
        codigo_postal:       formData.codigo_postal || null,
        local_interior:      li || null,
        monto:               formData.monto,
        comision:            formData.comision || 0,
        porcentaje_comision: formData.porcentaje_comision || null,
        fecha_emision:       formData.fecha_emision || null,
        fecha_deposito:      formData.fecha_deposito || null,
        notas:               formData.notas || null,
      })
      if (formFoto && res.data.id)
        await apiClient.client.post(`/cheques/${res.data.id}/foto`, { foto_base64: formFoto })
      setShowForm(false); setFormData(emptyForm()); setFormFoto(null); load()
    } catch (e: any) { setMsg(e?.response?.data?.detail || 'Error al guardar') }
    finally { setSaving(false) }
  }

  const handleAcreditar = async () => {
    if (!acreditarId || !acreditarBancoId) return
    setActioning(true)
    try {
      await apiClient.client.post(`/cheques/${acreditarId}/acreditar`, {
        fecha_acred:     acreditarFecha || null,
        banco_cuenta_id: acreditarBancoId,
      })
      setAcreditarId(null); setAcreditarFecha(''); setAcreditarBancoId('')
      load()
    } catch (e: any) { setMsg(e?.response?.data?.detail || 'Error') }
    finally { setActioning(false) }
  }

  const handleAcreditarMasivo = async () => {
    if (!acredMasivoBanco || selectedCheques.size === 0) return
    setAcreditandoMasivo(true); setMsg('')
    try {
      const params: Record<string, string | number> = {}
      if (activeOrgId) params.org_id = activeOrgId
      const res = await apiClient.client.post('/cheques/acreditar', {
        cheque_ids:      Array.from(selectedCheques),
        banco_cuenta_id: acredMasivoBanco,
        fecha_acred:     acredMasivoFecha || null,
      }, { params })
      const { acreditados, total, detalle } = res.data
      const errores = detalle.filter((d: any) => !d.ok)
      setMsg(`✓ ${acreditados}/${total} acreditados${errores.length ? ` · ${errores.length} error(es)` : ''}`)
      setSelectedCheques(new Set()); setAcredMasivoBanco(''); setAcredMasivoFecha('')
      // reload deposito data
      if (depositoFecha) {
        const p: Record<string, string | number> = { fecha: depositoFecha }
        if (activeOrgId) p.org_id = activeOrgId
        apiClient.client.get('/cheques/deposito', { params: p }).then(r => setDepositoData(r.data)).catch(() => {})
      }
    } catch (e: any) { setMsg(e?.response?.data?.detail || 'Error al acreditar') }
    finally { setAcreditandoMasivo(false) }
  }

  const handleRechazar = async () => {
    if (!rechazarId) return; setActioning(true)
    try {
      await apiClient.client.post(`/cheques/${rechazarId}/rechazar`, {
        fecha_rechazo:    rechazarData.fecha_rechazo || null,
        gastos_bancarios: parseFloat(rechazarData.gastos_bancarios) || 0,
        fisico:           rechazarData.fisico,
        fecha_devolucion: rechazarData.fecha_devolucion || null,
      })
      setRechazarId(null)
      setRechazarData({ fecha_rechazo: '', gastos_bancarios: '', fisico: false, fecha_devolucion: '' })
      load()
      if (tab === 'rechazados') {
        const params: Record<string, string | number> = { estado: 'rechazado', limit: '500' }
        if (activeOrgId) params.org_id = activeOrgId
        apiClient.client.get('/cheques', { params }).then(r => setRechazadosList(r.data.items)).catch(() => {})
      }
    } catch (e: any) { setMsg(e?.response?.data?.detail || 'Error') }
    finally { setActioning(false) }
  }

  const handleDelete = async (id: number) => {
    if (!await confirmDialog({ title: 'Eliminar cheque', message: '¿Eliminar este cheque?', confirmLabel: 'Eliminar', danger: true })) return
    try { await apiClient.client.delete(`/cheques/${id}`); load() }
    catch (e: any) { setMsg(e?.response?.data?.detail || 'Error al eliminar') }
  }

  const handleVerFoto = async (id: number) => {
    setVerFotoId(id); setFotoData(null); setLoadingFoto(true)
    try { const res = await apiClient.client.get(`/cheques/${id}/foto`); setFotoData(res.data.foto_base64) }
    catch { setFotoData(null) }
    finally { setLoadingFoto(false) }
  }

  const handleCompartir = async (c: Cheque) => {
    const nombre = c.cliente_nombre || c.librador || c.titular || 'Cheque'
    const texto = `Cheque registrado%0A• Cliente: ${nombre}%0A• Importe: ${fmt(c.monto)}%0A• Banco: ${c.banco_origen || '—'}%0A• Nro: ${c.numero || '—'}%0A• Vencimiento: ${fmtDate(c.fecha_deposito)}`
    if (c.tiene_foto) {
      try {
        const res = await apiClient.client.get(`/cheques/${c.id}/foto`)
        const fotoB64 = res.data.foto_base64
        if (fotoB64) {
          const sharedPdf = await shareChequePdf(c, fotoB64); if (sharedPdf) return
          if (navigator.share && navigator.canShare) {
            const blob = await fetch(fotoB64).then(r => r.blob())
            const file = new File([blob], `Cheque_${nombre}.jpg`, { type: 'image/jpeg' })
            if (navigator.canShare({ files: [file] })) {
              suppressLockForShare()
              await navigator.share({ title: `Cheque - ${nombre} - ${fmt(c.monto)}`, files: [file] }); return
            }
          }
        }
      } catch (e: any) {
        if (e?.name === 'AbortError') return  // el usuario cerró el menú de compartir
      }
    }
    if (navigator.share) {
      try { suppressLockForShare(); await navigator.share({ title: `Cheque - ${nombre}`, text: decodeURIComponent(texto) }); return } catch {}
    }
    window.open(`whatsapp://send?text=${texto}`, '_blank')
  }

  const handleImportExcel = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]; if (!file) return
    setImportando(true); setMsg('')
    const fd = new FormData(); fd.append('file', file)
    try {
      const res = await apiClient.client.post('/cheques/importar', fd, { headers: { 'Content-Type': 'multipart/form-data' } })
      const { importados, errores } = res.data
      setMsg(`✓ ${importados} cheque${importados !== 1 ? 's' : ''} importado${importados !== 1 ? 's' : ''}${errores.length ? ` · ${errores.length} error(es)` : ''}`)
      load()
    } catch (e: any) { setMsg(e?.response?.data?.detail || 'Error al importar') }
    finally { setImportando(false); if (importRef.current) importRef.current.value = '' }
  }

  const handleExportDeposito = async () => {
    if (!depositoFecha) return; setExportandoDeposito(true)
    try {
      const params: Record<string, string | number> = { fecha: depositoFecha }
      if (activeOrgId) params.org_id = activeOrgId
      const res = await apiClient.client.get('/cheques/deposito/exportar', { params, responseType: 'blob' })
      const url = URL.createObjectURL(res.data)
      const a = document.createElement('a'); a.href = url; a.download = `cheques_deposito_${depositoFecha}.xlsx`; a.click()
      URL.revokeObjectURL(url)
    } catch { setMsg('Error al exportar') }
    finally { setExportandoDeposito(false) }
  }

  const pendientes = cheques.filter(c => esRegistrado(c.estado) || c.estado === 'depositado')
  const totalPend  = pendientes.reduce((s, c) => s + c.monto, 0)
  const totalAcred = cheques.filter(c => c.estado === 'acreditado').reduce((s, c) => s + c.monto, 0)
  const totalRech  = cheques.filter(c => c.estado === 'rechazado').reduce((s, c) => s + c.monto, 0)

  return (
    <div className="p-4 md:p-6 max-w-7xl mx-auto space-y-5">
      {/* Header */}
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-xl font-semibold text-gray-100">Cheques</h1>
          <p className="text-xs text-gray-500 mt-0.5">Registro y seguimiento de cheques de terceros</p>
        </div>
        <div className="flex gap-2">
          <input ref={importRef} type="file" accept=".xlsx,.xls" className="hidden" onChange={handleImportExcel} />
          <button onClick={() => importRef.current?.click()} disabled={importando}
            className="px-3 py-1.5 bg-white/8 hover:bg-white/12 text-gray-300 text-sm rounded-lg transition-colors disabled:opacity-50">
            {importando ? 'Importando…' : '↑ Importar Excel'}
          </button>
          <button onClick={() => { setShowForm(true); setFormData(emptyForm()); setFormFoto(null); setMsg('') }}
            className="px-3 py-1.5 bg-indigo-600 hover:bg-indigo-500 text-white text-sm rounded-lg transition-colors">
            + Nuevo cheque
          </button>
        </div>
      </div>

      {msg && (
        <div className={`text-sm rounded-lg px-3 py-2 border ${msg.startsWith('✓') ? 'text-green-400 bg-green-500/10 border-green-500/20' : 'text-red-400 bg-red-500/10 border-red-500/20'}`}>
          {msg}
        </div>
      )}

      {/* Stats */}
      <div className="grid grid-cols-3 gap-3">
        {[
          { label: 'Pendientes',  value: fmt(totalPend),  sub: `${pendientes.length} cheq.`, color: 'text-yellow-400' },
          { label: 'Acreditados', value: fmt(totalAcred), sub: 'en el listado',               color: 'text-green-400'  },
          { label: 'Rechazados',  value: fmt(totalRech),  sub: 'en el listado',               color: 'text-red-400'    },
        ].map(s => (
          <div key={s.label} className="bg-white/3 border border-white/8 rounded-xl p-3">
            <p className="text-xs text-gray-500">{s.label}</p>
            <p className={`text-base font-semibold mt-1 ${s.color}`}>{s.value}</p>
            <p className="text-xs text-gray-600 mt-0.5">{s.sub}</p>
          </div>
        ))}
      </div>

      {/* Tabs */}
      <div className="flex gap-1 border-b border-white/8">
        {(['todos', 'deposito', 'rechazados'] as const).map(t => (
          <button key={t} onClick={() => setTab(t)}
            className={`px-4 py-2 text-sm font-medium transition-colors border-b-2 -mb-px ${
              tab === t ? 'border-indigo-500 text-indigo-400' : 'border-transparent text-gray-500 hover:text-gray-300'
            }`}>
            {t === 'todos' ? 'Todos' : t === 'deposito' ? 'Por depósito' : 'Rechazados'}
          </button>
        ))}
      </div>

      {/* ═══ TAB: TODOS ═══ */}
      {tab === 'todos' && (
        <>
          <div className="flex flex-wrap gap-2">
            <select value={filtroEstado} onChange={e => { setFiltroEstado(e.target.value); setSkip(0) }}
              className="bg-white/5 border border-white/10 rounded-lg px-3 py-1.5 text-sm text-gray-200 focus:outline-none">
              <option value="">Todos los estados</option>
              <option value="registrado">Registrado</option>
              <option value="depositado">Depositado</option>
              <option value="acreditado">Acreditado</option>
              <option value="rechazado">Rechazado</option>
            </select>
            <select value={filtroCliente} onChange={e => { setFiltroCliente(e.target.value); setSkip(0) }}
              className="bg-white/5 border border-white/10 rounded-lg px-3 py-1.5 text-sm text-gray-200 focus:outline-none">
              <option value="">Todos los clientes</option>
              {clientes.map(c => <option key={c.id} value={c.id}>{c.nombre}</option>)}
            </select>
            <input type="date" value={filtroDesde} onChange={e => { setFiltroDesde(e.target.value); setSkip(0) }}
              className="bg-white/5 border border-white/10 rounded-lg px-3 py-1.5 text-sm text-gray-200 focus:outline-none" />
            <input type="date" value={filtroHasta} onChange={e => { setFiltroHasta(e.target.value); setSkip(0) }}
              className="bg-white/5 border border-white/10 rounded-lg px-3 py-1.5 text-sm text-gray-200 focus:outline-none" />
            {(filtroEstado || filtroCliente || filtroDesde || filtroHasta) && (
              <button onClick={() => { setFiltroEstado(''); setFiltroCliente(''); setFiltroDesde(''); setFiltroHasta(''); setSkip(0) }}
                className="text-xs text-gray-400 hover:text-gray-200 px-2">Limpiar</button>
            )}
          </div>

          <div className="rounded-xl overflow-hidden border border-white/8">
            <div className="overflow-x-auto">
              <table className="w-full text-xs min-w-[860px]">
                <thead>
                  <tr className="bg-white/4 text-left text-gray-400">
                    <th className="px-3 py-2 font-medium">F. Depósito</th>
                    <th className="px-3 py-2 font-medium">Cliente</th>
                    <th className="px-3 py-2 font-medium">Librador</th>
                    <th className="px-3 py-2 font-medium">Portador</th>
                    <th className="px-3 py-2 font-medium">Banco</th>
                    <th className="px-3 py-2 font-medium">N° Cheque</th>
                    <th className="px-3 py-2 font-medium">CP</th>
                    <th className="px-3 py-2 font-medium">L/I</th>
                    <th className="px-3 py-2 font-medium text-right">Monto</th>
                    <th className="px-3 py-2 font-medium text-right">Comisión</th>
                    <th className="px-3 py-2 font-medium">Estado</th>
                    <th className="px-3 py-2 font-medium">Acred.</th>
                    <th className="px-3 py-2 font-medium">Acciones</th>
                  </tr>
                </thead>
                <tbody>
                  {loading ? (
                    <tr><td colSpan={13} className="text-center py-8 text-gray-500">Cargando…</td></tr>
                  ) : cheques.length === 0 ? (
                    <tr><td colSpan={13} className="text-center py-8 text-gray-500">Sin cheques registrados</td></tr>
                  ) : cheques.map((c, i) => (
                    <tr key={c.id} className={`border-t border-white/5 hover:bg-white/2 ${i % 2 === 0 ? '' : 'bg-white/1'}`}>
                      <td className="px-3 py-2 text-gray-300 whitespace-nowrap">{fmtDate(c.fecha_deposito)}</td>
                      <td className="px-3 py-2 text-gray-200">{c.cliente_nombre || <span className="text-gray-500">—</span>}</td>
                      <td className="px-3 py-2 text-gray-300 max-w-[110px] truncate" title={c.librador || c.titular || ''}>{c.librador || c.titular || '—'}</td>
                      <td className="px-3 py-2 text-gray-400">{c.portador_nombre || '—'}</td>
                      <td className="px-3 py-2 text-gray-400">{c.banco_origen || '—'}</td>
                      <td className="px-3 py-2 text-gray-400">{c.numero || '—'}</td>
                      <td className="px-3 py-2 text-gray-400">{c.codigo_postal || '—'}</td>
                      <td className="px-3 py-2"><LiBadge value={c.local_interior} /></td>
                      <td className="px-3 py-2 text-right font-mono text-gray-100">{fmt(c.monto)}</td>
                      <td className="px-3 py-2 text-right font-mono text-gray-400">{c.comision > 0 ? fmt(c.comision) : '—'}</td>
                      <td className="px-3 py-2">
                        <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${ESTADO_BADGE[c.estado] || ''}`}>
                          {ESTADO_LABEL[c.estado] || c.estado}
                        </span>
                      </td>
                      <td className="px-3 py-2 text-gray-400 whitespace-nowrap">{fmtDate(c.fecha_acred)}</td>
                      <td className="px-3 py-2">
                        <div className="flex gap-1">
                          {c.tiene_foto && (
                            <button onClick={() => handleVerFoto(c.id)}
                              className="px-2 py-0.5 bg-indigo-600/20 hover:bg-indigo-600/40 text-indigo-400 rounded text-xs transition-colors"
                              title="Ver foto">📷</button>
                          )}
                          <button onClick={() => handleCompartir(c)}
                            className="px-2 py-0.5 bg-green-600/20 hover:bg-green-600/40 text-green-400 rounded text-xs transition-colors"
                            title="Compartir">📤</button>
                          {esRegistrado(c.estado) && (
                            <>
                              <button onClick={() => { setAcreditarId(c.id); setAcreditarFecha(''); setAcreditarBancoId('') }}
                                className="px-2 py-0.5 bg-green-600/20 hover:bg-green-600/40 text-green-400 rounded text-xs transition-colors">Acreditar</button>
                              {canDelete && <button onClick={() => handleDelete(c.id)}
                                className="px-2 py-0.5 bg-white/5 hover:bg-white/10 text-gray-400 rounded text-xs transition-colors">✕</button>}
                            </>
                          )}
                          {c.estado === 'acreditado' && (
                            <button onClick={() => { setRechazarId(c.id); setRechazarData({ fecha_rechazo: '', gastos_bancarios: '', fisico: false, fecha_devolucion: '' }) }}
                              className="px-2 py-0.5 bg-red-600/20 hover:bg-red-600/40 text-red-400 rounded text-xs transition-colors">Rechazar</button>
                          )}
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          {total > LIMIT && (
            <div className="flex items-center justify-between text-xs text-gray-400">
              <span>{skip + 1}–{Math.min(skip + LIMIT, total)} de {total}</span>
              <div className="flex gap-2">
                <button disabled={skip === 0} onClick={() => setSkip(s => Math.max(0, s - LIMIT))}
                  className="px-3 py-1 bg-white/5 rounded disabled:opacity-40 hover:bg-white/10">← Anterior</button>
                <button disabled={skip + LIMIT >= total} onClick={() => setSkip(s => s + LIMIT)}
                  className="px-3 py-1 bg-white/5 rounded disabled:opacity-40 hover:bg-white/10">Siguiente →</button>
              </div>
            </div>
          )}
        </>
      )}

      {/* ═══ TAB: POR DEPÓSITO ═══ */}
      {tab === 'deposito' && (
        <div className="space-y-4">
          <div className="flex flex-wrap items-end gap-3">
            <div>
              <label className="block text-xs text-gray-400 mb-1">Fecha de depósito</label>
              <select value={depositoFecha} onChange={e => { setDepositoFecha(e.target.value); setSelectedCheques(new Set()) }}
                className="bg-white/5 border border-white/10 rounded-lg px-3 py-1.5 text-sm text-gray-200 focus:outline-none min-w-[170px]">
                <option value="">Seleccioná una fecha</option>
                {depositoFechas.map(f => <option key={f} value={f}>{fmtDate(f)}</option>)}
              </select>
            </div>
            {depositoFecha && (
              <button onClick={handleExportDeposito} disabled={exportandoDeposito}
                className="px-3 py-1.5 bg-green-700/30 hover:bg-green-700/50 text-green-400 text-sm rounded-lg transition-colors disabled:opacity-50">
                {exportandoDeposito ? 'Exportando…' : '↓ Excel'}
              </button>
            )}
          </div>

          {/* Acreditación masiva */}
          {depositoData && depositoData.items.some(c => esRegistrado(c.estado)) && (
            <div className="bg-indigo-500/5 border border-indigo-500/20 rounded-xl p-3 flex flex-wrap items-end gap-3">
              <div className="flex-1 min-w-[160px]">
                <label className="block text-xs text-gray-400 mb-1">Banco de acreditación</label>
                <select value={acredMasivoBanco} onChange={e => setAcredMasivoBanco(e.target.value ? parseInt(e.target.value) : '')}
                  className="w-full bg-white/5 border border-white/10 rounded-lg px-3 py-1.5 text-sm text-gray-200 focus:outline-none">
                  <option value="">Seleccioná banco</option>
                  {bancoCuentas.map(b => <option key={b.id} value={b.id}>{b.nombre} ({b.codigo})</option>)}
                </select>
              </div>
              <div>
                <label className="block text-xs text-gray-400 mb-1">Fecha de acreditación</label>
                <input type="date" value={acredMasivoFecha} onChange={e => setAcredMasivoFecha(e.target.value)}
                  className="bg-white/5 border border-white/10 rounded-lg px-3 py-1.5 text-sm text-gray-200 focus:outline-none" />
              </div>
              <button
                onClick={handleAcreditarMasivo}
                disabled={acreditandoMasivo || !acredMasivoBanco || selectedCheques.size === 0}
                className="px-4 py-1.5 bg-green-600 hover:bg-green-500 text-white text-sm rounded-lg disabled:opacity-50 transition-colors whitespace-nowrap">
                {acreditandoMasivo ? 'Procesando…' : `✓ Acreditar ${selectedCheques.size > 0 ? `(${selectedCheques.size})` : 'seleccionados'}`}
              </button>
              {selectedCheques.size > 0 && (
                <button onClick={() => setSelectedCheques(new Set())} className="text-xs text-gray-500 hover:text-gray-300 px-2">
                  Limpiar selección
                </button>
              )}
            </div>
          )}

          {depositoLoading ? (
            <p className="text-sm text-gray-500 text-center py-8">Cargando…</p>
          ) : !depositoData ? (
            <p className="text-sm text-gray-500 text-center py-8">
              {depositoFechas.length === 0 ? 'No hay cheques con fecha de depósito cargada' : 'Seleccioná una fecha para ver los cheques'}
            </p>
          ) : (
            <>
              {/* Resumen cards */}
              <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                <div className="bg-white/3 border border-white/8 rounded-xl p-3 col-span-2 md:col-span-1">
                  <p className="text-xs text-gray-500">Total del día</p>
                  <p className="text-lg font-semibold text-gray-100 mt-1">{fmt(depositoData.resumen.total)}</p>
                  <p className="text-xs text-gray-600 mt-0.5">{depositoData.items.length} cheques</p>
                </div>
                {depositoData.resumen.por_local_interior.map(li => (
                  <div key={li.tipo} className="bg-white/3 border border-white/8 rounded-xl p-3">
                    <p className="text-xs text-gray-500">{li.tipo === 'local' ? 'Local (CP < 2000)' : 'Interior (CP ≥ 2000)'}</p>
                    <p className={`text-base font-semibold mt-1 ${li.tipo === 'local' ? 'text-blue-400' : 'text-orange-400'}`}>{fmt(li.total)}</p>
                    <p className="text-xs text-gray-600 mt-0.5">{li.count} cheques</p>
                  </div>
                ))}
              </div>

              <div className="rounded-xl overflow-hidden border border-white/8">
                <div className="overflow-x-auto">
                  <table className="w-full text-xs min-w-[680px]">
                    <thead>
                      <tr className="bg-white/4 text-left text-gray-400">
                        <th className="px-2 py-2">
                          <input type="checkbox" className="w-3.5 h-3.5 accent-indigo-500"
                            checked={depositoData.items.filter(c => esRegistrado(c.estado)).length > 0 &&
                              depositoData.items.filter(c => esRegistrado(c.estado)).every(c => selectedCheques.has(c.id))}
                            onChange={e => {
                              const ids = depositoData.items.filter(c => esRegistrado(c.estado)).map(c => c.id)
                              setSelectedCheques(e.target.checked ? new Set(ids) : new Set())
                            }} />
                        </th>
                        <th className="px-3 py-2 font-medium">Cliente</th>
                        <th className="px-3 py-2 font-medium">Librador</th>
                        <th className="px-3 py-2 font-medium">Portador</th>
                        <th className="px-3 py-2 font-medium">Banco</th>
                        <th className="px-3 py-2 font-medium">N° Cheque</th>
                        <th className="px-3 py-2 font-medium">CP</th>
                        <th className="px-3 py-2 font-medium">L/I</th>
                        <th className="px-3 py-2 font-medium text-right">Monto</th>
                        <th className="px-3 py-2 font-medium">Estado</th>
                      </tr>
                    </thead>
                    <tbody>
                      {depositoData.items.map((c, i) => (
                        <tr key={c.id} className={`border-t border-white/5 hover:bg-white/2 ${selectedCheques.has(c.id) ? 'bg-indigo-500/5' : i % 2 === 0 ? '' : 'bg-white/1'}`}>
                          <td className="px-2 py-2">
                            {esRegistrado(c.estado) ? (
                              <input type="checkbox" className="w-3.5 h-3.5 accent-indigo-500"
                                checked={selectedCheques.has(c.id)}
                                onChange={e => {
                                  const s = new Set(selectedCheques)
                                  e.target.checked ? s.add(c.id) : s.delete(c.id)
                                  setSelectedCheques(s)
                                }} />
                            ) : <span className="w-3.5 h-3.5 block" />}
                          </td>
                          <td className="px-3 py-2 text-gray-200">{c.cliente_nombre || '—'}</td>
                          <td className="px-3 py-2 text-gray-300 max-w-[110px] truncate">{c.librador || c.titular || '—'}</td>
                          <td className="px-3 py-2 text-gray-400">{c.portador_nombre || '—'}</td>
                          <td className="px-3 py-2 text-gray-400">{c.banco_origen || '—'}</td>
                          <td className="px-3 py-2 text-gray-400">{c.numero || '—'}</td>
                          <td className="px-3 py-2 text-gray-400">{c.codigo_postal || '—'}</td>
                          <td className="px-3 py-2"><LiBadge value={c.local_interior} /></td>
                          <td className="px-3 py-2 text-right font-mono text-gray-100">{fmt(c.monto)}</td>
                          <td className="px-3 py-2">
                            <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${ESTADO_BADGE[c.estado] || ''}`}>
                              {ESTADO_LABEL[c.estado] || c.estado}
                            </span>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                    <tfoot>
                      <tr className="border-t border-white/10 bg-white/4">
                        <td colSpan={8} className="px-3 py-2 text-xs text-gray-400 font-medium">Total</td>
                        <td className="px-3 py-2 text-right font-mono text-gray-100 font-semibold">{fmt(depositoData.resumen.total)}</td>
                        <td />
                      </tr>
                    </tfoot>
                  </table>
                </div>
              </div>

              {depositoData.resumen.por_cliente.length > 0 && (
                <div className="bg-white/3 border border-white/8 rounded-xl p-4">
                  <h3 className="text-xs font-semibold text-gray-400 mb-3 uppercase tracking-wider">Resumen por cliente</h3>
                  <div className="space-y-1.5">
                    {depositoData.resumen.por_cliente.map(r => (
                      <div key={r.cliente} className="flex items-center justify-between text-xs">
                        <span className="text-gray-300">{r.cliente}</span>
                        <div className="flex items-center gap-3">
                          <span className="text-gray-500">{r.count} cheq.</span>
                          <span className="font-mono text-gray-100 font-medium">{fmt(r.total)}</span>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </>
          )}
        </div>
      )}

      {/* ═══ TAB: RECHAZADOS ═══ */}
      {tab === 'rechazados' && (
        <div className="space-y-4">
          {rechazadosLoading ? (
            <p className="text-sm text-gray-500 text-center py-8">Cargando…</p>
          ) : rechazadosList.length === 0 ? (
            <p className="text-sm text-gray-500 text-center py-8">No hay cheques rechazados</p>
          ) : (
            <div className="rounded-xl overflow-hidden border border-white/8">
              <div className="overflow-x-auto">
                <table className="w-full text-xs min-w-[960px]">
                  <thead>
                    <tr className="bg-white/4 text-left text-gray-400">
                      <th className="px-3 py-2 font-medium">F. Depósito</th>
                      <th className="px-3 py-2 font-medium">F. Rechazo</th>
                      <th className="px-3 py-2 font-medium">Cliente</th>
                      <th className="px-3 py-2 font-medium">F. Cheque</th>
                      <th className="px-3 py-2 font-medium">N° Banco</th>
                      <th className="px-3 py-2 font-medium">Banco</th>
                      <th className="px-3 py-2 font-medium">Librador</th>
                      <th className="px-3 py-2 font-medium">N° Cheque</th>
                      <th className="px-3 py-2 font-medium">CP</th>
                      <th className="px-3 py-2 font-medium">L/I</th>
                      <th className="px-3 py-2 font-medium text-right">Importe</th>
                      <th className="px-3 py-2 font-medium">Físico</th>
                      <th className="px-3 py-2 font-medium">F. Devolución</th>
                    </tr>
                  </thead>
                  <tbody>
                    {rechazadosList.map((c, i) => (
                      <tr key={c.id} className={`border-t border-white/5 hover:bg-white/2 ${i % 2 === 0 ? '' : 'bg-white/1'}`}>
                        <td className="px-3 py-2 text-gray-400 whitespace-nowrap">{fmtDate(c.fecha_deposito)}</td>
                        <td className="px-3 py-2 text-red-400 whitespace-nowrap">{fmtDate(c.fecha_rechazo)}</td>
                        <td className="px-3 py-2 text-gray-200">{c.cliente_nombre || '—'}</td>
                        <td className="px-3 py-2 text-gray-400 whitespace-nowrap">{fmtDate(c.fecha_emision)}</td>
                        <td className="px-3 py-2 text-gray-400">{c.numero || '—'}</td>
                        <td className="px-3 py-2 text-gray-400">{c.banco_origen || '—'}</td>
                        <td className="px-3 py-2 text-gray-300 max-w-[100px] truncate" title={c.librador || c.titular || ''}>{c.librador || c.titular || '—'}</td>
                        <td className="px-3 py-2 text-gray-400">{c.numero || '—'}</td>
                        <td className="px-3 py-2 text-gray-400">{c.codigo_postal || '—'}</td>
                        <td className="px-3 py-2"><LiBadge value={c.local_interior} /></td>
                        <td className="px-3 py-2 text-right font-mono text-gray-100">{fmt(c.monto)}</td>
                        <td className="px-3 py-2">
                          {c.fisico
                            ? <span className="px-1.5 py-0.5 rounded text-xs bg-blue-500/15 text-blue-400">Sí</span>
                            : <span className="text-gray-600">No</span>
                          }
                        </td>
                        <td className="px-3 py-2 text-gray-400 whitespace-nowrap">{fmtDate(c.fecha_devolucion)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </div>
      )}

      {/* ═══ Modal: Nuevo cheque ═══ */}
      {showForm && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4"
          onClick={e => e.target === e.currentTarget && setShowForm(false)}>
          <div className="bg-[#16161A] border border-white/10 rounded-xl p-5 w-full max-w-lg space-y-4 max-h-[90vh] overflow-y-auto">
            <div className="flex items-center justify-between">
              <h2 className="text-base font-semibold text-gray-100">Nuevo cheque</h2>
              <button onClick={() => setShowForm(false)} className="text-gray-500 hover:text-gray-300 text-xl leading-none">×</button>
            </div>
            {msg && <p className="text-xs text-red-400">{msg}</p>}
            <div className="grid grid-cols-2 gap-3">
              <div className="col-span-2">
                <ClienteSelector
                  clientes={clientes}
                  value={formData.cliente_id}
                  onChangeCliente={(id, cli) => setFormData(p => ({
                    ...p, cliente_id: id,
                    // al elegir cliente, pre-llena el % según local/interior del cheque
                    porcentaje_comision: pctParaCliente(cli, p.local_interior || computeLI(p.codigo_postal)),
                  }))}
                  onAdd={handleAddCliente}
                />
              </div>
              <div className="col-span-2">
                <PortadorSelector
                  portadores={portadores}
                  value={formData.portador_id}
                  onChange={id => setFormData(p => ({ ...p, portador_id: id }))}
                  onAdd={handleAddPortador}
                />
              </div>
              <div>
                <label className="block text-xs text-gray-400 mb-1">Librador</label>
                <input type="text" value={formData.librador} onChange={e => setFormData(p => ({ ...p, librador: e.target.value }))} className={inputClass} />
              </div>
              <div>
                <label className="block text-xs text-gray-400 mb-1">Banco origen</label>
                <input type="text" value={formData.banco_origen} onChange={e => setFormData(p => ({ ...p, banco_origen: e.target.value }))} className={inputClass} />
              </div>
              <div>
                <label className="block text-xs text-gray-400 mb-1">N° de cheque</label>
                <input type="text" value={formData.numero} onChange={e => setFormData(p => ({ ...p, numero: e.target.value }))} className={inputClass} />
              </div>
              <div>
                <label className="block text-xs text-gray-400 mb-1">Monto *</label>
                <input type="number" value={formData.monto || ''} onChange={e => setFormData(p => ({ ...p, monto: parseFloat(e.target.value) || 0 }))} className={inputClass} />
              </div>
              <div>
                <label className="block text-xs text-gray-400 mb-1">Comisión banco</label>
                <input type="number" value={formData.comision || ''} onChange={e => setFormData(p => ({ ...p, comision: parseFloat(e.target.value) || 0 }))} className={inputClass} />
              </div>
              <div>
                <label className="block text-xs text-gray-400 mb-1">% Comisión</label>
                <input type="number" step="0.1" min="0" max="100" placeholder="ej: 1.5"
                  value={formData.porcentaje_comision ?? ''} className={inputClass}
                  onChange={e => setFormData(p => ({ ...p, porcentaje_comision: e.target.value === '' ? null : parseFloat(e.target.value) }))} />
                {formData.porcentaje_comision != null && (() => {
                  const cli = clientes.find(c => c.id === formData.cliente_id) ?? null
                  const li = formData.local_interior || computeLI(formData.codigo_postal)
                  return pctParaCliente(cli, li) === formData.porcentaje_comision
                    ? <p className="text-xs text-gray-500 mt-0.5">↑ del cliente{li ? ` (${li})` : ''} — podés cambiarlo</p> : null
                })()}
              </div>
              <div>
                <label className="block text-xs text-gray-400 mb-1">Código postal</label>
                <input type="text" value={formData.codigo_postal} placeholder="ej: 1425"
                  onChange={e => {
                    const cp = e.target.value
                    setFormData(p => {
                      const li = computeLI(cp)
                      // si hay cliente, re-deriva el % según el nuevo local/interior
                      const cli = clientes.find(c => c.id === p.cliente_id) ?? null
                      return {
                        ...p, codigo_postal: cp, local_interior: li,
                        porcentaje_comision: cli ? pctParaCliente(cli, li) : p.porcentaje_comision,
                      }
                    })
                  }}
                  className={inputClass} />
              </div>
              <div>
                <label className="block text-xs text-gray-400 mb-1">Local / Interior</label>
                <div className="flex items-center gap-2 h-[34px] px-3 bg-white/5 border border-white/10 rounded">
                  {formData.local_interior
                    ? <LiBadge value={formData.local_interior} />
                    : <span className="text-xs text-gray-600">Auto por CP</span>
                  }
                </div>
              </div>
              <div>
                <label className="block text-xs text-gray-400 mb-1">Fecha emisión</label>
                <input type="date" value={formData.fecha_emision} onChange={e => setFormData(p => ({ ...p, fecha_emision: e.target.value }))} className={inputClass} />
              </div>
              <div>
                <label className="block text-xs text-gray-400 mb-1">Fecha depósito</label>
                <input type="date" value={formData.fecha_deposito} onChange={e => setFormData(p => ({ ...p, fecha_deposito: e.target.value }))} className={inputClass} />
              </div>
              <div className="col-span-2">
                <label className="block text-xs text-gray-400 mb-1">Notas</label>
                <textarea rows={2} value={formData.notas}
                  onChange={e => setFormData(p => ({ ...p, notas: e.target.value }))}
                  className="w-full bg-white/5 border border-white/10 rounded px-3 py-1.5 text-sm text-gray-100 focus:outline-none focus:border-indigo-500 resize-none" />
              </div>
              <div className="col-span-2">
                <label className="block text-xs text-gray-400 mb-1">Foto del cheque (opcional)</label>
                <div className="flex items-center gap-3">
                  <input ref={fotoInputRef} type="file" accept="image/*" capture="environment" className="hidden" onChange={handleFotoChange} />
                  <button type="button" onClick={() => fotoInputRef.current?.click()}
                    className="px-3 py-1.5 bg-white/8 hover:bg-white/12 text-gray-300 text-sm rounded border border-white/10 transition-colors">
                    📷 Sacar foto / subir imagen
                  </button>
                  {formFoto && (
                    <div className="flex items-center gap-2">
                      <img src={formFoto} alt="preview" className="h-10 w-10 object-cover rounded border border-white/10" />
                      <button onClick={() => setFormFoto(null)} className="text-xs text-red-400 hover:text-red-300">✕ quitar</button>
                    </div>
                  )}
                </div>
              </div>
            </div>
            <div className="flex justify-end gap-2 pt-2">
              <button onClick={() => setShowForm(false)} className="px-4 py-1.5 text-sm text-gray-400 hover:text-gray-200">Cancelar</button>
              <button onClick={handleCreate} disabled={saving}
                className="px-4 py-1.5 bg-indigo-600 hover:bg-indigo-500 text-white text-sm rounded-lg disabled:opacity-50 transition-colors">
                {saving ? 'Guardando…' : 'Guardar'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ═══ Modal: Acreditar ═══ */}
      {acreditarId && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4">
          <div className="bg-[#16161A] border border-white/10 rounded-xl p-5 w-full max-w-sm space-y-4">
            <h2 className="text-base font-semibold text-gray-100">Acreditar cheque</h2>
            <p className="text-xs text-gray-500">A1: Banco D / Cheques en cartera H — A2: Cheques depositados D / Cliente H</p>
            <div>
              <label className="block text-xs text-gray-400 mb-1">Banco *</label>
              <select value={acreditarBancoId} onChange={e => setAcreditarBancoId(e.target.value ? parseInt(e.target.value) : '')}
                className={inputClass}>
                <option value="">Seleccioná banco</option>
                {bancoCuentas.map(b => <option key={b.id} value={b.id}>{b.nombre} ({b.codigo})</option>)}
              </select>
            </div>
            <div>
              <label className="block text-xs text-gray-400 mb-1">Fecha de acreditación</label>
              <input type="date" value={acreditarFecha} onChange={e => setAcreditarFecha(e.target.value)} className={inputClass} />
              <p className="text-xs text-gray-500 mt-1">Si no se indica, se usa hoy.</p>
            </div>
            <div className="flex justify-end gap-2">
              <button onClick={() => setAcreditarId(null)} className="px-4 py-1.5 text-sm text-gray-400 hover:text-gray-200">Cancelar</button>
              <button onClick={handleAcreditar} disabled={actioning || !acreditarBancoId}
                className="px-4 py-1.5 bg-green-600 hover:bg-green-500 text-white text-sm rounded-lg disabled:opacity-50 transition-colors">
                {actioning ? 'Procesando…' : 'Confirmar'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ═══ Modal: Rechazar ═══ */}
      {rechazarId && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4">
          <div className="bg-[#16161A] border border-white/10 rounded-xl p-5 w-full max-w-sm space-y-4">
            <h2 className="text-base font-semibold text-gray-100">Registrar rechazo</h2>
            <p className="text-xs text-gray-500">A1: Cliente D / Banco H — A2: Cliente D / Gastos rechazos H — A3: Gastos rechazos D / Banco H</p>
            <div>
              <label className="block text-xs text-gray-400 mb-1">Fecha de rechazo</label>
              <input type="date" value={rechazarData.fecha_rechazo}
                onChange={e => setRechazarData(p => ({ ...p, fecha_rechazo: e.target.value }))}
                className={inputClass} />
              <p className="text-xs text-gray-500 mt-1">Si no se indica, se usa hoy.</p>
            </div>
            <div>
              <label className="block text-xs text-gray-400 mb-1">Gastos bancarios del rechazo</label>
              <input type="number" min="0" step="0.01" placeholder="0.00"
                value={rechazarData.gastos_bancarios}
                onChange={e => setRechazarData(p => ({ ...p, gastos_bancarios: e.target.value }))}
                className={inputClass} />
              <p className="text-xs text-gray-500 mt-1">Dejar en 0 si el banco no cobró gastos.</p>
            </div>
            <div className="flex items-center gap-3">
              <input type="checkbox" id="fisico-check" checked={rechazarData.fisico}
                onChange={e => setRechazarData(p => ({ ...p, fisico: e.target.checked }))}
                className="w-4 h-4 rounded accent-indigo-500" />
              <label htmlFor="fisico-check" className="text-sm text-gray-300">El cheque físico fue devuelto</label>
            </div>
            {rechazarData.fisico && (
              <div>
                <label className="block text-xs text-gray-400 mb-1">Fecha de devolución (opcional)</label>
                <input type="date" value={rechazarData.fecha_devolucion}
                  onChange={e => setRechazarData(p => ({ ...p, fecha_devolucion: e.target.value }))}
                  className={inputClass} />
              </div>
            )}
            <div className="flex justify-end gap-2">
              <button onClick={() => setRechazarId(null)} className="px-4 py-1.5 text-sm text-gray-400 hover:text-gray-200">Cancelar</button>
              <button onClick={handleRechazar} disabled={actioning}
                className="px-4 py-1.5 bg-red-600 hover:bg-red-500 text-white text-sm rounded-lg disabled:opacity-50 transition-colors">
                {actioning ? 'Procesando…' : 'Registrar rechazo'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ═══ Modal: Ver foto ═══ */}
      {verFotoId && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 p-4"
          onClick={() => { setVerFotoId(null); setFotoData(null) }}>
          <div className="bg-[#16161A] border border-white/10 rounded-xl p-4 max-w-lg w-full" onClick={e => e.stopPropagation()}>
            <div className="flex justify-between items-center mb-3">
              <h2 className="text-sm font-semibold text-gray-100">Comprobante del cheque</h2>
              <button onClick={() => { setVerFotoId(null); setFotoData(null) }} className="text-gray-500 hover:text-gray-300 text-xl">×</button>
            </div>
            {loadingFoto ? (
              <div className="text-center py-8 text-gray-400 text-sm">Cargando imagen…</div>
            ) : fotoData ? (
              <>
                <img src={fotoData} alt="comprobante" className="w-full rounded-lg object-contain max-h-[60vh]" />
                <button
                  onClick={() => {
                    const c = cheques.find(x => x.id === verFotoId) || rechazadosList.find(x => x.id === verFotoId)
                    if (c) handleCompartir(c)
                  }}
                  className="mt-3 w-full py-2 bg-green-600/20 hover:bg-green-600/30 text-green-400 rounded-lg text-sm transition-colors">
                  📤 Compartir por WhatsApp
                </button>
              </>
            ) : (
              <div className="text-center py-8 text-gray-500 text-sm">No se pudo cargar la imagen</div>
            )}
          </div>
        </div>
      )}
    </div>
  )
}
