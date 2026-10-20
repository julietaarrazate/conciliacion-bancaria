import React, { useEffect, useState } from 'react'
import { apiClient } from '@/services/api'
import { MovimientoFiltrado, PagoCandidato } from '@/types'
import { localIsoDate } from '@/utils/fecha'

interface ResolverMovimientoModalProps {
  mov: MovimientoFiltrado
  orgId?: number | null
  onClose: () => void
  onResuelto: (egresoId: number) => void
}

function fmtARS(n: number | string) {
  n = Number(n)
  return new Intl.NumberFormat('es-AR', { style: 'currency', currency: 'ARS', minimumFractionDigits: 2 }).format(n)
}
function fmtFecha(d?: string | null) {
  if (!d) return '—'
  return new Date(d + 'T00:00:00').toLocaleDateString('es-AR', { day: '2-digit', month: '2-digit', year: '2-digit' })
}

/**
 * "Resolver" un débito del extracto sin salir de Movimientos. Si ya hay pagos
 * cargados por el mismo importe (banco, sin vincular, fecha cercana) los ofrece
 * primero para vincularlos — así no se duplica el pago ni su asiento. Si no,
 * registra el pago o gasto que lo explica (banco, mismo importe) ya vinculado.
 * Se contabiliza igual que un pago cargado en Pagos.
 */
