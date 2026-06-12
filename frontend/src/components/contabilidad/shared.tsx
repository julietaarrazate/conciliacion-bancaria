import React, { useEffect, useRef, useState } from 'react'

// ── Tipos ────────────────────────────────────────────────────
export interface CarteraItem {
  cliente_id: number
  cliente_nombre: string
  cuenta: { id: number; codigo: string; nombre: string } | null
  saldo: number
  ultimo_movimiento: string | null
  estado_general: 'deudor' | 'acreedor' | 'equilibrado' | 'sin_actividad'
  conciliacion: string
}

export interface CuentaCliente { id: number; codigo: string; nombre: string }
export interface ClienteCuentaRow {
  cliente_id: number
  cliente_nombre: string
  cuenta: CuentaCliente | null
}
export interface CtaCteOrigen {
  asiento_id: number
  planilla_id?: number
  movimiento_id?: number
  extracto_id?: number
  cheque_id?: number
  pago_id?: number
}
export interface CtaCteMov {
  fecha: string
  tipo_cat: 'banco' | 'tt' | 'cheques' | 'ajustes'
  tipo_label: string
  referencia: string
  debito: number
  credito: number
  saldo: number
  estado: string
  origen: CtaCteOrigen
}
export interface CtaCteData {
  cliente: { id: number; nombre: string }
  cuenta: CuentaCliente | null
  sin_cuenta: boolean
  movimientos: CtaCteMov[]
  total_debito: number
  total_credito: number
  saldo_final: number
}

export interface CuentaItem {
  id: number
  codigo: string
  nombre: string
  tipo: string | null
  parent_id: number | null
  nivel: number
  activo: boolean
}

export interface ReglaItem {
  id: number
  evento: string
  descripcion: string | null
  debe: { id: number; codigo: string; nombre: string }
  haber: { id: number; codigo: string; nombre: string }
}

export interface AsientoItem {
  id: number
  fecha: string
  descripcion: string | null
  modulo: string | null
  referencia_id: number | null
}

export interface AsientoLinea {
  id: number
  cuenta: { id: number; codigo: string; nombre: string }
  debe: number
  haber: number
}

export interface SumaRow {
  id: number
  codigo: string
  nombre: string
  tipo: string | null
  nivel: number
  total_debe: number
  total_haber: number
  saldo_deudor: number
  saldo_acreedor: number
}

export interface BalanceData {
  activo:    { total_debe: number; total_haber: number; saldo: number }
  pasivo:    { total_debe: number; total_haber: number; saldo: number }
  resultado: { total_debe: number; total_haber: number; saldo: number }
  ecuacion_ok: boolean
}

export interface LibroMayorData {
  cuenta: { id: number; codigo: string; nombre: string; tipo: string | null }
  movimientos: { fecha: string; descripcion: string | null; modulo: string | null; debe: number; haber: number; saldo: number }[]
  total_debe: number
  total_haber: number
  saldo_final: number
}

export interface FixPreview {
  asientos_afectados: number
  egresos_afectados: number
  detalle_asientos: any[]
  detalle_egresos: any[]
}

export type Tab = 'plan' | 'reglas' | 'diario' | 'sumas' | 'balance' | 'mayor' | 'clientes' | 'ctacte'
export type CcFiltro = 'todos' | 'deudores' | 'acreedores' | 'cero' | 'recientes' | 'sin_actividad'

// ── Constantes ───────────────────────────────────────────────
export const TIPO_BADGE: Record<string, string> = {
  activo:    'border-blue-200 text-blue-600 dark:border-blue-800 dark:text-blue-400',
  pasivo:    'border-orange-200 text-orange-600 dark:border-orange-800 dark:text-orange-400',
  resultado: 'border-green-200 text-green-600 dark:border-green-800 dark:text-green-400',
}
export const TIPO_TEXT: Record<string, string> = {
  activo:    'text-blue-700 dark:text-blue-300',
  pasivo:    'text-orange-700 dark:text-orange-300',
  resultado: 'text-green-700 dark:text-green-300',
}
export const TIPO_BG: Record<string, string> = {
  activo:    'bg-blue-50 dark:bg-blue-900/20 border-blue-200 dark:border-blue-800',
  pasivo:    'bg-orange-50 dark:bg-orange-900/20 border-orange-200 dark:border-orange-800',
  resultado: 'bg-green-50 dark:bg-green-900/20 border-green-200 dark:border-green-800',
}

