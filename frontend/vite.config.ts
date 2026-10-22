/// <reference types="vitest" />
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'path'

// Nota: NO usamos vite-plugin-pwa. El service worker se gestiona manualmente
// desde /public/sw.js para evitar conflictos de cache entre dos SW distintos.
export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: { '@': path.resolve(__dirname, './src') }
  },
  build: {
    rollupOptions: {
      output: {
        // Vendors estables en chunks propios: cambian solo al actualizar
        // dependencias, así que después de un deploy el navegador (y la PWA)
        // los sigue teniendo en caché y baja únicamente el código de la app.
        manualChunks(id) {
          if (!id.includes('node_modules')) return undefined
          if (/node_modules\/(react|react-dom|scheduler|react-router|react-router-dom|@remix-run\/router)\//.test(id)) return 'vendor-react'
          if (/node_modules\/axios\//.test(id)) return 'vendor-axios'
          return undefined
        },
      },
    },
  },
  // Tests: jsdom para poder montar componentes (smoke tests con Testing Library).
  // Los tests de utilidades puras también corren bajo este entorno sin problema.
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: ['./src/test/setup.ts'],
  },
  server: {
    port: 3000,
    host: '0.0.0.0',
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
        rewrite: (p) => p.replace(/^\/api/, '')
      }
    }
  }
})
