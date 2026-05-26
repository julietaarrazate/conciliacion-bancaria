import React, { useEffect, useState, useCallback, useRef } from 'react'
import { useSearchParams, useNavigate } from 'react-router-dom'
import { apiClient } from '@/services/api'
import { confirmDialog } from '@/store/confirm'
import { useOrgStore } from '@/store/org'

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
  titular: string | null
  monto: number
  comision: number
  fecha_emision: string | null
  fecha_deposito: string | null
  fecha_acred: string | null
  estado: 'pendiente' | 'acreditado' | 'rechazado'
  notas: string | null
  tiene_foto: boolean
  created_at: string
}

interface ClienteOpt { id: number; nombre: string }

const ESTADO_BADGE: Record<string, string> = {
  pendiente:  'bg-yellow-500/15 text-yellow-400',
  acreditado: 'bg-green-500/15 text-green-400',
  rechazado:  'bg-red-500/15 text-red-400',
}

const emptyForm = (): Partial<Cheque> => ({
  cliente_id: null, numero: '', banco_origen: '', titular: '',
  monto: 0, comision: 0, fecha_emision: '', fecha_deposito: '', notas: '',
})

const inputClass = "w-full bg-white/5 border border-white/10 rounded px-3 py-1.5 text-sm text-gray-100 focus:outline-none focus:border-indigo-500"

// Convert file to base64
const toBase64 = (file: File): Promise<string> =>
  new Promise((resolve, reject) => {
    const reader = new FileReader()
    reader.onload = () => resolve(reader.result as string)
    reader.onerror = reject
    reader.readAsDataURL(file)
  })

