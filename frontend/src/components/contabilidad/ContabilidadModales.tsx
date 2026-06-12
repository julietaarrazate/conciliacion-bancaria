import React from 'react'
import type { ContabilidadCtx } from './useContabilidad'

export const RecuperarClientesModal: React.FC<{ c: ContabilidadCtx }> = ({ c }) => {
  if (!c.recModalOpen) return null
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4" onClick={() => !c.recGuardando && c.setRecModalOpen(false)}>
      <div className="bg-white dark:bg-ml-dark-surface rounded-xl shadow-xl w-full max-w-md max-h-[80vh] flex flex-col" onClick={e => e.stopPropagation()}>
        <div className="p-4 border-b border-gray-200 dark:border-ml-dark-border">
          <h3 className="text-sm font-semibold text-ml-text dark:text-white">Recuperar clientes del extracto</h3>
          <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
            Tildá solo los clientes reales que querés recrear. Los demás (nombres sueltos del extracto) dejalos sin marcar.
          </p>
        </div>
        <div className="p-2 overflow-y-auto flex-1">
          <div className="flex items-center justify-between px-2 py-1 mb-1">
            <button
              onClick={() => c.setRecSeleccion(new Set(c.recCandidatos))}
              className="text-xs text-ml-blue dark:text-ml-green hover:underline"
            >Marcar todos</button>
            <button
              onClick={() => c.setRecSeleccion(new Set())}
              className="text-xs text-gray-500 hover:underline"
            >Limpiar</button>
          </div>
          {c.recCandidatos.map(nombre => (
            <label key={nombre} className="flex items-center gap-2 px-2 py-1.5 rounded hover:bg-gray-50 dark:hover:bg-white/5 cursor-pointer">
              <input
                type="checkbox"
                checked={c.recSeleccion.has(nombre)}
                onChange={() => c.toggleRecSel(nombre)}
                className="rounded"
              />
              <span className="text-sm text-ml-text dark:text-zinc-200">{nombre}</span>
            </label>
          ))}
        </div>
        <div className="p-4 border-t border-gray-200 dark:border-ml-dark-border flex items-center justify-between gap-2">
          <span className="text-xs text-gray-500">{c.recSeleccion.size} seleccionado(s)</span>
          <div className="flex gap-2">
            <button
              onClick={() => c.setRecModalOpen(false)}
              disabled={c.recGuardando}
              className="text-xs px-3 py-2 rounded-lg border border-gray-300 dark:border-ml-dark-border text-gray-600 dark:text-zinc-300 disabled:opacity-50"
            >Cancelar</button>
            <button
              onClick={c.confirmarRecuperarClientes}
              disabled={c.recGuardando || c.recSeleccion.size === 0}
              className="text-xs px-3 py-2 rounded-lg bg-emerald-600 text-white font-medium hover:bg-emerald-700 disabled:opacity-50"
            >{c.recGuardando ? 'Recuperando…' : `Recuperar ${c.recSeleccion.size || ''}`}</button>
          </div>
        </div>
      </div>
    </div>
  )
}

