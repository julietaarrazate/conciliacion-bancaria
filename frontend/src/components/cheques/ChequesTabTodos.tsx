import React from 'react'
import { Cheque, ClienteOpt, ESTADO_BADGE, ESTADO_LABEL, LiBadge, esRegistrado, fmt, fmtDate } from './shared'

interface Props {
  cheques: Cheque[]
  clientes: ClienteOpt[]
  loading: boolean
  total: number
  skip: number
  limit: number
  canDelete: boolean
  filtroEstado: string
  filtroCliente: string
  filtroDesde: string
  filtroHasta: string
  onFiltroEstado: (v: string) => void
  onFiltroCliente: (v: string) => void
  onFiltroDesde: (v: string) => void
  onFiltroHasta: (v: string) => void
  onLimpiarFiltros: () => void
  onSkipChange: (fn: (s: number) => number) => void
  onVerFoto: (id: number) => void
  onCompartir: (c: Cheque) => void
  onEdit: (c: Cheque) => void
  onAcreditar: (id: number) => void
  onRechazar: (id: number) => void
  onDelete: (id: number) => void
}

export const ChequesTabTodos: React.FC<Props> = ({
  cheques, clientes, loading, total, skip, limit, canDelete,
  filtroEstado, filtroCliente, filtroDesde, filtroHasta,
  onFiltroEstado, onFiltroCliente, onFiltroDesde, onFiltroHasta, onLimpiarFiltros, onSkipChange,
  onVerFoto, onCompartir, onEdit, onAcreditar, onRechazar, onDelete,
}) => (
  <>
    <div className="flex flex-wrap gap-2">
      <select value={filtroEstado} onChange={e => onFiltroEstado(e.target.value)}
        className="bg-gray-50 dark:bg-white/5 border border-gray-200 dark:border-white/10 rounded-lg px-3 py-1.5 text-sm text-gray-800 dark:text-gray-200 focus:outline-none">
        <option value="">Todos los estados</option>
        <option value="registrado">Registrado</option>
        <option value="depositado">Depositado</option>
        <option value="acreditado">Acreditado</option>
        <option value="rechazado">Rechazado</option>
      </select>
      <select value={filtroCliente} onChange={e => onFiltroCliente(e.target.value)}
        className="bg-gray-50 dark:bg-white/5 border border-gray-200 dark:border-white/10 rounded-lg px-3 py-1.5 text-sm text-gray-800 dark:text-gray-200 focus:outline-none">
        <option value="">Todos los clientes</option>
        {clientes.map(c => <option key={c.id} value={c.id}>{c.nombre}</option>)}
      </select>
      <input type="date" value={filtroDesde} onChange={e => onFiltroDesde(e.target.value)}
        className="bg-gray-50 dark:bg-white/5 border border-gray-200 dark:border-white/10 rounded-lg px-3 py-1.5 text-sm text-gray-800 dark:text-gray-200 focus:outline-none" />
      <input type="date" value={filtroHasta} onChange={e => onFiltroHasta(e.target.value)}
        className="bg-gray-50 dark:bg-white/5 border border-gray-200 dark:border-white/10 rounded-lg px-3 py-1.5 text-sm text-gray-800 dark:text-gray-200 focus:outline-none" />
      {(filtroEstado || filtroCliente || filtroDesde || filtroHasta) && (
        <button onClick={onLimpiarFiltros}
          className="text-xs text-gray-400 hover:text-gray-800 dark:text-gray-200 px-2">Limpiar</button>
      )}
    </div>

    <div className="rounded-xl overflow-hidden border border-gray-200 dark:border-white/8">
      <div className="overflow-x-auto">
        <table className="w-full text-xs min-w-[860px]">
          <thead>
            <tr className="bg-gray-50 dark:bg-white/4 text-left text-gray-400">
              <th className="px-3 py-2 font-medium">F. Depósito</th>
              <th className="px-3 py-2 font-medium">Cliente</th>
              <th className="px-3 py-2 font-medium">Librador</th>
              <th className="px-3 py-2 font-medium">Portador</th>
              <th className="px-3 py-2 font-medium">Banco</th>
              <th className="px-3 py-2 font-medium">N° Cheque</th>
              <th className="px-3 py-2 font-medium">CP</th>
              <th className="px-3 py-2 font-medium">L/I</th>
              <th className="px-3 py-2 font-medium text-right">Monto</th>
              <th className="px-3 py-2 font-medium text-right">Comisión</th>
              <th className="px-3 py-2 font-medium">Estado</th>
              <th className="px-3 py-2 font-medium">Acred.</th>
              <th className="px-3 py-2 font-medium">Acciones</th>
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr><td colSpan={13} className="text-center py-8 text-gray-500">Cargando…</td></tr>
            ) : cheques.length === 0 ? (
              <tr><td colSpan={13} className="text-center py-8 text-gray-500">Sin cheques registrados</td></tr>
            ) : cheques.map((c, i) => (
              <tr key={c.id} className={`border-t border-gray-100 dark:border-white/5 hover:bg-gray-50 dark:hover:bg-white/2 ${i % 2 === 0 ? '' : 'bg-gray-50/60 dark:bg-white/1'}`}>
                <td className="px-3 py-2 text-gray-700 dark:text-gray-300 whitespace-nowrap">{fmtDate(c.fecha_deposito)}</td>
                <td className="px-3 py-2 text-gray-800 dark:text-gray-200">{c.cliente_nombre || <span className="text-gray-500">—</span>}</td>
                <td className="px-3 py-2 text-gray-700 dark:text-gray-300 max-w-[110px] truncate" title={c.librador || c.titular || ''}>{c.librador || c.titular || '—'}</td>
                <td className="px-3 py-2 text-gray-400">{c.portador_nombre || '—'}</td>
                <td className="px-3 py-2 text-gray-400">{c.banco_origen || '—'}</td>
                <td className="px-3 py-2 text-gray-400">{c.numero || '—'}</td>
                <td className="px-3 py-2 text-gray-400">{c.codigo_postal || '—'}</td>
                <td className="px-3 py-2"><LiBadge value={c.local_interior} /></td>
                <td className="px-3 py-2 text-right font-mono text-gray-900 dark:text-gray-100">{fmt(c.monto)}</td>
                <td className="px-3 py-2 text-right font-mono text-gray-400">{(() => { const val = c.comision > 0 ? c.comision : (c.porcentaje_comision && c.monto ? Math.round(c.monto * c.porcentaje_comision) / 100 : 0); return val > 0 ? fmt(val) : '—' })()}</td>
                <td className="px-3 py-2">
                  <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${ESTADO_BADGE[c.estado] || ''}`}>
                    {ESTADO_LABEL[c.estado] || c.estado}
                  </span>
                </td>
                <td className="px-3 py-2 text-gray-400 whitespace-nowrap">{fmtDate(c.fecha_acred)}</td>
                <td className="px-3 py-2">
                  <div className="flex gap-1">
                    {c.tiene_foto && (
                      <button onClick={() => onVerFoto(c.id)}
                        className="px-2 py-0.5 bg-indigo-50 hover:bg-indigo-100 text-indigo-600 dark:bg-indigo-600/20 dark:hover:bg-indigo-600/40 dark:text-indigo-400 rounded text-xs transition-colors"
                        title="Ver foto">📷</button>
                    )}
                    <button onClick={() => onCompartir(c)}
                      className="px-2 py-0.5 bg-green-50 hover:bg-green-100 text-green-700 dark:bg-green-600/20 dark:hover:bg-green-600/40 dark:text-green-400 rounded text-xs transition-colors"
                      title="Compartir">📤</button>
                    {esRegistrado(c.estado) && (
                      <>
                        <button onClick={() => onEdit(c)}
                          className="px-2 py-0.5 bg-gray-50 dark:bg-white/5 hover:bg-gray-200 dark:hover:bg-white/10 text-gray-600 dark:text-gray-300 rounded text-xs transition-colors"
                          title="Editar">✏️</button>
                        <button onClick={() => onAcreditar(c.id)}
                          className="px-2 py-0.5 bg-green-50 hover:bg-green-100 text-green-700 dark:bg-green-600/20 dark:hover:bg-green-600/40 dark:text-green-400 rounded text-xs transition-colors">Acreditar</button>
                        {canDelete && <button onClick={() => onDelete(c.id)}
                          className="px-2 py-0.5 bg-gray-50 dark:bg-white/5 hover:bg-gray-200 dark:hover:bg-white/10 text-gray-400 rounded text-xs transition-colors">✕</button>}
                      </>
                    )}
                    {c.estado === 'acreditado' && (
                      <button onClick={() => onRechazar(c.id)}
                        className="px-2 py-0.5 bg-red-50 hover:bg-red-100 text-red-700 dark:bg-red-600/20 dark:hover:bg-red-600/40 dark:text-red-400 rounded text-xs transition-colors">Rechazar</button>
                    )}
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>

    {total > limit && (
      <div className="flex items-center justify-between text-xs text-gray-400">
        <span>{skip + 1}–{Math.min(skip + limit, total)} de {total}</span>
        <div className="flex gap-2">
          <button disabled={skip === 0} onClick={() => onSkipChange(s => Math.max(0, s - limit))}
            className="px-3 py-1 bg-gray-50 dark:bg-white/5 rounded disabled:opacity-40 hover:bg-gray-200 dark:hover:bg-white/10">← Anterior</button>
          <button disabled={skip + limit >= total} onClick={() => onSkipChange(s => s + limit)}
            className="px-3 py-1 bg-gray-50 dark:bg-white/5 rounded disabled:opacity-40 hover:bg-gray-200 dark:hover:bg-white/10">Siguiente →</button>
        </div>
      </div>
    )}
  </>
)
