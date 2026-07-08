// Labels humanos para los estados de conciliación.
// Los VALORES de status son contrato de API (se guardan/mandan tal cual);
// esto solo traduce lo que se MUESTRA, para que cualquier persona lo entienda
// sin conocer la jerga interna ("no está", "sin datos (3 mov...)", etc.).
const EXACTOS: Record<string, string> = {
  'ok': 'Acreditado ✓',
  'no está': 'No encontrado ✕',
  'duplicado': 'Duplicado ⚠',
  'faltan datos': 'Sin datos ?',
  'pendiente': 'Pendiente',
  'PAGO_PARCIAL': 'Pago parcial',
  'CONCILIADO_CON_DIFERENCIA': 'Conciliado con diferencia',
  'VENCIDO': 'Vencido',
  'EN_REVISION': 'En revisión',
}

export function statusLabel(status: string | null | undefined): string {
  if (!status) return '—'
  const s = status.trim()
  if (EXACTOS[s]) return EXACTOS[s]
  // Variantes con detalle: "ok (aprendido)", "acreditado 15/06", "sin datos (3 mov...)",
  // "ambiguo (2 candidatos, mismo score)", "no coincide (2 mov...)"
  const low = s.toLowerCase()
  if (low.startsWith('ok')) return 'Acreditado ✓'
  if (low.startsWith('acreditado')) return `Acreditado ✓ ${s.slice('acreditado'.length).trim()}`.trim()
  if (low.startsWith('ambiguo')) return 'Ambiguo — elegir a mano'
  if (low.startsWith('sin datos')) return 'Sin datos ?'
  if (low.startsWith('no coincide')) return 'No coincide — revisar'
  if (low.startsWith('no está') || low.startsWith('no esta')) return 'No encontrado ✕'
  return s  // desconocido: se muestra tal cual
}
