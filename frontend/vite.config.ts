/// <reference types="vitest" />
import { defineConfig, type Plugin } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'path'

// La landing es lazy (no viaja en el bundle de /login ni de la app), pero en
// / y /landing es lo primero que se pinta. Este plugin agrega al index.html un
// script mínimo que, solo en esas rutas y sin sesión, pide el chunk de la
// landing con <link rel="modulepreload"> en paralelo con el entry en vez de
// esperar a que React lo pida.
function precargarLanding(): Plugin {
  return {
    name: 'precargar-landing',
    apply: 'build',
    transformIndexHtml: {
      order: 'post',
      handler(html, ctx) {
        const bundle = ctx.bundle
        if (!bundle) return html
        const landing = Object.values(bundle).find(
          (c) => c.type === 'chunk' && c.facadeModuleId?.replace(/\\/g, '/').endsWith('/src/pages/Landing.tsx'),
        )
        if (!landing || landing.type !== 'chunk') return html
        const entry = Object.values(bundle).find((c) => c.type === 'chunk' && c.isEntry)
        const yaCargados = new Set(entry && entry.type === 'chunk' ? [entry.fileName, ...entry.imports] : [])
        const archivos = [landing.fileName, ...landing.imports].filter((f) => !yaCargados.has(f))
        const urls = JSON.stringify(archivos.map((f) => '/' + f))
        const script =
          `<script>(function(){try{var p=location.pathname;` +
          `if(!(p==='/landing'||(p==='/'&&!sessionStorage.getItem('token'))))return;` +
          `${urls}.forEach(function(u){var l=document.createElement('link');` +
          `l.rel='modulepreload';l.crossOrigin='';l.href=u;document.head.appendChild(l)})}catch(e){}})();</script>`
        // Al final del <head>, después del CSS: medido, rinde más que ponerlo
        // antes del entry (no le compite ancho de banda a vendor-react).
        return html.replace('</head>', `  ${script}\n  </head>`)
      },
    },
  }
}

// Nota: NO usamos vite-plugin-pwa. El service worker se gestiona manualmente
// desde /public/sw.js para evitar conflictos de cache entre dos SW distintos.
export default defineConfig({
  plugins: [react(), precargarLanding()],
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
