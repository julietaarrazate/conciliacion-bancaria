import React, { useEffect, useState } from 'react'
import { apiClient } from '@/services/api'
import { useAuthStore } from '@/store/auth'
import { useOrgStore } from '@/store/org'

interface OrgActividad {
  id: number
  nombre: string
  plan: string
  planillas_mes: number
  filas_mes: number
  ok_mes: number
  sin_datos_mes: number
  en_revision_mes: number
  tasa_exito: number | null
  ultima_conciliacion: string | null
  usuarios_activos: number
  clientes_activos: number
  alerta: boolean
}

const fmt = (n: number) =>
  new Intl.NumberFormat('es-AR', { style: 'currency', currency: 'ARS', minimumFractionDigits: 0 }).format(n)

const fmtFecha = (s: string | null) => {
  if (!s) return '—'
  const d = new Date(s + (s.includes('T') ? '' : 'T00:00:00'))
  const dias = Math.floor((Date.now() - d.getTime()) / 86400000)
  if (dias === 0) return 'Hoy'
  if (dias === 1) return 'Ayer'
  if (dias < 7) return `Hace ${dias} días`
  return d.toLocaleDateString('es-AR', { day: '2-digit', month: '2-digit' })
}

export const Actividad: React.FC = () => {
  const { user } = useAuthStore()
  const { setActiveOrg } = useOrgStore()
  const [items, setItems] = useState<OrgActividad[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    if (!user?.is_superadmin) return
    apiClient.client.get('/admin/organizaciones/actividad')
      .then(r => setItems(r.data))
      .catch(() => setItems([]))
      .finally(() => setLoading(false))
  }, [user])

  if (!user?.is_superadmin) {
    return <div className="p-8 text-center text-gray-400">Solo disponible para superadmin.</div>
  }

  const mesActual = new Date().toLocaleString('es-AR', { month: 'long', year: 'numeric' })
  const alertas = items.filter(i => i.alerta).length
  const totalPlanillas = items.reduce((s, i) => s + i.planillas_mes, 0)
  const totalOk = items.reduce((s, i) => s + i.ok_mes, 0)
  const totalFilas = items.reduce((s, i) => s + i.filas_mes, 0)

  return (
    <div className="p-4 md:p-6 max-w-6xl mx-auto">
      {/* Header */}
      <div className="mb-6">
        <h1 className="text-xl font-bold dark:text-white">Panel de actividad</h1>
        <p className="text-sm text-gray-400 dark:text-zinc-500 mt-0.5 capitalize">{mesActual}</p>
      </div>

      {/* KPIs globales */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-6">
        {[
          { label: 'Orgs activas', val: items.length, cls: 'dark:text-white' },
          { label: 'Planillas este mes', val: totalPlanillas, cls: 'text-ml-blue dark:text-blue-400' },
          { label: 'Filas auto-conciliadas', val: totalOk, cls: 'text-green-600 dark:text-green-400' },
          { label: 'Con alertas', val: alertas, cls: alertas > 0 ? 'text-amber-500' : 'text-green-500' },
        ].map(k => (
          <div key={k.label} className="kpi">
            <p className="kpi-label">{k.label}</p>
            <p className={`kpi-value ${k.cls}`}>{k.val}</p>
          </div>
        ))}
      </div>

      {/* Lista de orgs */}
      {loading ? (
        <div className="card p-10 text-center text-gray-400">Cargando actividad...</div>
      ) : items.length === 0 ? (
        <div className="card p-10 text-center text-gray-400">Sin datos de actividad</div>
      ) : (
        <div className="space-y-3">
          {items.map(org => (
            <div key={org.id} className={`card p-0 overflow-hidden transition-all ${org.alerta ? 'ring-1 ring-amber-400 dark:ring-amber-600' : ''}`}>
              <div className="flex items-start gap-4 p-4">
                {/* Indicador alerta */}
                <div className={`w-2 h-2 rounded-full mt-1.5 shrink-0 ${
                  org.alerta ? 'bg-amber-400' : org.planillas_mes > 0 ? 'bg-green-400' : 'bg-gray-300 dark:bg-zinc-700'
                }`} />

                <div className="flex-1 min-w-0">
                  {/* Nombre + plan */}
                  <div className="flex items-center gap-2 flex-wrap">
                    <p className="font-semibold dark:text-white">{org.nombre}</p>
                    <span className={`text-2xs px-1.5 py-0.5 rounded-full font-mono uppercase ${
                      org.plan === 'pro'
                        ? 'bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400'
                        : 'bg-ml-gray dark:bg-ml-dark-card text-gray-500 dark:text-zinc-500'
                    }`}>{org.plan}</span>
                    {org.alerta && (
                      <span className="badge badge-warn text-2xs">⚠ Atención</span>
                    )}
                  </div>

                  {/* Stats del mes */}
                  <div className="grid grid-cols-3 md:grid-cols-6 gap-3 mt-3">
                    <div>
                      <p className="kpi-label">Planillas</p>
                      <p className="text-base font-bold dark:text-white">{org.planillas_mes}</p>
                    </div>
                    <div>
                      <p className="kpi-label">Tasa éxito</p>
                      <p className={`text-base font-bold ${
                        org.tasa_exito === null ? 'text-gray-400' :
                        org.tasa_exito >= 85 ? 'text-green-500' :
                        org.tasa_exito >= 60 ? 'text-amber-500' : 'text-red-500'
                      }`}>
                        {org.tasa_exito !== null ? `${org.tasa_exito}%` : '—'}
                      </p>
                    </div>
                    <div>
                      <p className="kpi-label">Sin datos</p>
                      <p className={`text-base font-bold ${org.sin_datos_mes > 0 ? 'text-amber-500' : 'text-gray-400 dark:text-zinc-600'}`}>
                        {org.sin_datos_mes || '—'}
                      </p>
                    </div>
                    <div>
                      <p className="kpi-label">En revisión</p>
                      <p className={`text-base font-bold ${org.en_revision_mes > 0 ? 'text-red-500' : 'text-gray-400 dark:text-zinc-600'}`}>
                        {org.en_revision_mes || '—'}
                      </p>
                    </div>
                    <div>
                      <p className="kpi-label">Última conc.</p>
                      <p className="text-sm font-medium dark:text-gray-300">{fmtFecha(org.ultima_conciliacion)}</p>
                    </div>
                    <div>
                      <p className="kpi-label">Usuarios</p>
                      <p className="text-base font-bold dark:text-white">{org.usuarios_activos}</p>
                    </div>
                  </div>

                  {/* Alertas específicas */}
                  {org.en_revision_mes > 0 && (
                    <p className="text-xs text-amber-600 dark:text-amber-400 mt-2">
                      ⚠ {org.en_revision_mes} caso{org.en_revision_mes > 1 ? 's' : ''} EN_REVISION pendiente{org.en_revision_mes > 1 ? 's' : ''} — revisar antes de cerrar período
                    </p>
                  )}
                  {org.tasa_exito !== null && org.tasa_exito < 70 && org.planillas_mes > 0 && (
                    <p className="text-xs text-amber-600 dark:text-amber-400 mt-1">
                      ⚠ Tasa de éxito baja — verificar si los clientes tienen CUIT/CBU cargados
                    </p>
                  )}
                </div>

                {/* Botón ver como esta org */}
                <button
                  onClick={() => setActiveOrg(org.id, org.nombre)}
                  className="btn-secondary text-xs py-1.5 shrink-0"
                >
                  Ver datos
                </button>
              </div>
            </div>
          ))}
        </div>
      )}

      <p className="text-center text-xs text-gray-400 dark:text-zinc-600 mt-6">
        Las alertas se activan cuando hay EN_REVISION pendientes o tasa de éxito &lt; 70%
      </p>
    </div>
  )
}
