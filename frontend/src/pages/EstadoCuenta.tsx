import React, { useEffect, useMemo, useState } from 'react'
import { useParams, Link } from 'react-router-dom'
import { apiClient } from '@/services/api'
import { localIsoDate, isoHaceNDias } from '@/utils/fecha'

type Resumen = {
  conciliado_periodo: number
  pendiente_periodo: number
  cantidad_filas: number
  cantidad_planillas: number
  cheques_pendientes_monto: number
  cheques_acreditados_monto: number
  cheques_rechazados_monto: number
  pagos_realizados_monto: number
  porcentaje_comision: number
  comision_monto: number
  neto_calculado: number
}
type Fila = {
  id: number
  monto: number
  status: string
  status_norm: string
  titular: string | null
  cuit: string | null
  fecha_acred: string | null
}
type PlanillaData = {
  id: number
  nombre_archivo: string
  fecha_carga: string | null
  dias_antiguedad: number | null
  filas: Fila[]
  subtotal_ok: number
  subtotal_pendiente: number
}
type ChequeData = {
  id: number
  numero: string | null
  banco_origen: string | null
  titular: string | null
  monto: number
  fecha_emision: string | null
  fecha_deposito: string | null
  fecha_acred: string | null
  estado: string
}
type PagoData = {
  id: number
  concepto: string | null
  monto: number
  medio: string
  fecha: string | null
}
type EstadoCuentaData = {
  cliente: { id: number; nombre: string; cuit: string | null; organizacion_id: number; porcentaje_comision: number }
  periodo: { desde: string; hasta: string }
  resumen: Resumen
  planillas: PlanillaData[]
  cheques: ChequeData[]
  pagos: PagoData[]
}

function fmtMoney(n: number): string {
  return new Intl.NumberFormat('es-AR', { style: 'currency', currency: 'ARS', maximumFractionDigits: 0 }).format(n)
}

const fechaHaceNDias = isoHaceNDias

const PERIODOS = [
  { label: '30 días', dias: 30 },
  { label: '90 días', dias: 90 },
  { label: '6 meses', dias: 180 },
  { label: '1 año', dias: 365 },
]

