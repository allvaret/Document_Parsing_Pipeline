/// <reference types="node" />
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { describe, expect, it } from 'vitest'

// Lê o arquivo cru: importar via Vite passaria pelo plugin do Tailwind, que consome o @theme.
const css = readFileSync(resolve(process.cwd(), 'src/styles/tokens.css'), 'utf8')

function color(name: string): string {
  const m = css.match(new RegExp(`--color-${name}:\\s*(#[0-9a-fA-F]{6})`))
  if (!m) throw new Error(`token ${name} não encontrado`)
  return m[1]
}

function luminance(hex: string): number {
  const [r, g, b] = [1, 3, 5]
    .map((i) => parseInt(hex.slice(i, i + 2), 16) / 255)
    .map((c) => (c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4))
  return 0.2126 * r + 0.7152 * g + 0.0722 * b
}

function contrast(a: string, b: string): number {
  const [hi, lo] = [luminance(a), luminance(b)].sort((x, y) => y - x)
  return (hi + 0.05) / (lo + 0.05)
}

// [texto, fundo, mínimo]. 4.5 = AA para texto normal; 3 = elementos gráficos.
const PAIRS: [string, string, number][] = [
  ['ink', 'paper', 4.5],
  ['ink-soft', 'paper', 4.5],
  ['ink-soft', 'paper-deep', 4.5],
  ['brass-ink', 'paper', 4.5],
  ['brass', 'velvet', 4.5],
  ['paper', 'velvet', 4.5],
  ['danger', 'paper', 4.5],
  ['focus', 'paper', 3],
]

describe('contraste dos tokens (WCAG AA)', () => {
  it.each(PAIRS)('%s sobre %s >= %s', (fg, bg, min) => {
    expect(contrast(color(fg), color(bg))).toBeGreaterThanOrEqual(min)
  })
})
