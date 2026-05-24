import React, { useEffect, useState, useCallback } from 'react'
import { useSearchParams } from 'react-router-dom'
import { apiClient } from '@/services/api'
import { useAuthStore } from '@/store/auth'

const fmt = (n: number) =>
  new Intl.NumberFormat('es-AR', { style: 'currency', currency: 'ARS', minimumFractionDigits: 2 }).format(n)

const fmtDate = (d?: string | null) =>
  d ? new Date(d + (d.includes('T') ? '' : 'T00:00:00')).toLocaleDateString('es-AR') : '—'

interface Pago {
  id: number
  cliente_id: number | null
  cliente_nombre: string | null
  concepto: string | null
  monto: number
  medio: string
  fecha: string | null
  referencia: string | null
  notas: string | null
  created_at: string
}

interface Gasto {
  id: number
  concepto: string
  categoria: string | null
  monto: number
  medio: string
  fecha: string | null
  referencia: string | null
  notas: string | null
  created_at: string
}

interface ClienteOpt { id: number; nombre: string }

const MEDIO_BADGE: Record<string, string> = {
  banco:    'bg-blue-100 dark:bg-blue-500/15 text-blue-700 dark:text-blue-400',
  efectivo: 'bg-emerald-100 dark:bg-emerald-500/15 text-emerald-700 dark:text-emerald-400',
}

const inputClass = "w-full bg-white/5 border border-white/10 rounded px-3 py-1.5 text-sm text-gray-100 focus:outline-none focus:border-indigo-500"
const filterClass = "bg-white dark:bg-white/5 border border-gray-200 dark:border-white/10 rounded-lg px-3 py-1.5 text-sm text-gray-700 dark:text-gray-200 focus:outline-none"

// ── Pagos tab ────────────────────────────────────────────────────

