import { Fragment, type ReactNode } from 'react'
import { parseMarkdown } from './parseMarkdown'

/**
 * Renderizador mínimo do Markdown que o LLM devolve: títulos, listas (- * 1.), parágrafos
 * e **negrito**. Monta elementos React (nunca HTML em string): o texto vem de um modelo e
 * é tratado como não confiável; `<script>` aparece como texto.
 * Títulos viram <h3>: o <h1>/<h2> da página já existem, e o outline não pode pular níveis.
 */

function inline(text: string): ReactNode[] {
  return text.split(/(\*\*[^*]+\*\*)/g).map((part, i) =>
    part.startsWith('**') && part.endsWith('**') && part.length > 4
      ? <strong key={i}>{part.slice(2, -2)}</strong>
      : <Fragment key={i}>{part}</Fragment>,
  )
}

export function Markdown({ text }: { text: string }) {
  return (
    <>
      {parseMarkdown(text).map((b, i) => {
        switch (b.kind) {
          case 'heading':
            return <h3 key={i} className="mt-6 mb-2 text-xl font-semibold first:mt-0">{inline(b.text)}</h3>
          case 'ul':
            return (
              <ul key={i} className="my-3 list-disc space-y-1.5 pl-6">
                {b.items.map((it, j) => <li key={j}>{inline(it)}</li>)}
              </ul>
            )
          case 'ol':
            return (
              <ol key={i} className="my-3 list-decimal space-y-1.5 pl-6">
                {b.items.map((it, j) => <li key={j}>{inline(it)}</li>)}
              </ol>
            )
          default:
            return <p key={i} className="my-3">{inline(b.text)}</p>
        }
      })}
    </>
  )
}
