import { t } from '../../i18n/pt'

/**
 * Hero estático: o couro da maleta fechada. A textura é só ambiente (cobre o fundo, sem
 * ladrilhar); o texto fica sobre um escurecimento, então o contraste não depende dela.
 * O fecho de latão é o ÚNICO destaque metálico da página.
 */
export function Hero() {
  return (
    <section aria-labelledby="hero-titulo" className="hero-leather relative flex min-h-[78vh] flex-col items-center justify-center px-4 text-center text-paper">
      <p className="text-sm uppercase tracking-[0.3em] text-brass">{t('app.tagline')}</p>
      <h1 id="hero-titulo" className="mt-3 font-serif text-8xl font-semibold tracking-tight sm:text-9xl">
        {t('app.name')}
      </h1>
      <p className="mt-6 max-w-2xl font-serif text-2xl leading-snug sm:text-3xl">{t('home.heroLead')}</p>
      <p className="mt-3 max-w-xl text-paper/85">{t('home.heroBody')}</p>
      <a href="#busca" className="btn-brass mt-8">{t('home.heroCta')}</a>
      <span aria-hidden className="clasp absolute bottom-0 left-1/2 -translate-x-1/2 translate-y-1/2" />
    </section>
  )
}
