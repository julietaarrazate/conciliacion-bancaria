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

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'

class ApiClient {
  private client: AxiosInstance
  private token: string | null = null

  constructor() {
    this.client = axios.create({
      baseURL: API_BASE_URL,
      headers: {
        'Content-Type': 'application/json'
      }
    })

    // Cargar token del localStorage
    const stored = localStorage.getItem('token')
    if (stored) {
      this.setToken(stored)
    }

    // Interceptor para añadir token a requests
    this.client.interceptors.request.use((config) => {
      if (this.token) {
        config.headers.Authorization = `Bearer ${this.token}`
      }
      return config
    })
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

  // Extractos endpoints
  async uploadExtraco(file: File): Promise<ExtractoBancario> {
    const formData = new FormData()
    formData.append('file', file)

    const res = await this.client.post('/extractos/upload', formData, {
      headers: { 'Content-Type': 'multipart/form-data' }
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
    fechaAcred: string = 'hoy'
  ): Promise<ConciliacionResultado> {
    const res = await this.client.post(
      `/planillas/${planillaId}/conciliar`,
      {},
      { params: { fecha_acred: fechaAcred } }
    )
    return res.data
  }

  // Historial
  async getHistorialPlanillas(params?: {
    skip?: number
    limit?: number
    cliente?: string
    desde?: string
    hasta?: string
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

  // Extractos: listar y filtrar movimientos, append UM
  async listExtractos(): Promise<{ total: number; items: ExtractoListItem[] }> {
    const res = await this.client.get('/extractos')
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

  async appendUM(extractoId: number, file: File): Promise<MergeUMResult> {
    const formData = new FormData()
    formData.append('file', file)
    const res = await this.client.post(
      `/extractos/${extractoId}/agregar-um`,
      formData,
      { headers: { 'Content-Type': 'multipart/form-data' } }
    )
    return res.data
  }
}

export const apiClient = new ApiClient()
