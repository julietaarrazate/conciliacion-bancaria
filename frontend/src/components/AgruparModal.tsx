import React, { useEffect, useMemo, useState } from 'react'
import { apiClient } from '@/services/api'
import { fmtFechaCorta as fmtDate } from '@/utils/formato'
import { subtotalGrupo, formaGrupoValida } from '@/utils/grupoSubtotal'

// Conciliar en grupo a mano: varias filas de la planilla contra UN movimiento del
// banco (el cliente pagó varias filas con una transferencia), o UNA fila contra
// varios movimientos (pagó una fila en dos o más transferencias). El subtotal se
// ve en vivo: verde si cuadra, rojo con la diferencia si no. Con diferencia solo
// se puede confirmar marcándolo a propósito ("Conciliado con diferencia").

export interface FilaAgrupar {
  id: number
  monto: number
  titular?: string | null
}

interface MovLibre {
  id: number
  fecha: string | null
  titular: string | null
  monto: number
  source: string
}

interface Props {
  planillaId: number
  filas: FilaAgrupar[]
  onClose: () => void
  onHecho: () => void
}

const ARS2 = new Intl.NumberFormat('es-AR', { style: 'currency', currency: 'ARS', minimumFractionDigits: 2, maximumFractionDigits: 2 })
const fmt2 = (n: number) => ARS2.format(n)

