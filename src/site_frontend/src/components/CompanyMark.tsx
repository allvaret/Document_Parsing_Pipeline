import { hueOf, initials } from '../lib/mark'

/**
 * Marca da empresa. Por ora só o monograma (iniciais + cor derivada do ticker, ou do nome
 * se a empresa não tem ticker). O logo estático (public/logos/{TICKER}) entra no passo 6.
 * Decorativo: o nome da empresa sempre aparece ao lado, então o alt é vazio.
 */
export function CompanyMark({ name, tickers, size = 56 }: { name: string; tickers: string[]; size?: number }) {
  const hue = hueOf(tickers[0] ?? name)
  return (
    <span
      aria-hidden
      className="inline-flex shrink-0 items-center justify-center rounded-sm font-serif font-semibold text-paper"
      // Luminosidade baixa e fixa: texto claro mantém contraste AA com qualquer matiz.
      style={{ width: size, height: size, fontSize: size * 0.4, background: `hsl(${hue} 35% 24%)` }}
    >
      {initials(name)}
    </span>
  )
}
