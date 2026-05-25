import React from 'react'
import ReactDOM from 'react-dom/client'
import { App } from './App'

class ErrorBoundary extends React.Component<
  { children: React.ReactNode },
  { hasError: boolean; message: string }
> {
  constructor(props: { children: React.ReactNode }) {
    super(props)
    this.state = { hasError: false, message: '' }
  }
  static getDerivedStateFromError(err: Error) {
    return { hasError: true, message: err?.message || 'Error desconocido' }
  }
  render() {
    if (this.state.hasError) {
      return (
        <div className="min-h-screen flex items-center justify-center bg-[#0B0B0F] p-8 text-center">
          <div>
            <p className="text-white font-semibold text-lg mb-1">Algo salió mal</p>
            <p className="text-gray-500 text-sm mb-6 font-mono">{this.state.message}</p>
            <button
              onClick={() => window.location.reload()}
              className="px-4 py-2 text-sm bg-white/10 hover:bg-white/20 text-white rounded-lg transition-colors"
            >
              Recargar
            </button>
          </div>
        </div>
      )
    }
    return this.props.children
  }
}

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <ErrorBoundary>
      <App />
    </ErrorBoundary>
  </React.StrictMode>,
)

// Marca a la app como booteada para el watchdog en index.html
;(window as any).__appBooted = true
