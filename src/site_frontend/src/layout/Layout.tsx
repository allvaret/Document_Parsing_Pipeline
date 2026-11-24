import { Link, Outlet, useLocation } from 'react-router-dom'
import { SearchBox } from '../components/SearchBox'
import { t } from '../i18n/pt'

export function Layout() {
  const home = useLocation().pathname === '/'
  return (
    <div className="flex min-h-dvh flex-col">
      <a href="#conteudo" className="skip-link">{t('app.skipToContent')}</a>
      {/* Na home o hero já é a marca e a busca está na página; nas demais, header compacto. */}
      {!home && (
        <header className="border-b border-rule">
          <div className="mx-auto flex max-w-5xl items-center justify-between gap-4 px-4 py-3">
            <Link
              to="/"
              className="font-serif text-2xl font-semibold tracking-tight text-ink"
              aria-label={`${t('app.name')} · ${t('nav.home')}`}
            >
              {t('app.name')}
            </Link>
            <SearchBox variant="compact" />
          </div>
        </header>
      )}
      <main id="conteudo" className={home ? 'flex-1' : 'mx-auto w-full max-w-5xl flex-1 px-4 py-8'}>
        <Outlet />
      </main>
      <footer className="border-t border-rule">
        <p className="mx-auto max-w-5xl px-4 py-4 text-sm text-ink-soft">{t('footer.disclaimer')}</p>
      </footer>
    </div>
  )
}
