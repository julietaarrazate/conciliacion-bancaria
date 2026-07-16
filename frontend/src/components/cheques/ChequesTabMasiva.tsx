import React from 'react'
import { ClienteOpt, LiBadge } from './shared'

export interface BulkOcrRow {
  index:          number
  filename:       string
  previewUrl:     string
  numero:         string
  banco_origen:   string
  librador:       string
  monto:          string
  fecha_emision:  string
  fecha_deposito: string
  codigo_postal:  string
  local_interior: string
  cliente_id:     number | null
  porcentaje_comision: string
  notas:          string
  error:          boolean
  error_msg:      string
}

interface Props {
  clientes: ClienteOpt[]
  bulkFiles: File[]
  bulkPreviews: string[]
  bulkRows: BulkOcrRow[]
  bulkProcessing: boolean
  bulkSaving: boolean
  bulkMsg: string
  bulkInputRef: React.RefObject<HTMLInputElement>
  onFileChange: (files: FileList | null) => void
  onRemoveFile: (idx: number) => void
  onProcess: () => void
  onUpdateRow: (idx: number, field: string, value: string | number | null) => void
  onRemoveRow: (idx: number) => void
  onClearRows: () => void
  onSave: () => void
}

export const ChequesTabMasiva: React.FC<Props> = ({
  clientes, bulkFiles, bulkPreviews, bulkRows, bulkProcessing, bulkSaving, bulkMsg, bulkInputRef,
  onFileChange, onRemoveFile, onProcess, onUpdateRow, onRemoveRow, onClearRows, onSave,
}) => (
  <div className="space-y-4">
    {/* Zona de upload */}
    <div
      className="border-2 border-dashed border-gray-200 dark:border-white/10 rounded-xl p-6 text-center cursor-pointer hover:border-indigo-400 dark:hover:border-indigo-500 transition-colors"
      onClick={() => bulkInputRef.current?.click()}
      onDragOver={e => { e.preventDefault(); e.stopPropagation() }}
      onDrop={e => { e.preventDefault(); e.stopPropagation(); onFileChange(e.dataTransfer.files) }}
    >
      <input
        ref={bulkInputRef}
        type="file"
        accept="image/*"
        multiple
        className="hidden"
        onChange={e => onFileChange(e.target.files)}
      />
      <p className="text-sm text-gray-500">
        📷 Arrastrá fotos aquí o <span className="text-indigo-600 dark:text-indigo-400 font-medium">hacé clic para seleccionar</span>
      </p>
      <p className="text-xs text-gray-400 mt-1">Podés poner varios cheques en una misma foto · Máximo 30 imágenes por lote · JPG, PNG, HEIC</p>
    </div>

    {/* Thumbnails de fotos seleccionadas */}
    {bulkFiles.length > 0 && bulkRows.length === 0 && (
      <div>
        <div className="flex items-center justify-between mb-2">
          <p className="text-sm text-gray-700 dark:text-gray-300 font-medium">{bulkFiles.length} foto{bulkFiles.length !== 1 ? 's' : ''} seleccionada{bulkFiles.length !== 1 ? 's' : ''}</p>
          <button
            onClick={onProcess}
            disabled={bulkProcessing}
            className="px-4 py-1.5 bg-indigo-600 hover:bg-indigo-500 text-white text-sm rounded-lg disabled:opacity-50 transition-colors flex items-center gap-2">
            {bulkProcessing ? (
              <><span className="animate-spin inline-block w-3.5 h-3.5 border-2 border-white/30 border-t-white rounded-full" />Procesando OCR…</>
            ) : '🔍 Procesar con OCR'}
          </button>
        </div>
        <div className="flex flex-wrap gap-2">
          {bulkPreviews.map((src, i) => (
            <div key={i} className="relative group">
              <img src={src} alt={bulkFiles[i]?.name} className="h-16 w-16 object-cover rounded-lg border border-gray-200 dark:border-white/10" />
              <button
                onClick={e => { e.stopPropagation(); onRemoveFile(i) }}
                className="absolute -top-1.5 -right-1.5 bg-red-500 text-white rounded-full w-4 h-4 text-xs flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity leading-none">✕</button>
              <p className="text-xs text-gray-400 mt-0.5 w-16 truncate text-center">{bulkFiles[i]?.name}</p>
            </div>
          ))}
        </div>
      </div>
    )}

    {bulkMsg && (
      <div className={`text-sm rounded-lg px-3 py-2 border ${bulkMsg.startsWith('✓') ? 'text-green-700 bg-green-50 border-green-200 dark:text-green-400 dark:bg-green-500/10 dark:border-green-500/20' : 'text-red-700 bg-red-50 border-red-200 dark:text-red-400 dark:bg-red-500/10 dark:border-red-500/20'}`}>
        {bulkMsg}
      </div>
    )}

    {/* Tabla editable de resultados */}
    {bulkRows.length > 0 && (
      <div className="space-y-3">
        <div className="flex items-center justify-between">
          <p className="text-sm text-gray-700 dark:text-gray-300 font-medium">{bulkRows.length} cheque{bulkRows.length !== 1 ? 's' : ''} extraído{bulkRows.length !== 1 ? 's' : ''} — revisá los datos antes de guardar</p>
          <div className="flex gap-2">
            <button
              onClick={onClearRows}
              className="px-3 py-1.5 bg-gray-100 dark:bg-white/8 hover:bg-gray-200 dark:hover:bg-white/12 text-gray-600 dark:text-gray-300 text-sm rounded-lg transition-colors">
              ✕ Limpiar
            </button>
            <button
              onClick={onSave}
              disabled={bulkSaving || bulkRows.filter(r => !r.error && parseFloat(r.monto) > 0).length === 0}
              className="px-4 py-1.5 bg-indigo-600 hover:bg-indigo-500 text-white text-sm rounded-lg disabled:opacity-50 transition-colors">
              {bulkSaving ? 'Guardando…' : `💾 Guardar todos (${bulkRows.filter(r => !r.error && parseFloat(r.monto) > 0).length})`}
            </button>
          </div>
        </div>

        <div className="rounded-xl overflow-hidden border border-gray-200 dark:border-white/8">
          <div className="overflow-x-auto">
            <table className="w-full text-xs min-w-[1100px]">
              <thead>
                <tr className="bg-gray-50 dark:bg-white/4 text-left text-gray-400">
                  <th className="px-2 py-2 font-medium w-10">Foto</th>
                  <th className="px-2 py-2 font-medium">Estado</th>
                  <th className="px-2 py-2 font-medium min-w-[140px]">Cliente *</th>
                  <th className="px-2 py-2 font-medium min-w-[90px]">N° Cheque</th>
                  <th className="px-2 py-2 font-medium min-w-[100px]">Banco</th>
                  <th className="px-2 py-2 font-medium min-w-[120px]">Librador</th>
                  <th className="px-2 py-2 font-medium min-w-[80px]">Monto *</th>
                  <th className="px-2 py-2 font-medium min-w-[110px]">F. Emisión</th>
                  <th className="px-2 py-2 font-medium min-w-[110px]">F. Depósito</th>
                  <th className="px-2 py-2 font-medium min-w-[60px]">CP</th>
                  <th className="px-2 py-2 font-medium min-w-[40px]">L/I</th>
                  <th className="px-2 py-2 font-medium min-w-[55px]">% Com.</th>
                  <th className="px-2 py-2 font-medium w-6"></th>
                </tr>
              </thead>
              <tbody>
                {bulkRows.map((row, i) => {
                  const montoNum = parseFloat(row.monto)
                  const sinCliente = !row.error && !row.cliente_id
                  const montoInvalido = !row.error && (isNaN(montoNum) || montoNum <= 0)
                  const cliObj = clientes.find(c => c.id === row.cliente_id) ?? null
                  const cliSinCuenta = cliObj && !cliObj.cuenta_contable_id
                  const rowError = row.error || montoInvalido || cliSinCuenta
                  return (
                    <tr key={i} className={`border-t border-gray-100 dark:border-white/5 ${rowError ? 'bg-red-50/50 dark:bg-red-500/5' : sinCliente ? 'bg-yellow-50/40 dark:bg-yellow-500/5' : 'hover:bg-gray-50 dark:hover:bg-white/2'}`}>
                      <td className="px-2 py-1.5">
                        {row.previewUrl && (
                          <img src={row.previewUrl} alt="" className="h-9 w-9 object-cover rounded border border-gray-200 dark:border-white/10" />
                        )}
                      </td>
                      <td className="px-2 py-1.5">
                        {row.error ? (
                          <span className="text-red-600 dark:text-red-400 font-medium" title={row.error_msg}>⚠️ OCR</span>
                        ) : cliSinCuenta ? (
                          <span className="text-red-600 dark:text-red-400 font-medium" title="El cliente no tiene cuenta contable">❌ Sin cta.</span>
                        ) : montoInvalido ? (
                          <span className="text-red-600 dark:text-red-400 font-medium">❌ Sin monto</span>
                        ) : sinCliente ? (
                          <span className="text-yellow-600 dark:text-yellow-400 font-medium">⚠️ Sin cliente</span>
                        ) : (
                          <span className="text-green-600 dark:text-green-400 font-medium">✅ Listo</span>
                        )}
                      </td>
                      <td className="px-2 py-1.5">
                        <select
                          value={row.cliente_id ?? ''}
                          onChange={e => onUpdateRow(i, 'cliente_id', e.target.value ? parseInt(e.target.value) : null)}
                          className={`w-full bg-white dark:bg-[#ffffff08] border rounded px-2 py-1 text-xs focus:outline-none ${cliSinCuenta ? 'border-red-400' : 'border-gray-200 dark:border-white/15'} text-gray-800 dark:text-gray-100`}>
                          <option value="">Sin cliente</option>
                          {clientes.map(c => <option key={c.id} value={c.id}>{c.nombre}</option>)}
                        </select>
                      </td>
                      <td className="px-2 py-1.5">
                        <input type="text" value={row.numero}
                          onChange={e => onUpdateRow(i, 'numero', e.target.value)}
                          className="w-full bg-white dark:bg-[#ffffff08] border border-gray-200 dark:border-white/15 rounded px-2 py-1 text-xs text-gray-800 dark:text-gray-100 focus:outline-none" />
                      </td>
                      <td className="px-2 py-1.5">
                        <input type="text" value={row.banco_origen}
                          onChange={e => onUpdateRow(i, 'banco_origen', e.target.value)}
                          className="w-full bg-white dark:bg-[#ffffff08] border border-gray-200 dark:border-white/15 rounded px-2 py-1 text-xs text-gray-800 dark:text-gray-100 focus:outline-none" />
                      </td>
                      <td className="px-2 py-1.5">
                        <input type="text" value={row.librador}
                          onChange={e => onUpdateRow(i, 'librador', e.target.value)}
                          className="w-full bg-white dark:bg-[#ffffff08] border border-gray-200 dark:border-white/15 rounded px-2 py-1 text-xs text-gray-800 dark:text-gray-100 focus:outline-none" />
                      </td>
                      <td className="px-2 py-1.5">
                        <input type="number" value={row.monto}
                          onChange={e => onUpdateRow(i, 'monto', e.target.value)}
                          className={`w-full bg-white dark:bg-[#ffffff08] border rounded px-2 py-1 text-xs focus:outline-none ${montoInvalido ? 'border-red-400' : 'border-gray-200 dark:border-white/15'} text-gray-800 dark:text-gray-100`} />
                      </td>
                      <td className="px-2 py-1.5">
                        <input type="date" value={row.fecha_emision}
                          onChange={e => onUpdateRow(i, 'fecha_emision', e.target.value)}
                          className="w-full bg-white dark:bg-[#ffffff08] border border-gray-200 dark:border-white/15 rounded px-2 py-1 text-xs text-gray-800 dark:text-gray-100 focus:outline-none" />
                      </td>
                      <td className="px-2 py-1.5">
                        <input type="date" value={row.fecha_deposito}
                          onChange={e => onUpdateRow(i, 'fecha_deposito', e.target.value)}
                          className="w-full bg-white dark:bg-[#ffffff08] border border-gray-200 dark:border-white/15 rounded px-2 py-1 text-xs text-gray-800 dark:text-gray-100 focus:outline-none" />
                      </td>
                      <td className="px-2 py-1.5">
                        <input type="text" value={row.codigo_postal} placeholder="ej: 1425"
                          onChange={e => onUpdateRow(i, 'codigo_postal', e.target.value)}
                          className="w-full bg-white dark:bg-[#ffffff08] border border-gray-200 dark:border-white/15 rounded px-2 py-1 text-xs text-gray-800 dark:text-gray-100 focus:outline-none" />
                      </td>
                      <td className="px-2 py-1.5">
                        <LiBadge value={row.local_interior || null} />
                      </td>
                      <td className="px-2 py-1.5">
                        <input type="number" step="0.1" min="0" max="100" value={row.porcentaje_comision} placeholder="0"
                          onChange={e => onUpdateRow(i, 'porcentaje_comision', e.target.value)}
                          className="w-full bg-white dark:bg-[#ffffff08] border border-gray-200 dark:border-white/15 rounded px-2 py-1 text-xs text-gray-800 dark:text-gray-100 focus:outline-none" />
                      </td>
                      <td className="px-2 py-1.5">
                        <button onClick={() => onRemoveRow(i)}
                          className="text-gray-400 hover:text-red-500 dark:hover:text-red-400 transition-colors" title="Quitar fila">✕</button>
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        </div>

        {bulkRows.some(r => r.error) && (
          <p className="text-xs text-red-600 dark:text-red-400">
            ⚠️ Las filas marcadas con "⚠️ OCR" tuvieron error en el reconocimiento. Podés completarlas manualmente o quitarlas con ✕.
          </p>
        )}
        {bulkRows.some(r => !r.error && !r.cliente_id) && (
          <p className="text-xs text-yellow-600 dark:text-yellow-500">
            Asigná un cliente a cada fila antes de guardar (requerido para el asiento contable).
          </p>
        )}
      </div>
    )}
  </div>
)
