import { useEffect, useMemo, useState, useCallback, useRef } from 'react'

/** Extract .response?.data?.detail from an axios-style error */
function apiDetail(e: unknown, fallback: string): string {
  const err = e as { response?: { data?: { detail?: string } }; message?: string }
  return err?.response?.data?.detail || err?.message || fallback
}
function isAbortError(e: unknown): boolean {
  return (e as { name?: string })?.name === 'AbortError'
}
import { useSearchParams, useNavigate } from 'react-router-dom'
import { apiClient } from '@/services/api'
import { confirmDialog } from '@/store/confirm'
import { useOrgStore } from '@/store/org'
import { useAuthStore } from '@/store/auth'
import {
  Cheque, ClienteOpt, PortadorOpt, BancoCuenta, DepositoData, RechazarData, FormState,
  emptyForm, esRegistrado, computeLI, pctParaCliente, fmt, fmtDate,
  toBase64, compressScanner, shareChequePdf, suppressLockForShare,
} from './shared'
import { BulkOcrRow } from './ChequesTabMasiva'
import type { CuentaItem } from '@/components/contabilidad/shared'

// Shape returned by /cheques/bulk-ocr for each item
interface BulkOcrItemRaw {
  index?: number
  filename?: string
  numero?: string | number | null
  banco_origen?: string | null
  librador?: string | null
  monto?: number | null
  fecha_emision?: string | null
  fecha_deposito?: string | null
  codigo_postal?: string | null
  local_interior?: string | null
  error?: boolean
  error_msg?: string
}

// Shape returned by POST /cheques/acreditar detalle[]
interface AcreditarDetalleItem { ok: boolean; id?: number; error?: string }

// Shape returned by POST /cheques/bulk-crear errores[]
interface BulkCrearErrorItem { index: number; msg: string }

// Response shape for /clientes/archivos
interface OrgClientesRaw {
  clientes?: Array<{
    id: number
    nombre: string
    porcentaje_comision?: number | null
    porcentaje_comision_local?: number | null
    porcentaje_comision_interior?: number | null
    cuenta_contable_id?: number | null
  }>
}

const LIMIT = 50

