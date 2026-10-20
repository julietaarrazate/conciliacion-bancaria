import React, { useCallback, useEffect, useMemo, useState } from 'react'
import { apiClient } from '@/services/api'
import { useAuthStore } from '@/store/auth'
import { hoyIso } from '@/utils/fecha'
import type { CeldaVencimiento, GrillaVencimientos, ImpuestoVencimiento } from '@/types'

const NOMBRES: Record<ImpuestoVencimiento, string> = {
  iva: 'IVA (F.2002)',
  monotributo: 'Monotributo',
  iibb_cm: 'IIBB Convenio Multilateral',
  f931: 'F.931 cargas sociales',
}
const ORDEN: ImpuestoVencimiento[] = ['iva', 'monotributo', 'iibb_cm', 'f931']

// Bloques de terminación de CUIT que usa cada calendario (ARCA / COMARB).
const BLOQUES: Record<ImpuestoVencimiento, [number, number][]> = {
  iva: [[0, 1], [2, 3], [4, 5], [6, 7], [8, 9]],
  f931: [[0, 3], [4, 6], [7, 9]],
  iibb_cm: [[0, 2], [3, 5], [6, 7], [8, 9]],
  monotributo: [[0, 9]],
}

const ESTILO: Record<CeldaVencimiento['estado'], { label: string; cls: string }> = {
  presentado: { label: 'Presentado', cls: 'bg-green-100 text-green-800 dark:bg-green-900/40 dark:text-green-300' },
  vencido: { label: 'Vencido', cls: 'bg-red-100 text-red-800 dark:bg-red-900/40 dark:text-red-300' },
  proximo: { label: 'Vence pronto', cls: 'bg-amber-100 text-amber-800 dark:bg-amber-900/40 dark:text-amber-300' },
  pendiente: { label: 'Pendiente', cls: 'bg-gray-100 text-gray-600 dark:bg-white/10 dark:text-gray-300' },
}

const inputClass = 'w-full px-2 py-1.5 rounded-lg border border-gray-300 dark:border-white/15 bg-white dark:bg-black/30 text-sm text-gray-900 dark:text-gray-100'
const btn = 'px-3 py-1.5 rounded-lg text-xs font-medium disabled:opacity-50'

function fmtDiaMes(iso: string) {
  return `${iso.slice(8, 10)}/${iso.slice(5, 7)}`
}
function nombreMes(mes: string) {
  return new Date(`${mes}-01T00:00:00`).toLocaleDateString('es-AR', { month: 'long', year: 'numeric' })
}
function siguienteMes(mes: string) {
  const [y, m] = mes.split('-').map(Number)
  return m === 12 ? `${y + 1}-01` : `${y}-${String(m + 1).padStart(2, '0')}`
}

