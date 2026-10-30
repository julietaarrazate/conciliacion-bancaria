import React, { useEffect, useState } from 'react'
import { apiClient, type ControlBanco } from '@/services/api'
import { fmtDate, fmtNum } from './shared'

// Solo para mostrar: los importes viajan como string desde el backend.
const money = (n: number) => `$ ${fmtNum(n)}`

/**
 * Control del banco: ¿el banco en los libros coincide con el extracto?
 * y cuánta plata del banco todavía no se explicó (cuentas transitorias).
 * Solo para quien puede ver Contabilidad (el endpoint exige view_accounting).
 */
export const ControlBancoCard: React.FC<{ orgId?: number }> = ({ orgId }) => {
  const [data, setData] = useState<ControlBanco | null>(null)

  useEffect(() => {
    let cancelado = false
    apiClient.getControlBanco(orgId)
      .then(r => { if (!cancelado) setData(r) })
      .catch(() => { if (!cancelado) setData(null) })
    return () => { cancelado = true }
  }, [orgId])

  if (!data) return null

  const dif = data.diferencia_libro_vs_extracto !== null ? Number(data.diferencia_libro_vs_extracto) : null
  const coincide = dif !== null && Math.abs(dif) <= 0.01
  // Si la diferencia es la suma de los huecos entre extractos, no es un error contable:
  // faltan movimientos sin cargar (ej. un mes entero sin extracto).
  const huecos = data.huecos ?? []
  const totalHuecos = huecos.reduce((s, h) => s + Number(h.monto_faltante), 0)
  const explicadaPorHuecos = dif !== null && !coincide && huecos.length > 0 && Math.abs(totalHuecos - dif) <= 0.01
  // Saldo = debe − haber: "cobros a imputar" es acreedora (negativo = hay plata sin imputar).
  const cobros = -Number(data.saldos.cobros_a_imputar.saldo)
  const pagos = Number(data.saldos.pagos_a_imputar.saldo)
  const sinAsiento = data.movimientos_extracto_sin_asiento

  return (
    <div className="mb-4 rounded-xl border border-gray-200 dark:border-white/10 bg-white dark:bg-white/5 px-4 py-3 text-xs" data-testid="control-banco">
      <div className="flex flex-wrap items-center gap-x-3 gap-y-1 mb-2">
        <span className="font-semibold text-gray-900 dark:text-gray-100">Control del banco</span>
        {dif === null ? (
          <span className="text-gray-500 dark:text-gray-400">Todavía no hay un extracto con saldo para comparar.</span>
        ) : coincide ? (
          <span className="font-medium text-green-600 dark:text-green-400">✓ El banco en libros coincide con el extracto</span>
        ) : explicadaPorHuecos ? (
          <span className="font-medium text-amber-600 dark:text-amber-400">
            Lo cargado está bien registrado, pero faltan movimientos del banco sin subir
          </span>
        ) : (
          <span className="font-medium text-red-600 dark:text-red-400">
            El banco en libros no coincide con el extracto: diferencia de {money(dif)}
          </span>
        )}
      </div>
      {explicadaPorHuecos && (
        <div className="mb-3 rounded-lg bg-amber-50 dark:bg-amber-900/20 px-3 py-2 text-amber-800 dark:text-amber-300" data-testid="control-banco-huecos">
          <ul className="space-y-1">
            {huecos.map(h => (
              <li key={`${h.desde}-${h.hasta}`}>
                {h.desde === h.hasta ? `El ${fmtDate(h.desde)}` : `Entre el ${fmtDate(h.desde)} y el ${fmtDate(h.hasta)}`}
                {' '}el saldo del banco pasa de {money(Number(h.saldo_antes))} a {money(Number(h.saldo_despues))}:
                {' '}faltan movimientos por <span className="font-semibold">{money(Number(h.monto_faltante))}</span>.
              </li>
            ))}
          </ul>
          <p className="mt-1">Subí el extracto (o los últimos movimientos) de esas fechas y el control va a cerrar.</p>
          {data.saldo_real_banco !== null && data.fecha_saldo_real_banco && (
            <p className="mt-1">Saldo real del banco al {fmtDate(data.fecha_saldo_real_banco)}: <span className="font-semibold">{money(Number(data.saldo_real_banco))}</span>.</p>
          )}
        </div>
      )}
      <div className="grid gap-3 sm:grid-cols-2">
        <div>
          <div className="text-gray-500 dark:text-gray-400">Cobros a imputar</div>
          <div className="font-mono text-sm font-semibold text-gray-900 dark:text-gray-100">{money(cobros)}</div>
          <p className="text-gray-500 dark:text-gray-400">Plata que entró al banco y todavía no se concilió con un cliente.</p>
        </div>
        <div>
          <div className="text-gray-500 dark:text-gray-400">Pagos a imputar</div>
          <div className="font-mono text-sm font-semibold text-gray-900 dark:text-gray-100">{money(pagos)}</div>
          <p className="text-gray-500 dark:text-gray-400">
            {pagos < 0
              ? 'Pagos cargados que el banco todavía no debitó.'
              : 'Plata que salió del banco y todavía no tiene un pago cargado que la explique.'}
          </p>
        </div>
      </div>
      {sinAsiento > 0 && (
        <p className="mt-2 text-amber-600 dark:text-amber-400">
          {sinAsiento} {sinAsiento === 1 ? 'movimiento del extracto todavía no está registrado' : 'movimientos del extracto todavía no están registrados'} en contabilidad.
        </p>
      )}
    </div>
  )
}
