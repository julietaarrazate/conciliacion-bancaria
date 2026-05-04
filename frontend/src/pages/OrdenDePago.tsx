
import React, { useEffect, useRef, useState } from 'react'
import { apiClient } from '@/services/api'

const DENOMINACIONES = [20000, 10000, 2000, 1000, 500, 200, 100]
const fmt = (n: number) =>
  new Intl.NumberFormat('es-AR', { style: 'currency', currency: 'ARS', minimumFractionDigits: 0 }).format(n)

interface Cliente { id: number; nombre: string }

type Step = 'foto' | 'datos' | 'exito'

export const OrdenDePago: React.FC = () => {
  const [step, setStep] = useState<Step>('foto')
  const [clientes, setClientes] = useState<Cliente[]>([])
  const [foto, setFoto] = useState<string | null>(null)
  const [fotoPreview, setFotoPreview] = useState<string | null>(null)
  const [form, setForm] = useState({
    cliente_id: '',
    beneficiario: '',
    importe: '',
  })
  const [dens, setDens] = useState<Record<string, string>>({})
  const [saving, setSaving] = useState(false)
  const [resultado, setResultado] = useState<any>(null)
  const [msg, setMsg] = useState('')
  const [showSugerencias, setShowSugerencias] = useState(false)
  const fileInputRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    apiClient.client.get('/clientes/archivos').then(r => {
      setClientes(r.data.clientes?.map((c: any) => ({ id: c.id || 0, nombre: c.nombre })) || [])
    }).catch(() => {
      apiClient.client.get('/historial/planillas?limit=200').then(r => {
        const nombres = [...new Set(r.data.items?.map((p: any) => p.cliente_nombre) || [])]
        setClientes(nombres.map((n: any, i: number) => ({ id: i + 1, nombre: n })))
      }).catch(() => {})
    })
  }, [])

  const handleFoto = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return
    const reader = new FileReader()
    reader.onload = ev => {
      const base64 = (ev.target?.result as string) || ''
      setFotoPreview(base64)
      const img = new Image()
      img.onload = () => {
        const canvas = document.createElement('canvas')
        const MAX = 1200
        let w = img.width, h = img.height
        if (w > MAX) { h = h * MAX / w; w = MAX }
        if (h > MAX) { w = w * MAX / h; h = MAX }
        canvas.width = w; canvas.height = h
        canvas.getContext('2d')?.drawImage(img, 0, 0, w, h)
        setFoto(canvas.toDataURL('image/jpeg', 0.7))
      }
      img.src = base64
    }
    reader.readAsDataURL(file)
  }

  const totalDens = DENOMINACIONES.reduce((s, d) => s + d * (parseInt(dens[String(d)]) || 0), 0)
  const importeNum = parseFloat(form.importe.replace(/\./g, '').replace(',', '.')) || 0
  const dif = importeNum - totalDens

  const handleConfirmar = async () => {
    if (!form.cliente_id || !form.beneficiario || !form.importe) {
      setMsg('Completá cliente, proveedor e importe')
      return
    }
    setSaving(true)
    setMsg('')
    try {
      const densObj = Object.fromEntries(
        Object.entries(dens).filter(([, v]) => parseInt(v) > 0).map(([k, v]) => [k, parseInt(v)])
      )
      const res = await apiClient.client.post('/caja/op/registrar', {
        cliente_nombre: form.cliente_id,
        beneficiario: form.beneficiario,
        importe: importeNum,
        foto_base64: foto,
        denominaciones: densObj
      })
      setResultado(res.data)
      setStep('exito')
    } catch (err: any) {
      setMsg(err.response?.data?.detail || 'Error al registrar')
    } finally { setSaving(false) }
  }

  const compartirWhatsApp = async () => {
    if (!resultado) return
    const texto = `OP pagada%0A• Proveedor: ${form.beneficiario}%0A• Cliente: ${form.cliente_id}%0A• Importe: ${fmt(importeNum)}%0A• Fecha: ${new Date().toLocaleDateString('es-AR')}`
    await apiClient.client.post(`/caja/op/${resultado.op_id}/compartir`).catch(() => {})
    if (foto && navigator.share && navigator.canShare) {
      try {
        const blob = await fetch(foto).then(r => r.blob())
        const file = new File([blob], `OP_${form.beneficiario}_${new Date().toLocaleDateString('es-AR').replace(/\//g, '-')}.jpg`, { type: 'image/jpeg' })
        if (navigator.canShare({ files: [file] })) {
          await navigator.share({
            title: `OP - ${form.beneficiario} - ${fmt(importeNum)}`,
            text: `OP pagada - ${form.beneficiario} - ${fmt(importeNum)} - ${new Date().toLocaleDateString('es-AR')}`,
            files: [file]
          })
          return
        }
      } catch { }
    }
    window.open(`whatsapp://send?text=${texto}`, '_blank')
  }

  const reiniciar = () => {
    setStep('foto')
    setFoto(null)
    setFotoPreview(null)
    setForm({ cliente_id: '', beneficiario: '', importe: '' })
    setDens({})
    setResultado(null)
    setMsg('')
  }

  const seleccionarCliente = (nombre: string) => {
    setForm(p => ({ ...p, cliente_id: nombre }))
    setShowSugerencias(false)
  }

  return (
    <div className="p-4 max-w-lg mx-auto">
      <div className="flex items-center gap-3 mb-5">
        <h1 className="text-xl font-bold dark:text-white">Registrar OP pagada</h1>
      </div>

      <div className="flex items-center gap-2 mb-6">
        {(['foto', 'datos', 'exito'] as Step[]).map((s, i) => (
          <React.Fragment key={s}>
            <div className={`w-7 h-7 rounded-full flex items-center justify-center text-xs font-bold transition-all ${
              step === s ? 'bg-ml-blue dark:bg-ml-green text-white dark:text-black' :
              (['foto', 'datos'].indexOf(step) > i || step === 'exito') ? 'bg-green-500 text-white' :
              'bg-ml-gray dark:bg-ml-dark-card text-gray-400'}`}>
              {i + 1}
            </div>
            {i < 2 && <div className="flex-1 h-0.5 bg-ml-gray dark:bg-ml-dark-border" />}
          </React.Fragment>
        ))}
      </div>

      {/* PASO 1: Foto */}
      {step === 'foto' && (
        <div className="space-y-4">
          <div className="card text-center">
            {fotoPreview ? (
              <div className="space-y-3">
                <img src={fotoPreview} alt="OP" className="max-h-64 mx-auto rounded-lg object-contain border border-ml-gray dark:border-ml-dark-border" />
                <div className="flex gap-2 justify-center">
                  <button onClick={() => { setFoto(null); setFotoPreview(null) }} className="btn-secondary text-sm">
                    Sacar otra foto
                  </button>
                  <button onClick={() => setStep('datos')} className="btn-yellow text-sm">
                    Usar esta foto →
                  </button>
                </div>
              </div>
            ) : (
              <div className="py-8 space-y-4">
                <div className="text-5xl">📄</div>
                <p className="font-semibold dark:text-white">Foto de la OP firmada</p>
                <p className="text-sm text-gray-400 dark:text-zinc-500">
                  Escaneá o fotografiá la orden de pago con la firma del proveedor
                </p>
                <input ref={fileInputRef} type="file" accept="image/*" capture="environment"
                  className="hidden" onChange={handleFoto} />
                <button onClick={() => fileInputRef.current?.click()} className="btn-yellow w-full text-base py-3">
                  📷 Abrir cámara
                </button>
                <button onClick={() => setStep('datos')} className="btn-ghost w-full text-sm">
                  Continuar sin foto
                </button>
              </div>
            )}
          </div>
        </div>
      )}

      {/* PASO 2: Datos */}
      {step === 'datos' && (
        <div className="space-y-4">
          {msg && (
            <div className="px-3 py-2 bg-red-50 dark:bg-red-900/20 text-red-600 dark:text-red-400 rounded-lg text-sm">{msg}</div>
          )}

          <div className="card space-y-4">
            <div className="relative">
              <label className="label">Cliente (quien pidió el pago)</label>

              {/* ── DROPDOWN CUSTOM ANDROID-SAFE ── */}
              <button
                type="button"
                className="input-field w-full text-left flex items-center justify-between"
                onClick={() => setShowSugerencias(v => !v)}
              >
                <span className={form.cliente_id ? 'dark:text-white' : 'text-gray-400'}>
                  {form.cliente_id || 'Seleccionar cliente...'}
                </span>
                <span className="text-gray-400 ml-2">▾</span>
              </button>

              {showSugerencias && (
                <div className="absolute z-50 left-0 right-0 mt-1 max-h-48 overflow-y-auto bg-white dark:bg-ml-dark-surface border border-ml-gray dark:border-ml-dark-border rounded-xl shadow-lg">
                  {clientes.map(c => (
                    <button
                      key={c.id}
                      type="button"
                      className="w-full text-left px-4 py-3 text-sm dark:text-white hover:bg-ml-gray-bg dark:hover:bg-ml-dark-card border-b border-ml-gray dark:border-ml-dark-border last:border-0"
                      onClick={() => seleccionarCliente(c.nombre)}
                    >
                      {c.nombre}
                    </button>
                  ))}
                  {clientes.length === 0 && (
                    <div className="px-4 py-3 text-sm text-gray-400">No hay clientes disponibles</div>
                  )}
                </div>
              )}
            </div>

            <div>
              <label className="label">Proveedor (a quién le pagaste)</label>
              <input className="input-field" placeholder="Nombre del proveedor"
                value={form.beneficiario}
                onChange={e => setForm(p => ({ ...p, beneficiario: e.target.value }))} />
              <p className="text-2xs text-gray-400 dark:text-zinc-600 mt-1">
                Este nombre se usa para el archivo al compartir por WhatsApp
              </p>
            </div>

            <div>
              <label className="label">Importe pagado</label>
              <input className="input-field font-mono text-lg" type="number" placeholder="0"
                value={form.importe}
                onChange={e => setForm(p => ({ ...p, importe: e.target.value }))} />
            </div>
          </div>

          {/* Denominaciones */}
          <div className="card">
            <h3 className="font-semibold text-sm dark:text-white mb-3">Billetes usados para este pago</h3>
            <div className="space-y-2">
              {DENOMINACIONES.map(d => {
                const cant = parseInt(dens[String(d)]) || 0
                return (
                  <div key={d} className="flex items-center gap-3">
                    <span className="text-sm font-mono text-gray-500 dark:text-zinc-400 w-20 text-right">
                      ${d.toLocaleString('es-AR')}
                    </span>
                    <span className="text-gray-400 text-sm">×</span>
                    <input type="number" min="0"
                      className="input-field !w-20 text-center font-mono"
                      value={dens[String(d)] || ''}
                      placeholder="0"
                      onChange={e => setDens(prev => ({ ...prev, [String(d)]: e.target.value }))} />
                    <span className="text-sm font-mono text-gray-400 dark:text-zinc-500 flex-1 text-right">
                      {cant > 0 ? fmt(d * cant) : ''}
                    </span>
                  </div>
                )
              })}
            </div>

            {totalDens > 0 && (
              <div className="mt-3 pt-3 border-t border-ml-gray dark:border-ml-dark-border flex justify-between items-center">
                <span className="text-sm font-semibold dark:text-white">Total en billetes</span>
                <div className="text-right">
                  <span className="font-mono font-bold dark:text-white">{fmt(totalDens)}</span>
                  {importeNum > 0 && Math.abs(dif) > 0.5 && (
                    <p className={`text-xs font-mono ${dif > 0 ? 'text-amber-500' : 'text-red-500'}`}>
                      {dif > 0 ? `Faltan ${fmt(dif)}` : `Sobran ${fmt(Math.abs(dif))}`}
                    </p>
                  )}
                  {importeNum > 0 && Math.abs(dif) <= 0.5 && (
                    <p className="text-xs text-green-500 font-mono">✓ Exacto</p>
                  )}
                </div>
              </div>
            )}
          </div>

          <div className="flex gap-3">
            <button onClick={() => setStep('foto')} className="btn-secondary flex-1">← Volver</button>
            <button onClick={handleConfirmar} disabled={saving} className="btn-yellow flex-1 text-base py-3">
              {saving ? 'Registrando...' : '✓ Confirmar pago'}
            </button>
          </div>
        </div>
      )}

      {/* PASO 3: Éxito */}
      {step === 'exito' && resultado && (
        <div className="space-y-4">
          <div className="card text-center py-6">
            <div className="text-5xl mb-3">✅</div>
            <p className="font-bold text-lg dark:text-white">OP registrada</p>
            <p className="text-sm text-gray-400 dark:text-zinc-500 mt-1">
              {form.beneficiario} · {fmt(importeNum)}
            </p>
            <div className="mt-4 grid grid-cols-2 gap-3 text-left">
              <div className="bg-green-50 dark:bg-green-900/20 rounded-lg p-3">
                <p className="text-2xs text-green-600 dark:text-green-400 font-semibold uppercase tracking-wider">Guardado en EFT</p>
                <p className="text-sm font-semibold text-green-700 dark:text-green-300 mt-0.5">{form.cliente_id}</p>
              </div>
              <div className="bg-blue-50 dark:bg-blue-900/20 rounded-lg p-3">
                <p className="text-2xs text-blue-600 dark:text-blue-400 font-semibold uppercase tracking-wider">Caja actualizada</p>
                <p className="text-sm font-semibold text-blue-700 dark:text-blue-300 mt-0.5">
                  Restante: {fmt(resultado.arqueo?.caja_restante || 0)}
                </p>
              </div>
            </div>
          </div>

          <button
            onClick={compartirWhatsApp}
            className="w-full py-3 rounded-xl text-base font-semibold bg-[#25D366] text-white hover:bg-[#20c25a] transition-colors flex items-center justify-center gap-2"
          >
            <span className="text-xl">📤</span>
            Compartir por WhatsApp
          </button>
          <p className="text-center text-xs text-gray-400 dark:text-zinc-600">
            Se comparte con el nombre del proveedor como nombre de archivo
          </p>

          <button onClick={reiniciar} className="btn-secondary w-full">
            + Registrar otra OP
          </button>
        </div>
      )}
    </div>
  )
}