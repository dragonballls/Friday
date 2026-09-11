/// <reference types="vitest" />
import { defineConfig } from 'vitest/config'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

const LOOPBACK_NETWORK_BOOTSTRAP = `
(() => {
  const nativeFetch = window.fetch.bind(window)
  window.fetch = (input, init = {}) => {
    const url = typeof input === 'string' ? input : input instanceof Request ? input.url : String(input)
    if (/^https?:\\/\\/(127\\.0\\.0\\.1|localhost)(:|\\/)/i.test(url)) {
      return nativeFetch(input, { ...init, targetAddressSpace: 'loopback' })
    }
    return nativeFetch(input, init)
  }
})()
`

export default defineConfig({
  base: process.env.GITHUB_ACTIONS ? '/Friday/' : '/',
  plugins: [
    react(),
    tailwindcss(),
    {
      name: 'friday-loopback-network-bootstrap',
      transformIndexHtml() {
        return {
          tags: [{ tag: 'script', children: LOOPBACK_NETWORK_BOOTSTRAP, injectTo: 'head-prepend' }],
        }
      },
    },
  ],
  clearScreen: false,
  server: {
    port: 5173,
    strictPort: true,
  },
  build: {
    target: 'esnext',
    minify: 'esbuild',
    rollupOptions: {
      output: {
        manualChunks(id: string) {
          if (id.includes('three')) return 'three'
        },
      },
    },
  },
  test: {
    globals: true,
    environment: 'jsdom',
    setupFiles: './src/test/setup.ts',
    css: true,
    reporters: ['verbose'],
    coverage: {
      provider: 'v8',
      reporter: ['text', 'json', 'html'],
      include: ['src/**/*.{ts,tsx}'],
      exclude: ['src/**/*.d.ts', 'src/test/**'],
    },
  },
})
