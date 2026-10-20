// Parseo de montos ingresados/OCR. Soporta number o string, formato argentino
// ("15.000,50" / "1.200.000,50"), formato US ("15,000.50"), coma decimal
// ("15000,50") y números planos. Devuelve null si no se puede interpretar.
//
// Signo: acepta "-1.234,56", "1.234,56-" (signo atrás, como lo imprimen varios
// bancos), "(1.234,56)" (paréntesis contables) y el menos tipográfico "−".
// Antes el signo se perdía o se mezclaba con los puntos de miles ("-1.234,56"
// daba -1.234).
//
// Área de bugs recurrente: ver BUGS.md ("Parseo de montos en formato argentino").
// NUNCA asumir que `parseFloat` directo alcanza para montos del usuario en Argentina.
export function parseMonto(raw: unknown): number | null {
  if (raw == null) return null
  if (typeof raw === 'number') return isNaN(raw) ? null : raw
  // quitar símbolo $ y espacios, luego analizar formato
  let s = String(raw).trim().replace(/[$\s]/g, '').replace(/−/g, '-')
  if (!s) return null
  // signo: paréntesis contables, menos adelante o menos atrás (uno solo)
  let negativo = false
  const parentesis = /^\((.*)\)$/.exec(s)
  if (parentesis) { negativo = true; s = parentesis[1] }
  if (s.startsWith('-')) { negativo = !negativo; s = s.slice(1) }
  else if (s.endsWith('-')) { negativo = !negativo; s = s.slice(0, -1) }
  if (!s) return null
  if (s.startsWith('+')) s = s.slice(1)
  const abs = parseMontoSinSigno(s)
  if (abs == null) return null
  return negativo && abs !== 0 ? -abs : abs
}

function parseMontoSinSigno(s: string): number | null {
  // formato argentino: 1.200.000,50 o 15.000,50
  if (/^\d{1,3}(\.\d{3})+(,\d{0,2})?$/.test(s))
    return parseFloat(s.replace(/\./g, '').replace(',', '.'))
  // formato con coma de miles: 1,200,000.50
  if (/^\d{1,3}(,\d{3})+(\.\d{0,2})?$/.test(s))
    return parseFloat(s.replace(/,/g, ''))
  // número con coma decimal: 15000,50
  if (/^\d+(,\d{1,2})$/.test(s))
    return parseFloat(s.replace(',', '.'))
  // número plano con o sin punto decimal
  const n = parseFloat(s.replace(',', '.'))
  return isNaN(n) ? null : n
}
