import { useState } from 'react'
import { useParams } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { api } from '../../services/api'
import {
  Reconciliation, BankTransaction, BankStatement, Cliente,
  PlanillaCliente, MovimientoPlanilla,
} from '../../types'
import EstadoBadge from '../../components/EstadoBadge'

export default function ReconciliationPage() {
  const { id } = useParams<{ id: string }>()
  const reconciliationId = Number(id)
  const qc = useQueryClient()

  const { data: recon } = useQuery<Reconciliation | undefined>({
    queryKey: ['reconciliation', reconciliationId],
    queryFn: () => api.get('/reconciliations/').then(
      (r) => (r.data as Reconciliation[]).find((x) => x.id === reconciliationId)
    ),
    enabled: !!reconciliationId,
  })

  const { data: stmt } = useQuery<BankStatement | undefined>({
    queryKey: ['statement', recon?.statement_id],
    queryFn: () => recon
      ? api.get('/statements/').then(
          (r) => (r.data as BankStatement[]).find((x) => x.id === recon.statement_id)
        )
      : Promise.resolve(undefined),
    enabled: !!recon,
  })

  const { data: txns = [] } = useQuery<BankTransaction[]>({
    queryKey: ['statement-txns', recon?.statement_id],
    queryFn: () => recon
      ? api.get(`/statements/${recon.statement_id}/transactions`).then((r) => r.data)
      : Promise.resolve([]),
    enabled: !!recon,
  })

  const { data: clientes = [] } = useQuery<Cliente[]>({
    queryKey: ['clientes'],
    queryFn: () => api.get('/clientes/').then((r) => r.data),
  })

  const autoMatch = useMutation({
    mutationFn: () => api.post(`/reconciliations/${reconciliationId}/auto-match`).then((r) => r.data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['statement-txns'] }),
  })

  const updateTxn = useMutation({
    mutationFn: ({ txnId, body }: { txnId: number; body: any }) =>
      api.patch(`/statements/transactions/${txnId}`, body).then((r) => r.data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['statement-txns'] }),
  })

  const desacreditar = useMutation({
    mutationFn: (itemId: number) => api.delete(`/reconciliations/items/${itemId}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['statement-txns'] }),
  })

  const [acreditarFor, setAcreditarFor] = useState<BankTransaction | null>(null)

  const exportCsv = () => {
    if (!recon) return
    window.open(
      `${import.meta.env.VITE_API_URL || 'http://localhost:8000'}/statements/${recon.statement_id}/export`,
      '_blank',
    )
  }

  return (
    <div className="p-8 max-w-7xl mx-auto">
      <div className="flex justify-between items-center mb-6">
        <h1 className="text-3xl font-bold">Conciliación #{reconciliationId}</h1>
        <div className="flex gap-2">
          <button
            onClick={() => autoMatch.mutate()}
            disabled={autoMatch.isPending}
            className="bg-blue-600 hover:bg-blue-700 text-white px-4 py-2 rounded font-medium"
          >
            {autoMatch.isPending ? 'Procesando...' : 'Auto-match'}
          </button>
          <button onClick={exportCsv} className="bg-gray-600 hover:bg-gray-700 text-white px-4 py-2 rounded font-medium">
            Exportar CSV
          </button>
        </div>
      </div>

      {stmt && (
        <div className="bg-white rounded-xl shadow p-4 mb-4 grid grid-cols-4 gap-4 text-sm">
          <Info label="Período" value={`${stmt.period_start} → ${stmt.period_end}`} />
          <Info label="Saldo inicial" value={stmt.opening_balance} />
          <Info label="Saldo final" value={stmt.closing_balance} />
          <Info label="Diferencia" value={recon?.difference || '—'} />
        </div>
      )}

      <div className="bg-white rounded-xl shadow overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-gray-50 border-b text-left">
            <tr>
              <th className="p-3">Fecha</th>
              <th className="p-3">Descripción</th>
              <th className="p-3 text-right">Monto</th>
              <th className="p-3">Ref</th>
              <th className="p-3">Cliente</th>
              <th className="p-3">Estado</th>
              <th className="p-3">Acreditado el</th>
              <th className="p-3">Acciones</th>
            </tr>
          </thead>
          <tbody>
            {txns.length === 0 ? (
              <tr><td colSpan={8} className="p-6 text-center text-gray-400">Sin transacciones.</td></tr>
            ) : txns.map((t) => (
              <tr key={t.id} className="border-b last:border-0 hover:bg-gray-50">
                <td className="p-3 whitespace-nowrap">{t.transaction_date}</td>
                <td className="p-3">
                  {t.description}
                  {t.es_manual && <span className="ml-2 text-xs text-blue-600">[manual]</span>}
                </td>
                <td className="p-3 text-right font-mono">{t.amount}</td>
                <td className="p-3">{t.reference || '—'}</td>
                <td className="p-3">
                  <select
                    value={t.cliente_id || ''}
                    onChange={(e) => updateTxn.mutate({
                      txnId: t.id,
                      body: { cliente_id: e.target.value ? Number(e.target.value) : null },
                    })}
                    className="border rounded px-2 py-1 text-xs"
                  >
                    <option value="">— sin —</option>
                    {clientes.map((c) => (
                      <option key={c.id} value={c.id}>{c.nombre}</option>
                    ))}
                  </select>
                </td>
                <td className="p-3"><EstadoBadge estado={t.estado} /></td>
                <td className="p-3 text-xs">
                  {t.fecha_acreditacion_original
                    ? `Acreditado el ${t.fecha_acreditacion_original}`
                    : '—'}
                </td>
                <td className="p-3 whitespace-nowrap">
                  {!t.is_reconciled ? (
                    <button
                      onClick={() => setAcreditarFor(t)}
                      className="text-blue-600 hover:underline text-xs"
                    >
                      Acreditar
                    </button>
                  ) : (
                    <button
                      onClick={() => {
                        if (confirm('¿Desacreditar?')) {
                          api.get(`/reconciliations/${reconciliationId}/items`).then((r) => {
                            const item = (r.data as any[]).find((i) => i.bank_transaction_id === t.id)
                            if (item) desacreditar.mutate(item.id)
                          })
                        }
                      }}
                      className="text-red-600 hover:underline text-xs"
                    >
                      Desacreditar
                    </button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {acreditarFor && (
        <ManualAcreditarModal
          txn={acreditarFor}
          reconciliationId={reconciliationId}
          onClose={() => setAcreditarFor(null)}
          onSuccess={() => {
            qc.invalidateQueries({ queryKey: ['statement-txns'] })
            setAcreditarFor(null)
          }}
        />
      )}
    </div>
  )
}

function Info({ label, value }: { label: string; value: string | number }) {
  return (
    <div>
      <div className="text-xs text-gray-500">{label}</div>
      <div className="font-medium">{value}</div>
    </div>
  )
}

function ManualAcreditarModal({
  txn, reconciliationId, onClose, onSuccess,
}: {
  txn: BankTransaction
  reconciliationId: number
  onClose: () => void
  onSuccess: () => void
}) {
  const [clienteId, setClienteId] = useState<number | null>(txn.cliente_id)
  const [planillaId, setPlanillaId] = useState<number | null>(null)
  const [movId, setMovId] = useState<number | null>(null)

  const { data: clientes = [] } = useQuery<Cliente[]>({
    queryKey: ['clientes'],
    queryFn: () => api.get('/clientes/').then((r) => r.data),
  })
  const { data: planillas = [] } = useQuery<PlanillaCliente[]>({
    queryKey: ['planillas-cliente', clienteId],
    queryFn: () => clienteId
      ? api.get(`/clientes/${clienteId}/planillas`).then((r) => r.data)
      : Promise.resolve([]),
    enabled: !!clienteId,
  })
  const { data: movimientos = [] } = useQuery<MovimientoPlanilla[]>({
    queryKey: ['movimientos', planillaId],
    queryFn: () => planillaId
      ? api.get(`/planillas/${planillaId}/movimientos`).then((r) => r.data)
      : Promise.resolve([]),
    enabled: !!planillaId,
  })

  const acreditar = useMutation({
    mutationFn: () => api.post(`/reconciliations/${reconciliationId}/items`, {
      bank_transaction_id: txn.id,
      planilla_movimiento_id: movId,
    }).then((r) => r.data),
    onSuccess,
  })

  return (
    <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50">
      <div className="bg-white rounded-xl p-6 w-[500px]">
        <h3 className="text-xl font-bold mb-4">Acreditar manualmente</h3>
        <div className="text-sm text-gray-600 mb-4">
          <div>Fecha: {txn.transaction_date}</div>
          <div>Monto: {txn.amount}</div>
          <div>Desc: {txn.description}</div>
        </div>

        <Select
          label="Cliente"
          value={clienteId}
          onChange={(v) => { setClienteId(v); setPlanillaId(null); setMovId(null) }}
          options={clientes.map((c) => ({ value: c.id, label: c.nombre }))}
        />
        <Select
          label="Planilla destino"
          value={planillaId}
          onChange={(v) => { setPlanillaId(v); setMovId(null) }}
          options={planillas.map((p) => ({
            value: p.id,
            label: `${p.nombre} (${p.periodo || '—'})`,
          }))}
        />
        <Select
          label="Movimiento de la planilla"
          value={movId}
          onChange={setMovId}
          options={movimientos.map((m) => ({
            value: m.id,
            label: `${m.fecha} — ${m.descripcion} — ${m.monto}`,
          }))}
        />

        <div className="flex justify-end gap-2 mt-6">
          <button onClick={onClose} className="px-4 py-2 rounded border">Cancelar</button>
          <button
            onClick={() => acreditar.mutate()}
            disabled={!movId || acreditar.isPending}
            className="px-4 py-2 rounded bg-blue-600 text-white disabled:opacity-50"
          >
            {acreditar.isPending ? 'Acreditando...' : 'Acreditar'}
          </button>
        </div>
      </div>
    </div>
  )
}

function Select({
  label, value, onChange, options,
}: {
  label: string
  value: number | null
  onChange: (v: number | null) => void
  options: { value: number; label: string }[]
}) {
  return (
    <div className="mb-3">
      <label className="block text-sm font-medium mb-1">{label}</label>
      <select
        value={value ?? ''}
        onChange={(e) => onChange(e.target.value ? Number(e.target.value) : null)}
        className="w-full border rounded px-3 py-2"
      >
        <option value="">— seleccionar —</option>
        {options.map((o) => (
          <option key={o.value} value={o.value}>{o.label}</option>
        ))}
      </select>
    </div>
  )
}
