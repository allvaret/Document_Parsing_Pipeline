import type { ReportDetail } from '../../api/types'
import { t, tf } from '../../i18n/pt'
import { formatDate } from '../../lib/format'

/** Método, modelo, versões e data: tudo o que permite saber COMO o conteúdo foi produzido. */
export function TransparencyBlock({ detail }: { detail: ReportDetail }) {
  const { report, summaries } = detail
  const llm = summaries.find((s) => s.method === 'llm')
  const heuristic = summaries.find((s) => s.method === 'heuristic')
  const rows: [string, React.ReactNode][] = []
  if (llm) {
    rows.push([t('report.tMethodNarrative'), tf('report.tNarrativeValue', {
      model: llm.model, version: llm.prompt_version, date: formatDate(llm.created_at),
    })])
  }
  if (heuristic) {
    rows.push([t('report.tMethodHeuristic'), tf('report.tHeuristicValue', {
      version: heuristic.prompt_version, date: formatDate(heuristic.created_at),
    })])
  }
  rows.push(
    [t('report.tExtractor'), report.extractor_version || t('report.tExtractorUnknown')],
    [t('report.tProcessed'), formatDate(report.parsed_at)],
    [t('report.tPages'), String(report.page_count)],
  )
  if (report.source_url && /^https?:\/\//i.test(report.source_url)) {
    rows.push([t('report.tSource'), (
      <a key="src" href={report.source_url} target="_blank" rel="noopener noreferrer" className="underline">
        {t('report.tSourceLink')}
      </a>
    )])
  }
  return (
    <section aria-labelledby="transparencia-titulo" className="border-t border-rule pt-6">
      <h2 id="transparencia-titulo" className="font-serif text-xl font-semibold">{t('report.transparencyTitle')}</h2>
      <dl className="mt-3 grid grid-cols-1 gap-x-8 gap-y-2 text-sm sm:grid-cols-[max-content_1fr]">
        {rows.map(([label, value]) => (
          <div key={label} className="contents">
            <dt className="text-ink-soft">{label}</dt>
            <dd className="tabular-nums">{value}</dd>
          </div>
        ))}
      </dl>
    </section>
  )
}
