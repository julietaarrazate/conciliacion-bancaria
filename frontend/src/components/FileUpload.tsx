import React, { useRef } from 'react'

interface FileUploadProps {
  onFileSelected: (file: File) => void
  accept?: string
  label?: string
  error?: string
}

export const FileUpload: React.FC<FileUploadProps> = ({
  onFileSelected,
  accept = '.xlsx,.xls,.csv,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet,application/vnd.ms-excel,text/csv',
  label = 'Selecciona un archivo',
  error
}) => {
  const inputRef = useRef<HTMLInputElement>(null)
  const [isDragActive, setIsDragActive] = React.useState(false)

  const handleDrag = (e: React.DragEvent) => {
    e.preventDefault()
    e.stopPropagation()
    setIsDragActive(e.type === 'dragenter' || e.type === 'dragover')
  }

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault()
    e.stopPropagation()
    setIsDragActive(false)

    const files = e.dataTransfer.files
    if (files && files.length > 0) {
      onFileSelected(files[0])
    }
  }

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files.length > 0) {
      onFileSelected(e.target.files[0])
    }
  }

  return (
    <div
      className={`border-2 border-dashed rounded-lg p-8 text-center cursor-pointer transition-colors ${
        isDragActive ? 'border-primary-500 bg-primary-50' : 'border-gray-300'
      } ${error ? 'border-red-500' : ''}`}
      onDragEnter={handleDrag}
      onDragLeave={handleDrag}
      onDragOver={handleDrag}
      onDrop={handleDrop}
      onClick={() => inputRef.current?.click()}
    >
      <input
        ref={inputRef}
        type="file"
        hidden
        accept={accept}
        onChange={handleChange}
      />
      <p className="text-gray-600 mb-2">{label}</p>
      <p className="text-sm text-gray-500">o arrastra un archivo aquí</p>
      {error && <p className="mt-2 text-sm text-red-600">{error}</p>}
    </div>
  )
}
