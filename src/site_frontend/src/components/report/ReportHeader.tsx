import { Link } from 'react-router-dom'
import type { ReportDetail } from '../../api/types'
import { tf } from '../../i18n/pt'
import { periodLabel, reportTypeLabel } from '../../lib/format'
import { CompanyMark } from '../CompanyMark'

export function ReportHeader({ detail }: { detail: ReportDetail }) {
  const { company, report } = detail
  return (
    <header className="flex flex-wrap items-center gap-5 border-b border-rule pb-6">
      <CompanyMark name={company.name} tickers={company.tickers} size={72} />
      <div className="min-w-0">
        <p className="text-sm text-ink-soft">
          <Link to={`/empresas/${company.id}`} className="underline">
            {tf('report.companyLink', { name: company.name })}
          </Link>
        </p>
        <h1 className="font-serif text-3xl font-semibold leading-tight text-ink sm:text-4xl">
          {company.name}
          {company.tickers.length > 0 && (
            <span className="ml-3 align-middle font-sans text-base font-medium text-ink-soft">
              {company.tickers.join(' · ')}
            </span>
          )}
        </h1>
        <p className="mt-1 text-lg text-ink">
          {reportTypeLabel(report.report_type)} · {periodLabel(report.period)}
          <span className="text-ink-soft"> · {tf('report.pages', { n: report.page_count })}</span>
        </p>
      </div>
    </header>
  )
}
