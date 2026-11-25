import type { FieldInfo } from '../api/types'

/** '1,69' / '1.234,56' / '5' -> número; qualquer outra coisa -> null. Aceita vírgula (pt-BR). */
export function parseDecimal(raw: string): number | null {
  const s = raw.trim().replace(/\s/g, '')
  if (!s) return null
  let normalized: string
  if (s.includes(',')) {
    // vírgula decimal; pontos antes dela são separador de milhar
    if (!/^-?\d{1,3}(\.\d{3})*,\d+$|^-?\d+,\d+$/.test(s)) return null
    normalized = s.replace(/\./g, '').replace(',', '.')
  } else {
    if (!/^-?\d+(\.\d+)?$/.test(s)) return null
    normalized = s
  }
  const n = Number(normalized)
  return Number.isFinite(n) ? n : null
}

export type FormErrors = Record<string, string>

/**
 * Valores digitados -> corpo da API. Percentual vira fração (8 -> 0,08). Campo opcional
 * vazio não vai no corpo (a API usa o padrão). Devolve os erros por campo, sem chamar a API.
 */
export function buildPayload(fields: FieldInfo[], values: Record<string, string>) {
  const premises: Record<string, number> = {}
  const errors: FormErrors = {}
  for (const f of fields) {
    const raw = values[f.nome] ?? ''
    if (!raw.trim()) {
      if (f.obrigatorio) errors[f.nome] = 'Preencha este campo.'
      continue
    }
    const n = parseDecimal(raw)
    if (n === null) errors[f.nome] = 'Digite um número, como 1,69.'
    else if (n < 0) errors[f.nome] = 'Use um valor positivo.'
    else premises[f.nome] = f.unidade === 'percentual' ? n / 100 : n
  }
  return { premises, errors }
}

/** Quanto o preço teto está acima (+) ou abaixo (−) da cotação, em %. */
export function marginOfSafety(ceiling: number, price: number): number {
  return (ceiling / price - 1) * 100
}

const brl = new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' })
export const formatBRL = (n: number) => brl.format(n)

/** Texto do campo pronto para o input: 5.5 -> '5,5'. */
export const toInput = (n: number) => String(n).replace('.', ',')
