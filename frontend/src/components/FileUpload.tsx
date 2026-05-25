import React, { useRef } from 'react'

interface FileUploadProps {
  onFileSelected?: (file: File) => void
  onFilesSelected?: (files: File[]) => void
  multiple?: boolean
  accept?: string
  label?: string
  error?: string
}

export const FileUpload: React.FC<FileUploadProps> = ({
  onFileSelected,
  onFilesSelected,
  multiple = false,
  accept = '*/*',
  label = 'Seleccionar archivo',
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
    const files = Array.from(e.dataTransfer.files || [])
    if (files.length === 0) return
    if (multiple && onFilesSelected) {
      onFilesSelected(files)
    } else if (onFileSelected) {
      onFileSelected(files[0])
    }
  }

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = Array.from(e.target.files || [])
    if (files.length === 0) return
    if (multiple && onFilesSelected) {
      onFilesSelected(files)
      e.target.value = ''
    } else if (onFileSelected && files.length > 0) {
      onFileSelected(files[0])
    }
  }

  return (
    <div>
      <button
        type="button"
        onClick={() => inputRef.current?.click()}
        onDragEnter={handleDrag}
        onDragLeave={handleDrag}
        onDragOver={handleDrag}
        onDrop={handleDrop}
        className={`w-full flex items-center gap-2.5 px-3 py-2.5 rounded-lg border text-sm transition-all duration-150 text-left
          ${isDragActive
            ? 'border-violet-400 bg-violet-500/10 text-violet-400 dark:border-violet-400'
            : 'border-gray-200 dark:border-white/10 bg-gray-50 dark:bg-white/5 text-gray-500 dark:text-gray-400 hover:border-gray-300 dark:hover:border-white/20 hover:bg-gray-100 dark:hover:bg-white/10'
          }
          ${error ? 'border-red-400 dark:border-red-500' : ''}
        `}
      >
        <svg
          className={`w-4 h-4 shrink-0 ${isDragActive ? 'text-violet-400' : 'text-gray-400 dark:text-gray-500'}`}
          fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}
        >
          <path strokeLinecap="round" strokeLinejoin="round"
            d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5m-13.5-9L12 3m0 0l4.5 4.5M12 3v13.5" />
        </svg>
        <span className="truncate">{isDragActive ? 'Soltá para subir' : label}</span>
      </button>
      {error && <p className="mt-1 text-xs text-red-500">{error}</p>}
      <input ref={inputRef} type="file" hidden accept={accept} multiple={multiple} onChange={handleChange} />
    </div>
  )
}
