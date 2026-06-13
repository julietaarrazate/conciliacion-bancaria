import React, { useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'
import { apiClient } from '@/services/api'

const fmtARS = (n: number) =>
  new Intl.NumberFormat('es-AR', { style: 'currency', currency: 'ARS', maximumFractionDigits: 0 }).format(n)

interface PaginaPublicaRow { titular?: string; monto: number; status: string }
interface PaginaPublicaPlanilla {
  id: number
  nombre_archivo: string
  fecha_carga: string
  acreditadas: number
  total: number
  rows: PaginaPublicaRow[]
}
interface PaginaPublicaCheque {
  numero?: string
  fecha_deposito?: string
  monto: number
  estado: string
}
interface PaginaPublicaData {
  cliente_nombre: string
  cliente_cuit?: string
  planillas: PaginaPublicaPlanilla[]
  cheques: PaginaPublicaCheque[]
}

export const PaginaPublica: React.FC = () => {
  const { token } = useParams<{ token: string }>()
  const [data, setData] = useState<PaginaPublicaData | null>(null)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    if (!token) { setError('Token no encontrado'); setLoading(false); return }
    apiClient.client.get(`/public/cliente/${token}`)
      .then(r => setData(r.data))
      .catch(e => setError(e.response?.data?.detail || 'Link inválido o expirado'))
      .finally(() => setLoading(false))
  }, [token])

  if (loading) return (
    <div className="min-h-screen bg-[#0B0B0F] flex items-center justify-center">
      <div className="text-gray-400 text-sm">Cargando...</div>
    </div>
  )

  if (error) return (
    <div className="min-h-screen bg-[#0B0B0F] flex items-center justify-center p-6 text-center">
      <div>
        <p className="text-white font-semibold mb-2">Link inválido o expirado</p>
        <p className="text-gray-500 text-sm">{error}</p>
      </div>
    </div>
  )

  if (!data) return null

  const totalConciliado = data.planillas.reduce((s, p) =>
    s + p.rows.filter(r => r.status === 'ok' || r.status === 'OK').reduce((a, r) => a + r.monto, 0), 0)
  const totalPendiente = data.planillas.reduce((s, p) =>
    s + p.rows.filter(r => !['ok', 'OK', 'duplicado'].includes(r.status)).reduce((a, r) => a + r.monto, 0), 0)

  return (
    <div className="min-h-screen bg-[#0B0B0F] text-white">
      <div className="max-w-2xl mx-auto px-4 py-8">
        {/* Header */}
        <div className="mb-6">
          <div className="flex items-center gap-2 text-gray-500 text-xs mb-3">
            <span className="w-5 h-5 bg-[#22C55E]/20 rounded-full flex items-center justify-center">
              <svg className="w-3 h-3 text-[#22C55E]" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" d="M9 12.75L11.25 15 15 9.75M21 12a9 9 0 11-18 0 9 9 0 0118 0z"/>
              </svg>
            </span>
            Estado de cuenta · Solo lectura
          </div>
          <h1 className="text-2xl font-bold">{data.cliente_nombre}</h1>
          {data.cliente_cuit && <p className="text-gray-500 text-sm mt-1">CUIT {data.cliente_cuit}</p>}
        </div>

        {/* KPIs */}
        <div className="grid grid-cols-2 gap-3 mb-6">
          <div className="bg-white/5 rounded-xl p-4 border border-white/10">
            <p className="text-xs text-gray-400 mb-1">Conciliado</p>
            <p className="text-xl font-bold text-green-400">{fmtARS(totalConciliado)}</p>
          </div>
          <div className="bg-white/5 rounded-xl p-4 border border-white/10">
            <p className="text-xs text-gray-400 mb-1">Pendiente</p>
            <p className="text-xl font-bold text-amber-400">{fmtARS(totalPendiente)}</p>
          </div>
        </div>

        {/* Planillas */}
        {data.planillas.length > 0 && (
          <div className="space-y-3 mb-6">
            <h2 className="text-sm font-semibold text-gray-300">Planillas</h2>
            {data.planillas.map((p) => (
              <div key={p.id} className="bg-white/5 rounded-xl border border-white/10 overflow-hidden">
                <div className="flex items-center justify-between px-4 py-3 border-b border-white/10">
                  <div>
                    <p className="text-sm font-medium">{p.nombre_archivo}</p>
                    <p className="text-xs text-gray-500">{p.fecha_carga}</p>
                  </div>
                  <span className="text-xs text-green-400 font-medium">{p.acreditadas}/{p.total} ok</span>
                </div>
                <div className="divide-y divide-white/5">
                  {p.rows.map((r, i) => (
                    <div key={i} className="flex items-center justify-between px-4 py-2 text-xs">
                      <span className="text-gray-400 truncate max-w-[180px]">{r.titular || '—'}</span>
                      <div className="flex items-center gap-3">
                        <span className="font-mono text-gray-300">{fmtARS(r.monto)}</span>
                        <span className={`px-1.5 py-0.5 rounded-full text-[10px] font-medium ${
                          r.status === 'ok' || r.status === 'OK'
                            ? 'bg-green-900/40 text-green-400'
                            : 'bg-amber-900/40 text-amber-400'
                        }`}>{r.status}</span>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            ))}
          </div>
        )}

        {/* Cheques */}
        {data.cheques.length > 0 && (
          <div className="space-y-2 mb-6">
            <h2 className="text-sm font-semibold text-gray-300">Cheques</h2>
            {data.cheques.map((c, i) => (
              <div key={i} className="flex items-center justify-between bg-white/5 rounded-lg px-4 py-3 border border-white/10">
                <div>
                  <p className="text-sm">{c.numero ? `#${c.numero}` : '—'}</p>
                  <p className="text-xs text-gray-500">{c.fecha_deposito || '—'}</p>
                </div>
                <div className="text-right">
                  <p className="font-mono text-sm">{fmtARS(c.monto)}</p>
                  <span className={`text-[10px] px-1.5 py-0.5 rounded-full font-medium ${
                    c.estado === 'acreditado' ? 'bg-green-900/40 text-green-400' :
                    c.estado === 'rechazado' ? 'bg-red-900/40 text-red-400' :
                    'bg-amber-900/40 text-amber-400'
                  }`}>{c.estado}</span>
                </div>
              </div>
            ))}
          </div>
        )}

        <p className="text-center text-xs text-gray-600 mt-8">Cuadra · Conciliación bancaria</p>
      </div>
    </div>
  )
}
