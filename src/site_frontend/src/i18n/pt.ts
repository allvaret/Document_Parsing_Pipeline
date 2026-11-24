// Todos os textos da interface. Para traduzir, copie este arquivo (en.ts) e troque
// os valores; as chaves são tipadas, então uma chave faltando não compila.
// Os RESUMOS (conteúdo gerado) não passam por aqui: tradução deles é v1.1.
export const pt = {
  app: {
    name: 'RQ',
    tagline: 'Resumo qualitativo',
    skipToContent: 'Pular para o conteúdo',
  },
  nav: {
    home: 'Início',
    search: 'Buscar empresa',
    searchPlaceholder: 'Nome ou ticker (ex.: Cemig, PETR4)',
  },
  footer: { disclaimer: 'Conteúdo informativo; não é recomendação de investimento.' },
  state: {
    loading: 'Carregando…',
    emptyTitle: 'Nada por aqui',
    errorTitle: 'Não foi possível carregar',
    errorNetwork: 'Não conseguimos falar com o servidor. Verifique a conexão e tente de novo.',
    errorServer: 'O servidor encontrou um problema. Tente de novo em instantes.',
    retry: 'Tentar de novo',
  },
  notFound: {
    title: 'Página não encontrada',
    body: 'O endereço não existe ou o conteúdo foi removido.',
    back: 'Voltar ao início',
  },
} as const

export type Messages = typeof pt

/** "state.retry" -> texto. Chave inexistente é erro de tipo. */
type Path<T, P extends string = ''> = {
  [K in keyof T & string]: T[K] extends string ? `${P}${K}` : Path<T[K], `${P}${K}.`>
}[keyof T & string]

export type MessageKey = Path<Messages>

export function t(key: MessageKey): string {
  let node: unknown = pt
  for (const part of key.split('.')) node = (node as Record<string, unknown>)[part]
  return node as string
}
