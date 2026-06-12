import React, { useRef, useState } from 'react'
import { useLockStore } from '@/store/lock'

// Evita que el share sheet nativo dispare el bloqueo PIN.
export function suppressLockForShare() {
  try { useLockStore.getState().suppressLock(20000) } catch { /* noop */ }
}
// Supresión corta para el selector de archivos (cámara): se cierra en segundos.
export function suppressLockForCamera() {
  try { useLockStore.getState().suppressLock(8000) } catch { /* noop */ }
}

export const fmt = (n: number) =>
  new Intl.NumberFormat('es-AR', { style: 'currency', currency: 'ARS', minimumFractionDigits: 2 }).format(n)

export const fmtDate = (d?: string | null) =>
  d ? new Date(d + (d.includes('T') ? '' : 'T00:00:00')).toLocaleDateString('es-AR') : '—'

export interface Cheque {
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

export interface ClienteOpt { id: number; nombre: string; porcentaje_comision: number | null; porcentaje_comision_local: number | null; porcentaje_comision_interior: number | null; cuenta_contable_id: number | null }
export interface PortadorOpt { id: number; nombre: string }
export interface BancoCuenta { id: number; codigo: string; nombre: string }

export interface DepositoResumen {
  total: number
  por_cliente: { cliente: string; total: number; count: number }[]
  por_local_interior: { tipo: string; total: number; count: number }[]
}

export interface DepositoData {
  fecha: string
  items: Cheque[]
  resumen: DepositoResumen
}

export interface RechazarData {
  fecha_rechazo: string
  gastos_bancarios: string
  fisico: boolean
  fecha_devolucion: string
}

export const ESTADO_BADGE: Record<string, string> = {
  pendiente:  'bg-yellow-50 text-yellow-700 dark:bg-yellow-500/15 dark:text-yellow-400',
  registrado: 'bg-yellow-50 text-yellow-700 dark:bg-yellow-500/15 dark:text-yellow-400',
  depositado: 'bg-orange-50 text-orange-700 dark:bg-orange-500/15 dark:text-orange-400',
  acreditado: 'bg-green-50 text-green-700 dark:bg-green-500/15 dark:text-green-400',
  rechazado:  'bg-red-50 text-red-700 dark:bg-red-500/15 dark:text-red-400',
  anulado:    'bg-gray-100 text-gray-600 dark:bg-gray-500/15 dark:text-gray-400',
}
export const ESTADO_LABEL: Record<string, string> = {
  pendiente: 'Registrado', registrado: 'Registrado', depositado: 'Depositado',
  acreditado: 'Acreditado', rechazado: 'Rechazado', anulado: 'Anulado',
}
export const esRegistrado = (estado: string) => estado === 'registrado' || estado === 'pendiente'

export const emptyForm = () => ({
  cliente_id:          null as number | null,
  portador_id:         null as number | null,
  numero:              '',
  banco_origen:        '',
  librador:            '',
  codigo_postal:       '',
  local_interior:      '',
  monto:               0,
  porcentaje_comision: null as number | null,
  fecha_emision:       '',
  fecha_deposito:      '',
  notas:               '',
})

export type FormState = ReturnType<typeof emptyForm>

export const inputClass = "w-full bg-white dark:bg-[#ffffff08] border border-gray-200 dark:border-[#ffffff1a] rounded px-3 py-1.5 text-sm text-gray-800 dark:text-gray-100 focus:outline-none focus:border-indigo-500"

export const computeLI = (cp: string): string => {
  if (!cp) return ''
  const n = parseInt(cp.replace(/\D/g, ''), 10)
  if (isNaN(n)) return ''
  return n < 2000 ? 'local' : 'interior'
}

// % de comisión que corresponde a un cliente según local/interior, con
// fallback al % general. Devuelve null si el cliente no tiene ninguno.
export const pctParaCliente = (cli: ClienteOpt | null | undefined, li: string): number | null => {
  if (!cli) return null
  if (li === 'local'    && cli.porcentaje_comision_local    != null) return cli.porcentaje_comision_local
  if (li === 'interior' && cli.porcentaje_comision_interior != null) return cli.porcentaje_comision_interior
  return cli.porcentaje_comision ?? null
}

export const LiBadge: React.FC<{ value: string | null }> = ({ value }) => {
  if (!value) return <span className="text-gray-500">—</span>
  return (
    <span className={`px-1.5 py-0.5 rounded text-xs font-medium ${
      value === 'local' ? 'bg-blue-50 text-blue-700 dark:bg-blue-500/15 dark:text-blue-400' : 'bg-orange-50 text-orange-700 dark:bg-orange-500/15 dark:text-orange-400'
    }`}>
      {value === 'local' ? 'L' : 'I'}
    </span>
  )
}

export const toBase64 = (file: File): Promise<string> =>
  new Promise((resolve, reject) => {
    const reader = new FileReader()
    reader.onload = () => resolve(reader.result as string)
    reader.onerror = reject
    reader.readAsDataURL(file)
  })

export const compressScanner = (src: string, maxPx: number, quality: number): Promise<string> =>
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

export const shareChequePdf = async (c: Cheque, fotoB64: string): Promise<boolean> => {
  try {
    const { jsPDF } = await import('jspdf')
    const pdf = new jsPDF({ orientation: 'portrait', unit: 'mm', format: 'a4' })
    const nombre = c.cliente_nombre || c.librador || c.titular || 'Sin nombre'
    pdf.setFont('helvetica', 'bold'); pdf.setFontSize(13)
    pdf.text('COMPROBANTE DE CHEQUE', 105, 16, { align: 'center' })
    pdf.setFont('helvetica', 'normal'); pdf.setFontSize(9)
    pdf.text(`N° ${c.numero || '—'} · ${c.banco_origen || '—'}`, 105, 23, { align: 'center' })
    // Re-renderizar con fondo blanco y respetar aspect ratio (igual que Pagos)
    const { jpeg, w, h } = await new Promise<{ jpeg: string; w: number; h: number }>((resolve, reject) => {
      const img = new Image()
      img.onload = () => {
        const iw = img.naturalWidth || 1000; const ih = img.naturalHeight || 700
        const canvas = document.createElement('canvas')
        canvas.width = iw; canvas.height = ih
        const ctx = canvas.getContext('2d')
        if (!ctx) { reject(new Error('no ctx')); return }
        ctx.fillStyle = '#ffffff'; ctx.fillRect(0, 0, iw, ih); ctx.drawImage(img, 0, 0)
        resolve({ jpeg: canvas.toDataURL('image/jpeg', 0.85), w: iw, h: ih })
      }
      img.onerror = () => reject(new Error('img load'))
      img.src = fotoB64
    })
    const maxW = 190, maxH = 135, x0 = 10, y0 = 28
    const ratio = Math.min(maxW / w, maxH / h)
    const drawW = w * ratio, drawH = h * ratio
    pdf.addImage(jpeg, 'JPEG', x0 + (maxW - drawW) / 2, y0, drawW, drawH)
    pdf.setDrawColor(180, 180, 180); pdf.line(10, 169, 200, 169)
    pdf.setFontSize(10)
    const rows = [
      ['Cliente:', nombre], ['Importe:', fmt(c.monto)],
      ['Emisión:', fmtDate(c.fecha_emision)], ['Vencimiento:', fmtDate(c.fecha_deposito)],
      ['Estado:', c.estado], ['Generado:', new Date().toLocaleDateString('es-AR')],
    ]
    rows.forEach(([label, value], i) => {
      const y = 177 + i * 8
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

export const PortadorSelector: React.FC<{
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
            className="px-2.5 py-1.5 bg-gray-100 dark:bg-white/8 hover:bg-gray-200 dark:hover:bg-white/12 text-gray-700 dark:text-gray-300 text-sm rounded border border-gray-200 dark:border-white/10 transition-colors"
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
            className="px-2 py-1.5 bg-gray-100 dark:bg-white/8 hover:bg-gray-200 dark:hover:bg-white/12 text-gray-400 text-sm rounded transition-colors">✕</button>
        </div>
      )}
    </div>
  )
}

export const ClienteSelector: React.FC<{
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
            className="px-2.5 py-1.5 bg-gray-100 dark:bg-white/8 hover:bg-gray-200 dark:hover:bg-white/12 text-gray-700 dark:text-gray-300 text-sm rounded border border-gray-200 dark:border-white/10 transition-colors"
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
            className="px-2 py-1.5 bg-gray-100 dark:bg-white/8 hover:bg-gray-200 dark:hover:bg-white/12 text-gray-400 text-sm rounded transition-colors">✕</button>
        </div>
      )}
    </div>
  )
}
