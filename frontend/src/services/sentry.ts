// Punto de entrada de Sentry para el import() dinámico de main.tsx.
// Re-exporta SOLO lo que usamos: si main.tsx hiciera import('@sentry/react')
// directo, el bundler no puede descartar nada del namespace y el chunk trae
// todo el SDK (replay, feedback, tracing…, ~490 KB). init() igual instala las
// integraciones por defecto (captura de errores globales, breadcrumbs, etc.).
export { init, captureException } from '@sentry/react'
