import type { HeuristicSummary, Summary } from '../../api/types'
import { t, tf } from '../../i18n/pt'
import { Empty } from '../Empty'

const MAX_SECTIONS = 6

function Structure({ content }: { content: HeuristicSummary }) {
  const topics = content.principais_assuntos.filter((x) => x.keyword_count > 0)
  const sections = content.secoes_relevantes.slice(0, MAX_SECTIONS)
  if (topics.length === 0 && sections.length === 0) return <Empty title={t('report.structureEmpty')} />
  const obs = content.observacoes
  return (
    <div className="space-y-5">
      {topics.length > 0 && (
        <div>
          <h3 className="text-sm font-semibold uppercase tracking-wide text-ink-soft">{t('report.topics')}</h3>
          <ul className="mt-2 flex flex-wrap gap-2">
            {topics.map((x) => (
              <li key={x.topic} className="rounded-sm border border-rule px-2.5 py-1 text-sm">{x.topic}</li>
            ))}
          </ul>
        </div>
      )}
      {sections.length > 0 && (
        <div>
          <h3 className="text-sm font-semibold uppercase tracking-wide text-ink-soft">{t('report.sections')}</h3>
          <ol className="mt-2 space-y-3">
            {sections.map((s) => (
              <li key={s.rank}>
                <p className="font-medium">
                  {s.title}
                  <span className="ml-2 text-sm font-normal text-ink-soft">{tf('report.sectionPage', { n: s.page })}</span>
                </p>
                {s.description && <p className="line-clamp-3 text-ink-soft">{s.description}</p>}
              </li>
            ))}
          </ol>
        </div>
      )}
      <p className="text-sm text-ink-soft">
        {tf('report.observations', { sections: obs.total_secoes, tables: obs.total_tabelas, notes: obs.total_notas_explicativas })}
      </p>
    </div>
  )
}

/**
 * Camada 1 alternativa (quando NÃO há resumo de IA): o heurístico ocupa o lugar do resumo, com o
 * selo "Heurístico · versão". Havendo IA, ele aparece recolhido como "Estrutura do documento".
 */
export function HeuristicBlock({ summary, main }: { summary: Summary; main: boolean }) {
  const content = summary.content_json
  if (!content) return null
  if (!main) {
    return (
      <details className="rounded-sm border border-rule px-6 py-4">
        <summary className="cursor-pointer font-serif text-xl font-semibold">{t('report.structureTitle')}</summary>
        <div className="mt-4"><Structure content={content} /></div>
      </details>
    )
  }
  return (
    <section aria-labelledby="resumo-titulo" className="rounded-sm border-l-4 border-ink-soft bg-paper-deep px-6 py-6 sm:px-8">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h2 id="resumo-titulo" className="font-serif text-2xl font-semibold">{t('report.narrativeTitle')}</h2>
        <p className="rounded-sm border border-ink-soft px-2 py-0.5 text-sm font-medium text-ink-soft">
          {tf('report.heuristicSeal', { version: summary.prompt_version })}
        </p>
      </div>
      <p className="mt-2 text-sm text-ink-soft">{t('report.noNarrative')} {t('report.heuristicNote')}</p>
      <div className="mt-4"><Structure content={content} /></div>
    </section>
  )
}
