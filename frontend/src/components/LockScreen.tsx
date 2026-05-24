import React, { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useLockStore } from '@/store/lock'
import { useAuthStore } from '@/store/auth'
import { CuadraLogo } from './CuadraLogo'

const PIN_LEN = 4
const MAX_ATTEMPTS = 5

export const LockScreen: React.FC = () => {
  const unlock = useLockStore(s => s.unlock)
  const biometricEnabled = useLockStore(s => s.biometricEnabled)
  const unlockBiometric = useLockStore(s => s.unlockBiometric)
  const logout = useAuthStore(s => s.logout)
  const user = useAuthStore(s => s.user)
  const navigate = useNavigate()
  const [pin, setPin] = useState('')
  const [shake, setShake] = useState(false)
  const [attempts, setAttempts] = useState(0)
  const [checking, setChecking] = useState(false)
  const [bioTried, setBioTried] = useState(false)
  const [bioRunning, setBioRunning] = useState(false)

  // Auto-prompt biometric al abrir el lock screen (una sola vez)
  useEffect(() => {
    if (!biometricEnabled || bioTried) return
    setBioTried(true)
    setBioRunning(true)
    unlockBiometric().finally(() => setBioRunning(false))
  }, [biometricEnabled, bioTried, unlockBiometric])

  const tryBiometric = async () => {
    if (bioRunning) return
    setBioRunning(true)
    await unlockBiometric()
    setBioRunning(false)
  }

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

        {biometricEnabled && (
          <button
            onClick={tryBiometric}
            disabled={bioRunning}
            className="mx-auto flex flex-col items-center gap-1.5 text-ml-text-soft dark:text-zinc-500 hover:text-ml-blue dark:hover:text-ml-green disabled:opacity-50 transition-colors group"
          >
            <span className="w-14 h-14 rounded-full border-2 border-current flex items-center justify-center group-active:scale-95 transition-transform">
              <svg className="w-7 h-7" fill="none" stroke="currentColor" strokeWidth={1.6} viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" d="M7.864 4.243A7.973 7.973 0 0112 3c2.21 0 4.21.895 5.657 2.343M3.873 9A8.97 8.97 0 003 12.001c0 1.652.42 3.206 1.157 4.563M7 21l3-3m4 3l-3-3m-2.5-7.5a3.5 3.5 0 117 0c0 2.485-1.5 5.5-3.5 7.5" />
              </svg>
            </span>
            <span className="text-[11px] font-medium">
              {bioRunning ? 'Esperando…' : 'Usar biometría'}
            </span>
          </button>
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
