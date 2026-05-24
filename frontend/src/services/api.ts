import axios, { AxiosInstance } from 'axios'
import {
  User,
  AuthResponse,
  ExtractoBancario,
  Planilla,
  ConciliacionResultado,
  PlanillaHistorialItem,
  ExtractoHistorialItem,
  AuditoriaLog,
  PaginatedResponse,
  UserRole,
  ExtractoListItem,
  MovimientoFiltrado,
  MergeUMResult,
  MovimientosFiltros
} from '@/types'

// Detecta la URL del backend automaticamente:
// 1) VITE_API_URL (env var en build de Vercel/produccion)  → siempre tiene prioridad
// 2) IP LAN (ej: 192.168.1.8) → solo cuando se accede desde la red local en dev
// 3) localhost:8000 → fallback para desarrollo local
//
// IMPORTANTE: en produccion Vercel, el hostname es "*.vercel.app" (dominio, no IP).
// Si no hay VITE_API_URL, caer a localhost (no usar el dominio como IP de backend).
function detectApiUrl(): string {
  // Produccion: Vite reemplaza esto en build time con el valor real
  const envUrl = import.meta.env.VITE_API_URL as string | undefined
  if (envUrl && envUrl.trim() !== '') return envUrl.trim()

  // Desarrollo LAN: solo si el hostname es una IP privada (192.168.x.x, 10.x.x.x, 172.16-31.x.x)
  if (typeof window !== 'undefined' && window.location) {
    const host = window.location.hostname
    const isLanIp = /^(192\.168\.|10\.|172\.(1[6-9]|2\d|3[01])\.)/.test(host)
    if (isLanIp) {
      return `http://${host}:8000`
    }
  }

  return 'http://localhost:8000'
}

const API_BASE_URL = detectApiUrl()

class ApiClient {
  client: AxiosInstance   // público para endpoints puntuales
  private token: string | null = null

  constructor() {
    this.client = axios.create({
      baseURL: API_BASE_URL,
      timeout: 60000,
      headers: {
        'Content-Type': 'application/json'
      }
    })

    const stored = localStorage.getItem('token')
    if (stored) {
      this.setToken(stored)
    }

    this.client.interceptors.request.use((config) => {
      if (this.token) {
        config.headers.Authorization = `Bearer ${this.token}`
      }
      return config
    })

    this.client.interceptors.response.use(
      (res) => res,
      (err) => {
        if (err.response?.status === 401 && this.token) {
          this.clearToken()
          window.location.href = '/login'
        }
        return Promise.reject(err)
      }
    )
  }

  setToken(token: string) {
    this.token = token
    localStorage.setItem('token', token)
  }

  clearToken() {
    this.token = null
    localStorage.removeItem('token')
  }

  // Auth endpoints
  async register(email: string, full_name: string, password: string): Promise<User> {
    const res = await this.client.post('/auth/register', {
      email,
      full_name,
      password
    })
    return res.data
  }

  async login(email: string, password: string): Promise<AuthResponse> {
    const res = await this.client.post('/auth/login', {
      email,
      password
    })
    if (res.data.access_token) {
      this.setToken(res.data.access_token)
    }
    return res.data
  }

  async getCurrentUser(): Promise<User> {
    const res = await this.client.get('/me')
    return res.data
  }

  async forgotPassword(email: string): Promise<{ ok: boolean; mensaje: string }> {
    const res = await this.client.post('/auth/forgot-password', { email })
    return res.data
  }

  async resetPassword(token: string, newPassword: string): Promise<{ ok: boolean; mensaje: string }> {
    const res = await this.client.post('/auth/reset-password', {
      token,
      new_password: newPassword,
    })
    return res.data
  }

  // Analisis / reportes
  async getDashboard(params?: { periodo?: 'hoy' | 'semana' | 'mes'; anio?: number; mes?: number; org_id?: number }): Promise<any> {
    const res = await this.client.get('/analisis/dashboard', { params })
    return res.data
  }

  async getClientesAging(orgId?: number): Promise<any> {
    const res = await this.client.get('/analisis/clientes-aging', { params: { org_id: orgId } })
    return res.data
  }

  async getEstadoCuentaCliente(clienteId: number, desde?: string, hasta?: string): Promise<any> {
    const res = await this.client.get(`/analisis/cliente/${clienteId}/estado-cuenta`, {
      params: { desde, hasta },
    })
    return res.data
  }

