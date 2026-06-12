import React from 'react'
import { BancoCuenta, inputClass } from './shared'

interface Props {
  bancoCuentas: BancoCuenta[]
  acreditarBancoId: number | ''
  acreditarFecha: string
  actioning: boolean
  onBancoChange: (v: number | '') => void
  onFechaChange: (v: string) => void
  onCancel: () => void
  onConfirm: () => void
}

export const ModalAcreditar: React.FC<Props> = ({
  bancoCuentas, acreditarBancoId, acreditarFecha, actioning,
  onBancoChange, onFechaChange, onCancel, onConfirm,
}) => (
  <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4">
    <div className="bg-white dark:bg-[#16161A] border border-gray-200 dark:border-white/10 rounded-xl p-5 w-full max-w-sm space-y-4">
      <h2 className="text-base font-semibold text-gray-900 dark:text-gray-100">Acreditar cheque</h2>
      <p className="text-xs text-gray-500">A1: Banco D / Cheques en cartera H — A2: Cheques depositados D / Cliente H</p>
      <div>
        <label className="block text-xs text-gray-400 mb-1">Banco *</label>
        <select value={acreditarBancoId} onChange={e => onBancoChange(e.target.value ? parseInt(e.target.value) : '')}
          className={inputClass}>
          <option value="">Seleccioná banco</option>
          {bancoCuentas.map(b => <option key={b.id} value={b.id}>{b.nombre} ({b.codigo})</option>)}
        </select>
      </div>
      <div>
        <label className="block text-xs text-gray-400 mb-1">Fecha de acreditación</label>
        <input type="date" value={acreditarFecha} onChange={e => onFechaChange(e.target.value)} className={inputClass} />
        <p className="text-xs text-gray-500 mt-1">Si no se indica, se usa hoy.</p>
      </div>
      <div className="flex justify-end gap-2">
        <button onClick={onCancel} className="px-4 py-1.5 text-sm text-gray-400 hover:text-gray-800 dark:text-gray-200">Cancelar</button>
        <button onClick={onConfirm} disabled={actioning || !acreditarBancoId}
          className="px-4 py-1.5 bg-green-600 hover:bg-green-500 text-white text-sm rounded-lg disabled:opacity-50 transition-colors">
          {actioning ? 'Procesando…' : 'Confirmar'}
        </button>
      </div>
    </div>
  </div>
)
