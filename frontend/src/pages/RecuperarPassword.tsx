import React, { useState } from 'react'
import { Link } from 'react-router-dom'
import { apiClient } from '@/services/api'

export const RecuperarPassword: React.FC = () => {
  const [email, setEmail] = useState('')
  const [loading, setLoading] = useState(false)
  const [enviado, setEnviado] = useState(false)
  const [error, setError] = useState('')

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')
    setLoading(true)
    try {
      await apiClient.forgotPassword(email)
      setEnviado(true)
    } catch (err: any) {
      const code = err.response?.status
      if (code === 429) {
        setError('Demasiados pedidos. Esperá un rato antes de volver a intentar.')
      } else if (err.code === 'ERR_NETWORK' || !err.response) {
        setError('No se pudo conectar al servidor. Intentá de nuevo en un minuto.')
      } else {
        setError('Algo salió mal. Intentá de nuevo.')
      }
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen bg-ml-gray-bg dark:bg-ml-dark-bg flex items-center justify-center p-4">
      <div className="w-full max-w-sm">

        <div className="text-center mb-8">
          <div className="inline-flex items-center justify-center w-16 h-16 rounded-2xl bg-ml-yellow dark:bg-ml-dark-surface dark:border dark:border-ml-green/40 mb-4 dark:shadow-green-glow">
            <span className="text-2xl dark:hidden">🔑</span>
            <span className="text-2xl hidden dark:inline font-mono text-ml-green">$_</span>
          </div>
          <h1 className="text-2xl font-bold text-ml-text dark:text-white tracking-tight">
            Recuperar contraseña
          </h1>
          <p className="text-xs text-ml-text-soft dark:text-zinc-500 mt-1">
            Te mandamos un link por email
          </p>
        </div>

        <div className="bg-white dark:bg-ml-dark-surface rounded-2xl p-6 shadow-sm border border-gray-100 dark:border-ml-dark-border dark:shadow-none">

          {enviado ? (
            <div className="space-y-4">
              <div className="p-4 bg-emerald-50 border border-emerald-200 rounded-lg text-emerald-800 text-sm dark:bg-emerald-950/30 dark:border-emerald-800/40 dark:text-emerald-400">
                <div className="font-semibold mb-1">📬 Email enviado</div>
                Si <strong>{email}</strong> esta registrado, te va a llegar un link
                en los proximos minutos para elegir una nueva contraseña.
                Revisa tambien la carpeta de spam.
              </div>
              <p className="text-xs text-ml-text-soft dark:text-zinc-500 text-center">
                El link sirve por 1 hora.
              </p>
              <Link
                to="/login"
                className="btn-yellow w-full block text-center py-3"
              >
                Volver al login
              </Link>
            </div>
          ) : (
            <>
              {error && (
                <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded-lg text-red-700 text-sm dark:bg-red-950/40 dark:border-red-800/50 dark:text-red-400">
                  {error}
                </div>
              )}

              <p className="text-sm text-ml-text-soft dark:text-zinc-400 mb-4">
                Escribi tu email y te mandamos un link para elegir una nueva contraseña.
              </p>

              <form onSubmit={handleSubmit} className="space-y-4">
                <div>
                  <label className="label">Email</label>
                  <input
                    type="email"
                    className="input-field"
                    placeholder="tu@email.com"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    required
                    autoComplete="email"
                    inputMode="email"
                    autoFocus
                  />
                </div>

                <button
                  type="submit"
                  className="btn-yellow w-full mt-2 py-3 text-base"
                  disabled={loading || !email}
                >
                  {loading
                    ? <span className="font-mono tracking-widest">enviando...</span>
                    : 'Mandar link'}
                </button>
              </form>

              <div className="mt-6 text-center">
                <Link
                  to="/login"
                  className="text-xs text-ml-text-soft dark:text-zinc-500 hover:text-ml-text dark:hover:text-ml-green transition-colors"
                >
                  ← Volver al login
                </Link>
              </div>
            </>
          )}
        </div>

        <p className="text-center text-xs text-gray-400 dark:text-zinc-700 mt-6 font-mono">
          © 2026 Julieta Arrazate
        </p>
      </div>
    </div>
  )
}
