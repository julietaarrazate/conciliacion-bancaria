import React from 'react'
import { fmtDate, fmtNum, MODULO_LABEL, ExcelFilterCtb } from './shared'
import type { ContabilidadCtx } from './useContabilidad'

export const ContabilidadLibroDiario: React.FC<{ c: ContabilidadCtx }> = ({ c }) => {
  const { canAdminAccounting, user } = c
  return (
    <>
      <div className="flex justify-end mb-3 gap-2">
        <button
          onClick={() => { c.setExportWarn([]); c.setExportModalOpen(true) }}
          className="text-xs px-3 py-2 rounded-lg bg-gray-100 dark:bg-slate-700 text-gray-700 dark:text-gray-200 font-medium hover:bg-gray-200 dark:hover:bg-slate-600 flex items-center gap-1.5 border border-gray-200 dark:border-slate-600"
        >
          <svg xmlns="http://www.w3.org/2000/svg" className="w-3.5 h-3.5" viewBox="0 0 20 20" fill="currentColor">
            <path fillRule="evenodd" d="M3 17a1 1 0 011-1h12a1 1 0 110 2H4a1 1 0 01-1-1zm3.293-7.707a1 1 0 011.414 0L9 10.586V3a1 1 0 112 0v7.586l1.293-1.293a1 1 0 111.414 1.414l-3 3a1 1 0 01-1.414 0l-3-3a1 1 0 010-1.414z" clipRule="evenodd" />
          </svg>
          Exportar contable
        </button>
        {canAdminAccounting && (
          <button
            onClick={() => { c.setAjusteError(''); c.setAjusteModalOpen(true) }}
            className="text-xs px-3 py-2 rounded-lg bg-ml-blue text-white font-medium hover:bg-ml-blue-dark flex items-center gap-1.5"
          >
            <span>✏️</span> Ajuste manual
          </button>
        )}
      </div>
      <div className="border border-gray-200 dark:border-slate-700 rounded-xl overflow-hidden">
        {c.asientos.length === 0 && !c.diarioDesde && !c.diarioHasta && !c.diarioModulo && !c.diarioCuentaId ? (
          <div className="py-16 text-center text-gray-400">
            <p className="text-3xl mb-2">📒</p>
            <p className="text-sm">Sin asientos todavía.</p>
            <p className="text-xs mt-1">Se generan automáticamente al subir extractos y conciliar planillas.</p>
          </div>
        ) : (
          <>
          {/* Barra de chips de filtros activos */}
          {(c.diarioDesde || c.diarioHasta || c.diarioModulo || c.diarioCuentaId) && (
            <div className="flex flex-wrap gap-2 px-3 py-2 bg-yellow-50 dark:bg-yellow-900/10 border-b border-yellow-200 dark:border-yellow-800 text-xs">
              <span className="text-gray-500">Filtros:</span>
              {c.diarioDesde && <span className="px-2 py-0.5 rounded-full bg-yellow-100 dark:bg-yellow-900/30 text-yellow-800 dark:text-yellow-300">Desde {c.diarioDesde}</span>}
              {c.diarioHasta && <span className="px-2 py-0.5 rounded-full bg-yellow-100 dark:bg-yellow-900/30 text-yellow-800 dark:text-yellow-300">Hasta {c.diarioHasta}</span>}
              {c.diarioModulo && <span className="px-2 py-0.5 rounded-full bg-yellow-100 dark:bg-yellow-900/30 text-yellow-800 dark:text-yellow-300">{(MODULO_LABEL[c.diarioModulo] || c.diarioModulo)}</span>}
              {c.diarioCuentaId && <span className="px-2 py-0.5 rounded-full bg-yellow-100 dark:bg-yellow-900/30 text-yellow-800 dark:text-yellow-300">
                {c.cuentas.find(cu => cu.id === c.diarioCuentaId)?.nombre || `Cuenta #${c.diarioCuentaId}`}
              </span>}
              <button onClick={() => { c.setDiarioDesde(''); c.setDiarioHasta(''); c.setDiarioModulo(''); c.setDiarioCuentaId(''); c.setDiarioCuentaBusq('') }}
                className="ml-auto text-gray-400 hover:text-red-500">✕ Limpiar</button>
            </div>
          )}
          <div className="overflow-x-auto"><table className="w-full text-xs min-w-[420px]">
            <thead className="bg-gray-50 dark:bg-slate-800 text-gray-500">
              <tr>
                <th className="w-6 px-2 py-2"></th>
                <th className="px-3 py-2 font-medium w-14 text-left">
                  <ExcelFilterCtb label="Nro" active={false}>
                    <p className="text-xs text-gray-400 mb-1">Los números se asignan al hacer el reset del Libro Diario.</p>
                  </ExcelFilterCtb>
                </th>
                <th className="px-3 py-2 font-medium text-left">
                  <ExcelFilterCtb label="Fecha" active={!!(c.diarioDesde || c.diarioHasta)}>
                    <div className="flex flex-col gap-2">
                      <label className="text-xs text-gray-500">Desde</label>
                      <input type="date" value={c.diarioDesde} onChange={e => c.setDiarioDesde(e.target.value)}
                        className="border border-gray-200 dark:border-slate-600 rounded px-2 py-1 text-xs bg-white dark:bg-slate-700 text-gray-800 dark:text-gray-200 w-full" />
                      <label className="text-xs text-gray-500">Hasta</label>
                      <input type="date" value={c.diarioHasta} onChange={e => c.setDiarioHasta(e.target.value)}
                        className="border border-gray-200 dark:border-slate-600 rounded px-2 py-1 text-xs bg-white dark:bg-slate-700 text-gray-800 dark:text-gray-200 w-full" />
                      {(c.diarioDesde || c.diarioHasta) && (
                        <button onClick={() => { c.setDiarioDesde(''); c.setDiarioHasta('') }} className="text-xs text-red-400 hover:text-red-600 text-left">✕ Limpiar</button>
                      )}
                    </div>
                  </ExcelFilterCtb>
                </th>
                <th className="px-3 py-2 font-medium text-left">
                  <ExcelFilterCtb label="Concepto" active={!!c.diarioModulo}>
                    <div className="flex flex-col gap-1">
                      {['', 'um_lote', 'um_reclass', 'cc_inicial', 'cheque_registro', 'cheque_acred_banco', 'cheque_acred_cliente', 'cheque_rechazo_banco', 'cheque_rechazo_cliente', 'cheque_rechazo_gasto', 'egreso', 'caja_op', 'caja_efectivo', 'ajuste_manual', 'ajuste_manual_reverso'].map(m => (
                        <button key={m} onClick={() => c.setDiarioModulo(m)}
                          className={`text-left px-2 py-1 rounded text-xs hover:bg-gray-100 dark:hover:bg-slate-700 ${c.diarioModulo === m ? 'bg-ml-blue text-white' : 'text-gray-700 dark:text-gray-300'}`}>
                          {m === '' ? '(Todos)' : (MODULO_LABEL[m] || m)}
                        </button>
                      ))}
                    </div>
                  </ExcelFilterCtb>
                </th>
                <th className="px-3 py-2 font-medium text-left">
                  <ExcelFilterCtb label="Cuenta" active={!!c.diarioCuentaId} align="right">
                    <div className="flex flex-col gap-2">
                      <input placeholder="Buscar cuenta..." value={c.diarioCuentaBusq} onChange={e => c.setDiarioCuentaBusq(e.target.value)}
                        className="border border-gray-200 dark:border-slate-600 rounded px-2 py-1 text-xs bg-white dark:bg-slate-700 text-gray-800 dark:text-gray-200 w-full" />
                      <div className="max-h-48 overflow-y-auto flex flex-col gap-0.5">
                        <button onClick={() => { c.setDiarioCuentaId(''); c.setDiarioCuentaBusq('') }}
                          className={`text-left px-2 py-1 rounded text-xs hover:bg-gray-100 dark:hover:bg-slate-700 ${!c.diarioCuentaId ? 'bg-ml-blue text-white' : 'text-gray-700 dark:text-gray-300'}`}>
                          (Todas)
                        </button>
                        {c.cuentas.filter(cu => !c.diarioCuentaBusq || `${cu.codigo} ${cu.nombre}`.toLowerCase().includes(c.diarioCuentaBusq.toLowerCase())).map(cu => (
                          <button key={cu.id} onClick={() => c.setDiarioCuentaId(cu.id)}
                            className={`text-left px-2 py-1 rounded text-xs hover:bg-gray-100 dark:hover:bg-slate-700 ${c.diarioCuentaId === cu.id ? 'bg-ml-blue text-white' : 'text-gray-700 dark:text-gray-300'}`}>
                            <span className="font-mono">{cu.codigo}</span> {cu.nombre}
                          </button>
                        ))}
                      </div>
                    </div>
                  </ExcelFilterCtb>
                </th>
                <th className="px-3 py-2 font-medium text-left">Descripción</th>
                {canAdminAccounting && <th className="w-8 px-2 py-2"></th>}
              </tr>
            </thead>
            <tbody>
              {c.asientos.map(a => {
                const isOpen = c.openAsientos.has(a.id)
                const isLoading = c.loadingLineas.has(a.id)
                const lineas = c.asientoLineas[a.id]
                return (
                  <React.Fragment key={a.id}>
                    <tr
                      className="border-b border-gray-100 dark:border-slate-700/50 hover:bg-gray-50 dark:hover:bg-slate-800/40 cursor-pointer select-none"
                      onClick={() => c.toggleAsiento(a.id)}
                    >
                      <td className="px-2 py-2 text-gray-400 text-center">{isOpen ? '▾' : '▸'}</td>
                      <td className="px-3 py-2 text-gray-400 font-mono">{a.numero_asiento ?? a.id}</td>
                      <td className="px-3 py-2 whitespace-nowrap" onClick={e => e.stopPropagation()}>
                        {user?.is_superadmin && c.editFechaId === a.id ? (
                          <div className="flex flex-col gap-1 min-w-[130px]">
                            <input type="date" value={c.editFechaVal}
                              onChange={e => c.setEditFechaVal(e.target.value)}
                              className="text-xs border border-orange-300 dark:border-orange-600 rounded px-2 py-1 bg-white dark:bg-slate-800 text-gray-900 dark:text-white w-full"
                              onKeyDown={e => { if (e.key === 'Enter') c.saveFechaAsiento(a.id); if (e.key === 'Escape') c.setEditFechaId(null) }}
                              autoFocus
                            />
                            <button onClick={() => c.saveFechaAsiento(a.id)}
                              className="w-full text-xs px-2 py-1 rounded bg-orange-500 hover:bg-orange-600 text-white font-semibold">
                              Guardar
                            </button>
                          </div>
                        ) : (
                          <span
                            className={`text-gray-700 dark:text-gray-300 ${user?.is_superadmin ? 'cursor-pointer hover:underline hover:text-orange-600 dark:hover:text-orange-400' : ''}`}
                            title={user?.is_superadmin ? 'Clic para editar fecha' : undefined}
                            onClick={() => { if (user?.is_superadmin) { c.setEditFechaId(a.id); c.setEditFechaVal(a.fecha || '') } }}
                          >{fmtDate(a.fecha)}</span>
                        )}
                      </td>
                      <td className="px-3 py-2">
                        <span className="text-[10px] px-1.5 py-0.5 rounded bg-gray-100 dark:bg-slate-700 text-gray-500">
                          {(a.modulo && MODULO_LABEL[a.modulo]) || a.modulo || '—'}
                        </span>
                      </td>
                      <td className="px-3 py-2 max-w-[180px]">
                        {(a.cuentas || []).map((cu, i) => (
                          <span key={i} className="block font-mono text-[10px] text-gray-500 dark:text-gray-400 truncate" title={cu}>{cu}</span>
                        ))}
                      </td>
                      <td className="px-3 py-2 text-gray-700 dark:text-gray-300">{a.descripcion || '—'}</td>
                      {canAdminAccounting && (
                        <td className="px-2 py-2 text-center" onClick={e => e.stopPropagation()}>
                          {a.modulo === 'ajuste_manual' && (
                            <button
                              onClick={() => { if (confirm('¿Revertir este ajuste manual?')) c.deleteAjusteManual(a.id) }}
                              className="text-red-400 hover:text-red-600 dark:hover:text-red-300 p-1 rounded hover:bg-red-50 dark:hover:bg-red-900/20"
                              title="Revertir ajuste"
                            >🗑️</button>
                          )}
                        </td>
                      )}
                    </tr>
                    {isOpen && (
                      <tr className="border-b border-gray-100 dark:border-slate-700/50 bg-gray-50/60 dark:bg-slate-800/30">
                        <td colSpan={canAdminAccounting ? 7 : 6} className="px-6 py-2">
                          {isLoading ? (
                            <p className="text-gray-400 py-1">Cargando...</p>
                          ) : !lineas || lineas.length === 0 ? (
                            <p className="text-gray-400 py-1">Sin líneas</p>
                          ) : (
                            <table className="w-full text-[11px]">
                              <thead>
                                <tr className="text-gray-400">
                                  <th className="text-left font-medium pr-3 py-0.5 w-20">Código</th>
                                  <th className="text-left font-medium pr-3 py-0.5">Cuenta</th>
                                  <th className="text-right font-medium pr-3 py-0.5 w-24 text-blue-500">Debe</th>
                                  <th className="text-right font-medium py-0.5 w-24 text-orange-500">Haber</th>
                                </tr>
                              </thead>
                              <tbody>
                                {lineas.map(l => (
                                  <tr key={l.id}>
                                    <td className="font-mono text-gray-400 pr-3 py-0.5">{l.cuenta.codigo}</td>
                                    <td className="text-gray-700 dark:text-gray-300 pr-3 py-0.5">{l.cuenta.nombre}</td>
                                    <td className="text-right font-mono text-blue-700 dark:text-blue-300 pr-3 py-0.5">
                                      {l.debe > 0 ? fmtNum(l.debe) : ''}
                                    </td>
                                    <td className="text-right font-mono text-orange-700 dark:text-orange-300 py-0.5">
                                      {l.haber > 0 ? fmtNum(l.haber) : ''}
                                    </td>
                                  </tr>
                                ))}
                              </tbody>
                            </table>
                          )}
                        </td>
                      </tr>
                    )}
                  </React.Fragment>
                )
              })}
              {c.asientos.length === 0 && (
                <tr><td colSpan={canAdminAccounting ? 7 : 6} className="px-4 py-8 text-center text-gray-400 text-xs">Sin asientos para los filtros aplicados.</td></tr>
              )}
            </tbody>
          </table></div>
          </>
        )}
      </div>
    </>
  )
}
