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
  is_superadmin: boolean
  organizacion_id?: number
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

export interface PlanillaHistorialItem {
  id: number
  cliente_nombre: string
  nombre_archivo: string
  fecha_carga: string
  usuario_nombre: string
  total_filas: number
  acreditadas: number
  no_encontradas: number
  duplicadas: number
  sin_datos: number
}

export interface ExtractoHistorialItem {
  id: number
  nombre_archivo: string
  fecha_creacion: string
  usuario_nombre: string
  total_movimientos: number
  acreditados: number
  banco?: string
}

export interface AuditoriaLog {
  id: number
  usuario_id: number
  usuario_nombre?: string
  usuario_email?: string
  tabla: string
  registro_id: number
  accion: string
  cambios?: Record<string, unknown> | null
  timestamp: string
}

export interface PaginatedResponse<T> {
  total: number
  items: T[]
}

export interface ExtractoListItem {
  id: number
  nombre_archivo: string
  fecha_creacion: string
  total_movimientos: number
  banco?: string
}

export interface MovimientoFiltrado {
  id: number
  extracto_id: number
  orden?: number
  fecha?: string | null
  mes?: string
  titular?: string
  monto: number
  saldo?: number
  cliente_acreditado?: string | null
  fecha_acred?: string | null
  source?: string  // 'extracto' | 'um'
}

export interface MergeUMResult {
  extracto_id: number
  agregados: number
  duplicados: number
  total_recibido: number
  corte_metodo?: string
  corte_saldo_detectado?: number
}

export interface MovimientosFiltros {
  cliente?: string
  cuit?: string
  titular?: string
  desde?: string
  hasta?: string
  fecha_desde?: string
  fecha_hasta?: string
  sin_acreditar?: boolean
  skip?: number
  limit?: number
}
