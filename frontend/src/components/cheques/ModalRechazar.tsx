import React from 'react'
import { RechazarData, inputClass } from './shared'

interface Props {
  rechazarData: RechazarData
  actioning: boolean
  onChange: (fn: (p: RechazarData) => RechazarData) => void
  onCancel: () => void
  onConfirm: () => void
}

export const ModalRechazar: React.FC<Props> = ({ rechazarData, actioning, onChange, onCancel, onConfirm }) => (
  <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4">
    <div className="bg-white dark:bg-[#16161A] border border-gray-200 dark:border-white/10 rounded-xl p-5 w-full max-w-sm space-y-4">
      <h2 className="text-base font-semibold text-gray-900 dark:text-gray-100">Registrar rechazo</h2>
      <p className="text-xs text-gray-500">A1: Cliente D / Banco H — A2: Cliente D / Gastos rechazos H — A3: Gastos rechazos D / Banco H</p>
      <div>
        <label className="block text-xs text-gray-400 mb-1">Fecha de rechazo</label>
        <input type="date" value={rechazarData.fecha_rechazo}
          onChange={e => onChange(p => ({ ...p, fecha_rechazo: e.target.value }))}
          className={inputClass} />
        <p className="text-xs text-gray-500 mt-1">Si no se indica, se usa hoy.</p>
      </div>
      <div>
        <label className="block text-xs text-gray-400 mb-1">Gastos bancarios del rechazo</label>
        <input type="number" min="0" step="0.01" placeholder="0.00"
          value={rechazarData.gastos_bancarios}
          onChange={e => onChange(p => ({ ...p, gastos_bancarios: e.target.value }))}
          className={inputClass} />
        <p className="text-xs text-gray-500 mt-1">Dejar en 0 si el banco no cobró gastos.</p>
      </div>
      <div className="flex items-center gap-3">
        <input type="checkbox" id="fisico-check" checked={rechazarData.fisico}
          onChange={e => onChange(p => ({ ...p, fisico: e.target.checked }))}
          className="w-4 h-4 rounded accent-indigo-500" />
        <label htmlFor="fisico-check" className="text-sm text-gray-700 dark:text-gray-300">El cheque físico fue devuelto</label>
      </div>
      {rechazarData.fisico && (
        <div>
          <label className="block text-xs text-gray-400 mb-1">Fecha de devolución (opcional)</label>
          <input type="date" value={rechazarData.fecha_devolucion}
            onChange={e => onChange(p => ({ ...p, fecha_devolucion: e.target.value }))}
            className={inputClass} />
        </div>
      )}
      <div className="flex justify-end gap-2">
        <button onClick={onCancel} className="px-4 py-1.5 text-sm text-gray-400 hover:text-gray-800 dark:text-gray-200">Cancelar</button>
        <button onClick={onConfirm} disabled={actioning}
          className="px-4 py-1.5 bg-red-600 hover:bg-red-500 text-white text-sm rounded-lg disabled:opacity-50 transition-colors">
          {actioning ? 'Procesando…' : 'Registrar rechazo'}
        </button>
      </div>
    </div>
  </div>
)
