import { useEffect } from 'react'
import { Link, useParams } from 'react-router-dom'
import { ApiError } from '../api/client'
import { getCompany, listCompanyReports } from '../api/endpoints'
import { CompanyMark } from '../components/CompanyMark'
import { Empty } from '../components/Empty'
import { ErrorState } from '../components/ErrorState'
import { Loading } from '../components/Loading'
import { useAsync } from '../hooks/useAsync'
import { t, tf } from '../i18n/pt'
import { formatDate, parseId, periodLabel, reportTypeLabel } from '../lib/format'
import { formatCnpj, groupByPeriod } from '../lib/group'

function CompanyNotFound() {
  return (
    <Empty title={t('company.notFoundTitle')}>
      <p>{t('company.notFoundBody')}</p>
      <Link to="/" className="btn mt-4 inline-block">{t('notFound.back')}</Link>
    </Empty>
  )
}

export function CompanyPage() {
  const id = parseId(useParams().id)
  // Empresa e relatórios em paralelo: uma falha em qualquer um vira um único estado de erro.
  const { state, reload } = useAsync(async (signal) => {
    if (id === null) return null
    const [company, reports] = await Promise.all([getCompany(id, signal), listCompanyReports(id, signal)])
    return { company, reports }
  }, [id])

  const name = state.status === 'success' ? state.data?.company.name : undefined
  useEffect(() => { document.title = name ? `${name} · RQ` : 'RQ' }, [name])

  if (id === null) return <CompanyNotFound />
  if (state.status === 'loading') return <Loading />
  if (state.status === 'error') {
    if (state.error instanceof ApiError && state.error.notFound) return <CompanyNotFound />
    return <ErrorState error={state.error} onRetry={reload} />
  }
  if (state.data === null) return <CompanyNotFound />

  const { company, reports } = state.data
  const groups = groupByPeriod(reports)

  return (
    <article className="space-y-8">
      <header className="flex flex-wrap items-center gap-5 border-b border-rule pb-6">
        <CompanyMark name={company.name} tickers={company.tickers} size={72} />
        <div className="min-w-0">
          <h1 className="font-serif text-3xl font-semibold leading-tight text-ink sm:text-4xl">{company.name}</h1>
          <p className="mt-1 text-ink-soft">
            {company.tickers.length > 0 ? company.tickers.join(' · ') : t('company.noTickers')}
            {company.cnpj && <span className="tabular-nums"> · {tf('company.cnpj', { cnpj: formatCnpj(company.cnpj) })}</span>}
          </p>
        </div>
      </header>

      <section aria-labelledby="relatorios-titulo">
        <h2 id="relatorios-titulo" className="font-serif text-2xl font-semibold">{t('company.reportsTitle')}</h2>
        {groups.length === 0 ? (
          <div className="mt-3"><Empty title={t('company.reportsEmptyTitle')}>{t('company.reportsEmpty')}</Empty></div>
        ) : (
          <ol className="mt-4 space-y-6 border-l-2 border-rule pl-6">
            {groups.map((g) => (
              <li key={g.period} className="relative">
                <span aria-hidden className="absolute -left-[1.9rem] top-2 size-3 rounded-full bg-brass ring-4 ring-paper" />
                <h3 className="font-serif text-xl font-semibold">{periodLabel(g.period)}</h3>
                <ul className="mt-2 space-y-2">
                  {g.items.map((r) => (
                    <li key={r.id}>
                      <Link
                        to={`/relatorios/${r.id}`}
                        className="block rounded-sm border border-rule bg-paper-deep px-4 py-3 hover:border-ink"
                      >
                        <span className="font-medium text-ink underline">{reportTypeLabel(r.report_type)}</span>
                        <span className="block text-sm text-ink-soft tabular-nums">
                          {tf('company.reportMeta', { pages: r.page_count, date: formatDate(r.parsed_at) })}
                        </span>
                      </Link>
                    </li>
                  ))}
                </ul>
              </li>
            ))}
          </ol>
        )}
      </section>
    </article>
  )
}