export const Cheques: React.FC = () => {
  const { activeOrgId } = useOrgStore()
  const [cheques, setCheques]     = useState<Cheque[]>([])
  const [total, setTotal]         = useState(0)
  const [clientes, setClientes]   = useState<ClienteOpt[]>([])
  const [loading, setLoading]     = useState(true)
  const [msg, setMsg]             = useState('')

  const [filtroEstado, setFiltroEstado]   = useState('')
  const [filtroCliente, setFiltroCliente] = useState('')
  const [filtroDesde, setFiltroDesde]     = useState('')
  const [filtroHasta, setFiltroHasta]     = useState('')
  const [skip, setSkip]                   = useState(0)
  const LIMIT = 50

  // Form modal
  const [showForm, setShowForm]     = useState(false)
  const [formData, setFormData]     = useState<Partial<Cheque>>(emptyForm())
  const [formFoto, setFormFoto]     = useState<string | null>(null)
  const [saving, setSaving]         = useState(false)
  const fotoInputRef                = useRef<HTMLInputElement>(null)

  // Action modals
  const [acreditarId, setAcreditarId] = useState<number | null>(null)
  const [rechazarId, setRechazarId]   = useState<number | null>(null)
  const [actionDate, setActionDate]   = useState('')
  const [actioning, setActioning]     = useState(false)

  // Photo viewer
  const [verFotoId, setVerFotoId]   = useState<number | null>(null)
  const [fotoData, setFotoData]     = useState<string | null>(null)
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
      setCheques(res.data.items)
      setTotal(res.data.total)
    } catch { setMsg('Error al cargar cheques') }
    finally { setLoading(false) }
  }, [filtroEstado, filtroCliente, filtroDesde, filtroHasta, skip, activeOrgId])

  useEffect(() => { load() }, [load])

  // Recibir foto compartida desde WhatsApp (PWA share target)
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
      if (imagen) {
        setShowForm(true)
        setFormData(emptyForm())
        setFormFoto(imagen.dataUrl)
        setMsg('')
      }
    } catch {}
    sessionStorage.removeItem('compartido:destino')
    sessionStorage.removeItem('compartido:archivos')
    sessionStorage.removeItem('compartido:titulo')
    sessionStorage.removeItem('compartido:texto')
    sessionStorage.removeItem('compartido:ts')
    // limpiar query para no re-disparar al recargar
    const sp = new URLSearchParams(searchParams)
    sp.delete('compartido')
    setSearchParams(sp, { replace: true })
  }, [searchParams, setSearchParams, navigate])

  useEffect(() => {
    apiClient.client.get('/clientes/archivos').then(r => {
      const orgs: any[] = r.data?.organizaciones || []
      const list: ClienteOpt[] = []
      orgs.forEach(org => (org.clientes || []).forEach((c: any) => list.push({ id: c.id, nombre: c.nombre })))
      setClientes(list)
    }).catch(() => {})
  }, [])

  const handleFotoChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return
    const b64 = await toBase64(file)
    setFormFoto(b64)
  }

  const handleCreate = async () => {
    if (!formData.monto || formData.monto <= 0) { setMsg('El monto es requerido'); return }
    setSaving(true); setMsg('')
    try {
      const res = await apiClient.client.post('/cheques', {
        cliente_id:    formData.cliente_id || null,
        numero:        formData.numero || null,
        banco_origen:  formData.banco_origen || null,
        titular:       formData.titular || null,
        monto:         formData.monto,
        comision:      formData.comision || 0,
        fecha_emision: formData.fecha_emision || null,
        fecha_deposito: formData.fecha_deposito || null,
        notas:         formData.notas || null,
      })
      // Si hay foto, subirla
      if (formFoto && res.data.id) {
        await apiClient.client.post(`/cheques/${res.data.id}/foto`, { foto_base64: formFoto })
      }
      setShowForm(false); setFormData(emptyForm()); setFormFoto(null); load()
    } catch (e: any) { setMsg(e?.response?.data?.detail || 'Error al guardar') }
    finally { setSaving(false) }
  }

  const handleAcreditar = async () => {
    if (!acreditarId) return
    setActioning(true)
    try {
      await apiClient.client.post(`/cheques/${acreditarId}/acreditar`, { fecha_acred: actionDate || null })
      setAcreditarId(null); setActionDate(''); load()
    } catch (e: any) { setMsg(e?.response?.data?.detail || 'Error') }
    finally { setActioning(false) }
  }

  const handleRechazar = async () => {
    if (!rechazarId) return
    setActioning(true)
    try {
      await apiClient.client.post(`/cheques/${rechazarId}/rechazar`, { fecha_acred: actionDate || null })
      setRechazarId(null); setActionDate(''); load()
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
    try {
      const res = await apiClient.client.get(`/cheques/${id}/foto`)
      setFotoData(res.data.foto_base64)
    } catch { setFotoData(null) }
    finally { setLoadingFoto(false) }
  }

  const handleImportExcel = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return
    setImportando(true); setMsg('')
    const fd = new FormData()
    fd.append('file', file)
    try {
      const res = await apiClient.client.post('/cheques/importar', fd, {
        headers: { 'Content-Type': 'multipart/form-data' }
      })
      const { importados, errores } = res.data
      setMsg(`✓ ${importados} cheque${importados !== 1 ? 's' : ''} importado${importados !== 1 ? 's' : ''}${errores.length ? ` · ${errores.length} error(es)` : ''}`)
      load()
    } catch (e: any) { setMsg(e?.response?.data?.detail || 'Error al importar') }
    finally { setImportando(false); if (importRef.current) importRef.current.value = '' }
  }

  const pendientes  = cheques.filter(c => c.estado === 'pendiente')
  const totalPend   = pendientes.reduce((s, c) => s + c.monto, 0)
  const totalAcred  = cheques.filter(c => c.estado === 'acreditado').reduce((s, c) => s + c.monto, 0)
  const totalRech   = cheques.filter(c => c.estado === 'rechazado').reduce((s, c) => s + c.monto, 0)

  const formField = (key: keyof Cheque, label: string, type = 'text') => (
    <div>
      <label className="block text-xs text-gray-400 mb-1">{label}</label>
      <input type={type} value={(formData[key] as string | number) ?? ''}
        onChange={e => setFormData(p => ({ ...p, [key]: type === 'number' ? (parseFloat(e.target.value) || 0) : e.target.value }))}
        className={inputClass} />
    </div>
  )

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
          { label: 'Acreditados', value: fmt(totalAcred), sub: 'en el listado',              color: 'text-green-400'  },
          { label: 'Rechazados',  value: fmt(totalRech),  sub: 'en el listado',              color: 'text-red-400'    },
        ].map(s => (
          <div key={s.label} className="bg-white/3 border border-white/8 rounded-xl p-3">
            <p className="text-xs text-gray-500">{s.label}</p>
            <p className={`text-base font-semibold mt-1 ${s.color}`}>{s.value}</p>
            <p className="text-xs text-gray-600 mt-0.5">{s.sub}</p>
          </div>
        ))}
      </div>

      {/* Filters */}
      <div className="flex flex-wrap gap-2">
        <select value={filtroEstado} onChange={e => { setFiltroEstado(e.target.value); setSkip(0) }}
          className="bg-white/5 border border-white/10 rounded-lg px-3 py-1.5 text-sm text-gray-200 focus:outline-none">
          <option value="">Todos los estados</option>
          <option value="pendiente">Pendiente</option>
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

      {/* Table */}
      <div className="rounded-xl overflow-hidden border border-white/8">
        <div className="overflow-x-auto">
          <table className="w-full text-xs min-w-[720px]">
            <thead>
              <tr className="bg-white/4 text-left text-gray-400">
                <th className="px-3 py-2 font-medium">Fecha dep.</th>
                <th className="px-3 py-2 font-medium">Cliente</th>
                <th className="px-3 py-2 font-medium">Titular</th>
                <th className="px-3 py-2 font-medium">Banco</th>
                <th className="px-3 py-2 font-medium">N° cheque</th>
                <th className="px-3 py-2 font-medium text-right">Monto</th>
                <th className="px-3 py-2 font-medium text-right">Comisión</th>
                <th className="px-3 py-2 font-medium">Estado</th>
                <th className="px-3 py-2 font-medium">Acred.</th>
                <th className="px-3 py-2 font-medium">Acciones</th>
              </tr>
            </thead>
            <tbody>
              {loading ? (
                <tr><td colSpan={10} className="text-center py-8 text-gray-500">Cargando…</td></tr>
              ) : cheques.length === 0 ? (
                <tr><td colSpan={10} className="text-center py-8 text-gray-500">Sin cheques registrados</td></tr>
              ) : cheques.map((c, i) => (
                <tr key={c.id} className={`border-t border-white/5 hover:bg-white/2 ${i % 2 === 0 ? '' : 'bg-white/1'}`}>
                  <td className="px-3 py-2 text-gray-300">{fmtDate(c.fecha_deposito)}</td>
                  <td className="px-3 py-2 text-gray-200">{c.cliente_nombre || <span className="text-gray-500">—</span>}</td>
                  <td className="px-3 py-2 text-gray-300 max-w-[130px] truncate" title={c.titular || ''}>{c.titular || '—'}</td>
                  <td className="px-3 py-2 text-gray-400">{c.banco_origen || '—'}</td>
                  <td className="px-3 py-2 text-gray-400">{c.numero || '—'}</td>
                  <td className="px-3 py-2 text-right font-mono text-gray-100">{fmt(c.monto)}</td>
                  <td className="px-3 py-2 text-right font-mono text-gray-400">{c.comision > 0 ? fmt(c.comision) : '—'}</td>
                  <td className="px-3 py-2">
                    <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${ESTADO_BADGE[c.estado]}`}>{c.estado}</span>
                  </td>
                  <td className="px-3 py-2 text-gray-400">{fmtDate(c.fecha_acred)}</td>
                  <td className="px-3 py-2">
                    <div className="flex gap-1">
                      {c.tiene_foto && (
                        <button onClick={() => handleVerFoto(c.id)}
                          className="px-2 py-0.5 bg-indigo-600/20 hover:bg-indigo-600/40 text-indigo-400 rounded text-xs transition-colors"
                          title="Ver foto">📷</button>
                      )}
                      {c.estado === 'pendiente' && (
                        <>
                          <button onClick={() => { setAcreditarId(c.id); setActionDate('') }}
                            className="px-2 py-0.5 bg-green-600/20 hover:bg-green-600/40 text-green-400 rounded text-xs transition-colors">Acreditar</button>
                          <button onClick={() => { setRechazarId(c.id); setActionDate('') }}
                            className="px-2 py-0.5 bg-red-600/20 hover:bg-red-600/40 text-red-400 rounded text-xs transition-colors">Rechazar</button>
                          <button onClick={() => handleDelete(c.id)}
                            className="px-2 py-0.5 bg-white/5 hover:bg-white/10 text-gray-400 rounded text-xs transition-colors">✕</button>
                        </>
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

      {/* New cheque modal */}
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
                <label className="block text-xs text-gray-400 mb-1">Cliente</label>
                <select value={formData.cliente_id ?? ''}
                  onChange={e => setFormData(p => ({ ...p, cliente_id: e.target.value ? parseInt(e.target.value) : null }))}
                  className={inputClass}>
                  <option value="">Sin cliente</option>
                  {clientes.map(c => <option key={c.id} value={c.id}>{c.nombre}</option>)}
                </select>
              </div>
              {formField('titular', 'Titular / librador')}
              {formField('banco_origen', 'Banco origen')}
              {formField('numero', 'N° de cheque')}
              {formField('monto', 'Monto *', 'number')}
              {formField('comision', 'Comisión', 'number')}
              {formField('fecha_emision', 'Fecha emisión', 'date')}
              {formField('fecha_deposito', 'Fecha depósito', 'date')}
              <div className="col-span-2">
                <label className="block text-xs text-gray-400 mb-1">Notas</label>
                <textarea rows={2} value={formData.notas ?? ''}
                  onChange={e => setFormData(p => ({ ...p, notas: e.target.value }))}
                  className="w-full bg-white/5 border border-white/10 rounded px-3 py-1.5 text-sm text-gray-100 focus:outline-none focus:border-indigo-500 resize-none" />
              </div>
              {/* Foto del cheque */}
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

      {/* Acreditar modal */}
      {acreditarId && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4">
          <div className="bg-[#16161A] border border-white/10 rounded-xl p-5 w-full max-w-sm space-y-4">
            <h2 className="text-base font-semibold text-gray-100">Acreditar cheque</h2>
            <p className="text-sm text-gray-400">Asiento: Banco (D) / Créditos (H).</p>
            <div>
              <label className="block text-xs text-gray-400 mb-1">Fecha de acreditación</label>
              <input type="date" value={actionDate} onChange={e => setActionDate(e.target.value)} className={inputClass} />
              <p className="text-xs text-gray-500 mt-1">Si no se indica, se usa hoy.</p>
            </div>
            <div className="flex justify-end gap-2">
              <button onClick={() => setAcreditarId(null)} className="px-4 py-1.5 text-sm text-gray-400 hover:text-gray-200">Cancelar</button>
              <button onClick={handleAcreditar} disabled={actioning}
                className="px-4 py-1.5 bg-green-600 hover:bg-green-500 text-white text-sm rounded-lg disabled:opacity-50 transition-colors">
                {actioning ? 'Procesando…' : 'Confirmar'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Rechazar modal */}
      {rechazarId && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4">
          <div className="bg-[#16161A] border border-white/10 rounded-xl p-5 w-full max-w-sm space-y-4">
            <h2 className="text-base font-semibold text-gray-100">Rechazar cheque</h2>
            <p className="text-sm text-gray-400">Asiento: Pasivo cliente (D) / Créditos (H).</p>
            <div>
              <label className="block text-xs text-gray-400 mb-1">Fecha de rechazo</label>
              <input type="date" value={actionDate} onChange={e => setActionDate(e.target.value)} className={inputClass} />
              <p className="text-xs text-gray-500 mt-1">Si no se indica, se usa hoy.</p>
            </div>
            <div className="flex justify-end gap-2">
              <button onClick={() => setRechazarId(null)} className="px-4 py-1.5 text-sm text-gray-400 hover:text-gray-200">Cancelar</button>
              <button onClick={handleRechazar} disabled={actioning}
                className="px-4 py-1.5 bg-red-600 hover:bg-red-500 text-white text-sm rounded-lg disabled:opacity-50 transition-colors">
                {actioning ? 'Procesando…' : 'Confirmar'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Photo viewer modal */}
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
              <img src={fotoData} alt="comprobante" className="w-full rounded-lg object-contain max-h-[60vh]" />
            ) : (
              <div className="text-center py-8 text-gray-500 text-sm">No se pudo cargar la imagen</div>
            )}
          </div>
        </div>
      )}
    </div>
  )
}
