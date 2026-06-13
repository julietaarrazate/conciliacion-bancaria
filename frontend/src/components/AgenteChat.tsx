import React, { useState, useRef, useEffect } from 'react'
import { apiClient } from '@/services/api'
import { CuadraLogo } from '@/components/CuadraLogo'

interface Mensaje {
  rol: 'user' | 'agente'
  texto: string
}

const MicIcon = () => (
  <svg className="w-4 h-4" fill="none" stroke="currentColor" strokeWidth={1.8} viewBox="0 0 24 24">
    <path strokeLinecap="round" strokeLinejoin="round" d="M12 18.75a6 6 0 006-6v-1.5m-6 7.5a6 6 0 01-6-6v-1.5m6 7.5v3.75m-3.75 0h7.5M12 15.75a3 3 0 01-3-3V4.5a3 3 0 116 0v8.25a3 3 0 01-3 3z"/>
  </svg>
)

const SendIcon = () => (
  <svg className="w-4 h-4" fill="none" stroke="currentColor" strokeWidth={1.8} viewBox="0 0 24 24">
    <path strokeLinecap="round" strokeLinejoin="round" d="M6 12L3.269 3.126A59.768 59.768 0 0121.485 12 59.77 59.77 0 013.27 20.876L5.999 12zm0 0h7.5"/>
  </svg>
)

const CloseIcon = () => (
  <svg className="w-4 h-4" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
    <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12"/>
  </svg>
)

const SUGERENCIAS = [
  '¿Cuánto pagó Green este mes?',
  '¿Qué cheques tenemos pendientes?',
  '¿Cuál es el saldo de caja hoy?',
  'Resumen financiero de mayo',
]