export const ResolverMovimientoModal: React.FC<ResolverMovimientoModalProps> = ({ mov, orgId, onClose, onResuelto }) => {
  const importe = Math.abs(mov.monto)
  const [tipo, setTipo] = useState<'gasto' | 'proveedor'>('gasto')
  const [beneficiario, setBeneficiario] = useState(mov.titular || '')
  const [concepto, setConcepto] = useState(mov.titular || '')
  const [categoria, setCategoria] = useState('')
  const [fecha, setFecha] = useState(mov.fecha || localIsoDate())
  const [categorias, setCategorias] = useState<{ id: number; nombre: string }[]>([])
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')
  const [candidatos, setCandidatos] = useState<PagoCandidato[]>([])

  useEffect(() => {
    let cancelado = false
    apiClient.pagosCandidatosMovimiento(mov.id, orgId)
      .then(c => { if (!cancelado) setCandidatos(c) })
      .catch(() => {})
    return () => { cancelado = true }
  }, [mov.id, orgId])

  const vincular = async (egresoId: number) => {
    setSaving(true)
    setError('')
    try {
      const res = await apiClient.vincularPagoAMovimiento(egresoId, mov.id)
      onResuelto(res.egreso.id)
    } catch (err: any) {
      setError(err?.response?.data?.detail || 'Error al vincular el pago')
    } finally {
      setSaving(false)
    }
  }

  useEffect(() => {
    let cancelado = false
    apiClient.listarCategoriasEgreso(orgId)
      .then(cats => {
        if (cancelado) return
        setCategorias(cats)
        if (mov.gasto_bancario) {
          const bancaria = cats.find(c => /banc/i.test(c.nombre))
          if (bancaria) setCategoria(bancaria.nombre)
        }
      })
      .catch(() => {})
    return () => { cancelado = true }
  }, [orgId, mov.gasto_bancario])

  const guardar = async () => {
    if (tipo === 'proveedor' && !beneficiario.trim()) { setError('Ingresá el proveedor'); return }
    setSaving(true)
    setError('')
    try {
      const res = await apiClient.crearPagoDesdeMovimiento({
        movimiento_banco_id: mov.id,
        tipo,
        forma_pago: 'banco',
        monto: importe,
        fecha,
        beneficiario: beneficiario.trim() || undefined,
        concepto: concepto.trim() || undefined,
        categoria: categoria || undefined,
        ...(orgId ? { org_id: orgId } : {}),
      })
      onResuelto(res.egreso.id)
    } catch (err: any) {
      setError(err?.response?.data?.detail || 'Error al registrar el pago')
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50" onClick={onClose}>
      <div className="bg-white dark:bg-slate-800 rounded-xl shadow-xl p-5 w-full max-w-sm mx-4" onClick={e => e.stopPropagation()}
        role="dialog" aria-label="Resolver movimiento">
        <h3 className="text-sm font-semibold text-ml-text dark:text-gray-100 mb-1">Resolver movimiento</h3>
        <p className="text-[11px] text-gray-500 dark:text-gray-400 mb-4">
          Registrá el pago o gasto que explica este débito. Queda vinculado al movimiento y se carga en Pagos.
        </p>
        <div className="mb-3 rounded-lg bg-gray-50 dark:bg-slate-700/50 px-3 py-2 text-xs">
          <p className="truncate dark:text-gray-200" title={mov.titular || ''}>{mov.titular || '—'}</p>
          <p className="font-mono font-semibold dark:text-white">{fmtARS(importe)} <span className="font-sans font-normal text-gray-400">· por banco</span></p>
        </div>
        {candidatos.length > 0 && (
          <div className="mb-4 rounded-lg border border-amber-200 dark:border-amber-800 bg-amber-50 dark:bg-amber-900/20 p-3">
            <p className="text-[11px] font-semibold text-amber-800 dark:text-amber-300 mb-2">
              {candidatos.length === 1 ? 'Hay un pago ya cargado' : `Hay ${candidatos.length} pagos ya cargados`} por el mismo importe.
              Si es este, vinculalo para no registrarlo dos veces.
            </p>
            <ul className="space-y-1.5">
              {candidatos.map(c => (
                <li key={c.id} className="flex items-center gap-2 text-xs">
                  <div className="min-w-0 flex-1">
                    <p className="truncate dark:text-gray-200">{c.beneficiario || c.cliente_nombre || 'Sin beneficiario'}</p>
                    <p className="truncate text-[10px] text-gray-500 dark:text-gray-400">
                      #{c.id} · {fmtFecha(c.fecha)}{c.concepto ? ` · ${c.concepto}` : ''}
                    </p>
                  </div>
                  <button type="button" onClick={() => vincular(c.id)} disabled={saving}
                    aria-label={`Vincular pago #${c.id}`}
                    className="px-2.5 py-1 text-[11px] bg-amber-600 text-white rounded hover:bg-amber-700 disabled:opacity-50">
                    Vincular
                  </button>
                </li>
              ))}
            </ul>
          </div>
        )}
        {candidatos.length > 0 && (
          <p className="text-[11px] font-semibold text-gray-500 dark:text-gray-400 mb-2">O registrá uno nuevo:</p>
        )}
        <div className="space-y-3">
          <div>
            <label htmlFor="resolver-tipo" className="label text-xs">Tipo</label>
            <select id="resolver-tipo" className="input-field text-xs" value={tipo}
              onChange={e => setTipo(e.target.value as 'gasto' | 'proveedor')}>
              <option value="gasto">Gasto</option>
              <option value="proveedor">Pago a proveedor</option>
            </select>
          </div>
          <div>
            <label htmlFor="resolver-beneficiario" className="label text-xs">{tipo === 'proveedor' ? 'Proveedor' : 'Beneficiario'}</label>
            <input id="resolver-beneficiario" className="input-field text-xs" value={beneficiario}
              onChange={e => setBeneficiario(e.target.value)} />
          </div>
          <div>
            <label htmlFor="resolver-concepto" className="label text-xs">Concepto</label>
            <input id="resolver-concepto" className="input-field text-xs" value={concepto}
              onChange={e => setConcepto(e.target.value)} />
          </div>
          <div>
            <label htmlFor="resolver-categoria" className="label text-xs">Categoría</label>
            <select id="resolver-categoria" className="input-field text-xs" value={categoria}
              onChange={e => setCategoria(e.target.value)}>
              <option value="">Sin categoría</option>
              {categorias.map(c => <option key={c.id} value={c.nombre}>{c.nombre}</option>)}
            </select>
          </div>
          <div>
            <label htmlFor="resolver-fecha" className="label text-xs">Fecha</label>
            <input id="resolver-fecha" type="date" className="input-field text-xs" value={fecha}
              onChange={e => setFecha(e.target.value)} />
          </div>
        </div>
        {error && <p className="mt-3 text-xs text-red-600 dark:text-red-400">{error}</p>}
        <div className="flex gap-2 mt-5 justify-end">
          <button onClick={onClose}
            className="px-3 py-1.5 text-xs text-gray-500 border border-gray-200 dark:border-slate-600 rounded hover:bg-gray-50 dark:hover:bg-slate-700">
            Cancelar
          </button>
          <button onClick={guardar} disabled={saving}
            className="px-4 py-1.5 text-xs bg-ml-blue text-white rounded hover:bg-ml-blue/90 disabled:opacity-50">
            {saving ? 'Guardando...' : 'Registrar pago'}
          </button>
        </div>
      </div>
    </div>
  )
}