export function useCheques() {
  const { activeOrgId } = useOrgStore()
  const canDelete = useAuthStore(s => s.hasPermission('delete_records'))

  const [tab, setTab] = useState<'todos' | 'deposito' | 'rechazados' | 'masiva'>('todos')

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

  // Rechazados tab
  const [rechazadosList, setRechazadosList]     = useState<Cheque[]>([])
  const [rechazadosLoading, setRechazadosLoading] = useState(false)

  // Deposito tab
  const [depositoFechas, setDepositoFechas]   = useState<string[]>([])
  const [depositoFecha, setDepositoFecha]     = useState('')
  const [depositoData, setDepositoData]       = useState<DepositoData | null>(null)
  const [depositoLoading, setDepositoLoading] = useState(false)
  const [exportandoDeposito, setExportandoDeposito] = useState(false)

  // Form modal (create + edit)
  const [showForm, setShowForm] = useState(false)
  const [editId, setEditId]     = useState<number | null>(null)
  const [formData, setFormData] = useState<FormState>(emptyForm())
  const [formFoto, setFormFoto] = useState<string | null>(null)
  const [saving, setSaving]     = useState(false)
  const fotoInputRef            = useRef<HTMLInputElement>(null)

  // Export todos
  const [exportandoTodos, setExportandoTodos] = useState(false)

  // Banco accounts for acreditación
  const [bancoCuentas, setBancoCuentas] = useState<BancoCuenta[]>([])

  // Action modals — individual
  const [acreditarId, setAcreditarId]     = useState<number | null>(null)
  const [acreditarFecha, setAcreditarFecha] = useState('')
  const [acreditarBancoId, setAcreditarBancoId] = useState<number | ''>('')
  const [rechazarId, setRechazarId]       = useState<number | null>(null)
  const [rechazarData, setRechazarData]   = useState<RechazarData>({ fecha_rechazo: '', gastos_bancarios: '', fisico: false, fecha_devolucion: '' })
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

  // Carga masiva OCR
  const [bulkFiles, setBulkFiles]     = useState<File[]>([])
  const [bulkPreviews, setBulkPreviews] = useState<string[]>([])
  const [bulkRows, setBulkRows]       = useState<BulkOcrRow[]>([])
  const [bulkProcessing, setBulkProcessing] = useState(false)
  const [bulkSaving, setBulkSaving]   = useState(false)
  const [bulkMsg, setBulkMsg]         = useState('')
  const bulkInputRef                  = useRef<HTMLInputElement>(null)

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
        const all: CuentaItem[] = Array.isArray(r.data) ? r.data : (r.data?.items ?? r.data?.cuentas ?? [])
        // IDs que son cuenta madre (tienen hijos) → no se imputan
        const parentIds = new Set(all.map(c => c.parent_id).filter(Boolean))
        const bancos = all.filter(c =>
          typeof c.nombre === 'string' &&
          c.nombre.toLowerCase().startsWith('banco') &&
          !parentIds.has(c.id)  // solo cuentas hoja
        )
        setBancoCuentas(bancos.map(c => ({ id: c.id, codigo: c.codigo, nombre: c.nombre })))
      })
      .catch(() => {})
  }, [activeOrgId])

  // Clientes
  useEffect(() => {
    const params: Record<string, number> = {}
    if (activeOrgId) params.org_id = activeOrgId
    apiClient.client.get('/clientes/archivos', { params }).then(r => {
      const orgs: OrgClientesRaw[] = r.data?.organizaciones || []
      const list: ClienteOpt[] = []
      orgs.forEach(org => (org.clientes || []).forEach(c =>
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

  const handleOpenEdit = (c: Cheque) => {
    setEditId(c.id)
    setFormData({
      cliente_id:          c.cliente_id,
      portador_id:         c.portador_id,
      numero:              c.numero || '',
      banco_origen:        c.banco_origen || '',
      librador:            c.librador || c.titular || '',
      codigo_postal:       c.codigo_postal || '',
      local_interior:      c.local_interior || '',
      monto:               c.monto,
      porcentaje_comision: c.porcentaje_comision,
      fecha_emision:       c.fecha_emision || '',
      fecha_deposito:      c.fecha_deposito || '',
      notas:               c.notas || '',
    })
    setFormFoto(null)
    setMsg('')
    setShowForm(true)
  }

  const handleSave = async () => {
    if (!formData.monto || formData.monto <= 0) { setMsg('El monto es requerido'); return }
    setSaving(true); setMsg('')
    try {
      const li = formData.local_interior || computeLI(formData.codigo_postal)
      // Comisión calculada automáticamente desde el %, sin campo manual
      const pct = formData.porcentaje_comision ?? 0
      const comisionCalc = pct > 0 ? Math.round(formData.monto * pct) / 100 : 0
      const payload = {
        cliente_id:          formData.cliente_id || null,
        portador_id:         formData.portador_id || null,
        numero:              formData.numero || null,
        banco_origen:        formData.banco_origen || null,
        librador:            formData.librador || null,
        codigo_postal:       formData.codigo_postal || null,
        local_interior:      li || null,
        monto:               formData.monto,
        comision:            comisionCalc,
        porcentaje_comision: formData.porcentaje_comision || null,
        fecha_emision:       formData.fecha_emision || null,
        fecha_deposito:      formData.fecha_deposito || null,
        notas:               formData.notas || null,
      }
      let id: number
      if (editId) {
        const res = await apiClient.client.patch(`/cheques/${editId}`, payload)
        id = res.data.id
      } else {
        const res = await apiClient.client.post('/cheques', payload)
        id = res.data.id
        if (formFoto && id)
          await apiClient.client.post(`/cheques/${id}/foto`, { foto_base64: formFoto })
      }
      setShowForm(false); setEditId(null); setFormData(emptyForm()); setFormFoto(null); load()
    } catch (e) { setMsg(apiDetail(e, 'Error al guardar')) }
    finally { setSaving(false) }
  }

  const handleExportarTodos = async () => {
    setExportandoTodos(true)
    try {
      const params: Record<string, string | number> = {}
      if (activeOrgId)   params.org_id    = activeOrgId
      if (filtroEstado)  params.estado     = filtroEstado
      if (filtroCliente) params.cliente_id = filtroCliente
      if (filtroDesde)   params.desde      = filtroDesde
      if (filtroHasta)   params.hasta      = filtroHasta
      const res = await apiClient.client.get('/cheques/exportar', { params, responseType: 'blob' })
      const url = URL.createObjectURL(res.data)
      const a = document.createElement('a'); a.href = url; a.download = 'cheques.xlsx'; a.click()
      URL.revokeObjectURL(url)
    } catch { setMsg('Error al exportar') }
    finally { setExportandoTodos(false) }
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
    } catch (e) { setMsg(apiDetail(e, 'Error')) }
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
      const { acreditados, total, detalle } = res.data as { acreditados: number; total: number; detalle: AcreditarDetalleItem[] }
      const errores = detalle.filter(d => !d.ok)
      setMsg(`✓ ${acreditados}/${total} acreditados${errores.length ? ` · ${errores.length} error(es)` : ''}`)
      setSelectedCheques(new Set()); setAcredMasivoBanco(''); setAcredMasivoFecha('')
      // reload deposito data
      if (depositoFecha) {
        const p: Record<string, string | number> = { fecha: depositoFecha }
        if (activeOrgId) p.org_id = activeOrgId
        apiClient.client.get('/cheques/deposito', { params: p }).then(r => setDepositoData(r.data)).catch(() => {})
      }
    } catch (e) { setMsg(apiDetail(e, 'Error al acreditar')) }
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
    } catch (e) { setMsg(apiDetail(e, 'Error')) }
    finally { setActioning(false) }
  }

  const handleDelete = async (id: number) => {
    if (!await confirmDialog({ title: 'Eliminar cheque', message: '¿Eliminar este cheque?', confirmLabel: 'Eliminar', danger: true })) return
    try { await apiClient.client.delete(`/cheques/${id}`); load() }
    catch (e) { setMsg(apiDetail(e, 'Error al eliminar')) }
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
            try {
              const img = new Image()
              await new Promise<void>((resolve, reject) => {
                img.onload = () => resolve(); img.onerror = () => reject(new Error('img')); img.src = fotoB64
              })
              const canvas = document.createElement('canvas')
              canvas.width = img.naturalWidth || 800; canvas.height = img.naturalHeight || 600
              const ctx = canvas.getContext('2d')!
              ctx.fillStyle = '#ffffff'; ctx.fillRect(0, 0, canvas.width, canvas.height); ctx.drawImage(img, 0, 0)
              const blob = await new Promise<Blob>((res, rej) => canvas.toBlob(b => b ? res(b) : rej(new Error('toBlob')), 'image/jpeg', 0.85))
              const file = new File([blob], `Cheque_${nombre}.jpg`, { type: 'image/jpeg' })
              if (navigator.canShare({ files: [file] })) {
                suppressLockForShare()
                await navigator.share({ title: `Cheque - ${nombre} - ${fmt(c.monto)}`, files: [file] }); return
              }
            } catch (imgErr) { if (isAbortError(imgErr)) return }
          }
        }
      } catch (e) {
        if (isAbortError(e)) return  // el usuario cerró el menú de compartir
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
    } catch (e) { setMsg(apiDetail(e, 'Error al importar')) }
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

  const { pendientes, totalPend, totalAcred, totalRech } = useMemo(() => {
    const pend = cheques.filter(c => esRegistrado(c.estado) || c.estado === 'depositado')
    return {
      pendientes: pend,
      totalPend:  pend.reduce((s, c) => s + c.monto, 0),
      totalAcred: cheques.filter(c => c.estado === 'acreditado').reduce((s, c) => s + c.monto, 0),
      totalRech:  cheques.filter(c => c.estado === 'rechazado').reduce((s, c) => s + c.monto, 0),
    }
  }, [cheques])

  const handleBulkFileChange = async (files: FileList | null) => {
    if (!files || files.length === 0) return
    const MAX = 30
    const arr = Array.from(files).slice(0, MAX)
    setBulkFiles(arr)
    setBulkRows([])
    setBulkMsg('')
    const previews = await Promise.all(arr.map(f => toBase64(f)))
    setBulkPreviews(previews)
  }

  const handleBulkRemoveFile = (idx: number) => {
    setBulkFiles(prev => prev.filter((_, i) => i !== idx))
    setBulkPreviews(prev => prev.filter((_, i) => i !== idx))
    setBulkRows([])
    setBulkMsg('')
  }

  const handleBulkProcess = async () => {
    if (bulkFiles.length === 0) return
    setBulkProcessing(true); setBulkMsg(''); setBulkRows([])
    try {
      const fd = new FormData()
      bulkFiles.forEach(f => fd.append('fotos', f))
      const params: Record<string, string | number> = {}
      if (activeOrgId) params.org_id = activeOrgId
      const res = await apiClient.client.post('/cheques/bulk-ocr', fd, {
        headers: { 'Content-Type': 'multipart/form-data' },
        params,
      })
      const items: BulkOcrItemRaw[] = res.data.items || []
      setBulkRows(items.map((item, i) => ({
        index:               item.index ?? i,
        filename:            item.filename ?? bulkFiles[i]?.name ?? `foto_${i}`,
        previewUrl:          bulkPreviews[item.index ?? i] ?? '',
        numero:              item.numero != null ? String(item.numero) : '',
        banco_origen:        item.banco_origen ?? '',
        librador:            item.librador ?? '',
        monto:               item.monto != null ? String(item.monto) : '',
        fecha_emision:       item.fecha_emision ?? '',
        fecha_deposito:      item.fecha_deposito ?? '',
        codigo_postal:       item.codigo_postal ?? '',
        local_interior:      item.local_interior ?? '',
        cliente_id:          null,
        porcentaje_comision: '',
        notas:               '',
        error:               item.error ?? false,
        error_msg:           item.error_msg ?? '',
      })))
    } catch (e) { setBulkMsg(apiDetail(e, 'Error al procesar OCR')) }
    finally { setBulkProcessing(false) }
  }

  const handleBulkUpdateRow = (idx: number, field: string, value: string | number | null) => {
    setBulkRows(prev => prev.map((r, i) => {
      if (i !== idx) return r
      const updated: BulkOcrRow = { ...r, [field]: value }
      if (field === 'codigo_postal') updated.local_interior = computeLI(String(value ?? ''))
      if (field === 'cliente_id') {
        const cli = clientes.find(c => c.id === (value as number)) ?? null
        const li = updated.local_interior || computeLI(updated.codigo_postal)
        const pct = pctParaCliente(cli, li)
        updated.porcentaje_comision = pct != null ? String(pct) : ''
      }
      return updated
    }))
  }

  const handleBulkRemoveRow = (idx: number) => {
    setBulkRows(prev => prev.filter((_, i) => i !== idx))
  }

  const clearBulkRows = () => { setBulkRows([]); setBulkMsg('') }

  const handleBulkSave = async () => {
    if (bulkRows.length === 0) return
    const readyRows = bulkRows.filter(r => !r.error && parseFloat(r.monto) > 0)
    if (readyRows.length === 0) { setBulkMsg('No hay filas válidas para guardar'); return }
    setBulkSaving(true); setBulkMsg('')
    try {
      const items = readyRows.map(r => ({
        cliente_id:          r.cliente_id || null,
        portador_id:         null,
        numero:              r.numero || null,
        banco_origen:        r.banco_origen || null,
        librador:            r.librador || null,
        monto:               parseFloat(r.monto),
        porcentaje_comision: r.porcentaje_comision ? parseFloat(r.porcentaje_comision) : null,
        codigo_postal:       r.codigo_postal || null,
        local_interior:      r.local_interior || null,
        fecha_emision:       r.fecha_emision || null,
        fecha_deposito:      r.fecha_deposito || null,
        notas:               r.notas || null,
      }))
      const params: Record<string, string | number> = {}
      if (activeOrgId) params.org_id = activeOrgId
      const res = await apiClient.client.post('/cheques/bulk-crear', { items, org_id: activeOrgId || null }, { params })
      const { creados, errores } = res.data as { creados: number; errores: BulkCrearErrorItem[] }
      const m = `✓ ${creados} cheque${creados !== 1 ? 's' : ''} guardado${creados !== 1 ? 's' : ''}${errores.length ? ` · ${errores.length} error(es)` : ''}`
      setBulkMsg(m)
      if (creados > 0) {
        setBulkFiles([]); setBulkPreviews([]); setBulkRows([])
        load()
      }
      if (errores.length > 0) {
        const errMsgs = errores.map(e => `Fila ${e.index + 1}: ${e.msg}`).join(' | ')
        setBulkMsg(`${m} — ${errMsgs}`)
      }
    } catch (e) { setBulkMsg(apiDetail(e, 'Error al guardar')) }
    finally { setBulkSaving(false) }
  }

  return {
    LIMIT, canDelete,
    tab, setTab,
    cheques, total, clientes, portadores, loading, msg,
    filtroEstado, setFiltroEstado, filtroCliente, setFiltroCliente, filtroDesde, setFiltroDesde, filtroHasta, setFiltroHasta,
    skip, setSkip,
    rechazadosList, rechazadosLoading,
    depositoFechas, depositoFecha, setDepositoFecha, depositoData, depositoLoading, exportandoDeposito,
    showForm, setShowForm, editId, setEditId, formData, setFormData, formFoto, setFormFoto, saving, fotoInputRef,
    exportandoTodos, bancoCuentas,
    acreditarId, setAcreditarId, acreditarFecha, setAcreditarFecha, acreditarBancoId, setAcreditarBancoId,
    rechazarId, setRechazarId, rechazarData, setRechazarData, actioning,
    selectedCheques, setSelectedCheques, acredMasivoBanco, setAcredMasivoBanco, acredMasivoFecha, setAcredMasivoFecha, acreditandoMasivo,
    verFotoId, setVerFotoId, fotoData, setFotoData, loadingFoto,
    importando, importRef,
    bulkFiles, bulkPreviews, bulkRows, bulkProcessing, bulkSaving, bulkMsg, bulkInputRef,
    pendientes, totalPend, totalAcred, totalRech,
    setMsg,
    handleAddPortador, handleAddCliente, handleFotoChange, handleOpenEdit, handleSave,
    handleExportarTodos, handleAcreditar, handleAcreditarMasivo, handleRechazar, handleDelete,
    handleVerFoto, handleCompartir, handleImportExcel, handleExportDeposito,
    handleBulkFileChange, handleBulkRemoveFile, handleBulkProcess, handleBulkUpdateRow, handleBulkRemoveRow, handleBulkSave,
    clearBulkRows,
  }
}
