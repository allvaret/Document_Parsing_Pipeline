const STOPWORDS = new Set(['de', 'da', 'do', 'das', 'dos', 'e', 'cia', 'companhia', 'sa', 's.a.', 'ltda'])

/** 'Companhia Energética de Minas Gerais' -> 'EM'; 'Cemig' -> 'CE'; nome vazio -> '?'. */
export function initials(name: string): string {
  const words = name
    .normalize('NFD')
    .replace(/\p{M}/gu, '')
    .split(/[\s.\-/]+/)
    .filter((w) => w && !STOPWORDS.has(w.toLowerCase()))
  if (words.length === 0) return '?'
  if (words.length === 1) return words[0].slice(0, 2).toUpperCase()
  return (words[0][0] + words[1][0]).toUpperCase()
}

/** Matiz 0–359, estável para a mesma chave (ticker, ou nome se não houver ticker). */
export function hueOf(key: string): number {
  let h = 0
  for (const ch of key.toUpperCase()) h = (h * 31 + ch.charCodeAt(0)) >>> 0
  return h % 360
}
