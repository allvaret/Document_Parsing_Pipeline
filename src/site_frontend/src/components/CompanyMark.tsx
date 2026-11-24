import { useState } from 'react'
import { hueOf, initials } from '../lib/mark'

/** Formatos aceitos em public/logos/{TICKER}.<ext>, na ordem de tentativa. */
const EXTENSIONS = ['svg', 'png'] as const

/** Ticker da B3: letras e dígitos. Barra qualquer coisa estranha antes de virar caminho de arquivo. */
const TICKER = /^[A-Z0-9]{4,6}$/

/** Logos que já falharam nesta sessão: não repete requisição por card. */
const missing = new Set<string>()

/**
 * Marca da empresa: logo estático em `public/logos/{TICKER}.svg|png` (nada é buscado na web)
 * e, se não houver arquivo ou ele falhar, o monograma (iniciais + cor derivada do ticker,
 * ou do nome se a empresa não tem ticker).
 * Decorativa: o nome da empresa sempre aparece ao lado, então o alt é vazio.
 */
export function CompanyMark({ name, tickers, size = 56 }: { name: string; tickers: string[]; size?: number }) {
  const ticker = tickers[0]?.toUpperCase()
  const candidates = ticker && TICKER.test(ticker)
    ? EXTENSIONS.map((ext) => `${ticker}.${ext}`).filter((f) => !missing.has(f))
    : []
  const [failed, setFailed] = useState<string[]>([])
  const file = candidates.find((f) => !failed.includes(f))

  if (file) {
    return (
      <img
        src={`/logos/${file}`}
        alt=""
        width={size}
        height={size}
        loading="lazy"
        onError={() => {
          missing.add(file)
          setFailed((f) => [...f, file])
        }}
        // Fundo de papel: logos com transparência ficam legíveis sobre o cartão.
        className="shrink-0 rounded-sm bg-white object-contain p-1"
        style={{ width: size, height: size }}
      />
    )
  }

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
