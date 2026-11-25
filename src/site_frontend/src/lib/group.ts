/** Agrupa mantendo a ordem em que a API devolveu (já é do período mais recente ao mais antigo). */
export function groupByPeriod<T extends { period: string }>(items: T[]): { period: string; items: T[] }[] {
  const groups: { period: string; items: T[] }[] = []
  for (const item of items) {
    const last = groups[groups.length - 1]
    if (last && last.period === item.period) last.items.push(item)
    else groups.push({ period: item.period, items: [item] })
  }
  return groups
}

/** '17155730000164' -> '17.155.730/0001-64'. Qualquer outra coisa volta como veio. */
export function formatCnpj(digits: string): string {
  const m = /^(\d{2})(\d{3})(\d{3})(\d{4})(\d{2})$/.exec(digits)
  return m ? `${m[1]}.${m[2]}.${m[3]}/${m[4]}-${m[5]}` : digits
}
