import React, { useEffect, useRef, useState } from 'react'
import { IconCheck, IconCursor, Logo, prefersReducedMotion, useInView } from './shared'

/**
 * La conciliación de Cuadra en ~6 segundos, armada con los mismos textos que
 * muestra la app (labels de `utils/status.ts` y de `ControlBancoCard`):
 *   1. se sube el extracto → 2. aparecen los movimientos → 3. cada uno se
 *   acredita contra la planilla de su cliente (uno con el monto repetido queda
 *   "Ambiguo — elegir a mano") → 4. la usuaria lo elige → 5. el Control del
 *   banco cierra.
 *
 * Todo el contenido está siempre montado: cada fase solo cambia atributos
 * `data-*` y el CSS anima `opacity`/`transform` (sin layout shift). Corre en
 * loop solo mientras está en pantalla; con reduced-motion queda en el cuadro final.
 */

type Row = { fecha: string; concepto: string; detalle: string; monto: number; cliente: number; ambiguo?: boolean }

const ROWS: Row[] = [
  { fecha: '02/10', concepto: 'TRANSF. FERRETERIA LIMA',        detalle: 'CUIT 30-71234567-8',   monto: 150000,   cliente: 0 },
  { fecha: '03/10', concepto: 'TRANSF. PANADERIA BELGRANO',        detalle: 'CBU ···· 4521',        monto: 82000,    cliente: 1 },
  { fecha: '06/10', concepto: 'DEP. CHEQUE 10483',       detalle: 'Ferretería Lima SRL',             monto: 250000,   cliente: 0 },
  { fecha: '07/10', concepto: 'TRANSFERENCIA RECIBIDA',  detalle: 'Sin datos del titular', monto: 45000,   cliente: 2, ambiguo: true },
  { fecha: '09/10', concepto: 'TRANSF. DISTRIB DEL SUR',   detalle: 'Titular: Distribuidora del Sur SA', monto: 45000, cliente: 2 },
  { fecha: '10/10', concepto: 'TRANSF. FERRETERIA LIMA',        detalle: 'CUIT 30-71234567-8',   monto: 64500,    cliente: 0 },
]

const CLIENTES = [
  { nombre: 'Ferretería Lima SRL', formato: 'Excel' },
  { nombre: 'Panadería Belgrano', formato: 'CSV' },
  { nombre: 'Distribuidora del Sur SA', formato: 'Excel' },
]

// Fases: 0 vacío · 1 archivo · 2 filas · 3..8 fila i procesada · 9 cursor · 10 elegida · 11 control OK
const FIRST_ROW_PHASE = 3
const P_CURSOR = FIRST_ROW_PHASE + ROWS.length
const P_RESOLVED = P_CURSOR + 1
const P_OK = P_RESOLVED + 1
const FINAL = P_OK
const TIMES = [0, 250, 1150, 1900, 2250, 2600, 2950, 3300, 3650, 4250, 5050, 5550]
const LOOP_MS = 9200

const fmt = (n: number) => '$ ' + n.toLocaleString('es-AR', { minimumFractionDigits: 2, maximumFractionDigits: 2 })

function estadoFila(i: number, p: number): 'pend' | 'ok' | 'amb' {
  if (p < FIRST_ROW_PHASE + i) return 'pend'
  if (ROWS[i].ambiguo && p < P_RESOLVED) return 'amb'
  return 'ok'
}

