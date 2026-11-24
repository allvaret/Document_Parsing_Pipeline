import { useEffect } from 'react'
import { Link, useParams } from 'react-router-dom'
import { ApiError } from '../api/client'
import { getReport } from '../api/endpoints'
import { Empty } from '../components/Empty'
import { ErrorState } from '../components/ErrorState'
import { Loading } from '../components/Loading'
import { HeuristicBlock } from '../components/report/HeuristicBlock'
import { IndicatorsTable } from '../components/report/IndicatorsTable'
import { NarrativeSummary } from '../components/report/NarrativeSummary'
import { ReportHeader } from '../components/report/ReportHeader'
import { TransparencyBlock } from '../components/report/TransparencyBlock'
import { useAsync } from '../hooks/useAsync'
import { t } from '../i18n/pt'
import { parseId } from '../lib/format'

function ReportNotFound() {
  return (
    <Empty title={t('report.notFoundTitle')}>
      <p>{t('report.notFoundBody')}</p>
      <Link to="/" className="btn mt-4 inline-block">{t('notFound.back')}</Link>
    </Empty>
  )
}

export function ReportPage() {
  const id = parseId(useParams().id)
  // Id que não é inteiro positivo nem chega à API: 404 direto.
  const { state, reload } = useAsync((signal) => (id === null ? Promise.resolve(null) : getReport(id, signal)), [id])

  const title = state.status === 'success' && state.data
    ? `${state.data.company.name} · ${state.data.report.period} · RQ`
    : 'RQ'
  useEffect(() => { document.title = title }, [title])

  if (id === null) return <ReportNotFound />
  if (state.status === 'loading') return <Loading />
  if (state.status === 'error') {
    if (state.error instanceof ApiError && state.error.notFound) return <ReportNotFound />
    return <ErrorState error={state.error} onRetry={reload} />
  }
  const detail = state.data
  if (detail === null) return <ReportNotFound />

  const llm = detail.summaries.find((s) => s.method === 'llm' && s.content_markdown)
  const heuristic = detail.summaries.find((s) => s.method === 'heuristic')

  return (
    <article className="space-y-8">
      <ReportHeader detail={detail} />
      {/* Camada 1: com IA, o narrativo; sem IA, o heurístico no lugar dele (sem buraco). */}
      {llm ? <NarrativeSummary summary={llm} /> : heuristic && <HeuristicBlock summary={heuristic} main />}
      {/* Camada 2: a tabela é a camada de fato. */}
      <IndicatorsTable keypoints={detail.keypoints} />
      {llm && heuristic && <HeuristicBlock summary={heuristic} main={false} />}
      <TransparencyBlock detail={detail} />
    </article>
  )
}
