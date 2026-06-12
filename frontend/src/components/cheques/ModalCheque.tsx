import React from 'react'
import {
  ClienteOpt, ClienteSelector, FormState, LiBadge, PortadorOpt, PortadorSelector,
  computeLI, fmt, inputClass, pctParaCliente, suppressLockForCamera,
} from './shared'

interface Props {
  editId: number | null
  formData: FormState
  formFoto: string | null
  saving: boolean
  msg: string
  clientes: ClienteOpt[]
  portadores: PortadorOpt[]
  fotoInputRef: React.RefObject<HTMLInputElement>
  onClose: () => void
  onChange: (fn: (p: FormState) => FormState) => void
  onSave: () => void
  onAddCliente: (nombre: string) => Promise<void>
  onAddPortador: (nombre: string) => Promise<void>
  onFotoChange: (e: React.ChangeEvent<HTMLInputElement>) => void
  onRemoveFoto: () => void
}

export const ModalCheque: React.FC<Props> = ({
  editId, formData, formFoto, saving, msg, clientes, portadores, fotoInputRef,
  onClose, onChange, onSave, onAddCliente, onAddPortador, onFotoChange, onRemoveFoto,
}) => (
  <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4"
    onClick={e => e.target === e.currentTarget && onClose()}>
    <div className="bg-white dark:bg-[#16161A] border border-gray-200 dark:border-white/10 rounded-xl p-5 w-full max-w-lg space-y-4 max-h-[90vh] overflow-y-auto">
      <div className="flex items-center justify-between">
        <h2 className="text-base font-semibold text-gray-900 dark:text-gray-100">{editId ? 'Editar cheque' : 'Nuevo cheque'}</h2>
        <button onClick={onClose} className="text-gray-500 hover:text-gray-700 dark:text-gray-300 text-xl leading-none">×</button>
      </div>
      {msg && <p className="text-xs text-red-600 dark:text-red-400">{msg}</p>}
      <div className="grid grid-cols-2 gap-3">
        <div className="col-span-2">
          <ClienteSelector
            clientes={clientes}
            value={formData.cliente_id}
            onChangeCliente={(id, cli) => onChange(p => ({
              ...p, cliente_id: id,
              // al elegir cliente, pre-llena el % según local/interior del cheque
              porcentaje_comision: pctParaCliente(cli, p.local_interior || computeLI(p.codigo_postal)),
            }))}
            onAdd={onAddCliente}
          />
        </div>
        <div className="col-span-2">
          <PortadorSelector
            portadores={portadores}
            value={formData.portador_id}
            onChange={id => onChange(p => ({ ...p, portador_id: id }))}
            onAdd={onAddPortador}
          />
        </div>
        <div>
          <label className="block text-xs text-gray-400 mb-1">Librador</label>
          <input type="text" value={formData.librador} onChange={e => onChange(p => ({ ...p, librador: e.target.value }))} className={inputClass} />
        </div>
        <div>
          <label className="block text-xs text-gray-400 mb-1">Banco origen</label>
          <input type="text" value={formData.banco_origen} onChange={e => onChange(p => ({ ...p, banco_origen: e.target.value }))} className={inputClass} />
        </div>
        <div>
          <label className="block text-xs text-gray-400 mb-1">N° de cheque</label>
          <input type="text" value={formData.numero} onChange={e => onChange(p => ({ ...p, numero: e.target.value }))} className={inputClass} />
        </div>
        <div>
          <label className="block text-xs text-gray-400 mb-1">Monto *</label>
          <input type="number" value={formData.monto || ''} onChange={e => onChange(p => ({ ...p, monto: parseFloat(e.target.value) || 0 }))} className={inputClass} />
        </div>
        <div className="col-span-2">
          <label className="block text-xs text-gray-400 mb-1">% Comisión (cuenta 3-1-3-0)</label>
          <div className="flex items-center gap-2">
            <input type="number" step="0.1" min="0" max="100" placeholder="ej: 1.5"
              value={formData.porcentaje_comision ?? ''} className={`${inputClass} flex-1`}
              onChange={e => onChange(p => ({ ...p, porcentaje_comision: e.target.value === '' ? null : parseFloat(e.target.value) }))} />
            {formData.porcentaje_comision != null && formData.monto > 0 && (
              <span className="text-xs text-gray-500 whitespace-nowrap">
                = {fmt(formData.monto * formData.porcentaje_comision / 100)}
              </span>
            )}
          </div>
          {formData.porcentaje_comision != null && (() => {
            const cli = clientes.find(c => c.id === formData.cliente_id) ?? null
            const li = formData.local_interior || computeLI(formData.codigo_postal)
            return pctParaCliente(cli, li) === formData.porcentaje_comision
              ? <p className="text-xs text-gray-500 mt-0.5">↑ del cliente{li ? ` (${li})` : ''} — podés cambiarlo</p> : null
          })()}
        </div>
        <div>
          <label className="block text-xs text-gray-400 mb-1">Código postal</label>
          <input type="text" value={formData.codigo_postal} placeholder="ej: 1425"
            onChange={e => {
              const cp = e.target.value
              onChange(p => {
                const li = computeLI(cp)
                // si hay cliente, re-deriva el % según el nuevo local/interior
                const cli = clientes.find(c => c.id === p.cliente_id) ?? null
                return {
                  ...p, codigo_postal: cp, local_interior: li,
                  porcentaje_comision: cli ? pctParaCliente(cli, li) : p.porcentaje_comision,
                }
              })
            }}
            className={inputClass} />
        </div>
        <div>
          <label className="block text-xs text-gray-400 mb-1">Local / Interior</label>
          <div className="flex items-center gap-2 h-[34px] px-3 bg-gray-50 dark:bg-white/5 border border-gray-200 dark:border-white/10 rounded">
            {formData.local_interior
              ? <LiBadge value={formData.local_interior} />
              : <span className="text-xs text-gray-600">Auto por CP</span>
            }
          </div>
        </div>
        <div>
          <label className="block text-xs text-gray-400 mb-1">Fecha emisión</label>
          <input type="date" value={formData.fecha_emision} onChange={e => onChange(p => ({ ...p, fecha_emision: e.target.value }))} className={inputClass} />
        </div>
        <div>
          <label className="block text-xs text-gray-400 mb-1">Fecha depósito</label>
          <input type="date" value={formData.fecha_deposito} onChange={e => onChange(p => ({ ...p, fecha_deposito: e.target.value }))} className={inputClass} />
        </div>
        <div className="col-span-2">
          <label className="block text-xs text-gray-400 mb-1">Notas</label>
          <textarea rows={2} value={formData.notas}
            onChange={e => onChange(p => ({ ...p, notas: e.target.value }))}
            className="w-full bg-white dark:bg-[#ffffff08] border border-gray-200 dark:border-[#ffffff1a] rounded px-3 py-1.5 text-sm text-gray-800 dark:text-gray-100 focus:outline-none focus:border-indigo-500 resize-none" />
        </div>
        {!editId && <div className="col-span-2">
          <label className="block text-xs text-gray-400 mb-1">Foto del cheque (opcional)</label>
          <div className="flex items-center gap-3">
            <input ref={fotoInputRef} type="file" accept="image/*" capture="environment" className="hidden" onChange={onFotoChange} />
            <button type="button" onClick={() => { suppressLockForCamera(); fotoInputRef.current?.click() }}
              className="px-3 py-1.5 bg-gray-100 dark:bg-white/8 hover:bg-gray-200 dark:hover:bg-white/12 text-gray-700 dark:text-gray-300 text-sm rounded border border-gray-200 dark:border-white/10 transition-colors flex items-center gap-1.5">
              <svg className="w-4 h-4" fill="none" stroke="currentColor" strokeWidth={1.8} viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" d="M6.827 6.175A2.31 2.31 0 015.186 7.23c-.38.054-.757.112-1.134.175C2.999 7.58 2.25 8.507 2.25 9.574V18a2.25 2.25 0 002.25 2.25h15A2.25 2.25 0 0021.75 18V9.574c0-1.067-.75-1.994-1.802-2.169a47.865 47.865 0 00-1.134-.175 2.31 2.31 0 01-1.64-1.055l-.822-1.316a2.192 2.192 0 00-1.736-1.039 48.774 48.774 0 00-5.232 0 2.192 2.192 0 00-1.736 1.039l-.821 1.316z"/><path strokeLinecap="round" strokeLinejoin="round" d="M16.5 12.75a4.5 4.5 0 11-9 0 4.5 4.5 0 019 0z"/></svg>
              Sacar foto / subir imagen
            </button>
            {formFoto && (
              <div className="flex items-center gap-2">
                <img src={formFoto} alt="preview" className="h-10 w-10 object-cover rounded border border-gray-200 dark:border-white/10" />
                <button onClick={onRemoveFoto} className="text-xs text-red-600 hover:text-red-500 dark:text-red-400 dark:hover:text-red-300">✕ quitar</button>
              </div>
            )}
          </div>
        </div>}
      </div>
      <div className="flex justify-end gap-2 pt-2">
        <button onClick={onClose} className="px-4 py-1.5 text-sm text-gray-400 hover:text-gray-800 dark:text-gray-200">Cancelar</button>
        <button onClick={onSave} disabled={saving}
          className="px-4 py-1.5 bg-indigo-600 hover:bg-indigo-500 text-white text-sm rounded-lg disabled:opacity-50 transition-colors">
          {saving ? 'Guardando…' : editId ? 'Guardar cambios' : 'Guardar'}
        </button>
      </div>
    </div>
  </div>
)
