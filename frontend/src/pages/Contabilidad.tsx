import React from 'react'
import { useAuthStore } from '@/store/auth'
import { Tab, TAB_PERM } from '@/components/contabilidad/shared'
import { useContabilidad } from '@/components/contabilidad/useContabilidad'
import { ContabilidadPlanCuentas } from '@/components/contabilidad/ContabilidadPlanCuentas'
import { ContabilidadReglas } from '@/components/contabilidad/ContabilidadReglas'
import { ContabilidadLibroDiario } from '@/components/contabilidad/ContabilidadLibroDiario'
import { ContabilidadSumas, ContabilidadBalance } from '@/components/contabilidad/ContabilidadSumasBalance'
import { ContabilidadMayor } from '@/components/contabilidad/ContabilidadMayor'
import { ContabilidadClientes } from '@/components/contabilidad/ContabilidadClientes'
import { ContabilidadCtaCteLista, ContabilidadCtaCteDetalle } from '@/components/contabilidad/ContabilidadCtaCte'
import { RecuperarClientesModal, AjusteManualModal, FixFechasModal } from '@/components/contabilidad/ContabilidadModales'

export const Contabilidad: React.FC<{ modo?: 'full' | 'ctacte' }> = ({ modo = 'full' }) => {
  const c = useContabilidad(modo)
  const { hasPermission } = useAuthStore()

  const FULL_TABS: [Tab, string][] = [
    ['plan',    '📊 Plan de cuentas'],
    ['reglas',  '⚙️ Reglas'],
    ['diario',  `📒 Libro diario${c.totalAsientos > 0 ? ` (${c.totalAsientos})` : ''}`],
    ['sumas',   '🧾 Sumas y saldo'],
    ['balance', '⚖️ Balance'],
    ['mayor',   '📖 Libro mayor'],
    ['clientes', '🔗 Clientes'],
  ]
  const TABS = modo === 'ctacte' ? [] : FULL_TABS.filter(([t]) => hasPermission(TAB_PERM[t]))

  return (
    <div className="p-4 md:p-6 max-w-5xl mx-auto">
      <div className="mb-6">
        <h1 className="text-xl font-bold text-ml-text dark:text-white">{modo === 'ctacte' ? 'Cuentas corrientes' : 'Contabilidad'}</h1>
        <p className="text-xs text-gray-500 dark:text-gray-400 mt-0.5">
          {modo === 'ctacte'
            ? 'Cartera de clientes · saldo, movimientos y estado por cuenta'
            : 'Plan de cuentas · Reglas · Libro diario · Sumas y saldo · Balance · Libro mayor'}
          {modo !== 'ctacte' && !c.canAdminAccounting && (
            <span className="ml-2 text-[10px] px-1.5 py-0.5 rounded-full bg-amber-50 dark:bg-amber-900/20 border border-amber-200 dark:border-amber-800 text-amber-600 dark:text-amber-400">
              solo lectura
            </span>
          )}
        </p>
      </div>

      {TABS.length > 0 && (
      <div className="grid grid-cols-3 gap-2 mb-4">
        {TABS.map(([t, label]) => (
          <button key={t} onClick={() => c.setTab(t)}
            className={`px-2 py-2 rounded-lg text-xs font-medium transition-colors text-center leading-tight ${
              c.tab === t ? 'bg-ml-blue text-white' : 'bg-gray-100 dark:bg-slate-800 text-gray-600 dark:text-gray-400 hover:bg-gray-200 dark:hover:bg-slate-700'
            }`}>
            {label}
          </button>
        ))}
      </div>
      )}

      {c.loading ? (
        <div className="py-16 text-center text-gray-400">Cargando...</div>
      ) : c.tab === 'plan' ? (
        <ContabilidadPlanCuentas c={c} />
      ) : c.tab === 'reglas' ? (
        <ContabilidadReglas c={c} />
      ) : c.tab === 'diario' ? (
        <ContabilidadLibroDiario c={c} />
      ) : c.tab === 'sumas' ? (
        <ContabilidadSumas c={c} />
      ) : c.tab === 'balance' ? (
        <ContabilidadBalance c={c} />
      ) : c.tab === 'mayor' ? (
        <ContabilidadMayor c={c} />
      ) : c.tab === 'clientes' ? (
        <ContabilidadClientes c={c} />
      ) : c.tab === 'ctacte' && c.ccMode === 'list' ? (
        <ContabilidadCtaCteLista c={c} />
      ) : c.tab === 'ctacte' ? (
        <ContabilidadCtaCteDetalle c={c} />
      ) : null}

      <RecuperarClientesModal c={c} />
      <AjusteManualModal c={c} />
      <FixFechasModal c={c} />
    </div>
  )
}
