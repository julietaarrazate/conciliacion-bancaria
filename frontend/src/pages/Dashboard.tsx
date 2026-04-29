import React, { useState } from 'react'
import { FileUpload } from '@/components/FileUpload'
import { Input } from '@/components/Input'
import { apiClient } from '@/services/api'

interface ConciliacionFormState {
  extractoFile: File | null
  planillaFile: File | null
  clienteNombre: string
}

export const Dashboard: React.FC = () => {
  const [form, setForm] = useState<ConciliacionFormState>({
    extractoFile: null,
    planillaFile: null,
    clienteNombre: ''
  })
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')
  const [resultado, setResultado] = useState<any>(null)
  const [extractoId, setExtratoId] = useState<number | null>(null)

  const handleUploadExtraco = async (file: File) => {
    setLoading(true)
    setError('')
    try {
      const data = await apiClient.uploadExtraco(file)
      setExtratoId(data.id)
      setSuccess(`Extracto cargado: ${data.nombre_archivo}`)
      setForm({ ...form, extractoFile: file })
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Error al cargar extracto')
    } finally {
      setLoading(false)
    }
  }

  const handleUploadPlanilla = async (file: File) => {
    if (!extractoId || !form.clienteNombre) {
      setError('Por favor carga primero un extracto e ingresa el nombre del cliente')
      return
    }

    setLoading(true)
    setError('')
    try {
      const planilla = await apiClient.uploadPlanilla(
        form.clienteNombre,
        extractoId,
        file
      )
      setForm({ ...form, planillaFile: file })
      setSuccess('Planilla cargada. Iniciando conciliación...')

      // Ejecutar conciliación automáticamente
      const resultado = await apiClient.conciliarPlanilla(planilla.id)
      setResultado(resultado)
      setSuccess(`Conciliación completada: ${resultado.acreditadas} acreditadas`)
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Error en la conciliación')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="p-8 max-w-5xl mx-auto">
      <h1 className="text-2xl font-bold text-gray-900 mb-2">Nueva conciliación</h1>
      <p className="text-gray-600 mb-6">Carga extracto + planilla y reconciliá automáticamente</p>

      <main>
        {error && (
          <div className="mb-6 p-4 bg-red-100 border border-red-400 rounded-lg text-red-700">
            {error}
          </div>
        )}

        {success && (
          <div className="mb-6 p-4 bg-green-100 border border-green-400 rounded-lg text-green-700">
            {success}
          </div>
        )}

        {/* Formulario de Conciliación */}
        <div className="card mb-8">
          <h2 className="text-xl font-bold mb-6">Nueva Conciliación</h2>

          <div className="space-y-6">
            {/* Paso 1: Extracto */}
            <div>
              <h3 className="text-lg font-semibold mb-4">1. Carga el Extracto Bancario</h3>
              <FileUpload
                onFileSelected={handleUploadExtraco}
                label="Selecciona el extracto bancario (XLSX)"
                error={!extractoId && error ? 'Carga primero un extracto' : ''}
              />
              {extractoId && (
                <p className="mt-2 text-sm text-green-600">✓ Extracto cargado correctamente</p>
              )}
            </div>

            {/* Paso 2: Cliente */}
            {extractoId && (
              <div>
                <h3 className="text-lg font-semibold mb-4">2. Información del Cliente</h3>
                <Input
                  label="Nombre del Cliente"
                  placeholder="Ej: Green, Tucu, David..."
                  value={form.clienteNombre}
                  onChange={(e) => setForm({ ...form, clienteNombre: e.target.value })}
                />
              </div>
            )}

            {/* Paso 3: Planilla */}
            {extractoId && form.clienteNombre && (
              <div>
                <h3 className="text-lg font-semibold mb-4">3. Carga la Planilla del Cliente</h3>
                <FileUpload
                  onFileSelected={handleUploadPlanilla}
                  label="Selecciona la planilla del cliente (XLSX)"
                />
              </div>
            )}
          </div>
        </div>

        {/* Resultados */}
        {resultado && (
          <div className="card">
            <h2 className="text-xl font-bold mb-6">Resultado de Conciliación</h2>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              <div className="bg-green-50 p-4 rounded-lg">
                <p className="text-sm text-gray-600">Acreditadas</p>
                <p className="text-2xl font-bold text-green-600">{resultado.acreditadas}</p>
              </div>
              <div className="bg-red-50 p-4 rounded-lg">
                <p className="text-sm text-gray-600">No Encontradas</p>
                <p className="text-2xl font-bold text-red-600">{resultado.no_encontradas}</p>
              </div>
              <div className="bg-yellow-50 p-4 rounded-lg">
                <p className="text-sm text-gray-600">Duplicadas</p>
                <p className="text-2xl font-bold text-yellow-600">{resultado.duplicadas}</p>
              </div>
              <div className="bg-blue-50 p-4 rounded-lg">
                <p className="text-sm text-gray-600">Sin Datos</p>
                <p className="text-2xl font-bold text-blue-600">{resultado.sin_datos}</p>
              </div>
            </div>
            <p className="mt-4 text-sm text-gray-600">
              Total: {resultado.filas_procesadas} filas procesadas
            </p>
          </div>
        )}
      </main>
    </div>
  )
}