const CalendarioForm: React.FC<{ onGuardado: () => void }> = ({ onGuardado }) => {
  const [impuesto, setImpuesto] = useState<ImpuestoVencimiento>('iva')
  const [periodo, setPeriodo] = useState(hoyIso().slice(0, 7))
  const [fuente, setFuente] = useState('argentina.gob.ar/arca/vencimientos')
  const [fechas, setFechas] = useState<string[]>([])
  const [guardando, setGuardando] = useState(false)
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null)
  const bloques = BLOQUES[impuesto]

  // Precarga lo que ya esté cargado para ese impuesto y período
  useEffect(() => {
    let cancelado = false
    setFechas(bloques.map(() => ''))
    apiClient.getCalendarioVencimientos(periodo).then(filas => {
      if (cancelado) return
      setFechas(bloques.map(([d]) => filas.find(f => f.impuesto === impuesto && f.terminacion_desde === d)?.fecha || ''))
    }).catch(() => {})
    return () => { cancelado = true }
  }, [impuesto, periodo, bloques])

  const guardar = async () => {
    setGuardando(true)
    setMsg(null)
    try {
      await apiClient.guardarCalendarioVencimientos({
        impuesto, periodo, fuente: fuente || undefined,
        fechas: bloques.map(([d, h], i) => ({ terminacion_desde: d, terminacion_hasta: h, fecha: fechas[i] })),
      })
      setMsg({ ok: true, text: 'Calendario guardado.' })
      onGuardado()
    } catch (err: any) {
      setMsg({ ok: false, text: err?.response?.data?.detail || 'No se pudo guardar.' })
    } finally {
      setGuardando(false)
    }
  }

  return (
    <div className="mb-6 rounded-xl border border-gray-200 dark:border-white/10 bg-white dark:bg-white/5 p-4">
      <div className="text-sm font-semibold text-gray-900 dark:text-gray-100 mb-1">Cargar calendario</div>
      <p className="text-xs text-gray-500 dark:text-gray-400 mb-3">
        Copiá las fechas de <span className="font-mono">argentina.gob.ar/arca/vencimientos</span>. Vale para todas las organizaciones.
        El período es el que se declara: el IVA de septiembre vence en octubre.
      </p>
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 mb-3">
        <div>
          <label htmlFor="cal-impuesto" className="block text-xs text-gray-600 dark:text-gray-400 mb-1">Impuesto</label>
          <select id="cal-impuesto" className={inputClass} value={impuesto} onChange={e => setImpuesto(e.target.value as ImpuestoVencimiento)}>
            {ORDEN.map(i => <option key={i} value={i}>{NOMBRES[i]}</option>)}
          </select>
        </div>
        <div>
          <label htmlFor="cal-periodo" className="block text-xs text-gray-600 dark:text-gray-400 mb-1">Período</label>
          <input id="cal-periodo" type="month" className={inputClass} value={periodo} onChange={e => setPeriodo(e.target.value)} />
        </div>
        <div>
          <label htmlFor="cal-fuente" className="block text-xs text-gray-600 dark:text-gray-400 mb-1">Fuente</label>
          <input id="cal-fuente" className={inputClass} value={fuente} onChange={e => setFuente(e.target.value)} />
        </div>
      </div>
      <div className="grid grid-cols-2 sm:grid-cols-5 gap-3">
        {bloques.map(([d, h], i) => {
          const label = d === h ? `CUIT terminado en ${d}` : `CUIT terminado en ${d} a ${h}`
          return (
            <div key={`${impuesto}-${d}`}>
              <label htmlFor={`cal-b-${d}`} className="block text-xs text-gray-600 dark:text-gray-400 mb-1">{label}</label>
              <input id={`cal-b-${d}`} type="date" className={inputClass} value={fechas[i] || ''}
                onChange={e => setFechas(prev => prev.map((v, j) => (j === i ? e.target.value : v)))} />
            </div>
          )
        })}
      </div>
      <div className="mt-3 flex items-center gap-3">
        <button className={`${btn} bg-ml-blue text-white`} onClick={guardar}
          disabled={guardando || fechas.length !== bloques.length || fechas.some(f => !f)}>
          {guardando ? 'Guardando…' : 'Guardar calendario'}
        </button>
        {msg && <span className={`text-xs ${msg.ok ? 'text-green-700 dark:text-green-300' : 'text-red-600 dark:text-red-400'}`}>{msg.text}</span>}
      </div>
    </div>
  )
}

/**
 * Grilla de vencimientos: qué vence este mes para cada organización que ve el
 * usuario, con su estado. Las fechas salen del calendario cargado (ARCA no
 * publica uno anual) según la terminación del CUIT de cada org.
 */
