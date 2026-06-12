import axios, { AxiosInstance, AxiosResponse } from 'axios'
import { localIsoDate } from '@/utils/fecha'
import {
  User,
  AuthResponse,
  PendingApproval,
  TwofaChallenge,
  LoginApprovalStatus,
  PendingRequest,
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
  MovimientosFiltros,
  ConciliacionItem,
  TarjetaUploadPreview,
  TarjetaCreatePayload,
  LiquidacionTarjeta,
} from '@/types'
import { useLockStore } from '@/store/lock'

// Evita que una descarga deliberada (PDF/Excel) dispare el bloqueo por PIN/huella:
// al abrir el diálogo de guardar, el navegador pierde foco un instante.
function _suppressLockForDownload() {
  try { useLockStore.getState().suppressLock() } catch { /* noop */ }
}

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

// Decide si una request fallida se debe reintentar (Render despertando / red).
// - 502/503/504: el proxy responde ANTES de ejecutar el handler → seguro reintentar
//   cualquier método (la operación no llegó a correr en el backend).
// - Sin respuesta (error de red / timeout): solo reintentar GET, para no arriesgar
//   duplicar una escritura (POST/PUT/DELETE) que sí pudo haber llegado al servidor.
const _MAX_RETRIES = 3

interface AxiosRetryConfig {
  __retryCount?: number
  method?: string
}

// err is typed as unknown because the axios interceptor receives Error | AxiosError
function _shouldRetry(err: unknown, cfg: AxiosRetryConfig): boolean {
  if ((cfg.__retryCount || 0) >= _MAX_RETRIES) return false
  const e = err as { response?: { status?: number }; code?: string; message?: string }
  const status = e?.response?.status
  if (status === 502 || status === 503 || status === 504) return true
  const noResponse = !e?.response
  const transientCode =
    e?.code === 'ERR_NETWORK' ||
    e?.code === 'ECONNABORTED' ||
    /network error|timeout/i.test(e?.message || '')
  const method = (cfg.method || 'get').toLowerCase()
  return noResponse && transientCode && method === 'get'
}

// Cache entry shape
interface CacheEntry { data: unknown; at: number }

class ApiClient {
  client: AxiosInstance   // público para endpoints puntuales
  private token: string | null = null
  private _cache = new Map<string, CacheEntry>()

  private _cacheKey(url: string, params?: Record<string, unknown>): string {
    return params ? `${url}?${JSON.stringify(params)}` : url
  }

  private _getCached(key: string, ttlMs: number): unknown {
    const e = this._cache.get(key)
    if (!e) return null
    if (Date.now() - e.at > ttlMs) { this._cache.delete(key); return null }
    return e.data
  }

  private _setCached(key: string, data: unknown): void {
    if (this._cache.size >= 60) {
      // evict oldest
      let oldestKey = ''
      let oldestAt = Infinity
      for (const [k, v] of this._cache) if (v.at < oldestAt) { oldestAt = v.at; oldestKey = k }
      if (oldestKey) this._cache.delete(oldestKey)
    }
    this._cache.set(key, { data, at: Date.now() })
  }

  // Invalida entradas cuya clave empieza con prefix. Sin prefix, limpia todo.
  invalidateCache(prefix?: string): void {
    if (!prefix) { this._cache.clear(); return }
    for (const k of this._cache.keys()) if (k.startsWith(prefix)) this._cache.delete(k)
  }

  private async _cached<T>(key: string, ttlMs: number, fetcher: () => Promise<T>): Promise<T> {
    const hit = this._getCached(key, ttlMs)
    if (hit !== null) return hit as T
    const data = await fetcher()
    this._setCached(key, data)
    return data
  }

