import React, { useEffect, useMemo, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { FileUpload } from '@/components/FileUpload'
import { PlanillaPanel } from '@/components/PlanillaPanel'
import { ColumnMapperModal } from '@/components/ColumnMapperModal'
import { DiagnosticoPanel } from '@/components/DiagnosticoPanel'
import { apiClient } from '@/services/api'
import { useOrgStore } from '@/store/org'
import { confirmDialog } from '@/store/confirm'
import { useAuthStore } from '@/store/auth'
import { useThemeStore } from '@/store/theme'
import {
  ConciliacionResultado,
  DeteccionInfo,
  ExtractoListItem,
  PlanillaHistorialItem,
  ResultadoMapeoPlanilla,
  MapeoColumnas
} from '@/types'
import { localIsoDate } from '@/utils/fecha'

// ── AlertasWidget ─────────────────────────────────────────────────────────────
type Alerta = { tipo: string; cantidad: number; label: string; urgencia: string; link: string }
const ALERTA_META: Record<string, { icon: string; color: string; bg: string; border: string }> = {
  cheques_urgentes:        { icon: '⏰', color: '#DC2626', bg: '#FEF2F2', border: '#FECACA' },
  cheques_vencidos:        { icon: '🔴', color: '#DC2626', bg: '#FEF2F2', border: '#FECACA' },
  filas_atrasadas:         { icon: '📋', color: '#D97706', bg: '#FFFBEB', border: '#FDE68A' },
  movimientos_sin_asignar: { icon: '🔍', color: '#2563EB', bg: '#EFF6FF', border: '#BFDBFE' },
  planillas_descuadre:     { icon: '⚖️', color: '#D97706', bg: '#FFFBEB', border: '#FDE68A' },
  filas_ambiguas:          { icon: '🤔', color: '#2563EB', bg: '#EFF6FF', border: '#BFDBFE' },
}
const ALERTA_META_DARK: Record<string, { color: string; bg: string; border: string }> = {
  cheques_urgentes:        { color: '#F87171', bg: 'rgba(239,68,68,.1)',  border: 'rgba(239,68,68,.25)' },
  cheques_vencidos:        { color: '#F87171', bg: 'rgba(239,68,68,.1)',  border: 'rgba(239,68,68,.25)' },
  filas_atrasadas:         { color: '#FCD34D', bg: 'rgba(245,158,11,.1)', border: 'rgba(245,158,11,.25)' },
  movimientos_sin_asignar: { color: '#60A5FA', bg: 'rgba(37,99,235,.1)',  border: 'rgba(37,99,235,.25)' },
  planillas_descuadre:     { color: '#FCD34D', bg: 'rgba(245,158,11,.1)', border: 'rgba(245,158,11,.25)' },
  filas_ambiguas:          { color: '#60A5FA', bg: 'rgba(37,99,235,.1)',  border: 'rgba(37,99,235,.25)' },
}
const AlertasWidget: React.FC<{ orgId: number | null; isDark: boolean }> = ({ orgId, isDark }) => {
  const navigate = useNavigate()
  const [alertas, setAlertas] = useState<Alerta[]>([])
  useEffect(() => {
    apiClient.getAlertas(orgId ?? undefined).then(r => setAlertas(r.alertas)).catch(() => {})
  }, [orgId])
  if (alertas.length === 0) return null
  return (
    <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, marginBottom: 20 }}>
      {alertas.map(a => {
        const m = isDark
          ? (ALERTA_META_DARK[a.tipo] ?? { color: '#71717A', bg: 'rgba(100,100,100,.1)', border: 'rgba(100,100,100,.2)' })
          : (ALERTA_META[a.tipo] ?? { color: '#71717A', bg: '#F4F4F5', border: '#E4E4E7' })
        const icon = (ALERTA_META[a.tipo] ?? { icon: '⚠️' }).icon
        return (
          <button key={a.tipo} onClick={() => navigate(a.link)}
            style={{ display: 'inline-flex', alignItems: 'center', gap: 7, padding: '7px 14px', borderRadius: 10, cursor: 'pointer', background: m.bg, border: `1px solid ${m.border}`, color: m.color, fontWeight: 600, fontSize: 13, transition: 'opacity .15s, transform .1s', whiteSpace: 'nowrap' }}
            onMouseEnter={e => { e.currentTarget.style.opacity = '0.8'; e.currentTarget.style.transform = 'translateY(-1px)' }}
            onMouseLeave={e => { e.currentTarget.style.opacity = '1'; e.currentTarget.style.transform = '' }}
          >
            <span style={{ fontSize: 14 }}>{icon}</span>
            <span style={{ fontSize: 18, fontWeight: 800, lineHeight: 1, fontFamily: 'monospace' }}>{a.cantidad}</span>
            <span style={{ fontSize: 12, fontWeight: 500, opacity: 0.85 }}>{a.label}</span>
            <span style={{ fontSize: 11, opacity: 0.6 }}>→</span>
          </button>
        )
      })}
    </div>
  )
}