export const AjusteManualModal: React.FC<{ c: ContabilidadCtx }> = ({ c }) => {
  if (!c.ajusteModalOpen) return null
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4" onClick={() => !c.ajusteGuardando && c.setAjusteModalOpen(false)}>
      <div className="bg-white dark:bg-ml-dark-surface rounded-xl shadow-xl w-full max-w-lg" onClick={e => e.stopPropagation()}>
        <div className="p-4 border-b border-gray-200 dark:border-ml-dark-border">
          <h3 className="text-sm font-semibold text-ml-text dark:text-white">✏️ Ajuste manual del Libro Diario</h3>
          <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">Solo cuentas hoja. El asiento es reversible con 🗑️ en la tabla.</p>
        </div>
        <div className="p-4 flex flex-col gap-4">
          <div>
            <label className="block text-xs font-medium text-blue-600 dark:text-blue-400 mb-1">Cuenta Debe *</label>
            <input type="text" placeholder="Buscar cuenta…" value={c.ajusteDebeBusq} onChange={e => c.setAjusteDebeBusq(e.target.value)}
              className="border border-gray-200 dark:border-slate-600 rounded px-2 py-1.5 text-xs bg-white dark:bg-slate-700 text-gray-800 dark:text-gray-200 w-full mb-1" />
            <div className="max-h-36 overflow-y-auto border border-gray-100 dark:border-slate-700 rounded">
              {c.cuentasHoja.filter(cu => !c.ajusteDebeBusq || `${cu.codigo} ${cu.nombre}`.toLowerCase().includes(c.ajusteDebeBusq.toLowerCase())).map(cu => (
                <button key={cu.id} onClick={() => { c.setAjusteDebeId(cu.id); c.setAjusteDebeBusq(`${cu.codigo} ${cu.nombre}`) }}
                  className={`w-full text-left px-2 py-1 text-xs hover:bg-gray-50 dark:hover:bg-slate-700 ${c.ajusteDebeId === cu.id ? 'bg-blue-50 dark:bg-blue-900/20 text-blue-700 dark:text-blue-300' : 'text-gray-700 dark:text-gray-300'}`}>
                  <span className="font-mono text-gray-400 mr-1">{cu.codigo}</span>{cu.nombre}
                </button>
              ))}
            </div>
          </div>
          <div>
            <label className="block text-xs font-medium text-orange-600 dark:text-orange-400 mb-1">Cuenta Haber *</label>
            <input type="text" placeholder="Buscar cuenta…" value={c.ajusteHaberBusq} onChange={e => c.setAjusteHaberBusq(e.target.value)}
              className="border border-gray-200 dark:border-slate-600 rounded px-2 py-1.5 text-xs bg-white dark:bg-slate-700 text-gray-800 dark:text-gray-200 w-full mb-1" />
            <div className="max-h-36 overflow-y-auto border border-gray-100 dark:border-slate-700 rounded">
              {c.cuentasHoja.filter(cu => !c.ajusteHaberBusq || `${cu.codigo} ${cu.nombre}`.toLowerCase().includes(c.ajusteHaberBusq.toLowerCase())).map(cu => (
                <button key={cu.id} onClick={() => { c.setAjusteHaberId(cu.id); c.setAjusteHaberBusq(`${cu.codigo} ${cu.nombre}`) }}
                  className={`w-full text-left px-2 py-1 text-xs hover:bg-gray-50 dark:hover:bg-slate-700 ${c.ajusteHaberId === cu.id ? 'bg-orange-50 dark:bg-orange-900/20 text-orange-700 dark:text-orange-300' : 'text-gray-700 dark:text-gray-300'}`}>
                  <span className="font-mono text-gray-400 mr-1">{cu.codigo}</span>{cu.nombre}
                </button>
              ))}
            </div>
          </div>
          <div className="flex gap-3">
            <div className="flex-1">
              <label className="block text-xs font-medium text-gray-600 dark:text-gray-400 mb-1">Monto *</label>
              <input type="number" min="0.01" step="0.01" placeholder="0.00" value={c.ajusteMonto} onChange={e => c.setAjusteMonto(e.target.value)}
                className="border border-gray-200 dark:border-slate-600 rounded px-2 py-1.5 text-xs bg-white dark:bg-slate-700 text-gray-800 dark:text-gray-200 w-full" />
            </div>
            <div className="flex-1">
              <label className="block text-xs font-medium text-gray-600 dark:text-gray-400 mb-1">Fecha *</label>
              <input type="date" value={c.ajusteFecha} onChange={e => c.setAjusteFecha(e.target.value)}
                className="border border-gray-200 dark:border-slate-600 rounded px-2 py-1.5 text-xs bg-white dark:bg-slate-700 text-gray-800 dark:text-gray-200 w-full" />
            </div>
          </div>
          <div>
            <label className="block text-xs font-medium text-gray-600 dark:text-gray-400 mb-1">Descripción</label>
            <input type="text" placeholder="Descripción del ajuste…" value={c.ajusteDesc} onChange={e => c.setAjusteDesc(e.target.value)}
              className="border border-gray-200 dark:border-slate-600 rounded px-2 py-1.5 text-xs bg-white dark:bg-slate-700 text-gray-800 dark:text-gray-200 w-full" />
          </div>
          {c.ajusteError && <p className="text-xs text-red-500">{c.ajusteError}</p>}
        </div>
        <div className="p-4 border-t border-gray-200 dark:border-ml-dark-border flex justify-end gap-2">
          <button onClick={() => c.setAjusteModalOpen(false)} disabled={c.ajusteGuardando}
            className="text-xs px-3 py-2 rounded-lg border border-gray-300 dark:border-ml-dark-border text-gray-600 dark:text-zinc-300 disabled:opacity-50">
            Cancelar
          </button>
          <button onClick={c.submitAjusteManual} disabled={c.ajusteGuardando || !c.ajusteDebeId || !c.ajusteHaberId || !c.ajusteMonto}
            className="text-xs px-4 py-2 rounded-lg bg-ml-blue text-white font-medium hover:bg-ml-blue-dark disabled:opacity-50">
            {c.ajusteGuardando ? 'Guardando…' : 'Registrar asiento'}
          </button>
        </div>
      </div>
    </div>
  )
}

