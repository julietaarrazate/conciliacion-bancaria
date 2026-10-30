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
  'SUGERIDO_GRUPO': 'Sugerido en grupo',
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

// Motivo de un match (`motivo_match` de /planillas/{id}/detalle): qué dato
// coincide entre la fila de la planilla y el movimiento del banco.
const MOTIVOS: Record<string, string> = {
  cuit: 'monto + CUIT',
  dni: 'monto + DNI',
  cbu: 'monto + CBU/CVU',
  numero: 'monto + n° de cuenta/operación',
  titular: 'monto + titular',
  referencia: 'monto + referencia',
  monto: 'solo monto',
}

export function motivoMatchLabel(motivo: string | null | undefined): string | null {
  if (!motivo) return null
  return MOTIVOS[motivo] ?? null
}

// Calidad del match (`coincidencia` de /planillas/{id}/detalle). Solo los casos
// que merecen revisión llevan aviso: el resto (cuit, titular, otro_dato) no.
const AVISOS_COINCIDENCIA: Record<string, { label: string; title: string; grave: boolean }> = {
  cuit_distinto: {
    label: 'CUIT distinto',
    title: 'La fila y el movimiento del banco traen CUIT y no coinciden: el match cerró solo por el monto. Revisalo.',
    grave: true,
  },
  solo_monto: {
    label: 'Solo monto',
    title: 'No coincide ningún dato además del importe (ni CUIT ni titular). Conviene revisarlo.',
    grave: false,
  },
}

export function avisoCoincidencia(c: string | null | undefined): { label: string; title: string; grave: boolean } | null {
  if (!c) return null
  return AVISOS_COINCIDENCIA[c] ?? null
}