  constructor() {
    this.client = axios.create({
      baseURL: API_BASE_URL,
      timeout: 60000,
      headers: {
        'Content-Type': 'application/json'
      }
    })

    // Migración única: mover token de localStorage a sessionStorage
    const legacy = localStorage.getItem('token')
    if (legacy) {
      sessionStorage.setItem('token', legacy)
      localStorage.removeItem('token')
    }
    const stored = sessionStorage.getItem('token')
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
      async (err) => {
        if (err.response?.status === 401 && this.token) {
          this.clearToken()
          window.location.href = '/login'
          return Promise.reject(err)
        }
        // Reintento automático ante errores transitorios (Render despertando tras
        // dormir, o red intermitente). Evita los errores "flash" al entrar por
        // primera vez o al cambiar de módulo: la request reintenta sola con backoff
        // en vez de propagar el error al componente.
        const cfg = err.config
        if (cfg && _shouldRetry(err, cfg)) {
          cfg.__retryCount = (cfg.__retryCount || 0) + 1
          await new Promise((r) => setTimeout(r, 1500 * cfg.__retryCount))  // 1.5s, 3s, 4.5s
          return this.client(cfg)
        }
        // Normalizar el detail de errores de validación de Pydantic (array de
        // objetos {type, loc, msg, ...}) a un string legible. Sin esto, los
        // componentes que renderizan err.response.data.detail directamente
        // crashean con "Objects are not valid as a React child" (error #31).
        const d = err.response?.data?.detail
        if (Array.isArray(d)) {
          err.response.data.detail = d
            .map((e: { msg?: string } | string) => (typeof e === 'string' ? e : e?.msg || 'Dato inválido'))
            .join(' · ')
        } else if (d && typeof d === 'object') {
          err.response.data.detail = (d as { msg?: string }).msg || JSON.stringify(d)
        }
        return Promise.reject(err)
      }
    )
  }

  setToken(token: string) {
    this.token = token
    sessionStorage.setItem('token', token)
  }

  clearToken() {
    this.token = null
    sessionStorage.removeItem('token')
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

  async login(email: string, password: string): Promise<AuthResponse | PendingApproval | TwofaChallenge> {
    const res = await this.client.post('/auth/login', {
      email,
      password
    })
    if (res.data.access_token) {
      this.setToken(res.data.access_token)
    }
    return res.data
  }

  // Login con aprobación en vivo (rol contador)
  async getLoginApprovalStatus(approvalId: number, secret: string): Promise<LoginApprovalStatus> {
    const res = await this.client.get(`/auth/login-approval/${approvalId}`, { params: { secret } })
    if (res.data?.access_token) {
      this.setToken(res.data.access_token)
    }
    return res.data
  }

  async getPendingApprovals(): Promise<PendingRequest[]> {
    const res = await this.client.get('/auth/pending-approvals')
    return res.data
  }

  async decideLoginApproval(approvalId: number, approve: boolean): Promise<{ status: string }> {
    const res = await this.client.post(`/auth/login-approval/${approvalId}/decide`, { approve })
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

  // Analisis / reportes — cacheados 60s para navegación fluida
  async getDashboard(params?: { periodo?: 'hoy' | 'semana' | 'mes'; anio?: number; mes?: number; org_id?: number }): Promise<any> {
    const key = this._cacheKey('/analisis/dashboard', params)
    return this._cached(key, 60_000, async () => {
      const res = await this.client.get('/analisis/dashboard', { params })
      return res.data
    })
  }

  async getClientesAging(orgId?: number): Promise<any> {
    const key = this._cacheKey('/analisis/clientes-aging', { org_id: orgId })
    return this._cached(key, 60_000, async () => {
      const res = await this.client.get('/analisis/clientes-aging', { params: { org_id: orgId } })
      return res.data
    })
  }

  async getEstadoCuentaCliente(clienteId: number, desde?: string, hasta?: string): Promise<any> {
    const key = this._cacheKey(`/analisis/cliente/${clienteId}/estado-cuenta`, { desde, hasta })
    return this._cached(key, 60_000, async () => {
      const res = await this.client.get(`/analisis/cliente/${clienteId}/estado-cuenta`, {
        params: { desde, hasta },
      })
      return res.data
    })
  }

  async downloadEstadoCuentaPdf(clienteId: number, desde?: string, hasta?: string): Promise<void> {
    _suppressLockForDownload()
    const res = await this.client.get(`/analisis/cliente/${clienteId}/estado-cuenta.pdf`, {
      params: { desde, hasta }, responseType: 'blob',
    })
    const disp: string = res.headers['content-disposition'] || ''
    const m = /filename="?([^"]+)"?/.exec(disp)
    const filename = m?.[1] || `estado_cuenta_${clienteId}.pdf`
    const url = URL.createObjectURL(new Blob([res.data], { type: 'application/pdf' }))
    const a = document.createElement('a')
    a.href = url
    a.download = filename
    a.click()
    URL.revokeObjectURL(url)
  }

  async generarShareLink(clienteId: number): Promise<{ token: string; url: string; expires_at: string; cliente_nombre: string }> {
    const res = await this.client.post(`/clientes/${clienteId}/share-link`)
    return res.data
  }

  async downloadCierreMensualXlsx(anio: number, mes: number, orgId?: number): Promise<void> {
    _suppressLockForDownload()
    const params: Record<string, number> = {}
    if (orgId) params.org_id = orgId
    const res = await this.client.get(`/analisis/cierre/${anio}/${mes}/export-xlsx`, {
      params,
      responseType: 'blob',
    })
    const url = URL.createObjectURL(res.data)
    const a = document.createElement('a')
    a.href = url
    const cd = res.headers['content-disposition'] || ''
    const match = cd.match(/filename="?([^"]+)"?/)
    a.download = match?.[1] || `cierre_${anio}_${String(mes).padStart(2, '0')}.xlsx`
    a.click()
    URL.revokeObjectURL(url)
  }

  async downloadCierreMensualPdf(anio: number, mes: number, orgId?: number): Promise<void> {
    _suppressLockForDownload()
    const res = await this.client.get(`/analisis/cierre/${anio}/${mes}.pdf`, {
      params: { org_id: orgId }, responseType: 'blob',
    })
    const disp: string = res.headers['content-disposition'] || ''
    const m = /filename="?([^"]+)"?/.exec(disp)
    const filename = m?.[1] || `cierre_${anio}_${mes}.pdf`
    const url = URL.createObjectURL(new Blob([res.data], { type: 'application/pdf' }))
    const a = document.createElement('a')
    a.href = url
    a.download = filename
    a.click()
    URL.revokeObjectURL(url)
  }

  async getEvolucion(meses: number = 6, orgId?: number): Promise<any> {
    const key = this._cacheKey('/analisis/evolucion', { meses, org_id: orgId })
    return this._cached(key, 60_000, async () => {
      const res = await this.client.get('/analisis/evolucion', { params: { meses, org_id: orgId } })
      return res.data
    })
  }

  async getFlujoCaja(meses: number = 6, orgId?: number): Promise<any> {
    const key = this._cacheKey('/analisis/flujo-caja', { meses, org_id: orgId })
    return this._cached(key, 60_000, async () => {
      const res = await this.client.get('/analisis/flujo-caja', { params: { meses, org_id: orgId } })
      return res.data
    })
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
    const params: Record<string, string | number | boolean> = { fecha_acred: fechaAcred, solo_pendientes: soloPendientes }
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
    org_id?: number | null
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
    org_id?: number | null
  }): Promise<PaginatedResponse<AuditoriaLog>> {
    const res = await this.client.get('/auditoria', { params })
    return res.data
  }

  // Admin / usuarios
  async getUsers(params?: {
    skip?: number
    limit?: number
    role?: UserRole
    org_id?: number
  }): Promise<PaginatedResponse<User>> {
    const res = await this.client.get('/admin/users', { params })
    return res.data
  }

  async updateUser(
    userId: number,
    payload: { full_name?: string; role?: UserRole; is_active?: boolean; organizacion_id?: number; allowed_org_ids?: number[] }
  ): Promise<User> {
    const res = await this.client.patch(`/admin/users/${userId}`, payload)
    return res.data
  }

  async listOrganizaciones(): Promise<{ id: number; nombre: string }[]> {
    const res = await this.client.get('/admin/organizaciones')
    return res.data
  }

  async getAllowedOrgs(): Promise<{ id: number; nombre: string }[]> {
    const res = await this.client.get('/me/allowed-orgs')
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
    const key = this._cacheKey(`/extractos/${extractoId}/movimientos`, params)
    return this._cached(key, 30_000, async () => {
      const res = await this.client.get(`/extractos/${extractoId}/movimientos`, { params })
      return res.data
    })
  }

  async getClientesArchivos(orgId?: number | null): Promise<any> {
    const cacheKey = orgId ? `/clientes/archivos?org_id=${orgId}` : '/clientes/archivos'
    return this._cached(cacheKey, 60_000, async () => {
      const res = await this.client.get('/clientes/archivos', { params: orgId ? { org_id: orgId } : {} })
      return res.data
    })
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

  async appendUM(extractoId: number, file: File, corteSaldo?: number, modoAsiento?: string): Promise<MergeUMResult> {
    const formData = new FormData()
    formData.append('file', file)
    if (corteSaldo !== undefined) {
      formData.append('corte_saldo', String(corteSaldo))
    }
    if (modoAsiento) {
      formData.append('modo_asiento', modoAsiento)
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

  async downloadCtaCtePdf(clienteId: number, orgId?: number): Promise<void> {
    _suppressLockForDownload()
    const params: Record<string, string | number> = { cliente_id: clienteId }
    if (orgId) params.org_id = orgId
    const res = await this.client.get('/contabilidad/cuenta-corriente/exportar-pdf', { params, responseType: 'blob' })
    const url = URL.createObjectURL(new Blob([res.data], { type: 'application/pdf' }))
    const a = document.createElement('a')
    a.href = url
    a.download = `cta_cte_${clienteId}.pdf`
    a.click()
    URL.revokeObjectURL(url)
  }

  // Exportar Excel
  async downloadPlanillaConciliada(planillaId: number): Promise<void> {
    _suppressLockForDownload()
    const res = await this.client.get(`/planillas/${planillaId}/download`, { responseType: 'blob' })
    const url = URL.createObjectURL(new Blob([res.data]))
    const a = document.createElement('a')
    a.href = url
    a.download = `planilla_conciliada_${planillaId}.xlsx`
    a.click()
    URL.revokeObjectURL(url)
  }

  async exportMovimientos(extractoId: number, filters: MovimientosFiltros = {}): Promise<void> {
    _suppressLockForDownload()
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
    a.download = `movimientos_${localIsoDate()}.xlsx`
    a.click()
    URL.revokeObjectURL(url)
  }

  async exportExtractoContador(extractoId: number): Promise<void> {
    _suppressLockForDownload()
    let res: AxiosResponse<Blob>
    try {
      res = await this.client.get(`/extractos/${extractoId}/export-contador`, { responseType: 'blob' })
    } catch (err) {
      // Blob error response: read text to surface backend message
      const e = err as { response?: { data?: Blob | unknown } }
      if (e.response?.data instanceof Blob) {
        const text = await (e.response.data as Blob).text()
        try {
          const parsed = JSON.parse(text)
          ;(e.response as { data: unknown }).data = parsed
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
    a.download = `historial_${localIsoDate()}.xlsx`
    a.click()
    URL.revokeObjectURL(url)
  }

  // ─── Conciliaciones (cross-extracto) ─────────────────────────
  async listConciliaciones(filters: {
    cliente?: string; titular?: string;
    desde?: string; hasta?: string;
    monto_min?: number; monto_max?: number;
    limit?: number; skip?: number;
    org_id?: number | null;
  } = {}): Promise<{ total: number; items: ConciliacionItem[]; suma: number }> {
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
    org_id?: number | null;
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
    a.download = match ? match[1] : `conciliaciones_${localIsoDate()}.xlsx`
    a.href = url; a.click()
    URL.revokeObjectURL(url)
  }

  async getAlertas(orgId?: number): Promise<{ total: number; alertas: { tipo: string; cantidad: number; label: string; urgencia: string; link: string }[] }> {
    const params: Record<string, number> = {}
    if (orgId) params.org_id = orgId
    const key = this._cacheKey('/analisis/alertas', params)
    return this._cached(key, 30_000, async () => {
      const res = await this.client.get('/analisis/alertas', { params })
      return res.data
    })
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

  // ─── Web Push ─────────────────────────────────────────────────
  async getPushPublicKey(): Promise<string | null> {
    const res = await this.client.get('/push/public-key')
    return res.data.vapid_public_key || null
  }

  async subscribePush(subscription: PushSubscriptionJSON): Promise<void> {
    await this.client.post('/push/subscribe', {
      endpoint: subscription.endpoint,
      keys: subscription.keys,
    })
  }

  async unsubscribePush(endpoint: string): Promise<void> {
    await this.client.delete('/push/subscribe', { data: { endpoint, keys: {} } })
  }

  async setupVapid(): Promise<{ vapid_public_key: string; vapid_private_key: string; instrucciones: string }> {
    const res = await this.client.post('/push/setup')
    return res.data
  }

  // ── Liquidaciones de tarjetas (Visa / Mastercard / Amex) ──────────────────
  async uploadTarjeta(file: File, marca: string): Promise<TarjetaUploadPreview> {
    const formData = new FormData()
    formData.append('file', file)
    const res = await this.client.post('/tarjetas/upload', formData, {
      params: { marca },
      headers: { 'Content-Type': 'multipart/form-data' },
    })
    return res.data
  }

  async createTarjeta(payload: TarjetaCreatePayload, orgId?: number): Promise<LiquidacionTarjeta> {
    const res = await this.client.post('/tarjetas', payload, {
      params: orgId ? { org_id: orgId } : {},
    })
    return res.data
  }

  async listTarjetas(params: {
    orgId?: number; marca?: string; estado?: string; periodo?: string; skip?: number; limit?: number
  } = {}): Promise<{ total: number; items: LiquidacionTarjeta[] }> {
    const q: Record<string, string | number> = {}
    if (params.orgId) q.org_id = params.orgId
    if (params.marca) q.marca = params.marca
    if (params.estado) q.estado = params.estado
    if (params.periodo) q.periodo = params.periodo
    if (params.skip != null) q.skip = params.skip
    if (params.limit != null) q.limit = params.limit
    const res = await this.client.get('/tarjetas', { params: q })
    return res.data
  }

  async conciliarTarjeta(liqId: number, extractoMovimientoId: number): Promise<any> {
    const res = await this.client.patch(`/tarjetas/${liqId}/conciliar`, {
      extracto_movimiento_id: extractoMovimientoId,
    })
    return res.data
  }

  async deleteTarjeta(liqId: number): Promise<void> {
    await this.client.delete(`/tarjetas/${liqId}`)
  }

  // ─── Export Contable ──────────────────────────────────────────
  async downloadAsientosContable(
    formato: string,
    desde?: string,
    hasta?: string,
    orgId?: number,
  ): Promise<void> {
    _suppressLockForDownload()
    const params: Record<string, string | number> = { formato }
    if (desde) params.desde = desde
    if (hasta) params.hasta = hasta
    if (orgId) params.org_id = orgId
    const res = await this.client.get('/contabilidad/asientos/exportar-contable', {
      params,
      responseType: 'blob',
    })
    const cd: string = res.headers['content-disposition'] || ''
    const m = /filename="?([^"]+)"?/.exec(cd)
    const filename = m ? m[1] : `libro_diario_${localIsoDate()}.${formato === 'csv' || formato === 'regisoft' ? 'csv' : 'txt'}`
    const url = URL.createObjectURL(new Blob([res.data]))
    const a = document.createElement('a')
    a.href = url
    a.download = filename
    a.click()
    URL.revokeObjectURL(url)
    // Devolver advertencias de cuentas sin mapeo al llamador
    const sinMapeo: string = res.headers['x-cuentas-sin-mapeo'] || ''
    if (sinMapeo) {
      // Lanzar un error especial para que el llamador muestre warning
      const err = Object.assign(new Error('cuentas_sin_mapeo'), {
        cuentas: sinMapeo.split(',').filter(Boolean),
      })
      throw err
    }
  }

  async getExportConfig(orgId?: number): Promise<{
    separador: string; encoding: string; formato_fecha: string;
    formato_default: string; mapeo_cuentas_export: Record<string, string>
  }> {
    const params: Record<string, number> = {}
    if (orgId) params.org_id = orgId
    const res = await this.client.get('/contabilidad/export-config', { params })
    return res.data
  }
}

export const apiClient = new ApiClient()
