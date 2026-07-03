import React, { useMemo, useState } from 'react'
import { MapeoColumnas, ResultadoMapeoPlanilla } from '@/types'

interface ColumnMapperModalProps {
  resultado: ResultadoMapeoPlanilla
  onConfirm: (mapeo: MapeoColumnas & { header_row: number }) => void
  onCancel: () => void
}

type CampoMapeo = keyof MapeoColumnas

const CAMPOS: { key: CampoMapeo; label: string }[] = [
  { key: 'monto', label: 'Monto' },
  { key: 'cuit', label: 'CUIT' },
  { key: 'titular', label: 'Titular' },
  { key: 'referencia', label: 'Referencia' },
  { key: 'fecha', label: 'Fecha' },
]

const IGNORAR = '__ignorar__'

const ORIGEN_META: Record<ResultadoMapeoPlanilla['origen'], { label: string; badge: string }> = {
  perfil: { label: 'Detectado por perfil guardado', badge: 'badge-ok' },
  heuristica: { label: 'Detección automática', badge: 'badge-info' },
  ia: { label: 'Detección con IA', badge: 'badge-info' },
  manual: { label: 'Mapeo manual', badge: 'badge-neutral' },
}

function confianzaLabel(confianza: number): string {
  if (confianza >= 0.8) return 'alta'
  if (confianza >= 0.5) return 'media'
  return 'baja'
}

export const ColumnMapperModal: React.FC<ColumnMapperModalProps> = ({ resultado, onConfirm, onCancel }) => {
  // Estado local: por cada índice de columna (1-based), qué campo tiene asignado (o null/ignorar)
  const [asignacion, setAsignacion] = useState<Record<number, CampoMapeo | null>>(() => {
    const inicial: Record<number, CampoMapeo | null> = {}
    for (const col of resultado.columnas_disponibles) inicial[col.idx] = null
    for (const campo of CAMPOS) {
      const idx = resultado.columnas[campo.key]
      if (idx != null) inicial[idx] = campo.key
    }
    return inicial
  })

  const handleChange = (idx: number, valor: string) => {
    setAsignacion(prev => {
      const next = { ...prev }
      const campoElegido = valor === IGNORAR ? null : (valor as CampoMapeo)
      // Un mismo campo no puede estar asignado a dos columnas: si ya estaba en otra, la libera
      if (campoElegido) {
        for (const key of Object.keys(next)) {
          const k = Number(key)
          if (next[k] === campoElegido && k !== idx) next[k] = null
        }
      }
      next[idx] = campoElegido
      return next
    })
  }

  const mapeoActual: MapeoColumnas = useMemo(() => {
    const m: MapeoColumnas = { monto: null, cuit: null, titular: null, fecha: null, referencia: null }
    for (const [idxStr, campo] of Object.entries(asignacion)) {
      if (campo) m[campo] = Number(idxStr)
    }
    return m
  }, [asignacion])

  const esValido = mapeoActual.monto != null && (mapeoActual.cuit != null || mapeoActual.titular != null)

  const origenMeta = ORIGEN_META[resultado.origen] ?? ORIGEN_META.manual

  const handleConfirmar = () => {
    if (!esValido) return
    onConfirm({ ...mapeoActual, header_row: resultado.header_row })
  }

  return (
    <div className="fixed inset-0 z-[150] flex items-center justify-center p-4">
      <div className="absolute inset-0 bg-black/50 backdrop-blur-sm" onClick={onCancel} />
      <div className="relative bg-white dark:bg-ml-dark-surface rounded-2xl shadow-xl border border-gray-200 dark:border-ml-dark-border p-5 md:p-6 w-full max-w-4xl max-h-[90vh] overflow-y-auto">
        <div className="flex items-start justify-between gap-3 mb-1">
          <h3 className="text-base font-semibold text-ml-text dark:text-white">
            Confirmá el mapeo de columnas
          </h3>
          <span className={origenMeta.badge}>{origenMeta.label}</span>
        </div>
        <p className="text-xs text-ml-text-soft dark:text-zinc-400 mb-4">
          Confianza: <span className="font-semibold">{Math.round(resultado.confianza * 100)}%</span>
          {' '}({confianzaLabel(resultado.confianza)})
        </p>

        <div className="mb-4 text-sm text-ml-text-soft dark:text-zinc-400">
          Se detectaron <span className="font-semibold text-ml-text dark:text-white">{resultado.filas_totales}</span> filas de datos.
          {resultado.filas_descartadas > 0 && (
            <span className="ml-1 text-amber-600 dark:text-amber-400">
              {resultado.filas_descartadas} fila{resultado.filas_descartadas === 1 ? '' : 's'} descartada{resultado.filas_descartadas === 1 ? '' : 's'} (vacías o inválidas).
            </span>
          )}
        </div>

        <div className="overflow-x-auto rounded-lg border border-gray-100 dark:border-white/10">
          <table className="min-w-full text-xs md:text-sm">
            <thead>
              <tr>
                {resultado.columnas_disponibles.map(col => (
                  <th key={col.idx} className="px-2 py-2 bg-gray-50 dark:bg-white/5 border-b border-gray-100 dark:border-white/10 align-top">
                    <select
                      className="input-field !py-1 !text-xs mb-1 w-full min-w-[110px]"
                      value={asignacion[col.idx] ?? IGNORAR}
                      onChange={(e) => handleChange(col.idx, e.target.value)}
                      aria-label={`Usar como (columna ${col.header})`}
                    >
                      <option value={IGNORAR}>(Ignorar)</option>
                      {CAMPOS.map(c => (
                        <option key={c.key} value={c.key}>{c.label}</option>
                      ))}
                    </select>
                    <div className="font-semibold text-ml-text dark:text-white truncate max-w-[160px]" title={col.header}>
                      {col.header || `Columna ${col.idx}`}
                    </div>
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {resultado.preview.map(fila => (
                <tr key={fila.fila} className="border-b border-gray-50 dark:border-white/5 last:border-0">
                  {resultado.columnas_disponibles.map((col, i) => (
                    <td key={col.idx} className="px-2 py-1.5 text-ml-text-soft dark:text-zinc-400 whitespace-nowrap max-w-[160px] truncate">
                      {fila.valores[i] ?? ''}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <div className="flex items-center justify-between gap-3 mt-5">
          <div>
            {!esValido && (
              <p className="text-xs text-amber-600 dark:text-amber-400">
                ⚠ Mapeá al menos Monto y (CUIT o Titular) para poder confirmar.
              </p>
            )}
          </div>
          <div className="flex gap-3 shrink-0">
            <button onClick={onCancel} className="btn-secondary">
              Cancelar
            </button>
            <button onClick={handleConfirmar} disabled={!esValido} className="btn-primary">
              Confirmar mapeo
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
