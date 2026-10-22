// Formato de importes y fechas para tablas grandes (Movimientos, Conciliaciones,
// PlanillaPanel). Los Intl.*Format se crean una sola vez: construir uno por celda
// (o usar toLocale*String con opciones, que lo construye por dentro) era lo más
// caro de dibujar cientos de filas.

const ARS_FMT = new Intl.NumberFormat('es-AR', { style: 'currency', currency: 'ARS', minimumFractionDigits: 0 })
const FECHA_CORTA_FMT = new Intl.DateTimeFormat('es-AR', { day: '2-digit', month: '2-digit', year: '2-digit' })

/** "$ 1.500" — pesos sin decimales forzados. null/undefined → "—". */
export function fmtARS(n: number | null | undefined): string {
  if (n == null) return '—'
  return ARS_FMT.format(n)
}

/** "01/09/26" desde "2026-09-01" (o un ISO con hora). Vacío → "—"; inválido → el texto tal cual. */
export function fmtFechaCorta(d?: string | null): string {
  if (!d) return '—'
  try { return FECHA_CORTA_FMT.format(new Date(d.includes('T') ? d : d + 'T00:00:00')) }
  catch { return d }
}
