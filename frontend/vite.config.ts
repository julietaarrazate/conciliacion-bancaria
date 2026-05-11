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
