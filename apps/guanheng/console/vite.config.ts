import react from '@vitejs/plugin-react'
import { loadEnv } from 'vite'
import { defineConfig } from 'vitest/config'
import { generatedStoragePath } from './generated-storage'
import { readFileSync } from 'node:fs'
import { observationBase } from './src/observation/deploymentBase'

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, '.', '')
  const consoleBffUrl = env.CONSOLE_BFF_URL || 'http://127.0.0.1:18120'
  const observationBffUrl = env.OBSERVATION_BFF_URL || consoleBffUrl
  const brand = JSON.parse(readFileSync(new URL('./config/project-branding.json', import.meta.url), 'utf8'))
  return {
    base: env.VITE_OBSERVATION_ONLY === 'true' ? observationBase(env.VITE_OBSERVATION_BASE) + '/' : '/',
    plugins: [react(), { name: 'observation-entry-and-brand', transformIndexHtml: { order: 'pre', handler(html: string) {
      const branded = html.replace(/<title>.*?<\/title>/, `<title>${brand.display_name}</title>`)
      return env.VITE_OBSERVATION_ONLY === 'true' ? branded.replace('/src/main.tsx', '/src/observation-main.tsx') : branded
    } } }],
    cacheDir: generatedStoragePath('cache/vite', 'node_modules/.vite'),
    server: {
      host: '127.0.0.1',
      port: 5173,
      strictPort: true,
      proxy: {
        '/v1/ui/market-observation': observationBffUrl,
        '/v1': consoleBffUrl,
      },
    },
    preview: {
      proxy: {
        '/v1/ui/market-observation': observationBffUrl,
        '/v1': consoleBffUrl,
      },
    },
    build: {
      sourcemap: false,
      manifest: true,
      chunkSizeWarningLimit: 900,
    },
    test: {
      environment: 'jsdom',
      setupFiles: './src/test-setup.ts',
      include: ['src/**/*.{test,spec}.{ts,tsx,js,jsx}'],
    },
  }
})
