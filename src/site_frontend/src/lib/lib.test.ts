import { describe, expect, it } from 'vitest'
import { formatDate, parseId, periodLabel, reportTypeLabel } from './format'
import { hueOf, initials } from './mark'
import { parseMarkdown } from './parseMarkdown'

describe('format', () => {
  it('período em português; formato desconhecido volta como veio', () => {
    expect(periodLabel('3T25')).toBe('3º trimestre de 2025')
    expect(periodLabel('9M25')).toBe('9M25')
    expect(periodLabel('lixo')).toBe('lixo')
  })
  it('tipo desconhecido não quebra', () => {
    expect(reportTypeLabel('ITR')).toContain('ITR')
    expect(reportTypeLabel('NOVO')).toBe('NOVO')
  })
  it('data não muda de dia por fuso', () => {
    expect(formatDate('2025-11-23 23:59:59')).toBe('23/11/2025')
    expect(formatDate('???')).toBe('???')
  })
  it('id só aceita inteiro positivo', () => {
    expect(parseId('12')).toBe(12)
    for (const bad of ['0', '-1', '1.5', 'abc', '', '01', '99999999999', undefined]) expect(parseId(bad)).toBeNull()
  })
})

describe('mark', () => {
  it('iniciais ignoram conectivos e acentos', () => {
    expect(initials('Companhia Energética de Minas Gerais')).toBe('EM')
    expect(initials('Cemig')).toBe('CE')
    expect(initials('BR PARTNERS')).toBe('BP')
    expect(initials('')).toBe('?')
  })
  it('matiz é estável e está em 0–359', () => {
    expect(hueOf('POMO4')).toBe(hueOf('pomo4'))
    expect(hueOf('X')).toBeGreaterThanOrEqual(0)
    expect(hueOf('Qualquer coisa longa')).toBeLessThan(360)
  })
})

describe('markdown', () => {
  it('títulos, listas, negrito e parágrafos', () => {
    const b = parseMarkdown('### T\n\nlinha 1\nlinha 2\n\n- a\n- b\n\n1. x\n2. y')
    expect(b.map((x) => x.kind)).toEqual(['heading', 'p', 'ul', 'ol'])
    expect(b[1]).toEqual({ kind: 'p', text: 'linha 1 linha 2' })
    expect(b[2]).toEqual({ kind: 'ul', items: ['a', 'b'] })
  })
})
