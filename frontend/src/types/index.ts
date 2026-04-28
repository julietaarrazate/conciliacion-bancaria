// Tipos globales de la aplicación

export enum UserRole {
  ADMIN = 'admin',
  OPERADOR = 'operador',
  REVISOR = 'revisor',
  AUDITOR = 'auditor'
}

export interface User {
  id: number
  email: string
  full_name: string
  role: UserRole
  is_active: boolean
  created_at: string
}

export interface AuthResponse {
  access_token: string
  token_type: string
  user: User
}

export interface MovimientoBanco {
  id: number
  orden?: number
  fecha?: string
  titular?: string
  monto: number
  cliente_acreditado?: string
  fecha_acred?: string
}

export interface ExtractoBancario {
  id: number
  nombre_archivo: string
  fecha_creacion: string
  fecha_extracto?: string
  movimientos: MovimientoBanco[]
}

export interface PlanillaRow {
  id: number
  monto: number
  cuit?: string
  titular?: string
  status: string
  orden_movimiento_acreditado?: number
}

export interface Planilla {
  id: number
  nombre_archivo: string
  cliente_id: number
  extracto_id: number
  fecha_carga: string
  rows: PlanillaRow[]
}

export interface ConciliacionResultado {
  planilla_id: number
  filas_procesadas: number
  acreditadas: number
  no_encontradas: number
  duplicadas: number
  sin_datos: number
}
