import React, { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'

interface SharedMeta {
  files: { key: string; name: string; type: string; size: number }[]
  title: string
  text: string
  ts: number
}

interface SharedFile {
  name: string
  type: string
  size: number
  dataUrl: string  // base64 data URL para mostrar y subir
}

const blobToDataUrl = (blob: Blob): Promise<string> =>
  new Promise((resolve, reject) => {
    const r = new FileReader()
    r.onload = () => resolve(r.result as string)
    r.onerror = reject
    r.readAsDataURL(blob)
  })

const fmtSize = (bytes: number) => {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

// Guarda los archivos compartidos en sessionStorage para que cada modulo
// destino los lea al abrirse y precargue el formulario con la foto.
const guardarParaDestino = (destino: string, files: SharedFile[], titulo: string, texto: string) => {
  sessionStorage.setItem('compartido:destino', destino)
  sessionStorage.setItem('compartido:archivos', JSON.stringify(files))
  sessionStorage.setItem('compartido:titulo', titulo || '')
  sessionStorage.setItem('compartido:texto',  texto  || '')
  sessionStorage.setItem('compartido:ts', String(Date.now()))
}

export const Compartir: React.FC = () => {
  const navigate = useNavigate()
  const [loading, setLoading] = useState(true)
  const [files, setFiles] = useState<SharedFile[]>([])
  const [titulo, setTitulo] = useState('')
  const [texto, setTexto] = useState('')
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    const cargar = async () => {
      try {
        const metaResp = await fetch('/__share__/meta', { cache: 'no-store' })
        if (!metaResp.ok) {
          setError('No encontramos nada para compartir. Probá enviar el archivo desde WhatsApp otra vez.')
          setLoading(false)
          return
        }
        const meta: SharedMeta = await metaResp.json()
        const archivos: SharedFile[] = []
        for (const f of meta.files) {
          const r = await fetch(f.key, { cache: 'no-store' })
          if (!r.ok) continue
          const blob = await r.blob()
          const dataUrl = await blobToDataUrl(blob)
          archivos.push({ name: f.name, type: f.type, size: f.size, dataUrl })
        }
        if (cancelled) return
        setFiles(archivos)
        setTitulo(meta.title || '')
        setTexto(meta.text || '')
        if (archivos.length === 0 && !meta.text && !meta.title) {
          setError('El archivo compartido llegó vacío.')
        }
      } catch (ex: any) {
        if (!cancelled) setError('Error leyendo el archivo compartido.')
      } finally {
        if (!cancelled) setLoading(false)
      }
    }
    cargar()
    return () => { cancelled = true }
  }, [])

  const irA = (destino: string, ruta: string) => {
    guardarParaDestino(destino, files, titulo, texto)
    navigate(ruta)
  }

  if (loading) {
    return (
      <div className="p-6">
        <div className="text-gray-400 text-sm">Cargando archivo compartido...</div>
      </div>
    )
  }

  return (
    <div className="p-4 sm:p-6 max-w-3xl mx-auto">
      <div className="mb-4">
        <h1 className="text-xl font-semibold text-gray-100">Compartido desde otra app</h1>
        <p className="text-sm text-gray-400 mt-1">
          Elegí qué hacer con {files.length === 1 ? 'este archivo' : `estos ${files.length} archivos`}.
        </p>
      </div>

      {error && (
        <div className="bg-red-500/15 border border-red-500/30 text-red-300 rounded p-3 text-sm mb-4">
          {error}
        </div>
      )}

      {(titulo || texto) && (
        <div className="bg-white/5 border border-white/10 rounded p-3 mb-4 text-sm">
          {titulo && <div className="text-gray-200 font-medium">{titulo}</div>}
          {texto  && <div className="text-gray-400 whitespace-pre-wrap mt-1">{texto}</div>}
        </div>
      )}

      {files.length > 0 && (
        <div className="grid grid-cols-2 sm:grid-cols-3 gap-3 mb-6">
          {files.map((f, idx) => (
            <div key={idx} className="bg-white/5 border border-white/10 rounded overflow-hidden">
              {f.type.startsWith('image/') ? (
                <img src={f.dataUrl} alt={f.name} className="w-full h-32 object-cover" />
              ) : (
                <div className="w-full h-32 flex items-center justify-center text-3xl bg-white/5">
                  {f.type === 'application/pdf' ? '📄' : '📎'}
                </div>
              )}
              <div className="px-2 py-1.5 text-[11px] text-gray-400">
                <div className="truncate text-gray-300">{f.name}</div>
                <div>{fmtSize(f.size)}</div>
              </div>
            </div>
          ))}
        </div>
      )}

      <div className="space-y-2">
        <div className="text-xs text-gray-400 uppercase tracking-wide mb-1">Cargar como</div>

        <button
          onClick={() => irA('cheque', '/cheques?compartido=1')}
          disabled={files.length === 0}
          className="w-full flex items-center justify-between bg-white/5 hover:bg-white/10 disabled:opacity-40 disabled:cursor-not-allowed border border-white/10 rounded px-4 py-3 text-left transition"
        >
          <span className="flex items-center gap-3">
            <span className="text-2xl">🧾</span>
            <span>
              <div className="text-gray-100 font-medium">Cheque</div>
              <div className="text-xs text-gray-400">Cargar nuevo cheque con esta foto</div>
            </span>
          </span>
          <span className="text-gray-500">→</span>
        </button>

        <button
          onClick={() => irA('acreditar', '/clientes?compartido=acreditar')}
          disabled={files.length === 0}
          className="w-full flex items-center justify-between bg-indigo-600/20 hover:bg-indigo-600/30 disabled:opacity-40 disabled:cursor-not-allowed border border-indigo-500/40 rounded px-4 py-3 text-left transition"
        >
          <span className="flex items-center gap-3">
            <span className="text-2xl">💸</span>
            <span>
              <div className="text-indigo-200 font-medium">Acreditar en extracto</div>
              <div className="text-xs text-indigo-300/70">Comprobante de transferencia de cliente</div>
            </span>
          </span>
          <span className="text-indigo-400">→</span>
        </button>

        <button
          onClick={() => irA('pago', '/pagos-gastos?compartido=pago')}
          disabled={files.length === 0}
          className="w-full flex items-center justify-between bg-white/5 hover:bg-white/10 disabled:opacity-40 disabled:cursor-not-allowed border border-white/10 rounded px-4 py-3 text-left transition"
        >
          <span className="flex items-center gap-3">
            <span className="text-2xl">💸</span>
            <span>
              <div className="text-gray-100 font-medium">Pago</div>
              <div className="text-xs text-gray-400">Registrar pago recibido</div>
            </span>
          </span>
          <span className="text-gray-500">→</span>
        </button>

        <button
          onClick={() => irA('gasto', '/pagos-gastos?compartido=gasto')}
          disabled={files.length === 0}
          className="w-full flex items-center justify-between bg-white/5 hover:bg-white/10 disabled:opacity-40 disabled:cursor-not-allowed border border-white/10 rounded px-4 py-3 text-left transition"
        >
          <span className="flex items-center gap-3">
            <span className="text-2xl">🧮</span>
            <span>
              <div className="text-gray-100 font-medium">Gasto</div>
              <div className="text-xs text-gray-400">Registrar gasto</div>
            </span>
          </span>
          <span className="text-gray-500">→</span>
        </button>

        <button
          onClick={() => irA('op', '/op?compartido=1')}
          disabled={files.length === 0}
          className="w-full flex items-center justify-between bg-white/5 hover:bg-white/10 disabled:opacity-40 disabled:cursor-not-allowed border border-white/10 rounded px-4 py-3 text-left transition"
        >
          <span className="flex items-center gap-3">
            <span className="text-2xl">📤</span>
            <span>
              <div className="text-gray-100 font-medium">Orden de pago</div>
              <div className="text-xs text-gray-400">Adjuntar comprobante a una OP</div>
            </span>
          </span>
          <span className="text-gray-500">→</span>
        </button>
      </div>

      <div className="mt-6 text-center">
        <button
          onClick={() => navigate('/dashboard')}
          className="text-sm text-gray-500 hover:text-gray-300"
        >
          Cancelar
        </button>
      </div>
    </div>
  )
}