export function AgenteChat() {
  const [abierto, setAbierto]       = useState(false)
  const [mensajes, setMensajes]     = useState<Mensaje[]>([])
  const [input, setInput]           = useState('')
  const [cargando, setCargando]     = useState(false)
  const [escuchando, setEscuchando] = useState(false)
  const [visible, setVisible]       = useState(true)
  const bottomRef                   = useRef<HTMLDivElement>(null)
  const inputRef                    = useRef<HTMLInputElement>(null)
  const recognitionRef              = useRef<{ stop(): void } | null>(null)
  const lastScrollY                 = useRef(0)
  const hideTimer                   = useRef<number | null>(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [mensajes, cargando])

  useEffect(() => {
    if (abierto) setTimeout(() => inputRef.current?.focus(), 100)
  }, [abierto])

  // Auto-hide FAB while scrolling down; re-show when scrolling up or stopped
  useEffect(() => {
    if (abierto) return  // keep visible when chat is open
    const handleScroll = () => {
      const currentY = window.scrollY
      if (currentY > lastScrollY.current + 8) {
        setVisible(false)
      } else if (currentY < lastScrollY.current - 4) {
        setVisible(true)
      }
      lastScrollY.current = currentY

      if (hideTimer.current) window.clearTimeout(hideTimer.current)
      hideTimer.current = window.setTimeout(() => setVisible(true), 1200)
    }
    window.addEventListener('scroll', handleScroll, { passive: true })
    return () => {
      window.removeEventListener('scroll', handleScroll)
      if (hideTimer.current) window.clearTimeout(hideTimer.current)
    }
  }, [abierto])

  const enviar = async (texto: string) => {
    const msg = texto.trim()
    if (!msg || cargando) return
    setInput('')
    setMensajes(m => [...m, { rol: 'user', texto: msg }])
    setCargando(true)
    try {
      const res = await apiClient.client.post('/agente/chat', { mensaje: msg })
      setMensajes(m => [...m, { rol: 'agente', texto: res.data.respuesta }])
    } catch (e) {
      const err = e as { response?: { data?: { detail?: string } } }
      const detalle = err?.response?.data?.detail || 'Error al conectar con el agente'
      setMensajes(m => [...m, { rol: 'agente', texto: `⚠️ ${detalle}` }])
    } finally {
      setCargando(false)
    }
  }

  const toggleMic = () => {
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition
    if (!SpeechRecognition) {
      alert('Tu navegador no soporta dictado por voz. Usá Chrome en Android.')
      return
    }
    if (escuchando) {
      recognitionRef.current?.stop()
      setEscuchando(false)
      return
    }
    const r = new SpeechRecognition()
    r.lang = 'es-AR'
    r.continuous = false
    r.interimResults = false
    r.onresult = (e: SpeechRecognitionEvent) => {
      const texto = e.results[0][0].transcript
      setInput(texto)
      setEscuchando(false)
    }
    r.onerror = () => setEscuchando(false)
    r.onend = () => setEscuchando(false)
    recognitionRef.current = r
    r.start()
    setEscuchando(true)
  }

  const hasSpeech = typeof window !== 'undefined' && (
    !!(window.SpeechRecognition) || !!(window.webkitSpeechRecognition)
  )

  return (
    <>
      {/* Botón flotante */}
      <button
        onClick={() => { setAbierto(o => !o); setVisible(true) }}
        className={`fixed bottom-20 right-4 z-40 md:bottom-6 w-10 h-10 rounded-full shadow-lg overflow-hidden flex items-center justify-center transition-all duration-300 hover:scale-105 ${visible || abierto ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-4 pointer-events-none'}`}
        title="Asistente IA"
      >
        {abierto
          ? <div className="w-10 h-10 rounded-full bg-[#5E6AD2] flex items-center justify-center text-white"><CloseIcon /></div>
          : <CuadraLogo size={40} animate={false} />
        }
      </button>

      {/* Panel de chat */}
      {abierto && (
        <div className="fixed bottom-36 right-4 z-40 md:bottom-20 w-[calc(100vw-2rem)] max-w-sm bg-[#13131A] border border-white/10 rounded-2xl shadow-2xl flex flex-col overflow-hidden"
          style={{ height: '420px' }}>

          {/* Header */}
          <div className="flex items-center gap-2 px-4 py-3 border-b border-white/10 bg-[#5E6AD2]/10">
            <CuadraLogo size={28} animate={false} />
            <div className="flex-1">
              <p className="text-sm font-semibold text-gray-100">Asistente Cuadra</p>
              <p className="text-xs text-gray-500">IA Cuadra · datos en tiempo real</p>
            </div>
            {mensajes.length > 0 && (
              <button onClick={() => setMensajes([])} className="text-xs text-gray-500 hover:text-gray-300">
                Limpiar
              </button>
            )}
          </div>

          {/* Mensajes */}
          <div className="flex-1 overflow-y-auto p-3 space-y-3">
            {mensajes.length === 0 && (
              <div className="space-y-2">
                <p className="text-xs text-gray-500 text-center pt-2">Preguntame sobre tus datos financieros</p>
                {SUGERENCIAS.map(s => (
                  <button key={s} onClick={() => enviar(s)}
                    className="w-full text-left text-xs px-3 py-2 rounded-lg bg-white/5 hover:bg-white/10 text-gray-400 hover:text-gray-200 transition-colors">
                    {s}
                  </button>
                ))}
              </div>
            )}

            {mensajes.map((m, i) => (
              <div key={i} className={`flex ${m.rol === 'user' ? 'justify-end' : 'justify-start'}`}>
                <div className={`max-w-[85%] px-3 py-2 rounded-xl text-sm break-words ${
                  m.rol === 'user'
                    ? 'bg-[#5E6AD2] text-white rounded-br-sm'
                    : 'bg-white/8 text-gray-200 rounded-bl-sm'
                }`}>
                  {m.texto}
                </div>
              </div>
            ))}

            {cargando && (
              <div className="flex justify-start">
                <div className="bg-white/8 px-3 py-2 rounded-xl rounded-bl-sm">
                  <div className="flex gap-1">
                    <span className="w-1.5 h-1.5 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '0ms' }} />
                    <span className="w-1.5 h-1.5 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '150ms' }} />
                    <span className="w-1.5 h-1.5 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '300ms' }} />
                  </div>
                </div>
              </div>
            )}
            <div ref={bottomRef} />
          </div>

          {/* Input */}
          <div className="border-t border-white/10 p-3 flex gap-2">
            {hasSpeech && (
              <button onClick={toggleMic}
                className={`p-2 rounded-lg transition-colors flex-shrink-0 ${escuchando ? 'bg-red-500/20 text-red-400 animate-pulse' : 'bg-white/5 hover:bg-white/10 text-gray-400'}`}
                title="Dictado por voz">
                <MicIcon />
              </button>
            )}
            <input
              ref={inputRef}
              value={input}
              onChange={e => setInput(e.target.value)}
              onKeyDown={e => e.key === 'Enter' && !e.shiftKey && enviar(input)}
              placeholder={escuchando ? 'Escuchando…' : 'Preguntá algo…'}
              className="flex-1 bg-white/5 border border-white/10 rounded-lg px-3 py-2 text-sm text-gray-200 placeholder-gray-600 focus:outline-none focus:border-[#5E6AD2]/50 min-w-0"
            />
            <button
              onClick={() => enviar(input)}
              disabled={!input.trim() || cargando}
              className="p-2 rounded-lg bg-[#5E6AD2] hover:bg-[#4f5bbf] disabled:opacity-40 text-white flex-shrink-0 transition-colors">
              <SendIcon />
            </button>
          </div>
        </div>
      )}
    </>
  )
}
