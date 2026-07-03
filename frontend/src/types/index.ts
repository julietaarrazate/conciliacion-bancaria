// Tipos globales de la aplicación

export enum UserRole {
  ADMIN = 'admin',
  OPERADOR = 'operador',
  REVISOR = 'revisor',
  AUDITOR = 'auditor',
  CONTADOR = 'contador'
}

export interface User {
  id: number
  email: string
  full_name: string
  role: UserRole
  is_active: boolean
  is_superadmin: boolean
  organizacion_id?: number
  allowed_org_ids?: number[]
  created_at: string
}

export interface AuthResponse {
  access_token: string
  token_type: string
  user: User
}

export interface PendingApproval {
  pending_approval: true
  approval_id: number
  poll_secret: string
  expires_at: string
}

export interface LoginApprovalStatus {
  status: 'pending' | 'approved' | 'denied' | 'expired'
  access_token?: string
  token_type?: string
  user?: User
}

export interface TwofaChallenge {
  requires_2fa: true
  email: string
}

export interface PendingRequest {
  id: number
  user_email: string
  user_name: string
  ip: string | null
  created_at: string
  expires_at: string
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
  monto_conciliado: number
  porcentaje_comision: number | null
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
  duplicados_internos?: number
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

export interface ConciliacionItem {
  id: number
  extracto_id: number
  orden: number | null
  fecha: string | null
  titular: string | null
  monto: number
  saldo: number | null
  cliente_acreditado: string
  fecha_acred: string | null
}

export interface TarjetaUploadPreview {
  marca?: string
  periodo?: string | null
  fecha_acreditacion?: string | null
  monto_bruto?: number | null
  aranceles?: number | null
  iva_df?: number | null
  percepciones_iibb?: number | null
  retenciones?: number | null
  neto?: number | null
  archivo_original?: string
  parse_warnings?: string[]
}

export interface TarjetaCreatePayload {
  marca: string
  periodo: string
  fecha_acreditacion: string
  monto_bruto: number
  aranceles: number
  iva_df: number
  percepciones_iibb: number
  retenciones: number
  neto: number
  notas?: string | null
  archivo_original?: string | null
}

export interface LiquidacionTarjeta {
  id: number
  organizacion_id: number
  marca: string
  periodo: string
  fecha_acreditacion: string
  monto_bruto: number
  aranceles: number
  iva_df: number
  percepciones_iibb: number
  retenciones: number
  neto: number
  estado: 'pendiente' | 'conciliada' | 'anulada'
  extracto_movimiento_id: number | null
  archivo_original: string | null
  asiento_id: number | null
  notas: string | null
  created_at: string
}

// ── IVA Proyección y DDJJ ───────────────────────────────────────────────────
export interface IvaConfigCuenta {
  id: number
  codigo: string
  nombre: string
  tipo: string
  es_ingreso: boolean
  tasa_iva: number | null
}

export interface IvaProyeccionDetalleItem {
  cuenta_id: number
  codigo: string
  nombre: string
  tipo: 'ingreso' | 'gasto'
  tasa_iva: number
  base_imponible: number
  iva: number
}

export interface IvaProyeccionPreview {
  periodo: string
  debito_fiscal: number
  credito_fiscal: number
  credito_fiscal_real: number
  credito_fiscal_proyectado: number
  saldo: number
  detalle: IvaProyeccionDetalleItem[]
}

export interface ProyeccionIva {
  id: number
  organizacion_id: number
  periodo: string
  debito_fiscal: number
  credito_fiscal: number
  saldo: number
  estado: 'proyectado' | 'presentado'
  fecha_presentacion: string | null
  detalle: IvaProyeccionDetalleItem[] | null
  created_at: string
  updated_at: string
}

// ── IVA — Comprobantes ARCA y Liquidación real ──────────────────────────────
export interface ComprobanteIva {
  id: number
  direccion: 'emitido' | 'recibido'
  fecha: string
  tipo_codigo: string
  tipo_desc: string
  punto_venta: number
  numero: string
  cuit_contraparte: string | null
  denominacion: string | null
  neto_gravado_total: number
  total_iva: number
  imp_total: number
  incluido: boolean
  es_nota_credito: boolean
}

export interface ComprobantesIvaResponse {
  items: ComprobanteIva[]
  totales: {
    debito_incluido: number
    credito_incluido: number
  }
}

export interface ImportarComprobantesIvaResult {
  importados: number
  duplicados: number
  fuera_de_periodo: number
  periodo: string
}

export interface LiquidacionIvaCalculoPayload {
  periodo: string
  retenciones?: number
  percepciones?: number
  saldo_tecnico_anterior?: number
  saldo_libre_anterior?: number
}

export interface LiquidacionIva {
  id: number
  periodo: string
  debito_fiscal: number
  credito_fiscal: number
  tecnico_periodo: number
  saldo_tecnico_anterior: number
  saldo_tecnico_nuevo: number
  retenciones: number
  percepciones: number
  saldo_libre_anterior: number
  saldo_libre_nuevo: number
  saldo_a_pagar: number
  cant_emitidos: number
  cant_recibidos: number
  estado: 'borrador' | 'presentada'
  fecha_presentacion: string | null
}

// ── Monotributo — Control Semestral ─────────────────────────────────────────
export interface MonotributoConfig {
  activo: boolean
  categoria_actual: string | null
  tipo_actividad: 'servicios' | 'bienes'
}

export interface CategoriaMonotributo {
  id: number
  categoria: string
  tipo_actividad: 'servicios' | 'bienes'
  limite_anual: number
  orden: number
}

export interface MonotributoDetalleMes {
  mes: string
  ingresos: number
}

export interface MonotributoControlPreview {
  periodo: string
  fecha_corte: string
  ingresos_12m: number
  categoria_actual: string
  limite_categoria_actual: number
  porcentaje_uso: number
  categoria_sugerida: string | null
  excede: boolean
  detalle: MonotributoDetalleMes[]
}

export interface ControlMonotributo {
  id: number
  organizacion_id: number
  periodo: string
  fecha_corte: string
  ingresos_12m: number
  categoria_actual: string
  limite_categoria_actual: number
  porcentaje_uso: number
  categoria_sugerida: string | null
  excede: boolean
  estado: 'pendiente' | 'revisado'
  fecha_revision: string | null
  detalle: MonotributoDetalleMes[]
  created_at: string
  updated_at: string
}

// ── Ingresos Brutos (IIBB) y Convenio Multilateral ──────────────────────────
export interface IIBBJurisdiccion {
  id: number
  nombre: string
  alicuota: number
  coeficiente_distribucion: number
  activa: boolean
  orden: number
}

export interface IIBBConfig {
  activo: boolean
  modo: 'simple' | 'convenio_multilateral'
  jurisdiccion_unica_id: number | null
}

export interface IIBBDetalleJurisdiccion {
  jurisdiccion_id: number
  nombre: string
  coeficiente: number
  ingreso_atribuido: number
  alicuota: number
  impuesto: number
}

export interface IIBBProyeccionPreview {
  periodo: string
  modo: 'simple' | 'convenio_multilateral'
  ingreso_total: number
  impuesto_total: number
  suma_coeficientes: number
  warning: string | null
  detalle: IIBBDetalleJurisdiccion[]
}

export interface IIBBProyeccion {
  id: number
  organizacion_id: number
  periodo: string
  ingreso_total: number
  impuesto_total: number
  detalle_por_jurisdiccion: IIBBDetalleJurisdiccion[] | null
  estado: 'proyectado' | 'presentado'
  fecha_presentacion: string | null
  created_at: string
  updated_at: string
}

// ── Sueldos y F931 ──────────────────────────────────────────────────────────
export interface SueldosConvenio {
  id: number
  nombre: string
  descripcion: string | null
  activo: boolean
}

export interface SueldosCategoria {
  id: number
  convenio_id: number
  nombre: string
  sueldo_basico: number
  orden: number
}

export interface SueldosEmpleado {
  id: number
  nombre: string
  cuil: string | null
  convenio_id: number | null
  categoria_id: number | null
  fecha_ingreso: string | null
  sueldo_basico: number | null
  cargas_familia: number
  activo: boolean
}

export interface SueldosConfig {
  activo: boolean
  aporte_jubilacion: number
  aporte_inssjp: number
  aporte_obra_social: number
  contrib_jubilacion: number
  contrib_inssjp: number
  contrib_obra_social: number
  contrib_asig_fam: number
  contrib_fondo_desempleo: number
  alicuota_art: number
  ganancias_activo: boolean
  minimo_no_imponible: number
  deduccion_especial: number
}

export interface EscalaGanancias {
  id: number
  tramo_desde: number
  tramo_hasta: number | null
  alicuota: number
  monto_fijo: number
}

export interface SueldosDetalleEmpleado {
  empleado_id: number
  nombre: string
  cuil: string | null
  sueldo_bruto: number
  sac_proporcional: number
  total_aportes: number
  total_contribuciones: number
  sueldo_neto: number
  retencion_ganancias?: number
  detalle_json: unknown
}

export interface SueldosLiquidacionPreview {
  periodo: string
  cantidad_empleados: number
  total_bruto: number
  total_aportes: number
  total_contribuciones: number
  total_neto: number
  f931: {
    total_remuneraciones: number
    total_aportes: number
    total_contribuciones: number
  }
  detalle: SueldosDetalleEmpleado[]
}

export interface SueldosLiquidacion {
  id: number
  organizacion_id: number
  periodo: string
  estado: 'borrador' | 'aprobado' | 'presentado'
  total_bruto: number
  total_aportes: number
  total_contribuciones: number
  total_neto: number
  fecha_aprobacion: string | null
  fecha_presentacion: string | null
  created_at: string
  updated_at: string
}

// ── ARCA (ex-AFIP) — facturación electrónica, integración propia WSFEv1 ────
export interface ArcaConfig {
  activo: boolean
  cuit: string | null
  ambiente: 'homologacion' | 'produccion'
  punto_venta: number
  tiene_certificado: boolean
  certificado_subido_en?: string | null
}

export interface ComprobanteArca {
  id: number
  cliente_id: number | null
  cliente_nombre: string | null
  tipo_comprobante: number
  punto_venta: number
  numero: number | null
  concepto: number
  doc_tipo: number
  doc_nro: string | null
  fecha_emision: string
  fecha_serv_desde: string | null
  fecha_serv_hasta: string | null
  fecha_vto_pago: string | null
  importe_neto: number
  importe_iva: number
  importe_total: number
  cae: string | null
  cae_vencimiento: string | null
  estado: 'borrador' | 'emitido' | 'rechazado' | 'error'
  error_detalle: string | null
  created_at: string
}

export interface ComprobanteArcaPayload {
  cliente_id?: number | null
  tipo_comprobante: number
  concepto?: number
  doc_tipo?: number
  doc_nro?: string | null
  importe_neto?: number
  importe_iva?: number
  importe_total: number
  fecha_serv_desde?: string | null
  fecha_serv_hasta?: string | null
  fecha_vto_pago?: string | null
}
