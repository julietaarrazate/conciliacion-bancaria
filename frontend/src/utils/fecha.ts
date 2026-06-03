// Utilidades de fecha — siempre en hora LOCAL del dispositivo (Argentina UTC-3).
//
// IMPORTANTE: `new Date().toISOString().slice(0,10)` devuelve la fecha en UTC.
// En Argentina (UTC-3), entre la medianoche y las 3 AM eso da la fecha de AYER,
// lo que rompía los defaults de los formularios (el pago/cheque/arqueo quedaba
// registrado un día antes en el Libro Diario). Usar siempre estos helpers.

/** Fecha local en formato YYYY-MM-DD (sin desfase de timezone). */
export function localIsoDate(d: Date = new Date()): string {
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
}

/** Fecha local de hoy (YYYY-MM-DD). Alias semántico de localIsoDate(). */
export function hoyIso(): string {
  return localIsoDate()
}

/** Fecha local hace N días (YYYY-MM-DD). */
export function isoHaceNDias(n: number): string {
  const d = new Date()
  d.setDate(d.getDate() - n)
  return localIsoDate(d)
}
