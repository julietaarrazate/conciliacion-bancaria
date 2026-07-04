import React from 'react'
import { apiClient } from '@/services/api'
import { toast } from '@/store/toast'
import { fmtDate, fmtNum, CAT_KEYS, CAT_LABEL, ESTADO_BADGE, GEN_BADGE, CcFiltro } from './shared'
import type { ContabilidadCtx } from './useContabilidad'

export const ContabilidadCtaCteLista: React.FC<{ c: ContabilidadCtx }> = ({ c }) => {
  const { user } = c
  return (
    <div>
      <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-2 mb-3">
        <p className="text-xs text-gray-500 dark:text-gray-400 flex-1">
          Visión global de la cartera. Saldo, último movimiento y estado por cliente — vista derivada de los asientos. No genera asientos.
        </p>
        {c.canAdminAccounting && (
          <div className="flex flex-col sm:flex-row gap-2 shrink-0">
            {user?.is_superadmin && (
              <>
                <button
                  onClick={c.resetYRebuild}
                  disabled={c.backfilling}
                  className="w-full sm:w-auto text-xs px-3 py-2 rounded-lg bg-emerald-600 text-white font-medium hover:bg-emerald-700 disabled:opacity-50"
                  title="Borra TODOS los asientos y reconstruye el Libro Diario limpio desde cero (banco UM + conciliaciones agrupadas), numerado desde 1. Vincula cuentas de clientes automáticamente."
                >
                  {c.backfilling ? 'Empezando…' : '🧹 Empezar limpio'}
                </button>
                <button
                  onClick={c.fixFechasUtc}
                  className="w-full sm:w-auto text-xs px-3 py-2 rounded-lg border border-orange-300 dark:border-orange-800 text-orange-600 dark:text-orange-400 font-medium hover:bg-orange-50 dark:hover:bg-orange-900/20"
                  title="Identifica y corrige registros con fecha UTC en vez de ART"
                >
                  🕐 Fix fechas UTC
                </button>
                <button
                  onClick={c.verGaps}
                  className="w-full sm:w-auto text-xs px-3 py-2 rounded-lg border border-gray-300 dark:border-gray-700 text-gray-600 dark:text-gray-400 font-medium hover:bg-gray-50 dark:hover:bg-gray-800"
                  title="Ver qué números de asiento están faltando en la secuencia"
                >
                  🔍 Ver gaps
                </button>
              </>
            )}
          </div>
        )}
      </div>
      <div className="flex flex-wrap items-center gap-2 mb-3">
        <input
          type="text" placeholder="Buscar cliente…"
          value={c.ccBusqueda} onChange={e => c.setCcBusqueda(e.target.value)}
          className="input-field max-w-[200px]"
        />
        <div className="flex items-center gap-1 flex-wrap">
          {([
            ['todos', 'Todos'], ['deudores', 'Deudores'], ['acreedores', 'Acreedores'],
            ['cero', 'Saldo cero'], ['recientes', 'Recientes'], ['sin_actividad', 'Sin actividad'],
          ] as [CcFiltro, string][]).map(([f, label]) => (
            <button key={f} onClick={() => c.setCcFiltro(f)}
              className={`px-2 py-1 rounded-md text-[11px] font-medium transition-colors ${
                c.ccFiltro === f ? 'bg-ml-blue text-white' : 'bg-gray-100 dark:bg-slate-800 text-gray-600 dark:text-gray-400 hover:bg-gray-200 dark:hover:bg-slate-700'
              }`}>{label}</button>
          ))}
        </div>
      </div>
      {c.loadingCartera ? (
        <div className="py-12 text-center text-gray-400">Cargando...</div>
      ) : (() => {
        const ahora = Date.now()
        const filtradas = c.cartera.filter(item => {
          if (c.ccBusqueda && !item.cliente_nombre.toLowerCase().includes(c.ccBusqueda.toLowerCase())) return false
          if (c.ccFiltro === 'deudores') return item.saldo > 0
          if (c.ccFiltro === 'acreedores') return item.saldo < 0
          if (c.ccFiltro === 'cero') return item.saldo === 0 && item.estado_general !== 'sin_actividad'
          if (c.ccFiltro === 'sin_actividad') return item.estado_general === 'sin_actividad'
          if (c.ccFiltro === 'recientes') return item.ultimo_movimiento != null && (ahora - new Date(item.ultimo_movimiento).getTime()) < 30 * 86400000
          return true
        })
        return filtradas.length === 0 ? (
          <p className="text-center py-8 text-gray-400 text-sm">Sin clientes para este filtro.</p>
        ) : (
          <div className="border border-gray-200 dark:border-slate-700 rounded-xl overflow-hidden">
            <div className="overflow-x-auto"><table className="w-full text-xs min-w-[560px]">
              <thead className="bg-gray-50 dark:bg-slate-800">
                <tr>
                  <th className="text-left px-3 py-2 font-medium text-gray-500">Cliente</th>
                  <th className="text-left px-3 py-2 font-medium text-gray-500">Cuenta</th>
                  <th className="text-right px-3 py-2 font-medium text-gray-500">Saldo</th>
                  <th className="text-left px-3 py-2 font-medium text-gray-500">Último mov.</th>
                  <th className="text-left px-3 py-2 font-medium text-gray-500">Estado</th>
                  <th className="text-right px-3 py-2 font-medium text-gray-500"></th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100 dark:divide-slate-700/50">
                {filtradas.map(item => {
                  const g = GEN_BADGE[item.estado_general]
                  return (
                    <tr key={item.cliente_id} className="hover:bg-gray-50 dark:hover:bg-slate-800/40 cursor-pointer" onClick={() => c.verCtaCteCliente(item.cliente_id)}>
                      <td className="px-3 py-2 font-medium text-ml-text dark:text-gray-200">{item.cliente_nombre}</td>
                      <td className="px-3 py-2 font-mono text-[11px] text-gray-400">{item.cuenta?.codigo}</td>
                      <td className="px-3 py-2 text-right font-mono text-gray-700 dark:text-gray-300">{fmtNum(item.saldo)}</td>
                      <td className="px-3 py-2 text-gray-500 dark:text-gray-400">{item.ultimo_movimiento ? fmtDate(item.ultimo_movimiento) : '—'}</td>
                      <td className="px-3 py-2"><span className={`text-[10px] px-1.5 py-0.5 rounded-full border ${g.cls}`} title={item.estado_general === 'sin_actividad' ? 'Cuenta vinculada sin movimientos contables (no implica inactividad comercial)' : undefined}>{g.label}</span></td>
                      <td className="px-3 py-2 text-right"><span className="text-ml-blue text-[11px] hover:underline">Ver →</span></td>
                    </tr>
                  )
                })}
              </tbody>
            </table></div>
          </div>
        )
      })()}
      <p className="text-[10px] text-gray-400 mt-2">
        "Sin actividad" = cuenta contable vinculada pero sin movimientos en la cuenta corriente. No implica inactividad comercial del cliente.
      </p>
    </div>
  )
}

