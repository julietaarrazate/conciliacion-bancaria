import React, { useEffect, useRef, useState, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import { apiClient } from '@/services/api'

interface SearchResult {
  clientes: { id: number; nombre: string }[]
  planillas: { id: number; cliente: string; archivo: string; fecha: string | null }[]
  movimientos: { id: number; titular: string; monto: number; fecha: string | null; extracto_id: number }[]
  cheques: { id: number; numero: string | null; emisor: string; monto: number }[]
}

interface Props {
  open: boolean
  onClose: () => void
}

const fmtARS = (n: number) =>
  new Intl.NumberFormat('es-AR', { style: 'currency', currency: 'ARS', maximumFractionDigits: 0 }).format(n)

export const SearchModal: React.FC<Props> = ({ open, onClose }) => {
  const navigate = useNavigate()
  const inputRef = useRef<HTMLInputElement>(null)
  const [q, setQ] = useState('')
  const [results, setResults] = useState<SearchResult | null>(null)
  const [loading, setLoading] = useState(false)
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  useEffect(() => {
    if (open) {
      setQ(''); setResults(null)
      setTimeout(() => inputRef.current?.focus(), 50)
    }
  }, [open])

  const doSearch = useCallback(async (query: string) => {
    if (query.length < 2) { setResults(null); return }
    setLoading(true)
    try {
      const res = await apiClient.client.get('/search', { params: { q: query } })
      setResults(res.data)
    } catch { /* ignore */ }
    finally { setLoading(false) }
  }, [])

  useEffect(() => {
    if (timerRef.current) clearTimeout(timerRef.current)
    timerRef.current = setTimeout(() => doSearch(q), 300)
    return () => { if (timerRef.current) clearTimeout(timerRef.current) }
  }, [q, doSearch])

  const go = (path: string) => { navigate(path); onClose() }

  const hasResults = results && (
    results.clientes.length + results.planillas.length +
    results.movimientos.length + results.cheques.length > 0
  )

  if (!open) return null

  return (
    <>
      <div className="fixed inset-0 bg-black/50 z-[200]" onClick={onClose} />
      <div className="fixed top-20 left-1/2 -translate-x-1/2 w-full max-w-lg z-[201] px-4">
        <div className="bg-white dark:bg-[#1C1C24] rounded-xl shadow-2xl border border-gray-200 dark:border-white/10 overflow-hidden">
          {/* Input */}
          <div className="flex items-center gap-3 px-4 py-3 border-b border-gray-100 dark:border-white/10">
            <svg className="w-4 h-4 text-gray-400 shrink-0" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" d="M21 21l-5.197-5.197m0 0A7.5 7.5 0 105.196 15.803a7.5 7.5 0 0010.607 10.607z"/>
            </svg>
            <input
              ref={inputRef}
              type="text"
              value={q}
              onChange={e => setQ(e.target.value)}
              placeholder="Buscar clientes, planillas, movimientos..."
              className="flex-1 text-sm bg-transparent text-gray-900 dark:text-white placeholder-gray-400 focus:outline-none"
              onKeyDown={e => e.key === 'Escape' && onClose()}
            />
            {loading && <span className="text-xs text-gray-400 animate-pulse">...</span>}
            <kbd className="text-[10px] text-gray-400 bg-gray-100 dark:bg-white/10 px-1.5 py-0.5 rounded font-mono">ESC</kbd>
          </div>

          {/* Results */}
          {hasResults ? (
            <div className="max-h-80 overflow-y-auto py-2">
              {results!.clientes.length > 0 && (
                <div>
                  <p className="px-4 py-1 text-[10px] font-semibold uppercase tracking-widest text-gray-400 dark:text-gray-500">Clientes</p>
                  {results!.clientes.map(c => (
                    <button key={c.id} onClick={() => go(`/clientes`)}
                      className="w-full flex items-center gap-3 px-4 py-2 hover:bg-gray-50 dark:hover:bg-white/5 text-left">
                      <span className="text-gray-400">👤</span>
                      <span className="text-sm text-gray-900 dark:text-white">{c.nombre}</span>
                    </button>
                  ))}
                </div>
              )}
              {results!.planillas.length > 0 && (
                <div>
                  <p className="px-4 py-1 text-[10px] font-semibold uppercase tracking-widest text-gray-400 dark:text-gray-500">Planillas</p>
                  {results!.planillas.map(p => (
                    <button key={p.id} onClick={() => go(`/historial`)}
                      className="w-full flex items-center gap-3 px-4 py-2 hover:bg-gray-50 dark:hover:bg-white/5 text-left">
                      <span className="text-gray-400">📄</span>
                      <div className="flex-1 min-w-0">
                        <span className="text-sm text-gray-900 dark:text-white">{p.cliente}</span>
                        <span className="text-xs text-gray-400 ml-2">{p.fecha}</span>
                      </div>
                    </button>
                  ))}
                </div>
              )}
              {results!.movimientos.length > 0 && (
                <div>
                  <p className="px-4 py-1 text-[10px] font-semibold uppercase tracking-widest text-gray-400 dark:text-gray-500">Movimientos</p>
                  {results!.movimientos.map(m => (
                    <button key={m.id} onClick={() => go(`/movimientos?extracto=${m.extracto_id}`)}
                      className="w-full flex items-center gap-3 px-4 py-2 hover:bg-gray-50 dark:hover:bg-white/5 text-left">
                      <span className="text-gray-400">💳</span>
                      <div className="flex-1 min-w-0">
                        <span className="text-sm text-gray-900 dark:text-white truncate block">{m.titular}</span>
                      </div>
                      <span className="text-xs text-gray-500 dark:text-gray-400 font-mono whitespace-nowrap">{fmtARS(m.monto)}</span>
                    </button>
                  ))}
                </div>
              )}
              {results!.cheques.length > 0 && (
                <div>
                  <p className="px-4 py-1 text-[10px] font-semibold uppercase tracking-widest text-gray-400 dark:text-gray-500">Cheques</p>
                  {results!.cheques.map(c => (
                    <button key={c.id} onClick={() => go('/cheques')}
                      className="w-full flex items-center gap-3 px-4 py-2 hover:bg-gray-50 dark:hover:bg-white/5 text-left">
                      <span className="text-gray-400">🏦</span>
                      <span className="text-sm text-gray-900 dark:text-white">{c.emisor}</span>
                      <span className="text-xs text-gray-500 dark:text-gray-400 ml-auto font-mono">{fmtARS(c.monto)}</span>
                    </button>
                  ))}
                </div>
              )}
            </div>
          ) : q.length >= 2 && !loading ? (
            <p className="px-4 py-6 text-sm text-center text-gray-400">Sin resultados para "{q}"</p>
          ) : q.length === 0 ? (
            <p className="px-4 py-4 text-xs text-center text-gray-400">Escribí para buscar en clientes, planillas y movimientos</p>
          ) : null}
        </div>
      </div>
    </>
  )
}
