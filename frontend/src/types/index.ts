export interface User {
  id: number
  email: string
  full_name: string | null
  is_active: boolean
}

export interface BankAccount {
  id: number
  name: string
  account_number: string
  bank_name: string
  currency: string
  user_id: number
  created_at: string
}

export interface BankStatement {
  id: number
  account_id: number
  period_start: string
  period_end: string
  opening_balance: string
  closing_balance: string
  status: 'draft' | 'processing' | 'closed'
  imported_at: string
}

export type EstadoTxn =
  | 'pendiente'
  | 'acreditado'
  | 'no_esta'
  | 'faltan_datos'
  | 'duplicado'

export interface BankTransaction {
  id: number
  statement_id: number
  transaction_date: string
  description: string
  amount: string
  reference: string | null
  is_reconciled: boolean
  cliente_id: number | null
  planilla_movimiento_id: number | null
  estado: EstadoTxn
  fecha_acreditacion_original: string | null
  es_manual: boolean
}

export interface AccountingEntry {
  id: number
  account_id: number
  entry_date: string
  description: string
  amount: string
  reference: string | null
  is_reconciled: boolean
}

export interface Reconciliation {
  id: number
  statement_id: number
  status: 'open' | 'in_progress' | 'closed'
  difference: string
  created_at: string
  closed_at: string | null
}

export interface ReconciliationItem {
  id: number
  reconciliation_id: number
  bank_transaction_id: number | null
  accounting_entry_id: number | null
  planilla_movimiento_id: number | null
  match_type: 'auto' | 'manual' | 'sync_planilla'
  estado: EstadoTxn
  observacion: string | null
  matched_at: string
}

export interface Cliente {
  id: number
  nombre: string
  cuit: string | null
  titular: string | null
  cuenta: string | null
  comision: string
  forma_pago: string | null
  activo: boolean
  created_at: string
}

export interface PlanillaCliente {
  id: number
  cliente_id: number
  nombre: string
  periodo: string | null
  created_at: string
}

export type EstadoMovPlanilla =
  | 'pendiente'
  | 'ok'
  | 'no_esta'
  | 'faltan_datos'
  | 'rechazado'

export interface MovimientoPlanilla {
  id: number
  planilla_id: number
  fecha: string
  descripcion: string
  monto: string
  referencia: string | null
  estado: EstadoMovPlanilla
  fecha_acreditacion: string | null
  datos_faltantes: string | null
  observacion: string | null
  updated_at: string
}

export interface Cheque {
  id: number
  cliente_id: number
  numero: string
  banco_emisor: string | null
  fecha_emision: string
  fecha_cobro: string
  monto: string
  comision: string
  estado: 'cargado' | 'acreditado' | 'rechazado'
  fecha_acreditacion: string | null
  motivo_rechazo: string | null
  created_at: string
}