// ── OnboardingChecklist ────────────────────────────────────────────────────────
const OnboardingChecklist: React.FC<{
  tieneExtracto: boolean
  tienePlanilla: boolean
  tieneConciliacion: boolean
  orgId: number | null
  onDismiss: () => void
  onUploadPlanilla: () => void
}> = ({ tieneExtracto, tienePlanilla, tieneConciliacion, orgId, onDismiss, onUploadPlanilla }) => {
  const navigate = useNavigate()
  const steps = [
    {
      done: tieneExtracto,
      title: 'Subir el extracto bancario',
      desc: 'Exportá el Excel de tu banco (Macro, BBVA, Santander…) y subilo acá.',
      action: { label: 'Subir extracto', onClick: () => navigate('/extractos-archivo') },
    },
    {
      done: tienePlanilla,
      title: 'Cargar la planilla de un cliente',
      desc: 'Subí la planilla de pagos con nombre del cliente, monto y referencia.',
      action: { label: 'Cargar planilla', onClick: onUploadPlanilla },
    },
    {
      done: tieneConciliacion,
      title: 'Ver tu primera conciliación',
      desc: 'El motor cruza automáticamente y marca cada fila como OK o pendiente.',
      action: null,
    },
  ]
  const done = steps.filter(s => s.done).length
  const allDone = done === steps.length
  if (allDone) return null

  return (
    <div style={{
      marginBottom: 24,
      borderRadius: 14,
      border: '1px solid #E4E4E7',
      background: '#FFFFFF',
      overflow: 'hidden',
    }} className="dark:bg-ml-dark-surface dark:border-ml-dark-border">
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '14px 18px', borderBottom: '1px solid #F0F0F0' }} className="dark:border-ml-dark-border">
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <span style={{ fontSize: 16 }}>🚀</span>
          <div>
            <div style={{ fontWeight: 700, fontSize: 14, color: '#111' }} className="dark:text-white">
              Primeros pasos
            </div>
            <div style={{ fontSize: 11, color: '#71717A', marginTop: 1 }}>
              {done} de {steps.length} completados
            </div>
          </div>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          {/* Progress bar */}
          <div style={{ width: 80, height: 5, borderRadius: 3, background: '#F0F0F0', overflow: 'hidden' }} className="dark:bg-ml-dark-border">
            <div style={{ width: `${(done / steps.length) * 100}%`, height: '100%', background: '#22C55E', borderRadius: 3, transition: 'width 0.4s ease' }} />
          </div>
          <button
            onClick={onDismiss}
            style={{ fontSize: 12, color: '#71717A', background: 'none', border: 'none', cursor: 'pointer', padding: '2px 6px', borderRadius: 6 }}
            title="Ocultar"
          >✕</button>
        </div>
      </div>
      {/* Steps */}
      <div style={{ padding: '8px 0' }}>
        {steps.map((s, i) => (
          <div key={i} style={{
            display: 'flex', alignItems: 'flex-start', gap: 14,
            padding: '12px 18px',
            opacity: s.done ? 0.5 : 1,
            transition: 'opacity 0.3s',
          }}>
            {/* Icon */}
            <div style={{
              width: 28, height: 28, borderRadius: '50%', flexShrink: 0, marginTop: 1,
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              background: s.done ? '#22C55E' : '#F4F4F5',
              border: s.done ? 'none' : '2px solid #E4E4E7',
              transition: 'all 0.3s',
            }} className={s.done ? '' : 'dark:bg-ml-dark-card dark:border-ml-dark-border'}>
              {s.done
                ? <svg width="13" height="13" viewBox="0 0 14 14" fill="none"><path d="M2.5 7.5L5.5 10.5L11.5 4" stroke="white" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/></svg>
                : <span style={{ fontSize: 11, fontWeight: 700, color: '#A1A1AA' }}>{i + 1}</span>
              }
            </div>
            {/* Text */}
            <div style={{ flex: 1, minWidth: 0 }}>
              <div style={{ fontSize: 13, fontWeight: 600, color: s.done ? '#71717A' : '#111', marginBottom: 2 }} className={s.done ? '' : 'dark:text-white'}>
                {s.done && <span style={{ marginRight: 6, color: '#22C55E' }}>✓</span>}{s.title}
              </div>
              {!s.done && (
                <div style={{ fontSize: 12, color: '#71717A', lineHeight: 1.5 }}>{s.desc}</div>
              )}
            </div>
            {/* Action */}
            {!s.done && s.action && (
              <button
                onClick={s.action.onClick}
                style={{
                  flexShrink: 0, fontSize: 12, fontWeight: 600,
                  padding: '6px 14px', borderRadius: 8,
                  background: '#22C55E', color: '#000', border: 'none', cursor: 'pointer',
                  transition: 'background 0.15s',
                }}
                onMouseEnter={e => (e.currentTarget.style.background = '#16A34A')}
                onMouseLeave={e => (e.currentTarget.style.background = '#22C55E')}
              >
                {s.action.label}
              </button>
            )}
          </div>
        ))}
      </div>
    </div>
  )
}

function fmtFecha(s: string) {
  if (!s) return '—'
  try {
    // El backend devuelve ISO sin timezone → parsear como local
    const d = new Date(s.endsWith('Z') ? s : s + 'Z')
    return d.toLocaleString('es-AR', { day: '2-digit', month: '2-digit', year: '2-digit', hour: '2-digit', minute: '2-digit' })
  } catch { return s }
}

// Bancos sugeridos en el desplegable al cargar un extracto. La lista es editable:
// el usuario puede escribir cualquier nombre, y los bancos que use se recuerdan
// (localStorage) y se suman al desplegable la próxima vez.
const BANCOS_SUGERIDOS = [
  'Banco Macro', 'Banco Nación', 'BBVA', 'Santander', 'Galicia', 'HSBC', 'Brubank',
  'Mercado Pago', 'ICBC', 'Bapro', 'Banco Ciudad', 'Credicoop', 'Supervielle',
  'Patagonia', 'Bancor', 'Banco Rioja', 'Banco La Pampa',
]

function leerBancosCustom(): string[] {
  try { return JSON.parse(localStorage.getItem('bancos_personalizados') || '[]') } catch { return [] }
}

