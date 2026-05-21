import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { api } from '../../services/api'
import { Cliente } from '../../types'

export default function ClientesPage() {
  const qc = useQueryClient()
  const { data: clientes = [], isLoading } = useQuery<Cliente[]>({
    queryKey: ['clientes'],
    queryFn: () => api.get('/clientes/').then((r) => r.data),
  })

  const [form, setForm] = useState({
    nombre: '', cuit: '', titular: '', cuenta: '', comision: '0', forma_pago: 'banco',
  })

  const create = useMutation({
    mutationFn: (body: typeof form) => api.post('/clientes/', body).then((r) => r.data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['clientes'] })
      setForm({ nombre: '', cuit: '', titular: '', cuenta: '', comision: '0', forma_pago: 'banco' })
    },
  })

  return (
    <div className="p-8 max-w-5xl mx-auto">
      <h1 className="text-3xl font-bold mb-6">Clientes</h1>

      <form
        onSubmit={(e) => { e.preventDefault(); create.mutate(form) }}
        className="bg-white rounded-xl shadow p-6 mb-6 grid grid-cols-2 gap-4"
      >
        <Input label="Nombre*" value={form.nombre} onChange={(v) => setForm({ ...form, nombre: v })} required />
        <Input label="CUIT" value={form.cuit} onChange={(v) => setForm({ ...form, cuit: v })} />
        <Input label="Titular" value={form.titular} onChange={(v) => setForm({ ...form, titular: v })} />
        <Input label="Cuenta" value={form.cuenta} onChange={(v) => setForm({ ...form, cuenta: v })} />
        <Input label="Comisión %" type="number" value={form.comision} onChange={(v) => setForm({ ...form, comision: v })} />
        <div>
          <label className="block text-sm font-medium mb-1">Forma de pago</label>
          <select
            className="w-full border rounded px-3 py-2"
            value={form.forma_pago}
            onChange={(e) => setForm({ ...form, forma_pago: e.target.value })}
          >
            <option value="banco">Banco</option>
            <option value="efectivo">Efectivo</option>
            <option value="cheque">Cheque</option>
            <option value="transferencia">Transferencia</option>
          </select>
        </div>
        <button
          type="submit"
          disabled={create.isPending}
          className="col-span-2 bg-blue-600 hover:bg-blue-700 text-white rounded py-2 font-medium"
        >
          {create.isPending ? 'Creando...' : 'Crear cliente'}
        </button>
      </form>

      <div className="bg-white rounded-xl shadow">
        <table className="w-full">
          <thead className="border-b text-left text-sm text-gray-500">
            <tr>
              <th className="p-3">Nombre</th><th className="p-3">CUIT</th>
              <th className="p-3">Titular</th><th className="p-3">Comisión</th>
              <th className="p-3">Forma pago</th><th className="p-3">Estado</th>
            </tr>
          </thead>
          <tbody>
            {isLoading ? (
              <tr><td colSpan={6} className="p-6 text-center text-gray-400">Cargando...</td></tr>
            ) : clientes.length === 0 ? (
              <tr><td colSpan={6} className="p-6 text-center text-gray-400">Sin clientes aún.</td></tr>
            ) : clientes.map((c) => (
              <tr key={c.id} className="border-b last:border-0">
                <td className="p-3 font-medium">{c.nombre}</td>
                <td className="p-3">{c.cuit || '—'}</td>
                <td className="p-3">{c.titular || '—'}</td>
                <td className="p-3">{c.comision}%</td>
                <td className="p-3">{c.forma_pago || '—'}</td>
                <td className="p-3">{c.activo ? 'Activo' : 'Inactivo'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}

function Input({
  label, value, onChange, type = 'text', required = false,
}: { label: string; value: string; onChange: (v: string) => void; type?: string; required?: boolean }) {
  return (
    <div>
      <label className="block text-sm font-medium mb-1">{label}</label>
      <input
        type={type}
        value={value}
        required={required}
        onChange={(e) => onChange(e.target.value)}
        className="w-full border rounded px-3 py-2"
      />
    </div>
  )
}