export const HeroDemo: React.FC = () => {
  const ref = useRef<HTMLDivElement>(null)
  const inView = useInView(ref)
  const [reduced] = useState(prefersReducedMotion)
  const [p, setP] = useState(reduced ? FINAL : 0)

  useEffect(() => {
    if (reduced || !inView) return
    const timers: number[] = []
    const ciclo = () => {
      TIMES.forEach((t, fase) => timers.push(window.setTimeout(() => setP(fase), t)))
      timers.push(window.setTimeout(ciclo, LOOP_MS))
    }
    ciclo()
    return () => timers.forEach(t => window.clearTimeout(t))
  }, [inView, reduced])

  const acreditado = (i: number) => estadoFila(i, p) === 'ok'
  const pendiente = ROWS.reduce((s, r, i) => s + (acreditado(i) ? 0 : r.monto), 0)

  return (
    <div
      ref={ref}
      className="hd"
      data-testid="hero-demo"
      data-phase={p}
      data-p-file={p >= 1}
      data-p-rows={p >= 2}
      data-p-ok={p >= P_OK}
      role="img"
      aria-label="Cuadra en acción: se sube el extracto del Banco Macro, cada movimiento se acredita contra la planilla de su cliente, el pago con monto repetido se elige a mano y el control del banco queda cerrado."
    >
      <div className="hd-bar" aria-hidden="true">
        <Logo size={18} />
        <span className="hd-bar-title">Conciliación</span>
        <span className="hd-bar-crumb">Banco Macro · Octubre</span>
        <span className="hd-file">
          <span className="hd-file-name">extracto_macro_oct.pdf</span>
          <span className="hd-file-bar"><i /></span>
        </span>
      </div>

      <div className="hd-body" aria-hidden="true">
        <div className="hd-main">
          <div className="hd-label">Movimientos del extracto <b>{ROWS.length} créditos</b></div>
          <div className="hd-rows">
            {ROWS.map((r, i) => {
              const st = estadoFila(i, p)
              const cursor = r.ambiguo ? (p === P_CURSOR ? 'true' : p > P_CURSOR ? 'gone' : 'false') : undefined
              return (
                <div key={i} className="hd-row" data-st={st} data-cursor={cursor} style={{ '--i': i } as React.CSSProperties}>
                  <span className="hd-date num">{r.fecha}</span>
                  <span className="hd-concept"><b>{r.concepto}</b><small>{r.detalle}</small></span>
                  <span className="hd-amount num">{fmt(r.monto)}</span>
                  <span className="hd-chip">
                    <span className="c-pend">Pendiente</span>
                    <span className="c-ok"><IconCheck size={12} /> Acreditado</span>
                    <span className="c-amb"><span className="hd-lg">Ambiguo — elegir a mano</span><span className="hd-sm">Elegir a mano</span></span>
                  </span>
                  {r.ambiguo && <span className="hd-cursor"><IconCursor /></span>}
                </div>
              )
            })}
          </div>
        </div>

        <div className="hd-side">
          <div className="hd-card">
            <div className="hd-label">Planillas de clientes</div>
            <div className="hd-clients">
              {CLIENTES.map((c, ci) => {
                const filas = ROWS.map((r, i) => ({ r, i })).filter(x => x.r.cliente === ci)
                const ok = filas.filter(x => acreditado(x.i)).length
                return (
                  <div key={c.nombre} className="hd-client" data-done={ok === filas.length}>
                    <span className="hd-client-name">{c.nombre}<small>{c.formato}</small></span>
                    <span className="hd-client-count num">{ok}/{filas.length}</span>
                    <span className="hd-track"><i style={{ transform: `scaleX(${ok / filas.length})` }} /></span>
                  </div>
                )
              })}
            </div>
          </div>

          <div className="hd-card">
            <div className="hd-ctrl-head">
              <span className="hd-ctrl-title">Control del banco</span>
              <span className="hd-ctrl-badge"><IconCheck size={13} /></span>
            </div>
            <div className="hd-stack hd-ctrl-status">
              <span className="s-wait">Conciliando el extracto…</span>
              <span className="s-ok">El banco en libros coincide con el extracto</span>
            </div>
            <div className="hd-ctrl-grid">
              <div><small>Cobros a imputar</small><span className="num">{fmt(pendiente)}</span></div>
              <div><small>Pagos a imputar</small><span className="num">{fmt(0)}</span></div>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
