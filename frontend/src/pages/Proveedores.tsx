import React, { useCallback, useEffect, useMemo, useState } from 'react'
import { apiClient } from '@/services/api'
import { useAuthStore } from '@/store/auth'
import { useOrgStore } from '@/store/org'
import { CondicionIva, Proveedor, ProveedorInput } from '@/types'

const inputClass = 'w-full px-2 py-1.5 rounded-lg border border-gray-300 dark:border-white/15 bg-white dark:bg-black/30 text-sm text-gray-900 dark:text-gray-100'
const btn = 'px-3 py-1.5 rounded-lg text-xs font-medium disabled:opacity-50'

const CONDICIONES_IVA: Record<CondicionIva, string> = {
  responsable_inscripto: 'Responsable inscripto',
  monotributo: 'Monotributo',
  exento: 'Exento',
  no_alcanzado: 'No alcanzado',
}

function fmtCuit(c: string | null) {
  return c && c.length === 11 ? `${c.slice(0, 2)}-${c.slice(2, 10)}-${c.slice(10)}` : (c || '—')
}
function fmtARS(n: number | string) {
  return new Intl.NumberFormat('es-AR', { style: 'currency', currency: 'ARS', minimumFractionDigits: 2 }).format(Number(n))
}

const VACIO: ProveedorInput = { razon_social: '', cuit: '', condicion_iva: null, email: '', cbu: '', notas: '' }

