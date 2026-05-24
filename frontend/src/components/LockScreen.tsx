import React, { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useLockStore } from '@/store/lock'
import { useAuthStore } from '@/store/auth'
import { CuadraLogo } from './CuadraLogo'

const PIN_LEN = 4
const MAX_ATTEMPTS = 5

export const LockScreen: React.FC = () => {
  const unlock = useLockStore(s => s.unlock)
  const logout = useAuthStore(s => s.logout)
  const user = useAuthStore(s => s.user)
  const navigate = useNavigate()
  const [pin, setPin] = useState('')
  const [shake, setShake] = useState(false)
  const [attempts, setAttempts] = useState(0)
  const [checking, setChecking] = useState(false)

  useEffect(() => {
    if (pin.length !== PIN_LEN || checking) return
    setChecking(true)
    unlock(pin).then(ok => {
      if (ok) {
        setPin('')
        setAttempts(0)
      } else {
        setShake(true)
        setTimeout(() => setShake(false), 400)
        setPin('')
        const next = attempts + 1
        setAttempts(next)
        if (next >= MAX_ATTEMPTS) {
          logout()
          navigate('/login')
        }
      }
    }).finally(() => setChecking(false))
  }, [pin])

  const press = (n: string) => {
    if (pin.length < PIN_LEN && !checking) setPin(p => p + n)
  }
  const backspace = () => setPin(p => p.slice(0, -1))

  const olvide = () => {
    if (confirm('Vas a tener que iniciar sesión de nuevo con email y contraseña. ¿Continuar?')) {
      logout()
      navigate('/login')
    }
  }

  return (
    <div className="fixed inset-0 z-[200] bg-ml-gray-bg dark:bg-ml-dark-bg flex flex-col items-center justify-center px-6 select-none">
      <div className="w-full max-w-xs space-y-8">
        <div className="text-center space-y-3">
          <div className="flex justify-center">
            <CuadraLogo size={64} animate={false} />
          </div>
          <h1 className="text-2xl font-bold dark:text-white font-mono">Cuadra</h1>
          {user && (
            <p className="text-xs text-ml-text-soft dark:text-zinc-500 truncate font-mono">
              {user.email}
            </p>
          )}
          <p className="text-sm text-ml-text-soft dark:text-zinc-400 pt-1">Ingresá tu PIN</p>
        </div>

        <div className={`flex justify-center gap-4 ${shake ? 'animate-shake' : ''}`}>
          {Array.from({ length: PIN_LEN }).map((_, i) => (
            <div
              key={i}
              className={`w-3.5 h-3.5 rounded-full border-2 transition-all ${
                pin.length > i
                  ? 'bg-ml-blue border-ml-blue dark:bg-ml-green dark:border-ml-green scale-110'
                  : 'border-gray-300 dark:border-zinc-700'
              }`}
            />
          ))}
        </div>

        {attempts > 0 && (
          <p className="text-center text-xs text-red-500 dark:text-red-400 -mt-4">
            PIN incorrecto · {MAX_ATTEMPTS - attempts} intento{MAX_ATTEMPTS - attempts !== 1 ? 's' : ''} restante{MAX_ATTEMPTS - attempts !== 1 ? 's' : ''}
          </p>
        )}

        <div className="grid grid-cols-3 gap-3 max-w-[260px] mx-auto">
          {[1, 2, 3, 4, 5, 6, 7, 8, 9].map(n => (
            <button
              key={n}
              onClick={() => press(String(n))}
              className="aspect-square rounded-full bg-white dark:bg-ml-dark-card text-2xl font-light dark:text-white border border-gray-200 dark:border-ml-dark-border hover:bg-gray-50 dark:hover:bg-ml-dark-hover active:scale-90 transition-transform"
            >
              {n}
            </button>
          ))}
          <div />
          <button
            onClick={() => press('0')}
            className="aspect-square rounded-full bg-white dark:bg-ml-dark-card text-2xl font-light dark:text-white border border-gray-200 dark:border-ml-dark-border hover:bg-gray-50 dark:hover:bg-ml-dark-hover active:scale-90 transition-transform"
          >
            0
          </button>
          <button
            onClick={backspace}
            disabled={pin.length === 0}
            className="aspect-square rounded-full text-xl text-ml-text-soft dark:text-zinc-500 hover:text-ml-text dark:hover:text-white disabled:opacity-30 active:scale-90 transition-transform"
          >
            ⌫
          </button>
        </div>

        <button
          onClick={olvide}
          className="block mx-auto text-xs text-ml-text-soft dark:text-zinc-500 hover:text-ml-text dark:hover:text-ml-green transition-colors"
        >
          ¿Olvidaste tu PIN?
        </button>
      </div>
    </div>
  )
}
