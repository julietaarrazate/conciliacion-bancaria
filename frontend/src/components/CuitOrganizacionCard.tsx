import React, { useEffect, useState } from 'react'
import { apiClient } from '@/services/api'

interface CuitOrganizacionCardProps {
  orgId?: number
  puedeEditar: boolean
}

function fmtCuit(c: string) {
  const d = c.replace(/\D/g, '')
  return d.length === 11 ? `${d.slice(0, 2)}-${d.slice(2, 10)}-${d.slice(10)}` : c
}

/**
 * CUIT de la organización para controlar que cada factura de compra esté a su
 * nombre (si la IA lee otro CUIT como comprador, el borrador muestra una alerta).
 * Sin CUIT cargado el control no corre.
 */
export const CuitOrganizacionCard: React.FC<CuitOrganizacionCardProps> = ({ orgId, puedeEditar }) => {
  const [cuit, setCuit] = useState<string | null | undefined>(undefined)
  const [editando, setEditando] = useState(false)
  const [valor, setValor] = useState('')
  const [guardando, setGuardando] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    let cancelado = false
    apiClient.getCuitOrganizacion(orgId)
      .then(r => { if (!cancelado) setCuit(r.cuit) })
      .catch(() => { if (!cancelado) setCuit(null) })
    return () => { cancelado = true }
  }, [orgId])

  const guardar = async () => {
    setGuardando(true)
    setError('')
    try {
      const r = await apiClient.setCuitOrganizacion(valor, orgId)
      setCuit(r.cuit)
      setEditando(false)
    } catch (err: any) {
      setError(err?.response?.data?.detail || 'No se pudo guardar el CUIT.')
    } finally {
      setGuardando(false)
    }
  }

  if (cuit === undefined) return null
  const mostrarForm = puedeEditar && (editando || !cuit)

  return (
    <div className="mb-6 rounded-xl border border-gray-200 dark:border-white/10 bg-white dark:bg-white/5 px-4 py-3 text-xs">
      <div className="flex flex-wrap items-center gap-x-3 gap-y-2">
        <span className="font-semibold text-gray-900 dark:text-gray-100">CUIT de la empresa</span>
        {cuit && !editando && (
          <>
            <span className="font-mono text-gray-800 dark:text-gray-200">{fmtCuit(cuit)}</span>
            <span className="text-gray-500 dark:text-gray-400">Se avisa si una factura está a nombre de otro CUIT.</span>
            {puedeEditar && (
              <button className="text-gray-500 dark:text-gray-400 hover:underline" onClick={() => { setValor(cuit); setEditando(true) }}>
                Cambiar
              </button>
            )}
          </>
        )}
        {!cuit && (
          <span className="text-amber-700 dark:text-amber-300">
            Sin cargar: no se controla a nombre de quién está cada factura.
            {!puedeEditar && ' Pedile a un administrador que lo cargue.'}
          </span>
        )}
        {mostrarForm && (
          <span className="flex items-center gap-2">
            <label htmlFor="cuit-organizacion" className="sr-only">CUIT de la organización</label>
            <input id="cuit-organizacion" inputMode="numeric" placeholder="30-12345678-9" value={valor}
              onChange={e => setValor(e.target.value)}
              className="w-36 px-2 py-1 rounded-sm border border-gray-300 dark:border-white/15 bg-white dark:bg-black/30 text-gray-900 dark:text-gray-100" />
            <button onClick={guardar} disabled={guardando || !valor.trim()}
              className="px-3 py-1 rounded-sm bg-ml-blue text-white disabled:opacity-50">
              {guardando ? 'Guardando…' : 'Guardar'}
            </button>
            {editando && <button className="text-gray-500 hover:underline" onClick={() => setEditando(false)}>Cancelar</button>}
          </span>
        )}
      </div>
      {error && <p className="mt-1 text-red-600 dark:text-red-400">{error}</p>}
    </div>
  )
}
