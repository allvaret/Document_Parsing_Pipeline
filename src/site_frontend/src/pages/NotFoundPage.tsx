import { Link } from 'react-router-dom'
import { t } from '../i18n/pt'

export function NotFoundPage() {
  return (
    <section className="py-16 text-center">
      <h1 className="font-serif text-4xl text-ink">{t('notFound.title')}</h1>
      <p className="mt-2 text-ink-soft">{t('notFound.body')}</p>
      <Link to="/" className="btn mt-6 inline-block">{t('notFound.back')}</Link>
    </section>
  )
}
