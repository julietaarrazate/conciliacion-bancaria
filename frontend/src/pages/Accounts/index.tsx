import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { api } from '../../services/api'
import { BankAccount } from '../../types'

export default function AccountsPage() {
  const qc = useQueryClient()
  const { data: accounts = [], isLoading } = useQuery<BankAccount[]>({
    queryKey: ['accounts'],
    queryFn: () => api.get('/accounts/').then((r) => r.data),
  })

  const [form, setForm] = useState({
    name: '', account_number: '', bank_name: '', currency: 'ARS',
  })

  const create = useMutation({
    mutationFn: (body: typeof form) => api.post('/accounts/', body).then((r) => r.data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['accounts'] })
      setForm({ name: '', account_number: '', bank_name: '', currency: 'ARS' })
    },
  })

  return (
    <div className="p-8 max-w-5xl mx-auto">
      <h1 className="text-3xl font-bold mb-6">Cuentas Bancarias</h1>

      <form
        onSubmit={(e) => { e.preventDefault(); create.mutate(form) }}
        className="bg-white rounded-xl shadow p-6 mb-6 grid grid-cols-2 gap-4"
      >
        <Input label="Nombre*" value={form.name} onChange={(v) => setForm({ ...form, name: v })} required />
        <Input label="Banco" value={form.bank_name} onChange={(v) => setForm({ ...form, bank_name: v })} />
        <Input label="Nº Cuenta" value={form.account_number} onChange={(v) => setForm({ ...form, account_number: v })} />
        <div>
          <label className="block text-sm font-medium mb-1">Moneda</label>
          <select
            className="w-full border rounded px-3 py-2"
            value={form.currency}
            onChange={(e) => setForm({ ...form, currency: e.target.value })}
          >
            <option value="ARS">ARS</option>
            <option value="USD">USD</option>
          </select>
        </div>
        <button
          type="submit"
          disabled={create.isPending}
          className="col-span-2 bg-blue-600 hover:bg-blue-700 text-white rounded py-2 font-medium"
        >
          {create.isPending ? 'Creando...' : 'Crear cuenta'}
        </button>
      </form>

      <div className="bg-white rounded-xl shadow">
        <table className="w-full">
          <thead className="border-b text-left text-sm text-gray-500">
            <tr>
              <th className="p-3">Nombre</th><th className="p-3">Banco</th>
              <th className="p-3">Nº Cuenta</th><th className="p-3">Moneda</th>
            </tr>
          </thead>
          <tbody>
            {isLoading ? (
              <tr><td colSpan={4} className="p-6 text-center text-gray-400">Cargando...</td></tr>
            ) : accounts.length === 0 ? (
              <tr><td colSpan={4} className="p-6 text-center text-gray-400">Sin cuentas aún.</td></tr>
            ) : accounts.map((a) => (
              <tr key={a.id} className="border-b last:border-0">
                <td className="p-3 font-medium">{a.name}</td>
                <td className="p-3">{a.bank_name || '—'}</td>
                <td className="p-3">{a.account_number || '—'}</td>
                <td className="p-3">{a.currency}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}

function Input({
  label, value, onChange, required = false,
}: { label: string; value: string; onChange: (v: string) => void; required?: boolean }) {
  return (
    <div>
      <label className="block text-sm font-medium mb-1">{label}</label>
      <input
        type="text"
        value={value}
        required={required}
        onChange={(e) => onChange(e.target.value)}
        className="w-full border rounded px-3 py-2"
      />
    </div>
  )
}
