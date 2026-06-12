import React from 'react'
import type { ContabilidadCtx } from './useContabilidad'

export const ContabilidadClientes: React.FC<{ c: ContabilidadCtx }> = ({ c }) => (
  <div>
    <div className="flex flex-wrap items-start justify-between gap-2 mb-3">
      <p className="text-xs text-gray-500 dark:text-gray-400 flex-1 min-w-[220px]">
        Vinculá cada cliente a su cuenta corriente contable (subcuenta de <span className="font-mono">2-1-2-0</span>).
        Cada cuenta pertenece a un solo cliente. Los sin vincular se resuelven asignando una cuenta existente o creando una nueva.
      </p>
      {c.canAdminAccounting && (
        <div className="flex flex-col sm:flex-row gap-2 shrink-0">
          <button
            onClick={c.recuperarClientesBorrados}
            disabled={c.recuperandoCli || c.creandoFaltantes}
            className="text-xs px-3 py-2 rounded-lg bg-emerald-600 text-white font-medium hover:bg-emerald-700 disabled:opacity-50"
            title="Recrea clientes que están acreditados en el extracto pero ya no existen, con su cuenta contable"
          >
            {c.recuperandoCli ? 'Recuperando…' : '↺ Recuperar clientes borrados'}
          </button>
          <button
            onClick={c.crearCuentasFaltantes}
            disabled={c.creandoFaltantes || c.recuperandoCli}
            className="text-xs px-3 py-2 rounded-lg bg-ml-blue text-white font-medium hover:bg-ml-blue-dark disabled:opacity-50"
            title="Crea y vincula la cuenta contable de todos los clientes que aún no tienen una"
          >
            {c.creandoFaltantes ? 'Creando…' : '+ Crear cuentas faltantes'}
          </button>
        </div>
      )}
    </div>
    {c.loadingCli ? (
      <div className="py-12 text-center text-gray-400">Cargando...</div>
    ) : c.cliCuentas.length === 0 ? (
      <p className="text-center py-8 text-gray-400 text-sm">Sin clientes</p>
    ) : (
      <div className="border border-gray-200 dark:border-slate-700 rounded-xl overflow-hidden">
        <div className="overflow-x-auto"><table className="w-full text-xs min-w-[520px]">
          <thead className="bg-gray-50 dark:bg-slate-800">
            <tr>
              <th className="text-left px-4 py-2 font-medium text-gray-500">Cliente</th>
              <th className="text-left px-4 py-2 font-medium text-gray-500">Cuenta contable</th>
              {c.canAdminAccounting && <th className="text-right px-4 py-2 font-medium text-gray-500">Acciones</th>}
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100 dark:divide-slate-700/50">
            {c.cliCuentas.map(row => {
              const saving = c.savingCli === row.cliente_id
              return (
                <tr key={row.cliente_id} className="hover:bg-gray-50 dark:hover:bg-slate-800/40">
                  <td className="px-4 py-2 font-medium text-ml-text dark:text-gray-200">{row.cliente_nombre}</td>
                  <td className="px-4 py-2">
                    {row.cuenta ? (
                      <span className="inline-flex items-center gap-1.5">
                        <span className="font-mono text-[11px] text-gray-400">{row.cuenta.codigo}</span>
                        <span className="text-amber-600 dark:text-amber-400">{row.cuenta.nombre}</span>
                      </span>
                    ) : (
                      <span className="text-[10px] px-1.5 py-0.5 rounded-full border border-gray-300 dark:border-slate-600 text-gray-400">sin vincular</span>
                    )}
                  </td>
                  {c.canAdminAccounting && (
                    <td className="px-4 py-2">
                      <div className="flex items-center justify-end gap-1.5 flex-wrap">
                        <select
                          value={row.cuenta?.id ?? ''}
                          disabled={saving}
                          onChange={e => c.asignarCuenta(row.cliente_id, e.target.value ? Number(e.target.value) : null)}
                          className="text-[11px] px-1.5 py-1 rounded-md border border-gray-300 dark:border-slate-600 bg-white dark:bg-slate-800 text-gray-700 dark:text-gray-300 max-w-[180px]"
                        >
                          <option value="">— sin vincular —</option>
                          {c.cuentasDisp.map(cu => (
                            <option key={cu.id} value={cu.id}>{cu.codigo} · {cu.nombre}</option>
                          ))}
                        </select>
                        {!row.cuenta && (
                          <button
                            onClick={() => c.crearCuenta(row.cliente_id)}
                            disabled={saving}
                            className="text-[11px] px-2 py-1 rounded-md bg-ml-blue text-white hover:bg-ml-blue-dark disabled:opacity-50"
                          >
                            + Crear cuenta
                          </button>
                        )}
                      </div>
                    </td>
                  )}
                </tr>
              )
            })}
          </tbody>
        </table></div>
      </div>
    )}
  </div>
)