export const AgruparModal: React.FC<Props> = ({ planillaId, filas, onClose, onHecho }) => {
  const [movs, setMovs] = useState<MovLibre[]>([])
  const [tolerancia, setTolerancia] = useState(0.01)
  const [cargando, setCargando] = useState(true)
  const [error, setError] = useState('')
  const [busqueda, setBusqueda] = useState('')
  const [elegidos, setElegidos] = useState<number[]>([])
  const [conDiferencia, setConDiferencia] = useState(false)
  const [guardando, setGuardando] = useState(false)

  // Varias filas → un solo movimiento; una fila → uno o varios movimientos.
  const variasFilas = filas.length > 1

  useEffect(() => {
    let vivo = true
    setCargando(true)
    apiClient.movimientosLibres(planillaId)
      .then(d => {
        if (!vivo) return
        setMovs(d.movimientos)
        setTolerancia(Number(d.tolerancia) || 0.01)
      })
      .catch((err: { response?: { data?: { detail?: string } } }) => {
        if (vivo) setError(err.response?.data?.detail || 'No se pudieron cargar los movimientos del extracto')
      })
      .finally(() => { if (vivo) setCargando(false) })
    return () => { vivo = false }
  }, [planillaId])

  const visibles = useMemo(() => {
    const t = busqueda.trim().toLowerCase()
    if (!t) return movs
    return movs.filter(m => (m.titular || '').toLowerCase().includes(t) || String(m.monto).includes(t))
  }, [movs, busqueda])

  const montosElegidos = useMemo(
    () => movs.filter(m => elegidos.includes(m.id)).map(m => Number(m.monto)),
    [movs, elegidos],
  )
  const sub = subtotalGrupo(filas.map(f => Number(f.monto)), montosElegidos, tolerancia)
  const formaOk = formaGrupoValida(filas.length, elegidos.length)
  const puedeConfirmar = formaOk && (sub.cuadra || conDiferencia) && !guardando

  const toggle = (id: number) => {
    setError('')
    setElegidos(prev => {
      if (prev.includes(id)) return prev.filter(x => x !== id)
      return variasFilas ? [id] : [...prev, id]
    })
  }

  const confirmar = async () => {
    if (!puedeConfirmar) return
    setGuardando(true)
    setError('')
    try {
      await apiClient.crearGrupo(planillaId, filas.map(f => f.id), elegidos, !sub.cuadra && conDiferencia)
      onHecho()
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail
      setError(msg || 'No se pudo conciliar el grupo')
    } finally {
      setGuardando(false)
    }
  }

  return (
    <div className="fixed inset-0 z-150 flex items-center justify-center p-4" role="dialog" aria-modal="true" aria-label="Conciliar en grupo">
      <div className="absolute inset-0 bg-black/50 backdrop-blur-xs" onClick={onClose} />
      <div className="relative bg-white dark:bg-ml-dark-surface rounded-2xl shadow-xl border border-gray-200 dark:border-ml-dark-border p-6 w-full max-w-lg max-h-[90vh] flex flex-col">
        <h3 className="text-base font-semibold text-ml-text dark:text-white mb-1">Conciliar en grupo</h3>
        <p className="text-xs text-ml-text-soft dark:text-zinc-400 mb-3">
          {variasFilas
            ? `Elegí el movimiento del banco que paga estas ${filas.length} filas juntas.`
            : 'Elegí los movimientos del banco que juntos pagan esta fila.'}
        </p>

        <input
          className="w-full px-3 py-1.5 mb-2 text-sm border border-gray-300 dark:border-slate-600 rounded-lg bg-white dark:bg-slate-700 dark:text-gray-200"
          placeholder="Buscar por titular o importe"
          value={busqueda}
          onChange={e => setBusqueda(e.target.value)}
          aria-label="Buscar movimiento"
        />

        <div className="flex-1 min-h-0 overflow-y-auto space-y-1.5 mb-3">
          {cargando && <p className="text-sm text-ml-text-soft dark:text-zinc-400 py-4 text-center">Buscando movimientos libres…</p>}
          {!cargando && visibles.length === 0 && (
            <p className="text-sm text-ml-text-soft dark:text-zinc-400 py-4 text-center">No hay movimientos libres en el extracto.</p>
          )}
          {!cargando && visibles.map(m => {
            const activo = elegidos.includes(m.id)
            return (
              <label
                key={m.id}
                className={`flex items-center gap-2 px-3 py-2 rounded-lg border cursor-pointer transition-colors ${activo ? 'border-ml-blue bg-blue-50 dark:bg-blue-900/20' : 'border-gray-200 dark:border-slate-600 hover:bg-ml-gray-bg dark:hover:bg-slate-700'}`}
              >
                <input
                  type={variasFilas ? 'radio' : 'checkbox'}
                  name="mov-grupo"
                  checked={activo}
                  onChange={() => toggle(m.id)}
                  aria-label={`Movimiento ${m.titular || ''} ${fmt2(Number(m.monto))}`}
                />
                <span className="flex-1 min-w-0 text-sm dark:text-gray-200 truncate" title={m.titular || ''}>{m.titular || '—'}</span>
                <span className="text-xs font-mono text-ml-text-soft dark:text-zinc-400 shrink-0">{fmtDate(m.fecha)}</span>
                <span className="text-sm font-mono font-semibold dark:text-white shrink-0">{fmt2(Number(m.monto))}</span>
              </label>
            )
          })}
        </div>

        <div
          data-testid="subtotal-grupo"
          className={`rounded-lg px-3 py-2 text-sm mb-3 ${elegidos.length === 0
            ? 'bg-gray-50 dark:bg-slate-800 text-ml-text-soft dark:text-zinc-400'
            : sub.cuadra
              ? 'bg-green-50 dark:bg-green-900/20 text-green-700 dark:text-green-300'
              : 'bg-red-50 dark:bg-red-900/20 text-red-700 dark:text-red-300'}`}
        >
          <div className="flex justify-between"><span>{filas.length === 1 ? 'Fila' : `${filas.length} filas`}</span><span className="font-mono">{fmt2(sub.totalFilas)}</span></div>
          <div className="flex justify-between"><span>{elegidos.length === 1 ? 'Movimiento' : `${elegidos.length} movimientos`}</span><span className="font-mono">{fmt2(sub.totalMovimientos)}</span></div>
          {elegidos.length > 0 && (
            <div className="flex justify-between font-semibold mt-1">
              <span>{sub.cuadra ? 'Cuadra' : 'Diferencia'}</span>
              {!sub.cuadra && <span className="font-mono">{fmt2(sub.diferencia)}</span>}
            </div>
          )}
        </div>

        {elegidos.length > 0 && !sub.cuadra && (
          <label className="flex items-start gap-2 text-xs text-ml-text dark:text-zinc-300 mb-3">
            <input type="checkbox" checked={conDiferencia} onChange={e => setConDiferencia(e.target.checked)} className="mt-0.5" />
            <span>Conciliar igual, como <strong>conciliado con diferencia</strong>. Al cliente se le acredita lo que entró al banco.</span>
          </label>
        )}
        {!variasFilas && elegidos.length === 1 && (
          <p className="text-xs text-ml-text-soft dark:text-zinc-400 mb-3">Para una fila contra un solo movimiento usá “Asignar movimiento” (🔗). Elegí al menos dos.</p>
        )}

        {error && <p className="text-sm text-red-500 mb-3">{error}</p>}

        <div className="flex justify-end gap-2">
          <button
            onClick={onClose}
            className="px-4 py-2 text-sm rounded-lg border border-gray-200 dark:border-ml-dark-border text-ml-text dark:text-zinc-300 hover:bg-gray-50 dark:hover:bg-white/5 transition-colors"
          >Cancelar</button>
          <button
            onClick={confirmar}
            disabled={!puedeConfirmar}
            className="px-4 py-2 text-sm rounded-lg bg-ml-blue text-white font-medium disabled:opacity-40 disabled:cursor-not-allowed"
          >{guardando ? 'Guardando…' : sub.cuadra || elegidos.length === 0 ? 'Conciliar grupo' : 'Conciliar con diferencia'}</button>
        </div>
      </div>
    </div>
  )
}
