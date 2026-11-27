import { reportTypeLabels } from '../i18n/pt'

/** '3T25' -> '3º trimestre de 2025'. Formato que não é trimestre (9M25, 1S26, lixo) volta como veio. */
export function periodLabel(period: string): string {
  const m = /^([1-4])T(\d{2})$/.exec(period.trim().toUpperCase())
  return m ? `${m[1]}º trimestre de 20${m[2]}` : period
}

export function reportTypeLabel(type: string): string {
  return reportTypeLabels[type] ?? type
}

/**
 * '2025-11-23 14:02:11' (UTC, como o SQLite grava) -> '23/11/2025'.
 * Só reordena o texto: não passa por Date, então não muda de dia por fuso horário.
 */
export function formatDate(stamp: string): string {
  const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(stamp)
  return m ? `${m[3]}/${m[2]}/${m[1]}` : stamp
}

/** Id da URL -> número, ou null se não for um inteiro positivo (nem chega a chamar a API). */
export function parseId(raw: string | undefined): number | null {
  return raw !== undefined && /^[1-9]\d{0,9}$/.test(raw) ? Number(raw) : null
}
