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
  report: {
    notFoundTitle: 'Relatório não encontrado',
    notFoundBody: 'Esse relatório não existe ou foi removido.',
    companyLink: 'Ver todos os relatórios de {name}',
    pages: '{n} páginas',
    narrativeTitle: 'Resumo',
    aiSeal: 'Gerado por IA · {model} · {version}',
    heuristicSeal: 'Heurístico · {version}',
    heuristicNote: 'Gerado por regras automáticas, sem IA.',
    numbersWarning: 'Números: confira na tabela de indicadores. Modelos de IA pequenos podem errar valores.',
    structureTitle: 'Estrutura do documento',
    topics: 'Principais assuntos',
    sections: 'Seções mais relevantes',
    sectionPage: 'p. {n}',
    observations: '{sections} seções, {tables} tabelas e {notes} notas explicativas identificadas.',
    structureEmpty: 'Nenhum assunto ou seção foi identificado neste documento.',
    indicatorsTitle: 'Indicadores',
    indicatorsNote: 'Extraídos automaticamente do PDF por regras. Confira no documento original antes de decidir.',
    colMetric: 'Indicador',
    colValue: 'Valor',
    colVariation: 'Variação',
    colPeriod: 'Período',
    colPage: 'Pág.',
    indicatorsEmptyTitle: 'Sem indicadores neste relatório',
    indicatorsEmpty: 'A extração automática não encontrou indicadores em formato reconhecível neste documento (comum em apresentações e teleconferências). O resumo acima continua válido; para os números, consulte o PDF original.',
    noNarrative: 'Este relatório ainda não tem resumo gerado por IA; abaixo está o resumo por regras.',
    transparencyTitle: 'Como este resumo foi feito',
    tMethodNarrative: 'Resumo narrativo',
    tMethodHeuristic: 'Indicadores e estrutura',
    tNarrativeValue: 'IA · {model} · {version} · {date}',
    tHeuristicValue: 'Regras automáticas · {version} · {date}',
    tExtractor: 'Versão da extração',
    tExtractorUnknown: 'não informada',
    tProcessed: 'Processado em',
    tPages: 'Páginas do documento',
    tSource: 'Documento original',
    tSourceLink: 'Abrir',
  },
  company: {
    notFoundTitle: 'Empresa não encontrada',
    notFoundBody: 'Essa empresa não existe ou foi removida.',
    cnpj: 'CNPJ {cnpj}',
    noTickers: 'Sem ticker cadastrado',
    reportsTitle: 'Relatórios',
    reportsEmptyTitle: 'Nenhum relatório ainda',
    reportsEmpty: 'Esta empresa está cadastrada, mas ainda não tem relatório processado.',
    reportMeta: '{pages} páginas · processado em {date}',
    open: 'Abrir relatório',
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

/** Como `t`, trocando `{nome}` pelos valores (ex.: tf('report.pages', { n: 30 })). */
export function tf(key: MessageKey, vars: Record<string, string | number>): string {
  return t(key).replace(/\{(\w+)\}/g, (_, k: string) => String(vars[k] ?? `{${k}}`))
}

export const reportTypeLabels: Record<string, string> = {
  ITR: 'ITR (informações trimestrais)',
  DFP: 'DFP (demonstrações financeiras)',
  EARNINGS_RELEASE: 'Release de resultados',
  FATO_RELEVANTE: 'Fato relevante',
  FORMULARIO_REFERENCIA: 'Formulário de referência',
  OUTRO: 'Outro',
}