export const MODULO_LABEL: Record<string, string> = {
  extracto: '🏦 Extracto', planilla: '📋 Planilla', caja: '💵 Caja', cheque: '🗒️ Cheque',
  ajuste_manual: '✏️ Ajuste manual', ajuste_manual_reverso: '↩️ Reverso ajuste',
  um_lote: '📥 UM lote', um_mov: '📥 UM mov', um_reclass: '🔀 Reclasif.', cc_inicial: '🔁 Backfill',
  cheque_registro: '🗒️ Cheque registro', cheque_acred_banco: '🗒️ Cheque banco', cheque_acred_cliente: '🗒️ Cheque cliente',
  cheque_rechazo_banco: '🗒️ Rechazo banco', cheque_rechazo_cliente: '🗒️ Rechazo cliente', cheque_rechazo_gasto: '🗒️ Rechazo gasto',
  egreso: '💸 Egreso', caja_op: '💵 Caja OP', caja_efectivo: '💵 Efectivo',
}

export const CAT_LABEL: Record<string, string> = { banco: 'TT', cheques: 'Cheques', ajustes: 'Ajustes' }
export const CAT_KEYS = ['banco', 'cheques', 'ajustes'] as const

export const ESTADO_BADGE: Record<string, string> = {
  Conciliado: 'bg-emerald-50 text-emerald-700 border-emerald-200 dark:bg-emerald-900/20 dark:text-emerald-300 dark:border-emerald-800',
  Pendiente:  'bg-amber-50 text-amber-700 border-amber-200 dark:bg-amber-900/20 dark:text-amber-300 dark:border-amber-800',
  Revertido:  'bg-red-50 text-red-700 border-red-200 dark:bg-red-900/20 dark:text-red-300 dark:border-red-800',
  Parcial:    'bg-blue-50 text-blue-700 border-blue-200 dark:bg-blue-900/20 dark:text-blue-300 dark:border-blue-800',
}

export const GEN_BADGE: Record<string, { label: string; cls: string }> = {
  deudor:        { label: 'Deudor',       cls: 'bg-blue-50 text-blue-700 border-blue-200 dark:bg-blue-900/20 dark:text-blue-300 dark:border-blue-800' },
  acreedor:      { label: 'Acreedor',     cls: 'bg-orange-50 text-orange-700 border-orange-200 dark:bg-orange-900/20 dark:text-orange-300 dark:border-orange-800' },
  equilibrado:   { label: 'Equilibrado',  cls: 'bg-emerald-50 text-emerald-700 border-emerald-200 dark:bg-emerald-900/20 dark:text-emerald-300 dark:border-emerald-800' },
  sin_actividad: { label: 'Sin actividad', cls: 'bg-gray-100 text-gray-500 border-gray-200 dark:bg-slate-800 dark:text-gray-400 dark:border-slate-600' },
}

export const TAB_PERM: Record<Tab, string> = {
  plan:     'view_accounting',
  reglas:   'view_accounting',
  diario:   'view_accounting',
  sumas:    'view_accounting',
  balance:  'view_accounting',
  mayor:    'view_accounting',
  clientes: 'view_accounting',
  ctacte:   'manage_finance',
}

// ── Helpers ──────────────────────────────────────────────────
export function fmtDate(s: string) {
  if (!s) return '—'
  try {
    const m = s.match(/^(\d{4})-(\d{2})-(\d{2})/)
    if (m) return new Date(+m[1], +m[2] - 1, +m[3]).toLocaleDateString('es-AR', { day: '2-digit', month: '2-digit', year: 'numeric' })
    return new Date(s.endsWith('Z') ? s : s + 'Z').toLocaleDateString('es-AR', { day: '2-digit', month: '2-digit', year: 'numeric' })
  }
  catch { return s }
}
export function fmtNum(n: number) { return n.toLocaleString('es-AR', { minimumFractionDigits: 2, maximumFractionDigits: 2 }) }

// ── Filtro desplegable tipo Excel ────────────────────────────
export const ExcelFilterCtb: React.FC<{ label: string; active: boolean; align?: 'left'|'right'; children: React.ReactNode }> = ({ label, active, align = 'left', children }) => {
  const [open, setOpen] = useState(false)
  const ref = useRef<HTMLDivElement>(null)
  useEffect(() => {
    const fn = (e: MouseEvent) => { if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false) }
    document.addEventListener('mousedown', fn)
    return () => document.removeEventListener('mousedown', fn)
  }, [])
  return (
    <div ref={ref} className="relative flex items-center gap-1 cursor-pointer select-none" onClick={() => setOpen(o => !o)}>
      <span>{label}</span>
      <span className={`text-[10px] ${active ? 'text-yellow-400' : 'text-blue-200'}`}>{active ? '▼●' : '▼'}</span>
      {open && (
        <div className={`absolute top-full mt-1 z-50 bg-white dark:bg-slate-800 border border-gray-200 dark:border-slate-600 rounded-lg shadow-xl p-3 min-w-[210px] ${align === 'right' ? 'right-0' : 'left-0'}`}
          onClick={e => e.stopPropagation()}>
          {children}
        </div>
      )}
    </div>
  )
}