export const EstadoCuenta: React.FC = () => {
  const { id } = useParams<{ id: string }>()
  const clienteId = Number(id)
  const [periodoDias, setPeriodoDias] = useState(90)
  const [data, setData] = useState<EstadoCuentaData | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [tab, setTab] = useState<'planillas' | 'cheques' | 'pagos'>('planillas')
  const [downloadingPdf, setDownloadingPdf] = useState(false)
  const [sharingLink, setSharingLink] = useState(false)
  const [linkCopiado, setLinkCopiado] = useState(false)

  const handleShare = async () => {
    setSharingLink(true)
    try {
      const { url } = await apiClient.generarShareLink(clienteId)
      await navigator.clipboard.writeText(url)
      setLinkCopiado(true)
      setTimeout(() => setLinkCopiado(false), 3000)
    } catch { /* ignore */ }
    finally { setSharingLink(false) }
  }

  const desde = useMemo(() => fechaHaceNDias(periodoDias), [periodoDias])
  const hasta = useMemo(() => localIsoDate(), [])

  useEffect(() => {
    if (!clienteId) return
    let activo = true
    setLoading(true)
    setError('')
    apiClient.getEstadoCuentaCliente(clienteId, desde, hasta)
      .then((d) => { if (activo) setData(d) })
      .catch((e) => {
        if (activo) {
          if (e.response?.status === 404) setError('Cliente no encontrado')
          else setError(e.response?.data?.detail || 'Error cargando estado de cuenta')
        }
      })
      .finally(() => { if (activo) setLoading(false) })
    return () => { activo = false }
  }, [clienteId, desde, hasta])

  if (loading && !data) {
    return <div className="p-6 text-ml-text-soft dark:text-zinc-500">Cargando estado de cuenta…</div>
  }
  if (error) {
    return (
      <div className="p-6">
        <p className="text-red-600 dark:text-red-400 mb-3">{error}</p>
        <Link to="/clientes" className="text-sm text-indigo-600 dark:text-ml-green hover:underline">← Volver a clientes</Link>
      </div>
    )
  }
  if (!data) return null

  const r = data.resumen

  return (
    <div className="p-4 sm:p-6 space-y-5 max-w-7xl">
      {/* Header */}
      <div>
        <Link to="/clientes" className="text-xs text-ml-text-soft hover:text-ml-text dark:text-zinc-500 dark:hover:text-ml-green mb-2 inline-block">
          ← Volver a clientes
        </Link>
        <div className="flex flex-col sm:flex-row sm:items-end sm:justify-between gap-3 mt-2">
          <div>
            <h1 className="text-2xl font-bold text-ml-text dark:text-white tracking-tight">{data.cliente.nombre}</h1>
            <p className="text-xs text-ml-text-soft dark:text-zinc-500 mt-1">
              Estado de cuenta {data.cliente.cuit ? `· CUIT ${data.cliente.cuit}` : ''}
            </p>
          </div>
          <div className="flex items-center gap-2 flex-wrap">
            <div className="flex items-center gap-1 bg-white dark:bg-ml-dark-surface rounded-lg border border-gray-200 dark:border-ml-dark-border p-1">
              {PERIODOS.map((p) => (
                <button
                  key={p.dias}
                  onClick={() => setPeriodoDias(p.dias)}
                  className={`px-3 py-1.5 text-xs rounded transition-colors ${
                    periodoDias === p.dias
                      ? 'bg-ml-text dark:bg-ml-green text-white dark:text-ml-dark-bg font-semibold'
                      : 'text-ml-text-soft dark:text-zinc-400 hover:bg-gray-50 dark:hover:bg-white/5'
                  }`}
                >
                  {p.label}
                </button>
              ))}
            </div>
            <button
              onClick={async () => {
                setDownloadingPdf(true)
                try { await apiClient.downloadEstadoCuentaPdf(clienteId, desde, hasta) }
                catch { /* el toast/error global puede manejarlo si se agrega */ }
                finally { setDownloadingPdf(false) }
              }}
              disabled={downloadingPdf || !data}
              className="px-3 py-1.5 text-xs rounded-lg bg-ml-text dark:bg-ml-green text-white dark:text-ml-dark-bg font-semibold hover:opacity-90 transition-opacity disabled:opacity-50"
              title="Descargar estado de cuenta en PDF"
            >
              {downloadingPdf ? 'Generando…' : '📄 PDF'}
            </button>
            <button
              onClick={handleShare}
              disabled={sharingLink}
              className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-indigo-600 dark:text-indigo-400 border border-indigo-200 dark:border-indigo-800 rounded-lg hover:bg-indigo-50 dark:hover:bg-indigo-900/20 transition-colors disabled:opacity-50"
            >
              {linkCopiado ? '✓ Link copiado' : '🔗 Compartir'}
            </button>
          </div>
        </div>
        <p className="text-[11px] text-ml-text-soft dark:text-zinc-600 mt-2">
          Periodo: {data.periodo.desde} → {data.periodo.hasta}
        </p>
      </div>

      {/* KPIs del cliente */}
      <div className="grid grid-cols-2 lg:grid-cols-3 gap-3">
        <div className="bg-emerald-50 dark:bg-emerald-950/30 border border-emerald-200 dark:border-emerald-900/40 rounded-xl p-4">
          <p className="text-[10px] uppercase tracking-wide text-emerald-700 dark:text-emerald-400 font-semibold">Conciliado</p>
          <p className="text-xl font-bold text-emerald-800 dark:text-emerald-300 mt-1">{fmtMoney(r.conciliado_periodo)}</p>
          <p className="text-[10px] text-emerald-700 dark:text-emerald-500 mt-1">{r.cantidad_filas} filas · {r.cantidad_planillas} planillas</p>
        </div>
        <div className="bg-amber-50 dark:bg-amber-950/30 border border-amber-200 dark:border-amber-900/40 rounded-xl p-4">
          <p className="text-[10px] uppercase tracking-wide text-amber-700 dark:text-amber-400 font-semibold">
            Comisión <span className="font-normal normal-case">({r.porcentaje_comision}%)</span>
          </p>
          <p className="text-xl font-bold text-amber-800 dark:text-amber-300 mt-1">{fmtMoney(r.comision_monto)}</p>
          <p className="text-[10px] text-amber-700 dark:text-amber-500 mt-1">
            Neto: <span className="font-semibold">{fmtMoney(r.neto_calculado)}</span>
          </p>
        </div>
        <div className="bg-indigo-50 dark:bg-indigo-950/30 border border-indigo-200 dark:border-indigo-900/40 rounded-xl p-4">
          <p className="text-[10px] uppercase tracking-wide text-indigo-700 dark:text-indigo-400 font-semibold">Pendiente</p>
          <p className="text-xl font-bold text-indigo-800 dark:text-indigo-300 mt-1">{fmtMoney(r.pendiente_periodo)}</p>
          <p className="text-[10px] text-indigo-700 dark:text-indigo-500 mt-1">no conciliado aún</p>
        </div>
      </div>

      {/* Fila secundaria: cheques y pagos */}
      <div className="grid grid-cols-2 gap-3">
        <div className="bg-white dark:bg-ml-dark-surface border border-gray-200 dark:border-ml-dark-border rounded-xl p-4">
          <p className="text-[10px] uppercase tracking-wide text-ml-text-soft dark:text-zinc-500 font-semibold">Cheques pendientes</p>
          <p className="text-lg font-bold text-ml-text dark:text-white mt-1">{fmtMoney(r.cheques_pendientes_monto)}</p>
          <p className="text-[10px] text-ml-text-soft dark:text-zinc-600 mt-1">en cartera</p>
        </div>
        <div className="bg-white dark:bg-ml-dark-surface border border-gray-200 dark:border-ml-dark-border rounded-xl p-4">
          <p className="text-[10px] uppercase tracking-wide text-ml-text-soft dark:text-zinc-500 font-semibold">Pagos al cliente</p>
          <p className="text-lg font-bold text-ml-text dark:text-white mt-1">{fmtMoney(r.pagos_realizados_monto)}</p>
          <p className="text-[10px] text-ml-text-soft dark:text-zinc-600 mt-1">Saldo neto: {fmtMoney(r.conciliado_periodo - r.pagos_realizados_monto)}</p>
        </div>
      </div>

      {/* Tabs de detalle */}
      <div className="bg-white dark:bg-ml-dark-surface rounded-xl border border-gray-100 dark:border-ml-dark-border overflow-hidden">
        <div className="flex border-b border-gray-100 dark:border-ml-dark-border">
          <TabBtn label={`Planillas (${data.planillas.length})`} activo={tab === 'planillas'} onClick={() => setTab('planillas')} />
          <TabBtn label={`Cheques (${data.cheques.length})`} activo={tab === 'cheques'} onClick={() => setTab('cheques')} />
          <TabBtn label={`Pagos (${data.pagos.length})`} activo={tab === 'pagos'} onClick={() => setTab('pagos')} />
        </div>

        <div className="p-4">
          {tab === 'planillas' && (
            data.planillas.length === 0 ? (
              <p className="text-sm text-ml-text-soft dark:text-zinc-500">No hay planillas en el período</p>
            ) : (
              <div className="space-y-3">
                {data.planillas.map((p) => (
                  <PlanillaCard key={p.id} planilla={p} />
                ))}
              </div>
            )
          )}

          {tab === 'cheques' && (
            data.cheques.length === 0 ? (
              <p className="text-sm text-ml-text-soft dark:text-zinc-500">No hay cheques en el período</p>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-xs">
                  <thead>
                    <tr className="text-left text-ml-text-soft dark:text-zinc-500 border-b border-gray-100 dark:border-ml-dark-border">
                      <th className="py-2 px-2">Nº</th>
                      <th className="py-2 px-2">Banco</th>
                      <th className="py-2 px-2">Emisión</th>
                      <th className="py-2 px-2">Depósito</th>
                      <th className="py-2 px-2 text-right">Monto</th>
                      <th className="py-2 px-2">Estado</th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.cheques.map((c) => (
                      <tr key={c.id} className="border-b border-gray-50 dark:border-white/5">
                        <td className="py-1.5 px-2 font-mono text-ml-text dark:text-white">{c.numero || '—'}</td>
                        <td className="py-1.5 px-2 text-ml-text dark:text-zinc-300">{c.banco_origen || '—'}</td>
                        <td className="py-1.5 px-2 text-ml-text-soft dark:text-zinc-500">{c.fecha_emision || '—'}</td>
                        <td className="py-1.5 px-2 text-ml-text-soft dark:text-zinc-500">{c.fecha_deposito || '—'}</td>
                        <td className="py-1.5 px-2 text-right font-mono text-ml-text dark:text-white">{fmtMoney(c.monto)}</td>
                        <td className="py-1.5 px-2"><EstadoBadge estado={c.estado} /></td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )
          )}

          {tab === 'pagos' && (
            data.pagos.length === 0 ? (
              <p className="text-sm text-ml-text-soft dark:text-zinc-500">No hay pagos en el período</p>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-xs">
                  <thead>
                    <tr className="text-left text-ml-text-soft dark:text-zinc-500 border-b border-gray-100 dark:border-ml-dark-border">
                      <th className="py-2 px-2">Fecha</th>
                      <th className="py-2 px-2">Concepto</th>
                      <th className="py-2 px-2">Medio</th>
                      <th className="py-2 px-2 text-right">Monto</th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.pagos.map((p) => (
                      <tr key={p.id} className="border-b border-gray-50 dark:border-white/5">
                        <td className="py-1.5 px-2 text-ml-text-soft dark:text-zinc-500">{p.fecha || '—'}</td>
                        <td className="py-1.5 px-2 text-ml-text dark:text-zinc-300">{p.concepto || '—'}</td>
                        <td className="py-1.5 px-2 text-ml-text-soft dark:text-zinc-500 capitalize">{p.medio}</td>
                        <td className="py-1.5 px-2 text-right font-mono text-ml-text dark:text-white">{fmtMoney(p.monto)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )
          )}
        </div>
      </div>
    </div>
  )
}

const TabBtn: React.FC<{ label: string; activo: boolean; onClick: () => void }> = ({ label, activo, onClick }) => (
  <button
    onClick={onClick}
    className={`px-4 py-3 text-xs font-semibold uppercase tracking-wide transition-colors border-b-2 ${
      activo
        ? 'text-ml-text dark:text-ml-green border-ml-text dark:border-ml-green'
        : 'text-ml-text-soft dark:text-zinc-500 border-transparent hover:text-ml-text dark:hover:text-zinc-300'
    }`}
  >
    {label}
  </button>
)

const PlanillaCard: React.FC<{ planilla: PlanillaData }> = ({ planilla }) => {
  const [abierto, setAbierto] = useState(false)
  const dias = planilla.dias_antiguedad
  const colorAntiguedad = dias === null ? '' : dias <= 30 ? 'text-emerald-600 dark:text-emerald-400' : dias <= 60 ? 'text-amber-600 dark:text-amber-400' : 'text-red-600 dark:text-red-400'

  return (
    <div className="border border-gray-100 dark:border-ml-dark-border rounded-lg overflow-hidden">
      <button
        onClick={() => setAbierto(!abierto)}
        className="w-full p-3 flex items-center justify-between hover:bg-gray-50 dark:hover:bg-white/5 transition-colors text-left"
      >
        <div className="min-w-0 flex-1">
          <div className="font-medium text-sm text-ml-text dark:text-white truncate">{planilla.nombre_archivo}</div>
          <div className="text-[11px] text-ml-text-soft dark:text-zinc-500 flex items-center gap-2 mt-0.5">
            <span>{planilla.fecha_carga?.slice(0, 10)}</span>
            {dias !== null && <span className={colorAntiguedad}>· hace {dias}d</span>}
            <span>· {planilla.filas.length} filas</span>
          </div>
        </div>
        <div className="text-right shrink-0 ml-3">
          <div className="text-xs font-mono text-emerald-600 dark:text-emerald-400">{fmtMoney(planilla.subtotal_ok)}</div>
          {planilla.subtotal_pendiente > 0 && (
            <div className="text-xs font-mono text-amber-600 dark:text-amber-400">{fmtMoney(planilla.subtotal_pendiente)} pdte</div>
          )}
        </div>
        <span className="ml-2 text-ml-text-soft dark:text-zinc-500">{abierto ? '▾' : '▸'}</span>
      </button>
      {abierto && (
        <div className="border-t border-gray-100 dark:border-ml-dark-border bg-gray-50/50 dark:bg-white/5 p-3">
          <table className="w-full text-[11px]">
            <thead>
              <tr className="text-left text-ml-text-soft dark:text-zinc-500">
                <th className="py-1">Titular</th>
                <th className="py-1">CUIT</th>
                <th className="py-1 text-right">Monto</th>
                <th className="py-1">Estado</th>
              </tr>
            </thead>
            <tbody>
              {planilla.filas.map((f) => (
                <tr key={f.id} className="border-t border-gray-100 dark:border-white/5">
                  <td className="py-1 text-ml-text dark:text-zinc-300 truncate max-w-[180px]">{f.titular || '—'}</td>
                  <td className="py-1 font-mono text-ml-text-soft dark:text-zinc-500">{f.cuit || '—'}</td>
                  <td className="py-1 text-right font-mono text-ml-text dark:text-white">{fmtMoney(f.monto)}</td>
                  <td className="py-1"><EstadoBadge estado={f.status_norm} /></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}

const EstadoBadge: React.FC<{ estado: string }> = ({ estado }) => {
  const e = estado.toLowerCase()
  const cls = e === 'ok' || e === 'acreditado'
    ? 'bg-emerald-100 text-emerald-700 dark:bg-emerald-950/40 dark:text-emerald-400'
    : e === 'pendiente'
      ? 'bg-amber-100 text-amber-700 dark:bg-amber-950/40 dark:text-amber-400'
      : e === 'rechazado'
        ? 'bg-red-100 text-red-700 dark:bg-red-950/40 dark:text-red-400'
        : 'bg-gray-100 text-gray-600 dark:bg-white/10 dark:text-zinc-400'
  return <span className={`inline-block px-2 py-0.5 rounded text-[10px] font-semibold uppercase tracking-wide ${cls}`}>{estado}</span>
}