  // Extractos endpoints
  async uploadExtraco(file: File, banco: string = 'Banco Macro'): Promise<ExtractoBancario> {
    const formData = new FormData()
    formData.append('file', file)

    const res = await this.client.post('/extractos/upload', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
      params: { banco }
    })
    return res.data
  }

  async getExtraco(id: number): Promise<ExtractoBancario> {
    const res = await this.client.get(`/extractos/${id}`)
    return res.data
  }

  // Planillas endpoints
  async uploadPlanilla(
    clienteNombre: string,
    extractoId: number,
    file: File
  ): Promise<Planilla> {
    const formData = new FormData()
    formData.append('file', file)

    const res = await this.client.post('/planillas/upload', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
      params: {
        cliente_nombre: clienteNombre,
        extracto_id: extractoId
      }
    })
    return res.data
  }

  async getPlanilla(id: number): Promise<Planilla> {
    const res = await this.client.get(`/planillas/${id}`)
    return res.data
  }

  async conciliarPlanilla(
    planillaId: number,
    fechaAcred: string = 'hoy',
    soloPendientes = false,
    comisionPct = 0
  ): Promise<ConciliacionResultado> {
    const params: Record<string, any> = { fecha_acred: fechaAcred, solo_pendientes: soloPendientes }
    if (comisionPct > 0) params.comision_pct = comisionPct
    const res = await this.client.post(`/planillas/${planillaId}/conciliar`, {}, { params })
    return res.data
  }

  // Historial
  async getHistorialPlanillas(params?: {
    skip?: number
    limit?: number
    cliente?: string
    desde?: string
    hasta?: string
    org_id?: number | null
  }): Promise<PaginatedResponse<PlanillaHistorialItem>> {
    const res = await this.client.get('/historial/planillas', { params })
    return res.data
  }

  async getHistorialExtractos(params?: {
    skip?: number
    limit?: number
  }): Promise<PaginatedResponse<ExtractoHistorialItem>> {
    const res = await this.client.get('/historial/extractos', { params })
    return res.data
  }

  // Auditoría
  async getAuditoria(params?: {
    skip?: number
    limit?: number
    tabla?: string
    accion?: string
  }): Promise<PaginatedResponse<AuditoriaLog>> {
    const res = await this.client.get('/auditoria', { params })
    return res.data
  }

  // Admin / usuarios
  async getUsers(params?: {
    skip?: number
    limit?: number
    role?: UserRole
  }): Promise<PaginatedResponse<User>> {
    const res = await this.client.get('/admin/users', { params })
    return res.data
  }

  async updateUser(
    userId: number,
    payload: { full_name?: string; role?: UserRole; is_active?: boolean }
  ): Promise<User> {
    const res = await this.client.patch(`/admin/users/${userId}`, payload)
    return res.data
  }

  async deleteUser(userId: number): Promise<void> {
    await this.client.delete(`/admin/users/${userId}`)
  }

  // Extractos: listar y filtrar movimientos, append UM
  async listExtractos(orgId?: number | null): Promise<{ total: number; items: ExtractoListItem[] }> {
    const res = await this.client.get('/extractos', { params: orgId ? { org_id: orgId } : {} })
    return res.data
  }

  async getMovimientos(
    extractoId: number,
    filters: MovimientosFiltros = {}
  ): Promise<{ extracto_id: number; total: number; items: MovimientoFiltrado[] }> {
    const params: Record<string, string | number | boolean> = {}
    Object.entries(filters).forEach(([k, v]) => {
      if (v !== undefined && v !== null && v !== '') params[k] = v
    })
    const res = await this.client.get(`/extractos/${extractoId}/movimientos`, { params })
    return res.data
  }

  async updateMovimiento(extractoId: number, movId: number, payload: Record<string, unknown>): Promise<void> {
    await this.client.patch(`/extractos/${extractoId}/movimientos/${movId}`, payload)
  }

  async deleteMovimiento(extractoId: number, movId: number): Promise<void> {
    await this.client.delete(`/extractos/${extractoId}/movimientos/${movId}`)
  }

  async guardarEnCarpeta(planillaId: number): Promise<{ path?: string; blob: Blob }> {
    const res = await this.client.post(`/clientes/planillas/${planillaId}/guardar`, {}, { responseType: 'blob' })
    const savedPath = res.headers['x-saved-path'] as string | undefined
    return { path: savedPath, blob: new Blob([res.data]) }
  }

  async deleteExtracto(extractoId: number): Promise<void> {
    await this.client.delete(`/extractos/${extractoId}`)
  }

  async deleteTodosExtractos(): Promise<{ mensaje: string }> {
    const res = await this.client.delete('/extractos')
    return res.data
  }

  async deletePlanilla(planillaId: number): Promise<void> {
    await this.client.delete(`/planillas/${planillaId}`)
  }

  async patchRowStatus(rowId: number, status: string, comentario?: string, fechaAcred?: string): Promise<void> {
    await this.client.patch(`/planillas/rows/${rowId}`, { status, comentario, fecha_acred: fechaAcred })
  }

  async deleteRow(rowId: number): Promise<void> {
    await this.client.delete(`/planillas/rows/${rowId}`)
  }

  async appendUM(extractoId: number, file: File, corteSaldo?: number): Promise<MergeUMResult> {
    const formData = new FormData()
    formData.append('file', file)
    if (corteSaldo !== undefined) {
      formData.append('corte_saldo', String(corteSaldo))
    }
    const res = await this.client.post(
      `/extractos/${extractoId}/agregar-um`,
      formData,
      { headers: { 'Content-Type': 'multipart/form-data' } }
    )
    return res.data
  }

  async deleteUM(extractoId: number, forzarTodo = false): Promise<{ ok: boolean; eliminados: number }> {
    const res = await this.client.delete(`/extractos/${extractoId}/movimientos-um${forzarTodo ? '?forzar_todo=true' : ''}`)
    return res.data
  }

  // Exportar Excel
  async downloadPlanillaConciliada(planillaId: number): Promise<void> {
    const res = await this.client.get(`/planillas/${planillaId}/download`, { responseType: 'blob' })
    const url = URL.createObjectURL(new Blob([res.data]))
    const a = document.createElement('a')
    a.href = url
    a.download = `planilla_conciliada_${planillaId}.xlsx`
    a.click()
    URL.revokeObjectURL(url)
  }

  async exportMovimientos(extractoId: number, filters: MovimientosFiltros = {}): Promise<void> {
    const params: Record<string, string | number | boolean> = {}
    Object.entries(filters).forEach(([k, v]) => {
      if (v !== undefined && v !== null && v !== '') params[k] = v as string | number | boolean
    })
    const res = await this.client.get(`/extractos/${extractoId}/movimientos/export`, {
      params, responseType: 'blob'
    })
    const url = URL.createObjectURL(new Blob([res.data]))
    const a = document.createElement('a')
    a.href = url
    a.download = `movimientos_${new Date().toISOString().slice(0,10)}.xlsx`
    a.click()
    URL.revokeObjectURL(url)
  }

  async exportExtractoContador(extractoId: number): Promise<void> {
    let res: any
    try {
      res = await this.client.get(`/extractos/${extractoId}/export-contador`, { responseType: 'blob' })
    } catch (err: any) {
      // Blob error response: read text to surface backend message
      if (err.response?.data instanceof Blob) {
        const text = await err.response.data.text()
        try {
          const parsed = JSON.parse(text)
          err.response.data = parsed
        } catch { /* not JSON, leave as-is */ }
      }
      throw err
    }
    const url = URL.createObjectURL(res.data)
    const a = document.createElement('a')
    const cd = res.headers['content-disposition'] || ''
    const match = cd.match(/filename="([^"]+)"/)
    a.download = match ? match[1] : `extracto_conciliado.xlsx`
    a.href = url; a.click()
    URL.revokeObjectURL(url)
  }

  async exportHistorial(params?: { cliente?: string }): Promise<void> {
    const res = await this.client.get('/historial/planillas/export', {
      params, responseType: 'blob'
    })
    const url = URL.createObjectURL(new Blob([res.data]))
    const a = document.createElement('a')
    a.href = url
    a.download = `historial_${new Date().toISOString().slice(0,10)}.xlsx`
    a.click()
    URL.revokeObjectURL(url)
  }

  // ─── Conciliaciones (cross-extracto) ─────────────────────────
  async listConciliaciones(filters: {
    cliente?: string; titular?: string;
    desde?: string; hasta?: string;
    monto_min?: number; monto_max?: number;
    limit?: number; skip?: number;
  } = {}): Promise<{ total: number; items: any[]; suma: number }> {
    const params: Record<string, string | number> = {}
    Object.entries(filters).forEach(([k, v]) => {
      if (v !== undefined && v !== null && v !== '') params[k] = v as string | number
    })
    const res = await this.client.get('/conciliaciones', { params })
    return res.data
  }

  async exportConciliaciones(filters: {
    cliente?: string; titular?: string;
    desde?: string; hasta?: string;
    monto_min?: number; monto_max?: number;
  } = {}): Promise<void> {
    const params: Record<string, string | number> = {}
    Object.entries(filters).forEach(([k, v]) => {
      if (v !== undefined && v !== null && v !== '') params[k] = v as string | number
    })
    const res = await this.client.get('/conciliaciones/export', { params, responseType: 'blob' })
    const url = URL.createObjectURL(new Blob([res.data]))
    const a = document.createElement('a')
    const cd = res.headers['content-disposition'] || ''
    const match = cd.match(/filename="([^"]+)"/)
    a.download = match ? match[1] : `conciliaciones_${new Date().toISOString().slice(0,10)}.xlsx`
    a.href = url; a.click()
    URL.revokeObjectURL(url)
  }

  // Bulk reconciliar: multiples planillas de un mismo extracto
  async bulkConciliar(
    extractoId: number,
    planillas: { file: File; clienteNombre: string }[]
  ): Promise<ConciliacionResultado[]> {
    const resultados: ConciliacionResultado[] = []
    for (const p of planillas) {
      const planilla = await this.uploadPlanilla(p.clienteNombre, extractoId, p.file)
      const r = await this.conciliarPlanilla(planilla.id)
      resultados.push(r)
    }
    return resultados
  }
}

export const apiClient = new ApiClient()