export const ContabilidadCtaCteDetalle: React.FC<{ c: ContabilidadCtx }> = ({ c }) => {
  const { ctaCte } = c
  return (
    <div>
      <div className="flex flex-wrap items-center gap-2 mb-3">
        <button onClick={() => { c.setCcMode('list'); c.setCtaCte(null); c.setCtaCteClienteId(''); c.cargarCartera() }}
          className="text-xs text-ml-blue hover:underline">← Volver a cartera</button>
        <select
          value={c.ctaCteClienteId}
          onChange={e => { const v = e.target.value ? Number(e.target.value) : ''; if (v) c.verCtaCteCliente(v) }}
          className="input-field max-w-[220px]"
        >
          <option value="">Elegí un cliente…</option>
          {c.cliCuentas.map(cli => (
            <option key={cli.cliente_id} value={cli.cliente_id}>{cli.cliente_nombre}</option>
          ))}
        </select>
        <div className="flex items-center gap-2 flex-wrap">
          {CAT_KEYS.map(cat => (
            <label key={cat} className="flex items-center gap-1 text-xs text-gray-600 dark:text-gray-300 cursor-pointer">
              <input type="checkbox" checked={c.catFiltro.has(cat)} onChange={() => c.toggleCat(cat)} className="accent-ml-blue" />
              {CAT_LABEL[cat]}
            </label>
          ))}
        </div>
        {c.ctaCteClienteId && (
          <button
            onClick={() => apiClient.downloadCtaCtePdf(Number(c.ctaCteClienteId), c.activeOrgId ?? undefined)}
            className="ml-auto text-xs px-2 py-1 rounded-lg border border-gray-300 dark:border-ml-dark-border text-gray-600 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-white/5 flex items-center gap-1"
            title="Exportar PDF cuenta corriente"
          >
            <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 21h10a2 2 0 002-2V9.414a1 1 0 00-.293-.707l-5.414-5.414A1 1 0 0012.586 3H7a2 2 0 00-2 2v14a2 2 0 002 2z"/></svg>
            PDF
          </button>
        )}
      </div>

      {c.loadingCtaCte ? (
        <div className="py-12 text-center text-gray-400">Cargando...</div>
      ) : !ctaCte ? (
        <p className="text-center py-8 text-gray-400 text-sm">Elegí un cliente para ver su cuenta corriente.</p>
      ) : ctaCte.sin_cuenta ? (
        <div className="text-center py-8 text-sm text-amber-600 dark:text-amber-400">
          {ctaCte.cliente.nombre} no tiene cuenta contable vinculada. Vinculala en el tab 🔗 Clientes.
        </div>
      ) : (() => {
        const visibles = ctaCte.movimientos.filter(m => c.catFiltro.has(m.tipo_cat))
        return (
          <div>
            <div className="flex flex-wrap gap-3 mb-2 text-xs">
              <span className="text-gray-500 dark:text-gray-400">Cuenta: <span className="font-mono text-amber-600 dark:text-amber-400">{ctaCte.cuenta?.codigo} {ctaCte.cuenta?.nombre}</span></span>
              <span className="text-gray-400">({visibles.length} de {ctaCte.movimientos.length} movimientos)</span>
            </div>
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-2 mb-3">
              <div className="bg-blue-50 dark:bg-blue-900/20 border border-blue-200 dark:border-blue-800 rounded-lg px-3 py-2 flex sm:block items-center justify-between sm:text-center">
                <p className="text-[10px] text-blue-600 dark:text-blue-400 font-medium">Total Débito</p>
                <p className="font-mono text-sm font-semibold text-blue-700 dark:text-blue-300">{fmtNum(ctaCte.total_debito)}</p>
              </div>
              <div className="bg-orange-50 dark:bg-orange-900/20 border border-orange-200 dark:border-orange-800 rounded-lg px-3 py-2 flex sm:block items-center justify-between sm:text-center">
                <p className="text-[10px] text-orange-600 dark:text-orange-400 font-medium">Total Crédito</p>
                <p className="font-mono text-sm font-semibold text-orange-700 dark:text-orange-300">{fmtNum(ctaCte.total_credito)}</p>
              </div>
              <div className={`rounded-lg px-3 py-2 flex sm:block items-center justify-between sm:text-center border ${ctaCte.saldo_final >= 0 ? 'bg-green-50 dark:bg-green-900/20 border-green-200 dark:border-green-800' : 'bg-red-50 dark:bg-red-900/20 border-red-200 dark:border-red-800'}`}>
                <p className={`text-[10px] font-medium ${ctaCte.saldo_final >= 0 ? 'text-green-600 dark:text-green-400' : 'text-red-600 dark:text-red-400'}`}>Saldo Final</p>
                <p className={`font-mono text-sm font-bold ${ctaCte.saldo_final >= 0 ? 'text-green-700 dark:text-green-300' : 'text-red-700 dark:text-red-300'}`}>{fmtNum(ctaCte.saldo_final)}</p>
              </div>
            </div>
            {visibles.length === 0 ? (
              <p className="text-center py-8 text-gray-400 text-sm">Sin movimientos para los filtros elegidos.</p>
            ) : (
              <div className="border border-gray-200 dark:border-slate-700 rounded-xl overflow-hidden">
                <div className="overflow-x-auto"><table className="w-full text-xs min-w-[640px]">
                  <thead className="bg-gray-50 dark:bg-slate-800">
                    <tr>
                      <th className="text-left px-3 py-2 font-medium text-gray-500">Fecha</th>
                      <th className="text-left px-3 py-2 font-medium text-gray-500">Tipo</th>
                      <th className="text-left px-3 py-2 font-medium text-gray-500">Referencia</th>
                      <th className="text-left px-3 py-2 font-medium text-gray-500">Estado</th>
                      <th className="text-right px-3 py-2 font-medium text-blue-600 dark:text-blue-400">Débito</th>
                      <th className="text-right px-3 py-2 font-medium text-orange-600 dark:text-orange-400">Crédito</th>
                      <th className="text-right px-3 py-2 font-medium text-gray-500">Saldo</th>
                      <th className="text-right px-3 py-2 font-medium text-gray-500">Origen</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-100 dark:divide-slate-700/50">
                    {visibles.map((m, i) => (
                      <tr key={i} className="hover:bg-gray-50 dark:hover:bg-slate-800/40">
                        <td className="px-3 py-2 whitespace-nowrap text-gray-600 dark:text-gray-400">{fmtDate(m.fecha)}</td>
                        <td className="px-3 py-2 text-gray-700 dark:text-gray-300">{m.tipo_label}</td>
                        <td className="px-3 py-2 text-gray-700 dark:text-gray-300 max-w-[150px] truncate" title={m.referencia}>{m.referencia}</td>
                        <td className="px-3 py-2">
                          <span className={`text-[10px] px-1.5 py-0.5 rounded-full border ${ESTADO_BADGE[m.estado] || ''}`}>{m.estado}</span>
                        </td>
                        <td className="px-3 py-2 text-right font-mono text-blue-700 dark:text-blue-300">{m.debito > 0 ? fmtNum(m.debito) : ''}</td>
                        <td className="px-3 py-2 text-right font-mono text-orange-700 dark:text-orange-300">{m.credito > 0 ? fmtNum(m.credito) : ''}</td>
                        <td className="px-3 py-2 text-right font-mono text-gray-700 dark:text-gray-300">{fmtNum(m.saldo)}</td>
                        <td className="px-3 py-2 text-right whitespace-nowrap">
                          {m.origen.extracto_id && (
                            <a href={`/movimientos?extracto=${m.origen.extracto_id}`} className="text-ml-blue hover:underline mr-2" title="Movimiento bancario">🏦</a>
                          )}
                          {m.origen.planilla_id && (
                            <>
                              <button onClick={async () => { try { await apiClient.downloadPlanillaConciliada(m.origen.planilla_id!) } catch { toast.error('No se pudo descargar') } }} className="text-ml-blue hover:underline mr-2" title="Descargar Excel planilla">📄</button>
                              <button onClick={async () => { try { await apiClient.exportPlanillaPdf(m.origen.planilla_id!) } catch { toast.error('No se pudo descargar') } }} className="text-ml-blue hover:underline" title="Descargar PDF planilla">📕</button>
                            </>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                  <tfoot className="bg-gray-50 dark:bg-slate-800 border-t border-gray-200 dark:border-slate-700">
                    <tr>
                      <td colSpan={3} className="px-3 py-2 font-semibold text-gray-600 dark:text-gray-400">Totales (todos los movimientos)</td>
                      <td className="px-3 py-2 text-right font-mono font-semibold text-blue-700 dark:text-blue-300">{fmtNum(ctaCte.total_debito)}</td>
                      <td className="px-3 py-2 text-right font-mono font-semibold text-orange-700 dark:text-orange-300">{fmtNum(ctaCte.total_credito)}</td>
                      <td className="px-3 py-2 text-right font-mono font-semibold">{fmtNum(ctaCte.saldo_final)}</td>
                      <td></td>
                    </tr>
                  </tfoot>
                </table></div>
              </div>
            )}
          </div>
        )
      })()}
    </div>
  )
}
