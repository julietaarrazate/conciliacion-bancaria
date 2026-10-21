import React, { useState } from 'react'
import { apiClient } from '@/services/api'
import { useAuthStore } from '@/store/auth'
import { confirmDialog } from '@/store/confirm'
import { hoyIso } from '@/utils/fecha'
import { manejaVariasOrgs } from '@/utils/orgs'
import type {
  AccionMasiva, ComparacionMisComprobantesArchivo, ImportacionMisComprobantesArchivo, ResultadoMasivo,
} from '@/types'

const ACCIONES: { valor: AccionMasiva; nombre: string; semestral?: boolean }[] = [
  { valor: 'iva_liquidacion', nombre: 'Liquidación de IVA' },
  { valor: 'iva_proyeccion', nombre: 'Proyección de IVA' },
  { valor: 'iibb_proyeccion', nombre: 'Proyección de Ingresos Brutos' },
  { valor: 'monotributo_control', nombre: 'Control semestral de Monotributo', semestral: true },
  { valor: 'sueldos_liquidacion', nombre: 'Liquidación de sueldos' },
]

const ESTILO: Record<ResultadoMasivo['resultado'], { label: string; cls: string }> = {
  calculado: { label: 'Calculado', cls: 'bg-green-100 text-green-800 dark:bg-green-900/40 dark:text-green-300' },
  ya_presentado: { label: 'Ya presentado', cls: 'bg-blue-100 text-blue-800 dark:bg-blue-900/40 dark:text-blue-300' },
  omitido: { label: 'Omitido', cls: 'bg-gray-100 text-gray-600 dark:bg-white/10 dark:text-gray-300' },
  error: { label: 'Error', cls: 'bg-red-100 text-red-800 dark:bg-red-900/40 dark:text-red-300' },
}

const inputClass = 'w-full px-2 py-1.5 rounded-lg border border-gray-300 dark:border-white/15 bg-white dark:bg-black/30 text-sm text-gray-900 dark:text-gray-100'
const btnPrimary = 'px-4 py-2 rounded-lg bg-ml-blue text-white text-sm font-medium disabled:opacity-50'
const card = 'rounded-xl border border-gray-200 dark:border-white/10 bg-white dark:bg-white/5 p-4 mb-6'
const th = 'text-left font-medium px-3 py-2'

function fmtARS(n: number) {
  return new Intl.NumberFormat('es-AR', { style: 'currency', currency: 'ARS', minimumFractionDigits: 2 }).format(n)
}
function semestres(): string[] {
  const anio = Number(hoyIso().slice(0, 4))
  const out: string[] = []
  for (let y = anio + 1; y >= anio - 2; y--) out.push(`${y}-S2`, `${y}-S1`)
  return out
}
function resumenTexto(r: ResultadoMasivo): string {
  const s = r.resumen || {}
  if (typeof s.saldo_a_pagar === 'number') return `A pagar ${fmtARS(s.saldo_a_pagar)}`
  if (typeof s.saldo === 'number') return `Saldo ${fmtARS(s.saldo)}`
  if (typeof s.impuesto_total === 'number') return `Impuesto ${fmtARS(s.impuesto_total)}`
  if (typeof s.total_bruto === 'number') return `Bruto ${fmtARS(s.total_bruto)}`
  if (s.categoria_sugerida) return `Categoría sugerida ${s.categoria_sugerida}${s.excede ? ' · excede' : ''}`
  return ''
}

