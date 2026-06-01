import React, { useEffect, useState } from 'react'
import { useSearchParams, useNavigate } from 'react-router-dom'
import { PlanillaPanel } from '@/components/PlanillaPanel'
import { apiClient } from '@/services/api'
import { Skeleton } from '@/components/Skeleton'
import { confirmDialog } from '@/store/confirm'
import { useOrgStore } from '@/store/org'
import { useAuthStore } from '@/store/auth'

interface Archivo {
  id: number
  nombre_archivo: string
  fecha_carga: string
  fecha_dia: string
  total: number
  acreditadas: number
}
interface MesArchivos {
  mes: string  // "2026/Mayo"
  archivos: Archivo[]
}
interface ClienteData {
  id: number
  nombre: string
  cuit?: string | null
  porcentaje_comision?: number | null
  porcentaje_comision_local?: number | null
  porcentaje_comision_interior?: number | null
  total_archivos: number
  meses: MesArchivos[]
}
interface OrgData {
  id: number
  nombre: string
  total_clientes: number
  clientes: ClienteData[]
}

const GRADIENTS = [
  'linear-gradient(135deg, #6366F1 0%, #8B5CF6 100%)',
  'linear-gradient(135deg, #3B82F6 0%, #06B6D4 100%)',
  'linear-gradient(135deg, #10B981 0%, #34D399 100%)',
  'linear-gradient(135deg, #F59E0B 0%, #EF4444 100%)',
  'linear-gradient(135deg, #EC4899 0%, #F43F5E 100%)',
  'linear-gradient(135deg, #14B8A6 0%, #6366F1 100%)',
  'linear-gradient(135deg, #F97316 0%, #FBBF24 100%)',
  'linear-gradient(135deg, #8B5CF6 0%, #EC4899 100%)',
  'linear-gradient(135deg, #06B6D4 0%, #10B981 100%)',
  'linear-gradient(135deg, #EF4444 0%, #F97316 100%)',
]
function hashNombre(n: string): number {
  let h = 0
  for (let i = 0; i < n.length; i++) h = (h * 31 + n.charCodeAt(i)) >>> 0
  return h % GRADIENTS.length
}

const ClienteAvatar: React.FC<{ nombre: string; size?: 'sm' | 'md' }> = ({ nombre, size = 'md' }) => {
  const idx = hashNombre(nombre)
  const letter = nombre.trim().charAt(0).toUpperCase()
  const dim = size === 'sm' ? 'w-7 h-7 text-xs' : 'w-9 h-9 text-sm'
  return (
    <span
      className={`${dim} rounded-xl flex items-center justify-center font-bold text-white shrink-0 select-none shadow-md`}
      style={{ background: GRADIENTS[idx] } as any}
    >
      {letter}
    </span>
  )
}

const fmtFecha = (s: string) => {
  try { return new Date(s + 'Z').toLocaleDateString('es-AR', { day: '2-digit', month: '2-digit', year: '2-digit', hour: '2-digit', minute: '2-digit' }) }
  catch { return s }
}

