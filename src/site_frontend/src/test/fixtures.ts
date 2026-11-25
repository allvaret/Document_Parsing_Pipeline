import type { ReportDetail, Summary } from '../api/types'

export const heuristicSummary: Summary = {
  method: 'heuristic', model: 'heuristic', prompt_version: 'heuristic-v2',
  created_at: '2026-11-23 10:00:00', content_format: 'json', content_markdown: null,
  content_json: {
    header: { empresa: 'Cemig', periodo: '1T26', num_paginas: 30 },
    principais_assuntos: [{ topic: 'Resultado', matched_sections: [0], keyword_count: 3 }],
    secoes_relevantes: [{ rank: 1, title: 'Destaques do trimestre', page: 2, description: 'Resumo dos destaques.', relevance_score: 0.9 }],
    indicadores: [],
    observacoes: { total_secoes: 12, total_tabelas: 4, total_notas_explicativas: 1, secoes_alta_confianca: 5, extras: [] },
  },
}

export const llmSummary: Summary = {
  method: 'llm', model: 'ollama:qwen2.5:3b', prompt_version: 'prompt-v1',
  created_at: '2026-11-23 11:30:00', content_format: 'markdown', content_json: null,
  content_markdown: '### Resumo Executivo\n\nA **receita** subiu.\n\n- **Lucro:** R$ 10 mi\n- Margem estável',
}

export function reportDetail(over: Partial<ReportDetail> = {}): ReportDetail {
  return {
    report: {
      id: 2, report_type: 'EARNINGS_RELEASE', period: '1T26', page_count: 30,
      parsed_at: '2026-11-23 10:00:00', source_url: null, extractor_version: 'heuristic-v2',
    },
    company: { id: 7, name: 'Cemig', kind: 'ACAO', cnpj: null, tickers: [] },
    keypoints: [
      { metric: 'Receita Líquida', value_text: 'R$ 1,2 bi', value_numeric: null, variation_text: '+5%', period: '1T26', page: 3 },
    ],
    summaries: [heuristicSummary, llmSummary],
    ...over,
  }
}

export function jsonResponse(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } })
}
