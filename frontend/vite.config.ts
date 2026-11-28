import { fileURLToPath, URL } from 'node:url'

import vue from '@vitejs/plugin-vue'
import tailwindcss from '@tailwindcss/vite'
import { defineConfig } from 'vitest/config'

// https://vite.dev/config/
export default defineConfig({
  plugins: [vue(), tailwindcss()],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
    },
  },
  server: {
    port: 5173,
    strictPort: true,
  },
  worker: {
    // El motor LLM y pdf.js viven en un Web Worker. El formato "es" es el que
    // soporta WebGPU con los modulos de WebAssembly de Vite 8.
    format: 'es',
  },
  build: {
    // El bundle del motor LLM es enorme y se descarga aparte. Vite lo separa
    // para que la aplicacion carga rapido y los pesos llegan cuando el usuario
    // pide analizar.
    //
    // Rolldown (Vite 8) solo admite `manualChunks` como funcion: la forma de
    // objeto se elimino en esta version.
    rollupOptions: {
      output: {
        manualChunks(id) {
          if (id.includes('@mlc-ai/web-llm')) return 'llm'
          if (id.includes('pdfjs-dist')) return 'pdf'
          return undefined
        },
      },
    },
  },
  test: {
    environment: 'jsdom',
    globals: true,
    include: ['src/**/*.{test,spec}.{ts,tsx}'],
  },
})
