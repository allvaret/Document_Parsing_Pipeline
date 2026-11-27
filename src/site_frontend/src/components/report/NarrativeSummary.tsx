import type { Summary } from '../../api/types'
import { t, tf } from '../../i18n/pt'
import { Markdown } from '../../lib/Markdown'

/**
 * Camada 1: resumo narrativo escrito por IA. Visualmente separado (serifa, fundo de papel
 * mais escuro, filete de latão) e SEMPRE com o selo e o aviso: o modelo de 3B erra números.
 */
export function NarrativeSummary({ summary }: { summary: Summary }) {
  return (
    <section aria-labelledby="resumo-titulo" className="rounded-sm border-l-4 border-brass bg-paper-deep px-6 py-6 sm:px-8">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h2 id="resumo-titulo" className="font-serif text-2xl font-semibold">{t('report.narrativeTitle')}</h2>
        <p className="rounded-sm border border-brass-ink px-2 py-0.5 text-sm font-medium text-brass-ink">
          {tf('report.aiSeal', { model: summary.model, version: summary.prompt_version })}
        </p>
      </div>
      <div className="mt-3 font-serif text-lg leading-relaxed">
        <Markdown text={summary.content_markdown ?? ''} />
      </div>
      <p className="mt-4 border-t border-rule pt-3 text-sm text-ink-soft">{t('report.numbersWarning')}</p>
    </section>
  )
}