const PagosTab: React.FC<{ clientes: ClienteOpt[]; canEdit: boolean }> = ({ clientes, canEdit }) => {
  const [pagos, setPagos]         = useState<Pago[]>([])
  const [total, setTotal]         = useState(0)
  const [loading, setLoading]     = useState(true)
  const [msg, setMsg]             = useState('')
  const [showForm, setShowForm]   = useState(false)
  const [saving, setSaving]       = useState(false)
  const [editingPago, setEditingPago] = useState<Pago | null>(null)

  const [filtroCliente, setFiltroCliente] = useState('')
  const [filtroMedio, setFiltroMedio]     = useState('')
  const [filtroDesde, setFiltroDesde]     = useState('')
  const [filtroHasta, setFiltroHasta]     = useState('')
  const [skip, setSkip]                   = useState(0)
  const LIMIT = 50

  const emptyForm = { cliente_id: '', concepto: '', monto: '', medio: 'banco', fecha: '', referencia: '', notas: '' }
  const [form, setForm] = useState(emptyForm)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const params: Record<string, string> = { skip: String(skip), limit: String(LIMIT) }
      if (filtroCliente) params.cliente_id = filtroCliente
      if (filtroMedio)   params.medio      = filtroMedio
      if (filtroDesde)   params.desde      = filtroDesde
      if (filtroHasta)   params.hasta      = filtroHasta
      const res = await apiClient.client.get('/pagos', { params })
      setPagos(res.data.items)
      setTotal(res.data.total)
    } catch { setMsg('Error al cargar pagos') }
    finally { setLoading(false) }
  }, [filtroCliente, filtroMedio, filtroDesde, filtroHasta, skip])

  useEffect(() => { load() }, [load])

  const handleCreate = async () => {
    if (!form.monto || parseFloat(form.monto) <= 0) { setMsg('El monto es requerido'); return }
    setSaving(true); setMsg('')
    try {
      await apiClient.client.post('/pagos', {
        cliente_id: form.cliente_id ? parseInt(form.cliente_id) : null,
        concepto:   form.concepto || null,
        monto:      parseFloat(form.monto),
        medio:      form.medio,
        fecha:      form.fecha || null,
        referencia: form.referencia || null,
        notas:      form.notas || null,
      })
      setShowForm(false)
      setForm(emptyForm)
      load()
    } catch (e: any) { setMsg(e?.response?.data?.detail || 'Error al guardar') }
    finally { setSaving(false) }
  }

  const handleUpdate = async () => {
    if (!editingPago) return
    if (!form.monto || parseFloat(form.monto) <= 0) { setMsg('El monto es requerido'); return }
    setSaving(true); setMsg('')
    try {
      await apiClient.client.patch(`/pagos/${editingPago.id}`, {
        cliente_id: form.cliente_id ? parseInt(form.cliente_id) : null,
        concepto:   form.concepto || null,
        monto:      parseFloat(form.monto),
        medio:      form.medio,
        fecha:      form.fecha || null,
        referencia: form.referencia || null,
        notas:      form.notas || null,
      })
      setEditingPago(null)
      setForm(emptyForm)
      load()
    } catch (e: any) { setMsg(e?.response?.data?.detail || 'Error al guardar') }
    finally { setSaving(false) }
  }

  const openEdit = (p: Pago) => {
    setForm({
      cliente_id: p.cliente_id ? String(p.cliente_id) : '',
      concepto:   p.concepto   || '',
      monto:      String(p.monto),
      medio:      p.medio,
      fecha:      p.fecha      || '',
      referencia: p.referencia || '',
      notas:      p.notas      || '',
    })
    setMsg('')
    setEditingPago(p)
  }

  const handleDelete = async (id: number) => {
    if (!confirm('¿Eliminar este pago?')) return
    try { await apiClient.client.delete(`/pagos/${id}`); load() }
    catch (e: any) { setMsg(e?.response?.data?.detail || 'Error') }
  }

  const totalMonto = pagos.reduce((s, p) => s + p.monto, 0)
  const isFormOpen = showForm || !!editingPago

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="text-sm text-gray-500 dark:text-gray-400">
          {total} pago{total !== 1 ? 's' : ''} · Total visible: <span className="text-gray-800 dark:text-gray-200 font-medium">{fmt(totalMonto)}</span>
        </div>
        <button onClick={() => { setShowForm(true); setMsg('') }}
          className="px-3 py-1.5 bg-indigo-600 hover:bg-indigo-500 text-white text-sm rounded-lg transition-colors">
          + Registrar pago
        </button>
      </div>

      {msg && <div className="text-sm text-red-400 bg-red-500/10 border border-red-500/20 rounded-lg px-3 py-2">{msg}</div>}

      {/* Filters */}
      <div className="flex flex-wrap gap-2">
        <select value={filtroCliente} onChange={e => { setFiltroCliente(e.target.value); setSkip(0) }} className={filterClass}>
          <option value="">Todos los clientes</option>
          {clientes.map(c => <option key={c.id} value={c.id}>{c.nombre}</option>)}
        </select>
        <select value={filtroMedio} onChange={e => { setFiltroMedio(e.target.value); setSkip(0) }} className={filterClass}>
          <option value="">Banco y efectivo</option>
          <option value="banco">Banco</option>
          <option value="efectivo">Efectivo</option>
        </select>
        <input type="date" value={filtroDesde} onChange={e => { setFiltroDesde(e.target.value); setSkip(0) }} className={filterClass} />
        <input type="date" value={filtroHasta} onChange={e => { setFiltroHasta(e.target.value); setSkip(0) }} className={filterClass} />
        {(filtroCliente || filtroMedio || filtroDesde || filtroHasta) && (
          <button onClick={() => { setFiltroCliente(''); setFiltroMedio(''); setFiltroDesde(''); setFiltroHasta(''); setSkip(0) }}
            className="text-xs text-gray-400 hover:text-gray-600 dark:hover:text-gray-200 px-2">Limpiar</button>
        )}
      </div>

      <div className="rounded-xl overflow-hidden border border-gray-200 dark:border-white/8">
        <div className="overflow-x-auto">
          <table className="w-full text-xs min-w-[600px]">
            <thead>
              <tr className="bg-gray-50 dark:bg-white/4 text-left text-gray-500 dark:text-gray-400">
                <th className="px-3 py-2 font-medium">Fecha</th>
                <th className="px-3 py-2 font-medium">Cliente</th>
                <th className="px-3 py-2 font-medium">Concepto</th>
                <th className="px-3 py-2 font-medium">Medio</th>
                <th className="px-3 py-2 font-medium text-right">Monto</th>
                <th className="px-3 py-2 font-medium">Referencia</th>
                {canEdit && <th className="px-3 py-2 font-medium w-16"></th>}
              </tr>
            </thead>
            <tbody>
              {loading ? (
                <tr><td colSpan={canEdit ? 7 : 6} className="text-center py-8 text-gray-500">Cargando…</td></tr>
              ) : pagos.length === 0 ? (
                <tr><td colSpan={canEdit ? 7 : 6} className="text-center py-8 text-gray-500">Sin pagos registrados</td></tr>
              ) : pagos.map((p, i) => (
                <tr key={p.id} className={`border-t border-gray-100 dark:border-white/5 hover:bg-gray-50 dark:hover:bg-white/2 ${i % 2 === 0 ? '' : 'bg-gray-50/40 dark:bg-white/1'}`}>
                  <td className="px-3 py-2 text-gray-600 dark:text-gray-300">{fmtDate(p.fecha)}</td>
                  <td className="px-3 py-2 text-gray-800 dark:text-gray-200">{p.cliente_nombre || <span className="text-gray-400">—</span>}</td>
                  <td className="px-3 py-2 text-gray-600 dark:text-gray-300">{p.concepto || '—'}</td>
                  <td className="px-3 py-2">
                    <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${MEDIO_BADGE[p.medio] || ''}`}>{p.medio}</span>
                  </td>
                  <td className="px-3 py-2 text-right font-mono text-gray-800 dark:text-gray-100">{fmt(p.monto)}</td>
                  <td className="px-3 py-2 text-gray-500 dark:text-gray-400">{p.referencia || '—'}</td>
                  {canEdit && (
                    <td className="px-3 py-2">
                      <div className="flex gap-1">
                        <button onClick={() => openEdit(p)}
                          className="px-2 py-0.5 bg-gray-100 dark:bg-white/5 hover:bg-indigo-100 dark:hover:bg-indigo-600/20 text-gray-400 hover:text-indigo-600 dark:hover:text-indigo-400 rounded text-xs transition-colors">✏</button>
                        <button onClick={() => handleDelete(p.id)}
                          className="px-2 py-0.5 bg-gray-100 dark:bg-white/5 hover:bg-red-100 dark:hover:bg-red-600/20 text-gray-400 hover:text-red-500 dark:hover:text-red-400 rounded text-xs transition-colors">✕</button>
                      </div>
                    </td>
                  )}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {total > LIMIT && (
        <div className="flex items-center justify-between text-xs text-gray-500 dark:text-gray-400">
          <span>{skip + 1}–{Math.min(skip + LIMIT, total)} de {total}</span>
          <div className="flex gap-2">
            <button disabled={skip === 0} onClick={() => setSkip(s => Math.max(0, s - LIMIT))}
              className="px-3 py-1 bg-gray-100 dark:bg-white/5 rounded disabled:opacity-40 hover:bg-gray-200 dark:hover:bg-white/10">← Anterior</button>
            <button disabled={skip + LIMIT >= total} onClick={() => setSkip(s => s + LIMIT)}
              className="px-3 py-1 bg-gray-100 dark:bg-white/5 rounded disabled:opacity-40 hover:bg-gray-200 dark:hover:bg-white/10">Siguiente →</button>
          </div>
        </div>
      )}

      {/* Create / Edit modal */}
      {isFormOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4"
          onClick={e => e.target === e.currentTarget && (setShowForm(false), setEditingPago(null))}>
          <div className="bg-[#16161A] border border-white/10 rounded-xl p-5 w-full max-w-md space-y-4">
            <div className="flex items-center justify-between">
              <h2 className="text-base font-semibold text-gray-100">{editingPago ? 'Editar pago' : 'Registrar pago'}</h2>
              <button onClick={() => { setShowForm(false); setEditingPago(null) }} className="text-gray-500 hover:text-gray-300 text-xl leading-none">×</button>
            </div>
            {msg && <p className="text-xs text-red-400">{msg}</p>}
            <p className="text-xs text-gray-500">Asiento: Pasivo cliente (D) / {form.medio === 'banco' ? 'Banco' : 'Efectivo'} (H)</p>
            <div className="grid grid-cols-2 gap-3">
              <div className="col-span-2">
                <label className="block text-xs text-gray-400 mb-1">Cliente</label>
                <select value={form.cliente_id} onChange={e => setForm(f => ({ ...f, cliente_id: e.target.value }))} className={inputClass}>
                  <option value="">Sin cliente</option>
                  {clientes.map(c => <option key={c.id} value={c.id}>{c.nombre}</option>)}
                </select>
              </div>
              <div className="col-span-2">
                <label className="block text-xs text-gray-400 mb-1">Concepto</label>
                <input type="text" value={form.concepto} onChange={e => setForm(f => ({ ...f, concepto: e.target.value }))} className={inputClass} />
              </div>
              <div>
                <label className="block text-xs text-gray-400 mb-1">Monto *</label>
                <input type="number" value={form.monto} onChange={e => setForm(f => ({ ...f, monto: e.target.value }))} className={inputClass} />
              </div>
              <div>
                <label className="block text-xs text-gray-400 mb-1">Medio</label>
                <select value={form.medio} onChange={e => setForm(f => ({ ...f, medio: e.target.value }))} className={inputClass}>
                  <option value="banco">Banco</option>
                  <option value="efectivo">Efectivo</option>
                </select>
              </div>
              <div>
                <label className="block text-xs text-gray-400 mb-1">Fecha</label>
                <input type="date" value={form.fecha} onChange={e => setForm(f => ({ ...f, fecha: e.target.value }))} className={inputClass} />
              </div>
              <div>
                <label className="block text-xs text-gray-400 mb-1">Referencia</label>
                <input type="text" value={form.referencia} onChange={e => setForm(f => ({ ...f, referencia: e.target.value }))} className={inputClass} />
              </div>
              <div className="col-span-2">
                <label className="block text-xs text-gray-400 mb-1">Notas</label>
                <textarea rows={2} value={form.notas} onChange={e => setForm(f => ({ ...f, notas: e.target.value }))}
                  className="w-full bg-white/5 border border-white/10 rounded px-3 py-1.5 text-sm text-gray-100 focus:outline-none focus:border-indigo-500 resize-none" />
              </div>
            </div>
            <div className="flex justify-end gap-2 pt-2">
              <button onClick={() => { setShowForm(false); setEditingPago(null) }} className="px-4 py-1.5 text-sm text-gray-400 hover:text-gray-200">Cancelar</button>
              <button onClick={editingPago ? handleUpdate : handleCreate} disabled={saving}
                className="px-4 py-1.5 bg-indigo-600 hover:bg-indigo-500 text-white text-sm rounded-lg disabled:opacity-50 transition-colors">
                {saving ? 'Guardando…' : editingPago ? 'Guardar cambios' : 'Guardar'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

// ── Gastos tab ───────────────────────────────────────────────────

const GastosTab: React.FC<{ canEdit: boolean }> = ({ canEdit }) => {
  const [gastos, setGastos]       = useState<Gasto[]>([])
  const [total, setTotal]         = useState(0)
  const [loading, setLoading]     = useState(true)
  const [msg, setMsg]             = useState('')
  const [showForm, setShowForm]   = useState(false)
  const [saving, setSaving]       = useState(false)
  const [editingGasto, setEditingGasto] = useState<Gasto | null>(null)

  const [filtroCategoria, setFiltroCategoria] = useState('')
  const [filtroMedio, setFiltroMedio]         = useState('')
  const [filtroDesde, setFiltroDesde]         = useState('')
  const [filtroHasta, setFiltroHasta]         = useState('')
  const [skip, setSkip]                       = useState(0)
  const LIMIT = 50

  const emptyForm = { concepto: '', categoria: '', monto: '', medio: 'banco', fecha: '', referencia: '', notas: '' }
  const [form, setForm] = useState(emptyForm)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const params: Record<string, string> = { skip: String(skip), limit: String(LIMIT) }
      if (filtroCategoria) params.categoria = filtroCategoria
      if (filtroMedio)     params.medio     = filtroMedio
      if (filtroDesde)     params.desde     = filtroDesde
      if (filtroHasta)     params.hasta     = filtroHasta
      const res = await apiClient.client.get('/gastos', { params })
      setGastos(res.data.items)
      setTotal(res.data.total)
    } catch { setMsg('Error al cargar gastos') }
    finally { setLoading(false) }
  }, [filtroCategoria, filtroMedio, filtroDesde, filtroHasta, skip])

  useEffect(() => { load() }, [load])

  const handleCreate = async () => {
    if (!form.concepto.trim()) { setMsg('El concepto es requerido'); return }
    if (!form.monto || parseFloat(form.monto) <= 0) { setMsg('El monto es requerido'); return }
    setSaving(true); setMsg('')
    try {
      await apiClient.client.post('/gastos', {
        concepto:   form.concepto,
        categoria:  form.categoria || null,
        monto:      parseFloat(form.monto),
        medio:      form.medio,
        fecha:      form.fecha || null,
        referencia: form.referencia || null,
        notas:      form.notas || null,
      })
      setShowForm(false)
      setForm(emptyForm)
      load()
    } catch (e: any) { setMsg(e?.response?.data?.detail || 'Error al guardar') }
    finally { setSaving(false) }
  }

  const handleUpdate = async () => {
    if (!editingGasto) return
    if (!form.concepto.trim()) { setMsg('El concepto es requerido'); return }
    if (!form.monto || parseFloat(form.monto) <= 0) { setMsg('El monto es requerido'); return }
    setSaving(true); setMsg('')
    try {
      await apiClient.client.patch(`/gastos/${editingGasto.id}`, {
        concepto:   form.concepto,
        categoria:  form.categoria || null,
        monto:      parseFloat(form.monto),
        medio:      form.medio,
        fecha:      form.fecha || null,
        referencia: form.referencia || null,
        notas:      form.notas || null,
      })
      setEditingGasto(null)
      setForm(emptyForm)
      load()
    } catch (e: any) { setMsg(e?.response?.data?.detail || 'Error al guardar') }
    finally { setSaving(false) }
  }

  const openEdit = (g: Gasto) => {
    setForm({
      concepto:   g.concepto,
      categoria:  g.categoria  || '',
      monto:      String(g.monto),
      medio:      g.medio,
      fecha:      g.fecha      || '',
      referencia: g.referencia || '',
      notas:      g.notas      || '',
    })
    setMsg('')
    setEditingGasto(g)
  }

  const handleDelete = async (id: number) => {
    if (!confirm('¿Eliminar este gasto?')) return
    try { await apiClient.client.delete(`/gastos/${id}`); load() }
    catch (e: any) { setMsg(e?.response?.data?.detail || 'Error') }
  }

  const totalMonto = gastos.reduce((s, g) => s + g.monto, 0)
  const isFormOpen = showForm || !!editingGasto

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="text-sm text-gray-500 dark:text-gray-400">
          {total} gasto{total !== 1 ? 's' : ''} · Total visible: <span className="text-gray-800 dark:text-gray-200 font-medium">{fmt(totalMonto)}</span>
        </div>
        <button onClick={() => { setShowForm(true); setMsg('') }}
          className="px-3 py-1.5 bg-indigo-600 hover:bg-indigo-500 text-white text-sm rounded-lg transition-colors">
          + Registrar gasto
        </button>
      </div>

      {msg && <div className="text-sm text-red-400 bg-red-500/10 border border-red-500/20 rounded-lg px-3 py-2">{msg}</div>}

      {/* Filters */}
      <div className="flex flex-wrap gap-2">
        <select value={filtroCategoria} onChange={e => { setFiltroCategoria(e.target.value); setSkip(0) }} className={filterClass}>
          <option value="">Todas las categorías</option>
          <option value="impuestos">Impuestos déb/créd</option>
          <option value="bancarios">Gastos bancarios</option>
          <option value="otros">Otros</option>
        </select>
        <select value={filtroMedio} onChange={e => { setFiltroMedio(e.target.value); setSkip(0) }} className={filterClass}>
          <option value="">Banco y efectivo</option>
          <option value="banco">Banco</option>
          <option value="efectivo">Efectivo</option>
        </select>
        <input type="date" value={filtroDesde} onChange={e => { setFiltroDesde(e.target.value); setSkip(0) }} className={filterClass} />
        <input type="date" value={filtroHasta} onChange={e => { setFiltroHasta(e.target.value); setSkip(0) }} className={filterClass} />
        {(filtroCategoria || filtroMedio || filtroDesde || filtroHasta) && (
          <button onClick={() => { setFiltroCategoria(''); setFiltroMedio(''); setFiltroDesde(''); setFiltroHasta(''); setSkip(0) }}
            className="text-xs text-gray-400 hover:text-gray-600 dark:hover:text-gray-200 px-2">Limpiar</button>
        )}
      </div>

      <div className="rounded-xl overflow-hidden border border-gray-200 dark:border-white/8">
        <div className="overflow-x-auto">
          <table className="w-full text-xs min-w-[600px]">
            <thead>
              <tr className="bg-gray-50 dark:bg-white/4 text-left text-gray-500 dark:text-gray-400">
                <th className="px-3 py-2 font-medium">Fecha</th>
                <th className="px-3 py-2 font-medium">Concepto</th>
                <th className="px-3 py-2 font-medium">Categoría</th>
                <th className="px-3 py-2 font-medium">Medio</th>
                <th className="px-3 py-2 font-medium text-right">Monto</th>
                <th className="px-3 py-2 font-medium">Referencia</th>
                {canEdit && <th className="px-3 py-2 font-medium w-16"></th>}
              </tr>
            </thead>
            <tbody>
              {loading ? (
                <tr><td colSpan={canEdit ? 7 : 6} className="text-center py-8 text-gray-500">Cargando…</td></tr>
              ) : gastos.length === 0 ? (
                <tr><td colSpan={canEdit ? 7 : 6} className="text-center py-8 text-gray-500">Sin gastos registrados</td></tr>
              ) : gastos.map((g, i) => (
                <tr key={g.id} className={`border-t border-gray-100 dark:border-white/5 hover:bg-gray-50 dark:hover:bg-white/2 ${i % 2 === 0 ? '' : 'bg-gray-50/40 dark:bg-white/1'}`}>
                  <td className="px-3 py-2 text-gray-600 dark:text-gray-300">{fmtDate(g.fecha)}</td>
                  <td className="px-3 py-2 text-gray-800 dark:text-gray-200">{g.concepto}</td>
                  <td className="px-3 py-2 text-gray-500 dark:text-gray-400">{g.categoria || '—'}</td>
                  <td className="px-3 py-2">
                    <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${MEDIO_BADGE[g.medio] || ''}`}>{g.medio}</span>
                  </td>
                  <td className="px-3 py-2 text-right font-mono text-gray-800 dark:text-gray-100">{fmt(g.monto)}</td>
                  <td className="px-3 py-2 text-gray-500 dark:text-gray-400">{g.referencia || '—'}</td>
                  {canEdit && (
                    <td className="px-3 py-2">
                      <div className="flex gap-1">
                        <button onClick={() => openEdit(g)}
                          className="px-2 py-0.5 bg-gray-100 dark:bg-white/5 hover:bg-indigo-100 dark:hover:bg-indigo-600/20 text-gray-400 hover:text-indigo-600 dark:hover:text-indigo-400 rounded text-xs transition-colors">✏</button>
                        <button onClick={() => handleDelete(g.id)}
                          className="px-2 py-0.5 bg-gray-100 dark:bg-white/5 hover:bg-red-100 dark:hover:bg-red-600/20 text-gray-400 hover:text-red-500 dark:hover:text-red-400 rounded text-xs transition-colors">✕</button>
                      </div>
                    </td>
                  )}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {total > LIMIT && (
        <div className="flex items-center justify-between text-xs text-gray-500 dark:text-gray-400">
          <span>{skip + 1}–{Math.min(skip + LIMIT, total)} de {total}</span>
          <div className="flex gap-2">
            <button disabled={skip === 0} onClick={() => setSkip(s => Math.max(0, s - LIMIT))}
              className="px-3 py-1 bg-gray-100 dark:bg-white/5 rounded disabled:opacity-40 hover:bg-gray-200 dark:hover:bg-white/10">← Anterior</button>
            <button disabled={skip + LIMIT >= total} onClick={() => setSkip(s => s + LIMIT)}
              className="px-3 py-1 bg-gray-100 dark:bg-white/5 rounded disabled:opacity-40 hover:bg-gray-200 dark:hover:bg-white/10">Siguiente →</button>
          </div>
        </div>
      )}

      {/* Create / Edit modal */}
      {isFormOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4"
          onClick={e => e.target === e.currentTarget && (setShowForm(false), setEditingGasto(null))}>
          <div className="bg-[#16161A] border border-white/10 rounded-xl p-5 w-full max-w-md space-y-4">
            <div className="flex items-center justify-between">
              <h2 className="text-base font-semibold text-gray-100">{editingGasto ? 'Editar gasto' : 'Registrar gasto'}</h2>
              <button onClick={() => { setShowForm(false); setEditingGasto(null) }} className="text-gray-500 hover:text-gray-300 text-xl leading-none">×</button>
            </div>
            {msg && <p className="text-xs text-red-400">{msg}</p>}
            <p className="text-xs text-gray-500">Asiento: Gastos (D) / {form.medio === 'banco' ? 'Banco' : 'Efectivo'} (H)</p>
            <div className="grid grid-cols-2 gap-3">
              <div className="col-span-2">
                <label className="block text-xs text-gray-400 mb-1">Concepto *</label>
                <input type="text" value={form.concepto} onChange={e => setForm(f => ({ ...f, concepto: e.target.value }))} className={inputClass} />
              </div>
              <div>
                <label className="block text-xs text-gray-400 mb-1">Categoría</label>
                <select value={form.categoria} onChange={e => setForm(f => ({ ...f, categoria: e.target.value }))} className={inputClass}>
                  <option value="">Sin categoría</option>
                  <option value="impuestos">Impuestos déb/créd</option>
                  <option value="bancarios">Gastos bancarios</option>
                  <option value="otros">Otros</option>
                </select>
              </div>
              <div>
                <label className="block text-xs text-gray-400 mb-1">Medio</label>
                <select value={form.medio} onChange={e => setForm(f => ({ ...f, medio: e.target.value }))} className={inputClass}>
                  <option value="banco">Banco</option>
                  <option value="efectivo">Efectivo</option>
                </select>
              </div>
              <div>
                <label className="block text-xs text-gray-400 mb-1">Monto *</label>
                <input type="number" value={form.monto} onChange={e => setForm(f => ({ ...f, monto: e.target.value }))} className={inputClass} />
              </div>
              <div>
                <label className="block text-xs text-gray-400 mb-1">Fecha</label>
                <input type="date" value={form.fecha} onChange={e => setForm(f => ({ ...f, fecha: e.target.value }))} className={inputClass} />
              </div>
              <div className="col-span-2">
                <label className="block text-xs text-gray-400 mb-1">Referencia / comprobante</label>
                <input type="text" value={form.referencia} onChange={e => setForm(f => ({ ...f, referencia: e.target.value }))} className={inputClass} />
              </div>
              <div className="col-span-2">
                <label className="block text-xs text-gray-400 mb-1">Notas</label>
                <textarea rows={2} value={form.notas} onChange={e => setForm(f => ({ ...f, notas: e.target.value }))}
                  className="w-full bg-white/5 border border-white/10 rounded px-3 py-1.5 text-sm text-gray-100 focus:outline-none focus:border-indigo-500 resize-none" />
              </div>
            </div>
            <div className="flex justify-end gap-2 pt-2">
              <button onClick={() => { setShowForm(false); setEditingGasto(null) }} className="px-4 py-1.5 text-sm text-gray-400 hover:text-gray-200">Cancelar</button>
              <button onClick={editingGasto ? handleUpdate : handleCreate} disabled={saving}
                className="px-4 py-1.5 bg-indigo-600 hover:bg-indigo-500 text-white text-sm rounded-lg disabled:opacity-50 transition-colors">
                {saving ? 'Guardando…' : editingGasto ? 'Guardar cambios' : 'Guardar'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

// ── Página principal ─────────────────────────────────────────────

export const PagosGastos: React.FC = () => {
  const [searchParams, setSearchParams] = useSearchParams()
  const compartido = searchParams.get('compartido')
  const [tab, setTab]           = useState<'pagos' | 'gastos'>(
    compartido === 'gasto' ? 'gastos' : 'pagos'
  )
  const [clientes, setClientes] = useState<ClienteOpt[]>([])
  const { hasPermission }       = useAuthStore()
  const canEdit                 = hasPermission('manage_users')

  useEffect(() => {
    apiClient.client.get('/clientes/archivos').then(r => {
      const orgs: any[] = r.data?.organizaciones || []
      const list: ClienteOpt[] = []
      orgs.forEach(org => (org.clientes || []).forEach((c: any) => list.push({ id: c.id, nombre: c.nombre })))
      setClientes(list)
    }).catch(() => {})
  }, [])

  // Si vino por share target, limpiar el query (los archivos no se persisten
  // aca, pero el tab ya se selecciono). El sessionStorage se limpia al cancelar.
  useEffect(() => {
    if (!compartido) return
    const sp = new URLSearchParams(searchParams)
    sp.delete('compartido')
    setSearchParams(sp, { replace: true })
  }, [])

  return (
    <div className="p-4 md:p-6 max-w-7xl mx-auto space-y-5">
      <div>
        <h1 className="text-xl font-semibold text-gray-800 dark:text-gray-100">Pagos y Gastos</h1>
        <p className="text-xs text-gray-500 mt-0.5">Registro contable de pagos a clientes y gastos operativos</p>
      </div>

      {/* Tabs */}
      <div className="flex gap-1 bg-gray-100 dark:bg-white/4 p-1 rounded-lg w-fit">
        {(['pagos', 'gastos'] as const).map(t => (
          <button key={t} onClick={() => setTab(t)}
            className={`px-4 py-1.5 text-sm rounded-md transition-colors capitalize ${
              tab === t ? 'bg-white dark:bg-white/10 text-gray-800 dark:text-gray-100 shadow-sm' : 'text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-200'
            }`}>
            {t === 'pagos' ? 'Pagos a clientes' : 'Gastos operativos'}
          </button>
        ))}
      </div>

      {tab === 'pagos'
        ? <PagosTab clientes={clientes} canEdit={canEdit} />
        : <GastosTab canEdit={canEdit} />}
    </div>
  )
}