export const Dashboard: React.FC = () => {
  const navigate = useNavigate()
  const canDelete = useAuthStore(s => s.hasPermission('delete_records'))
  const { activeOrgId, activeOrgNombre } = useOrgStore()
  const isDark = useThemeStore(s => s.theme === 'dark')
  const [extractos, setExtractos] = useState<ExtractoListItem[]>([])
  const [planillas, setPlanillas] = useState<PlanillaHistorialItem[]>([])
  const [dataLoaded, setDataLoaded] = useState(false)
  const onboardingKey = `onboarding-dismissed-${activeOrgId ?? 'default'}`
  const [onboardingVisible, setOnboardingVisible] = useState(true)
  useEffect(() => {
    try { setOnboardingVisible(localStorage.getItem(onboardingKey) !== '1') } catch {}
  }, [onboardingKey])
  const [extractoId, setExtractoId] = useState<number | null>(null)
  const [_extractoNombre, setExtractoNombre] = useState<string>('')
  const [clienteNombre, setClienteNombre] = useState('')
  const [_loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')
  const [resultado, setResultado] = useState<ConciliacionResultado | null>(null)
  const [deteccionCuadre, setDeteccionCuadre] = useState<DeteccionInfo | null>(null)
  const [panelId, setPanelId] = useState<number | null>(null)
  const [fechaAcred, setFechaAcred] = useState<string>(localIsoDate())
  const [banco, setBanco] = useState('Banco Macro')
  const [bancosCustom, setBancosCustom] = useState<string[]>(leerBancosCustom)

  // Recuerda un banco escrito por el usuario para que aparezca en el desplegable
  // la próxima vez (no pisa los sugeridos ni duplica).
  const recordarBanco = (nombre: string) => {
    const n = nombre.trim()
    if (!n || BANCOS_SUGERIDOS.includes(n)) return
    setBancosCustom(prev => {
      if (prev.includes(n)) return prev
      const next = [...prev, n]
      try { localStorage.setItem('bancos_personalizados', JSON.stringify(next)) } catch { /* storage lleno/bloqueado */ }
      return next
    })
  }
  const [comisionPct, setComisionPct] = useState('')
  const [umCorteDetectado, setUmCorteDetectado] = useState<number | null>(null)
  const [umCorteManual, setUmCorteManual] = useState<string>('')
  const [umFile, setUmFile] = useState<File | null>(null)

  // ── Preview / mapeo de columnas de la planilla individual ────
  const [mapeoPendiente, setMapeoPendiente] = useState<ResultadoMapeoPlanilla | null>(null)
  const [archivoPendiente, setArchivoPendiente] = useState<File | null>(null)

  // ── Carga masiva ──────────────────────────────────────────────
  interface BulkItem {
    id: string; file: File; clienteNombre: string
    status: 'pending' | 'loading' | 'ok' | 'error'
    resultado?: ConciliacionResultado; error?: string
  }
  const [tab, setTab] = useState<'individual' | 'masiva'>('individual')
  const [bulkItems, setBulkItems] = useState<BulkItem[]>([])
  const [bulkRunning, setBulkRunning] = useState(false)
  const [bulkFecha, setBulkFecha] = useState(localIsoDate())
  const [autoRun, setAutoRun] = useState(true)
  const justAddedRef = useRef(false)

  const handleBulkFilesArray = (files: File[]) => {
    setBulkItems(prev => [...prev, ...files.map(f => ({
      id: `${f.name}-${Date.now()}-${Math.random()}`,
      file: f,
      clienteNombre: f.name.replace(/\.[^.]+$/, '').replace(/[_-]/g, ' ').trim(),
      status: 'pending' as const
    }))])
    justAddedRef.current = true
  }

  // Auto-conciliar: cuando se agregan planillas y autoRun está activo
  useEffect(() => {
    if (justAddedRef.current && autoRun && extractoId && !bulkRunning) {
      justAddedRef.current = false
      handleBulkRun()
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [bulkItems])
  const updateBulkItem = (id: string, patch: Partial<BulkItem>) =>
    setBulkItems(prev => prev.map(it => it.id === id ? { ...it, ...patch } : it))
  const handleBulkRun = async () => {
    if (!extractoId || bulkItems.length === 0) return
    setBulkRunning(true)
    for (const item of bulkItems) {
      if (item.status === 'ok') continue
      updateBulkItem(item.id, { status: 'loading', error: undefined })
      try {
        const planilla = await apiClient.uploadPlanilla(item.clienteNombre, extractoId, item.file, activeOrgId)
        const resultado = await apiClient.conciliarPlanilla(planilla.id, bulkFecha)
        updateBulkItem(item.id, { status: 'ok', resultado })
      } catch (err: any) {
        updateBulkItem(item.id, { status: 'error', error: err.response?.data?.detail || 'Error' })
      }
    }
    setBulkRunning(false)
    apiClient.invalidateCache('/analisis')
    apiClient.getHistorialPlanillas({ limit: 5, org_id: activeOrgId }).then(d => setPlanillas(d.items))
  }
  const { bulkPendingCount, bulkOkCount, bulkTotalAcred, bulkTotalFilas } = useMemo(() => ({
    bulkPendingCount: bulkItems.filter(i => i.status === 'pending' || i.status === 'error').length,
    bulkOkCount:      bulkItems.filter(i => i.status === 'ok').length,
    bulkTotalAcred:   bulkItems.reduce((s, i) => s + (i.resultado?.acreditadas || 0), 0),
    bulkTotalFilas:   bulkItems.reduce((s, i) => s + (i.resultado?.filas_procesadas || 0), 0),
  }), [bulkItems])

  useEffect(() => {
    setExtractoId(null)
    setExtractoNombre('')
    setDataLoaded(false)
    Promise.all([
      apiClient.listExtractos(activeOrgId),
      apiClient.getHistorialPlanillas({ limit: 5, org_id: activeOrgId }),
    ]).then(([extData, planData]) => {
      setExtractos(extData.items)
      if (extData.items.length > 0) {
        setExtractoId(extData.items[0].id)
        setExtractoNombre(extData.items[0].nombre_archivo)
      }
      setPlanillas(planData.items)
      setDataLoaded(true)
    })
  }, [activeOrgId])

  const refreshExtractos = async () => {
    const data = await apiClient.listExtractos(activeOrgId)
    setExtractos(data.items)
  }

  const handleDeleteExtracto = async (id: number) => {
    if (!await confirmDialog({
      title: 'Borrar extracto',
      message: 'Los movimientos se eliminan, pero las planillas conciliadas quedan conservadas como historial.',
      confirmLabel: 'Borrar',
      danger: true,
    })) return
    try {
      await apiClient.deleteExtracto(id)
      // SIEMPRE scopear por la org activa: sin org_id, un superadmin recibe los
      // extractos de TODAS las orgs y se filtran empresas ajenas (fuga de tenant).
      const data = await apiClient.listExtractos(activeOrgId)
      setExtractos(data.items)
      if (extractoId === id) {
        setExtractoId(data.items[0]?.id ?? null)
        setExtractoNombre(data.items[0]?.nombre_archivo ?? '')
      }
      setSuccess('Extracto eliminado')
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Error al eliminar')
    }
  }

  const handleLimpiarTodo = async () => {
    const confirmacion = window.prompt('⚠️ PELIGRO: Esto borra TODOS los extractos, movimientos y planillas.\n\nEscribí BORRAR para confirmar:')
    if (confirmacion !== 'BORRAR') return
    try {
      const r = await apiClient.deleteTodosExtractos()
      setExtractos([])
      setExtractoId(null)
      setExtractoNombre('')
      setPlanillas([])
      setResultado(null)
      setSuccess(r.mensaje)
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Error al limpiar')
    }
  }

  const handleUploadExtraco = async (file: File) => {
    setLoading(true)
    setError('')
    setSuccess('')
    try {
      const data = await apiClient.uploadExtraco(file, banco, activeOrgId)
      setExtractoId(data.id)
      setExtractoNombre(data.nombre_archivo)
      setSuccess(`Extracto cargado: ${data.movimientos.length} movimientos`)
      recordarBanco(banco)
      await refreshExtractos()
    } catch (err: any) {
      // Detectar duplicado (409)
      if (err.response?.status === 409) {
        const det = err.response.data?.detail
        const msg = typeof det === 'object' ? det.message : det
        const existId = typeof det === 'object' ? det.extracto_id : null
        setError(msg || 'Extracto duplicado')
        if (existId) { setExtractoId(existId); await refreshExtractos() }
      } else {
        setError(err.response?.data?.detail || 'Error al cargar extracto')
      }
    } finally {
      setLoading(false)
    }
  }

  const handleUploadUM = async (file: File, corteSaldoOverride?: number) => {
    if (!extractoId) {
      setError('Cargá primero un extracto')
      return
    }
    setLoading(true)
    setError('')
    setSuccess('')
    try {
      const r = await apiClient.appendUM(extractoId, file, corteSaldoOverride)
      setUmCorteDetectado(r.corte_saldo_detectado ?? null)
      setUmFile(file)
      apiClient.invalidateCache('/movimientos')
      const metodo = r.corte_metodo === 'manual' ? ' (corte manual)' : r.corte_metodo === 'fallback' ? ' ⚠️ corte por fallback — verificar' : ''
      setSuccess(
        r.agregados > 0
          ? `UM agregado: ${r.agregados} movimientos nuevos · ${r.duplicados} ya existían${metodo}`
          : `UM procesado: no había movimientos nuevos — ${r.duplicados} ya existían${metodo}`
      )
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Error al cargar UM')
    } finally {
      setLoading(false)
    }
  }

  const handleReintentarUMConCorteManual = async () => {
    if (!umFile) return
    const saldo = parseFloat(umCorteManual.replace(/\./g, '').replace(',', '.'))
    if (isNaN(saldo)) { setError('Ingresá un saldo válido para el corte manual'); return }
    await handleUploadUM(umFile, saldo)
    setUmCorteManual('')
  }

  const handleUploadPlanilla = async (file: File, mapeo?: MapeoColumnas & { header_row: number }) => {
    if (!extractoId || !clienteNombre.trim()) {
      setError('Cargá primero un extracto e ingresá el cliente')
      return
    }
    setLoading(true)
    setError('')
    setSuccess('')
    setResultado(null)
    setDeteccionCuadre(null)
    try {
      const planilla = await apiClient.uploadPlanilla(
        clienteNombre,
        extractoId,
        file,
        activeOrgId,
        mapeo
      )
      setDeteccionCuadre(planilla.deteccion ?? null)
      const r = await apiClient.conciliarPlanilla(planilla.id, fechaAcred, false, parseFloat(comisionPct) || 0)
      setResultado(r)
      setSuccess(`Conciliación completa: ${r.acreditadas}/${r.filas_procesadas} acreditadas`)
      apiClient.invalidateCache('/analisis')
      apiClient.getHistorialPlanillas({ limit: 5, org_id: activeOrgId }).then((d) => setPlanillas(d.items))
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Error en la conciliación')
    } finally {
      setLoading(false)
    }
  }

  // Al elegir el archivo: previsualiza el mapeo de columnas. Si el perfil del cliente
  // ya lo conoce o la confianza es alta, sube directo sin fricción; si no, pide confirmación
  // visual (ColumnMapperModal). Si el preview falla, degrada al upload directo de siempre.
  const handleFileSelected = async (file: File) => {
    if (!extractoId || !clienteNombre.trim()) {
      setError('Cargá primero un extracto e ingresá el cliente')
      return
    }
    setError('')
    setSuccess('')
    setLoading(true)
    try {
      const resultado = await apiClient.previewPlanilla(file, undefined, activeOrgId, clienteNombre.trim())
      setLoading(false)
      if (resultado.origen === 'perfil' || resultado.confianza >= 0.8) {
        await handleUploadPlanilla(file, { ...resultado.columnas, header_row: resultado.header_row })
      } else {
        setArchivoPendiente(file)
        setMapeoPendiente(resultado)
      }
    } catch {
      setLoading(false)
      // No se pudo previsualizar (endpoint no disponible, archivo raro, etc.):
      // no bloquea la carga, sube sin mapeo como antes.
      await handleUploadPlanilla(file)
    }
  }

  const handleConfirmarMapeo = async (mapeo: MapeoColumnas & { header_row: number }) => {
    const file = archivoPendiente
    setMapeoPendiente(null)
    setArchivoPendiente(null)
    if (!file) return
    await handleUploadPlanilla(file, mapeo)
  }

  const handleCancelarMapeo = () => {
    setMapeoPendiente(null)
    setArchivoPendiente(null)
  }

  // Stats — usa solo el extracto activo para movimientos (no sumar duplicados)
  const hoyStr = localIsoDate()
  const { totalMovimientos, totalAcreditadas, totalProcesadas: _totalProcesadas, accuracy, montoConciliadoHoy, planillasHoy } = useMemo(() => {
    const extractoActivo = extractos.find(e => e.id === extractoId)
    const totalMovimientos = extractoActivo?.total_movimientos ?? 0
    const totalAcreditadas = planillas.reduce((s, p) => s + p.acreditadas, 0)
    const totalProcesadas = planillas.reduce((s, p) => s + p.total_filas, 0)
    const accuracy = totalProcesadas > 0
      ? Math.round((totalAcreditadas / totalProcesadas) * 100)
      : 0
    const planillasHoy = planillas.filter(p => p.fecha_carga.startsWith(hoyStr))
    const montoConciliadoHoy = planillasHoy.reduce((s, p) => s + (p.monto_conciliado ?? 0), 0)
    return { totalMovimientos, totalAcreditadas, totalProcesadas, accuracy, montoConciliadoHoy, planillasHoy }
  }, [extractos, extractoId, planillas, hoyStr])
  const fmtMonto = (n: number) =>
    n.toLocaleString('es-AR', { style: 'currency', currency: 'ARS', maximumFractionDigits: 0 })

  const tieneConciliacion = planillas.some(p => p.acreditadas > 0)
  const handleDismissOnboarding = () => {
    try { localStorage.setItem(onboardingKey, '1') } catch {}
    setOnboardingVisible(false)
  }
  // Auto-dismiss once data loads if all 3 onboarding steps are already done
  useEffect(() => {
    if (dataLoaded && onboardingVisible && extractos.length > 0 && planillas.length > 0 && tieneConciliacion) {
      handleDismissOnboarding()
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [dataLoaded])

  return (
    <div className="p-4 md:p-6 max-w-7xl mx-auto">
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-ml-text dark:text-white">Conciliar transferencias</h1>
        {activeOrgId ? (
          <p className="text-sm mt-1 text-ml-green dark:text-ml-green font-mono">
            ▸ Viendo: <strong>{activeOrgNombre}</strong>
          </p>
        ) : (
          <p className="text-ml-text-soft dark:text-gray-400 text-sm mt-1">
            Subí el extracto bancario y las planillas de cliente.
          </p>
        )}
      </div>

      <AlertasWidget orgId={activeOrgId} isDark={isDark} />

      {dataLoaded && onboardingVisible && (
        <OnboardingChecklist
          tieneExtracto={extractos.length > 0}
          tienePlanilla={planillas.length > 0}
          tieneConciliacion={tieneConciliacion}
          orgId={activeOrgId}
          onDismiss={handleDismissOnboarding}
          onUploadPlanilla={() => {
            setTab('individual')
            setTimeout(() => document.getElementById('upload-planilla-section')?.scrollIntoView({ behavior: 'smooth', block: 'start' }), 100)
          }}
        />
      )}

      {/* Tabs */}
      <div className="flex gap-1 mb-6 border-b border-gray-200 dark:border-slate-700">
        {([['individual', '📄 Individual'], ['masiva', '📂 Carga masiva']] as const).map(([key, label]) => (
          <button
            key={key}
            onClick={() => setTab(key)}
            className={`px-4 py-2 text-sm font-medium border-b-2 -mb-px transition-colors ${
              tab === key
                ? 'border-ml-blue text-ml-blue dark:border-ml-green dark:text-ml-green'
                : 'border-transparent text-ml-text-soft hover:text-ml-text dark:hover:text-gray-300'
            }`}
          >{label}</button>
        ))}
      </div>

      {/* KPIs */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
        <div className="kpi">
          <p className="kpi-label">Conciliado hoy</p>
          <p className="kpi-value text-ml-green dark:text-ml-green">
            {montoConciliadoHoy > 0 ? fmtMonto(montoConciliadoHoy) : '—'}
          </p>
          {planillasHoy.length > 0 && (
            <p className="text-xs text-ml-text-soft dark:text-gray-500 mt-0.5">
              {planillasHoy.length} planilla{planillasHoy.length !== 1 ? 's' : ''}
            </p>
          )}
        </div>
        <div className="kpi">
          <p className="kpi-label">Acreditadas (últimas 5)</p>
          <p className="kpi-value text-green-600">{totalAcreditadas}</p>
        </div>
        <div className="kpi">
          <p className="kpi-label">Precisión</p>
          <p className="kpi-value text-ml-blue">{accuracy}%</p>
        </div>
        <div className="kpi">
          <p className="kpi-label">Movimientos extracto</p>
          <p className="kpi-value">{totalMovimientos.toLocaleString('es-AR')}</p>
        </div>
      </div>

      {error && (
        <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded-md text-red-700 text-sm dark:bg-red-900/20 dark:border-red-800/50 dark:text-red-400">
          {error}
        </div>
      )}
      {success && (
        <div className="mb-4 p-3 bg-green-50 border border-green-200 rounded-md text-green-700 text-sm dark:bg-green-900/20 dark:border-green-800/50 dark:text-green-400">
          {success}
        </div>
      )}

      {tab === 'individual' && (<>
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        {/* Paso 1: Extracto */}
        <div className="bg-white dark:bg-white/5 border border-gray-100 dark:border-white/10 rounded-xl p-5 shadow-sm">
          <div className="flex items-center gap-3 mb-4">
            <span className="flex items-center justify-center w-7 h-7 rounded-full bg-violet-500/15 text-violet-500 dark:text-violet-400 text-xs font-bold shrink-0">1</span>
            <h3 className="text-sm font-semibold text-gray-800 dark:text-white tracking-tight">
              Extracto bancario
            </h3>
          </div>

          {extractos.length > 0 && (
            <div className="mb-3">
              <div className="flex gap-2">
                <select
                  className="input-field flex-1"
                  value={extractoId ?? ''}
                  onChange={(e) => {
                    const id = Number(e.target.value)
                    setExtractoId(id)
                    setExtractoNombre(extractos.find((x) => x.id === id)?.nombre_archivo || '')
                  }}
                >
                  {extractos.map((e) => (
                    <option key={e.id} value={e.id}>
                      #{e.id} · {e.nombre_archivo} ({e.total_movimientos} movs)
                    </option>
                  ))}
                </select>
                {extractoId && canDelete && (
                  <button
                    onClick={() => handleDeleteExtracto(extractoId)}
                    className="px-2 text-red-500 hover:text-red-700 hover:bg-red-50 dark:hover:bg-red-900/20 rounded-md transition-colors"
                    title="Borrar este extracto"
                  >🗑️</button>
                )}
              </div>
              {extractos.length > 1 && canDelete && (
                <details className="mt-2">
                  <summary className="text-xs text-gray-400 dark:text-zinc-600 cursor-pointer select-none">
                    Opciones avanzadas
                  </summary>
                  <button
                    onClick={handleLimpiarTodo}
                    className="mt-1.5 text-xs text-red-600 dark:text-red-400 hover:underline block"
                  >
                    🗑️ Borrar todo ({extractos.length} extractos)
                  </button>
                </details>
              )}
            </div>
          )}

          <div className="mb-3">
            <label className="label">Banco</label>
            <input
              className="input-field"
              value={banco}
              onChange={e => setBanco(e.target.value)}
              placeholder="Escribí el banco (ej: Banco Comercio)"
            />
            {/* Chips en vez de <datalist> (poco fiable en mobile): tocás uno para
                elegirlo, o escribís el tuyo arriba. Los custom aparecen primero. */}
            <div className="flex flex-wrap gap-1.5 mt-2">
              {[...bancosCustom, ...BANCOS_SUGERIDOS.slice(0, 8)].map(b => (
                <button
                  key={b}
                  type="button"
                  onClick={() => setBanco(b)}
                  className={`px-2.5 py-1 text-xs rounded-full border transition-colors ${
                    banco === b
                      ? 'bg-ml-blue text-white border-ml-blue'
                      : 'border-gray-300 dark:border-slate-600 text-gray-600 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-slate-700'
                  }`}
                >
                  {b}
                </button>
              ))}
            </div>
            <p className="text-xs opacity-60 mt-1">
              Tocá un banco de la lista o escribí el tuyo arriba (ej: Banco Comercio).
              El que escribas queda guardado para la próxima.
            </p>
          </div>

          <FileUpload
            onFileSelected={handleUploadExtraco}
            label="Subir extracto (.xlsx, .xls, .csv)"
          />

          {extractoId && (
            <>
              <button
                onClick={() => navigate(`/movimientos?extracto=${extractoId}`)}
                className="w-full mt-2 flex items-center justify-center gap-2 px-3 py-2 text-sm text-ml-blue border border-ml-blue rounded-md hover:bg-ml-blue/5 dark:hover:bg-ml-blue/10 transition-colors"
              >
                📊 Ver y filtrar movimientos
              </button>
              <button
                onClick={async () => {
                  if (!extractoId) return
                  setError('')
                  try {
                    await apiClient.exportExtractoContador(extractoId)
                  } catch (err: any) {
                    const msg = err.response?.data?.detail || err.message || 'Error al exportar'
                    setError(`Export falló: ${msg}`)
                  }
                }}
                className="w-full mt-2 flex items-center justify-center gap-2 px-3 py-2 text-sm text-green-700 dark:text-green-400 border border-green-600 dark:border-green-700 rounded-md hover:bg-green-50 dark:hover:bg-green-900/20 transition-colors font-medium"
              >
                📤 Exportar para contador (.xlsx)
              </button>
              <div className="mt-3 pt-3 border-t border-gray-100 dark:border-slate-700">
                <p className="text-xs text-ml-text-soft dark:text-gray-400 mb-2">
                  ¿Tenés <abbr title="El Excel diario que manda el banco/contador con los movimientos nuevos" className="no-underline border-b border-dotted border-gray-400 cursor-help">Últimos Movimientos (UM)</abbr> del banco? Sumalos sin duplicar:
                </p>
                <div className="flex gap-2 items-center">
                  <div className="flex-1">
                    <FileUpload onFileSelected={(f) => handleUploadUM(f)} label="+ Agregar UM" />
                  </div>
                  <button
                    onClick={async () => {
                      if (!extractoId) return
                      setLoading(true)
                      setError('')
                      try {
                        const r = await apiClient.deleteUM(extractoId)
                        setUmCorteDetectado(null)
                        setUmFile(null)
                        setSuccess(`UM limpiado: ${r.eliminados} movimientos eliminados. Ahora podés re-subir el UM.`)
                      } catch (err: any) {
                        if (err.response?.status === 409) {
                          const det = err.response.data?.detail
                          const msg = typeof det === 'object' ? det.mensaje : det
                          const total = typeof det === 'object' ? det.total : 0
                          if (await confirmDialog({ title: 'UM ya existe', message: `${msg}\n\n¿Borrar los ${total} movimientos UM?`, confirmLabel: 'Borrar UM', danger: true })) {
                            try {
                              const r = await apiClient.deleteUM(extractoId, true)
                              setUmCorteDetectado(null)
                              setUmFile(null)
                              setSuccess(`UM limpiado: ${r.eliminados} movimientos eliminados.`)
                            } catch (e2: any) {
                              setError(e2.response?.data?.detail || 'Error al limpiar UM')
                            }
                          }
                        } else {
                          setError(err.response?.data?.detail || 'Error al limpiar UM')
                        }
                      } finally {
                        setLoading(false)
                      }
                    }}
                    className="text-xs px-2 py-1.5 text-red-500 border border-red-300 dark:border-red-800 rounded hover:bg-red-50 dark:hover:bg-red-900/20 whitespace-nowrap"
                    title="Borra los Últimos Movimientos agregados, para re-subirlos desde cero"
                  >
                    🗑 Limpiar UM
                  </button>
                </div>
                {umCorteDetectado && (
                  <p className="text-xs text-ml-text-soft dark:text-gray-400 mt-2">
                    Corte detectado en saldo <span className="font-mono font-medium">${umCorteDetectado.toLocaleString('es-AR', { minimumFractionDigits: 2 })}</span>
                  </p>
                )}
                {umFile && (
                  <div className="mt-2 flex gap-2 items-center">
                    <input
                      type="text"
                      value={umCorteManual}
                      onChange={(e) => setUmCorteManual(e.target.value)}
                      placeholder="Saldo del corte manual ej: 99657675.21"
                      className="flex-1 text-xs px-2 py-1.5 rounded border border-gray-200 dark:border-slate-600 bg-white dark:bg-slate-800 text-ml-text dark:text-gray-200 focus:outline-none focus:border-ml-blue"
                    />
                    <button
                      onClick={handleReintentarUMConCorteManual}
                      className="text-xs px-3 py-1.5 bg-ml-blue text-white rounded hover:bg-ml-blue/90 whitespace-nowrap"
                    >
                      Reintentar
                    </button>
                  </div>
                )}
              </div>
            </>
          )}
        </div>

        {/* Paso 2: Cliente + Planilla */}
        <div id="upload-planilla-section" className="bg-white dark:bg-white/5 border border-gray-100 dark:border-white/10 rounded-xl p-5 shadow-sm">
          <div className="flex items-center gap-3 mb-4">
            <span className="flex items-center justify-center w-7 h-7 rounded-full bg-violet-500/15 text-violet-500 dark:text-violet-400 text-xs font-bold shrink-0">2</span>
            <h3 className="text-sm font-semibold text-gray-800 dark:text-white tracking-tight">
              Cliente y planilla
            </h3>
          </div>

          <div className="mb-3">
            <label className="label">Nombre del cliente</label>
            <input
              type="text"
              className="input-field"
              placeholder="Green, Tucu, David, Alojando..."
              value={clienteNombre}
              onChange={(e) => setClienteNombre(e.target.value)}
              disabled={!extractoId}
            />
          </div>

          <div className="mb-3">
            <label className="label">Fecha de acreditación</label>
            <input
              type="date"
              className="input-field font-mono"
              value={fechaAcred}
              onChange={(e) => setFechaAcred(e.target.value)}
              disabled={!extractoId}
            />
            <p className="mt-1 text-xs text-gray-400 dark:text-zinc-600">
              Con esta fecha se registran los movimientos acreditados
            </p>
          </div>

          <div className="mb-3">
            <label className="label">% Comisión de esta planilla <span className="text-gray-400 dark:text-zinc-600 font-normal">(obligatorio si aplica)</span></label>
            <input
              type="number" min="0" max="100" step="0.01"
              className="input-field font-mono"
              value={comisionPct}
              onChange={(e) => setComisionPct(e.target.value)}
              placeholder="0"
              disabled={!extractoId}
            />
            <p className="mt-1 text-xs text-amber-600 dark:text-amber-400">
              Cada planilla tiene su propio %. No se hereda del cliente.
            </p>
          </div>

          <FileUpload
            onFileSelected={handleFileSelected}
            label={!extractoId ? 'Cargá primero un extracto (Paso 1)' : 'Subir planilla (.xlsx, .xls, .csv)'}
          />
          {!clienteNombre.trim() && extractoId && (
            <p className="mt-1.5 text-xs text-amber-600 dark:text-amber-400">
              ⚠ Completá el nombre del cliente antes de subir
            </p>
          )}
        </div>

        {/* Paso 3: Resultado */}
        <div className="bg-white dark:bg-white/5 border border-gray-100 dark:border-white/10 rounded-xl p-5 shadow-sm">
          <div className="flex items-center gap-3 mb-4">
            <span className="flex items-center justify-center w-7 h-7 rounded-full bg-violet-500/15 text-violet-500 dark:text-violet-400 text-xs font-bold shrink-0">3</span>
            <h3 className="text-sm font-semibold text-gray-800 dark:text-white tracking-tight">
              Resultado
            </h3>
          </div>

          {resultado ? (
            <div className="space-y-2">
              {[
                { label: 'Acreditadas', val: resultado.acreditadas, cls: 'bg-green-50 dark:bg-green-900/30', txt: 'text-green-700 dark:text-green-300' },
                { label: 'No encontradas', val: resultado.no_encontradas, cls: 'bg-red-50 dark:bg-red-900/30', txt: 'text-red-700 dark:text-red-300' },
                { label: 'Ya acreditadas', val: resultado.duplicadas, cls: 'bg-amber-50 dark:bg-amber-900/30', txt: 'text-amber-700 dark:text-amber-300' },
                { label: 'Faltan datos', val: resultado.sin_datos, cls: 'bg-blue-50 dark:bg-blue-900/30', txt: 'text-blue-700 dark:text-blue-300' },
              ].map(r => (
                <div key={r.label} className={`flex justify-between items-center px-3 py-2 rounded-lg ${r.cls}`}>
                  <span className={`text-sm font-medium ${r.txt}`}>{r.label}</span>
                  <span className={`text-lg font-bold ${r.txt}`}>{r.val}</span>
                </div>
              ))}
              <div className="pt-2 border-t border-gray-100 dark:border-slate-700 text-xs text-gray-500 dark:text-gray-400 text-center">
                Total: {resultado.filas_procesadas} filas procesadas
              </div>

              <DiagnosticoPanel diagnostico={resultado.diagnostico} />

              {deteccionCuadre?.total_movimientos != null && (
                <div className="pt-2 border-t border-gray-100 dark:border-slate-700 space-y-1.5">
                  <div className="flex justify-between items-center text-xs">
                    <span className="text-gray-500 dark:text-gray-400">Total de la planilla</span>
                    <span className="font-mono font-semibold text-ml-text dark:text-white">
                      {fmtMonto(deteccionCuadre.total_movimientos)}
                    </span>
                  </div>
                  {deteccionCuadre.total_declarado != null && (
                    <div className="flex justify-between items-center text-xs gap-2">
                      <span className="text-gray-500 dark:text-gray-400 shrink-0">Declarado por el cliente</span>
                      <span className="flex items-center gap-1.5 flex-wrap justify-end">
                        <span className="font-mono font-semibold text-ml-text dark:text-white">
                          {fmtMonto(deteccionCuadre.total_declarado)}
                        </span>
                        {deteccionCuadre.total_cuadra === true && (
                          <span className="badge badge-ok">✓ Cuadra</span>
                        )}
                        {deteccionCuadre.total_cuadra === false && (
                          <span className="badge badge-warn">
                            ⚠ Difiere en {fmtMonto(Math.abs(deteccionCuadre.total_declarado - deteccionCuadre.total_movimientos))}
                          </span>
                        )}
                      </span>
                    </div>
                  )}
                </div>
              )}

              <button
                onClick={() => setPanelId(resultado.planilla_id)}
                className="mt-3 w-full px-3 py-2 text-sm font-medium bg-ml-blue text-white rounded-md hover:bg-ml-blue-dark transition-colors flex items-center justify-center gap-2"
                title="Ver, editar estados, corregir errores y descargar"
              >
                ✏️ Revisar y editar estados
              </button>
              <p className="text-[10px] text-gray-400 dark:text-gray-500 text-center mt-1">
                Podés cambiar cualquier estado antes de exportar al contador
              </p>
            </div>
          ) : (
            <div className="text-sm text-ml-text-soft py-8 text-center space-y-1.5">
              <p className="font-medium text-ml-text dark:text-gray-300">Todavía no hay resultado</p>
              <p className="text-xs">1. Elegí el extracto del banco</p>
              <p className="text-xs">2. Escribí el nombre del cliente</p>
              <p className="text-xs">3. Subí su planilla — la conciliación sale sola</p>
            </div>
          )}
        </div>
      </div>

      {/* Conciliaciones recientes */}
      {planillas.length > 0 && (
        <div className="card mt-6 p-0 overflow-hidden">
          <div className="px-5 py-3 border-b border-gray-100 dark:border-slate-700 bg-ml-gray-bg dark:bg-slate-900 flex justify-between items-center">
            <h3 className="text-sm font-semibold text-ml-text dark:text-white">
              Conciliaciones recientes
            </h3>
            <span className="text-xs text-ml-text-soft dark:text-gray-400">
              Hacé clic en una fila para ver el detalle
            </span>
          </div>
          <table className="w-full text-sm">
            <thead className="bg-white dark:bg-slate-800 border-b border-gray-100 dark:border-slate-700">
              <tr>
                <th className="px-4 py-2 text-left text-xs font-semibold text-ml-text-soft uppercase">Cliente</th>
                <th className="px-4 py-2 text-left text-xs font-semibold text-ml-text-soft uppercase">Fecha</th>
                <th className="px-4 py-2 text-center text-xs font-semibold text-ml-text-soft uppercase">Total</th>
                <th className="px-4 py-2 text-center text-xs font-semibold text-green-700 uppercase">OK</th>
                <th className="px-4 py-2 text-center text-xs font-semibold text-red-700 uppercase">Error</th>
                <th className="px-4 py-2 text-left text-xs font-semibold text-ml-text-soft uppercase">%</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100 dark:divide-slate-700">
              {planillas.map((p) => {
                const errores = p.no_encontradas + p.duplicadas + p.sin_datos
                const acc = p.total_filas > 0 ? Math.round((p.acreditadas / p.total_filas) * 100) : 0
                return (
                  <tr
                    key={p.id}
                    onClick={() => setPanelId(p.id)}
                    className="hover:bg-ml-gray-bg dark:hover:bg-slate-700/50 cursor-pointer transition-colors"
                  >
                    <td className="px-4 py-2.5 font-medium text-ml-text dark:text-white">{p.cliente_nombre}</td>
                    <td className="px-4 py-2.5 text-ml-text-soft dark:text-gray-400 whitespace-nowrap">
                      {fmtFecha(p.fecha_carga)}
                    </td>
                    <td className="px-4 py-2.5 text-center dark:text-gray-300">{p.total_filas}</td>
                    <td className="px-4 py-2.5 text-center text-green-600 dark:text-green-400 font-bold">
                      {p.acreditadas}
                    </td>
                    <td className="px-4 py-2.5 text-center text-red-600 dark:text-red-400 font-bold">
                      {errores || '—'}
                    </td>
                    <td className="px-4 py-2.5">
                      <span className={`badge ${acc === 100 ? 'badge-ok' : acc >= 80 ? 'badge-warn' : 'badge-error'}`}>
                        {acc === 100 ? '✓' : `${acc}%`}
                      </span>
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      )}

      {/* Panel deslizante de detalle */}
      <PlanillaPanel
        planillaId={panelId}
        onClose={() => setPanelId(null)}
        onDelete={async (id) => {
          await apiClient.deletePlanilla(id)
          setPanelId(null)
          const d = await apiClient.getHistorialPlanillas({ limit: 5 })
          setPlanillas(d.items)
        }}
      />
      </>)}

      {/* ── Tab: Carga masiva ─────────────────────────────── */}
      {tab === 'masiva' && (
        <div className="space-y-4">
          {/* Extracto selector */}
          <div className="card">
            <label className="label">Extracto bancario</label>
            {extractos.length > 0 ? (
              <select
                className="input-field max-w-sm"
                value={extractoId ?? ''}
                onChange={e => {
                  const id = Number(e.target.value)
                  setExtractoId(id)
                  setExtractoNombre(extractos.find(x => x.id === id)?.nombre_archivo || '')
                }}
              >
                {extractos.map(e => (
                  <option key={e.id} value={e.id}>#{e.id} · {e.nombre_archivo} ({e.total_movimientos} movs)</option>
                ))}
              </select>
            ) : (
              <p className="text-sm text-amber-600 dark:text-amber-400">⚠ Cargá primero un extracto en la pestaña Individual</p>
            )}
          </div>

          {/* Fecha + drop zone */}
          <div className="card">
            <div className="flex flex-wrap gap-4 items-end mb-4">
              <div>
                <label className="label">Fecha de acreditación</label>
                <input type="date" className="input-field font-mono w-auto" value={bulkFecha} onChange={e => setBulkFecha(e.target.value)} />
              </div>
              <p className="text-xs text-gray-400 dark:text-zinc-600 pb-2">Todas las planillas se acreditarán con esta fecha</p>
            </div>
            <div className="flex flex-col gap-2">
              <FileUpload
                multiple
                onFilesSelected={handleBulkFilesArray}
                label="Seleccionar planillas (múltiples)"
              />
              <label className="flex items-center gap-2 text-xs text-gray-500 dark:text-gray-400 cursor-pointer select-none">
                <input
                  type="checkbox"
                  checked={autoRun}
                  onChange={e => setAutoRun(e.target.checked)}
                  className="w-3 h-3 accent-violet-500"
                />
                Auto-conciliar al cargar
              </label>
            </div>
          </div>

          {/* Lista de planillas */}
          {bulkItems.length > 0 && (
            <>
              <div className="card p-0 overflow-hidden">
                <div className="px-4 py-3 bg-ml-gray-bg dark:bg-slate-900 border-b dark:border-slate-700 flex justify-between items-center">
                  <span className="text-sm font-medium dark:text-white">
                    {bulkItems.length} planillas · {bulkOkCount} procesadas
                    {bulkTotalFilas > 0 && ` · ${bulkTotalAcred}/${bulkTotalFilas} acreditadas`}
                  </span>
                  <button onClick={() => setBulkItems([])} className="text-xs text-red-600 dark:text-red-400 hover:underline" disabled={bulkRunning}>
                    Limpiar todo
                  </button>
                </div>
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b dark:border-slate-700">
                      <th className="px-4 py-2 text-left text-xs font-semibold text-ml-text-soft uppercase">Archivo</th>
                      <th className="px-4 py-2 text-left text-xs font-semibold text-ml-text-soft uppercase">Cliente</th>
                      <th className="px-4 py-2 text-center text-xs font-semibold text-ml-text-soft uppercase">Estado</th>
                      <th className="px-4 py-2 text-center text-xs font-semibold text-ml-text-soft uppercase">Resultado</th>
                      <th className="px-4 py-2 w-8"></th>
                    </tr>
                  </thead>
                  <tbody className="divide-y dark:divide-slate-700">
                    {bulkItems.map(item => (
                      <tr key={item.id} className="hover:bg-ml-gray-bg dark:hover:bg-slate-700/50">
                        <td className="px-4 py-2.5 dark:text-gray-300 max-w-[200px] truncate">{item.file.name}</td>
                        <td className="px-4 py-2.5">
                          <input
                            className="input-field !py-1 text-sm"
                            value={item.clienteNombre}
                            onChange={e => updateBulkItem(item.id, { clienteNombre: e.target.value })}
                            disabled={bulkRunning || item.status === 'ok'}
                            placeholder="Nombre cliente..."
                          />
                        </td>
                        <td className="px-4 py-2.5 text-center">
                          {item.status === 'pending' && <span className="badge badge-info">Pendiente</span>}
                          {item.status === 'loading' && <span className="badge badge-warn">⏳ Procesando</span>}
                          {item.status === 'ok' && <span className="badge badge-ok">✓ OK</span>}
                          {item.status === 'error' && <span className="badge badge-error" title={item.error}>Error</span>}
                        </td>
                        <td className="px-4 py-2.5 text-center text-xs text-ml-text-soft dark:text-gray-400">
                          {item.resultado
                            ? <span><span className="text-green-600 font-bold">{item.resultado.acreditadas}</span>/{item.resultado.filas_procesadas}</span>
                            : item.error ? <span className="text-red-500">{item.error.slice(0, 40)}</span>
                            : '—'}
                        </td>
                        <td className="px-4 py-2.5 text-center">
                          <button onClick={() => setBulkItems(prev => prev.filter(i => i.id !== item.id))} disabled={bulkRunning}
                            className="text-ml-text-soft hover:text-red-600 dark:text-gray-500 dark:hover:text-red-400 disabled:opacity-30">✕</button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <div className="flex gap-3">
                <button
                  onClick={handleBulkRun}
                  disabled={bulkRunning || bulkPendingCount === 0 || !extractoId}
                  className="btn-yellow disabled:opacity-50"
                >
                  {bulkRunning ? '⏳ Conciliando...' : `⚡ Conciliar ${bulkPendingCount} planilla${bulkPendingCount !== 1 ? 's' : ''}`}
                </button>
                {bulkOkCount > 0 && (
                  <div className="flex items-center gap-2 text-sm text-green-700 dark:text-green-400 bg-green-50 dark:bg-green-900/20 px-4 py-2 rounded-md">
                    ✓ {bulkOkCount} procesadas · {bulkTotalAcred} acreditadas de {bulkTotalFilas}
                  </div>
                )}
              </div>
            </>
          )}
        </div>
      )}

      {mapeoPendiente && (
        <ColumnMapperModal
          resultado={mapeoPendiente}
          onConfirm={handleConfirmarMapeo}
          onCancel={handleCancelarMapeo}
        />
      )}
    </div>
  )
}
