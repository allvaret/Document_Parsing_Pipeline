/// <reference types="vitest/config" />
import { readFileSync, writeFileSync, existsSync } from 'node:fs'
import { resolve } from 'node:path'
import { defineConfig, loadEnv, type Plugin } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

const API_ORIGIN_PLACEHOLDER = '__API_ORIGIN__'

/** Origem (esquema + host + porta) da API, validada. Lança se a URL for inválida. */
export function apiOrigin(url: string): string {
  const u = new URL(url)
  if (u.protocol !== 'https:' && u.protocol !== 'http:') throw new Error(`VITE_API_URL inválida: ${url}`)
  return u.origin
}

/** Build de produção: exige VITE_API_URL e grava a origem exata da API no connect-src
 *  do `_headers` (Cloudflare Pages). Assim o CSP nunca diverge da URL que o site chama. */
function apiUrlGuard(mode: string): Plugin {
  const env = loadEnv(mode, process.cwd(), 'VITE_')
  let outDir = 'dist'
  return {
    name: 'api-url-guard',
    apply: 'build',
    configResolved(cfg) {
      outDir = cfg.build.outDir
      if (!env.VITE_API_URL) {
        throw new Error('VITE_API_URL não definida: o build de produção precisa da URL da API.')
      }
      apiOrigin(env.VITE_API_URL)
    },
    closeBundle() {
      const file = resolve(outDir, '_headers')
      if (!existsSync(file)) return
      const s = readFileSync(file, 'utf-8')
      writeFileSync(file, s.replaceAll(API_ORIGIN_PLACEHOLDER, apiOrigin(env.VITE_API_URL)))
    },
  }
}

export default defineConfig(({ mode }) => ({
  plugins: [react(), tailwindcss(), apiUrlGuard(mode)],
  test: {
    environment: 'jsdom',
    setupFiles: ['./src/test/setup.ts'],
  },
}))
