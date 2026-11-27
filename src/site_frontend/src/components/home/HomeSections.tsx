import { Link } from 'react-router-dom'
import { latestReports, listAllCompanies } from '../../api/endpoints'
import { useAsync } from '../../hooks/useAsync'
import { t } from '../../i18n/pt'
import { formatDate, periodLabel, reportTypeLabel } from '../../lib/format'
import { CompanyMark } from '../CompanyMark'
import { Empty } from '../Empty'
import { ErrorState } from '../ErrorState'
import { Loading } from '../Loading'

/** Os estados usam cores de tinta (escuras): sobre o veludo precisam de um cartão de papel. */
function OnPaper({ children }: { children: React.ReactNode }) {
  return <div className="mt-4 rounded-sm bg-paper px-4 text-ink">{children}</div>
}

const cardClass = 'flex items-center gap-4 rounded-sm bg-paper px-4 py-3 text-ink hover:bg-paper-deep'

const LATEST_LIMIT = 3 // só os 3 mais recentes na home

/** Cada seção busca e falha sozinha: erro nos últimos relatórios não derruba a grade. */
export function LatestReports() {
  const { state, reload } = useAsync((signal) => latestReports(LATEST_LIMIT, signal), [])
  return (
    <section aria-labelledby="ultimos-titulo">
      <h2 id="ultimos-titulo" className="section-title">{t('home.latestTitle')}</h2>
      {state.status === 'loading' && <OnPaper><Loading /></OnPaper>}
      {state.status === 'error' && <OnPaper><ErrorState error={state.error} onRetry={reload} /></OnPaper>}
      {state.status === 'success' && state.data.length === 0 && <OnPaper><Empty title={t('home.latestEmpty')} /></OnPaper>}
      {state.status === 'success' && state.data.length > 0 && (
        <ul className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {state.data.map((r) => (
            <li key={r.id}>
              <Link to={`/relatorios/${r.id}`} className={cardClass}>
                <CompanyMark name={r.company_name} tickers={r.tickers} size={44} />
                <span className="min-w-0">
                  <span className="block truncate font-serif text-lg font-semibold">{r.company_name}</span>
                  <span className="block text-sm text-ink-soft">
                    {reportTypeLabel(r.report_type)} · {periodLabel(r.period)}
                  </span>
                  <span className="block text-sm text-ink-soft tabular-nums">{formatDate(r.parsed_at)}</span>
                </span>
              </Link>
            </li>
          ))}
        </ul>
      )}
    </section>
  )
}

export function CompanyGrid() {
  const { state, reload } = useAsync((signal) => listAllCompanies(signal), [])
  return (
    <section aria-labelledby="empresas-titulo">
      <h2 id="empresas-titulo" className="section-title">{t('home.companiesTitle')}</h2>
      {state.status === 'loading' && <OnPaper><Loading /></OnPaper>}
      {state.status === 'error' && <OnPaper><ErrorState error={state.error} onRetry={reload} /></OnPaper>}
      {state.status === 'success' && state.data.length === 0 && <OnPaper><Empty title={t('home.companiesEmpty')} /></OnPaper>}
      {state.status === 'success' && state.data.length > 0 && (
        <ul className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {state.data.map((c) => (
            <li key={c.id}>
              <Link to={`/empresas/${c.id}`} className={cardClass}>
                <CompanyMark name={c.name} tickers={c.tickers} size={44} />
                <span className="min-w-0">
                  <span className="block truncate font-serif text-lg font-semibold">{c.name}</span>
                  <span className="block text-sm text-ink-soft">
                    {c.tickers.length > 0 ? c.tickers.join(' · ') : t('company.noTickers')}
                  </span>
                </span>
              </Link>
            </li>
          ))}
        </ul>
      )}
    </section>
  )
}

const STEPS = [
  ['home.step1', 'home.step1Body'],
  ['home.step2', 'home.step2Body'],
  ['home.step3', 'home.step3Body'],
  ['home.step4', 'home.step4Body'],
  ['home.step5', 'home.step5Body'],
] as const

export function HowItWorks() {
  return (
    <section aria-labelledby="como-titulo">
      <h2 id="como-titulo" className="section-title">{t('home.howTitle')}</h2>
      <ol aria-label={t('home.howSteps')} className="mt-4 grid gap-4 sm:grid-cols-2 lg:grid-cols-5">
        {STEPS.map(([title, body], i) => (
          <li key={title} className="border-t border-brass pt-3 text-paper">
            <span aria-hidden className="font-serif text-brass tabular-nums">{i + 1}</span>
            <p className="font-serif text-xl font-semibold">{t(title)}</p>
            <p className="mt-1 text-sm text-paper/85">{t(body)}</p>
          </li>
        ))}
      </ol>
    </section>
  )
}
