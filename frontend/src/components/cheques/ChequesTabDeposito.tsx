import React from 'react'
import { BancoCuenta, DepositoData, ESTADO_BADGE, ESTADO_LABEL, LiBadge, esRegistrado, fmt, fmtDate } from './shared'

interface Props {
  depositoFechas: string[]
  depositoFecha: string
  depositoData: DepositoData | null
  depositoLoading: boolean
  exportandoDeposito: boolean
  bancoCuentas: BancoCuenta[]
  selectedCheques: Set<number>
  acredMasivoBanco: number | ''
  acredMasivoFecha: string
  acreditandoMasivo: boolean
  onDepositoFechaChange: (v: string) => void
  onExportDeposito: () => void
  onAcredMasivoBanco: (v: number | '') => void
  onAcredMasivoFecha: (v: string) => void
  onAcreditarMasivo: () => void
  onSetSelected: (s: Set<number>) => void
}

export const ChequesTabDeposito: React.FC<Props> = ({
  depositoFechas, depositoFecha, depositoData, depositoLoading, exportandoDeposito, bancoCuentas,
  selectedCheques, acredMasivoBanco, acredMasivoFecha, acreditandoMasivo,
  onDepositoFechaChange, onExportDeposito, onAcredMasivoBanco, onAcredMasivoFecha, onAcreditarMasivo, onSetSelected,
}) => (
  <div className="space-y-4">
    <div className="flex flex-wrap items-end gap-3">
      <div>
        <label className="block text-xs text-gray-400 mb-1">Fecha de depósito</label>
        <select value={depositoFecha} onChange={e => { onDepositoFechaChange(e.target.value); onSetSelected(new Set()) }}
          className="bg-gray-50 dark:bg-white/5 border border-gray-200 dark:border-white/10 rounded-lg px-3 py-1.5 text-sm text-gray-800 dark:text-gray-200 focus:outline-none min-w-[170px]">
          <option value="">Seleccioná una fecha</option>
          {depositoFechas.map(f => <option key={f} value={f}>{fmtDate(f)}</option>)}
        </select>
      </div>
      {depositoFecha && (
        <button onClick={onExportDeposito} disabled={exportandoDeposito}
          className="px-3 py-1.5 bg-green-100 hover:bg-green-200 dark:bg-green-700/30 dark:hover:bg-green-700/50 text-green-700 dark:text-green-400 text-sm rounded-lg transition-colors disabled:opacity-50">
          {exportandoDeposito ? 'Exportando…' : '↓ Excel'}
        </button>
      )}
    </div>

    {/* Acreditación masiva */}
    {depositoData && depositoData.items.some(c => esRegistrado(c.estado)) && (
      <div className="bg-indigo-50 border border-indigo-200 dark:bg-indigo-500/5 dark:border-indigo-500/20 rounded-xl p-3 flex flex-wrap items-end gap-3">
        <div className="flex-1 min-w-[160px]">
          <label className="block text-xs text-gray-400 mb-1">Banco de acreditación</label>
          <select value={acredMasivoBanco} onChange={e => onAcredMasivoBanco(e.target.value ? parseInt(e.target.value) : '')}
            className="w-full bg-gray-50 dark:bg-white/5 border border-gray-200 dark:border-white/10 rounded-lg px-3 py-1.5 text-sm text-gray-800 dark:text-gray-200 focus:outline-none">
            <option value="">Seleccioná banco</option>
            {bancoCuentas.map(b => <option key={b.id} value={b.id}>{b.nombre} ({b.codigo})</option>)}
          </select>
        </div>
        <div>
          <label className="block text-xs text-gray-400 mb-1">Fecha de acreditación</label>
          <input type="date" value={acredMasivoFecha} onChange={e => onAcredMasivoFecha(e.target.value)}
            className="bg-gray-50 dark:bg-white/5 border border-gray-200 dark:border-white/10 rounded-lg px-3 py-1.5 text-sm text-gray-800 dark:text-gray-200 focus:outline-none" />
        </div>
        <button
          onClick={onAcreditarMasivo}
          disabled={acreditandoMasivo || !acredMasivoBanco || selectedCheques.size === 0}
          className="px-4 py-1.5 bg-green-600 hover:bg-green-500 text-white text-sm rounded-lg disabled:opacity-50 transition-colors whitespace-nowrap">
          {acreditandoMasivo ? 'Procesando…' : `✓ Acreditar ${selectedCheques.size > 0 ? `(${selectedCheques.size})` : 'seleccionados'}`}
        </button>
        {selectedCheques.size > 0 && (
          <button onClick={() => onSetSelected(new Set())} className="text-xs text-gray-500 hover:text-gray-700 dark:text-gray-300 px-2">
            Limpiar selección
          </button>
        )}
      </div>
    )}

    {depositoLoading ? (
      <p className="text-sm text-gray-500 text-center py-8">Cargando…</p>
    ) : !depositoData ? (
      <p className="text-sm text-gray-500 text-center py-8">
        {depositoFechas.length === 0 ? 'No hay cheques con fecha de depósito cargada' : 'Seleccioná una fecha para ver los cheques'}
      </p>
    ) : (
      <>
        {/* Resumen cards */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          <div className="bg-white dark:bg-white/3 border border-gray-200 dark:border-white/8 rounded-xl p-3 col-span-2 md:col-span-1">
            <p className="text-xs text-gray-500">Total del día</p>
            <p className="text-lg font-semibold text-gray-900 dark:text-gray-100 mt-1">{fmt(depositoData.resumen.total)}</p>
            <p className="text-xs text-gray-600 mt-0.5">{depositoData.items.length} cheques</p>
          </div>
          {depositoData.resumen.por_local_interior.map(li => (
            <div key={li.tipo} className="bg-white dark:bg-white/3 border border-gray-200 dark:border-white/8 rounded-xl p-3">
              <p className="text-xs text-gray-500">{li.tipo === 'local' ? 'Local (CP < 2000)' : 'Interior (CP ≥ 2000)'}</p>
              <p className={`text-base font-semibold mt-1 ${li.tipo === 'local' ? 'text-blue-600 dark:text-blue-400' : 'text-orange-600 dark:text-orange-400'}`}>{fmt(li.total)}</p>
              <p className="text-xs text-gray-600 mt-0.5">{li.count} cheques</p>
            </div>
          ))}
        </div>

        <div className="rounded-xl overflow-hidden border border-gray-200 dark:border-white/8">
          <div className="overflow-x-auto">
            <table className="w-full text-xs min-w-[680px]">
              <thead>
                <tr className="bg-gray-50 dark:bg-white/4 text-left text-gray-400">
                  <th className="px-2 py-2">
                    <input type="checkbox" className="w-3.5 h-3.5 accent-indigo-500"
                      checked={depositoData.items.filter(c => esRegistrado(c.estado)).length > 0 &&
                        depositoData.items.filter(c => esRegistrado(c.estado)).every(c => selectedCheques.has(c.id))}
                      onChange={e => {
                        const ids = depositoData.items.filter(c => esRegistrado(c.estado)).map(c => c.id)
                        onSetSelected(e.target.checked ? new Set(ids) : new Set())
                      }} />
                  </th>
                  <th className="px-3 py-2 font-medium">Cliente</th>
                  <th className="px-3 py-2 font-medium">Librador</th>
                  <th className="px-3 py-2 font-medium">Portador</th>
                  <th className="px-3 py-2 font-medium">Banco</th>
                  <th className="px-3 py-2 font-medium">N° Cheque</th>
                  <th className="px-3 py-2 font-medium">CP</th>
                  <th className="px-3 py-2 font-medium">L/I</th>
                  <th className="px-3 py-2 font-medium text-right">Monto</th>
                  <th className="px-3 py-2 font-medium">Estado</th>
                </tr>
              </thead>
              <tbody>
                {depositoData.items.map((c, i) => (
                  <tr key={c.id} className={`border-t border-gray-100 dark:border-white/5 hover:bg-gray-50 dark:hover:bg-white/2 ${selectedCheques.has(c.id) ? 'bg-indigo-50 dark:bg-indigo-500/5' : i % 2 === 0 ? '' : 'bg-gray-50/60 dark:bg-white/1'}`}>
                    <td className="px-2 py-2">
                      {esRegistrado(c.estado) ? (
                        <input type="checkbox" className="w-3.5 h-3.5 accent-indigo-500"
                          checked={selectedCheques.has(c.id)}
                          onChange={e => {
                            const s = new Set(selectedCheques)
                            e.target.checked ? s.add(c.id) : s.delete(c.id)
                            onSetSelected(s)
                          }} />
                      ) : <span className="w-3.5 h-3.5 block" />}
                    </td>
                    <td className="px-3 py-2 text-gray-800 dark:text-gray-200">{c.cliente_nombre || '—'}</td>
                    <td className="px-3 py-2 text-gray-700 dark:text-gray-300 max-w-[110px] truncate">{c.librador || c.titular || '—'}</td>
                    <td className="px-3 py-2 text-gray-400">{c.portador_nombre || '—'}</td>
                    <td className="px-3 py-2 text-gray-400">{c.banco_origen || '—'}</td>
                    <td className="px-3 py-2 text-gray-400">{c.numero || '—'}</td>
                    <td className="px-3 py-2 text-gray-400">{c.codigo_postal || '—'}</td>
                    <td className="px-3 py-2"><LiBadge value={c.local_interior} /></td>
                    <td className="px-3 py-2 text-right font-mono text-gray-900 dark:text-gray-100">{fmt(c.monto)}</td>
                    <td className="px-3 py-2">
                      <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${ESTADO_BADGE[c.estado] || ''}`}>
                        {ESTADO_LABEL[c.estado] || c.estado}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
              <tfoot>
                <tr className="border-t border-gray-200 dark:border-white/10 bg-white/4">
                  <td colSpan={8} className="px-3 py-2 text-xs text-gray-400 font-medium">Total</td>
                  <td className="px-3 py-2 text-right font-mono text-gray-900 dark:text-gray-100 font-semibold">{fmt(depositoData.resumen.total)}</td>
                  <td />
                </tr>
              </tfoot>
            </table>
          </div>
        </div>

        {depositoData.resumen.por_cliente.length > 0 && (
          <div className="bg-white dark:bg-white/3 border border-gray-200 dark:border-white/8 rounded-xl p-4">
            <h3 className="text-xs font-semibold text-gray-400 mb-3 uppercase tracking-wider">Resumen por cliente</h3>
            <div className="space-y-1.5">
              {depositoData.resumen.por_cliente.map(r => (
                <div key={r.cliente} className="flex items-center justify-between text-xs">
                  <span className="text-gray-700 dark:text-gray-300">{r.cliente}</span>
                  <div className="flex items-center gap-3">
                    <span className="text-gray-500">{r.count} cheq.</span>
                    <span className="font-mono text-gray-900 dark:text-gray-100 font-medium">{fmt(r.total)}</span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}
      </>
    )}
  </div>
)
