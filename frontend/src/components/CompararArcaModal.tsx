import React, { useEffect, useState } from 'react'
import { apiClient } from '@/services/api'
import { CompararComprobantesIvaResult, ImportarComprobantesIvaResult } from '@/types'

interface CompararArcaModalProps {
  file: File
  direccion: 'emitido' | 'recibido'
  periodo: string
  orgId?: number
  onClose: () => void
  onImportado: (res: ImportarComprobantesIvaResult) => void
}

function fmtARS(n: number) {
  return new Intl.NumberFormat('es-AR', { style: 'currency', currency: 'ARS', minimumFractionDigits: 2 }).format(Number(n))
}
function fmtFecha(d?: string | null) {
  if (!d) return '—'
  return new Date(d + 'T00:00:00').toLocaleDateString('es-AR', { day: '2-digit', month: '2-digit', year: '2-digit' })
}
function nroComp(pv?: number | string | null, num?: number | string | null) {
  return `${String(pv ?? 0).padStart(5, '0')}-${String(num ?? 0).padStart(8, '0')}`
}

/**
 * Compara el Excel "Mis Comprobantes" de ARCA con lo cargado en Cuadra antes de
 * importar: qué falta (para elegir qué traer), qué ya está con otro importe y qué
 * está en Cuadra y ARCA no tiene. No se conecta a ARCA: usa el Excel bajado de la web.
 */