export const FixFechasModal: React.FC<{ c: ContabilidadCtx }> = ({ c }) => {
  if (!c.fixFechasOpen) return null
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
      <div className="bg-white dark:bg-ml-dark-surface rounded-2xl shadow-xl w-full max-w-md">
        <div className="p-4 border-b border-gray-200 dark:border-ml-dark-border flex items-center justify-between">
          <h3 className="font-semibold text-gray-900 dark:text-white text-sm">🕐 Corrección de fechas en Libro Diario</h3>
          <button onClick={() => c.setFixFechasOpen(false)} className="text-gray-400 hover:text-gray-600 dark:hover:text-gray-200">✕</button>
        </div>
        <div className="p-4 space-y-3">
          <p className="text-xs text-gray-500 dark:text-zinc-400">
            Corrige egresos o asientos cuya fecha quedó 1 día adelantada o atrasada por diferencia UTC/ART.
          </p>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs text-gray-500 mb-1">Desde</label>
              <input type="date" value={c.fixDesde} onChange={e => { c.setFixDesde(e.target.value); c.setFixPreview(null) }}
                className="input-field w-full text-sm" />
            </div>
            <div>
              <label className="block text-xs text-gray-500 mb-1">Hasta</label>
              <input type="date" value={c.fixHasta} onChange={e => { c.setFixHasta(e.target.value); c.setFixPreview(null) }}
                className="input-field w-full text-sm" />
            </div>
          </div>
          <div>
            <label className="block text-xs text-gray-500 mb-1">Dirección</label>
            <select value={c.fixDir} onChange={e => { c.setFixDir(e.target.value as any); c.setFixPreview(null) }}
              className="input-field w-full text-sm">
              <option value="adelantar">Adelantar +1 día (muestran 1 día antes de lo correcto)</option>
              <option value="atrasar">Atrasar −1 día (muestran 1 día después de lo correcto)</option>
            </select>
          </div>
          <label className="flex items-center gap-2 text-xs text-gray-600 dark:text-zinc-400 cursor-pointer">
            <input type="checkbox" checked={c.fixSoloEgresos} onChange={e => { c.setFixSoloEgresos(e.target.checked); c.setFixPreview(null) }} className="rounded" />
            Solo egresos (no tocar asientos de cheques, UM, etc.)
          </label>

          {c.fixPreview && (
            <div className="bg-orange-50 dark:bg-orange-900/20 border border-orange-200 dark:border-orange-700 rounded-lg p-3 text-xs space-y-1">
              <p className="font-semibold text-orange-800 dark:text-orange-300">
                Afectados: {c.fixPreview.asientos_afectados} asientos + {c.fixPreview.egresos_afectados} egresos
              </p>
              {[...c.fixPreview.detalle_asientos, ...c.fixPreview.detalle_egresos].slice(0, 5).map((a: any, i) => (
                <p key={i} className="text-orange-700 dark:text-orange-400 truncate">
                  #{a.id} · {a.fecha_actual} → {a.fecha_nueva} · {a.descripcion}
                </p>
              ))}
              {(c.fixPreview.asientos_afectados + c.fixPreview.egresos_afectados) > 5 && (
                <p className="text-orange-600 dark:text-orange-500">…y más</p>
              )}
            </div>
          )}

          {c.fixMsg && (
            <p className={`text-xs rounded-lg px-3 py-2 ${c.fixMsg.startsWith('✓') ? 'bg-green-50 dark:bg-green-900/20 text-green-700 dark:text-green-400' : 'bg-red-50 dark:bg-red-900/20 text-red-700 dark:text-red-400'}`}>
              {c.fixMsg}
            </p>
          )}
        </div>
        <div className="p-4 border-t border-gray-200 dark:border-ml-dark-border flex flex-wrap justify-end gap-2">
          <button onClick={() => c.setFixFechasOpen(false)} className="text-xs px-3 py-2 rounded-lg border border-gray-300 dark:border-ml-dark-border text-gray-600 dark:text-zinc-300">
            Cerrar
          </button>
          <button onClick={c.fixFechasDryRun} disabled={c.fixLoading || !c.fixDesde || !c.fixHasta}
            className="text-xs px-3 py-2 rounded-lg border border-orange-300 dark:border-orange-700 text-orange-700 dark:text-orange-300 hover:bg-orange-50 dark:hover:bg-orange-900/20 disabled:opacity-50">
            {c.fixLoading && !c.fixPreview ? 'Buscando…' : '🔍 Vista previa'}
          </button>
          {c.fixPreview && (c.fixPreview.asientos_afectados + c.fixPreview.egresos_afectados) > 0 && (
            <button onClick={c.fixFechasEjecutar} disabled={c.fixLoading}
              className="text-xs px-4 py-2 rounded-lg bg-orange-600 text-white font-medium hover:bg-orange-700 disabled:opacity-50">
              {c.fixLoading ? 'Corrigiendo…' : `✓ Corregir ${c.fixPreview.asientos_afectados + c.fixPreview.egresos_afectados} registros`}
            </button>
          )}
        </div>
      </div>
    </div>
  )
}
