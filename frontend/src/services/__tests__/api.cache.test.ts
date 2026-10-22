// Cache de GETs del ApiClient: dedupe de requests en vuelo, clave por organización,
// invalidación tras escrituras y al cambiar de token (otro usuario).
import { describe, it, expect, beforeEach } from 'vitest'
import type { InternalAxiosRequestConfig, AxiosResponse } from 'axios'
import { apiClient } from '@/services/api'

type Llamada = { method: string; url: string; params?: Record<string, unknown> }
let llamadas: Llamada[] = []
let respuestas: Record<string, unknown> = {}
let demora = 0

function instalarAdapter() {
  apiClient.client.defaults.adapter = async (config: InternalAxiosRequestConfig): Promise<AxiosResponse> => {
    llamadas.push({ method: (config.method || 'get').toLowerCase(), url: config.url || '', params: config.params })
    if (demora) await new Promise(r => setTimeout(r, demora))
    const orgId = (config.params as { org_id?: number } | undefined)?.org_id ?? 'todas'
    const data = respuestas[config.url || ''] ?? { url: config.url, org: orgId, n: llamadas.length }
    return { data, status: 200, statusText: 'OK', headers: {}, config }
  }
}

const gets = (url: string) => llamadas.filter(l => l.method === 'get' && l.url === url).length

beforeEach(() => {
  llamadas = []
  respuestas = {}
  demora = 0
  apiClient.invalidateCache()
  instalarAdapter()
})

describe('ApiClient cache', () => {
  it('dos pedidos simultáneos del mismo GET cacheable comparten una sola request', async () => {
    demora = 20
    const [a, b] = await Promise.all([apiClient.getAlertas(), apiClient.getAlertas()])
    expect(gets('/analisis/alertas')).toBe(1)
    expect(a).toBe(b)
  })

  it('la clave incluye la organización: org distinta → request distinta y datos de esa org', async () => {
    const a = await apiClient.getAlertas(1)
    const b = await apiClient.getAlertas(2)
    const a2 = await apiClient.getAlertas(1)
    expect(gets('/analisis/alertas')).toBe(2)
    expect((a as unknown as { org: number }).org).toBe(1)
    expect((b as unknown as { org: number }).org).toBe(2)
    expect(a2).toBe(a)
  })

  it('una escritura exitosa invalida lo cacheado (ej. agregar UM y recargar movimientos)', async () => {
    await apiClient.getMovimientos(1, { limit: 0 })
    await apiClient.getMovimientos(1, { limit: 0 })
    expect(gets('/extractos/1/movimientos')).toBe(1)
    await apiClient.updateMovimiento(1, 5, { titular: 'X' })
    await apiClient.getMovimientos(1, { limit: 0 })
    expect(gets('/extractos/1/movimientos')).toBe(2)
  })

  it('una respuesta que llega después de invalidar no queda guardada en el cache', async () => {
    demora = 20
    const p = apiClient.getAlertas()
    apiClient.invalidateCache()
    await p
    demora = 0
    await apiClient.getAlertas()
    expect(gets('/analisis/alertas')).toBe(2)
  })

  it('cambiar de token (otro usuario) vacía el cache', async () => {
    await apiClient.getAlertas()
    apiClient.setToken('token-otro-usuario')
    await apiClient.getAlertas()
    expect(gets('/analisis/alertas')).toBe(2)
    apiClient.clearToken()
  })

  it('un GET que falla no queda en vuelo ni cacheado', async () => {
    apiClient.client.defaults.adapter = async (config: InternalAxiosRequestConfig) => {
      llamadas.push({ method: 'get', url: config.url || '' })
      throw Object.assign(new Error('boom'), { config, response: { status: 500, data: {} } })
    }
    await expect(apiClient.getAlertas()).rejects.toThrow()
    instalarAdapter()
    await apiClient.getAlertas()
    expect(gets('/analisis/alertas')).toBe(2)
  })
})
