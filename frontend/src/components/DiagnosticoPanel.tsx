import React from 'react'
import { DiagnosticoConciliacion } from '@/types'
import { fmtFechaCorta } from '@/utils/fecha'

interface DiagnosticoPanelProps {
  diagnostico: DiagnosticoConciliacion | null | undefined
}

/**
 * Explica por qué una conciliación dejó filas sin conciliar, cuando la causa
 * es estructural (no un bug): el banco no informa identidad, el monto no está
 * en este extracto, o las fechas de planilla/extracto no se superponen.
 * No se muestra si el diagnóstico viene null o si todo está OK.
 */
export const DiagnosticoPanel: React.FC<DiagnosticoPanelProps> = ({ diagnostico }) => {
  if (!diagnostico) return null

  const { banco_trae_identidad, cobertura_montos, periodo_planilla, periodo_extracto, solapan_fechas } = diagnostico
  const faltanMontos = cobertura_montos.total - cobertura_montos.en_extracto
  const coberturaParcial = cobertura_montos.total > 0 && faltanMontos > 0

  const nada = banco_trae_identidad !== false && !coberturaParcial && solapan_fechas
  if (nada) return null

  return (
    <div className="pt-2 border-t border-gray-100 dark:border-slate-700 space-y-2" data-testid="diagnostico-panel">
      {banco_trae_identidad === false && (
        <div className="badge badge-info items-start !inline-flex w-full whitespace-normal text-left leading-snug py-1.5">
          <span>ℹ Este banco no incluye el nombre ni el CUIT en el extracto → la conciliación es solo por monto.</span>
        </div>
      )}

      {cobertura_montos.total > 0 && (
        <div className="text-xs text-gray-500 dark:text-gray-400">
          {cobertura_montos.en_extracto} de {cobertura_montos.total} montos de la planilla aparecen en el extracto.
          {coberturaParcial && (
            <span className="block mt-1 text-amber-600 dark:text-amber-400">
              Los otros {faltanMontos} no aparecen en este extracto — ¿es el extracto correcto o falta cargar otro período?
            </span>
          )}
        </div>
      )}

      {!solapan_fechas && (
        <div className="badge badge-warn items-start !inline-flex w-full whitespace-normal text-left leading-snug py-1.5">
          <span>
            ⚠ Las fechas de la planilla ({fmtFechaCorta(periodo_planilla.desde)} – {fmtFechaCorta(periodo_planilla.hasta)}) no coinciden
            con el período del extracto ({fmtFechaCorta(periodo_extracto.desde)} – {fmtFechaCorta(periodo_extracto.hasta)}).
          </span>
        </div>
      )}
    </div>
  )
}
