import { describe, expect, it } from 'vitest'
import type { FieldInfo } from '../api/types'
import { buildPayload, formatBRL, marginOfSafety, parseDecimal } from './calculadora'

const field = (over: Partial<FieldInfo>): FieldInfo => ({
  nome: 'x', rotulo: 'X', unidade: 'moeda', ajuda: '', obrigatorio: true, padrao: null, exemplo: 1, ...over,
})

describe('parseDecimal', () => {
  it.each([
    ['1,69', 1.69], ['5', 5], ['0.5', 0.5], ['1.234,56', 1234.56], [' 7,83 ', 7.83], ['1234,5', 1234.5],
  ])('%s -> %s', (raw, n) => expect(parseDecimal(raw)).toBe(n))

  it.each(['', 'abc', '1,2,3', '1..2', '1.234.567', '--1', 'NaN', 'Infinity', '1e5', '1,', ',5', '<script>'])(
    'recusa %j',
    (raw) => expect(parseDecimal(raw)).toBeNull(),
  )
})

describe('buildPayload', () => {
  const campos = [
    field({ nome: 'dpa' }),
    field({ nome: 'dy_minimo', unidade: 'percentual', obrigatorio: false, padrao: 0.06 }),
  ]

  it('percentual vira fração e opcional vazio fica de fora', () => {
    expect(buildPayload(campos, { dpa: '1,36', dy_minimo: '8' }).premises).toEqual({ dpa: 1.36, dy_minimo: 0.08 })
    expect(buildPayload(campos, { dpa: '1,36', dy_minimo: '' }).premises).toEqual({ dpa: 1.36 })
  })

  it('obrigatório vazio, texto e negativo viram erro por campo', () => {
    expect(buildPayload(campos, {}).errors).toEqual({ dpa: 'Preencha este campo.' })
    expect(buildPayload(campos, { dpa: 'abc' }).errors.dpa).toMatch(/número/)
    expect(buildPayload(campos, { dpa: '-1' }).errors.dpa).toMatch(/positivo/)
  })
})

it('margem de segurança: teto acima da cotação é positiva', () => {
  expect(marginOfSafety(20, 10)).toBe(100)
  expect(marginOfSafety(10, 20)).toBe(-50)
})

it('formata em reais', () => {
  expect(formatBRL(1234.5).replace(/\s/g, ' ')).toBe('R$ 1.234,50')
})
