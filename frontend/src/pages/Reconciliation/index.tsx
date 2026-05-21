import { useParams } from 'react-router-dom'

export default function ReconciliationPage() {
  const { id } = useParams()
  return (
    <div className="p-8">
      <h1 className="text-3xl font-bold mb-6">Conciliación #{id}</h1>
      <p className="text-gray-500">UI de matching — implementar con /dev</p>
    </div>
  )
}
