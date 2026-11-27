// Parser do Markdown mínimo do LLM (ver Markdown.tsx). Separado: a regra do React
// só quer componentes em arquivo de componente.

export type Block =
  | { kind: 'heading'; text: string }
  | { kind: 'ul' | 'ol'; items: string[] }
  | { kind: 'p'; text: string }

const HEADING = /^#{1,6}\s+(.*)$/
const BULLET = /^\s*[-*+]\s+(.*)$/
const NUMBERED = /^\s*\d+[.)]\s+(.*)$/

export function parseMarkdown(source: string): Block[] {
  const blocks: Block[] = []
  let para: string[] = []
  const flush = () => {
    if (para.length) blocks.push({ kind: 'p', text: para.join(' ') })
    para = []
  }
  for (const raw of source.replace(/\r\n/g, '\n').split('\n')) {
    const line = raw.trimEnd()
    let m: RegExpExecArray | null
    if (!line.trim()) {
      flush()
    } else if ((m = HEADING.exec(line))) {
      flush()
      blocks.push({ kind: 'heading', text: m[1].trim() })
    } else if ((m = BULLET.exec(line))) {
      flush()
      const last = blocks[blocks.length - 1]
      if (last?.kind === 'ul') last.items.push(m[1].trim())
      else blocks.push({ kind: 'ul', items: [m[1].trim()] })
    } else if ((m = NUMBERED.exec(line))) {
      flush()
      const last = blocks[blocks.length - 1]
      if (last?.kind === 'ol') last.items.push(m[1].trim())
      else blocks.push({ kind: 'ol', items: [m[1].trim()] })
    } else {
      para.push(line.trim())
    }
  }
  flush()
  return blocks
}