export const CompararArcaModal: React.FC<CompararArcaModalProps> = ({
  file, direccion, periodo, orgId, onClose, onImportado,
}) => {
  const [res, setRes] = useState<CompararComprobantesIvaResult | null>(null)
  const [elegidas, setElegidas] = useState<Set<string>>(new Set())
  const [error, setError] = useState('')
  const [importando, setImportando] = useState(false)

  useEffect(() => {
    let cancelado = false
    apiClient.compararComprobantesIva(file, direccion, periodo, orgId)
      .then(r => {
        if (cancelado) return
        setRes(r)
        setElegidas(new Set(r.faltantes.map(f => f.clave)))
      })
      .catch((err: any) => {
        if (!cancelado) setError(err?.response?.data?.detail || 'No se pudo leer el archivo.')
      })
    return () => { cancelado = true }
  }, [file, direccion, periodo, orgId])

  const toggle = (clave: string) => setElegidas(prev => {
    const s = new Set(prev)
    if (s.has(clave)) s.delete(clave)
    else s.add(clave)
    return s
  })

  const importar = async () => {
    if (!res) return
    setImportando(true)
    setError('')
    try {
      const claves = res.faltantes.map(f => f.clave).filter(c => elegidas.has(c))
      onImportado(await apiClient.importarComprobantesIva(file, direccion, periodo, orgId, claves))
    } catch (err: any) {
      setError(err?.response?.data?.detail || 'No se pudo importar.')
    } finally {
      setImportando(false)
    }
  }

  const titulo = direccion === 'emitido' ? 'ventas' : 'compras'
  const distintos = res?.ya_cargados.filter(f => f.importe_distinto) ?? []

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50" onClick={onClose}>
      <div className="bg-white dark:bg-slate-800 rounded-xl shadow-xl p-5 w-full max-w-2xl mx-4 max-h-[90vh] overflow-y-auto"
        onClick={e => e.stopPropagation()} role="dialog" aria-label="Comparar con ARCA">
        <h3 className="text-sm font-semibold text-ml-text dark:text-gray-100">Comparar {titulo} de ARCA con Cuadra · {periodo}</h3>
        <p className="text-[11px] text-gray-500 dark:text-gray-400 mb-4">
          Antes de importar, revisá qué falta. Solo se cargan las facturas que tildes.
        </p>

        {error && <p className="mb-3 text-xs text-red-600 dark:text-red-400">{error}</p>}
        {!res && !error && <p className="text-xs text-gray-400">Comparando…</p>}

        {res && (
          <div className="space-y-4">
            <div className="flex flex-wrap gap-2 text-[11px]">
              <span className="pill rounded-full bg-amber-100 dark:bg-amber-900/40 text-amber-800 dark:text-amber-300">
                {res.faltantes.length} faltan en Cuadra
              </span>
              <span className="pill rounded-full bg-green-100 dark:bg-green-900/40 text-green-800 dark:text-green-300">
                {res.ya_cargados.length} ya cargadas
              </span>
              {res.solo_en_cuadra.length > 0 && (
                <span className="pill rounded-full bg-red-100 dark:bg-red-900/40 text-red-800 dark:text-red-300">
                  {res.solo_en_cuadra.length} en Cuadra y no en ARCA
                </span>
              )}
              {res.fuera_de_periodo > 0 && (
                <span className="pill rounded-full bg-gray-100 dark:bg-slate-700 text-gray-600 dark:text-gray-300">
                  {res.fuera_de_periodo} de otro período (se ignoran)
                </span>
              )}
            </div>

            <section>
              <h4 className="text-xs font-semibold text-gray-700 dark:text-gray-200 mb-1">Faltan en Cuadra</h4>
              {res.faltantes.length === 0 ? (
                <p className="text-xs text-gray-500 dark:text-gray-400">No falta nada: todo lo de ARCA ya está cargado.</p>
              ) : (
                <>
                  <p className="text-[11px] text-gray-500 dark:text-gray-400 mb-1">
                    IVA {direccion === 'emitido' ? 'débito' : 'crédito'} que suman: <b className="font-mono">{fmtARS(res.iva_faltante)}</b>
                  </p>
                  <ul className="divide-y divide-gray-100 dark:divide-slate-700 text-xs">
                    {res.faltantes.map(f => (
                      <li key={f.clave} className="py-1.5">
                        <label className="flex items-center gap-2 cursor-pointer">
                          <input type="checkbox" checked={elegidas.has(f.clave)} onChange={() => toggle(f.clave)}
                            aria-label={`${f.denominacion || f.cuit_contraparte} ${nroComp(f.punto_venta, f.numero)}`} />
                          <span className="w-16 text-gray-500 dark:text-gray-400">{fmtFecha(f.fecha)}</span>
                          <span className="min-w-0 flex-1">
                            <span className="block truncate dark:text-gray-200">{f.denominacion || f.cuit_contraparte}</span>
                            <span className="block truncate text-[10px] text-gray-400">
                              {f.tipo_desc} {nroComp(f.punto_venta, f.numero)}
                            </span>
                          </span>
                          <span className="text-right font-mono dark:text-gray-200">
                            {f.es_nota_credito ? '−' : ''}{fmtARS(f.imp_total)}
                            <span className="block text-[10px] text-gray-400">IVA {fmtARS(f.total_iva)}</span>
                          </span>
                        </label>
                      </li>
                    ))}
                  </ul>
                </>
              )}
            </section>

            {distintos.length > 0 && (
              <section>
                <h4 className="text-xs font-semibold text-gray-700 dark:text-gray-200 mb-1">Ya cargadas con importe distinto</h4>
                <ul className="divide-y divide-gray-100 dark:divide-slate-700 text-xs">
                  {distintos.map(f => (
                    <li key={f.clave} className="py-1.5 flex gap-2">
                      <span className="min-w-0 flex-1 truncate dark:text-gray-200">
                        {f.denominacion} · {nroComp(f.punto_venta, f.numero)}
                      </span>
                      <span className="text-amber-700 dark:text-amber-300">
                        Importe distinto: IVA ARCA {fmtARS(f.total_iva)} · Cuadra {fmtARS(f.total_iva_cuadra ?? 0)}
                      </span>
                    </li>
                  ))}
                </ul>
              </section>
            )}

            {res.solo_en_cuadra.length > 0 && (
              <section>
                <h4 className="text-xs font-semibold text-gray-700 dark:text-gray-200 mb-1">En Cuadra y no en ARCA</h4>
                <p className="text-[11px] text-gray-500 dark:text-gray-400 mb-1">
                  ARCA no tiene estos comprobantes: revisá si están bien cargados.
                  {direccion === 'recibido' && ' Si el proveedor no los informó, ese crédito fiscal no se puede computar.'}
                </p>
                <ul className="divide-y divide-gray-100 dark:divide-slate-700 text-xs">
                  {res.solo_en_cuadra.map(c => (
                    <li key={c.id} className="py-1.5 flex gap-2">
                      <span className="w-16 text-gray-500 dark:text-gray-400">{fmtFecha(c.fecha)}</span>
                      <span className="min-w-0 flex-1 truncate dark:text-gray-200">{c.denominacion || c.cuit_contraparte}</span>
                      <span className="text-[10px] text-gray-400">{nroComp(c.punto_venta, c.numero)}</span>
                      <span className="font-mono dark:text-gray-200">{fmtARS(c.imp_total)}</span>
                    </li>
                  ))}
                </ul>
              </section>
            )}
          </div>
        )}

        <div className="flex gap-2 mt-5 justify-end">
          <button onClick={onClose}
            className="px-3 py-1.5 text-xs text-gray-500 border border-gray-200 dark:border-slate-600 rounded-sm hover:bg-gray-50 dark:hover:bg-slate-700">
            {res && res.faltantes.length > 0 ? 'Cancelar' : 'Cerrar'}
          </button>
          {res && res.faltantes.length > 0 && (
            <button onClick={importar} disabled={importando || elegidas.size === 0}
              className="px-4 py-1.5 text-xs bg-ml-blue text-white rounded-sm hover:bg-ml-blue/90 disabled:opacity-50">
              {importando ? 'Importando…' : `Importar ${elegidas.size} ${elegidas.size === 1 ? 'factura' : 'facturas'}`}
            </button>
          )}
        </div>
      </div>
    </div>
  )
}
