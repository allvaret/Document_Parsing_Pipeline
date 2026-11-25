import type { Keypoint } from '../../api/types'
import { t } from '../../i18n/pt'
import { Empty } from '../Empty'

/**
 * Camada 2: indicadores. É a camada de fato (extraída por regras, determinística; o LLM nunca
 * toca nos números). Sem keypoints, explica o porquê em vez de mostrar uma tabela vazia.
 * Não "corrige" valor/variação trocados (problema conhecido da heurística): mostra o que há.
 */
export function IndicatorsTable({ keypoints }: { keypoints: Keypoint[] }) {
  return (
    <section aria-labelledby="indicadores-titulo">
      <h2 id="indicadores-titulo" className="font-serif text-2xl font-semibold">{t('report.indicatorsTitle')}</h2>
      {keypoints.length === 0 ? (
        <div className="mt-3">
          <Empty title={t('report.indicatorsEmptyTitle')}>{t('report.indicatorsEmpty')}</Empty>
        </div>
      ) : (
        <>
          <p className="mt-1 text-sm text-ink-soft">{t('report.indicatorsNote')}</p>
          <div className="mt-3 overflow-x-auto rounded-sm border border-rule">
            <table className="w-full min-w-[32rem] border-collapse text-left tabular-nums">
              <caption className="sr-only">{t('report.indicatorsTitle')}</caption>
              <thead className="bg-paper-deep text-sm">
                <tr>
                  <th scope="col" className="px-4 py-2 font-semibold">{t('report.colMetric')}</th>
                  <th scope="col" className="px-4 py-2 text-right font-semibold">{t('report.colValue')}</th>
                  <th scope="col" className="px-4 py-2 text-right font-semibold">{t('report.colVariation')}</th>
                  <th scope="col" className="px-4 py-2 font-semibold">{t('report.colPeriod')}</th>
                  <th scope="col" className="px-4 py-2 text-right font-semibold">{t('report.colPage')}</th>
                </tr>
              </thead>
              <tbody>
                {keypoints.map((k, i) => (
                  <tr key={`${k.metric}-${i}`} className="border-t border-rule">
                    <th scope="row" className="px-4 py-2 font-medium">{k.metric}</th>
                    <td className="px-4 py-2 text-right">{k.value_text}</td>
                    <td className="px-4 py-2 text-right">{k.variation_text ?? '—'}</td>
                    <td className="px-4 py-2">{k.period ?? '—'}</td>
                    <td className="px-4 py-2 text-right">{k.page ?? '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </section>
  )
}
