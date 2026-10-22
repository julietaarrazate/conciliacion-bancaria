/// <reference types="vitest" />
import { defineConfig, type Plugin } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'path'

// La landing, el Layout y el cliente HTTP son lazy (no viajan en el bundle
// inicial), pero en ciertas rutas se sabe de entrada que se van a necesitar.
// Este plugin agrega al index.html un script mínimo que, según la ruta y si hay
// sesión, los pide con <link rel="modulepreload"> en paralelo con el entry en
// vez de esperar a que React los importe:
//   - / (sin sesión) y /landing → chunk de la landing
//   - con sesión → Layout + services/api (axios), que /auth/me necesita antes
//     de pintar nada
const PRECARGAS: { condicion: string; modulos: string[] }[] = [
  { condicion: "p==='/landing'||(p==='/'&&!t)", modulos: ['/src/pages/Landing.tsx'] },
  { condicion: 't', modulos: ['/src/components/Layout.tsx', '/src/services/api.ts'] },
]

function precargarChunks(): Plugin {
  return {
    name: 'precargar-chunks',
    apply: 'build',
    transformIndexHtml: {
      order: 'post',
      handler(html, ctx) {
        const bundle = ctx.bundle
        if (!bundle) return html
        const chunks = Object.values(bundle).flatMap((c) => (c.type === 'chunk' ? [c] : []))
        const entry = chunks.find((c) => c.isEntry)
        const yaCargados = new Set(entry ? [entry.fileName, ...entry.imports] : [])
        const reglas: string[] = []
        for (const { condicion, modulos } of PRECARGAS) {
          const archivos = new Set<string>()
          for (const m of modulos) {
            const chunk = chunks.find((c) => c.facadeModuleId?.replace(/\\/g, '/').endsWith(m))
            if (!chunk) continue
            for (const f of [chunk.fileName, ...chunk.imports]) if (!yaCargados.has(f)) archivos.add(f)
          }
          if (archivos.size) reglas.push(`if(${condicion})u=u.concat(${JSON.stringify([...archivos].map((f) => '/' + f))});`)
        }
        if (!reglas.length) return html
        const script =
          `<script>(function(){try{var p=location.pathname,t=sessionStorage.getItem('token'),u=[];` +
          reglas.join('') +
          `u.forEach(function(h){var l=document.createElement('link');` +
          `l.rel='modulepreload';l.crossOrigin='';l.href=h;document.head.appendChild(l)})}catch(e){}})();</script>`
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
  plugins: [react(), precargarChunks()],
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
