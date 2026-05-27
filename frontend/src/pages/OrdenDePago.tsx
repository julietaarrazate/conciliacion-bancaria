import React, { useEffect, useRef, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { apiClient } from '@/services/api'
import { useOrgStore } from '@/store/org'

const fmt = (n: number) =>
  new Intl.NumberFormat('es-AR', { style: 'currency', currency: 'ARS', minimumFractionDigits: 0 }).format(n)

interface Cliente { id: number; nombre: string }

type Step = 'foto' | 'datos' | 'exito'

export const OrdenDePago: React.FC = () => {
  const { activeOrgId } = useOrgStore()
  const [step, setStep] = useState<Step>('foto')
  const [clientes, setClientes] = useState<Cliente[]>([])
  const [foto, setFoto] = useState<string | null>(null)  // base64
  const [fotoPreview, setFotoPreview] = useState<string | null>(null)
  const [form, setForm] = useState({
    cliente_id: '',
    beneficiario: '',
    importe: '',
  })
  const [saving, setSaving] = useState(false)
  const [resultado, setResultado] = useState<any>(null)
  const [msg, setMsg] = useState('')
  const fileInputRef = useRef<HTMLInputElement>(null)

  const [searchParams, setSearchParams] = useSearchParams()
  useEffect(() => {
    if (searchParams.get('compartido') !== '1') return
    const destino = sessionStorage.getItem('compartido:destino')
    const archivosRaw = sessionStorage.getItem('compartido:archivos')
    if (destino === 'op' && archivosRaw) {
      try {
        const archivos = JSON.parse(archivosRaw) as { name: string; type: string; dataUrl: string }[]
        const imagen = archivos.find(a => a.type.startsWith('image/')) || archivos[0]
        if (imagen && imagen.dataUrl) {
          setFotoPreview(imagen.dataUrl)
          setFoto(imagen.dataUrl)
          setStep('datos')
        }
      } catch {}
      sessionStorage.removeItem('compartido:destino')
      sessionStorage.removeItem('compartido:archivos')
      sessionStorage.removeItem('compartido:titulo')
      sessionStorage.removeItem('compartido:texto')
      sessionStorage.removeItem('compartido:ts')
    }
    const sp = new URLSearchParams(searchParams)
    sp.delete('compartido')
    setSearchParams(sp, { replace: true })
  }, [searchParams, setSearchParams])

  useEffect(() => {
    const params = activeOrgId ? { org_id: activeOrgId } : {}
    apiClient.client.get('/clientes/archivos', { params }).then(r => {
      setClientes(r.data.clientes?.map((c: any) => ({ id: c.id || 0, nombre: c.nombre })) || [])
    }).catch(() => {
      // fallback: traer del historial
      const p: Record<string, string | number> = { limit: 200 }
      if (activeOrgId) p.org_id = activeOrgId
      apiClient.client.get('/historial/planillas', { params: p }).then(r => {
        const nombres = [...new Set(r.data.items?.map((p: any) => p.cliente_nombre) || [])]
        setClientes(nombres.map((n: any, i: number) => ({ id: i + 1, nombre: n })))
      }).catch(() => {})
    })
  }, [activeOrgId])

  const handleFoto = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return
    const reader = new FileReader()
    reader.onload = ev => {
      const base64 = (ev.target?.result as string) || ''
      setFotoPreview(base64)
      // Comprimir si es muy grande (max ~500KB para la DB)
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

  const importeNum = parseFloat(form.importe.replace(/\./g, '').replace(',', '.')) || 0

  const handleConfirmar = async () => {
    if (!form.cliente_id || !form.beneficiario || !form.importe) {
      setMsg('Completá cliente, proveedor e importe')
      return
    }
    setSaving(true)
    setMsg('')
    try {
      const res = await apiClient.client.post('/caja/op/registrar', {
        cliente_nombre: form.cliente_id,
        beneficiario: form.beneficiario,
        importe: importeNum,
        foto_base64: foto,
        ...(activeOrgId ? { org_id: activeOrgId } : {}),
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

    // Marcar como compartida
    await apiClient.client.post(`/caja/op/${resultado.op_id}/compartir`).catch(() => {})

    // Intentar compartir foto via Web Share API
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
    // Fallback: abrir WhatsApp con texto
    window.open(`whatsapp://send?text=${texto}`, '_blank')
  }

  const reiniciar = () => {
    setStep('foto')
    setFoto(null)
    setFotoPreview(null)
    setForm({ cliente_id: '', beneficiario: '', importe: '' })
    setResultado(null)
    setMsg('')
  }

  return (
    <div className="p-4 max-w-lg mx-auto">
      <div className="flex items-center gap-3 mb-5">
        <h1 className="text-xl font-bold dark:text-white">Registrar OP pagada</h1>
      </div>

      {/* Indicador de pasos */}
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
            <div>
              <label className="label">Cliente (quien pidió el pago)</label>
              <select className="input-field" value={form.cliente_id}
                onChange={e => setForm(p => ({ ...p, cliente_id: e.target.value }))}>
                <option value="">Seleccionar cliente...</option>
                {clientes.map(c => <option key={c.id} value={c.nombre}>{c.nombre}</option>)}
              </select>
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