const CalcularParaTodas: React.FC = () => {
  const [accion, setAccion] = useState<AccionMasiva>('iva_liquidacion')
  const semestral = ACCIONES.find(a => a.valor === accion)?.semestral
  const [mes, setMes] = useState(hoyIso().slice(0, 7))
  const [semestre, setSemestre] = useState(semestres()[2])
  const [corriendo, setCorriendo] = useState(false)
  const [resultados, setResultados] = useState<ResultadoMasivo[] | null>(null)
  const [error, setError] = useState('')
  const periodo = semestral ? semestre : mes

  const correr = async () => {
    setCorriendo(true)
    setError('')
    setResultados(null)
    try {
      setResultados((await apiClient.calcularMasivo(accion, periodo)).resultados)
    } catch (err: any) {
      setError(err?.response?.data?.detail || 'No se pudo correr el proceso.')
    } finally {
      setCorriendo(false)
    }
  }

  const cuenta = (r: ResultadoMasivo['resultado']) => resultados?.filter(x => x.resultado === r).length || 0

  return (
    <section className={card}>
      <h2 className="text-sm font-semibold text-gray-900 dark:text-gray-100 mb-1">Calcular para todas las organizaciones</h2>
      <p className="text-xs text-gray-500 dark:text-gray-400 mb-3">
        Corre el cálculo en cada organización que ves y que tiene el módulo activo. Lo ya presentado no se toca, y lo cargado a
        mano (como las retenciones de IVA) se conserva.
      </p>
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 items-end">
        <div>
          <label htmlFor="pm-accion" className="block text-xs text-gray-600 dark:text-gray-400 mb-1">Acción</label>
          <select id="pm-accion" className={inputClass} value={accion} onChange={e => setAccion(e.target.value as AccionMasiva)}>
            {ACCIONES.map(a => <option key={a.valor} value={a.valor}>{a.nombre}</option>)}
          </select>
        </div>
        <div>
          <label htmlFor="pm-periodo" className="block text-xs text-gray-600 dark:text-gray-400 mb-1">Período</label>
          {semestral
            ? <select id="pm-periodo" className={inputClass} value={semestre} onChange={e => setSemestre(e.target.value)}>
                {semestres().map(s => <option key={s} value={s}>{s.replace('-S', ' · semestre ')}</option>)}
              </select>
            : <input id="pm-periodo" type="month" className={inputClass} value={mes} onChange={e => setMes(e.target.value)} />}
        </div>
        <button className={btnPrimary} onClick={correr} disabled={corriendo || !periodo}>
          {corriendo ? 'Calculando…' : 'Calcular para todas'}
        </button>
      </div>
      {error && <p className="mt-3 text-sm text-red-600 dark:text-red-400">{error}</p>}
      {resultados && (
        <>
          <p className="mt-4 mb-2 text-xs text-gray-600 dark:text-gray-300">
            {cuenta('calculado')} calculada{cuenta('calculado') === 1 ? '' : 's'} · {cuenta('ya_presentado')} ya presentada
            {cuenta('ya_presentado') === 1 ? '' : 's'} · {cuenta('omitido')} omitida{cuenta('omitido') === 1 ? '' : 's'} ·{' '}
            {cuenta('error')} con error
          </p>
          <div className="overflow-x-auto rounded-lg border border-gray-100 dark:border-white/10">
            <table className="w-full text-sm">
              <thead className="bg-gray-50 dark:bg-white/5 text-xs text-gray-500 dark:text-gray-400">
                <tr><th className={th}>Organización</th><th className={th}>Resultado</th><th className={th}>Detalle</th></tr>
              </thead>
              <tbody className="divide-y divide-gray-100 dark:divide-white/10">
                {resultados.map(r => (
                  <tr key={r.organizacion_id}>
                    <td className="px-3 py-2 text-gray-900 dark:text-gray-100">{r.nombre}</td>
                    <td className="px-3 py-2">
                      <span className={`pill rounded-full text-[10px] px-2 py-0.5 ${ESTILO[r.resultado].cls}`}>{ESTILO[r.resultado].label}</span>
                    </td>
                    <td className="px-3 py-2 text-xs text-gray-600 dark:text-gray-300">{r.detalle || resumenTexto(r)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </section>
  )
}

const MisComprobantesVarios: React.FC = () => {
  const [direccion, setDireccion] = useState<'emitido' | 'recibido'>('recibido')
  const [periodo, setPeriodo] = useState(hoyIso().slice(0, 7))
  const [archivos, setArchivos] = useState<File[]>([])
  const [comparacion, setComparacion] = useState<ComparacionMisComprobantesArchivo[] | null>(null)
  const [importados, setImportados] = useState<ImportacionMisComprobantesArchivo[] | null>(null)
  const [deshechos, setDeshechos] = useState<Set<string>>(new Set())
  const [ocupado, setOcupado] = useState(false)
  const [error, setError] = useState('')

  const comparar = async (files: File[]) => {
    setArchivos(files)
    setComparacion(null)
    setImportados(null)
    setError('')
    if (!files.length) return
    setOcupado(true)
    try {
      setComparacion((await apiClient.compararMisComprobantesVarios(files, direccion, periodo)).archivos)
    } catch (err: any) {
      setError(err?.response?.data?.detail || 'No se pudieron leer los archivos.')
    } finally {
      setOcupado(false)
    }
  }

  const conFaltantes = comparacion?.filter(c => c.organizacion_id && c.faltantes > 0) || []

  const importar = async () => {
    setOcupado(true)
    setError('')
    try {
      setImportados((await apiClient.importarMisComprobantesVarios(archivos, direccion, periodo)).archivos)
      setComparacion(null)
    } catch (err: any) {
      setError(err?.response?.data?.detail || 'No se pudo importar.')
    } finally {
      setOcupado(false)
    }
  }

  const deshacer = async (a: ImportacionMisComprobantesArchivo) => {
    if (!a.lote || !a.organizacion_id) return
    if (!await confirmDialog({ title: 'Deshacer importación', message: `¿Borrar lo importado de ${a.nombre}?`, confirmLabel: 'Deshacer', danger: true })) return
    try {
      await apiClient.deshacerImportacionIva(a.lote, a.organizacion_id)
      setDeshechos(prev => new Set(prev).add(a.lote!))
    } catch (err: any) {
      setError(err?.response?.data?.detail || 'No se pudo deshacer.')
    }
  }

  return (
    <section className={card}>
      <h2 className="text-sm font-semibold text-gray-900 dark:text-gray-100 mb-1">Mis Comprobantes de varias organizaciones</h2>
      <p className="text-xs text-gray-500 dark:text-gray-400 mb-3">
        Subí juntos los Excels de Mis Comprobantes (descargados de la web de ARCA) de cada organización que manejás. Cada
        uno va a su organización por el CUIT del título. Primero ves qué falta; nada se carga hasta que importás.
      </p>
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 items-end">
        <div>
          <label htmlFor="mc-direccion" className="block text-xs text-gray-600 dark:text-gray-400 mb-1">Tipo</label>
          <select id="mc-direccion" className={inputClass} value={direccion}
            onChange={e => { setDireccion(e.target.value as 'emitido' | 'recibido'); setComparacion(null) }}>
            <option value="recibido">Compras (recibidos)</option>
            <option value="emitido">Ventas (emitidos)</option>
          </select>
        </div>
        <div>
          <label htmlFor="mc-periodo" className="block text-xs text-gray-600 dark:text-gray-400 mb-1">Período del Excel</label>
          <input id="mc-periodo" type="month" className={inputClass} value={periodo}
            onChange={e => { setPeriodo(e.target.value); setComparacion(null) }} />
        </div>
        <div>
          <label htmlFor="mc-archivos" className="block text-xs text-gray-600 dark:text-gray-400 mb-1">Excels de Mis Comprobantes</label>
          <input id="mc-archivos" type="file" multiple accept=".xlsx" className="text-xs text-gray-700 dark:text-gray-300"
            disabled={ocupado} onChange={e => comparar(Array.from(e.target.files || []))} />
        </div>
      </div>
      {ocupado && <p className="mt-3 text-xs text-gray-400">Procesando…</p>}
      {error && <p className="mt-3 text-sm text-red-600 dark:text-red-400">{error}</p>}

      {comparacion && (
        <>
          <div className="mt-4 overflow-x-auto rounded-lg border border-gray-100 dark:border-white/10">
            <table className="w-full text-sm">
              <thead className="bg-gray-50 dark:bg-white/5 text-xs text-gray-500 dark:text-gray-400">
                <tr>
                  <th className={th}>Archivo</th><th className={th}>Organización</th><th className={th}>Faltan</th>
                  <th className={th}>IVA que falta</th><th className={th}>Importe distinto</th><th className={th}>En Cuadra y no en ARCA</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100 dark:divide-white/10">
                {comparacion.map(c => (
                  <tr key={c.archivo}>
                    <td className="px-3 py-2 text-xs text-gray-600 dark:text-gray-300">{c.archivo}</td>
                    {c.error ? (
                      <td colSpan={5} className="px-3 py-2 text-xs text-red-600 dark:text-red-400">{c.error}</td>
                    ) : (
                      <>
                        <td className="px-3 py-2 text-gray-900 dark:text-gray-100">{c.nombre}</td>
                        <td className="px-3 py-2 font-mono">{c.faltantes}</td>
                        <td className="px-3 py-2 font-mono">{fmtARS(c.iva_faltante)}</td>
                        <td className={`px-3 py-2 font-mono ${c.importes_distintos ? 'text-amber-700 dark:text-amber-300' : ''}`}>{c.importes_distintos}</td>
                        <td className={`px-3 py-2 font-mono ${c.solo_en_cuadra ? 'text-red-600 dark:text-red-400' : ''}`}>{c.solo_en_cuadra}</td>
                      </>
                    )}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="mt-2 text-[11px] text-gray-500 dark:text-gray-400">
            Para revisar factura por factura (importes distintos, lo que ARCA no tiene), subí el Excel desde IVA de esa organización.
          </p>
          {conFaltantes.length > 0 && (
            <button className={`${btnPrimary} mt-3`} onClick={importar} disabled={ocupado}>
              Importar faltantes de {conFaltantes.length} {conFaltantes.length === 1 ? 'organización' : 'organizaciones'}
            </button>
          )}
        </>
      )}

      {importados && (
        <div className="mt-4 overflow-x-auto rounded-lg border border-gray-100 dark:border-white/10">
          <table className="w-full text-sm">
            <tbody className="divide-y divide-gray-100 dark:divide-white/10">
              {importados.map(a => (
                <tr key={a.archivo}>
                  <td className="px-3 py-2 text-xs text-gray-600 dark:text-gray-300">{a.archivo}</td>
                  <td className="px-3 py-2 text-gray-900 dark:text-gray-100">{a.nombre || '—'}</td>
                  <td className="px-3 py-2 text-xs">
                    {a.error ? <span className="text-red-600 dark:text-red-400">{a.error}</span>
                      : a.lote && deshechos.has(a.lote) ? 'Importación deshecha'
                      : `${a.importados} importados${a.duplicados ? ` · ${a.duplicados} ya estaban` : ''}`}
                  </td>
                  <td className="px-3 py-2 text-right">
                    {a.lote && !deshechos.has(a.lote) && (
                      <button className="text-xs text-ml-blue dark:text-blue-400 hover:underline" onClick={() => deshacer(a)}>Deshacer</button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  )
}

/** Procesos que corren en todas las organizaciones del estudio de una vez. */
export const ProcesosMasivos: React.FC = () => {
  const { hasPermission, user } = useAuthStore()
  return (
    <div className="p-4 md:p-6 max-w-6xl mx-auto">
      <h1 className="text-xl md:text-2xl font-semibold text-gray-900 dark:text-gray-100 mb-1">Procesos masivos</h1>
      <p className="text-sm text-gray-500 dark:text-gray-400 mb-4">
        Para quien maneja varias organizaciones (empresas que usan Cuadra): lo que hoy se hace de a una, para todas de una vez.
      </p>
      {!manejaVariasOrgs(user)
        ? <p className="text-sm text-gray-500 dark:text-gray-400">Esta pantalla es para quien maneja más de una organización. Con una sola, usá IVA, Ingresos Brutos, Monotributo o Sueldos directamente.</p>
        : hasPermission('manage_finance')
          ? <><CalcularParaTodas /><MisComprobantesVarios /></>
          : <p className="text-sm text-gray-500 dark:text-gray-400">No tenés permiso para correr procesos masivos.</p>}
    </div>
  )
}

export default ProcesosMasivos