export const Vencimientos: React.FC = () => {
  const { user, hasPermission } = useAuthStore()
  const puedeMarcar = hasPermission('manage_finance')
  const esSuperadmin = !!user?.is_superadmin
  const [mes, setMes] = useState(hoyIso().slice(0, 7))
  const [grilla, setGrilla] = useState<GrillaVencimientos | null>(null)
  const [error, setError] = useState('')
  const [ocupado, setOcupado] = useState<string | null>(null)
  const [verCalendario, setVerCalendario] = useState(false)

  const cargar = useCallback(async () => {
    setError('')
    try {
      setGrilla(await apiClient.getGrillaVencimientos(mes))
    } catch (err: any) {
      setError(err?.response?.data?.detail || 'No se pudo cargar la grilla.')
    }
  }, [mes])

  useEffect(() => { cargar() }, [cargar])

  const columnas = useMemo(() => ORDEN.filter(i => grilla?.filas.some(f => f.obligaciones.some(o => o.impuesto === i))), [grilla])
  const faltaCalendario = grilla?.filas.some(f => f.obligaciones.some(o => o.motivo === 'sin_calendario'))

  const alternar = async (orgId: number, c: CeldaVencimiento) => {
    const clave = `${orgId}-${c.impuesto}`
    setOcupado(clave)
    try {
      if (c.presentado_por === 'manual') await apiClient.desmarcarVencimiento(orgId, c.impuesto, c.periodo)
      else await apiClient.marcarVencimiento(orgId, c.impuesto, c.periodo)
      await cargar()
    } catch (err: any) {
      setError(err?.response?.data?.detail || 'No se pudo actualizar.')
    } finally {
      setOcupado(null)
    }
  }

  return (
    <div className="p-4 md:p-6 max-w-6xl mx-auto">
      <h1 className="text-xl md:text-2xl font-semibold text-gray-900 dark:text-gray-100 mb-1">Vencimientos</h1>
      <p className="text-sm text-gray-500 dark:text-gray-400 mb-4">
        Qué vence en el mes para cada organización, según la terminación de su CUIT y los módulos que tiene activos.
        Lo presentado en IVA, Ingresos Brutos o Sueldos aparece solo; el resto se marca a mano.
      </p>

      <div className="flex flex-wrap items-end gap-3 mb-4">
        <div>
          <label htmlFor="venc-mes" className="block text-xs text-gray-600 dark:text-gray-400 mb-1">Mes de vencimiento</label>
          <input id="venc-mes" type="month" className={inputClass} value={mes} onChange={e => setMes(e.target.value)} />
        </div>
        <button className={`${btn} border border-gray-300 dark:border-white/15 text-gray-700 dark:text-gray-200`}
          onClick={() => setMes(siguienteMes(mes))}>
          Ver {nombreMes(siguienteMes(mes))}
        </button>
        {esSuperadmin && (
          <button className={`${btn} border border-gray-300 dark:border-white/15 text-gray-700 dark:text-gray-200 ml-auto`}
            onClick={() => setVerCalendario(v => !v)}>
            {verCalendario ? 'Ocultar calendario' : 'Cargar calendario'}
          </button>
        )}
      </div>

      {esSuperadmin && verCalendario && <CalendarioForm onGuardado={cargar} />}

      {error && <p className="mb-3 text-sm text-red-600 dark:text-red-400">{error}</p>}
      {faltaCalendario && (
        <p className="mb-3 text-xs text-amber-700 dark:text-amber-300">
          Falta cargar el calendario de {nombreMes(mes)} para algunos impuestos.
          {esSuperadmin ? ' Usá "Cargar calendario".' : ' Pedíselo al superadmin.'}
        </p>
      )}

      {grilla && grilla.filas.length === 0 && (
        <p className="text-sm text-gray-500 dark:text-gray-400">No hay organizaciones para mostrar.</p>
      )}

      {grilla && grilla.filas.length > 0 && (
        <div className="overflow-x-auto rounded-xl border border-gray-200 dark:border-white/10">
          <table className="w-full text-sm">
            <thead className="bg-gray-50 dark:bg-white/5 text-xs text-gray-500 dark:text-gray-400">
              <tr>
                <th className="text-left font-medium px-3 py-2">Organización</th>
                {columnas.map(i => <th key={i} className="text-left font-medium px-3 py-2">{NOMBRES[i]}</th>)}
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100 dark:divide-white/10">
              {grilla.filas.map(f => (
                <tr key={f.organizacion_id}>
                  <td className="px-3 py-2 align-top">
                    <div className="font-medium text-gray-900 dark:text-gray-100">{f.nombre}</div>
                    <div className="text-[11px] text-gray-400 font-mono">{f.cuit || 'Sin CUIT cargado'}</div>
                  </td>
                  {columnas.map(imp => {
                    const c = f.obligaciones.find(o => o.impuesto === imp)
                    if (!c) return <td key={imp} className="px-3 py-2 text-gray-300 dark:text-gray-600">—</td>
                    const e = ESTILO[c.estado]
                    return (
                      <td key={imp} className="px-3 py-2 align-top">
                        <div className="flex items-center gap-2">
                          {c.fecha
                            ? <span className="font-mono text-gray-900 dark:text-gray-100">{fmtDiaMes(c.fecha)}</span>
                            : <span className="text-[11px] text-amber-700 dark:text-amber-300">
                                {c.motivo === 'sin_cuit' ? 'Sin CUIT' : 'Falta el calendario'}
                              </span>}
                          <span className={`pill rounded-full text-[10px] px-2 py-0.5 ${e.cls}`}>{e.label}</span>
                        </div>
                        <div className="text-[10px] text-gray-400">
                          Período {c.periodo}{c.presentado_por === 'modulo' ? ' · desde el módulo' : ''}
                        </div>
                        {puedeMarcar && c.presentado_por !== 'modulo' && (
                          <button className="mt-1 text-[11px] text-ml-blue dark:text-blue-400 hover:underline disabled:opacity-50"
                            disabled={ocupado === `${f.organizacion_id}-${imp}`}
                            onClick={() => alternar(f.organizacion_id, c)}>
                            {c.presentado_por === 'manual' ? 'Desmarcar' : 'Marcar presentado'}
                          </button>
                        )}
                      </td>
                    )
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}

export default Vencimientos
