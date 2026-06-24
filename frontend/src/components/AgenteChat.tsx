import { useState, useRef, useEffect } from 'react'
import { apiClient } from '@/services/api'
import { CuadraLogo } from '@/components/CuadraLogo'
import { toast } from '@/store/toast'

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

// Elige el mejor mimeType soportado por el browser para MediaRecorder
function elegirMimeType(): string | undefined {
  const candidatos = ['audio/webm', 'audio/mp4', 'audio/ogg']
  for (const t of candidatos) {
    if (typeof MediaRecorder !== 'undefined' && MediaRecorder.isTypeSupported(t)) return t
  }
  return undefined // deja que el browser elija el default
}

export function AgenteChat() {
  const [abierto, setAbierto]           = useState(false)
  const [mensajes, setMensajes]         = useState<Mensaje[]>([])
  const [input, setInput]               = useState('')
  const [cargando, setCargando]         = useState(false)
  const [escuchando, setEscuchando]     = useState(false)
  const [transcribiendo, setTranscribiendo] = useState(false)
  const [visible, setVisible]           = useState(true)
  const [saludoListo, setSaludoListo]   = useState(false)
  const saludoIntentado                 = useRef(false)
  const bottomRef                       = useRef<HTMLDivElement>(null)
  const inputRef                        = useRef<HTMLInputElement>(null)
  const recognitionRef                  = useRef<{ stop(): void } | null>(null)
  const mediaRecorderRef                = useRef<MediaRecorder | null>(null)
  const chunksRef                       = useRef<Blob[]>([])
  const lastScrollY                     = useRef(0)
  const hideTimer                       = useRef<number | null>(null)

  // true si SpeechRecognition nativa está disponible (Chrome Android / desktop)
  const hasSpeech = typeof window !== 'undefined' && (
    !!(window.SpeechRecognition) || !!(window.webkitSpeechRecognition)
  )

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [mensajes, cargando])

  useEffect(() => {
    if (abierto) setTimeout(() => inputRef.current?.focus(), 100)
  }, [abierto])

  // Al abrir el chat por primera vez, pedimos un pantallazo proactivo en vez
  // de esperar a que el usuario pregunte algo (alertas + resumen del día).
  useEffect(() => {
    if (!abierto || saludoIntentado.current) return
    saludoIntentado.current = true
    setSaludoListo(false)
    apiClient.client.get('/agente/saludo-proactivo')
      .then(res => {
        const texto = res.data?.respuesta
        if (texto) setMensajes(m => [...m, { rol: 'agente', texto }])
      })
      .catch(() => { /* silencioso: si falla, quedan las sugerencias fijas */ })
      .finally(() => setSaludoListo(true))
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

  // Parte A: SpeechRecognition con feedback de errores
  const toggleSpeechRecognition = () => {
    const SR = window.SpeechRecognition || window.webkitSpeechRecognition
    if (escuchando) {
      recognitionRef.current?.stop()
      setEscuchando(false)
      return
    }
    if (!SR) return
    const r = new SR()
    r.lang = 'es-AR'
    r.continuous = false
    r.interimResults = false
    r.onresult = (e: SpeechRecognitionEvent) => {
      const texto = e.results[0][0].transcript
      setInput(texto)
      setEscuchando(false)
    }
    // onerror type varies between browsers; cast to accept the error event
    ;(r as unknown as { onerror: (e: { error?: string }) => void }).onerror = (e) => {
      setEscuchando(false)
      switch (e.error) {
        case 'not-allowed':
        case 'service-not-allowed':
          toast.error('Permiso de micrófono denegado. Activalo en los ajustes del navegador.')
          break
        case 'no-speech':
          toast.warn('No se detectó voz. Intentá de nuevo.')
          break
        case 'audio-capture':
          toast.error('No se encontró micrófono.')
          break
        default:
          toast.error('No se pudo usar el micrófono.')
      }
    }
    r.onend = () => setEscuchando(false)
    recognitionRef.current = r
    r.start()
    setEscuchando(true)
  }

  // Parte B: MediaRecorder (fallback para iOS y cualquier browser sin SpeechRecognition)
  const toggleMediaRecorder = async () => {
    // Si ya está grabando, detener y subir
    if (escuchando && mediaRecorderRef.current) {
      mediaRecorderRef.current.stop()
      return
    }

    let stream: MediaStream
    try {
      stream = await navigator.mediaDevices.getUserMedia({ audio: true })
    } catch {
      toast.error('Permiso de micrófono denegado. Activalo en los ajustes del navegador.')
      return
    }

    const mimeType = elegirMimeType()
    const rec = new MediaRecorder(stream, mimeType ? { mimeType } : undefined)
    chunksRef.current = []

    rec.ondataavailable = (e: BlobEvent) => {
      if (e.data.size > 0) chunksRef.current.push(e.data)
    }

    rec.onstop = async () => {
      // Cortar el stream de inmediato para apagar el indicador de micrófono del sistema
      stream.getTracks().forEach(t => t.stop())
      setEscuchando(false)

      const blob = new Blob(chunksRef.current, { type: rec.mimeType || 'audio/webm' })
      chunksRef.current = []

      if (blob.size === 0) {
        toast.warn('No se grabó audio. Intentá de nuevo.')
        return
      }

      setTranscribiendo(true)
      try {
        const fd = new FormData()
        // Extender la extensión según el mimeType real
        const ext = (rec.mimeType || 'audio/webm').includes('mp4') ? 'mp4'
          : (rec.mimeType || '').includes('ogg') ? 'ogg'
          : 'webm'
        fd.append('audio', blob, `audio.${ext}`)
        // NO setear Content-Type manualmente — axios lo maneja con el boundary correcto
        const res = await apiClient.client.post('/agente/transcribir', fd)
        const texto: string = res.data?.texto ?? ''
        if (texto.trim()) {
          setInput(texto)
        } else {
          toast.warn('No se entendió el audio, probá de nuevo.')
        }
      } catch (e) {
        const err = e as { response?: { data?: { detail?: string } } }
        toast.error(err.response?.data?.detail || 'No se pudo transcribir el audio.')
      } finally {
        setTranscribiendo(false)
      }
    }

    mediaRecorderRef.current = rec
    rec.start()
    setEscuchando(true)
  }

  // Decide qué flujo usar al tocar el botón de micrófono
  const toggleMic = () => {
    if (hasSpeech) {
      toggleSpeechRecognition()
    } else {
      void toggleMediaRecorder()
    }
  }

  // Placeholder dinámico según estado
  const placeholder = transcribiendo
    ? 'Transcribiendo…'
    : escuchando
      ? 'Escuchando…'
      : 'Preguntá algo…'

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
            {mensajes.length === 0 && !saludoListo && (
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

            {!mensajes.some(m => m.rol === 'user') && saludoListo && (
              <div className="space-y-2">
                {mensajes.length === 0 && (
                  <p className="text-xs text-gray-500 text-center pt-2">Preguntame sobre tus datos financieros</p>
                )}
                {SUGERENCIAS.map(s => (
                  <button key={s} onClick={() => enviar(s)}
                    className="w-full text-left text-xs px-3 py-2 rounded-lg bg-white/5 hover:bg-white/10 text-gray-400 hover:text-gray-200 transition-colors">
                    {s}
                  </button>
                ))}
              </div>
            )}

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
            {/* Botón de micrófono: SIEMPRE visible (funciona en iOS via MediaRecorder) */}
            <button
              onClick={toggleMic}
              disabled={transcribiendo}
              className={`p-2 rounded-lg transition-colors flex-shrink-0 ${
                transcribiendo
                  ? 'bg-[#5E6AD2]/20 text-[#5E6AD2] opacity-60 cursor-not-allowed'
                  : escuchando
                    ? 'bg-red-500/20 text-red-400 animate-pulse'
                    : 'bg-white/5 hover:bg-white/10 text-gray-400'
              }`}
              title={transcribiendo ? 'Transcribiendo…' : escuchando ? 'Detener grabación' : 'Grabar audio'}>
              <MicIcon />
            </button>
            <input
              ref={inputRef}
              value={input}
              onChange={e => setInput(e.target.value)}
              onKeyDown={e => e.key === 'Enter' && !e.shiftKey && enviar(input)}
              placeholder={placeholder}
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