const ProveedorForm: React.FC<{
  inicial: Proveedor | null
  orgId?: number
  onGuardado: () => void
  onCancelar: () => void
}> = ({ inicial, orgId, onGuardado, onCancelar }) => {
  const [datos, setDatos] = useState<ProveedorInput>(inicial ? {
    razon_social: inicial.razon_social, cuit: inicial.cuit || '', condicion_iva: inicial.condicion_iva,
    email: inicial.email || '', cbu: inicial.cbu || '', notas: inicial.notas || '',
  } : VACIO)
  const [error, setError] = useState('')
  const [guardando, setGuardando] = useState(false)
  const set = (campo: keyof ProveedorInput) => (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement>) =>
    setDatos(d => ({ ...d, [campo]: e.target.value || null }))

  const guardar = async () => {
    setGuardando(true)
    setError('')
    try {
      if (inicial) await apiClient.actualizarProveedor(inicial.id, datos)
      else await apiClient.crearProveedor(datos, orgId)
      onGuardado()
    } catch (err: any) {
      setError(err?.response?.data?.detail || 'No se pudo guardar el proveedor.')
    } finally {
      setGuardando(false)
    }
  }

  return (
    <div className="mb-4 rounded-xl border border-gray-200 dark:border-white/10 p-4">
      <h2 className="text-sm font-semibold text-gray-900 dark:text-gray-100 mb-3">
        {inicial ? `Editar ${inicial.razon_social}` : 'Nuevo proveedor'}
      </h2>
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
        <div>
          <label htmlFor="prov-razon" className="block text-xs text-gray-600 dark:text-gray-400 mb-1">Razón social</label>
          <input id="prov-razon" className={inputClass} value={datos.razon_social || ''} onChange={set('razon_social')} />
        </div>
        <div>
          <label htmlFor="prov-cuit" className="block text-xs text-gray-600 dark:text-gray-400 mb-1">CUIT</label>
          <input id="prov-cuit" className={inputClass} value={datos.cuit || ''} onChange={set('cuit')}
            placeholder="Opcional si es un proveedor informal" />
        </div>
        <div>
          <label htmlFor="prov-iva" className="block text-xs text-gray-600 dark:text-gray-400 mb-1">Condición frente al IVA</label>
          <select id="prov-iva" className={inputClass} value={datos.condicion_iva || ''} onChange={set('condicion_iva')}>
            <option value="">Sin cargar</option>
            {Object.entries(CONDICIONES_IVA).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
          </select>
        </div>
        <div>
          <label htmlFor="prov-email" className="block text-xs text-gray-600 dark:text-gray-400 mb-1">Email</label>
          <input id="prov-email" type="email" className={inputClass} value={datos.email || ''} onChange={set('email')} />
        </div>
        <div>
          <label htmlFor="prov-cbu" className="block text-xs text-gray-600 dark:text-gray-400 mb-1">CBU / CVU</label>
          <input id="prov-cbu" className={inputClass} value={datos.cbu || ''} onChange={set('cbu')} />
        </div>
        <div>
          <label htmlFor="prov-notas" className="block text-xs text-gray-600 dark:text-gray-400 mb-1">Notas</label>
          <input id="prov-notas" className={inputClass} value={datos.notas || ''} onChange={set('notas')} />
        </div>
      </div>
      {error && <p className="mt-3 text-sm text-red-600 dark:text-red-400">{error}</p>}
      <div className="flex gap-2 justify-end mt-4">
        <button className={`${btn} border border-gray-300 dark:border-white/15 text-gray-700 dark:text-gray-200`} onClick={onCancelar}>
          Cancelar
        </button>
        <button className={`${btn} bg-ml-blue text-white`} onClick={guardar} disabled={guardando}>
          {guardando ? 'Guardando…' : 'Guardar'}
        </button>
      </div>
    </div>
  )
}

/**
 * Ficha de proveedores PROPIOS de la organización: a quien le compra. Salen de
 * las facturas recibidas o se cargan a mano. Los proveedores de los clientes
 * (OP por cuenta de un cliente) no van acá: esos pagos son del cliente.
 */
export const Proveedores: React.FC = () => {
  const { hasPermission } = useAuthStore()
  const puedeEditar = hasPermission('reconcile')
  const { activeOrgId } = useOrgStore()
  const orgId = activeOrgId ?? undefined
  const [lista, setLista] = useState<Proveedor[] | null>(null)
  const [buscar, setBuscar] = useState('')
  const [error, setError] = useState('')
  const [aviso, setAviso] = useState('')
  const [editando, setEditando] = useState<Proveedor | 'nuevo' | null>(null)
  const [ocupado, setOcupado] = useState(false)

  const cargar = useCallback(async () => {
    setError('')
    try {
      setLista(await apiClient.listarProveedores(orgId))
    } catch (err: any) {
      setError(err?.response?.data?.detail || 'No se pudieron cargar los proveedores.')
    }
  }, [orgId])

  useEffect(() => { cargar() }, [cargar])

  const visibles = useMemo(() => {
    const q = buscar.trim().toLocaleLowerCase('es-AR')
    const digitos = q.replace(/\D/g, '')
    if (!lista || !q) return lista
    return lista.filter(p => p.razon_social.toLocaleLowerCase('es-AR').includes(q)
      || (!!digitos && !!p.cuit && p.cuit.includes(digitos)))
  }, [lista, buscar])

  const sincronizar = async () => {
    setOcupado(true)
    setAviso('')
    try {
      const { creados } = await apiClient.sincronizarProveedores(orgId)
      setAviso(creados ? `Se agregaron ${creados} proveedores nuevos desde las facturas recibidas.`
        : 'No había proveedores nuevos en las facturas recibidas.')
      await cargar()
    } catch (err: any) {
      setError(err?.response?.data?.detail || 'No se pudo traer los proveedores.')
    } finally {
      setOcupado(false)
    }
  }

  const darDeBaja = async (p: Proveedor) => {
    if (!window.confirm(`¿Dar de baja a ${p.razon_social}? Sus pagos y facturas quedan.`)) return
    try {
      await apiClient.bajaProveedor(p.id)
      await cargar()
    } catch (err: any) {
      setError(err?.response?.data?.detail || 'No se pudo dar de baja.')
    }
  }

  return (
    <div className="p-4 md:p-6 max-w-6xl mx-auto">
      <h1 className="text-xl md:text-2xl font-semibold text-gray-900 dark:text-gray-100 mb-1">Proveedores</h1>
      <p className="text-sm text-gray-500 dark:text-gray-400 mb-4">
        A quién le compra la organización. Las OP que se pagan por cuenta de un cliente no van acá: esos
        proveedores son del cliente y el pago se descuenta de su cuenta corriente.
      </p>

      <div className="flex flex-wrap items-end gap-3 mb-4">
        <div className="flex-1 min-w-[200px]">
          <label htmlFor="prov-buscar" className="block text-xs text-gray-600 dark:text-gray-400 mb-1">Buscar</label>
          <input id="prov-buscar" className={inputClass} placeholder="Nombre o CUIT" value={buscar}
            onChange={e => setBuscar(e.target.value)} />
        </div>
        {puedeEditar && (
          <>
            <button className={`${btn} border border-gray-300 dark:border-white/15 text-gray-700 dark:text-gray-200`}
              onClick={sincronizar} disabled={ocupado}>
              {ocupado ? 'Trayendo…' : 'Traer de las facturas'}
            </button>
            <button className={`${btn} bg-ml-blue text-white`} onClick={() => setEditando('nuevo')}>
              Nuevo proveedor
            </button>
          </>
        )}
      </div>

      {editando && (
        <ProveedorForm key={editando === 'nuevo' ? 'nuevo' : editando.id}
          inicial={editando === 'nuevo' ? null : editando} orgId={orgId}
          onCancelar={() => setEditando(null)}
          onGuardado={() => { setEditando(null); cargar() }} />
      )}

      {error && <p className="mb-3 text-sm text-red-600 dark:text-red-400">{error}</p>}
      {aviso && <p className="mb-3 text-sm text-ml-green">{aviso}</p>}

      {visibles && visibles.length === 0 && (
        <p className="text-sm text-gray-500 dark:text-gray-400">
          {buscar ? 'No hay proveedores que coincidan.' : 'Todavía no hay proveedores. Traelos de las facturas recibidas o cargalos a mano.'}
        </p>
      )}

      {visibles && visibles.length > 0 && (
        <div className="overflow-x-auto rounded-xl border border-gray-200 dark:border-white/10">
          <table className="w-full text-sm">
            <thead className="bg-gray-50 dark:bg-white/5 text-xs text-gray-500 dark:text-gray-400">
              <tr>
                <th className="text-left font-medium px-3 py-2">Proveedor</th>
                <th className="text-left font-medium px-3 py-2">CUIT</th>
                <th className="text-left font-medium px-3 py-2">IVA</th>
                <th className="text-right font-medium px-3 py-2">Facturado</th>
                <th className="text-right font-medium px-3 py-2">Pagado</th>
                <th className="text-right font-medium px-3 py-2">Saldo</th>
                {puedeEditar && <th className="px-3 py-2" />}
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100 dark:divide-white/10">
              {visibles.map(p => (
                <tr key={p.id}>
                  <td className="px-3 py-2 text-gray-900 dark:text-gray-100">{p.razon_social}</td>
                  <td className="px-3 py-2 font-mono text-xs text-gray-700 dark:text-gray-300">{fmtCuit(p.cuit)}</td>
                  <td className="px-3 py-2 text-xs text-gray-700 dark:text-gray-300">
                    {p.condicion_iva ? CONDICIONES_IVA[p.condicion_iva] : <span className="text-gray-400">Sin cargar</span>}
                  </td>
                  <td className="px-3 py-2 text-right font-mono text-xs">{fmtARS(p.total_facturado)}</td>
                  <td className="px-3 py-2 text-right font-mono text-xs">{fmtARS(p.total_pagado)}</td>
                  <td className={`px-3 py-2 text-right font-mono text-xs ${Number(p.saldo) > 0 ? 'text-amber-700 dark:text-amber-300' : ''}`}>
                    {fmtARS(p.saldo)}
                  </td>
                  {puedeEditar && (
                    <td className="px-3 py-2 text-right whitespace-nowrap">
                      <button className="text-xs text-ml-blue hover:underline mr-3" onClick={() => setEditando(p)}
                        aria-label={`Editar ${p.razon_social}`}>Editar</button>
                      <button className="text-xs text-red-600 dark:text-red-400 hover:underline" onClick={() => darDeBaja(p)}
                        aria-label={`Dar de baja ${p.razon_social}`}>Dar de baja</button>
                    </td>
                  )}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      <p className="mt-3 text-xs text-gray-500 dark:text-gray-400">
        Facturado: facturas recibidas en IVA (las notas de crédito restan). Pagado: pagos a proveedor vinculados a la ficha.
      </p>
    </div>
  )
}

export default Proveedores
