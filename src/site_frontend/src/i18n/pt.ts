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
  footer: {
    disclaimer: 'Conteúdo informativo, gerado a partir de relatórios públicos das companhias; não é recomendação de investimento.',
    credit: 'Desenvolvido por Alvaro Danko',
  },
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
  home: {
    heroLead: 'Entenda os relatórios de resultados das empresas da B3.',
    heroBody: 'Resumos claros, números conferíveis na tabela e transparência sobre como cada texto foi feito.',
    heroCta: 'Buscar uma empresa',
    tabsLabel: 'Tipo de ativo',
    tabStocks: 'Ações',
    tabFiis: 'FIIs · em breve',
    latestTitle: 'Últimos relatórios',
    latestEmpty: 'Nenhum relatório processado ainda.',
    companiesTitle: 'Empresas disponíveis',
    companiesEmpty: 'Nenhuma empresa cadastrada ainda.',
    howTitle: 'Como funciona',
    howSteps: 'Do PDF ao site',
    step1: 'PDF',
    step1Body: 'O relatório de resultados, como a empresa o publicou.',
    step2: 'Processamento',
    step2Body: 'Um script local extrai seções e indicadores e gera o resumo, uma única vez.',
    step3: 'Banco',
    step3Body: 'O resultado é gravado. Rodar de novo não duplica nada.',
    step4: 'API',
    step4Body: 'O servidor só lê o banco. Nenhuma consulta chama IA.',
    step5: 'Site',
    step5Body: 'Você lê o resumo e confere os números.',
  },
  search: {
    label: 'Buscar empresa por nome ou ticker',
    searching: 'Buscando…',
    none: 'Nenhuma empresa encontrada.',
    error: 'Não foi possível buscar agora.',
    count: '{n} resultados',
    countOne: '1 resultado',
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
  calc: {
    nav: 'Calculadora',
    title: 'Calculadora de preço teto',
    intro: 'Escolha um método, informe as premissas e veja o preço máximo que ele sugere pagar. A conta roda no servidor e nada do que você digita é guardado.',
    methodLabel: 'Método',
    stocks: 'Ações',
    fiis: 'Fundos imobiliários',
    formula: 'Fórmula',
    premises: 'Premissas',
    optional: '(opcional)',
    defaultHint: 'Se vazio, usa {value}.',
    example: 'ex.: {value}',
    priceLabel: 'Cotação atual',
    priceHelp: 'Informe para ver a margem em relação ao preço teto.',
    submit: 'Calcular',
    resultTitle: 'Preço teto',
    marginBelow: 'A cotação está {pct}% abaixo do teto.',
    marginAbove: 'A cotação está {pct}% acima do teto: o método não sugere comprar a esse preço.',
    marginEqual: 'A cotação está no preço teto.',
    warning: 'Resultado de um modelo simplificado, que depende das premissas que você informou. Não é recomendação de investimento.',
    formErrors: 'Corrija os campos destacados.',
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
  RELATORIO_ADMINISTRACAO: 'Relatório da administração',
  OUTRO: 'Outro',
}