export const Clientes: React.FC = () => {
  const [searchParams, setSearchParams] = useSearchParams()
  const { activeOrgId } = useOrgStore()
  const navigate = useNavigate()
  const puedeVerCtaCte = useAuthStore(s => s.hasPermission('view_accounting'))
  const canDelete = useAuthStore(s => s.hasPermission('delete_records'))
  const [orgs, setOrgs] = useState<OrgData[]>([])
  const [loading, setLoading] = useState(true)

  // Foto compartida desde WhatsApp para referenciar al acreditar
  const [fotoRef, setFotoRef] = useState<string | null>(null)
  const [fotoRefNombre, setFotoRefNombre] = useState<string>('')
  const [fotoRefVisible, setFotoRefVisible] = useState(true)
  const [openOrg, setOpenOrg] = useState<Record<number, boolean>>({})
  const [openCli, setOpenCli] = useState<Record<string, boolean>>({})
  const [openMes, setOpenMes] = useState<Record<string, boolean>>({})
  const [panelId, setPanelId] = useState<number | null>(null)
  const [savingId, setSavingId] = useState<number | null>(null)
  const [msg, setMsg] = useState('')

  // Form nuevo cliente
  const [creando, setCreando] = useState<number | null>(null) // org_id donde estoy creando
  const [nuevoNombre, setNuevoNombre] = useState('')
  const [nuevoCuit, setNuevoCuit] = useState('')
  const [creandoLoading, setCreandoLoading] = useState(false)

  // Editor comision por cliente (% general / TT)
  const [editComisionId, setEditComisionId] = useState<number | null>(null)
  const [editComisionVal, setEditComisionVal] = useState('')
  const [savingComision, setSavingComision] = useState(false)

  // Renombrar cliente
  const [renombrando, setRenombrando] = useState<number | null>(null)
  const [renombreVal, setRenombreVal] = useState('')
  const [savingRenombre, setSavingRenombre] = useState(false)

  // Fusionar clientes
  const [fusionandoId, setFusionandoId] = useState<number | null>(null) // source client id
  const [fusionTargetId, setFusionTargetId] = useState<number | ''>('')
  const [savingFusion, setSavingFusion] = useState(false)

  // Modal acreditar comprobante
  const [acreditarCli, setAcreditarCli] = useState<{ id: number; nombre: string } | null>(null)
  const [acrMonto, setAcrMonto] = useState('')
  const [acrFecha, setAcrFecha] = useState('')           // fecha de la transferencia
  const [acrFechaAcred, setAcrFechaAcred] = useState('') // fecha en que yo acredito (default hoy)
  const [acrRef, setAcrRef] = useState('')
  const [acrOrigen, setAcrOrigen] = useState('')
  const [acrCandidatos, setAcrCandidatos] = useState<any[]>([])
  const [acrLoading, setAcrLoading] = useState(false)
  const [acrConfirming, setAcrConfirming] = useState<number | null>(null)

  const abrirAcreditar = (cliente: { id: number; nombre: string }) => {
    setAcreditarCli(cliente)
    setAcrMonto(''); setAcrFecha(''); setAcrRef(''); setAcrOrigen('')
    setAcrFechaAcred(new Date().toISOString().slice(0, 10)) // hoy por default
    setAcrCandidatos([])
  }
  const cerrarAcreditar = () => {
    setAcreditarCli(null); setAcrCandidatos([])
  }
  const buscarCandidatos = async () => {
    if (!acreditarCli) return
    // al menos uno de los campos debe tener valor
    if (!acrMonto && !acrFecha && !acrRef && !acrOrigen) {
      setMsg('✗ Ingresá al menos un campo: importe, fecha, referencia u origen')
      return
    }
    setAcrLoading(true); setMsg('')
    try {
      const body: any = { referencia: acrRef, origen: acrOrigen }
      if (acrMonto) body.monto = parseFloat(acrMonto.replace(/\./g, '').replace(',', '.'))
      if (acrFecha) body.fecha = acrFecha
      const r = await apiClient.client.post(`/clientes/${acreditarCli.id}/buscar-movimiento`, body)
      setAcrCandidatos(r.data.candidatos || [])
      if (!r.data.candidatos?.length) setMsg(`✗ No se encontró ningún movimiento con esos datos`)
    } catch (e: any) {
      setMsg(`✗ ${e.response?.data?.detail || 'Error buscando'}`)
    } finally { setAcrLoading(false) }
  }
  const confirmarAcreditacion = async (movId: number) => {
    if (!acreditarCli) return
    setAcrConfirming(movId)
    try {
      // Usar la fecha de acreditacion explicita; si no, la fecha de la transferencia; si no, hoy
      const fechaAcred = acrFechaAcred || acrFecha || new Date().toISOString().slice(0, 10)
      await apiClient.client.post(`/clientes/movimientos/${movId}/acreditar`, {
        cliente_id: acreditarCli.id,
        fecha_acred: fechaAcred,
      })
      setMsg(`✓ Acreditado a ${acreditarCli.nombre}. Guardado en su carpeta.`)
      cerrarAcreditar()
      cargar()
    } catch (e: any) {
      setMsg(`✗ ${e.response?.data?.detail || 'Error al acreditar'}`)
    } finally { setAcrConfirming(null) }
  }

  const cargar = () => {
    setLoading(true)
    apiClient.getClientesArchivos(activeOrgId)
      .then((r: any) => {
        // Soporta dos formatos:
        // 1) Nuevo: { organizaciones: [{id, nombre, clientes: [...]}] }
        // 2) Viejo (fallback por SW cacheado): { clientes: [{nombre, meses: [...]}] }
        let data: OrgData[] = r.organizaciones || []
        if (data.length === 0 && Array.isArray(r.clientes)) {
          const clientesViejos = r.clientes.map((c: any, idx: number) => ({
            id: idx + 1,
            nombre: c.nombre,
            cuit: null,
            total_archivos: c.meses?.reduce((s: number, m: any) => s + m.archivos.length, 0) || 0,
            meses: c.meses || [],
          }))
          data = [{
            id: 1,
            nombre: 'Organización A',
            total_clientes: clientesViejos.length,
            clientes: clientesViejos,
          }]
        }
        setOrgs(data)
        if (data.length > 0) setOpenOrg(o => ({ ...o, [data[0].id]: true }))
      })
      .catch(() => setOrgs([]))
      .finally(() => setLoading(false))
  }

  useEffect(() => { cargar() }, [activeOrgId])

  // Detectar comprobante compartido desde /compartir
  useEffect(() => {
    if (searchParams.get('compartido') !== 'acreditar') return
    const archivosRaw = sessionStorage.getItem('compartido:archivos')
    if (archivosRaw) {
      try {
        const archivos = JSON.parse(archivosRaw) as { name: string; type: string; dataUrl: string }[]
        const imagen = archivos.find(a => a.type.startsWith('image/')) || archivos[0]
        if (imagen) {
          setFotoRef(imagen.dataUrl)
          setFotoRefNombre(imagen.name || 'comprobante')
          setFotoRefVisible(true)
        }
      } catch {}
    }
    sessionStorage.removeItem('compartido:destino')
    sessionStorage.removeItem('compartido:archivos')
    sessionStorage.removeItem('compartido:titulo')
    sessionStorage.removeItem('compartido:texto')
    sessionStorage.removeItem('compartido:ts')
    const sp = new URLSearchParams(searchParams)
    sp.delete('compartido')
    setSearchParams(sp, { replace: true })
  }, [searchParams, setSearchParams])

  const handleGuardar = async (id: number, clienteNombre: string) => {
    setSavingId(id)
    setMsg('')
    try {
      const { path, blob } = await apiClient.guardarEnCarpeta(id)
      if (path) {
        setMsg(`✓ Guardado en clientes/${clienteNombre}/...`)
      } else {
        const url = URL.createObjectURL(blob)
        const a = document.createElement('a')
        a.href = url; a.download = `${clienteNombre}_acreditado.xlsx`; a.click()
        URL.revokeObjectURL(url)
      }
    } catch { setMsg('✗ Error al guardar') }
    finally { setSavingId(null) }
  }

  const handleBorrarCliente = async (clienteId: number, clienteNombre: string, totalArchivos: number) => {
    const tieneArchivos = totalArchivos > 0
    const mensaje = tieneArchivos
      ? `Tiene ${totalArchivos} archivo(s) guardados. Se van a borrar TODOS los archivos y las acreditaciones quedarán sin cliente asignado.`
      : 'Sin archivos guardados.'
    if (!await confirmDialog({ title: `Borrar "${clienteNombre}"`, message: mensaje, confirmLabel: 'Borrar', danger: true })) return
    if (tieneArchivos && !await confirmDialog({ title: 'Última confirmación', message: `¿Borrar "${clienteNombre}" y sus ${totalArchivos} archivo(s)?`, confirmLabel: 'Sí, borrar todo', danger: true })) return

    setMsg('')
    try {
      await apiClient.client.delete(`/clientes/${clienteId}`, {
        params: tieneArchivos ? { force: true } : {}
      })
      apiClient.invalidateCache(activeOrgId ? `/clientes/archivos?org_id=${activeOrgId}` : '/clientes/archivos')
      setMsg(`✓ Cliente "${clienteNombre}" borrado`)
      cargar()
    } catch (e: any) {
      setMsg(`✗ ${e.response?.data?.detail?.message || e.response?.data?.detail || 'Error al borrar'}`)
    }
  }

  const handleCrearCliente = async (org_id: number) => {
    if (!nuevoNombre.trim()) return
    setCreandoLoading(true)
    setMsg('')
    try {
      await apiClient.client.post('/clientes', {
        nombre: nuevoNombre.trim(),
        cuit: nuevoCuit.trim() || null,
        organizacion_id: org_id,
      })
      setMsg(`✓ Cliente "${nuevoNombre.trim()}" creado`)
      setNuevoNombre(''); setNuevoCuit(''); setCreando(null)
      apiClient.invalidateCache(activeOrgId ? `/clientes/archivos?org_id=${activeOrgId}` : '/clientes/archivos')
      cargar()
    } catch (e: any) {
      setMsg(`✗ ${e.response?.data?.detail || 'Error al crear'}`)
    } finally { setCreandoLoading(false) }
  }

  const handleRenombrar = async (clienteId: number) => {
    if (!renombreVal.trim()) return
    setSavingRenombre(true)
    try {
      await apiClient.client.put(`/clientes/${clienteId}/renombrar`, { nombre: renombreVal.trim() })
      setMsg(`✓ Cliente renombrado a "${renombreVal.trim()}"`)
      setRenombrando(null)
      apiClient.invalidateCache(activeOrgId ? `/clientes/archivos?org_id=${activeOrgId}` : '/clientes/archivos')
      cargar()
    } catch (e: any) {
      setMsg(`✗ ${e.response?.data?.detail || 'Error al renombrar'}`)
    } finally { setSavingRenombre(false) }
  }

  const handleFusionar = async (sourceId: number, sourceNombre: string) => {
    if (!fusionTargetId) return
    const targetCliente = orgs.flatMap(o => o.clientes).find(c => c.id === fusionTargetId)
    if (!targetCliente) return
    if (!await confirmDialog({
      title: `Fusionar "${sourceNombre}" en "${targetCliente.nombre}"`,
      message: `Se reasignarán todas las planillas y movimientos de "${sourceNombre}" a "${targetCliente.nombre}". Esta acción no se puede deshacer.`,
      confirmLabel: 'Fusionar', danger: true,
    })) return
    setSavingFusion(true)
    try {
      const r = await apiClient.client.post(`/clientes/${sourceId}/fusionar`, { target_id: fusionTargetId })
      setMsg(`✓ ${r.data.mensaje} · ${r.data.planillas_reasignadas} planilla(s) reasignada(s)`)
      setFusionandoId(null); setFusionTargetId('')
      apiClient.invalidateCache(activeOrgId ? `/clientes/archivos?org_id=${activeOrgId}` : '/clientes/archivos')
      cargar()
    } catch (e: any) {
      setMsg(`✗ ${e.response?.data?.detail || 'Error al fusionar'}`)
    } finally { setSavingFusion(false) }
  }

  const handleGuardarComision = async (clienteId: number) => {
    setSavingComision(true)
    try {
      const pct = editComisionVal.trim() === '' ? null : parseFloat(editComisionVal.replace(',', '.'))
      await apiClient.client.put(`/clientes/${clienteId}/comision`, { porcentaje_comision: pct })
      apiClient.invalidateCache(activeOrgId ? `/clientes/archivos?org_id=${activeOrgId}` : '/clientes/archivos')
      cargar()
      setEditComisionId(null)
    } catch (e: any) {
      setMsg(`✗ ${e.response?.data?.detail || 'Error al guardar comisión'}`)
    } finally { setSavingComision(false) }
  }

  return (
    <div className="p-3 md:p-6 max-w-4xl mx-auto">
      <div className="mb-3">
        <h1 className="text-xl md:text-2xl font-bold dark:text-white">Clientes</h1>
        <p className="text-xs md:text-sm text-gray-500 dark:text-gray-400 mt-1">
          Carpetas de conciliaciones organizadas por organización · cliente · mes
        </p>
      </div>

      {/* Panel de referencia: foto compartida desde WhatsApp */}
      {fotoRef && fotoRefVisible && (
        <div className="mb-3 border border-indigo-500/40 bg-indigo-500/10 rounded-xl overflow-hidden">
          <div className="flex items-center justify-between px-3 py-2">
            <span className="text-xs text-indigo-300 font-medium">
              💸 Comprobante recibido · tocá un cliente y luego "Acreditar"
            </span>
            <button onClick={() => setFotoRefVisible(false)} className="text-indigo-400 hover:text-indigo-200 text-lg leading-none">✕</button>
          </div>
          <img
            src={fotoRef}
            alt={fotoRefNombre}
            className="w-full max-h-48 object-contain bg-black/20"
            onClick={() => {
              const w = window.open()
              if (w) { w.document.write(`<img src="${fotoRef}" style="max-width:100%;height:auto">`) }
            }}
          />
          <div className="px-3 py-1.5 text-[11px] text-indigo-400/70">
            {fotoRefNombre} · tocá la imagen para ampliar
          </div>
        </div>
      )}

      {msg && (
        <div className={`mb-3 px-3 py-2 rounded text-sm ${msg.startsWith('✓') ? 'bg-green-50 text-green-700 dark:bg-green-900/20 dark:text-green-300' : 'bg-red-50 text-red-700 dark:bg-red-900/20 dark:text-red-300'}`}>
          {msg}
        </div>
      )}

      {loading ? (
        <div className="space-y-2">
          {Array.from({ length: 4 }).map((_, i) => (
            <div key={i} className="card flex items-center justify-between gap-3">
              <div className="flex items-center gap-3 flex-1 min-w-0">
                <Skeleton className="w-8 h-8 rounded-lg shrink-0" />
                <div className="flex-1 space-y-1.5 min-w-0">
                  <Skeleton className="h-4 w-1/3" />
                  <Skeleton className="h-3 w-1/4" />
                </div>
              </div>
              <Skeleton className="h-6 w-16 shrink-0 rounded-full" />
            </div>
          ))}
        </div>
      ) : orgs.length === 0 ? (
        <div className="card p-8 text-center text-gray-400">Sin organizaciones</div>
      ) : (
        <div className="space-y-2">
          {orgs.map(org => {
            const orgOpen = openOrg[org.id]
            const totArchivos = org.clientes.reduce((s, c) => s + c.total_archivos, 0)
            return (
              <div key={org.id} className="card p-0 overflow-hidden">
                {/* Nivel 1: Organización */}
                <button
                  onClick={() => setOpenOrg(o => ({ ...o, [org.id]: !orgOpen }))}
                  className="w-full flex items-center gap-3 px-3 md:px-4 py-3 bg-gradient-to-r from-ml-yellow/20 to-transparent dark:from-amber-900/20 hover:bg-ml-gray-bg dark:hover:bg-ml-dark-hover transition-colors text-left"
                >
                  <span className="text-lg">🏢</span>
                  <div className="flex-1 min-w-0">
                    <p className="font-bold dark:text-white truncate">{org.nombre}</p>
                    <p className="text-[11px] text-gray-500 dark:text-gray-400">
                      {org.total_clientes} clientes · {totArchivos} conciliaciones
                    </p>
                  </div>
                  <span className="text-gray-400 dark:text-gray-500 text-xs">{orgOpen ? '▲' : '▼'}</span>
                </button>

                {orgOpen && (
                  <div className="border-t dark:border-slate-700">
                    {/* Botón crear cliente */}
                    <div className="px-3 md:px-4 py-2 bg-gray-50/50 dark:bg-slate-900/30 border-b dark:border-slate-700/50">
                      {creando === org.id ? (
                        <div className="flex flex-wrap items-center gap-1.5">
                          <input className="input-field text-xs flex-1 min-w-[120px]" placeholder="Nombre del cliente"
                            value={nuevoNombre} onChange={e => setNuevoNombre(e.target.value)}
                            onKeyDown={e => e.key === 'Enter' && handleCrearCliente(org.id)} autoFocus />
                          <input className="input-field text-xs w-32" placeholder="CUIT (opcional)"
                            value={nuevoCuit} onChange={e => setNuevoCuit(e.target.value)}
                            onKeyDown={e => e.key === 'Enter' && handleCrearCliente(org.id)} />
                          <button onClick={() => handleCrearCliente(org.id)} disabled={creandoLoading || !nuevoNombre.trim()}
                            className="px-2 py-1 text-xs bg-green-600 text-white rounded hover:bg-green-700 disabled:opacity-30">
                            {creandoLoading ? '⏳' : 'Crear'}
                          </button>
                          <button onClick={() => { setCreando(null); setNuevoNombre(''); setNuevoCuit('') }}
                            className="px-2 py-1 text-xs text-gray-500 hover:text-gray-700">✕</button>
                        </div>
                      ) : (
                        <button onClick={() => setCreando(org.id)}
                          className="text-xs text-blue-600 dark:text-blue-400 hover:underline flex items-center gap-1">
                          <span className="text-base leading-none">+</span> Nuevo cliente
                        </button>
                      )}
                    </div>

                    {/* Nivel 2: Clientes */}
                    {org.clientes.length === 0 ? (
                      <div className="px-6 py-4 text-xs text-gray-400 text-center">Sin clientes todavía</div>
                    ) : org.clientes.map(cliente => {
                      const cliKey = `${org.id}-${cliente.id}`
                      const cliOpen = openCli[cliKey]
                      const otrosClientes = org.clientes.filter(c => c.id !== cliente.id)
                      return (
                        <div key={cliente.id}>
                          {/* Fila renombrar (modo edición inline) */}
                          {renombrando === cliente.id && (
                            <div className="flex items-center gap-1.5 pl-6 pr-3 py-2 bg-amber-50 dark:bg-amber-900/10 border-b dark:border-slate-700/50">
                              <input
                                className="input-field text-xs flex-1"
                                value={renombreVal}
                                onChange={e => setRenombreVal(e.target.value)}
                                onKeyDown={e => { if (e.key === 'Enter') handleRenombrar(cliente.id); if (e.key === 'Escape') setRenombrando(null) }}
                                autoFocus
                                placeholder="Nuevo nombre"
                              />
                              <button onClick={() => handleRenombrar(cliente.id)} disabled={savingRenombre || !renombreVal.trim()}
                                className="px-2 py-1 text-xs bg-amber-500 text-white rounded hover:bg-amber-600 disabled:opacity-30">
                                {savingRenombre ? '⏳' : 'Guardar'}
                              </button>
                              <button onClick={() => setRenombrando(null)} className="px-1.5 py-1 text-xs text-gray-400 hover:text-gray-600">✕</button>
                            </div>
                          )}
                          {/* Fila fusionar */}
                          {fusionandoId === cliente.id && (
                            <div className="flex items-center gap-1.5 pl-6 pr-3 py-2 bg-purple-50 dark:bg-purple-900/10 border-b dark:border-slate-700/50">
                              <span className="text-xs text-purple-700 dark:text-purple-300 shrink-0">Fusionar en →</span>
                              <select
                                className="input-field text-xs flex-1"
                                value={fusionTargetId}
                                onChange={e => setFusionTargetId(Number(e.target.value))}
                              >
                                <option value="">— seleccioná el cliente destino —</option>
                                {otrosClientes.map(c => (
                                  <option key={c.id} value={c.id}>{c.nombre}</option>
                                ))}
                              </select>
                              <button onClick={() => handleFusionar(cliente.id, cliente.nombre)}
                                disabled={savingFusion || !fusionTargetId}
                                className="px-2 py-1 text-xs bg-purple-600 text-white rounded hover:bg-purple-700 disabled:opacity-30">
                                {savingFusion ? '⏳' : 'Fusionar'}
                              </button>
                              <button onClick={() => { setFusionandoId(null); setFusionTargetId('') }}
                                className="px-1.5 py-1 text-xs text-gray-400 hover:text-gray-600">✕</button>
                            </div>
                          )}
                          <div className="flex items-center gap-1 pl-3 md:pl-6 pr-2 md:pr-3 py-2.5 hover:bg-gray-50 dark:hover:bg-slate-700/40 transition-colors">
                            <button
                              onClick={() => setOpenCli(o => ({ ...o, [cliKey]: !cliOpen }))}
                              className="flex items-center gap-2 flex-1 min-w-0 text-left"
                            >
                              <ClienteAvatar nombre={cliente.nombre} size="sm" />
                              <div className="flex-1 min-w-0">
                                <p className="text-sm font-semibold dark:text-white truncate">{cliente.nombre}</p>
                                <p className="text-[11px] text-gray-500 dark:text-gray-400">
                                  {cliente.total_archivos} archivo{cliente.total_archivos !== 1 ? 's' : ''}
                                </p>
                              </div>
                            </button>
                            {/* Chip comisión (% general / TT) */}
                            {editComisionId === cliente.id ? (
                              <div className="flex items-center gap-1 flex-shrink-0" onClick={e => e.stopPropagation()}>
                                <input
                                  type="number" step="0.1" min="0" max="100"
                                  placeholder="%"
                                  className="input-field text-xs w-16 py-0.5 px-1.5"
                                  value={editComisionVal}
                                  onChange={e => setEditComisionVal(e.target.value)}
                                  onKeyDown={e => { if (e.key === 'Enter') handleGuardarComision(cliente.id); if (e.key === 'Escape') setEditComisionId(null) }}
                                  autoFocus
                                />
                                <button onClick={() => handleGuardarComision(cliente.id)} disabled={savingComision}
                                  className="px-1.5 py-0.5 text-[10px] bg-green-600 text-white rounded hover:bg-green-700 disabled:opacity-30">
                                  {savingComision ? '⏳' : '✓'}
                                </button>
                                <button onClick={() => setEditComisionId(null)}
                                  className="text-[10px] text-gray-400 hover:text-gray-600 px-0.5">✕</button>
                              </div>
                            ) : (
                              <button
                                onClick={(e) => { e.stopPropagation(); setEditComisionId(cliente.id); setEditComisionVal(cliente.porcentaje_comision != null ? String(cliente.porcentaje_comision) : '') }}
                                className={`px-2 py-1 text-[11px] rounded font-medium flex-shrink-0 transition-colors ${cliente.porcentaje_comision != null ? 'bg-amber-100 dark:bg-amber-900/40 text-amber-700 dark:text-amber-300 hover:bg-amber-200 dark:hover:bg-amber-900/60' : 'bg-gray-100 dark:bg-zinc-700 text-gray-500 dark:text-zinc-400 hover:bg-gray-200 dark:hover:bg-zinc-600'}`}
                                title="% comisión — click para editar"
                              >
                                {cliente.porcentaje_comision != null ? `${cliente.porcentaje_comision}%` : '% —'}
                              </button>
                            )}
                            <a
                              href={`/clientes/${cliente.id}/estado-cuenta`}
                              onClick={(e) => e.stopPropagation()}
                              className="px-2 py-1 text-[11px] bg-indigo-100 dark:bg-indigo-900/40 text-indigo-700 dark:text-indigo-300 rounded hover:bg-indigo-200 dark:hover:bg-indigo-900/60 font-medium flex-shrink-0"
                              title="Ver estado de cuenta del cliente"
                            >
                              📊<span className="hidden md:inline"> Estado</span>
                            </a>
                            {puedeVerCtaCte && (
                              <button
                                onClick={(e) => { e.stopPropagation(); navigate(`/cuentas-corrientes?cc=${cliente.id}`) }}
                                className="inline-flex items-center gap-1 px-2 py-1 text-[11px] bg-sky-100 dark:bg-sky-900/40 text-sky-700 dark:text-sky-300 rounded hover:bg-sky-200 dark:hover:bg-sky-900/60 font-medium flex-shrink-0"
                                title="Ver cuenta corriente del cliente"
                              >
                                <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" strokeWidth={1.8} viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" d="M3 21h18M4.5 21V10.5m4 10.5V10.5m7 10.5V10.5m4 10.5V10.5M3 10.5h18M12 3l9 4.5H3L12 3z"/></svg>
                                <span className="hidden md:inline">Cta. cte.</span>
                              </button>
                            )}
                            <button
                              onClick={(e) => { e.stopPropagation(); abrirAcreditar({ id: cliente.id, nombre: cliente.nombre }) }}
                              className="px-2 py-1 text-[11px] bg-emerald-100 dark:bg-emerald-900/40 text-emerald-700 dark:text-emerald-300 rounded hover:bg-emerald-200 dark:hover:bg-emerald-900/60 font-medium flex-shrink-0"
                              title="Acreditar transferencia desde comprobante"
                            >
                              💸<span className="hidden md:inline"> Acreditar</span>
                            </button>
                            <button
                              onClick={(e) => { e.stopPropagation(); setRenombrando(cliente.id); setRenombreVal(cliente.nombre) }}
                              className="hidden md:inline-flex p-1 text-amber-500 hover:text-amber-700 hover:bg-amber-50 dark:hover:bg-amber-900/20 rounded flex-shrink-0"
                              title="Renombrar cliente"
                            >
                              ✏️
                            </button>
                            {otrosClientes.length > 0 && (
                              <button
                                onClick={(e) => { e.stopPropagation(); setFusionandoId(cliente.id); setFusionTargetId('') }}
                                className="hidden md:inline-flex p-1 text-purple-500 hover:text-purple-700 hover:bg-purple-50 dark:hover:bg-purple-900/20 rounded flex-shrink-0"
                                title="Fusionar con otro cliente"
                              >
                                🔀
                              </button>
                            )}
                            {canDelete && (
                              <button
                                onClick={(e) => { e.stopPropagation(); handleBorrarCliente(cliente.id, cliente.nombre, cliente.total_archivos) }}
                                className="p-1 text-red-400 hover:text-red-600 hover:bg-red-50 dark:hover:bg-red-900/20 rounded flex-shrink-0"
                                title="Borrar cliente"
                              >
                                🗑
                              </button>
                            )}
                            <button onClick={() => setOpenCli(o => ({ ...o, [cliKey]: !cliOpen }))}
                              className="hidden md:block text-gray-400 text-xs px-1">{cliOpen ? '▲' : '▼'}</button>
                          </div>

                          {cliOpen && cliente.meses.length === 0 && (
                            <div className="pl-12 py-2 text-xs text-gray-400">Carpeta vacía — conciliá una planilla para que aparezca acá</div>
                          )}

                          {/* Nivel 3: Meses */}
                          {cliOpen && cliente.meses.map(mes => {
                            const mesKey = `${cliKey}-${mes.mes}`
                            const mesOpen = openMes[mesKey] !== false
                            return (
                              <div key={mes.mes}>
                                <button
                                  onClick={() => setOpenMes(o => ({ ...o, [mesKey]: !mesOpen }))}
                                  className="w-full flex items-center gap-2 pl-12 pr-3 py-2 bg-gray-50/50 dark:bg-slate-900/30 hover:bg-gray-100 dark:hover:bg-slate-700/30 text-left transition-colors"
                                >
                                  <span className="text-sm">📅</span>
                                  <span className="text-xs font-medium text-gray-700 dark:text-gray-300 flex-1">{mes.mes}</span>
                                  <span className="text-[10px] text-gray-400">{mes.archivos.length} {mesOpen ? '▲' : '▼'}</span>
                                </button>

                                {/* Nivel 4: Archivos */}
                                {mesOpen && (
                                  <div className="divide-y dark:divide-slate-700/50">
                                    {mes.archivos.map(a => {
                                      const pct = a.total > 0 ? Math.round((a.acreditadas / a.total) * 100) : 0
                                      return (
                                        <div key={a.id} className="flex items-center gap-2 pl-16 pr-3 py-2 hover:bg-gray-50 dark:hover:bg-slate-700/30 transition-colors">
                                          <span className="text-sm">📄</span>
                                          <div className="flex-1 min-w-0">
                                            <p className="text-xs truncate dark:text-gray-200" title={a.nombre_archivo}>
                                              <span className="text-gray-400 font-mono mr-1.5">{a.fecha_dia}</span>{a.nombre_archivo}
                                            </p>
                                            <p className="text-[10px] text-gray-400 dark:text-gray-500">
                                              {fmtFecha(a.fecha_carga)} · {a.acreditadas}/{a.total} ({pct}%)
                                            </p>
                                          </div>
                                          <div className="flex items-center gap-0.5 flex-shrink-0">
                                            <span className={`text-[10px] px-1.5 py-0.5 rounded-full font-medium ${pct === 100 ? 'bg-green-100 text-green-700 dark:bg-green-900/40 dark:text-green-300' : pct >= 80 ? 'bg-amber-100 text-amber-700 dark:bg-amber-900/40 dark:text-amber-300' : 'bg-red-100 text-red-700 dark:bg-red-900/40 dark:text-red-300'}`}>
                                              {pct}%
                                            </span>
                                            <button onClick={() => setPanelId(a.id)} className="p-1 text-blue-500 hover:text-blue-700 dark:text-blue-400" title="Ver detalle">👁️</button>
                                            <button onClick={() => handleGuardar(a.id, cliente.nombre)} disabled={savingId === a.id}
                                              className="p-1 text-purple-500 hover:text-purple-700 dark:text-purple-400 disabled:opacity-30" title="Exportar para contador">
                                              {savingId === a.id ? '⏳' : '📁'}
                                            </button>
                                            <button onClick={() => apiClient.downloadPlanillaConciliada(a.id)}
                                              className="p-1 text-green-600 hover:text-green-700 dark:text-green-400" title="Descargar Excel">⬇️</button>
                                          </div>
                                        </div>
                                      )
                                    })}
                                  </div>
                                )}
                              </div>
                            )
                          })}
                        </div>
                      )
                    })}
                  </div>
                )}
              </div>
            )
          })}
        </div>
      )}

      <PlanillaPanel planillaId={panelId} onClose={() => setPanelId(null)} />

      {/* Modal: Acreditar comprobante */}
      {acreditarCli && (
        <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-3" onClick={cerrarAcreditar}>
          <div className="bg-white dark:bg-slate-800 rounded-xl shadow-2xl max-w-md w-full p-4 max-h-[90vh] overflow-y-auto" onClick={e => e.stopPropagation()}>
            <div className="flex items-start justify-between mb-3">
              <div>
                <h2 className="text-base font-bold dark:text-white">Acreditar a {acreditarCli.nombre}</h2>
                <p className="text-xs text-gray-500 dark:text-gray-400 mt-0.5">
                  Buscá el movimiento en el extracto a partir de los datos del comprobante.
                </p>
              </div>
              <button onClick={cerrarAcreditar} className="text-gray-400 hover:text-gray-600 text-lg leading-none">✕</button>
            </div>

            {/* Foto de referencia dentro del modal si hay comprobante compartido */}
            {fotoRef && (
              <div className="mb-3 rounded-lg overflow-hidden border border-indigo-500/30 bg-black/20 cursor-pointer"
                onClick={() => { const w = window.open(); if (w) w.document.write(`<img src="${fotoRef}" style="max-width:100%;height:auto">`) }}>
                <img src={fotoRef} alt="comprobante" className="w-full max-h-32 object-contain" />
                <div className="px-2 py-1 text-[10px] text-indigo-400/70">Comprobante compartido · tocá para ampliar</div>
              </div>
            )}

            <div className="space-y-2 mb-3">
              <p className="text-[11px] text-gray-500 dark:text-gray-400 -mt-1 mb-1">
                Todos los campos son opcionales · llená al menos uno
              </p>
              <div className="grid grid-cols-2 gap-2">
                <div>
                  <label className="label text-xs">Importe</label>
                  <input className="input-field" placeholder="500000" value={acrMonto} onChange={e => setAcrMonto(e.target.value)} autoFocus />
                </div>
                <div>
                  <label className="label text-xs">Fecha transferencia</label>
                  <input type="date" className="input-field" value={acrFecha} onChange={e => setAcrFecha(e.target.value)} />
                </div>
              </div>
              <div>
                <label className="label text-xs">Código de referencia</label>
                <input className="input-field" placeholder="00194624" value={acrRef} onChange={e => setAcrRef(e.target.value)} />
              </div>
              <div>
                <label className="label text-xs">Origen / titular</label>
                <input className="input-field" placeholder="Walter Daniel Leguisa o DNI 20221499" value={acrOrigen} onChange={e => setAcrOrigen(e.target.value)} />
              </div>
              <div className="border-t border-gray-200 dark:border-slate-700 pt-2">
                <label className="label text-xs flex items-center gap-1">
                  Fecha de acreditación <span className="text-gray-400 font-normal">(en qué día lo acreditás)</span>
                </label>
                <input type="date" className="input-field" value={acrFechaAcred} onChange={e => setAcrFechaAcred(e.target.value)} />
              </div>
              <button onClick={buscarCandidatos} disabled={acrLoading}
                className="w-full mt-1 px-3 py-2 text-sm font-medium bg-ml-blue text-white rounded-md hover:bg-ml-blue-dark disabled:opacity-40">
                {acrLoading ? '⏳ Buscando...' : '🔍 Buscar coincidencias'}
              </button>
            </div>

            {acrCandidatos.length > 0 && (
              <div className="border-t dark:border-slate-700 pt-2">
                <p className="text-xs font-medium text-gray-600 dark:text-gray-300 mb-2">
                  {acrCandidatos.length} coincidencia{acrCandidatos.length !== 1 ? 's' : ''} encontrada{acrCandidatos.length !== 1 ? 's' : ''} · tocá la que corresponda
                </p>
                <div className="space-y-1.5 max-h-64 overflow-y-auto">
                  {acrCandidatos.map(c => {
                    const fechaTxt = c.fecha ? new Date(c.fecha + 'T00:00:00').toLocaleDateString('es-AR', { day:'2-digit', month:'2-digit' }) : '?'
                    const isMejor = c === acrCandidatos[0] && c.score >= 12
                    return (
                      <button key={c.id} onClick={() => confirmarAcreditacion(c.id)} disabled={acrConfirming === c.id}
                        className={`w-full text-left p-2 rounded border ${isMejor ? 'border-green-300 bg-green-50 dark:bg-green-900/20 dark:border-green-700' : 'border-gray-200 dark:border-slate-600 hover:bg-gray-50 dark:hover:bg-slate-700/30'} disabled:opacity-50`}>
                        <div className="flex justify-between items-start gap-2">
                          <div className="flex-1 min-w-0">
                            <p className="text-xs font-mono truncate dark:text-gray-200">{c.titular || '—'}</p>
                            <p className="text-[10px] text-gray-500 dark:text-gray-400">
                              {fechaTxt} · orden {c.orden} · ext #{c.extracto_id}
                              {c.razones?.length > 0 && <span className="ml-1 text-green-600 dark:text-green-400">· {c.razones.join(', ')}</span>}
                            </p>
                            {c.ya_acreditado_a_este_cliente && (
                              <p className="text-[10px] text-amber-600 dark:text-amber-400">⚠ ya está acreditado a {acreditarCli.nombre}</p>
                            )}
                            {c.ya_acreditado_a_otro && (
                              <p className="text-[10px] text-red-600 dark:text-red-400">⚠ ya acreditado a "{c.cliente_acreditado}" — confirmar pisa esa marca</p>
                            )}
                          </div>
                          <div className="text-right flex-shrink-0">
                            <p className="text-sm font-bold dark:text-white">${c.monto.toLocaleString('es-AR')}</p>
                            {isMejor && <span className="text-[9px] text-green-600 dark:text-green-400">👍 mejor</span>}
                          </div>
                        </div>
                      </button>
                    )
                  })}
                </div>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  )
}
