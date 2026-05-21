import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { api } from '../../services/api'
import { Reconciliation } from '../../types'

export default function DashboardPage() {
  const { data: reconciliations = [], isLoading } = useQuery<Reconciliation[]>({
    queryKey: ['reconciliations'],
    queryFn: () => api.get('/reconciliations/').then((r) => r.data),
  })

  const open = reconciliations.filter((r) => r.status !== 'closed').length
  const withDiff = reconciliations.filter((r) => parseFloat(r.difference) !== 0).length

  return (
    <div className="p-8 max-w-4xl mx-auto">
      <h1 className="text-3xl font-bold mb-8">Dashboard</h1>
      <div className="grid grid-cols-3 gap-6 mb-8">
        <StatCard label="Conciliaciones abiertas" value={open} color="blue" />
        <StatCard label="Con diferencias" value={withDiff} color="red" />
        <StatCard label="Total" value={reconciliations.length} color="green" />
      </div>
      <div className="bg-white rounded-xl shadow p-6">
        <h2 className="text-xl font-semibold mb-4">Conciliaciones recientes</h2>
        {isLoading ? (
          <p className="text-gray-500">Cargando...</p>
        ) : reconciliations.length === 0 ? (
          <p className="text-gray-400">No hay conciliaciones aún.</p>
        ) : (
          <ul className="divide-y">
            {reconciliations.slice(0, 10).map((r) => (
              <li key={r.id} className="py-3 flex justify-between items-center">
                <span className="font-medium">Conciliación #{r.id}</span>
                <span className={`px-3 py-1 rounded-full text-sm font-medium ${
                  r.status === 'closed' ? 'bg-green-100 text-green-700' :
                  r.status === 'in_progress' ? 'bg-yellow-100 text-yellow-700' :
                  'bg-blue-100 text-blue-700'
                }`}>{r.status}</span>
                <Link to={`/reconciliation/${r.id}`} className="text-primary hover:underline text-sm">
                  Ver →
                </Link>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  )
}

function StatCard({ label, value, color }: { label: string; value: number; color: string }) {
  const colors: Record<string, string> = {
    blue: 'bg-blue-50 text-blue-700',
    red: 'bg-red-50 text-red-700',
    green: 'bg-green-50 text-green-700',
  }
  return (
    <div className={`rounded-xl p-6 ${colors[color]}`}>
      <p className="text-sm font-medium opacity-70">{label}</p>
      <p className="text-4xl font-bold mt-1">{value}</p>
    </div>
  )
}
