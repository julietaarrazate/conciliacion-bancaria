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

export interface BankTransaction {
  id: number
  statement_id: number
  transaction_date: string
  description: string
  amount: string
  reference: string | null
  is_reconciled: boolean
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
  match_type: 'auto' | 'manual'
  matched_at: string
}
