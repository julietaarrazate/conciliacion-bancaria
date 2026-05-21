const COLORS: Record<string, string> = {
  pendiente: 'bg-gray-100 text-gray-700',
  acreditado: 'bg-green-100 text-green-700',
  ok: 'bg-green-100 text-green-700',
  no_esta: 'bg-red-100 text-red-700',
  faltan_datos: 'bg-yellow-100 text-yellow-800',
  duplicado: 'bg-purple-100 text-purple-700',
  rechazado: 'bg-rose-100 text-rose-700',
}

const LABELS: Record<string, string> = {
  pendiente: 'Pendiente',
  acreditado: 'Acreditado',
  ok: 'OK',
  no_esta: 'NO ESTÁ',
  faltan_datos: 'FALTAN DATOS',
  duplicado: 'Duplicado',
  rechazado: 'Rechazado',
}

export default function EstadoBadge({ estado }: { estado: string }) {
  return (
    <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${COLORS[estado] || COLORS.pendiente}`}>
      {LABELS[estado] || estado}
    </span>
  )
}
